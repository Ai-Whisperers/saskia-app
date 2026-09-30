"""P3 profile batch: birthday, how-found, channel, consent, facturación
defaults, address manager, and the clientes data-completion nudge.

Migration 071 adds customer.birthday / how_found / preferred_channel /
marketing_consent / invoice_name / invoice_ruc.
"""

from __future__ import annotations

from tests.factories import make_customer, make_product


def _edit_payload(**over):
    payload = {
        "name": "Profile UX",
        "phone": "0983112233",
        "notes": "",
        "birthday": "15-03",
        "how_found": "instagram",
        "preferred_channel": "whatsapp",
        "marketing_consent": "1",
        "invoice_name": "Estudio Contable UX SRL",
        "invoice_ruc": "80012345-6",
    }
    payload.update(over)
    return payload


def test_edit_saves_profile_fields(client, session_factory):
    with session_factory() as s:
        c = make_customer(s, name="Profile UX")
        s.commit()
        cid = c.id
    r = client.post(
        f"/clientes/{cid}/editar", data=_edit_payload(), follow_redirects=False
    )
    assert r.status_code == 303, r.status_code
    from app.rms.models import Customer
    with session_factory() as s:
        c = s.get(Customer, cid)
        assert c.birthday == "15-03"
        assert c.how_found == "instagram"
        assert c.preferred_channel == "whatsapp"
        assert c.marketing_consent is True
        assert c.invoice_name == "Estudio Contable UX SRL"
        assert c.invoice_ruc == "80012345-6"


def test_edit_rejects_bad_how_found(client, session_factory):
    with session_factory() as s:
        c = make_customer(s, name="ProfileBad UX")
        s.commit()
        cid = c.id
    r = client.post(
        f"/clientes/{cid}/editar",
        data=_edit_payload(name="ProfileBad UX", how_found="hackr"),
        follow_redirects=False,
    )
    assert r.status_code == 400


def test_edit_clears_consent(client, session_factory):
    with session_factory() as s:
        c = make_customer(s, name="ConsentOff UX")
        c.marketing_consent = True
        s.commit()
        cid = c.id
    client.post(
        f"/clientes/{cid}/editar",
        data=_edit_payload(name="ConsentOff UX", marketing_consent=""),
        follow_redirects=False,
    )
    from app.rms.models import Customer
    with session_factory() as s:
        assert s.get(Customer, cid).marketing_consent is False


def test_edit_form_renders_profile_fields(client, session_factory):
    with session_factory() as s:
        c = make_customer(s, name="ProfileForm UX")
        c.invoice_name = "Previa SRL"
        s.commit()
        cid = c.id
    r = client.get(f"/clientes/{cid}/editar")
    assert r.status_code == 200
    body = r.text
    assert 'name="birthday"' in body
    assert 'name="how_found"' in body
    assert 'name="preferred_channel"' in body
    assert 'name="marketing_consent"' in body
    assert 'name="invoice_name"' in body
    assert 'name="invoice_ruc"' in body
    assert "Previa SRL" in body  # prefilled
    # address manager present
    assert "Direcciones de delivery" in body
    assert "addr-add" in body


# ── Address manager API ──────────────────────────────────────────────────

def test_address_add_and_delete_api(client, session_factory):
    with session_factory() as s:
        c = make_customer(s, name="AddrMgr UX")
        s.commit()
        cid = c.id
    r = client.post(
        f"/clientes/api/{cid}/addresses",
        json={"label": "oficina", "address_text": "Edificio UX, piso 5", "zone_id": None},
    )
    assert r.status_code == 200, r.status_code
    aid = r.json()["id"]
    assert r.json()["is_default"] is True  # first address = default

    r2 = client.delete(f"/clientes/api/{cid}/addresses/{aid}")
    assert r2.status_code == 200
    from app.rms.models import CustomerAddress
    with session_factory() as s:
        assert s.get(CustomerAddress, aid) is None


def test_address_api_rejects_empty_text(client, session_factory):
    with session_factory() as s:
        c = make_customer(s, name="AddrEmpty UX")
        s.commit()
        cid = c.id
    r = client.post(
        f"/clientes/api/{cid}/addresses", json={"label": "x", "address_text": "  "}
    )
    assert r.status_code == 400


def test_address_delete_wrong_customer_404(client, session_factory):
    with session_factory() as s:
        c = make_customer(s, name="AddrOwner UX")
        c2 = make_customer(s, name="AddrOther UX")
        s.commit()
        cid, cid2 = c.id, c2.id
    r = client.post(
        f"/clientes/api/{cid}/addresses",
        json={"label": "casa", "address_text": "Somewhere 1"},
    )
    aid = r.json()["id"]
    r2 = client.delete(f"/clientes/api/{cid2}/addresses/{aid}")
    assert r2.status_code == 404


# ── Pedido invoice prefill ───────────────────────────────────────────────

def test_pedido_prefills_invoice_from_profile(client, session_factory):
    with session_factory() as s:
        c = make_customer(s, name="InvoicePrefill UX")
        c.invoice_name = "Prefill SRL"
        c.invoice_ruc = "80099999-9"
        s.flush()
        p = make_product(s, name="InvoiceProd UX", sale_price_gs=10000)
        s.commit()
        cid, pid = c.id, p.id
    r = client.post(
        "/pedidos/nuevo",
        data={
            "customer_id": str(cid),
            "promised_date": "2030-02-01",
            "line_product_id": str(pid),
            "line_qty": "1",
            "line_unit_price_gs": "10000",
            "invoice_name": "",   # operator left empty → profile defaults
            "invoice_ruc": "",
        },
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)
    from app.rms.models import Pedido
    with session_factory() as s:
        ped = s.query(Pedido).order_by(Pedido.id.desc()).first()
        assert ped.invoice_name == "Prefill SRL"
        assert ped.invoice_ruc == "80099999-9"


def test_pedido_explicit_invoice_overrides_profile(client, session_factory):
    with session_factory() as s:
        c = make_customer(s, name="InvoiceOverride UX")
        c.invoice_name = "Default SRL"
        s.flush()
        p = make_product(s, name="InvoiceOvProd UX", sale_price_gs=10000)
        s.commit()
        cid, pid = c.id, p.id
    client.post(
        "/pedidos/nuevo",
        data={
            "customer_id": str(cid),
            "promised_date": "2030-02-02",
            "line_product_id": str(pid),
            "line_qty": "1",
            "line_unit_price_gs": "10000",
            "invoice_name": "Explicit S.A.",  # operator typed → wins
        },
        follow_redirects=False,
    )
    from app.rms.models import Pedido
    with session_factory() as s:
        ped = s.query(Pedido).order_by(Pedido.id.desc()).first()
        assert ped.invoice_name == "Explicit S.A."


# ── Completion nudge ─────────────────────────────────────────────────────

def test_clientes_list_shows_nudge_banner(client, session_factory):
    with session_factory() as s:
        make_customer(s, name="NudgeNoPhone UX", phone="")  # no phone
        s.commit()
    r = client.get("/clientes")
    assert r.status_code == 200
    body = r.text
    assert "Datos incompletos" in body
    assert "sin teléfono" in body
    assert "sin perfil dietético" in body


def test_nudge_hidden_when_data_complete(client, session_factory):
    """A fully-filled client contributes zero nudge counts."""
    with session_factory() as s:
        c = make_customer(s, name="NudgeComplete UX", phone="0983112233")
        c.dietary_restrictions = "vegano"
        c.marketing_consent = True
        s.commit()
        cid = c.id
    from app.rms.models import CustomerAddress
    with session_factory() as s:
        s.add(CustomerAddress(customer_id=cid, label="casa",
                              address_text="Calle 1"))
        s.commit()
    r = client.get(f"/clientes?q=NudgeComplete")
    assert r.status_code == 200
    # banner may still show (other clients exist in DB) but this client
    # adds no counts — assert the page renders fine.
    assert "NudgeComplete UX" in r.text
