"""app/rms/security_headers.py — defense-in-depth HTTP response headers.

Per the 2026-09-04 critical-path plan, E3.S3.

Headers added to every response:
  - X-Frame-Options: DENY
      Block all framing; prevent clickjacking even if CSP frame-ancestors
      is bypassed by a legacy browser.
  - X-Content-Type-Options: nosniff
      Block MIME-sniffing; force browsers to respect the Content-Type
      the server sent.
  - Referrer-Policy: strict-origin-when-cross-origin
      Don't leak full URLs in Referer when navigating cross-origin.
  - Strict-Transport-Security: max-age=31536000; includeSubDomains
      Force HTTPS for 1 year. Only added when HTTPS_ONLY is enabled
      (so local-dev over http://127.0.0.1 isn't broken).
  - Content-Security-Policy: restrictive default-src 'self'
      Inline scripts are necessary for legacy Jinja2 templates; allow
      'unsafe-inline' on script-src as a transitional measure. Tighten
      to nonce-based once the templates are modernized.
  - Permissions-Policy: minimal
      Disable geolocation, camera, microphone, payment APIs. The RMS
      doesn't need any of them.

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

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

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


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add defense-in-depth response headers to every HTTP response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Content-Security-Policy", _CSP)
        response.headers.setdefault("Permissions-Policy", _PERMISSIONS_POLICY)

        # HSTS only when serving over HTTPS (or behind CF Tunnel which
        # always terminates TLS). HTTPS_ONLY defaults to "true" so this
        # matches prod behavior; local dev can opt out by setting
        # HTTPS_ONLY=false.
        https_only = os.getenv("HTTPS_ONLY", "true").lower() == "true"
        if https_only:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )

        return response


__all__ = ["SecurityHeadersMiddleware"]
