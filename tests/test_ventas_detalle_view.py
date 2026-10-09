"""Tests for /ventas/{sale_id} standalone HTML detail view (BACKLOG #16).

Operator-only (login required). Distinct from /recibo which is the
printable A6 receipt; this is a normal-width operator-facing detail
page showing the same sale with full product info, payment method,
and void metadata.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.rms.models import Customer, Sale


def _seed_sale(session_factory, *, payment_method: str = "efectivo") -> int:
    """Seed product, customer, sale; return sale.id."""
    s = session_factory()
    try:
        from tests.factories import make_catalog, make_sale

        cat = make_catalog(s, price_gs=10_000)
        cust = Customer(
            name="Detalle Test",
            phone="+595981000111",
            loyalty_points=42,
        )
        s.add(cust)
        s.flush()
        sale = make_sale(s, product=cat["product"], qty=2)
        sale.customer_id = cust.id
        sale.payment_method = payment_method
        sale.channel = "mostrador"
        s.commit()
        return int(sale.id)
    finally:
        s.close()


def test_ventas_detail_returns_200_for_valid_sale(authed_client, session_factory):
    sale_id = _seed_sale(session_factory)
    response = authed_client.get(f"/ventas/{sale_id}")
    assert response.status_code == 200, response.text[:200]
    body = response.text
    # Core fields
    assert f"Venta #{sale_id}" in body
    assert "Detalle Test" in body  # customer
    assert "efectivo" in body.lower()


def test_ventas_detail_404_for_missing_sale(authed_client):
    response = authed_client.get("/ventas/999999")
    assert response.status_code == 404


def test_ventas_detail_shows_void_banner_when_voided(authed_client, session_factory):
    sale_id = _seed_sale(session_factory)
    # Void the sale
    s = session_factory()
    try:
        sale = s.get(Sale, sale_id)
        sale.voided_at = datetime.now(timezone.utc)
        sale.void_reason = "test void"
        s.commit()
    finally:
        s.close()

    response = authed_client.get(f"/ventas/{sale_id}")
    assert response.status_code == 200
    body = response.text
    assert "ANULADO" in body or "anulada" in body.lower()


def test_ventas_detail_route_protected_by_require_login():
    """Static check: the /ventas/{id:int} route uses the same auth decorator
    as the rest of the ventas router (require_login). Catches regressions
    if someone removes the decorator."""
    from app.routers import sales as sales_module

    found = False
    for route in sales_module.router.routes:
        path = getattr(route, "path", "")
        if path == "/ventas/{sale_id:int}":
            assert len(route.dependencies) > 0, (
                "sale_detail route lost its require_login dependency"
            )
            # require_login is wrapped via require_login_or_disabled in test
            dep = route.dependencies[0]
            assert "require_login" in str(dep), f"Expected require_login dependency, got {dep}"
            found = True
    assert found, "/ventas/{sale_id:int} route not registered"
