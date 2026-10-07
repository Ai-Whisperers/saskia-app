"""P3.11: /clientes/{id}/editar invoice-profile add + default both use
in-DOM update instead of window.location.reload().

Address add (P3.10) and delete (P3.6) were fixed. For consistency,
invoice-profile add and the 'set as default' action should also be
in-DOM (no full reload).

Acceptance:
  - GET /clientes/{id}/editar returns 200.
  - The invoice-add handler uses DOM insertion (insertAdjacentHTML /
    appendChild / insertRow) on the invoice tbody.
  - The invoice-default handler uses DOM manipulation (button class
    swap / .classList.add+remove) to mark the chosen row as default
    without reloading.
"""

from __future__ import annotations

import re
import uuid

from tests.factories import make_customer


def _extract_inline_js(body: str) -> str:
    return "\n".join(re.findall(r"<script>(.*?)</script>", body, re.DOTALL))


def _find_handler_by_id(js: str, element_id: str) -> str:
    """Find the handler that binds to a button by id, e.g. id="inv-add"."""
    pat = f'getElementById("{element_id}")'
    start = js.find(pat)
    assert start >= 0, f"couldn't locate handler for {element_id!r}"
    return js[start : start + 3000]


def test_cliente_editar_invoice_add_uses_dom_insertion(client, session_factory):
    """P3.11: invoice-profile add inserts the new <tr> in the DOM."""
    s = session_factory()
    try:
        cust = make_customer(s, name=f"inv-add-{uuid.uuid4().hex[:6]}")
        s.commit()
        cid = cust.id
    finally:
        s.close()

    r = client.get(f"/clientes/{cid}/editar")
    assert r.status_code == 200
    js = _extract_inline_js(r.text)
    handler = _find_handler_by_id(js, "inv-add")

    has_dom_insert = bool(
        re.search(
            r"insertAdjacentHTML|insertBefore|appendChild|insertRow|tbody\.prepend|table\.prepend|\.prepend\(",
            handler,
        )
    )
    assert has_dom_insert, (
        "invoice-add handler must insert the new row in the DOM; "
        "currently it only calls window.location.reload()."
    )


def test_cliente_editar_invoice_default_uses_dom_swap(client, session_factory):
    """P3.11: 'set as default' swaps the default badge in the DOM."""
    s = session_factory()
    try:
        cust = make_customer(s, name=f"inv-def-{uuid.uuid4().hex[:6]}")
        s.commit()
        cid = cust.id
    finally:
        s.close()

    r = client.get(f"/clientes/{cid}/editar")
    assert r.status_code == 200
    js = _extract_inline_js(r.text)
    start = js.find('querySelectorAll(".inv-default"')
    assert start >= 0, "couldn't locate inv-default handler"
    handler = js[start : start + 3000]

    # We expect a classList swap or attribute change for the badge.
    has_dom_swap = bool(
        re.search(
            r"classList\.(add|remove|toggle)|setAttribute|\.badge\b.*replace|innerHTML\s*=",
            handler,
        )
    )
    assert has_dom_swap, (
        "inv-default handler must swap the default badge in the DOM; "
        "currently it only calls window.location.reload()."
    )
