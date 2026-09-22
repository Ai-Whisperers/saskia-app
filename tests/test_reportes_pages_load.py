"""Reportes (reports) pages smoke tests."""
from __future__ import annotations

import pytest


REPORTES_PAGES = [
    "/reportes",
    "/reportes/iva",
    "/reportes/libro-ventas",
    "/reportes/diario",
    "/reportes/comparacion",
    "/reportes/top-productos",
    "/reportes/retencion",
    "/reportes/valor-pedido",
    "/reportes/ventas-hora",
    "/reportes/metodos-pago",
    "/reportes/precios",
]


@pytest.mark.parametrize("route", REPORTES_PAGES)
def test_reportes_page_loads(authed_client, route):
    """Every reportes page must return non-5xx."""
    r = authed_client.get(route)
    assert r.status_code < 500, (
        f"GET {route} returned {r.status_code}: {r.text[:200]}"
    )


def test_reportes_libro_ventas_set_pdf(authed_client):
    """GET /reportes/libro-ventas/set-pdf must not 500."""
    r = authed_client.get("/reportes/libro-ventas/set-pdf")
    assert r.status_code < 500, (
        f"/reportes/libro-ventas/set-pdf returned {r.status_code}"
    )
