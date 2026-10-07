"""P-43: /auditoria must redact sensitive fields from entry details.

Audit detail JSON sometimes contains passwords, API keys, and other
secrets that should not render in plain text on the page. The page
must mask known sensitive keys.

Acceptance:
  - GET /auditoria returns 200.
  - When detail pairs include a sensitive key (e.g., "password"),
    the rendered value is masked (e.g., "***" or empty).
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.rms.models import AuditLog


def test_auditoria_redacts_password(client, session_factory):
    """P-43: password fields are masked in /auditoria detail pairs."""
    s = session_factory()
    try:
        # Insert a fake audit entry with a password in detail.
        entry = AuditLog(
            action="login.failure",
            user_id="tester",
            target_type=None,
            target_id=None,
            occurred_at=datetime.now(timezone.utc),
            detail={
                "username": "operator1",
                "password": "hunter2-actual-password",
                "ip": "192.0.2.1",
            },
            ip="192.0.2.1",
            user_agent="test-ua",
        )
        s.add(entry)
        s.commit()
        _entry_id = entry.id
    finally:
        s.close()

    r = client.get("/auditoria")
    assert r.status_code == 200
    body = r.text

    # The literal password must NOT appear in the body.
    assert "hunter2-actual-password" not in body, (
        "password leaked in plain text on /auditoria"
    )

    # The page should render this audit entry. We look for the username
    # which is non-sensitive.
    assert "operator1" in body, (
        "expected the audit entry (via non-sensitive username) on /auditoria"
    )
