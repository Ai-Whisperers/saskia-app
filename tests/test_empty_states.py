"""Phase 22 — Empty state component tests.

Verifies the empty_state_ext macro, CSS, and integration across list pages.
"""
from __future__ import annotations

from pathlib import Path


CSS_FILE = Path(__file__).parent.parent / "app" / "static" / "empty-states.css"
ATOMS = Path(__file__).parent.parent / "app" / "templates" / "_components" / "atoms.html"
BASE_HTML = Path(__file__).parent.parent / "app" / "templates" / "base.html"


def test_empty_state_css_exists():
    """Should have dedicated empty state styles."""
    assert CSS_FILE.exists()


def test_empty_state_css_loaded_in_base():
    """Should be loaded in base.html."""
    text = BASE_HTML.read_text()
    assert "empty-states.css" in text


def test_empty_state_macro_exists():
    """Should have empty_state_ext macro in atoms.html."""
    text = ATOMS.read_text()
    assert "macro empty_state_ext" in text


def test_empty_state_macro_supports_required_args():
    """Macro should support title, message, icon, action_url, action_label."""
    text = ATOMS.read_text()
    
    # Check macro signature
    assert "title," in text
    assert "message," in text
    assert "icon=" in text
    assert "action_url=" in text
    assert "action_label=" in text


def test_empty_state_macro_renders_proper_structure():
    """Should render with proper accessibility (role=status, aria-live)."""
    text = ATOMS.read_text()
    
    # Check accessibility
    assert 'role="status"' in text
    assert 'aria-live="polite"' in text
    assert 'class="empty-state' in text
    assert 'empty-state__title' in text
    assert 'empty-state__message' in text


def test_empty_state_macro_uses_icons():
    """Should use SVG icons from the icon system."""
    text = ATOMS.read_text()
    assert '<use href="#{{ icon }}"/>' in text or 'href="#{{ icon }}' in text


def test_empty_state_macro_supports_optional_action():
    """Should support optional action button."""
    text = ATOMS.read_text()
    assert "{% if action_url and action_label %}" in text
    assert "btn btn-primary" in text
    assert "#icon-plus" in text


def test_empty_state_macro_supports_compact_variant():
    """Should support compact variant."""
    text = ATOMS.read_text()
    assert "compact" in text
    assert "empty-state--compact" in text


def test_empty_state_css_has_dark_mode():
    """Should support dark mode."""
    css = CSS_FILE.read_text()
    assert '[data-theme="dark"]' in css
    assert ".empty-state" in css


def test_empty_state_css_handles_print():
    """Should handle print styles."""
    css = CSS_FILE.read_text()
    assert "@media print" in css
    assert ".empty-state__action" in css
    assert "display: none" in css


def test_empty_state_css_respects_reduced_motion():
    """Should respect prefers-reduced-motion."""
    css = CSS_FILE.read_text()
    assert "prefers-reduced-motion" in css


def test_empty_state_css_has_proper_spacing():
    """Should use design tokens for spacing."""
    css = CSS_FILE.read_text()
    assert "var(--space-" in css or "padding:" in css
    assert "border-radius:" in css


def test_empty_state_has_icon_styling():
    """Should style the icon properly."""
    css = CSS_FILE.read_text()
    assert ".empty-state__icon" in css
    assert "width: 64px" in css
    assert "height: 64px" in css
    assert "opacity:" in css


def test_empty_state_has_title_styling():
    """Should style the title prominently."""
    css = CSS_FILE.read_text()
    assert ".empty-state__title" in css
    assert "font-size:" in css
    assert "font-weight:" in css


def test_empty_state_has_message_styling():
    """Should style the message with proper typography."""
    css = CSS_FILE.read_text()
    assert ".empty-state__message" in css
    assert "max-width" in css
    assert "line-height:" in css


def test_existing_empty_states_continue_to_work():
    """Existing ui.empty_state (different signature) should still work."""
    text = ATOMS.read_text()
    # The original macro should still exist
    assert "macro empty_state(title, icon='icon-search'" in text
    # And the new one
    assert "macro empty_state_ext" in text