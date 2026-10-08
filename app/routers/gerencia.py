"""Gerencia landing page. One overview; the modules stay on their own screens."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.auth import require_login_or_disabled as require_login
from app.rms.dependencies import get_session
from app.rms.gerencia_snapshot import snapshot
from app.services.template_render import render

router = APIRouter(dependencies=[Depends(require_login)])


@router.get("/gerencia", response_class=HTMLResponse)
def gerencia_home(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    return render(request, "gerencia.html", snapshot(session))
