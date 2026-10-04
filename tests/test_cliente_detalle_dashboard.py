"""P0-P2 fixes from the Gemini UX review of cliente_detalle.

P0: `s.product_name` never existed on Sale → Jinja Undefined → EVERY
history row rendered "(eliminado)". Route now decorates history with the
live product name (or "(eliminado #id)" when the product was hard-deleted).

P0: page rebuilt as a 2-column dashboard (contact/notes/activity left,
KPIs + history right).

P1: quantities render as ints when whole (2 not 2.00; 0.5 stays 0.5).

P2: client name title-cased in h1 + breadcrumb.
"""
# allow-hardcoded-dates: fixed instants required for deterministic ordering/TZ assertions

from __future__ import annotations

from datetime import datetime

from tests.factories import make_customer, make_product


def _seed_sale(session, customer_id, product_id, qty=1.0, price=15000):
    from app.rms.models import Sale

    sale = Sale(
        product_id=product_id,
        customer_id=customer_id,
        qty=qty,
        unit_price_gs=price,
        sold_at=datetime(2026, 9, 15, 12, 0),
        discount_gs=0,
    )
    session.add(sale)
    return sale


def test_history_shows_live_product_name(client, session_factory):
    """P0: an existing product's name renders — not '(eliminado)'."""
    with session_factory() as s:
        c = make_customer(s, name="histName UX")
        s.flush()
        p = make_product(s, name="Torta HistName UX")
        s.flush()
        _seed_sale(s, c.id, p.id)
        s.commit()
        cid = c.id
    r = client.get(f"/clientes/{cid}")
    assert r.status_code == 200
    body = r.text
    assert "Torta HistName UX" in body
    assert "(eliminado)" not in body


def test_history_decorator_fallback_unit():
    """P0 defense: decorate_history falls back to '(eliminado #id)' when a
    Sale's product relationship loads None. FK constraints make a real
    orphan near-impossible; drive the helper with a fake orphan sale."""
    from types import SimpleNamespace

    from app.rms.customers import decorate_history

    fake = SimpleNamespace(
        product=None,
        product_id=999999,
        qty=1,
        unit_price_gs=9000,
        voided_at=None,
        sold_at=datetime(2026, 9, 16, 9, 0),
    )
    view = decorate_history(None, [fake])
    assert view[0]["product_name"] == "(eliminado #999999)"
    assert view[0]["product_exists"] is False


def test_quantities_render_as_integers(client, session_factory):
    """P1: whole quantities show without decimals; fractional kept."""
    with session_factory() as s:
        c = make_customer(s, name="QtyInt UX")
        s.flush()
        p = make_product(s, name="QtyProd UX")
        s.flush()
        _seed_sale(s, c.id, p.id, qty=2)
        _seed_sale(s, c.id, p.id, qty=0.5)
        s.commit()
        cid = c.id
    r = client.get(f"/clientes/{cid}")
    assert r.status_code == 200
    body = r.text
    assert "2.00" not in body
    assert ">2<" in body or ">2 </td>" in body or ">2<" in body
    assert "0.5" in body  # fractional survives


def test_name_title_cased(client, session_factory):
    """P2: lowercase names render Title Case in h1 + breadcrumb."""
    with session_factory() as s:
        c = make_customer(s, name="kyrian weiss")
        s.commit()
        cid = c.id
    r = client.get(f"/clientes/{cid}")
    assert r.status_code == 200
    body = r.text
    assert "Kyrian Weiss" in body
    assert ">kyrian weiss<" not in body


def test_layout_two_column_dashboard(client, session_factory):
    """P0: page uses the 1fr/2fr dashboard grid with contact card left,
    KPI strip + history right."""
    with session_factory() as s:
        c = make_customer(s, name="LayoutDash UX", phone="0983112233")
        s.commit()
        cid = c.id
    r = client.get(f"/clientes/{cid}")
    assert r.status_code == 200
    body = r.text
    # T-2026-10-01: page now uses semantic class cliente-detalle-grid
    assert "cliente-detalle-grid" in body
    assert "grid-template-columns:1fr 2fr" in body
    assert ">Contacto<" in body
    assert ">Notas<" in body
    assert ">Gasto total<" in body
    assert ">Visitas<" in body
    assert ">Puntos<" in body
    assert "Historial de compras" in body
    # old flat <dl class="customer-meta"> layout is gone
    assert 'class="customer-meta"' not in body
    # dietary alert still present when set
    c2 = None
    with session_factory() as s:
        from tests.factories import make_customer as mc

        c2 = mc(s, name="DietAlert LayoutDash")
        c2.dietary_restrictions = "sin lactosa"
        s.commit()
        cid2 = c2.id
    r2 = client.get(f"/clientes/{cid2}")
    assert "Perfil dietético" in r2.text
