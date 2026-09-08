"""app/routers/sales.py — Sale entry, history, void.

Per dev plan §9 Task 5.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_login_or_disabled as require_login
from app.rms.config import ASUNCION_TZ
from app.rms.costing import RecipeWithoutYield, apply_sale, void_sale
from app.rms.models import Product, Sale
from app.services.template_render import render

router = APIRouter(prefix="/ventas", dependencies=[Depends(require_login)])


def get_session(request: Request) -> Session:
    return request.app.state.session_factory()


def _decorated(s: Sale) -> dict:
    return {
        "id": s.id,
        "sold_at": s.sold_at,
        "sold_at_str": s.sold_at.strftime("%d/%m/%Y %H:%M"),
        "product_id": s.product_id,
        "product_name": s.product.name if s.product else "(deleted)",
        "qty": s.qty,
        "unit_price_gs": s.unit_price_gs,
        "total_gs": int(round(s.qty * s.unit_price_gs)),
        "notes": s.notes,
        "voided_at": s.voided_at,
        "customer_phone": s.customer.phone if s.customer else None,
        "payment_method": s.payment_method,
        "discount_gs": s.discount_gs,
    }


@router.get("", response_class=HTMLResponse)
async def sales_list(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    products = session.scalars(select(Product).order_by(Product.name)).all()
    sales = session.scalars(select(Sale).order_by(Sale.sold_at.desc()).limit(50)).all()

    # Quick-sell: top 5 products by revenue in last 14 days
    from datetime import timedelta

    from sqlalchemy import func
    since = datetime.now(ASUNCION_TZ) - timedelta(days=14)
    q = (
        select(Sale.product_id, func.sum(Sale.qty).label("units"), func.sum(Sale.qty * Sale.unit_price_gs).label("rev"))
        .where(Sale.sold_at >= since, Sale.voided_at.is_(None))
        .group_by(Sale.product_id)
        .order_by(func.sum(Sale.qty * Sale.unit_price_gs).desc())
        .limit(5)
    )
    quick_rows = session.execute(q).all()
    product_by_id = {p.id: p for p in products}
    quick_sell = []
    for pid, units, rev in quick_rows:
        p = product_by_id.get(pid)
        if p is not None:
            quick_sell.append({
                "product_id": pid,
                "name": p.name,
                "sale_price_gs": p.sale_price_gs,
                "units": float(units),
                "revenue_gs": int(rev or 0),
            })

    return render(
        request,
        "ventas.html",
        {
            "products": products,
            "sales": [_decorated(s) for s in sales],
            "quick_sell": quick_sell,
            "payment_methods": ["efectivo", "transferencia", "tarjeta", "otro"],
            "now_local": datetime.now(ASUNCION_TZ).strftime("%Y-%m-%dT%H:%M"),
        },
    )


@router.post("/nueva")
async def sale_create(
    request: Request, session: Session = Depends(get_session)
) -> RedirectResponse:
    """Create a sale with stock drop."""
    form = await request.form()
    try:
        product_id = int(form.get("product_id", "0"))
        qty = float(form.get("qty", "0"))
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=400, detail=f"Entrada inválida: {e}") from e

    if product_id <= 0 or qty <= 0:
        raise HTTPException(status_code=400, detail="Producto y cantidad son obligatorios")

    # Parse sold_at (defaults to now in Asunción TZ)
    sold_at_raw = str(form.get("sold_at", "")).strip()
    if sold_at_raw:
        try:
            # Form sends "YYYY-MM-DDTHH:MM" (no TZ). Treat as Asunción local.
            naive = datetime.fromisoformat(sold_at_raw)
            sold_at = naive.replace(tzinfo=ASUNCION_TZ).astimezone(ASUNCION_TZ)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Fecha inválida: {sold_at_raw!r}") from e
    else:
        sold_at = datetime.now(ASUNCION_TZ)

    notes = str(form.get("notes", "")).strip() or None
    payment_method = str(form.get("payment_method", "")).strip() or None
    discount_raw = str(form.get("discount_gs", "0")).strip() or "0"
    try:
        discount_gs = max(0, int(discount_raw))
    except ValueError:
        discount_gs = 0
    customer_phone = str(form.get("customer_phone", "")).strip() or None
    customer_id: int | None = None
    if customer_phone:
        from app.rms.customers import ensure_customer
        c = ensure_customer(session, name=customer_phone, phone=customer_phone)
        customer_id = c.id

    try:
        apply_sale(
            session,
            product_id,
            qty,
            sold_at,
            notes,
            customer_id=customer_id,
            payment_method=payment_method,
            discount_gs=discount_gs,
        )
    except RecipeWithoutYield as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return RedirectResponse(url="/ventas", status_code=303)


@router.post("/{sale_id}/anular")
async def sale_void(
    sale_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Void a sale and reverse stock."""
    try:
        void_sale(session, sale_id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return RedirectResponse(url="/ventas", status_code=303)


__all__ = ["router"]
