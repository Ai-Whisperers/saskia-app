"""Probe script to identify dead sidebar routes. Run manually for P-30 investigation.

Output is a table: route → status code → friendly-body marker.
"""
from __future__ import annotations

import pytest

pytestmark = [pytest.mark.smoke]


# All sidebar routes from NAV_GROUPS (app/rms/nav.py). If a route is in
# the sidebar, users WILL click it. It MUST either:
# - return 200 (works)
# - return 301/302 (redirect to a working page)
# - return 410 Gone with a friendly "en construcción" body
# Returning plain 404 is a bug — the user clicked a real-looking link.
SIDEBAR_ROUTES = [
    "/", "/ventas", "/pedidos", "/produccion", "/eod",
    "/productos", "/recetas", "/inventario", "/merma",
    "/reorder", "/shopping-list", "/suppliers", "/wishlist",
    "/clientes",
    "/reportes", "/analisis", "/dashboard", "/pricing", "/vs-mercado",
    "/bank", "/riesgos",
    "/settings", "/users", "/excel", "/auditoria", "/guia",
]


@pytest.mark.parametrize("route", SIDEBAR_ROUTES)
def test_sidebar_route_returns_friendly_response(client, route):
    """P-30: Every sidebar-linked route must return a friendly response.

    Acceptable responses:
    - 200: works (or 204, etc.)
    - 301/302/303/307: redirect to a working page
    - 410 Gone: intentional — feature pending (with friendly body)
    - 401 Unauthorized: legitimate auth denial (user lacks permission)
    - 403 Forbidden: legitimate permission denial

    UNACCEPTABLE: plain 404 (user clicked a sidebar link and got "not found"),
    or 500 (server crash).
    """
    r = client.get(route, follow_redirects=False)
    status = r.status_code
    assert status in (200, 204, 301, 302, 303, 307, 401, 403, 410), (
        f"Sidebar route {route} returned {status} — should be 200, redirect, "
        f"401/403 (legit auth), or 410 (intentional Gone). "
        f"Plain 404 or 500 = bug because users click this from the nav."
    )
    # If 410, body must be friendly
    if status == 410:
        body = r.text.lower()
        assert (
            "construcción" in body
            or "en construcción" in body
            or "próximamente" in body
            or "coming soon" in body
            or "no implementado" in body
            or "intencionalmente" in body
        ), (
            f"Sidebar route {route} returned 410 but body is not a friendly 'en construcción' page. "
            f"Body (first 500 chars): {r.text[:500]}"
        )
    # If 30x, must have Location header
    if 300 <= status < 400:
        loc = r.headers.get("Location") or r.headers.get("location")
        assert loc, (
            f"Sidebar route {route} returned {status} without Location header — "
            f"would create redirect loop or broken UX"
        )
