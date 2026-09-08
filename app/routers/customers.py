"""app/routers/customers.py — /clientes (Customer directory + loyalty).

Built on top of app/rms/customers.py which has all the helpers:
- list_customers()
- get_customer()
- customer_stats()
- customer_purchase_history()
- tier_for_spend()
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.auth import require_login_or_disabled as require_login
from app.rms.customers import (
    customer_purchase_history,
    customer_stats,
    list_customers,
)
from app.services.template_render import render

router = APIRouter(prefix="/clientes", dependencies=[Depends(require_login)])


def get_session(request: Request) -> Session:
    return request.app.state.session_factory()


@router.get("", response_class=HTMLResponse)
def clientes_list(
    request: Request,
    q: str | None = None,
    tier: str | None = None,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Customer directory with loyalty tiers + points + filters."""
    from app.rms.models import Customer

    stmt = select(Customer)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Customer.name).like(like),
                func.lower(Customer.phone).like(like),
            )
        )
    if tier:
        # Filter by tier requires computing stats per customer; for
        # simplicity we filter post-hoc in Python (limit is small).
        customers = list_customers(session)
        if q:
            ql = q.lower()
            customers = [
                c for c in customers
                if (c.name and ql in c.name.lower())
                or (c.phone and ql in c.phone)
            ]
        rows = []
        for c in customers:
            stats = customer_stats(session, c)
            if stats.tier.value == tier:
                rows.append({
                    "id": c.id, "name": c.name or "(sin nombre)", "phone": c.phone,
                    "lifetime_spend_gs": stats.lifetime_spend_gs,
                    "n_sales": stats.n_sales,
                    "last_sale_at": stats.last_sale_at,
                    "tier": stats.tier.value,
                    "tier_label": stats.tier.value.capitalize(),
                    "points": c.loyalty_points,
                })
    else:
        # No tier filter — but q filter was applied via stmt.
        if q:
            ql = q.lower()
            customers = [
                c for c in list_customers(session)
                if (c.name and ql in c.name.lower())
                or (c.phone and ql in c.phone)
            ]
        else:
            customers = list_customers(session)
        rows = []
        for c in customers:
            stats = customer_stats(session, c)
            rows.append({
                "id": c.id, "name": c.name or "(sin nombre)", "phone": c.phone,
                "lifetime_spend_gs": stats.lifetime_spend_gs,
                "n_sales": stats.n_sales,
                "last_sale_at": stats.last_sale_at,
                "tier": stats.tier.value,
                "tier_label": stats.tier.value.capitalize(),
                "points": c.loyalty_points,
            })

    return render(request, "clientes.html", {
        "customers": rows,
        "q": q or "",
        "tier": tier or "",
        "tiers": ["bronze", "silver", "gold", "platinum"],
    })


@router.get("/{customer_id}", response_class=HTMLResponse)
def cliente_detail(
    request: Request,
    customer_id: int = Path(...),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Single customer: stats + purchase history."""
    from datetime import datetime, timezone

    from app.rms.customers import get_customer

    customer = get_customer(session, customer_id)
    if customer is None:
        return RedirectResponse(url="/clientes", status_code=status.HTTP_303_SEE_OTHER)
    stats = customer_stats(session, customer)
    history = customer_purchase_history(session, customer.id)
    return render(request, "cliente_detalle.html", {
        "customer": customer,
        "stats": stats,
        "history": history,
        "now_iso": datetime.now(timezone.utc).isoformat(),
    })


__all__ = ["router"]
