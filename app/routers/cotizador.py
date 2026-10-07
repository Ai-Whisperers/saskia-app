"""app/routers/cotizador.py — Fase 3: cotizador de catering.

GET  /cotizador           → form: productos + cantidades + descuento
POST /cotizador           → calcula y muestra la cotización (preview)
POST /cotizador/pdf       → PDF de la cotización (pdf_reportlab)

Read-only: nunca escribe ventas ni stock. El operador ajusta
cantidades/descuento hasta que el margen cierra.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_login_or_disabled as require_login
from app.rms.cotizador import build_quote
from app.rms.csrf import verify_form_csrf
from app.rms.dependencies import get_session
from app.services.template_render import render

router = APIRouter(prefix="/cotizador", dependencies=[Depends(require_login)])

_DESCUENTOS = [0, 5, 10, 15, 20]


def _catalog(session: Session) -> list[dict[str, object]]:
    from app.rms.models_legacy import Product

    rows = session.scalars(
        select(Product).where(Product.is_available.is_(True)).order_by(Product.name)
    ).all()
    return [{"id": p.id, "name": p.name, "price_gs": p.sale_price_gs} for p in rows]


def _requested_from_form(form: object) -> list[tuple[int, int]]:
    """campos qty_<product_id> → [(product_id, qty)] con qty>0."""
    out: list[tuple[int, int]] = []
    for key, val in form.multi_items():  # type: ignore[attr-defined]
        if not key.startswith("qty_"):
            continue
        try:
            pid = int(key[4:])
            qty = int(str(val or "0").replace(".", "").replace(",", "").strip() or "0")
        except ValueError:
            continue
        if qty > 0:
            out.append((pid, qty))
    return out


@router.get("", response_class=HTMLResponse)
def form_page(
    request: Request, session: Session = Depends(get_session)
) -> HTMLResponse:
    return render(
        request,
        "cotizador.html",
        {"catalog": _catalog(session), "quote": None, "descuentos": _DESCUENTOS},
    )


@router.post("", response_class=HTMLResponse)
async def quote_page(
    request: Request, session: Session = Depends(get_session)
) -> HTMLResponse:
    await verify_form_csrf(request)
    form = await request.form()
    requested = _requested_from_form(form)
    quote = build_quote(session, requested)
    try:
        descuento = float(str(form.get("descuento") or 0))
    except ValueError:
        descuento = 0.0
    descuento = min(max(descuento, 0.0), 50.0)
    return render(
        request,
        "cotizador.html",
        {
            "catalog": _catalog(session),
            "quote": quote,
            "descuento": descuento,
            "descuentos": _DESCUENTOS,
            "total_con_descuento": quote.apply_discount_pct(descuento),
        },
    )


@router.post("/pdf")
async def quote_pdf(
    request: Request, session: Session = Depends(get_session)
) -> RedirectResponse:
    await verify_form_csrf(request)
    form = await request.form()
    requested = _requested_from_form(form)
    quote = build_quote(session, requested)
    if not quote.items:
        return RedirectResponse("/cotizador?flash=empty", status_code=303)
    from io import BytesIO

    from fastapi.responses import Response

    from app.services.pdf_reportlab import import_reportlab

    rl = import_reportlab()
    A4 = rl["A4"]
    ParagraphStyle = rl["ParagraphStyle"]
    getSampleStyleSheet = rl["getSampleStyleSheet"]
    cm = rl["cm"]
    Paragraph = rl["Paragraph"]
    SimpleDocTemplate = rl["SimpleDocTemplate"]
    Spacer = rl["Spacer"]
    Table = rl["Table"]
    TableStyle = rl["TableStyle"]

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("title", parent=styles["Heading1"], fontSize=14, spaceAfter=12)
    elements: list = [Paragraph("Cotización", title_style), Spacer(1, 0.4 * cm)]
    data: list[list[str]] = [["Producto", "Cantidad", "Precio carta", "Costo"]]
    for it in quote.items:
        cost = f"Gs {it.line_cost_gs:,.0f}" if it.line_cost_gs is not None else "s/costear"
        data.append([
            it.product_name,
            f"{it.qty} × {it.portion_label}",
            f"Gs {it.line_menu_gs:,.0f}",
            cost,
        ])
    data.append(["TOTAL", "", f"Gs {quote.total_menu_gs:,.0f}", ""])
    table = Table(data, colWidths=[6 * cm, 4 * cm, 3.5 * cm, 3.5 * cm])
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, rl["colors"].grey),
        ("BACKGROUND", (0, 0), (-1, 0), rl["colors"].lightgrey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
    ]))
    elements.append(table)
    doc.build(elements)
    return Response(
        content=buf.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="cotizacion.pdf"'},
    )
