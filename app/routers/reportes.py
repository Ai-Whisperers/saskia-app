"""app/routers/reportes.py — /reportes (IVA reports, libro de ventas, daily summary).

Built on app/rms/accounting.py which has monthly_iva_breakdown + libro_ventas
+ daily_summary.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.auth import require_login_or_disabled as require_login
from app.rms.accounting import daily_summary, libro_ventas, monthly_iva_breakdown
from app.rms.dependencies import get_session
from app.services.template_render import render

router = APIRouter(prefix="/reportes", dependencies=[Depends(require_login)])


@router.get("", response_class=HTMLResponse)
def reportes_index(request: Request) -> HTMLResponse:
    """Reports hub."""
    return render(request, "reportes.html", {})


@router.get("/iva", response_class=HTMLResponse)
def reportes_iva(
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Monthly IVA breakdown (last 12 months)."""
    rows = monthly_iva_breakdown(session)
    return render(request, "reportes_iva.html", {"rows": rows})


@router.get("/libro-ventas", response_class=HTMLResponse)
def reportes_libro_ventas(
    request: Request,
    start: str | None = Query(None),
    end: str | None = Query(None),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Libro de Ventas (chronological) within a date range."""
    if start:
        start_date = datetime.fromisoformat(start)
    else:
        start_date = datetime.now(timezone.utc) - timedelta(days=30)
    if end:
        end_date = datetime.fromisoformat(end)
    else:
        end_date = datetime.now(timezone.utc)
    rows = libro_ventas(session, start_date=start_date, end_date=end_date)
    return render(request, "reportes_libro_ventas.html", {
        "rows": rows,
        "start_date": start_date.date().isoformat(),
        "end_date": end_date.date().isoformat(),
    })


@router.get("/diario", response_class=HTMLResponse)
def reportes_diario(
    request: Request,
    for_date: str | None = Query(None),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Daily summary (revenue, IVA, COGS, margin)."""
    if for_date:
        d = datetime.fromisoformat(for_date)
    else:
        d = datetime.now(timezone.utc)
    summary = daily_summary(session, day=d)
    return render(request, "reportes_diario.html", {
        "summary": summary,
        "for_date": d.date().isoformat(),
    })


__all__ = ["router"]
