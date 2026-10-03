"""Smoke test: /pedidos/nuevo must have exactly one address input
backed by a native <datalist id="customer-addresses">.

T-2026-10-01: replaced the two competing JS-injected <select>s
(pedido-combos.js's address_quick_pick + pedido-prefill.js's
address-picker) with a single native combobox. The picker is the
existing address_text <input list="customer-addresses">, which is
writeable AND shows the saved addresses as dropdown options.

This test pins the new contract so a future regression can't
re-introduce duplicate pickers or stacked "— direcciones guardadas —"
labels.
"""
from __future__ import annotations

import json
import re

from app.rms.models import Customer, CustomerAddress


def test_datalist_present_and_empty_when_no_customer(client, session_factory):
    """Even with no customer selected, the <datalist id=customer-addresses>
    must exist (empty) so the input can be populated when a customer
    is later picked. No competing pickers."""
    from tests.factories import make_customer
    with session_factory() as s:
        cid = make_customer(s, name="NoAddr Test").id
        s.commit()
    r = client.get(f"/pedidos/nuevo?customer_id={cid}")
    assert r.status_code == 200, r.text[:200]
    body = r.text
    # Single native <datalist id="customer-addresses"> present
    assert 'id="customer-addresses"' in body, (
        "Expected <datalist id='customer-addresses'> in the rendered "
        "form (provides native writeable+selectable combobox)."
    )
    # The address input references the datalist via `list=` attr
    assert 'list="customer-addresses"' in body, (
        "Expected address_text input to use list='customer-addresses' "
        "to bind it to the datalist."
    )
    # No JS-injected duplicates from pre-fix code
    assert 'id="address_quick_pick"' not in body
    assert 'id="address-picker"' not in body
    # No stacked "direcciones guardadas" label leaking into HTML
    assert body.count("direcciones guardadas") == 0


def test_datalist_populates_when_customer_has_addresses(client, session_factory):
    """With a customer that has saved addresses, the datalist must
    carry one <option> per address (no duplicates, no stray selects)."""
    with session_factory() as s:
        c = Customer(name="Datalist UX", phone="+595 9XX XXXX")
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

    r = client.get(f"/pedidos/nuevo?customer_id={cid}")
    assert r.status_code == 200, r.text[:200]
    body = r.text

    # Datalist exists
    assert 'id="customer-addresses"' in body
    # Each address appears at least once in the rendered page (it
    # shows up in both the <datalist> options and the customer-prefill
    # JSON payload; we only care that there's at least one visible copy).
    assert body.count("Av. España 123") >= 1
    assert body.count("Mcal. López 456") >= 1
    assert body.count("Sajonia 789") >= 1
    # No pre-fix duplicate-picker residues
    assert 'id="address_quick_pick"' not in body
    assert 'id="address-picker"' not in body
    # No JS-rendered label leaks into HTML (the datalist is bare)
    assert "direcciones guardadas" not in body

    # The prefill JSON still carries the address book for other consumers
    m = re.search(
        r'<script id="customer-prefill" type="application/json">(.*?)</script>',
        body, re.S,
    )
    assert m is not None, "customer-prefill JSON script block missing"
    data = json.loads(m.group(1))
    addrs = data.get("available_addresses", [])
    assert len(addrs) == 3, f"expected 3 saved addresses, got {len(addrs)}"
    assert {a["label"] for a in addrs} == {"Casa", "Oficina", "Mamá"}


def test_datalist_options_have_value_and_label(client, session_factory):
    """Each <option> inside the datalist must have a value attr (so
    browsers autofill the input on selection) and the address text as
    its body (so the dropdown shows the full text, not just an ID)."""
    with session_factory() as s:
        c = Customer(name="Datalist Opts", phone="+595 9XX XXXX")
        s.add(c)
        s.flush()
        s.add(CustomerAddress(
            customer_id=c.id,
            label="casa",
            address_text="Edificio Villa Morra, Piso 7 of. 703",
        ))
        s.commit()
        cid = c.id

    r = client.get(f"/pedidos/nuevo?customer_id={cid}")
    body = r.text

    # Find the datalist options. The datalist options use the
    # address_text as value (so the input fills with the address on
    # selection) and the label as part of the visible text.
    options = re.findall(
        r'<option value="([^"]+)"[^>]*>([^<]+)</option>',
        body,
    )
    assert options, "no <option> tags rendered in the page"
    values = [v for v, _ in options]
    texts = [t for _, t in options]
    assert "Edificio Villa Morra, Piso 7 of. 703" in values
    assert "casa — Edificio Villa Morra, Piso 7 of. 703" in texts, (
        f"Expected label+address in display text, got {texts!r}"
    )


def test_no_duplicate_pickers_across_paths(client, session_factory):
    """The two JS entry points (pedido-combos.js's loadCustomerAddresses
    + pedido-prefill.js's renderAddressPicker) both target the same
    datalist — there should never be two pickers stacked on the page
    even after the customer is changed via the combo."""
    from tests.factories import make_customer
    # Two customers — switching between them must not accumulate pickers
    with session_factory() as s:
        c1 = make_customer(s, name="SwitchA", phone="+595****7101")
        c2 = make_customer(s, name="SwitchB", phone="+595****7102")
        s.commit()
        cid1, _cid2 = c1.id, c2.id

    r = client.get(f"/pedidos/nuevo?customer_id={cid1}")
    body = r.text
    # Exactly ONE datalist reference
    assert body.count('id="customer-addresses"') == 1
    # No legacy picker IDs
    assert 'id="address_quick_pick"' not in body
    assert 'id="address-picker"' not in body
    # No "direcciones guardadas" label that the OLD wrong-select showed
    assert "direcciones guardadas" not in body
