"""Batch B5 (2026-10-07): rate-limit threshold override tests.

Tests that the new ``rate_limit_cfg`` kwarg on the three rate-limit
helpers (login / write / read) correctly accepts a partial override dict
and merges it with ``DEFAULT_RATE_LIMIT_CONFIG``.

The pre-existing tests in test_rate_limit.py and
test_rate_limit_atomicity.py already cover the no-override default path
and the explicit-kwarg path; these tests fill the new in-between
ground (override dict).
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from app.rms.audit import record as audit_record
from app.rms.rate_limit import (
    DEFAULT_RATE_LIMIT_CONFIG,
    DEFAULT_LIMIT,
    DEFAULT_READ_LIMIT,
    DEFAULT_READ_WINDOW_SECONDS,
    DEFAULT_WINDOW_MINUTES,
    is_rate_limited,
    is_read_rate_limited,
    is_write_rate_limited,
)


def _make_request(ip: str = "203.0.113.50") -> SimpleNamespace:
    """Build a fake Request-like object with the given IP."""
    return SimpleNamespace(
        headers={"x-forwarded-for": ip},
        client=None,
    )


# ── DEFAULT_RATE_LIMIT_CONFIG shape ─────────────────────────────────────


def test_default_rate_limit_config_has_all_5_keys():
    """The registry dict has exactly the 5 keys documented in the plan."""
    expected = {
        "login_max_failures",
        "login_window_minutes",
        "write_max_per_minute",
        "read_max_per_minute",
        "read_window_seconds",
    }
    assert set(DEFAULT_RATE_LIMIT_CONFIG.keys()) == expected


def test_default_rate_limit_config_matches_legacy_constants():
    """The new dict's values equal the legacy module-level constants.

    Pre-existing code imported DEFAULT_LIMIT, DEFAULT_WINDOW_MINUTES,
    DEFAULT_READ_LIMIT, DEFAULT_READ_WINDOW_SECONDS by name. Their
    values must match the new dict so backward compat is preserved.
    """
    assert DEFAULT_LIMIT == DEFAULT_RATE_LIMIT_CONFIG["login_max_failures"]
    assert DEFAULT_WINDOW_MINUTES == DEFAULT_RATE_LIMIT_CONFIG["login_window_minutes"]
    assert DEFAULT_READ_LIMIT == DEFAULT_RATE_LIMIT_CONFIG["read_max_per_minute"]
    assert DEFAULT_READ_WINDOW_SECONDS == DEFAULT_RATE_LIMIT_CONFIG["read_window_seconds"]


# ── is_rate_limited override ────────────────────────────────────────────


def test_is_rate_limited_accepts_cfg_override(session_factory):
    """Override dict changes the effective login failure cap.

    With 3 failures planted and override cap=2, the IP must be blocked.
    With default cap=5, the same 3 failures must be allowed.
    """
    ip = "203.0.113.100"
    req = _make_request(ip)

    with session_factory() as s:
        for _ in range(3):
            audit_record(s, user_id=None, action="login.failure", request=req)
        s.commit()

        now = datetime.now(timezone.utc)

        # Without override (default cap=5): still allowed (3 < 5)
        d_default = is_rate_limited(s, req, now=now)
        assert d_default.allowed is True

        # With override cap=2: blocked (3 >= 2)
        d_override = is_rate_limited(s, req, rate_limit_cfg={"login_max_failures": 2}, now=now)
        assert d_override.allowed is False


def test_is_rate_limited_partial_cfg_merges_with_defaults(session_factory):
    """Partial override dict only changes the named keys.

    Passing only ``login_max_failures=2`` keeps
    ``login_window_minutes`` at 5 — partial dicts merge into defaults,
    they don't replace them.
    """
    ip = "203.0.113.101"
    req = _make_request(ip)

    with session_factory() as s:
        audit_record(s, user_id=None, action="login.failure", request=req)
        s.commit()

        now = datetime.now(timezone.utc)

        # Override only the cap; window stays at default (5 min).
        # With cap=2 and 1 failure → still allowed.
        d = is_rate_limited(s, req, rate_limit_cfg={"login_max_failures": 2}, now=now)
        assert d.allowed is True


# ── is_write_rate_limited override ──────────────────────────────────────


def test_is_write_rate_limited_accepts_cfg_override(session_factory):
    """Override dict tightens the write cap.

    With 3 writes in window and override cap=2, must block. With default
    cap=10, must allow.
    """
    ip = "203.0.113.200"
    req = _make_request(ip)

    with session_factory() as s:
        for _ in range(3):
            audit_record(s, user_id=None, action="write.sale.create", request=req)
        s.commit()

        now = datetime.now(timezone.utc)

        # Default cap=10 → allowed (3 < 10)
        assert is_write_rate_limited(s, req, now=now) is False
        # Override cap=2 → blocked (3 >= 2)
        assert (
            is_write_rate_limited(s, req, rate_limit_cfg={"write_max_per_minute": 2}, now=now)
            is True
        )


# ── is_read_rate_limited override ──────────────────────────────────────


def test_is_read_rate_limited_accepts_cfg_override(session_factory):
    """Override dict tightens the read cap."""
    ip = "203.0.113.201"
    req = _make_request(ip)

    with session_factory() as s:
        for _ in range(4):
            audit_record(s, user_id=None, action="read.heavy.reportes", request=req)
        s.commit()

        now = datetime.now(timezone.utc)

        # Default cap=60/window=60 → 4 reads allowed
        d_default = is_read_rate_limited(s, req, now=now)
        assert d_default.allowed is True

        # Override cap=3 → 4 reads blocked
        d_override = is_read_rate_limited(
            s, req, rate_limit_cfg={"read_max_per_minute": 3}, now=now
        )
        assert d_override.allowed is False


# ── Public API surface ─────────────────────────────────────────────────


def test_get_rate_limit_config_returns_dict(session_factory):
    """The helper returns a dict with all 5 keys."""
    from app.rms.settings_runtime import get_rate_limit_config

    with session_factory() as s:
        cfg = get_rate_limit_config(s)
        assert isinstance(cfg, dict)
        assert set(cfg.keys()) == set(DEFAULT_RATE_LIMIT_CONFIG.keys())


def test_get_rate_limit_config_uses_defaults_when_db_empty(session_factory):
    """With no settings stored, get_*_config returns module defaults."""
    from app.rms.settings_runtime import get_rate_limit_config

    with session_factory() as s:
        cfg = get_rate_limit_config(s)
        assert cfg == DEFAULT_RATE_LIMIT_CONFIG
