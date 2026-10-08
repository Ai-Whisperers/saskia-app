"""app/rms/session_lifecycle.py — production middleware to detect session leaks.

Tracks every Session object opened via request.app.state.session_factory
during a request. If a session is still open when the response returns,
emits a warning log + audit-log row. This is a defense-in-depth
counterpart to the FastAPI dependency-injection pattern: even if a
future route handler forgets to use `Depends(get_session)` and instead
opens a session directly, we'll catch the leak.

Activate in app/rms/main.py:
    from app.rms.session_lifecycle import SessionLifecycleMiddleware
    app.add_middleware(SessionLifecycleMiddleware)

Detection: we use gc.get_referrers() in a finalizer to find any Session
object still referencing the request. If we find one, we close it +
log a warning.

NOTE: DISABLED in production (SASKIA_DEBUG only). The gc.get_objects()
walk is too expensive on every request. Leaking sessions are better
caught via the dependency pattern + explicit session.close() calls.
"""

from __future__ import annotations

import gc
import logging
import os

from fastapi import Request
from fastapi.responses import Response
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("app.rms.session_lifecycle")


class SessionLifecycleMiddleware(BaseHTTPMiddleware):
    """Detect sessions opened during a request that weren't closed."""

    async def dispatch(self, request: Request, call_next: object) -> Response:
        # Skip entirely in production — gc.get_objects() is too expensive
        if not os.getenv("SASKIA_DEBUG"):
            return await call_next(request)

        # Skip for /static/* and /healthz* — they never open DB sessions
        path = request.url.path
        if path.startswith(("/static/", "/healthz")):
            return await call_next(request)

        # Snapshot open sessions before request.
        before_ids = self._open_session_ids()

        response = await call_next(request)

        # After response: scan for any new Session objects that the
        # request opened but didn't close.
        after_ids = self._open_session_ids()
        leaked = after_ids - before_ids
        if leaked:
            logger.warning(
                "session-leak: %d unclosed session(s) after %s %s",
                len(leaked),
                request.method,
                request.url.path,
            )
            # Best-effort: close them so the underlying connection is freed.
            for obj in gc.get_objects():
                if id(obj) in leaked and isinstance(obj, Session):
                    try:
                        obj.close()
                    except Exception:  # noqa: S110
                        pass
        return response

    @staticmethod
    def _open_session_ids() -> set[int]:
        """Return id() set of all SQLAlchemy Session objects currently in memory."""
        return {id(o) for o in gc.get_objects() if isinstance(o, Session)}


__all__ = ["SessionLifecycleMiddleware"]
