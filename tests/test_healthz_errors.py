"""tests/test_healthz_errors.py — /healthz/errors endpoint tests."""

from __future__ import annotations


def test_healthz_errors_returns_counts(client):
    """/healthz/errors returns 200 with http_500_count object."""
    resp = client.get("/healthz/errors")
    assert resp.status_code == 200
    body = resp.json()
    assert "http_500_count" in body
    assert "last_1h" in body["http_500_count"]
    assert "last_24h" in body["http_500_count"]
    # Counts must be non-negative ints.
    assert isinstance(body["http_500_count"]["last_1h"], int)
    assert body["http_500_count"]["last_1h"] >= 0


def test_healthz_errors_503_when_not_ready(client):
    """Respects the readiness flag like other /healthz* endpoints."""
    from app.rms.main import app

    app.state.ready = False
    try:
        resp = client.get("/healthz/errors")
        assert resp.status_code == 503
    finally:
        app.state.ready = True


def test_healthz_errors_counts_audit_log(client, session_factory):
    """/healthz/errors counts `action=http.500` audit rows in last 24h."""
    from datetime import datetime, timedelta, timezone

    from app.rms.models import AuditLog

    with session_factory() as s:
        # Insert 3 recent and 2 old http.500 rows
        for i in range(3):
            s.add(
                AuditLog(
                    occurred_at=datetime.now(timezone.utc),
                    action="http.500",
                    user_id=None,
                    target_type="http_error",
                    target_id=f"recent-{i}",
                    detail={"path": "/"},
                )
            )
        for i in range(2):
            s.add(
                AuditLog(
                    occurred_at=datetime.now(timezone.utc) - timedelta(hours=48),
                    action="http.500",
                    user_id=None,
                    target_type="http_error",
                    target_id=f"old-{i}",
                    detail={"path": "/"},
                )
            )
        s.commit()

    resp = client.get("/healthz/errors")
    assert resp.status_code == 200
    body = resp.json()
    # Recent (≤24h ago) must include the 3; old (>24h) should not.
    assert body["http_500_count"]["last_1h"] >= 3
    assert body["http_500_count"]["last_24h"] >= 3
