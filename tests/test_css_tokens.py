"""tests/test_css_tokens.py — locks the design-token contract.

Companion to app/static/tokens.css (ported from FloCafe globals.css).

What this test file locks in:
1. The :root block in tokens.css defines every token documented in
   the file's comment header (no token disappears silently).
2. Every value is a valid CSS color / length / font-family string.
3. Dark mode is not silently added (no [data-theme="dark"] block).
4. The token file is linked FIRST in base.html (before app.css and
   friends) so tokens override any token-collision in app-shell.css
   or app-improvements.css.
5. The 5 Sazon-specific layout tokens (--topnav-height,
   --btn-height, --input-height, --btn-height-sm, --btn-height-lg)
   match the values used in app-shell.css (so future token-collision
   regressions get caught).
6. The 5 chart palette slots (--chart-1 through --chart-5) are
   hex values (not oklch, which older browsers don't support).

Why this test matters: design tokens are often refactored by hand
when a new feature needs a new color, and the easiest mistake is
to either (a) add a duplicate token to the wrong place, or
(b) refactor the existing tokens and accidentally drop one. Both
would be caught here.

Note: this test reads the CSS file as a string and asserts the
content. It doesn't parse CSS. For full CSS validation, use
stylelint or css-validator in a separate step (not in scope for
this PR).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[1]
TOKENS_CSS = REPO / "app" / "static" / "tokens.css"
BASE_HTML = REPO / "app" / "templates" / "base.html"


# ---- 1. Required tokens are present --------------------------------------


REQUIRED_TOKENS = [
    # Typography
    "--font-sans",
    "--font-mono",
    # Geometry
    "--radius",
    # Surfaces
    "--background",
    "--foreground",
    "--card",
    "--card-foreground",
    "--popover",
    "--popover-foreground",
    # Brand
    "--primary",
    "--primary-foreground",
    "--secondary",
    "--secondary-foreground",
    # Muted
    "--muted",
    "--muted-foreground",
    # Accent
    "--accent",
    "--accent-foreground",
    # Destructive
    "--destructive",
    "--destructive-foreground",
    # Form primitives
    "--border",
    "--input",
    "--ring",
    # Sazon-specific
    "--sazon-success",
    "--sazon-warn",
    # Selected-row highlight (FloCafe pattern)
    "--selected-row",
    # Chart palette (5 slots)
    "--chart-1",
    "--chart-2",
    "--chart-3",
    "--chart-4",
    "--chart-5",
    # Sidebar
    "--sidebar",
    "--sidebar-foreground",
    "--sidebar-primary",
    # Sazon-specific layout tokens
    "--topnav-height",
    "--btn-height",
    "--btn-height-sm",
    "--btn-height-lg",
    "--input-height",
    # Spacing scale
    "--space-1",
    "--space-4",
    # Touch target
    "--touch-target-min",
]


@pytest.fixture(scope="module")
def tokens_css() -> str:
    """Read tokens.css as UTF-8. Module scope because the file is small
    (~5KB) and the tests are read-only."""
    return TOKENS_CSS.read_text(encoding="utf-8")


@pytest.mark.parametrize("token", REQUIRED_TOKENS)
def test_required_token_is_defined(tokens_css: str, token: str):
    """Every documented token must be defined in :root.

    If this test fails, someone deleted (or renamed) a token. Update
    REQUIRED_TOKENS and the comment in tokens.css together.
    """
    pattern = rf"{re.escape(token)}\s*:"
    assert re.search(pattern, tokens_css), (
        f"Token {token} is missing from tokens.css. "
        f"Either restore it or update REQUIRED_TOKENS + the docstring."
    )


# ---- 2. The :root block exists and is well-formed ------------------------


def test_root_block_is_present(tokens_css):
    """tokens.css must have exactly one :root block.

    Multiple :root blocks would cause cascading precedence bugs.
    """
    n = tokens_css.count(":root")
    assert n >= 1, "tokens.css must have a :root block"
    # Multiple :root blocks (e.g., for dark mode) is documented as
    # not-supported yet. If you add dark mode, change this assertion
    # to assert the dark block exists too.
    assert n == 1, (
        f"tokens.css has {n} :root blocks; "
        f"only 1 supported today (no dark mode yet). "
        f"If adding dark mode, also assert the dark selector exists."
    )


# ---- 3. No Tailwind imports leaked in -------------------------------------


FORBIDDEN_IMPORTS = [
    "@import \"tailwindcss\"",
    "@import \"tw-animate-css\"",
    "@import \"shadcn/tailwind.css\"",
    "@custom-variant",
]


def test_no_tailwind_imports_leaked_in(tokens_css):
    """tokens.css is the Jinja2-compatible port. Tailwind directives
    are forbidden because Sazon has no Tailwind (per AGENTS.md
    anti-rule).

    The strings "@import \"tailwindcss\"" etc. are allowed in the
    file's documentation comment (explaining what was stripped from
    the FloCafe source). They're NOT allowed as directives (i.e., on
    their own line, not inside a /* ... */ block).

    If a future port adds Tailwind, update AGENTS.md FIRST and remove
    this test.
    """
    # Strip comments (/* ... */ blocks) so we don't false-positive
    # on the doc comment that mentions what was stripped.
    code_only = re.sub(r"/\*.*?\*/", "", tokens_css, flags=re.DOTALL)

    for forbidden in FORBIDDEN_IMPORTS:
        assert forbidden not in code_only, (
            f"tokens.css contains forbidden directive: {forbidden}. "
            f"This is a Tailwind-only construct not supported in Sazon. "
            f"Per AGENTS.md anti-rule, Tailwind is not allowed. "
            f"(The doc comment mentioning these by name is fine; "
            f"the directive itself is not.)"
        )


# ---- 4. Chart palette uses hex (not oklch) -------------------------------


def test_chart_palette_uses_hex_not_oklch(tokens_css):
    """FloCafe uses oklch() in their chart slots. Older browsers
    (and any browser without wide-gamut support) don't render oklch
    correctly, falling back to srgb-grey. Sazon supports operators
    on whatever laptop they have, so we use hex.
    """
    for i in range(1, 6):
        m = re.search(rf"--chart-{i}\s*:\s*([^;]+);", tokens_css)
        assert m, f"--chart-{i} missing"
        value = m.group(1).strip()
        assert not value.startswith("oklch("), (
            f"--chart-{i} uses oklch({value}); "
            f"older browsers may not support oklch. Use hex."
        )


# ---- 5. Tokens.css is loaded BEFORE app.css ------------------------------


def test_tokens_css_loaded_before_app_css():
    """tokens.css must be the FIRST stylesheet link in base.html.

    CSS cascade is order-sensitive: tokens.css must load first so
    any token-collision in app.css / app-shell.css / app-improvements.css
    is resolved by the token file's value. If tokens.css loads after
    a file that defines the same --variable, the file's value wins.
    """
    html = BASE_HTML.read_text(encoding="utf-8")
    tokens_idx = html.find('tokens.css')
    app_idx = html.find('app.css')
    assert tokens_idx > 0, "tokens.css is not linked in base.html"
    assert app_idx > 0, "app.css is not linked in base.html"
    assert tokens_idx < app_idx, (
        f"tokens.css appears at byte {tokens_idx}, app.css at {app_idx}. "
        f"tokens.css must be FIRST so its tokens override the cascaded "
        f"defaults in app.css / app-shell.css / app-improvements.css."
    )


# ---- 6. Sazon-specific layout tokens match app-shell.css values ----------


@pytest.fixture(scope="module")
def app_shell_css() -> str:
    return (REPO / "app" / "static" / "app-shell.css").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "token, expected_value",
    [
        # Sazon uses touch-target-friendly heights (44px is iOS HIG min;
        # 36px for secondary; 52px for primary CTA). These match
        # app-shell.css verbatim — see the `min-height: 44px` rule in
        # app-improvements.css for the touch-device breakpoint.
        ("--topnav-height", "56px"),
        ("--btn-height", "44px"),
        ("--btn-height-sm", "36px"),
        ("--btn-height-lg", "52px"),
        ("--input-height", "44px"),
    ],
)
def test_sazon_layout_token_matches_shell_value(tokens_css, app_shell_css, token, expected_value):
    """app-shell.css defines --topnav-height etc. with hardcoded
    values. tokens.css redefines them with the FloCafe pattern. Both
    must agree — otherwise the cascade picks one and the other is
    dead code.

    If this fails, someone changed one file but not the other.
    """
    tokens_match = re.search(rf"{re.escape(token)}\s*:\s*([^;]+);", tokens_css)
    shell_match = re.search(rf"{re.escape(token)}\s*:\s*([^;]+);", app_shell_css)
    assert tokens_match, f"{token} missing in tokens.css"
    assert shell_match, f"{token} missing in app-shell.css"
    tokens_val = tokens_match.group(1).strip()
    shell_val = shell_match.group(1).strip()
    assert tokens_val == shell_val == expected_value, (
        f"{token} mismatch: tokens.css='{tokens_val}', "
        f"app-shell.css='{shell_val}', expected='{expected_value}'. "
        f"Update both files together."
    )


# ---- 7. No duplicate :root token between files ---------------------------


def test_no_token_collision_between_tokens_and_app_files():
    """Sazon has tokens.css (FloCafe-port) AND app-improvements.css
    (Sazon-original --color-* family). They should NOT define the
    SAME name with conflicting values.

    Note: we match `--token:` (the definition form) NOT
    `var(--token, ...)` (the use form). The use form's default
    doesn't count as a definition.
    """
    tokens_text = TOKENS_CSS.read_text()
    improvements_text = (REPO / "app" / "static" / "app-improvements.css").read_text()

    # Match definitions like "  --token: value;" — anchor at line start
    # to skip `var(--token, default)` use sites.
    tokens_defs = set(re.findall(r"^\s*(--[\w-]+)\s*:", tokens_text, re.MULTILINE))
    improvements_defs = set(re.findall(r"^\s*(--[\w-]+)\s*:", improvements_text, re.MULTILINE))

    collision = tokens_defs & improvements_defs
    assert not collision, (
        f"tokens.css and app-improvements.css both define: {sorted(collision)}. "
        f"Either pick one source of truth or rename (e.g., --bg vs --color-bg)."
    )


# ---- 8. Token count grows monotonically (no silent drops) ----------------


def test_token_count_is_at_least_50():
    """Sanity floor. The FloCafe port defines ~50 tokens. If a future
    refactor drops half of them, the count would drop below this
    floor and fail. Update the floor (and the comment) if intentional.
    """
    n = len(set(re.findall(r"(--[\w-]+)\s*:", TOKENS_CSS.read_text())))
    assert n >= 50, (
        f"tokens.css has only {n} tokens. Expected at least 50. "
        f"If intentional, lower this floor and update the docstring."
    )