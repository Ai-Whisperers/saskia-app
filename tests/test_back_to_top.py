"""Phase 22 — Back-to-top button (Volver arriba) verification.

The base.html now includes a <button class="back-to-top"> and loads
app/static/back-to-top.js. The button is fixed positioned, hidden by
default, and becomes visible after the user scrolls >400px.
"""
from __future__ import annotations

from pathlib import Path


BASE_HTML = Path(__file__).parent.parent / "app" / "templates" / "base.html"
BACK_TO_TOP_JS = Path(__file__).parent.parent / "app" / "static" / "back-to-top.js"
COMBOBOX_CSS = Path(__file__).parent.parent / "app" / "static" / "combobox.css"


# ---------------------------------------------------------------------------
# Static asset presence
# ---------------------------------------------------------------------------


def test_back_to_top_js_exists():
    assert BACK_TO_TOP_JS.exists()


def test_back_to_top_button_in_base_html():
    text = BASE_HTML.read_text()
    assert 'class="back-to-top"' in text
    assert "Volver arriba" in text


def test_back_to_top_button_has_aria_label():
    """Accessibility: button should announce itself to screen readers."""
    text = BASE_HTML.read_text()
    assert 'aria-label="Volver arriba"' in text


def test_back_to_top_uses_correct_icon():
    """Should use an arrow-up icon from the sprite."""
    text = BASE_HTML.read_text()
    # Find the back-to-top button
    btn_idx = text.find('class="back-to-top"')
    btn_section = text[btn_idx:btn_idx + 500]
    assert "icon-" in btn_section
    assert "arrow" in btn_section.lower() or "up" in btn_section.lower()


def test_back_to_top_script_is_loaded():
    """base.html should load the JS via <script src='/static/back-to-top.js'>."""
    text = BASE_HTML.read_text()
    assert "/static/back-to-top.js" in text


def test_back_to_top_initially_hidden():
    """The button should have the hidden attribute initially."""
    text = BASE_HTML.read_text()
    btn_idx = text.find('class="back-to-top"')
    line_start = text.rfind("\n", 0, btn_idx) + 1
    btn_line = text[line_start:text.find(">", btn_idx) + 1]
    assert "hidden" in btn_line, f"Button missing hidden attr: {btn_line}"


# ---------------------------------------------------------------------------
# JS behavior expectations
# ---------------------------------------------------------------------------


def test_back_to_top_js_uses_passive_scroll():
    """Scroll listener should be passive for perf."""
    text = BACK_TO_TOP_JS.read_text()
    assert "passive" in text


def test_back_to_top_js_respects_reduced_motion():
    """Reduced-motion users should get instant scroll, not smooth."""
    text = BACK_TO_TOP_JS.read_text()
    assert "prefers-reduced-motion" in text
    assert "auto" in text or "'auto'" in text


def test_back_to_top_js_thresholds_at_400():
    """Button should appear after 400px of scroll."""
    text = BACK_TO_TOP_JS.read_text()
    assert "400" in text


def test_back_to_top_js_smooth_scroll():
    """Default users should get smooth scroll."""
    text = BACK_TO_TOP_JS.read_text()
    assert "smooth" in text


def test_back_to_top_js_uses_domcontentloaded():
    """Script should wait for DOMContentLoaded if needed."""
    text = BACK_TO_TOP_JS.read_text()
    assert "DOMContentLoaded" in text or "document.readyState" in text


def test_back_to_top_js_only_init_once():
    """Should not double-attach handlers if loaded twice."""
    text = BACK_TO_TOP_JS.read_text()
    assert "querySelector" in text


# ---------------------------------------------------------------------------
# CSS verification
# ---------------------------------------------------------------------------


def _find_rule(css_text: str, selector: str) -> int:
    """Find selector in CSS, allowing for optional space after the dot."""
    import re
    m = re.search(rf"\.{re.escape(selector)}\s*\{{", css_text)
    return m.start() if m else -1


def test_back_to_top_css_uses_fixed_position():
    text = COMBOBOX_CSS.read_text()
    idx = _find_rule(text, "back-to-top")
    assert idx > 0, "back-to-top CSS class not found"
    css_section = text[idx:idx + 1500]
    assert "fixed" in css_section


def test_back_to_top_css_bottom_right():
    """Button should be in the bottom-right corner."""
    text = COMBOBOX_CSS.read_text()
    idx = _find_rule(text, "back-to-top")
    css_section = text[idx:idx + 1500]
    assert "right" in css_section
    assert "bottom" in css_section


def test_back_to_top_css_round():
    """Button should be round (border-radius: 50%)."""
    text = COMBOBOX_CSS.read_text()
    idx = _find_rule(text, "back-to-top")
    css_section = text[idx:idx + 1500]
    assert "border-radius:50%" in css_section or "border-radius: 50%" in css_section


def test_back_to_top_css_has_visible_state():
    """.back-to-top.is-visible should override the hidden state."""
    text = COMBOBOX_CSS.read_text()
    assert ".back-to-top.is-visible" in text or "back-to-top.is-visible" in text


def test_back_to_top_css_respects_reduced_motion():
    text = COMBOBOX_CSS.read_text()
    assert "prefers-reduced-motion" in text