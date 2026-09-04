"""app/auth_supabase.py — Supabase Auth integration (Milestone 1, Supabase path).

When SUPABASE_URL is set, this module replaces the bcrypt-based auth
in app/auth.py with Supabase's managed auth service.

What this gives us:
- Email/password sign-in via Supabase Auth (GoTrue)
- JWT validation against Supabase's JWKS endpoint (locally cached)
- Access + refresh token rotation handled by Supabase
- Password reset via email magic link (Supabase handles delivery)
- User metadata in auth.users (managed by Supabase, not by us)

What we still own:
- Server-side session cookie (SessionMiddleware) — keeps the access
  token encrypted, never exposes it to the browser JS
- Authorization (which rows in our DB this user can see) — RLS or
  app-level checks
- Audit trail (who-did-what) — app_meta or dedicated audit table

References:
- https://supabase.com/docs/reference/python/auth-getuser
- https://supabase.com/docs/guides/auth/jwts
- https://supabase.com/docs/reference/python/auth-signinwithpassword

Why server-side cookies, not client-side Supabase SDK:
- Saskia doesn't need the full Supabase JS SDK
- Our routes are server-rendered HTML, not SPA — no JS auth state needed
- Server-side cookie keeps tokens out of XSS reach
- Same SessionMiddleware pattern as the bcrypt path; easy to swap back
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from fastapi import Request

# --- Config ---

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_PUBLISHABLE_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SECRET_KEY")


def is_supabase_auth_enabled() -> bool:
    """True if all three Supabase env vars are set."""
    return bool(SUPABASE_URL and SUPABASE_ANON_KEY and SUPABASE_SERVICE_ROLE_KEY)


# --- Client singletons (lazy) ---

_client = None  # anon key client (for sign-in)
_admin_client = None  # service role client (for admin operations)


def get_supabase_client():
    """Return the anon-key Supabase client (lazy init)."""
    global _client
    if _client is None:
        from supabase import create_client

        _client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    return _client


def get_supabase_admin():
    """Return the service-role Supabase client (lazy init)."""
    global _admin_client
    if _admin_client is None:
        from supabase import create_client

        _admin_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    return _admin_client


# --- Session model ---


@dataclass
class SupabaseUser:
    """Lightweight user object extracted from a verified JWT."""

    id: str  # Supabase user UUID (string)
    email: str
    role: str  # "authenticated" | "anon" | custom roles
    raw_claims: dict  # full JWT payload for callers who need more

    def is_authenticated(self) -> bool:
        return bool(self.id) and self.role == "authenticated"


# --- Session keys (server-side cookie storage) ---

SESSION_KEY_ACCESS = "supabase_access_token"
SESSION_KEY_REFRESH = "supabase_refresh_token"
SESSION_KEY_USER_ID = "supabase_user_id"
SESSION_KEY_USER_EMAIL = "supabase_user_email"


# --- Sign-in / sign-out ---


def sign_in_with_password(email: str, password: str) -> Optional[dict]:
    """Sign in via Supabase Auth. Returns the session dict on success.

    Returns None on bad credentials (Supabase raises but we swallow).
    Raises on network/Supabase errors.
    """
    client = get_supabase_client()
    try:
        response = client.auth.sign_in_with_password({"email": email, "password": password})
    except Exception as exc:
        # Supabase raises on bad creds; we want a clean None return.
        msg = str(exc).lower()
        if "invalid" in msg or "credentials" in msg or "401" in msg:
            return None
        raise
    if response is None or response.session is None:
        return None
    return {
        "access_token": response.session.access_token,
        "refresh_token": response.session.refresh_token,
        "user_id": response.user.id if response.user else None,
        "email": response.user.email if response.user else None,
    }


def sign_out(access_token: str) -> None:
    """Sign out via Supabase (revokes the refresh token).

    Per Supabase docs, the access_token JWT stays valid until expiry
    even after sign-out (server-side revocation is a TODO from them).
    We mitigate by clearing the cookie immediately, so the browser
    stops sending the JWT to us.
    """
    try:
        client = get_supabase_client()
        client.auth.sign_out()
    except Exception:
        pass  # best-effort


def refresh_session(refresh_token: str) -> Optional[dict]:
    """Use the refresh token to get a new access token.

    Returns new session dict, or None if the refresh token is invalid.
    """
    client = get_supabase_client()
    try:
        response = client.auth.refresh_session(refresh_token)
    except Exception:
        return None
    if response is None or response.session is None:
        return None
    return {
        "access_token": response.session.access_token,
        "refresh_token": response.session.refresh_token,
    }


# --- JWT verification (the hot path) ---


def verify_jwt(access_token: str) -> Optional[SupabaseUser]:
    """Verify the access token against Supabase's JWKS.

    Fast: the SDK caches the JWKS endpoint result and only re-fetches
    on key rotation. Use this on every authenticated request.
    """
    if not access_token:
        return None
    client = get_supabase_client()
    try:
        claims = client.auth.get_claims(access_token)
    except Exception:
        return None
    if claims is None:
        return None
    # claims.claims is the JWT payload dict
    payload = getattr(claims, "claims", {}) or {}
    return SupabaseUser(
        id=str(payload.get("sub", "")),
        email=str(payload.get("email", "")),
        role=str(payload.get("role", "anon")),
        raw_claims=payload,
    )


# --- Cookie session helpers (server-side storage) ---


def store_session(
    request: Request,
    access_token: str,
    refresh_token: str,
    user_id: str,
    email: str,
) -> None:
    """Save the Supabase session into the server-side encrypted cookie."""
    request.session[SESSION_KEY_ACCESS] = access_token
    request.session[SESSION_KEY_REFRESH] = refresh_token
    request.session[SESSION_KEY_USER_ID] = user_id
    request.session[SESSION_KEY_USER_EMAIL] = email


def clear_session(request: Request) -> None:
    """Wipe all session keys."""
    for key in (
        SESSION_KEY_ACCESS,
        SESSION_KEY_REFRESH,
        SESSION_KEY_USER_ID,
        SESSION_KEY_USER_EMAIL,
    ):
        request.session.pop(key, None)


def get_session_user(request: Request) -> Optional[SupabaseUser]:
    """Return the verified user from the cookie session, or None.

    Refreshes the access token if expired. Returns None if cookie
    missing, JWT invalid, or refresh fails.
    """
    access = request.session.get(SESSION_KEY_ACCESS)
    if not access:
        return None
    user = verify_jwt(access)
    if user and user.is_authenticated():
        return user
    # Try refresh
    refresh = request.session.get(SESSION_KEY_REFRESH)
    if not refresh:
        clear_session(request)
        return None
    new_session = refresh_session(refresh)
    if new_session is None:
        clear_session(request)
        return None
    request.session[SESSION_KEY_ACCESS] = new_session["access_token"]
    request.session[SESSION_KEY_REFRESH] = new_session["refresh_token"]
    return verify_jwt(new_session["access_token"])


# --- Password reset ---


def trigger_password_reset(email: str) -> None:
    """Send a password-reset email via Supabase Auth.

    Always returns None silently — we don't leak whether the email
    exists in the system (Supabase's recommended security practice).
    """
    try:
        client = get_supabase_client()
        client.auth.reset_password_email(email)
    except Exception:
        pass


__all__ = [
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
    "is_supabase_auth_enabled",
    "get_supabase_client",
    "get_supabase_admin",
    "SupabaseUser",
    "SESSION_KEY_ACCESS",
    "SESSION_KEY_REFRESH",
    "SESSION_KEY_USER_ID",
    "SESSION_KEY_USER_EMAIL",
    "sign_in_with_password",
    "sign_out",
    "refresh_session",
    "verify_jwt",
    "store_session",
    "clear_session",
    "get_session_user",
    "trigger_password_reset",
]
