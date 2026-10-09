"""tests/test_sold_by_weight.py — WP-1.1 venta por peso (2026-10-07).

product.sold_by_weight (migration 104): fractional-kg sales for weight
products on the multi-sale POS route, integer rule intact for discrete
goods. Frontend renders a kg input; backend stays the source of truth.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import inspect
from sqlalchemy.orm import sessionmaker

from tests.factories import make_ingredient, make_product, make_recipe


@pytest.fixture()
def _weight_seed(session_factory):
    """One weight product (con receta, for the full costing flow) + one
    discrete product, both committed."""
    s = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        make_ingredient(s, unit="kg", stock_qty=25.0, min_stock_qty=2.0)
        rec = make_recipe(s, yield_qty=12, yield_unit="und")
        w = make_product(
            s,
            name="Chipa kilo",
            sale_price_gs=18000,
            recipe=rec,
            sold_by_weight=True,
        )
        d = make_product(s, name="Chipa unidad", sale_price_gs=1500, recipe=rec)
        s.commit()
        return {"weight_id": w.id, "discrete_id": d.id}
    finally:
        s.close()


def test_migration_104_adds_column(app_engine):
    insp = inspect(app_engine)
    cols = {c["name"] for c in insp.get_columns("product")}
    assert "sold_by_weight" in cols


def test_schema_version_at_least_104(app_engine):
    from app.rms.db import schema_version

    with app_engine.connect() as conn:
        assert schema_version(conn) >= 104


def test_default_is_false(session_factory):
    s = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        p = make_product(s, name="Pan lactal")
        s.commit()
        assert p.sold_by_weight is False
    finally:
        s.close()


def test_multi_accepts_fractional_qty_for_weight_product(
    authed_client, session_factory, _weight_seed
):
    r = authed_client.post(
        "/ventas/nueva/multi",
        json={"items": [{"product_id": _weight_seed["weight_id"], "qty": 0.5}]},
        follow_redirects=False,
    )
    assert r.status_code == 303, r.text[:300]
    s2 = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        from app.rms.models_legacy import Sale

        sale = s2.query(Sale).order_by(Sale.id.desc()).first()
        assert sale is not None and float(sale.qty) == 0.5
        # line total = 0.5 × 18.000 = 9.000 (Sale keeps unit snapshot; total derived)
        assert sale.unit_price_gs * sale.qty == 9000
    finally:
        s2.close()


def test_multi_rejects_fractional_qty_for_discrete_product(
    authed_client, session_factory, _weight_seed
):
    r = authed_client.post(
        "/ventas/nueva/multi",
        json={"items": [{"product_id": _weight_seed["discrete_id"], "qty": 1.5}]},
        follow_redirects=False,
    )
    assert r.status_code == 400
    assert "entero" in r.text


def test_mixed_cart_fractional_weight_plus_integer_discrete_ok(
    authed_client, session_factory, _weight_seed
):
    r = authed_client.post(
        "/ventas/nueva/multi",
        json={
            "items": [
                {"product_id": _weight_seed["weight_id"], "qty": 1.25},
                {"product_id": _weight_seed["discrete_id"], "qty": 2},
            ]
        },
        follow_redirects=False,
    )
    assert r.status_code == 303, r.text[:300]


def test_discrete_still_accepts_integer_qty(authed_client, session_factory, _weight_seed):
    r = authed_client.post(
        "/ventas/nueva/multi",
        json={"items": [{"product_id": _weight_seed["discrete_id"], "qty": 2}]},
        follow_redirects=False,
    )
    assert r.status_code == 303, r.text[:300]


def test_weight_qty_upper_bound_still_enforced(authed_client, session_factory, _weight_seed):
    from app.rms.schemas import MAX_QTY

    r = authed_client.post(
        "/ventas/nueva/multi",
        json={"items": [{"product_id": _weight_seed["weight_id"], "qty": MAX_QTY + 0.5}]},
        follow_redirects=False,
    )
    assert r.status_code == 400


def test_apply_sale_persists_fractional_qty(session_factory, _weight_seed):
    """Service layer already Float-safe: apply_sale stores 0.25 directly."""
    from app.rms.costing import apply_sale
    from app.rms.models_legacy import Sale

    s = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        apply_sale(s, _weight_seed["weight_id"], 0.25, datetime.now(timezone.utc))
        s.commit()
    finally:
        s.close()
    s2 = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        sale = s2.query(Sale).order_by(Sale.id.desc()).first()
        assert float(sale.qty) == 0.25
    finally:
        s2.close()


def test_products_api_search_includes_sold_by_weight(authed_client, session_factory, _weight_seed):
    r = authed_client.get("/productos/api/search?q=Chipa kilo")
    assert r.status_code == 200
    data = r.json()
    hit = next(x for x in data["results"] if x["id"] == _weight_seed["weight_id"])
    assert hit["sold_by_weight"] is True
