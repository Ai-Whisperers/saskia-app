"""tests/test_help_route.py — verify /guia renders user-guide content."""


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
    assert "/guia" in body
    assert 'aria-label="Guía de uso"' in body or 'title="Guía de uso"' in body
