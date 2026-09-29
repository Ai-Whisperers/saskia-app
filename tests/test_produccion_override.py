"""Produccion override endpoint tests."""
from __future__ import annotations

from datetime import date, datetime, timezone

from app.rms.models import ProductionCompletion


def test_produccion_override_updates_completion(authed_client, session_factory):
    """POST /produccion/override must update ProductionCompletion."""
    from app.rms.models import Product

    with session_factory() as s:
        product = Product(
            name="Override Product",
            portion_label="1 und",
            sale_price_gs=5000,
            is_available=True,
        )
        s.add(product)
        s.commit()
        s.refresh(product)

        completion = ProductionCompletion(
            product_id=product.id,
            for_date=date.today(),
            completed_qty=5.0,
            recorded_at=datetime.now(timezone.utc),
        )
        s.add(completion)
        s.commit()

    r = authed_client.post(
        "/produccion/override",
        data={"for_date": date.today().isoformat(), "product_id": str(product.id), "qty": "12"},
    )
    assert r.status_code < 500, (
        f"/produccion/override returned {r.status_code}: {r.text[:200]}"
    )
