"""P-01 + audit #4: /login must not render the app sidebar or nav chrome.

The sidebar reveals the entire app structure (Operación, Catálogo, Compras,
Ventas y clientes, FINANZAS) and all sub-routes (Inicio, Ventas, Pedidos,
Productos, Recetas, Inventario, Merma, etc.) to anyone hitting /login
unauthenticated. This is a privacy leak AND a UX issue — the sidebar
toggle/buttons don't make sense when there is no session.

Root cause hypothesis (verify before fixing):
- app/templates/base.html line 69 wraps the sidebar+topbar in
  `{% if is_logged_in %}` ... {% endif %}
- app/services/template_render.py:269 sets ctx.setdefault("is_logged_in",
  get_current_user(request) is not None)
- get_current_user() requires a DB session dependency that may raise on
  /login, falling into the except branch which sets is_logged_in = True.
- The /login route also does not explicitly pass is_logged_in=False.

This test reproduces the bug. It must FAIL before the fix and PASS after.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.smoke]


# Routes that MUST NOT render the app sidebar / nav chrome
PUBLIC_ROUTES = [
    "/login",
]


@pytest.fixture
def production_like_client(client, monkeypatch):
    """Like the regular `client` fixture but with the test auth bypass disabled.

    The dev/test conftest sets `SASKIA_TEST_AUTH_DISABLED=1` so 280+ existing
    tests don't need to pre-login. P-01 specifically validates production
    behavior, so it must run with the bypass OFF.
    """
    monkeypatch.delenv("SASKIA_TEST_AUTH_DISABLED", raising=False)
    return client


@pytest.mark.parametrize("route", PUBLIC_ROUTES)
def test_public_route_does_not_render_sidebar(production_like_client, route):
    """P-01: GET <route> must NOT include the sidebar or any nav_items."""
    r = production_like_client.get(route)
    assert r.status_code == 200, f"{route} returned {r.status_code}"
    body = r.text

    # The sidebar wrapper itself
    assert 'class="sidebar"' not in body, (
        f"{route} renders sidebar — should be hidden for unauthenticated users. "
        f"First 1KB:\n{body[:1000]}"
    )

    # The topbar (also hidden when not logged in)
    assert 'class="topbar"' not in body, (
        f"{route} renders topbar — should be hidden for unauthenticated users. "
        f"First 1KB:\n{body[:1000]}"
    )

    # The topbar search button that exposes "Cmd+K" shortcuts
    assert "Buscar producto, cliente, pedido" not in body, (
        f"{route} renders topbar search — should be hidden for unauthenticated users."
    )

    # Any sidebar section heading (Operación / Catálogo / Compras / Ventas y clientes)
    for section in ("Operación", "Catálogo", "Compras", "Ventas y clientes", "Finanzas"):
        assert section not in body, (
            f"{route} exposes nav section '{section}' to unauthenticated users"
        )

    # The brand link goes to /, that's fine, but the brand-mark + brand-name
    # should still render (we want branding for the login screen, just not the nav).
    assert "Saskia RMS" in body, f"{route} lost its branding"


def test_login_renders_brand_but_no_nav_items(production_like_client):
    """P-01: /login must keep brand identity but strip all nav_items."""
    r = production_like_client.get("/login")
    assert r.status_code == 200
    body = r.text
    # No nav-item links at all
    assert body.count('class="nav-item') == 0, (
        f"/login renders {body.count(chr(34) + 'nav-item')} nav-item links — full structure leak"
    )
    # The "Nuevo" button (topbar action menu) is also chrome — should be hidden
    assert "nuevo-btn" not in body, "/login renders the Nuevo dropdown — should be hidden"
