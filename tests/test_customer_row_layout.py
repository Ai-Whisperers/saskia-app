"""Tests for the customer picker row layout (combo-rows.js:customerRowLabel).

T-2026-10-01: customerRowLabel was a cramped one-line renderer
"name0982515138". Replaced with a 3-line layout: name + tier badge,
phone + CI/RUC, email + dietary chip + lifetime spend.

These tests pin the new contract so the dropdown stays scannable for
the cashier. They assert the contract on:
  1. The CSS bundle (so styles can't regress)
  2. The JS bundle (so the renderer can't regress)
  3. The /ventas rendered HTML (so the wiring can't regress)
"""
from __future__ import annotations

import re


# ── CSS bundle contains the new customer-row classes ─────────────────

def test_combobox_css_includes_customer_row_classes(client):
    """The CSS bundle must include the new customer-row styles."""
    r = client.get("/static/combobox.css")
    assert r.status_code == 200
    body = r.text
    assert ".combo-row--customer" in body
    assert ".combo-row-tier--platinum" in body
    assert ".combo-row-chip--warn" in body
    assert ".combo-row-line--name" in body
    assert ".combo-row-line--contact" in body
    assert ".combo-row-line--meta" in body


def test_combobox_css_disables_nowrap_on_customer_main(client):
    """The combo-row-main default sets `white-space: nowrap` which
    would single-line our 3-line layout. The customer-row override
    must reset it."""
    r = client.get("/static/combobox.css")
    body = r.text
    # Find the customer row block
    m = re.search(
        r"\.combo-row--customer\s+\.combo-row-main[^}]+}",
        body, re.S,
    )
    assert m, "no .combo-row--customer .combo-row-main rule in combobox.css"
    block = m.group(0)
    assert "white-space: normal" in block, (
        f"Expected white-space:normal override inside {block!r}"
    )


# ── JS bundle contains the new 3-line renderer ──────────────────────

def test_combo_rows_js_has_three_line_customer_row(client):
    """The JS bundle must contain the new 3-line customer renderer."""
    r = client.get("/static/combo-rows.js")
    assert r.status_code == 200
    body = r.text
    for marker in (
        "combo-row-line--name",
        "combo-row-line--contact",
        "combo-row-line--meta",
        "combo-row-tier--${",  # tier class is built from row.tier
        "combo-row-chip--warn",
        "dietary_restrictions",
        "lifetime_label",
    ):
        assert marker in body, f"missing {marker} in combo-rows.js"


def test_combo_rows_js_uses_dietary_and_lifetime_fields(client):
    """The renderer should read dietary_restrictions + lifetime_label."""
    r = client.get("/static/combo-rows.js")
    body = r.text
    assert "dietary_restrictions" in body
    assert "lifetime_label" in body


# ── Wiring on /ventas (the picker) ──────────────────────────────────

def test_customer_picker_html_passes_row_label_attribute(client, session_factory):
    """The /ventas page must set row-label='customerRowLabel' so the
    combo uses our new 3-line renderer (otherwise it falls back to
    defaultRowLabel which is the cramped one-line layout)."""
    from tests.factories import make_customer
    with session_factory() as s:
        make_customer(s, name="Test Pick", phone="+595****9911")
        s.commit()
    r = client.get("/ventas")
    assert r.status_code == 200
    body = r.text
    assert 'row-label="customerRowLabel"' in body, (
        "Expected customer_id_combo to declare row-label='customerRowLabel' "
        "so the dropdown rows use the new 3-line layout."
    )


def test_ventas_page_loads_combo_rows_bundle(client, session_factory):
    """combo-rows.js must be served on /ventas so customerRowLabel
    is in scope for the combo's row-label lookup."""
    from tests.factories import make_customer
    with session_factory() as s:
        make_customer(s, name="Bundle Test")
        s.commit()
    r = client.get("/ventas")
    body = r.text
    # Either bundled inline or as a <script src> reference
    assert ("combo-rows.js" in body) or ("customerRowLabel" in body)


# ── Search endpoint returns the fields the renderer needs ───────────

def test_search_endpoint_returns_tier_and_lifetime(client, session_factory):
    """The search API must include `tier` and `lifetime_label` so the
    new renderer has something to show in the tier chip and lifetime cell."""
    # Create one customer with no sales (lifetime = 0) so the search
    # endpoint has at least one result to assert fields on.
    from app.rms.models import Customer
    with session_factory() as s:
        c = Customer(name="Tier Test", phone="+595****8800")
        s.add(c)
        s.commit()
    r = client.get("/clientes/api/search?q=Tier")
    assert r.status_code == 200, r.text[:200]
    body = r.json()
    assert body["count"] >= 1
    # At least one result must carry the metadata fields
    rows = body["results"]
    assert rows, "no customers in search results"
    sample = rows[0]
    assert "name" in sample
    assert "phone" in sample
    assert "tier" in sample, f"missing 'tier' field; got keys: {list(sample.keys())}"
    assert "lifetime_label" in sample, f"missing 'lifetime_label'; got keys: {list(sample.keys())}"


def test_search_endpoint_returns_dietary_when_present(client, session_factory):
    """Customers with dietary restrictions must have the field
    populated so the chip renders in the dropdown row."""
    from app.rms.models import Customer
    with session_factory() as s:
        c = Customer(
            name="Sin Nueces Test",
            phone="+595****9901",
            dietary_restrictions="sin frutos secos",
            dietary_confirm_always=False,
        )
        s.add(c)
        s.commit()
        cid = c.id
    r = client.get("/clientes/api/search?q=Sin Nueces")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] >= 1
    matches = [row for row in body["results"] if row["id"] == cid]
    assert len(matches) == 1
    row = matches[0]
    dietary = row.get("dietary_restrictions") or []
    assert "sin frutos secos" in dietary, (
        f"Expected 'sin frutos secos' in dietary_restrictions; got {dietary!r}"
    )


def test_search_endpoint_returns_email_and_cedula(client, session_factory, qseed):
    """Email + cedula fields must be present in the search response
    so the renderer can show them on the contact line."""
    from app.rms.models import Customer
    with session_factory() as s:
        c = Customer(
            name="Contacto Test",
            cedula="1234567",
            email="contacto@example.com",
            phone="+595 981 999 888",
        )
        s.add(c)
        s.commit()
    body = client.get("/clientes/api/search?q=Contacto").json()
    assert body["count"] >= 1
    row = body["results"][0]
    assert row["cedula"] == "1234567"
    assert row["email"] == "contacto@example.com"
    assert row["phone"] == "+595 981 999 888"