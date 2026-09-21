"""app/routers/produccion.py — /produccion (Production worksheet + calendar).

Views:
  day   (default) — one day's plan table (backward compat: for_date param)
  week  — 7-day grid via the calendar macro (Saskia: "calendario cíclico
          por semana")
  month — month grid via the calendar macro

POST /produccion/override — per-day manual qty override (query-param
persistence: the override lands in the redirect URL as ov_{product_id}
so the day view re-renders with manual_forecast applied. Nothing is
stored in the DB — an override is a what-if re-plan, not an edit.)

Seasonal-multiplier editor intentionally absent: blocked on T-0.1
(forecast_source semantics clarification with Saskia).
"""
from __future__ import annotations

import calendar as _calendar
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.auth import require_login_or_disabled as require_login
from app.rms.dependencies import get_session
from app.rms.models import Product
from app.rms.production import plan_production
from app.services.template_render import render

router = APIRouter(prefix="/produccion", dependencies=[Depends(require_login)])

FORECAST_SOURCE_LABELS = {
    "rolling_14d_avg": "Promedio 14 días",
    "seasonal_event": "Evento estacional",
    "manual": "Manual",
}
FORECAST_SOURCE_HELP = {
    "rolling_14d_avg": "Promedio de ventas de los últimos 14 días",
    "seasonal_event": "Ajuste por evento estacional en la fecha",
    "manual": "Cantidad cargada a mano",
}


def _asuncion_today() -> date:
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo

    return datetime.now(timezone.utc).astimezone(ZoneInfo("America/Asuncion")).date()


def _week_monday(any_date: date) -> date:
    return any_date - timedelta(days=any_date.weekday())


def _day_counts(session: Session, days: list[date]) -> dict[str, int]:
    """item_count per day: number of products with qty>0 in that day's plan."""
    counts: dict[str, int] = {}
    for d in days:
        plan = plan_production(session, for_date=d)
        counts[d.isoformat()] = len([r for r in plan.rows if r.qty_to_produce > 0])
    return counts


def _parse_overrides(params) -> dict[int, float]:
    """Override params look like ov_12=10.5 -> {12: 10.5}."""
    out: dict[int, float] = {}
    for key, value in params.items():
        if key.startswith("ov_"):
            try:
                out[int(key[3:])] = float(value)
            except (TypeError, ValueError):
                continue
    return out


@router.get("", response_class=HTMLResponse)
def produccion_worksheet(
    request: Request,
    view: str = Query("day", pattern="^(day|week|month)$"),
    for_date: date | None = Query(None),
    week: date | None = Query(None),
    month: str | None = Query(None, pattern=r"^\d{4}-\d{2}$"),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Production plan: day table, week grid, or month grid."""
    today = _asuncion_today()
    overrides = _parse_overrides(request.query_params)

    if view == "week":
        week_start = _week_monday(week or today)
        days = [week_start + timedelta(days=i) for i in range(7)]
        counts = _day_counts(session, days)
        day_dicts = [
            {
                "date_iso": d.isoformat(),
                "label": str(d.day),
                "item_count": counts.get(d.isoformat(), 0),
                "is_today": d == today,
                "is_selected": False,
            }
            for d in days
        ]
        return render(
            request,
            "produccion_calendario.html",
            {
                "view": "week",
                "weekdays": ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"],
                "days": day_dicts,
                "prev_week_iso": (week_start - timedelta(days=7)).isoformat(),
                "next_week_iso": (week_start + timedelta(days=7)).isoformat(),
                "today_iso": today.isoformat(),
            },
        )

    if view == "month":
        if month:
            year, mon = (int(x) for x in month.split("-"))
        else:
            year, mon = today.year, today.month
        ndays = _calendar.monthrange(year, mon)[1]
        days = [date(year, mon, d) for d in range(1, ndays + 1)]
        counts = _day_counts(session, days)
        day_dicts = [
            {
                "date_iso": d.isoformat(),
                "label": str(d.day),
                "item_count": counts.get(d.isoformat(), 0),
                "is_today": d == today,
                "is_selected": d == for_date,
            }
            for d in days
        ]
        prev_month = date(year, mon, 1) - timedelta(days=1)
        next_month = date(year, mon, ndays) + timedelta(days=1)
        return render(
            request,
            "produccion_calendario.html",
            {
                "view": "month",
                "year": year,
                "month": mon,
                "days": day_dicts,
                "prev_month_iso": prev_month.strftime("%Y-%m"),
                "next_month_iso": next_month.strftime("%Y-%m"),
                "today_iso": today.isoformat(),
            },
        )

    # day view (default)
    plan = plan_production(session, for_date=for_date, manual_forecast=overrides or None)
    return render(request, "produccion.html", {
        "plan": plan,
        "for_date": plan.for_date.isoformat() if plan.for_date else "",
        "view": "day",
        "source_labels": FORECAST_SOURCE_LABELS,
        "source_help": FORECAST_SOURCE_HELP,
        "overrides": overrides,
    })


@router.post("/override")
def produccion_override(
    request: Request,
    for_date: date = Form(...),
    product_id: int = Form(...),
    qty: float = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Per-day manual qty override — redirects back to day view with the
    override encoded as ov_{product_id} query param (what-if re-plan)."""
    from app.rms.rate_limit import is_write_rate_limited
    if is_write_rate_limited(session, request, max_per_minute=10):
        raise HTTPException(
            status_code=429,
            detail="Demasiadas acciones en 1 minuto. Esperá un momento.",
        )
    if qty < 0:
        raise HTTPException(status_code=400, detail="La cantidad no puede ser negativa")
    if session.get(Product, product_id) is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    from app.auth import current_user_id
    from app.rms.audit import record as audit_record
    audit_record(
        session,
        user_id=current_user_id(request) or "operator",
        action="write.produccion.override",
        request=request,
        detail={"product_id": product_id, "for_date": for_date.isoformat(), "qty": qty},
    )
    session.commit()
    return RedirectResponse(
        url=f"/produccion?for_date={for_date.isoformat()}&ov_{product_id}={qty}",
        status_code=303,
    )


__all__ = ["router"]
