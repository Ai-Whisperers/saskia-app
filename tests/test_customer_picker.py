"""tests/test_customer_picker.py — /clientes/api/{search,create} + picker UI.

Covers the customer-picker overhaul on /ventas:

- GET /clientes/api/search returns matches by name, phone, email, cedula, notes
  (case-insensitive substring via SQL `or_` + `ilike`).
- GET /clientes/api/search respects limit and returns empty on no match.
- POST /clientes/api/create persists with name required (422 if missing).
- POST /clientes/api/create is idempotent on phone duplicate.
- POST /clientes/api/create stores cedula when provided.
- Sale POST handler accepts customer_id (instead of customer_phone) and links
  the picked customer to the new Sale row.
- /ventas page renders the picker component.
"""
from __future__ import annotations

from sqlalchemy import select

from app.rms.models import Customer, Product, Sale

# --- /clientes/api/search ---


def test_api_search_matches_by_name(client, session_factory):
    with session_factory() as s:
        s.add(Customer(name="María González", phone="+595981000001"))
        s.add(Customer(name="Pedro Pérez", phone="+595981000002"))
        s.commit()

    resp = client.get("/clientes/api/search", params={"q": "maría"})
    assert resp.status_code == 200
    data = resp.json()
    names = [r["name"] for r in data["results"]]
    assert "María González" in names
    assert "Pedro Pérez" not in names
    # Picked customer has the hint field populated
    picked = next(r for r in data["results"] if r["name"] == "María González")
    assert "hint" in picked
    assert "María González" in picked["hint"]


def test_api_search_matches_by_phone(client, session_factory):
    with session_factory() as s:
        s.add(Customer(name="A", phone="+595981111111"))
        s.add(Customer(name="B", phone="+595982222222"))
        s.commit()

    resp = client.get("/clientes/api/search", params={"q": "5959811"})
    assert resp.status_code == 200
    data = resp.json()
    assert any(r["phone"] == "+595981111111" for r in data["results"])
    assert not any(r["phone"] == "+595982222222" for r in data["results"])


def test_api_search_matches_by_cedula(client, session_factory):
    with session_factory() as s:
        s.add(Customer(name="Cliente CI", phone="+595981000010", cedula="1234567"))
        s.add(Customer(name="Otra persona", phone="+595981000011", cedula="7654321"))
        s.commit()

    resp = client.get("/clientes/api/search", params={"q": "1234567"})
    assert resp.status_code == 200
    data = resp.json()
    assert any(r["cedula"] == "1234567" for r in data["results"])
    assert not any(r["cedula"] == "7654321" for r in data["results"])


def test_api_search_matches_by_email_substring(client, session_factory):
    with session_factory() as s:
        s.add(Customer(name="Con Email", phone="+595981000020",
                       email="maria.gonzalez@example.com"))
        s.add(Customer(name="Sin Match", phone="+595981000021",
                       email="otro@elsewhere.com"))
        s.commit()

    resp = client.get("/clientes/api/search", params={"q": "gonzalez"})
    assert resp.status_code == 200
    data = resp.json()
    assert any(r["name"] == "Con Email" for r in data["results"])
    assert not any(r["name"] == "Sin Match" for r in data["results"])


def test_api_search_matches_by_notes(client, session_factory):
    with session_factory() as s:
        s.add(Customer(name="VIP cliente", phone="+595981000030",
                       notes="Cumpleaños en noviembre"))
        s.add(Customer(name="Regular", phone="+595981000031"))
        s.commit()

    resp = client.get("/clientes/api/search", params={"q": "noviembre"})
    assert resp.status_code == 200
    data = resp.json()
    assert any(r["name"] == "VIP cliente" for r in data["results"])


def test_api_search_respects_limit(client, session_factory):
    with session_factory() as s:
        for i in range(15):
            s.add(Customer(name=f"Cliente {i:02d}", phone=f"+59598200000{i:02d}"))
        s.commit()

    resp = client.get("/clientes/api/search", params={"q": "Cliente", "limit": 5})
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 5
    assert len(data["results"]) == 5


def test_api_search_returns_empty_for_no_match(client, session_factory):
    with session_factory() as s:
        s.add(Customer(name="Algo", phone="+595981000099"))
        s.commit()

    resp = client.get("/clientes/api/search", params={"q": "zzzz-no-existe"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 0
    assert data["results"] == []


def test_api_search_empty_q_returns_recent(client, session_factory):
    """Empty query returns most-recent customers (so the picker isn't blank)."""
    with session_factory() as s:
        s.add(Customer(name="Viejo", phone="+595981000050"))
        s.add(Customer(name="Reciente", phone="+595981000051"))
        s.commit()

    resp = client.get("/clientes/api/search", params={"q": ""})
    assert resp.status_code == 200
    data = resp.json()
    # Both should be in the default limit
    assert data["count"] == 2


# --- /clientes/api/create ---


def test_api_create_creates_customer_with_name_required(client, session_factory):
    resp = client.post(
        "/clientes/api/create",
        json={"name": "Cliente Nuevo"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["created"] is True
    assert isinstance(data["id"], int) and data["id"] > 0
    assert data["customer"]["name"] == "Cliente Nuevo"

    # Verify it's in the DB
    with session_factory() as s:
        c = s.execute(select(Customer).where(Customer.id == data["id"])).scalar_one()
        assert c.name == "Cliente Nuevo"


def test_api_create_returns_422_when_name_missing(client):
    resp = client.post("/clientes/api/create", json={"phone": "+595981000200"})
    assert resp.status_code == 422


def test_api_create_with_phone_duplicate_is_idempotent(client, session_factory):
    """If a customer with the same phone exists, return that row instead of duplicating."""
    # Seed
    with session_factory() as s:
        existing = Customer(name="Existente", phone="+595981000300")
        s.add(existing)
        s.commit()
        existing_id = existing.id

    # Create via API with same phone
    resp = client.post(
        "/clientes/api/create",
        json={"name": "Otro Nombre", "phone": "+595981000300"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == existing_id

    # No duplicate row
    with session_factory() as s:
        rows = s.execute(
            select(Customer).where(Customer.phone == "+595981000300")
        ).scalars().all()
        assert len(rows) == 1


def test_api_create_stores_cedula(client, session_factory):
    resp = client.post(
        "/clientes/api/create",
        json={"name": "Con Cedula", "cedula": "4567890"},
    )
    assert resp.status_code == 200
    data = resp.json()
    new_id = data["id"]
    with session_factory() as s:
        c = s.execute(select(Customer).where(Customer.id == new_id)).scalar_one()
        assert c.cedula == "4567890"


def test_api_create_with_full_form_data(client, session_factory):
    resp = client.post(
        "/clientes/api/create",
        json={
            "name": "Full Test",
            "phone": "+595981000400",
            "email": "test@example.com",
            "cedula": "1112223334",
            "notes": "Cliente de prueba",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    cust = data["customer"]
    assert cust["name"] == "Full Test"
    assert cust["phone"] == "+595981000400"
    assert cust["email"] == "test@example.com"
    assert cust["cedula"] == "1112223334"
    assert cust["notes"] == "Cliente de prueba"


def test_api_create_returns_hint_and_stats(client, session_factory):
    """Created customer payload includes hint + lifetime stats."""
    resp = client.post(
        "/clientes/api/create",
        json={"name": "Cliente Stats"},
    )
    assert resp.status_code == 200
    cust = resp.json()["customer"]
    assert "hint" in cust
    assert "n_sales" in cust
    assert "lifetime_label" in cust
    assert cust["n_sales"] == 0


# --- /ventas POST + customer_id linking ---


def test_ventas_post_links_customer_id(client, session_factory):
    """POST /ventas/nueva with customer_id links the picked customer to the Sale."""
    with session_factory() as s:
        prod = Product(name="Croissant", sale_price_gs=12000, recipe_id=None)
        s.add(prod)
        s.flush()
        cust = Customer(name="Cliente Venta", phone="+595981000500")
        s.add(cust)
        s.commit()
        product_id = prod.id
        customer_id = cust.id

    resp = client.post(
        "/ventas/nueva",
        data={
            "product_id": str(product_id),
            "qty": "1",
            "customer_id": str(customer_id),
        },
        follow_redirects=False,
    )
    assert resp.status_code in (303, 302), resp.text

    with session_factory() as s:
        sale = s.execute(select(Sale).where(Sale.product_id == product_id)).scalar_one()
        assert sale.customer_id == customer_id


def test_ventas_post_without_customer_id_still_works(client, session_factory):
    """Picking a customer is optional — sales without a customer still work."""
    with session_factory() as s:
        prod = Product(name="Sin Cliente", sale_price_gs=5000, recipe_id=None)
        s.add(prod)
        s.commit()
        product_id = prod.id

    resp = client.post(
        "/ventas/nueva",
        data={"product_id": str(product_id), "qty": "1"},
        follow_redirects=False,
    )
    assert resp.status_code in (303, 302), resp.text

    with session_factory() as s:
        sale = s.execute(select(Sale).where(Sale.product_id == product_id)).scalar_one()
        assert sale.customer_id is None


def test_ventas_post_with_bad_customer_id_returns_422(client, session_factory):
    """A stale / fake customer_id must NOT silently create a new customer."""
    with session_factory() as s:
        prod = Product(name="Test", sale_price_gs=5000, recipe_id=None)
        s.add(prod)
        s.commit()
        product_id = prod.id

    resp = client.post(
        "/ventas/nueva",
        data={"product_id": str(product_id), "qty": "1", "customer_id": "999999"},
        follow_redirects=False,
    )
    assert resp.status_code == 422


# --- /ventas page smoke ---


def test_ventas_page_renders_customer_picker(client):
    """/ventas page includes the customer picker component."""
    resp = client.get("/ventas")
    assert resp.status_code == 200
    body = resp.text
    for marker in [
        "customer_picker_trigger",
        "customer_id",
        "customer_picker_label",
        "customer_picker_hint",
        "customer_picker_search",
        "customer_picker_results",
        "customer_picker_new_btn",
    ]:
        assert marker in body, f"Picker marker {marker!r} not found in /ventas"


def test_ventas_page_includes_picker_js(client):
    """/ventas page references the picker script."""
    resp = client.get("/ventas")
    assert resp.status_code == 200
    body = resp.text
    assert "customer-picker.js" in body


def test_picker_js_is_served(client):
    """The picker JS bundle is reachable at /static/customer-picker.js."""
    resp = client.get("/static/customer-picker.js")
    assert resp.status_code == 200
    body = resp.text
    assert "/clientes/api/search" in body
    assert "/clientes/api/create" in body
    assert "SaskiaCustomerPicker" in body


# --- All endpoints return JSON correctly with the expected schema ---


def test_api_search_payload_shape(client, session_factory):
    with session_factory() as s:
        s.add(Customer(
            name="Shape Test", phone="+595981000600",
            email="shape@test.com", cedula="9999",
        ))
        s.commit()

    resp = client.get("/clientes/api/search", params={"q": "Shape"})
    assert resp.status_code == 200
    data = resp.json()
    assert set(data.keys()) == {"results", "count"}
    r = data["results"][0]
    expected_keys = {
        "id", "name", "phone", "email", "cedula", "notes",
        "loyalty_points", "n_sales", "lifetime_spend_gs",
        "lifetime_label", "tier", "hint",
    }
    assert expected_keys.issubset(r.keys()), f"Missing keys: {expected_keys - r.keys()}"


def test_api_create_payload_shape(client):
    resp = client.post("/clientes/api/create", json={"name": "Shape Create"})
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert "created" in data
    assert "customer" in data
    assert "hint" in data["customer"]
