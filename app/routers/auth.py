"""app/routers/auth.py — login + logout + (later) password reset."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.auth import (
    get_db_session,
    get_user_model,
    login_user,
    logout_user,
)
from app.services.template_render import render

router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
def login_form(
    request: Request,
    next: str = "/",
    error: str | None = None,
) -> HTMLResponse:
    """Render login form. Preserves ?next= for post-login redirect."""
    return render(
        request,
        "login.html",
        {"next": next, "error": error},
    )


@router.post("/login")
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form("/"),
    session: Session = Depends(get_db_session),
) -> RedirectResponse:
    """Verify credentials, set session, redirect to ?next."""
    User = get_user_model()
    user = (
        session.query(User)
        .filter(User.username == username, User.is_active.is_(True))
        .one_or_none()
    )
    if user is None or not user.check_password(password):
        # Redirect back to /login with error (don't leak which field was wrong)
        return RedirectResponse(
            url=f"/login?next={next}&error=credenciales+inv%C3%A1lidas",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    # Success: set session, update last_login_at
    from datetime import datetime

    login_user(request, user.id, user.username)
    user.last_login_at = datetime.now()
    session.commit()
    # Prevent open-redirect: only allow relative paths starting with /
    safe_next = next if next.startswith("/") and not next.startswith("//") else "/"
    return RedirectResponse(url=safe_next, status_code=status.HTTP_303_SEE_OTHER)


@router.post("/logout")
def logout(request: Request) -> RedirectResponse:
    """Clear session, redirect to /login."""
    logout_user(request)
    return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/logout")
def logout_get(request: Request) -> RedirectResponse:
    """GET variant for the nav logout link (same behavior as POST)."""
    logout_user(request)
    return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)


__all__ = ["router"]
