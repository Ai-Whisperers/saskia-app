"""app/routers/produccion/forecast.py - Forecast API + tomorrow preview.

Sazon-Improvement v2 (2026-10-06) Phase E step 4: extracted from
app/routers/produccion/_full.py lines 1154-1301. Behavior unchanged.

Routes (2 GETs):
  GET /produccion/api/forecast  - JSON forecast for a date (consumed by JS)
  GET /produccion/manana        - tomorrow's plan preview page
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import Depends, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rms.dependencies import get_session
from app.rms.models import (
    Ingredient,
    Product,
    ProductionPlanOverride,
    Recipe,
    RecipeLine,
)
from app.rms.production import get_weekly_template, plan_production
from app.rms.production_demand import get_demand
from app.routers.produccion._helpers import (
    _asuncion_today,
    _fermentation_reminder,
    _week_monday,
)
from app.routers.produccion._router import router
from app.services.template_render import render


@router.get("/api/forecast")
def produccion_api_forecast(
    for_date: str = Query(...),
    product_id: int | None = Query(None, ge=1),
    session: Session = Depends(get_session),
) -> JSONResponse:
    """Return production-plan rows for a date (filtered to one product if given).

    Shape:
            {"for_date": "YYYY-MM-DD",
             "rows": [{"product_id": int, "product_name": str,
                       "qty_to_produce": float, "forecast_source": str,
                       "confidence_pct": int}, ...]}
    """
    try:
        parsed = date.fromisoformat(for_date)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"for_date inválido: {for_date!r}") from None

    plan = plan_production(session, for_date=parsed)

    rows = [
        {
            "product_id": r.product_id,
            "product_name": r.product_name,
            "qty_to_produce": float(r.qty_to_produce),
            "forecast_source": r.forecast_source,
            "confidence_pct": r.confidence_pct,
        }
        for r in plan.rows
    ]

    if product_id is not None:
        rows = [r for r in rows if r["product_id"] == product_id]

    return JSONResponse({"for_date": parsed.isoformat(), "rows": rows})


# --- P1-B2 forecast enchufado: tomorrow-focused view ---
@router.get("/manana", response_class=HTMLResponse)
def produccion_manana(
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Tomorrow's production plan with confidence scores + seasonal events.

    The roadmap asks for: "mañana vas a necesitar ~120 chipitas (confianza 78%)"
    Each row shows:
      - product name + qty to produce
      - confidence % (color: <50 red, 50-75 amber, >=75 green)
      - source: rolling_14d_avg / override / template / manual
      - seasonal event note (if a calendar event applies tomorrow)

    Operators can override the qty by typing a number; the form posts to
    /produccion/override as usual.
    """
    from app.rms.config import ASUNCION_TZ
    from app.rms.seasonal import calendar_for_year

    today = datetime.now(ASUNCION_TZ).date()
    tomorrow = today + timedelta(days=1)
    # B2 (2026-10-01): /produccion/manana now uses the DOW-aware
    # forecast with a 12-week lookback. Only this surface opts in;
    # week/month views keep the legacy flat 14-day avg (unchanged).
    plan = plan_production(
        session,
        for_date=tomorrow,
        days_history=84,
        use_dow_forecast=True,
    )

    # Pull seasonal events for tomorrow's date (calendar uses SEASONAL_CALENDAR_2026)
    # The calendar dict has 'start'/'end' fields (date ranges), not 'date'.
    tomorrow_iso = tomorrow.isoformat()
    events = [
        ev
        for ev in calendar_for_year(tomorrow.year)
        if ev.get("start", "") <= tomorrow_iso <= ev.get("end", "")
    ]
    seasonal_multiplier = None  # already baked into plan.rows[*].qty
    seasonal_note = None
    if events:
        # Take the first event as the headline; plan.notes carries the multiplier
        head = events[0]
        seasonal_note = f"{head.get('name', 'Evento estacional')} (×{head.get('multiplier', 1.0)})"

    # Sort: highest confidence first, lowest qty last
    rows = sorted(plan.rows, key=lambda r: (-r.confidence_pct, r.product_name))

    # Total estimated production in Gs (sum of qty * product.sale_price_gs)
    products_by_id = {p.id: p for p in session.execute(select(Product)).scalars()}
    estimated_revenue_gs = 0
    for row in rows:
        p = products_by_id.get(row.product_id)
        if p is not None and p.sale_price_gs:
            estimated_revenue_gs += int(row.qty_to_produce * p.sale_price_gs)

    # Override form pre-fill (read existing overrides for tomorrow)
    from app.rms.production import get_overrides_for_date

    overrides_tomorrow = get_overrides_for_date(session, tomorrow)

    # PRO-PED (2026-09-30): pedidos confirmados con entrega/retiro mañana —
    # el planificador ve los encargos reales en la misma pantalla donde
    # planifica (antes solo vivían en Pedidos y en el card de Inicio).
    #
    # 2026-10-07: enrich with line items (what each client ordered) and
    # aggregated qty per product so the "Qué producir" table can show
    # a "Pedidos" column = how many of each product are already committed.
    from app.rms.models import Pedido
    from app.routers.pedidos import _pedido_total_gs

    pedidos_q = (
        session.execute(
            select(Pedido)
            .where(
                Pedido.promised_date == tomorrow,
                Pedido.status.in_(["pending", "confirmed", "ready"]),
            )
            .order_by(Pedido.promised_time.nulls_last(), Pedido.id)
        )
        .scalars()
    )
    pedidos_manana = []
    pedidos_by_product: dict[int, float] = {}  # product_id -> qty committed
    # Cache product names by id so the per-line label is one query
    products_by_id = {
        p.id: p.name
        for p in session.execute(select(Product).where(Product.id > 0)).scalars()
    }
    for p_ in pedidos_q:
        pedido_lines = []
        for ln in p_.lines:
            ln_qty = float(ln.qty or 0)
            pedido_lines.append(
                {
                    "product_id": ln.product_id,
                    "product_name": products_by_id.get(ln.product_id, f"#{ln.product_id}"),
                    "qty": ln_qty,
                    "unit": "und",  # pedidos sell by unit, never by weight
                }
            )
            if ln.product_id is not None:
                pedidos_by_product[ln.product_id] = (
                    pedidos_by_product.get(ln.product_id, 0.0) + ln_qty
                )
        pedidos_manana.append(
            {
                "id": p_.id,
                "customer_name": p_.customer_name,
                "customer_phone": p_.customer_phone,
                "promised_time": p_.promised_time,
                "channel": p_.channel,
                "status": p_.status,
                "total_gs": _pedido_total_gs(p_),
                "lines": pedido_lines,
            }
        )

    return render(
        request,
        "produccion_manana.html",
        {
            "pedidos_manana": pedidos_manana,
            "today": today.isoformat(),
            # PRODUCCION-V3 Phase 6: alias for the manana page-nav to
            # link to /produccion?for_date=<today>.
            "today_iso": today.isoformat(),
            "tomorrow": tomorrow.isoformat(),
            "rows": rows,
            "plan": plan,
            "pedidos_by_product": pedidos_by_product,
            "seasonal_note": seasonal_note,
            "seasonal_multiplier": seasonal_multiplier,
            "estimated_revenue_gs": estimated_revenue_gs,
            "overrides_tomorrow": overrides_tomorrow,
            "low_confidence_count": sum(1 for r in rows if r.confidence_pct < 70),
        },
    )


