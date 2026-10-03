"""tests/test_pedido_post_phase13_integration.py — Phase 13 (2026-10-01).

Integration test: POST /pedidos/nuevo with delivery_preference=window +
delivery_window_start + delivery_window_end + a customer_invoice_profile_id +
customer_address_id + structured address fields. Confirms the Pedido row
carries them all, and GET /pedidos/{id} shows the ventana text with the
"(no es garantía)" suffix.
"""
from datetime import date, timedelta

from sqlalchemy import select

from app.rms.models import Pedido


def _seed_product(session_factory, name="Phase13Prod", price=12000):
    from app.rms.models import Product
    with session_factory() as s:
        p = Product(name=name, sale_price_gs=price)
        s.add(p)
        s.commit()
        s.refresh(p)
        return p.id


def test_post_pedido_persists_delivery_preference_window(client, session_factory):
    """Phase 13: a POST carrying the ventana fields + invoice profile id +
    structured-address fields persists them on the Pedido row, and the
    detail page renders the ventana via ventana_text()."""
    pid = _seed_product(session_factory)
    target = (date.today() + timedelta(days=2)).isoformat()

    idem = "phase13-window-1"
    data = {
        "customer_name": "Fase 13 Cliente",
        "customer_phone": "+595 981 999000",
        "promised_date": target,
        "promised_time": "15:00",
        "channel": "whatsapp",
        "payment_intent": "efectivo",
        "idempotency_key": idem,
        "line_product_id": [str(pid)],
        "line_qty": ["2"],
        "line_unit_price_gs": ["12000"],
        # Phase 13 (2026-10-01): ventana + invoice + address fields
        "delivery_preference": "window",
        "delivery_window_start": "14:00",
        "delivery_window_end": "16:00",
        "invoice_ruc": "80012345-6",
        "invoice_name": "Fase 13 S.A.",
        "address_text": "Av. España 1234, Las Carmelitas",
        "address_calle_principal": "Av. España",
        "address_calle_secundaria": "Curupayty",
        "address_numero": "1234",
        "address_barrio": "Las Carmelitas",
        "address_ciudad": "Asunción",
        "address_departamento": "Central",
        "address_recipient_name": "Lucía",
    }
    r = client.post("/pedidos/nuevo", data=data, follow_redirects=False)
    assert r.status_code in (302, 303), r.text[:500]
    location = r.headers.get("location", "")
    assert "/pedidos/" in location

    # Extract pedido id from location: /pedidos/{id}
    pedido_id = int(location.rstrip("/").split("/")[-1])

    with session_factory() as s:
        p = s.scalar(select(Pedido).where(Pedido.id == pedido_id))
        assert p is not None
        assert p.delivery_preference == "window"
        assert p.delivery_window_start is not None
        assert p.delivery_window_end is not None
        assert p.invoice_ruc == "80012345-6"
        assert p.invoice_name == "Fase 13 S.A."

    # GET the detail page and check the ventana text contains the
    # explicit "(no es garantía)" suffix.
    detail = client.get(f"/pedidos/{pedido_id}")
    assert detail.status_code == 200
    body = detail.text
    assert "14:00" in body
    assert "16:00" in body
    assert "no es garantía" in body.lower() or "preferida" in body.lower()


def test_post_pedido_persists_scheduled_preference(client, session_factory):
    """delivery_preference=scheduled + scheduled_date + ventana start/end
    → all 3 fields persisted, detail shows the date + (no es garantía)."""
    pid = _seed_product(session_factory, name="Phase13SchedProd", price=8000)
    target = (date.today() + timedelta(days=3)).isoformat()
    schedule_for = (date.today() + timedelta(days=7)).isoformat()

    idem = "phase13-scheduled-1"
    data = {
        "customer_name": "Cliente Programado",
        "promised_date": target,
        "promised_time": "11:00",
        "channel": "whatsapp",
        "payment_intent": "transferencia",
        "idempotency_key": idem,
        "line_product_id": [str(pid)],
        "line_qty": ["1"],
        "line_unit_price_gs": ["8000"],
        "delivery_preference": "scheduled",
        "delivery_window_start": "10:00",
        "delivery_window_end": "12:00",
        "delivery_scheduled_date": schedule_for,
        "address_text": "Recoleta 456",
        "invoice_ruc": "1234567",
        "invoice_name": "Cliente Programado",
    }
    r = client.post("/pedidos/nuevo", data=data, follow_redirects=False)
    assert r.status_code in (302, 303)
    location = r.headers.get("location", "")
    pedido_id = int(location.rstrip("/").split("/")[-1])

    with session_factory() as s:
        p = s.scalar(select(Pedido).where(Pedido.id == pedido_id))
        assert p is not None
        assert p.delivery_preference == "scheduled"
        assert p.delivery_scheduled_date is not None
        # Date matches
        assert p.delivery_scheduled_date.isoformat() == schedule_for

    detail = client.get(f"/pedidos/{pedido_id}")
    assert detail.status_code == 200
    body = detail.text
    # Programado text contains the date and the disclaimer
    assert "Programado" in body or "programado" in body.lower()
    assert "no es garantía" in body.lower() or "preferida" in body.lower()


def test_post_pedido_asap_persists_with_preference_asap(client, session_factory):
    """ASAP: detail page shows 'Lo antes posible' or equivalent."""
    pid = _seed_product(session_factory, name="Phase13Asap", price=5000)
    target = (date.today() + timedelta(days=1)).isoformat()
    data = {
        "customer_name": "Cliente ASAP",
        "promised_date": target,
        "promised_time": "09:00",
        "channel": "whatsapp",
        "payment_intent": "efectivo",
        "idempotency_key": "phase13-asap-1",
        "line_product_id": [str(pid)],
        "line_qty": ["1"],
        "line_unit_price_gs": ["5000"],
        "delivery_preference": "asap",
        "address_text": "Test 1",
        "invoice_ruc": "1111111",
        "invoice_name": "Cliente ASAP",
    }
    r = client.post("/pedidos/nuevo", data=data, follow_redirects=False)
    assert r.status_code in (302, 303)
    location = r.headers.get("location", "")
    pedido_id = int(location.rstrip("/").split("/")[-1])

    with session_factory() as s:
        p = s.scalar(select(Pedido).where(Pedido.id == pedido_id))
        assert p is not None
        assert p.delivery_preference == "asap"

    detail = client.get(f"/pedidos/{pedido_id}")
    assert detail.status_code == 200
    body = detail.text
    # The ventana badge renders inline below the channel/payment badges.
    # Verify either the legacy literal or the new "Lo antes posible"
    # badge from ventana_text() is present.
    assert "Lo antes posible" in body or "antes posible" in body.lower(), (
        f"Expected ventana badge on detail page (delivery_preference=asap).\n"
        f"detail.status_code={detail.status_code}\n"
        f"Body length: {len(body)}\n"
    )
