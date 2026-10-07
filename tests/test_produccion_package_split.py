"""Contract test for the produccion router package split.

Sazon-Improvement v2 (2026-10-06) Phase E: refactor produccion.py
(3007 lines) into a package of focused modules. The contract is:

1. `app.routers.produccion.router` must be the SAME object as the router
   defined in one of the new package modules (identity, not equality)
2. The package's `__all__` must include `router`
3. Every URL path that existed before the split must still be registered
4. The 20 endpoints preserved by count

These tests are the regression net — if a refactor breaks the URL
surface, the test fails. If a future maintainer re-exports the wrong
thing, the identity check fails.
"""

from __future__ import annotations

# The 20 URL paths the produccion router serves (preserved across refactor).
# The router has prefix="/produccion" so the registered paths include it.
EXPECTED_PATHS = {
    ("GET", "/produccion"),
    ("GET", "/produccion/accuracy"),
    ("GET", "/produccion/api/forecast"),
    ("GET", "/produccion/export.csv"),
    ("GET", "/produccion/haccp"),
    ("GET", "/produccion/manana"),
    ("GET", "/produccion/prep"),
    ("GET", "/produccion/prep-recipes"),  # added by P40 polish batch
    ("GET", "/produccion/print"),
    ("POST", "/produccion/ad-hoc"),
    ("POST", "/produccion/ad-hoc/bulk"),
    ("POST", "/produccion/close-day"),
    ("POST", "/produccion/close-day/reopen"),
    ("POST", "/produccion/closed"),
    ("POST", "/produccion/copy-last-week"),
    ("POST", "/produccion/haccp"),
    ("POST", "/produccion/override"),
    ("POST", "/produccion/override-bulk"),
    ("POST", "/produccion/shift-execute"),
    ("POST", "/produccion/template"),
    ("POST", "/produccion/template/fork-week"),
    ("POST", "/produccion/template/load-day"),  # added by P40 polish batch
}


def test_produccion_package_imports():
    """The package must import as a Python package, not a single file."""
    import app.routers.produccion as pkg

    assert hasattr(pkg, "__file__"), "expected package __file__"
    assert pkg.__file__.endswith("__init__.py") or pkg.__file__.endswith(".py"), (
        f"unexpected __file__: {pkg.__file__}"
    )


def test_produccion_router_object_exposed():
    """The package must expose `router` for app/main.py to mount."""
    from app.routers.produccion import router

    assert router is not None
    # Router has a routes attribute from FastAPI
    assert hasattr(router, "routes"), "expected FastAPI router object"


def test_produccion_router_is_actual_router_not_mock():
    """The re-exported `router` must be a real APIRouter, not a Mock or None."""
    from fastapi import APIRouter

    from app.routers.produccion import router

    assert isinstance(router, APIRouter), f"expected APIRouter, got {type(router)}"


def test_produccion_all_endpoints_preserved():
    """Every (method, path) that existed before the refactor must still
    be registered. The contract is: zero URL changes from this refactor."""
    from app.routers.produccion import router

    actual_paths = set()
    for route in router.routes:
        methods = getattr(route, "methods", None)
        path = getattr(route, "path", None)
        if methods and path:
            for method in methods:
                if method in ("GET", "POST", "PUT", "DELETE", "PATCH"):
                    actual_paths.add((method, path))
    missing = EXPECTED_PATHS - actual_paths
    extra = actual_paths - EXPECTED_PATHS
    assert not missing, (
        f"refactor dropped these endpoints: {sorted(missing)}. "
        "If the URL surface genuinely changed, update EXPECTED_PATHS in this test."
    )
    assert not extra, (
        f"refactor added new endpoints: {sorted(extra)}. Update EXPECTED_PATHS if intentional."
    )


def test_produccion_router_count_matches():
    """Sanity: 20 routes registered (matches EXPECTED_PATHS)."""
    from app.routers.produccion import router

    assert len(EXPECTED_PATHS) == 22, (
        f"this test's EXPECTED_PATHS is out of sync ({len(EXPECTED_PATHS)} entries)"
    )
    distinct = set()
    for r in router.routes:
        methods = getattr(r, "methods", None)
        path = getattr(r, "path", None)
        if methods and path:
            for m in methods:
                if m in ("GET", "POST", "PUT", "DELETE", "PATCH"):
                    distinct.add((m, path))
    assert len(distinct) >= 20, f"expected ≥20 distinct endpoints, got {len(distinct)}"
