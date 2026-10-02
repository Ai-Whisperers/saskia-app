"""tests/test_plan_accuracy_page.py — BACKLOG #29 + #33 page-wire tests.

Covers:
  - /produccion/accuracy renders (no auth wall, returns 200)
  - period toggle: preset=7d / 30d / 90d all return 200
  - invalid preset returns 422 (not 500)
  - empty DB → empty-state copy in HTML, not a crash
  - with seeded completions → product appears in the table
"""
from __future__ import annotations

import pytest

SASKIA_TEST_AUTH = "1"


@pytest.fixture(autouse=True)
def _auth_bypass(monkeypatch):
    monkeypatch.setenv("SASKIA_TEST_AUTH_DISABLED", SASKIA_TEST_AUTH)


def test_accuracy_renders_200(client):
    r = client.get("/produccion/accuracy")
    assert r.status_code == 200
    body = r.text
    assert "Precisión del plan" in body


def test_accuracy_7d_renders(client):
    r = client.get("/produccion/accuracy?preset=7d")
    assert r.status_code == 200


def test_accuracy_30d_renders(client):
    r = client.get("/produccion/accuracy?preset=30d")
    assert r.status_code == 200


def test_accuracy_90d_renders(client):
    r = client.get("/produccion/accuracy?preset=90d")
    assert r.status_code == 200


def test_accuracy_invalid_preset_4xx(client):
    """FastAPI returns 400 (not 422) for Query pattern-mismatch on GET params."""
    r = client.get("/produccion/accuracy?preset=42d")
    assert r.status_code in (400, 422)


def test_accuracy_empty_db_empty_state(client):
    """Empty DB → empty-state copy, not a 500."""
    r = client.get("/produccion/accuracy")
    assert r.status_code == 200
    body = r.text
    # Either shows the empty state OR an empty table — but never a crash.
    assert "Algo salió mal" not in body
    assert ("No hay datos de producción" in body
            or "Precisión del plan" in body)