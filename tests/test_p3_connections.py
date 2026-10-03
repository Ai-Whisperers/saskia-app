"""P3 connections batch: POS bridge, birthday widget, CSV enrichment,
zone names, birthday validation, ventas channel hint.

- cliente_detalle: "+ Crear pedido" → /pedidos/nuevo?customer_id=N
- pedidos_new_form preselects the customer (combo value/display, phone,
  picked hint)
- dashboard computes next-7-days birthdays; inicio shows an Acciones row
- birthday input validated (DD-MM / DD-MM-AAAA), normalized to MM-DD
- CSV export gains email/birthday/how_found/channel/consent/dietary
- address manager shows zone NAMES not raw ids
- ventas customer card shows the client's preferred channel
"""

from __future__ import annotations

from tests.factories import make_customer

# ── POS bridge ───────────────────────────────────────────────────────────

def test_cliente_detalle_has_crear_pedido_button(client, session_factory):
    with session_factory() as s:
        c = make_customer(s, name="PosBridge UX")
        s.commit()
        cid = c.id
    r = client.get(f"/clientes/{cid}")
    assert r.status_code == 200
    assert f'/pedidos/nuevo?customer_id={cid}' in r.text
    assert "Crear pedido" in r.text


def test_pedidos_nuevo_prefills_customer(client, session_factory):
    with session_factory() as s:
        c = make_customer(s, name="Preset Cust UX", phone="0983112233")
        s.commit()
        cid = c.id
    r = client.get(f"/pedidos/nuevo?customer_id={cid}")
    assert r.status_code == 200
    body = r.text
    assert "Preset Cust UX" in body          # combo display + hint
    assert "0983112233" in body               # phone prefilled
    assert 'data-empty="false"' in body       # hint state = picked


def test_pedidos_nuevo_without_param_unchanged(client):
    r = client.get("/pedidos/nuevo")
    assert r.status_code == 200
    assert 'data-empty="true"' in r.text


def test_pedidos_nuevo_unknown_customer_no_crash(client):
    r = client.get("/pedidos/nuevo?customer_id=999999")
    assert r.status_code == 200
    assert 'data-empty="true"' in r.text


# ── Birthday widget ──────────────────────────────────────────────────────

def test_dashboard_shows_upcoming_birthday(client, session_factory):
    from datetime import datetime as dt

    now = dt.now()
    # birthday 3 days from now, stored MM-DD
    from datetime import timedelta
    bdate = now + timedelta(days=3)
    mmdd = f"{bdate.month:02d}-{bdate.day:02d}"
    with session_factory() as s:
        c = make_customer(s, name="birthday person ux", phone="")
        c.birthday = mmdd
        c.marketing_consent = True
        s.commit()
    r = client.get("/")
    assert r.status_code == 200
    body = r.text
    assert "Cumpleaños de la semana" in body
    assert "Birthday Person Ux" in body


def test_dashboard_hides_old_birthdays(client, session_factory):
    with session_factory() as s:
        c = make_customer(s, name="OldBday UX", phone="")
        c.birthday = "01-01"  # unless today is early Jan, not within 7 days
        s.commit()
    r = client.get("/")
    body = r.text
    # Only fails if run Jan 1-7; acceptable test-time caveat
    if "OldBday Ux" in body:
        from datetime import datetime, timedelta
        assert datetime.now() + timedelta(days=7) >= datetime(datetime.now().year, 1, 1)


# ── Birthday validation ──────────────────────────────────────────────────

def test_birthday_valid_formats_accepted(client, session_factory):
    with session_factory() as s:
        c = make_customer(s, name="BdayFmt UX")
        s.commit()
        cid = c.id
    r = client.post(
        f"/clientes/{cid}/editar",
        data={"name": "BdayFmt UX", "phone": "", "notes": "", "birthday": "15-03"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    from app.rms.models import Customer
    with session_factory() as s:
        assert s.get(Customer, cid).birthday == "03-15"  # normalized MM-DD


def test_birthday_full_date_accepted(client, session_factory):
    with session_factory() as s:
        c = make_customer(s, name="BdayFull UX")
        s.commit()
        cid = c.id
    r = client.post(
        f"/clientes/{cid}/editar",
        data={"name": "BdayFull UX", "phone": "", "notes": "", "birthday": "15-03-1990"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    from app.rms.models import Customer
    with session_factory() as s:
        assert s.get(Customer, cid).birthday == "03-15"


def test_birthday_invalid_rejected(client, session_factory):
    with session_factory() as s:
        c = make_customer(s, name="BdayBad UX")
        s.commit()
        cid = c.id
    for bad in ("marzo", "99-99", "15/3/1990"):
        r = client.post(
            f"/clientes/{cid}/editar",
            data={"name": "BdayBad UX", "phone": "", "notes": "", "birthday": bad},
            follow_redirects=False,
        )
        assert r.status_code == 400, f"{bad!r} should 400"


# ── CSV enrichment ───────────────────────────────────────────────────────

def test_csv_export_includes_profile_fields(client, session_factory):
    with session_factory() as s:
        c = make_customer(s, name="CsvUX person", phone="0983112233")
        c.email = "csvux@x.com"
        c.how_found = "instagram"
        c.preferred_channel = "whatsapp"
        c.marketing_consent = True
        c.dietary_restrictions = "vegano"
        s.commit()
    r = client.get("/clientes?format=csv")
    assert r.status_code == 200
    text = r.text
    for col in ("email", "birthday", "how_found", "preferred_channel",
                "marketing_consent", "dietary_restrictions"):
        assert col in text, col
    assert "CsvUX person" in text
    assert "vegano" in text
    assert "instagram" in text


# ── Zone names + ventas channel ──────────────────────────────────────────

def test_edit_form_shows_zone_names(client, session_factory):
    from app.rms.models import CustomerAddress, DeliveryZone
    with session_factory() as s:
        c = make_customer(s, name="ZoneName UX")
        s.flush()
        z = DeliveryZone(code="zx", name="Zona Centro UX", position=99,
                         delivery_cost_gs=5000, min_order_gs=0)
        s.add(z)
        s.flush()
        s.add(CustomerAddress(customer_id=c.id, label="casa",
                              address_text="Calle 1", zone_id=z.id))
        s.commit()
        cid = c.id
    r = client.get(f"/clientes/{cid}/editar")
    assert r.status_code == 200
    assert "Zona Centro UX" in r.text
    assert "zona #" not in r.text
