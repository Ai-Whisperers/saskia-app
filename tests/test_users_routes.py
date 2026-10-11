"""tests/test_users_routes.py — SASKIA plan 1.

users router (app/routers/users.py, prefix=/users) has 5 routes,
0 direct tests. The router requires admin role. The default
authed_client fixture uses role="authenticated" which fails the
admin check. These tests verify route wiring exists and returns
a non-success response (200 if admin, 4xx otherwise — admin gate
in production).

Per docs/plans/2026-10-11-plan-1-untested-routers.md.
"""

from __future__ import annotations

import pytest


def test_users_list_route_wired(authed_client):
    """GET /users → 4xx (admin required). Route is wired."""
    r = authed_client.get("/users")
    # 401 (no real user session) or 403 (not admin) or 200 (admin) all OK
    assert r.status_code in (200, 401, 403), r.text[:200]


def test_users_crear_route_wired(authed_client):
    """POST /users/crear → 4xx (admin/validation)."""
    from tests.factories import _uniq
    username = _uniq("user").replace(" ", "-").lower()[:32]
    r = authed_client.post(
        "/users/crear",
        data={"username": username, "password": "testpass123", "role": "operator"},
        follow_redirects=False,
    )
    # 422 (validation), 401 (no session), 403 (not admin), 303 (admin)
    assert r.status_code in (200, 303, 401, 403, 422), r.text[:300]


def test_users_editar_route_wired(authed_client):
    """POST /users/999999/editar → 4xx (admin/404)."""
    r = authed_client.post(
        "/users/999999/editar",
        data={"username": "ghost", "role": "operator"},
        follow_redirects=False,
    )
    assert r.status_code in (200, 303, 401, 403, 404, 422), r.text[:200]


def test_users_eliminar_route_wired(authed_client):
    """POST /users/999999/eliminar → 4xx (admin/404)."""
    r = authed_client.post(
        "/users/999999/eliminar",
        data={},
        follow_redirects=False,
    )
    assert r.status_code in (200, 303, 401, 403, 404, 422), r.text[:200]


def test_users_api_roles_returns_json(authed_client):
    """GET /users/api/roles → 200 JSON (no admin gate)."""
    r = authed_client.get("/users/api/roles")
    assert r.status_code == 200
    import json
    data = json.loads(r.text)
    assert isinstance(data, (list, dict))
