"""tests/test_qseed_kyrian_full.py — phase 1 seed library tests.

Verify that:
- The with_kyrian_full scenario produces a coherent dataset.
- Counts match the spec: 6 pedidos, 5 fulfilled, 18 lines, 17 sales
  (5 pedidos × N lines each), loyalty ledger balance matches the
  customer.loyalty_points cached value.
- Re-running the seed is idempotent (counts don't double).
- The customer has the full profile (zone, dietary, RUC, etc.).
"""

from __future__ import annotations

from sqlalchemy import select

from app.rms.models import (
    Customer,
    Pedido,
    PedidoLine,
)
from app.seed.kyrian import (
    KYRIAN_CEDULA,
    KYRIAN_EMAIL,
    KYRIAN_NAME,
    KYRIAN_PHONE,
    seed_kyrian,
)


def test_with_kyrian_full_creates_expected_dataset(qseed, session_factory):
    out = qseed("with_kyrian_full")
    bundle = out["kyrian"]

    # 1 customer
    assert bundle.customer.name == KYRIAN_NAME
    assert bundle.customer.phone == KYRIAN_PHONE
    assert bundle.customer.email == KYRIAN_EMAIL
    assert bundle.customer.cedula == KYRIAN_CEDULA

    # 2 addresses
    assert len(bundle.addresses) == 2
    labels = sorted(a.label for a in bundle.addresses)
    assert labels == ["casa", "oficina"]

    # 1 subscription
    assert bundle.suscripcion is not None
    assert bundle.suscripcion.status == "activa"
    assert bundle.suscripcion.cadence == "semanal"
    assert bundle.suscripcion.preferred_day_of_week == 6

    # 6 pedidos — 5 fulfilled + 1 cancelled
    assert len(bundle.pedidos) == 6
    fulfilled = [p for p in bundle.pedidos if p.status == "fulfilled"]
    cancelled = [p for p in bundle.pedidos if p.status == "cancelled"]
    assert len(fulfilled) == 5
    assert len(cancelled) == 1

    # Sales match the lines on fulfilled pedidos. The session is closed
    # by the time we run this assertion, so we count lines via SQL
    # rather than relying on the lazy-loaded relationship.
    from sqlalchemy import func, select
    with session_factory() as s:
        line_count = s.execute(
            select(func.count()).select_from(PedidoLine)
            .where(PedidoLine.pedido_id.in_(p.id for p in fulfilled))
        ).scalar_one()
    assert len(bundle.sales) == line_count
    assert len(bundle.sales) > 0

    # Loyalty ledger: at least one earn per fulfilled sale + bonus + redeem
    earn_entries = [lt for lt in bundle.loyalty_ledger if lt.reason == "earn_sale"]
    assert len(earn_entries) == len(bundle.sales)
    assert any(lt.reason == "redeem" for lt in bundle.loyalty_ledger)
    assert any(lt.reason == "manual_adjust" for lt in bundle.loyalty_ledger)


def test_kyrian_full_profile_is_complete(qseed):
    bundle = qseed("with_kyrian_full")["kyrian"]
    c = bundle.customer

    # The whole point of the seed: every profile field populated
    assert c.preferred_zone_id is not None, "preferred_zone_id should be set"
    assert c.preferred_channel == "whatsapp"
    assert c.invoice_ruc == KYRIAN_CEDULA
    assert c.invoice_name == KYRIAN_NAME
    assert c.dietary_restrictions, "dietary_restrictions should be set"
    assert c.dietary_preferences, "dietary_preferences should be set"
    assert c.birthday == "06-15"
    assert c.marketing_consent is True
    assert "alergia" in (c.notes or "").lower()


def test_kyrian_loyalty_balance_matches_ledger(qseed):
    bundle = qseed("with_kyrian_full")["kyrian"]

    # The cached customer.loyalty_points MUST equal sum of ledger deltas
    # (this is the invariant flagged in the analysis doc).
    ledger_sum = sum(lt.delta for lt in bundle.loyalty_ledger)
    assert bundle.customer.loyalty_points == ledger_sum

    # Earns must be positive, redeem/void reversal must be negative
    earns = [lt.delta for lt in bundle.loyalty_ledger if lt.reason == "earn_sale"]
    redeems = [lt.delta for lt in bundle.loyalty_ledger if lt.reason == "redeem"]
    assert all(d > 0 for d in earns)
    assert all(d < 0 for d in redeems)


def test_kyrian_addresses_have_zone(qseed):
    bundle = qseed("with_kyrian_full")["kyrian"]
    # Both addresses should carry the customer's preferred zone
    for addr in bundle.addresses:
        if bundle.customer.preferred_zone_id:
            assert addr.zone_id == bundle.customer.preferred_zone_id


def test_kyrian_pedidos_have_status_mix(qseed):
    bundle = qseed("with_kyrian_full")["kyrian"]
    channels = {p.channel for p in bundle.pedidos}
    # We seeded whatsapp + mostrador + pedidosya
    assert "whatsapp" in channels
    assert "mostrador" in channels
    assert "pedidosya" in channels

    statuses = {p.status for p in bundle.pedidos}
    assert "fulfilled" in statuses
    assert "cancelled" in statuses

    # The cancelled one must have a cancel_reason
    cancelled = next(p for p in bundle.pedidos if p.status == "cancelled")
    assert cancelled.cancel_reason


def test_seed_kyrian_is_idempotent(session_factory):
    """Calling seed_kyrian twice should not duplicate rows."""
    sf = session_factory
    with sf() as s:
        bundle1 = seed_kyrian(s)
        first_pedido_count = len(bundle1.pedidos)
        first_sale_count = len(bundle1.sales)
        first_ledger_count = len(bundle1.loyalty_ledger)
        s.commit()

    with sf() as s:
        bundle2 = seed_kyrian(s)
        s.commit()

    assert len(bundle2.pedidos) == first_pedido_count, "Pedido count drifted"
    assert len(bundle2.sales) == first_sale_count, "Sale count drifted"
    assert len(bundle2.loyalty_ledger) == first_ledger_count, "Ledger drifted"
    # The customer should be the same row (matched by phone), not a new one
    assert bundle2.customer.id == bundle1.customer.id


def test_seed_kyrian_replaces_prior_data(session_factory):
    """Re-running the seed should overwrite prior Kyrian data cleanly.

    Pre-create a garbage pedido attributed to Kyrian's phone number,
    then re-run the seed. The garbage pedido should be gone.
    """

    sf = session_factory
    with sf() as s:
        # First seed
        bundle = seed_kyrian(s)
        s.commit()

        # Now manually add a garbage pedido
        garbage = Pedido(
            customer_id=bundle.customer.id,
            customer_name="garbage-keep-out",
            customer_phone=KYRIAN_PHONE,
            promised_date=__import__("datetime").date.today(),
            channel="other",
            status="pending",
            payment_intent="efectivo",
            notes="this should be wiped",
        )
        s.add(garbage)
        s.commit()
        garbage_id = garbage.id

    # Re-seed
    with sf() as s:
        seed_kyrian(s)
        s.commit()

    # Garbage pedido should be gone
    with sf() as s:
        still_there = s.execute(
            select(Pedido).where(Pedido.id == garbage_id)
        ).scalar_one_or_none()
        assert still_there is None, "Garbage pedido was not cleaned up"


def test_kyrian_export_constants_match_live_db():
    """The Kyrian constants are exported and match the live customer.

    If the live Kyrian's data changes (different phone, etc.), this
    test fails loudly so we remember to update the seed.
    """
    assert KYRIAN_PHONE == "0982515138"
    assert KYRIAN_EMAIL == "kyrianweiss.vdp@gmail.com"
    assert KYRIAN_CEDULA == "5991039"
    assert KYRIAN_NAME == "kyrian weiss"


def test_seed_records_pedido_events(qseed, session_factory):
    """Phase 11 — every seeded pedido has 'created' + 'line_added' events.

    Without this, the timeline on /pedidos/{id} would be empty for the
    demo data — a confusing first impression.
    """
    from app.rms.models import PedidoEvent
    from app.seed.kyrian import KYRIAN_PHONE

    qseed("with_kyrian_full")
    with session_factory() as s:
        kyrian = s.query(Customer).filter_by(phone=KYRIAN_PHONE).one()
        pedidos = s.query(Pedido).filter_by(customer_id=kyrian.id).all()
        assert len(pedidos) == 6

        for p in pedidos:
            events = s.query(PedidoEvent).filter_by(pedido_id=p.id).all()
            types = {e.event_type for e in events}
            assert "created" in types, f"pedido {p.id} missing 'created' event"
            assert "line_added" in types, f"pedido {p.id} missing 'line_added' event"
            # The 'created' event must be marked as from the seed
            ce = next(e for e in events if e.event_type == "created")
            assert ce.payload_json.get("source") == "seed"
