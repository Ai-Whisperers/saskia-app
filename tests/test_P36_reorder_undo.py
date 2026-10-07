"""P-36.2: /reorder bulk-generate should offer an undo affordance.

Double-clicking the bulk-generate button can fire two sets of WhatsApp
messages. We need either a debounce or a 5s undo toast on the response.

Acceptance:
  - The bulk-generate button has data-undo-window attribute (a
    non-zero number of seconds) signalling an undo path.
  - The bulk form's action attribute is /reorder/generate-po OR a
    similar endpoint that supports undo.
"""

from __future__ import annotations

import re
import uuid

from sqlalchemy.orm import sessionmaker

from tests.factories import make_ingredient


def test_reorder_bulk_button_has_undo_attr(client, session_factory):
    """P-36.2: bulk-generate button advertises an undo window."""
    s = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        make_ingredient(
            s,
            name=f"undo-{uuid.uuid4().hex[:8]}",
            unit="kg",
            stock_qty=0.5,
            min_stock_qty=5.0,
            purchase_price_gs=4500,
        )
        s.commit()
    finally:
        s.close()

    r = client.get("/reorder")
    assert r.status_code == 200
    body = r.text

    btn_match = re.search(r'<button[^>]*id="generate-po-btn"[^>]*>', body, re.DOTALL)
    assert btn_match, "no generate-po-btn"
    btn_html = btn_match.group(0)

    assert "data-undo-window" in btn_html, (
        f"expected data-undo-window attribute on bulk-generate button: {btn_html[:200]}"
    )
    # The window should be a positive number.
    win_match = re.search(r'data-undo-window="(\d+)"', btn_html)
    if win_match:
        secs = int(win_match.group(1))
        assert 1 <= secs <= 60, f"undo window should be 1-60s; got {secs}"
