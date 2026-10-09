"""tests/test_idempotency_request_id.py — verify idempotency records carry request_id.

Phase 1B ticket #10: per the audit, duplicate-POST forensics need to
correlate the two requests. We already store the sale_id/pedido_id in
the idempotency record's value column; adding request_id lets ops grep
"show me all the requests that hit sale_idem:abc123" via the access log.

Implementation: store JSON {"sale_id": "1", "request_id": "..."} in the
AppMeta.value column (Text → JSON string). Backwards-compat: legacy
plain-string values are still readable.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone


def _seed_minimal_sale(session_factory):
    from app.rms.models import Ingredient, Product, Recipe, RecipeLine, Sale

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
        s.add(
            Sale(
                product_id=product.id,
                qty=1.0,
                unit_price_gs=10000,
                sold_at=datetime.now(timezone.utc),
                invoice_type="boleta_resimple",
            )
        )
        s.commit()


def test_idempotency_value_stores_request_id_in_json(client, session_factory):
    """The idempotency record's value column contains JSON with sale_id + request_id."""
    _seed_minimal_sale(session_factory)
    idem = uuid.uuid4().hex

    r = client.post(
        "/ventas/nueva",
        data={
            "product_id": "1",
            "qty": "1.0",
            "payment_method": "efectivo",
            "discount_gs": "0",
            "channel": "mostrador",
            "idempotency_key": idem,
        },
        headers={"x-request-id": "test-rid-12345"},
        follow_redirects=False,
    )
    assert r.status_code in (303, 302)

    # Inspect the stored idempotency record
    from app.rms.models import AppMeta

    with session_factory() as s:
        row = s.scalar(
            __import__("sqlalchemy").select(AppMeta).where(AppMeta.key == f"sale_idem:{idem}")
        )

    assert row is not None
    # value should be JSON-parseable with sale_id + request_id
    payload = json.loads(row.value)
    assert "sale_id" in payload
    assert payload["request_id"] == "test-rid-12345"


def test_idempotency_value_works_without_request_id_header(client, session_factory):
    """Without X-Request-Id header, request_id is generated and stored."""
    _seed_minimal_sale(session_factory)
    idem = uuid.uuid4().hex

    r = client.post(
        "/ventas/nueva",
        data={
            "product_id": "1",
            "qty": "1.0",
            "payment_method": "efectivo",
            "discount_gs": "0",
            "channel": "mostrador",
            "idempotency_key": idem,
        },
        follow_redirects=False,
    )
    assert r.status_code in (303, 302)

    import json

    from app.rms.models import AppMeta

    with session_factory() as s:
        row = s.scalar(
            __import__("sqlalchemy").select(AppMeta).where(AppMeta.key == f"sale_idem:{idem}")
        )
    payload = json.loads(row.value)
    # Generated request_id per app/rms/observability.py:33 is uuid4().hex[:12]
    # (12-char prefix). Just assert non-empty and looks like a hex string.
    assert payload["request_id"], "request_id should not be empty"
    assert all(c in "0123456789abcdef" for c in payload["request_id"]), (
        f"request_id should be hex, got {payload['request_id']!r}"
    )


def test_existing_idempotency_record_reads_sale_id_back(client, session_factory):
    """Operators looking at the value column can still extract sale_id."""
    _seed_minimal_sale(session_factory)
    idem = uuid.uuid4().hex

    r = client.post(
        "/ventas/nueva",
        data={
            "product_id": "1",
            "qty": "1.0",
            "payment_method": "efectivo",
            "discount_gs": "0",
            "channel": "mostrador",
            "idempotency_key": idem,
        },
        follow_redirects=False,
    )
    assert r.status_code in (303, 302)

    import json

    from app.rms.models import AppMeta

    with session_factory() as s:
        row = s.scalar(
            __import__("sqlalchemy").select(AppMeta).where(AppMeta.key == f"sale_idem:{idem}")
        )
    payload = json.loads(row.value)
    sale_id = payload["sale_id"]
    assert int(sale_id) > 0
    # Same sale_id is what existing tests already verify
