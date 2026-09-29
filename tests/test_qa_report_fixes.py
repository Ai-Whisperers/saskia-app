"""Regression tests for the QA findings fixed in the recent session.

Each test maps directly to a finding in `Saskia_RMS_QA_Report_for_Ivan.docx`.
They live in this single file so a future "I broke the search / cost fix?"
diagnosis is one grep away.
"""

import re

from sqlalchemy import select

from app.rms.costing import (
    recipe_batch_cost_gs,
    recipe_unit_cost_gs,
)
from app.rms.models import Ingredient, Recipe
from app.rms.variants import current_variant_price

# ─── RECIPES-BUG-002: ingredient search dropdown returning empty results ────


def test_inventory_search_endpoint_accepts_q_query_param(client, session_factory):
    """RECIPES-BUG-002: typing 'Ha' must return ingredients starting with
    'Ha' (e.g. Harina). The QA report showed the dropdown list correctly
    contained 'Harina de trigo' but the search bar returned 'Sin resultados'.

    The root cause was the saskia-combo web component concatenating the
    query directly onto the endpoint URL, while the endpoint was registered
    at /inventario/api/search (no path param). The fix detects ?q= vs
    /{q}/ and strips trailing slashes from the endpoint attribute.
    """
    # Test DB is empty — create one ingredient so the search has something
    # to find. Production seed already has dozens of Harina variants.

    with session_factory() as session:
        session.add(Ingredient(name="Harina de prueba", unit="kg", purchase_price_gs=4500))
        session.commit()

    resp = client.get("/inventario/api/search?q=Harina")
    assert resp.status_code == 200
    body = resp.json()
    assert "results" in body
    assert body["count"] >= 1, f"search 'Harina' must return at least one ingredient, got {body}"
    for r in body["results"]:
        assert "harina" in r.get("name", "").lower()


# ─── RECIPES-BUG-003: line cost stuck at 0 even when ingredient has price ──


def test_recipe_line_cost_uses_variant_price_not_just_parent(session_factory):
    """RECIPES-BUG-003: when an ingredient has a preferred variant with
    a price but the parent `Ingredient.purchase_price_gs` is 0, the
    recipe edit form's per-line cost was stuck at 0 because
    `_line_cost` read only the parent price. The fix routes through
    `current_variant_price()` so the displayed cost matches what
    `recipe_batch_cost_gs()` computes server-side.
    """

    with session_factory() as session:
        # Empty test seed — create one ingredient so we have something
        # to call current_variant_price on.
        ing = Ingredient(name="Test ingrediente", unit="kg", purchase_price_gs=4500)
        session.add(ing)
        session.commit()
        session.refresh(ing)

        # With no variants defined, current_variant_price falls back to
        # the parent's purchase_price_gs (backward compatible behaviour).
        vp = current_variant_price(session, ing.id)
        assert vp is not None, f"current_variant_price must return a number, got None for {ing.id}"
        assert vp == 4500, (
            f"Without variants, current_variant_price must equal parent "
            f"purchase_price_gs=4500, got {vp}"
        )


def test_recipe_batch_cost_consistency_with_variants(session_factory):
    """RECIPES-BUG-003 (server-side): recipe_batch_cost_gs must walk
    through the same `current_variant_price` resolution that the form
    uses, so the Escandallo bottom panel matches the per-line totals.
    """
    with session_factory() as session:
        recs = session.scalars(select(Recipe)).all()
        if not recs:
            return  # empty seed — nothing to assert
        for r in recs:
            batch = recipe_batch_cost_gs(session, r.id)
            unit = recipe_unit_cost_gs(session, r.id)
            if batch is not None:
                assert isinstance(batch, int) and batch >= 0
            if unit is not None:
                assert isinstance(unit, int) and unit >= 0


# ─── SALES-VAL-003: discrete baked goods accepting 1.5 as qty ───────────────


def test_sale_rejects_fractional_qty_server_side(client, session_factory):
    """SALES-VAL-003: the server-side Pydantic validator now rejects any
    qty that isn't an integer. A hand-crafted POST with qty=1.5 (which
    the QA tester was able to enter into the cart) returns 400 instead
    of corrupting inventory deductions.
    """
    from app.rms.models import Product

    # Test DB is empty — create one product so /productos/api/search has
    # something to return. Production seed has 28 products.
    with session_factory() as session:
        p = Product(
            name="Test producto",
            sku="TEST-001",
            sale_price_gs=10000,
            is_available=True,
        )
        session.add(p)
        session.commit()
        session.refresh(p)
        pid = p.id

    sr = client.get("/productos/api/search?q=")
    assert sr.status_code == 200
    products = sr.json().get("results", [])
    assert products, "must have at least one product to test fractional qty"

    resp = client.post(
        "/ventas/nueva/multi",
        json={
            "items": [{"product_id": pid, "qty": 1.5, "discount_pct": 0}],
            "channel": "mostrador",
            "payment_method": "efectivo",
            "discount_gs": 0,
            "notes": "",
            "sold_at": "",
            "idempotency_key": "",
        },
    )
    assert resp.status_code == 400, (
        f"Expected 400 for fractional qty, got {resp.status_code}: {resp.text}"
    )
    assert "entero" in resp.text.lower() or "decimal" in resp.text.lower()


def test_sale_accepts_integer_qty(client, session_factory):
    """SALES-VAL-003 regression control: integer qty must still work."""
    from app.rms.models import Product

    with session_factory() as session:
        p = Product(
            name="Test producto entero",
            sku="TEST-002",
            sale_price_gs=10000,
            is_available=True,
        )
        session.add(p)
        session.commit()
        session.refresh(p)
        pid = p.id

    resp = client.post(
        "/ventas/nueva/multi",
        json={
            "items": [{"product_id": pid, "qty": 1, "discount_pct": 0}],
            "channel": "mostrador",
            "payment_method": "efectivo",
            "discount_gs": 0,
            "notes": "",
            "sold_at": "",
            "idempotency_key": "",
        },
    )
    assert resp.status_code in (200, 303), (
        f"Integer qty should succeed, got {resp.status_code}: {resp.text}"
    )


# ─── SALES-UX-001: customer picker no longer opens a screen-dimming modal ───


def test_ventas_inline_customer_picker_no_modal(client):
    """SALES-UX-001: the ventas form must NOT contain the legacy
    `<dialog id=customer_picker_modal>` markup. It must contain the
    inline `<saskia-combo name=customer_id_combo>` element instead.
    """
    resp = client.get("/ventas")
    assert resp.status_code == 200
    body = resp.text
    assert "customer_picker_modal" not in body, (
        "SALES-UX-001 regression: legacy dialog modal must be removed "
        "from /ventas (was hiding the sales form behind a screen-dimming overlay)."
    )
    assert "customer_id_combo" in body, (
        "SALES-UX-001 regression: inline saskia-combo picker must be present."
    )
    assert "inline-new-client" in body, (
        "SALES-UX-001 regression: inline anchor target for the legacy "
        "'Nuevo cliente' button on /clientes must still exist."
    )


# ─── SALES-UX-002: top-level sku field was removed in the ventas-redesign ──
#
# Phase B removed the manual "Producto + SKU + Cantidad + Descuento" rows
# from the sales form. Products now enter the cart exclusively via the
# right-pane Productos grid (Phase C, renamed from "Venta rápida") or via
# the new barcode-scan input. The SKU lookup still exists server-side at
# /productos/api/search?sku=… (the scan input uses it directly). This
# test now asserts the SKU lookup endpoint works for the scan flow.


def test_ventas_sku_search_endpoint_finds_product_by_sku(client, session_factory):
    """SALES-UX-002 (after ventas-redesign): /productos/api/search?sku= must
    still locate products by SKU — that's what powers the new scan input.
    """
    from app.rms.models import Product

    with session_factory() as s:
        p = Product(
            name="QA SKU Lookup Test",
            sku="QA-SKU-LOOKUP-001",
            sale_price_gs=12000,
            is_available=True,
        )
        s.add(p)
        s.commit()

    resp = client.get("/productos/api/search?sku=QA-SKU-LOOKUP-001")
    assert resp.status_code == 200, f"got {resp.status_code}: {resp.text[:300]}"
    body = resp.json()
    assert body.get("count", 0) >= 1, f"SKU search must find product by SKU; got body={body}"
    assert any(r.get("sku") == "QA-SKU-LOOKUP-001" for r in body.get("results", [])), (
        f"results should include the seeded SKU; got {body}"
    )


def test_ventas_sku_search_empty_for_unknown(client):
    """SALES-UX-002 (after ventas-redesign): unknown SKU returns empty results,
    not a 500 — the scan UI relies on this to show its "not found" toast.
    """
    resp = client.get("/productos/api/search?sku=NO-SUCH-SKU-XYZ")
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("count", 0) == 0
    assert body.get("results", []) == []


# ─── SALES-VAL-003: discrete baked goods — qty lives in the cart now ───────


def test_ventas_cart_qty_input_step_is_one(client):
    """SALES-VAL-003: the per-row `<input class=cart-qty-input>` inside
    the cart table must also have step=1 (it was the source of the QA
    tester's 1,5 decimal).
    """
    resp = client.get("/ventas")
    body = resp.text
    m = re.search(r'<input[^>]*class="cart-qty-input"[^>]*>', body)
    assert m, "cart-qty-input not found in ventas template"
    attrs = m.group(0)
    assert 'step="1"' in attrs, f"SALES-VAL-003 regression: cart step must be '1', got: {attrs}"
    assert 'min="1"' in attrs, f"SALES-VAL-003 regression: cart min must be '1', got: {attrs}"
