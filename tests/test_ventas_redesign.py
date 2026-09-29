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
