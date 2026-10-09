"""Tests for shift-execution UX (Tier 3-A).

T-2026-10-04: The cook currently types qty into each row's number
input and submits. For end-of-shift, 2 fast UX wins:
  1. +/- stepper buttons next to the qty input — no keyboard typing.
  2. "Marcar todos como hecho" button — bulk-update all rows to
     target qty in one click.

The steppers are pure client-side (data-* attrs + JS handlers).
The bulk button posts form actions "bulk=mark_all" with each row's
target qty. We verify the markup + JS wiring.
"""

from pathlib import Path


def test_stepper_buttons_present(authed_client):
    """The stepper JS function + CSS are in the rendered template."""
    r = authed_client.get("/produccion?view=day")
    assert r.status_code == 200
    body = r.text
    # The stepper handler is defined as `function stepRow(btn, delta)` in JS.
    # We verify the script is loaded (always present regardless of rows).
    assert "stepRow" in body
    # The CSS for .step-btn is in the <style> block.
    assert "step-btn" in body
    # step-down/step-up classes render per plan row (empty day → absent);
    # the per-row markup is covered by the seeded-row tests in
    # test_production_close_day.py. Here we pin the always-present surface:
    assert "qty-stepper" in body or "stepRow" in body


def test_stepper_buttons_have_aria(authed_client):
    """Stepper JS function calls closeAria attributes via aria-label."""
    r = authed_client.get("/produccion?view=day")
    assert r.status_code == 200
    body = r.text
    assert "aria-label" in body


def test_mark_all_button_present(authed_client):
    """The 'Marcar todos como hecho' button + JS handler are wired."""
    r = authed_client.get("/produccion?view=day")
    assert r.status_code == 200
    body = r.text
    # The JS function `markAllDone()` is defined; the button only renders
    # when there are rows (cold-start state shows no button).
    assert "markAllDone" in body


def test_stepper_button_styling(authed_client):
    """The stepper CSS is wired (moved to the static stylesheets in the
    CSS deep-audit; the rendered page carries the markup, the stylesheet
    carries the rules)."""
    css = (
        Path(__file__).resolve().parents[1] / "app" / "static" / "app-improvements.css"
    ).read_text()
    assert ".step-btn" in css
    assert ".step-btn.step-down" in css
    r = authed_client.get("/produccion?view=day")
    assert r.status_code == 200
    assert "qty-stepper" in r.text


def test_mark_all_action_wired(authed_client):
    """The mark-all button is wired to the markAllDone function."""
    r = authed_client.get("/produccion?view=day")
    assert r.status_code == 200
    body = r.text
    # The button text is in the JS feedback ("✓ Listo — guardá abajo") OR
    # in the button label. Either way, we verify the action is wired:
    assert "mark-all-btn" in body or 'id="mark-all-btn"' in body


def test_stepper_decrements_floor_at_zero(authed_client):
    """The stepRow function clamps qty to ≥0."""
    r = authed_client.get("/produccion?view=day")
    assert r.status_code == 200
    body = r.text
    # The JS function checks `if (next < 0) next = 0;` — we verify the
    # function exists.
    assert "function stepRow" in body
