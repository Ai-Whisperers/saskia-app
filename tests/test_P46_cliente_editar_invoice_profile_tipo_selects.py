"""P3.5: /clientes/{id}/editar must expose invoice profile tipo_documento
and tipo_operacion as selects, not hardcoded values in JS.

Currently the inline JS hardcodes:
  - tipo_documento = "CI_PARAGUAYA"
  - tipo_operacion = "B2C"

This means B2B / RUC / Pasaporte / Extranjero customers can't be
represented. The form must offer all valid SIFEN values as <select>s.

Acceptance:
  - GET /clientes/{id}/editar returns 200.
  - The form contains <select> elements with id="inv-tipo-doc" and
    id="inv-tipo-operacion".
  - Both selects have at least 4 options each (SIFEN has 7 tipo_doc
    and 4 tipo_operacion values).
"""
from __future__ import annotations

import re
import uuid

from tests.factories import make_customer


def test_cliente_editar_invoice_profile_has_tipo_selects(client, session_factory):
    """P3.5: tipo_documento and tipo_operacion are <select>s, not hardcoded."""
    s = session_factory()
    try:
        cust = make_customer(s, name=f"invsel-{uuid.uuid4().hex[:6]}")
        s.commit()
        cid = cust.id
    finally:
        s.close()

    r = client.get(f"/clientes/{cid}/editar")
    assert r.status_code == 200
    body = r.text

    # Both selects must exist.
    assert 'id="inv-tipo-doc"' in body, "expected <select id='inv-tipo-doc'>"
    assert 'id="inv-tipo-operacion"' in body, "expected <select id='inv-tipo-operacion'>"

    # Each <select> must have multiple <option>s.
    for sid in ("inv-tipo-doc", "inv-tipo-operacion"):
        m = re.search(rf'<select[^>]*id="{sid}"[^>]*>(.*?)</select>', body, re.DOTALL)
        assert m, f"couldn't locate <select id='{sid}'>"
        options = re.findall(r'<option[^>]*value="([^"]+)"', m.group(1))
        assert len(options) >= 4, (
            f"<select id='{sid}'> must have >= 4 options; got {len(options)}"
        )

    # Common SIFEN values must be present.
    assert "CI_PARAGUAYA" in body, "CI_PARAGUAYA option missing"
    assert "B2C" in body, "B2C option missing"