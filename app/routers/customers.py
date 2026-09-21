"""app/routers/customers.py — /clientes (Customer directory + loyalty).

Built on top of app/rms/customers.py which has all the helpers:
- list_customers()
- get_customer()
- customer_stats()
- customer_purchase_history()
- tier_for_spend()
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.auth import require_login_or_disabled as require_login
from app.rms.customers import (
    batch_customer_stats,
    customer_purchase_history,
    customer_stats,
    list_customers,
    search_customers,
)
from app.rms.dependencies import get_session
from app.rms.models import Customer
from app.services.template_render import render

router = APIRouter(prefix="/clientes", dependencies=[Depends(require_login)])


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
        all_stats = batch_customer_stats(session, customers)
        for c in customers:
            stats = all_stats.get(c.id)
            if stats is None:
                continue
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
        # Batch-fetch all stats in one query instead of N queries
        all_stats = batch_customer_stats(session, customers)
        rows = []
        for c in customers:
            stats = all_stats.get(c.id)
            if stats is None:
                continue
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


def customer_to_api_payload(c: Customer, session: Session) -> dict:
    """Serialize a Customer row + computed stats for the picker UI.

    For a single customer (N=1) — calls customer_stats() which makes 1 query.
    For lists use batch_customer_stats() instead.
    """
    stats = customer_stats(session, c)
    lifetime_label = _format_gs_compact(stats.lifetime_spend_gs)
    return {
        "id": c.id,
        "name": c.name or "",
        "phone": c.phone or "",
        "email": c.email or "",
        "cedula": c.cedula or "",
        "notes": c.notes or "",
        "loyalty_points": c.loyalty_points,
        "n_sales": stats.n_sales,
        "lifetime_spend_gs": stats.lifetime_spend_gs,
        "lifetime_label": lifetime_label,
        "tier": stats.tier.value,
        "hint": f"{c.name} — {stats.n_sales} visitas, {lifetime_label} lifetime",
    }


def _format_gs_compact(value: int) -> str:
    """Format an integer Gs. amount in compact human-friendly form.

    1_500_000 → 'Gs. 1.5M', 250_000 → 'Gs. 250k', 0 → 'Gs. 0'.
    """
    if value >= 1_000_000:
        return f"Gs. {value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"Gs. {value // 1_000}k"
    return f"Gs. {value}"


@router.get("/api/search", response_class=JSONResponse)
def customer_search_api(
    q: str = Query("", description="Search query"),
    limit: int = Query(10, ge=1, le=50),
    session: Session = Depends(get_session),
) -> JSONResponse:
    """Search customers by name/phone/email/cedula/notes (case-insensitive).

    Used by the customer picker modal on /ventas.
    """
    rows = search_customers(session, q, limit=limit)
    if not rows:
        return JSONResponse({"results": [], "count": 0})
    all_stats = batch_customer_stats(session, rows)
    payload = []
    for c in rows:
        stats = all_stats.get(c.id)
        if stats is None:
            continue
        lifetime_label = _format_gs_compact(stats.lifetime_spend_gs)
        payload.append({
            "id": c.id,
            "name": c.name or "",
            "phone": c.phone or "",
            "email": c.email or "",
            "cedula": c.cedula or "",
            "notes": c.notes or "",
            "loyalty_points": c.loyalty_points,
            "n_sales": stats.n_sales,
            "lifetime_spend_gs": stats.lifetime_spend_gs,
            "lifetime_label": lifetime_label,
            "tier": stats.tier.value,
            "hint": f"{c.name} — {stats.n_sales} visitas, {lifetime_label} lifetime",
        })
    return JSONResponse({"results": payload, "count": len(payload)})


@router.post("/api/create", response_class=JSONResponse)
async def customer_create_api(
    request: Request,
    session: Session = Depends(get_session),
) -> JSONResponse:
    """Create (or update) a customer from form/JSON data.

    Accepts both form-encoded and JSON bodies. Required: name. If a phone
    matches an existing customer, that row is updated (idempotent).

    Returns JSON with the new/existing customer's id + display payload.
    """
    content_type = (request.headers.get("content-type") or "").lower()
    if "application/json" in content_type:
        body = await request.json()
        data = dict(body) if isinstance(body, dict) else {}
    else:
        form = await request.form()
        data = {k: form.get(k) for k in form.keys()}

    name = (str(data.get("name") or "")).strip()
    if not name:
        raise HTTPException(status_code=422, detail="name is required")

    phone = (str(data.get("phone") or "")).strip() or None
    email = (str(data.get("email") or "")).strip() or None
    cedula = (str(data.get("cedula") or "")).strip() or None
    notes = (str(data.get("notes") or "")).strip() or None

    from app.rms.customers import ensure_customer

    customer = ensure_customer(
        session,
        name=name,
        phone=phone,
        email=email,
        cedula=cedula,
        notes=notes,
    )
    session.commit()
    session.refresh(customer)
    return JSONResponse({
        "id": customer.id,
        "created": True,
        "customer": customer_to_api_payload(customer, session),
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
