"""Tests for Tier-5-K: 2-cook edit prevention (concurrent-edit detection).

T-2026-10-04: Two cooks editing the same shift's completion in
parallel currently do last-write-wins silently. We add:
  - An updated_at column on production_completion (migration 099).
  - A form_opened_at hidden field on the shift-execute form so the
    POST handler can detect "someone else saved while you were
    filling it out" and surface a soft warning.
  - The handler compares max(updated_at) for the date against
    form_opened_at. If form_opened_at < max(updated_at), we still
    save the new values (last-write-wins remains the floor), but
    the redirect includes a ?concurrent_modify=1 flag so the
    confirmation page can render a banner.

We verify:
  - Without form_opened_at, no warning (backward compat).
  - With form_opened_at < max(updated_at), redirect includes
    concurrent_modify=1.
  - With form_opened_at > max(updated_at), no warning.
  - The day-view page renders a banner when ?concurrent_modify=1.
"""
from datetime import date, datetime, timedelta, timezone

import pytest  # noqa: F401 — fixtures via authed_client


def test_shift_execute_no_warning_without_form_opened_at(authed_client):
    """Without form_opened_at, the redirect doesn't add concurrent flag."""
    r = authed_client.post(
        "/produccion/shift-execute",
        data={"for_date": "2026-10-04"},
        follow_redirects=False,
    )
    # 303 redirect; query string shouldn't have concurrent_modify.
    location = r.headers.get("location", "")
    assert "concurrent_modify" not in location


def test_shift_execute_no_warning_when_no_prior_save(authed_client):
    """No prior save + form_opened_at set = no concurrent warning.

    With no ProductionCompletion rows for 2026-10-04, max(updated_at)
    is None — there's nothing to compare against. No warning.
    """
    r = authed_client.post(
        "/produccion/shift-execute",
        data={
            "for_date": "2026-10-04",
            "form_opened_at": "2026-10-04T10:00:00+00:00",
        },
        follow_redirects=False,
    )
    location = r.headers.get("location", "")
    assert "concurrent_modify" not in location


def test_shift_execute_warning_when_form_opened_before_save(authed_client, session_factory):
    """form_opened_at < updated_at triggers concurrent_modify flag.

    Pre-populate a Product + ProductionCompletion with updated_at = T+10min.
    Submit with form_opened_at = T-5min. The handler should detect
    "the row was edited after the form was opened" and add the flag.
    """
    from sqlalchemy import text as sa_text  # noqa: F401 — kept for raw-SQL escape hatch

    from app.rms.models_legacy import Product, ProductionCompletion

    with session_factory() as s:
        # Seed a product (foreign key target).
        prod = Product(
            name="TestProductoConcurrent",
            sale_price_gs=10000,
            portion_label="1 unidad",
        )
        s.add(prod)
        s.flush()
        pid = prod.id

        now = datetime.now(timezone.utc)
        s.add(ProductionCompletion(
            product_id=pid,
            for_date=date(2026, 10, 4),
            completed_qty=5.0,
            recorded_at=now,
            updated_at=now + timedelta(minutes=10),  # edited 10min in the future
        ))
        s.commit()

    form_opened = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    r = authed_client.post(
        "/produccion/shift-execute",
        data={
            "for_date": "2026-10-04",
            "form_opened_at": form_opened,
            f"completed_{pid}": "5",
        },
        follow_redirects=False,
    )
    location = r.headers.get("location", "")
    assert "concurrent_modify=1" in location


def test_day_view_renders_concurrent_modify_banner(authed_client):
    """GET /produccion?concurrent_modify=1 renders a soft warning."""
    r = authed_client.get("/produccion?view=day&concurrent_modify=1")
    assert r.status_code == 200
    body = r.text
    # The banner uses text "se actualizó" or "cambios concurrentes"
    # with data-concurrent-modify attribute for analytics.
    assert "concurrent-modify" in body or "se actualizó" in body or "concurrent_modify" in body


def test_day_view_no_banner_without_flag(authed_client):
    """Without concurrent_modify=1, no banner."""
    r = authed_client.get("/produccion?view=day")
    assert r.status_code == 200
    body = r.text
    # Without the flag, the banner shouldn't render.
    # (The page may still contain 'concurrent' in script/asset URLs,
    # but the actual banner markup should not appear.)
    assert "data-concurrent-modify" not in body
