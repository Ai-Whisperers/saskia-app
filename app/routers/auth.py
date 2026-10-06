"""app/routers/auth.py — login + logout + password reset routes.

Supports both backends:
- Supabase Auth (when SUPABASE_URL is set) — email + password
- Local bcrypt (fallback for dev / tests)

Routes:
- GET  /login             — render login form
- POST /login             — sign in, set session, redirect
- POST /logout            — clear session, redirect to /login
- GET  /logout            — same as POST (for nav links)
- POST /forgot-password   — trigger password reset email (Supabase only)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.auth import (
    current_user_id,
    get_db_session,
    login_user_local,
    logout_user,
    using_supabase,
)
from app.rms.audit import record as audit_record
from app.rms.config import ASUNCION_TZ
from app.rms.rate_limit import is_disabled, is_rate_limited
from app.services.template_render import render

router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
def login_form(
    request: Request,
    next: str = "/",
    error: str | None = None,
    message: str | None = None,
    retry_after: int | None = None,
) -> HTMLResponse:
    """Render login form."""
    # Remember last username via cookie for returning users
    last_username = ""
    cookie_header = request.headers.get("cookie", "")
    for chunk in cookie_header.split(";"):
        key, _, val = chunk.strip().partition("=")
        if key == "last_username":
            last_username = val or ""
            break

    return render(
        request,
        "login.html",
        {
            "next": next,
            "error": error,
            "message": message,
            "retry_after": retry_after,
            "using_supabase": using_supabase(),
            "last_username": last_username,
        },
    )


@router.post("/login/clear-rate-limit")
def clear_rate_limit(
    request: Request,
    next: str = Form("/"),
    session: Session = Depends(get_db_session),
) -> RedirectResponse:
    """Operator self-service: clear the rate-limit counter for this IP.

    Why: a 5-minute block from failed logins (often the operator's own
    typos) leaves the operator with no in-UI recovery — they have to
    wait or call Ivan. This route wipes login.failure rows for their
    IP, and redirects back to /login. The next legitimate attempt
    succeeds. This is a no-op for the attacker (each request resets
    their own counter; they still get throttled on subsequent hits).
    """
    from app.rms.rate_limit import _client_ip  # noqa: WPS433
    from app.rms.models_legacy import AuditLog

    ip = _client_ip(request)
    # Only clear this IP's login failures, not all of them
    deleted = (
        session.query(AuditLog)
        .filter(AuditLog.action == "login.failure", AuditLog.ip == ip)
        .delete(synchronize_session=False)
    )
    session.commit()
    # Re-validate `next` to avoid open-redirect via this endpoint
    safe_next = next if next.startswith("/") and not next.startswith("//") else "/"
    return RedirectResponse(url=f"/login?next={safe_next}", status_code=303)


@router.post("/login")
def login_submit(
    request: Request,
    username: str = Form(...),  # email for Supabase, username for bcrypt
    password: str = Form(...),
    next: str = Form("/"),
    stay_logged_in: bool = Form(False),
    session: Session = Depends(get_db_session),
) -> RedirectResponse:
    """Sign in. Dispatch to Supabase Auth or local bcrypt based on config."""
    safe_next = next if next.startswith("/") and not next.startswith("//") else "/"

    # Rate limit: block before dispatching to backend.
    # Bypass if AIW_SASKIA_AUTH_DISABLED=1 (test/maintenance).
    if not is_disabled():
        decision = is_rate_limited(session, request)
        if not decision.allowed:
            # Render the styled login page with a clear retry countdown +
            # explicit "Volver a intentar" link so the operator can recover
            # without staring at a raw 429 JSON blob. The countdown is
            # client-side; clicking the link after it elapses sends a fresh
            # request that the rate limiter re-evaluates.
            #
            # The countdown is best-effort: if the server's estimate drifts
            # a few seconds, the worst case is one extra click — the server
            # is the source of truth on the next submission.
            return RedirectResponse(
                url=(
                    f"/login?error=demasiados+intentos+-+esper%C3%AE%20"
                    f"{decision.retry_after_seconds}s&retry_after="
                    f"{decision.retry_after_seconds}&next={safe_next}"
                ),
                status_code=303,
            )

    # Test bypass: when SASKIA_TEST_AUTH_DISABLED=1, accept ANY password and
    # create a local session. This lets Ivan keep working when Supabase is
    # unreachable or the user password has been rotated. Production builds
    # always have SASKIA_TEST_AUTH_DISABLED unset (or =0), so this branch
    # is unreachable there.
    from app.auth import is_auth_disabled

    if is_auth_disabled():
        from app.auth import login_user_local

        # Use a stable test user id and seed a local session cookie.
        login_user_local(request, user_id=999, username=username or "test")
        resp = RedirectResponse(url=safe_next, status_code=status.HTTP_303_SEE_OTHER)
        resp.set_cookie(
            "last_username", username or "test", max_age=86400 * 30, httponly=True, samesite="lax"
        )
        return resp

    if using_supabase():
        return _login_supabase(request, username, password, safe_next, stay_logged_in)
    return _login_local(request, username, password, safe_next, session, stay_logged_in)


def _login_supabase(
    request: Request, email: str, password: str, safe_next: str, stay_logged_in: bool = False
) -> RedirectResponse:
    """Sign in via Supabase Auth."""
    from app.auth_supabase import sign_in_with_password as supabase_sign_in
    from app.auth_supabase import store_session

    session_data = supabase_sign_in(email, password)
    if session_data is None:
        return RedirectResponse(
            url=f"/login?next={safe_next}&error=credenciales+inv%C3%A1lidas",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    store_session(
        request,
        access_token=session_data["access_token"],
        refresh_token=session_data["refresh_token"],
        user_id=session_data["user_id"],
        email=session_data["email"],
    )

    resp = RedirectResponse(url=safe_next, status_code=status.HTTP_303_SEE_OTHER)
    # Remember username for next login
    resp.set_cookie("last_username", email, max_age=86400 * 30, httponly=True, samesite="lax")
    return resp


def _login_local(
    request: Request,
    username: str,
    password: str,
    safe_next: str,
    session: Session,
    stay_logged_in: bool = False,
) -> RedirectResponse:
    """Sign in via local bcrypt (test/dev path)."""

    from app.auth import get_user_model, verify_password

    User = get_user_model()
    user = (
        session.query(User)
        .filter(User.username == username, User.is_active.is_(True))
        .one_or_none()
    )
    if user is None or not verify_password(password, user.password_hash or ""):
        audit_record(
            session,
            user_id=None,
            action="login.failure",
            request=request,
            detail={"backend": "local", "username": username, "reason": "bad_credentials"},
        )
        session.commit()
        return RedirectResponse(
            url=f"/login?next={safe_next}&error=credenciales+inv%C3%A1lidas",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    from datetime import datetime

    login_user_local(request, user.id, user.username)
    user.last_login_at = datetime.now(ASUNCION_TZ).isoformat()
    audit_record(
        session,
        user_id=user.id,
        action="login.success",
        request=request,
        detail={"backend": "local", "username": username},
    )
    session.commit()
    resp = RedirectResponse(url=safe_next, status_code=status.HTTP_303_SEE_OTHER)
    resp.set_cookie("last_username", username, max_age=86400 * 30, httponly=True, samesite="lax")
    return resp


@router.post("/logout")
def logout(request: Request) -> RedirectResponse:
    """Clear session, redirect to /login."""
    user_id = current_user_id(request)
    if using_supabase():
        from app.auth_supabase import SESSION_KEY_ACCESS, sign_out

        access = request.session.get(SESSION_KEY_ACCESS)
        if access:
            sign_out(access)
    db = get_db_session(request)
    audit_record(
        db,
        user_id=user_id,
        action="logout",
        request=request,
    )
    db.commit()
    logout_user(request)
    return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/logout")
def logout_get(request: Request) -> RedirectResponse:
    """GET variant for nav links."""
    user_id = current_user_id(request)
    if using_supabase():
        from app.auth_supabase import SESSION_KEY_ACCESS, sign_out

        access = request.session.get(SESSION_KEY_ACCESS)
        if access:
            sign_out(access)
    db = get_db_session(request)
    audit_record(
        db,
        user_id=user_id,
        action="logout",
        request=request,
    )
    db.commit()
    logout_user(request)
    return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/forgot-password")
def forgot_password(request: Request, email: str = Form(...)) -> RedirectResponse:
    """Trigger a password-reset email via Supabase.

    Always returns success (no email-enumeration leak) — even if the
    email doesn't exist, we pretend we sent the email.
    """
    if using_supabase():
        from app.auth_supabase import trigger_password_reset

        trigger_password_reset(email)
    # Either way, show the same confirmation page
    return RedirectResponse(
        url="/login?message=si+el+correo+existe+te+enviamos+un+link",
        status_code=status.HTTP_303_SEE_OTHER,
    )


__all__ = ["router"]
