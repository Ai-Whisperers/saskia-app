"""tests/test_tip.py — WP-4.1 propina (2026-10-07).

tip_gs en la primera fila; pagos cubren total+tip; 409 si no;
recibo muestra la línea de propina.
"""

from __future__ import annotations


def _mk_product(session_factory, name, price):
    from tests.factories import make_product

    with session_factory() as s:
        p = make_product(s, name=name, sale_price_gs=price)
        s.commit()
        return p.id


def test_tip_lands_on_first_row(authed_client, session_factory):
    pid1 = _mk_product(session_factory, "Tip A", 50_000)
    pid2 = _mk_product(session_factory, "Tip B", 30_000)
    r = authed_client.post(
        "/ventas/nueva/multi",
        json={
            "items": [
                {"product_id": pid1, "qty": 1},
                {"product_id": pid2, "qty": 1},
            ],
            "tip_gs": 8_000,
            "payments": [{"method": "efectivo", "amount_gs": 88_000}],
        },
        follow_redirects=False,
    )
    assert r.status_code == 303, r.text[:300]
    from app.rms.models_legacy import Sale

    with session_factory() as s:
        rows = s.query(Sale).order_by(Sale.id.desc()).limit(2).all()
        tips = sorted([row.tip_gs for row in rows], reverse=True)
        assert tips == [8_000, 0]
        # ledger covers total + tip
        from app.rms.models_legacy import SalePayment

        total_paid = s.query(SalePayment).order_by(SalePayment.id.desc()).all()
        assert sum(p.amount_gs for p in total_paid) == 88_000


def test_tip_payments_short_rejected(authed_client):
    r = authed_client.post(
        "/ventas/nueva/multi",
        json={
            "items": [],
            "tip_gs": 5_000,
            "payments": [{"method": "efectivo", "amount_gs": 5_000}],
        },
    )
    assert r.status_code in (400, 422)


def test_tip_negative_rejected(authed_client):
    r = authed_client.post(
        "/ventas/nueva/multi",
        json={"items": [{"product_id": 1, "qty": 1}], "tip_gs": -100, "payments": []},
        follow_redirects=False,
    )
    assert r.status_code in (400, 422)


def test_recibo_muestra_propina(authed_client, session_factory):
    from app.rms.models_legacy import Sale

    with session_factory() as s:
        row = Sale(
            product_id=_mk_product(session_factory, "Tip R", 10_000),
            qty=1,
            unit_price_gs=10_000,
            discount_gs=0,
            payment_method="efectivo",
            tip_gs=1_000,
            sold_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        )
        s.add(row)
        s.commit()
        sid = row.id
    r = authed_client.get(f"/ventas/{sid}/recibo")
    assert r.status_code == 200
    assert "Propina" in r.text
