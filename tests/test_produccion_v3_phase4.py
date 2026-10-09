"""Tests for PRODUCCION-V3 Phase 4 — ad-hoc UX improvements.

The audit (H4, M6, M13) found the "Horneado extra" button was easy
to miss and the bulk-CSV paste was only in a hidden button.

Phase 4 ship:
  - Primary button is `btn-primary` (not `btn-secondary`).
  - The card shows the day's ad-hoc count when > 0.
  - The data-action delegation wiring is present in shortcuts.js.
  - The ad-hoc card is hidden from print (no-print).
  - The bulk-CSV modal is still present in the DOM.
"""

from __future__ import annotations

import re
from pathlib import Path

# ── HTML / route integration ─────────────────────────────────────


def test_adhoc_button_is_primary_class(client, qseed):
    qseed("with_kyrian_full")
    r = client.get("/produccion?for_date=2026-10-06&view=day")
    body = r.content.decode("utf-8", errors="replace")
    assert r.status_code == 200
    # The "+ Agregá horneado extra" button must be btn-primary now.
    m = re.search(
        r'<button[^>]*?data-action="open-adhoc-modal"[^>]*?class="([^"]+)"[^>]*?>',
        body,
    )
    if not m:
        # attributes in the other order
        m = re.search(
            r'<button[^>]*?class="([^"]+)"[^>]*?data-action="open-adhoc-modal"',
            body,
        )
    assert m, "ad-hoc open button not found in DOM"
    classes = m.group(1)
    assert "btn-primary" in classes, (
        f"ad-hoc button is {classes!r}, expected btn-primary for prominence"
    )


def test_adhoc_card_has_no_print_class(client, qseed):
    """The ad-hoc entry card must be hidden on the print view — the
    operator shouldn't see 'Agregá horneado extra' on a paper plan."""
    qseed("with_kyrian_full")
    r = client.get("/produccion?for_date=2026-10-06&view=day")
    body = r.content.decode("utf-8", errors="replace")
    assert r.status_code == 200
    # Either the whole section has no-print, or the buttons inside do.
    assert 'class="card mb-4 no-print"' in body or "data-adhoc-card" in body, (
        "ad-hoc card missing data-adhoc-card hook"
    )
    # And at least one of the buttons is no-print.
    assert re.search(
        r'<button[^>]*data-action="open-adhoc-(?:modal|bulk)"[^>]*class="[^"]*\bno-print\b',
        body,
    ) or re.search(
        r"<section[^>]*no-print[^>]*data-adhoc-card",
        body,
    ), "ad-hoc section should be hidden in print"


def test_adhoc_count_badge_appears_when_count_greater_than_zero(client, qseed):
    """The 'N hoy' badge must render next to the card title when at
    least one ad-hoc bake exists in the plan for for_date."""
    qseed("with_kyrian_full")
    # No ad-hoc bakes seeded, so the badge should be absent.
    r = client.get("/produccion?for_date=2026-10-06&view=day")
    body = r.content.decode("utf-8", errors="replace")
    assert r.status_code == 200
    # No badge when 0 (the {% if day_adhoc_count > 0 %} gate).
    # Look for data-adhoc-count — should NOT be present.
    assert "data-adhoc-count" not in body, "ad-hoc count badge rendered when day_adhoc_count=0"


def test_bulk_modal_still_in_dom(client, qseed):
    qseed("with_kyrian_full")
    r = client.get("/produccion?for_date=2026-10-06&view=day")
    body = r.content.decode("utf-8", errors="replace")
    assert r.status_code == 200
    assert 'id="adhoc-bulk-modal"' in body, "bulk-CSV modal missing from DOM"
    assert 'id="adhoc-modal"' in body, "single ad-hoc modal missing from DOM"


# ── Static-file integration ──────────────────────────────────────


def test_shortcuts_js_wires_data_action_handlers():
    """The data-action delegation must exist in shortcuts.js so the
    open-adhoc-modal / open-adhoc-bulk buttons actually open the
    dialogs (no inline onclick=)."""
    js = Path("/opt/data/profiles/ivan/scratch/saskia-app-work/app/static/shortcuts.js")
    src = js.read_text()
    assert "data-action" in src, "shortcuts.js must listen for data-action"
    assert "open-adhoc-modal" in src, "must handle open-adhoc-modal"
    assert "open-adhoc-bulk" in src, "must handle open-adhoc-bulk"
    # And the dialog IDs it targets must match what's in the template.
    assert "adhoc-modal" in src
    assert "adhoc-bulk-modal" in src


def test_no_inline_onclick_adhoc_in_template():
    """We removed the inline onclick= from the ad-hoc button. Make
    sure no regression re-adds it."""
    tpl = Path("/opt/data/profiles/ivan/scratch/saskia-app-work/app/templates/produccion.html")
    src = tpl.read_text()
    # There should be NO inline onclick= that opens an ad-hoc dialog.
    assert "onclick=\"document.getElementById('adhoc-modal').showModal()\"" not in src
    assert "onclick=\"document.getElementById('adhoc-bulk-modal').showModal()\"" not in src
