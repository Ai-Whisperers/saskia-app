"""tests/test_create_app_isolation.py — verifies the create_app() factory
returns independent FastAPI instances.

The create_app() refactor (2026-10-09) replaces the module-level
`app = FastAPI(...)` pattern with a factory function. This test
verifies that two calls to create_app() return **independent**
instances - no shared middleware state, no shared router lists.

Why this matters:
- Multi-worker uvicorn (--workers N): each worker needs its own
  clean app instance. Sharing the module-level app between workers
  caused "module-level state was modified by a different worker"
  bugs in pre-refactor Sazon.
- Test isolation: a test can call create_app() and get a clean
  FastAPI without worrying about state leaking from previous tests.

Run with: pytest -x -q tests/test_create_app_isolation.py
"""

from __future__ import annotations

from fastapi import FastAPI


def test_create_app_returns_fastapi_instance() -> None:
    from app.rms.main import create_app

    app = create_app()
    assert isinstance(app, FastAPI)


def test_create_app_returns_independent_instances() -> None:
    """Two calls must return different objects, not the same singleton."""
    from app.rms.main import create_app

    a = create_app()
    b = create_app()
    assert a is not b, "create_app() must return a fresh instance each call"


def test_create_app_routes_are_independent() -> None:
    """Adding a route to one app must NOT affect another app."""
    from app.rms.main import create_app

    a = create_app()
    b = create_app()

    initial_a = len(a.routes)
    initial_b = len(b.routes)

    # Define a sentinel route on a
    @a.get("/__test_sentinel__")
    def sentinel() -> dict[str, str]:
        return {"ok": "yes"}

    assert len(a.routes) == initial_a + 1
    assert len(b.routes) == initial_b, (
        f"b picked up the route added to a — routes were shared. "
        f"a has {len(a.routes)} routes, b has {len(b.routes)} (expected {initial_b})"
    )


def test_create_app_middleware_stacks_are_independent() -> None:
    """Middleware stacks must not be shared between create_app() calls.

    FastAPI/Starlette uses `app.user_middleware` (a list). If two
    create_app() calls returned the same list, adding a middleware
    to one would affect the other.
    """
    from app.rms.main import create_app

    a = create_app()
    b = create_app()

    # user_middleware is a list; identity check catches shared state
    assert a.user_middleware is not b.user_middleware, (
        "user_middleware list is shared between create_app() calls"
    )


def test_module_level_app_still_exists() -> None:
    """The module-level `app` reference (used by uvicorn
    `app.rms.main:app` and by tests that `from app.rms.main import app`)
    must still work after the refactor.
    """
    from app.rms import main

    assert isinstance(main.app, FastAPI)
    # And it should be one of the create_app() instances (or at least
    # equivalent in type). We don't check `is` because the module
    # import path may have side effects.


def test_create_app_does_not_mutate_module_level_app() -> None:
    """Calling create_app() must not mutate the module-level app's
    routes. This was a bug in pre-refactor Sazon where the second
    import of main.py would add a second copy of all routers.
    """
    from app.rms import main
    from app.rms.main import create_app

    initial_route_count = len(main.app.routes)
    initial_middleware_count = len(main.app.user_middleware)

    _ = create_app()
    _ = create_app()

    assert len(main.app.routes) == initial_route_count, (
        f"module-level app routes grew: {initial_route_count} -> "
        f"{len(main.app.routes)} after create_app() calls"
    )
    assert len(main.app.user_middleware) == initial_middleware_count, (
        f"module-level app middleware grew: {initial_middleware_count} -> "
        f"{len(main.app.user_middleware)} after create_app() calls"
    )
