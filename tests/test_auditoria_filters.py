"""tests/test_auditoria_filters.py — /auditoria?start_date=&end_date= filter.

/auditoria only shows recent 100 entries by default. Operators
investigating "what happened yesterday" need date filters.
"""
from __future__ import annotations

from datetime import datetime, timedelta


def test_auditoria_filters_by_date_range(client, session_factory):
    from datetime import datetime, timedelta

    from app.rms.models import AuditLog

    with session_factory() as s:
        now = datetime.utcnow()
        s.add(AuditLog(occurred_at=now, action="recent", user_id=None))
        s.add(AuditLog(occurred_at=now - timedelta(days=10), action="week_ago", user_id=None))
        s.add(AuditLog(occurred_at=now - timedelta(days=40), action="month_ago", user_id=None))
        s.commit()

    resp = client.get(f"/auditoria?start_date={(now - timedelta(days=15)).date().isoformat()}")
    assert resp.status_code == 200
    body = resp.text
    assert "recent" in body
    assert "week_ago" in body


def test_auditoria_combined_filter(client, session_factory):
    """action_filter + date range together."""
    from app.rms.models import AuditLog

    with session_factory() as s:
        s.add(AuditLog(
            occurred_at=datetime.utcnow() - timedelta(days=60),
            action="login.success",
            user_id=None,
        ))
        s.commit()

    resp = client.get("/auditoria?action_filter=login.success&start_date=2020-01-01")
    assert resp.status_code == 200
