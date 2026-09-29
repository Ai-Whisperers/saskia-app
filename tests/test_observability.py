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


# ─── BACKLOG #48: HTML 4xx error template ────────────────────────────
#
# Browser requests with Accept: text/html get a styled 4xx page; API
# clients (Accept: application/json) keep the JSON payload. The page
# must surface the reason_code + request_id so support can grep the
# log without asking the user to copy/paste anything.


def test_4xx_html_template_exists():
    """The shared 4xx.html template is in place at the canonical path."""
    import os
    p = os.path.join(os.path.dirname(__file__), "..", "app", "templates", "errors", "4xx.html")
    assert os.path.isfile(p), f"missing 4xx.html at {p}"
    with open(p, encoding="utf-8") as f:
        body = f.read()
    assert "status_code" in body
    assert "message" in body
    assert "Volver al inicio" in body, "must include 'Volver al inicio' CTA"


def test_error_titles_module_alias_complete():
    """_ERROR_TITLES covers every common 4xx code (BACKLOG #48)."""
    from app.rms.errors import _ERROR_TITLES

    for code in (400, 401, 403, 404, 409, 422, 429):
        assert code in _ERROR_TITLES, f"missing title for status {code}"
        title, msg = _ERROR_TITLES[code]
        assert title, f"empty title for {code}"
        assert msg, f"empty default message for {code}"


def test_bad_request_renders_html_for_browser(client):
    """Browser request → 4xx.html template; reason_code + request_id surfaced."""
    from app.rms.errors import BadRequest

    path = _add_test_route(
        client.app, "/__test_bad_html",
        lambda: BadRequest("Dato inválido en el campo X"),
    )
    try:
        r = client.get(path, headers={"Accept": "text/html"})
        assert r.status_code == 400
        body = r.text
        assert "400" in body, "status code not rendered"
        # Spanish title — match by token to avoid UTF-8 quoting.
        assert "Solicitud" in body and "inv" in body.lower(), \
            "Spanish title not rendered"
        # User-supplied message is the source of truth.
        assert "Dato" in body and "campo X" in body, "user message not rendered"
        # request_id is surfaced both in the body and as a header.
        assert "x-request-id" in {h.lower() for h in r.headers.keys()}, \
            "X-Request-Id header must be set so a copy-paste by user includes it"
        assert "ID de seguimiento" in body, \
            "request_id is not visible in the body — support can't grep it"
    finally:
        client.app.router.routes = [
            r for r in client.app.router.routes
            if not getattr(r, "path", "").startswith("/__test_")
        ]


def test_unauthorized_renders_html_for_browser(client):
    """401 → styled 4xx page with reason_code + user message."""
    from app.rms.errors import Unauthenticated

    path = _add_test_route(
        client.app, "/__test_unauth_html",
        lambda: Unauthenticated("Tu sesión expiró."),
    )
    try:
        r = client.get(path, headers={"Accept": "text/html"})
        assert r.status_code == 401
        body = r.text
        assert "No autenticado" in body, "401 title missing"
        assert "unauthenticated" in body, "reason_code missing"
        assert "Tu" in body and "expir" in body, "user message missing"
    finally:
        client.app.router.routes = [
            r for r in client.app.router.routes
            if not getattr(r, "path", "").startswith("/__test_")
        ]


def test_bad_request_api_client_still_gets_json(client):
    """API client (Accept: application/json) keeps the structured JSON payload.

    BACKLOG #48 must NOT regress API consumers — the HTML template is
    only used when the request signals browser intent.
    """
    from app.rms.errors import BadRequest

    path = _add_test_route(
        client.app, "/__test_bad_json",
        lambda: BadRequest("test bad input"),
    )
    try:
        r = client.get(path, headers={"Accept": "application/json"})
        assert r.status_code == 400
        body = r.json()
        assert body["reason"] == "bad_request"
        assert body["error"] == "test bad input"
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


# ─── Regression: BACKLOG #41 (user_id session key lookup) ─────────────
#
# Background: the bcrypt backend writes ``request.session["local_user_id"]``
# and the Supabase backend writes ``request.session["supabase_user_id"]``.
# Before 2026-09-29, ``_safe_get_user_id`` only checked generic
# ``user_id`` / ``uid`` / ``user`` keys, so bcrypt users logged as
# ``user_id=None`` in every log line (audit rows were correct — those go
# through ``auth.current_user_id()`` which uses the right key).
#
# These tests pin the new behavior so a future refactor that drops the
# key list re-introduces the bug is caught at CI time.


def _fake_request_with_session(session_dict: dict):
    """Build a minimal request-like object exposing ``.session``."""
    from types import SimpleNamespace
    from typing import cast

    from starlette.requests import Request

    # SimpleNamespace lets us set arbitrary attrs without subclassing.
    # The cast silences type-checkers (the function under test only
    # reads ``request.session``, which SimpleNamespace exposes fine).
    return cast(Request, SimpleNamespace(session=session_dict))


def test_safe_get_user_id_bcrypt_key():
    """The bcrypt backend's ``local_user_id`` key resolves to the user id."""
    from app.rms.observability import _safe_get_user_id

    req = _fake_request_with_session({"local_user_id": 42})
    assert _safe_get_user_id(req) == "42"


def test_safe_get_user_id_supabase_key():
    """The Supabase backend's ``supabase_user_id`` key resolves to the user id."""
    from app.rms.observability import _safe_get_user_id

    req = _fake_request_with_session({"supabase_user_id": "abc-uuid-1234"})
    assert _safe_get_user_id(req) == "abc-uuid-1234"


def test_safe_get_user_id_generic_key_still_supported():
    """Generic ``user_id`` / ``uid`` / ``user`` keys still work (back-compat)."""
    from app.rms.observability import _safe_get_user_id

    assert _safe_get_user_id(_fake_request_with_session({"user_id": 7})) == "7"
    assert _safe_get_user_id(_fake_request_with_session({"uid": 8})) == "8"
    assert _safe_get_user_id(_fake_request_with_session({"user": "nine"})) == "nine"


def test_safe_get_user_id_missing_returns_none():
    """No recognised key → None (anonymous request)."""
    from app.rms.observability import _safe_get_user_id

    assert _safe_get_user_id(_fake_request_with_session({})) is None
    assert _safe_get_user_id(_fake_request_with_session({"unrelated": "x"})) is None


def test_safe_get_user_id_empty_string_treated_as_missing():
    """An empty string is NOT a valid user id — return None so callers
    can distinguish 'no session' from 'session with user_id=0'."""
    from app.rms.observability import _safe_get_user_id

    assert _safe_get_user_id(_fake_request_with_session({"local_user_id": ""})) is None


def test_safe_get_user_id_priority_order():
    """If multiple keys are present (shouldn't happen, but defensive),
    ``local_user_id`` wins because it's the bcrypt default."""
    from app.rms.observability import _safe_get_user_id

    req = _fake_request_with_session(
        {"local_user_id": 1, "supabase_user_id": "2", "user_id": 3}
    )
    assert _safe_get_user_id(req) == "1"


def test_safe_get_user_id_no_session_attr():
    """A request without ``.session`` (e.g. WebSocket) doesn't crash."""
    from app.rms.observability import _safe_get_user_id

    class _R:
        pass

    r = _R()
    # No .session attribute at all
    assert _safe_get_user_id(r) is None


def test_safe_get_user_id_session_raises_swallowed():
    """If ``request.session`` raises on access (defensive), we still
    return None instead of propagating — middleware must never crash."""
    from app.rms.observability import _safe_get_user_id

    class _R:
        @property
        def session(self):
            raise RuntimeError("session unavailable")

    assert _safe_get_user_id(_R()) is None


def test_session_user_id_keys_constant_is_complete():
    """Pin the canonical session-key list so a future refactor that
    drops a backend breaks here at CI time, not in prod at 2am."""
    from app.rms.observability import _SESSION_USER_ID_KEYS

    # The list must contain the bcrypt AND supabase keys as the first
    # two entries (highest priority). Generic keys come after for
    # back-compat.
    assert "local_user_id" in _SESSION_USER_ID_KEYS
    assert "supabase_user_id" in _SESSION_USER_ID_KEYS
    assert _SESSION_USER_ID_KEYS[0] == "local_user_id"
    assert _SESSION_USER_ID_KEYS[1] == "supabase_user_id"
