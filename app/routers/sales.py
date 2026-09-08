"""app/routers/sales.py — Sale entry, history, void.

Per dev plan §9 Task 5.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.auth import require_login_or_disabled as require_login
from app.rms.config import ASUNCION_TZ
from app.rms.costing import RecipeWithoutYield, apply_sale, void_sale
from app.rms.models import Customer, Product, Sale
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
async def sales_list(
    request: Request,
    q: str | None = None,
    product_id: int | None = None,
    days: int | None = None,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Sales list with optional filter (?q=substring, ?product_id=, ?days=N).

    Filters run on the existing sales query so `/ventas?q=cabernet`
    only returns matches. Helps operators find old sales without
    scrolling 50+ rows.
    """
    products = session.scalars(select(Product).order_by(Product.name)).all()
    sales_q = select(Sale).order_by(Sale.sold_at.desc())
    if product_id is not None:
        sales_q = sales_q.where(Sale.product_id == product_id)
    if days is not None and days > 0:
        cutoff = datetime.now(ASUNCION_TZ) - timedelta(days=days)
        sales_q = sales_q.where(Sale.sold_at >= cutoff)
    if q:
        # Search across product name, notes, customer phone.
        like = f"%{q.lower()}%"
        sales_q = (
            sales_q
            .outerjoin(Product, Sale.product_id == Product.id)
            .outerjoin(Customer, Sale.customer_id == Customer.id)
            .where(
                or_(
                    func.lower(Product.name).like(like),
                    func.lower(Sale.notes).like(like),
                    func.lower(Customer.phone).like(like),
                )
            )
        )
    sales = session.scalars(sales_q.limit(50)).all()

    # Quick-sell: top 5 products by revenue in last 14 days
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
    request: Request,
    product_id: int = Form(..., gt=0),
    qty: float = Form(..., gt=0),
    payment_method: str = Form(""),
    discount_gs: int = Form(0, ge=0),
    customer_phone: str = Form(""),
    notes: str = Form(""),
    sold_at: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Create a sale with stock drop.

    Validation: FastAPI's Form(...) enforces types + bounds before this
    handler runs. Bad input → 422.
    """
    from app.rms.schemas import ALLOWED_PAYMENT_METHODS, MAX_DISCOUNT_GS, MAX_QTY
    # Form(...) didn't enforce upper bounds here because Form() with `le=`
    # requires a literal value, not a constant. So we re-check explicitly.
    # The 422 path is hit when gt/le/... mismatch happens (handled by
    # FastAPI). For " > MAX_QTY specifically, raise 422 in the route via
    # the same alias — but that's overcomplicated. Keep 400 for these.
    if qty > MAX_QTY:
        raise HTTPException(status_code=422, detail=f"qty must be ≤ {MAX_QTY}")
    if discount_gs > MAX_DISCOUNT_GS:
        raise HTTPException(status_code=422, detail=f"discount_gs must be ≤ {MAX_DISCOUNT_GS}")

    # Parse sold_at (defaults to now in Asunción TZ)
    sold_at_raw = sold_at.strip()
    if sold_at_raw:
        try:
            # Form sends "YYYY-MM-DDTHH:MM" (no TZ). Treat as Asunción local.
            naive = datetime.fromisoformat(sold_at_raw)
            sold_at_dt = naive.replace(tzinfo=ASUNCION_TZ).astimezone(ASUNCION_TZ)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Fecha inválida: {sold_at_raw!r}") from e
    else:
        sold_at_dt = datetime.now(ASUNCION_TZ)

    # payment_method: optional, must be in ALLOWED_PAYMENT_METHODS if set
    payment_method_clean = payment_method.strip() or None
    if payment_method_clean is not None and payment_method_clean not in ALLOWED_PAYMENT_METHODS:
        raise HTTPException(
            status_code=400,
            detail=f"Forma de pago inválida. Permitidas: {sorted(ALLOWED_PAYMENT_METHODS)}",
        )

    notes_clean = notes.strip() or None
    customer_phone_clean = customer_phone.strip() or None
    customer_id: int | None = None
    if customer_phone_clean:
        from app.rms.customers import ensure_customer
        c = ensure_customer(session, name=customer_phone_clean, phone=customer_phone_clean)
        customer_id = c.id

    try:
        apply_sale(
            session,
            product_id,
            qty,
            sold_at_dt,
            notes_clean,
            customer_id=customer_id,
            payment_method=payment_method_clean,
            discount_gs=discount_gs,
        )
    except RecipeWithoutYield as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    # Audit + rate-limit (writes only — read paths not counted).
    from app.rms.audit import record as audit_record
    from app.rms.rate_limit import is_write_rate_limited
    if is_write_rate_limited(session, request, max_per_minute=10):
        raise HTTPException(status_code=429, detail="Demasiadas ventas en 1 minuto. Esperá un momento.")
    audit_record(
        session,
        user_id=None,
        action="write.sale.create",
        request=request,
        detail={"product_id": product_id, "qty": qty, "discount_gs": discount_gs},
    )
    session.commit()

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
