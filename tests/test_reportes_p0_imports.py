"""P-0 regression (2026-10-02): NameError when /reportes/ventas-hora and
/reportes/mermas-cost were 500-ing in production because the new
`sales_by_hour`, `sales_heatmap`, and `waste_roi_by_ingredient` were
not imported in app/routers/reportes.py.

This test imports the module and confirms the names are bound in the
module namespace, so a future refactor that drops the import trips
the test instead of breaking live."""

from __future__ import annotations


def test_reportes_imports_sales_by_hour() -> None:
    import app.routers.reportes as r

    assert hasattr(r, "sales_by_hour"), (
        "sales_by_hour not imported in app/routers/reportes.py — "
        "GET /reportes/ventas-hora will 500 in production"
    )
    assert callable(r.sales_by_hour)


def test_reportes_imports_sales_heatmap() -> None:
    import app.routers.reportes as r

    assert hasattr(r, "sales_heatmap"), "sales_heatmap not imported — ventas-hora heatmap broken"
    assert callable(r.sales_heatmap)


def test_reportes_imports_waste_roi_by_ingredient() -> None:
    import app.routers.reportes as r

    assert hasattr(r, "waste_roi_by_ingredient"), (
        "waste_roi_by_ingredient not imported — GET /reportes/mermas-cost will 500 in production"
    )
    assert callable(r.waste_roi_by_ingredient)


def test_reportes_imports_customer_retention() -> None:
    """Original import; make sure refactor didn't drop it either."""
    import app.routers.reportes as r

    assert hasattr(r, "customer_retention")
    assert callable(r.customer_retention)
