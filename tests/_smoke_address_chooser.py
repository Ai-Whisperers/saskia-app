"""Smoke test: server-rendered HTML for /pedidos/nuevo must not contain
any address-chooser markup (the chooser is JS-injected, not server-rendered).

Bug context: the screenshot shows three 'direcciones guardadas' labels
stacked. pedido-combos.js's `loadCustomerAddresses` appends a new
chooser to addrInput.parentElement every time the operator picks a
customer — without removing the previous one. pedido-prefill.js has a
similar bug in renderAddressPicker. This test pins the server-rendered
HTML to ZERO choosers so we can target the duplication fix without
needing a JS test runner.
"""
from __future__ import annotations

import re


def test_server_html_has_no_address_chooser(client, session_factory):
    """With a customer that has 3 saved addresses, server HTML must have zero choosers."""
    from app.rms.models import Customer, CustomerAddress

    with session_factory() as s:
        c = Customer(name="Chooser Demo", phone="+595 9XX XXXX")
        s.add(c)
        s.flush()
        for label, addr, is_def in [
            ("Casa", "Av. España 123", True),
            ("Oficina", "Mcal. López 456", False),
            ("Mamá", "Sajonia 789", False),
        ]:
            s.add(CustomerAddress(
                customer_id=c.id,
                label=label,
                address_text=addr,
                is_default=is_def,
            ))
        s.commit()
        cid = c.id

    resp = client.get(f"/pedidos/nuevo?customer_id={cid}")
    assert resp.status_code == 200, resp.text[:200]
    html = resp.text

    # Server HTML must have ZERO address-chooser markers.
    assert html.count("direcciones guardadas") == 0, (
        f"'direcciones guardadas' appears {html.count('direcciones guardadas')} times "
        "in server HTML; the chooser should be JS-injected only"
    )
    assert html.count('id="address-picker"') == 0, (
        f"address-picker div appears {html.count('id=\"address-picker\"')} times in HTML"
    )
    assert html.count('id="address_quick_pick"') == 0, (
        f"address_quick_pick appears {html.count('id=\"address_quick_pick\"')} times in HTML"
    )

    # The prefill JSON must carry the address book so JS can render it
    import json
    m = re.search(
        r'<script id="customer-prefill" type="application/json">(.*?)</script>',
        html, re.S,
    )
    assert m is not None, "customer-prefill JSON script block missing"
    data = json.loads(m.group(1))
    addrs = data.get("available_addresses", [])
    assert len(addrs) == 3, f"expected 3 saved addresses, got {len(addrs)}"
    assert {a["label"] for a in addrs} == {"Casa", "Oficina", "Mamá"}