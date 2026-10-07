"""P3.10: /clientes/{id}/editar address add must append the new row in the DOM,
not call window.location.reload().

Currently the addr-add handler also reloads. We just made delete use
in-DOM removal; add should use in-DOM insertion for symmetry.

Acceptance:
  - GET /clientes/{id}/editar returns 200.
  - The inline JS for address add contains DOM insertion logic (e.g.
    `<tbody>.insertAdjacentHTML`, `tbody.appendChild`, `insertRow`,
    `prepend`, etc.) — NOT just `window.location.reload()`.
"""
from __future__ import annotations

import re
import uuid

from tests.factories import make_customer


def _extract_inline_js(body: str) -> str:
    return "\n".join(re.findall(r"<script>(.*?)</script>", body, re.DOTALL))


def test_cliente_editar_address_add_uses_dom_insertion(client, session_factory):
    """P3.10: address add inserts the new row in the DOM, no reload."""
    s = session_factory()
    try:
        cust = make_customer(s, name=f"addr-add-{uuid.uuid4().hex[:6]}")
        s.commit()
        cid = cust.id
    finally:
        s.close()

    r = client.get(f"/clientes/{cid}/editar")
    assert r.status_code == 200
    js = _extract_inline_js(r.text)

    # Find the address-add handler.
    start = js.find('querySelectorAll(".addr-add"')
    if start < 0:
        # Some templates use a different anchor (e.g. .addr-add-row, button#addr-add).
        for alt in ('addr-add', 'id="addr-add"', 'address-add'):
            start = js.find(alt)
            if start >= 0:
                break
    assert start >= 0, "couldn't locate address-add handler"
    handler = js[start:start + 3000]

    has_dom_insert = bool(
        re.search(
            r"insertAdjacentHTML|insertBefore|appendChild|insertRow|tbody\.prepend|table\.prepend|list\.append|\.prepend\(",
            handler,
        )
    )
    assert has_dom_insert, (
        "address-add handler must insert the new row in the DOM; "
        "currently it only calls window.location.reload()."
    )
