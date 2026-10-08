"""Phase 22 — form-dirty.js (unsaved-changes warning) verification.

The shared form-dirty.js binds to forms with [data-saskia-dirty] and
prompts via beforeunload if the user has unsaved changes.
"""

from __future__ import annotations

from pathlib import Path


FORM_DIRTY_JS = Path(__file__).parent.parent / "app" / "static" / "form-dirty.js"


def test_form_dirty_js_exists():
    assert FORM_DIRTY_JS.exists()


def test_form_dirty_js_uses_data_saskia_dirty():
    """Binds to forms with [data-saskia-dirty] attribute."""
    text = FORM_DIRTY_JS.read_text()
    assert "data-saskia-dirty" in text


def test_form_dirty_js_uses_beforeunload():
    text = FORM_DIRTY_JS.read_text()
    assert "beforeunload" in text


def test_form_dirty_js_calls_preventDefault():
    text = FORM_DIRTY_JS.read_text()
    assert "preventDefault" in text


def test_form_dirty_js_sets_returnValue():
    """Chrome requires e.returnValue = '' for the prompt to appear."""
    text = FORM_DIRTY_JS.read_text()
    assert "returnValue" in text


def test_form_dirty_js_listens_for_input():
    text = FORM_DIRTY_JS.read_text()
    # Should listen for "input" events
    assert "'input'" in text or '"input"' in text


def test_form_dirty_js_listens_for_change():
    """Also bind to 'change' for select/checkbox changes."""
    text = FORM_DIRTY_JS.read_text()
    assert "'change'" in text or '"change"' in text


def test_form_dirty_js_resets_on_submit():
    """When form is submitted, dirty flag should reset to false."""
    text = FORM_DIRTY_JS.read_text()
    assert "'submit'" in text or '"submit"' in text
    assert "dirty = false" in text or "dirty=false" in text


def test_form_dirty_js_initializes_on_domready():
    text = FORM_DIRTY_JS.read_text()
    assert "DOMContentLoaded" in text or "document.readyState" in text


def test_form_dirty_js_prevents_double_binding():
    """Guard against double-binding if loaded twice."""
    text = FORM_DIRTY_JS.read_text()
    assert "__saskiaDirtyBound" in text
