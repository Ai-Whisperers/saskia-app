"""PROD-MERMA-2: Verify the quick-merma modal disables inactive-tab inputs.

Bug: both tabs (ingrediente suelto + lote entero) have `name="reason"` and
`name="notes"` fields. When the form submits, the browser sends ALL of them —
including values from the hidden tab. This double-submission could confuse
the backend (multiple `reason` values in one POST) or leak empty values.

Fix: the qmSwitchTab JS function now disables every input in the inactive
panel so its values are excluded from form submission.
"""
from __future__ import annotations


def test_quick_merma_modal_html_loaded(client):
    """The quick-merma-modal <dialog> is in the rendered /produccion HTML."""
    r = client.get("/produccion?view=day")
    assert r.status_code == 200
    assert "quick-merma-modal" in r.text
    # The two reason combo fields exist (one per tab). The fix relies on JS
    # toggling disabled, so we just confirm the markup is correct here.
    # Count occurrences of name="reason" — at least 2 (one per tab).
    assert r.text.count('name="reason"') >= 2


def test_qmSwitchTab_JS_function_present(client):
    """The qmSwitchTab JS function (with togglePanelInputs) is in the page."""
    r = client.get("/produccion?view=day")
    body = r.text
    assert "function qmSwitchTab" in body
    assert "togglePanelInputs" in body
    assert "setAttribute('disabled'" in body or "setAttribute(\"disabled\"" in body
    assert "removeAttribute('disabled')" in body or "removeAttribute(\"disabled\")" in body


def test_quick_merma_modal_two_combos_per_panel(client):
    """Each panel has its own combo fields with `name="reason"` — confirms
    the JS-toggle is needed (otherwise both submit)."""
    r = client.get("/produccion?view=day")
    body = r.text
    # At least 2 reason combos (one per tab) + 2 notes textareas
    assert body.count('name="reason"') >= 2, (
        "Expected 2 reason combos (one per tab); got fewer — fix may not be needed"
    )
    assert body.count('name="notes"') >= 2, (
        "Expected 2 notes textareas (one per tab); got fewer — fix may not be needed"
    )
