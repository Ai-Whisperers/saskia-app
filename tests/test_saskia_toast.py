"""Phase 22 — saskia-toast component verification.

The app/static/saskia-toast.js file already provides:
- <saskia-toast-stack> Web Component for stacking toasts
- window.SaskiaToast.show({...}) / dismiss() / dismissAll()
- 4 severities: success, info, warn, error
- Auto-dismiss after duration ms (default 4000)

These tests verify the module loads and exposes the expected API surface.
"""
from __future__ import annotations

import re
from pathlib import Path


SASKIA_TOAST = Path(__file__).parent.parent / "app" / "static" / "saskia-toast.js"


def test_saskia_toast_module_exists():
    assert SASKIA_TOAST.exists(), f"saskia-toast.js not found at {SASKIA_TOAST}"


def test_saskia_toast_defines_global():
    """The module should expose window.SaskiaToast."""
    text = SASKIA_TOAST.read_text()
    assert "window.SaskiaToast" in text
    assert "SaskiaToast.show" in text or ".show:" in text


def test_saskia_toast_has_severity_levels():
    """Toasts support success/info/warn/error severities."""
    text = SASKIA_TOAST.read_text()
    for sev in ("success", "info", "warn", "error"):
        assert sev in text, f"Missing severity: {sev}"


def test_saskia_toast_has_aria_live():
    """Toasts should be accessible — aria-live attribute for screen readers."""
    text = SASKIA_TOAST.read_text()
    assert "aria-live" in text


def test_saskia_toast_auto_dismiss():
    """Toasts should auto-dismiss after the duration."""
    text = SASKIA_TOAST.read_text()
    assert "duration" in text
    # Either setTimeout for dismiss or a similar mechanism
    assert "setTimeout" in text or "_dismiss" in text


def test_saskia_toast_custom_element_registered():
    """Should register the <saskia-toast-stack> custom element."""
    text = SASKIA_TOAST.read_text()
    assert "customElements" in text
    assert "saskia-toast-stack" in text


def test_saskia_toast_supports_actions():
    """Toasts can have action buttons (e.g. "Deshacer")."""
    text = SASKIA_TOAST.read_text()
    # Check for action handling
    assert "action" in text.lower()


def test_saskia_toast_dismiss_methods():
    """API should include show/dismiss/dismissAll."""
    text = SASKIA_TOAST.read_text()
    assert "show" in text
    assert "dismiss" in text
    assert "dismissAll" in text


def test_saskia_toast_responsive():
    """Toasts should adapt to mobile width (responsive CSS)."""
    text = SASKIA_TOAST.read_text()
    assert "@media" in text or "max-width" in text


def test_saskia_toast_uses_shadow_dom():
    """Web Component should use Shadow DOM for encapsulation."""
    text = SASKIA_TOAST.read_text()
    assert "attachShadow" in text or "shadowRoot" in text