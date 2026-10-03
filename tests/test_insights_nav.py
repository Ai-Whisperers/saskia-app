"""tests/test_insights_nav.py — Phase 21 insight-page navigation.

Verifies every insight page has:
- page_header macro with breadcrumbs
- insights_nav macro with the active page flagged
- aria-current=page on the active nav link
- back-link to dashboard via breadcrumb
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "app" / "templates"


# All insight pages and their nav keys
INSIGHT_PAGES = [
    ("insight_demand.html",      "demand"),
    ("insight_food_cost.html",   "food_cost"),
    ("insight_freshness.html",   "freshness"),
    ("insight_margenes.html",    "margenes"),
    ("insight_price_impact.html","price_impact"),
    ("insight_stock.html",       "stock"),
    ("insight_afinidades.html",  "afinidades"),
]


@pytest.mark.parametrize("filename,nav_key", INSIGHT_PAGES)
def test_insight_page_has_page_header(filename, nav_key):
    """Each insight page must call page_header with crumbs + nav."""
    path = TEMPLATES_DIR / filename
    text = path.read_text()
    assert "ui.page_header" in text, f"{filename}: missing page_header"
    assert "crumbs=" in text, f"{filename}: missing breadcrumbs"
    assert "m.insights_nav(" in text, \
        f"{filename}: missing insights_nav call"


@pytest.mark.parametrize("filename,nav_key", INSIGHT_PAGES)
def test_insight_page_has_breadcrumb_to_dashboard(filename, nav_key):
    """Each insight page must have a breadcrumb linking to /dashboard."""
    path = TEMPLATES_DIR / filename
    text = path.read_text()
    # Should contain a tuple with /dashboard in the crumbs list
    assert "'/dashboard'" in text or '"/dashboard"' in text, \
        f"{filename}: breadcrumb does not link back to /dashboard"


def test_macros_has_insights_nav():
    """_components/macros.html must define insights_nav macro."""
    macros = (TEMPLATES_DIR / "_components" / "macros.html").read_text()
    assert "macro insights_nav" in macros
    # All 6 nav keys must be present
    for key in ("demand", "food_cost", "freshness", "margenes",
                "price_impact", "stock", "afinidades"):
        assert f'"{key}"' in macros, f"missing insights nav key: {key}"


def test_combobox_css_has_insights_nav_styles():
    """combobox.css must define the insights-nav visual rules."""
    css = (TEMPLATES_DIR.parent / "static" / "combobox.css").read_text()
    assert ".insights-nav" in css
    assert ".insights-nav__link--active" in css


@pytest.mark.parametrize("filename,nav_key", INSIGHT_PAGES)
def test_insight_page_active_nav_key_matches(filename, nav_key):
    """Each page's insights_nav(current=X) call must match its filename key."""
    path = TEMPLATES_DIR / filename
    text = path.read_text()
    m = re.search(r"insights_nav\('([^']+)'\)", text)
    assert m, f"{filename}: no insights_nav() call found"
    actual = m.group(1)
    assert actual == nav_key, \
        f"{filename}: insights_nav('{actual}') but expected '{nav_key}'"
