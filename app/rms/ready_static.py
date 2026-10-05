"""app/rms/ready_static.py — StaticFiles subclass that gates on app readiness.

Problem: during Render cold-start (5-30s), uvicorn accepts requests before
lifespan finishes create_all() + init_db(). Static files mounted via plain
StaticFiles don't check app.state.ready, so the browser can fetch /static/app.css
during the cold-start window and get a broken layout. Worse, our global
exception handler converts HTTPException into JSON, which the browser can't
parse as CSS → it logs 503 for every retry.

Fix: subclass StaticFiles to check request.app.state.ready first. If not
ready, raise 503 (HTML for browsers, JSON for monitoring tools).
"""

from __future__ import annotations

from fastapi import Request
from starlette.staticfiles import StaticFiles


class ReadyStaticFiles(StaticFiles):
    """StaticFiles that 503s during cold-start (matches /healthz behavior)."""

    async def __call__(self, scope: object, receive: object, send: object) -> None:
        if scope["type"] != "http":
            return await super().__call__(scope, receive, send)

        # Lazy import — Request is a Starlette types helper.
        request = Request(scope)
        ready = getattr(request.app.state, "ready", False)
        if not ready:
            # Mirror /healthz: structured JSON 503.
            from starlette.responses import JSONResponse

            resp = JSONResponse(
                status_code=503,
                content={
                    "status": "warming_up",
                    "detail": "App is still initializing; retry in a few seconds.",
                    "path": scope.get("path", ""),
                },
            )
            await resp(scope, receive, send)
            return

        return await super().__call__(scope, receive, send)


__all__ = ["ReadyStaticFiles"]
