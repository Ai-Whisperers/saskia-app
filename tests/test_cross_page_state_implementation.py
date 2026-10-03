"""Phase 22 — Cross-page state preservation tests.

state-preservation.js handles filter preservation, search queries, and form data
across page visits with localStorage and auto-save features.
"""
from __future__ import annotations

from pathlib import Path


STATE_JS = Path(__file__).parent.parent / "app" / "static" / "state-preservation.js"
BASE_HTML = Path(__file__).parent.parent / "app" / "templates" / "base.html"


def test_state_preservation_script_exists():
    """Should have a dedicated state preservation script."""
    assert STATE_JS.exists()


def test_state_preservation_is_loaded_in_base():
    """Should be loaded in base.html."""
    text = BASE_HTML.read_text()
    assert 'state-preservation.js' in text
    assert 'defer' in text


def test_state_preservation_has_filter_persistence():
    """Should preserve filter state across pages."""
    js = STATE_JS.read_text()
    
    # Check core state functions
    assert 'getFilters' in js
    assert 'setFilters' in js
    assert 'localStorage' in js
    
    # Check filter preservation patterns
    assert 'data-saskia-state' in js
    assert 'dataset.saskiaPage' in js  # Uses dataset.saskiaPage
    assert 'autosave' in js.lower()


def test_state_preservation_has_search_persistence():
    """Should preserve search queries across pages."""
    js = STATE_JS.read_text()
    
    # Check search state functions
    assert 'getSearch' in js
    assert 'setSearch' in js
    
    # Check auto-save for inputs
    assert 'addEventListener(\'input\'' in js
    assert 'addEventListener(\'change\'' in js


def test_state_preservation_has_form_drafts():
    """Should handle unsaved form data."""
    js = STATE_JS.read_text()
    
    # Check draft functions
    assert 'saveFormData' in js
    assert 'getFormData' in js
    assert 'clearOldDrafts' in js
    
    # Check form data preservation
    assert 'data-saskia-autosave' in js
    assert 'FormData' in js


def test_state_preservation_has_auto_events():
    """Should wire auto-save events automatically."""
    js = STATE_JS.read_text()
    
    # Check event listeners
    assert 'DOMContentLoaded' in js
    assert 'addEventListener(\'input\'' in js
    assert 'addEventListener(\'change\'' in js
    assert 'addEventListener(\'submit\'' in js


def test_state_preservation_has_error_handling():
    """Should handle localStorage errors gracefully."""
    js = STATE_JS.read_text()
    
    # Check try/catch blocks
    assert 'try {' in js
    assert 'catch (e)' in js
    assert 'console.warn' in js


def test_state_preservation_has_timeout_cleanup():
    """Should clean up old drafts automatically."""
    js = STATE_JS.read_text()
    
    # Check draft cleanup
    assert '24 * 60 * 60 * 1000' in js  # 24 hours
    assert 'clearOldDrafts' in js
    assert 'timestamp' in js


def test_state_preservation_handles_form_restoration():
    """Should restore saved form data."""
    js = STATE_JS.read_text()
    
    # Check restoration function
    assert 'restoreFormData' in js
    assert 'getFormData' in js
    assert 'querySelector' in js


def test_state_preservation_global_namespace():
    """Should expose StatePreservation globally."""
    js = STATE_JS.read_text()
    
    # Check global exposure
    assert 'window.StatePreservation' in js
    assert 'window.restoreFormData' in js


def test_insight_food_cost_has_state_attributes():
    """Insight food cost should have state preservation attributes."""
    template = Path(__file__).parent.parent / "app" / "templates" / "insight_food_cost.html"
    text = template.read_text()
    
    # Check form has auto-save
    assert 'data-saskia-autosave' in text
    
    # Check days_filter has state attributes
    assert 'data_saskia_state="days"' in text
    assert 'data_saskia_page="/insights/food-cost"' in text


def test_days_filter_macro_supports_state_attributes():
    """days_filter macro should support new data_* attributes."""
    macros = Path(__file__).parent.parent / "app" / "templates" / "_components" / "macros.html"
    text = macros.read_text()
    
    # Check macro signature
    assert 'data_saskia_state=None' in text
    assert 'data_saskia_page=None' in text
    
    # Check macro implementation
    assert 'data-saskia-page' in text
    assert 'data-saskia-state' in text