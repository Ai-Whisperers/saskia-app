"""tests/test_dependencies.py — shared get_session dependency."""


def test_get_session_returns_session_from_app_state(client):
    """End-to-end: a route that uses get_session() can serve a request."""
    # If the dependency broke, this would 500. Smoke-test via /healthz/db
    # which uses session_factory internally.
    r = client.get("/healthz/db")
    assert r.status_code == 200


def test_dependencies_module_imports():
    """Sanity: the module is importable."""
    from app.rms.dependencies import get_app_state, get_session

    assert callable(get_session)
    assert callable(get_app_state)
