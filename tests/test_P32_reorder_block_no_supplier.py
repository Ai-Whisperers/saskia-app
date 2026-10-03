"""P-32.3: /reorder must block submit on rows with no supplier.

The "sin proveedor" row currently renders a working Reponer form, so
the cashier can submit and create a stock movement with no supplier.
That breaks the audit trail and the supplier-cascade.

Fix: when `supplier_info[0]` is None, render the Reponer button as
`disabled` with a `data-blocked="no-supplier"` attribute and a tooltip
explaining why.

Acceptance:
  - The Reponer button has `disabled` and `data-blocked` on rows where
    the ingredient has no supplier.
  - The button still works for rows that DO have a supplier.
"""
from __future__ import annotations

import re
import uuid

from sqlalchemy.orm import sessionmaker

from tests.factories import make_ingredient, make_supplier


def test_reorder_no_supplier_row_blocks_submit(client, session_factory):
    """P-32.3: Reponer button is disabled when no supplier is attached."""
    unique = f"nosup-{uuid.uuid4().hex[:8]}"
    s = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        # Make ingredient below min, no supplier.
        make_ingredient(
            s, name=unique, unit="kg", stock_qty=0.5, min_stock_qty=5.0,
            purchase_price_gs=4500,
        )
        s.commit()
    finally:
        s.close()

    r = client.get("/reorder")
    assert r.status_code == 200, f"got {r.status_code}: {r.text[:500]}"
    body = r.text

    # At least one Reponer button (confirm-btn) should be disabled.
    confirm_btns = re.findall(
        r'<button[^>]*class="[^"]*confirm-btn[^"]*"[^>]*>', body
    )
    assert confirm_btns, "no confirm-btn found in body"
    # At least one of them should be disabled.
    assert any("disabled" in btn for btn in confirm_btns), (
        f"expected at least one confirm-btn to be disabled; got: {confirm_btns}"
    )
    # And the data-blocked attribute should mark the reason.
    assert "data-blocked" in body, (
        "expected data-blocked attribute on disabled Reponer buttons"
    )


def test_reorder_with_supplier_row_unblocks_submit(client, session_factory):
    """P-32.3: Reponer button is NOT disabled when supplier exists."""
    unique = f"withsup-{uuid.uuid4().hex[:8]}"
    s = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        ing = make_ingredient(
            s, name=unique, unit="kg", stock_qty=0.5, min_stock_qty=5.0,
            purchase_price_gs=4500,
        )
        sup = make_supplier(s, name=f"sup-{unique}", phone="+595 9XX")
        # Link them via the parent supplier_id (used by supplier_map fallback).
        ing.supplier_id = sup.id
        s.commit()
    finally:
        s.close()

    r = client.get("/reorder")
    body = r.text

    confirm_btns = re.findall(
        r'<button[^>]*class="[^"]*confirm-btn[^"]*"[^>]*>', body
    )
    assert confirm_btns, "no confirm-btn found in body"
    # When the row has a supplier, no confirm-btn should be disabled.
    for btn in confirm_btns:
        assert "disabled" not in btn, (
            f"confirm-btn should be enabled when supplier exists: {btn}"
        )
