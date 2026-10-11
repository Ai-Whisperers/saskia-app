"""tests/test_fiado.py — Fase 2 fiado (2026-10-07).

Ledger firmado: cargo positivo / pago negativo. Idempotencia por
idem_key. Límite de crédito. Venta con payment_method='fiado' →
cargo automático (requiere customer). Void → reversa.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from tests.factories import make_product


def _mk_customer(s, name="Cliente Fiado"):
    from app.rms.models_legacy import Customer

    c = Customer(name=name)
    s.add(c)
    s.flush()
    return c


def _sess(session_factory):
    return sessionmaker(bind=session_factory.kw["bind"])()


# ---------- service layer ----------


def test_cargo_y_saldo(session_factory):
    from app.rms.fiado import registrar_cargo, saldo

    s = _sess(session_factory)
    try:
        c = _mk_customer(s)
        registrar_cargo(s, c.id, 50_000, note="venta 1")
        registrar_cargo(s, c.id, 20_000, note="venta 2")
        s.commit()
        assert saldo(s, c.id) == 70_000
    finally:
        s.close()


def test_pago_descuenta_y_es_negativo(session_factory):
    from app.rms.fiado import registrar_cargo, registrar_pago, saldo

    s = _sess(session_factory)
    try:
        c = _mk_customer(s)
        registrar_cargo(s, c.id, 50_000)
        tx = registrar_pago(s, c.id, 30_000)
        s.commit()
        assert tx.amount_gs == -30_000
        assert tx.kind == "pago"
        assert saldo(s, c.id) == 20_000
    finally:
        s.close()


def test_pago_idempotente_por_idem_key(session_factory):
    from app.rms.fiado import registrar_cargo, registrar_pago, saldo

    s = _sess(session_factory)
    try:
        c = _mk_customer(s)
        registrar_cargo(s, c.id, 50_000)
        first = registrar_pago(s, c.id, 30_000, idem_key="pos-1")
        dup = registrar_pago(s, c.id, 30_000, idem_key="pos-1")
        s.commit()
        assert dup is None
        assert saldo(s, c.id) == 20_000
        assert first is not None
    finally:
        s.close()


def test_limite_de_credito_bloca(session_factory):
    from app.rms.fiado import FiadoConflict, get_or_create_account, registrar_cargo, saldo

    s = _sess(session_factory)
    try:
        c = _mk_customer(s)
        acc = get_or_create_account(s, c.id)
        acc.limit_gs = 50_000
        s.flush()
        registrar_cargo(s, c.id, 10_000)
        registrar_cargo(s, c.id, 30_000)  # 40k <= 50k ok
        with pytest.raises(FiadoConflict):
            registrar_cargo(s, c.id, 20_000)  # 60k > 50k
        s.commit()
        assert saldo(s, c.id) == 40_000
    finally:
        s.close()


def test_cuenta_suspendida_bloca_cargo(session_factory):
    from app.rms.fiado import FiadoConflict, get_or_create_account, registrar_cargo

    s = _sess(session_factory)
    try:
        c = _mk_customer(s)
        acc = get_or_create_account(s, c.id)
        acc.active = False
        s.flush()
        with pytest.raises(FiadoConflict):
            registrar_cargo(s, c.id, 10_000)
    finally:
        s.close()


def test_montos_no_positivos_rechazados(session_factory):
    from app.rms.fiado import FiadoError, registrar_cargo, registrar_pago

    s = _sess(session_factory)
    try:
        c = _mk_customer(s)
        with pytest.raises(FiadoError):
            registrar_cargo(s, c.id, 0)
        with pytest.raises(FiadoError):
            registrar_pago(s, c.id, -5)
    finally:
        s.close()


def test_void_reversal_devuelve_saldo(session_factory):
    from app.rms.fiado import registrar_cargo, saldo, void_reversal

    s = _sess(session_factory)
    try:
        c = _mk_customer(s)
        tx = registrar_cargo(s, c.id, 45_000, note="venta a fiado")
        s.commit()
        assert saldo(s, c.id) == 45_000
        total = void_reversal(s, tx.sale_id)
        s.commit()
        assert total == 45_000
        assert saldo(s, c.id) == 0
    finally:
        s.close()


def test_aging_buckets_fifo(session_factory):
    from datetime import datetime, timedelta

    from app.rms.config import ASUNCION_TZ
    from app.rms.fiado import aging_report, registrar_cargo, registrar_pago

    s = _sess(session_factory)
    try:
        c = _mk_customer(s)
        t1 = registrar_cargo(s, c.id, 30_000)
        t2 = registrar_cargo(s, c.id, 30_000)
        # backdate: t1 a 45 días, t2 a 10 días
        t1.ts = datetime.now(ASUNCION_TZ) - timedelta(days=45)
        t2.ts = datetime.now(ASUNCION_TZ) - timedelta(days=10)
        registrar_pago(s, c.id, 30_000)  # cubre t1 (FIFO)
        s.commit()
        b = aging_report(s)
        # el pago (FIFO) cubre el cargo más viejo (45 d) → queda el de 10 d
        assert b["b0_30"] == 30_000
        assert b["b31_60"] == 0
        assert b["b61_mas"] == 0
    finally:
        s.close()


# ---------- HTTP layer ----------


def test_venta_fiado_crea_cargo_automatico(authed_client, session_factory):
    from app.rms.fiado import saldo

    s = _sess(session_factory)
    try:
        prod = make_product(s, name="Fiado Prod 1")
        c = _mk_customer(s, name="Fiado HTTP 1")
        s.commit()
        pid, prod_price, cid = prod.id, prod.sale_price_gs, c.id
    finally:
        s.close()
    r = authed_client.post(
        "/ventas/nueva",
        data={
            "product_id": str(pid),
            "qty": "2",
            "payment_method": "fiado",
            "customer_id": str(cid),
        },
        follow_redirects=False,
    )
    assert r.status_code in (303, 302), r.text[:400]
    s = _sess(session_factory)
    try:
        assert saldo(s, cid) == 2 * prod_price
    finally:
        s.close()


def test_venta_fiado_sin_cliente_rechazada(authed_client, session_factory):
    s = _sess(session_factory)
    try:
        prod = make_product(s, name="Fiado Prod 2")
        s.commit()
        pid = prod.id
    finally:
        s.close()
    r = authed_client.post(
        "/ventas/nueva",
        data={
            "product_id": str(pid),
            "qty": "1",
            "payment_method": "fiado",
        },
        follow_redirects=False,
    )
    assert r.status_code == 400, r.status_code
    # The handler returns a Spanish detail message; the machine-readable
    # error code is the JSON detail. Accept either the message OR the
    # "fiado" substring.
    assert "fiado" in r.text.lower() or "FIADO_REQUIERE_CLIENTE" in r.text


def test_pagos_cobranza_endpoint(client_with_caja, session_factory):
    s = _sess(session_factory)
    try:
        c = _mk_customer(s, name="Fiado HTTP 2")
        s.commit()
        cid = c.id
    finally:
        s.close()
    r1 = client_with_caja.post(
        f"/fiado/{cid}/cobrar",
        data={"amount_gs": "15000", "idempotency_key": "cobro-9"},
        follow_redirects=False,
    )
    assert r1.status_code == 303
    r2 = client_with_caja.post(
        f"/fiado/{cid}/cobrar",
        data={"amount_gs": "15000", "idempotency_key": "cobro-9"},
        follow_redirects=False,
    )
    assert r2.status_code == 303
    assert "fiado_duplicate" in r2.headers["location"]
    from app.rms.models_legacy import CreditTransaction

    s = _sess(session_factory)
    try:
        rows = (
            s.execute(select(CreditTransaction).where(CreditTransaction.idem_key == "cobro-9"))
            .scalars()
            .all()
        )
        assert len(rows) == 1
        assert rows[0].amount_gs == -15_000
    finally:
        s.close()


def test_venta_multi_fiado_crea_cargo(authed_client, session_factory):

    from app.rms.fiado import saldo

    s = _sess(session_factory)
    try:
        prod = make_product(s, name="Fiado Multi 1")
        c = _mk_customer(s, name="Fiado Multi Cust")
        s.commit()
        pid, price, cid = prod.id, prod.sale_price_gs, c.id
    finally:
        s.close()
    r = authed_client.post(
        "/ventas/nueva/multi",
        json={
            "items": [{"product_id": pid, "qty": 3}],
            "payment_method": "fiado",
            "customer_id": cid,
        },
        follow_redirects=False,
    )
    assert r.status_code in (303, 302), r.text[:400]
    s = _sess(session_factory)
    try:
        assert saldo(s, cid) == 3 * price
    finally:
        s.close()


# ─── Route-level tests (SASKIA audit: /cargar and /estado had no route tests) ─
# The existing tests cover service-layer logic and `/cobrar` via HTTP, but
# `/cargar` (manual charge) and `/estado` (suspend/resume) have no direct
# route tests. These add the missing coverage.


def test_fiado_cargar_endpoint_creates_ledger_row(authed_client, session_factory):
    """POST /fiado/{cid}/cargar → 303 + CreditTransaction(amount > 0)."""
    s = _sess(session_factory)
    try:
        c = _mk_customer(s, name="Fiado Cargar Test")
        s.commit()
        cid = c.id
    finally:
        s.close()

    r = authed_client.post(
        f"/fiado/{cid}/cargar",
        data={"amount_gs": "50000", "note": "ajuste manual test"},
        follow_redirects=False,
    )
    assert r.status_code == 303, r.text[:200]
    assert "fiado_charge" in r.headers["location"]

    from app.rms.models_legacy import CreditTransaction

    s = _sess(session_factory)
    try:
        txs = (
            s.execute(
                select(CreditTransaction).where(
                    CreditTransaction.account_id == _get_account_id(s, cid)
                )
            )
            .scalars()
            .all()
        )
        assert len(txs) == 1
        assert txs[0].amount_gs == 50_000
        assert txs[0].note == "ajuste manual test"
    finally:
        s.close()


def test_fiado_cargar_rejects_zero_amount(authed_client, session_factory):
    """POST /fiado/{cid}/cargar with amount=0 → 303 with error flash (no ledger row)."""
    s = _sess(session_factory)
    try:
        c = _mk_customer(s, name="Fiado Zero Cargar")
        s.commit()
        cid = c.id
    finally:
        s.close()

    r = authed_client.post(
        f"/fiado/{cid}/cargar",
        data={"amount_gs": "0", "note": ""},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert "fiado_error" in r.headers["location"]

    from app.rms.models_legacy import CreditTransaction

    s = _sess(session_factory)
    try:
        txs = (
            s.execute(
                select(CreditTransaction).where(
                    CreditTransaction.account_id == _get_account_id(s, cid)
                )
            )
            .scalars()
            .all()
        )
        assert len(txs) == 0  # No ledger row was created
    finally:
        s.close()


def test_fiado_estado_endpoint_toggles_active(authed_client, session_factory):
    """POST /fiado/{cid}/estado with active=1 → 303 + account.active=True."""
    from app.rms.fiado import get_or_create_account

    s = _sess(session_factory)
    try:
        c = _mk_customer(s, name="Fiado Estado Test")
        s.commit()
        cid = c.id
        # Ensure account starts as active (the default).
        acc = get_or_create_account(s, cid)
        s.commit()
        assert acc.active is True
    finally:
        s.close()

    # Suspend.
    r = authed_client.post(
        f"/fiado/{cid}/estado",
        data={"active": "0"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert "fiado_status" in r.headers["location"]

    s = _sess(session_factory)
    try:
        from app.rms.fiado import get_or_create_account

        acc = get_or_create_account(s, cid)
        assert acc.active is False
    finally:
        s.close()

    # Re-activate.
    r = authed_client.post(
        f"/fiado/{cid}/estado",
        data={"active": "1"},
        follow_redirects=False,
    )
    assert r.status_code == 303

    s = _sess(session_factory)
    try:
        from app.rms.fiado import get_or_create_account

        acc = get_or_create_account(s, cid)
        assert acc.active is True
    finally:
        s.close()


def test_fiado_cargar_writes_audit_row(authed_client, session_factory):
    """POST /fiado/{cid}/cargar → 1 audit row tagged fiado_cargo."""
    from app.rms.models import AuditLog

    s = _sess(session_factory)
    try:
        c = _mk_customer(s, name="Fiado Audit Test")
        s.commit()
        cid = c.id
    finally:
        s.close()

    r = authed_client.post(
        f"/fiado/{cid}/cargar",
        data={"amount_gs": "10000", "note": "audit check"},
        follow_redirects=False,
    )
    assert r.status_code == 303

    s = _sess(session_factory)
    try:
        cargo_audits = (
            s.query(AuditLog)
            .filter(AuditLog.action == "fiado_cargo", AuditLog.target_id == cid)
            .all()
        )
        assert len(cargo_audits) == 1, f"Expected 1 fiado_cargo audit, got {len(cargo_audits)}"
        import json
        detail = cargo_audits[0].detail if cargo_audits[0].detail else {}
        assert detail.get("amount_gs") == 10_000
    finally:
        s.close()


def _get_account_id(s, customer_id: int) -> int:
    """Helper: return the CreditAccount.id for a customer."""
    from app.rms.fiado import get_or_create_account

    return get_or_create_account(s, customer_id).id
