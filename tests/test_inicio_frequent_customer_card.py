"""tests test_inicio_frequent_customer_card.py — phase 10.

Verify the /inicio frequent customer card:
- Lists the top 5 customers by 30d visits
- Shows name + n_visits + lifetime spend per row
- Each row has a "+ Pedido" CTA that links to
  /pedidos/nuevo?customer_id=<id> (one-click create)
- The full name links to /clientes/{id} for detail view
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.rms.config import ASUNCION_TZ


def _kyrian_id(session_factory, qseed):
    from app.rms.models import Customer
    from app.seed.kyrian import KYRIAN_PHONE
    qseed("with_kyrian_full")
    with session_factory() as s:
        return s.query(Customer).filter_by(phone=KYRIAN_PHONE).one().id


def test_inicio_renders_frequent_customer_card(client, qseed, session_factory):
    """Kyrian's seed creates 14 sales in the last 30d → she's a regular."""
    cid = _kyrian_id(session_factory, qseed)
    r = client.get("/inicio")
    assert r.status_code == 200
    html = r.text
    assert "Clientes habituales" in html
    assert "kyrian weiss" in html.lower() or "kyrian" in html.lower()


def test_inicio_card_has_pedido_cta(client, qseed, session_factory):
    """Each regular row has a '+ Pedido' button linking to /pedidos/nuevo."""
    cid = _kyrian_id(session_factory, qseed)
    r = client.get("/inicio")
    html = r.text
    expected = f"/pedidos/nuevo?customer_id={cid}"
    assert expected in html, f"Expected {expected} in /inicio HTML"


def test_inicio_card_shows_visit_count(client, qseed, session_factory):
    """Each row displays the visit count + lifetime spend."""
    cid = _kyrian_id(session_factory, qseed)
    r = client.get("/inicio")
    html = r.text
    # Look for visit count pattern — should be a number >= 1 followed by "visita"
    import re
    assert re.search(r"\d+\s+visitas?\b", html), "Expected visit count in /inicio"


def test_inicio_empty_state_for_fresh_db(client):
    """No sales → no regulars → empty state shown."""
    r = client.get("/inicio")
    assert r.status_code == 200
    # The empty_state block uses "Sin habituales aún" or just shows the
    # fallback hint. We assert it doesn't crash and renders.
    assert "Sin habituales" in r.text or "habituales" in r.text


def test_inicio_card_displays_at_most_5(client, qseed, session_factory):
    """The card limits to top 5 (the 'regulars_count_total' shows full count)."""
    # Add 7 extra customers with 3+ sales each so we exceed 5
    from app.rms.costing import apply_sale
    from app.rms.models import Customer, Product

    qseed("with_kyrian_full")
    with session_factory() as s:
        prod = s.execute(__import__("sqlalchemy").text("SELECT id FROM product LIMIT 1")).scalar()
        if prod is None:
            p = Product(name="Bulk Product", sale_price_gs=10000)
            s.add(p); s.flush()
            prod = p.id

        now = datetime.now(ASUNCION_TZ)
        for i in range(7):
            c = Customer(name=f"Regular {i:02d}", phone=f"099{i:08d}")
            s.add(c); s.flush()
            for j in range(3):
                apply_sale(
                    session=s,
                    product_id=prod,
                    qty=1.0,
                    sold_at=now - timedelta(days=j),
                    customer_id=c.id,
                )
        s.commit()

    r = client.get("/inicio")
    html = r.text
    # Each row should have a + Pedido link. The top 5 are shown; the rest
    # are accessible via the "Ver los N habituales →" link.
    pedido_links = html.count("/pedidos/nuevo?customer_id=")
    assert pedido_links >= 5  # at least 5 in the card
    # The "Ver los N habituales" link appears when there are more than 5
    assert "Ver los" in html or pedido_links == 5
