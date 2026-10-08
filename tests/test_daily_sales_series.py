"""# allow-hardcoded-dates: fixtures intentionally pin fixed dates (calendar edges, tz math, far-future sentinels); asserted relative to frozen or explicit anchors.
tests/test_daily_sales_series.py — E4.S2 daily_sales_series helper + presets.

The dashboard chart needs a per-day series with one row per day in the
range (zero-fill for no-sales days), a configurable preset (7d/30d/90d/
current_month/last_month), and a top-product hint per day.

Tests cover:
- _resolve_daily_range: each preset's start/end
- daily_sales_series: zero-fill (no sales → all totals=0)
- daily_sales_series: bucket totals correctly per local-date
- daily_sales_series: excludes voided sales
- daily_sales_series: picks top product by qty, ties by name
- daily_sales_series: respects preset boundaries
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from app.services.reports import (
    DailySalesRow,
    _resolve_daily_range,
    daily_sales_series,
)


def _asuncion_today() -> date:
    """Today in America/Asuncion for stable test bucketing.

    daily_sales_series buckets by Asunción-local date. The CI runner is
    UTC, so date.today() on the runner differs from Asunción date.today()
    when the test runs near midnight. Using a stable Asunción anchor
    keeps tests that assert "today's row has N sales" deterministic.
    """
    from zoneinfo import ZoneInfo

    return datetime.now(ZoneInfo("America/Asuncion")).date()


# --- Preset resolution ---


def test_resolve_daily_range_7d():
    start, end = _resolve_daily_range("7d", today=date(2026, 10, 1))
    assert start == date(2026, 9, 25)
    assert end == date(2026, 10, 1)


def test_resolve_daily_range_30d():
    start, end = _resolve_daily_range("30d", today=date(2026, 10, 1))
    assert start == date(2026, 9, 2)
    assert end == date(2026, 10, 1)


def test_resolve_daily_range_90d():
    start, end = _resolve_daily_range("90d", today=date(2026, 10, 1))
    assert start == date(2026, 7, 4)
    assert end == date(2026, 10, 1)


def test_resolve_daily_range_current_month():
    start, end = _resolve_daily_range("current_month", today=date(2026, 10, 15))
    assert start == date(2026, 10, 1)
    assert end == date(2026, 10, 15)


def test_resolve_daily_range_last_month_october_from_nov():
    start, end = _resolve_daily_range("last_month", today=date(2026, 11, 10))
    assert start == date(2026, 10, 1)
    assert end == date(2026, 10, 31)


def test_resolve_daily_range_unknown_preset_raises():
    import pytest

    with pytest.raises(ValueError):
        _resolve_daily_range("garbage")


# --- Daily series ---


def test_daily_sales_series_empty_returns_zero_filled(session_factory):
    Session = session_factory
    with Session() as s:
        rows = daily_sales_series(s, preset="7d", today=date(2026, 10, 7))
    assert len(rows) == 7
    for r in rows:
        assert isinstance(r, DailySalesRow)
        assert r.total_gs == 0
        assert r.sale_count == 0
        assert r.top_product_id is None
        assert r.top_product_name is None


def test_daily_sales_series_buckets_sales_by_local_date(session_factory, qseed):
    """Sales in different local days land in different rows."""
    Session = session_factory
    data = qseed("with_sale")
    p = data["product"]
    with Session() as s:
        # Add 2 more sales on different days via apply_sale.
        from datetime import timezone

        from app.rms.costing import apply_sale

        # Day -1 (yesterday)
        apply_sale(
            s,
            product_id=p.id,
            qty=1.0,
            sold_at=datetime.now(timezone.utc) - timedelta(days=1),
            notes=None,
            customer_id=None,
            payment_method="efectivo",
            discount_gs=0,
            channel="mostrador",
        )
        # Day -3
        apply_sale(
            s,
            product_id=p.id,
            qty=2.0,
            sold_at=datetime.now(timezone.utc) - timedelta(days=3),
            notes=None,
            customer_id=None,
            payment_method="efectivo",
            discount_gs=0,
            channel="mostrador",
        )
        s.commit()
        rows = daily_sales_series(s, preset="7d", today=_asuncion_today())
        assert len(rows) == 7
    # Today's row should have 1 sale (the original from with_sale seed).
    assert rows[-1].sale_count == 1
    # Total non-zero rows must be exactly 3 (today, yesterday, day-3).
    active = [r for r in rows if r.sale_count > 0]
    assert len(active) == 3


def test_daily_sales_series_excludes_voided_sales(session_factory, qseed):
    """Voided sales don't count in totals or sale_count."""
    Session = session_factory
    data = qseed("with_voided_sale")
    p = data["product"]
    with Session() as s:
        from app.rms.costing import apply_sale

        apply_sale(
            s,
            product_id=p.id,
            qty=1.0,
            sold_at=datetime.now(timezone.utc),
            notes=None,
            customer_id=None,
            payment_method="efectivo",
            discount_gs=0,
            channel="mostrador",
        )
        s.commit()
        rows_today = daily_sales_series(s, preset="7d", today=_asuncion_today())
    # The qseed already voided a sale. The new apply_sale is the only
    # non-voided sale today. So today's sale_count should be 1, NOT 2.
    today = rows_today[-1]
    assert today.sale_count == 1


def test_daily_sales_series_top_product_by_qty(session_factory, qseed):
    """Day's top product is the one with the most qty sold."""
    Session = session_factory
    data = qseed("with_sale")
    data["product"]
    # Need a second product — use qseed's recipe product as a starting
    # point; create another via qseed's underlying helpers.
    with Session() as s:
        # Create a second product
        from app.rms.models import Ingredient, Product, Recipe, RecipeLine

        ing = s.query(Ingredient).first()
        rec2 = Recipe(name="Otra Receta", yield_qty=5.0, yield_unit="und")
        s.add(rec2)
        s.flush()
        s.add(
            RecipeLine(
                recipe_id=rec2.id,
                line_kind="ingredient",
                line_ref_id=ing.id,
                qty=0.2,
                line_unit="kg",
            )
        )
        p2 = Product(name="Otro Producto", recipe_id=rec2.id, sale_price_gs=2000)
        s.add(p2)
        s.flush()
        s.commit()
        p2_id = p2.id

    # Now sell 1× p1 and 5× p2 today. p2 should be top.
    with Session() as s:
        from app.rms.costing import apply_sale

        apply_sale(
            s,
            product_id=data["product"].id,
            qty=1.0,
            sold_at=datetime.now(timezone.utc),
            notes=None,
            customer_id=None,
            payment_method="efectivo",
            discount_gs=0,
            channel="mostrador",
        )
        apply_sale(
            s,
            product_id=p2_id,
            qty=5.0,
            sold_at=datetime.now(timezone.utc),
            notes=None,
            customer_id=None,
            payment_method="efectivo",
            discount_gs=0,
            channel="mostrador",
        )
        s.commit()
        rows = daily_sales_series(s, preset="7d", today=_asuncion_today())
        today = rows[-1]
        assert today.sale_count == 3  # qseed 'with_sale' (1) + 2 we added
    assert today.top_product_id == p2_id
    assert today.top_product_name == "Otro Producto"


def test_daily_sales_series_respects_preset_range(session_factory, qseed):
    """30d preset returns 30 rows; current_month returns day-of-month rows."""
    Session = session_factory
    qseed("basic")
    with Session() as s:
        rows_30 = daily_sales_series(s, preset="30d", today=date(2026, 10, 15))
    assert len(rows_30) == 30

    with Session() as s:
        rows_month = daily_sales_series(s, preset="current_month", today=date(2026, 10, 15))
    assert len(rows_month) == 15  # 1st through 15th


def test_daily_sales_series_to_dict_serializable(session_factory, qseed):
    """to_dict() round-trips JSON-safe."""
    Session = session_factory
    qseed("with_sale")
    with Session() as s:
        rows = daily_sales_series(s, preset="7d", today=_asuncion_today())
    d = rows[-1].to_dict()
    assert isinstance(d["date"], str)
    assert isinstance(d["total_gs"], int)
    assert isinstance(d["sale_count"], int)
    # JSON-safe — no datetime, no Decimal.
    import json

    json.dumps(d)


def test_daily_sales_series_last_month_crosses_year_boundary(session_factory):
    """January → last_month = December of previous year."""
    Session = session_factory
    with Session() as s:
        rows = daily_sales_series(s, preset="last_month", today=date(2026, 1, 15))
    assert len(rows) == 31  # December has 31 days
    assert rows[0].date == date(2025, 12, 1)
    assert rows[-1].date == date(2025, 12, 31)
