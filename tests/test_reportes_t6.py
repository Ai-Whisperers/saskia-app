"""T-6 regression test: 9 reportes sub-pages have the features added by T-6.

The features exist in the templates. These tests confirm the pages render
without errors (status 200). Specific feature markers (e.g. 'Cohorte')
are only visible when underlying data exists; for full end-to-end
coverage see the report-specific test files in tests/.

Phase 1 plan:
- T-6a reportes_diario: Gastos metric card (was already live)
- T-6b reportes_iva: YTD badge (committed in 75cc461)
- T-6c reportes_libro_ventas: Hoy/Semana/Mes preset chips (7ad7a13)
- T-6d reportes_top_productos: Ingresos/Revenue columns (already had 2)
- T-6e reportes_precios: Variación de costo (already had)
- T-6f reportes_ventas_hora: vs. ayer (a3ee754)
- T-6g reportes_metodos_pago: Tendencia SVG (already had)
- T-6h reportes_consumo: Proveedor principal (already had)
- T-6i reportes_retencion: Cohorte (already had)
"""


def test_reportes_pages_return_200(authed_client):
    """All 9 reportes sub-pages render without error."""
    pages = [
        "/reportes/diario",
        "/reportes/iva",
        "/reportes/libro-ventas",
        "/reportes/top-productos",
        "/reportes/precios",
        "/reportes/ventas-hora",
        "/reportes/metodos-pago",
        "/reportes/consumo",
        "/reportes/retencion",
    ]
    for path in pages:
        r = authed_client.get(path)
        assert r.status_code == 200, f"{path} returned {r.status_code}"


def test_diario_has_gastos_marker(authed_client):
    """T-6a — /reportes/diario has Gastos metric card label."""
    assert "Gastos" in authed_client.get("/reportes/diario").text


def test_libro_ventas_has_hoy_preset(authed_client):
    """T-6c — /reportes/libro-ventas has Hoy preset chip."""
    assert "Hoy" in authed_client.get("/reportes/libro-ventas").text


def test_consumo_has_proveedor_label(authed_client):
    """T-6h — /reportes/consumo has Proveedor label."""
    assert "Proveedor" in authed_client.get("/reportes/consumo").text


def test_iva_page_renders(authed_client):
    """T-6b — /reportes/iva renders with IVA content."""
    text = authed_client.get("/reportes/iva").text
    assert "IVA" in text or "iva" in text.lower()