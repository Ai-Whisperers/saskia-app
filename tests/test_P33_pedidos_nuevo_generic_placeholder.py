"""P-33.2: /pedidos/nuevo customer combo placeholder must be name-agnostic.

Pre-existing placeholder "María González — escribí para buscar" assumes
the most common customer is named María. If Kyrian is more frequent, this
is a bias bug. Fix: replace with a generic name-agnostic string.

Acceptance:
  - The customer combo's placeholder does NOT contain "María González".
  - The placeholder still includes a "buscá/buscar" hint.
"""
from __future__ import annotations


def test_pedidos_nuevo_customer_placeholder_is_generic(client):
    """P-33.2: placeholder must not be name-biased."""
    r = client.get("/pedidos/nuevo")
    assert r.status_code == 200
    body = r.text

    # The biased customer-combo placeholder must be gone. (Other placeholders
    # like "Ej: María González" for the NEW customer creation input are fine
    # — those are examples, not the search field.)
    # We check the customer combo specifically by looking at the
    # `placeholder=` immediately following the customer combo macro.
    import re
    # The customer combo renders as a saskia-combo with name="customer_id".
    # Find the placeholder near it.
    combo_match = re.search(
        r'name=.customer_id.\s+[^>]*?placeholder=[\\\'"]([^\\\'"]+)[\\\'"]',
        body, re.DOTALL,
    )
    if combo_match:
        # The combo macro expands differently — fall back to searching for
        # the literal `customer_id` macro string in the rendered HTML.
        # If we find it, the test is moot (the macro expanded).
        combo_placeholder = combo_match.group(1)
        assert "María González" not in combo_placeholder, (
            f"customer combo placeholder is biased: {combo_placeholder!r}"
        )

    # The literal text "María González — escribí para buscar" must be gone.
    assert "María González — escribí para buscar" not in body, (
        "old biased placeholder still in the page"
    )

    # A new generic placeholder should be present, with a search hint.
    placeholders = re.findall(r'placeholder="([^"]+)"', body)
    customer_placeholders = [
        p for p in placeholders
        if ("busc" in p.lower() or "escrib" in p.lower())
        and "ej" not in p.lower()
    ]
    assert customer_placeholders, (
        f"no customer search placeholder found; placeholders: {placeholders[:5]}"
    )
