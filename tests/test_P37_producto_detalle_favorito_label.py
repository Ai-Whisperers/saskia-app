"""P-37: /productos/{id} must distinguish 'Favorito' vs 'Quitar de favoritos'.

Bug: app/templates/producto_detalle.html:28-29 — both branches of
the if/else show "Favorito". When is_favorite is true, the button
should read "Quitar de favoritos".

Acceptance:
  - For a product with is_favorite=True, the button text contains
    "Quitar" + a reference to favoritos.
  - For is_favorite=False, the button text is just "Favorito" (no "Quitar").
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import sessionmaker

from tests.factories import make_product


def test_producto_detalle_favorito_label(client, session_factory):
    """P-37: 'Favorito' vs 'Quitar de favoritos' is distinguished."""
    s = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        # Product NOT favorited.
        prod = make_product(
            s,
            name=f"nofav-{uuid.uuid4().hex[:8]}",
            is_favorite=False,
        )
        s.commit()
        product_id = prod.id
    finally:
        s.close()

    r = client.get(f"/productos/{product_id}")
    assert r.status_code == 200
    body = r.text

    # The favorite form/button block is identifiable by a form action
    # /productos/{id}/favorito OR a button with "Favorito" text.
    import re

    # Find the section between "Favorito" mentions.
    fav_block = re.search(r"(<form[^>]*?/favorito.*?</form>)", body, re.DOTALL)
    if fav_block:
        text = fav_block.group(1)
        # When is_favorite=False, button should say "Favorito" (not Quitar).
        assert "Quitar" not in text, (
            f"product not favorited should not show 'Quitar' button: {text[:200]}"
        )


def test_producto_detalle_quitar_label_when_favorited(client, session_factory):
    """P-37: 'Quitar de favoritos' label when is_favorite=True."""
    s = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        prod = make_product(
            s,
            name=f"fav-{uuid.uuid4().hex[:8]}",
            is_favorite=True,
        )
        s.commit()
        product_id = prod.id
    finally:
        s.close()

    r = client.get(f"/productos/{product_id}")
    assert r.status_code == 200
    body = r.text

    # Look for the "Quitar" string anywhere on the page (in the form).
    assert "Quitar" in body, "expected 'Quitar' label on a favorited product"
