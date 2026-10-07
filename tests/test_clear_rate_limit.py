"""TDD: rate-limited login must expose a self-service reset path so
operators can recover from their own failed-attempt spam.

Why this test exists:
- 2026-10-06 a 5-minute rate-limit block from a few bad-password
  attempts stranded the operator with no in-UI recovery.
- Operators can (and will) fat-finger creds; we need a one-click
  escape hatch that clears this IP's login.failure rows and sends
  them back to the login form.

Coverage:
1. The /login/clear-rate-limit route exists and accepts POST.
2. POSTing there clears this IP's login.failure rows from audit_log.
3. POSTing there redirects to /login with the original `next` param.
4. Other IPs' login.failure rows are NOT touched.
5. The login.html template renders a "Limpiar bloqueo" form when
   the page is shown with retry_after set.
"""
from pathlib import Path

import pytest

from app.rms.models_legacy import AuditLog

pytestmark = pytest.mark.auth


def _seed_failure_rows(session_factory, ip: str, count: int) -> None:
    """Seed login.failure rows directly into the SQLite DB for the
    given IP. Idempotent: clears existing rows for that IP first."""
    from datetime import datetime, timezone
    s = session_factory()
    try:
        s.query(AuditLog).filter(
            AuditLog.action == "login.failure",
            AuditLog.ip == ip,
        ).delete(synchronize_session=False)
        now = datetime.now(timezone.utc)
        for _ in range(count):
            s.add(AuditLog(
                action="login.failure",
                detail={"reason": "test"},
                ip=ip,
                occurred_at=now,
            ))
        s.commit()
    finally:
        s.close()


def _count_failures(session_factory, ip: str) -> int:
    s = session_factory()
    try:
        return s.query(AuditLog).filter(
            AuditLog.action == "login.failure",
            AuditLog.ip == ip,
        ).count()
    finally:
        s.close()


def test_clear_rate_limit_route_exists(client):
    r = client.post("/login/clear-rate-limit", data={"next": "/productos"}, follow_redirects=False)
    assert r.status_code == 303, f"expected 303, got {r.status_code}: {r.text[:200]}"


def test_clear_rate_limit_redirects_to_login(client):
    r = client.post("/login/clear-rate-limit", data={"next": "/productos"}, follow_redirects=False)
    assert r.headers["location"].startswith("/login")
    assert "next=/productos" in r.headers["location"]


def test_clear_rate_limit_removes_this_ip_failures(client, session_factory):
    _seed_failure_rows(session_factory, "testclient", 5)
    assert _count_failures(session_factory, "testclient") == 5

    r = client.post("/login/clear-rate-limit", data={"next": "/"}, follow_redirects=False)
    assert r.status_code == 303
    assert _count_failures(session_factory, "testclient") == 0


def test_clear_rate_limit_does_not_touch_other_ips(client, session_factory):
    _seed_failure_rows(session_factory, "testclient", 3)
    _seed_failure_rows(session_factory, "198.51.100.5", 3)

    client.post("/login/clear-rate-limit", data={"next": "/"}, follow_redirects=False)

    assert _count_failures(session_factory, "testclient") == 0
    assert _count_failures(session_factory, "198.51.100.5") == 3


def test_open_redirect_protection(client):
    """The reset endpoint must not be an open redirect — it must only
    allow same-origin relative paths."""
    r = client.post(
        "/login/clear-rate-limit",
        data={"next": "https://evil.com/x"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert "evil.com" not in r.headers["location"]


def test_login_template_shows_reset_form_when_retry_after():
    """The /login page must render a 'Limpiar bloqueo' link when the
    user is rate-limited, so they can self-recover."""
    tpl = Path("app/templates/login.html").read_text(encoding="utf-8")

    # The form must target the new endpoint
    assert 'action="/login/clear-rate-limit"' in tpl, \
        "login.html must render a <form action=/login/clear-rate-limit> when retry_after is set"

    # The visible text is the recovery affordance
    assert "Limpiar bloqueo" in tpl, "login.html must show a 'Limpiar bloqueo' link"

    # The link must be inside an `{% if retry_after %}` block that
    # contains the action area (button + form), not the text-only
    # countdown block.
    tpl_lines = tpl.splitlines()
    _candidates = []
    for i, line in enumerate(tpl_lines):
        if "if retry_after" in line:
            # Find matching endif
            for j in range(i + 1, len(tpl_lines)):
                if "{% endif %}" in tpl_lines[j]:
                    block = "\n".join(tpl_lines[i:j + 1])
                    if "Limpiar bloqueo" in block:
                        return  # success
                    break
    assert False, "Limpiar bloqueo must live inside a {% if retry_after %} block that contains the action area"
