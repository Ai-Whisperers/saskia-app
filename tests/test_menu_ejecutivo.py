"""tests/test_menu_ejecutivo.py — WP-4.2 (2026-10-07).

Menú ejecutivo: expansión a productos con precio de menú en la 1ra
línea; venta por API descuenta stock por producto; ABM page renders.
"""

from __future__ import annotations

import pytest


def _mk(session_factory, model, **kw):
    with session_factory() as s:
        obj = model(**kw)
        s.add(obj)
        s.commit()
        return obj.id


def _products(session_factory, n=2, price=20_000):
    from tests.factories import make_product

    ids = []
    with session_factory() as s:
        for i in range(n):
            p = make_product(s, name=f"MenuProd{i}", sale_price_gs=price)
            s.add(p)
            s.commit()
            ids.append(p.id)
    return ids


def test_expand_menu_pricing(session_factory):
    from app.rms.menu_ejecutivo import expand_menu_items
    from app.rms.models_legacy import Menu, MenuItem

    ids = _products(session_factory)
    mid = _mk(
        session_factory,
        Menu,
        name="Ejecutivo",
        price_gs=35_000,
        active=True,
        tenant_id=1,
    )
    with session_factory() as s:
        s.add(MenuItem(menu_id=mid, product_id=ids[0], qty=1))
        s.add(MenuItem(menu_id=mid, product_id=ids[1], qty=0.5))
        s.commit()
        lines = expand_menu_items(s, mid, 2)
        assert [(p, q) for p, q, _ in lines] == [(ids[0], 2.0), (ids[1], 1.0)]
        # precio del menú en la primera línea ×2 (qty del menú)
        assert lines[0][2] == 35_000
        assert lines[1][2] == 0


def test_expand_inactive_menu_rejected(session_factory):
    from app.rms.menu_ejecutivo import MenuNotFound, expand_menu_items
    from app.rms.models_legacy import Menu

    mid = _mk(session_factory, Menu, name="Off", price_gs=1_000, active=False, tenant_id=1)
    with session_factory() as s:
        with pytest.raises(MenuNotFound):
            expand_menu_items(s, mid, 1)


def test_venta_menu_via_api(authed_client, session_factory):
    from app.rms.models_legacy import Menu, MenuItem, Sale

    ids = _products(session_factory)
    mid = _mk(session_factory, Menu, name="Combo API", price_gs=30_000, active=True, tenant_id=1)
    with session_factory() as s:
        s.add(MenuItem(menu_id=mid, product_id=ids[0], qty=1))
        s.add(MenuItem(menu_id=mid, product_id=ids[1], qty=1))
        s.commit()

    r = authed_client.post(
        "/ventas/nueva/multi",
        json={
            "items": [{"menu_id": mid, "qty": 1}],
            "payment_method": "efectivo",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303, r.text[:300]
    with session_factory() as s:
        rows = s.query(Sale).order_by(Sale.id.desc()).limit(2).all()
        total = sum(r_.unit_price_gs * r_.qty for r_ in rows)
        assert total == 30_000  # precio del menú, NO sumatoria (40k)
        assert {r_.product_id for r_ in rows} == set(ids)


def test_menus_page_renders(authed_client):
    r = authed_client.get("/menus")
    assert r.status_code == 200
    assert "Menús ejecutivos" in r.text


def test_both_ids_rejected(authed_client):
    r = authed_client.post(
        "/ventas/nueva/multi",
        json={"items": [{"product_id": 1, "menu_id": 1, "qty": 1}]},
        follow_redirects=False,
    )
    assert r.status_code == 400


def test_pos_shows_menus_strip(authed_client, session_factory):
    """WP-4.2 UI: GET /ventas renderiza la franja de menús ejecutivos
    con nombre + precio + data-menu-id cuando hay menús activos."""
    from app.rms.models_legacy import Menu, MenuItem

    ids = _products(session_factory)
    mid = _mk(
        session_factory, Menu, name="Ejecutivo Midday", price_gs=35_000, active=True, tenant_id=1
    )
    with session_factory() as s:
        s.add(MenuItem(menu_id=mid, product_id=ids[0], qty=1))
        s.commit()

    r = authed_client.get("/ventas")
    assert r.status_code == 200
    body = r.content.decode()
    assert "Menús ejecutivos" in body
    assert "data-menu-id" in body or f"addMenuToCart({mid}" in body
    assert "Ejecutivo Midday" in body
    assert "Gs. 35.000" in body


def test_pos_hides_menus_strip_when_empty(authed_client, session_factory):
    """Sin menús activos la franja no aparece (cero ruido en el POS)."""
    from app.rms.models_legacy import Menu

    with session_factory() as s:
        for m in s.query(Menu).all():
            m.active = False
        s.commit()
    r = authed_client.get("/ventas")
    assert r.status_code == 200
    assert "Menús ejecutivos" not in r.content.decode()
