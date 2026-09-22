"""app/routers/reportes.py — /reportes (IVA reports, libro de ventas, daily summary).

Built on app/rms/accounting.py which has monthly_iva_breakdown + libro_ventas
+ daily_summary.
"""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import require_login_or_disabled as require_login
from app.rms.accounting import (
    average_order_value,
    cross_period_comparison,
    daily_summary,
    libro_ventas,
    monthly_iva_breakdown,
    sales_by_payment_method,
    top_products_report,
)
from app.rms.charts import fmt_short_date, line_chart
from app.rms.dependencies import get_session
from app.rms.models import Ingredient, IngredientPriceEvent, Sale
from app.rms.price_history import batch_price_stats, price_history, price_stats
from app.rms.sales_intel import customer_retention, sales_by_hour
from app.services.template_render import render

router = APIRouter(prefix="/reportes", dependencies=[Depends(require_login)])

_ALLOWED_DAYS = (7, 30, 90, 365)

_SOURCE_LABELS = {
    "restock": "Reposición",
    "manual": "Manual",
    "excel_import": "Importación Excel",
}


# ─── Helpers ────────────────────────────────────────────────────────────────


def _parse_date(val: str | None) -> datetime | None:
    if not val:
        return None
    try:
        return datetime.fromisoformat(val)
    except ValueError:
        return None


def _today_str() -> str:
    return datetime.utcnow().date().isoformat()


# ─── Index ─────────────────────────────────────────────────────────────────


@router.get("", response_class=HTMLResponse)
def reportes_index(request: Request) -> HTMLResponse:
    """Reports hub with links to all reports and help text."""
    reports = [
        {
            "id": "iva",
            "name": "Libro IVA",
            "desc": "Desglose de IVA 10% por mes con acumulado del año.",
            "help": "Muestra las ventas brutas, base imponible y IVA 10% mes por mes. "
                     "El acumulado YTD es la suma de todos los meses del año hasta la fecha.",
            "icon": "#icon-report",
            "url": "/reportes/iva",
        },
        {
            "id": "libro_ventas",
            "name": "Libro de Ventas",
            "desc": "Ventas cronológicas con IVA para SET (Paraguay).",
            "help": "Libro registro de ventas conforme al formato requerido por SET. "
                     "Incluye exporte en formato PDF libro/book para presentación fiscal.",
            "icon": "#icon-report",
            "url": "/reportes/libro-ventas",
        },
        {
            "id": "diario",
            "name": "Resumen diario",
            "desc": "Ingresos, IVA, COGS, gastos y margen del día.",
            "help": "Resumen del día con ventas netas, IVA acumulado, costo de producción (COGS), "
                     "gastos operativos y margen bruto.",
            "icon": "#icon-report",
            "url": "/reportes/diario",
        },
        {
            "id": "comparacion",
            "name": "Comparación de períodos",
            "desc": "Este mes vs mes anterior.",
            "help": "Compara ventas, cantidad de operaciones y margen entre dos períodos. "
                     "Útil para ver evolución mes a mes.",
            "icon": "#icon-report",
            "url": "/reportes/comparacion",
        },
        {
            "id": "top_productos",
            "name": "Top productos",
            "desc": "Productos que más ingresaron (por revenue).",
            "help": "Ranking de productos por revenue en el período seleccionado. "
                     "Por defecto últimos 30 días.",
            "icon": "#icon-report",
            "url": "/reportes/top-productos",
        },
        {
            "id": "retencion",
            "name": "Retención de clientes",
            "desc": "Clientes nuevos vs recurrentes.",
            "help": "Muestra cuántos clientes впервые appeared en el período (nuevos) "
                     "y cuántos ya habían comprado antes (recurrentes).",
            "icon": "#icon-report",
            "url": "/reportes/retencion",
        },
        {
            "id": "valor_pedido",
            "name": "Valor promedio del pedido",
            "desc": "Average order value (AOV) del período.",
            "help": "Revenue total dividido por cantidad de ventas. "
                     "Indicador clave para entender el ticket promedio.",
            "icon": "#icon-report",
            "url": "/reportes/valor-pedido",
        },
        {
            "id": "ventas_hora",
            "name": "Ventas por hora",
            "desc": "Picos de ventas por hora del día.",
            "help": "Cantidad de ventas por cada hora (0–23). "
                     "Útil para planificar personal y producción.",
            "icon": "#icon-report",
            "url": "/reportes/ventas-hora",
        },
        {
            "id": "metodos_pago",
            "name": "Ventas por método de pago",
            "desc": "Desglose por forma de pago.",
            "help": "Cantidad de ventas y total facturado por cada método de pago "
                     "(EFECTIVO, TARJETA, etc.).",
            "icon": "#icon-report",
            "url": "/reportes/metodos-pago",
        },
        {
            "id": "precios",
            "name": "Precios",
            "desc": "Histórico de precios de ingredientes.",
            "help": "Precio de cada ingrediente en el tiempo. "
                     "Hacé clic en un ingrediente para ver el gráfico de 90 días.",
            "icon": "#icon-report",
            "url": "/reportes/precios",
        },
    ]
    return render(request, "reportes.html", {"reports": reports})


# ─── IVA ───────────────────────────────────────────────────────────────────


@router.get("/iva", response_class=HTMLResponse)
def reportes_iva(
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Monthly IVA breakdown (last 12 months) with year-to-date cumulative view."""
    rows = monthly_iva_breakdown(session)
    # YTD totals
    current_year = datetime.utcnow().year
    ytd_rows = [r for r in rows if r.year == current_year]
    ytd = {
        "n_sales": sum(r.n_sales for r in ytd_rows),
        "total_gross_gs": sum(r.total_gross_gs for r in ytd_rows),
        "total_base_gs": sum(r.total_base_gs for r in ytd_rows),
        "total_iva_gs": sum(r.total_iva_gs for r in ytd_rows),
    }
    return render(request, "reportes_iva.html", {"rows": rows, "ytd": ytd})


# ─── Libro Ventas ──────────────────────────────────────────────────────────


@router.get("/libro-ventas", response_class=HTMLResponse)
def reportes_libro_ventas(
    request: Request,
    start: str | None = Query(None),
    end: str | None = Query(None),
    preset: str | None = Query(None, description="today|week|month|last_month"),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Libro de Ventas (chronological) within a date range.

    Supports date presets: ?preset=today, ?preset=week, ?preset=month, ?preset=last_month
    """
    today = datetime.utcnow().date()
    if preset == "today":
        start_date = datetime.combine(today, datetime.min.time()).replace(tzinfo=timezone.utc)
        end_date = datetime.combine(today, datetime.max.time()).replace(tzinfo=timezone.utc)
    elif preset == "week":
        start_date = datetime.combine(today - timedelta(days=today.weekday()), datetime.min.time()).replace(tzinfo=timezone.utc)
        end_date = datetime.combine(today, datetime.max.time()).replace(tzinfo=timezone.utc)
    elif preset == "month":
        start_date = datetime.combine(today.replace(day=1), datetime.min.time()).replace(tzinfo=timezone.utc)
        end_date = datetime.combine(today, datetime.max.time()).replace(tzinfo=timezone.utc)
    elif preset == "last_month":
        first_this_month = today.replace(day=1)
        last_month_end = first_this_month - timedelta(days=1)
        start_date = datetime.combine(last_month_end.replace(day=1), datetime.min.time()).replace(tzinfo=timezone.utc)
        end_date = datetime.combine(last_month_end, datetime.max.time()).replace(tzinfo=timezone.utc)
    elif start:
        start_date = datetime.fromisoformat(start)
        end_date = datetime.fromisoformat(end) if end else datetime.now(timezone.utc)
    else:
        start_date = datetime.now(timezone.utc) - timedelta(days=30)
        end_date = datetime.now(timezone.utc)

    rows = libro_ventas(session, start_date=start_date, end_date=end_date)
    return render(request, "reportes_libro_ventas.html", {
        "rows": rows,
        "start_date": start_date.date().isoformat(),
        "end_date": end_date.date().isoformat(),
        "preset": preset or "",
    })


@router.get("/libro-ventas/set-pdf")
def libro_ventas_set_pdf(
    request: Request,
    start: str | None = Query(None),
    end: str | None = Query(None),
    session: Session = Depends(get_session),
) -> Response:
    """SET-compliant PDF export for Paraguay's Libro de Ventas.

    Format: A4 book/ledger with chronological entries, totals per page,
    and a summary footer. This is the format required for tax filing.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    if start:
        start_date = datetime.fromisoformat(start)
    else:
        start_date = datetime.now(timezone.utc) - timedelta(days=30)
    if end:
        end_date = datetime.fromisoformat(end)
    else:
        end_date = datetime.now(timezone.utc)

    rows = libro_ventas(session, start_date=start_date, end_date=end_date)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("title", parent=styles["Heading1"], fontSize=14, spaceAfter=12)
    bold_style = ParagraphStyle("bold", parent=styles["Normal"], fontName="Helvetica-Bold")

    elements = []

    # Header
    elements.append(Paragraph("LIBRO DE VENTAS — SET", title_style))
    elements.append(Paragraph(f"Período: {start_date.date().isoformat()} a {end_date.date().isoformat()}", styles["Normal"]))
    elements.append(Spacer(1, 0.5 * cm))

    # Totals
    total_gross = sum(r.total_gross_gs for r in rows)
    total_base = sum(r.base_gs for r in rows)
    total_iva = sum(r.iva_gs for r in rows)
    elements.append(Paragraph(f"Total ventas: Gs. {total_gross:,.0f}", styles["Normal"]))
    elements.append(Paragraph(f"Base imponible: Gs. {total_base:,.0f}", styles["Normal"]))
    elements.append(Paragraph(f"IVA 10%: Gs. {total_iva:,.0f}", styles["Normal"]))
    elements.append(Spacer(1, 0.5 * cm))

    # Table
    table_data = [
        ["Fecha", "Cliente", "Producto", "Cant.", "Gravado", "IVA", "Total"],
    ]
    for r in rows:
        table_data.append([
            r.sold_at.strftime("%d/%m/%Y") if r.sold_at else "",
            (r.customer_name or "—")[:30],
            r.product_name[:30],
            f"{r.qty:.2f}",
            f"{r.base_gs:,}",
            f"{r.iva_gs:,}",
            f"{r.total_gross_gs:,}",
        ])

    t = Table(table_data, colWidths=[2.5 * cm, 4 * cm, 4 * cm, 1.5 * cm, 3 * cm, 2 * cm, 3 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.Color(0.95, 0.95, 0.95)]),
        ("ALIGN", (3, 0), (-1, -1), "RIGHT"),
    ]))
    elements.append(t)
    doc.build(elements)

    buf.seek(0)
    return Response(
        content=buf.read(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=libro_ventas_{start_date.date()}_{end_date.date()}.pdf"},
    )


# ─── Diario ────────────────────────────────────────────────────────────────


@router.get("/diario", response_class=HTMLResponse)
def reportes_diario(
    request: Request,
    for_date: str | None = Query(None),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Daily summary (revenue, IVA, COGS, expenses, margin)."""
    if for_date:
        d = datetime.fromisoformat(for_date)
    else:
        d = datetime.now(timezone.utc)
    summary = daily_summary(session, day=d)
    return render(request, "reportes_diario.html", {
        "summary": summary,
        "for_date": d.date().isoformat(),
    })


# ─── Comparación períodos ──────────────────────────────────────────────────


@router.get("/comparacion", response_class=HTMLResponse)
def reportes_comparacion(
    request: Request,
    start1: str | None = Query(None),
    end1: str | None = Query(None),
    start2: str | None = Query(None),
    end2: str | None = Query(None),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Cross-period comparison (this month vs last month by default)."""
    today = datetime.utcnow()
    today_date = today.date()
    first_this_month = today_date.replace(day=1)
    last_month_end = first_this_month - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)

    p1_start = datetime.fromisoformat(start1) if start1 else datetime.combine(first_this_month, datetime.min.time()).replace(tzinfo=timezone.utc)
    p1_end = datetime.fromisoformat(end1) if end1 else datetime.combine(today_date, datetime.max.time()).replace(tzinfo=timezone.utc)
    p2_start = datetime.fromisoformat(start2) if start2 else datetime.combine(last_month_start, datetime.min.time()).replace(tzinfo=timezone.utc)
    p2_end = datetime.fromisoformat(end2) if end2 else datetime.combine(last_month_end, datetime.max.time()).replace(tzinfo=timezone.utc)

    comparison = cross_period_comparison(session, p1_start, p1_end, p2_start, p2_end)
    return render(request, "reportes_comparacion.html", {
        "comparison": comparison,
        "start1": p1_start.date().isoformat(),
        "end1": p1_end.date().isoformat(),
        "start2": p2_start.date().isoformat(),
        "end2": p2_end.date().isoformat(),
    })


# ─── Top productos ─────────────────────────────────────────────────────────


@router.get("/top-productos", response_class=HTMLResponse)
def reportes_top_productos(
    request: Request,
    start: str | None = Query(None),
    end: str | None = Query(None),
    limit: int = Query(20, ge=5, le=100),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Top products by revenue."""
    start_date = datetime.fromisoformat(start) if start else None
    end_date = datetime.fromisoformat(end) if end else None
    rows = top_products_report(session, start_date=start_date, end_date=end_date, limit=limit)
    return render(request, "reportes_top_productos.html", {
        "rows": rows,
        "start_date": start_date.date().isoformat() if start_date else "",
        "end_date": end_date.date().isoformat() if end_date else "",
        "limit": limit,
    })


# ─── Retención ─────────────────────────────────────────────────────────────


@router.get("/retencion", response_class=HTMLResponse)
def reportes_retencion(
    request: Request,
    start: str | None = Query(None),
    end: str | None = Query(None),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Customer retention report (new vs returning)."""
    start_date = datetime.fromisoformat(start) if start else None
    end_date = datetime.fromisoformat(end) if end else None
    stats = customer_retention(session, start_date=start_date, end_date=end_date)
    return render(request, "reportes_retencion.html", {
        "stats": stats,
        "start_date": start_date.date().isoformat() if start_date else "",
        "end_date": end_date.date().isoformat() if end_date else "",
    })


# ─── Valor promedio ────────────────────────────────────────────────────────


@router.get("/valor-pedido", response_class=HTMLResponse)
def reportes_valor_pedido(
    request: Request,
    start: str | None = Query(None),
    end: str | None = Query(None),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Average order value."""
    start_date = datetime.fromisoformat(start) if start else None
    end_date = datetime.fromisoformat(end) if end else None
    aov = average_order_value(session, start_date=start_date, end_date=end_date)
    return render(request, "reportes_valor_pedido.html", {
        "aov": aov,
        "start_date": start_date.date().isoformat() if start_date else "",
        "end_date": end_date.date().isoformat() if end_date else "",
    })


# ─── Ventas por hora ───────────────────────────────────────────────────────


@router.get("/ventas-hora", response_class=HTMLResponse)
def reportes_ventas_hora(
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Sales by hour of day."""
    by_hour = sales_by_hour(session)
    peak_hour = max(by_hour.items(), key=lambda kv: kv[1])[0] if any(v > 0 for v in by_hour.values()) else -1
    return render(request, "reportes_ventas_hora.html", {
        "by_hour": by_hour,
        "peak_hour": peak_hour,
    })


# ─── Métodos de pago ───────────────────────────────────────────────────────


@router.get("/metodos-pago", response_class=HTMLResponse)
def reportes_metodos_pago(
    request: Request,
    start: str | None = Query(None),
    end: str | None = Query(None),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Sales breakdown by payment method."""
    start_date = datetime.fromisoformat(start) if start else None
    end_date = datetime.fromisoformat(end) if end else None
    breakdown = sales_by_payment_method(session, start_date=start_date, end_date=end_date)
    total_gs = sum(v["total_gs"] for v in breakdown.values())
    return render(request, "reportes_metodos_pago.html", {
        "breakdown": breakdown,
        "total_gs": total_gs,
        "start_date": start_date.date().isoformat() if start_date else "",
        "end_date": end_date.date().isoformat() if end_date else "",
    })


# ─── Precios (existing) ────────────────────────────────────────────────────


def _precio_rows(session: Session, days: int) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    ingredient_ids = [
        row[0] for row in session.execute(
            select(IngredientPriceEvent.ingredient_id.distinct())
            .where(IngredientPriceEvent.recorded_at >= cutoff)
        ).all()
    ]
    stats_map = batch_price_stats(session, ingredient_ids, days=days)
    ingredients = {
        ing.id: ing for ing in
        session.scalars(select(Ingredient).where(Ingredient.id.in_(ingredient_ids))).all()
    }
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


# ─── PDF exports ───────────────────────────────────────────────────────────


def _pdf_response(pdf_bytes: bytes, filename: str) -> Response:
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/diario/pdf")
def reportes_diario_pdf(
    request: Request,
    for_date: str | None = Query(None),
    session: Session = Depends(get_session),
) -> Response:
    """PDF export of the daily summary."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    if for_date:
        d = datetime.fromisoformat(for_date)
    else:
        d = datetime.now(timezone.utc)

    summary = daily_summary(session, day=d)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm)
    styles = getSampleStyleSheet()
    title = ParagraphStyle("title", parent=styles["Heading1"], fontSize=16, spaceAfter=12)

    elements = []
    elements.append(Paragraph(f"Resumen Diario — {d.date().isoformat()}", title))
    elements.append(Spacer(1, 0.5 * cm))

    data = [
        ["Métrica", "Valor"],
        ["Ingresos (Gs.)", f"{summary.revenue_gross_gs:,}"],
        ["IVA 10% (Gs.)", f"{summary.iva_gs:,}"],
        ["COGS (Gs.)", f"{summary.cogs_gs:,}"],
        ["Gastos (Gs.)", f"{summary.expenses_gs:,}"],
        ["Margen bruto (Gs.)", f"{summary.margin_gs:,}"],
        ["Nº ventas", str(summary.n_sales)],
    ]
    if summary.revenue_gross_gs > 0:
        margin_pct = (summary.margin_gs * 100.0) / summary.revenue_gross_gs
        data.append(["Margen %", f"{margin_pct:.1f}%"])

    t = Table(data, colWidths=[6 * cm, 5 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("ALIGN", (1, 1), (1, -1), "RIGHT"),
    ]))
    elements.append(t)
    doc.build(elements)
    buf.seek(0)
    return _pdf_response(buf.read(), f"resumen_diario_{d.date()}.pdf")


@router.get("/iva/pdf")
def reportes_iva_pdf(
    request: Request,
    session: Session = Depends(get_session),
) -> Response:
    """PDF export of the IVA report."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    rows = monthly_iva_breakdown(session)
    current_year = datetime.utcnow().year
    ytd_rows = [r for r in rows if r.year == current_year]
    ytd_gross = sum(r.total_gross_gs for r in ytd_rows)
    ytd_iva = sum(r.total_iva_gs for r in ytd_rows)
    ytd_base = sum(r.total_base_gs for r in ytd_rows)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm)
    styles = getSampleStyleSheet()
    title = ParagraphStyle("title", parent=styles["Heading1"], fontSize=14, spaceAfter=12)

    elements = []
    elements.append(Paragraph("Libro IVA — últimos 12 meses", title))
    elements.append(Spacer(1, 0.3 * cm))

    # YTD summary
    ytd_data = [
        ["Acumulado del año (YTD)", ""],
        ["Ventas", str(sum(r.n_sales for r in ytd_rows))],
        ["Base imponible (Gs.)", f"{ytd_base:,}"],
        ["IVA 10% (Gs.)", f"{ytd_iva:,}"],
        ["Total (Gs.)", f"{ytd_gross:,}"],
    ]
    yt = Table(ytd_data, colWidths=[6 * cm, 4 * cm])
    yt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("ALIGN", (1, 1), (1, -1), "RIGHT"),
    ]))
    elements.append(yt)
    elements.append(Spacer(1, 0.3 * cm))

    # Monthly table
    table_data = [["Mes", "Ventas", "Gravado", "IVA 10%", "Total"]]
    for r in rows:
        table_data.append([
            f"{r.year}-{r.month:02d}",
            str(r.n_sales),
            f"{r.total_base_gs:,}",
            f"{r.total_iva_gs:,}",
            f"{r.total_gross_gs:,}",
        ])
    t = Table(table_data, colWidths=[3 * cm, 2 * cm, 4 * cm, 3 * cm, 4 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
    ]))
    elements.append(t)
    doc.build(elements)
    buf.seek(0)
    return _pdf_response(buf.read(), f"libro_iva_{current_year}.pdf")


__all__ = ["router"]
