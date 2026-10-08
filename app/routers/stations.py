"""Chooser and station switch. Owner picks a task; staff never reach this page."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse, Response

from app.rms.stations import (
    SESSION_LOCKED,
    SESSION_STATION,
    STATIONS,
    decide,
    get_station,
)
from app.services.template_render import render

router = APIRouter()


def _redirect_if_locked(request: Request) -> RedirectResponse | None:
    from app.auth import is_auth_disabled

    result = decide(
        request.url.path,
        request.session,
        auth_disabled=is_auth_disabled(),
        user_present=True,
    )
    if result and result.startswith("redirect:"):
        return RedirectResponse(result.split(":", 1)[1], status_code=303)
    return None


@router.get("/puesto")
def puesto(request: Request) -> Response:
    """Five stations. Staff are sent to their pinned home before this renders."""
    locked = _redirect_if_locked(request)
    if locked is not None:
        return locked
    return render(
        request,
        "puesto.html",
        {
            "stations": list(STATIONS.values()),
            "on_chooser": True,
        },
    )


@router.post("/puesto")
def puesto_elegir(request: Request, station: str = Form(...)) -> Response:
    """Owner enters a station. A pinned login cannot change it."""
    locked = _redirect_if_locked(request)
    if locked is not None:
        return locked
    chosen = get_station(station)
    if chosen is None:
        return RedirectResponse("/puesto", status_code=303)
    request.session[SESSION_STATION] = chosen.id
    request.session[SESSION_LOCKED] = False
    return RedirectResponse(chosen.home, status_code=303)


@router.get("/puesto/cambiar")
def puesto_cambiar(request: Request) -> Response:
    """Owner returns to the five stations. Staff stay where they are."""
    locked = _redirect_if_locked(request)
    if locked is not None:
        return locked
    request.session.pop(SESSION_STATION, None)
    request.session[SESSION_LOCKED] = False
    return RedirectResponse("/puesto", status_code=303)
