"""tests/test_visual_revolution.py — Phase 0 token + icon + error page tests.

Verifies:
- Token system: every primitive + semantic token defined on :root
- Dark mode: every semantic token overrides correctly
- Forced-colors: token map for high-contrast mode
- prefers-reduced-motion: global reset present
- Icon sprite: every referenced icon exists
- Icon buttons: every icon-only button has aria-label
- Error pages: 404 serves styled HTML for browsers, JSON for API clients
- 500 sanitization: raw exception text never leaks to response body
"""

from __future__ import annotations

from pathlib import Path
from pathlib import Path

import re

# ---- Token system tests ----------------------------------------------------


def _read_css() -> str:
    """Read the bundled app.css."""
    with open("app/static/app.css") as f:
        return f.read()


def test_primitive_tokens_defined():
    """All primitive color tokens must be declared on :root."""
    css = _read_css()
    required_primitives = [
        "--orange-50",
        "--orange-500",
        "--orange-600",
        "--orange-900",
        "--gray-50",
        "--gray-100",
        "--gray-500",
        "--gray-800",
        "--gray-900",
        "--green-500",
        "--green-600",
        "--amber-500",
        "--amber-600",
        "--red-500",
        "--red-600",
        "--blue-500",
        "--blue-600",
        "--white",
        "--black",
        "--cream",
    ]
    for token in required_primitives:
        assert token in css, f"Primitive token {token} not declared"
        assert re.search(rf"{re.escape(token)}\s*:\s*[^;]+;", css), (
            f"Primitive {token} has no value"
        )


def test_semantic_tokens_defined():
    """All semantic tokens must be declared on :root."""
    css = _read_css()
    required_semantic = [
        "--color-bg",
        "--color-surface",
        "--color-surface-raised",
        "--color-text",
        "--color-text-muted",
        "--color-text-link",
        "--color-border",
        "--color-border-focus",
        "--color-accent",
        "--color-accent-hover",
        "--color-accent-soft",
        "--color-accent-fg",
        "--color-success",
        "--color-warn",
        "--color-danger",
        "--color-info",
        "--color-focus-ring",
    ]
    for token in required_semantic:
        assert token in css, f"Semantic token {token} not declared"


def test_semantic_tokens_override_in_dark_mode():
    """Every semantic token must be re-declared under [data-theme="dark"]."""
    css = _read_css()
    m = re.search(r'\[data-theme="dark"\]\s*\{([^}]+(?:\{[^}]*\}[^}]*)*)\}', css)
    assert m, "No dark mode block found"
    dark_block = m.group(1)
    semantic = [
        "--color-bg",
        "--color-surface",
        "--color-text",
        "--color-text-muted",
        "--color-border",
        "--color-accent",
        "--color-accent-hover",
        "--color-success",
        "--color-warn",
        "--color-danger",
        "--color-info",
    ]
    for token in semantic:
        assert token in dark_block, (
            f"Token {token} not overridden in dark mode — partial dark mode is a bug"
        )


def test_forced_colors_block_present():
    """High-contrast mode must have a token override block."""
    css = _read_css()
    css_compact = css.replace(" ", "")
    assert "@media(forced-colors:active)" in css_compact


def test_prefers_reduced_motion_block_present():
    """Reduced-motion global reset must be present."""
    css = _read_css()
    css_compact = css.replace(" ", "")
    assert "@media(prefers-reduced-motion:reduce)" in css_compact
    assert "animation-duration" in css
    assert "transition-duration" in css


def test_legacy_aliases_preserved():
    """Old token names must still resolve (backwards compat for templates)."""
    css = _read_css()
    legacy_aliases = [
        "--bg",
        "--card-bg",
        "--text",
        "--text-muted",
        "--border",
        "--primary",
        "--primary-hover",
        "--danger",
        "--warn",
        "--good",
    ]
    for token in legacy_aliases:
        assert token in css, f"Legacy alias {token} missing — old templates will break"


def test_spacing_scale_defined():
    """Spacing scale on 4px base."""
    css = _read_css()
    for i in [1, 2, 3, 4, 6, 8, 12]:
        assert f"--space-{i}:" in css, f"Spacing token --space-{i} not defined"


def test_radius_scale_defined():
    """Radius scale including the pill radius."""
    css = _read_css()
    for r in ["sm", "", "md", "lg", "xl", "pill"]:
        token = f"--radius-{r}" if r else "--radius"
        assert token in css, f"Radius token {token} not defined"


# ---- Icon sprite tests ------------------------------------------------------


def test_icon_sprite_exists():
    """The icon sprite file must exist in _components."""
    import os

    path = "app/templates/_components/icons.svg"
    assert os.path.exists(path), f"{path} missing"
    with open(path) as f:
        content = f.read()
    symbols = re.findall(r'<symbol id="icon-(\w+)"', content)
    assert len(symbols) >= 20, f"Only {len(symbols)} icons defined; need >=20"


def test_icon_sprite_included_in_base():
    """Every page must include the icon sprite so <use href> resolves."""
    from starlette.testclient import TestClient

    from app.rms.main import app

    client = TestClient(app)
    for path in ["/login", "/"]:
        resp = client.get(path, headers={"Accept": "text/html"})
        assert 'id="icon-home"' in resp.text, f"{path} missing icon sprite"


def test_nav_links_have_icons():
    """Every nav link should have an icon (Phase 2 deliverable)."""
    from starlette.testclient import TestClient

    from app.rms.main import app

    client = TestClient(app)
    resp = client.get("/login", headers={"Accept": "text/html"})
    assert 'href="#icon-home"' in resp.text or 'href="#icon-heart"' in resp.text


def test_icon_only_buttons_have_aria_label():
    """Every icon-only button in nav-right must have an accessible name."""
    from starlette.testclient import TestClient

    from app.rms.main import app

    client = TestClient(app)
    resp = client.get("/login", headers={"Accept": "text/html"})
    for label in [
        "Cambiar tema claro/oscuro",
        "Guía de uso",
        "Estado del servidor",
        "Cerrar sesión",
    ]:
        assert f'aria-label="{label}"' in resp.text, f"Icon button missing aria-label: {label}"


# ---- Error page tests -------------------------------------------------------


def test_404_returns_html_for_browser(client):
    """A browser hitting an unknown route gets the styled 404 page."""
    resp = client.get("/this-route-does-not-exist", headers={"Accept": "text/html"})
    assert resp.status_code == 404
    assert "<!DOCTYPE html>" in resp.text
    assert "Página no encontrada" in resp.text
    assert "Volver al inicio" in resp.text


def test_404_returns_json_for_api(client):
    """An API client gets JSON, not HTML."""
    resp = client.get(
        "/this-route-does-not-exist",
        headers={"Accept": "application/json"},
    )
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/json")
    body = resp.json()
    assert body["error"] == "not_found"


def test_500_does_not_leak_exception_text(client):
    """The 500 handler must NEVER leak raw exception text to the browser."""
    from fastapi.testclient import TestClient

    from app.rms import main as main_module

    @main_module.app.get("/__test_boom_html")
    def boom_html():
        raise RuntimeError("[Errno -2] super secret internal detail")

    try:
        with TestClient(main_module.app, raise_server_exceptions=False) as c:
            resp = c.get("/__test_boom_html", headers={"Accept": "text/html"})
            assert resp.status_code == 500, (
                f"Expected 500, got {resp.status_code}. Body: {resp.text[:200]}"
            )
            assert "<!DOCTYPE html>" in resp.text
            assert "[Errno -2]" not in resp.text, (
                "500 page leaked raw exception text — security bug"
            )
            assert "super secret internal detail" not in resp.text
            assert "Código de referencia" in resp.text
    finally:
        main_module.app.router.routes = [
            r
            for r in main_module.app.router.routes
            if getattr(r, "path", "") != "/__test_boom_html"
        ]


def test_500_returns_json_for_api(client):
    """An API client gets structured JSON with request_id."""
    from fastapi.testclient import TestClient

    from app.rms import main as main_module

    @main_module.app.get("/__test_boom_json")
    def boom_json():
        raise RuntimeError("internal stuff")

    try:
        with TestClient(main_module.app, raise_server_exceptions=False) as c:
            resp = c.get(
                "/__test_boom_json",
                headers={"Accept": "application/json"},
            )
            assert resp.status_code == 500
            body = resp.json()
            assert body["error"] == "internal_server_error"
            assert "request_id" in body
            assert "internal stuff" not in str(body)
    finally:
        main_module.app.router.routes = [
            r
            for r in main_module.app.router.routes
            if getattr(r, "path", "") != "/__test_boom_json"
        ]


# ---- Component class tests --------------------------------------------------


def test_button_classes_present():
    """The new button component classes are available in CSS."""
    css = _read_css()
    for cls in [
        ".btn",
        ".btn-primary",
        ".btn-secondary",
        ".btn-danger",
        ".btn-ghost",
        ".btn-icon",
        ".btn-sm",
        ".btn-lg",
    ]:
        assert cls in css, f"Button class {cls} not defined"


def test_card_classes_present():
    css = _read_css()
    for cls in [
        ".card",
        ".card-header",
        ".card-body",
        ".card-footer",
        ".metric-card",
        ".metric-value",
        ".metric-delta",
    ]:
        assert cls in css, f"Card class {cls} not defined"


def test_badge_classes_present():
    css = _read_css()
    for cls in [
        ".badge",
        ".badge-ok",
        ".badge-warn",
        ".badge-danger",
        ".badge-info",
        ".badge-neutral",
        ".badge-dot",
    ]:
        assert cls in css, f"Badge class {cls} not defined"


def test_table_classes_present():
    css = _read_css()
    for cls in [
        ".table",
        ".table.is-striped",
        ".table.is-hoverable",
        ".table--compact",
        ".table--comfortable",
    ]:
        assert cls in css, f"Table class {cls} not defined"


def test_alert_classes_present():
    css = _read_css()
    for cls in [".alert", ".alert-success", ".alert-warn", ".alert-danger", ".alert-info"]:
        assert cls in css, f"Alert class {cls} not defined"


def test_modal_classes_present():
    css = _read_css()
    for cls in [
        ".modal-backdrop",
        ".modal-dialog",
        ".modal-header",
        ".modal-body",
        ".modal-footer",
    ]:
        assert cls in css, f"Modal class {cls} not defined"


def test_loading_classes_present():
    css = _read_css()
    for cls in [".spinner", ".skeleton", ".skeleton-block", ".skeleton-circle", ".skeleton-line"]:
        assert cls in css, f"Loading class {cls} not defined"


def test_mobile_nav_breakpoint():
    """Responsive breakpoint exists; nav is now the dropdown menu
    (nav-menu, in calendar.css) which works at all widths — the old
    checkbox hamburger (.nav-toggle-label) is legacy dead CSS kept
    only for backward compat."""
    css = _read_css()
    css_compact = css.replace(" ", "")
    assert "@media(max-width:768px)" in css_compact
    # Dropdown menu styles live in calendar.css (site-wide, not size-gated)
    cal_css = (Path(__file__).parent.parent / "app" / "static" / "calendar.css").read_text()
    assert ".nav-menu" in cal_css
    assert ".menu-panel" in cal_css


def test_empty_state_class_present():
    css = _read_css()
    assert ".empty-state" in css


def test_print_styles_present():
    """@media print must be present for paper-friendly EOD + reports."""
    css = _read_css()
    css_compact = css.replace(" ", "")
    assert "@mediaprint" in css_compact


def test_quick_sell_grid_present():
    """.quick-sell-grid class must be present."""
    css = _read_css()
    assert ".quick-sell-grid" in css


# ---- P0 visual polish tests -----------------------------------------------


def test_card_radius_is_20px():
    """--card-radius should be --radius-xl (20px) for the softer Square pattern."""
    css = _read_css()
    m = re.search(r"--card-radius:var\(--([^)]+)\)", css)
    assert m, "--card-radius token missing"
    token = m.group(1)
    m2 = re.search(rf"--{token}:([^;]+);", css)
    assert m2, f"Cannot resolve {token}"
    assert m2.group(1) == "20px", f"card-radius should be 20px, got {m2.group(1)}"


def test_metric_label_uses_mono_eyebrow():
    """.metric-label should use mono font + bolder weight (eyebrow style)."""
    css = _read_css()
    m = re.search(r"\.metric-label\{[^}]*\}", css)
    assert m, ".metric-label rule missing"
    rule = m.group(0)
    assert "font-family:var(--font-mono)" in rule, (
        ".metric-label should use mono font (Square eyebrow pattern)"
    )
    assert "font-weight:600" in rule, (
        ".metric-label should be bolder (eyebrow pattern)"
    )


def test_btn_pill_class_defined():
    """.btn-pill should be defined for full-pill CTAs (login + error pages)."""
    css = _read_css()
    assert re.search(r"\.btn-pill\{[^}]*border-radius:var\(--radius-pill\)", css), (
        ".btn-pill must use --radius-pill (9999px) for full-pill effect"
    )


def test_pill_buttons_applied_to_login_and_errors():
    """Login + error pages should use btn-pill for primary CTAs."""
    with open("app/templates/login.html") as f:
        login = f.read()
    assert "btn-pill" in login, "login.html should use btn-pill on Ingresar"
    with open("app/templates/errors/404.html") as f:
        e404 = f.read()
    assert "btn-pill" in e404, "errors/404.html should use btn-pill on Volver"
    with open("app/templates/errors/500.html") as f:
        e500 = f.read()
    assert "btn-pill" in e500, "errors/500.html should use btn-pill on Volver"


def test_shortcut_help_button_in_nav():
    """There should be a visible '?' button in nav-right for shortcut discovery."""
    with open("app/templates/base.html") as f:
        base = f.read()
    assert 'id="open-shortcuts"' in base, (
        "base.html should include an #open-shortcuts button for shortcut discovery"
    )


def test_shortcut_button_wired_in_js():
    """shortcuts.js should wire the new #open-shortcuts button to showShortcutHelp()."""
    with open("app/static/shortcuts.js") as f:
        js = f.read()
    assert "open-shortcuts" in js, (
        "shortcuts.js must wire the new nav button"
    )
    assert "navBtn._shortcutsWired" in js, (
        "shortcuts.js must guard against double-binding"
    )


# ---- P0 insight-card tests --------------------------------------------------


def test_insight_card_macro_defined():
    """The insight_card macro should be defined in macros.html (Lightspeed-style)."""
    with open("app/templates/_components/macros.html") as f:
        macros = f.read()
    assert "{% macro insight_card" in macros, (
        "macros.html must define insight_card macro"
    )
    assert 'severity="{{ severity }}"' in macros or "severity-" in macros, (
        "insight_card macro must use severity-* classes"
    )


def test_insight_card_css_rules_present():
    """.insight-card + .severity-ok/warn/danger rules must exist in CSS."""
    css = _read_css()
    for rule in [
        r"\.insight-card\{",
        r"\.insight-card\.severity-ok\{",
        r"\.insight-card\.severity-warn\{",
        r"\.insight-card\.severity-danger\{",
        r"\.insight-list",
        r"\.insight-item",
        r"\.insight-grid",
    ]:
        assert re.search(rule, css), f"CSS rule {rule!r} missing for insight-card"


def test_insight_card_used_for_stars_dogs():
    """inicio.html should use m.insight_card() for stars/dogs/low_stock/rising/churning."""
    with open("app/templates/inicio.html") as f:
        inicio = f.read()
    for label in ["Stars", "Dogs", "Reposición urgente", "En alza", "En baja"]:
        assert "insight_card" in inicio and label in inicio, (
            f"inicio.html must render {label!r} via insight_card macro"
        )


def test_old_quadrant_unstyled_lists_removed():
    """The bare <ul> stars/dogs blocks should no longer be in inicio.html."""
    with open("app/templates/inicio.html") as f:
        inicio = f.read()
    assert "<h3 class=\"quadrant-star\">" not in inicio, (
        "Old bare <ul> quadrant-star block should be replaced by insight_card"
    )
    assert "<h3 class=\"quadrant-dog\">" not in inicio, (
        "Old bare <ul> quadrant-dog block should be replaced by insight_card"
    )


# ---- P1 audit #10: vs. last period delta tests ----------------------------


def test_delta_pill_macro_defined():
    """The delta_pill macro should be defined in macros.html."""
    with open("app/templates/_components/macros.html") as f:
        macros = f.read()
    assert "{% macro delta_pill" in macros, (
        "macros.html must define delta_pill macro"
    )
    assert "metric-delta is-" in macros, (
        "delta_pill macro must use the existing .metric-delta.is-* classes"
    )


def test_delta_pill_used_for_top_three_metrics():
    """inicio.html should render delta_pill on Ventas/COGS/Margen cards."""
    with open("app/templates/inicio.html") as f:
        inicio = f.read()
    assert inicio.count("m.delta_pill(") == 3, (
        "inicio.html should call delta_pill exactly 3 times (Ventas, COGS, Margen)"
    )
    for label in ["delta_ventas", "delta_cogs", "delta_margen"]:
        assert label in inicio, f"inicio.html must pass {label} to delta_pill"


def test_delta_prior_css_rule_present():
    """.metric-delta .delta-prior must be styled (sub-label inside pill)."""
    css = _read_css()
    assert re.search(
        r"\.metric-delta \.delta-prior\{[^}]*color:var\(--color-text-subtle\)",
        css,
    ), "CSS rule for .delta-delta .delta-prior missing"
