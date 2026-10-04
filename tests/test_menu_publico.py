"""Public /menu catalog page — no-login customer-facing menu.

Covers:
  - 200 without auth, lists visible+available products grouped by category
  - hides unavailable / tablet-invisible products
  - category grouping order + custom categories
  - deep-links to /m/{slug} when set
  - empty state
"""

from __future__ import annotations


def _mk_product(
    session,
    name,
    *,
    category="panaderia",
    price=5000,
    available=True,
    visible=True,
    slug=None,
    portion="1 und",
):
    from app.rms.models import Product

    p = Product(
        name=name,
        sale_price_gs=price,
        portion_label=portion,
        category=category,
        is_available=available,
        tablet_visible=visible,
        tablet_slug=slug,
    )
    session.add(p)
    session.flush()
    return p


def test_menu_publico_renders_without_login(client, session_factory):
    """/menu returns 200 with products, no auth required."""
    with session_factory() as s:
        _mk_product(s, "Chipa Guazú Menú", category="panaderia", slug="chipa-menu")
        _mk_product(s, "Café Menú", category="bebida")
        s.commit()

    resp = client.get("/menu")
    assert resp.status_code == 200
    body = resp.text
    assert "Chipa Guazú Menú" in body
    assert "Café Menú" in body
    # Category section headers
    assert "Panadería" in body
    assert "Bebidas" in body
    # The page's own public chrome renders (no app-shell body class gate
    # on the menu container itself).
    assert "menu-publico" in body
    # NOTE: we don't assert sidebar absence — under SASKIA_TEST_AUTH_DISABLED
    # (this test env) render() forces is_logged_in=True, so base.html draws
    # the shell. In production /menu without a session cookie renders
    # logged-out chrome (no sidebar), which is the actual requirement.


def test_menu_publico_hides_unavailable_and_hidden(client, session_factory):
    """is_available=False or tablet_visible=False products don't leak."""
    with session_factory() as s:
        _mk_product(s, "Torta Visible", available=True, visible=True)
        _mk_product(s, "Torta Sin Stock", available=False, visible=True)
        _mk_product(s, "Torta Oculta", available=True, visible=False)
        s.commit()

    resp = client.get("/menu")
    assert resp.status_code == 200
    assert "Torta Visible" in resp.text
    assert "Torta Sin Stock" not in resp.text
    assert "Torta Oculta" not in resp.text


def test_menu_publico_groups_by_category_with_links(client, session_factory):
    """Items land in the right section; slug deep-links to /m/{slug}."""
    with session_factory() as s:
        _mk_product(s, "Medialuna Menú", category="pasteleria", slug="medialuna-menu")
        _mk_product(s, "Pan Menú", category="panaderia")
        s.commit()

    resp = client.get("/menu")
    body = resp.text
    # Deep link
    assert "/m/medialuna-menu" in body
    # Pastelería section appears after Panadería (canonical order)
    idx_pan = body.find("Panadería")
    idx_pas = body.find("Pastelería")
    assert 0 < idx_pan < idx_pas


def test_menu_publico_empty_state(client, session_factory):
    """No visible products → friendly empty message, not a crash."""
    resp = client.get("/menu")
    assert resp.status_code == 200
    assert "no tiene productos publicados" in resp.text


def test_menu_hides_order_ui_without_whatsapp(client):
    """No shop_whatsapp setting -> no cart buttons on /menu (pure brochure)."""
    resp = client.get("/menu")
    assert resp.status_code == 200
    assert "data-add" not in resp.text
    assert "mp-cartbar" not in resp.text


def test_menu_shows_order_ui_with_whatsapp(session_factory, client):
    """Setting shop_whatsapp turns on the per-item + Agregar buttons."""
    from datetime import datetime as _dt

    from app.rms.models import Product, Recipe, SettingsKV

    with session_factory() as session:
        session.add(
            SettingsKV(key="shop_whatsapp", value_json="595981123456", updated_at=_dt.utcnow())
        )
        # Seed one visible product so a card (+ its Agregar button) renders.
        recipe = Recipe(name="R menu", yield_qty=1, yield_unit="und")
        session.add(recipe)
        session.flush()
        session.add(
            Product(
                name="Torta test",
                recipe_id=recipe.id,
                sale_price_gs=10000,
                is_available=True,
                tablet_visible=True,
            )
        )
        session.commit()

    resp = client.get("/menu")
    assert resp.status_code == 200
    assert 'data-add="' in resp.text
    assert "mp-cartbar" in resp.text
    assert "595981123456" in resp.text  # WA digits embedded for the JS cart


def test_settings_shop_whatsapp_roundtrip(client):
    """POST then GET /api/settings/shop-whatsapp stores digits-only."""
    r = client.post("/api/settings/shop-whatsapp", json={"phone": "+595 981 123-456"})
    assert r.status_code == 200
    assert r.json()["phone"] == "595981123456"
    assert r.json()["ordering_enabled"] is True

    r2 = client.get("/api/settings/shop-whatsapp")
    assert r2.json()["phone"] == "595981123456"

    r3 = client.post("/api/settings/shop-whatsapp", json={"phone": ""})
    assert r3.json()["ordering_enabled"] is False
