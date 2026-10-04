"""Tests for /recetas pagination (audit finding: list(session.scalars(...)).all()).

Pagination was added so that /recetas returns at most page_size=50 recipes
per request. When there are more than 50 recipes, the UI shows a Siguiente
button that goes to ?page=2.
"""


def test_recetas_paginates_above_50(qseed, authed_client, session_factory):
    """When >50 recipes exist, /recetas?page=2 lists the next batch."""
    from app.rms.models import Recipe

    sf = session_factory
    # Create 60 recipes
    with sf() as s:
        for i in range(60):
            r = Recipe(name=f"Receta {i:03d}", yield_qty=10, yield_unit="und")
            s.add(r)
        s.commit()

    r = authed_client.get("/recetas?page=1&page_size=50")
    assert r.status_code == 200
    body = r.text
    assert "página" in body or "Mostrando" in body
    # First page should NOT include the Siguiente → button should be there
    assert "Siguiente" in body

    r2 = authed_client.get("/recetas?page=2&page_size=50")
    assert r2.status_code == 200
    body2 = r2.text
    # Page 2 should have anterior
    assert "Anterior" in body2


def test_recetas_pagination_singular_page_when_few(qseed, authed_client, session_factory):
    """When <50 recipes, no pagination nav is rendered."""
    from app.rms.models import Recipe

    sf = session_factory
    with sf() as s:
        for i in range(5):
            r = Recipe(name=f"Poco {i}", yield_qty=10, yield_unit="und")
            s.add(r)
        s.commit()

    r = authed_client.get("/recetas?page_size=50")
    assert r.status_code == 200
    body = r.text
    # No Siguiente button when only 1 page
    assert "Siguiente →" not in body
    assert "← Anterior" not in body


def test_recetas_pagination_respects_search(qseed, authed_client, session_factory):
    """?q=foo filters the count too (pagination aware)."""
    from app.rms.models import Recipe

    sf = session_factory
    with sf() as s:
        for i in range(20):
            r = Recipe(name=f"Manzana {i}", yield_qty=10, yield_unit="und")
            s.add(r)
        for i in range(20):
            r = Recipe(name=f"Pera {i}", yield_qty=10, yield_unit="und")
            s.add(r)
        s.commit()

    r = authed_client.get("/recetas?q=Pera&page_size=10")
    assert r.status_code == 200
    body = r.text
    # Find the pagination text
    assert "página 1 de 2" in body  # 20 peras / 10 = 2 pages
