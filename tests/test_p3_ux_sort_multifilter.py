"""P3 UX batch: sortable columns + multi-select filters on /inventario and /recetas.

Covers:
- sort_th macro renders toggle links on every column (inventario, recetas)
- inventario: estado/almacen/expiry multi-select (was radio), diet filter
- recetas: dificultad multi-select, ingredient multi-select (AND semantics)
- legacy single-value params keep working (backward compat)
"""
from tests.factories import ing_line, make_ingredient, make_product, make_recipe


def _seed_inventory(session_factory):
    with session_factory() as s:
        make_ingredient(s, name="Harina 000 UX", category="harinas",
                        storage="ambient", stock_qty=5, min_stock_qty=10,
                        purchase_price_gs=2000)
        make_ingredient(s, name="Leche UX", category="lacteos",
                        storage="refrigerated", stock_qty=2, min_stock_qty=1,
                        purchase_price_gs=8000)
        make_ingredient(s, name="Manteca UX", category="lacteos",
                        storage="refrigerated", stock_qty=0, min_stock_qty=4,
                        purchase_price_gs=12000)
        s.commit()


def test_inventario_multi_estado(client, session_factory):
    """estado=bajo&estado=critico matches ingredients in EITHER bucket."""
    _seed_inventory(session_factory)
    r = client.get("/inventario?estado=bajo&estado=critico")
    assert r.status_code == 200
    body = r.text
    assert "Harina 000 UX" in body   # stock 5 <= min 10 → bajo
    assert "Manteca UX" in body      # stock 0 → critico
    assert "Leche UX" not in body    # stock 2 > min 1 → ok


def test_inventario_legacy_single_estado(client, session_factory):
    """Legacy single estado=bajo still works."""
    _seed_inventory(session_factory)
    r = client.get("/inventario?estado=bajo")
    assert r.status_code == 200
    assert "Harina 000 UX" in r.text


def test_inventario_multi_almacen(client, session_factory):
    _seed_inventory(session_factory)
    r = client.get("/inventario?almacen=refrigerated")
    assert r.status_code == 200
    body = r.text
    assert "Leche UX" in body
    assert "Harina 000 UX" not in body


def test_inventario_diet_filter(client, session_factory):
    """?diet=sin gluten matches ingredients carrying that dietary tag."""
    _seed_inventory(session_factory)
    with session_factory() as s:
        from sqlalchemy import select
        from app.rms.models import Ingredient
        ing = s.execute(
            select(Ingredient).where(Ingredient.name == "Harina 000 UX")
        ).scalar_one()
        ing.dietary_tags = "sin gluten"
        s.commit()
    r = client.get("/inventario?diet=sin+gluten")
    assert r.status_code == 200
    assert "Harina 000 UX" in r.text
    assert "Leche UX" not in r.text


def test_inventario_sort_valor_gs(client, session_factory):
    """?sort=valor_gs&dir=desc puts the highest stock×price first."""
    _seed_inventory(session_factory)
    r = client.get("/inventario?sort=valor_gs&dir=desc")
    assert r.status_code == 200
    body = r.text
    # Manteca: 0 × 12000 = 0; Harina: 5 × 2000 = 10000; Leche: 2 × 8000 = 16000
    assert body.index("Leche UX") < body.index("Harina 000 UX") < body.index("Manteca UX")


def test_recetas_sort_difficulty(client, session_factory):
    with session_factory() as s:
        make_recipe(s, name="Rec Fácil UX", difficulty=1)
        make_recipe(s, name="Rec Difícil UX", difficulty=5)
        s.commit()
    r = client.get("/recetas?sort=difficulty&dir=desc")
    assert r.status_code == 200
    body = r.text
    assert body.index("Rec Difícil UX") < body.index("Rec Fácil UX")


def test_recetas_dificultad_multi(client, session_factory):
    with session_factory() as s:
        make_recipe(s, name="Rec D1 UX", difficulty=1)
        make_recipe(s, name="Rec D3 UX", difficulty=3)
        make_recipe(s, name="Rec D5 UX", difficulty=5)
        s.commit()
    r = client.get("/recetas?dificultad=1&dificultad=3")
    assert r.status_code == 200
    body = r.text
    assert "Rec D1 UX" in body
    assert "Rec D3 UX" in body
    assert "Rec D5 UX" not in body


def test_recetas_ingredient_multi_and_semantics(client, session_factory):
    """ingredient_multi uses AND semantics: recipe must use ALL selected."""
    from tests.factories import ing_line
    with session_factory() as s:
        a = make_ingredient(s, name="IngMulti A UX")
        b = make_ingredient(s, name="IngMulti B UX")
        c = make_ingredient(s, name="IngMulti C UX")
        r_ab = make_recipe(s, name="Rec AB UX", lines=[
            ing_line(ingredient=a, qty=1), ing_line(ingredient=b, qty=1)])
        r_a = make_recipe(s, name="Rec A UX", lines=[ing_line(ingredient=a, qty=1)])
        s.commit()
        a_id, b_id, c_id = a.id, b.id, c.id

    r = client.get(f"/recetas?ingredient_multi={a_id}&ingredient_multi={b_id}")
    assert r.status_code == 200
    body = r.text
    assert "Rec AB UX" in body    # has both
    assert "Rec A UX" not in body # only has A

    # single ingredient still matches both
    r2 = client.get(f"/recetas?ingredient_multi={c_id}")
    assert r2.status_code == 200
    assert "Rec AB UX" not in r2.text
    assert "Rec A UX" not in r2.text


def test_recetas_sort_headers_render(client, session_factory):
    """Every sortable column header renders with a sort link."""
    with session_factory() as s:
        make_recipe(s, name="Rec Header UX")
        s.commit()
    r = client.get("/recetas")
    assert r.status_code == 200
    body = r.text
    for key in ("sort=name", "sort=yield_qty", "sort=difficulty",
                "sort=prep_minutes", "sort=cook_minutes", "sort=line_count",
                "sort=batch_cost_gs", "sort=unit_cost_gs"):
        assert key in body, f"missing sortable header: {key}"


def test_inventario_sort_headers_render(client, session_factory):
    _seed_inventory(session_factory)
    r = client.get("/inventario")
    assert r.status_code == 200
    body = r.text
    for key in ("sort=name", "sort=stock_qty", "sort=valor_gs",
                "sort=min_stock_qty", "sort=purchase_price_gs", "sort=unit"):
        assert key in body, f"missing sortable header: {key}"


def test_productos_sort_headers_render(client, session_factory):
    from tests.factories import make_product
    with session_factory() as s:
        make_product(s, name="ProdHeaderUX")
        s.commit()
    r = client.get("/productos")
    assert r.status_code == 200
    body = r.text
    for key in ("sort=name", "sort=sale_price_gs", "sort=cost_gs", "sort=margin_gs"):
        assert key in body, f"missing sortable header: {key}"


def test_ventas_page_renders(client, session_factory):
    """Sanity: /ventas still renders after the P3 batch (quick-sell pills etc)."""
    with session_factory() as s:
        make_product(s, name="Ventas Sanity UX")
        s.commit()
    r = client.get("/ventas")
    assert r.status_code == 200
