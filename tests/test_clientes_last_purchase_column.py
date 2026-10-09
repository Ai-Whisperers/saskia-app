"""Test T-7: clientes.html - add email + última compra columns."""

from app.rms.models import Customer


def test_clientes_page_shows_new_columns(authed_client, session_factory):
    """T-7 — /clientes shows Email and Última compra columns."""
    with session_factory() as s:
        s.add(Customer(name="T7-Test", phone="0981234567", email="t7@test.com"))
        s.commit()

    r = authed_client.get("/clientes")
    assert r.status_code == 200
    assert "Email" in r.text, "T-7 missing: Email column header"
    assert "Última compra" in r.text, "T-7 missing: Última compra column header"


def test_clientes_shows_nunca_compro_fallback(authed_client, session_factory):
    """T-7 — customers with no sales show 'Nunca compró' fallback."""
    with session_factory() as s:
        s.add(Customer(name="T7-NoSales", phone="0981234567", email="x@y.com"))
        s.commit()

    r = authed_client.get("/clientes")
    assert r.status_code == 200
    assert "Nunca compró" in r.text, (
        "T-7 missing: 'Nunca compró' fallback text for unsold customers"
    )
