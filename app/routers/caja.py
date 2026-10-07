"""app/routers/caja.py — WP-1.3 arqueo de caja X/Z.

GET  /caja            → estado actual (abierta: expected vivo; cerrada: última)
POST /caja/abrir      → abre sesión con monto inicial
POST /caja/cerrar     → cierra con conteo físico (diff = counted - expected)
GET  /caja/z/{id}     → ticket Z imprimible (eod_print.html patrón)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import current_user_id
from app.auth import require_login_or_disabled as require_login
from app.rms.cash import (
    CashSessionConflict,
    CashSessionError,
    close_session,
    expected_gs,
    get_open_session,
    open_session,
)
from app.rms.dependencies import get_session
from app.rms.models_legacy import CashSession
from app.rms.observability import record_audit
from app.rms.rate_limit import is_write_rate_limited
from app.services.template_render import render

router = APIRouter(prefix="/caja", dependencies=[Depends(require_login)])


def _fmt(v: int | None) -> str:
    return f"Gs. {v:,.0f}".replace(",", ".") if v is not None else "—"


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
def caja_home(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    open_sess = get_open_session(session)
    recent = (
        session.execute(select(CashSession).order_by(CashSession.id.desc()).limit(10))
        .scalars()
        .all()
    )
    exp = expected_gs(session, open_sess) if open_sess is not None else None
    return render(
        request,
        "caja.html",
        {
            "open_sess": open_sess,
            "expected": exp,
            "recent": recent,
            "money": _fmt,
        },
    )


@router.post("/abrir")
def caja_abrir(
    request: Request,
    opening_gs: str = Form("0"),
    channel: str = Form(""),
    note: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    from app.rms.money import to_int_gs

    if is_write_rate_limited(session, request):
        return RedirectResponse("/caja?flash=rate_limited", status_code=303)
    try:
        opening = to_int_gs(str(opening_gs))
        sess = open_session(
            session,
            opening_gs=opening,
            opened_by=str(current_user_id(request) or "operador"),
            channel=channel or None,
            note=note or None,
        )
        session.commit()
    except (CashSessionConflict, CashSessionError) as e:
        return RedirectResponse(f"/caja?flash=caja_error&msg={e}", status_code=303)
    record_audit(
        request,
        session=session,
        action="cash_session_open",
        target_type="cash_session",
        target_id=sess.id,
        detail={"opening_gs": sess.opening_gs},
    )
    session.commit()
    return RedirectResponse("/caja?flash=caja_abierta", status_code=303)


@router.post("/cerrar")
def caja_cerrar(
    request: Request,
    counted_gs: str = Form("0"),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    from app.rms.money import to_int_gs

    if is_write_rate_limited(session, request):
        return RedirectResponse("/caja?flash=rate_limited", status_code=303)
    try:
        counted = to_int_gs(str(counted_gs))
        sess = close_session(
            session,
            counted_gs=counted,
            closed_by=str(current_user_id(request) or "operador"),
        )
        session.commit()
    except (CashSessionError, CashSessionConflict) as e:
        return RedirectResponse(f"/caja?flash=caja_error&msg={e}", status_code=303)
    record_audit(
        request,
        session=session,
        action="cash_session_close",
        target_type="cash_session",
        target_id=sess.id,
        detail={
            "counted_gs": sess.counted_gs,
            "expected_gs": sess.expected_gs,
            "diff_gs": sess.diff_gs,
        },
    )
    session.commit()
    return RedirectResponse(f"/caja?flash=caja_cerrada&zid={sess.id}", status_code=303)


@router.get("/z/{session_id}", response_class=HTMLResponse)
def caja_z(
    session_id: int, request: Request, session: Session = Depends(get_session)
) -> HTMLResponse:
    sess = session.get(CashSession, session_id)
    if sess is None:
        return render(request, "caja.html", {"error": "Sesión no encontrada"}, status_code=404)
    return render(request, "caja_z.html", {"sess": sess, "money": _fmt})
