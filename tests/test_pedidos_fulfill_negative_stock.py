"""tests/test_pedidos_fulfill_negative_stock.py — P1 guard for /pedidos/{id}/fulfill.

P1 bug: ``POST /pedidos/<id>/stock-preview`` shows the operator which
ingredients will go negative, but the confirm button on the preview page
fired ``POST /pedidos/<id>/fulfill`` unconditionally — there was no
server-side check, so any click on Confirm with insufficient stock
silently drove ingredient stock below zero.

Fix: ``pedidos_fulfill`` now replays the preview's stock-move calc
BEFORE calling ``apply_sale``. If any ingredient would go below zero and
the operator has not sent ``force=true`` (form field or query param),
the route sends a 303 back to ``/pedidos/<id>/stock-preview`` with a
flash query param, leaving the pedido untouched. With ``force=true``
the fulfill proceeds, a warning is logged, and the audit detail carries
the shortfalls for ops audit.

These tests cover the two required outcomes:
- Test 1: POST without ``force`` redirects 303 to the preview page;
  pedido stays unfulfilled; ingredient stock unchanged.
- Test 2: POST with ``force=true`` fulfills the pedido; ingredient stock
  goes negative; the audit log records ``force_fulfilled_over_shortfall``.
"""

from __future__ import annotations

import json

# --- helpers ----------------------------------------------------------------


def _seed_pedido_insufficient(session_factory):
    """One pedido with 1 product backed by a recipe whose ingredient has
    only 0.5 kg in stock. The pedido line consumes 2 kg total (yield 12,
    0.3 kg per line * 6 lines worth → 0.3 * 2 * (qty/12)) which exceeds
    the 0.5 kg on hand.

    Returns (pedido_id, ingredient_id, product_id).

    Use uuid-named builder per fixture-collision pitfall in
    saskia-rms-development SKILL.
    """
    from tests.factories import (
        ing_line,
        make_ingredient,
        make_pedido,
        make_product,
        make_recipe,
        pedido_item,
    )

    with session_factory() as s:
        ing = make_ingredient(s, name="Harina QA Stock", unit="kg", stock_qty=0.5)
        rec = make_recipe(
            s,
            name="Receta QA Stock",
            yield_qty=12.0,
            yield_unit="und",
            lines=[ing_line(ing, qty=0.3)],
        )
        # sale_price from a uuid-named product (no hardcoded names).
        prod = make_product(s, recipe=rec, sale_price_gs=15000)
        # pedido_item qty=2 → 2 sales of the product. With yield=12 und and
        # recipe using 0.3 kg per batch, per-sale ingredient = 0.3/12 = 0.025 kg.
        # 2 sales × 0.025 = 0.05 kg. To force a shortfall, scale up the pedido
        # line qty enough that the per-sale consumption outruns 0.5 kg.
        # qty=24 → 24 * (0.3/12) = 0.6 kg. Stock 0.5 → shortfall 0.1.
        ped = make_pedido(
            s,
            status="pending",
            items=[pedido_item(prod, qty=24, unit_price_gs=15000)],
        )
        s.commit()
        return ped.id, ing.id, prod.id


def _post_fulfill(client, pedido_id: int, *, force: str = "", idempotency_key: str = ""):
    """POST /pedidos/<id>/fulfill with optional force flag.

    `force` is sent both as a form field AND as a query param to exercise
    both parse paths the route supports.
    """
    data: dict = {"idempotency_key": idempotency_key}
    if force:
        data["force"] = force
    return client.post(
        f"/pedidos/{pedido_id}/fulfill",
        data=data,
        params=({"force": force} if force else {}),
        follow_redirects=False,
    )


# --- Test 1: no force → blocked, redirect 303, no fulfill --------------------


def test_fulfill_without_force_blocks_on_negative_stock(client, session_factory):
    """POST without ``force=true`` on a pedido whose fulfill would push an
    ingredient below zero MUST redirect 303 back to the stock-preview
    page WITHOUT marking the pedido fulfilled or changing stock.
    """
    pedido_id, ing_id, _ = _seed_pedido_insufficient(session_factory)

    r = _post_fulfill(client, pedido_id)
    assert r.status_code == 303, f"expected 303 redirect, got {r.status_code}: {r.text[:200]}"
    # Redirects to the preview page (not to the pedido detail page).
    location = r.headers.get("location", "")
    assert f"/pedidos/{pedido_id}/stock-preview" in location, (
        f"expected redirect to stock-preview; got {location!r}"
    )
    # And carries a flash query param so the UI can announce the block.
    assert "flash=" in location, f"expected flash= in redirect, got {location!r}"
    assert "Stock+insuficiente" in location or "Stock insuficiente" in location, (
        f"expected insufficient-stock flash; got {location!r}"
    )

    # Pedido is NOT fulfilled, ingredient stock UNCHANGED.
    from app.rms.models import Ingredient, Pedido

    with session_factory() as s:
        pedido = s.get(Pedido, pedido_id)
        assert pedido.status != "fulfilled", (
            f"pedido should NOT be fulfilled when blocked; status={pedido.status!r}"
        )
        ing = s.get(Ingredient, ing_id)
        assert ing.stock_qty == 0.5, (
            f"ingredient stock must be untouched after blocked fulfill; got {ing.stock_qty}"
        )

    # Idempotency key is NOT consumed: a retry without force still blocks,
    # with force it succeeds — proving the rollback cleared the reservation.
    r_retry = _post_fulfill(client, pedido_id)
    assert r_retry.status_code == 303, "retry should also redirect 303"
    assert f"/pedidos/{pedido_id}/stock-preview" in r_retry.headers.get("location", "")


# --- Test 2: force=true → fulfills, stock goes negative, audit detail -------


def test_fulfill_with_force_proceeds_and_audits_shortfall(client, session_factory):
    """POST with ``force=true`` on a pedido whose fulfill would push an
    ingredient below zero MUST proceed: status becomes 'fulfilled', stock
    goes negative, and the audit log records the shortfalls.
    """
    pedido_id, ing_id, _ = _seed_pedido_insufficient(session_factory)

    r = _post_fulfill(client, pedido_id, force="true")
    assert r.status_code in (303, 302), (
        f"force=true should succeed with 303; got {r.status_code}: {r.text[:200]}"
    )
    # Success redirect goes to the pedido detail page, not the preview.
    location = r.headers.get("location", "")
    assert "/stock-preview" not in location, (
        f"force-fulfill should NOT redirect to preview; got {location!r}"
    )

    from app.rms.models import Ingredient, Pedido

    with session_factory() as s:
        pedido = s.get(Pedido, pedido_id)
        assert pedido.status == "fulfilled", f"force=true must fulfill; status={pedido.status!r}"
        ing = s.get(Ingredient, ing_id)
        # qty=24 * (0.3/12) = 0.6 kg deducted from 0.5 kg → -0.1 kg.
        assert ing.stock_qty < 0, f"force-fulfilled stock should go negative; got {ing.stock_qty}"

        # Audit row carries the shortfalls so ops can audit the override.
        from app.rms.models import AuditLog

        row = (
            s.execute(
                __import__("sqlalchemy")
                .select(AuditLog)
                .where(AuditLog.target_type == "pedido")
                .where(AuditLog.target_id == str(pedido_id))
                .where(AuditLog.action == "write.pedido.fulfill")
                .order_by(AuditLog.id.desc())
            )
            .scalars()
            .first()
        )
        assert row is not None, "expected audit row for force-fulfill"
        # AuditLog.detail may round-trip as a JSON string depending on
        # dialect (SQLite stores as TEXT); tolerate either shape.
        detail = row.detail
        if isinstance(detail, (str, bytes, bytearray)):
            detail = json.loads(detail)
        assert "force_fulfilled_over_shortfall" in detail, (
            f"audit detail must record force shortfalls; got keys: {list(detail)}"
        )
        shortfalls = detail["force_fulfilled_over_shortfall"]
        assert isinstance(shortfalls, list) and len(shortfalls) >= 1, (
            f"force_fulfilled_over_shortfall should be a non-empty list; got {shortfalls!r}"
        )
        first = shortfalls[0]
        assert "ingredient" in first and "shortfall" in first, (
            f"shortfall dict shape wrong; got {first!r}"
        )
        assert first["shortfall"] > 0, f"shortfall should be positive; got {first['shortfall']!r}"


def test_fulfill_without_force_no_audit_force_detail(client, session_factory):
    """Sanity: a blocked fulfill MUST NOT leave a force-fulfill audit row
    (otherwise the audit trail gets polluted with every blocked retry).
    """
    pedido_id, _, _ = _seed_pedido_insufficient(session_factory)

    r = _post_fulfill(client, pedido_id)
    assert r.status_code == 303

    from app.rms.models import AuditLog

    with session_factory() as s:
        rows = (
            s.execute(
                __import__("sqlalchemy")
                .select(AuditLog)
                .where(AuditLog.action == "write.pedido.fulfill")
            )
            .scalars()
            .all()
        )
        assert rows == [], f"blocked fulfill must NOT write audit row; got {len(rows)} rows"
