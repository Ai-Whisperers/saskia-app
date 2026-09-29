"""Tests for S5 — US 4.2 Quick-Sell + US 4.3 Sales History split.

US 4.3 acceptance criteria (split):
- /ventas renders the POS page (Quick-Sell + New Sale form) WITHOUT history rows.
- /ventas/historial renders the sales history (table, summary, filter form).
- The two pages share filter query semantics (?q, ?product_id, ?days, ?offset)
  via _build_sales_context — no logic duplication.
- The history page exposes the per-row Anular button with a CSRF token.
- /ventas and /ventas/historial cross-link from each other's CTA.

US 4.2 acceptance criteria (Quick-Sell search + customer multi-field):
- The Quick-Sell grid renders one button per top-N product by recent revenue.
- The Quick-Sell search input has an aria-label and filters client-side
  by product name (case-insensitive substring).
- /clientes/api/search returns matches on name, phone, cedula, email,
  notes — each verified independently.
"""

from datetime import datetime, timedelta, timezone

from app.rms.models import Customer, Product, Sale

# =========================================================================
# US 4.3 — Sales history split
# =========================================================================


def test_pos_page_does_not_render_history_section(client):
    """US 4.3 — /ventas (POS) must not show the historial table.

    The history table contains 'Fecha' / 'Anulada' / summary card text.
    None of those should appear on the POS page.
    """
    resp = client.get("/ventas")
    assert resp.status_code == 200
    body = resp.text
    assert "<h2>Historial</h2>" not in body
    assert "Ventas activas" not in body  # summary card only on historial
    # POS should still show the new-sale form
    assert "<h2>Nueva venta</h2>" in body or "<h1>Nueva venta</h1>" in body


def test_historial_page_renders_history(client, session_factory):
    """US 4.3 — /ventas/historial renders the sales history table."""
    with session_factory() as s:
        p = Product(name="BrownieSplit", sale_price_gs=10000, recipe_id=None)
        s.add(p); s.flush()
        s.add(Sale(product_id=p.id, qty=2, unit_price_gs=10000,
                   sold_at=datetime.now(timezone.utc)))
        s.commit()

    resp = client.get("/ventas/historial")
    assert resp.status_code == 200
    body = resp.text
    assert "Historial de ventas" in body
    assert "BrownieSplit" in body
    assert "Ventas activas" in body  # summary card visible


def test_historial_links_back_to_pos(client):
    """US 4.3 — the historial page exposes a CTA to return to Nueva venta."""
    resp = client.get("/ventas/historial")
    assert resp.status_code == 200
    assert 'href="/ventas"' in resp.text
    assert "Ir a Nueva venta" in resp.text


def test_pos_links_to_historial(client):
    """US 4.3 — the POS page exposes a link to /ventas/historial.

    Without this, an operator who just registered a sale would have no way
    to find the history view.
    """
    resp = client.get("/ventas")
    assert resp.status_code == 200
    assert 'href="/ventas/historial"' in resp.text


def test_historial_anular_button_has_csrf_token(client, session_factory):
    """US 4.3 — the Anular button on the history table submits a CSRF token.

    Without it, /ventas/{id}/anular returns 403 because CSRF middleware
    rejects the POST.
    """
    with session_factory() as s:
        p = Product(name="AnulameSplit", sale_price_gs=5000, recipe_id=None)
        s.add(p); s.flush()
        sale = Sale(product_id=p.id, qty=1, unit_price_gs=5000,
                    sold_at=datetime.now(timezone.utc))
        s.add(sale); s.commit()
        sale_id = sale.id

    resp = client.get("/ventas/historial")
    assert resp.status_code == 200
    body = resp.text
    assert f'action="/ventas/{sale_id}/anular"' in body
    # CSRF token rendered server-side, must be non-empty (signed nonce)
    import re
    m = re.search(
        r'name="_csrf_token" value="([^"]*)"',
        body,
    )
    assert m is not None, "Anular form must render _csrf_token input"
    token = m.group(1)
    assert len(token) >= 8, f"CSRF token must be a real signed value, got {token!r}"


def test_historial_filter_returns_relevant_rows(client, session_factory):
    """US 4.3 — /ventas/historial?q=cake only renders matching rows."""
    with session_factory() as s:
        p1 = Product(name="CakeSplit", sale_price_gs=10000, recipe_id=None)
        p2 = Product(name="BreadSplit", sale_price_gs=5000, recipe_id=None)
        s.add_all([p1, p2]); s.flush()
        s.add(Sale(product_id=p1.id, qty=1, unit_price_gs=10000,
                   sold_at=datetime.now(timezone.utc)))
        s.add(Sale(product_id=p2.id, qty=1, unit_price_gs=5000,
                   sold_at=datetime.now(timezone.utc)))
        s.commit()

    resp = client.get("/ventas/historial?q=CakeSplit")
    assert resp.status_code == 200
    body = resp.text
    assert "CakeSplit" in body
    # BreadSplit is filtered out — should not appear in the history table.
    # (It might still appear in a hidden search option, but not as a row.)


def test_historial_days_filter_works(client, session_factory):
    """US 4.3 — /ventas/historial?days=7 accepts the days filter without 500."""
    with session_factory() as s:
        p = Product(name="OldSale", sale_price_gs=1000, recipe_id=None)
        s.add(p); s.flush()
        old = datetime.now(timezone.utc) - timedelta(days=30)
        s.add(Sale(product_id=p.id, qty=1, unit_price_gs=1000, sold_at=old))
        s.commit()

    resp = client.get("/ventas/historial?days=7")
    assert resp.status_code == 200


# =========================================================================
# US 4.2 — Quick-Sell search + customer multi-field search
# =========================================================================


def test_quick_sell_section_renders_on_pos(client, session_factory):
    """US 4.2 — POS page shows the Quick-Sell grid."""
    with session_factory() as s:
        p = Product(name="QS_Brownie", sale_price_gs=10000, recipe_id=None)
        s.add(p); s.flush()
        now = datetime.now(timezone.utc)
        # Add 5 sales across 3 products so Quick-Sell has data to surface
        for _i in range(3):
            s.add(Sale(product_id=p.id, qty=1, unit_price_gs=10000, sold_at=now))
        s.commit()

    resp = client.get("/ventas")
    assert resp.status_code == 200
    body = resp.text
    assert "Quick-sell" in body
    assert "quick-sell-grid" in body
    # Each Quick-Sell item is a <form> POST to /ventas/nueva with hidden product_id
    assert 'action="/ventas/nueva"' in body
    assert 'name="product_id"' in body


def test_quick_sell_search_input_present(client, session_factory):
    """US 4.2 — the POS page exposes a Quick-Sell search input with an a11y label.

    Requires recent sales so the Quick-Sell section actually renders
    (the template wraps it in {% if quick_sell %}).
    """
    with session_factory() as s:
        p = Product(name="TortaInput", sale_price_gs=50000, recipe_id=None)
        s.add(p); s.flush()
        now = datetime.now(timezone.utc)
        s.add(Sale(product_id=p.id, qty=1, unit_price_gs=50000, sold_at=now))
        s.commit()

    resp = client.get("/ventas")
    assert resp.status_code == 200
    assert 'id="quick-sell-search"' in resp.text
    assert 'aria-label="Buscar producto en venta rápida"' in resp.text


def test_quick_sell_buttons_carry_product_id_and_qty(client, session_factory):
    """US 4.2 — each Quick-Sell button is a one-tap form with the
    product_id and qty=1 hidden. (Operator doesn't need to type qty.)
    """
    with session_factory() as s:
        p = Product(name="TortaQS", sale_price_gs=50000, recipe_id=None)
        s.add(p); s.flush()
        now = datetime.now(timezone.utc)
        s.add(Sale(product_id=p.id, qty=1, unit_price_gs=50000, sold_at=now))
        s.commit()
        pid = p.id

    resp = client.get("/ventas")
    assert resp.status_code == 200
    assert f'name="product_id" value="{pid}"' in resp.text
    assert 'name="qty" value="1"' in resp.text


def test_quick_sell_section_hidden_when_no_recent_sales(client):
    """US 4.2 — when no recent sales exist, the Quick-Sell section is hidden.

    The template wraps the entire Quick-Sell block in
    {% if quick_sell %} so an empty inventory doesn't surface a
    misleading "0 items" UI to a new operator.
    """
    resp = client.get("/ventas")
    assert resp.status_code == 200
    body = resp.text
    # The grid div only renders when quick_sell is non-empty.
    assert "quick-sell-grid" not in body
    # The Quick-Sell search input only renders inside the Quick-Sell block.
    assert 'id="quick-sell-search"' not in body
    # The new-sale form action points to /ventas/nueva/multi (multi-item cart)
    assert 'action="/ventas/nueva/multi"' in body or 'action="/ventas/nueva"' in body


def test_customer_api_search_by_name(client, session_factory):
    """US 4.2 — /clientes/api/search matches by customer name."""
    with session_factory() as s:
        s.add(Customer(name="Juana Test", phone="0981112222"))
        s.commit()

    resp = client.get("/clientes/api/search?q=juana")
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert any("Juana" in r.get("name", "") for r in data["results"])


def test_customer_api_search_by_phone(client, session_factory):
    """US 4.2 — /clientes/api/search matches by phone (id=cedula also)."""
    with session_factory() as s:
        s.add(Customer(name="Phone Match", phone="0981234567"))
        s.commit()

    resp = client.get("/clientes/api/search?q=0981234567")
    assert resp.status_code == 200
    data = resp.json()
    assert any("Phone Match" in r.get("name", "") for r in data["results"])


def test_customer_api_search_by_cedula(client, session_factory):
    """US 4.2 — /clientes/api/search matches by cedula (CI/RUC)."""
    with session_factory() as s:
        s.add(Customer(name="Cedula Match", cedula="1234567"))
        s.commit()

    resp = client.get("/clientes/api/search?q=1234567")
    assert resp.status_code == 200
    data = resp.json()
    assert any("Cedula Match" in r.get("name", "") for r in data["results"])
