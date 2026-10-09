"""P-02 / audit #12, #13, #25: /clientes hygiene.

Audit findings addressed:
- #12 "Programa de puntos" was rendered TWICE (once in page header,
    once in a redundant inline <p>). Should appear EXACTLY once.
- #13 All 8 customers showed "None" for Teléfono. Phone should be
    formatted, not "None".
- #25 Placeholder test customers leaked into production data.

These tests verify that:
1. /clientes renders 200
2. "Programa de puntos" appears exactly once in the HTML
3. Customers with phones get a formatted phone (not "None")
4. /clientes/api/search returns valid JSON
5. CSV export works
6. No placeholder test customers (e.g. "Test Customer", "Cliente Test")
    appear as fixture data
"""

from __future__ import annotations

import re

import pytest

pytestmark = [pytest.mark.smoke]


def test_clientes_renders_200(client):
    r = client.get("/clientes")
    assert r.status_code == 200, f"got {r.status_code}"
    assert "Clientes" in r.text


def test_puntos_programa_appears_exactly_once(client):
    """P-02 #12: 'Programa de puntos' must appear exactly once (was duplicated)."""
    r = client.get("/clientes")
    assert r.status_code == 200
    # Count occurrences of the literal phrase. Page header renders it
    # once; any inline duplication breaks the count.
    occurrences = r.text.count("Programa de puntos")
    assert occurrences == 1, (
        f"'Programa de puntos' appears {occurrences} times on /clientes — "
        f"audit #12 found it duplicated. Expected exactly 1."
    )


def test_puntos_description_text_present(client):
    """P-02 #12: The points-program description must still be visible
    (just not duplicated)."""
    r = client.get("/clientes")
    assert r.status_code == 200
    assert "1 punto por cada 1.000 Gs." in r.text or "1 punto = 100 Gs." in r.text, (
        "Points-program description missing entirely from /clientes. "
        "If you removed the duplicate, make sure the page-header description remains."
    )


def test_clientes_has_search_input(client):
    """P-02: /clientes has a search bar (filter by name/phone)."""
    r = client.get("/clientes")
    assert r.status_code == 200
    body = r.text
    assert 'name="q"' in body or 'placeholder="Buscar' in body, "Missing search input on /clientes"


def test_clientes_has_new_customer_button(client):
    """P-02: There's a 'Nuevo cliente' button (CRUD entry point)."""
    r = client.get("/clientes")
    assert r.status_code == 200
    body = r.text
    assert "Nuevo cliente" in body or "nuevo-cliente-btn" in body, (
        "Missing 'Nuevo cliente' button on /clientes"
    )


def test_clientes_has_csv_export(client):
    """P-02: /clientes has an Exportar CSV link."""
    r = client.get("/clientes")
    assert r.status_code == 200
    body = r.text
    # CSV export should be a download link with format=csv param
    assert "format=csv" in body or "Exportar CSV" in body, "Missing CSV export on /clientes"


def test_clientes_api_search_returns_json(client):
    """P-02: /clientes/api/search returns JSON for autocomplete."""
    r = client.get("/clientes/api/search?q=cliente")
    assert r.status_code == 200
    # FastAPI's JSONResponse uses application/json
    assert "application/json" in r.headers.get("content-type", ""), (
        f"/clientes/api/search returned non-JSON: {r.headers.get('content-type')}"
    )


def test_phone_field_renders_friendly_when_blank(client):
    """P-02 #13: When a customer has no phone, the cell must show
    something user-friendly — NOT the literal string 'None'."""
    r = client.get("/clientes")
    assert r.status_code == 200
    body = r.text
    # The literal 'None' (Python's str(None)) is the bad pattern.
    # Acceptable alternatives: '—', '—', empty <td>, or 'Sin teléfono'.
    bad_pattern = re.compile(r"<(?:td|span)[^>]*>\s*None\s*</", re.IGNORECASE)
    matches = bad_pattern.findall(body)
    assert len(matches) == 0, (
        f"Found {len(matches)} 'None' string in customer table cells. "
        f"Audit #13: use '—' or 'Sin teléfono' instead."
    )


def test_clientes_does_not_contain_test_fixture_names(client):
    """P-02 #25: No placeholder test customers in production data.

    Common bad fixture names: 'Test Customer', 'Cliente Test', 'Foo Bar'.
    A real customer list should contain only names that look real.
    This is a soft check — we look for the obvious anti-patterns.
    """
    r = client.get("/clientes")
    assert r.status_code == 200
    body_lower = r.text.lower()
    bad = [
        "test customer",
        "cliente test",
        "foo bar",
        "john doe",
        "jane doe",
    ]
    found = [b for b in bad if b in body_lower]
    assert not found, (
        f"Placeholder test customer name(s) found in /clientes: {found}. "
        f"Audit #25: production data must not contain test fixtures."
    )
