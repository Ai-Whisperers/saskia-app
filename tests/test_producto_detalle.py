"""Tests for the customer product detail page."""


from app.rms.models import Product, Recipe, RecipeLine


def test_detalle_returns_200(authed_client, session_factory):
    """GET /productos/{valid_id} returns 200"""
    # Create test data
    with session_factory() as s:
        product = Product(name="Producto Test", sale_price_gs=5000)
        s.add(product)
        s.commit()
        product_id = product.id

    response = authed_client.get(f"/productos/{product_id}")
    assert response.status_code == 200
    assert "Producto Test" in response.text


def test_detalle_404_for_missing(authed_client):
    """GET /productos/999999 returns 404"""
    response = authed_client.get("/productos/999999")
    assert response.status_code == 404
    assert response.status_code == 404


def test_detalle_shows_product_name(authed_client, session_factory):
    """Response contains the product's name"""
    product_name = "Pan con Queso Test"
    with session_factory() as s:
        product = Product(name=product_name, sale_price_gs=3000)
        s.add(product)
        s.commit()
        product_id = product.id

    response = authed_client.get(f"/productos/{product_id}")
    assert product_name in response.text


def test_detalle_shows_current_stock(authed_client, session_factory):
    """Response contains the stock value (formatted)"""
    with session_factory() as s:
        from app.rms.models import Ingredient, Recipe
        ingredient = Ingredient(name="Pan Test", unit="und", stock_qty=10.5)
        s.add(ingredient)

        # Create a recipe first to satisfy foreign key constraint
        recipe = Recipe(name="Receta Test", yield_qty=12.0)
        s.add(recipe)
        s.commit()

        product = Product(name="Pan Test", sale_price_gs=2500, recipe_id=recipe.id)
        s.add(product)
        s.commit()
        product_id = product.id

    response = authed_client.get(f"/productos/{product_id}")
    # Stock 10.5 rendered as "10,50 und" (Paraguayan format: 2 decimals, comma)
    assert "10,50" in response.text, f"Expected formatted stock in HTML; got first 300 chars: {response.text[:300]}"


def test_detalle_shows_recipes_using(authed_client, session_factory):
    """When product is in 1+ recipes, the recipe list appears"""
    with session_factory() as s:
        # Create recipe with ingredients
        from app.rms.models import Ingredient
        ingredient = Ingredient(name="Harina", unit="kg", stock_qty=10.0)
        s.add(ingredient)
        s.flush()

        recipe = Recipe(name="Receta Test", yield_qty=12.0)
        s.add(recipe)
        s.flush()

        recipe_line = RecipeLine(
            recipe_id=recipe.id,
            line_kind="ingredient",
            line_ref_id=ingredient.id,
            qty=0.5,
            line_unit="kg"
        )
        s.add(recipe_line)

        # Create product that uses the recipe
        product = Product(name="Producto con Receta", sale_price_gs=4000, recipe_id=recipe.id)
        s.add(product)
        s.commit()
        product_id = product.id

    response = authed_client.get(f"/productos/{product_id}")
    assert "Receta Test" in response.text
    assert "Uso en recetas" in response.text


def test_detalle_no_recipes_empty_state(authed_client, session_factory):
    """When product is in 0 recipes, the empty state shows"""
    with session_factory() as s:
        product = Product(name="Producto Sin Receta", sale_price_gs=3000)
        s.add(product)
        s.commit()
        product_id = product.id

    response = authed_client.get(f"/productos/{product_id}")
    assert "No se usa en ninguna receta todavía" in response.text


def test_detalle_recent_sales_section(authed_client, session_factory):
    """Response contains 'Ventas recientes' or similar header"""
    with session_factory() as s:
        product = Product(name="Producto con Ventas", sale_price_gs=2000)
        s.add(product)
        s.commit()
        product_id = product.id

        # Create a test sale
        from datetime import datetime, timezone

        from app.rms.costing import apply_sale

        today = datetime.now(timezone.utc).replace(hour=12, minute=0, second=0, microsecond=0)
        apply_sale(
            s, product_id=product_id, qty=2.0,
            sold_at=today, notes=None, customer_id=None,
            payment_method="efectivo", discount_gs=0, channel="mostrador"
        )
        s.commit()

    response = authed_client.get(f"/productos/{product_id}")
    assert "Ventas recientes" in response.text


def test_detalle_action_buttons_present(authed_client, session_factory):
    """Response contains edit link + favorite form"""
    with session_factory() as s:
        product = Product(name="Producto con Botones", sale_price_gs=4000)
        s.add(product)
        s.commit()
        product_id = product.id

    response = authed_client.get(f"/productos/{product_id}")
    assert f"/productos/{product_id}/editar" in response.text
    assert f'form method="POST" action="/productos/{product_id}/favorito"' in response.text


def test_detalle_paraguay_money_format(authed_client, session_factory):
    """Response contains 'Gs.' formatting"""
    with session_factory() as s:
        product = Product(name="Producto Test", sale_price_gs=5000)
        s.add(product)
        s.commit()
        product_id = product.id

    response = authed_client.get(f"/productos/{product_id}")
    assert "Gs." in response.text
    assert "5.000" in response.text  # Paraguayan format for 5000 Gs.


def test_detalle_list_page_links_to_detail(authed_client, session_factory):
    """GET /productos and confirm each row has a 'Ver' link to /productos/{id}"""
    with session_factory() as s:
        # Create multiple products
        products = [
            Product(name="Producto 1", sale_price_gs=1000),
            Product(name="Producto 2", sale_price_gs=2000),
            Product(name="Producto 3", sale_price_gs=3000),
        ]
        for p in products:
            s.add(p)
        s.commit()

        product_ids = [p.id for p in products]

    response = authed_client.get("/productos")
    assert response.status_code == 200

    # Check that each product row has a 'Ver' link (icon + 'Ver' text, then </a>)
    for product_id in product_ids:
        # The link is <a href="/productos/{id}" class="btn..."><svg/>...Ver</a>
        assert f'href="/productos/{product_id}"' in response.text
    # The 'Ver' text appears in the actions column for every product row
    assert response.text.count("Ver\n        </a>") >= len(product_ids)
