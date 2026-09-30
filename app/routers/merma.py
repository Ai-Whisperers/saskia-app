"""app/routers/merma.py — /merma (Waste log).

Built on app/rms/waste.py which has record_waste + list_waste + waste_impact
+ waste_as_pct_of_revenue.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import require_login_or_disabled as require_login
from app.rms.dependencies import get_session
from app.rms.errors import BadRequest, NotFound
from app.rms.models import AuditLog, Ingredient, Recipe, Sale, WasteLog
from app.rms.observability import record_audit
from app.rms.waste import (
    WasteReason,
    list_waste,
    record_recipe_waste,
    record_waste,
    waste_as_pct_of_revenue,
    waste_impact,
)
from app.services.template_render import render

router = APIRouter(prefix="/merma", dependencies=[Depends(require_login)])


@router.get("", response_class=HTMLResponse)
def merma_list(
    request: Request,
    days: int = Query(30, description="Days to look back (7, 30, 90, or custom)"),
    since: str | None = Query(None, description="ISO date start override"),
    until: str | None = Query(None, description="ISO date end override"),
    reason: str | None = Query(None, description="Filter by waste reason"),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """List recent waste + summary with date range filter.

    Presets: 7, 30, 90 days. Custom range via since/until ISO dates.
    Optional reason filter.
    """
    # Resolve date range
    today = datetime.now(timezone.utc)
    if since:
        try:
            start_date = datetime.strptime(since, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            start_date = today - timedelta(days=days)
    else:
        start_date = today - timedelta(days=days)

    if until:
        try:
            end_date = (
                datetime.strptime(until, "%Y-%m-%d")
                .replace(tzinfo=timezone.utc)
                .replace(hour=23, minute=59, second=59)
            )
        except ValueError:
            end_date = today
    else:
        end_date = today

    # Validate reason filter
    reason_filter: WasteReason | None = None
    if reason:
        try:
            reason_filter = WasteReason(reason)
        except ValueError:
            reason_filter = None

    items = list_waste(
        session, start_date=start_date, end_date=end_date, reason=reason_filter, limit=200
    )
    impact = waste_impact(session, start_date=start_date, end_date=end_date)
    # Estimate revenue from sales in same window
    rev_total = (
        session.execute(
            select(func.sum(Sale.qty * Sale.unit_price_gs)).where(
                Sale.sold_at >= start_date, Sale.voided_at.is_(None)
            )
        ).scalar()
        or 0
    )
    # pct is None when there is no revenue in the window, so the template
    # can show the "no hay ventas todavía" copy from MER-03.
    if rev_total > 0:
        pct = waste_as_pct_of_revenue(
            session, start_date=start_date, end_date=end_date, revenue_gs=int(rev_total)
        )
    else:
        pct = None
    # List of ingredients for the form dropdown
    ingredients = list(session.scalars(select(Ingredient).order_by(Ingredient.name)).all())
    # Recipes with a yield_qty for the whole-batch waste form (T6)
    recipes_with_yield = list(
        session.scalars(
            select(Recipe)
            .where(Recipe.yield_qty.isnot(None), Recipe.yield_qty > 0)
            .order_by(Recipe.name)
        ).all()
    )
    # Top merma ingredients: group impact.by_ingredient and sort descending
    top_ingredients = sorted(impact.by_ingredient, key=lambda x: x[2], reverse=True)[:10]

    # PROD-MERMA-2: surface the entrypoint on the /merma eventos table so the
    # operator can distinguish events from the new quick-merma modal
    # (source='production') from entries logged the legacy way (source='manual').
    # Build a map waste_log_id → source by joining AuditLog on target_id.
    waste_ids = [w.id for w in items]
    source_by_waste_id: dict[int, str] = {}
    if waste_ids:
        audit_rows = session.execute(
            select(AuditLog.target_id, AuditLog.detail).where(
                AuditLog.action == "write.merma.create",
                AuditLog.target_type == "merma",
                AuditLog.target_id.in_(waste_ids),
            )
        ).all()
        for target_id, detail in audit_rows:
            src = "manual"
            if isinstance(detail, dict):
                src = str(detail.get("source", "manual") or "manual")
            # Normalize to int for template lookup (waste_ids are ints; the
            # audit row stores target_id as str for UUID compat).
            try:
                key = int(target_id)
            except (TypeError, ValueError):
                key = target_id
            source_by_waste_id[key] = src

    # Build preset query strings
    def preset_url(d: int) -> str:
        sd = (today - timedelta(days=d)).strftime("%Y-%m-%d")
        return f"/merma?days={d}&since={sd}&reason={reason or ''}"

    return render(
        request,
        "merma.html",
        {
            "items": items,
            "impact": impact,
            "pct": pct,
            "reasons": [r.value for r in WasteReason],
            "selected_reason": reason or "",
            "ingredients": ingredients,
            "recipes": recipes_with_yield,
            "top_ingredients": top_ingredients,
                    "source_by_waste_id": source_by_waste_id,  # PROD-MERMA-2: entrypoint tag
                    "days": days,
            "since": start_date.strftime("%Y-%m-%d"),
            "until": end_date.strftime("%Y-%m-%d"),
            "preset_url_7": preset_url(7),
            "preset_url_30": preset_url(30),
            "preset_url_90": preset_url(90),
            # MER-01: unit selector. Per-ingredient stock unit, plus finer units
            # from the same family (kg → allow g, l → allow ml). The default unit
            # is the finer one because operators typically enter small quantities.
            "available_units": ["g", "kg", "ml", "l", "und"],
            "default_unit": "g",
            "total": len(items),
            "page_start": 1,
            "page_end": len(items),
        },
    )


@router.post("/registrar")
def merma_register(
    request: Request,
    ingredient_id: int = Form(...),
    qty: float = Form(...),
    qty_unit: str = Form(""),
    reason: str = Form(...),
    notes: str = Form(""),
    source: str = Form(
        "manual"
    ),  # PROD-MERMA-1: "manual" (default) | "production" (from quick-merma modal)
    session: Session = Depends(get_session),
) -> object:
    """Record a new waste event.

    MER-01: qty_unit lets the operator enter 50 g of harina instead of 0.05 kg.
    The unit is converted to the ingredient's stock unit before stock decrement.
    PROD-MERMA-1: source="production" routes the redirect to /produccion with
    a merma=ok flash; source="manual" keeps the legacy redirect to /merma.
    """
    # Validate reason is in the enum
    try:
        reason_enum = WasteReason(reason)
    except ValueError as exc:
        raise BadRequest(
            "Motivo de merma inválido.",
            context={"original_error": str(exc)},
        ) from exc

    # Rate-limit writes per IP.
    from app.rms.rate_limit import is_write_rate_limited

    with session.bind.connect() as _:
        pass  # touch to ensure session is live
    # We need request inside the function — use a quick manual lookup
    ip = request.headers.get("x-forwarded-for", "")
    if ip:
        ip = ip.split(",")[0].strip()
    # Re-use the rate-limit helper through session_factory
    if is_write_rate_limited(session, request, max_per_minute=10):
        raise HTTPException(
            status_code=429, detail="Demasiadas acciones en 1 minuto. Esperá un momento."
        )

    # PROD-MERMA-2 (Batch E): duplicate-record guard.
    # If the same operator just submitted the same (ingredient, reason, qty)
    # within the last 60 seconds, return the existing event id instead of
    # double-recording. Tolerance on qty: within 5% or 0.01 absolute — covers
    # "qty=0.5" being typed twice without rounding noise.
    dup_window_seconds = 60
    dup_qty_tolerance_abs = 0.01
    dup_qty_tolerance_pct = 0.05
    from datetime import datetime, timedelta, timezone as _tz
    cutoff = datetime.now(_tz.utc) - timedelta(seconds=dup_window_seconds)
    qty_abs = abs(float(qty))
    tol = max(dup_qty_tolerance_abs, qty_abs * dup_qty_tolerance_pct)
    recent = list(
        session.execute(
            select(WasteLog)
            .where(
                WasteLog.ingredient_id == ingredient_id,
                WasteLog.reason == reason,
                WasteLog.recorded_at >= cutoff,
            )
            .order_by(WasteLog.recorded_at.desc())
            .limit(5)
        ).scalars()
    )
    for prev in recent:
        prev_qty = float(prev.qty or 0)
        if abs(prev_qty - qty_abs) <= tol:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Ya registraste este evento hace menos de {dup_window_seconds}s "
                    f"(id=#{prev.id}). Si fue intencional, esperá un momento y volvé a intentar."
                ),
                headers={"X-Saskia-Duplicate-Of": str(prev.id)},
            )

    try:
        log = record_waste(
            session,
            ingredient_id=ingredient_id,
            qty=qty,
            qty_unit=qty_unit or None,
            reason=reason_enum,
            notes=notes or None,
        )
    except ValueError as exc:
        # Unknown ingredient FK etc. — 404, not a 500 crash (found by the
        # e2e negative-path matrix).
        raise NotFound(
            "Recurso no encontrado",
            context={"operation": "record_waste", "original_error": str(exc)},
        ) from exc

    from app.auth import current_user_id

    record_audit(
        request,
        session=session,
        action="write.merma.create",
        target_type="merma",
        target_id=log.id,
        detail={
            "ingredient_id": ingredient_id,
            "qty": qty,
            "reason": reason,
            "source": source,  # PROD-MERMA-1: tag entrypoint for /merma event log
        },
        user_id=str(current_user_id(request) or "operator"),
    )
    session.commit()
    # PROD-MERMA-1: route the redirect based on entrypoint so the operator lands
    # where they came from with a flash banner.
    if source == "production":
        return RedirectResponse(url="/produccion?view=day&merma=ok&lines=1", status_code=303)
    return RedirectResponse(url="/merma", status_code=303)


@router.post("/receta")
def merma_register_recipe(
    request: Request,
    recipe_id: int = Form(...),
    batch_qty: float = Form(...),
    reason: str = Form(...),
    notes: str = Form(""),
    source: str = Form("manual"),  # PROD-MERMA-1: "manual" | "production"
    session: Session = Depends(get_session),
) -> object:
    """Record a whole-batch waste event (Saskia review T6).

    Expands the recipe into per-ingredient WasteLog rows and decrements
    stock proportionally. Sub-recipes recurse via _compute_stock_moves.

    PROD-MERMA-1: source="production" routes the redirect to /produccion with
    a merma=ok flash (the line count equals the recipe's ingredient count).
    """
    try:
        reason_enum = WasteReason(reason)
    except ValueError as exc:
        raise BadRequest(
            "Motivo de merma inválido.",
            context={"original_error": str(exc)},
        ) from exc
    if batch_qty <= 0:
        raise HTTPException(status_code=400, detail="La cantidad de lotes debe ser mayor a 0")

    from app.rms.rate_limit import is_write_rate_limited

    if is_write_rate_limited(session, request, max_per_minute=10):
        raise HTTPException(
            status_code=429,
            detail="Demasiadas acciones en 1 minuto. Esperá un momento.",
        )

    try:
        result = record_recipe_waste(
            session,
            recipe_id=recipe_id,
            batch_qty=batch_qty,
            reason=reason_enum,
            notes=notes or None,
        )
    except ValueError as exc:
        raise BadRequest(
            "Datos inválidos para registrar merma por receta.",
            context={"original_error": str(exc)},
        ) from exc

    from app.auth import current_user_id

    record_audit(
        request,
        session=session,
        action="write.merma.recipe",
        target_type="merma",
        target_id=recipe_id,
        detail={
            "recipe_id": recipe_id,
            "recipe_name": result.recipe_name,
            "batch_qty": batch_qty,
            "cost_gs": result.cost_gs,
            "n_ingredient_logs": len(result.waste_logs),
            "reason": reason,
            "source": source,  # PROD-MERMA-1: tag entrypoint
        },
        user_id=str(current_user_id(request) or "operator"),
    )
    session.commit()
    # PROD-MERMA-1: redirect by entrypoint; recipe expansion yields N ingredient
    # lines so the banner reports the actual count.
    if source == "production":
        n_lines = max(len(result.waste_logs), 1)
        return RedirectResponse(
            url=f"/produccion?view=day&merma=ok&lines={n_lines}",
            status_code=303,
        )
    return RedirectResponse(url="/merma", status_code=303)


@router.get("/api/reasons", response_class=JSONResponse)
def waste_reasons_api() -> JSONResponse:
    """List all waste reasons.

    Used by the combo system on /merma forms for reason selection.
    """
    from app.rms.waste import WasteReason

    payload = [
        {
            "value": reason.value,
            "display": reason.value,
        }
        for reason in WasteReason
    ]

    return JSONResponse({"results": payload, "count": len(payload)})


__all__ = ["router"]
