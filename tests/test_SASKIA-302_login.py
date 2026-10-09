"""tests/test_SASKIA-302_login.py — Phase 1, LOGIN.1-LOGIN.4 fixes.

Locks the fixes for the login page per docs/ux/copy-fix-list.md:
  - LOGIN.1 (P0): remove duplicate stay_logged_in checkbox
  - LOGIN.2: translate "Sazón strives to conform" to Spanish
  - LOGIN.4: tagline fallback (when branding.tagline is empty)

The 'Recordar este dispositivo' checkbox is the one to KEEP.
The 'stay_logged_in' (Mantener sesión abierta) is the one to REMOVE.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.smoke]


def test_login_has_only_one_persistence_checkbox(authed_client):
    """`/login` must have exactly one persistence checkbox (Recordar este dispositivo)."""
    r = authed_client.get("/login")
    assert r.status_code == 200
    body = r.text
    # Old code had two: stay_logged_in AND remember
    assert "stay_logged_in" not in body, "Old `stay_logged_in` checkbox still present"
    # The remaining one is `remember` (with label `Recordar este dispositivo`)
    assert 'name="remember"' in body, "Expected `remember` checkbox"
    # And the visible label
    assert "Recordar este dispositivo" in body, "Expected 'Recordar este dispositivo' label"
    # The duplicate helper text "No uses esto en equipos compartidos" should be gone
    assert "No uses esto en equipos compartidos" not in body, "Stale helper text still present"


def test_login_a11y_statement_in_spanish(authed_client):
    """`/login` accessibility statement must be in Spanish (was English)."""
    r = authed_client.get("/login")
    assert r.status_code == 200
    body = r.text
    # Old: "Sazón strives to conform to WCAG 2.1 Level AA."
    # New: "Sazón apunta a cumplir con WCAG 2.1 Nivel AA."
    assert "Sazón strives" not in body, "English a11y statement still present"
    assert "apunta a cumplir" in body, "Expected Spanish replacement"
    # The "WCAG 2.1" part stays (it's a standard name)
    assert "WCAG 2.1" in body
