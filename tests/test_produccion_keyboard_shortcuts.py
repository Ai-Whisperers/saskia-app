"""Tests for /produccion D.5 — keyboard shortcuts.

Cooks can navigate production rows, open override, and toggle close-day
without lifting their hands from the keyboard. Saves ~10s/turn × 21
turns/day = ~1.5 h/mes.

Verified by static template/JS source inspection since the keyboard
handlers are pure client-side.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = REPO_ROOT / "app" / "templates" / "produccion.html"
SHORTCUTS = REPO_ROOT / "app" / "static" / "shortcuts.js"

TEMPLATE_SRC = TEMPLATE.read_text(encoding="utf-8")
SHORTCUTS_SRC = SHORTCUTS.read_text(encoding="utf-8")


# ────────────────────── shortcuts.js (D.5) ──────────────────────


def test_shortcuts_js_has_produccion_hotkeys():
    """D.5 — J/K/O/C handlers must be defined for /produccion."""
    assert "PROD_HOTKEYS" in SHORTCUTS_SRC, "D.5 — PROD_HOTKEYS map must be defined in shortcuts.js"
    # The 4 hotkeys we shipped
    for key, label in (
        ("'j'", "next row"),
        ("'k'", "prev row"),
        ("'o'", "override"),
        ("'c'", "close-day"),
    ):
        assert key in SHORTCUTS_SRC, f"D.5 — PROD_HOTKEYS['{label}'] missing"


def test_shortcuts_js_produccion_route_guard():
    """D.5 — Hotkeys only fire on /produccion and desktop viewports."""
    # The guard string must include path + viewport checks.
    assert "startsWith('/produccion')" in SHORTCUTS_SRC, (
        "D.5 — PROD_HOTKEYS must be guarded by /produccion path check"
    )
    assert "pointer: coarse" in SHORTCUTS_SRC, (
        "D.5 — PROD_HOTKEYS must skip on touch devices (pointer:coarse)"
    )
    assert "innerWidth >= 768" in SHORTCUTS_SRC, "D.5 — PROD_HOTKEYS must require viewport ≥768px"


def test_shortcuts_js_j_navigates_to_next_row():
    """D.5 — J moves focus to the next production row's qty input."""
    prod_idx = SHORTCUTS_SRC.find("const PROD_HOTKEYS")
    assert prod_idx > 0
    j_idx = SHORTCUTS_SRC.find("'j':", prod_idx)
    assert j_idx > 0
    block = SHORTCUTS_SRC[j_idx : j_idx + 800]
    assert "production-row" in block, "D.5 — J must target .production-row"
    assert ".progress-input" in block, "D.5 — J must focus the row's .progress-input (qty field)"
    assert "scrollIntoView" in block, "D.5 — J must scrollIntoView so the cook sees the new focus"


def test_shortcuts_js_k_navigates_to_previous_row():
    """D.5 — K moves focus to the previous production row's qty input."""
    prod_idx = SHORTCUTS_SRC.find("const PROD_HOTKEYS")
    assert prod_idx > 0
    k_idx = SHORTCUTS_SRC.find("'k':", prod_idx)
    assert k_idx > 0
    block = SHORTCUTS_SRC[k_idx : k_idx + 800]
    assert "production-row" in block
    assert "Math.max(idx - 1" in block, "D.5 — K must clamp at 0 (not go negative)"


def test_shortcuts_js_o_opens_override_for_active_row():
    """D.5 — O navigates to /produccion/override for the active row."""
    # Find PROD_HOTKEYS section first, then search within it.
    prod_idx = SHORTCUTS_SRC.find("const PROD_HOTKEYS")
    assert prod_idx > 0
    # Find 'o': inside PROD_HOTKEYS only (not NAV).
    o_idx = SHORTCUTS_SRC.find("'o':", prod_idx)
    assert o_idx > 0
    block = SHORTCUTS_SRC[o_idx : o_idx + 800]
    assert "data-product-id" in block, "D.5 — O must read the active row's data-product-id"
    assert "/produccion/override" in block, "D.5 — O must navigate to /produccion/override"


def test_shortcuts_js_c_toggles_close_day():
    """D.5 — C clicks the close-day button via its data-action hook."""
    prod_idx = SHORTCUTS_SRC.find("const PROD_HOTKEYS")
    assert prod_idx > 0
    c_idx = SHORTCUTS_SRC.find("'c':", prod_idx)
    assert c_idx > 0
    block = SHORTCUTS_SRC[c_idx : c_idx + 500]
    assert "toggle-close-day" in block, (
        "D.5 — C must click the button with data-action='toggle-close-day'"
    )


# ────────────────────── produccion.html ──────────────────────


def test_produccion_template_has_kbd_hint():
    """D.5 — A visible kbd-hint shows the cook which shortcuts exist."""
    assert "kbd-hint" in TEMPLATE_SRC, "D.5 — section header must include a kbd-hint element"
    # The 4 keys must appear as <kbd> elements
    for key in ("J</kbd>", "K</kbd>", "O</kbd>", "C</kbd>"):
        assert key in TEMPLATE_SRC, (
            f"D.5 — kbd-hint must include <kbd>{key.replace('</kbd>', '')}</kbd>"
        )


def test_produccion_template_close_day_button_has_data_action():
    """D.5 — The close-day button must have data-action='toggle-close-day'."""
    assert 'data-action="toggle-close-day"' in TEMPLATE_SRC, (
        "D.5 — close-day button must have data-action='toggle-close-day' "
        "so the C shortcut can find it"
    )


def test_produccion_template_hides_kbd_hint_on_mobile():
    """D.5 — kbd-hint must be hidden on touch / small viewports via CSS."""
    # The kbd-hint element is in the template; the hide-on-touch rule
    # lives in the global stylesheets (CSS deep-audit f65ce313 moved it
    # out of the template's inline block).
    assert "kbd-hint" in TEMPLATE_SRC, "D.5 — .kbd-hint element must exist"
    css = (REPO_ROOT / "app" / "static" / "app-shell.css").read_text(encoding="utf-8") + (
        REPO_ROOT / "app" / "static" / "app-improvements.css"
    ).read_text(encoding="utf-8")
    assert "kbd-hint" in css and "pointer: coarse" in css, (
        "D.5 — CSS must hide .kbd-hint on touch devices"
    )


# ────────────────────── help modal ──────────────────────


def test_shortcuts_help_modal_lists_produccion_keys():
    """D.5 — The ? help modal must list the new produccion shortcuts."""
    help_idx = SHORTCUTS_SRC.find("showShortcutHelp")
    assert help_idx > 0
    # The help modal is built via innerHTML; check that the new keys
    # are listed in the table body.
    help_end = SHORTCUTS_SRC.find("modal-body", help_idx)
    block = SHORTCUTS_SRC[help_idx : help_end + 5000]
    assert "Navegar filas" in block, "D.5 — help modal must describe J/K navigation"
    assert "override" in block.lower(), "D.5 — help modal must describe O override"
    assert "Cerrar" in block, "D.5 — help modal must describe C close-day"
