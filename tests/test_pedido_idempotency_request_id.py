"""tests/test_pedido_idempotency_request_id.py — verify pedido fulfill
idempotency records carry request_id.

Companion to tests/test_idempotency_request_id.py (which covers sales).
Same JSON shape: {pedido_id, sale_id, request_id}.
"""
from __future__ import annotations

import json
import uuid
from datetime import date


def _seed_pedido(session_factory):
    """Minimal pedido ready to fulfill."""
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
            name="Muffin", portion_label="1 muffin", recipe_id=recipe.id,
            sale_price_gs=10000, iva_rate="10",
        )
        s.add(product)
        s.flush()
        pedido = Pedido(
            status="pending", notes="test", payment_intent="efectivo",
            promised_date=date(2026, 9, 24), promised_time="14:00",
            channel="whatsapp",
        )
        s.add(pedido)
        s.flush()
        s.add(PedidoLine(
            pedido_id=pedido.id, product_id=product.id,
            qty=2.0, unit_price_gs=10000,
        ))
        s.flush()
        pid = pedido.id
        s.commit()
        return pid


def _post_fulfill(client, pedido_id: int, idempotency_key: str, request_id: str | None = None):
    headers = {}
    if request_id:
        headers["x-request-id"] = request_id
    return client.post(
        f"/pedidos/{pedido_id}/fulfill",
        data={"idempotency_key": idempotency_key},
        headers=headers,
        follow_redirects=False,
    )


def test_pedido_idempotency_value_contains_request_id(client, session_factory):
    """Pedido fulfill idempotency record has JSON value with request_id."""
    pedido_id = _seed_pedido(session_factory)
    idem = uuid.uuid4().hex

    r = _post_fulfill(client, pedido_id, idem, request_id="test-rid-pedido-abc")
    assert r.status_code in (303, 302)

    from app.rms.models import AppMeta

    with session_factory() as s:
        row = s.scalar(
            __import__("sqlalchemy").select(AppMeta).where(
                AppMeta.key == f"pedido_fulfill_idem:{idem}"
            )
        )

    assert row is not None
    payload = json.loads(row.value)
    assert payload["pedido_id"] == str(pedido_id)
    assert payload["request_id"] == "test-rid-pedido-abc"
    # sale_id is filled in by the post-fulfill UPDATE
    assert payload["sale_id"]  # non-empty after fulfill


def test_pedido_idempotency_generates_request_id_when_missing(client, session_factory):
    """No X-Request-Id header → generated request_id is stored."""
    pedido_id = _seed_pedido(session_factory)
    idem = uuid.uuid4().hex

    r = _post_fulfill(client, pedido_id, idem)  # no header
    assert r.status_code in (303, 302)

    import json

    from app.rms.models import AppMeta

    with session_factory() as s:
        row = s.scalar(
            __import__("sqlalchemy").select(AppMeta).where(
                AppMeta.key == f"pedido_fulfill_idem:{idem}"
            )
        )
    payload = json.loads(row.value)
    assert payload["request_id"], "request_id should not be empty"
