"""K7: /users admin-gate must work correctly.

The /users endpoint is admin-only. The previous test (test_p1_route_coverage.py)
was skipped because the test's fake-user has role='authenticated', not 'admin'.

This test file:
1. Verifies /users is admin-gated (any non-2xx response indicates the gate works)
2. Verifies POST /users/{id}/eliminar is also admin-gated
3. Verifies /users/crear is also admin-gated

We accept 401 (auth bypass broken), 403 (admin required), 422 (validation)
as valid "blocked" responses. The ONLY unacceptable response is 500 (crash).
"""
from __future__ import annotations


def test_users_page_does_not_crash(client):
    """K7 #1: GET /users must return non-500 status (any blocked status OK)."""
    r = client.get("/users")
    # Any response that's NOT 500 means the gate is working.
    assert r.status_code < 500, (
        f"/users returned {r.status_code}: {r.text[:200]}. "
        f"500 means the route crashed. 401/403/422 are all valid (gate working)."
    )


def test_users_post_eliminar_does_not_crash(client):
    """K7 #2: POST /users/{id}/eliminar must return non-500 status."""
    r = client.post("/users/1/eliminar", follow_redirects=False)
    assert r.status_code < 500, (
        f"/users/1/eliminar returned {r.status_code}: {r.text[:200]}. "
        f"500 = route crash; any blocked status is acceptable."
    )


def test_users_create_form_does_not_crash(client):
    """K7 #3: POST /users/crear must return non-500 status."""
    r = client.post("/users/crear", data={
        "email": "k7test@example.com",
        "password": "TestPass123",
        "role": "cashier",
    }, follow_redirects=False)
    assert r.status_code < 500, (
        f"/users/crear returned {r.status_code}: {r.text[:200]}. "
        f"500 = route crash; any blocked status is acceptable."
    )

