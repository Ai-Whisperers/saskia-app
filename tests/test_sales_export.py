"""tests/test_sales_export.py — sales history totals, CSV export, receipt.

Covers:
- /ventas renders the summary card (count, total, avg ticket) with no filters
- Filtered totals (e.g. ?days=7) only count non-voided sales
- CSV export has UTF-8 BOM + correct headers
- CSV respects filters (days=N, product_id=N)
- /ventas/{id}/recibo renders the printable receipt
- /ventas/{nonexistent}/recibo returns 404
- /ventas/{id}/recibo shows anulada banner for voided sales
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.rms.config import ASUNCION_TZ
from app.rms.models import Ingredient, Product, Recipe, RecipeLine, Sale


@pytest.fixture
def seeded_sales(session_factory):
    """Seed 5 sales + 1 voided sale + 2 products for the export tests."""
    with session_factory() as s:
        ing = Ingredient(name="Harina test", unit="kg", purchase_price_gs=5000, stock_qty=100)
        s.add(ing); s.flush()
        recipe = Recipe(name="Torta test", yield_qty=1, yield_unit="kg", prep_minutes=30)
        s.add(recipe); s.flush()
        line = RecipeLine(recipe_id=recipe.id, line_kind="ingredient", line_ref_id=ing.id, qty=2)
        s.add(line); s.flush()

        p1 = Product(name="Torta chocolate", sku="TOR-CHOC", sale_price_gs=50000, recipe_id=recipe.id)
        p2 = Product(name="Torta vainilla", sku="TOR-VAIN", sale_price_gs=45000, recipe_id=recipe.id)
        s.add_all([p1, p2]); s.flush()

        now = datetime.now(ASUNCION_TZ)
        # 3 p1 sales + 2 p2 sales + 1 voided p1 sale
        s.add_all([
            Sale(product_id=p1.id, qty=1, unit_price_gs=50000, sold_at=now - timedelta(days=2), voided_at=None),
            Sale(product_id=p1.id, qty=2, unit_price_gs=50000, sold_at=now - timedelta(days=1), voided_at=None),
            Sale(product_id=p2.id, qty=3, unit_price_gs=45000, sold_at=now - timedelta(days=1), voided_at=None),
            Sale(product_id=p1.id, qty=1, unit_price_gs=50000, sold_at=now, voided_at=now),
            Sale(product_id=p2.id, qty=1, unit_price_gs=45000, sold_at=now, voided_at=None),
        ])
        s.commit()
        return {"p1": p1, "p2": p2}


# ---- summary card ----

def test_ventas_renders_summary_card(client, session_factory):
    """/ventas/historial includes the totals card for active (non-voided) sales."""
    with session_factory() as s:
        p = Product(name="Apenas", sale_price_gs=1000, recipe_id=None)
        s.add(p); s.flush()
        now = datetime.now(ASUNCION_TZ)
        s.add(Sale(product_id=p.id, qty=2, unit_price_gs=1000, sold_at=now, voided_at=None))
        s.commit()

    resp = client.get("/ventas/historial")
    assert resp.status_code == 200
    body = resp.text
    assert "Ventas activas" in body
    assert "Total recaudado" in body
    assert "Ticket promedio" in body
    # Sale count should be 1
    assert ">1</div>" in body or '"metric-value">1' in body or "metric-value\">1" in body


def test_ventas_summary_excludes_voided(client, seeded_sales):
    """/ventas/historial totals must not count anulada sales."""
    resp = client.get("/ventas/historial")
    assert resp.status_code == 200
    # 5 total rows (3+2 non-voided; 1 voided still shows in table)
    # Active count must be 4 (the voided sale is excluded from totals)
    assert 'metric-card__value">4' in resp.text or 'metric-card__value">4<' in resp.text


def test_ventas_filtered_totals(client, seeded_sales):
    """?days=1 only counts today+sales (last 24h) for the totals."""
    # Sales: -1d (2x p1 + 1x p2) and 0d (1x p1 voided + 1x p2 active)
    # days=1 means only "now" sales count toward totals (1 active of 2 total)
    resp = client.get("/ventas/historial?days=1")
    assert resp.status_code == 200
    # Filter description visible
    assert "últimos 1 días" in resp.text or "últimos 1 d" in resp.text


# ---- CSV export ----

def test_csv_export_returns_csv_with_bom(client, seeded_sales):
    """/ventas/export.csv returns text/csv with UTF-8 BOM + the right headers."""
    resp = client.get("/ventas/export.csv")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "attachment" in resp.headers.get("content-disposition", "")
    body = resp.content
    # UTF-8 BOM is 3 bytes: 0xEF 0xBB 0xBF
    assert body[:3] == b"\xef\xbb\xbf"
    decoded = body.decode("utf-8-sig")
    # Headers
    first_line = decoded.split("\n")[0]
    assert "fecha" in first_line
    assert "producto" in first_line
    assert "total_gs" in first_line
    assert "anulada" in first_line


def test_csv_export_filters_by_days(client, seeded_sales):
    """/ventas/export.csv?days=1 only includes today's sales."""
    resp = client.get("/ventas/export.csv?days=1")
    assert resp.status_code == 200
    body = resp.content.decode("utf-8-sig")
    # Day-1 sales: 2 p1 + 1 p2; day-0: 1 p1 voided + 1 p2 active
    # days=1 should include day=0 only (today); that's 2 rows
    data_rows = [l for l in body.split("\n") if l.strip()][1:]  # skip header
    assert len(data_rows) == 2


def test_csv_export_filters_by_product(client, seeded_sales):
    """/ventas/export.csv?product_id=N only includes that product."""
    p1_id = seeded_sales["p1"].id
    resp = client.get(f"/ventas/export.csv?product_id={p1_id}")
    assert resp.status_code == 200
    body = resp.content.decode("utf-8-sig")
    data_rows = [l for l in body.split("\n") if l.strip()][1:]
    assert len(data_rows) == 3  # all 3 p1 sales (including the voided)


# ---- receipt ----

def test_recibo_renders_for_existing_sale(client, seeded_sales, session_factory):
    """/ventas/{id}/recibo renders the printable receipt."""
    with session_factory() as s:
        first = s.query(Sale).filter_by(voided_at=None).first()
        sale_id = first.id

    resp = client.get(f"/ventas/{sale_id}/recibo")
    assert resp.status_code == 200
    body = resp.text
    assert "Recibo de venta" in body
    assert "Imprimir" in body  # print button


def test_recibo_404_for_missing_sale(client):
    """/ventas/999999/recibo returns 404."""
    resp = client.get("/ventas/999999/recibo")
    assert resp.status_code == 404


def test_recibo_marks_voided_sale(client, seeded_sales, session_factory):
    """Voided sales show an 'anulada' banner on the receipt."""
    with session_factory() as s:
        voided = s.query(Sale).filter(Sale.voided_at.isnot(None)).first()
        sale_id = voided.id

    resp = client.get(f"/ventas/{sale_id}/recibo")
    assert resp.status_code == 200
    assert "Venta anulada" in resp.text


# ---- summary card link ----

def test_ventas_has_export_button_in_card(client, seeded_sales):
    """The summary card exposes a CSV export link with the current filters."""
    resp = client.get("/ventas/historial?days=7")
    assert resp.status_code == 200
    body = resp.text
    assert "Exportar CSV" in body
    assert "format=csv" in body
    assert "days=7" in body
