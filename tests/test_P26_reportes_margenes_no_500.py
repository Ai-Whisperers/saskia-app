"""P-26 / audit #3: /reportes/margenes 500 crash.

Audit #3: clicking the sidebar link /reportes/margenes returned HTTP
500 — the route was referenced but never implemented.

This test verifies that:
1. The route is reachable (not 500)
2. The response is either the proper margins report, OR a friendly
    "no data yet" / "coming soon" placeholder — NOT a Python traceback.
3. No 500s, no template render errors, no missing attribute exceptions.
"""
from __future__ import annotations

import pytest


pytestmark = [pytest.mark.smoke]


def test_reportes_margenes_does_not_500(client):
    """P-26 #3: /reportes/margenes must not crash with 500."""
    r = client.get("/reportes/margenes", follow_redirects=True)
    assert r.status_code != 500, (
        f"/reportes/margenes returned 500 — audit #3 crash. "
        f"Body excerpt: {r.text[:500]}"
    )
    # Acceptable outcomes:
    #  200 — page rendered (with data or empty state)
    #  303/307 — redirect (e.g. to /reportes if margenes is consolidated)
    #  404 — explicit "not implemented" page
    #  410 — gone (explicit removal)
    assert r.status_code in (200, 303, 307, 404, 410), (
        f"/reportes/margenes returned {r.status_code} — should be friendly."
    )


def test_reportes_margenes_no_traceback_in_html(client):
    """P-26 #3: No Python traceback in the rendered HTML."""
    r = client.get("/reportes/margenes", follow_redirects=True)
    if r.status_code == 200:
        body = r.text
        # Common traceback markers
        bad_markers = [
            "Traceback (most recent call last):",
            'class="traceback"',
            "Internal Server Error",
            "RuntimeError:",
            "AttributeError:",
            "KeyError:",
            "TypeError:",
            "NameError:",
        ]
        found = [m for m in bad_markers if m in body]
        assert not found, (
            f"Found traceback markers in /reportes/margenes response: {found}. "
            f"Audit #3: route is crashing."
        )


def test_reportes_margenes_has_page_chrome(client):
    """P-26: Even an empty / coming-soon page should have proper page chrome
    (page-header, navigation, footer)."""
    r = client.get("/reportes/margenes", follow_redirects=True)
    if r.status_code == 200:
        body = r.text
        assert (
            "page-header" in body or "container" in body or "main" in body
        ), "Missing page chrome on /reportes/margenes"


def test_sidebar_margenes_link_consistent(client):
    """P-26: The sidebar link to /reportes/margenes (when present) should
    reach a working page."""
    # Get the index/dashboard page and find the margenes sidebar link
    r = client.get("/reportes")
    if r.status_code == 200:
        body = r.text
        # The sidebar/nav often lists reports; if margenes is listed,
        # verify it works.
        if "/reportes/margenes" in body:
            r2 = client.get("/reportes/margenes", follow_redirects=True)
            assert r2.status_code != 500, (
                "Sidebar links to /reportes/margenes but the route 500s."
            )
