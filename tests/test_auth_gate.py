"""tests/test_auth_gate.py — proves the production auth gate works.

With `SASKIA_TEST_AUTH_DISABLED=0` (production mode), the gate must
redirect unauthenticated requests to /login and reject API calls
with 401. These tests bypass the conftest's test-mode env var.

Each test temporarily sets the env var to a non-truthy value, makes
the request, then restores.
"""

from __future__ import annotations

import pytest

PROTECTED_PATHS_GET = [
    "/",
    "/inventario",
    "/recetas",
    "/productos",
    "/ventas",
    "/excel",
]

PROTECTED_PATHS_POST = [
    "/inventario/nuevo",
    "/recetas/nueva",
    "/productos/nuevo",
    "/ventas/nueva",
    "/excel/importar",
]


def _force_production_auth(monkeypatch):
    """Turn off the test bypass so the gate runs."""
    monkeypatch.setenv("SASKIA_TEST_AUTH_DISABLED", "0")


@pytest.mark.parametrize("path", PROTECTED_PATHS_GET)
def test_get_protected_routes_redirect_when_unauthenticated(client, monkeypatch, path):
    """GET on protected route without login → 303 to /login (HTML accept)."""
    _force_production_auth(monkeypatch)
    r = client.get(
        path,
        headers={"Accept": "text/html"},
        follow_redirects=False,
    )
    assert r.status_code == 303, f"{path} returned {r.status_code}"
    assert "/login" in r.headers["location"]


@pytest.mark.parametrize("path", PROTECTED_PATHS_POST)
def test_post_protected_routes_redirect_when_unauthenticated(client, monkeypatch, path):
    """POST on protected route without login → 303 to /login (HTML form submit)."""
    _force_production_auth(monkeypatch)
    r = client.post(
        path,
        data={"foo": "bar"},
        headers={"Accept": "text/html"},
        follow_redirects=False,
    )
    assert r.status_code == 303, f"{path} returned {r.status_code}"
    assert "/login" in r.headers["location"]


def test_api_route_returns_401(client, monkeypatch):
    """API clients (Accept: application/json) get 401, not redirect."""
    _force_production_auth(monkeypatch)
    r = client.get(
        "/",
        headers={"Accept": "application/json"},
        follow_redirects=False,
    )
    # JSON accept means API client — should get 401 (no session)
    assert r.status_code == 401


def test_api_excel_export_returns_401(client, monkeypatch):
    """GET /excel/exportar (binary endpoint) → 401 without session."""
    _force_production_auth(monkeypatch)
    r = client.get(
        "/excel/exportar",
        headers={"Accept": "application/octet-stream"},
        follow_redirects=False,
    )
    assert r.status_code == 401


def test_login_routes_are_public(client, monkeypatch):
    """GET /login works even when auth gate is on."""
    _force_production_auth(monkeypatch)
    r = client.get("/login")
    assert r.status_code == 200


def test_healthz_is_public(client, monkeypatch):
    """GET /healthz works (monitoring endpoint)."""
    _force_production_auth(monkeypatch)
    r = client.get("/healthz")
    assert r.status_code == 200


def test_static_is_public(client, monkeypatch):
    """GET /static/app.css works (CSS for login page)."""
    _force_production_auth(monkeypatch)
    r = client.get("/static/app.css")
    assert r.status_code == 200
    assert ":root" in r.text or "--bg" in r.text


def test_logout_is_public(client, monkeypatch):
    """GET /logout is reachable even without auth (so user can always exit)."""
    _force_production_auth(monkeypatch)
    r = client.get("/logout", follow_redirects=False)
    assert r.status_code == 303
    assert "/login" in r.headers["location"]
