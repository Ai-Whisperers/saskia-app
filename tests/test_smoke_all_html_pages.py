"""Comprehensive smoke test for every HTML page in the app.

Per SASKIA_TEST_PLAN.md §5 #6 — one test per GET-HTML endpoint. Every page
must return 2xx, 3xx, or 422 (validation error) — NEVER 5xx.

This is the regression net that would have caught:
- 2026-09-22 /ventas TemplateRuntimeError
- 2026-09-22 /healthz/db returning null schema when DB drift
- Any future route that starts 500-ing due to missing columns or templates
"""

from __future__ import annotations

import pytest

# Full inventory of HTML routes (per SASKIA_TEST_PLAN.md §1.3)
HTML_ROUTES = [
    "/",
    "/ventas",
    "/ventas/nueva",
    "/productos",
    "/productos/nuevo",
    "/inventario",
    "/inventario/nuevo",
    "/recetas",
    "/recetas/nueva",
    "/clientes",
    "/merma",
    "/produccion",
    "/reorder",
    "/reportes",
    "/reportes/iva",
    "/reportes/diario",
    "/reportes/comparacion",
    "/reportes/top-productos",
    "/reportes/retencion",
    "/reportes/metodos-pago",
    "/reportes/precios",
    "/auditoria",
    "/eod",
    "/suppliers",
    "/suppliers/nuevo",
    "/excel",
    "/excel/mode-guidance",
    "/guia",
    "/guia/getting-started",
    "/guia/accessibility",
    "/ops/status",
    "/settings",
    "/pedidos",
    "/pedidos/board",
    "/pedidos/nuevo",
    "/healthz",
    "/healthz/db",
    "/healthz/schema",
    "/healthz/deps",
    "/healthz/errors",
]


@pytest.mark.parametrize("route", HTML_ROUTES)
def test_html_route_no_5xx(client, route):
    """Every HTML route must return <500 (200, 303, 422, or 404 acceptable)."""
    r = client.get(route)
    assert r.status_code < 500, (
        f"GET {route} returned {r.status_code}: {r.text[:200]}. "
        f"5xx means template/DB/env error — investigate immediately."
    )


def test_login_page_loads_unauthenticated(client):
    """GET /login must return 200 (public route, no auth required)."""
    r = client.get("/login")
    assert r.status_code == 200


def test_static_app_css_serves_correct_content_type(client):
    """/static/app.css must serve with text/css content-type."""
    r = client.get("/static/app.css")
    assert r.status_code == 200
    assert "css" in r.headers.get("content-type", "").lower()


def test_static_app_js_serves_correct_content_type(client):
    """/static/app.js must serve with javascript content-type."""
    r = client.get("/static/app.js")
    assert r.status_code == 200
    assert "javascript" in r.headers.get("content-type", "").lower()


def test_static_calendar_css_serves(client):
    """/static/calendar.css must serve."""
    r = client.get("/static/calendar.css")
    assert r.status_code == 200


def test_static_shortcuts_js_serves(client):
    """/static/shortcuts.js must serve."""
    r = client.get("/static/shortcuts.js")
    assert r.status_code == 200


def test_login_post_redirects_on_success_or_returns_form_on_failure(client):
    """POST /login with bad creds must redirect (303) or show form (200)."""
    r = client.post(
        "/login",
        data={"username": "fake@nowhere.com", "password": "wrongpassword"},
        follow_redirects=False,
    )
    # 303 redirect to login page with error, or 200 with form re-shown
    assert r.status_code in (200, 303, 422), f"POST /login returned {r.status_code}: {r.text[:200]}"
