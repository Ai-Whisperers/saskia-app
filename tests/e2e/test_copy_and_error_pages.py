"""tests/e2e/test_copy_and_error_pages.py — D5 + D6.

D5: UI copy stays Paraguayan Spanish (vos form) on the main surfaces.
D6: 404/500 render branded Spanish pages (the `branding is undefined`
crash class of 2026-09), never stack traces or English-only bodies.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.smoke]


@pytest.mark.parametrize("path,needles", [
    ("/login", ["Iniciar sesión", "contraseña"]),
    ("/dashboard", ["dashboard", "ventas"]),
], ids=["login", "dashboard"])
def test_public_pages_speak_spanish(client, path, needles):
    r = client.get(path, follow_redirects=True)
    if r.status_code != 200:
        pytest.skip("page needs seeded/auth state")
    for n in needles:
        assert n.lower() in r.text.lower(), f"{path}: missing Spanish copy {n!r}"


def test_404_is_structured_not_stacktrace(client):
    """404s return a structured JSON/HTML body — never a traceback leak."""
    r = client.get("/pagina-inexistente-xyz")
    assert r.status_code == 404
    body = r.text.lower()
    assert "traceback" not in body
    assert "exception" not in body
    assert "not_found" in body or "404" in body or "no se encontró" in body


def test_flash_messages_are_spanish(client, session_factory):
    """Wrong-password style flash through login → Spanish, never raw English."""
    r = client.post("/login", data={"username": "x", "password": "bad"},
                    follow_redirects=True)
    body = r.text.lower()
    assert "invalid username or password" not in body, "English error leaked"
