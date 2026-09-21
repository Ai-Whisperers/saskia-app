"""tests/test_reportes_precios.py — Phase D Q1-surface: /reportes/precios.

List view (all ingredients with events), detail view (line chart + event
table), CSV export, and ?days= validation.
"""

from __future__ import annotations

import pytest

from app.rms.models import Ingredient
from app.rms.price_history import record_price_event


@pytest.fixture
def priced_ingredient(session_factory):
    with session_factory() as s:
        ing = Ingredient(name="Harina reportes", unit="kg", stock_qty=5.0, purchase_price_gs=6000)
        s.add(ing)
        s.commit()
        ing_id = ing.id

    with session_factory() as s:
        for p in (5000, 5500, 6000):
            record_price_event(s, ing_id, p, source="manual")
            s.commit()
    return ing_id


def test_list_view_200_shows_stats(client, priced_ingredient):
    r = client.get("/reportes/precios")
    assert r.status_code == 200
    assert "Harina reportes" in r.text
    assert "5.000" in r.text  # min
    assert "6.000" in r.text  # max / current
    # link to detail view
    assert f"ingredient_id={priced_ingredient}" in r.text


def test_detail_view_200_has_chart_and_events(client, priced_ingredient):
    r = client.get(f"/reportes/precios?ingredient_id={priced_ingredient}")
    assert r.status_code == 200
    assert "<svg" in r.text  # line chart
    assert "Harina reportes" in r.text
    assert "Manual" in r.text  # source label in Spanish


def test_detail_view_unknown_ingredient_404(client):
    r = client.get("/reportes/precios?ingredient_id=999999")
    assert r.status_code == 404


def test_csv_export_headers_and_rows(client, priced_ingredient):
    r = client.get("/reportes/precios/csv")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers.get("content-disposition", "")
    lines = r.text.strip().splitlines()
    assert lines[0] == "ingredient_id,name,current,min,max,avg,last_event_at"
    assert any("Harina reportes" in line for line in lines[1:])


def test_days_param_validated(client):
    r = client.get("/reportes/precios?days=45")
    assert r.status_code == 422
    r2 = client.get("/reportes/precios/csv?days=45")
    assert r2.status_code == 422


def test_days_365_ok(client, priced_ingredient):
    r = client.get("/reportes/precios?days=365")
    assert r.status_code == 200
    assert "Harina reportes" in r.text
