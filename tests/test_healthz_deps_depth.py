"""Tests for BACKLOG #40: /healthz/deps extended to ping Supabase + R2 + disk.

The original /healthz/deps only reported env-var fingerprints and package
versions. Operators hit it to debug env mismatches, but couldn't tell
whether the external dependencies (Supabase Auth, R2 storage) were
actually reachable. This added depth:

- supabase_ok: True if we can hit Supabase's /auth/v1/health endpoint,
  or "skipped" if SUPABASE_URL is not set (so dev boxes don't fail).
- r2_ok: True if we can list objects in the bucket, or "skipped" if
  R2 isn't configured.
- disk: {total_gb, used_gb, free_gb, used_pct, alarm_threshold_pct=90}

The endpoint stays public (no PII) and 503s if any "skipped" path was
reachable but failed.
"""

from __future__ import annotations

import time
from collections import namedtuple
from pathlib import Path
from unittest.mock import patch

import pytest

DiskUsageMock = namedtuple("DiskUsageMock", ["total", "used", "free"])


def test_healthz_deps_includes_supabase_and_disk_fields(client):
    """E4.S1 (BACKLOG #40): /healthz/deps now reports supabase + disk."""
    resp = client.get("/healthz/deps")
    assert resp.status_code == 200
    body = resp.json()

    # New: supabase reachability
    assert "supabase" in body, "missing 'supabase' key in /healthz/deps"
    sb = body["supabase"]
    assert "ok" in sb
    # ok can be True, False, or "skipped" — all three are valid states
    assert sb["ok"] in (True, False, "skipped")

    # New: disk usage
    assert "disk" in body, "missing 'disk' key in /healthz/deps"
    disk = body["disk"]
    for key in ("total_gb", "used_gb", "free_gb", "used_pct", "path"):
        assert key in disk, f"missing '{key}' in disk block"
    assert isinstance(disk["total_gb"], (int, float))
    assert disk["total_gb"] > 0
    assert 0 <= disk["used_pct"] <= 100

    # Original keys still present
    assert "packages" in body
    assert "SUPABASE_URL" in body


def test_healthz_deps_disk_uses_data_root(client, monkeypatch):
    """The disk block should report on the same root the app uses for DB+state.

    Default is /opt/data on VPS, /tmp on dev. Both are real paths and
    will report non-zero total_gb."""
    resp = client.get("/healthz/deps")
    body = resp.json()
    disk = body["disk"]
    # path should exist and be absolute
    p = Path(disk["path"])
    assert p.is_absolute()
    assert p.exists(), f"disk.path '{p}' does not exist"


def test_healthz_deps_disk_alarm_threshold(client):
    """When disk is over 90% used, alarm flag should appear.

    We don't actually fill the disk — we patch shutil.disk_usage to
    return fake numbers and verify the threshold logic."""
    # Mock: 95% used
    fake = DiskUsageMock(total=10**9, used=int(0.95 * 10**9), free=int(0.05 * 10**9))
    with patch("app.routers.health._disk_usage", return_value=fake):
        resp = client.get("/healthz/deps")
    body = resp.json()
    disk = body["disk"]
    assert disk["used_pct"] == pytest.approx(95.0, rel=1)
    assert disk.get("alarm") == "disk_full"
    # Don't 503 — we still want the operator to see the body. The alarm
    # field is for UptimeRobot / dashboards.


def test_healthz_deps_supabase_skipped_without_url(client, monkeypatch):
    """If SUPABASE_URL is unset, supabase.ok must be 'skipped' (not False)."""
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    resp = client.get("/healthz/deps")
    body = resp.json()
    assert body["supabase"]["ok"] == "skipped"
    # Should NOT 503 — this is a dev-box state
    assert resp.status_code == 200


def test_healthz_deps_supabase_unreachable_returns_503(client, monkeypatch):
    """When SUPABASE_URL is set but unreachable, /healthz/deps returns 503.

    The helper now returns a diagnostic dict instead of a bare bool —
    we patch it with the failure shape (ok=False, error_class=URLError)
    so the JSON body surfaces the real cause to UptimeRobot / operators.
    """
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    from app.routers import health as health_module

    monkeypatch.setattr(
        health_module,
        "_check_supabase_reachable",
        lambda url, timeout=2.0: {
            "ok": False,
            "http_status": None,
            "error_class": "URLError",
            "latency_ms": None,
            "reason": "Name or service not known",
        },
    )
    resp = client.get("/healthz/deps")
    body = resp.json()
    assert body["supabase"]["ok"] is False
    assert body["supabase"]["error_class"] == "URLError"
    assert resp.status_code == 503


def test_healthz_deps_supabase_healthy_returns_200(client, monkeypatch):
    """When supabase probe returns ok=True, no 503 from /healthz/deps.

    Locks the GET-not-HEAD change: HEAD was returning 405 from Supabase
    auth health endpoint (per its openapi.yaml), masking healthy projects
    as down. With GET + 200, the probe should report reachable.
    """
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    from app.routers import health as health_module

    monkeypatch.setattr(
        health_module,
        "_check_supabase_reachable",
        lambda url, timeout=2.0: {
            "ok": True,
            "http_status": 200,
            "error_class": None,
            "latency_ms": 42,
            "reason": None,
        },
    )
    resp = client.get("/healthz/deps")
    body = resp.json()
    assert body["supabase"]["ok"] is True
    assert body["supabase"]["http_status"] == 200
    assert body["supabase"]["latency_ms"] == 42
    # /healthz/deps only 503s if a configured dep is False; here supabase
    # is True so the overall status is ok (r2 stays "skipped" since no
    # R2 config in this test).
    assert resp.status_code == 200


def test_healthz_deps_supabase_405_now_reports_diagnostics(client, monkeypatch):
    """GET 405 (the historical HEAD-fallback bug) is now surfaced clearly.

    Previously: 405 was caught by the bool helper, returned False, no
    diagnostic. Now the JSON includes http_status=405 + reason. The
    operator sees "HTTP 405 Method Not Allowed" instead of a generic
    'unreachable'.
    """
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    from app.routers import health as health_module

    monkeypatch.setattr(
        health_module,
        "_check_supabase_reachable",
        lambda url, timeout=2.0: {
            "ok": False,
            "http_status": 405,
            "error_class": "HTTPError",
            "latency_ms": 30,
            "reason": "HTTP 405 Method Not Allowed",
        },
    )
    resp = client.get("/healthz/deps")
    body = resp.json()
    assert body["supabase"]["http_status"] == 405
    assert "Method Not Allowed" in body["supabase"]["reason"]


def test_healthz_deps_r2_block_present(client):
    """R2 status appears; ok is True/False/'skipped' depending on config."""
    resp = client.get("/healthz/deps")
    body = resp.json()
    assert "r2" in body
    assert body["r2"]["ok"] in (True, False, "skipped")


def test_healthz_deps_r2_skipped_without_config(client, monkeypatch):
    """If no R2 config, r2.ok is 'skipped' (not False)."""
    monkeypatch.setattr(
        "app.services.r2_backup.load_r2_settings",
        lambda: None,
    )
    resp = client.get("/healthz/deps")
    body = resp.json()
    assert body["r2"]["ok"] == "skipped"
    assert resp.status_code == 200


def test_healthz_deps_returns_quickly(client):
    """External pings have 2s timeout each — endpoint should not hang."""
    t0 = time.time()
    client.get("/healthz/deps")
    elapsed = time.time() - t0
    # 2s for supabase + 2s for r2 = max 4s if both timeout. With timeouts
    # not actually triggered, should be sub-second.
    assert elapsed < 3.0, f"/healthz/deps took {elapsed:.2f}s — too slow"
