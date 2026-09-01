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
    get_db_session,
    login_user_local,
    logout_user,
    using_supabase,
)
from app.services.template_render import render

router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
def login_form(
    request: Request,
    next: str = "/",
    error: str | None = None,
    message: str | None = None,
) -> HTMLResponse:
    """Render login form."""
    return render(
        request,
        "login.html",
        {
            "next": next,
            "error": error,
            "message": message,
            "using_supabase": using_supabase(),
        },
    )


@router.post("/login")
def login_submit(
    request: Request,
    username: str = Form(...),  # email for Supabase, username for bcrypt
    password: str = Form(...),
    next: str = Form("/"),
    session: Session = Depends(get_db_session),
) -> RedirectResponse:
    """Sign in. Dispatch to Supabase Auth or local bcrypt based on config."""
    safe_next = next if next.startswith("/") and not next.startswith("//") else "/"

    if using_supabase():
        return _login_supabase(request, username, password, safe_next)
    return _login_local(request, username, password, safe_next, session)


def _login_supabase(
    request: Request, email: str, password: str, safe_next: str
) -> RedirectResponse:
    """Sign in via Supabase Auth."""
    from app.auth_supabase import sign_in_with_password, store_session

    session_data = sign_in_with_password(email, password)
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
    return RedirectResponse(url=safe_next, status_code=status.HTTP_303_SEE_OTHER)


def _login_local(
    request: Request,
    username: str,
    password: str,
    safe_next: str,
    session: Session,
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
        return RedirectResponse(
            url=f"/login?next={safe_next}&error=credenciales+inv%C3%A1lidas",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    from datetime import datetime

    login_user_local(request, user.id, user.username)
    user.last_login_at = datetime.now().isoformat()
    session.commit()
    return RedirectResponse(url=safe_next, status_code=status.HTTP_303_SEE_OTHER)


@router.post("/logout")
def logout(request: Request) -> RedirectResponse:
    """Clear session, redirect to /login."""
    if using_supabase():
        from app.auth_supabase import SESSION_KEY_ACCESS, sign_out

        access = request.session.get(SESSION_KEY_ACCESS)
        if access:
            sign_out(access)
    logout_user(request)
    return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/logout")
def logout_get(request: Request) -> RedirectResponse:
    """GET variant for nav links."""
    if using_supabase():
        from app.auth_supabase import SESSION_KEY_ACCESS, sign_out

        access = request.session.get(SESSION_KEY_ACCESS)
        if access:
            sign_out(access)
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
