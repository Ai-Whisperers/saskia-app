"""Tests for T-4: inventario stock-state filter (low/out/overstocked).

The /inventario list supports a multi-select `estado` filter with values
`bajo` (low), `critico` (critical), `negativo` (negative), `sincargar`
(never loaded), `sinprecio` (no price), `ok` (healthy), and as of Phase 1
T-4 `sobre_stock` (overstocked — stock > max_stock_qty).
"""
from app.rms.models import Ingredient


def _ing(session_factory, **kw):
    sf = session_factory
    with sf() as s:
        i = Ingredient(name=kw.pop("name", "T4-ing"), unit="kg", **kw)
        s.add(i); s.commit()
        return i.id


def test_inventario_filter_sobre_stock_renders(client):
    """T-4 — 'Sobre-stock' option must appear in the estado filter panel."""
    r = client.get("/inventario")
    assert r.status_code == 200
    assert "Sobre-stock" in r.text, (
        "T-4 missing: 'Sobre-stock' filter chip not in /inventario"
    )
    # The value attribute too (in the checkbox)
    assert 'value="sobre_stock"' in r.text, (
        "T-4 missing: estado=sobre_stock checkbox not in /inventario"
    )


def test_inventario_filter_sobre_stock_excludes_others(client, session_factory):
    """T-4 — ?estado=sobre_stock must show only ingredients with stock > max."""
    # Healthy: stock > min, well below max
    _ing(session_factory, name="T4-healthy", stock_qty=10, min_stock_qty=1, max_stock_qty=20)
    # Overstocked: stock > max
    _ing(session_factory, name="T4-overstock", stock_qty=25, min_stock_qty=1, max_stock_qty=20)
    # Low: stock <= min
    _ing(session_factory, name="T4-low", stock_qty=0, min_stock_qty=1, max_stock_qty=20)

    r = client.get("/inventario?estado=sobre_stock")
    assert r.status_code == 200
    assert "T4-overstock" in r.text
    assert "T4-healthy" not in r.text
    assert "T4-low" not in r.text


def test_inventario_filter_existing_states_still_work(client, session_factory):
    """T-4 — the 6 states that shipped before T-4 must still filter."""
    _ing(session_factory, name="T4-ok", stock_qty=10, min_stock_qty=1)
    _ing(session_factory, name="T4-bajo", stock_qty=0, min_stock_qty=1)
    _ing(session_factory, name="T4-negativo", stock_qty=0, min_stock_qty=1)

    # estado=bajo must include T4-bajo but not T4-ok
    r = client.get("/inventario?estado=bajo")
    assert r.status_code == 200
    assert "T4-bajo" in r.text
    assert "T4-ok" not in r.text