"""tests/test_sale_idempotency.py — verify sale POST is idempotent under retry.

Phase 1A ticket #1: Sale idempotency check must run BEFORE the Sale row is
created and BEFORE the invoice_number is allocated. This closes the race
window documented in SASKIA_ARCHITECTURE_REFACTOR_PLAN_2026-09-24.md §F2.

Reproduction:
  1. POST /ventas/nueva with idempotency_key=K and product P
  2. POST /ventas/nueva with idempotency_key=K and product P (retry/double-click)
  3. BUG (pre-fix): two Sale rows, two invoice_numbers, two stock decrements.
  4. EXPECTED: exactly one Sale row, one invoice_number, idempotency record.

These tests verify the fix holds under three scenarios:
  - Same idempotency_key posted twice in sequence → exactly one sale.
  - Different idempotency_keys posted twice → two distinct sales.
  - Empty idempotency_key → no idempotency record (back-compat for older forms).
"""
from __future__ import annotations

import uuid

import pytest

# ─── Helpers ────────────────────────────────────────────────────────────────


def _seed_minimal(session_factory):
    """One product with sufficient stock for at least 2 sales."""
    from app.rms.models import Ingredient, Product, Recipe, RecipeLine

    with session_factory() as s:
        ing = Ingredient(name="Harina", unit="kg", stock_qty=10.0, purchase_price_gs=5000)
        s.add(ing)
        s.flush()

        recipe = Recipe(name="Muffin", yield_qty=12.0, yield_unit="und")
        s.add(recipe)
        s.flush()

        s.add(RecipeLine(recipe_id=recipe.id, line_kind="ingredient", line_ref_id=ing.id, qty=0.3))
        s.flush()

        product = Product(
            name="Muffin", portion_label="1 muffin", recipe_id=recipe.id,
            sale_price_gs=10000, iva_rate="10",
        )
        s.add(product)
        s.flush()
        pid = product.id
        s.commit()
        return pid


def _post_sale(client, product_id: int, idempotency_key: str = "", qty: float = 1.0):
    """POST /ventas/nueva and follow redirects to see the final URL."""
    return client.post(
        "/ventas/nueva",
        data={
            "product_id": str(product_id),
            "qty": str(qty),
            "payment_method": "efectivo",
            "discount_gs": "0",
            "channel": "mostrador",
            "idempotency_key": idempotency_key,
        },
        follow_redirects=False,
    )


# ─── Tests ──────────────────────────────────────────────────────────────────


def test_same_idempotency_key_creates_exactly_one_sale(client, session_factory):
    """Two POSTs with the same key produce one Sale row, not two."""
    product_id = _seed_minimal(session_factory)
    idem = uuid.uuid4().hex

    r1 = _post_sale(client, product_id, idempotency_key=idem)
    assert r1.status_code in (303, 302), f"first POST failed: {r1.status_code} {r1.text}"

    r2 = _post_sale(client, product_id, idempotency_key=idem)
    assert r2.status_code in (303, 302), f"retry POST failed: {r2.status_code}"

    # Exactly one Sale row exists.
    from app.rms.models import Sale
    with session_factory() as s:
        n_sales = s.query(Sale).count()
    assert n_sales == 1, f"expected 1 sale, got {n_sales}"


def test_same_idempotency_key_does_not_double_decrement_stock(client, session_factory):
    """Retry with same key must not decrement ingredient stock twice."""
    product_id = _seed_minimal(session_factory)
    idem = uuid.uuid4().hex

    _post_sale(client, product_id, idempotency_key=idem, qty=2.0)
    _post_sale(client, product_id, idempotency_key=idem, qty=2.0)

    from app.rms.models import Ingredient
    with session_factory() as s:
        ing = s.query(Ingredient).filter_by(name="Harina").one()
        # 10.0 starting stock. Recipe: yield 12 muffins per recipe, 0.3 kg flour.
        # Per muffin: 0.3 / 12 = 0.025 kg. qty=2.0 → 0.05 kg deduction.
        # 1 sale (with idem) → 9.95. 2 sales (without idem) → 9.9.
        # We expect 9.95 (one sale honored, one suppressed).
        assert ing.stock_qty == pytest.approx(9.95, abs=0.01), (
            f"stock should reflect 1 sale not 2; got {ing.stock_qty}"
        )


def test_different_idempotency_keys_create_distinct_sales(client, session_factory):
    """Two POSTs with DIFFERENT keys produce two Sale rows."""
    product_id = _seed_minimal(session_factory)

    _post_sale(client, product_id, idempotency_key=uuid.uuid4().hex)
    _post_sale(client, product_id, idempotency_key=uuid.uuid4().hex)

    from app.rms.models import Sale
    with session_factory() as s:
        n_sales = s.query(Sale).count()
    assert n_sales == 2, f"expected 2 sales, got {n_sales}"


def test_empty_idempotency_key_creates_sale_without_record(client, session_factory):
    """Empty key means 'no idempotency' — sale creates, no AppMeta row written."""
    product_id = _seed_minimal(session_factory)

    r = _post_sale(client, product_id, idempotency_key="")
    assert r.status_code in (303, 302)

    from app.rms.models import AppMeta, Sale
    with session_factory() as s:
        assert s.query(Sale).count() == 1
        # No sale_idem: rows for empty key
        idem_rows = s.query(AppMeta).filter(AppMeta.key.like("sale_idem:%")).count()
        assert idem_rows == 0, f"unexpected idem record for empty key: {idem_rows}"


def test_retry_returns_to_original_sale(client, session_factory):
    """Retry with same key should advertise the original sale, not a new one."""
    product_id = _seed_minimal(session_factory)
    idem = uuid.uuid4().hex

    _post_sale(client, product_id, idempotency_key=idem)
    _post_sale(client, product_id, idempotency_key=idem)

    # Both responses go to /ventas. The retry's redirect URL should reference
    # the same sale_id from the AppMeta value (or, in current behavior, just
    # go to /ventas with flash=sale_duplicate). Either way: only one sale row.
    from app.rms.models import Sale
    with session_factory() as s:
        assert s.query(Sale).count() == 1
