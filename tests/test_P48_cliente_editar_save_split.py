"""P3.7 (T7): /clientes/{id}/editar form has two save buttons:
- 'Guardar y volver al detalle' (saves, returns to /clientes/{id})
- 'Guardar y seguir editando' (saves, returns to /clientes/{id}/editar)

Currently there's only ONE save button which always redirects to the
detail page. Operators editing many fields lose any unsubmitted changes
because they have to re-open the form to make a small tweak.

Acceptance:
  - GET /clientes/{id}/editar returns 200.
  - The form contains two <button type='submit'> elements with
    data-redirect-to attributes — one with /clientes/{id} and one
    with /clientes/{id}/editar.
"""
from __future__ import annotations

import uuid

from tests.factories import make_customer


def test_cliente_editar_has_two_save_buttons(client, session_factory):
    """P3.7: split save button — 'back to detail' vs 'keep editing'."""
    s = session_factory()
    try:
        cust = make_customer(s, name=f"save-split-{uuid.uuid4().hex[:6]}")
        s.commit()
        cid = cust.id
    finally:
        s.close()

    r = client.get(f"/clientes/{cid}/editar")
    assert r.status_code == 200
    body = r.text

    # Two <button type="submit"> elements with data-redirect-to.
    # First one should redirect to detail page (no /editar suffix).
    # Second one should redirect to the edit page itself.
    assert 'data-save-back' in body, "expected data-save-back button"
    assert 'data-save-stay' in body, "expected data-save-stay button"
    assert f'href="/clientes/{cid}"' in body, (
        "back-to-detail button should have href to detail"
    )
