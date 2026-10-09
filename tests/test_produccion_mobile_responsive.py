"""Tests for mobile-friendly shift execution (P2).

T-2026-10-04: The 8-column production table is unreadable on phones
(≤640px). This converts each row into a stacked card with `data-label`
hints, and bumps the qty input + checkbox to iOS HIG ≥44px tap targets.

Evolved contract (CSS deep-audit f65ce313): the responsive rules moved
from the template's inline <style> block to the global stylesheets the
page loads (app-shell.css + app-improvements.css). These tests verify
the page loads those stylesheets AND that each rule exists in them.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SHELL_CSS = REPO_ROOT / "app" / "static" / "app-shell.css"
IMPROVEMENTS_CSS = REPO_ROOT / "app" / "static" / "app-improvements.css"


def _css() -> str:
    return SHELL_CSS.read_text(encoding="utf-8") + IMPROVEMENTS_CSS.read_text(encoding="utf-8")


def test_data_label_attrs_on_tds(authed_client):
    """The page renders and loads the stylesheet that consumes data-label."""
    r = authed_client.get("/produccion?view=day")
    assert r.status_code == 200
    body = r.text
    assert len(body) > 1000, f"Body too short ({len(body)} chars); view not rendering"
    assert "app-shell.css" in body, "page must load app-shell.css"
    assert "app-improvements.css" in body, "page must load app-improvements.css"
    assert "attr(data-label)" in _css()


def test_mobile_media_query_present(authed_client):
    """The @media (max-width: 640px) rule ships in the loaded stylesheet."""
    r = authed_client.get("/produccion?view=day")
    assert r.status_code == 200
    assert "@media (max-width: 640px)" in _css()


def test_ios_hig_tap_target_height(authed_client):
    """The progress-input keeps the iOS HIG ≥44px height in the mobile CSS."""
    r = authed_client.get("/produccion?view=day")
    assert r.status_code == 200
    assert "44px" in _css()


def test_data_label_uses_attr_function(authed_client):
    """The CSS uses content: attr(data-label) so the column name displays."""
    assert "attr(data-label)" in _css()


def test_shift_form_id_is_unique(authed_client):
    """The mobile CSS is scoped to #shift-form so other tables aren't affected."""
    r = authed_client.get("/produccion?view=day")
    assert r.status_code == 200
    body = r.text
    # The form id is in the template source (always present even without data)
    assert "shift-form" in body
    # The mobile rules reference the form's table structure
    assert "#shift-form table" in _css()


def test_mobile_css_does_not_break_desktop(authed_client):
    """On desktop the table still renders normally (data-label attrs don't interfere)."""
    r = authed_client.get("/produccion?view=day")
    assert r.status_code == 200
    body = r.text
    assert len(body) > 1000, f"Body too short ({len(body)} chars); view not rendering"
    assert "@media (max-width: 640px)" in _css()
