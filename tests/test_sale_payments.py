"""tests/test_sale_payments.py — WP-1.2 pagos mixtos (2026-10-07).

sale_payment ledger: uniform one-row-per-method. Mixed carts split the
total across methods; the sum must equal the cart total; void removes
the payment rows (soft-void keeps the Sale row for audit).
"""

from __future__ import annotations

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.orm import sessionmaker

from tests.factories import make_ingredient, make_product, make_recipe


@pytest.fixture()
def _seed(session_factory):
    s = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        make_ingredient(s, unit="kg", stock_qty=25.0, min_stock_qty=2.0)
        rec = make_recipe(s, yield_qty=12, yield_unit="und")
        p1 = make_product(s, name="Pago Mixto A", sale_price_gs=10000, recipe=rec)
        p2 = make_product(s, name="Pago Mixto B", sale_price_gs=25000, recipe=rec)
        s.commit()
        return {"a": p1.id, "b": p2.id}
    finally:
        s.close()


def _payments(session_factory):
    s2 = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        from app.rms.models_legacy import SalePayment

        return s2.execute(select(SalePayment).order_by(SalePayment.id)).scalars().all()
    finally:
        s2.close()


def test_migration_105_creates_table(app_engine):
    insp = inspect(app_engine)
    assert "sale_payment" in insp.get_table_names()


def test_single_method_writes_one_uniform_row(authed_client, session_factory, _seed):
    r = authed_client.post(
        "/ventas/nueva/multi",
        json={"items": [{"product_id": _seed["a"], "qty": 2}], "payment_method": "qr"},
        follow_redirects=False,
    )
    assert r.status_code == 303, r.text[:300]
    rows = _payments(session_factory)
    assert len(rows) == 1
    assert rows[0].method == "qr"
    assert rows[0].amount_gs == 20000


def test_mixed_payments_split_and_sum_ok(client_with_caja, session_factory, _seed):
    authed_client = client_with_caja  # SASKIA-MIG-2: open caja required for cash sales
    # total = 10000 + 25000 = 35000 → 20000 efectivo + 15000 transferencia
    r = authed_client.post(
        "/ventas/nueva/multi",
        json={
            "items": [
                {"product_id": _seed["a"], "qty": 1},
                {"product_id": _seed["b"], "qty": 1},
            ],
            "payment_method": "efectivo",
            "payments": [
                {"method": "efectivo", "amount_gs": 20000},
                {"method": "transferencia", "amount_gs": 15000},
            ],
        },
        follow_redirects=False,
    )
    assert r.status_code == 303, r.text[:300]
    rows = _payments(session_factory)
    # Split is attributed per sale row (each row's payments sum to its
    # line total); aggregate per method must equal what the operator
    # entered.
    from collections import Counter

    per_method = Counter()
    for x in rows:
        per_method[x.method] += x.amount_gs
    assert dict(per_method) == {"efectivo": 20000, "transferencia": 15000}
    assert sum(x.amount_gs for x in rows) == 35000


def test_mixed_payments_wrong_sum_rejected(client_with_caja, session_factory, _seed):
    authed_client = client_with_caja  # SASKIA-MIG-2: open caja required for cash sales
    r = authed_client.post(
        "/ventas/nueva/multi",
        json={
            "items": [{"product_id": _seed["a"], "qty": 1}],
            "payments": [
                {"method": "efectivo", "amount_gs": 5000},
                {"method": "qr", "amount_gs": 4000},
            ],
        },
        follow_redirects=False,
    )
    assert r.status_code == 400
    assert "suma" in r.text.lower() or "total" in r.text.lower()


def test_mixed_payments_invalid_method_rejected(client_with_caja, session_factory, _seed):
    authed_client = client_with_caja  # SASKIA-MIG-2: open caja required for cash sales
    r = authed_client.post(
        "/ventas/nueva/multi",
        json={
            "items": [{"product_id": _seed["a"], "qty": 1}],
            "payments": [
                {"method": "cripto", "amount_gs": 10000},
            ],
        },
        follow_redirects=False,
    )
    assert r.status_code == 400


def test_void_removes_payment_rows(authed_client, session_factory, _seed):
    r = authed_client.post(
        "/ventas/nueva/multi",
        json={"items": [{"product_id": _seed["a"], "qty": 1}], "payment_method": "qr"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert len(_payments(session_factory)) == 1

    s2 = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        from app.rms.models_legacy import Sale

        sale_id = s2.execute(select(Sale).order_by(Sale.id.desc())).scalars().first().id
    finally:
        s2.close()

    # void_sale directly (service) — the router path needs CSRF+form only
    s3 = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        from app.rms.costing import void_sale

        void_sale(s3, sale_id, reason="test")
    finally:
        s3.close()
    assert _payments(session_factory) == []
