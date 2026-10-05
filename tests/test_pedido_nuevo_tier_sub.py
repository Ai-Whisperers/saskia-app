"""Tier 6.4 (2026-10-01) — /pedidos/nuevo customer tier + suscripción prefill.

Two flows added to /pedidos/nuevo:
  1. Tier badge — a small BRONZE/SILVER/GOLD/PLATINUM pill that renders
     inline near the customer combo after a customer is picked.
  2. Suscripción picker — a small panel listing the customer's active
     suscripciones with an "Aplicar" button that copies the
     product_summary into the notes field.

Both fields are part of the CustomerPrefill dataclass (computed server-
side in app/services/customer_prefill.py) and rendered client-side by
static/pedido-prefill.js.

Run: cd /opt/data/profiles/ivan/scratch/sazon-app-work && ./.venv/bin/python -m pytest tests/test_pedido_nuevo_tier_sub.py -v
"""

from __future__ import annotations

from datetime import datetime

from app.rms.models import Customer, Product, Sale, Suscripcion
from app.services.customer_prefill import compute_customer_defaults


def _make_customer_with_spend(session, lifetime_spend_gs: int) -> int:
    """Helper: create a customer whose lifetime spend equals the given Gs."""
    cust = Customer(name=f"Cust {lifetime_spend_gs}", phone=f"+595****{lifetime_spend_gs:04d}")
    session.add(cust)
    session.flush()
    # Add a single sale of `lifetime_spend_gs` total so lifetime_spend matches
    prod = Product(name=f"Prod {lifetime_spend_gs}", sale_price_gs=lifetime_spend_gs)
    session.add(prod)
    session.flush()
    session.add(
        Sale(
            customer_id=cust.id,
            product_id=prod.id,
            qty=1,
            unit_price_gs=lifetime_spend_gs,
            sold_at=datetime(2026, 9, 1, 10, 0),
            channel="mostrador",
            tz="America/Asuncion",
        )
    )
    session.commit()
    return cust.id


# ---- Backend tests: CustomerPrefill.tier and active_subscriptions ----


def test_prefill_includes_tier_bronze(session_factory) -> None:
    """A new customer (no spend) has tier='bronze' in prefill."""
    with session_factory() as s:
        cust = Customer(name="Newbie", phone="+595****0001")
        s.add(cust)
        s.commit()
        cid = cust.id

    with session_factory() as s:
        prefill = compute_customer_defaults(s, cid)

    assert prefill.tier == "bronze", f"Expected tier='bronze' for 0 spend, got {prefill.tier}"


def test_prefill_includes_tier_silver(session_factory) -> None:
    """A customer with ~250k lifetime spend has tier='silver'."""
    with session_factory() as s:
        cid = _make_customer_with_spend(s, 250_000)

    with session_factory() as s:
        prefill = compute_customer_defaults(s, cid)

    assert prefill.tier == "silver", f"Expected tier='silver' for 250k spend, got {prefill.tier}"


def test_prefill_includes_tier_gold(session_factory) -> None:
    """A customer with ~750k lifetime spend has tier='gold'."""
    with session_factory() as s:
        cid = _make_customer_with_spend(s, 750_000)

    with session_factory() as s:
        prefill = compute_customer_defaults(s, cid)

    assert prefill.tier == "gold", f"Expected tier='gold' for 750k spend, got {prefill.tier}"


def test_prefill_includes_tier_platinum(session_factory) -> None:
    """A customer with ~1.5M lifetime spend has tier='platinum'."""
    with session_factory() as s:
        cid = _make_customer_with_spend(s, 1_500_000)

    with session_factory() as s:
        prefill = compute_customer_defaults(s, cid)

    assert prefill.tier == "platinum", (
        f"Expected tier='platinum' for 1.5M spend, got {prefill.tier}"
    )


def test_prefill_includes_active_subscriptions(session_factory) -> None:
    """A customer with an active suscripción has it in prefill.active_subscriptions."""
    with session_factory() as s:
        cust = Customer(name="Subber", phone="+595****0100")
        s.add(cust)
        s.flush()
        s.add(
            Suscripcion(
                customer_id=cust.id,
                product_summary="1 kg chipas",
                cadence="semanal",
                preferred_day_of_week=5,  # Friday
                price_gs=50000,
                status="activa",
                start_date=datetime(2026, 9, 1).date(),
            )
        )
        # And one INactiva — should NOT appear
        s.add(
            Suscripcion(
                customer_id=cust.id,
                product_summary="Old cancelled sub",
                cadence="mensual",
                status="cancelada",
                start_date=datetime(2026, 1, 1).date(),
            )
        )
        s.commit()
        cid = cust.id

    with session_factory() as s:
        prefill = compute_customer_defaults(s, cid)

    assert isinstance(prefill.active_subscriptions, list)
    assert len(prefill.active_subscriptions) == 1, (
        f"Expected exactly 1 active suscripción, got {len(prefill.active_subscriptions)}: "
        f"{prefill.active_subscriptions}"
    )
    sub = prefill.active_subscriptions[0]
    assert sub["product_summary"] == "1 kg chipas"
    assert sub["cadence"] == "semanal"
    assert sub["price_gs"] == 50000
    assert sub["preferred_day_of_week"] == 5


def test_prefill_excludes_paused_subscriptions(session_factory) -> None:
    """Only 'activa' status suscripciones show up in prefill."""
    with session_factory() as s:
        cust = Customer(name="Pauser", phone="+595****0200")
        s.add(cust)
        s.flush()
        s.add(
            Suscripcion(
                customer_id=cust.id,
                product_summary="Paused sub",
                cadence="mensual",
                status="pausada",
            )
        )
        s.commit()
        cid = cust.id

    with session_factory() as s:
        prefill = compute_customer_defaults(s, cid)

    assert prefill.active_subscriptions == [], (
        f"pausada should NOT appear; got {prefill.active_subscriptions}"
    )


def test_prefill_empty_for_customer_with_no_subs(session_factory) -> None:
    """A customer without any suscripción has empty active_subscriptions."""
    with session_factory() as s:
        cust = Customer(name="NoSub", phone="+595****0300")
        s.add(cust)
        s.commit()
        cid = cust.id

    with session_factory() as s:
        prefill = compute_customer_defaults(s, cid)

    assert prefill.active_subscriptions == []


# ---- HTTP endpoint test: JSON prefill includes tier + subs ----


def test_customer_defaults_api_includes_tier_and_subs(client, session_factory) -> None:
    """GET /pedidos/api/customer-defaults/<id> returns tier + active_subscriptions."""
    with session_factory() as s:
        cust = Customer(name="APICust", phone="+595****0400")
        s.add(cust)
        s.flush()
        prod = Product(name="APIProd", sale_price_gs=600_000)
        s.add(prod)
        s.flush()
        s.add(
            Sale(
                customer_id=cust.id,
                product_id=prod.id,
                qty=1,
                unit_price_gs=600_000,
                sold_at=datetime(2026, 9, 1, 10, 0),
                channel="mostrador",
                tz="America/Asuncion",
            )
        )
        s.add(
            Suscripcion(
                customer_id=cust.id,
                product_summary="API test sub",
                cadence="quincenal",
                status="activa",
            )
        )
        s.commit()
        cid = cust.id

    resp = client.get(f"/pedidos/api/customer-defaults/{cid}")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    body = resp.json()
    assert body.get("tier") == "gold", (
        f"Expected tier='gold' (600k spend); got {body.get('tier')!r}"
    )
    assert isinstance(body.get("active_subscriptions"), list)
    assert len(body["active_subscriptions"]) == 1
    assert body["active_subscriptions"][0]["product_summary"] == "API test sub"


# ---- Template test: /pedidos/nuevo renders the tier badge + sub picker ----


def test_pedidos_nuevo_template_has_tier_badge_and_sub_picker(client) -> None:
    """/pedidos/nuevo template includes the Tier 6.4 placeholders."""
    resp = client.get("/pedidos/nuevo")
    assert resp.status_code == 200
    body = resp.text
    assert 'id="customer-tier-badge"' in body, (
        "Expected tier badge placeholder in /pedidos/nuevo template"
    )
    assert 'id="customer-subscription-picker"' in body, (
        "Expected suscripción picker placeholder in /pedidos/nuevo template"
    )


def test_pedidos_nuevo_includes_updated_pedido_prefill_js(client) -> None:
    """/pedidos/nuevo template still references /static/pedido-prefill.js."""
    resp = client.get("/pedidos/nuevo")
    assert resp.status_code == 200
    assert "/static/pedido-prefill.js" in resp.text


def test_pedido_prefill_js_has_tier_and_sub_renderers() -> None:
    """static/pedido-prefill.js exports the Tier 6.4 render functions."""
    from pathlib import Path

    p = Path("/opt/data/profiles/ivan/scratch/sazon-app-work/app/static/pedido-prefill.js")
    text = p.read_text(encoding="utf-8")
    assert "function renderTierBadge" in text, "pedido-prefill.js must export renderTierBadge()"
    assert "function renderSubscriptionPicker" in text, (
        "pedido-prefill.js must export renderSubscriptionPicker()"
    )
    # The calls to those render functions must also be wired in applyPrefill
    assert "renderTierBadge(prefill);" in text
    assert "renderSubscriptionPicker(prefill);" in text
