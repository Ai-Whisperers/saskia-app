"""app/routers/reportes.py — /reportes (IVA reports, libro de ventas, daily summary).

Built on app/rms/accounting.py which has monthly_iva_breakdown + libro_ventas
+ daily_summary.
"""
from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import require_login_or_disabled as require_login
from app.rms.accounting import daily_summary, libro_ventas, monthly_iva_breakdown
from app.rms.charts import fmt_short_date, line_chart
from app.rms.dependencies import get_session
from app.rms.models import Ingredient, IngredientPriceEvent
from app.rms.price_history import batch_price_stats, price_history, price_stats
from app.services.template_render import render

router = APIRouter(prefix="/reportes", dependencies=[Depends(require_login)])

_ALLOWED_DAYS = (7, 30, 90, 365)

_SOURCE_LABELS = {
    "restock": "Reposición",
    "manual": "Manual",
    "excel_import": "Importación Excel",
}


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


def _precio_rows(session: Session, days: int) -> list[dict]:
    """One summary row per ingredient that has events in the window."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # Fetch all ingredients with events in the window — single query
    ingredient_ids = [
        row[0] for row in session.execute(
            select(IngredientPriceEvent.ingredient_id.distinct())
            .where(IngredientPriceEvent.recorded_at >= cutoff)
        ).all()
    ]

    # Batch-fetch all price stats — single query (was N queries)
    stats_map = batch_price_stats(session, ingredient_ids, days=days)

    # Fetch ingredient objects for name/unit lookup
    ingredients = {
        ing.id: ing for ing in
        session.scalars(select(Ingredient).where(Ingredient.id.in_(ingredient_ids))).all()
    }

    # Last event timestamp per ingredient — single query (was N queries)
    last_ts_map = dict(
        session.execute(
            select(
                IngredientPriceEvent.ingredient_id,
                func.max(IngredientPriceEvent.recorded_at),
            )
            .where(
                IngredientPriceEvent.ingredient_id.in_(ingredient_ids),
                IngredientPriceEvent.recorded_at >= cutoff,
            )
            .group_by(IngredientPriceEvent.ingredient_id)
        ).all()
    )

    rows = []
    for iid in ingredient_ids:
        stats = stats_map.get(iid, {})
        if stats.get("count", 0) == 0:
            continue
        ing = ingredients.get(iid)
        rows.append({
            "ingredient_id": iid,
            "name": ing.name if ing else f"#{iid}",
            "unit": ing.unit if ing else "",
            **stats,
            "last_event_at": last_ts_map.get(iid),
        })
    return rows


@router.get("/precios", response_class=HTMLResponse)
def reportes_precios(
    request: Request,
    ingredient_id: int | None = Query(None),
    days: int = Query(90),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Price-history report: list of all priced ingredients or one detail."""
    if days not in _ALLOWED_DAYS:
        raise HTTPException(status_code=422, detail=f"días inválido: usá uno de {list(_ALLOWED_DAYS)}")

    if ingredient_id is None:
        return render(request, "reportes_precios.html", {
            "rows": _precio_rows(session, days),
            "days": days,
            "detail": None,
            "detail_events": None,
        })

    ing = session.get(Ingredient, ingredient_id)
    if ing is None:
        raise HTTPException(status_code=404, detail="Ingrediente no encontrado")

    history = price_history(session, ingredient_id, days=days)
    chart_svg = line_chart(
        [(fmt_short_date(ts), float(p)) for ts, p in history],
        label=f"Precio de {ing.name} — últimos {days} días (Gs.)",
        y_format="Gs. {:,.0f}",
    )
    events = [
        {
            "date": ts,
            "price_gs": p,
            "source": _SOURCE_LABELS.get(src, src),
        }
        for (ts, p), src in zip(
            history,
            session.scalars(
                select(IngredientPriceEvent.source)
                .where(IngredientPriceEvent.ingredient_id == ingredient_id)
                .where(IngredientPriceEvent.recorded_at >= datetime.now(timezone.utc) - timedelta(days=days))
                .order_by(IngredientPriceEvent.recorded_at.asc())
            ).all(),
        )
    ]
    return render(request, "reportes_precios.html", {
        "rows": None,
        "days": days,
        "detail": {
            "ingredient": ing,
            "stats": price_stats(session, ingredient_id, days=days),
            "chart_svg": chart_svg,
        },
        "detail_events": events,
    })


@router.get("/precios/csv")
def reportes_precios_csv(
    days: int = Query(90),
    session: Session = Depends(get_session),
) -> Response:
    """CSV export of the price summary (same shape as the list view)."""
    if days not in _ALLOWED_DAYS:
        raise HTTPException(status_code=422, detail=f"días inválido: usá uno de {list(_ALLOWED_DAYS)}")

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["ingredient_id", "name", "current", "min", "max", "avg", "last_event_at"])
    for row in _precio_rows(session, days):
        writer.writerow([
            row["ingredient_id"],
            row["name"],
            row["current"],
            row["min"],
            row["max"],
            f"{row['avg']:.0f}" if row["avg"] is not None else "",
            row["last_event_at"].strftime("%Y-%m-%d %H:%M") if row["last_event_at"] else "",
        ])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="precios.csv"'},
    )


__all__ = ["router"]
