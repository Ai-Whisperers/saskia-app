"""Tests that inicio.html renders the 5 orphan dashboard metrics as teaser cards.

The 5 metrics are computed in app/routers/dashboard.py:736-749 but previously
were only rendered on /analisis (the full analytics page). Phase 1 T-1 surfaces
counts for each as a teaser card on /inicio so operators see them at a glance.
"""


def test_inicio_renders_top_margin_teaser(client):
    """inicio.html must render a teaser card with 'Top por margen' label."""
    r = client.get("/inicio")
    assert r.status_code == 200
    assert "Top por margen" in r.text, "T-1 missing: 'Top por margen' teaser not in /inicio"


def test_inicio_renders_concentration_teaser(client):
    """inicio.html must render a teaser card with 'Concentración de costo' label."""
    r = client.get("/inicio")
    assert r.status_code == 200
    assert "Concentración de costo" in r.text, (
        "T-1 missing: 'Concentración de costo' teaser not in /inicio"
    )


def test_inicio_renders_turnover_teaser(client):
    """inicio.html must render a teaser card with 'Rotación de stock' label."""
    r = client.get("/inicio")
    assert r.status_code == 200
    assert "Rotación de stock" in r.text, "T-1 missing: 'Rotación de stock' teaser not in /inicio"


def test_inicio_renders_dow_heatmap_teaser(client):
    """inicio.html must render a teaser card with 'Heatmap día × hora' label."""
    r = client.get("/inicio")
    assert r.status_code == 200
    assert "Heatmap día" in r.text, "T-1 missing: 'Heatmap día' teaser not in /inicio"


def test_inicio_renders_complexity_teaser(client):
    """inicio.html must render a teaser card with 'Recetas más complejas' label."""
    r = client.get("/inicio")
    assert r.status_code == 200
    assert "Recetas más complejas" in r.text, (
        "T-1 missing: 'Recetas más complejas' teaser not in /inicio"
    )


def test_inicio_teasers_link_to_analisis_anchors(client):
    """Each T-1 teaser card must point at /analisis."""
    r = client.get("/inicio")
    assert r.status_code == 200
    # Find every new T-1 teaser href
    for href in [
        "/analisis#top-margin",
        "/analisis#concentration",
        "/analisis#turnover",
        "/analisis#dow-heatmap",
        "/analisis#complexity",
    ]:
        assert href in r.text, f"T-1 link missing: {href}"
