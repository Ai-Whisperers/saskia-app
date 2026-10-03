"""Tests for BACKLOG #34: waste ROI per ingredient.

The "ROI" of waste = cost of waste over the cost of good inventory it
replaced. We compute two related views:

  1. `waste_roi_by_ingredient(session, since_days)` — for each
     ingredient that had waste in the window, return:
       - total_waste_gs: sum(WasteLog.cost_gs) over the window
       - total_consumed_gs: sum(Sale.qty * RecipeLine.qty *
         IngredientPriceEvent.price_gs at sale time) over the same
         window. We approximate "price at sale time" with the most
         recent IngredientPriceEvent before the waste date (since
         we already have IngredientPriceEvent rows).
       - waste_pct: total_waste_gs / (total_waste_gs + total_consumed_gs)
       - avg_waste_per_event_gs: total_waste_gs / event count
       - event_count

     Sorted by total_waste_gs desc so the operator can spot the
     biggest money leaks first.

  2. `waste_vs_purchase_trend(session, ingredient_id, since_days)` —
     for one ingredient, return the per-month (cost_gs, count)
     tuple list so we can render a sparkline of waste cost over
     time.

Both are append-only reads. No data mutations. Voided waste rows
should NOT be excluded (WasteLog doesn't have a voided_at column
yet — but it has SoftDelete columns? Let me check).
"""
from __future__ import annotations

from datetime import datetime, timedelta

from app.rms.config import ASUNCION_TZ
from app.rms.sales_intel import waste_roi_by_ingredient, waste_vs_purchase_trend
from tests.factories import make_ingredient, make_waste_log


def test_waste_roi_by_ingredient_returns_expected_keys(session_factory):
    """Output shape: list of dicts with the contract keys."""
    with session_factory() as s:
        out = waste_roi_by_ingredient(s, since_days=90)
    assert isinstance(out, list)
    if out:
        first = out[0]
        assert set(first.keys()) >= {
            "ingredient_id",
            "ingredient_name",
            "unit",
            "total_waste_gs",
            "total_consumed_gs",
            "waste_pct",
            "avg_waste_per_event_gs",
            "event_count",
        }


def test_waste_roi_empty_db_returns_empty_list(session_factory):
    """No ingredients → no rows."""
    with session_factory() as s:
        out = waste_roi_by_ingredient(s, since_days=90)
    assert out == []


def test_waste_roi_aggregates_per_ingredient(session_factory):
    """Two waste events on the same ingredient sum their costs."""
    with session_factory() as s:
        ing = make_ingredient(s, name="harina_000", unit="kg")
        # 2 waste events: ₲1000 + ₲500 = ₲1500 total
        make_waste_log(s, ingredient=ing, qty=1.0, cost_gs=1000)
        make_waste_log(s, ingredient=ing, qty=0.5, cost_gs=500)
        s.commit()

    with session_factory() as s:
        out = waste_roi_by_ingredient(s, since_days=90)

    assert len(out) == 1
    row = out[0]
    assert row["ingredient_id"] == ing.id
    assert row["total_waste_gs"] == 1500
    assert row["event_count"] == 2
    assert row["avg_waste_per_event_gs"] == 750


def test_waste_roi_sorted_by_total_cost_desc(session_factory):
    """Biggest money leaks first."""
    with session_factory() as s:
        cheap = make_ingredient(s, name="sal_500", unit="kg")
        expensive = make_ingredient(s, name="carne_5000", unit="kg")
        make_waste_log(s, ingredient=cheap, qty=1.0, cost_gs=500)
        make_waste_log(s, ingredient=expensive, qty=1.0, cost_gs=5000)
        s.commit()

    with session_factory() as s:
        out = waste_roi_by_ingredient(s, since_days=90)

    assert len(out) == 2
    # expensive first
    assert out[0]["total_waste_gs"] > out[1]["total_waste_gs"]
    assert out[0]["ingredient_id"] == expensive.id


def test_waste_roi_respects_since_days(session_factory):
    """Waste older than since_days is excluded."""
    with session_factory() as s:
        ing = make_ingredient(s, name="queso_xxx", unit="kg")
        old = datetime.now(ASUNCION_TZ) - timedelta(days=200)
        make_waste_log(s, ingredient=ing, qty=1.0, cost_gs=2000, at=old)
        s.commit()

    with session_factory() as s:
        out_90 = waste_roi_by_ingredient(s, since_days=90)
        out_365 = waste_roi_by_ingredient(s, since_days=365)

    assert out_90 == []
    assert len(out_365) == 1


def test_waste_vs_purchase_trend_returns_per_month_buckets(session_factory):
    """Per-month (year, month, cost_gs, event_count) tuples for one ingredient."""
    with session_factory() as s:
        ing = make_ingredient(s, name="leche_xxx", unit="l")
        now = datetime.now(ASUNCION_TZ)
        make_waste_log(s, ingredient=ing, qty=1.0, cost_gs=1000,
                      at=now - timedelta(days=5))
        make_waste_log(s, ingredient=ing, qty=0.5, cost_gs=500,
                      at=now - timedelta(days=35))
        s.commit()

    with session_factory() as s:
        trend = waste_vs_purchase_trend(s, ingredient_id=ing.id, since_days=90)

    assert isinstance(trend, list)
    assert len(trend) >= 1
    # Each row has year + month + cost_gs + event_count
    for row in trend:
        assert set(row.keys()) >= {"year", "month", "cost_gs", "event_count"}


def test_waste_vs_purchase_trend_empty_for_unknown_ingredient(session_factory):
    """Unknown ingredient → empty list, not an error."""
    with session_factory() as s:
        trend = waste_vs_purchase_trend(s, ingredient_id=999_999, since_days=90)
    assert trend == []


def test_mermas_cost_page_renders(client, session_factory):
    """/reportes/mermas-cost renders an empty state when no waste rows."""
    resp = client.get("/reportes/mermas-cost")
    assert resp.status_code == 200
    body = resp.text
    assert "Costo de mermas" in body or "mermas" in body.lower()


def test_mermas_cost_page_respects_days_param(client, session_factory):
    """/reportes/mermas-cost?days=30 honors the period param."""
    resp = client.get("/reportes/mermas-cost?days=30")
    assert resp.status_code == 200
    assert "30" in resp.text or "Últimos" in resp.text


def test_mermas_cost_page_clamps_invalid_days(client):
    """/reportes/mermas-cost?days=999 clamps to a sane max (365)."""
    resp = client.get("/reportes/mermas-cost?days=999")
    assert resp.status_code == 200
    # The template echoes `days`; with 999 input it should clamp to 365.
    assert "365" in resp.text


def test_mermas_cost_page_shows_ingredient_data(client, session_factory):
    """/reportes/mermas-cost surfaces an ingredient row when waste exists."""
    from datetime import datetime as dt

    from app.rms.config import ASUNCION_TZ
    from tests.factories import make_ingredient, make_waste_log

    with session_factory() as s:
        ing = make_ingredient(s, name="page_test_xyz", unit="kg")
        make_waste_log(s, ingredient=ing, qty=1.0, cost_gs=2500,
                      at=dt.now(ASUNCION_TZ))
        s.commit()

    resp = client.get("/reportes/mermas-cost")
    assert resp.status_code == 200
    assert "page_test_xyz" in resp.text
    assert "2,500" in resp.text or "2500" in resp.text
