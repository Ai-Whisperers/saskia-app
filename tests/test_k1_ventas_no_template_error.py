"""K1: /ventas must NOT raise TemplateRuntimeError.

The 2026-09-22 outage: GET /ventas returned 500 with `TemplateRuntimeError`
because the template referenced `s.customer_id` but `_decorated()` didn't
include it. Plus several other template-render issues surfaced from missing
context variables.

This test loads /ventas with three different DB states:
- Empty (no products, no sales)
- One product, no sales
- Many products + sales (the live case)

Each must return 200 with no TemplateRuntimeError.
"""
from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import text


def test_ventas_loads_with_empty_db(client, session_factory):
    """K1 #1: /ventas must render even with zero products + zero sales."""
    # DB is fresh — no products, no sales
    r = client.get("/ventas")
    assert r.status_code == 200, (
        f"/ventas on empty DB returned {r.status_code}: {r.text[:200]}"
    )


def test_ventas_loads_with_one_product_no_sales(client, session_factory):
    """K1 #2: /ventas must render with a product but no sales yet."""
    from app.rms.models import Product
    with session_factory() as s:
        p = Product(
            name="K1 Test Pan",
            portion_label="1 und",
            sale_price_gs=5000,
            is_available=True,
        )
        s.add(p)
        s.commit()

    r = client.get("/ventas")
    assert r.status_code == 200, (
        f"/ventas with 1 product returned {r.status_code}: {r.text[:200]}"
    )


def test_ventas_loads_with_many_products_and_sales(client, session_factory):
    """K1 #3: /ventas must render with the realistic live data shape.

    Mimics the live DB: many products, many sales, some voided.
    """
    from datetime import datetime, timedelta, timezone
    from app.rms.models import Product, Sale

    with session_factory() as s:
        for i in range(5):
            p = Product(
                name=f"K1 Product {i}",
                portion_label="1 und",
                sale_price_gs=5000 + i * 1000,
                is_available=True,
            )
            s.add(p)
        s.commit()

        with session_factory() as s2:
            products = s2.execute(text("SELECT id FROM product")).fetchall()
            for pid_row in products[:5]:
                pid = pid_row[0]
                for j in range(3):
                    sale = Sale(
                        product_id=pid,
                        qty=1,
                        unit_price_gs=5000,
                        sold_at=datetime.now(timezone.utc) - timedelta(days=j),
                    )
                    s2.add(sale)
                # One voided sale
                s2.add(Sale(
                    product_id=pid,
                    qty=1,
                    unit_price_gs=5000,
                    sold_at=datetime.now(timezone.utc),
                    voided_at=datetime.now(timezone.utc),
                ))
            s2.commit()

    r = client.get("/ventas")
    assert r.status_code == 200, (
        f"/ventas with realistic data returned {r.status_code}: {r.text[:200]}"
    )
    # Body should contain the ventas page title
    body = r.text
    assert "Ventas" in body or "ventas" in body


def test_ventas_loads_with_filter_query(client, session_factory):
    """K1 #4: /ventas must accept ?q=, ?product_id=, ?days= filters without 500."""
    from app.rms.models import Product
    with session_factory() as s:
        p = Product(
            name="K1 Filtered",
            portion_label="1 und",
            sale_price_gs=5000,
            is_available=True,
        )
        s.add(p)
        s.commit()

    # All three filter forms
    for params in ["", "?q=Test", "?product_id=1", "?days=7", "?days=30&product_id=1"]:
        r = client.get(f"/ventas{params}")
        assert r.status_code == 200, (
            f"/ventas{params} returned {r.status_code}: {r.text[:200]}"
        )


def test_ventas_loads_with_customer_attached_to_sale(client, session_factory):
    """K1 #5: regression for the 2026-09-22 production TemplateRuntimeError.

    The original outage: /ventas returned 500 because ventas.html referenced
    `s.customer_id` on each sale row, but `_decorated()` in
    app/routers/sales.py did not include that key. With a customer attached
    to the sale the template tries to render the customer name + phone AND
    use customer_id as the data-copy attribute; a missing key on the dict
    blows up the template.

    This test ensures that with the realistic shape (customer set, channel
    set, payment_method set, discount non-zero, voided sale present),
    /ventas still renders 200.
    """
    from datetime import datetime, timedelta, timezone

    from app.rms.models import Customer, Product, Sale

    with session_factory() as s:
        c = Customer(name="Cliente K1", phone="0981123456")
        s.add(c)
        s.commit()
        s.refresh(c)

        for i in range(3):
            p = Product(
                name=f"K1 Cust Product {i}",
                portion_label="1 und",
                sale_price_gs=5000 + i * 1000,
                is_available=True,
            )
            s.add(p)
        s.commit()

        with session_factory() as s2:
            products = s2.execute(text("SELECT id FROM product")).fetchall()
            for pid_row in products[:3]:
                pid = pid_row[0]
                # Full real-data shape: customer + channel + payment + discount
                s2.add(Sale(
                    product_id=pid,
                    qty=1.5,
                    unit_price_gs=7500,
                    customer_id=c.id,
                    payment_method="efectivo",
                    discount_gs=500,
                    channel="mostrador",
                    notes="nota test",
                    sold_at=datetime.now(timezone.utc) - timedelta(days=1),
                ))
                # Voided sale with different channel/payment
                s2.add(Sale(
                    product_id=pid,
                    qty=1,
                    unit_price_gs=7500,
                    customer_id=c.id,
                    payment_method="qr",
                    discount_gs=0,
                    channel="whatsapp",
                    sold_at=datetime.now(timezone.utc),
                    voided_at=datetime.now(timezone.utc),
                ))
            s2.commit()

    r = client.get("/ventas")
    assert r.status_code == 200, (
        f"/ventas with realistic data returned {r.status_code}: {r.text[:400]}"
    )
    # Body should contain every populated field — if any Jinja2 attribute is
    # missing the render fails BEFORE this assertion.
    body = r.text
    assert "Cliente K1" in body
    assert "efectivo" in body
    assert "qr" in body
    assert "whatsapp" in body
    assert "mostrador" in body


def test_ventas_recibo_loads_with_full_data(client, session_factory):
    """K1 #6: /ventas/{id}/recibo uses the SAME _decorated dict — must not 500.

    Catches the same regression as test_5 but at the recibo endpoint that
    also feeds on _decorated.
    """
    from datetime import datetime, timezone

    from app.rms.models import Customer, Product, Sale

    with session_factory() as s:
        c = Customer(name="Cliente Recibo", phone="0981999888")
        s.add(c)
        s.commit()
        s.refresh(c)

        p = Product(
            name="Recibo K1 Product",
            portion_label="1 und",
            sale_price_gs=12000,
            is_available=True,
        )
        s.add(p)
        s.commit()
        s.refresh(p)

        sale = Sale(
            product_id=p.id,
            qty=2,
            unit_price_gs=12000,
            customer_id=c.id,
            payment_method="tarjeta",
            discount_gs=1000,
            channel="mostrador",
            notes="recibo test",
            sold_at=datetime.now(timezone.utc),
        )
        s.add(sale)
        s.commit()
        s.refresh(sale)
        sale_id = sale.id

    r = client.get(f"/ventas/{sale_id}/recibo")
    assert r.status_code == 200, (
        f"/ventas/{sale_id}/recibo returned {r.status_code}: {r.text[:400]}"
    )
    assert "Recibo K1 Product" in r.text
    assert "Cliente Recibo" in r.text or "0981999888" in r.text


def test_decorated_covers_every_template_attribute_reference():
    """K1 #7: structural invariant — every {{ s.X }} in ventas.html & recibo.html
    must map to a key in _decorated(s).

    This is the LOCALIZABLE check the audit asked for. If a future template
    edit adds `{{ s.user_id }}` (or any other field) without updating
    _decorated, this test fails FIRST — before a 500 hits production.

    Why scan both templates: both feed from _decorated. The /ventas page
    iterates `sales` (loop var `s`); the /ventas/{id}/recibo page passes
    a single `sale` dict. Both must agree on the key set.
    """
    import re
    from pathlib import Path

    from app.routers.sales import _decorated

    repo_root = Path(__file__).resolve().parents[1]
    ventas_html = (repo_root / "app/templates/ventas.html").read_text()
    recibo_html = (repo_root / "app/templates/recibo.html").read_text()

    def find_loop_refs(html: str, loop_var: str) -> set[str]:
        """Return every `<loop_var>.X` reference inside its for-loop block."""
        m = re.search(r"\{%\s*for\s+" + loop_var + r"\s+in\s+", html)
        if not m:
            return set()
        start = m.start()
        depth = 0
        i = start
        while i < len(html):
            if html[i:i+2] == "{%":
                end_pct = html.find("%}", i + 2)
                if end_pct == -1:
                    break
                tag = html[i + 2:end_pct].strip()
                if tag.startswith("for ") or tag.startswith("if "):
                    depth += 1
                elif tag in ("endfor", "endif"):
                    depth -= 1
                    if depth == 0:
                        break
                i = end_pct + 2
            else:
                i += 1
        end = i + len("{% endfor %}")
        block = html[start:end]
        return set(re.findall(r"\b" + re.escape(loop_var) + r"\.([a-zA-Z_][a-zA-Z0-9_]*)", block))

    ventas_refs = find_loop_refs(ventas_html, "s")
    recibo_refs = find_loop_refs(recibo_html, "sale")

    # Build the dict via _decorated() with a fake Sale to enumerate keys.
    # We don't have a real Sale row here — easier: import the source and
    # inspect the literal dict by calling _decorated with a stub.
    class _Stub:
        pass

    def _stub_sale():
        s = _Stub()
        # Attributes referenced by _decorated source.
        s.id = 1
        s.sold_at = datetime(2026, 1, 1, 12, 0, 0)
        s.product_id = 1
        s.product = _Stub()
        s.product.name = "stub product"
        s.qty = 1.0
        s.unit_price_gs = 1000
        s.notes = None
        s.voided_at = None
        s.customer_id = None
        s.customer = None  # _decorated reads `s.customer.phone if s.customer else None`
        s.payment_method = None
        s.discount_gs = 0
        s.channel = "mostrador"
        return s

    keys = set(_decorated(_stub_sale()).keys())

    missing = (ventas_refs | recibo_refs) - keys
    assert not missing, (
        "Template references fields NOT in _decorated(s). "
        f"Missing: {sorted(missing)}. "
        f"_decorated keys: {sorted(keys)}. "
        f"ventas.html refs: {sorted(ventas_refs)}. "
        f"recibo.html refs: {sorted(recibo_refs)}."
    )
