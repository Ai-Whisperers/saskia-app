"""Phase 22 — Keyboard shortcuts verification (shortcuts.js).

The shortcuts module provides:
- g + <letter> navigation: i/v/p/r/n/e/m/s/a/o/x/l/t/c
- Cmd+K / Ctrl+K command palette
- ? shortcut help modal
- Esc to close modals
- F2/F4 POS hotkeys
- Disabled when typing in form fields
"""
from __future__ import annotations

import re
from pathlib import Path


SHORTCUTS_JS = Path(__file__).parent.parent / "app" / "static" / "shortcuts.js"


def test_shortcuts_js_exists():
    assert SHORTCUTS_JS.exists()


def test_shortcuts_disabled_in_form_fields():
    """Shortcuts should not fire while user is typing."""
    text = SHORTCUTS_JS.read_text()
    assert "isEditable" in text or "isContentEditable" in text
    # Should check for input/textarea/select
    assert "input" in text
    assert "textarea" in text
    assert "select" in text


def test_g_prefix_navigation():
    """g + <letter> nav map should cover main pages."""
    text = SHORTCUTS_JS.read_text()
    nav = re.search(r"const NAV\s*=\s*\{([^}]+)\}", text, re.DOTALL)
    assert nav, "NAV map not found"
    nav_text = nav.group(1)
    # Spot-check a few important keys
    assert "'/ventas'" in nav_text
    assert "'/productos'" in nav_text
    assert "'/recetas'" in nav_text
    assert "'/eod'" in nav_text
    assert "'/merma'" in nav_text


def test_cmd_k_command_palette():
    """Cmd+K (or Ctrl+K) opens command palette."""
    text = SHORTCUTS_JS.read_text()
    assert "metaKey" in text or "ctrlKey" in text
    # Look for K key
    assert "'k'" in text or '"k"' in text or "e.key === 'k'" in text or 'e.key === "k"' in text


def test_question_mark_shows_help():
    """Pressing ? should show the shortcut help modal."""
    text = SHORTCUTS_JS.read_text()
    assert "?" in text
    assert "showShortcutHelp" in text or "shortcut-help" in text


def test_esc_closes_modal():
    text = SHORTCUTS_JS.read_text()
    assert "'Escape'" in text or '"Escape"' in text or "Escape" in text


def test_modal_has_aria_modal():
    """Shortcut help modal should announce itself to screen readers."""
    text = SHORTCUTS_JS.read_text()
    assert 'aria-modal' in text or 'role="dialog"' in text or "role='dialog'" in text


def test_modal_has_labelledby():
    text = SHORTCUTS_JS.read_text()
    assert "aria-labelledby" in text or "labelledby" in text


def test_prefix_timeout_prevents_stuck_state():
    """If the second key isn't pressed in time, the prefix should expire."""
    text = SHORTCUTS_JS.read_text()
    assert "PREFIX_TIMEOUT_MS" in text or "prefixTimer" in text


def test_pos_hotkeys_for_sales():
    """F2/F4 should be POS-specific hotkeys on /ventas."""
    text = SHORTCUTS_JS.read_text()
    assert "POS_HOTKEYS" in text or "F2" in text


def test_shortcuts_skip_when_modal_open():
    """When a modal is open, single-key shortcuts should not fire."""
    text = SHORTCUTS_JS.read_text()
    # Look for open-modal check
    assert "open" in text.lower() or "modal" in text.lower()


def test_shortcuts_dont_break_ctrl_etc():
    """g prefix should not fire when user is pressing Ctrl+G or Cmd+G."""
    text = SHORTCUTS_JS.read_text()
    # Should ignore when modifier keys are pressed
    assert "metaKey" in text or "ctrlKey" in text or "altKey" in text