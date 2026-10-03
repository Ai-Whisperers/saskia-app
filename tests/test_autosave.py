"""Phase 35 — Auto-save form drafts tests.

Verifies the data-autosave form draft persistence utility.
"""
from __future__ import annotations

from pathlib import Path


AUTOSAVE_JS = Path(__file__).parent.parent / "app" / "static" / "autosave.js"
BASE_HTML = Path(__file__).parent.parent / "app" / "templates" / "base.html"


def test_autosave_js_exists():
    """Should have autosave script."""
    assert AUTOSAVE_JS.exists()


def test_autosave_loaded_in_base():
    """Should be loaded in base.html."""
    text = BASE_HTML.read_text()
    assert "autosave.js" in text


def test_autosave_exposes_global():
    """Should expose AutoSave globally."""
    js = AUTOSAVE_JS.read_text()
    assert "window.AutoSave" in js


def test_autosave_uses_iife():
    """Should be wrapped in IIFE."""
    js = AUTOSAVE_JS.read_text()
    assert "(function()" in js
    assert "'use strict'" in js


def test_autosave_uses_data_attribute():
    """Should use data-autosave attribute on forms."""
    js = AUTOSAVE_JS.read_text()
    assert "data-autosave" in js
    assert "form[data-autosave]" in js


def test_autosave_has_debounce():
    """Should debounce saves for performance."""
    js = AUTOSAVE_JS.read_text()
    assert "debounceMs" in js
    assert "800" in js
    assert "_debounce" in js


def test_autosave_uses_localstorage():
    """Should use localStorage for persistence."""
    js = AUTOSAVE_JS.read_text()
    assert "localStorage.setItem" in js
    assert "localStorage.getItem" in js
    assert "localStorage.removeItem" in js


def test_autosave_stores_timestamp():
    """Should store timestamp with data."""
    js = AUTOSAVE_JS.read_text()
    assert "savedAt" in js
    assert "Date.now" in js


def test_autosave_serializes_checkboxes():
    """Should handle checkboxes correctly."""
    js = AUTOSAVE_JS.read_text()
    assert "type === 'checkbox'" in js
    assert "field.checked" in js


def test_autosave_serializes_radios():
    """Should handle radio buttons."""
    js = AUTOSAVE_JS.read_text()
    assert "type === 'radio'" in js


def test_autosave_serializes_multi_select():
    """Should handle multi-select fields."""
    js = AUTOSAVE_JS.read_text()
    assert "multiple" in js
    assert "selectedOptions" in js


def test_autosave_serializes_text_inputs():
    """Should handle text/textarea inputs."""
    js = AUTOSAVE_JS.read_text()
    assert "field.value" in js


def test_autosave_restores_form():
    """Should restore form on load."""
    js = AUTOSAVE_JS.read_text()
    assert "_restoreForm" in js
    assert "JSON.parse" in js


def test_autosave_expiry_24h():
    """Should expire drafts after 24 hours."""
    js = AUTOSAVE_JS.read_text()
    assert "24 * 60 * 60 * 1000" in js
    assert "removeItem(key)" in js


def test_autosave_clears_on_submit():
    """Should clear draft on form submit."""
    js = AUTOSAVE_JS.read_text()
    assert "form.addEventListener('submit'" in js
    assert "this._clear" in js


def test_autosave_handles_errors():
    """Should handle localStorage errors gracefully."""
    js = AUTOSAVE_JS.read_text()
    assert "try" in js
    assert "catch (e)" in js
    assert "console.warn" in js


def test_autosave_shows_restore_notice():
    """Should show notice when draft restored."""
    js = AUTOSAVE_JS.read_text()
    assert "_showRestoreNotice" in js
    assert "autosave-notice" in js
    assert "restauró" in js or "restored" in js


def test_autosave_discard_button():
    """Should have discard button."""
    js = AUTOSAVE_JS.read_text()
    assert "data-discard-autosave" in js
    assert "Descartar borrador" in js or "Discard draft" in js


def test_autosave_handles_empty():
    """Should handle empty drafts gracefully."""
    js = AUTOSAVE_JS.read_text()
    assert "if (!stored) return" in js or "if (!stored)" in js


def test_autosave_counts_restored_fields():
    """Should track number of restored fields."""
    js = AUTOSAVE_JS.read_text()
    assert "restored++" in js
    assert "restored > 0" in js


def test_autosave_dom_ready():
    """Should wait for DOM ready."""
    js = AUTOSAVE_JS.read_text()
    assert "readyState" in js
    assert "DOMContentLoaded" in js


def test_autosave_iterates_forms():
    """Should iterate all matching forms."""
    js = AUTOSAVE_JS.read_text()
    assert "querySelectorAll" in js
    assert "forEach" in js


def test_autosave_uses_input_listener():
    """Should listen to input events."""
    js = AUTOSAVE_JS.read_text()
    assert "'input'" in js


def test_autosave_uses_change_listener():
    """Should listen to change events."""
    js = AUTOSAVE_JS.read_text()
    assert "'change'" in js


def test_autosave_skips_unnamed_fields():
    """Should skip fields without name attribute."""
    js = AUTOSAVE_JS.read_text()
    assert "if (!field.name) return" in js


def test_autosave_form_reset_on_discard():
    """Should reset form when discarding."""
    js = AUTOSAVE_JS.read_text()
    assert "form.reset" in js