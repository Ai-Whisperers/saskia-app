"""Phase 22 — Flex/gap utility class tests.

The combobox.css adds:
- .flex-center { display: flex; align-items: center; justify-content: center; }
- .flex-between { display: flex; align-items: center; justify-content: space-between; }
- .flex-wrap { flex-wrap: wrap; }
- .gap-1 { gap: var(--space-1); }
- .gap-3 { gap: var(--space-3); }

app.css already has:
- .flex, .flex-col, .gap-2, .gap-4, .items-center, .justify-between, .justify-end
"""
from __future__ import annotations

import re
from pathlib import Path


COMBOBOX_CSS = Path(__file__).parent.parent / "app" / "static" / "combobox.css"
APP_CSS = Path(__file__).parent.parent / "app" / "static" / "app.css"


def _get_rule(css_text: str, selector: str) -> str:
    """Extract the rule body for a given selector."""
    # Find .selector{...}
    m = re.search(rf"\.{re.escape(selector)}\s*\{{([^}}]+)\}}", css_text)
    return m.group(1) if m else ""


def test_flex_center_exists():
    body = _get_rule(COMBOBOX_CSS.read_text(), "flex-center")
    assert "display:flex" in body or "display: flex" in body
    assert "align-items:center" in body or "align-items: center" in body
    assert "justify-content:center" in body or "justify-content: center" in body


def test_flex_between_exists():
    body = _get_rule(COMBOBOX_CSS.read_text(), "flex-between")
    assert "display:flex" in body or "display: flex" in body
    assert "justify-content:space-between" in body or "justify-content: space-between" in body


def test_flex_wrap_exists():
    body = _get_rule(COMBOBOX_CSS.read_text(), "flex-wrap")
    assert "flex-wrap: wrap" in body


def test_gap_1_exists():
    body = _get_rule(COMBOBOX_CSS.read_text(), "gap-1")
    assert "--space-1" in body


def test_gap_3_exists():
    body = _get_rule(COMBOBOX_CSS.read_text(), "gap-3")
    assert "--space-3" in body


def test_existing_flex_class_in_app_css():
    """Pre-existing .flex utility is available."""
    body = _get_rule(APP_CSS.read_text(), "flex")
    assert "display:flex" in body or "display: flex" in body


def test_existing_flex_col_in_app_css():
    body = _get_rule(APP_CSS.read_text(), "flex-col")
    assert "flex-direction:column" in body or "flex-direction: column" in body


def test_existing_gap_2_in_app_css():
    body = _get_rule(APP_CSS.read_text(), "gap-2")
    assert "--space-2" in body


def test_existing_gap_4_in_app_css():
    body = _get_rule(APP_CSS.read_text(), "gap-4")
    assert "--space-4" in body


def test_existing_items_center_in_app_css():
    body = _get_rule(APP_CSS.read_text(), "items-center")
    assert "align-items:center" in body or "align-items: center" in body


def test_existing_justify_between_in_app_css():
    body = _get_rule(APP_CSS.read_text(), "justify-between")
    assert "justify-content:space-between" in body or "justify-content: space-between" in body


def test_no_duplicate_flex_center():
    """Verify we don't accidentally re-add flex-center to app.css."""
    app = APP_CSS.read_text()
    combo = COMBOBOX_CSS.read_text()
    # flex-center should only be in combobox.css
    if "flex-center" in app:
        # If it's in app.css too, it should be identical to combobox.css
        assert _get_rule(app, "flex-center") == _get_rule(combo, "flex-center")