"""P-33.1: /pedidos/nuevo must keep free-text address as primary path.

Two parallel address input paths:
  1. Free-text <input id="address_text" list="customer-addresses">
  2. <details id="address-struct-details"> with 12 structured fields

Cashier doesn't know which to use. Fix: free-text remains the primary
visible input; structured <details> stays closed by default with a
clear hint that the structured fields are optional refinement.

Acceptance:
  - <input id="address_text"> is rendered OUTSIDE the <details id="address-struct-details">.
  - The <details> does NOT have the `open` attribute (closed by default).
  - The hint text mentions "Datos estructurados" or "opcional".
"""
from __future__ import annotations


def test_pedidos_nuevo_address_text_is_primary(client):
    """P-33.1: free-text address input is outside the structured disclosure."""
    r = client.get("/pedidos/nuevo")
    assert r.status_code == 200
    body = r.text

    # Both elements must be present.
    assert 'id="address_text"' in body, "address_text input missing"
    assert 'id="address-struct-details"' in body, (
        "address-struct-details disclosure missing"
    )

    # address_text must appear BEFORE the <details> in DOM order.
    text_idx = body.index('id="address_text"')
    details_idx = body.index('id="address-struct-details"')
    assert text_idx < details_idx, (
        f"address_text (idx={text_idx}) should appear before "
        f"address-struct-details (idx={details_idx})"
    )

    # The <details> must NOT have the `open` attribute on its first tag.
    idx = body.index("<details")
    end = body.index(">", idx)
    opening_tag = body[idx:end + 1]
    assert "open" not in opening_tag.split()[-5:], (
        f"address-struct-details should default to closed: {opening_tag[:120]}"
    )

    # The disclosure copy should mention "Datos estructurados" or "opcional".
    # We look for either as evidence the operator can identify the path.
    section = body[details_idx:details_idx + 1500]
    assert ("Datos estructurados" in section) or ("opcional" in section), (
        "address-struct-details must label itself clearly"
    )
