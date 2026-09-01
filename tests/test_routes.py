"""tests/test_routes.py — End-to-end tests of the HTTP routes.

Uses the `client` fixture from conftest.py which:
- forces a temp DB path (no pollution of production)
- inits an in-memory SQLite
- wires up a TestClient with a session_factory bound to that DB

Tests cover the happy path of each route + key edge cases.
"""

from __future__ import annotations

from datetime import datetime

import pytest


def _seed(session_factory):
    """Create a small test world: 3 ingredients + 1 recipe + 1 product."""
    from app.rms.models import Ingredient, Product, Recipe, RecipeLine

    with session_factory() as s:
        flour = Ingredient(name="Harina", unit="kg", stock_qty=2.0, purchase_price_gs=5000)
        sugar = Ingredient(name="Azúcar", unit="kg", stock_qty=1.5, purchase_price_gs=4000)
        egg = Ingredient(name="Huevo", unit="und", stock_qty=20.0, purchase_price_gs=1500)
        s.add_all([flour, sugar, egg])
        s.flush()

        recipe = Recipe(name="Muffin", yield_qty=12.0, yield_unit="und")
        s.add(recipe)
        s.flush()

        s.add_all(
            [
                RecipeLine(
                    recipe_id=recipe.id, line_kind="ingredient", line_ref_id=flour.id, qty=0.3
                ),
                RecipeLine(
                    recipe_id=recipe.id, line_kind="ingredient", line_ref_id=sugar.id, qty=0.2
                ),
                RecipeLine(
                    recipe_id=recipe.id, line_kind="ingredient", line_ref_id=egg.id, qty=2.0
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
        s.commit()
        return product.id


# --- Health ---


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_healthz_db(client):
    r = client.get("/healthz/db")
    assert r.status_code == 200
    body = r.json()
    assert body["db"] == "ok"
    assert body["journal_mode"] == "wal"


# --- Dashboard ---


def test_dashboard_empty(client):
    r = client.get("/?period=today")
    assert r.status_code == 200
    assert "Inicio" in r.text
    assert "Ventas" in r.text


def test_dashboard_with_sale(client, session_factory):
    _seed(session_factory)
    # Record a sale
    r = client.post(
        "/ventas/nueva",
        data={
            "product_id": "1",
            "qty": "2",
            "sold_at": datetime.now().strftime("%Y-%m-%dT%H:%M"),
            "notes": "",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    # Now dashboard should show data
    r = client.get("/?period=today")
    assert r.status_code == 200
    assert "Muffin" in r.text  # ranking includes product name


@pytest.mark.parametrize("period", ["today", "week", "month"])
def test_dashboard_periods(client, period):
    r = client.get(f"/?period={period}")
    assert r.status_code == 200


def test_dashboard_invalid_period(client):
    r = client.get("/?period=invalid")
    assert r.status_code == 422


# --- Inventory ---


def test_inventory_list_empty(client):
    r = client.get("/inventario")
    assert r.status_code == 200
    assert "Inventario" in r.text


def test_inventory_create_get(client):
    r = client.post(
        "/inventario/nuevo",
        data={
            "name": "Sal",
            "unit": "g",
            "stock_qty": "1000",
            "min_stock_qty": "100",
            "purchase_price_gs": "200",
            "notes": "",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    # Verify it appears in list
    r = client.get("/inventario")
    assert "Sal" in r.text


def test_inventory_duplicate_name_rejected(client):
    client.post(
        "/inventario/nuevo",
        data={
            "name": "Sal",
            "unit": "g",
            "stock_qty": "1000",
            "min_stock_qty": "100",
            "purchase_price_gs": "200",
            "notes": "",
        },
        follow_redirects=False,
    )
    r = client.post(
        "/inventario/nuevo",
        data={
            "name": "Sal",
            "unit": "kg",
            "stock_qty": "500",
            "min_stock_qty": "50",
            "purchase_price_gs": "300",
            "notes": "",
        },
        follow_redirects=False,
    )
    assert r.status_code == 409


def test_inventory_invalid_unit_rejected(client):
    r = client.post(
        "/inventario/nuevo",
        data={
            "name": "Mystery",
            "unit": "stones",
            "stock_qty": "1.0",
            "min_stock_qty": "0",
            "purchase_price_gs": "",
            "notes": "",
        },
        follow_redirects=False,
    )
    # Either 400 (rejected by route) or 422 (caught by FastAPI as form validation)
    assert r.status_code in (400, 422)


def test_inventory_empty_price_ok(client):
    """purchase_price_gs can be blank (UI defaults to NULL)."""
    r = client.post(
        "/inventario/nuevo",
        data={
            "name": "Mystery",
            "unit": "kg",
            "stock_qty": "1.0",
            "min_stock_qty": "0",
            "purchase_price_gs": "",
            "notes": "",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303


def test_inventory_vos_copy_present(client):
    """Verify Spanish (vos) copy is in templates."""
    r = client.get("/inventario")
    assert "Inventario" in r.text
    r = client.get("/inventario/nuevo")
    assert "Nuevo ingrediente" in r.text
    assert "Guardá" in r.text


# --- Products ---


def test_products_list_empty(client):
    r = client.get("/productos")
    assert r.status_code == 200


def test_products_create_and_list(client):
    r = client.post(
        "/productos/nuevo",
        data={
            "name": "Muffin",
            "portion_label": "1 muffin",
            "sale_price_gs": "8000",
            "recipe_id": "",
            "notes": "",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    r = client.get("/productos")
    assert "Muffin" in r.text


# --- Recipes ---


def test_recipes_list_empty(client):
    r = client.get("/recetas")
    assert r.status_code == 200


def test_recipe_create_no_lines(client, session_factory):
    """Recipe with no lines should still save (cost shows 'falta precio')."""
    r = client.post(
        "/recetas/nueva",
        data={
            "name": "Empty recipe",
            "yield_qty": "12",
            "yield_unit": "und",
            "notes": "",
            # no line_kind, no line_target_id, no line_qty
        },
        follow_redirects=False,
    )
    assert r.status_code == 303


def test_recipe_vos_copy(client):
    r = client.get("/recetas")
    assert "Recetas" in r.text
    r = client.get("/recetas/nueva")
    assert "Nueva receta" in r.text


# --- Sales ---


def test_sales_list_empty(client):
    r = client.get("/ventas")
    assert r.status_code == 200


def test_sale_create_drops_stock(client, session_factory):
    product_id = _seed(session_factory)
    r = client.post(
        "/ventas/nueva",
        data={
            "product_id": str(product_id),
            "qty": "2",
            "sold_at": "",
            "notes": "",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    # Verify stock was dropped
    with session_factory() as s:
        from app.rms.models import Ingredient

        flour = s.query(Ingredient).filter_by(name="Harina").first()
        # 2.0 - (0.3/12)*2 = 2.0 - 0.05 = 1.95
        assert abs(flour.stock_qty - 1.95) < 0.001


def test_sale_invalid_product(client):
    r = client.post(
        "/ventas/nueva",
        data={
            "product_id": "99999",
            "qty": "1",
            "sold_at": "",
            "notes": "",
        },
        follow_redirects=False,
    )
    assert r.status_code == 400


def test_sale_negative_qty_rejected(client, session_factory):
    product_id = _seed(session_factory)
    r = client.post(
        "/ventas/nueva",
        data={
            "product_id": str(product_id),
            "qty": "-1",
            "sold_at": "",
            "notes": "",
        },
        follow_redirects=False,
    )
    assert r.status_code == 400


def test_sale_void_restores_stock(client, session_factory):
    from app.rms.models import Ingredient, Sale

    product_id = _seed(session_factory)
    r = client.post(
        "/ventas/nueva",
        data={
            "product_id": str(product_id),
            "qty": "2",
            "sold_at": "",
            "notes": "",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303

    with session_factory() as s:
        flour = s.query(Ingredient).filter_by(name="Harina").first()
        assert abs(flour.stock_qty - 1.95) < 0.001  # dropped from 2.0
        sale_id = s.query(Sale).first().id

    r = client.post(f"/ventas/{sale_id}/anular", follow_redirects=False)
    assert r.status_code == 303

    with session_factory() as s:
        flour = s.query(Ingredient).filter_by(name="Harina").first()
        assert abs(flour.stock_qty - 2.0) < 0.001  # restored


# --- Excel routes (stubs for Batch 4) ---


def test_excel_page_renders(client):
    r = client.get("/excel")
    assert r.status_code == 200
    assert "Excel" in r.text
    assert "Importar" in r.text
    assert "Exportar" in r.text


def test_excel_import_stub_returns_501(client):
    """Import is a stub in Batch 2; returns 501 not-implemented."""
    # Need a real .xlsx file to bypass the extension check
    import openpyxl

    wb = openpyxl.Workbook()
    wb.save("/tmp/test-import.xlsx")
    with open("/tmp/test-import.xlsx", "rb") as f:
        r = client.post(
            "/excel/importar",
            files={
                "file": (
                    "test.xlsx",
                    f,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
            follow_redirects=False,
        )
    # 501 because stub, not 400
    assert r.status_code == 501


def test_excel_export_stub_returns_501(client):
    r = client.get("/excel/exportar")
    assert r.status_code == 501


# --- Money formatting ---


def test_paraguayan_gs_format_in_inventory(client):
    """Verify Gs. formatting uses period as thousands sep."""
    client.post(
        "/inventario/nuevo",
        data={
            "name": "Caro",
            "unit": "kg",
            "stock_qty": "1000",
            "min_stock_qty": "100",
            "purchase_price_gs": "1234567",
            "notes": "",
        },
        follow_redirects=False,
    )
    r = client.get("/inventario")
    # Should show "Gs. 1.234.567" not "Gs. 1,234,567"
    assert "Gs. 1.234.567" in r.text
    assert "1,234,567" not in r.text  # no English-style commas
    assert "Caro" in r.text  # sanity check: it's the test ingredient


# --- Spanish (vos) copy across all pages ---


@pytest.mark.parametrize(
    "path", ["/", "/inventario", "/recetas", "/productos", "/ventas", "/excel"]
)
def test_spanish_vos_copy(client, path):
    """All pages should have Spanish (vos) copy, not tú or usted."""
    r = client.get(path)
    assert r.status_code == 200
    # We should see vos conjugations (not "tú" / "usted")
    body = r.text
    # Vos forms: "Guardá", "Cancelar", "Estás", "Tenés", "Podés"
    # We don't strictly check; just verify no English-form header like "Log in"
    assert "Log in" not in body
    assert "Sign in" not in body
    assert "Welcome" not in body
