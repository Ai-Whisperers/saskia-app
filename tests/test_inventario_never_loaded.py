"""tests/test_inventario_never_loaded.py — PRO-INV (2026-09-30).

El KPI "Stock crítico" mezclaba "nunca cargué stock inicial" con "me agoté
de verdad": en día 1 mostraba 65 críticos cuando solo ~44 eran reales.

- Ingredientes con stock 0 y CERO movimientos en el ledger → "Sin carga
  inicial" (badge neutral, KPI separado, filtro estado=sincargar).
- Ingredientes con stock 0 y movimientos → crítico real (rojo).
- /inventario/carga-inicial: pantalla de carga masiva del faltante.
"""
from __future__ import annotations

from sqlalchemy.orm import sessionmaker

from tests.factories import make_ingredient


def _seed(s):
    agotado = make_ingredient(s, name="Harina agotada", unit="kg", stock_qty=0.0, min_stock_qty=2.0)
    nunca = make_ingredient(s, name="Vaso 8oz", unit="und", stock_qty=0.0, min_stock_qty=50.0)
    ok = make_ingredient(s, name="Azúcar OK", unit="kg", stock_qty=5.0, min_stock_qty=1.0)
    from datetime import datetime, timezone

    from app.rms.models_legacy import StockMovement

    s.add(StockMovement(
        ingredient_id=agotado.id,
        movement_type="adjustment",
        qty=-3.0,
        reason="prueba",
        recorded_at=datetime.now(timezone.utc),
    ))
    s.commit()
    return agotado, nunca, ok


def test_kpi_separates_never_loaded_from_critical(client, session_factory):
    s = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        _seed(s)
    finally:
        s.close()
    r = client.get("/inventario")
    assert r.status_code == 200
    # el crítico real aparece; el nunca-cargado va aparte
    assert "Sin carga inicial" in r.text or "sin carga inicial" in r.text
    assert "Harina agotada" in r.text


def test_filtro_estado_sincargar(client, session_factory):
    s = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        _seed(s)
    finally:
        s.close()
    r = client.get("/inventario?estado=sincargar")
    assert r.status_code == 200
    assert "Vaso 8oz" in r.text
    assert "Harina agotada" not in r.text


def test_carga_inicial_view_lists_and_saves(authed_client, session_factory):
    s = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        _agotado, nunca, _ok = _seed(s)
        nunca_id = nunca.id
    finally:
        s.close()
    # vista: lista solo los nunca-cargados
    r = authed_client.get("/inventario/carga-inicial")
    assert r.status_code == 200
    assert "Vaso 8oz" in r.text
    assert "Harina agotada" not in r.text  # ya tiene movimientos

    # guardar: qty_ para el vaso
    r2 = authed_client.post("/inventario/carga-inicial", data={"qty_%d" % nunca_id: "60"}, follow_redirects=False)
    assert r2.status_code == 303
    s2 = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        from app.rms.models_legacy import Ingredient, StockMovement

        ing = s2.get(Ingredient, nunca_id)
        assert ing.stock_qty == 60.0
        mv = s2.query(StockMovement).filter_by(ingredient_id=nunca_id, movement_type="initial").one()
        assert mv.qty == 60.0
        # tras la carga ya no está en la pantalla
    finally:
        s2.close()
    r3 = authed_client.get("/inventario/carga-inicial")
    assert "Vaso 8oz" not in r3.text
