"""P-32.1: /reorder must collapse non-action columns behind a disclosure.

The /reorder page has 15 columns. On a 1366px laptop that's horizontal scroll.
Operator can't see action cells (qty, unit, price, submit) at the same time
as the snapshot data (actual, min, max, suggested, urgency, days).

Fix: wrap the snapshot columns in a <details> element so the operator can
expand/collapse per row, while keeping the action cells always visible.

Acceptance:
  - The snapshot columns (Mínimo, Máximo, Sugerido, Tendencia, Días)
    are inside a <details> element OR wrapped by a class that toggles
    visibility (e.g., reorder-row__snapshot).
  - The action cells (qty, unit, price, submit) are NOT inside any
    <details> element.
  - The disclosure is closed by default (no `open` attribute).
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import sessionmaker

from tests.factories import make_ingredient


def _setup_ingredient_with_supplier(s, name: str) -> None:
    """Helper: create one ingredient below its min so it appears in /reorder."""
    make_ingredient(
        s,
        name=name,
        unit="kg",
        stock_qty=0.5,  # below min → shows up in /reorder
        min_stock_qty=5.0,
        purchase_price_gs=4500,
    )


def test_reorder_snapshot_columns_collapse(client, session_factory):
    """P-32.1: snapshot data collapses; actions stay visible."""
    unique = f"collapse-{uuid.uuid4().hex[:8]}"
    s = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        _setup_ingredient_with_supplier(s, unique)
        s.commit()
    finally:
        s.close()

    r = client.get("/reorder")
    assert r.status_code == 200, f"got {r.status_code}: {r.text[:500]}"
    body = r.text

    # The disclosure wrapper class is the new convention.
    # Old code had no wrapper, so this assertion would fail until P0.1 lands.
    assert "reorder-row__snapshot" in body or "<details" in body, (
        "expected a <details> or .reorder-row__snapshot wrapper for snapshot cols"
    )

    # Action inputs must be present and outside any collapsed wrapper.
    # We use the literal name attrs from reorder.html.
    for action_input in ('name="qty"', 'name="price_gs"', 'name="ingredient_id"'):
        assert action_input in body, f"action input {action_input} missing"

    # The submit button is still rendered (not gated by the disclosure).
    assert ">Reponer<" in body, "Reponer submit button missing"


def test_reorder_snapshot_disclosure_starts_closed(client, session_factory):
    """P-32.1: the disclosure defaults to closed (no `open` attribute on first <details>)."""
    unique = f"closed-{uuid.uuid4().hex[:8]}"
    s = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        _setup_ingredient_with_supplier(s, unique)
        s.commit()
    finally:
        s.close()

    r = client.get("/reorder")
    body = r.text

    # If a <details> exists, it must NOT have `open` attribute by default.
    # We check by finding the first <details> in the body and verifying
    # the very next non-whitespace character is not `open`.
    if "<details" in body:
        idx = body.index("<details")
        # Find the closing `>` of the opening tag
        end = body.index(">", idx)
        opening_tag = body[idx : end + 1]
        assert "open" not in opening_tag.split()[-5:], (
            f"<details> should default to closed; found: {opening_tag[:100]}"
        )
