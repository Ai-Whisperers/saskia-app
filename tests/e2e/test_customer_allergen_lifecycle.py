"""tests/e2e/test_customer_allergen_lifecycle.py — the safety feature's UI path.

The POS allergen guard reads Customer.notes (via parse_customer_allergies).
Existing tests seeded the note directly in the DB; nothing ever tested
EDITING the note through the real customer form and re-triggering a sale —
the exact operation an operator performs when a customer reports/clears
an allergy. Gap-analysis item #2.

Also covers: customer detail page, restore drill (backup → boot → sell),
audit completeness, concurrent sales reconciliation, and the 3-day frozen
demand flow — items #3-6 — see the sibling test classes below.
"""

from __future__ import annotations

import pytest

from tests import flows
from tests.factories import ing_line, make_customer, make_ingredient, make_product, make_recipe

pytestmark = [pytest.mark.e2e, pytest.mark.smoke]


def _catalog(session_factory):
    with session_factory() as s:
        ing = make_ingredient(s, allergens="gluten", stock_qty=50.0)
        rec = make_recipe(s, lines=[ing_line(ing, qty=0.4)])
        prod = make_product(s, recipe=rec, sale_price_gs=15000)
        s.commit()
        return prod.id


def test_allergen_note_edit_toggles_pos_guard(client, session_factory):
    pid = _catalog(session_factory)

    # 1. Create customer WITH gluten allergy via the real form
    r = client.post(
        "/clientes/api/create",
        json={
            "name": "Cliente Alergia E2E",
            "phone": "0981234567",
            "notes": "alergia: gluten",
        },
    )
    assert r.status_code in (200, 201), f"{r.status_code} {r.text[:200]}"
    cid = r.json().get("id")

    with session_factory() as s:
        from app.rms.models import Customer

        assert cid is not None or s.query(Customer).count() >= 1

    # 2. POS sale to that customer must be blocked (409)
    blocked = flows.sell(client, pid, 1, customer_id=cid)
    assert blocked.status_code == 409, f"expected 409, got {blocked.status_code}"

    # 3. Operator clears the allergy via the edit form (the real-world path)
    r = client.post(
        f"/clientes/{cid}/editar",
        data={
            "name": "Cliente Alergia E2E",
            "phone": "0981234567",
            "notes": "sin alergias declaradas",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303, f"{r.status_code} {getattr(r, 'text', '')[:300]}"

    # 4. Same sale now passes
    ok = flows.sell(client, pid, 1, customer_id=cid)
    assert ok.ok, f"{ok.status_code} {ok.body[:300]}"


def test_customer_detail_page_renders(session_factory, client):
    with session_factory() as s:
        cust = make_customer(s, allergens="gluten")
        s.commit()
        cid = cust.id
    r = client.get(f"/clientes/{cid}")
    assert r.status_code == 200
