"""tests/test_pro_merma_pedidos.py — PRO-MERMA + PRO-PED (2026-09-30).

PRO-MERMA: botón de merma en cada fila de /inventario → modal que postea a
/merma/registrar (la misma ruta del módulo). El test verifica que el modal
se incluya, que el botón esté por fila y que el POST rápido funcione.
PRO-PED: /produccion/manana muestra los pedidos confirmados de mañana.
"""
from __future__ import annotations

from sqlalchemy.orm import sessionmaker

from tests.factories import make_ingredient, make_product


def test_inventario_fila_tiene_boton_merma_y_modal(authed_client, session_factory):
    s = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        make_ingredient(s, unit="kg", stock_qty=5.0, min_stock_qty=1.0)
        s.commit()
    finally:
        s.close()
    r = authed_client.get("/inventario")
    assert r.status_code == 200
    assert "openMermaModal(" in r.text, "falta el botón de merma por fila"
    assert 'id="merma-modal"' in r.text, "falta el modal de merma"
    assert 'action="/merma/registrar"' in r.text, "el modal debe postear a /merma/registrar"


def test_merma_rapida_desde_modal_registra(authed_client, session_factory):
    s = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        ing = make_ingredient(s, unit="kg", stock_qty=5.0, min_stock_qty=1.0)
        iid = ing.id
        s.commit()
    finally:
        s.close()
    r = authed_client.post(
        "/merma/registrar",
        data={"ingredient_id": iid, "qty": "0.5", "qty_unit": "kg",
              "reason": "vencida", "notes": "test rápido"},
        follow_redirects=False,
    )
    assert r.status_code == 303, r.text[:300]
    s2 = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        from app.rms.models_legacy import WasteLog
        w = s2.query(WasteLog).order_by(WasteLog.id.desc()).first()
        assert w is not None and w.ingredient_id == iid and w.qty == 0.5
    finally:
        s2.close()


def test_produccion_manana_muestra_pedidos(authed_client, session_factory):
    from datetime import datetime, timedelta, timezone

    from app.rms.config import ASUNCION_TZ

    s = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        p = make_product(s, sale_price_gs=8000)
        manana = (datetime.now(ASUNCION_TZ) + timedelta(days=1)).date()
        from app.rms.models_legacy import Pedido, PedidoLine
        ped = Pedido(
            customer_name="Cliente Test",
            promised_date=manana,
            promised_time="10:00",
            channel="WhatsApp",
            status="confirmed",
            payment_intent="efectivo",
            public_token="T" + "x" * 11,
            public_token_expires_at=datetime.utcnow() + timedelta(days=30),
        )
        s.add(ped)
        s.flush()
        s.add(PedidoLine(pedido_id=ped.id, product_id=p.id, qty=3,
                         unit_price_gs=8000, fulfilled_qty=0))
        s.commit()
    finally:
        s.close()
    r = authed_client.get("/produccion/manana")
    assert r.status_code == 200
    assert "Pedidos para mañana" in r.text
    assert "Cliente Test" in r.text
