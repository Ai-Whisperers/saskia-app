"""Email alerts (Resend transactional API).

Tier 8.2 (2026-10-01): outbound notifications for backup failures, EOD
anomalies, and migration drift. Gated on RESEND_API_KEY — no-op when
unset (dev / local). Uses Resend's HTTP API via stdlib (urllib) so we
don't take on a new dependency for a single POST endpoint.

Design:
- One module, one function: ``send_alert(subject, body, severity=...)``.
- HTML body is templated from a single template + kwargs.
- Subject prefix ``[saskia-{severity}]`` so Iván can filter.
- Failures to send are logged but NEVER raised (we don't want a broken
  email path to take down the app).
- No PII scrubbing is needed because the operator (Iván) IS the
  recipient; the customer-PII rule is about leaks from the operator to
  the outside, not operator-facing alerts.

Environment:
- ``RESEND_API_KEY`` — required to actually send. Free tier: 100 emails/day,
  3,000/month. Resend is the recommended provider (2026-10-01 decision).
- ``ALERT_EMAIL_TO`` — recipient. Defaults to ``ivan@aiwhisperers.dev``.
- ``ALERT_EMAIL_FROM`` — sender. Defaults to
  ``Saskia RMS <noreply@aiwhisperers.dev>`` (must be a verified domain on
  Resend's side).
- ``ALERT_EMAIL_DRY_RUN=1`` — log the payload, do not POST. Used in tests
  and in dev to verify what would be sent.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Literal

from loguru import logger

Severity = Literal["info", "warn", "error", "critical"]

_RESEND_URL = "https://api.resend.com/emails"
_TIMEOUT_S = 5  # never block startup > 5s on email


@dataclass(frozen=True)
class EmailConfig:
    """Loaded from env at call time, not import time.

    Lazy so dev/test runs without the env vars don't crash.
    """

    api_key: str | None
    to: str
    sender: str
    dry_run: bool

    @classmethod
    def from_env(cls) -> "EmailConfig":
        return cls(
            api_key=os.getenv("RESEND_API_KEY") or None,
            to=os.getenv("ALERT_EMAIL_TO", "ivan@aiwhisperers.dev"),
            sender=os.getenv(
                "ALERT_EMAIL_FROM",
                "Saskia RMS <noreply@aiwhisperers.dev>",
            ),
            dry_run=os.getenv("ALERT_EMAIL_DRY_RUN", "0") == "1",
        )

    @property
    def enabled(self) -> bool:
        return self.api_key is not None


def _render_body(subject: str, body: str, severity: Severity) -> tuple[str, str]:
    """Return (text, html) bodies. Subject is the plain text only.

    The HTML body is intentionally minimal — a single div with the body
    inside a <pre> so line breaks in stack traces survive.
    """
    safe_subject = f"[saskia-{severity}] {subject}"
    html_body = (
        f'<div style="font-family:ui-monospace,monospace;font-size:14px;'
        f'line-height:1.5;color:#1a1a1a">'
        f"<pre style=\"white-space:pre-wrap;margin:0\">{_html_escape(body)}</pre>"
        f"</div>"
    )
    return safe_subject, html_body


def _html_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def send_alert(
    subject: str,
    body: str,
    severity: Severity = "warn",
    *,
    cfg: EmailConfig | None = None,
) -> bool:
    """Send a single alert email. Returns True if sent (or dry-run logged),
    False otherwise. Never raises.

    Severity is one of: info / warn / error / critical. The prefix
    ``[saskia-{severity}]`` is added to the subject so the operator can
    filter.
    """
    cfg = cfg or EmailConfig.from_env()
    safe_subject, html_body = _render_body(subject, body, severity)
    payload = {
        "from": cfg.sender,
        "to": [cfg.to],
        "subject": safe_subject,
        "text": body,
        "html": html_body,
    }

    if not cfg.enabled or cfg.dry_run:
        # Log and return True so callers can treat the path as "ok, we
        # tried" — but with a clear "dry_run" / "disabled" note.
        logger.info(
            f"email_alert dry_run={cfg.dry_run} enabled={cfg.enabled} "
            f"subject={safe_subject!r} to={cfg.to!r} body_len={len(body)}"
        )
        return True

    try:
        req = urllib.request.Request(
            _RESEND_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {cfg.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "saskia-rms/1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:
            ok = 200 <= resp.status < 300
            if not ok:
                logger.warning(
                    f"email_alert resend returned status={resp.status} "
                    f"subject={safe_subject!r}"
                )
            return ok
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
        # Never crash the caller over email. A log line is enough —
        # Sentry (separate integration) is the system of record for
        # alert delivery failures.
        logger.warning(f"email_alert send failed: {exc!r} subject={safe_subject!r}")
        return False


__all__ = [
    "EmailConfig",
    "Severity",
    "send_alert",
]
