"""app/rms/observability.py — Request-scoped logging context + middleware.

Every request gets:
- request_id (UUID4 hex, surfaced in X-Request-Id header + error pages)
- user_id (from session, if authenticated)
- path / method / route

The Loguru `logger.contextualize()` makes these auto-attach to every
log line emitted during the request, so support can grep one request_id
and see the full trace without manual f-string interpolation in every
router.

Also exposes a `record_audit()` helper that:
- auto-fills the request_id
- wraps `app.rms.audit.record` with structured error handling
- catches DB failures (so a buggy audit never crashes the request)
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Callable

from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_REQUEST_ID_HEADER = "X-Request-Id"
_LOG_CONTEXT_KEYS = ("request_id", "user_id", "method", "path", "route")

# Order matters: the bcrypt backend writes ``local_user_id`` (see
# ``app.auth.LOCAL_SESSION_KEY_USER_ID``) and the Supabase backend writes
# ``supabase_user_id`` (see ``app.auth_supabase.SESSION_KEY_USER_ID``).
# The previous lookup only checked a generic ``user_id`` / ``uid`` /
# ``user`` set of keys, so bcrypt users logged as ``user_id=None`` in
# every log line — fixed 2026-09-29 (see IMPROVEMENT_BACKLOG.md #41).
_SESSION_USER_ID_KEYS = (
    "local_user_id",
    "supabase_user_id",
    "user_id",
    "uid",
    "user",
)


def generate_request_id() -> str:
    """Generate a short, URL-safe request id (12 hex chars)."""
    return uuid.uuid4().hex[:12]


def _safe_get_user_id(request: Request) -> str | None:
    """Extract user id from session if present (without raising).

    Tries each known backend's session key in order; first non-empty wins.
    See ``_SESSION_USER_ID_KEYS`` for the canonical list.
    """
    try:
        sess = getattr(request, "session", None) or {}
        for key in _SESSION_USER_ID_KEYS:
            u = sess.get(key)
            if u is not None and u != "":
                return str(u)
        return None
    except Exception:
        return None


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach request_id + user_id to every log line, set X-Request-Id header.

    This is the single chokepoint that makes the rest of the app
    traceable. Without it, every router would need to manually thread
    request_id through every function call.

    The middleware is registered FIRST in ``app.add_middleware`` so it
    ends up the INNERMOST — meaning by the time its preprocess runs,
    the outer ``_NoVaryCookieSessionMiddleware`` has already decrypted
    the cookie and ``request.session`` is populated. (BACKLOG #41.)
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Honour incoming X-Request-Id if a proxy/upstream set one.
        # This makes traces stitchable across services.
        rid = request.headers.get(_REQUEST_ID_HEADER) or generate_request_id()
        request.state.request_id = rid

        # ``request.session`` works here because RequestContextMiddleware
        # is registered FIRST in app.add_middleware() calls, which makes
        # it the INNERMOST middleware at request time — so the outer
        # SessionMiddleware has already populated scope["session"] before
        # our preprocess reads it. (BACKLOG #41 — was the cause of
        # ``user_id=None`` on every log line prior to 2026-09-29.)
        request.state.user_id = _safe_get_user_id(request)

        # Bind context for all loguru emissions during this request.
        with logger.contextualize(
            request_id=rid,
            user_id=request.state.user_id,
            method=request.method,
            path=request.url.path,
        ):
            # Skip access log for high-noise endpoints (static assets,
            # health probes). The exception handler still runs for these.
            skip_log = request.url.path.startswith(("/static/", "/healthz"))
            start = time.perf_counter() if not skip_log else None
            try:
                response = await call_next(request)
            except Exception as exc:
                # AppError / HTTPException are EXPECTED: FastAPI's exception
                # handler will render them with the right status. We just
                # re-raise without logging (the exception handler will log).
                from fastapi import HTTPException

                from app.rms.errors import AppError

                if isinstance(exc, (AppError, HTTPException)):
                    raise
                # True unhandled: log + re-raise so the global handler picks it up.
                if not skip_log:
                    elapsed_ms = (time.perf_counter() - start) * 1000  # type: ignore
                    logger.error(
                        "request CRASHED method={} path={} elapsed_ms={:.0f} error={!r}",
                        request.method,
                        request.url.path,
                        elapsed_ms,
                        exc,
                    )
                raise
            if not skip_log:
                elapsed_ms = (time.perf_counter() - start) * 1000  # type: ignore
                # INFO for 2xx/3xx, WARNING for 4xx, ERROR for 5xx
                log_fn = (
                    logger.error
                    if response.status_code >= 500
                    else logger.warning
                    if response.status_code >= 400
                    else logger.info
                )
                log_fn(
                    "access method={} path={} status={} elapsed_ms={:.0f}",
                    request.method,
                    request.url.path,
                    response.status_code,
                    elapsed_ms,
                )
            # CRITICAL: do not read response.body here. Reading it would
            # consume the body iterator that GZipMiddleware (registered
            # OUTSIDE us) needs to wrap. Returning the response untouched
            # lets GZip see the original body size and decide whether to
            # compress based on minimum_size.
            response.headers[_REQUEST_ID_HEADER] = rid
            return response


def bind_request_route(request: Request, route_name: str) -> None:
    """Re-bind loguru context with the matched route name (call after routing)."""
    # Loguru doesn't support incremental context updates cleanly, so
    # we emit a marker line. The next logger.* call in the same request
    # won't have it, but it's still useful for grep/grep-aware tooling.
    logger.bind(route=route_name).debug("route matched")


def record_audit(
    request: Request,
    *,
    session: Any,
    action: str,
    target_type: str | None = None,
    target_id: str | int | None = None,
    detail: dict[str, Any] | None = None,
    user_id: str | None = None,
) -> str | None:
    """Best-effort audit log row that auto-fills request_id + user_id.

    Returns the audit row id on success, None if audit DB call failed.
    Never raises — a broken audit must not break the user's request.
    Use the `session` parameter (NOT a factory) — the caller's session
    is mid-transaction and committing here is intentional.
    """
    from app.rms.audit import record

    rid = getattr(request.state, "request_id", None)
    uid = user_id or getattr(request.state, "user_id", None)
    merged_detail = {"request_id": rid, **(detail or {})}
    try:
        return record(
            session,
            user_id=uid,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            detail=merged_detail,
            request=request,
        )
    except Exception as e:  # pragma: no cover — defensive
        logger.error(
            "audit_log_failed action={} target={}#{} rid={}: {!r}",
            action,
            target_type,
            target_id,
            rid,
            e,
        )
        return None
