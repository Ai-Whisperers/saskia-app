"""P0 fix — Void-after-EOD-close bug.

The roadmap (saskia-only-roadmap.md, 2026-09-29) flagged a critical gap:
`void_sale()` did not check whether the sale belongs to a day whose EOD has
been closed. Saskia could void a Monday sale on Wednesday AFTER closing
Monday's books.

This module verifies:
1. The eod_closed helper correctly identifies a closed day (all EOD
   checklist items checked off)
2. void_sale raises ValueError with prefix "void_after_eod_close:<date>"
   when the sale belongs to a closed day
3. void_sale succeeds when the day is NOT closed
4. The router translates the ValueError into a Spanish 409 Conflict

Run: cd /opt/data/profiles/ivan/scratch/saskia-app-work && ./.venv/bin/python -m pytest tests/test_p0_void_after_eod.py -v
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.rms.eod_closed import eod_get_open_days, eod_is_day_closed
from app.rms.models import AppMeta, Product, Sale
from app.rms.workflow import fresh_eod_checklist

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def yesterday() -> date:
    """Yesterday in Asuncion local time."""
    from app.rms.config import ASUNCION_TZ

    return (datetime.now(ASUNCION_TZ) - timedelta(days=1)).date()


@pytest.fixture
def mark_yesterday_closed(session_factory, yesterday: date) -> None:
    """Persist AppMeta rows making yesterday's EOD checklist 100% done."""
    items = fresh_eod_checklist()
    # Skip notes_for_tomorrow — it's a text input, not a checkbox.
    checkable_items = [item for item in items if item.key != "notes_for_tomorrow"]
    assert len(checkable_items) >= 9, (
        f"Expected at least 9 checkable EOD items, got {len(checkable_items)}"
    )
    now_iso = datetime.utcnow().isoformat()
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


@pytest.fixture
def sale_yesterday(session_factory, yesterday: date) -> int:
    """Insert a sale dated yesterday and return its id."""
    sold_at = datetime.combine(yesterday, datetime.min.time(), tzinfo=timezone.utc) + timedelta(
        hours=12
    )
    with session_factory() as s:
        product = s.scalar(select(Product).limit(1))
        if product is None:
            product = Product(
                name="Test chipa",
                sale_price_gs=2500,
            )
            s.add(product)
            s.flush()
        sale = Sale(
            product_id=product.id,
            qty=2.0,
            sold_at=sold_at,
            unit_price_gs=2500,
            channel="mostrador",
        )
        s.add(sale)
        s.commit()
        s.refresh(sale)
        return sale.id


# ---------------------------------------------------------------------------
# eod_closed unit tests
# ---------------------------------------------------------------------------


def test_eod_is_day_closed_returns_false_when_no_rows(session_factory, yesterday: date) -> None:
    """A day with no AppMeta rows is not closed."""
    with session_factory() as s:
        assert eod_is_day_closed(s, yesterday) is False


def test_eod_is_day_closed_returns_false_with_partial_checklist(
    session_factory, yesterday: date
) -> None:
    """A day with only some checklist items is not closed."""
    items = fresh_eod_checklist()
    checkable_items = [item for item in items if item.key != "notes_for_tomorrow"]
    with session_factory() as s:
        for item in checkable_items[:-1]:  # Skip the last checkable item
            key = f"eod_check_{yesterday.isoformat()}_{item.key}"
            s.add(AppMeta(key=key, value="1", updated_at=datetime.utcnow().isoformat()))
        s.commit()
        assert eod_is_day_closed(s, yesterday) is False


def test_eod_is_day_closed_returns_true_when_all_done(
    session_factory, yesterday: date, mark_yesterday_closed
) -> None:
    """All checklist items checked off → day is closed."""
    with session_factory() as s:
        assert eod_is_day_closed(s, yesterday) is True


def test_eod_is_day_closed_ignores_notes_for_tomorrow(session_factory, yesterday: date) -> None:
    """notes_for_tomorrow is a text input, not a checkbox — its absence
    doesn't block the day from being closed."""
    from app.rms.workflow import fresh_eod_checklist

    checkable_items = [item for item in fresh_eod_checklist() if item.key != "notes_for_tomorrow"]
    assert len(checkable_items) >= 9, f"Expected ≥9 checkable items, got {len(checkable_items)}"
    now_iso = datetime.utcnow().isoformat()
    with session_factory() as s:
        for item in checkable_items:
            key = f"eod_check_{yesterday.isoformat()}_{item.key}"
            s.add(AppMeta(key=key, value="1", updated_at=now_iso))
        # notes_for_tomorrow deliberately NOT added
        s.commit()
        assert eod_is_day_closed(s, yesterday) is True


def test_eod_is_day_closed_returns_false_for_future_date(session_factory) -> None:
    """Future dates are never closed."""
    future = datetime.utcnow().date() + timedelta(days=7)
    with session_factory() as s:
        assert eod_is_day_closed(s, future) is False


def test_eod_get_open_days_returns_unclosed_days(session_factory, yesterday: date) -> None:
    """eod_get_open_days lists days without closed EOD."""
    with session_factory() as s:
        open_days = eod_get_open_days(s, yesterday)
    assert yesterday in open_days


def test_eod_get_open_days_excludes_closed_days(
    session_factory, yesterday: date, mark_yesterday_closed
) -> None:
    """Closed days are filtered out."""
    with session_factory() as s:
        open_days = eod_get_open_days(s, yesterday)
    assert yesterday not in open_days


# ---------------------------------------------------------------------------
# void_sale integration tests
# ---------------------------------------------------------------------------


def test_void_sale_blocked_after_eod_closed(
    session_factory, yesterday: date, mark_yesterday_closed, sale_yesterday: int
) -> None:
    """void_sale raises ValueError with prefix 'void_after_eod_close:' for closed days."""
    from app.rms.costing import void_sale

    with session_factory() as s:
        with pytest.raises(ValueError, match=r"^void_after_eod_close:\d{4}-\d{2}-\d{2}$"):
            void_sale(s, sale_yesterday, reason="test", voided_by="operator")
    with session_factory() as s:
        sale = s.get(Sale, sale_yesterday)
        assert sale.voided_at is None, "Sale must NOT be voided when EOD is closed"


def test_void_sale_succeeds_when_eod_open(session_factory, sale_yesterday: int) -> None:
    """void_sale proceeds normally when yesterday's EOD is NOT closed."""
    from app.rms.costing import void_sale

    with session_factory() as s:
        void_sale(s, sale_yesterday, reason="test", voided_by="operator")
    with session_factory() as s:
        sale = s.get(Sale, sale_yesterday)
        assert sale.voided_at is not None, "Sale must be voided when EOD is open"


def test_void_sale_already_voided_still_raises_valueerror(
    session_factory, sale_yesterday: int
) -> None:
    """Idempotency check still works: double-void raises the original ValueError."""
    from app.rms.costing import void_sale

    with session_factory() as s:
        void_sale(s, sale_yesterday, reason="first", voided_by="operator")
    with session_factory() as s:
        with pytest.raises(ValueError, match="ya anulada"):
            void_sale(s, sale_yesterday, reason="second", voided_by="operator")


# ---------------------------------------------------------------------------
# Router integration test
# ---------------------------------------------------------------------------


def test_void_sale_router_returns_spanish_409_after_eod_close(
    client, session_factory, yesterday: date, mark_yesterday_closed, sale_yesterday: int
) -> None:
    """The /ventas/{id}/anular endpoint translates the ValueError to a clean
    Spanish 409 Conflict response that mentions the closed date."""
    r = client.post(
        f"/ventas/{sale_yesterday}/anular",
        data={"reason": "test"},
        follow_redirects=False,
    )
    assert r.status_code == 409, f"Expected 409, got {r.status_code}: {r.text[:200]}"
    assert yesterday.isoformat() in r.text, f"Expected date {yesterday} in error body"
    assert "ya fue cerrado" in r.text or "ya fue cerrada" in r.text, (
        f"Expected user-facing message about closed day, got: {r.text[:300]}"
    )


def test_void_sale_router_succeeds_when_eod_open(
    client, session_factory, sale_yesterday: int
) -> None:
    """The /ventas/{id}/anular endpoint returns 303 redirect when EOD is open."""
    r = client.post(
        f"/ventas/{sale_yesterday}/anular",
        data={"reason": "test"},
        follow_redirects=False,
    )
    assert r.status_code == 303, f"Expected 303, got {r.status_code}: {r.text[:200]}"
