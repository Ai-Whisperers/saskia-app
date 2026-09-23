"""Tests for the new error/observability/logging infrastructure."""

import pytest

from app.rms.errors import (
    AlreadyExists,
    AppError,
    BadRequest,
    Conflict,
    DependencyError,
    Forbidden,
    NotFound,
    RateLimited,
    Unauthenticated,
    ValidationError,
    to_http_exception,
)


# ─── Cleanup fixture ─────────────────────────────────────────────
#
# Note: we used to have an autouse fixture that cleaned up __test_*
# routes after every test. Several other test files (test_csrf_local_dev,
# test_review_quick_wins, test_lazy_openpyxl) reload app.rms.main,
# creating a NEW FastAPI() instance. Our `app` import may point to a
# stale one. The fix is to use `client.app` (the live instance) and
# only clean up when the test actually uses the client fixture.
#
# Instead of relying on autouse + dynamic fixture detection, each test
# that adds a route uses `try/finally` to clean up. This is explicit
# and avoids the pytest-fixture-stack assertion errors that arise when
# cleanup tries to call getfixturevalue for a fixture that wasn't used.


# ─── Custom exception hierarchy ─────────────────────────────────


def test_app_error_carries_message_and_reason_code():
    """AppError subclasses propagate message + reason_code + context."""
    err = BadRequest("Datos inválidos.", context={"field": "price"})
    assert err.message == "Datos inválidos."
    assert err.reason_code == "bad_request"
    assert err.status_code == 400
    assert err.context == {"field": "price"}


def test_not_found_entity_helper():
    """NotFound('Pedido', id=42) auto-builds the message and reason_code."""
    err = NotFound("Pedido", id=42)
    assert err.status_code == 404
    assert err.reason_code == "Pedido_not_found"
    assert "Pedido" in err.message and "42" in err.message
    assert err.context == {"entity": "Pedido", "id": "42"}


def test_not_found_without_id():
    """NotFound('Cliente') works without an id (just entity name)."""
    err = NotFound("Cliente")
    assert err.context == {"entity": "Cliente"}
    assert "Cliente" in err.message


def test_app_error_to_dict():
    """to_dict() returns the structured payload."""
    err = Conflict("Duplicate.", context={"key": "name"})
    d = err.to_dict()
    assert d["error"] == "Duplicate."
    assert d["type"] == "Conflict"
    assert d["status"] == 409
    assert d["context"] == {"key": "name"}


def test_to_http_exception_carries_reason_code_header():
    """to_http_exception adds X-Reason-Code header for ops visibility."""
    http_exc = to_http_exception(BadRequest("test"))
    assert http_exc.status_code == 400
    assert http_exc.headers == {"X-Reason-Code": "bad_request"}


def test_exception_hierarchy_inheritance():
    """All typed errors inherit from AppError."""
    for cls in [BadRequest, ValidationError, NotFound, AlreadyExists,
                Conflict, Unauthenticated, Forbidden, RateLimited]:
        assert issubclass(cls, AppError)


def test_app_error_cause_is_preserved():
    """AppError carries its underlying cause in .cause for log inspection."""
    try:
        raise ValueError("root cause")
    except ValueError as e:
        err = BadRequest("Wrapper error.", cause=e)
    assert isinstance(err.cause, ValueError)
    assert "root cause" in str(err)


# ─── Observability middleware ───────────────────────────────────


def test_request_id_header_honors_upstream(client):
    """If client sends X-Request-Id, it gets echoed back."""
    custom_rid = "test-abc-123"
    r = client.get("/healthz", headers={"X-Request-Id": custom_rid})
    assert r.headers.get("x-request-id") == custom_rid


def test_request_id_is_short_hex(client):
    """Generated request_id is a short hex string (12 chars)."""
    r = client.get("/healthz")
    rid = r.headers.get("x-request-id", "")
    assert len(rid) == 12
    assert all(c in "0123456789abcdef" for c in rid)


# ─── Global exception handler ────────────────────────────────────


def _add_test_route(app_obj, path: str, exc_factory):
    """Helper to add a throwaway route that raises the given exception.

    Uses a unique UUID-based path so concurrent test files that also add
    /__test_* routes don't shadow each other (FastAPI matches first route
    found for a path; first-add wins on duplicate).

    The caller MUST pass the live app object (client.app, not the module-
    level import) because some test files reload app.rms.main, which
    creates a new FastAPI() instance. The TestClient fixture holds a
    reference to that new instance; importing `app` in another test file
    may give you the OLD one.
    """
    import uuid
    unique = f"/__test_{uuid.uuid4().hex[:8]}_{path.lstrip('/').replace('/', '_')}"
    @app_obj.get(unique)
    def _raise():
        raise exc_factory()
    return unique


def test_app_error_returns_structured_json(client):
    """A 4xx AppError on a JSON route returns the structured payload."""
    path = _add_test_route(client.app, "/__test_bad_request", lambda: BadRequest("test bad input", context={"foo": "bar"}))
    try:
        r = client.get(path, headers={"Accept": "application/json"})
        assert r.status_code == 400
        body = r.json()
        assert body["error"] == "test bad input"
        assert body["type"] == "BadRequest"
        assert body["reason"] == "bad_request"
        assert body["context"] == {"foo": "bar"}
        assert "request_id" in body
        assert r.headers.get("x-reason-code") == "bad_request"
    finally:
        client.app.router.routes = [
            r for r in client.app.router.routes
            if not getattr(r, "path", "").startswith("/__test_")
        ]


def test_not_found_returns_404_with_reason(client):
    """NotFound surfaces as 404 with reason_code in headers."""
    path = _add_test_route(client.app, "/__test_not_found", lambda: NotFound("TestEntity", id=99))
    try:
        r = client.get(path, headers={"Accept": "application/json"})
        assert r.status_code == 404
        body = r.json()
        assert body["reason"] == "TestEntity_not_found"
        assert body["context"]["id"] == "99"
        assert r.headers.get("x-reason-code") == "TestEntity_not_found"
    finally:
        client.app.router.routes = [
            r for r in client.app.router.routes
            if not getattr(r, "path", "").startswith("/__test_")
        ]


def test_dependency_error_502(client):
    """DependencyError surfaces as 502."""
    path = _add_test_route(client.app, "/__test_dep_error", lambda: DependencyError("Bank feed down"))
    try:
        r = client.get(path, headers={"Accept": "application/json"})
        assert r.status_code == 502
        assert r.json()["reason"] == "dependency_unavailable"
    finally:
        client.app.router.routes = [
            r for r in client.app.router.routes
            if not getattr(r, "path", "").startswith("/__test_")
        ]


def test_unauthenticated_error_returns_401(client):
    """Unauthenticated surfaces as 401."""
    path = _add_test_route(client.app, "/__test_unauth", lambda: Unauthenticated("Login required."))
    try:
        r = client.get(path, headers={"Accept": "application/json"})
        assert r.status_code == 401
        assert r.json()["reason"] == "unauthenticated"
    finally:
        client.app.router.routes = [
            r for r in client.app.router.routes
            if not getattr(r, "path", "").startswith("/__test_")
        ]


# ─── Messages catalog ───────────────────────────────────────────


def test_messages_catalog_imports():
    """All message constants importable."""
    from app.rms.messages import (
        PEDIDO_NOT_FOUND,
        RECIPE_NOT_FOUND,
        INGREDIENT_NOT_FOUND,
        BANK_ADDED,
        WISHLIST_ITEM_PURCHASED,
        SHOPPING_LIST_DELETED,
        BENCHMARK_UPDATED,
    )
    assert isinstance(PEDIDO_NOT_FOUND, str)
    assert isinstance(RECIPE_NOT_FOUND, str)
    assert isinstance(INGREDIENT_NOT_FOUND, str)
    assert isinstance(BANK_ADDED, str)
    assert isinstance(WISHLIST_ITEM_PURCHASED, str)
    assert isinstance(SHOPPING_LIST_DELETED, str)
    assert isinstance(BENCHMARK_UPDATED, str)


def test_observability_helpers_importable():
    """Observability module exports the right helpers."""
    from app.rms.observability import (
        RequestContextMiddleware,
        generate_request_id,
        record_audit,
    )
    rid = generate_request_id()
    assert len(rid) == 12
    assert all(c in "0123456789abcdef" for c in rid)
    from starlette.middleware.base import BaseHTTPMiddleware
    assert issubclass(RequestContextMiddleware, BaseHTTPMiddleware)
