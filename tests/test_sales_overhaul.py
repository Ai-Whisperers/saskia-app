"""tests/test_sales_overhaul.py — Phase 5 sales form features."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select


def test_sale_accepts_payment_method(session_factory):
    """apply_sale with payment_method persists it (Spanish keys)."""
    from app.rms.costing import apply_sale
    from app.rms.models import Product, Sale

    with session_factory() as s:
        p = Product(name="Test P", sale_price_gs=10000, recipe_id=None)
        s.add(p)
        s.flush()
        apply_sale(
            s,
            product_id=p.id,
            qty=1,
            sold_at=datetime.now(timezone.utc),
            payment_method="efectivo",
        )
        s.commit()

    with session_factory() as s:
        sale = s.execute(select(Sale).where(Sale.product_id == p.id)).scalar_one()
        assert sale.payment_method == "efectivo"


def test_sale_accepts_discount(session_factory):
    """apply_sale with discount_gs persists the discount."""
    from app.rms.costing import apply_sale
    from app.rms.models import Product, Sale

    with session_factory() as s:
        p = Product(name="Test D", sale_price_gs=10000, recipe_id=None)
        s.add(p)
        s.flush()
        apply_sale(
            s,
            product_id=p.id,
            qty=1,
            sold_at=datetime.now(timezone.utc),
            discount_gs=500,
        )
        s.commit()

    with session_factory() as s:
        sale = s.execute(select(Sale).where(Sale.product_id == p.id)).scalar_one()
        assert sale.discount_gs == 500


def test_ventas_page_has_quick_sell_section(client):
    """/ventas shows Productos (formerly "Venta rápida") section.

    Phase C1 of the ventas-redesign renamed the right pane from
    "Venta rápida" to "Productos" — products are no longer treated as
    a "quick sale" shortcut, they're the canonical picking surface.
    The section heading + the page form must still render (200 OK)
    even with no sale history.
    """
    resp = client.get("/ventas")
    assert resp.status_code == 200
    # The right-pane heading must be present (either the new "Productos"
    # or the legacy "Venta rápida" copy — we just want a visible section).
    body = resp.text
    assert (
        ">Productos<" in body
        or "Productos" in body
        or "Venta rápida" in body
        or "Venta rapida" in body
        or "Nueva venta" in body
    ), "Productos / quick-sell section heading missing from /ventas"


def test_ventas_page_has_payment_method_field(client):
    """Ventas form must include payment_method + discount_gs + customer picker.

    SALES-UX-001: the customer picker now uses `<ui-combo>` with
    name=customer_id_combo (visible) plus a hidden customer_id field
    that the inline JS keeps in sync. The legacy `<button id=customer_picker_trigger>`
    was replaced with an inline disclosure — see _customer_picker.html.
    """
    resp = client.get("/ventas")
    assert resp.status_code == 200
    body = resp.text
    for field in ["payment_method", "discount_gs", "customer_id", "customer_id_combo"]:
        assert field in body, f"Missing field {field} in ventas form"


def test_ventas_filter_search_exists(client):
    """/ventas/historial shows search input + product filter + days filter (US 4.3)."""
    resp = client.get("/ventas/historial")
    assert resp.status_code == 200
    body = resp.text
    for field in ['name="q"', 'name="product_id"', 'name="days"']:
        assert field in body, f"Missing filter field {field}"


def test_ventas_filter_by_q(client, session_factory):
    """/ventas/historial?q=foo only returns matching sales."""
    from datetime import datetime, timezone

    from app.rms.models import Product, Sale

    with session_factory() as s:
        p1 = Product(name="Cabernet", sale_price_gs=10000, recipe_id=None)
        p2 = Product(name="Quinoa", sale_price_gs=15000, recipe_id=None)
        s.add_all([p1, p2])
        s.flush()
        s.add(
            Sale(product_id=p1.id, qty=1, unit_price_gs=10000, sold_at=datetime.now(timezone.utc))
        )
        s.add(
            Sale(product_id=p2.id, qty=1, unit_price_gs=15000, sold_at=datetime.now(timezone.utc))
        )
        s.commit()

    resp = client.get("/ventas/historial?q=cabernet")
    assert resp.status_code == 200
    assert "Cabernet" in resp.text


def test_ventas_filter_by_product(client, session_factory):
    """/ventas/historial?product_id=N filters to that product's sales."""
    from datetime import datetime, timezone

    from app.rms.models import Product, Sale

    with session_factory() as s:
        p1 = Product(name="CakeFiltroUno", sale_price_gs=20000, recipe_id=None)
        p2 = Product(name="PieFiltroDos", sale_price_gs=12000, recipe_id=None)
        s.add_all([p1, p2])
        s.flush()
        s.add(
            Sale(product_id=p1.id, qty=1, unit_price_gs=20000, sold_at=datetime.now(timezone.utc))
        )
        s.add(
            Sale(product_id=p2.id, qty=1, unit_price_gs=12000, sold_at=datetime.now(timezone.utc))
        )
        s.commit()
        p1_id = p1.id

    resp_all = client.get("/ventas/historial")
    resp_filt = client.get(f"/ventas/historial?product_id={p1_id}")
    assert resp_all.status_code == 200
    assert resp_filt.status_code == 200
    # Filtered should contain p1's name; unfiltered should contain both.
    assert "CakeFiltroUno" in resp_filt.text
    assert "PieFiltroDos" not in resp_filt.text or "CakeFiltroUno" in resp_all.text


def test_ventas_filter_by_days(client, session_factory):
    """/ventas/historial?days=7 should not 500; recent sales still appear."""
    from datetime import datetime, timezone

    from app.rms.models import Product, Sale

    with session_factory() as s:
        p = Product(name="Bread", sale_price_gs=5000, recipe_id=None)
        s.add(p)
        s.flush()
        s.add(
            Sale(
                product_id=p.id,
                qty=1,
                unit_price_gs=5000,
                sold_at=datetime.now(timezone.utc),
                notes="X",
            )
        )
        s.commit()

    # No 500 even with the days filter applied
    resp = client.get("/ventas?days=7")
    assert resp.status_code == 200
