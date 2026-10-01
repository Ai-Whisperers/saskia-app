"""Tier 6.2 (2026-10-01) — /clientes/{id} recent pedidos + top products.

Two flows added to /clientes/{id}:
  1. "Pedidos recientes" table — shows up to 5 of the customer's most
     recent pedidos with status pills + a "Pedir de nuevo" CTA that
     pre-fills the next pedido with this customer's profile.
  2. "Productos frecuentes" table — top 5 products this customer buys,
     ranked by sales count, with cumulative qty + total Gs.

These flows close the gap where the operator had to navigate to /pedidos
and filter manually to figure out "what does this customer order
regularly?"
"""

from __future__ import annotations

import datetime as _dt
from decimal import Decimal


def _kyrian_customer_id(session_factory):
    """Return the Kyrian customer id from the with_kyrian_full seed."""
    with session_factory() as s:
        from app.rms.models import Customer

        c = s.execute(
            __import__("sqlalchemy").select(Customer).where(
                Customer.name.ilike("%kyrian%")
            )
        ).scalar_one_or_none()
        assert c is not None, "Kyrian customer must exist in with_kyrian_full"
        return c.id


def test_detalle_recent_pedidos_table_renders(client, qseed, session_factory):
    """With >1 pedido for Kyrian, the /clientes/{id} page shows the
    'Pedidos recientes' table."""
    qseed("with_kyrian_full")
    cid = _kyrian_customer_id(session_factory)

    r = client.get(f"/clientes/{cid}")
    assert r.status_code == 200
    body = r.text
    assert "Pedidos recientes" in body
    # Each pedido row links to /pedidos/{id}
    assert "/pedidos/" in body


def test_detalle_recent_pedidos_shows_status_pill(client, qseed, session_factory):
    """The recent pedidos table renders the status pill with the
    Spanish label (e.g. 'Pendiente', 'Confirmado', 'Entregado')."""
    qseed("with_kyrian_full")
    cid = _kyrian_customer_id(session_factory)

    r = client.get(f"/clientes/{cid}")
    body = r.text
    # Pull just the pedidos section between the heading and the next <h2>
    start = body.find("Pedidos recientes")
    assert start >= 0
    section = body[start:]
    # One of the canonical ES labels must appear in the pedidos section
    # (we don't assert a specific status because Kyrian's pedidos could
    # land in any state depending on seed defaults)
    canonical_labels = [
        "Pendiente",
        "Confirmado",
        "Listo",
        "Entregado",
        "Cancelado",
        "pending",
        "confirmed",
        "fulfilled",
    ]
    assert any(label in section for label in canonical_labels), (
        "Expected at least one canonical status label in pedidos section"
    )


def test_detalle_pedir_de_nuevo_cta_links(client, qseed, session_factory):
    """Each pedido row has a 'Pedir de nuevo' link to
    /pedidos/nuevo?customer_id=N&from=M."""
    qseed("with_kyrian_full")
    cid = _kyrian_customer_id(session_factory)

    r = client.get(f"/clientes/{cid}")
    assert r.status_code == 200
    body = r.text
    # The CTA must be present somewhere in the page
    assert "Pedir de nuevo" in body
    # The link shape must include the customer_id + from params
    assert f"/pedidos/nuevo?customer_id={cid}&from=" in body


def test_detalle_top_products_section_renders(client, qseed, session_factory):
    """T-2026-10-01: reviewer's "right-pane table bloat" rule. The
    Productos frecuentes section was removed (folded into Pedidos
    recientes <details>). This test is preserved as a regression
    guard so the new shape — pedidos with inline line-item expansion
    — stays present.
    """
    qseed("with_kyrian_full")
    cid = _kyrian_customer_id(session_factory)

    r = client.get(f"/clientes/{cid}")
    body = r.text
    # New shape: pedidos with <details> expansion (the line-item
    # snapshot lives inside, not as a separate table).
    assert "Pedidos recientes" in body
    assert "recent-pedido" in body
    # The Productos frecuentes section was deliberately removed.
    assert "Productos frecuentes" not in body


def test_detalle_top_products_lists_product_with_sales(client, qseed, session_factory):
    """T-2026-10-01: reviewer's "right-pane table bloat" rule. The
    Productos frecuentes table was removed — the same product data
    is now surfaced inline inside each Pedidos recientes <details>
    expansion (via top_lines). This test now asserts the new shape:
    the pedidos section is present and at least one pedido row
    expands to show item lines including the Croissant / Pan Francés
    that Kyrian buys.
    """
    qseed("with_kyrian_full")
    cid = _kyrian_customer_id(session_factory)

    r = client.get(f"/clientes/{cid}")
    body = r.text

    # Pedidos recientes section must exist
    assert "Pedidos recientes" in body
    # Each pedido row is now a <details class="recent-pedido">
    assert "recent-pedido" in body
    # Kyrian's seeded favorites include Appeltaart, Babka de chocolate,
    # Cheesecake entera, Pan lactal, Stroopwafel — at least one of
    # these MUST be in the HTML (rendered inside the <details>
    # expansion). This proves the top_lines snapshot is wired through.
    body_text = body
    expected_products = ["Appeltaart", "Babka de chocolate", "Cheesecake entera", "Pan lactal", "Stroopwafel"]
    assert any(prod in body_text for prod in expected_products), (
        f"Expected at least one of {expected_products} in the page (rendered "
        f"inside the new Pedidos recientes <details> expansion), but none "
        f"appeared. Either the seed or the top_lines snapshot is broken."
    )


def test_detalle_no_recent_pedidos_hides_section(client, qseed, session_factory):
    """When the customer has zero pedidos, the section is hidden (no
    empty table rendered)."""
    # Use a brand-new customer with no history so we don't have to fight
    # FK constraints from pedido_events / sales.
    with session_factory() as s:
        from app.rms.models import Customer

        c = Customer(name="Empty Test Cliente", phone="+595991234567")
        s.add(c)
        s.commit()
        cid = c.id

    r = client.get(f"/clientes/{cid}")
    assert r.status_code == 200
    body = r.text
    # The section must NOT render when there are no pedidos
    assert "Pedidos recientes" not in body
    # ...but the page itself must still render OK
    assert "Contacto" in body or "Notas" in body


def test_detalle_top_products_omitted_when_no_sales(client, qseed, session_factory):
    """When the customer has zero sales, the Productos frecuentes
    section is hidden (not an empty table)."""
    with session_factory() as s:
        from app.rms.models import Customer

        c = Customer(name="Empty Sales Test Cliente", phone="+595991234568")
        s.add(c)
        s.commit()
        cid = c.id

    r = client.get(f"/clientes/{cid}")
    body = r.text
    assert "Productos frecuentes" not in body