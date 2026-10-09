"""app/rms/security_headers.py — defense-in-depth HTTP response headers.

Per the 2026-09-04 critical-path plan, E3.S3.

2026-10-07: Migrated from Starlette's BaseHTTPMiddleware to a pure ASGI
implementation, AND added a HTTPException handler. Two bugs motivated
this rewrite:

1. BaseHTTPMiddleware has a well-documented bug where mutations to
   the response object in `dispatch()` are silently dropped because
   Starlette internally builds a `_StreamingResponse` from the raw
   `http.response.start` ASGI message BEFORE `dispatch()` gets a
   chance to mutate headers.

2. Pure ASGI middleware that wraps `send()` doesn't see error
   responses either: when an HTTPException is raised from a
   downstream middleware, it propagates UP through our
   `await self.app(...)` call and our `send_wrapper` is never
   invoked. Starlette's outer ExceptionMiddleware catches the
   exception and builds a fresh JSONResponse that bypasses us.

   Fix: we catch HTTPException ourselves and build the JSONResponse
   with our headers attached, then send it ourselves.

Reference: https://github.com/encode/starlette/issues/1438

Headers added to every response (success or error, GET or POST):
    - X-Frame-Options: DENY
        Block all framing; prevent clickjacking even if CSP
        frame-ancestors is bypassed by a legacy browser.
    - X-Content-Type-Options: nosniff
        Block MIME-sniffing; force browsers to respect the
        Content-Type the server sent.
    - Referrer-Policy: strict-origin-when-cross-origin
        Don't leak full URLs in Referer when navigating cross-origin.
    - Strict-Transport-Security: max-age=31536000; includeSubDomains
        Force HTTPS for 1 year. Only added when HTTPS_ONLY is enabled
        (so local-dev over http://127.0.0.1 isn't broken).
    - Content-Security-Policy: restrictive default-src 'self'
        Inline scripts are necessary for legacy Jinja2 templates;
        allow 'unsafe-inline' on script-src as a transitional measure.
        Tighten to nonce-based once the templates are modernized.
    - Permissions-Policy: minimal
        Disable geolocation, camera, microphone, payment APIs. The RMS
        doesn't need any of them.
    - Cross-Origin-Resource-Policy: same-origin
        Defense-in-depth against Spectre-class cross-origin read attacks
        (OWASP ZAP rule 90004). Sazón is same-origin by design; we have
        no legitimate cross-origin resource consumers.
    - Cross-Origin-Opener-Policy: same-origin
        Isolates the window from cross-origin popups/tabs (Spectre-class
        side-channel defense). Combined CORP+COOP=same-origin fully
        isolates the browsing context.

Headers NOT modified here:
    - Set-Cookie: SameSite=Lax + HttpsOnly are already set in
        app/rms/main.py via SessionMiddleware(...)
    - Server: Starlette doesn't expose Server header by default.

References:
    - https://owasp.org/www-project-secure-headers/
    - https://infosec.mozilla.org/guidelines/web_security
"""

from __future__ import annotations

import os

from fastapi import HTTPException as FastAPIHTTPException
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# Catch either FastAPI's or Starlette's HTTPException class.
HTTPException = (FastAPIHTTPException, StarletteHTTPException)

_CSP = (
    "default-src 'self'; "
    "img-src 'self' data:; "
    "style-src 'self' 'unsafe-inline'; "
    "script-src 'self' 'unsafe-inline'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)

_PERMISSIONS_POLICY = (
    "geolocation=(), "
    "camera=(), "
    "microphone=(), "
    "payment=(), "
    "usb=(), "
    "magnetometer=(), "
    "gyroscope=(), "
    "accelerometer=()"
)


def _security_headers() -> dict[str, str]:
    """Build the headers dict, including HSTS iff HTTPS_ONLY is on.

    HTTPS_ONLY defaults to "true" so this matches prod behavior;
    local dev can opt out by setting HTTPS_ONLY=false.
    """
    headers = {
        "x-frame-options": "DENY",
        "x-content-type-options": "nosniff",
        "referrer-policy": "strict-origin-when-cross-origin",
        "content-security-policy": _CSP,
        "permissions-policy": _PERMISSIONS_POLICY,
        "cross-origin-resource-policy": "same-origin",
        "cross-origin-opener-policy": "same-origin",
        # Explicit default: declares no cross-origin isolation (none of
        # our resources are cross-origin isolated consumers). Satisfies
        # ZAP rule 90004 without breaking third-party asset loads.
        "cross-origin-embedder-policy": "unsafe-none",
    }
    if os.getenv("HTTPS_ONLY", "true").lower() == "true":
        headers["strict-transport-security"] = "max-age=31536000; includeSubDomains"
    return headers


class SecurityHeadersMiddleware:
    """Pure ASGI middleware that injects defense-in-depth response headers.

    Two layers of defense:

    1. `send_wrapper` mutates the `http.response.start` ASGI message
       to add our headers on the way out for normal responses.

    2. The except block catches HTTPException raised from inner
       middleware (e.g. CSRF's 403) and builds the JSONResponse
       with headers attached, since Starlette's ExceptionMiddleware
       bypasses us on the way up.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers_to_add = _security_headers()

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                existing = {k.decode("latin-1").lower(): k for k, _ in message.get("headers", [])}
                merged = list(message.get("headers", []))
                for name, value in headers_to_add.items():
                    if name in existing:
                        continue
                    merged.append((name.encode("latin-1"), value.encode("latin-1")))
                message["headers"] = merged
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except HTTPException as exc:
            # Inner middleware (e.g. csrf_cookie_middleware) raised
            # HTTPException. Our send_wrapper was never called for the
            # error response — Starlette's outer ExceptionMiddleware
            # builds a fresh JSONResponse that bypasses us. So we build
            # the response ourselves with our headers attached.
            response = JSONResponse(
                status_code=exc.status_code,
                content={
                    "error": getattr(exc, "detail", str(exc)),
                    "type": "HTTPException",
                    "status": exc.status_code,
                },
                headers=headers_to_add,
            )
            await response(scope, receive, send)


__all__ = ["SecurityHeadersMiddleware"]
