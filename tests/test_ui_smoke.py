"""tests/test_ui_smoke.py — UI smoke tests for all routes.

Per dev plan Batch 7 (lightweight approach): TestClient hits each route,
checks status code, Spanish copy, and money formatting.

Plus targeted tests for the POST form handlers (inventory, recipes,
products, sales) which are the gap between 78% and 80% coverage.

What we cover:
- All GET routes return 200 with Spanish (vos) copy
- Money formatting renders with Gs. N.NNN.NNN pattern
- All POST create handlers work end-to-end
- POST handlers validate input (return 400 on bad data)
- POST handlers return 409 on uniqueness conflicts
- POST handlers return 404 on missing entity
- DELETE handlers work + block FK usage

Why this matters: the per-router form POST handlers had only one happy-path
test each. The validation/conflict/404 paths were untested, which is why
inventory.py/products.py/recipes.py were at ~50% coverage.
"""

from __future__ import annotations

from datetime import datetime

import pytest

# --- Helpers ---


def _seed_min_catalog(session_factory):
    """2 ingredients, 1 recipe, 1 product, 1 sale."""
    from app.rms.models import Ingredient, Product, Recipe, RecipeLine, Sale

    with session_factory() as s:
        flour = Ingredient(
            name="Harina",
            unit="kg",
            stock_qty=2.0,
            purchase_price_gs=5000,
            min_stock_qty=1.0,
        )
        egg = Ingredient(
            name="Huevo",
            unit="und",
            stock_qty=20.0,
            purchase_price_gs=1500,
            min_stock_qty=0.0,
        )
        s.add_all([flour, egg])
        s.flush()

        recipe = Recipe(name="Muffin", yield_qty=12.0, yield_unit="und")
        s.add(recipe)
        s.flush()

        s.add_all(
            [
                RecipeLine(
                    recipe_id=recipe.id,
                    line_kind="ingredient",
                    line_ref_id=flour.id,
                    qty=0.3,
                ),
                RecipeLine(
                    recipe_id=recipe.id,
                    line_kind="ingredient",
                    line_ref_id=egg.id,
                    qty=2.0,
                ),
            ]
        )
        s.flush()

        product = Product(
            name="Muffin",
            portion_label="1 muffin",
            sale_price_gs=8000,
            recipe_id=recipe.id,
        )
        s.add(product)
        s.flush()

        sale = Sale(
            sold_at=datetime.now(),
            product_id=product.id,
            qty=2.0,
            unit_price_gs=8000,
        )
        s.add(sale)
        s.commit()
        return flour.id, egg.id, recipe.id, product.id, sale.id


# --- Spanish (vos) copy on every page ---


@pytest.mark.parametrize(
    "path", ["/", "/inventario", "/recetas", "/productos", "/ventas", "/excel"]
)
def test_every_page_returns_200(client, path):
    """All primary routes return 200."""
    r = client.get(path)
    assert r.status_code == 200, f"{path} returned {r.status_code}"


@pytest.mark.parametrize(
    "path", ["/", "/inventario", "/recetas", "/productos", "/ventas", "/excel"]
)
def test_every_page_uses_spanish_copy(client, path):
    """No English-form chrome on any page."""
    r = client.get(path)
    body = r.text
    assert "Log in" not in body
    assert "Sign in" not in body
    assert "Welcome" not in body


# --- Money formatting ---


def test_money_format_in_inventory_page(client, session_factory):
    """Inventory page renders Gs. N.NNN.NNN for prices."""
    from app.rms.models import Ingredient

    with session_factory() as s:
        s.add(
            Ingredient(
                name="Caro",
                unit="kg",
                stock_qty=1.0,
                purchase_price_gs=17500000,
            )
        )
        s.commit()

    r = client.get("/inventario")
    assert "Gs. 17.500.000" in r.text


def test_money_format_in_products_page(client, session_factory):
    """Products page renders Gs. formatting for sale prices."""
    from app.rms.models import Product, Recipe

    with session_factory() as s:
        rec = Recipe(name="R", yield_qty=10.0, yield_unit="und")
        s.add(rec)
        s.flush()
        s.add(
            Product(
                name="Top",
                portion_label="1",
                sale_price_gs=1234567,
                recipe_id=rec.id,
            )
        )
        s.commit()

    r = client.get("/productos")
    assert "Gs. 1.234.567" in r.text


# --- Inventory POST handlers ---


def test_inventory_create_success(client, session_factory):
    """POST /inventario/nuevo with valid data → 303 + row appears."""
    from app.rms.models import Ingredient

    r = client.post(
        "/inventario/nuevo",
        data={
            "name": "Manteca",
            "unit": "kg",
            "stock_qty": "1.5",
            "min_stock_qty": "0.5",
            "purchase_price_gs": "12000",
            "notes": "",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303

    with session_factory() as s:
        ing = s.query(Ingredient).filter_by(name="Manteca").one()
        assert ing.unit == "kg"
        assert ing.stock_qty == 1.5
        assert ing.purchase_price_gs == 12000


def test_inventory_create_duplicate_name_returns_409(client, session_factory):
    """Duplicate ingredient name → 409."""
    from app.rms.models import Ingredient

    with session_factory() as s:
        s.add(Ingredient(name="Duplicado", unit="kg", stock_qty=1.0))
        s.commit()

    r = client.post(
        "/inventario/nuevo",
        data={
            "name": "Duplicado",
            "unit": "kg",
            "stock_qty": "1.0",
            "min_stock_qty": "0",
            "purchase_price_gs": "",
            "notes": "",
        },
    )
    assert r.status_code == 409


def test_inventory_create_bad_unit_returns_400(client):
    """Invalid unit → 400."""
    r = client.post(
        "/inventario/nuevo",
        data={
            "name": "Malo",
            "unit": "stones",
            "stock_qty": "1.0",
            "min_stock_qty": "0",
            "purchase_price_gs": "",
            "notes": "",
        },
    )
    assert r.status_code == 400


def test_inventory_create_negative_stock_returns_400(client):
    """Negative stock_qty → 400."""
    r = client.post(
        "/inventario/nuevo",
        data={
            "name": "Negativo",
            "unit": "kg",
            "stock_qty": "-1.0",
            "min_stock_qty": "0",
            "purchase_price_gs": "",
            "notes": "",
        },
    )
    assert r.status_code == 400


def test_inventory_create_bad_price_returns_400(client):
    """Malformed price → 400."""
    r = client.post(
        "/inventario/nuevo",
        data={
            "name": "Malo",
            "unit": "kg",
            "stock_qty": "1.0",
            "min_stock_qty": "0",
            "purchase_price_gs": "abc",
            "notes": "",
        },
    )
    assert r.status_code == 400


def test_inventory_edit_success(client, session_factory):
    """POST /inventario/{id}/editar updates the row."""
    from app.rms.models import Ingredient

    with session_factory() as s:
        ing = Ingredient(name="Viejo", unit="kg", stock_qty=1.0)
        s.add(ing)
        s.commit()
        ing_id = ing.id

    r = client.post(
        f"/inventario/{ing_id}/editar",
        data={
            "name": "Nuevo",
            "unit": "kg",
            "stock_qty": "2.5",
            "min_stock_qty": "0.5",
            "purchase_price_gs": "5000",
            "notes": "editado",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303

    with session_factory() as s:
        ing = s.get(Ingredient, ing_id)
        assert ing.name == "Nuevo"
        assert ing.stock_qty == 2.5


def test_inventory_edit_missing_returns_404(client):
    """Editing a non-existent ingredient → 404."""
    r = client.post(
        "/inventario/99999/editar",
        data={
            "name": "X",
            "unit": "kg",
            "stock_qty": "1.0",
            "min_stock_qty": "0",
            "purchase_price_gs": "",
            "notes": "",
        },
    )
    assert r.status_code == 404


def test_inventory_delete_unused_succeeds(client, session_factory):
    """Deleting an ingredient with no recipe usage → 303."""
    from app.rms.models import Ingredient

    with session_factory() as s:
        ing = Ingredient(name="Basura", unit="kg", stock_qty=1.0)
        s.add(ing)
        s.commit()
        ing_id = ing.id

    r = client.post(f"/inventario/{ing_id}/eliminar", follow_redirects=False)
    assert r.status_code == 303

    with session_factory() as s:
        assert s.get(Ingredient, ing_id) is None


def test_inventory_delete_used_in_recipe_returns_409(client, session_factory):
    """Deleting an ingredient that's in a recipe → 409 (FK block)."""
    flour_id, _, _, _, _ = _seed_min_catalog(session_factory)
    r = client.post(f"/inventario/{flour_id}/eliminar")
    assert r.status_code == 409


def test_inventory_delete_missing_returns_404(client):
    """Deleting a non-existent ingredient → 404."""
    r = client.post("/inventario/99999/eliminar")
    assert r.status_code == 404


# --- Recipes POST handlers ---


def test_recipes_list_renders_recipes(client, session_factory):
    """GET /recetas shows seeded recipes."""
    _seed_min_catalog(session_factory)
    r = client.get("/recetas")
    assert r.status_code == 200
    assert "Muffin" in r.text


def test_recipe_create_success(client, session_factory):
    """POST /recetas/nueva with valid data → 303."""
    from app.rms.models import Recipe

    flour_id, _, _, _, _ = _seed_min_catalog(session_factory)
    r = client.post(
        "/recetas/nueva",
        data={
            "name": "Torta",
            "yield_qty": "10",
            "yield_unit": "und",
            "notes": "",
            "lines-0-line_kind": "ingredient",
            "lines-0-line_ref_id": str(flour_id),
            "lines-0-qty": "1.0",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303

    with session_factory() as s:
        rec = s.query(Recipe).filter_by(name="Torta").one()
        assert rec.yield_qty == 10.0


def test_recipe_create_duplicate_returns_409(client, session_factory):
    """Duplicate recipe name → 409."""
    from app.rms.models import Recipe

    with session_factory() as s:
        s.add(Recipe(name="Dup", yield_qty=10.0, yield_unit="und"))
        s.commit()

    r = client.post(
        "/recetas/nueva",
        data={
            "name": "Dup",
            "yield_qty": "10",
            "yield_unit": "und",
            "notes": "",
        },
    )
    assert r.status_code == 409


def test_recipe_create_bad_unit_returns_400(client):
    """Invalid yield_unit → 400."""
    r = client.post(
        "/recetas/nueva",
        data={
            "name": "X",
            "yield_qty": "10",
            "yield_unit": "stones",
            "notes": "",
        },
    )
    assert r.status_code == 400


def test_recipe_edit_missing_returns_404(client):
    """Editing non-existent recipe → 404."""
    r = client.post(
        "/recetas/99999/editar",
        data={
            "name": "X",
            "yield_qty": "10",
            "yield_unit": "und",
            "notes": "",
        },
    )
    assert r.status_code == 404


def test_recipe_delete_not_implemented(client, session_factory):
    """Recipe delete endpoint doesn't exist (Fase 1 scope). 404 expected."""
    from app.rms.models import Recipe

    with session_factory() as s:
        rec = Recipe(name="Basura", yield_qty=10.0, yield_unit="und")
        s.add(rec)
        s.commit()
        rec_id = rec.id

    r = client.post(f"/recetas/{rec_id}/eliminar", follow_redirects=False)
    # 404: no /eliminar route on the recipes router
    assert r.status_code == 404


def test_recipe_delete_missing_returns_404(client):
    """Same: no /eliminar route at all → 404."""
    r = client.post("/recetas/99999/eliminar")
    assert r.status_code == 404


# --- Products POST handlers ---


def test_products_list_renders_products(client, session_factory):
    """GET /productos shows seeded products."""
    _seed_min_catalog(session_factory)
    r = client.get("/productos")
    assert r.status_code == 200
    assert "Muffin" in r.text


def test_product_create_success(client, session_factory):
    """POST /productos/nuevo with valid data → 303."""
    from app.rms.models import Product

    _, _, _, _, _ = _seed_min_catalog(session_factory)
    r = client.post(
        "/productos/nuevo",
        data={
            "name": "TortaProducto",
            "portion_label": "1 torta",
            "sale_price_gs": "25000",
            "recipe_id": "",
            "notes": "",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303

    with session_factory() as s:
        prod = s.query(Product).filter_by(name="TortaProducto").one()
        assert prod.sale_price_gs == 25000
        assert prod.recipe_id is None


def test_product_create_duplicate_returns_409(client, session_factory):
    """Duplicate product name → 409."""
    from app.rms.models import Product

    with session_factory() as s:
        s.add(
            Product(
                name="Dup",
                portion_label="1",
                sale_price_gs=1000,
            )
        )
        s.commit()

    r = client.post(
        "/productos/nuevo",
        data={
            "name": "Dup",
            "portion_label": "1",
            "sale_price_gs": "1000",
            "recipe_id": "",
            "notes": "",
        },
    )
    assert r.status_code == 409


def test_product_edit_missing_returns_404(client):
    """Editing non-existent product → 404."""
    r = client.post(
        "/productos/99999/editar",
        data={
            "name": "X",
            "portion_label": "1",
            "sale_price_gs": "1000",
            "recipe_id": "",
            "notes": "",
        },
    )
    assert r.status_code == 404


def test_product_delete_succeeds(client, session_factory):
    """Deleting a product with no sales → 303."""
    from app.rms.models import Product

    with session_factory() as s:
        prod = Product(
            name="Basura",
            portion_label="1",
            sale_price_gs=1000,
        )
        s.add(prod)
        s.commit()
        prod_id = prod.id

    r = client.post(f"/productos/{prod_id}/eliminar", follow_redirects=False)
    assert r.status_code == 303


def test_product_delete_missing_returns_404(client):
    """Deleting non-existent product → 404."""
    r = client.post("/productos/99999/eliminar")
    assert r.status_code == 404


# --- Sales POST handlers ---


def test_sales_list_renders_sales(client, session_factory):
    """GET /ventas shows the new-sale form + sales history table."""
    _seed_min_catalog(session_factory)
    r = client.get("/ventas")
    assert r.status_code == 200
    # Spanish chrome
    assert "Historial" in r.text
    assert "Nueva venta" in r.text


def test_sale_create_form_renders(client, session_factory):
    """POST /ventas/nueva exists; GET also returns 200 (the form is on /ventas)."""
    _seed_min_catalog(session_factory)
    # The form lives on /ventas, not /ventas/nueva. /ventas/nueva is POST-only.
    r_get = client.get("/ventas")
    assert r_get.status_code == 200
    # POST to an empty form is allowed (will return 400 because no product)
    r_post = client.post(
        "/ventas/nueva",
        data={
            "product_id": "",
            "qty": "1",
            "sold_at": "",
            "notes": "",
        },
    )
    assert r_post.status_code == 400  # bad product_id


def test_sale_create_success(client, session_factory):
    """POST /ventas/nueva with valid data → 303 + sale exists."""
    from app.rms.models import Sale

    _, _, _, product_id, _ = _seed_min_catalog(session_factory)
    r = client.post(
        "/ventas/nueva",
        data={
            "product_id": str(product_id),
            "qty": "1.5",
            "sold_at": datetime.now().strftime("%Y-%m-%dT%H:%M"),
            "notes": "",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303

    with session_factory() as s:
        sales = s.query(Sale).all()
        # 1 seeded + 1 new = 2
        assert len(sales) == 2
        new = [x for x in sales if x.qty == 1.5][0]
        assert new.product_id == product_id


def test_sale_create_zero_qty_returns_400(client, session_factory):
    """qty=0 → 400."""
    _, _, _, product_id, _ = _seed_min_catalog(session_factory)
    r = client.post(
        "/ventas/nueva",
        data={
            "product_id": str(product_id),
            "qty": "0",
            "sold_at": "",
            "notes": "",
        },
    )
    assert r.status_code == 400


def test_sale_create_negative_qty_returns_400(client, session_factory):
    """qty=-1 → 400."""
    _, _, _, product_id, _ = _seed_min_catalog(session_factory)
    r = client.post(
        "/ventas/nueva",
        data={
            "product_id": str(product_id),
            "qty": "-1",
            "sold_at": "",
            "notes": "",
        },
    )
    assert r.status_code == 400


def test_sale_create_unknown_product_returns_400(client, session_factory):
    """Unknown product_id → 400."""
    _seed_min_catalog(session_factory)
    r = client.post(
        "/ventas/nueva",
        data={
            "product_id": "99999",
            "qty": "1",
            "sold_at": "",
            "notes": "",
        },
    )
    assert r.status_code == 400


def test_sale_void_success(client, session_factory):
    """POST /ventas/{id}/anular → 303 + voided_at set."""
    from app.rms.models import Sale

    _, _, _, _, sale_id = _seed_min_catalog(session_factory)
    r = client.post(f"/ventas/{sale_id}/anular", follow_redirects=False)
    assert r.status_code == 303

    with session_factory() as s:
        sale = s.get(Sale, sale_id)
        assert sale.voided_at is not None


def test_sale_void_double_void_returns_409(client, session_factory):
    """Voiding twice → 409 Conflict (already voided)."""

    _, _, _, _, sale_id = _seed_min_catalog(session_factory)
    # First void: OK
    client.post(f"/ventas/{sale_id}/anular")
    # Second void: 409
    r = client.post(f"/ventas/{sale_id}/anular")
    assert r.status_code == 409


def test_sale_void_unknown_returns_409(client):
    """Voiding non-existent sale → 409 Conflict (router uses 409 for state errors)."""
    r = client.post("/ventas/99999/anular")
    assert r.status_code == 409


# --- Excel page ---


def test_excel_page_renders(client, session_factory):
    """GET /excel returns 200 + Spanish chrome (Importar / Exportar buttons)."""
    r = client.get("/excel")
    assert r.status_code == 200
    assert "Importar" in r.text
    assert "Exportar" in r.text


def test_footer_renders_year_not_function_repr(client):
    """Footer renders the current year, NOT the function's repr.

    Regression for the bug found via screenshot exercise: `{{ now_year }}`
    in the template printed `<function _now_year at 0x...>` because
    Jinja2 doesn't auto-call globals. Fixed by using `{{ now_year() }}`.
    """
    from datetime import datetime

    r = client.get("/")
    assert r.status_code == 200
    current_year = str(datetime.now().year)
    assert current_year in r.text
    # The function repr must NOT appear
    assert "<function _now_year" not in r.text
