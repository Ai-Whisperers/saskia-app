"""tests/test_produccion_hidden_products.py — PRO-11.

Un producto con is_available=False (oculto del menú/POS) con ventas
históricas NO debe recibir sugerencia automática en el plan de producción.
Si la operadora lo fuerza con un override/template/manual, sí aparece.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import sessionmaker

from tests.factories import make_ingredient, make_product, make_recipe, make_sale


def _seed(s):
    make_ingredient(s, unit="kg", stock_qty=10.0, min_stock_qty=2.0)
    rec = make_recipe(s, yield_qty=12, yield_unit="und")
    activo = make_product(s, sale_price_gs=7000, recipe=rec, name="Producto activo")
    oculto = make_product(
        s, sale_price_gs=3000, recipe=rec, name="Producto oculto", is_available=False
    )
    now = datetime.now(timezone.utc)
    for _ in range(3):
        make_sale(s, product=activo, qty=2, at=now - timedelta(days=1))
        make_sale(s, product=oculto, qty=2, at=now - timedelta(days=1))
    s.commit()
    return activo, oculto


def test_plan_auto_no_sugiere_ocultos(session_factory):
    """Auto-forecast (rolling): el oculto no aparece en las filas del plan."""
    from app.rms.production import plan_production

    s = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        _activo, _oculto = _seed(s)
        plan = plan_production(s)
        nombres = {r.product_name for r in plan.rows if r.qty_to_produce > 0}
        assert any("activo" in n for n in nombres), f"activo debería planificar: {nombres}"
        assert not any("oculto" in n for n in nombres), (
            f"oculto no debe recibir auto-sugerencia: {nombres}"
        )
    finally:
        s.close()


def test_plan_override_fuerza_oculto(client, session_factory):
    """Con override explícito para la fecha, el oculto SÍ aparece."""
    from datetime import datetime

    from app.rms.config import ASUNCION_TZ
    from app.rms.production import plan_production, upsert_override

    s = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        _activo, oculto = _seed(s)
        manana = datetime.now(ASUNCION_TZ).date() + timedelta(days=1)
        upsert_override(s, for_date=manana, product_id=oculto.id, qty=6.0, updated_by="test")
        plan = plan_production(s, for_date=manana)
        filas = {r.product_id: r.qty_to_produce for r in plan.rows}
        assert filas.get(oculto.id) == 6.0, f"override debe respetarse: {filas}"
    finally:
        s.close()
