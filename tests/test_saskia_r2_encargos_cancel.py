"""Tests for S6 — US 4.4 (encargos→production) + CIE-01 (sale cancellation audit).

US 4.4 acceptance criteria:
- /produccion (day view) shows a "Pedidos pendientes para hoy" panel when
  pedidos exist with promised_date == the requested for_date.
- The panel is filtered to status ∈ {pending, confirmed, ready} — fulfilled
  and cancelled pedidos do not appear.
- Each pedido row links to /pedidos/{id} and shows qty × product_name.
- Sorted by promised_time ASC (nulls last), then created_at ASC.

CIE-01 acceptance criteria:
- Sale.void_reason and Sale.voided_by are persisted on the Sale row.
- /ventas/{id}/anular accepts a `reason` form field.
- The history table renders void_reason and voided_by when present.
- void_sale() updates the StockMovement.reason to include the new reason.
- Legacy POSTs (no reason) still void the sale — void_reason is NULL.
- Already-voided sales still raise ValueError (idempotency preserved).
"""

from datetime import date, datetime, timedelta, timezone

import pytest

from app.rms.config import ASUNCION_TZ
from app.rms.models import (
    Customer,
    Ingredient,
    Pedido,
    PedidoLine,
    Product,
    Sale,
    StockMovement,
)


# =========================================================================
# US 4.4 — pedidos surface in /produccion day view
# =========================================================================


def _seed_pedido(
    session_factory,
    *,
    customer_name: str = "Cliente Test",
    status: str = "pending",
    promised_date: date | None = None,
    promised_time: str | None = None,
    product_name: str | None = None,
    qty: float = 2.0,
) -> int:
    import secrets as _secrets
    import uuid as _uuid

    if product_name is None:
        product_name = f"Torta_{_uuid.uuid4().hex[:8]}"
    with session_factory() as s:
        c = Customer(name=customer_name, phone="0981112222")
        p = Product(name=product_name, sale_price_gs=50000, recipe_id=None)
        s.add_all([c, p]); s.flush()
        pedido = Pedido(
            customer_id=c.id,
            customer_name=customer_name,
            customer_phone="0981112222",
            promised_date=promised_date or date.today(),
            promised_time=promised_time,
            channel="whatsapp",
            status=status,
            payment_intent="efectivo",
            # Real pedidos get a unique URL token; tests must too or the
            # unique index on pedido.public_token fails when seeding N pedidos.
            public_token=_secrets.token_urlsafe(8)[:8],
        )
        s.add(pedido); s.flush()
        s.add(PedidoLine(
            pedido_id=pedido.id, product_id=p.id,
            qty=qty, unit_price_gs=50000,
        ))
        s.commit()
        return pedido.id


def test_produccion_day_shows_pedido_for_today(client, session_factory):
    """US 4.4 — a pedido for today's promised_date appears in /produccion."""
    pedido_id = _seed_pedido(session_factory, status="pending")
    resp = client.get("/produccion")
    assert resp.status_code == 200
    body = resp.text
    assert "Pedidos pendientes para hoy" in body
    assert f"Pedido #{pedido_id}" in body
    # The product name in the pedido line should be visible (uuid'd for
    # uniqueness across tests — see _seed_pedido).
    with session_factory() as s:
        line = s.query(PedidoLine).filter_by(pedido_id=pedido_id).one()
        assert line.product.name in body


def test_produccion_day_excludes_other_dates(client, session_factory):
    """US 4.4 — pedidos for OTHER dates do not appear in today's view."""
    # Pedido for tomorrow
    _seed_pedido(session_factory, status="pending",
                 promised_date=date.today() + timedelta(days=1))
    resp = client.get("/produccion")
    assert resp.status_code == 200
    body = resp.text
    # The section either doesn't render OR doesn't contain "Pedidos pendientes para hoy"
    # when there are no pedidos for today.
    assert "Pedido #" not in body


def test_produccion_day_shows_pending_confirmed_ready(client, session_factory):
    """US 4.4 — non-terminal statuses are all surfaced."""
    ids = [
        _seed_pedido(session_factory, status="pending", customer_name="P1"),
        _seed_pedido(session_factory, status="confirmed", customer_name="C1"),
        _seed_pedido(session_factory, status="ready", customer_name="R1"),
    ]
    resp = client.get("/produccion")
    assert resp.status_code == 200
    body = resp.text
    for pid in ids:
        assert f"Pedido #{pid}" in body, f"Pedido {pid} should be visible"


def test_produccion_day_excludes_fulfilled_and_cancelled(client, session_factory):
    """US 4.4 — fulfilled and cancelled pedidos do NOT appear."""
    _seed_pedido(session_factory, status="fulfilled", customer_name="F1")
    _seed_pedido(session_factory, status="cancelled", customer_name="X1")
    # Plus one pending so the panel renders
    _seed_pedido(session_factory, status="pending", customer_name="P1")
    resp = client.get("/produccion")
    assert resp.status_code == 200
    body = resp.text
    assert "F1" not in body
    assert "X1" not in body
    assert "P1" in body


def test_produccion_day_pedidos_have_link_to_detail(client, session_factory):
    """US 4.4 — each pedido row links to /pedidos/{id} for navigation."""
    pedido_id = _seed_pedido(session_factory, status="pending")
    resp = client.get("/produccion")
    assert resp.status_code == 200
    assert f'href="/pedidos/{pedido_id}"' in resp.text


def test_produccion_day_sorts_by_promised_time_asc(client, session_factory):
    """US 4.4 — pedidos are sorted by promised_time ASC (earliest first)."""
    pid_late = _seed_pedido(
        session_factory, status="pending",
        customer_name="Late", promised_time="18:00",
    )
    pid_early = _seed_pedido(
        session_factory, status="pending",
        customer_name="Early", promised_time="09:00",
    )
    resp = client.get("/produccion")
    assert resp.status_code == 200
    body = resp.text
    # 'Early' should appear before 'Late' in the rendered HTML
    assert body.index("Early") < body.index("Late")
    assert pid_early and pid_late


def test_produccion_day_no_pedidos_means_no_panel(client, session_factory):
    """US 4.4 — when no pedidos for today, the panel is not rendered."""
    resp = client.get("/produccion")
    assert resp.status_code == 200
    assert "Pedidos pendientes para hoy" not in resp.text


# =========================================================================
# CIE-01 — sale cancellation audit trail
# =========================================================================


def _seed_sale(session_factory) -> int:
    with session_factory() as s:
        p = Product(name="BrownieAudit", sale_price_gs=10000, recipe_id=None)
        s.add(p); s.flush()
        sale = Sale(
            product_id=p.id,
            qty=2,
            unit_price_gs=10000,
            sold_at=datetime.now(timezone.utc),
            channel="mostrador",
        )
        s.add(sale); s.commit()
        return sale.id


def test_void_sale_persists_reason_and_voided_by(session_factory):
    """CIE-01 — void_sale() stores reason + voided_by on the Sale row."""
    from app.rms.costing import void_sale

    sale_id = _seed_sale(session_factory)
    void_sale(session_factory(), sale_id,
              reason="Cliente devolvió producto", voided_by="operator42")

    with session_factory() as s:
        sale = s.get(Sale, sale_id)
        assert sale.voided_at is not None
        assert sale.void_reason == "Cliente devolvió producto"
        assert sale.voided_by == "operator42"


def test_void_sale_without_reason_still_works(session_factory):
    """CIE-01 — legacy callers (no reason) still void successfully."""
    from app.rms.costing import void_sale

    sale_id = _seed_sale(session_factory)
    void_sale(session_factory(), sale_id)  # no reason, no voided_by

    with session_factory() as s:
        sale = s.get(Sale, sale_id)
        assert sale.voided_at is not None
        assert sale.void_reason is None
        assert sale.voided_by is None


def test_void_sale_appends_reason_to_stock_movement(session_factory):
    """CIE-01 — the reversed StockMovement.reason includes the void reason.

    Sets up a minimal recipe (Polymorphic RecipeLine) so apply_sale generates
    a real StockMovement via the relationship, then voids and checks the
    reversal movement's reason carries the void reason.
    """
    from app.rms.costing import apply_sale, void_sale
    from app.rms.models import Recipe, RecipeLine

    with session_factory() as s:
        ing = Ingredient(name="CIE_Flour_audit", stock_qty=1000.0, unit="g")
        p = Product(name="CIE_Brownie_audit", sale_price_gs=10000, recipe_id=None)
        s.add_all([ing, p]); s.flush()
        rcp = Recipe(name="CIE_Brownie_recipe", yield_qty=1, yield_unit="und")
        s.add(rcp); s.flush()
        p.recipe_id = rcp.id
        s.add(RecipeLine(
            recipe_id=rcp.id, line_kind="ingredient",
            line_ref_id=ing.id, qty=50.0, line_unit="g",
        ))
        s.commit()
        product_id = p.id

    with session_factory() as s:
        result = apply_sale(
            s, product_id=product_id, qty=2.0,
            sold_at=datetime.now(ASUNCION_TZ),
        )
        s.commit()
        sale_id = result.sale_id

    void_sale(session_factory(), sale_id,
              reason="error de cobro", voided_by="operator")

    with session_factory() as s:
        moves = s.query(StockMovement).filter_by(reference_id=sale_id).all()
        reversal = [m for m in moves if m.qty > 0]
        assert len(reversal) >= 1
        assert "error de cobro" in reversal[0].reason


def test_double_void_raises_valueerror(session_factory):
    """CIE-01 — idempotency preserved: voiding twice still raises."""
    from app.rms.costing import void_sale

    sale_id = _seed_sale(session_factory)
    void_sale(session_factory(), sale_id, reason="primera")
    with pytest.raises(ValueError):
        void_sale(session_factory(), sale_id, reason="segunda")


def test_void_endpoint_accepts_reason_form_field(client, session_factory):
    """CIE-01 — POST /ventas/{id}/anular with reason persists it."""
    sale_id = _seed_sale(session_factory)

    resp = client.post(
        f"/ventas/{sale_id}/anular",
        data={"reason": "Cliente cambió de opinión"},
        follow_redirects=False,
    )
    assert resp.status_code == 303

    with session_factory() as s:
        sale = s.get(Sale, sale_id)
        assert sale.voided_at is not None
        assert sale.void_reason == "Cliente cambió de opinión"


def test_void_endpoint_redirects_to_historial(client, session_factory):
    """CIE-01 — POST /ventas/{id}/anular now redirects to /ventas/historial
    (post-split flow), not the unified /ventas page."""
    sale_id = _seed_sale(session_factory)

    resp = client.post(
        f"/ventas/{sale_id}/anular",
        data={"reason": "test"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "/ventas/historial" in resp.headers["location"]


def test_void_endpoint_no_reason_still_voids(client, session_factory):
    """CIE-01 — POST without a reason still voids the sale (legacy compat)."""
    sale_id = _seed_sale(session_factory)
    resp = client.post(
        f"/ventas/{sale_id}/anular",
        follow_redirects=False,
    )
    assert resp.status_code == 303
    with session_factory() as s:
        sale = s.get(Sale, sale_id)
        assert sale.voided_at is not None
        assert sale.void_reason is None


def test_void_endpoint_already_voided_returns_409(client, session_factory):
    """CIE-01 — POST on an already-voided sale returns 409."""
    sale_id = _seed_sale(session_factory)
    client.post(f"/ventas/{sale_id}/anular", follow_redirects=False)
    resp = client.post(
        f"/ventas/{sale_id}/anular",
        follow_redirects=False,
    )
    assert resp.status_code == 409


def test_void_sale_restores_stock_with_reason(session_factory):
    """CIE-01 — void_sale still restores stock correctly when a reason is
    provided (the audit trail must not break the core reversal semantics)."""
    from app.rms.costing import apply_sale, void_sale

    # Set up: 1 ingredient, product with recipe, sale decrements stock
    with session_factory() as s:
        ing = Ingredient(name="CIE_Flour", stock_qty=1000.0, unit="g")
        s.add(ing); s.flush()
        # We don't actually need a recipe to test void restore; apply_sale
        # expects ingredient-level stock moves. Use the existing sale path
        # which writes stock_moves. We'll instead create the StockMove rows
        # directly to test the void restore path.
        p = Product(name="CIE_Brownie", sale_price_gs=10000, recipe_id=None)
        s.add(p); s.flush()
        sale = Sale(
            product_id=p.id, qty=5, unit_price_gs=10000,
            sold_at=datetime.now(timezone.utc),
        )
        s.add(sale); s.flush()
        s.add(StockMovement(
            ingredient_id=ing.id, movement_type="sale",
            qty=-100.0,  # sold 100g
            reason=f"Sale #{sale.id}",
            reference_id=sale.id, reference_type="sale",
            recorded_at=datetime.now(timezone.utc),
        ))
        s.commit()
        sale_id = sale.id
        ing_id = ing.id

    void_sale(session_factory(), sale_id,
              reason="error de cobro", voided_by="operator")

    with session_factory() as s:
        ing = s.get(Ingredient, ing_id)
        # 1000 - 100 + 100 = 1000 again
        assert abs(ing.stock_qty - 1000.0) < 0.01


def test_historial_renders_void_reason_and_by(client, session_factory):
    """CIE-01 — the history table surfaces void_reason and voided_by."""
    from app.rms.costing import void_sale

    sale_id = _seed_sale(session_factory)
    void_sale(session_factory(), sale_id,
              reason="prueba auditoría", voided_by="admin")

    resp = client.get("/ventas/historial")
    assert resp.status_code == 200
    body = resp.text
    # The void reason appears in the voided-banner block
    assert "prueba auditoría" in body
    assert "admin" in body
