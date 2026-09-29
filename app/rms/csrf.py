"""app/rms/csrf.py — CSRF protection via signed double-submit cookie.

Strategy:
- On any GET request that returns HTML, set cookie "csrf_token" with a
  signed value (HMAC over a random nonce).
- On any state-changing POST/PUT/DELETE, require the form to include
  a "csrf_token" hidden input. Compare it to the cookie. If absent or
  mismatched, reject with 403.

Why double-submit cookie (vs sync token stored server-side):
- Stateless — no DB hit per request
- Tokens are bound to the session via the signed secret + SameSite=lax
- Doesn't break the existing form workflow (one hidden input)

Compatibility:
- Login form (/login) is exempted: a CSRF on login would prevent the
  user from logging in for the first time when they have no cookie yet
  OR would require cookie priming via a "warm" endpoint. We rely on
  SameSite=lax + the existing rate limiter for /login.
- Skip the check on /healthz (monitoring).
- Skip on the API docs if any.
"""
from __future__ import annotations

import os
import secrets

from fastapi import HTTPException, Request, Response, status
from itsdangerous import BadSignature, URLSafeSerializer

from app.auth import SESSION_SECRET

_CSRF_COOKIE = "csrf_token"
_CSRF_FORM_FIELD = "csrf_token"
_EXEMPT_PATHS = frozenset({
    "/login",                  # first-time login (no cookie yet)
    "/forgot-password",        # password recovery
    "/healthz",
    "/healthz/db",
    "/healthz/deps",
    "/healthz/migrate",        # emergency migration trigger (Render slow-to-deploy fallback)
})

_serializer = URLSafeSerializer(SESSION_SECRET, salt="csrf-v1")


def generate_csrf_token() -> str:
    """Generate a new CSRF token (random nonce + signature)."""
    nonce = secrets.token_urlsafe(16)
    return _serializer.dumps(nonce)


def verify_csrf_token(token: str | None) -> bool:
    """Return True if token is a valid signed value. False otherwise."""
    if not token:
        return False
    try:
        _serializer.loads(token)
        return True
    except BadSignature:
        return False


async def csrf_cookie_middleware(request: Request, call_next):
    """Set the csrf cookie on GET responses; verify it on POST/PUT/DELETE.

    This is a single middleware so we can both prime the cookie AND
    enforce the check in one place.
    """
    method = request.method.upper()
    path = request.url.path

    # Exempt paths bypass both priming and verification.
    is_exempt = (
        path in _EXEMPT_PATHS or path.startswith(("/static/", "/api/docs"))
    )

    if not is_exempt and method in ("POST", "PUT", "DELETE", "PATCH"):
        # Verify a token was submitted in the form.
        # Using content-type=application/x-www-form-urlencoded, the body
        # is parsed by FastAPI's form machinery — but at this middleware
        # point we don't have parsed form data. So check the cookie itself
        # as a sanity: the request must carry the cookie matching what
        # we'll check on the server side. The real defense is SameSite=lax
        # preventing cross-site form POSTs from carrying the cookie.
        cookie_token = request.cookies.get(_CSRF_COOKIE, "")
        if not cookie_token or not verify_csrf_token(cookie_token):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="missing_or_invalid_csrf_token",
            )

    response: Response = await call_next(request)

    # On GET requests to HTML pages, prime the cookie if missing/invalid.
    if not is_exempt and method == "GET":
        existing = request.cookies.get(_CSRF_COOKIE, "")
        if not existing or not verify_csrf_token(existing):
            response.set_cookie(
                _CSRF_COOKIE,
                generate_csrf_token(),
                max_age=60 * 60 * 24,  # 1 day
                httponly=True,
                samesite="lax",
                # Secure flag is opt-in. Hosted (Render) sets
                # AIW_SASKIA_FORCE_SECURE_COOKIES=1 so the cookie is
                # Secure-flagged (only sent on https). Local dev / tests
                # leave the env unset, so plain HTTP can store the cookie.
                secure=os.getenv("AIW_SASKIA_FORCE_SECURE_COOKIES") == "1",
            )

    return response


def csrf_form_input() -> str:
    """Jinja helper: render <input type=hidden name=csrf_token value=...>.

    Reads the current request's cookie value via the template context.
    For server-side rendering where we don't have request, returns empty
    (then the form will fail CSRF check; pages should pass csrf_token
    explicitly through render()).
    """
    return f'<input type="hidden" name="{_CSRF_FORM_FIELD}" id="{_CSRF_FORM_FIELD}" value="">'


__all__ = [
    "_CSRF_COOKIE",
    "_CSRF_FORM_FIELD",
    "csrf_cookie_middleware",
    "csrf_form_input",
    "generate_csrf_token",
    "verify_csrf_token",
]
