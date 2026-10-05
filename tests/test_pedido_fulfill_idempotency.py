"""tests/test_pedido_fulfill_idempotency.py — verify pedido fulfill is idempotent.

Phase 1A ticket #2: Pedido fulfillment idempotency record must be written
in the SAME transaction as the Sales + stock moves, not AFTER. This
closes the race window in SASKIA_ARCHITECTURE_REFACTOR_PLAN_2026-09-24.md
§F3 where a retry could double-deduct stock and emit two WhatsApp
notifications.

Reproduction:
  1. POST /pedidos/{id}/fulfill with idempotency_key=K
  2. POST /pedidos/{id}/fulfill with idempotency_key=K (retry)
  3. BUG (pre-fix): two sets of Sales, double stock deduction, two pings.
  4. EXPECTED: exactly one fulfill, one set of Sales, single stock hit.
"""

# allow-hardcoded-dates: idempotency key derives from fixed date
from __future__ import annotations

import uuid

import pytest


def _seed_pedido_minimal(session_factory):
    """One pedido with 1 product (1 ingredient) ready to fulfill."""
    from app.rms.models import (
        Ingredient,
        Pedido,
        PedidoLine,
        Product,
        Recipe,
        RecipeLine,
    )

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
            name="Muffin",
            portion_label="1 muffin",
            recipe_id=recipe.id,
            sale_price_gs=10000,
            iva_rate="10",
        )
        s.add(product)
        s.flush()

        from datetime import date as _date

        pedido = Pedido(
            status="pending",
            notes="Test pedido",
            payment_intent="efectivo",
            promised_date=_date(2026, 9, 24),
            promised_time="14:00",
            channel="whatsapp",
        )
        s.add(pedido)
        s.flush()

        s.add(
            PedidoLine(
                pedido_id=pedido.id,
                product_id=product.id,
                qty=2.0,
                unit_price_gs=10000,
            )
        )
        s.flush()

        pid = pedido.id
        ing_id = ing.id
        s.commit()
        return pid, ing_id


def _post_fulfill(client, pedido_id: int, idempotency_key: str = ""):
    return client.post(
        f"/pedidos/{pedido_id}/fulfill",
        data={"idempotency_key": idempotency_key},
        follow_redirects=False,
    )


# ─── Tests ──────────────────────────────────────────────────────────────────


def test_same_idempotency_key_fulfills_once(client, session_factory):
    """Two POSTs with same key create exactly one fulfill + one set of Sales."""
    pedido_id, _ = _seed_pedido_minimal(session_factory)
    idem = uuid.uuid4().hex

    r1 = _post_fulfill(client, pedido_id, idempotency_key=idem)
    assert r1.status_code in (303, 302, 409), f"first fulfill failed: {r1.status_code}"

    # Second POST should redirect (303) or 409 (already fulfilled), NOT create new sales.
    r2 = _post_fulfill(client, pedido_id, idempotency_key=idem)
    assert r2.status_code in (303, 302, 409)

    from app.rms.models import Pedido, Sale

    with session_factory() as s:
        pedido = s.get(Pedido, pedido_id)
        assert pedido.status == "fulfilled"
        # Exactly one Sale row from this fulfill
        n_sales = s.query(Sale).filter_by(product_id=pedido.lines[0].product_id).count()
    assert n_sales == 1, f"expected 1 sale, got {n_sales}"


def test_same_idempotency_key_does_not_double_deduct_stock(client, session_factory):
    """Retry with same key must not decrement ingredient stock twice."""
    pedido_id, ing_id = _seed_pedido_minimal(session_factory)
    idem = uuid.uuid4().hex

    _post_fulfill(client, pedido_id, idempotency_key=idem)
    _post_fulfill(client, pedido_id, idempotency_key=idem)

    from app.rms.models import Ingredient

    with session_factory() as s:
        ing = s.get(Ingredient, ing_id)
        # 10.0 starting. Recipe: yield 12, 0.3 kg per recipe. Per muffin = 0.025 kg.
        # PedidoLine qty=2.0 → 0.05 kg deduction.
        # 1 fulfill (with idem) → 9.95. 2 fulfills (without idem) → 9.9.
        assert ing.stock_qty == pytest.approx(9.95, abs=0.01), (
            f"stock should reflect 1 fulfill not 2; got {ing.stock_qty}"
        )


def test_different_idempotency_keys_still_409(client, session_factory):
    """After a successful fulfill, a fresh idempotency key still 409s.

    Status check (pending/confirmed/ready) fires regardless of idem key.
    Once status=fulfilled, ANY fulfill attempt fails with 409.
    """
    pedido_id, _ = _seed_pedido_minimal(session_factory)

    r1 = _post_fulfill(client, pedido_id, idempotency_key=uuid.uuid4().hex)
    assert r1.status_code in (303, 302)

    r2 = _post_fulfill(client, pedido_id, idempotency_key=uuid.uuid4().hex)
    assert r2.status_code == 409, f"second fulfill should 409, got {r2.status_code}"


def test_empty_idempotency_key_does_not_create_record(client, session_factory):
    """Empty key means 'no idempotency' — fulfill happens, no AppMeta row."""
    pedido_id, _ = _seed_pedido_minimal(session_factory)

    r = _post_fulfill(client, pedido_id, idempotency_key="")
    assert r.status_code in (303, 302)

    from app.rms.models import AppMeta, Pedido

    with session_factory() as s:
        pedido = s.get(Pedido, pedido_id)
        assert pedido.status == "fulfilled"
        idem_rows = s.query(AppMeta).filter(AppMeta.key.like("pedido_fulfill_idem:%")).count()
        assert idem_rows == 0, f"unexpected idem record for empty key: {idem_rows}"


def test_appmeta_record_exists_after_successful_fulfill(client, session_factory):
    """After fulfill, the idem record must exist with value=str(pedido_id).

    Even though the existing TOCTOU pre-check handles serial retries, the
    record MUST be persisted (atomically with the fulfill, ideally) so a
    concurrent retry sees it. This test asserts the post-condition.
    """
    pedido_id, _ = _seed_pedido_minimal(session_factory)
    idem = uuid.uuid4().hex

    r = _post_fulfill(client, pedido_id, idempotency_key=idem)
    assert r.status_code in (303, 302)

    from app.rms.models import AppMeta

    with session_factory() as s:
        row = s.scalar(
            __import__("sqlalchemy")
            .select(AppMeta)
            .where(AppMeta.key == f"pedido_fulfill_idem:{idem}")
        )
    assert row is not None, "idempotency record missing after fulfill"
    # Value is JSON (Phase 1B #10): {pedido_id, sale_id, request_id}
    import json as _json

    payload = _json.loads(row.value)
    assert payload["pedido_id"] == str(pedido_id), (
        f"expected pedido_id={pedido_id}, got {payload['pedido_id']}"
    )


def test_concurrent_fulfills_one_winner_at_most(client, session_factory):
    """Two parallel-ish fulfills with the SAME key must produce ≤1 fulfill.

    Uses sequential POSTs (SQLite single-writer makes true concurrency tricky)
    but exercises the post-condition: at most one fulfill succeeded; the
    other must redirect (303) or 409.

    For a true race test, see test_pedido_fulfill_atomicity.py (uses real
    Postgres + threading).
    """
    pedido_id, _ = _seed_pedido_minimal(session_factory)
    idem = uuid.uuid4().hex

    # Sequential POSTs with same key. Even if a single postgres race exists
    # at the SQLite level, the status check at line 706 will catch the second.
    r1 = _post_fulfill(client, pedido_id, idempotency_key=idem)
    r2 = _post_fulfill(client, pedido_id, idempotency_key=idem)

    # First MUST be 303 (success). Second MUST be 303 (duplicate redirect) or 409.
    assert r1.status_code in (303, 302), f"first should succeed: {r1.status_code}"
    assert r2.status_code in (303, 302, 409), f"second should not 500: {r2.status_code}"

    # Exactly one fulfill (status=fulfilled), one set of sales.
    from app.rms.models import Pedido, Sale

    with session_factory() as s:
        pedido = s.get(Pedido, pedido_id)
        assert pedido.status == "fulfilled"
        # Count sales for THIS pedido via its lines
        product_ids = [ln.product_id for ln in pedido.lines]
        n_sales = s.query(Sale).filter(Sale.product_id.in_(product_ids)).count()
    assert n_sales == 1, f"expected 1 sale, got {n_sales}"
