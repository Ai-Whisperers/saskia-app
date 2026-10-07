"""Ivan 2026-10-07 — sidebar disappeared at 13" laptop window widths.

The previous CSS collapsed the sidebar at <1024px. Many operators use
1024×600 split-screen layouts (laptop + side monitor, browser DevTools
docked, half-screen remote-desktop windows) where the sidebar slid
off-screen but the hamburger toggle was hidden too — the operator
couldn't open the navigation at all.

This test pins the new rule: the sidebar is visible by default from
601px and up. Only true phone widths (≤600px) get the slide-out
hamburger pattern.
"""
from __future__ import annotations

import re
from pathlib import Path


def test_css_sidebar_breakpoint_is_phone_width_only():
    """The hamburger/slide-out media query must trigger at <=600px,
    not the old 1023px. Anything above 600px shows the persistent
    sidebar so the operator can always reach navigation."""
    css = Path("app/static/app-shell.css").read_text()
    # The slide-out hamburger rule was `max-width: 1023px` historically.
    # If that string reappears, the bug is back.
    assert "@media (max-width: 1023px)" not in css, (
        "BUG: sidebar hamburger still triggers at <=1023px. Ivan lost "
        "the nav on his 13\" laptop. Should be <=600px (phone only)."
    )
    # The new rule must be present (covers the 601-1024 laptop range)
    assert "@media (max-width: 600px)" in css, (
        "the new phone-only hamburger breakpoint is missing — re-add it"
    )
    # Companion rule: >=601px must hide the hamburger toggle so it
    # doesn't double up with the persistent sidebar.
    assert "@media (min-width: 601px)" in css, (
        "missing companion rule: at >=601px the hamburger toggle must "
        "be hidden (the persistent sidebar is the only nav control)"
    )


def test_sidebar_renders_in_authed_html(authed_client, qseed):
    """On a logged-in page, the sidebar must be in the served HTML
    so the operator sees nav links without clicking anything."""
    r = authed_client.get("/produccion/manana")
    body = r.text
    assert 'class="sidebar"' in body or 'class="sidebar ' in body, (
        "sidebar element missing from served HTML"
    )
    # Has at least one nav group + at least one nav item
    assert body.count('sidebar-section') >= 1, "no sidebar sections rendered"
    assert body.count('class="nav-item') >= 1, "no nav items rendered"


def test_sidebar_default_open_on_first_render(authed_client, qseed):
    """The sidebar must NOT have the sidebar-open class on first
    render (which would close it on phones), but on a desktop-width
    viewport the inline CSS makes it visible regardless. We assert
    the page does not START with sidebar-open (which would close
    the mobile sidebar by default on phones)."""
    r = authed_client.get("/")
    body = r.text
    # The body class is set in CSS via JS click — initial render is clean
    # (no .sidebar-open). On a desktop viewport the sidebar is visible
    # because it has position:sticky, not because of any class.
    assert "sidebar-open" not in body.split("</head>")[1][:5000], (
        "sidebar started open on first render — phone users will see a "
        "permanent overlay covering their content"
    )


def test_base_sidebar_rule_does_not_hide_sidebar():
    """The base `.sidebar {}` rule must NOT include
    `transform: translateX(-100%)` — that hides the sidebar at every
    viewport. It belongs only in the phone-only @media block."""
    import re
    from pathlib import Path

    css = Path("app/static/app-shell.css").read_text()
    base_block = re.search(r"^\.sidebar\s*\{[^}]+\}", css, re.MULTILINE | re.DOTALL)
    assert base_block is not None, "no base .sidebar rule in app-shell.css"
    assert "translateX" not in base_block.group(0), (
        "BUG: base .sidebar rule contains translateX — sidebar is hidden "
        "by default at every viewport, not just on phones"
    )
