"""Tests for closed-day flag (P1).

T-2026-10-04: Operators need to mark a date as closed (holiday,
vacation, equipment failure). The plan view should show a banner
with the reason, and the reopen action should clear it.

Two routes to exercise:
  - GET /produccion?view=day (rendering with closed_day_active=True)
  - POST /produccion/closed action=close / action=reopen
"""
from datetime import date, timedelta

from app.rms.models import ProductionClosedDay


def test_closed_day_banner_shows_when_active(authed_client, session_factory):
    """When ProductionClosedDay has a row for for_date, the banner renders."""
    target = (date.today() + timedelta(days=3)).isoformat()
    with session_factory() as s:
        from datetime import datetime
        s.add(ProductionClosedDay(
            for_date=date.fromisoformat(target),
            reason="Feriado nacional",
            closed_by="test",
            closed_at=datetime.utcnow(),
        ))
        s.commit()
    r = authed_client.get(f"/produccion?view=day&for_date={target}")
    assert r.status_code == 200
    body = r.text
    assert "closed-day-banner" in body
    assert "Día cerrado" in body
    assert "Feriado nacional" in body
    assert 'action="/produccion/closed"' in body
    assert 'value="reopen"' in body


def test_closed_day_toggle_form_shows_when_not_active(authed_client):
    """When the date is NOT closed, the toggle form is shown."""
    r = authed_client.get("/produccion?view=day")
    assert r.status_code == 200
    body = r.text
    assert "closed-day-toggle" in body
    assert 'value="close"' in body
    assert "Cerrar este día" in body


def test_closed_day_post_close_creates_row(authed_client, session_factory):
    """POST /produccion/closed action=close creates a ProductionClosedDay row."""
    target = (date.today() + timedelta(days=5)).isoformat()
    r = authed_client.post(
        "/produccion/closed",
        data={
            "for_date": target,
            "action": "close",
            "reason": "Vacaciones",
        },
        follow_redirects=False,  # so we see the 303
    )
    assert r.status_code == 303, f"Expected 303, got {r.status_code}"
    with session_factory() as s:
        row = s.get(ProductionClosedDay, date.fromisoformat(target))
        assert row is not None
        assert row.reason == "Vacaciones"
        assert row.closed_by is not None


def test_closed_day_post_reopen_deletes_row(authed_client, session_factory):
    """POST /produccion/closed action=reopen deletes the row."""
    target = (date.today() + timedelta(days=6)).isoformat()
    with session_factory() as s:
        from datetime import datetime
        s.add(ProductionClosedDay(
            for_date=date.fromisoformat(target),
            reason="Test",
            closed_by="test",
            closed_at=datetime.utcnow(),
        ))
        s.commit()
    r = authed_client.post(
        "/produccion/closed",
        data={"for_date": target, "action": "reopen", "reason": ""},
        follow_redirects=False,
    )
    assert r.status_code == 303
    with session_factory() as s:
        row = s.get(ProductionClosedDay, date.fromisoformat(target))
        assert row is None


def test_closed_day_post_invalid_action_rejected(authed_client):
    """POST with action='invalid' is rejected (400 by CSRF guard, 422 by Pydantic)."""
    target = (date.today() + timedelta(days=7)).isoformat()
    r = authed_client.post(
        "/produccion/closed",
        data={"for_date": target, "action": "invalid", "reason": ""},
        follow_redirects=False,
    )
    # Either 400 (CSRF) or 422 (Pydantic pattern) is acceptable — both
    # indicate the request was not accepted.
    assert r.status_code in (400, 422), (
        f"Expected 400 or 422, got {r.status_code}"
    )


def test_closed_day_close_default_reason(authed_client, session_factory):
    """When reason is empty, the row stores 'Cerrado' as the default."""
    target = (date.today() + timedelta(days=8)).isoformat()
    r = authed_client.post(
        "/produccion/closed",
        data={"for_date": target, "action": "close", "reason": ""},
        follow_redirects=False,
    )
    assert r.status_code == 303
    with session_factory() as s:
        row = s.get(ProductionClosedDay, date.fromisoformat(target))
        assert row is not None
        assert row.reason == "Cerrado"


def test_closed_day_no_banner_after_reopen(authed_client, session_factory):
    """After reopen, the day view no longer shows the closed banner."""
    target = (date.today() + timedelta(days=9)).isoformat()
    with session_factory() as s:
        from datetime import datetime
        s.add(ProductionClosedDay(
            for_date=date.fromisoformat(target),
            reason="X",
            closed_by="t",
            closed_at=datetime.utcnow(),
        ))
        s.commit()
    r1 = authed_client.get(f"/produccion?view=day&for_date={target}")
    assert "closed-day-banner" in r1.text
    authed_client.post(
        "/produccion/closed",
        data={"for_date": target, "action": "reopen", "reason": ""},
    )
    r2 = authed_client.get(f"/produccion?view=day&for_date={target}")
    assert "closed-day-banner" not in r2.text
    assert "closed-day-toggle" in r2.text
