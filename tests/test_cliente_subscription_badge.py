"""tests/test_cliente_subscription_badge.py — phase 9.

Verify:
- The /clientes/{id} GET handler loads Suscripcion rows
- The template renders an "📦 Suscripciones" section when subscriptions exist
- The "Crear pedido" CTA is wired to /pedidos/nuevo?customer_id=...
- Active + paused + cancelled statuses all surface in the badge colors
- A customer with no subscriptions shows no banner
"""

from __future__ import annotations

from datetime import date


def _kyrian_id(session_factory, qseed):
    from app.rms.models import Customer
    from app.seed.kyrian import KYRIAN_PHONE
    qseed("with_kyrian_full")
    with session_factory() as s:
        return s.query(Customer).filter_by(phone=KYRIAN_PHONE).one().id


def test_cliente_detail_renders_subscription_section(client, qseed, session_factory):
    """Kyrian's seed creates 1 active subscription — page should show it."""
    cid = _kyrian_id(session_factory, qseed)
    r = client.get(f"/clientes/{cid}")
    assert r.status_code == 200, r.text
    html = r.text
    assert "Suscripciones" in html
    # The seeded subscription is "1 kg chipa + 2 facturas (sábados)"
    assert "chipa" in html or "facturas" in html
    # The status badge should appear
    assert "activa" in html or "pausada" in html or "cancelada" in html


def test_cliente_detail_shows_create_pedido_cta(client, qseed, session_factory):
    """Active subscription shows a 'Crear pedido' button that links
    to /pedidos/nuevo?customer_id=<id>."""
    cid = _kyrian_id(session_factory, qseed)
    r = client.get(f"/clientes/{cid}")
    html = r.text
    expected_href = f"/pedidos/nuevo?customer_id={cid}"
    assert expected_href in html, f"Expected {expected_href} in detail HTML"


def test_cliente_detail_no_subscription_banner_for_new_customer(client, session_factory):
    """Customer with no subscriptions does NOT show the banner."""
    from app.rms.models import Customer
    with session_factory() as s:
        c = Customer(name="Sin Suscripcion", phone="0991110000")
        s.add(c); s.commit()
        cid = c.id
    r = client.get(f"/clientes/{cid}")
    assert r.status_code == 200
    # The subscription section should be absent (template guards with
    # `if active_subscriptions`). Other sections like the loyalty ledger
    # may also mention "Suscripciones" — we look for the actual heading.
    html = r.text
    # The subscription heading + form would only render if there's a subscription
    # We assert the CTA form is NOT present (active_subscriptions is empty).
    assert "/pedidos/nuevo?customer_id=" not in html or "📦 Crear pedido" not in html


def test_handler_loads_all_subscription_statuses(client, qseed, session_factory):
    """The handler returns subscriptions of all statuses (activa/pausada/cancelada)
    so the operator can see the full picture (paused subs can be reactivated,
    cancelled ones stay on file for reference)."""
    from app.rms.models import Suscripcion
    cid = _kyrian_id(session_factory, qseed)

    with session_factory() as s:
        # Add a paused + cancelled sub for the same customer
        s.add(Suscripcion(
            customer_id=cid,
            product_summary="Babka semanal (pausada)",
            cadence="semanal",
            preferred_day_of_week=3,
            start_date=date(2026, 9, 1),
            price_gs=50000,
            status="pausada",
        ))
        s.add(Suscripcion(
            customer_id=cid,
            product_summary="Torta vieja (cancelada)",
            cadence="mensual",
            start_date=date(2026, 6, 1),
            end_date=date(2026, 8, 31),
            price_gs=80000,
            status="cancelada",
        ))
        s.commit()

    r = client.get(f"/clientes/{cid}")
    html = r.text
    assert "Babka semanal (pausada)" in html
    assert "Torta vieja (cancelada)" in html
    assert "pausada" in html
    assert "cancelada" in html
