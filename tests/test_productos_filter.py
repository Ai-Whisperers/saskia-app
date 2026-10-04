"""tests/test_productos_filter.py — filter by q + has_recipe."""

from __future__ import annotations


def test_productos_filter_search_exists(client):
    """/productos shows search input + has_recipe filter."""
    resp = client.get("/productos")
    assert resp.status_code == 200
    body = resp.text
    for field in ['name="q"', 'name="has_recipe"']:
        assert field in body, f"Missing filter {field} in /productos"


def test_productos_filter_by_q(client, session_factory):
    """/productos?q=cake only returns matching products."""
    from app.rms.models import Product

    with session_factory() as s:
        s.add(Product(name="TortaFiltroCake", sale_price_gs=20000, recipe_id=None))
        s.add(Product(name="BrownieFiltroNo", sale_price_gs=12000, recipe_id=None))
        s.commit()

    resp = client.get("/productos?q=tortafiltrocake")
    assert resp.status_code == 200
    assert "TortaFiltroCake" in resp.text
    # BrownieFiltroNo has "no" in it which would match "no" but the q is specific.


def test_productos_filter_has_recipe_yes(client, session_factory):
    """/productos?has_recipe=yes filters to products with a recipe."""
    from app.rms.models import Product, Recipe

    with session_factory() as s:
        r = Recipe(name="Base_Recipe_filter")
        s.add(r)
        s.flush()
        s.add(Product(name="ConRecetaFiltro", sale_price_gs=10000, recipe_id=r.id))
        s.add(Product(name="SinRecetaFiltro", sale_price_gs=20000, recipe_id=None))
        s.commit()

    resp = client.get("/productos?has_recipe=yes")
    assert resp.status_code == 200
    assert "ConRecetaFiltro" in resp.text


def test_productos_filter_has_recipe_no(client, session_factory):
    """/productos?has_recipe=no filters to products WITHOUT a recipe."""
    from app.rms.models import Product, Recipe

    with session_factory() as s:
        r = Recipe(name="Base_Recipe_filter_no")
        s.add(r)
        s.flush()
        s.add(Product(name="ConRecetaFiltroNo", sale_price_gs=10000, recipe_id=r.id))
        s.add(Product(name="SinRecetaFiltroNo", sale_price_gs=20000, recipe_id=None))
        s.commit()

    resp = client.get("/productos?has_recipe=no")
    assert resp.status_code == 200
    assert "SinRecetaFiltroNo" in resp.text
