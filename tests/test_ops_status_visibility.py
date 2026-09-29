"""Ops status visibility tests."""
from __future__ import annotations


def test_ops_status_page_loads(authed_client):
    """GET /ops/status must return 200."""
    r = authed_client.get("/ops/status")
    assert r.status_code == 200, f"/ops/status returned {r.status_code}"


def test_ops_status_shows_schema_drift(authed_client):
    """/ops/status should include schema_version info."""
    r = authed_client.get("/ops/status")
    if r.status_code == 200:
        body = r.text.lower()
        # Either schema_version, drift, or migration status mentioned
        assert any(kw in body for kw in ("schema", "drift", "migrat", "version")), (
            f"/ops/status missing schema info. Body preview: {body[:500]}"
        )


def test_ops_status_no_secrets_leaked(authed_client):
    """/ops/status must NEVER include passwords or API keys."""
    r = authed_client.get("/ops/status")
    if r.status_code == 200:
        body = r.text
        # Check for secret patterns (case-insensitive substring search)
        # Note: "password" as a JavaScript variable name is OK,
        # but actual values like "password=foo" are NOT OK.
        import re
        for pattern in [
            r"(?i)password\s*[=:]\s*['\"][^'\"]+['\"]",
            r"(?i)api[_-]?key\s*[=:]\s*['\"][^'\"]+['\"]",
            r"(?i)secret[_-]?key\s*[=:]\s*['\"][^'\"]+['\"]",
            r"eyJ[A-Za-z0-9_-]+\.[eyJ]",  # JWT pattern
            r"sk_live_[A-Za-z0-9]+",  # Stripe live key
        ]:
            assert not re.search(pattern, body), (
                f"/ops/status may leak secret. Pattern matched: {pattern}"
            )


def test_ops_reset_demo_data_admin_gated(authed_client):
    """POST /ops/reset-demo-data must not 500 (admin gate)."""
    r = authed_client.post("/ops/reset-demo-data", follow_redirects=False)
    assert r.status_code < 500, (
        f"/ops/reset-demo-data returned {r.status_code}: {r.text[:200]}"
    )
