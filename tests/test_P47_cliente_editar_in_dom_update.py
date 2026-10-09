"""P3.6: /clientes/{id}/editar add/delete must update the DOM in place,
not call window.location.reload().

Currently every successful add/delete/set-default triggers a full page
reload via `window.location.reload()`. That's slow (round-trip + re-render
~300ms) and loses any unsubmitted form state. The fix: append the new
row / remove the deleted row in-place.

Acceptance:
  - GET /clientes/{id}/editar returns 200.
  - The inline JS for address delete contains `rowEl.remove` /
    `parentNode.removeChild` / similar DOM-removal logic — NOT just
    `window.location.reload()`.
  - The inline JS for invoice-profile delete similarly uses in-DOM
    removal logic.
"""

from __future__ import annotations

import re
import uuid

from tests.factories import make_customer


def _extract_inline_js(body: str) -> str:
    """Pull the inline <script> blocks (no src attr)."""
    return "\n".join(re.findall(r"<script>(.*?)</script>", body, re.DOTALL))


def _find_handler(js: str, marker: str) -> str:
    """Find a handler block by its querySelectorAll('marker') start anchor.

    Returns the next 3000 chars of source — handlers are well under that.
    """
    start = js.find(f'querySelectorAll("{marker}"')
    assert start >= 0, f"couldn't locate {marker!r} handler"
    return js[start : start + 3000]


def _has_dom_removal(handler: str) -> bool:
    return bool(
        re.search(
            r"\.remove\(\s*\)|parentNode\.removeChild|closest\([^)]+\)\.remove",
            handler,
        )
    )


def test_cliente_editar_delete_uses_dom_removal(client, session_factory):
    """P3.6: address delete uses DOM removal, not window.location.reload()."""
    s = session_factory()
    try:
        cust = make_customer(s, name=f"del-dom-{uuid.uuid4().hex[:6]}")
        s.commit()
        cid = cust.id
    finally:
        s.close()

    r = client.get(f"/clientes/{cid}/editar")
    assert r.status_code == 200
    js = _extract_inline_js(r.text)
    handler = _find_handler(js, ".addr-del")
    assert _has_dom_removal(handler), (
        "address-delete handler must remove the row in the DOM; "
        "currently it only calls window.location.reload()."
    )


def test_cliente_editar_invoice_delete_uses_dom_removal(client, session_factory):
    """P3.6: invoice-profile delete uses DOM removal, not reload."""
    s = session_factory()
    try:
        cust = make_customer(s, name=f"inv-del-{uuid.uuid4().hex[:6]}")
        s.commit()
        cid = cust.id
    finally:
        s.close()

    r = client.get(f"/clientes/{cid}/editar")
    assert r.status_code == 200
    js = _extract_inline_js(r.text)
    handler = _find_handler(js, ".inv-del")
    assert _has_dom_removal(handler), "invoice-delete handler must remove the row in the DOM"
