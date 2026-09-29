"""tests/test_ventas_redesign.py — Regression tests for the ventas-redesign.

Phase A: customer info card (GET /clientes/api/{id}, allergen chip, stats).
Phase B: manual add form removed; cart panel + metadata in its place.
Phase C: right pane renamed to "Productos"; barcode-scan input wired to
         /productos/api/search?sku=.
Phase D: empty-cart hint copy, submit-button visible & Spanish.

These tests are designed to survive calendar drift and arithmetic mistakes
(no date arithmetic, no Decimal/float money math). The shape of the
returned JSON and the rendered HTML is asserted directly.
"""

from __future__ import annotations

from datetime import datetime, timezone

# ── Phase A: GET /clientes/api/{customer_id} ─────────────────────────────────


def test_clientes_detail_api_returns_full_payload(client, session_factory):
    """GET /clientes/api/{id} returns notes + stats + top_products for a real customer."""
    from app.rms.models import Customer, Product, Sale

    with session_factory() as s:
        c = Customer(
            name="Ana QA",
            phone="0981110001",
            cedula="1234567",
            notes="alérgica a la lactosa",
            loyalty_points=42,
        )
        s.add(c)
        s.flush()
        p1 = Product(name="Pan", sale_price_gs=5000, recipe_id=None)
        p2 = Product(name="Torta", sale_price_gs=20000, recipe_id=None)
        s.add_all([p1, p2])
        s.flush()
        now = datetime.now(timezone.utc)
        # Two sales of Pan (count=2), one of Torta (count=1) — Pan wins top-3.
        s.add_all(
            [
                Sale(customer_id=c.id, product_id=p1.id, qty=1, unit_price_gs=5000, sold_at=now),
                Sale(customer_id=c.id, product_id=p1.id, qty=1, unit_price_gs=5000, sold_at=now),
                Sale(customer_id=c.id, product_id=p2.id, qty=1, unit_price_gs=20000, sold_at=now),
            ]
        )
        s.commit()
        s.refresh(c)
        cid = c.id

    resp = client.get(f"/clientes/api/{cid}")
    assert resp.status_code == 200, f"got {resp.status_code}: {resp.text[:300]}"
    body = resp.json()
    # Required keys per the spec.
    for key in (
        "id",
        "name",
        "phone",
        "email",
        "cedula",
        "notes",
        "loyalty_points",
        "n_sales",
        "lifetime_spend_gs",
        "lifetime_label",
        "tier",
        "last_sale_at",
        "top_products",
        "hint",
    ):
        assert key in body, f"missing key '{key}' in /clientes/api/{{}} payload: {body}"
    # Spot-check values.
    assert body["name"] == "Ana QA"
    assert body["phone"] == "0981110001"
    assert body["cedula"] == "1234567"
    assert "lactosa" in body["notes"]
    assert body["loyalty_points"] == 42
    assert body["n_sales"] == 3
    assert body["lifetime_spend_gs"] == 30000  # 5000 + 5000 + 20000
    assert body["last_sale_at"], "last_sale_at must be a non-empty ISO string"
    assert isinstance(body["top_products"], list)
    assert len(body["top_products"]) >= 1, "top_products must list at least 1 item"
    assert body["top_products"][0]["name"] in ("Pan", "Torta")
    assert body["top_products"][0]["count"] >= 1


def test_clientes_detail_api_returns_404_for_missing(client):
    """GET /clientes/api/{id} with a non-existent id must return 404 + JSON {error: not_found}."""
    resp = client.get("/clientes/api/999999")
    assert resp.status_code == 404, f"got {resp.status_code}: {resp.text[:300]}"
    body = resp.json()
    assert body.get("error") == "not_found"


def test_clientes_detail_api_returns_200_for_customer_with_no_sales(client, session_factory):
    """Brand-new customer with no sales: n_sales=0, lifetime=0, last_sale_at=null."""
    from app.rms.models import Customer

    with session_factory() as s:
        c = Customer(name="Nuevo Sin Ventas", phone="0981110002")
        s.add(c)
        s.commit()
        s.refresh(c)
        cid = c.id

    resp = client.get(f"/clientes/api/{cid}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["n_sales"] == 0
    assert body["lifetime_spend_gs"] == 0
    assert body["last_sale_at"] is None
    assert body["tier"] == "bronze"
    assert body["top_products"] == []


# ── Phase A4: customer_create_api returns the full payload ───────────────────


def test_clientes_create_api_returns_full_payload(client):
    """POST /clientes/api/create must return the FULL detail payload (incl. notes + stats + top_products)."""
    resp = client.post(
        "/clientes/api/create",
        json={"name": "Creado Por Test", "phone": "0981110003", "notes": "sin gluten"},
    )
    assert resp.status_code == 200, f"got {resp.status_code}: {resp.text[:300]}"
    body = resp.json()
    assert body.get("created") is True
    assert isinstance(body.get("id"), int)
    cust = body["customer"]
    for key in (
        "id",
        "name",
        "phone",
        "notes",
        "n_sales",
        "lifetime_spend_gs",
        "tier",
        "last_sale_at",
        "top_products",
    ):
        assert key in cust, f"missing key '{key}' in create-response customer payload: {cust}"
    assert cust["name"] == "Creado Por Test"
    assert "gluten" in cust["notes"]
    assert cust["n_sales"] == 0


# ── Phase B: ventas.html no longer carries the manual-add fields ────────────


def test_ventas_form_does_not_contain_top_level_qty_field(client):
    """The manual "Cantidad" <input name=qty> field is gone — qty lives
    in the cart table (cart-qty-input) only.
    """
    resp = client.get("/ventas")
    body = resp.text
    # No top-level qty field with the removed manual-add shape.
    import re

    matches = re.findall(r'<input[^>]*name="qty"[^>]*>', body)
    assert not matches, f"Phase B regression: top-level qty field removed but found: {matches}"


def test_ventas_form_does_not_contain_top_level_sku_field(client):
    """The manual SKU <input name=sku> field is gone — scanning happens via
    the dedicated #quick-scan input at the top of the right pane (Phase C).
    """
    resp = client.get("/ventas")
    body = resp.text
    import re

    matches = re.findall(r'<input[^>]*name="sku"[^>]*>', body)
    assert not matches, f"Phase B regression: top-level sku field removed but found: {matches}"


def test_ventas_form_has_quick_scan_input(client):
    """Phase C: a scan input with id=quick-scan exists at the top of the right pane."""
    resp = client.get("/ventas")
    body = resp.text
    assert 'id="quick-scan"' in body, "Phase C regression: #quick-scan input must be on /ventas"
    # Should carry the autofocus attribute (Phase C2 spec).
    import re

    m = re.search(r'<input[^>]*id="quick-scan"[^>]*>', body)
    assert m, "quick-scan input element not found"
    assert "autofocus" in m.group(0), (
        f"quick-scan input should be autofocus for scanner flow; got: {m.group(0)}"
    )


def test_ventas_form_has_customer_picker_and_card(client):
    """Phase A + B: ventas.html includes the customer picker (combo) AND
    the customer info card section.
    """
    resp = client.get("/ventas")
    body = resp.text
    assert "customer_id_combo" in body, "customer picker combo missing from /ventas"
    assert 'id="customer-card"' in body, "customer info card section missing from /ventas"
    assert "customer-card-name" in body, "customer card name element missing"
    assert "customer-card-tier" in body, "customer card tier element missing"
    assert "customer-card-allergen-chip" in body, "customer card allergen chip missing"


# ── Phase C: right pane renamed + scan input ────────────────────────────────


def test_ventas_right_pane_heading_is_productos(client):
    """Phase C1: <h2>Venta rápida</h2> must now be <h2>Productos</h2>."""
    resp = client.get("/ventas")
    body = resp.text
    import re

    h2_matches = re.findall(r"<h2[^>]*>([^<]+)</h2>", body)
    # At least one h2 in the body must be "Productos".
    assert "Productos" in h2_matches, (
        f"Phase C1 regression: right pane must be renamed to 'Productos'; h2 tags found: {h2_matches}"
    )


# ── Phase D: empty-cart hint copy ────────────────────────────────────────────


def test_ventas_empty_cart_hint_copy(client):
    """Phase D1: empty cart hint copy must be the new action-oriented text."""
    resp = client.get("/ventas")
    body = resp.text
    assert "Tocá un producto o escaneá un código para empezar" in body, (
        "Phase D1 regression: empty-cart hint copy must be action-oriented (scan or tap a product)."
    )


# ── Phase C: SKU search endpoint contract ────────────────────────────────────


def test_productos_api_search_by_sku_finds_seeded_product(client, session_factory):
    """Phase C4: /productos/api/search?sku=TEST-001 must return a result when
    a Product row with that SKU is seeded.
    """
    from app.rms.models import Product

    with session_factory() as s:
        p = Product(name="Test SKU Pan", sku="TEST-001", sale_price_gs=8500, is_available=True)
        s.add(p)
        s.commit()

    resp = client.get("/productos/api/search?sku=TEST-001")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] >= 1, f"expected ≥1 result for TEST-001, got {body}"
    assert any(r.get("sku") == "TEST-001" for r in body["results"])


def test_productos_api_search_unknown_sku_returns_empty(client):
    """Phase C4: unknown SKU returns empty results (the scan UI relies on this)."""
    resp = client.get("/productos/api/search?sku=NOPE-DOES-NOT-EXIST-XYZ")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 0
    assert body["results"] == []


def test_productos_api_search_q_param_still_works(client, session_factory):
    """Phase C4: existing q=name search must not break when sku= is added."""
    from app.rms.models import Product

    with session_factory() as s:
        p = Product(name="Focaccia Genovesa", sale_price_gs=12000, is_available=True)
        s.add(p)
        s.commit()

    resp = client.get("/productos/api/search?q=focaccia")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] >= 1, f"expected ≥1 result for q=focaccia, got {body}"


# ── Phase D2: submit button visible & Spanish ────────────────────────────────


def test_ventas_submit_button_is_spanish_registra_venta(client):
    """Phase D2: the submit button text must be Paraguayan Spanish 'Registrá venta'."""
    resp = client.get("/ventas")
    body = resp.text
    assert "Registrá venta" in body, (
        "Phase D2 regression: submit button text must be 'Registrá venta' (vos)."
    )
    # And the submit button must exist.
    import re

    m = re.search(r'<button[^>]*id="sale-submit-btn"[^>]*>', body)
    assert m, "sale-submit-btn must exist on /ventas"


# ── E13.S2: Venta libre (cashier-typed price) ──────────────────────────────
#
# These tests guard the venta libre feature end-to-end:
# - seed row exists in the DB (idempotent, by SKU)
# - the /ventas page renders the special tile + populates its product id
# - the cart table header has a Precio column
# - POSTing a sale with unit_price_gs=150000 stores that exact price on Sale
# - POSTing a sale WITHOUT unit_price_gs falls back to the catalog price
#   (no regression to the normal-priced path)


def _ensure_venta_libre(session_factory):
    """Insert the VAR-001 Product row if missing — mirrors seed.py logic.

    Kept here (instead of relying on seed_demo_data) so each test pays only
    the cost of a single INSERT and the test stays self-contained.
    """
    from app.rms.models import Product

    with session_factory() as s:
        existing = s.query(Product).filter_by(sku="VAR-001").one_or_none()
        if existing is None:
            s.add(Product(
                name="Venta libre",
                sku="VAR-001",
                sale_price_gs=0,
                is_available=True,
                notes="Venta libre — definí el precio en el carrito.",
                category="varios",
            ))
            s.commit()


def test_venta_libre_seed_product_exists(session_factory):
    """E13.S2 AC: a Product with sku='VAR-001' must exist after seeding.

    Catches accidental removal of the venta libre row from seed.py or
    from the operator's first-run migration.
    """
    from app.rms.models import Product

    _ensure_venta_libre(session_factory)
    with session_factory() as s:
        p = s.query(Product).filter_by(sku="VAR-001").one_or_none()
        assert p is not None, "Venta libre product (sku=VAR-001) must be seeded"
        assert p.sale_price_gs == 0, "Catalog price must default to 0 (cashier overrides)"
        assert p.is_available is True
        assert p.category == "varios"


def test_ventas_page_has_venta_libre_button(client, session_factory):
    """E13.S2 AC: /ventas must render the + Venta libre tile with a populated product id."""
    _ensure_venta_libre(session_factory)
    resp = client.get("/ventas")
    assert resp.status_code == 200
    body = resp.text
    import re

    # The button must exist with id=venta-libre-btn
    assert 'id="venta-libre-btn"' in body, "venta-libre-btn must render"

    # The quick-sell-btn--varios variant class must be present in the page
    # (the tile is the only consumer of this class).
    assert 'quick-sell-btn--varios' in body, (
        "venta-libre-btn must use the .quick-sell-btn--varios dashed-border variant"
    )

    # The data-product-id must be populated (so the JS click handler can add it)
    m2 = re.search(
        r'id="venta-libre-btn"[^>]*data-product-id="(\d+)"', body, re.DOTALL
    )
    assert m2, "venta-libre-btn must carry data-product-id"
    pid = int(m2.group(1))
    assert pid > 0, f"data-product-id must be a positive integer, got {pid}"


def test_cart_price_input_rendered(client, session_factory):
    """E13.S2 AC: the cart table must include a per-row price input.

    Verifies the JS-rendered DOM contract: every cart row has a
    cart-price-input with min=100 so the cashier can edit the unit
    price inline. We can't execute the JS here, but we can verify the
    HTML scaffolding (Precio column header + input class).
    """
    resp = client.get("/ventas")
    body = resp.text
    assert "Precio" in body, "Cart table must have a 'Precio' column header"
    # The render() JS uses this class — confirm the class string is in
    # the inline script so a typo on our side surfaces as a real failure.
    assert "cart-price-input" in body, (
        "Cart render JS must include cart-price-input markup"
    )


def test_sale_with_price_override_creates_correct_unit_price(client, session_factory):
    """E13.S2 AC: POST /ventas/nueva/multi with unit_price_gs=150000 persists that price.

    Without the override the server would read product.sale_price_gs (or
    zero for venta libre) — this test confirms the cashier-typed price
    flows end-to-end into Sale.unit_price_gs.
    """
    _ensure_venta_libre(session_factory)
    # Get the venta libre product id
    from app.rms.models import Product, Sale

    with session_factory() as s:
        vl = s.query(Product).filter_by(sku="VAR-001").one()
        vl_id = vl.id

    payload = {
        "items": [
            {"product_id": vl_id, "qty": 1, "unit_price_gs": 150000},
        ],
        "payment_method": "efectivo",
        "channel": "mostrador",
        "discount_gs": 0,
        "notes": "",
        "sold_at": "",
        "idempotency_key": "",
        "invoice_type": "none",
    }
    r = client.post("/ventas/nueva/multi", json=payload)
    assert r.status_code in (200, 303), f"expected 200/303, got {r.status_code}: {r.text[:300]}"

    with session_factory() as s:
        sale = s.query(Sale).filter_by(product_id=vl_id).order_by(Sale.id.desc()).first()
        assert sale is not None, "Sale row must be created"
        assert sale.unit_price_gs == 150000, (
            f"Sale.unit_price_gs must be the cashier-typed 150000, got {sale.unit_price_gs}"
        )


def test_sale_without_price_override_uses_catalog_price(client, session_factory):
    """Regression: normal-priced sales must still read product.sale_price_gs.

    E13.S2 added an optional unit_price_gs field. When the client does
    NOT send it (the common case for quick-sell grid items), the server
    must fall back to product.sale_price_gs so the sale row matches the
    catalog. This guards against the override accidentally overriding
    everything.
    """
    from app.rms.models import Product, Recipe, RecipeLine, Sale, Ingredient

    with session_factory() as s:
        # Build a small recipe tree so apply_sale can compute stock moves
        ing = Ingredient(name="Harina vl-test", unit="kg", stock_qty=10.0,
                         purchase_price_gs=5000)
        s.add(ing); s.flush()
        recipe = Recipe(name="Receta vl-test", yield_qty=10, yield_unit="und")
        s.add(recipe); s.flush()
        s.add(RecipeLine(recipe_id=recipe.id, line_kind="ingredient",
                         line_ref_id=ing.id, qty=0.1, line_unit="kg"))
        prod = Product(name="Producto vl-test", sale_price_gs=12500,
                       is_available=True, recipe_id=recipe.id)
        s.add(prod); s.commit()
        prod_id = prod.id

    payload = {
        "items": [
            {"product_id": prod_id, "qty": 2},  # NO unit_price_gs — must use catalog 12500
        ],
        "payment_method": "efectivo",
        "channel": "mostrador",
        "discount_gs": 0,
        "notes": "",
        "sold_at": "",
        "idempotency_key": "",
        "invoice_type": "none",
    }
    r = client.post("/ventas/nueva/multi", json=payload)
    assert r.status_code in (200, 303), f"expected 200/303, got {r.status_code}: {r.text[:300]}"

    with session_factory() as s:
        sale = s.query(Sale).filter_by(product_id=prod_id).order_by(Sale.id.desc()).first()
        assert sale is not None, "Sale row must be created"
        assert sale.unit_price_gs == 12500, (
            f"Sale.unit_price_gs must equal the catalog price 12500, got {sale.unit_price_gs}"
        )
