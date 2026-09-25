"""tests/test_price_insight.py — Phase D Q1-surface: dashboard price insight.

'price_fluctuation' in InsightsPanel: ingredients whose current price is
>20% above their 30d avg. No crossers → no card, no error.
"""

from __future__ import annotations

from app.rms.models import Ingredient
from app.rms.price_history import record_price_event


def _seed(session_factory, name, prices):
    with session_factory() as s:
        ing = Ingredient(name=name, unit="kg", stock_qty=5.0)
        s.add(ing)
        s.commit()
        ing_id = ing.id
    with session_factory() as s:
        for p in prices:
            record_price_event(s, ing_id, p, source="manual")
            s.commit()
    return ing_id


def test_rising_ingredient_appears_in_insight(session_factory):
    """~+30% above avg crosses the 20% threshold."""
    # avg of 5000,5000,5000 = 5000; current 6500 = +30%
    _seed(session_factory, "Harina alza", [5000, 5000, 5000, 6500])

    from app.rms.insights import build_insights

    with session_factory() as s:
        panel = build_insights(s)

    names = [item["name"] for item in panel.price_fluctuation]
    assert "Harina alza" in names
    item = next(i for i in panel.price_fluctuation if i["name"] == "Harina alza")
    assert item["pct_above_avg"] > 20


def test_stable_ingredient_not_flagged(session_factory):
    # avg 5000, current 5200 = +4% — below threshold
    _seed(session_factory, "Sal estable", [5000, 5100, 5150, 5200])

    from app.rms.insights import build_insights

    with session_factory() as s:
        panel = build_insights(s)

    names = [item["name"] for item in panel.price_fluctuation]
    assert "Sal estable" not in names


def test_empty_db_no_card_no_error(session_factory):
    from app.rms.insights import build_insights

    with session_factory() as s:
        panel = build_insights(s)
    assert panel.price_fluctuation == []


def test_dashboard_shows_card_only_when_crossing(client, session_factory):
    """Dashboard surfaces the insight card via the existing mechanism."""
    r = client.get("/analisis")
    assert r.status_code == 200
    assert "Precios en alza" not in r.text

    _seed(session_factory, "Harina dashboard", [5000, 5000, 5000, 7000])
    r2 = client.get("/analisis")
    assert r2.status_code == 200
    assert "Precios en alza" in r2.text
    assert "Harina dashboard" in r2.text
    assert "+27%" in r2.text  # 7000 vs avg(5000,5000,5000,7000)=5500 -> +27.3%
