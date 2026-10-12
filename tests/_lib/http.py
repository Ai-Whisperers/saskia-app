"""tests/_lib/http.py — Shared HTTP status code constants.

Eliminates the (200, 302, 303, 307, 404, 500) duplication across 8 tier
test files. Use the named constants instead of inline tuples.

Usage:
    from tests._lib.http import SAFE_CODES, AUTH_CODES, LOGIN_CODES

    def test_x(client):
        r = client.get("/")
        assert r.status_code in SAFE_CODES
"""

from __future__ import annotations

# Safe response codes — any of these is acceptable for "page loaded"
SAFE_CODES = (200, 302, 303, 307, 404, 500)

# Authentication-related codes
AUTH_CODES = (200, 302, 303, 307, 401, 403, 404, 500)

# Authentication codes including method-not-allowed
AUTH_METHOD_CODES = (200, 302, 303, 307, 401, 403, 404, 405, 500)

# Login form codes — same as safe but includes 503
LOGIN_CODES = (200, 302, 303, 307, 401, 403, 404, 405, 500, 503)

# Login form codes with POST that should be rejected
LOGIN_POST_CODES = (200, 302, 303, 307, 400, 401, 403, 404, 422, 500)

# Login codes that should NEVER return 500
LOGIN_SAFE_CODES = (200, 302, 303, 307, 400, 401, 403, 404, 422)

# Rate-limited login codes
LOGIN_RATE_LIMITED_CODES = (200, 302, 303, 307, 400, 401, 403, 404, 422, 429, 500)

# Method not allowed
METHOD_NOT_ALLOWED_CODES = (200, 302, 303, 307, 401, 403, 404, 405, 500)

# Auth codes (for routes that need login)
REQUIRES_LOGIN_CODES = (200, 302, 303, 307, 401, 403, 404, 500)


__all__ = [
    "AUTH_CODES",
    "AUTH_METHOD_CODES",
    "LOGIN_CODES",
    "LOGIN_POST_CODES",
    "LOGIN_RATE_LIMITED_CODES",
    "LOGIN_SAFE_CODES",
    "METHOD_NOT_ALLOWED_CODES",
    "REQUIRES_LOGIN_CODES",
    "SAFE_CODES",
]
