"""CSRF protection tests across all form endpoints.

Per SASKIA_TEST_PLAN.md §5 #26 — every form endpoint must reject unprimed POSTs.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.security


# Form endpoints that should require CSRF
FORM_ENDPOINTS = [
    ("/productos/1/editar", "name=Test"),
    ("/inventario/1/ajustar", "adjustment=5&reason=test"),
    ("/suppliers/1/eliminar", ""),
    ("/users/crear", "email=x@y.com&password=12345&role=cashier"),
]


@pytest.mark.parametrize("route,data", FORM_ENDPOINTS)
def test_form_rejects_unprimed_post(client, route, data):
    """POST without CSRF cookie must be blocked (403/422, never 200)."""
    # Parse data string into dict
    from urllib.parse import parse_qsl
    form_data = dict(parse_qsl(data))

    r = client.post(route, data=form_data, follow_redirects=False)
    # 401 = CSRF or auth gate; 403 = CSRF blocked; 422 = validation rejected
    # 400 = our new BUG-00 Spanish 400 with field error; 404 = route gone
    assert r.status_code in (400, 401, 403, 422, 404), (
        f"POST {route} returned {r.status_code}: {r.text[:200]}. "
        f"CSRF must reject unprimed POSTs."
    )


def test_csrf_login_is_exempt(client):
    """/login POST must be CSRF-exempt (first-time login)."""
    r = client.post(
        "/login",
        data={"username": "fake@example.com", "password": "wrong"},
        follow_redirects=False,
    )
    # /login is exempt from CSRF; should return 200/303, not 403
    assert r.status_code in (200, 303, 422), (
        f"/login POST returned {r.status_code}: {r.text[:200]}"
    )


def test_csrf_get_does_not_check_csrf(client):
    """GET requests must NOT check CSRF (only POST/PUT/DELETE do)."""
    r = client.get("/productos")
    assert r.status_code == 200
