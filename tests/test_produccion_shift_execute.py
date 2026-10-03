"""Tests for /produccion/shift-execute + /produccion/ad-hoc (Sprint 1+4).

The shift-execute endpoint must persist actual production via the
ProductionCompletion helper (one row per (product, for_date) — UPSERT
semantics, NOT the production_plan_override table).
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.rms.models import Product, ProductionCompletion


@pytest.fixture
def product_id(session_factory):
    with session_factory() as s:
        prod = Product(
            name="Cheesecake sprint test",
            portion_label="1 und",
            sale_price_gs=45000,
            is_available=True,
        )
        s.add(prod)
        s.commit()
        s.refresh(prod)
        return prod.id


@pytest.fixture
def other_product_id(session_factory):
    with session_factory() as s:
        prod = Product(
            name="Brownie sprint test",
            portion_label="1 und",
            sale_price_gs=8000,
            is_available=True,
        )
        s.add(prod)
        s.commit()
        s.refresh(prod)
        return prod.id


# --- shift-execute: writes ProductionCompletion ---


def test_shift_execute_creates_completion_rows(
    authed_client, session_factory, product_id, other_product_id
):
    """POST /produccion/shift-execute must upsert ProductionCompletion per product."""
    today = datetime.now(_UTC).date()

    r = authed_client.post(
        "/produccion/shift-execute",
        data={
            "for_date": today.isoformat(),
            f"completed_{product_id}": "5",
            f"completed_{other_product_id}": "12",
        },
    )
    assert r.status_code in (200, 303), f"shift-execute returned {r.status_code}: {r.text[:200]}"

    with session_factory() as s:
        rows = list(
            s.execute(
                select(ProductionCompletion).where(ProductionCompletion.for_date == today)
            ).scalars()
        )
    by_pid = {r.product_id: r.completed_qty for r in rows}
    assert by_pid.get(product_id) == 5.0
    assert by_pid.get(other_product_id) == 12.0


def test_shift_execute_updates_existing_completion(
    authed_client, session_factory, product_id
):
    """Re-recording the same (product, date) MUST update in place (upsert)."""
    from app.rms.eod_completions import upsert_completion

    today = datetime.now(_UTC).date()
    with session_factory() as s:
        upsert_completion(s, product_id=product_id, for_date=today, completed_qty=3.0)
        s.commit()

    r = authed_client.post(
        "/produccion/shift-execute",
        data={"for_date": today.isoformat(), f"completed_{product_id}": "9"},
    )
    assert r.status_code in (200, 303)

    with session_factory() as s:
        rows = list(
            s.execute(
                select(ProductionCompletion).where(
                    ProductionCompletion.product_id == product_id,
                    ProductionCompletion.for_date == today,
                )
            ).scalars()
        )
    assert len(rows) == 1, "upsert should keep one row per (product, date)"
    assert rows[0].completed_qty == 9.0


def test_shift_execute_skips_unknown_product_id(authed_client, session_factory):
    """A bogus product_id in the form must be silently skipped."""
    today = datetime.now(_UTC).date()
    r = authed_client.post(
        "/produccion/shift-execute",
        data={"for_date": today.isoformat(), "completed_99999": "5"},
    )
    assert r.status_code in (200, 303)


def test_shift_execute_ignores_invalid_qty(authed_client, session_factory, product_id):
    """Non-numeric qty must be skipped, not crash."""
    today = datetime.now(_UTC).date()
    r = authed_client.post(
        "/produccion/shift-execute",
        data={"for_date": today.isoformat(), f"completed_{product_id}": "abc"},
    )
    assert r.status_code in (200, 303)

    with session_factory() as s:
        rows = list(
            s.execute(
                select(ProductionCompletion).where(
                    ProductionCompletion.product_id == product_id
                )
            ).scalars()
        )
    assert len(rows) == 0, "non-numeric qty must not write a row"


def test_shift_execute_does_not_write_plan_override(
    authed_client, session_factory, product_id
):
    """The endpoint writes ProductionCompletion, NOT ProductionPlanOverride.

    This is the core invariant — actual production must live in its own
    table so /eod and forecast accuracy can read it.
    """
    from app.rms.models import ProductionPlanOverride

    today = datetime.now(_UTC).date()
    r = authed_client.post(
        "/produccion/shift-execute",
        data={"for_date": today.isoformat(), f"completed_{product_id}": "7"},
    )
    assert r.status_code in (200, 303)

    with session_factory() as s:
        overrides = list(
            s.execute(
                select(ProductionPlanOverride).where(
                    ProductionPlanOverride.for_date == today
                )
            ).scalars()
        )
    assert overrides == [], (
        "shift-execute must NEVER write production_plan_override — that's the plan, not the actual"
    )


# --- ad-hoc bake entry ---


def test_ad_hoc_creates_completion_with_adhoc_tag(
    authed_client, session_factory, product_id
):
    """POST /produccion/ad-hoc must record a ProductionCompletion with notes='ad_hoc'."""
    today = datetime.now(_UTC).date()
    r = authed_client.post(
        "/produccion/ad-hoc",
        data={
            "for_date": today.isoformat(),
            "product_id": str(product_id),
            "qty": "4",
            "notes": "walk-in",
        },
    )
    assert r.status_code in (200, 303), f"ad-hoc returned {r.status_code}: {r.text[:200]}"

    with session_factory() as s:
        rows = list(
            s.execute(
                select(ProductionCompletion).where(
                    ProductionCompletion.product_id == product_id,
                    ProductionCompletion.for_date == today,
                )
            ).scalars()
        )
    assert len(rows) == 1
    assert rows[0].completed_qty == 4.0
    assert rows[0].notes and "ad_hoc" in rows[0].notes
    assert "walk-in" in rows[0].notes


def test_ad_hoc_rejects_zero_qty(authed_client, product_id):
    """qty <= 0 must return 400."""
    today = datetime.now(_UTC).date()
    r = authed_client.post(
        "/produccion/ad-hoc",
        data={
            "for_date": today.isoformat(),
            "product_id": str(product_id),
            "qty": "0",
            "notes": "",
        },
    )
    assert r.status_code == 400


def test_ad_hoc_404_unknown_product(authed_client):
    """Unknown product_id must return 404."""
    today = datetime.now(_UTC).date()
    r = authed_client.post(
        "/produccion/ad-hoc",
        data={
            "for_date": today.isoformat(),
            "product_id": "999999",
            "qty": "3",
            "notes": "",
        },
    )
    assert r.status_code == 404


# --- day view renders completions ---


def test_day_view_renders_completed_qty(authed_client, session_factory, product_id):
    """The day view must render pre-filled completed_qty from ProductionCompletion."""
    from app.rms.eod_completions import upsert_completion

    today = datetime.now(_UTC).date()
    with session_factory() as s:
        upsert_completion(s, product_id=product_id, for_date=today, completed_qty=7.5)
        s.commit()

    r = authed_client.get(f"/produccion?for_date={today.isoformat()}")
    assert r.status_code == 200
    body = r.text
    assert "Cheesecake sprint test" in body
    assert 'value="7.5"' in body or 'value="7,5"' in body, (
        "completed_qty must pre-fill the input from ProductionCompletion"
    )


def test_day_view_renders_adhoc_row(authed_client, session_factory, product_id):
    """A completion WITHOUT a plan row must render with badge Ad-hoc/Extra."""
    from app.rms.eod_completions import upsert_completion

    today = datetime.now(_UTC).date()
    with session_factory() as s:
        upsert_completion(
            s,
            product_id=product_id,
            for_date=today,
            completed_qty=3.0,
            notes="ad_hoc: walk-in",
        )
        s.commit()

    r = authed_client.get(f"/produccion?for_date={today.isoformat()}")
    assert r.status_code == 200
    body = r.text
    if "Cheesecake sprint test" in body:
        assert "Extra" in body or "Ad-hoc" in body
