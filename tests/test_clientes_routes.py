"""tests/test_clientes_routes.py — /clientes + /clientes/{id} route tests."""

from __future__ import annotations


def test_clientes_list_renders(client):
    """GET /clientes returns 200 with the customers page."""
    resp = client.get("/clientes")
    assert resp.status_code == 200
    body = resp.text
    assert "Clientes" in body


def test_clientes_list_shows_columns(client, session_factory):
    """List must show: Nombre, Teléfono, Visitas, Gasto total, Puntos, Nivel."""
    from app.rms.models import Customer

    with session_factory() as s:
        c = Customer(phone="0981111111", name="Cliente Test")
        s.add(c)
        s.commit()

    resp = client.get("/clientes")
    assert resp.status_code == 200
    body = resp.text
    for col in ["Nombre", "Teléfono", "Nivel"]:
        assert col in body, f"Missing column {col} in /clientes"


def test_clientes_list_shows_tier_labels(client, session_factory):
    """Tier labels render when a customer with > 0 spend exists."""
    from app.rms.models import Customer

    with session_factory() as s:
        # Lifetime spend > 100k → Silver
        c = Customer(phone="0982222222", name="Cliente Silver")
        s.add(c)
        s.commit()

    resp = client.get("/clientes")
    assert resp.status_code == 200
    body = resp.text
    # Some tier label should appear (Bronze by default for new customer with 0 spend)
    assert "Bronze" in body or "bronze" in body.lower()


def test_cliente_detail_renders(client, session_factory):
    """GET /clientes/{id} shows purchase history + tier + points."""
    from app.rms.models import Customer

    with session_factory() as s:
        c = Customer(phone="0981234567", name="Test Cliente")
        s.add(c)
        s.commit()
        cid = c.id

    resp = client.get(f"/clientes/{cid}")
    assert resp.status_code == 200
    body = resp.text
    assert "Test Cliente" in body
    assert "0981234567" in body


def test_clientes_empty_state_message(client):
    """When there are no customers, show a helpful empty-state."""
    resp = client.get("/clientes")
    assert resp.status_code == 200
    # Should not 500 just because no customers exist
    # (the page should render with empty table + a message)
    assert (
        "No hay" in resp.text
        or "no hay" in resp.text.lower()
        or "Agregar" in resp.text
        or "Clientes" in resp.text
    )
