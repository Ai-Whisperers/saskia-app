"""P-28 / audit #28: /settings/catalog page heading must be clear, Spanish, descriptive.

The audit captured a screenshot with the heading "Nuestros únicos activos"
which was an internal-developer placeholder, not a user-facing title.
That placeholder has since been removed by a concurrent refactor (the page
is now tab-based with section labels like "Categorías producto").

This regression test ensures the page heading stays meaningful and the
tabs are labeled with bakery-domain language (Categorías, Familias,
Canales, etc.). It must NOT regress to placeholder/internal text.
"""
from __future__ import annotations

import re

import pytest

pytestmark = [pytest.mark.smoke]


# Placeholder text that should NEVER appear in the catalog settings heading.
# If we ever see this string again, the page has been re-broken.
# Matched case-insensitively as whole words / phrases to avoid false
# positives like "todo" (Spanish for "all/everything") or "placeholder"
# HTML attribute which is legitimate.
FORBIDDEN_HEADING_FRAGMENTS = [
    "nuestros únicos activos",
    "nuestros unicos activos",
    "lorem ipsum",
]


# Words that MUST appear somewhere in the visible page content
# (heading + tab labels + section text) — ensures the page is actually
# labeled with bakery-domain vocabulary.
REQUIRED_VOCABULARY = [
    "Categorías producto",  # first tab
    "Familias de receta",   # second tab
    "Canales de venta",     # third tab
    "Formas de pago",       # fourth tab
]


def test_settings_catalog_returns_200(client):
    """P-28: /settings/catalog must be reachable."""
    r = client.get("/settings/catalog")
    assert r.status_code == 200, f"/settings/catalog returned {r.status_code}"


def test_settings_catalog_has_page_title(client):
    """P-28: <title> must be meaningful (not the internal 'Settings' default)."""
    r = client.get("/settings/catalog")
    body = r.text
    title_m = re.search(r"<title>(?P<t>.*?)</title>", body, re.IGNORECASE | re.DOTALL)
    assert title_m, "Page missing <title> tag"
    title = title_m.group("t").strip()
    assert "Catálog" in title or "Catalog" in title, (
        f"Page title '{title}' should mention Catálogo/Catalog — "
        f"this is the settings catalog page"
    )


@pytest.mark.parametrize("forbidden", FORBIDDEN_HEADING_FRAGMENTS)
def test_settings_catalog_no_forbidden_placeholder_heading(client, forbidden):
    """P-28: Must not contain internal-developer placeholder text anywhere visible."""
    r = client.get("/settings/catalog")
    body_lower = r.text.lower()
    assert forbidden.lower() not in body_lower, (
        f"Page contains forbidden placeholder text '{forbidden}'. "
        f"This is the audit #28 bug regressing."
    )


@pytest.mark.parametrize("vocab", REQUIRED_VOCABULARY)
def test_settings_catalog_has_bakery_vocabulary(client, vocab):
    """P-28: Page must be labeled with bakery-domain tab vocabulary."""
    r = client.get("/settings/catalog")
    assert r.status_code == 200
    assert vocab in r.text, (
        f"Settings catalog page missing expected bakery tab label '{vocab}'. "
        f"Body (first 1500 chars):\n{r.text[:1500]}"
    )


def test_settings_catalog_has_h1_or_page_header(client):
    """P-28: The page must have an h1 or page-header div for the screen reader.

    Tab buttons alone are not a sufficient heading hierarchy — the page
    itself must be named.
    """
    r = client.get("/settings/catalog")
    body = r.text
    has_h1 = bool(re.search(r"<h1[\s>]", body, re.IGNORECASE))
    has_page_header = bool(re.search(r'<div[^>]*class="[^"]*page-header', body))
    assert has_h1 or has_page_header, (
        "Settings catalog page has no h1 or .page-header — "
        "screen readers and SEO need a top-level page title. "
        f"Body (first 2000 chars):\n{body[:2000]}"
    )
