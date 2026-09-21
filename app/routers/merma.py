"""app/routers/merma.py — /merma (Waste log).

Built on app/rms/waste.py which has record_waste + list_waste + waste_impact
+ waste_as_pct_of_revenue.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import require_login_or_disabled as require_login
from app.rms.dependencies import get_session
from app.rms.models import Ingredient, Recipe
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
def merma_list(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    """List recent waste + summary."""
    items = list_waste(session, limit=50)
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=30)
    impact = waste_impact(session, start_date=start_date, end_date=end_date)
    # Estimate revenue from sales in same window
    from app.rms.models import Sale
    rev_total = session.execute(
        select(func.sum(Sale.qty * Sale.unit_price_gs)).where(
            Sale.sold_at >= start_date, Sale.voided_at.is_(None)
        )
    ).scalar() or 0
    pct = waste_as_pct_of_revenue(
        session, start_date=start_date, end_date=end_date, revenue_gs=int(rev_total)
    )
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
    return render(request, "merma.html", {
        "items": items,
        "impact": impact,
        "pct": pct,
        "reasons": [r.value for r in WasteReason],
        "ingredients": ingredients,
        "recipes": recipes_with_yield,
    })


@router.post("/registrar")
def merma_register(
    request: Request,
    ingredient_id: int = Form(...),
    qty: float = Form(...),
    reason: str = Form(...),
    notes: str = Form(""),
    session: Session = Depends(get_session),
):
    """Record a new waste event."""
    # Validate reason is in the enum
    try:
        reason_enum = WasteReason(reason)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

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
        raise HTTPException(status_code=429, detail="Demasiadas acciones en 1 minuto. Esperá un momento.")

    record_waste(
        session,
        ingredient_id=ingredient_id,
        qty=qty,
        reason=reason_enum,
        notes=notes or None,
    )

    # Audit + commit
    from app.auth import current_user_id
    from app.rms.audit import record as audit_record
    audit_record(
        session,
        user_id=current_user_id(request) or "operator",
        action="write.merma.register",
        request=request,
        detail={"ingredient_id": ingredient_id, "qty": qty, "reason": reason},
    )
    session.commit()
    return RedirectResponse(url="/merma", status_code=303)


@router.post("/receta")
def merma_register_recipe(
    request: Request,
    recipe_id: int = Form(...),
    batch_qty: float = Form(...),
    reason: str = Form(...),
    notes: str = Form(""),
    session: Session = Depends(get_session),
):
    """Record a whole-batch waste event (Saskia review T6).

    Expands the recipe into per-ingredient WasteLog rows and decrements
    stock proportionally. Sub-recipes recurse via _compute_stock_moves.
    """
    try:
        reason_enum = WasteReason(reason)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if batch_qty <= 0:
        raise HTTPException(
            status_code=400, detail="La cantidad de lotes debe ser mayor a 0"
        )

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
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    from app.auth import current_user_id
    from app.rms.audit import record as audit_record
    audit_record(
        session,
        user_id=current_user_id(request) or "operator",
        action="write.merma.recipe",
        request=request,
        detail={
            "recipe_id": recipe_id,
            "recipe_name": result.recipe_name,
            "batch_qty": batch_qty,
            "cost_gs": result.cost_gs,
            "n_ingredient_logs": len(result.waste_logs),
            "reason": reason,
        },
    )
    session.commit()
    return RedirectResponse(url="/merma", status_code=303)


__all__ = ["router"]
