"""tests/test_pedido_prefill.py — phase 3 smart autofill tests.

Verify the customer-prefill service computes the right defaults:

- All contact fields populated from customer record
- Zone + address + delivery window inferred from history
- Promised date = today + average lead time
- Payment intent + channel from history (most common)
- Lines cloned from a source pedido when ?from=N is passed
- Empty defaults returned for unknown customer (no crash)
"""

from __future__ import annotations

from datetime import date

from app.services.customer_prefill import (
    CustomerPrefill,
    compute_customer_defaults,
)


def _make_full_customer(session_factory, qseed):
    """Set up Kyrian via the qseed fixture and return his id."""
    qseed("with_kyrian_full")
    from app.rms.models import Customer
    from app.seed.kyrian import KYRIAN_PHONE
    with session_factory() as s:
        c = s.query(Customer).filter_by(phone=KYRIAN_PHONE).one()
        return c.id


def test_prefill_returns_full_profile(qseed, session_factory):
    cid = _make_full_customer(session_factory, qseed)
    with session_factory() as s:
        out = compute_customer_defaults(s, cid, today=date(2026, 10, 1))

    # Contact fields
    assert out.phone == "0982515138"
    assert out.invoice_ruc == "5991039"
    assert out.invoice_name == "kyrian weiss"

    # Zone + address
    assert out.delivery_zone_id is not None
    assert "mariscal" in (out.address_text or "").lower()
    assert out.address_label == "casa"
    assert out.save_address is False  # Kyrian has 2 addresses, no auto-save

    # When
    assert out.promised_date is not None
    assert out.delivery_window_start is not None
    assert out.delivery_window_end is not None
    assert out.promised_time is not None

    # How
    assert out.channel in ("whatsapp", "mostrador", "pedidosya", "phone", "other")
    assert out.payment_intent is not None

    # Dietary banner (we set sin frutos secos)
    assert "frutos secos" in (out.dietary_banner or "")


def test_prefill_clones_most_recent_pedido(qseed, session_factory):
    """Without ?from=, the most recent pedido's lines are suggested."""
    cid = _make_full_customer(session_factory, qseed)
    with session_factory() as s:
        out = compute_customer_defaults(s, cid, today=date(2026, 10, 1))

    # Kyrian has 6 pedidos, the most recent is -2 days from today
    assert len(out.clone_lines) > 0
    assert all("product_id" in ln and "qty" in ln for ln in out.clone_lines)
    assert out.last_pedido_id is not None


def test_prefill_from_specific_pedido(qseed, session_factory):
    """When ?from=<id> is passed, those specific lines are cloned."""
    cid = _make_full_customer(session_factory, qseed)
    with session_factory() as s:
        from app.rms.models import Pedido
        # Pick the pedido from 25 days ago (the oldest pedido)
        target = s.execute(
            __import__("sqlalchemy").select(Pedido)
            .where(Pedido.customer_id == cid)
            .order_by(Pedido.promised_date.asc())
            .limit(1)
        ).scalar_one()
        target_id = target.id
        target_lines = len(target.lines)

        out = compute_customer_defaults(s, cid, from_pedido_id=target_id, today=date(2026, 10, 1))

    assert out.last_pedido_id == target_id
    assert len(out.clone_lines) == target_lines


def test_prefill_handles_unknown_customer(session_factory):
    """No crash when customer_id doesn't exist — returns empty defaults."""
    with session_factory() as s:
        out = compute_customer_defaults(s, 999999999, today=date(2026, 10, 1))
    assert isinstance(out, CustomerPrefill)
    assert out.phone is None
    assert out.invoice_ruc is None


def test_prefill_empty_history_returns_sensible_defaults(qseed, session_factory):
    """A customer with no pedidos gets tomorrow's date + empty channels."""
    from app.rms.models import Customer
    with session_factory() as s:
        c = Customer(name="Cliente Nuevo", phone="0991112222")
        s.add(c)
        s.commit()
        cid = c.id

    with session_factory() as s:
        out = compute_customer_defaults(s, cid, today=date(2026, 10, 1))

    assert out.phone == "0991112222"
    # No history → tomorrow
    assert out.promised_date == "2026-10-02"
    assert out.channel is None  # no preference + no history
    assert out.payment_intent is None


def test_prefill_to_dict_serializable(qseed, session_factory):
    """CustomerPrefill.to_dict() must be JSON-safe for the JS handoff."""
    import json
    cid = _make_full_customer(session_factory, qseed)
    with session_factory() as s:
        out = compute_customer_defaults(s, cid, today=date(2026, 10, 1))
        d = out.to_dict()
        # Must serialize without TypeError
        json.dumps(d)
    assert "phone" in d
    assert "clone_lines" in d
    assert isinstance(d["clone_lines"], list)


def test_prefill_endpoint_returns_json(client, monkeypatch, qseed, session_factory):
    """GET /pedidos/api/customer-defaults/<id> returns the JSON for JS."""
    cid = _make_full_customer(session_factory, qseed)

    r = client.get(f"/pedidos/api/customer-defaults/{cid}")
    assert r.status_code == 200
    body = r.json()
    assert body["phone"] == "0982515138"
    assert body["invoice_ruc"] == "5991039"
    assert isinstance(body["clone_lines"], list)


def test_prefill_endpoint_with_from_param(client, monkeypatch, qseed, session_factory):
    """GET /pedidos/api/customer-defaults/<id>?from=<pedido_id> clones that pedido."""
    cid = _make_full_customer(session_factory, qseed)
    from app.rms.models import Pedido
    with session_factory() as s:
        oldest = s.execute(
            __import__("sqlalchemy").select(Pedido)
            .where(Pedido.customer_id == cid)
            .order_by(Pedido.promised_date.asc())
            .limit(1)
        ).scalar_one()
        target_id = oldest.id

    r = client.get(f"/pedidos/api/customer-defaults/{cid}?from={target_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["last_pedido_id"] == target_id
    assert len(body["clone_lines"]) > 0
