"""tests/test_auditoria_ip_user_filter.py — additional filter dimensions."""
from __future__ import annotations

from datetime import datetime, timezone


def test_auditoria_filter_by_ip(client, session_factory):
    from app.rms.models import AuditLog
    with session_factory() as s:
        s.add(AuditLog(occurred_at=datetime.now(timezone.utc), action="login.fail", user_id=None, ip="10.0.0.1"))
        s.add(AuditLog(occurred_at=datetime.now(timezone.utc), action="login.fail", user_id=None, ip="10.0.0.2"))
        s.commit()

    resp = client.get("/auditoria?ip_filter=10.0.0.1")
    assert resp.status_code == 200


def test_auditoria_filter_by_user_id(client, session_factory):
    from app.rms.models import AuditLog
    with session_factory() as s:
        s.add(AuditLog(occurred_at=datetime.now(timezone.utc), action="login.success", user_id="saskia"))
        s.add(AuditLog(occurred_at=datetime.now(timezone.utc), action="login.success", user_id="ivan"))
        s.commit()

    resp = client.get("/auditoria?user_filter=saskia")
    assert resp.status_code == 200
