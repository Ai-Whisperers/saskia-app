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
def clientes_list(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    """Customer directory with loyalty tiers + points."""
    customers = list_customers(session)
    rows = []
    for c in customers:
        stats = customer_stats(session, c)
        rows.append({
            "id": c.id,
            "name": c.name or "(sin nombre)",
            "phone": c.phone,
            "lifetime_spend_gs": stats.lifetime_spend_gs,
            "n_sales": stats.n_sales,
            "last_sale_at": stats.last_sale_at,
            "tier": stats.tier.value,
            "tier_label": stats.tier.value.capitalize(),
            "points": c.loyalty_points,
        })
    return render(request, "clientes.html", {"customers": rows})


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
