"""app/routers/customers.py — /clientes (Customer directory + loyalty).

Built on top of app/rms/customers.py which has all the helpers:
- list_customers()
- get_customer()
- customer_stats()
- customer_purchase_history()
- tier_for_spend()
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Form, HTTPException, Path, Query, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse as StarletteRedirectResponse

logger = logging.getLogger(__name__)

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
from app.rms.nav import status_es
from app.services.template_render import render

router = APIRouter(prefix="/clientes", dependencies=[Depends(require_login)])


PAGE_SIZE = 50


@router.get("", response_class=HTMLResponse)
def clientes_list(
    request: Request,
    q: str | None = None,
    tier: str | None = None,
    sort: str | None = Query(
        None, description="Sort column: name, phone, n_sales, lifetime_spend_gs, points, tier"
    ),
    dir: str | None = Query("asc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Customer directory with loyalty tiers + points + filters."""
    import csv
    import io

    from starlette.responses import StreamingResponse

    q = q or ""
    f"%{q.lower()}%"

    if tier:
        # Tier filter requires post-hoc filtering (stats needed per customer).
        customers = list_customers(session)
        if q:
            ql = q.lower()
            customers = [
                c
                for c in customers
                if (c.name and ql in c.name.lower()) or (c.phone and ql in c.phone)
            ]
        rows = []
        all_stats = batch_customer_stats(session, customers)
        for c in customers:
            stats = all_stats.get(c.id)
            if stats is None:
                continue
            if stats.tier.value == tier:
                rows.append(
                    {
                        "id": c.id,
                        "name": c.name or "(sin nombre)",
                        "phone": c.phone,
                        "lifetime_spend_gs": stats.lifetime_spend_gs,
                        "n_sales": stats.n_sales,
                        "last_sale_at": stats.last_sale_at,
                        "tier": stats.tier.value,
                        "tier_label": status_es(stats.tier.value)[0],
                        "tier_sev": status_es(stats.tier.value)[1],
                        "points": c.loyalty_points,
                        "created_at": c.created_at,
                    }
                )
    else:
        # No tier filter — search only.
        if q:
            ql = q.lower()
            customers = [
                c
                for c in list_customers(session)
                if (c.name and ql in c.name.lower()) or (c.phone and ql in c.phone)
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
            rows.append(
                {
                    "id": c.id,
                    "name": c.name or "(sin nombre)",
                    "phone": c.phone,
                    "lifetime_spend_gs": stats.lifetime_spend_gs,
                    "n_sales": stats.n_sales,
                    "last_sale_at": stats.last_sale_at,
                    "tier": stats.tier.value,
                    "tier_label": status_es(stats.tier.value)[0],
                    "tier_sev": status_es(stats.tier.value)[1],
                    "points": c.loyalty_points,
                    "created_at": c.created_at,
                }
            )

    # Apply sorting
    sort_col = sort or "name"
    reverse = dir == "desc"
    col_map = {
        "name": "name",
        "phone": "phone",
        "n_sales": "n_sales",
        "lifetime_spend_gs": "lifetime_spend_gs",
        "points": "points",
        "tier": "tier",
    }
    col = col_map.get(sort_col, "name")
    if rows and col in rows[0]:
        rows.sort(
            key=lambda r: r.get(col) or "" if isinstance(r.get(col), str) else r.get(col) or 0,
            reverse=reverse,
        )

    # Pagination
    total = len(rows)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(page, total_pages)
    start = (page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE
    page_rows = rows[start:end]

    # --- CSV export (all rows, not just current page) ---
    if request.query_params.get("format") == "csv":
        export_rows = [
            {
                "id": r["id"],
                "name": r["name"],
                "phone": r["phone"] or "",
                "n_sales": r["n_sales"],
                "lifetime_spend_gs": r["lifetime_spend_gs"],
                "tier": r["tier"],
                "points": r["points"],
                "last_sale_at": r["last_sale_at"].iso if r["last_sale_at"] else "",
                "created_at": r["created_at"].iso if r["created_at"] else "",
            }
            for r in rows
        ]
        buf = io.StringIO()
        w = csv.DictWriter(
            buf,
            fieldnames=[
                "id",
                "name",
                "phone",
                "n_sales",
                "lifetime_spend_gs",
                "tier",
                "points",
                "last_sale_at",
                "created_at",
            ],
        )
        w.writeheader()
        w.writerows(export_rows)
        return StreamingResponse(
            iter([buf.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=clientes.csv"},
        )

    return render(
        request,
        "clientes.html",
        {
            "customers": page_rows,
            "q": q or "",
            "tier": tier or "",
            "tiers": ["bronze", "silver", "gold", "platinum"],
            "sort": sort or "",
            "dir": dir or "asc",
            "page": page,
            "total_pages": total_pages,
            "total": total,
            "page_start": (page - 1) * 50 + 1,
            "page_end": min(page * 50, total),
        },
    )


def customer_to_api_payload(c: Customer, session: Session) -> dict:
    """Serialize a Customer row + computed stats for the picker UI.

    For a single customer (N=1) — calls customer_stats() which makes 1 query.
    For lists use batch_customer_stats() instead.

    Returns the picker-friendly shape (compact stats, no top_products).
    For the full /clientes/api/{id} payload (notes, last_sale_at, top_products)
    use _customer_detail_payload() instead.
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


def _customer_detail_payload(c: Customer, session: Session) -> dict:
    """Full payload for /clientes/api/{id} and /clientes/api/create response.

    Includes the same fields as the search/picker payload PLUS:
      - last_sale_at (ISO timestamp from latest Sale.sold_at, or null)
      - top_products: top 3 products the customer buys most often
        ([{name, count}]) — counted across non-voided sales

    Uses batch_customer_stats() to keep the stats query consistent with the
    search/list endpoints. One extra query walks Sale rows for top_products.
    """
    stats_map = batch_customer_stats(session, [c])
    stats = stats_map.get(c.id)
    if stats is None:
        # Shouldn't happen — batch_customer_stats() always fills in a BRONZE
        # row even when the customer has zero sales — but defend anyway.
        from app.rms.customers import customer_stats as _per_cust

        stats = _per_cust(session, c)
    lifetime_label = _format_gs_compact(stats.lifetime_spend_gs)
    top_products = _top_products_for_customer(session, c.id, limit=3)
    last_sale_at_iso = stats.last_sale_at.isoformat() if stats.last_sale_at else None
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
        "last_sale_at": last_sale_at_iso,
        "top_products": top_products,
        "hint": f"{c.name} — {stats.n_sales} visitas, {lifetime_label} lifetime",
    }


def _top_products_for_customer(session: Session, customer_id: int, limit: int = 3) -> list[dict]:
    """Return the customer's top-N products by total qty across non-voided sales.

    [{name: str, count: int|float}] — `count` is total units purchased.

    One query (group by product, sum qty, order by sum desc). Used by the
    customer info card on /ventas to show what they typically buy.
    """
    from app.rms.models import Product, Sale

    rows = session.execute(
        select(
            Product.name.label("name"),
            func.coalesce(func.sum(Sale.qty), 0).label("count"),
        )
        .join(Sale, Sale.product_id == Product.id)
        .where(Sale.customer_id == customer_id, Sale.voided_at.is_(None))
        .group_by(Product.name)
        .order_by(func.coalesce(func.sum(Sale.qty), 0).desc())
        .limit(limit)
    ).all()
    return [{"name": r.name, "count": int(r.count or 0)} for r in rows]


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
        payload.append(
            {
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
        )
    return JSONResponse({"results": payload, "count": len(payload)})


@router.post("/api/create", response_class=JSONResponse)
async def customer_create_api(
    request: Request,
    session: Session = Depends(get_session),
) -> JSONResponse:
    """Create (or update) a customer from form/JSON data.

    Accepts both form-encoded and JSON bodies. Required: name. If a phone
    matches an existing customer, that row is updated (idempotent).

    Returns JSON with the new/existing customer's id + FULL display payload
    (notes, last_sale_at, top_products, stats, tier) — same shape as the
    /clientes/api/{id} GET endpoint so the inline-create flow on /ventas
    can populate the customer info card without a second fetch.
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
        raise HTTPException(status_code=422, detail="nombre es obligatorio")

    # Use centralized validation for email/phone/cedula so we don't accept
    # garbage like "nope" as an email or "abc" as a phone.
    from app.rms.validation import (
        optional_text,
        validate_cedula,
        validate_email,
        validate_phone,
    )

    phone = validate_phone(str(data.get("phone") or ""))
    email = validate_email(str(data.get("email") or ""))
    cedula = validate_cedula(str(data.get("cedula") or ""))
    notes = optional_text(str(data.get("notes") or ""), max_len=2000)

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
    return JSONResponse(
        {
            "id": customer.id,
            "created": True,
            "customer": _customer_detail_payload(customer, session),
        }
    )


@router.get("/api/{customer_id}", response_class=JSONResponse)
def customer_detail_api(
    customer_id: int = Path(..., ge=1, description="Customer primary key"),
    session: Session = Depends(get_session),
) -> JSONResponse:
    """Return a single customer's full payload (notes + stats + top_products).

    Used by the inline customer info card on /ventas. 404 if not found.
    500 on DB error (defensive — the picker UI relies on this never crashing).
    """
    try:
        customer = session.get(Customer, customer_id)
        if customer is None:
            return JSONResponse({"error": "not_found"}, status_code=404)
        return JSONResponse(_customer_detail_payload(customer, session))
    except Exception:
        # OPSEC: log only the customer_id, never the name/phone/email.
        logger.exception("customer_detail_api failed for customer_id=%s", customer_id)
        return JSONResponse({"error": "internal_error"}, status_code=500)


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
    return render(
        request,
        "cliente_detalle.html",
        {
            "customer": customer,
            "stats": stats,
            "history": history,
            "now_iso": datetime.now(timezone.utc).isoformat(),
        },
    )


@router.get("/{customer_id}/editar", response_class=HTMLResponse)
def cliente_edit(
    request: Request,
    customer_id: int = Path(...),
    session: Session = Depends(get_session),
) -> object:
    """Edit form for an existing customer."""
    customer = session.get(Customer, customer_id)
    if customer is None:
        return StarletteRedirectResponse(url="/clientes", status_code=303)
    return render(request, "cliente_editar.html", {"customer": customer})


@router.post("/{customer_id}/editar")
def cliente_update(
    request: Request,
    customer_id: int = Path(...),
    name: str = Form(""),
    phone: str = Form(""),
    email: str = Form(""),
    cedula: str = Form(""),
    notes: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Update an existing customer's fields."""
    from app.rms.audit import record
    from app.rms.validation import (
        optional_text,
        require_text,
        validate_cedula,
        validate_email,
        validate_phone,
    )

    customer = session.get(Customer, customer_id)
    if customer is None:
        return RedirectResponse(url="/clientes", status_code=303)
    customer.name = require_text(name, field="nombre", max_len=120)
    customer.phone = validate_phone(phone)
    customer.email = validate_email(email)
    customer.cedula = validate_cedula(cedula)
    customer.notes = optional_text(notes, max_len=2000)
    session.commit()
    record(
        session,
        user_id=None,
        action="customer.updated",
        target_type="customer",
        target_id=str(customer_id),
        detail={"name": customer.name},
        request=request,
    )
    return RedirectResponse(
        url=f"/clientes/{customer_id}?flash=Cliente+actualizado", status_code=303
    )


@router.post("/bulk-eliminar")
def clientes_bulk_delete(
    request: Request,
    ids: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Delete multiple customers at once. Skips any with sales."""
    from app.rms.audit import record

    deleted = 0
    skipped = 0
    for cid in ids.split(","):
        cid = cid.strip()
        if not cid:
            continue
        try:
            c = session.get(Customer, int(cid))
        except ValueError:
            continue
        if c is None:
            continue
        # Check for sales — use limit(1) for efficiency
        from app.rms.models import Sale

        has_sales = session.scalar(select(Sale.id).where(Sale.customer_id == c.id).limit(1))
        if has_sales is not None:
            skipped += 1
            continue
        # Log deletion before deleting
        record(
            session,
            user_id=None,  # session-based auth; user_id not yet available
            action="customer.deleted",
            target_type="customer",
            target_id=c.id,
            detail={"name": c.name, "phone": c.phone},
            request=request,
        )
        session.delete(c)
        deleted += 1

    session.commit()
    flash = f"{deleted} cliente(s) eliminado(s)"
    if skipped:
        flash += f", {skipped} omitido(s) por tener ventas"
    return RedirectResponse(url=f"/clientes?flash={flash}", status_code=303)
