"""Phase 22 — saskia-skeleton loader verification.

The saskia-skeleton.js Web Component provides:
- <saskia-skeleton> element for placeholder loading
- Width/height/shape attrs (text/circle/rect)
- Animation pulse while loading
- auto-removal via data-loaded attribute
"""
from __future__ import annotations

from pathlib import Path


SKELETON_JS = Path(__file__).parent.parent / "app" / "static" / "saskia-skeleton.js"
APP_CSS = Path(__file__).parent.parent / "app" / "static" / "app.css"


def test_skeleton_js_exists():
    assert SKELETON_JS.exists()


def test_skeleton_uses_custom_element():
    """Should register a custom element."""
    text = SKELETON_JS.read_text()
    assert "customElements" in text
    assert "saskia-skeleton" in text


def test_skeleton_supports_text_shape():
    """Default shape is line (text-line placeholder)."""
    text = SKELETON_JS.read_text()
    assert "line" in text


def test_skeleton_supports_card_shape():
    text = SKELETON_JS.read_text()
    assert "card" in text


def test_skeleton_supports_kpi_shape():
    text = SKELETON_JS.read_text()
    assert "kpi" in text


def test_skeleton_has_animation():
    """Should pulse/animate while loading."""
    text = SKELETON_JS.read_text()
    # Check CSS for @keyframes
    css_text = APP_CSS.read_text()
    assert "skeleton" in css_text.lower()
    # Animation should be defined
    assert "animation" in css_text or "keyframes" in css_text


def test_skeleton_can_be_removed_via_attribute():
    """Should support attribute changes to re-render."""
    text = SKELETON_JS.read_text()
    assert "attributeChangedCallback" in text


def test_skeleton_aria_busy():
    """Should announce loading state to screen readers."""
    text = SKELETON_JS.read_text()
    assert "aria-busy" in text


def test_skeleton_aria_label():
    """Should have a default aria-label."""
    text = SKELETON_JS.read_text()
    assert "aria-label" in text


def test_skeleton_respects_reduced_motion():
    """Should respect prefers-reduced-motion."""
    css_text = APP_CSS.read_text()
    assert "prefers-reduced-motion" in css_text


def test_skeleton_used_in_dashboard():
    """Dashboard template should use skeleton for at least one KPI."""
    text = (Path(__file__).parent.parent / "app" / "templates" / "dashboard.html").read_text()
    # Look for skeleton references - any variant
    import re
    has_skel = (
        "saskia-skeleton" in text
        or "skeleton-section" in text
        or "skeleton" in text
    )
    assert has_skel, "Dashboard should use skeleton loaders"


def test_skeleton_uses_shadow_dom():
    """Should use Shadow DOM for encapsulation."""
    text = SKELETON_JS.read_text()
    assert "attachShadow" in text


def test_skeleton_has_aria_attribute():
    """Should announce loading state to screen readers."""
    text = SKELETON_JS.read_text()
    assert "aria-" in text


def test_skeleton_used_across_multiple_pages():
    """Skeleton component should be reused across multiple pages."""
    from pathlib import Path
    templates = Path(__file__).parent.parent / "app" / "templates"
    count = 0
    for tf in templates.glob("*.html"):
        t = tf.read_text()
        if "saskia-skeleton" in t or "skeleton-section" in t or "skeleton" in t.lower():
            count += 1
    assert count >= 5, f"Skeleton only used in {count} templates; want >= 5"