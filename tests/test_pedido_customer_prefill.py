
# allow-hardcoded-dates: fixed instants for deterministic assertions

def test_pedido_nuevo_prefills_customer_data(session_factory, client):
    """?customer_id=N loads the customer's phone/RUC/razón social into the form."""
    from app.rms.models import Customer

    with session_factory() as s:
        s.add(Customer(name="Kyrian Weiss", phone="0982515138",
                       email="k@x.com", cedula="5991039",
                       invoice_ruc="5991039", invoice_name="Kyrian Weiss B.V."))
        s.commit()
        cid = s.query(Customer).filter_by(name="Kyrian Weiss").one().id

    r = client.get(f"/pedidos/nuevo?customer_id={cid}")
    body = r.text
    assert 'value="0982515138"' in body          # phone
    assert 'value="5991039"' in body             # RUC (falls back to cedula too)
    assert 'value="Kyrian Weiss B.V."' in body   # razón social
    assert "k@x.com" in body                     # email visible in hint


def test_pedido_create_writes_back_customer_contact(session_factory, client):
    """Creating a pedido updates the customer's phone/RUC/razón on record."""
    from app.rms.models import Customer, Product, Recipe

    with session_factory() as s:
        rec = Recipe(name="R wb", yield_qty=1, yield_unit="und")
        s.add(rec)
        s.flush()
        p = Product(name="Pan wb", recipe_id=rec.id, sale_price_gs=5000,
                    is_available=True, tablet_visible=True)
        s.add(p)
        c = Customer(name="Writeback Test", phone=None)
        s.add(c)
        s.commit()
        cid, pid = c.id, p.id

    resp = client.post("/pedidos/nuevo", data={
        "customer_id": str(cid),
        "customer_name": "Writeback Test",
        "customer_phone": "0982000111",
        "promised_date": "2030-01-01",
        "channel": "whatsapp",
        "payment_intent": "efectivo",
        "invoice_ruc": "80012345-6",
        "invoice_name": "WB Sociedad",
        "line_product_id": str(pid),
        "line_qty": "1",
        "line_unit_price_gs": "5000",
    }, follow_redirects=False)
    assert resp.status_code == 303

    with session_factory() as s:
        c = s.get(Customer, cid)
        assert c.phone == "0982000111"
        assert c.invoice_ruc == "80012345-6"
        assert c.invoice_name == "WB Sociedad"


def test_customer_search_returns_invoice_fields(client, session_factory):
    """/clientes/api/search carries invoice_ruc/invoice_name for form prefill."""
    from app.rms.models import Customer

    with session_factory() as s:
        s.add(Customer(name="Invoice Prefill", phone="0983", cedula="123",
                       invoice_ruc="800999-7", invoice_name="IP SA"))
        s.commit()

    r = client.get("/clientes/api/search?q=Invoice Prefill")
    data = r.json()
    row = data["results"][0]
    assert row["invoice_ruc"] == "800999-7"
    assert row["invoice_name"] == "IP SA"
