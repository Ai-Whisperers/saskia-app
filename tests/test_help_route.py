"""tests/test_help_route.py — verify /guia renders user-guide content."""
from __future__ import annotations

import pytest


def test_guia_index_returns_200(client):
    resp = client.get("/guia")
    assert resp.status_code == 200
    body = resp.text
    assert "Guía" in body or "guía" in body.lower()


def test_guia_section_returns_200(client):
    resp = client.get("/guia/01-dashboard")
    assert resp.status_code == 200
    body = resp.text
    # Should contain the section title (h1 inside)
    assert "Inicio" in body or "Dashboard" in body or "tablero" in body.lower()


def test_guia_section_404_for_missing(client):
    resp = client.get("/guia/99-nonexistent")
    assert resp.status_code == 404


def test_guia_renders_dashboard_section_with_h1(client):
    """Verify H1 from markdown is rendered as <h1>."""
    resp = client.get("/guia/01-dashboard")
    assert resp.status_code == 200
    assert "<h1>" in resp.text


def test_guia_renders_ventas_section_quick_sell_mention(client):
    """Verify the ventas section mentions Quick-sell."""
    resp = client.get("/guia/02-ventas")
    assert resp.status_code == 200
    body = resp.text
    # The page describes Quick-sell prominently
    assert "Quick" in body or "quick" in body.lower()


def test_help_link_in_nav(client):
    """The base.html nav has a help link (? icon) pointing to /guia."""
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.text
    assert '/guia' in body
    assert 'aria-label="Guía de uso"' in body or 'title="Guía de uso"' in body


# ─── P3: D.7 Glossary (2026-10-05) ────────────────────────────────────
# 20 bakery-domain terms defined in docs/user-guide/glosario.md, served
# at /guia/glosario via the existing /guia/{section} catch-all.


def test_guia_glosario_returns_200(client):
    """The glossary section renders without error."""
    resp = client.get("/guia/glosario")
    assert resp.status_code == 200


def test_guia_glosario_renders_h1(client):
    """The glossary H1 title is rendered."""
    resp = client.get("/guia/glosario")
    assert resp.status_code == 200
    assert "<h1>" in resp.text
    assert "Glosario" in resp.text


def test_guia_glosario_has_20_terms(client):
    """All 20 glossary terms render as <h3> headings."""
    resp = client.get("/guia/glosario")
    assert resp.status_code == 200
    h3_count = resp.text.count("<h3>")
    assert h3_count >= 20, f"Expected ≥20 glossary terms, got {h3_count}"


@pytest.mark.parametrize("term", [
    "Escandallo",
    "Merma",
    "Food cost",
    "Receta técnica",
    "Stock",
    "Cierre diario",
    "Arqueo de caja",
    "Producción",
    "Pedido",
    "Comprobante",
    "SKU",
    "Migración",
    "Backup",
    "CSRF",
    "Auditoría",
    "Health check",
    "Schema version",
    "Token público",
])
def test_guia_glosario_contains_term(client, term):
    """Each key bakery/technical term is defined in the glossary."""
    resp = client.get("/guia/glosario")
    assert resp.status_code == 200
    assert term in resp.text, f"Term '{term}' missing from glossary"


def test_help_route_includes_glossary_link(client):
    """The /guia index (README.md) mentions the glossary."""
    resp = client.get("/guia")
    assert resp.status_code == 200
    assert "glosario" in resp.text.lower(), "glosario link missing from /guia index"
