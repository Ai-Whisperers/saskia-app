"""P-36.1: /reorder bulk-generate should consolidate by supplier before submit.

Current flow: bulk-generate button POSTs the form with all selected
items, and the backend creates N separate orders/messages. With 30
items across 5 suppliers, that's 5 WhatsApp messages (current best)
or 30 messages (current worst).

Fix: client-side, group selected items by supplier phone, show a
confirm dialog ("Vas a enviar 5 mensajes a 5 proveedores"), and fire
one POST per supplier on confirm.

Acceptance:
  - The bulk-generate button has a data attribute marking it for
    consolidation (e.g., data-consolidate='by-supplier').
"""
from __future__ import annotations

import re
import uuid

from sqlalchemy.orm import sessionmaker

from tests.factories import make_ingredient


def test_reorder_bulk_button_has_consolidate_attr(client, session_factory):
    """P-36.1: bulk-generate button advertises consolidation."""
    # Seed an item so the bulk-generate section renders.
    s = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        make_ingredient(
            s, name=f"consol-{uuid.uuid4().hex[:8]}", unit="kg",
            stock_qty=0.5, min_stock_qty=5.0, purchase_price_gs=4500,
        )
        s.commit()
    finally:
        s.close()

    r = client.get("/reorder")
    assert r.status_code == 200
    body = r.text

    # The button is multiline so we use DOTALL.
    btn_match = re.search(
        r'<button[^>]*id="generate-po-btn"[^>]*>', body, re.DOTALL
    )
    assert btn_match, "no generate-po-btn in /reorder"
    btn_html = btn_match.group(0)

    # The data attribute should signal consolidation.
    assert "data-consolidate" in btn_html, (
        f"expected data-consolidate attribute on bulk-generate button: {btn_html[:200]}"
    )

