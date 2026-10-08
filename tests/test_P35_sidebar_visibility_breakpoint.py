"""Ivan, early Oct 2026 — sidebar disappeared at 13" laptop window widths.

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
        'the nav on his 13" laptop. Should be <=600px (phone only).'
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
    assert body.count("sidebar-section") >= 1, "no sidebar sections rendered"
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


def test_no_top_level_display_none_on_sidebar():
    """Early-Oct-2026 Ivan note: a .eod_print section in app-improvements.css
    had a top-level `.sidebar { display: none !important; }` rule
    (missing the .eod-print prefix). This hid the persistent sidebar
    on every page, not just eod_print. Pin the fix: any top-level
    rule in app-improvements.css whose SELECTOR (not just comment
    text) targets `.sidebar` is the bug. Strip CSS comments before
    matching so the explanatory comment we left in place does not
    trigger a false positive."""
    import re
    from pathlib import Path

    css = Path("app/static/app-improvements.css").read_text()
    # Strip /* ... */ comments so they don't trip the selector scan
    css_no_comments = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)

    depth = 0
    in_print = False
    i = 0
    while i < len(css_no_comments):
        brace = min(
            (css_no_comments.find("{", i), css_no_comments.find("}", i)),
            key=lambda x: x if x >= 0 else 10**9,
        )
        if brace < 0:
            break
        chunk = css_no_comments[i:brace]
        if brace == css_no_comments.find("{", i):
            if "@media" in chunk and "print" in chunk:
                in_print = True
            depth += 1
        else:
            depth -= 1
            if depth == 0:
                in_print = False
        # Check the SELECTOR chunk (between depth-0 .. depth=1) for
        # an un-scoped .sidebar reference. A correctly-scoped rule
        # like `.eod-print .sidebar` is fine because the selector
        # contains `.eod-print` BEFORE `.sidebar`.
        if depth == 1 and not in_print and ".sidebar" in chunk:
            sel = chunk.strip()
            # An un-scoped `.sidebar` reference is the bug. The
            # fix scopes it to `.eod-print .sidebar` (with the parent
            # class before it). Accept any selector that has a
            # non-`.sidebar` class/component preceding `.sidebar`.
            # Simplest check: split the selector on commas; for each
            # part, if it contains `.sidebar` as a standalone token
            # (not preceded by another class), it's unscoped.
            for part in sel.split(","):
                part = part.strip()
                # Find the position of `.sidebar` in this selector part
                idx = part.find(".sidebar")
                if idx < 0:
                    continue
                # If there's another class BEFORE it (e.g. ".eod-print .sidebar")
                # or it's a different element selector like "aside.sidebar" (which
                # we still want to allow if scoped), we accept it.
                # Standalone `.sidebar` selector or starting with `.sidebar` and
                # not preceded by another class is the bug.
                prefix = part[:idx].strip()
                # If the prefix is empty or just a parent combinator (no class),
                # this `.sidebar` is unscoped. That is the bug.
                if not prefix or prefix in (">", "+", "~") or prefix.startswith("&"):
                    raise AssertionError(
                        f"BUG: app-improvements.css has an un-scoped "
                        f"`{part}` selector outside @media print. This "
                        f"hides the persistent sidebar on every page "
                        f"instead of just the EOD print view. Scope it "
                        f"to `.eod-print .sidebar` (or similar parent)."
                    )
        i = brace + 1
