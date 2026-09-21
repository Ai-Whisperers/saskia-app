"""tests/test_inventario_price_strip.py — Phase D Q1-surface: /inventario strip.

Under the purchase-price cell, ingredients with >=2 price events in the
last 90 days show a muted "90d: min X · max Y" line; >=3 events also get
a sparkline SVG (charts.sparkline).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.rms.models import Ingredient
from app.rms.price_history import record_price_event


def _seed_with_events(session_factory, name, prices):
    """Seed an ingredient + one price event per price (recent)."""
    with session_factory() as s:
        ing = Ingredient(name=name, unit="kg", stock_qty=5.0, min_stock_qty=1.0)
        s.add(ing)
        s.commit()
        ing_id = ing.id

    with session_factory() as s:
        for p in prices:
            record_price_event(s, ing_id, p, source="manual")
            s.commit()
    return ing_id


def test_single_event_no_strip(client, session_factory):
    _seed_with_events(session_factory, "Una precio", [5000])
    _seed_with_events(session_factory, "Cero eventos", [])
    r = client.get("/inventario")
    assert r.status_code == 200
    assert "90d:" not in r.text


def test_three_events_show_strip_and_sparkline(client, session_factory):
    ing_id = _seed_with_events(session_factory, "Tres precios", [5000, 5500, 6000])
    r = client.get("/inventario")
    assert r.status_code == 200
    body = r.text
    # min/max muted line
    assert "90d:" in body
    assert "min" in body and "max" in body
    # min 5.000 / max 6.000 rendered via money format (dots as thousands)
    assert "5.000" in body and "6.000" in body
    # sparkline svg present for this ingredient
    assert 'class="sparkline"' in body
    assert "Tres precios" in body
