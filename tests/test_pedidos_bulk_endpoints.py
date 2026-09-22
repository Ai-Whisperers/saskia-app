"""Pedidos bulk endpoints tests."""
from __future__ import annotations

import pytest
from datetime import date
from app.rms.models import Pedido, PedidoLine, Product


def test_pedidos_bulk_fulfill_no_500(authed_client, session_factory):
    """POST /pedidos/bulk-fulfill with empty selection must not 500."""
    r = authed_client.post("/pedidos/bulk-fulfill", data={"selected": []})
    assert r.status_code < 500, (
        f"/pedidos/bulk-fulfill returned {r.status_code}: {r.text[:200]}"
    )


def test_pedidos_bulk_cancel_no_500(authed_client, session_factory):
    """POST /pedidos/bulk-cancel with empty selection must not 500."""
    r = authed_client.post("/pedidos/bulk-cancel", data={"selected": []})
    assert r.status_code < 500, (
        f"/pedidos/bulk-cancel returned {r.status_code}: {r.text[:200]}"
    )


def test_pedidos_board_page_loads(authed_client):
    """GET /pedidos/board must return 200."""
    r = authed_client.get("/pedidos/board")
    assert r.status_code == 200, f"/pedidos/board returned {r.status_code}"


def test_pedidos_nuevo_form_loads(authed_client):
    """GET /pedidos/nuevo must return 200."""
    r = authed_client.get("/pedidos/nuevo")
    assert r.status_code == 200, f"/pedidos/nuevo returned {r.status_code}"


def test_pedidos_detail_page_loads(authed_client, session_factory):
    """GET /pedidos/{id} must return 200 for existing pedido."""
    from app.rms.models import Pedido

    with session_factory() as s:
        pedido = Pedido(
            customer_name="Bulk Test",
            promised_date=date.today(),
            channel="mostrador",
            status="pending",
        )
        s.add(pedido)
        s.commit()
        s.refresh(pedido)
        pedido_id = pedido.id

    r = authed_client.get(f"/pedidos/{pedido_id}")
    assert r.status_code == 200, f"/pedidos/{pedido_id} returned {r.status_code}"
