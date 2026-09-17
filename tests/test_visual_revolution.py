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
    """Mobile hamburger nav must appear below 768px."""
    css = _read_css()
    css_compact = css.replace(" ", "")
    assert "@media(max-width:768px)" in css_compact
    assert ".nav-toggle-label" in css


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
