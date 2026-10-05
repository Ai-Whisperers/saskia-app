"""tests/test_suscripcion_dispatcher.py — phase 13.

Verify the suscripcion->pedido bridge:
- generate_weekly_pedidos creates one Pedido per active Suscripcion
- Idempotency: running twice in the same week is a no-op
- Skips paused, cancelled, past-end-date, non-weekly cadences
- Records PedidoEvent 'created' rows with source='suscripcion_dispatch'
- HTTP POST /suscripciones/dispatch triggers generation
- The undo_for_pedido helper removes the dedupe row
"""

from __future__ import annotations

from datetime import date

from app.rms.models import (
    Customer,
    Pedido,
    PedidoEvent,
    Suscripcion,
)

# ---------- helpers ----------


def _make_customer(s, name="Sub Test", phone="0997000001"):
    c = Customer(name=name, phone=phone)
    s.add(c)
    s.flush()
    return c


def _make_sub(s, customer_id, **kw):
    defaults = dict(
        customer_id=customer_id,
        product_summary="1 kg chipa",
        cadence="semanal",
        preferred_day_of_week=4,  # Thursday
        preferred_time="09:00",
        start_date=date(2026, 1, 1),
        price_gs=45000,
        status="activa",
        notes="",
    )
    defaults.update(kw)
    sub = Suscripcion(**defaults)
    s.add(sub)
    s.flush()
    return sub


# ---------- 1. Service unit tests ----------


def test_dispatcher_generates_for_one_active_sub(session_factory):
    """One active suscripcion → one Pedido created."""
    with session_factory() as s:
        c = _make_customer(s)
        sub = _make_sub(s, c.id)

        from app.services.suscripcion_dispatcher import generate_weekly_pedidos

        result = generate_weekly_pedidos(s)

        assert result.total == 1
        assert result.generated[0].suscripcion_id == sub.id
        assert result.generated[0].customer_id == c.id

        # Verify the pedido row exists with the right shape
        pedido_id = result.generated[0].pedido_id
        pedido = s.get(Pedido, pedido_id)
        assert pedido.status == "pending"
        assert pedido.channel == "whatsapp"
        assert pedido.customer_id == c.id
        assert "[Auto-generado desde suscripción" in (pedido.notes or "")

        # PedidoEvent row recorded
        events = s.query(PedidoEvent).filter_by(pedido_id=pedido_id).all()
        assert len(events) == 1
        assert events[0].event_type == "created"
        assert events[0].payload_json["source"] == "suscripcion_dispatch"
        assert events[0].payload_json["suscripcion_id"] == sub.id


def test_dispatcher_is_idempotent_within_week(session_factory):
    """Re-running in the same week is a no-op (uses AppMeta dedupe)."""
    with session_factory() as s:
        c = _make_customer(s, "Idempotent Sub")
        sub = _make_sub(s, c.id)

        from app.services.suscripcion_dispatcher import generate_weekly_pedidos

        r1 = generate_weekly_pedidos(s)
        assert r1.total == 1

        r2 = generate_weekly_pedidos(s)
        assert r2.total == 0
        assert sub.id in r2.skipped_already_done


def test_dispatcher_skips_paused(session_factory):
    """A paused suscripcion doesn't generate."""
    with session_factory() as s:
        c = _make_customer(s, "Paused Sub")
        _make_sub(s, c.id, status="pausada")

        from app.services.suscripcion_dispatcher import generate_weekly_pedidos

        result = generate_weekly_pedidos(s)
        assert result.total == 0
        # Only 'pausada' so it shouldn't even be queried as 'activa'.
        assert len(result.generated) == 0


def test_dispatcher_skips_past_end_date(session_factory):
    """Suscripcion whose end_date is in the past is skipped."""
    with session_factory() as s:
        c = _make_customer(s, "Past Sub")
        _make_sub(s, c.id, end_date=date(2020, 1, 1))

        from app.services.suscripcion_dispatcher import generate_weekly_pedidos

        result = generate_weekly_pedidos(s)
        assert result.total == 0
        assert result.skipped_past_end_date


def test_dispatcher_skips_non_weekly_for_now(session_factory):
    """Quincenal + mensual are deferred (Phase 13 scope is weekly)."""
    with session_factory() as s:
        c1 = _make_customer(s, "Quincenal Sub", "0997000011")
        c2 = _make_customer(s, "Mensual Sub", "0997000012")
        _make_sub(s, c1.id, cadence="quincenal")
        _make_sub(s, c2.id, cadence="mensual")

        from app.services.suscripcion_dispatcher import generate_weekly_pedidos

        result = generate_weekly_pedidos(s)
        assert result.total == 0
        # 2 skipped
        assert len(result.skipped_no_dow_match) == 2


def test_dispatcher_undo_for_pedido(session_factory):
    """undo_for_pedido removes the dedupe row so re-run regenerates."""
    with session_factory() as s:
        c = _make_customer(s, "Undo Sub")
        _make_sub(s, c.id)

        from app.services.suscripcion_dispatcher import (
            generate_weekly_pedidos,
            undo_for_pedido,
        )

        r1 = generate_weekly_pedidos(s)
        pedido_id = r1.generated[0].pedido_id

        # Re-run → no-op
        r2 = generate_weekly_pedidos(s)
        assert r2.total == 0

        # Undo
        ok = undo_for_pedido(s, pedido_id)
        assert ok

        # Now re-run → generates again
        r3 = generate_weekly_pedidos(s)
        assert r3.total == 1


# ---------- 2. HTTP endpoint ----------


def test_http_dispatch_creates_pedidos(client, session_factory):
    """POST /suscripciones/dispatch generates pending pedidos."""
    with session_factory() as s:
        c = Customer(name="HTTP Sub", phone="0997000002")
        s.add(c)
        s.flush()
        cid = c.id
        _make_sub(s, cid)
        s.commit()  # ← flush only persists within this session

    r = client.post("/suscripciones/dispatch", follow_redirects=False)
    assert r.status_code in (303, 302)
    location = r.headers.get("location", "")
    assert "dispatched=1" in location, f"expected dispatched=1, got: {location}"

    with session_factory() as s:
        # One new pending pedido with [Auto-generado
        n = (
            s.query(Pedido)
            .filter(
                Pedido.notes.like("[Auto-generado desde suscripción%"),
                Pedido.customer_id == cid,
            )
            .count()
        )
        assert n == 1


def test_http_dispatch_idempotent(client, session_factory):
    """POST twice → still 1 pedido, second shows in skipped_already_done."""
    with session_factory() as s:
        c = Customer(name="HTTP Idempotent Sub", phone="0997000003")
        s.add(c)
        s.flush()
        _make_sub(s, c.id)
        s.commit()

    client.post("/suscripciones/dispatch", follow_redirects=False)
    r2 = client.post("/suscripciones/dispatch", follow_redirects=False)
    assert "dispatched=0" in r2.headers.get("location", "")

    with session_factory() as s:
        n = s.query(Pedido).filter(Pedido.notes.like("[Auto-generado desde suscripción%")).count()
        assert n == 1
