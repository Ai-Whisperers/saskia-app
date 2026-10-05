"""Tier 8.2 (2026-10-01) — Resend email send path.

We test that ``send_alert``:
- No-ops cleanly when ``RESEND_API_KEY`` is unset (returns True).
- Logs but does not POST when ``ALERT_EMAIL_DRY_RUN=1``.
- POSTs the right shape to Resend when an API key is set (mocked).
- Survives network errors (returns False, doesn't raise).
- HTML-escapes user content so a stray ``<script>`` in a stack trace
  doesn't become a real tag in the email body.
"""

from __future__ import annotations

import json
import os
import urllib.error
from unittest.mock import patch

import pytest

from app.observability.email import (
    EmailConfig,
    send_alert,
)


def _cfg(api_key: str | None = None, dry_run: bool = False) -> EmailConfig:
    return EmailConfig(
        api_key=api_key,
        to="test@example.com",
        sender="Test <noreply@example.com>",
        dry_run=dry_run,
    )


def test_send_alert_no_op_when_api_key_missing() -> None:
    """No API key + no dry-run = no-op. Returns True so callers
    can treat the path as 'tried'."""
    cfg = _cfg(api_key=None, dry_run=False)
    assert send_alert("hello", "world", cfg=cfg) is True


def test_send_alert_dry_run_does_not_post() -> None:
    """dry_run=True must not invoke the network, but should still
    return True (the alert path is 'tried' from the caller's POV)."""
    cfg = _cfg(api_key="re_test_dryrun", dry_run=True)
    with patch("urllib.request.urlopen") as mock_urlopen:
        result = send_alert("subject", "body", cfg=cfg)
    assert result is True
    assert mock_urlopen.call_count == 0


def test_send_alert_posts_correct_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    """When API key is set, must POST JSON to Resend with the right
    shape and the right Authorization header."""
    cfg = _cfg(api_key="re_test_real", dry_run=False)
    captured: dict = {}

    class _FakeResp:
        status = 200

        def __enter__(self):  # for ``with urlopen() as r``
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["method"] = req.method
        captured["headers"] = dict(req.headers)
        captured["body"] = json.loads(req.data.decode("utf-8"))
        captured["timeout"] = timeout
        return _FakeResp()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    result = send_alert(
        "Backup failed",
        "traceback here",
        severity="error",
        cfg=cfg,
    )
    assert result is True
    assert captured["url"] == "https://api.resend.com/emails"
    assert captured["method"] == "POST"
    assert captured["headers"]["Authorization"] == "Bearer re_test_real"
    assert captured["body"]["from"] == cfg.sender
    assert captured["body"]["to"] == [cfg.to]
    assert captured["body"]["subject"] == "[saskia-error] Backup failed"
    assert "traceback here" in captured["body"]["text"]
    assert "traceback here" in captured["body"]["html"]


def test_send_alert_html_escapes_payload() -> None:
    """XSS-y content in the body must be HTML-escaped in the HTML
    body, but preserved verbatim in the text body."""
    cfg = _cfg(api_key="re_test_xss", dry_run=True)
    send_alert("hi", "<script>alert(1)</script>", cfg=cfg)
    # dry-run doesn't return the payload, so we re-test the renderer
    # via the import: no exception, payload escaped correctly.
    # Direct check via the helper:
    from app.observability.email import _render_body

    subj, html = _render_body("hi", "<script>alert(1)</script>", "warn")
    assert subj == "[saskia-warn] hi"
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_send_alert_returns_false_on_network_error() -> None:
    """Network errors must NOT propagate. Return False so callers
    can decide to fall back to Sentry."""
    cfg = _cfg(api_key="re_test_err", dry_run=False)

    def boom(*a, **kw):
        raise urllib.error.URLError("connection refused")

    with patch("urllib.request.urlopen", boom):
        assert send_alert("x", "y", cfg=cfg) is False


def test_send_alert_handles_non_2xx_status() -> None:
    """Resend returns 422 for bad payloads. Treat non-2xx as a soft
    failure (return False, don't raise)."""
    cfg = _cfg(api_key="re_test_422", dry_run=False)

    class _Fake422:
        status = 422

        def __enter__(self): return self
        def __exit__(self, *a): return False

    def fake_urlopen(req, timeout):
        return _Fake422()

    with patch("urllib.request.urlopen", fake_urlopen):
        assert send_alert("x", "y", cfg=cfg) is False


def test_email_config_from_env_reads_known_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RESEND_API_KEY", "re_test_env")
    monkeypatch.setenv("ALERT_EMAIL_TO", "ops@example.com")
    monkeypatch.setenv("ALERT_EMAIL_FROM", "Saskia <s@example.com>")
    monkeypatch.setenv("ALERT_EMAIL_DRY_RUN", "1")
    cfg = EmailConfig.from_env()
    assert cfg.api_key == "re_test_env"
    assert cfg.to == "ops@example.com"
    assert cfg.sender == "Saskia <s@example.com>"
    assert cfg.dry_run is True
    assert cfg.enabled is True


def test_email_config_defaults() -> None:
    """Without env vars, defaults to dev-mode (no key, no dry-run,
    ivan@aiwhisperers.dev)."""
    for var in (
        "RESEND_API_KEY",
        "ALERT_EMAIL_TO",
        "ALERT_EMAIL_FROM",
        "ALERT_EMAIL_DRY_RUN",
    ):
        os.environ.pop(var, None)
    cfg = EmailConfig.from_env()
    assert cfg.api_key is None
    assert cfg.enabled is False
    assert cfg.dry_run is False
    assert cfg.to.endswith("@aiwhisperers.dev") or "@" in cfg.to
