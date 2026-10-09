"""P1-B6 — Cmd+K command palette + POS hotkeys (F2/F4).

The roadmap asks for "Cmd+K + atajos POS". We:
1. Added the palette UI to shortcuts.js (Cmd+K / Ctrl+K opens a modal).
2. Added F2/F4 to /ventas only — they click the data-action= buttons.
3. The topbar search button now opens the palette.

Run: cd /opt/data/profiles/ivan/scratch/sazon-app-work && ./.venv/bin/python -m pytest tests/test_p1_b6_cmdk_shortcuts.py -v

Note: this is a JS-only feature; tests verify the SHIPPED JS file contains
the expected wiring. Functional behavior must be smoke-tested in the browser.
"""

from __future__ import annotations

import re
from pathlib import Path


def _shortcuts_js() -> str:
    return Path("app/static/shortcuts.js").read_text()


def test_shortcuts_js_has_cmd_k_handler():
    """The keyboard handler for Cmd+K / Ctrl+K is present."""
    js = _shortcuts_js()
    assert "metaKey" in js and "ctrlKey" in js
    assert "openPalette()" in js or "openPalette" in js
    # Looks for a keydown listener that triggers on k
    assert re.search(r"e\.key\.toLowerCase\(\)\s*===\s*['\"]k['\"]", js)


def test_shortcuts_js_has_palette_modal():
    """The palette modal HTML is built dynamically."""
    js = _shortcuts_js()
    assert "cmd-k-palette" in js
    assert 'id="cmd-k-input"' in js
    assert 'id="cmd-k-results"' in js
    assert "Buscar página o acción" in js


def test_shortcuts_js_builds_items_from_sidebar():
    """The palette reads .sidebar .nav-item elements."""
    js = _shortcuts_js()
    assert "buildPaletteItems" in js
    assert ".sidebar .nav-item" in js


def test_shortcuts_js_handles_arrow_keys():
    """Arrow keys move the active item; Enter navigates."""
    js = _shortcuts_js()
    assert "ArrowDown" in js
    assert "ArrowUp" in js
    assert "Enter" in js or '"Enter"' in js


def test_shortcuts_js_includes_pos_hotkeys():
    """F2/F4 hotkeys are defined (only fire on /ventas)."""
    js = _shortcuts_js()
    assert "POS_HOTKEYS" in js
    assert "'F2'" in js or '"F2"' in js
    assert "'F4'" in js or '"F4"' in js
    assert 'data-action="save-sale"' in js
    assert 'data-action="apply-discount"' in js


def test_pos_hotkeys_only_fire_on_ventas():
    """The handler gates F2/F4 on /ventas to avoid leaking into other pages."""
    js = _shortcuts_js()
    assert "startsWith('/ventas')" in js


def test_topbar_button_opens_palette():
    """The #global-search-btn opens the palette when clicked."""
    js = _shortcuts_js()
    assert "global-search-btn" in js
    # The wiring lives inside showShortcutHelp (which is callable any time)
    assert "openPalette" in js


def test_shortcuts_js_includes_cmdk_in_help_modal():
    """The shortcut-help modal now mentions Cmd+K and F2/F4."""
    js = _shortcuts_js()
    assert "⌘K" in js or "Ctrl+K" in js or "Cmd+K" in js or "cmd-k" in js.lower()
    assert "Paleta de comandos" in js
    assert "F2" in js
    assert "F4" in js


def test_shortcuts_js_loads_in_base_template():
    """base.html includes /static/shortcuts.js so the palette is global."""
    base = Path("app/templates/base.html").read_text()
    assert "shortcuts.js" in base


def test_base_html_has_cmdk_kbd():
    """The topbar shows the ⌘K hint chip."""
    base = Path("app/templates/base.html").read_text()
    assert "⌘K" in base
