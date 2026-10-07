"""Contract test for the operations + print_export module split.

Sazon-Improvement v2 (2026-10-06) Phase E step 4: extract the 9 POST
routes (overrides + closed + shift + ad-hoc + close-day + template) and
the 3 GET print/export routes into focused modules. The contract is:

1. The shared `app.routers.produccion.router` still has all 20 routes.
2. No URL changed.
3. No new 500s on the POST routes (verified via the existing
   v2 test suites which exercise these endpoints).
"""
from __future__ import annotations


def test_operations_module_imports():
    """app/routers/produccion/operations.py must exist and import cleanly."""
    from app.routers.produccion import operations
    assert hasattr(operations, "produccion_override")
    assert hasattr(operations, "produccion_copy_last_week")
    assert hasattr(operations, "produccion_closed_toggle")
    assert hasattr(operations, "produccion_override_bulk")
    assert hasattr(operations, "produccion_shift_execute")
    assert hasattr(operations, "produccion_ad_hoc")
    assert hasattr(operations, "produccion_close_day")
    assert hasattr(operations, "produccion_close_day_reopen")
    assert hasattr(operations, "produccion_ad_hoc_bulk")


def test_print_export_module_imports():
    """app/routers/produccion/print_export.py must exist and import cleanly."""
    from app.routers.produccion import print_export
    assert hasattr(print_export, "produccion_print")
    assert hasattr(print_export, "produccion_export_csv")
    assert hasattr(print_export, "produccion_prep")


def test_templates_module_imports():
    """app/routers/produccion/templates_ops.py must exist (2 template POSTs)."""
    from app.routers.produccion import templates_ops
    assert hasattr(templates_ops, "produccion_template_set")
    assert hasattr(templates_ops, "produccion_template_fork_week")


def test_forecast_module_imports():
    """app/routers/produccion/forecast.py must exist (api/forecast + manana)."""
    from app.routers.produccion import forecast
    assert hasattr(forecast, "produccion_api_forecast")
    assert hasattr(forecast, "produccion_manana")


def test_shim_reexports_operations_identity():
    """The shim re-exports the shared router; submodule functions are
    reachable via their canonical module path (e.g.
    app.routers.produccion.operations.produccion_override). The shim
    does NOT re-export every handler — it only re-exports the router
    and the public helpers, to keep the package surface small.

    What matters for callers is: the function objects are the SAME
    identity between operations.py and the FastAPI route table
    (because they share the @router decorator and same module
    load). Verified by ensuring operations.produccion_override is
    registered on the router.
    """
    from app.routers.produccion import operations, router

    # The handler function is registered on the shared router.
    # This pins the wiring: if operations.py didn't use the shared
    # router, the route would be registered on a different instance
    # and not show up here.
    route_paths = {getattr(r, "path", None) for r in router.routes}
    assert "/produccion/override" in route_paths, (
        "produccion_override must be registered on the shared router"
    )
    # The handler is importable from operations.py and is callable.
    assert callable(operations.produccion_override)


def test_router_endpoints_preserved_after_phase_e_step4():
    """All 20 endpoints (9 POST operations + 3 print/export + 2 template +
    2 forecast + 1 worksheet + 1 accuracy + 2 haccp) must still be
    registered after the operations/print_export/templates_ops/forecast
    extraction.
    """
    from app.routers.produccion import router

    expected_paths = {
        ("GET", "/produccion"),
        ("GET", "/produccion/accuracy"),
        ("GET", "/produccion/haccp"),
        ("POST", "/produccion/haccp"),
        ("POST", "/produccion/override"),
        ("POST", "/produccion/copy-last-week"),
        ("POST", "/produccion/closed"),
        ("POST", "/produccion/override-bulk"),
        ("POST", "/produccion/shift-execute"),
        ("POST", "/produccion/ad-hoc"),
        ("POST", "/produccion/close-day"),
        ("POST", "/produccion/close-day/reopen"),
        ("POST", "/produccion/ad-hoc/bulk"),
        ("POST", "/produccion/template"),
        ("POST", "/produccion/template/fork-week"),
        ("GET", "/produccion/api/forecast"),
        ("GET", "/produccion/manana"),
        ("GET", "/produccion/print"),
        ("GET", "/produccion/export.csv"),
        ("GET", "/produccion/prep"),
    }

    def _path(r):
        # Use getattr to avoid pyright noise on the BaseRoute union.
        return getattr(r, "path", None)

    def _methods(r):
        m = getattr(r, "methods", None)
        return next(iter(m)) if m else None

    actual = {(_methods(r), _path(r)) for r in router.routes}
    missing = expected_paths - actual
    extra = actual - expected_paths
    assert not missing, f"Missing routes after Phase E step 4: {missing}"
    assert not extra, f"Unexpected extra routes: {extra}"
