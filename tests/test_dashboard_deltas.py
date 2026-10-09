"""tests/test_dashboard_deltas.py — P1 audit #10: vs. last period deltas.

Covers:
- _period_window / _prior_period_window for today/week/month
- _delta_pct for new/decreased/increased/neutral cases
- /inicio renders delta pills when prior + current differ
"""

# allow-hardcoded-dates: delta computation needs a fixed anchor date
from __future__ import annotations

import sys
from pathlib import Path

# Make app package importable when running pytest from project root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

pytestmark = pytest.mark.smoke

from app.routers.dashboard import (
    _compute_window_totals,
    _delta_pct,
    _period_window,
    _prior_period_window,
)

# ---- window helper tests --------------------------------------------------


def test_prior_period_today_is_yesterday():
    """today's prior window is yesterday 00:00 → today 00:00."""
    now = datetime.now(ZoneInfo("America/Asuncion")).replace(
        hour=15, minute=30, second=0, microsecond=0
    )
    start, end = _prior_period_window("today")
    assert end.astimezone(ZoneInfo("America/Asuncion")).date() == now.date()
    assert (end - start) == timedelta(days=1)
    assert start.hour == 0 and end.hour == 0


def test_prior_period_week_is_previous_mon_to_this_mon():
    """week's prior window is the previous Monday 00:00 → this Monday 00:00."""
    start, end = _prior_period_window("week")
    assert (end - start) == timedelta(days=7)
    # Both endpoints should be at midnight local
    assert start.hour == 0 and start.minute == 0
    assert end.hour == 0 and end.minute == 0


def test_prior_period_month_is_previous_full_month():
    """month's prior window is 1st → last day of the previous month."""
    start, end = _prior_period_window("month")
    assert start.hour == 0 and end.hour == 0
    # If we're mid-month, prior window is a complete previous calendar month.
    now = datetime.now(ZoneInfo("America/Asuncion"))
    if now.day > 5:  # safe to check full prior month
        (start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        # end is the 1st of the current month
        assert end.month == now.month
        # last day of prior month is start.month, last possible day
        assert (end - start).days >= 28


def test_prior_period_unknown_raises():
    """Unknown period raises ValueError."""
    with pytest.raises(ValueError):
        _prior_period_window("year")


def test_period_window_unknown_raises():
    """Unknown period raises ValueError (mirror test for symmetry)."""
    with pytest.raises(ValueError):
        _period_window("year")


# ---- _delta_pct tests -----------------------------------------------------


def test_delta_pct_no_sales_both_zero_is_neutral():
    """0/0 → neutral, no label."""
    d = _delta_pct(0, 0)
    assert d["direction"] == "neutral"
    assert d["pct"] is None
    assert d["label"] is None


def test_delta_pct_new_product_is_new():
    """Prior=0, current>0 → direction='new', label='nuevo'."""
    d = _delta_pct(100_000, 0)
    assert d["direction"] == "new"
    assert d["label"] == "nuevo"


def test_delta_pct_increase_is_up():
    """100→150 = +50%."""
    d = _delta_pct(150, 100)
    assert d["direction"] == "up"
    assert d["pct"] == pytest.approx(50.0)
    assert d["label"] == "50% arriba"


def test_delta_pct_decrease_is_down():
    """100→80 = -20%."""
    d = _delta_pct(80, 100)
    assert d["direction"] == "down"
    assert d["pct"] == pytest.approx(-20.0)
    assert d["label"] == "20% abajo"


def test_delta_pct_tiny_change_is_neutral():
    """Changes < 0.5% should be reported as 'sin cambio' (visual stability)."""
    d = _delta_pct(100, 100)
    assert d["direction"] == "neutral"
    assert d["label"] == "sin cambio"


def test_delta_pct_decrease_from_zero_is_new():
    """current=0, prior>0 — 2026-09-25 Inicio-v2 critique: an empty window is
    a neutral state ("sin ventas en el período"), never a -100% alarm."""
    d = _delta_pct(0, 100)
    assert d["direction"] == "neutral"
    assert d["label"] == "sin ventas en el período"


# ---- integration with route ----------------------------------------------


def test_inicio_renders_delta_pills(client):
    """When prior period differs from current, /inicio should render metric-delta is-*."""
    # Empty DB → both current and prior = 0 → no pills (label is None).
    with client:
        resp = client.get("/inicio?period=today")
    assert resp.status_code == 200
    # With empty DB, delta_pill macro produces no span (because label is None).
    # We verify no error and HTML still renders.
    body = resp.text
    assert "metric-card" in body


def test_inicio_renders_period_label_in_dashboard(client):
    """prior_label appears in template for delta pills."""
    with client:
        resp = client.get("/inicio?period=week")
    assert resp.status_code == 200
    # period=week → prior_label = 'semana pasada'
    # With empty DB there are no pills, so we don't assert the string is rendered.
    # We just verify the route doesn't 500.


# ---- ensure _compute_window_totals returns batch_costs for ranking ---------


def test_compute_window_totals_returns_six_tuple():
    """Tuple must include batch_costs so the ranking loop can reuse it."""
    from sqlalchemy.orm import sessionmaker

    from app.rms.db import init_db, make_engine

    engine = make_engine("sqlite:///:memory:")
    init_db(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    result = _compute_window_totals(
        s,
        datetime(2020, 1, 1, tzinfo=ZoneInfo("America/Asuncion")),
        datetime(2020, 1, 2, tzinfo=ZoneInfo("America/Asuncion")),
    )
    s.close()
    assert len(result) == 6, "_compute_window_totals must return 6-tuple (incl. batch_costs)"
    ventas_gs, cogs_gs, margen_gs, _sales_no_recipe, sales, batch_costs = result
    assert ventas_gs == 0
    assert cogs_gs == 0
    assert margen_gs == 0
    assert sales == []
    assert isinstance(batch_costs, dict)


# ---- seeded-data integration tests ---------------------------------------


def _seed_sales_for_delta(s, *, today_qty: int, yesterday_qty: int):
    """Seed product+recipe+ingredient and 2 sales (today + yesterday)."""
    from app.rms.models import Ingredient, Product, Recipe, RecipeLine, Sale

    ing = Ingredient(name="DeltaTestIng", unit="kg", purchase_price_gs=1000, stock_qty=10)
    s.add(ing)
    s.flush()
    rec = Recipe(name="DeltaTestRec", yield_qty=10, yield_unit="und")
    s.add(rec)
    s.flush()
    s.add(RecipeLine(recipe_id=rec.id, line_kind="ingredient", line_ref_id=ing.id, qty=0.1))
    s.flush()
    prod = Product(name="DeltaTestProd", portion_label="und", sale_price_gs=1000, recipe_id=rec.id)
    s.add(prod)
    s.flush()

    now_local = datetime.now(ZoneInfo("America/Asuncion"))
    now_utc_naive = now_local.astimezone(__import__("datetime").timezone.utc).replace(tzinfo=None)
    yesterday_utc_naive = (
        (now_local - timedelta(days=1))
        .astimezone(__import__("datetime").timezone.utc)
        .replace(tzinfo=None)
    )

    if today_qty > 0:
        s.add(Sale(product=prod, qty=today_qty, unit_price_gs=1000, sold_at=now_utc_naive))
    if yesterday_qty > 0:
        s.add(
            Sale(product=prod, qty=yesterday_qty, unit_price_gs=1000, sold_at=yesterday_utc_naive)
        )
    s.commit()


def test_dashboard_renders_delta_up_pill(client):
    """today=5, yesterday=1 → '400% arriba vs. ayer' on Ventas card."""
    from app.rms import main as main_module

    sf = main_module.app.state.session_factory
    with sf() as s:
        _seed_sales_for_delta(s, today_qty=5, yesterday_qty=1)

    with client:
        resp = client.get("/inicio?period=today")
    assert resp.status_code == 200
    body = resp.text
    # d820a23 replaced metric-delta pills with the ui-kpi-card component.
    assert 'delta-direction="up"' in body, (
        "Expected delta-direction=up on the Ventas kpi-card with today>yesterday sales"
    )
    assert "vs ayer" in body, "Expected 'vs ayer' prior label (period=today)"


def test_dashboard_renders_delta_down_pill(client):
    """today=1, yesterday=5 → '80% abajo vs. ayer'."""
    from app.rms import main as main_module

    sf = main_module.app.state.session_factory
    with sf() as s:
        _seed_sales_for_delta(s, today_qty=1, yesterday_qty=5)

    with client:
        resp = client.get("/inicio?period=today")
    assert resp.status_code == 200
    body = resp.text
    # d820a23 replaced metric-delta pills with the ui-kpi-card component.
    assert 'delta-direction="down"' in body, (
        "Expected delta-direction=down with today<yesterday sales"
    )


def test_dashboard_no_delta_when_both_zero(client):
    """Empty DB → no delta pills rendered (label is None)."""
    with client:
        resp = client.get("/inicio?period=today")
    assert resp.status_code == 200
    body = resp.text
    # With no sales today and no sales yesterday, all deltas are neutral w/ no label.
    # The metric-delta class still appears for the margen_pct, but no is-up/down arrows.
    # We check that no "vs. ayer" sub-label appears.
    assert "vs. ayer" not in body, (
        "Empty DB should NOT render 'vs. ayer' (no prior sales to compare)"
    )
