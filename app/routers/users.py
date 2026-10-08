"""app/routers/users.py — /users user management (admin only).

CRUD for local-bcrypt users. Supabase-auth deployments use the Supabase dashboard.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.auth import (
    current_user_id,
    get_current_user,
    get_user_model,
    hash_password,
)
from app.auth import (
    require_login_or_disabled as require_login,
)
from app.rms.audit import record as audit_record
from app.rms.dependencies import get_session
from app.rms.stations import ACCEPTED_ROLES, ASSIGNABLE_ROLES
from app.services.template_render import render

router = APIRouter(prefix="/users", dependencies=[Depends(require_login)])

VALID_ROLES = ACCEPTED_ROLES


def _is_admin(user: object) -> bool:
    """Return True if the current user has admin role."""
    if user is None:
        return False
    # For Supabase users (dict-like), check role field
    if hasattr(user, "role"):
        return getattr(user, "role", None) == "admin"
    # For ORM User objects
    return getattr(user, "role", "admin") == "admin"


def _require_admin(request: Request, session: Session = Depends(get_session)) -> object:
    """Dependency: require admin role, else 403."""
    user = get_current_user(request, session)
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="Acceso denegado: se requiere rol admin")
    return user


@router.get("", response_class=HTMLResponse)
def users_list(
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """User management page (admin only)."""
    _require_admin(request, session)
    User = get_user_model()
    users = session.query(User).order_by(User.id).all()

    return render(
        request,
        "users.html",
        {
            "users": users,
            "current_user_id": current_user_id(request),
            "total": len(users),
            "page_start": 1,
            "page_end": len(users),
        },
    )


@router.post("/crear", response_class=RedirectResponse)
def users_create(
    request: Request,
    username: str = Form(""),
    password: str = Form(""),
    role: str = Form("cashier"),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Create a new user (admin only)."""
    from app.rms.validation import require_text

    _require_admin(request, session)

    clean_username = require_text(username, field="nombre de usuario", max_len=120)
    clean_password = require_text(password, field="contraseña", max_len=200)

    if role not in VALID_ROLES:
        raise HTTPException(status_code=422, detail=f"Rol inválido: {role}")

    if len(clean_password) < 6:
        return RedirectResponse(
            url="/users?flash=La+contraseña+debe+tener+al+menos+6+caracteres",
            status_code=303,
        )

    User = get_user_model()

    # Check username uniqueness
    existing = session.query(User).filter(User.username == clean_username).first()
    if existing:
        return RedirectResponse(
            url="/users?flash=El+nombre+de+usuario+ya+existe",
            status_code=303,
        )

    user = User(
        username=clean_username,
        password_hash=hash_password(clean_password),
        role=role,
        is_active=True,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    session.add(user)
    audit_record(
        session,
        user_id=current_user_id(request),
        action="user.create",
        detail={"username": clean_username, "role": role},
    )
    session.commit()

    return RedirectResponse(url="/users?flash=Usuario+creado", status_code=303)


@router.post("/{user_id}/editar", response_class=RedirectResponse)
def users_edit(
    request: Request,
    user_id: int,
    username: str = Form(""),
    role: str = Form("cashier"),
    is_active: bool = Form(False),
    new_password: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Edit an existing user (admin only)."""
    from app.rms.validation import require_text

    admin_user = _require_admin(request, session)

    clean_username = require_text(username, field="nombre de usuario", max_len=120)

    if role not in VALID_ROLES:
        raise HTTPException(status_code=422, detail=f"Rol inválido: {role}")

    User = get_user_model()
    user = session.get(User, user_id)

    if user is None:
        return RedirectResponse(url="/users?flash=Usuario+no+encontrado", status_code=303)

    # Check username uniqueness (excluding self)
    existing = (
        session.query(User)
        .filter(
            User.username == clean_username,
            User.id != user_id,
        )
        .first()
    )
    if existing:
        return RedirectResponse(
            url="/users?flash=El+nombre+de+usuario+ya+existe",
            status_code=303,
        )

    user.username = clean_username
    user.role = role
    user.is_active = is_active

    if new_password:
        if len(new_password) < 6:
            return RedirectResponse(
                url="/users?flash=La+contraseña+debe+tener+al+menos+6+caracteres",
                status_code=303,
            )
        user.password_hash = hash_password(new_password)
        audit_record(
            session,
            user_id=current_user_id(request),
            action="user.password_change",
            detail={
                "target_user": clean_username,
                "changed_by": admin_user.username
                if hasattr(admin_user, "username")
                else str(admin_user),
            },
        )

    audit_record(
        session,
        user_id=current_user_id(request),
        action="user.update",
        detail={"username": username, "role": role, "is_active": is_active},
    )
    session.commit()

    return RedirectResponse(url="/users?flash=Usuario+actualizado", status_code=303)


@router.post("/{user_id}/eliminar", response_class=RedirectResponse)
def users_delete(
    request: Request,
    user_id: int,
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Delete a user (admin only). Cannot delete yourself."""
    _require_admin(request, session)

    User = get_user_model()
    user = session.get(User, user_id)

    if user is None:
        return RedirectResponse(url="/users?flash=Usuario+no+encontrado", status_code=303)

    current_uid = current_user_id(request)
    if user.id == current_uid:
        return RedirectResponse(
            url="/users?flash=No+puedes+eliminarte+a+ti+mismo",
            status_code=303,
        )

    username = user.username
    session.delete(user)
    audit_record(
        session,
        user_id=current_uid,
        action="user.delete",
        detail={"deleted_username": username},
    )
    session.commit()

    return RedirectResponse(url="/users?flash=Usuario+eliminado", status_code=303)


@router.get("/api/roles", response_class=JSONResponse)
def user_roles_api() -> JSONResponse:
    """List all available user roles.

    Used by the combo system on /users form for role selection.
    """
    payload = []
    for value, display in ASSIGNABLE_ROLES:
        payload.append(
            {
                "value": value,
                "display": display,
            }
        )

    return JSONResponse({"results": payload, "count": len(payload)})


__all__ = ["router"]
