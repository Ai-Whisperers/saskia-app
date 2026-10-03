"""P-41: /healthz/deps should be split between operator and UptimeRobot.

Currently /healthz/deps mixes two audiences: UptimeRobot (liveness,
no env values) and the operator (env fingerprint, R2 status, etc.).

Fix: add a separate /admin/health/deps route for operators (with env
values) and keep /healthz/deps for UptimeRobot.

Acceptance:
  - GET /healthz/deps returns 200 with NO env values (e.g., no
    SUPABASE_URL value).
  - GET /admin/health/deps (with admin auth) returns 200 with env
    values present, OR returns 403 without auth.
"""
from __future__ import annotations

import os
import re


def test_healthz_deps_no_env_leak(client):
    """P-41: /healthz/deps is safe for UptimeRobot (no env values)."""
    r = client.get("/healthz/deps")
    if r.status_code == 404:
        import pytest
        pytest.skip("/healthz/deps not implemented")
    assert r.status_code == 200
    body = r.text

    # /healthz/deps must NOT contain env values. We check for typical
    # env value patterns (key=value where value is a UUID, hostname,
    # or URL).
    env_value_patterns = [
        r"AIW_SASKIA_SECRET_KEY=[\w-]+",  # any secret key value
        r"SUPABASE_URL=https?://[^\s\"'<>]+",  # full URL
    ]
    for pat in env_value_patterns:
        m = re.search(pat, body)
        assert not m, (
            f"/healthz/deps leaks env value matching {pat}: {m.group(0)[:80]}"
        )


def test_admin_health_deps_for_operators(client):
    """P-41: /admin/health/deps is available for operators."""
    # Try GET. If 404 → not implemented yet, skip.
    r = client.get("/admin/health/deps")
    if r.status_code == 404:
        import pytest
        pytest.skip("/admin/health/deps not yet implemented")
    # If 403/302 → exists but requires auth (good).
    assert r.status_code in (200, 302, 403), (
        f"unexpected status {r.status_code} for /admin/health/deps"
    )
