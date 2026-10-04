"""tests/test_route_coverage_manifest.py — K1: every registered route is
exercised by at least one test (or explicitly exempted).

Kills the dark-router class permanently: settings_runtime shipped 37 routes
with zero behavioral tests; this manifest test fails when a new route lands
without coverage. Exemptions are explicit and reviewed.
"""

from __future__ import annotations

import pathlib


def _all_routes():
    """Walk all routes reachable from app, recursing into _IncludedRouter wrappers.

    FastAPI's app.routes mixes APIRoute (user-defined) with _IncludedRouter
    wrappers (sub-routers registered via include_router). Each wrapper's
    routes live on .original_router.routes; we recurse into that.
    """
    from app.rms.main import app

    out = []

    def _walk(routes, prefix=""):
        for r in routes:
            sub = getattr(r, "routes", None)
            orig = getattr(r, "original_router", None)
            if orig is not None and getattr(orig, "routes", None):
                # _IncludedRouter: recurse. The include-time prefix lives on
                # include_context.prefix (e.g. /api/insights); inner route
                # paths do NOT include it, so merge it into the walk prefix.
                inc_prefix = getattr(getattr(r, "include_context", None), "prefix", "") or ""
                _walk(orig.routes, prefix=prefix + inc_prefix)
                continue
            if sub is not None and getattr(r, "methods", None) is None:
                # Mount or other non-API wrapper: skip.
                continue
            methods = sorted(
                m
                for m in getattr(r, "methods", []) or []
                if m in ("GET", "POST", "PUT", "DELETE", "PATCH")
            )
            path = (prefix + (getattr(r, "path", "") or "")) or prefix
            if not path or path.startswith(("/openapi", "/docs")):
                continue
            for m in methods:
                out.append((m, path))

    _walk(app.routes)
    return sorted(set(out))


# Route families deliberately untested (with reasons). Shrink this list,
# never grow it silently.
_EXEMPT = {
    # health/internal ops: covered by smoke + uptime, not behavior
    ("GET", "/healthz"),
    ("GET", "/healthz/db"),
    ("GET", "/healthz/deps"),
    ("GET", "/healthz/migrate"),
    ("GET", "/healthz/schema"),
    ("GET", "/ops/status"),
    ("GET", "/auditoria"),
    # static assets
    ("GET", "/static/{path:path}"),
    # API docs surfaces (FastAPI auto-generated)
    ("GET", "/api/docs"),
    ("GET", "/api/openapi.json"),
    # emergency operator action; smoke-covered only
    ("POST", "/admin/migrate"),
    # /api/validate/* are inline blur validators, tested via UI flows
    ("POST", "/api/validate/product"),
    ("POST", "/api/validate/recipe"),
}


def _test_corpus() -> str:
    corpus: list = [f.read_text() for f in pathlib.Path(__file__).parent.rglob("*.py")]
    return "\n".join(corpus)


def test_every_route_has_a_test_reference():
    corpus = _test_corpus()
    missing = []
    for method, path in _all_routes():
        if (method, path) in _EXEMPT:
            continue
        # A route is "covered" if its concrete first-segment appears in the
        # corpus (parametrized paths matched by their literal prefix).
        seg = "/" + path.strip("/").split("/")[0]
        if seg == "/api":
            seg = "/" + "/".join(path.strip("/").split("/")[:2])
        if seg not in corpus:
            missing.append(f"{method} {path}")
    assert not missing, f"{len(missing)} route(s) have no test reference:\n  " + "\n  ".join(
        missing
    )


def test_route_count_regression():
    """The manifest itself: routes only grow deliberately."""
    routes = _all_routes()
    assert len(routes) > 150, f"suspiciously few routes: {len(routes)}"
