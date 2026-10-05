"""tests/test_pos_payment_default.py — PRO-POS (2026-09-30).

El 98,7% de las ventas de prod quedaron con payment_method=NULL porque
/nueva/multi guardaba None silencioso. Ahora el default (is_default →
'efectivo') llena el método cuando el operador no lo elige.
"""

from __future__ import annotations

from sqlalchemy.orm import sessionmaker

from tests.factories import make_ingredient, make_product, make_recipe


def _seed(s):
    """Producto CON receta (para que el flujo completo de costing corra)."""
    make_ingredient(s, unit="kg", stock_qty=10.0, min_stock_qty=2.0)
    rec = make_recipe(s, yield_qty=12, yield_unit="und")
    p = make_product(s, sale_price_gs=7000, recipe=rec)
    s.commit()
    return p


def test_venta_sin_pago_usa_default_efectivo(authed_client, session_factory):
    s = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        p = _seed(s)
        pid = p.id
    finally:
        s.close()
    r = authed_client.post(
        "/ventas/nueva/multi",
        json={"items": [{"product_id": pid, "qty": 2}], "payment_method": ""},
        follow_redirects=False,
    )
    assert r.status_code == 303, r.text[:300]
    s2 = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        from app.rms.models_legacy import Sale

        sale = s2.query(Sale).order_by(Sale.id.desc()).first()
        assert sale is not None
        assert sale.payment_method == "efectivo", (
            f"payment_method={sale.payment_method!r} — debió usar default"
        )
    finally:
        s2.close()


def test_venta_con_pago_explorado_lo_respeta(authed_client, session_factory):
    s = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        p = _seed(s)
        pid = p.id
    finally:
        s.close()
    r = authed_client.post(
        "/ventas/nueva/multi",
        json={"items": [{"product_id": pid, "qty": 1}], "payment_method": "qr"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    s2 = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        from app.rms.models_legacy import Sale

        sale = s2.query(Sale).order_by(Sale.id.desc()).first()
        assert sale.payment_method == "qr"
    finally:
        s2.close()
