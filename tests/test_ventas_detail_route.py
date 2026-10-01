"""Tests for /ventas/{sale_id} detail page (BACKLOG #16)."""

from __future__ import annotations

import pytest
from sqlalchemy import text


def _make_sale(session_factory, *, with_stock_moves=False):
    """Insert a product + sale via the test factories; returns the sale id."""
    from tests.factories import make_ingredient, make_product, make_recipe, make_sale

    sid = None
    with session_factory() as s:
        ing = make_ingredient(s, name="Harina", unit="kg")
        recipe = make_recipe(s)
        p = make_product(s)
        sale = make_sale(s, product=p, qty=2.0, unit_price_gs=10000)
        s.flush()
        sid = sale.id
        if with_stock_moves:
            s.execute(text(
                "INSERT INTO sale_stock_move (sale_id, affected_recipe_id, ingredient_id, qty_delta) "
                "VALUES (:sid, :rid, :iid, -0.5)"
            ), {"sid": sid, "rid": recipe.id, "iid": ing.id})
        s.commit()
    return sid


def test_ventas_detail_renders(client, session_factory):
    sid = _make_sale(session_factory)
    r = client.get(f"/ventas/{sid}")
    assert r.status_code == 200
    body = r.text
    assert f"Venta #{sid}" in body
    assert "Pago y canal" in body


def test_ventas_detail_404_on_missing(client):
    r = client.get("/ventas/9999999")
    assert r.status_code in (404, 410)


def test_ventas_detail_shows_voided_banner(client, session_factory):
    """When sale.voided_at is set, show the ANULADO banner."""
    sid = _make_sale(session_factory)
    with session_factory() as s:
        s.execute(text(
            "UPDATE sale SET voided_at = CURRENT_TIMESTAMP, voided_by = 'tester', void_reason = 'client cancel' WHERE id = :id"
        ), {"id": sid})
        s.commit()
    r = client.get(f"/ventas/{sid}")
    assert r.status_code == 200
    assert "ANULADO" in r.text
    assert "tester" in r.text
    # Anular button must be hidden for voided sales
    assert "Anular venta" not in r.text


def test_ventas_detail_renders_stock_moves(client, session_factory):
    """When SaleStockMove rows exist, show the stock-moves card."""
    sid = _make_sale(session_factory, with_stock_moves=True)
    r = client.get(f"/ventas/{sid}")
    assert r.status_code == 200
    assert "Stock moves" in r.text


def test_ventas_detail_recibo_link(client, session_factory):
    """Detail page should link to the printable recibo."""
    sid = _make_sale(session_factory)
    r = client.get(f"/ventas/{sid}")
    assert f"/ventas/{sid}/recibo" in r.text


def test_ventas_recibo_still_works(client, session_factory):
    """Regression: /{sale_id}/recibo must not be shadowed by /{sale_id}."""
    sid = _make_sale(session_factory)
    r = client.get(f"/ventas/{sid}/recibo")
    assert r.status_code == 200
    # Recibo template uses different page chrome ("Recibo de venta")
    assert "Recibo de venta" in r.text or "Recibo" in r.text