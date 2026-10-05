"""app/routers/sales.py — Sale entry, history, void.

Per dev plan §9 Task 5.
"""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response, StreamingResponse
from loguru import logger
from sqlalchemy import Select, func, or_, select, update
from sqlalchemy.orm import Session, selectinload

from app.auth import require_login_or_disabled as require_login
from app.rms.audit import record as audit_record
from app.rms.catalogs import (
    default_channel_code,
    default_payment_method_code,
    list_channels,
    list_payment_methods,
)
from app.rms.config import ASUNCION_TZ
from app.rms.costing import RecipeWithoutYield, apply_sale, void_sale
from app.rms.db import safe_commit
from app.rms.dependencies import get_session
from app.rms.errors import BadRequest, Conflict, NotFound, ValidationError
from app.rms.loyalty import discount_gs_for_points
from app.rms.messages import (
    SALE_BODY_INVALID,
    SALE_CUSTOMER_NOT_FOUND,
    SALE_DISCOUNT_TOO_HIGH,
    SALE_INVALID_CHANNEL,
    SALE_INVALID_DATE,
    SALE_INVALID_PAYMENT_METHOD,
    SALE_PRODUCT_OR_SKU_REQUIRED,
    SALE_QTY_TOO_HIGH,
    SALE_RATE_LIMITED,
    SALE_SKU_NOT_FOUND,
    SALE_SKU_REQUIRED,
    SALE_TOO_MANY_ITEMS,
)
from app.rms.models import Customer, Product, Sale, StockMovement
from app.rms.money import to_int_gs
from app.rms.public_tokens import (
    enforce_rate_limit as public_token_enforce_rate_limit,
    generate_public_token,
    is_token_valid,
)
from app.rms.settings_runtime import get_branding
from app.rms.schemas import (
    ALLOWED_CHANNELS,
    CHANNEL_DEFAULT,
    CHANNELS_DISPLAY,
    PAYMENT_METHOD_DEFAULT,
    PAYMENT_METHODS_DISPLAY,
)
from app.services.template_render import render

router = APIRouter(prefix="/ventas", dependencies=[Depends(require_login)])

# BACKLOG #17: public_router for /r/{token} — no auth, no CSRF.
# Lives at root (mounted via app.include_router in main.py) so the URL
# is short enough for WhatsApp messages. Mirrors pedidos.public_router.
# Token generation, expiry validation, client-IP extraction, and
# rate-limiting all delegate to app.rms.public_tokens so the two
# public routes can never drift apart.
public_router = APIRouter()


def _decorated(s: Sale) -> dict:
    return {
        "id": s.id,
        "sold_at": s.sold_at,
        "sold_at_str": s.sold_at.strftime("%d/%m/%Y %H:%M"),
        "product_id": s.product_id,
        "product_name": s.product.name if s.product else "(deleted)",
        "qty": s.qty,
        "unit_price_gs": s.unit_price_gs,
        "total_gs": to_int_gs(Decimal(str(s.qty)) * Decimal(str(s.unit_price_gs))),
        "notes": s.notes,
        "voided_at": s.voided_at,
        "voided_at_str": s.voided_at.strftime("%d/%m/%Y %H:%M") if s.voided_at else None,
        # CIE-01: void metadata exposed to templates for audit display.
        "void_reason": getattr(s, "void_reason", None),
        "voided_by": getattr(s, "voided_by", None),
        "customer_id": s.customer_id,
        "customer_phone": s.customer.phone if s.customer else None,
        "customer_name": s.customer.name if s.customer else None,
        "payment_method": s.payment_method,
        "channel": s.channel or "mostrador",
        "discount_gs": s.discount_gs,
    }


def _generate_idem_key() -> str:
    """Generate a per-render idempotency key for the sale form.

    Server-side UUID so the template doesn't have to call Jinja2's
    `|random` filter (which doesn't exist in stock Jinja2 — only with
    the django-jinja extra). UUIDs are 12 hex chars, same shape the
    template was building with `range(1000000)|random|string`.
    """
    return uuid.uuid4().hex[:12]


PAGE_SIZE = 20


def _get_tax_regime(session: Session) -> str:
    """Return the configured tax_regime from ComplianceInfo. Defaults to DEFAULT_TAX_REGIME."""
    from app.rms.constants import DEFAULT_TAX_REGIME
    from app.rms.models import ComplianceInfo
    ci = session.get(ComplianceInfo, 1)
    return ci.tax_regime if ci else DEFAULT_TAX_REGIME


def _build_sales_context(
    request: Request,
    q: str | None,
    product_id: int | None,
    days: int | None,
    offset: int | None,
    session: Session,
    fav: bool = False,
) -> dict:
    """Build the render context shared by /ventas and /ventas/historial.

    Computes products, filtered sales page, summary totals, and Quick-Sell
    top-5 in one pass. Both routes call this then render a different
    template (ventas.html for the POS, ventas_historial.html for history)
    so the filter logic stays in sync — US 4.3 split.
    """
    products_q = select(Product).order_by(Product.name)
    if fav:
        products_q = products_q.where(Product.is_favorite.is_(True))
    products = session.scalars(products_q).all()
    sales_q = (
        select(Sale)
        .options(selectinload(Sale.product), selectinload(Sale.customer))
        .order_by(Sale.sold_at.desc())
    )
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

    # Count total matching (for pagination has_more)
    count_q = select(func.count(Sale.id))
    if product_id is not None:
        count_q = count_q.where(Sale.product_id == product_id)
    if days is not None and days > 0:
        cutoff = datetime.now(ASUNCION_TZ) - timedelta(days=days)
        count_q = count_q.where(Sale.sold_at >= cutoff)
    if q:
        like = f"%{q.lower()}%"
        count_q = (
            count_q
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
    total_count = session.scalar(count_q) or 0

    # Apply offset pagination (default PAGE_SIZE rows)
    start_offset = offset or 0
    sales = session.scalars(sales_q.offset(start_offset).limit(PAGE_SIZE + 1)).all()
    has_more = len(sales) > PAGE_SIZE
    sales_page = sales[:PAGE_SIZE]

    # Aggregate totals (excluding voided) for the filtered set — used by
    # both the HTML summary card and the CSV export. We apply the same
    # filters onto a count/sum aggregate (no 50-row limit).
    totals_q = select(
        func.count(Sale.id),
        func.coalesce(func.sum(Sale.qty * Sale.unit_price_gs), 0),
    ).where(Sale.voided_at.is_(None))
    if product_id is not None:
        totals_q = totals_q.where(Sale.product_id == product_id)
    if days is not None and days > 0:
        cutoff = datetime.now(ASUNCION_TZ) - timedelta(days=days)
        totals_q = totals_q.where(Sale.sold_at >= cutoff)
    if q:
        like = f"%{q.lower()}%"
        totals_q = totals_q.outerjoin(Product, Sale.product_id == Product.id).outerjoin(
        Customer, Sale.customer_id == Customer.id
    ).where(
        or_(
            func.lower(Product.name).like(like),
            func.lower(Sale.notes).like(like),
            func.lower(Customer.phone).like(like),
        )
    )
    row = session.execute(totals_q).one()
    total_count = int(row[0] or 0)
    total_gs = int(row[1] or 0)

    # Quick-sell: top 5 products by revenue in last 14 days
    since = datetime.now(ASUNCION_TZ) - timedelta(days=14)
    quick_sell_q = (
        select(Sale.product_id, func.sum(Sale.qty).label("units"), func.sum(Sale.qty * Sale.unit_price_gs).label("rev"))
        .where(Sale.sold_at >= since, Sale.voided_at.is_(None))
        .group_by(Sale.product_id)
        .order_by(func.sum(Sale.qty * Sale.unit_price_gs).desc())
        .limit(5)
    )
    quick_rows = session.execute(quick_sell_q).all()
    product_by_id = {p.id: p for p in products}
    quick_sell = []
    seen_qs: set[int] = set()
    for pid, units, rev in quick_rows:
        p = product_by_id.get(pid)
        if p is not None:
            quick_sell.append({
                "product_id": pid,
                "name": p.name,
                "sale_price_gs": p.sale_price_gs,
                "units": float(units),
                "revenue_gs": int(rev or 0),
                "is_available": p.is_available,
                "stock_qty": getattr(p, "stock_qty", None),
                "image_url": getattr(p, "image_url", None) or "",
                "is_favorite": bool(p.is_favorite),
            })
            seen_qs.add(pid)

    # P3 UX (2026-09-30): favorites always visible on the POS grid, even
    # with no recent sales (fresh boot / quiet week). The cashier's
    # "initial options are the most relevant": favorites first, then the
    # top sellers. New favorites appear immediately when toggled.
    for p in products:
        if p.is_favorite and p.id not in seen_qs:
            quick_sell.append({
                "product_id": p.id,
                "name": p.name,
                "sale_price_gs": p.sale_price_gs,
                "units": 0.0,
                "revenue_gs": 0,
                "is_available": p.is_available,
                "stock_qty": getattr(p, "stock_qty", None),
                "image_url": getattr(p, "image_url", None) or "",
                "is_favorite": True,
            })
            seen_qs.add(p.id)
    # favorites first within the merged list (stable for the rest)
    quick_sell.sort(key=lambda item: not item.get("is_favorite", False))

    # E13.S2 — Venta libre: pass the cashier-custom-price product id so
    # the ventas template can render a "+ Venta libre" tile that opens
    # a price prompt. NULL when the row hasn't been seeded yet (e.g.
    # brand-new DB before the operator runs seed); the button is
    # hidden in that case.
    venta_libre = session.execute(
        select(Product).where(Product.sku == "VAR-001")
    ).scalar_one_or_none()
    venta_libre_id = venta_libre.id if venta_libre is not None else None

    return {
        "products": products,
        "sales": [_decorated(s) for s in sales_page],
        "quick_sell": quick_sell,
        "q": q or "",
        "product_id": product_id or "",
        "days": days,
        "products_filtered": products,  # alias used by historial.html
        # DB-driven catalogs (Phase 4 of static-content audit). Falls back
        # to schema constants if the DB tables haven't been seeded yet.
        "channels": [c.code for c in list_channels(session)] or list(CHANNELS_DISPLAY),
        "channel_default": default_channel_code(session) or CHANNEL_DEFAULT,
        "payment_methods": [pm.code for pm in list_payment_methods(session)] or list(PAYMENT_METHODS_DISPLAY),
        "payment_method_default": default_payment_method_code(session) or PAYMENT_METHOD_DEFAULT,
        "now_local": datetime.now(ASUNCION_TZ).strftime("%Y-%m-%dT%H:%M"),
        "idem_key": _generate_idem_key(),
        # Phase 1.B — pass tax regime so the form defaults the invoice type
        "tax_regime": _get_tax_regime(session),
        "totals": {
            "count": total_count,
            "total_gs": total_gs,
            "avg_ticket_gs": int(total_gs / total_count) if total_count else 0,
            "filters": _filter_summary(
                q=q, product_id=product_id, days=days, products=products
            ),
        },
        "has_more": has_more,
        "current_offset": start_offset,
        "current_page_size": PAGE_SIZE,
        "page_start": start_offset + 1,
        "page_end": min(start_offset + PAGE_SIZE, total_count),
        "total_count": total_count,
        # E13.S2 — venta libre (cashier-typed price) plumbing
        "venta_libre_id": venta_libre_id,
    }


@router.get("", response_class=HTMLResponse)
async def sales_list(
    request: Request,
    q: str | None = None,
    product_id: int | None = None,
    days: int | None = None,
    offset: int | None = None,
    fav: int | None = None,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """POS landing page — Nueva venta (new sale form + Quick-Sell).

    US 4.3 (S5): History view moved to /ventas/historial so the
    counter screen isn't cluttered with 50+ past rows.
    """
    ctx = _build_sales_context(
        request=request,
        session=session,
        q=q,
        product_id=product_id,
        days=days,
        offset=offset,
        fav=bool(fav),
    )
    return render(request, "ventas.html", ctx)


# ─────────────────────────────────────────────────────────────────────
# QA / Smoke tests (2026-09-29)
# ─────────────────────────────────────────────────────────────────────
# Page at /ventas/qa runs 6 automated end-to-end checks against the live
# API surface. Each test is a separate fetch() against an internal route
# (login is via cookie). Output is a green/red table the operator can
# read before declaring a deploy safe.
#
# Tests cover the full cashier flow:
#   1. login + session healthz
#   2. create customer via /clientes/api/create
#   3. list products (catalog reachable)
#   4. create sale without customer (cash-only)
#   5. create sale with customer (debt tracked)
#   6. void the sale (must restore customer stats + product stock)
# ─────────────────────────────────────────────────────────────────────


@router.get("/qa", response_class=HTMLResponse)
def ventas_qa(request: Request) -> HTMLResponse:
    """Smoke-test page. Each test fires a fetch() against the live API
    and shows pass/fail. No DB writes happen until the operator clicks
    'Run all tests' — the page itself just describes what each test
    does so the operator knows what they're approving.
    """
    return render(request, "ventas_qa.html", {})


@router.get("/historial", response_class=HTMLResponse)
async def sales_history(
    request: Request,
    q: str | None = None,
    product_id: int | None = None,
    days: int | None = None,
    page: int | None = Query(None),
    offset: int | None = None,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Sales history (US 4.3 split).

    Shares query logic with sales_list via _build_sales_context so the
    filter semantics stay in sync. Renders ventas_historial.html which
    shows the summary card, filter form, table of past sales, and the
    per-row Anular button.
    """
    # Accept page=1-based OR offset=0-based; page takes priority
    computed_offset: int | None
    if page is not None and page > 0:
        computed_offset = (page - 1) * PAGE_SIZE
    else:
        computed_offset = offset

    ctx = _build_sales_context(
        request=request,
        session=session,
        q=q,
        product_id=product_id,
        days=days,
        offset=computed_offset,
    )
    # Derive pagination metadata and add to existing ctx (do NOT reassign ctx)
    total = ctx.get("total_count", 0)
    page_sz = PAGE_SIZE
    current_offset = computed_offset or 0
    current_page = (current_offset // page_sz) + 1 if page_sz > 0 else 1
    total_pages = (total + page_sz - 1) // page_sz if page_sz > 0 else 1
    ctx["pagination"] = {
        "page": current_page,
        "total_pages": total_pages,
        "total_count": total,
    }
    # Clean filter values for pagination links: drop None/empty string
    ctx["_q_val"] = q if q else None
    ctx["_product_id_val"] = product_id if product_id else None
    ctx["_days_val"] = days if days else None
    return render(request, "ventas_historial.html", ctx)


def _filter_summary(
    q: str | None,
    product_id: int | None,
    days: int | None,
    products: list[Product],
) -> str:
    """Human-readable description of the active filter (shown in the summary card)."""
    parts = []
    if days is not None and days > 0:
        parts.append(f"últimos {days} días")
    if product_id is not None:
        prod = next((p for p in products if p.id == product_id), None)
        if prod is not None:
            parts.append(f"producto: {prod.name}")
    if q:
        parts.append(f"«{q}»")
    if not parts:
        return "todos los registros activos"
    return ", ".join(parts)


def _build_filtered_sales_query(
    q: str | None,
    product_id: int | None,
    days: int | None,
) -> Select:
    """Build a Sale query applying the same filters as sales_list.

    Used by both the HTML view and the CSV export so they stay
    consistent. Eager-loads product + customer to avoid N+1 in _decorated.
    """
    sales_q = (
        select(Sale)
        .options(selectinload(Sale.product), selectinload(Sale.customer))
        .order_by(Sale.sold_at.desc())
    )
    if product_id is not None:
        sales_q = sales_q.where(Sale.product_id == product_id)
    if days is not None and days > 0:
        cutoff = datetime.now(ASUNCION_TZ) - timedelta(days=days)
        sales_q = sales_q.where(Sale.sold_at >= cutoff)
    if q:
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
    return sales_q


@router.get("/export.csv")
async def sales_export_csv(
    q: str | None = None,
    product_id: int | None = None,
    days: int | None = None,
    session: Session = Depends(get_session),
) -> Response:
    """CSV export of the sales history (matches the filters on /ventas).

    No row limit — operators want full records for accounting / IVA.
    Content-disposition: attachment so browsers download instead of
    rendering. UTF-8 BOM-prefixed so Excel opens it correctly in PY.
    """
    sales_q = _build_filtered_sales_query(q=q, product_id=product_id, days=days)
    sales = session.scalars(sales_q).all()

    def _row_stream():
        from app.rms.streaming_csv import stream_csv_rows

        header = [
            "fecha", "producto", "cantidad", "precio_unitario_gs",
            "total_gs", "telefono_cliente", "forma_pago",
            "anulada", "notas", "canal",
        ]
        def _iter():
            for s in sales:
                yield [
                    s.sold_at.strftime("%Y-%m-%d %H:%M"),
                    s.product.name if s.product else "(deleted)",
                    f"{s.qty:.2f}",
                    s.unit_price_gs,
                    to_int_gs(Decimal(str(s.qty)) * Decimal(str(s.unit_price_gs))),
                    s.customer.phone if s.customer else "",
                    s.payment_method or "",
                    "sí" if s.voided_at else "no",
                    s.notes or "",
                    s.channel or "mostrador",
                ]
        # BOM=True: Excel-PY requires it (CSV without BOM shows accents wrong).
        return stream_csv_rows(header, _iter(), bom=True)

    return StreamingResponse(
        _row_stream(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="ventas.csv"',
        },
    )


@router.get("/{sale_id}", response_class=HTMLResponse)
async def sale_detail(
    request: Request,
    sale_id: int,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Operator-facing single-sale detail page (BACKLOG #16).

    Distinct from /recibo (the printable customer receipt):
    - Full nav + breadcrumbs
    - Action buttons: view recibo, void, refund
    - Wider layout — fits channel, payment method, customer link
    - Stock-move ledger so the operator can trace what got consumed
    - Refund history table (M1, 2026-10-02)

    Placed before /recibo so the {sale_id} path matches first; FastAPI
    routing prefers more-specific literals, so /{sale_id}/recibo still
    wins for the printable receipt.
    """
    from app.rms.errors import NotFound
    from app.rms.models import Ingredient, StockMovement
    from app.rms.refunds import list_refunds_for, sum_refunds_for

    sale = session.get(Sale, sale_id)
    if sale is None:
        raise NotFound("venta", id=sale_id)

    # Stock-move ledger for this sale (BACKLOG #16 traceability).
    # After BACKLOG #1 (this session), the ledger lives in stock_movement
    # keyed by (reference_id=sale_id, reference_type='sale'). Voids
    # create a NEW positive-qty row, so both rows show up in the list.
    moves = session.execute(
        select(StockMovement)
        .where(StockMovement.reference_id == sale_id)
        .where(StockMovement.reference_type == "sale")
        .order_by(StockMovement.id.asc())
    ).scalars().all()

    stock_moves = []
    for sm in moves:
        ing = session.get(Ingredient, sm.ingredient_id) if sm.ingredient_id else None
        stock_moves.append({
            "id": sm.id,
            "ingredient_id": sm.ingredient_id,
            "ingredient_name": ing.name if ing else f"#{sm.ingredient_id}",
            "qty": abs(float(sm.qty)),
            "unit": ing.unit if ing else "",
            "affected_recipe_id": sm.affected_recipe_id,
            "recorded_at_str": sm.recorded_at.isoformat() if sm.recorded_at else "—",
        })

    # M1: refund history (newest first for the operator table).
    refund_rows = list_refunds_for(session, "sale", sale_id)
    refunds_total_gs = sum_refunds_for(session, "sale", sale_id)
    sale_total = int(sale.unit_price_gs or 0)
    refunds_remaining_gs = sale_total - refunds_total_gs

    refunds = []
    for r in sorted(refund_rows, key=lambda x: x.recorded_at, reverse=True):
        refunds.append({
            "id": r.id,
            "amount_gs": int(r.amount_gs),
            "payment_method": r.payment_method,
            "restock_qty": bool(r.restock_qty),
            "restocked_qty": float(r.restocked_qty or 0),
            "reason": r.reason,
            "recorded_by": r.recorded_by,
            "recorded_at_str": r.recorded_at.strftime("%Y-%m-%d %H:%M") if r.recorded_at else "—",
        })

    return render(
        request,
        "ventas_detalle.html",
        {
            "sale": _decorated(sale),
            "stock_moves": stock_moves,
            "refunds": refunds,
            "refunds_total_gs": refunds_total_gs,
            "refunds_count": len(refunds),
            "refunds_remaining_gs": refunds_remaining_gs,
        },
    )


@router.get("/{sale_id}/recibo", response_class=HTMLResponse)
async def sale_receipt(
    request: Request,
    sale_id: int,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Printable single-sale receipt for handing to the customer.

    Renders a minimal A6-friendly page with title, date, line, total,
    payment method, and a "thank you" footer. Print stylesheet hides
    the nav. Operator can press ⌘P / Ctrl+P to print or save as PDF.
    """
    sale = session.get(Sale, sale_id)
    if sale is None:
        raise NotFound("venta", id=sale_id)
    # Phase 4 tier 2.2 (2026-10-01): if this sale has a customer AND
    # a ledger row, surface "+X puntos" + "Nuevo saldo: Y" on the
    # receipt. Two queries max; both are FK-indexed so they cost <1ms.
    loyalty_snapshot = None
    if sale.customer_id:
        from app.rms.models import Customer as _Cust, LoyaltyTransaction as _LT
        cust = session.get(_Cust, sale.customer_id)
        if cust is not None:
            earn_row = session.execute(
                select(_LT)
                .where(_LT.sale_id == sale_id)
                .where(_LT.reason == "earn_sale")
                .limit(1)
            ).scalar_one_or_none()
            redeemed_row = session.execute(
                select(_LT)
                .where(_LT.sale_id == sale_id)
                .where(_LT.reason == "redeem")
                .limit(1)
            ).scalar_one_or_none()
            # Ledger rows are signed: earn_sale → positive delta,
            # redeem → negative delta. Surface them to the cashier
            # as absolute point counts so the receipt reads naturally
            # ("canjeaste 5 puntos") instead of (-5).
            earn_abs = int(earn_row.delta) if earn_row else 0
            redeem_abs = -int(redeemed_row.delta) if redeemed_row else 0
            loyalty_snapshot = {
                "customer_name": cust.name or cust.phone or "Cliente",
                "earn_points": earn_abs,
                "redeemed_points": redeem_abs,
                "current_balance": int(cust.loyalty_points or 0),
                # T-2026-10-01: pre-format the discount Gs at the source
                # instead of having the template multiply by a hardcoded
                # 1000. The POINTS_VALUE_GS rate (1 pt = 100 Gs) lives
                # in app/rms/loyalty/ledger.py — change there, not here.
                "redeemed_discount_gs": discount_gs_for_points(redeem_abs),
            }
    return render(
        request,
        "recibo.html",
        {
            "sale": _decorated(sale),
            "loyalty_snapshot": loyalty_snapshot,
            "branding": get_branding(session),
        },
    )


@router.get("/{sale_id:int}", response_class=HTMLResponse)
async def sale_detail(
    request: Request,
    sale_id: int,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Operator-facing full-width detail view for a single sale.

    BACKLOG #16 (2026-10-02): complements the printable A6 receipt
    (/ventas/{sale_id}/recibo) with a normal-width operator page that
    shows product, customer, payment method, channel, void metadata,
    and any loyalty ledger entries tied to the sale. Linkable by URL
    so /ventas/helpdesk tickets can deep-link to a specific sale.
    """
    sale = session.get(Sale, sale_id)
    if sale is None:
        raise NotFound("venta", id=sale_id)

    # Loyalty snapshot (same data shape as the receipt route)
    loyalty_snapshot = None
    if sale.customer_id:
        from app.rms.models import Customer as _Cust, LoyaltyTransaction as _LT
        cust = session.get(_Cust, sale.customer_id)
        if cust is not None:
            earn_row = session.execute(
                select(_LT)
                .where(_LT.sale_id == sale_id)
                .where(_LT.reason == "earn_sale")
                .limit(1)
            ).scalar_one_or_none()
            redeemed_row = session.execute(
                select(_LT)
                .where(_LT.sale_id == sale_id)
                .where(_LT.reason == "redeem")
                .limit(1)
            ).scalar_one_or_none()
            earn_abs = int(earn_row.delta) if earn_row else 0
            redeem_abs = -int(redeemed_row.delta) if redeemed_row else 0
            loyalty_snapshot = {
                "customer_name": cust.name or cust.phone or "Cliente",
                "customer_phone": cust.phone,
                "customer_id": cust.id,
                "earn_points": earn_abs,
                "redeemed_points": redeem_abs,
                "current_balance": int(cust.loyalty_points or 0),
                "redeemed_discount_gs": discount_gs_for_points(redeem_abs),
            }

    # Stock-move audit trail (which ingredients this sale consumed).
    # Two queries max; both FK-indexed.
    stock_moves = session.execute(
        select(StockMovement)
        .where(StockMovement.reference_id == sale_id)
        .where(StockMovement.reference_type == "sale")
    ).scalars().all()

    # Related pedido (if sale came from a pedido fulfillment)
    related_pedido = None
    if sale.linked_pedido_id:
        from app.rms.models import Pedido
        related_pedido = session.get(Pedido, sale.linked_pedido_id)

    return render(
        request,
        "ventas_detalle.html",
        {
            "sale": _decorated(sale),
            "loyalty_snapshot": loyalty_snapshot,
            "stock_moves": stock_moves,
            "related_pedido": related_pedido,
        },
    )


@router.get("/buscar", response_model=None)
def sale_lookup_by_sku(
    request: Request,
    sku: str | None = None,
    session: Session = Depends(get_session),
) -> JSONResponse | dict:
    """Lookup product by SKU for cashier scan flow.

    Returns JSON: {found, product_id, name, sale_price_gs, sku}.
    Used by the scan-to-sell JavaScript handler on /ventas.
    """
    from app.integrations.barcode import get_product_by_sku

    if not sku:
        raise ValidationError(SALE_SKU_REQUIRED, context={"field": "sku"})
    result = get_product_by_sku(session, sku)
    if not result.ok or result.product is None:
        return JSONResponse({"found": False, "sku": sku})
    p = result.product
    return JSONResponse({
        "found": True,
        "product_id": p.id,
        "name": p.name,
        "sale_price_gs": p.sale_price_gs,
        "sku": p.sku,
    })


@router.post("/nueva")
async def sale_create(
    request: Request,
    product_id: int | None = Form(None, gt=0),
    sku: str = Form(""),
    qty: float = Form(..., gt=0),
    payment_method: str = Form(""),
    discount_gs: int = Form(0, ge=0),
    customer_id: int | None = Form(None, gt=0),
    notes: str = Form(""),
    sold_at: str = Form(""),
    channel: str = Form(""),
    idempotency_key: str = Form(""),
    # Phase 1.B — fiscal invoice fields
    invoice_type: str = Form("boleta_resimple"),
    invoice_customer_ruc: str = Form(""),
    invoice_customer_name: str = Form(""),
    # US 4.1 — per-sale packaging (audio: "the box for the cake"). The same
    # product sold to-go vs. eat-in vs. event may need different packaging.
    # Both fields must be set together (or both empty).
    packaging_item_id: int | None = Form(None, gt=0),
    packaging_qty: float | None = Form(None, gt=0),
    # Phase 4 loyalty (2026-10-01): POS redeem flow. When > 0, converts
    # to Gs. discount at 1pt = 1.000 Gs., writes a ledger row tied to
    # the resulting Sale.id, and ADDS the discount to discount_gs below.
    # 0 means "don't redeem"; never negative.
    points_to_redeem: int = Form(0, ge=0),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Create a sale with stock drop.

    Validation: FastAPI's Form(...) enforces types + bounds before this
    handler runs. Bad input → 422.

    Either product_id (manual selection) or sku (barcode scan) is
    required. If sku is given, we look up the product first.
    """
    from app.integrations.barcode import get_product_by_sku
    from app.rms.schemas import ALLOWED_PAYMENT_METHODS, MAX_DISCOUNT_GS, MAX_QTY

    # SKU path: if sku is provided and product_id is not, look up.
    if (not product_id or product_id == 0) and sku:
        result = get_product_by_sku(session, sku)
        if not result.ok or result.product is None:
            raise NotFound(
                "sku",
                context={"sku": sku},
                message=SALE_SKU_NOT_FOUND,
            )
        product_id = result.product.id
    if not product_id:
        raise BadRequest(SALE_PRODUCT_OR_SKU_REQUIRED)

    # Allergen guard (derived-intel engine 3): block sales that put a
    # declared customer allergen in their hands. Hard stop, Spanish detail.
    from app.rms.derived_intel import check_customer_risk
    risk = check_customer_risk(session, customer_id, product_id)
    if not risk.safe:
        raise HTTPException(
            status_code=409,
            detail=(
                f"⚠️ ALÉRGENO: {risk.matched}. El cliente es alérgico. "
                "Confirmá con el cliente antes de vender (quitá la nota de "
                "alergia en /clientes si es un error)."
            ),
        )
    # Form(...) didn't enforce upper bounds here because Form() with `le=`
    # requires a literal value, not a constant. So we re-check explicitly.
    # The 422 path is hit when gt/le/... mismatch happens (handled by
    # FastAPI). For " > MAX_QTY specifically, raise 422 in the route via
    # the same alias — but that's overcomplicated. Keep 400 for these.
    if qty > MAX_QTY:
        raise HTTPException(
            status_code=400,
            detail=SALE_QTY_TOO_HIGH,
            headers={"X-Max-Qty": str(MAX_QTY)},
        )
    if discount_gs > MAX_DISCOUNT_GS:
        raise HTTPException(
            status_code=400,
            detail=SALE_DISCOUNT_TOO_HIGH,
            headers={"X-Max-Discount-Gs": str(MAX_DISCOUNT_GS)},
        )

    # Parse sold_at (defaults to now in Asunción TZ)
    sold_at_raw = sold_at.strip()
    if sold_at_raw:
        try:
            # Form sends "YYYY-MM-DDTHH:MM" (no TZ). Treat as Asunción local.
            naive = datetime.fromisoformat(sold_at_raw)
            sold_at_dt = naive.replace(tzinfo=ASUNCION_TZ).astimezone(ASUNCION_TZ)
        except ValueError as e:
            raise HTTPException(
                status_code=400, detail=SALE_INVALID_DATE
            ) from e
    else:
        sold_at_dt = datetime.now(ASUNCION_TZ)

    # BACKLOG #15 part 2 (2026-10-02): block writes against a closed day.
    # sold_at_dt is Asunción-local; EOD uses the same TZ, so .date()
    # gives us the local day the operator is billing to.
    from app.rms.eod_closed import assert_day_open_or_raise
    try:
        assert_day_open_or_raise(
            session, sold_at_dt.date(), action="sale_insert"
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=f"EOD_CLOSED:{e}")

    # payment_method: optional, must be in ALLOWED_PAYMENT_METHODS if set
    payment_method_clean = payment_method.strip() or None
    if payment_method_clean is not None and payment_method_clean not in ALLOWED_PAYMENT_METHODS:
        raise HTTPException(
            status_code=400,
            detail=SALE_INVALID_PAYMENT_METHOD,
        )

    # channel: optional, must be in ALLOWED_CHANNELS if set.
    # Empty string defaults to CHANNEL_DEFAULT ('mostrador'). Unknown
    # values are rejected so we don't end up with 'bitcoin' rows.
    channel_clean = channel.strip() or CHANNEL_DEFAULT
    if channel_clean not in ALLOWED_CHANNELS:
        raise HTTPException(
            status_code=400,
            detail=SALE_INVALID_CHANNEL,
        )

    notes_clean = notes.strip() or None
    # Verify the customer exists if one was picked. We no longer
    # auto-create-by-phone; the picker modal is the only path to a new
    # customer. A bogus customer_id from a stale form is a 422.
    if customer_id is not None:
        from app.rms.customers import get_customer

        if get_customer(session, customer_id) is None:
            raise HTTPException(
                status_code=400, detail=SALE_CUSTOMER_NOT_FOUND
            )

    # Phase 1.B — Compute fiscal invoice fields BEFORE apply_sale so we can
    # pass them as part of the Sale row creation.
    from app.rms.constants import DEFAULT_INVOICE_TYPE, INVOICE_TYPES
    from app.rms.invoicing import compute_invoice_snapshot
    from app.rms.models import Product as _Product

    invoice_type_clean = (invoice_type or DEFAULT_INVOICE_TYPE).strip()
    if invoice_type_clean not in INVOICE_TYPES:
        invoice_type_clean = DEFAULT_INVOICE_TYPE
    invoice_customer_ruc_clean = (invoice_customer_ruc or "").strip() or None
    invoice_customer_name_clean = (invoice_customer_name or "").strip() or None

    # When invoice_type='factura' and customer_ruc not provided, take from
    # the selected customer (if any).
    if invoice_type_clean == "factura" and not invoice_customer_ruc_clean and customer_id:
        from app.rms.customers import get_customer as _gc
        cust = _gc(session, customer_id)
        if cust:
            invoice_customer_ruc_clean = cust.cedula_ruc or None
            invoice_customer_name_clean = cust.name or None

    # Fetch product to get the real unit price (re-fetched by apply_sale too,
    # but we need it here for the IVA snapshot).
    product = session.get(_Product, product_id)
    unit_price_gs = product.sale_price_gs if product else 0

    snapshot = compute_invoice_snapshot(
        session,
        product_id=product_id,
        qty=qty,
        unit_price_gs=unit_price_gs,
        discount_gs=discount_gs,
        invoice_type=invoice_type_clean,
    )

    # Idempotency: reserve the AppMeta row BEFORE apply_sale runs, so a
    # duplicate POST aborts before creating a second Sale. AppMeta.key is
    # the primary key — duplicate INSERT raises IntegrityError.
    if idempotency_key:
        from sqlalchemy.exc import IntegrityError

        from app.rms.models import AppMeta as _AppMeta
        try:
            session.add(_AppMeta(
                key=f"sale_idem:{idempotency_key}",
                value="pending",  # updated below to str(sale.sale_id)
                updated_at=datetime.now(timezone.utc).isoformat(),
            ))
            session.flush()  # surface IntegrityError without committing
        except IntegrityError:
            session.rollback()
            # Re-fetch on a fresh transaction; the row from the winning
            # request is now visible.
            existing_sale_id = session.scalar(
                select(_AppMeta).where(_AppMeta.key == f"sale_idem:{idempotency_key}")
            )
            return RedirectResponse(
                url=f"/ventas?flash=sale_duplicate&sale_id={existing_sale_id.value}",
                status_code=303,
            )

    # Phase 4 loyalty POS redeem (2026-10-01): when points_to_redeem > 0,
    # convert to Gs. discount (1pt = 1.000 Gs.) and ADD it to discount_gs
    # so it flows through the existing apply_sale path. The ledger row is
    # written AFTER apply_sale returns (we need the real sale_id to FK
    # into). If the customer doesn't have enough points, we raise 400 —
    # we DO NOT silently round down because the cashier typed a number
    # and expects that exact amount to be honored.
    if points_to_redeem > 0:
        if customer_id is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Para canjear puntos necesitás seleccionar un cliente. "
                    "Tocá el buscador de clientes y elegí uno."
                ),
            )
        from app.rms.customers import get_customer as _gc_redeem
        cust_redeem = _gc_redeem(session, customer_id)
        if cust_redeem is None:
            raise HTTPException(status_code=400, detail=SALE_CUSTOMER_NOT_FOUND)
        if (cust_redeem.loyalty_points or 0) < points_to_redeem:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Puntos insuficientes: el cliente tiene "
                    f"{cust_redeem.loyalty_points or 0}, intentás canjear "
                    f"{points_to_redeem}."
                ),
            )
        points_discount_gs = points_to_redeem * 1000
        discount_gs = (discount_gs or 0) + points_discount_gs
        # Re-check the upper bound after adding the points discount.
        if discount_gs > MAX_DISCOUNT_GS:
            raise HTTPException(
                status_code=400,
                detail=SALE_DISCOUNT_TOO_HIGH,
                headers={"X-Max-Discount-Gs": str(MAX_DISCOUNT_GS)},
            )

    try:
        sale = apply_sale(
            session,
            product_id,
            qty,
            sold_at_dt,
            notes_clean,
            customer_id=customer_id,
            payment_method=payment_method_clean,
            discount_gs=discount_gs,
            channel=channel_clean,
            packaging_item_id=packaging_item_id,
            packaging_qty=packaging_qty,
        )
    except RecipeWithoutYield as e:
        raise Conflict(
            "La receta no tiene rendimiento definido; no se puede vender.",
            context={"original_error": str(e)},
        ) from e
    except ValueError as e:
        raise BadRequest(
            "Datos inválidos para registrar la venta.",
            context={"original_error": str(e)},
        ) from e

    # Apply Phase 1.B invoice fields to the just-created Sale
    from app.rms.invoicing import allocate_invoice_number
    invoice_number = None
    if invoice_type_clean != "none":
        invoice_number = allocate_invoice_number(session, invoice_type_clean)
    sale.invoice_type = invoice_type_clean
    sale.invoice_number = invoice_number
    sale.invoice_customer_ruc = invoice_customer_ruc_clean
    sale.invoice_customer_name = invoice_customer_name_clean
    sale.iva_rate = snapshot["iva_rate"]
    sale.iva_base_gs = snapshot["iva_base_gs"]
    sale.iva_amount_gs = snapshot["iva_amount_gs"]

    # Update the idempotency record's value with the real sale_id now that
    # apply_sale returned. The AppMeta row was reserved BEFORE apply_sale
    # (see block above); this UPDATE brings it up to date.
    if idempotency_key:
        from app.rms.models import AppMeta as _AppMeta
        session.execute(
            update(_AppMeta)
            .where(_AppMeta.key == f"sale_idem:{idempotency_key}")
            .values(value=str(sale.sale_id))
        )

    # Loyalty (Phase 4, 2026-10-01): credit points to the customer if one
    # was attached to this sale. Awarded on the POST-discount total
    # (what the customer actually paid = total_price_gs - discount_gs)
    # per industry norm — you earn on what you spent, not sticker price.
    # Void/return reversal is handled by ``reverse_points_for_void``
    # (called from /ventas/{id}/anular).
    if customer_id is not None:
        from app.auth import current_user_id
        from app.rms.customers import get_customer as _get_cust
        from app.rms.loyalty import award_points as _award_points
        from app.rms.models import Sale as _Sale
        cust = _get_cust(session, customer_id)
        if cust is not None:
            # apply_sale() returns an ApplySaleResult dataclass with
            # total_price_gs but NOT discount_gs. The Sale ORM row
            # carries discount_gs (just persisted). Query through the
            # session to get the real discount for this sale.
            sale_row = session.get(_Sale, sale.sale_id)
            discount_for_award = int(sale_row.discount_gs or 0) if sale_row else 0
            net_paid_gs = max(0, int(sale.total_price_gs) - discount_for_award)
            _award_points(
                session,
                cust,
                net_paid_gs,
                sale_id=sale.sale_id,
                actor=str(current_user_id(request) or "operator"),
            )

    # Phase 4 loyalty POS redeem (2026-10-01): if the cashier redeemed
    # points via the inline "Usar puntos" form, write the ledger row NOW
    # (sale.sale_id is now known — redeem_points takes it as a FK). The
    # balance check + discount math already happened above; redeem_points
    # itself is a no-op when points_to_redeem == 0.
    if points_to_redeem > 0 and customer_id is not None:
        from app.auth import current_user_id
        from app.rms.customers import get_customer as _get_cust_redeem
        from app.rms.loyalty import redeem_points as _redeem_points
        cust_redeem = _get_cust_redeem(session, customer_id)
        if cust_redeem is not None:
            _redeem_points(
                session,
                cust_redeem,
                points_to_redeem,
                sale_id=sale.sale_id,
                actor=str(current_user_id(request) or "operator"),
                notes=f"POS redeem en sale #{sale.sale_id}",
            )

    safe_commit(session)

    # Audit + rate-limit (writes only — read paths not counted).
    from app.auth import current_user_id
    from app.rms.audit import record as audit_record
    from app.rms.rate_limit import is_write_rate_limited
    if is_write_rate_limited(session, request, max_per_minute=10):
        raise HTTPException(status_code=429, detail=SALE_RATE_LIMITED)

    audit_record(
        session,
        user_id=current_user_id(request) or "operator",
        action="write.sale.create",
        request=request,
        detail={"product_id": product_id, "qty": qty, "discount_gs": discount_gs, "channel": channel_clean},
    )

    # Update the idempotency record's value with the real sale_id AND
    # request_id, so duplicate-POST forensics can correlate the two
    # requests via the access log. Value is JSON-encoded for forward
    # compatibility (we may add more fields later).
    #
    # This is a SECOND commit, but the AppMeta row was already persisted
    # in the first commit (along with the Sale), so a retry immediately
    # sees the idem record and aborts via IntegrityError.
    if idempotency_key:
        import json

        from app.rms.models import AppMeta as _AppMeta
        request_id = getattr(request.state, "request_id", None) or ""
        payload = json.dumps({
            "sale_id": str(sale.sale_id),
            "request_id": request_id,
        })
        session.execute(
            update(_AppMeta)
            .where(_AppMeta.key == f"sale_idem:{idempotency_key}")
            .values(value=payload)
        )

    safe_commit(session)

    # Best-effort: fire the printer with the new receipt.
    # Failures are logged but never block the sale.
    _fire_printer_for_sale(session, request, product_id, qty, discount_gs, payment_method_clean, notes_clean)

    # If points were redeemed at the till, append a flash token so the
    # operator sees the confirmation toast. ``points_redeemed_pos:N:D``
    # tells the JS renderer "N puntos canjeados por D Gs. de descuento".
    # Reusing the existing points_redeemed prefix means the
    # flash_toast macro in _components/atoms.html handles it (with
    # the new _pos suffix to distinguish it from /clientes/{id} redeem).
    if points_to_redeem > 0:
        return RedirectResponse(
            url=f"/ventas?flash=sale_created&points_flash={points_to_redeem}:{points_to_redeem * 1000}",
            status_code=303,
        )
    return RedirectResponse(url="/ventas?flash=sale_created", status_code=303)


# ── Multi-item cart endpoint ────────────────────────────────────────────────

@router.post("/nueva/multi")
async def sale_create_multi(
    request: Request,
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Create a sale with multiple line items from the POS cart.

    Accepts a JSON body::
        {
          "items": [{"product_id": int, "qty": float}, ...],
          "customer_id": int | null,
          "payment_method": str,
          "channel": str,
          "discount_gs": int,
          "notes": str,
          "sold_at": str,
          "invoice_type": str,
          "invoice_customer_ruc": str,
          "invoice_customer_name": str,
          "idempotency_key": str,
        }

    All metadata (customer, payment, invoice, etc.) applies to the
    parent sale only. Each item gets its own stock_movement rows via
    repeated apply_sale() calls within one transaction.
    """
    from pydantic import BaseModel, Field

    from app.rms.schemas import ALLOWED_PAYMENT_METHODS, MAX_DISCOUNT_GS, MAX_QTY

    class _Item(BaseModel):
        product_id: int = Field(..., gt=0)
        qty: float = Field(..., gt=0)
        discount_pct: float = Field(0, ge=0, le=100)  # per-item % discount
        unit_price_gs: int | None = Field(None, ge=0, le=999_999_999)  # E13.S2 cashier override

    class _Body(BaseModel):
        items: list[_Item] = Field(..., min_length=1)
        customer_id: int | None = Field(None, gt=0)
        payment_method: str = Field("")
        discount_gs: int = Field(0, ge=0)
        # Phase 4 loyalty (2026-10-01): POS redeem on multi-sale. Same
        # semantics as /ventas/nueva — converts to Gs. discount (1pt =
        # 1.000 Gs.), ADDS to discount_gs, writes a ledger row tied
        # to the first sale_id after apply_sale runs. 0 = no redeem.
        points_to_redeem: int = Field(0, ge=0)
        notes: str = Field("")
        sold_at: str = Field("")
        channel: str = Field("")
        idempotency_key: str = Field("")
        invoice_type: str = Field("boleta_resimple")
        invoice_customer_ruc: str = Field("")
        invoice_customer_name: str = Field("")

    try:
        body = _Body.model_validate(await request.json())
    except Exception:  # noqa: BLE001 — defensive default
        raise HTTPException(status_code=400, detail=SALE_BODY_INVALID) from None

    items = body.items
    if len(items) > 50:
        raise HTTPException(status_code=400, detail=SALE_TOO_MANY_ITEMS)

    for item in items:
        # SALES-VAL-003: discrete baked goods — reject fractional quantities
        # server-side so even a hand-crafted POST can't sneak 1.5 in.
        # Math.floor(parseFloat(...)) with a check on the raw int parses
        # the float exactly — 1.0 == 1 is true, 1.5 != 1 so it rejects.
        if item.qty != int(item.qty):
            raise HTTPException(
                status_code=400,
                detail="Cantidad debe ser un número entero (sin decimales).",
            )
        if item.qty > MAX_QTY:
            raise HTTPException(
                status_code=400,
                detail=SALE_QTY_TOO_HIGH,
                headers={"X-Max-Qty": str(MAX_QTY)},
            )

    # ── Sold-at ──────────────────────────────────────────────────────────
    sold_at_raw = body.sold_at.strip()
    if sold_at_raw:
        try:
            naive = datetime.fromisoformat(sold_at_raw)
            sold_at_dt = naive.replace(tzinfo=ASUNCION_TZ).astimezone(ASUNCION_TZ)
        except ValueError as e:
            raise HTTPException(
                status_code=400, detail=SALE_INVALID_DATE
            ) from e
    else:
        sold_at_dt = datetime.now(ASUNCION_TZ)

    # BACKLOG #15 part 2 (2026-10-02): block writes against a closed day.
    from app.rms.eod_closed import assert_day_open_or_raise
    try:
        assert_day_open_or_raise(
            session, sold_at_dt.date(), action="sale_insert_multi"
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=f"EOD_CLOSED:{e}")

    # ── Customer ──────────────────────────────────────────────────────────
    customer_id = body.customer_id
    if customer_id is not None:
        from app.rms.customers import get_customer
        if get_customer(session, customer_id) is None:
            raise HTTPException(
                status_code=400, detail=SALE_CUSTOMER_NOT_FOUND
            )

    # ── Payment ───────────────────────────────────────────────────────────
    # PRO-POS (2026-09-30): silent-None payment_method flooded the ledger
    # with NULLs (699/708 sales unattributed). Fall back to the default
    # method (is_default → 'efectivo') so every sale carries a method.
    payment_method_clean = body.payment_method.strip() or default_payment_method_code(session)
    if payment_method_clean not in ALLOWED_PAYMENT_METHODS:
        raise HTTPException(
            status_code=400,
            detail=SALE_INVALID_PAYMENT_METHOD,
        )

    channel_clean = body.channel.strip() or CHANNEL_DEFAULT
    if channel_clean not in ALLOWED_CHANNELS:
        raise HTTPException(
            status_code=400,
            detail=SALE_INVALID_CHANNEL,
        )

    notes_clean = body.notes.strip() or None
    discount_gs = body.discount_gs
    points_to_redeem = body.points_to_redeem

    # Phase 4 loyalty POS redeem (2026-10-01, multi-sale variant):
    # Same validation as /ventas/nueva. Customer required, balance
    # sufficient, combined discount ≤ MAX_DISCOUNT_GS. 400 on each
    # failure with a Spanish message. Then add points × 1000 to
    # discount_gs so the existing path picks it up.
    if points_to_redeem > 0:
        if customer_id is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Para canjear puntos necesitás seleccionar un cliente. "
                    "Tocá el buscador de clientes y elegí uno."
                ),
            )
        from app.rms.customers import get_customer as _gc_redeem
        cust_redeem = _gc_redeem(session, customer_id)
        if cust_redeem is None:
            raise HTTPException(status_code=400, detail=SALE_CUSTOMER_NOT_FOUND)
        if (cust_redeem.loyalty_points or 0) < points_to_redeem:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Puntos insuficientes: el cliente tiene "
                    f"{cust_redeem.loyalty_points or 0}, intentás canjear "
                    f"{points_to_redeem}."
                ),
            )
        discount_gs = discount_gs + (points_to_redeem * 1000)

    if discount_gs > MAX_DISCOUNT_GS:
        raise HTTPException(
            status_code=400,
            detail=SALE_DISCOUNT_TOO_HIGH,
            headers={"X-Max-Discount-Gs": str(MAX_DISCOUNT_GS)},
        )

    # ── Invoice ───────────────────────────────────────────────────────────
    from app.rms.constants import DEFAULT_INVOICE_TYPE, INVOICE_TYPES
    invoice_type_clean = (body.invoice_type or DEFAULT_INVOICE_TYPE).strip()
    if invoice_type_clean not in INVOICE_TYPES:
        invoice_type_clean = DEFAULT_INVOICE_TYPE
    invoice_customer_ruc_clean = (body.invoice_customer_ruc or "").strip() or None
    invoice_customer_name_clean = (body.invoice_customer_name or "").strip() or None

    if invoice_type_clean == "factura" and not invoice_customer_ruc_clean and customer_id:
        from app.rms.customers import get_customer as _gc
        cust = _gc(session, customer_id)
        if cust:
            invoice_customer_ruc_clean = cust.cedula_ruc or None
            invoice_customer_name_clean = cust.name or None

    # ── Idempotency ───────────────────────────────────────────────────────
    idempotency_key = body.idempotency_key
    if idempotency_key:
        from sqlalchemy.exc import IntegrityError

        from app.rms.models import AppMeta as _AppMeta
        try:
            session.add(_AppMeta(
                key=f"sale_multi_idem:{idempotency_key}",
                value="pending",
                updated_at=datetime.now(timezone.utc).isoformat(),
            ))
            session.flush()
        except IntegrityError:
            session.rollback()
            return RedirectResponse(
                url="/ventas?flash=sale_duplicate",
                status_code=303,
            )

    # ── Apply each item (one transaction) ─────────────────────────────────
    sale_ids: list[int] = []
    first_product_id: int | None = None

    try:
        for idx, item in enumerate(items):
            # Allergen guard
            from app.rms.derived_intel import check_customer_risk
            risk = check_customer_risk(session, customer_id, item.product_id)
            if not risk.safe:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"⚠️ ALÉRGENO: {risk.matched}. "
                        "El cliente es alérgico a un producto de esta venta."
                    ),
                )

            # Fetch product price for discount calculation
            product = session.get(Product, item.product_id)
            catalog_price = product.sale_price_gs if product else 0
            # E13.S2 — accept cashier price override for venta libre / misc
            # sales. Falls back to the catalog price when the client doesn't
            # send one. Sale.unit_price_gs is already a snapshot column so
            # the override is safe to persist.
            unit_price = (
                item.unit_price_gs
                if item.unit_price_gs is not None and item.unit_price_gs > 0
                else catalog_price
            )

            # All items in the cart share the same metadata (customer, payment, channel)
            # Phase 14 #20: discount math uses Decimal (NOT float) so a huge
            # qty or unit_price can't trigger float overflow. discount_pct
            # is already Pydantic-bounded to [0, 100] at line 1028, so
            # the discount can never exceed the line subtotal.
            from app.rms.money import to_decimal

            subtotal_gs = int(
                (to_decimal(item.qty) * to_decimal(unit_price))
                .quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            )
            line_discount_gs = int(
                (
                    to_decimal(item.qty)
                    * to_decimal(unit_price)
                    * to_decimal(item.discount_pct or 0)
                    / to_decimal(100)
                ).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            )
            result = apply_sale(
                session,
                item.product_id,
                item.qty,
                sold_at_dt,
                notes_clean,
                customer_id=customer_id,
                payment_method=payment_method_clean,
                discount_gs=line_discount_gs,
                channel=channel_clean,
                unit_price_gs_override=unit_price if item.unit_price_gs else None,
            )
            if first_product_id is None:
                first_product_id = item.product_id

            # Attach invoice fields to the first sale only
            if idx == 0:
                from app.rms.invoicing import allocate_invoice_number, compute_invoice_snapshot
                product = session.get(Product, item.product_id)
                # E13.S2 — invoice snapshot must reflect the cashier-typed
                # price (when present) so the IVA base matches what the
                # cashier sold at.
                snapshot = compute_invoice_snapshot(
                    session,
                    product_id=item.product_id,
                    qty=item.qty,
                    unit_price_gs=unit_price,
                    discount_gs=discount_gs,
                    invoice_type=invoice_type_clean,
                )
                first_sale = session.get(Sale, result.sale_id)
                if first_sale:
                    if invoice_type_clean != "none":
                        first_sale.invoice_number = allocate_invoice_number(session, invoice_type_clean)
                    first_sale.invoice_type = invoice_type_clean
                    first_sale.invoice_customer_ruc = invoice_customer_ruc_clean
                    first_sale.invoice_customer_name = invoice_customer_name_clean
                    first_sale.iva_rate = snapshot["iva_rate"]
                    first_sale.iva_base_gs = snapshot["iva_base_gs"]
                    first_sale.iva_amount_gs = snapshot["iva_amount_gs"]

    except RecipeWithoutYield as e:
        raise Conflict(
            "La receta no tiene rendimiento definido; no se puede vender.",
            context={"original_error": str(e)},
        ) from e
    except ValueError as e:
        raise BadRequest(
            "Datos inválidos para registrar la venta.",
            context={"original_error": str(e)},
        ) from e

    # Update idempotency record
    if idempotency_key:
        import json

        from app.rms.models import AppMeta as _AppMeta
        request_id = getattr(request.state, "request_id", None) or ""
        session.execute(
            update(_AppMeta)
            .where(_AppMeta.key == f"sale_multi_idem:{idempotency_key}")
            .values(value=json.dumps({"sale_ids": sale_ids, "request_id": request_id}))
        )

    # Loyalty (Phase 4, 2026-10-01): credit points on the sum of all
    # POST-DISCOUNT totals across the multi-line cart. One ledger row
    # (earn_sale) per invoice — fk'd to the first sale.id. Then write
    # the redeem row (if any) so the ledger stays consistent.
    if customer_id is not None and sale_ids:
        from app.auth import current_user_id
        from app.rms.customers import (
            award_points as _award_points,
            get_customer as _get_cust,
            redeem_points as _redeem_points,
        )
        from app.rms.models import Sale as _Sale
        cust = _get_cust(session, customer_id)
        if cust is not None:
            # Sum per-line GROSS, then subtract the per-line discount
            # (the discount_pct × qty × unit_price that apply_sale
            # stored on each Sale row). The remaining is what the
            # customer actually paid — what we earn on.
            rows = session.execute(
                select(_Sale).where(_Sale.id.in_(sale_ids))
            ).scalars().all()
            net_paid_gs = sum(
                max(0, int(r.total_price_gs) - int(r.discount_gs or 0))
                for r in rows
            )
            _award_points(
                session,
                cust,
                net_paid_gs,
                sale_id=sale_ids[0],
                actor=str(current_user_id(request) or "operator"),
            )
            if points_to_redeem > 0:
                _redeem_points(
                    session,
                    cust,
                    points_to_redeem,
                    sale_id=sale_ids[0],
                    actor=str(current_user_id(request) or "operator"),
                    notes=f"POS redeem en sale multi #{sale_ids[0]}",
                )

    safe_commit(session)

    # Rate-limit + audit
    from app.auth import current_user_id
    from app.rms.audit import record as audit_record
    from app.rms.rate_limit import is_write_rate_limited
    if is_write_rate_limited(session, request, max_per_minute=10):
        raise HTTPException(status_code=429, detail=SALE_RATE_LIMITED)

    audit_record(
        session,
        user_id=current_user_id(request) or "operator",
        action="write.sale.create_multi",
        request=request,
        detail={"item_count": len(items), "sale_ids": sale_ids},
    )

    return _redirect_with_loyalty_flash(
        "/ventas?flash=sale_created",
        points_to_redeem=points_to_redeem,
    )


def _redirect_with_loyalty_flash(
    base_url: str,
    points_to_redeem: int,
) -> RedirectResponse:
    """Append the points_flash=N:D query param if points were redeemed.

    Phase 4 loyalty (2026-10-01): lets the flash_toast macro in
    _components/atoms.html render the same success toast as the
    Quick-Sell path. Returns the base URL unchanged when no redeem
    happened, so the existing ``flash=sale_created`` UX is intact.
    """
    if points_to_redeem <= 0:
        return RedirectResponse(url=base_url, status_code=303)
    sep = "&" if "?" in base_url else "?"
    return RedirectResponse(
        url=f"{base_url}{sep}points_flash={points_to_redeem}:{points_to_redeem * 1000}",
        status_code=303,
    )


def _fire_printer_for_sale(
    session: Session,
    request: Request,
    product_id: int,
    qty: float,
    discount_gs: int,
    payment_method: str | None,
    notes: str | None,
) -> None:
    """Send a receipt to the configured printer. Best-effort.

    Module-level imports so tests can monkeypatch the printer.
    """
    from app.rms.models import Product, Sale
    from app.integrations.printer import (
        config_from_env,
        format_receipt_text,
        send_to_printer,
    )

    try:
        sale_product = session.get(Product, product_id)
        if sale_product is None:
            return
        last_sale = (
            session.query(Sale)
            .filter(Sale.product_id == product_id)
            .order_by(Sale.id.desc())
            .first()
        )
        sale_id = last_sale.id if last_sale else 0
        receipt = format_receipt_text(
            business_name="Saskia RMS",
            sale_id=sale_id,
            product_name=sale_product.name,
            qty=qty,
            unit_price_gs=sale_product.sale_price_gs,
            total_gs=int(qty * sale_product.sale_price_gs - discount_gs),
        )
        try:
            cfg = config_from_env()
            send_to_printer(receipt.encode("utf-8"), cfg)
        except Exception:  # noqa: BLE001 — defensive default
            from loguru import logger
            logger.warning("printer send failed (non-fatal)")
    except Exception as exc:  # noqa: BLE001 — defensive default
        from loguru import logger
        logger.warning(f"printer trigger skipped: {exc!r}")


@router.post("/{sale_id}/anular")
async def sale_void(
    sale_id: int,
    request: Request,
    reason: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Void a sale and reverse stock.

    CIE-01: accepts an optional ``reason`` form field (free text) and the
    authenticated user id, both persisted on Sale.void_reason /
    Sale.voided_by for audit. The modal that triggers this POST lives on
    /ventas/historial; legacy callers that POST without a reason still
    work — the void just records no reason.
    """
    from app.auth import current_user_id

    # Loyalty (Phase 4, 2026-10-01): if this sale earned points, reverse
    # them BEFORE void_sale runs so the ledger stays consistent with the
    # cached balance. ``reverse_points_for_void`` is a no-op if no earn
    # rows exist for this sale_id (defensive: only the original earn is
    # reversed, not subsequent unrelated redemptions).
    try:
        from app.rms.models import Sale as _Sale
        from app.rms.customers import get_customer as _get_cust_void
        from app.rms.loyalty import reverse_points_for_void
        _sale_row = session.get(_Sale, sale_id)
        if _sale_row and _sale_row.customer_id:
            _cust_void = _get_cust_void(session, _sale_row.customer_id)
            if _cust_void is not None:
                reverse_points_for_void(
                    session,
                    _cust_void,
                    sale_id=sale_id,
                    actor=str(current_user_id(request) or "operator"),
                )
                session.flush()
    except Exception as _loyalty_void_exc:  # noqa: BLE001
        from loguru import logger as _logger
        _logger.warning("loyalty void-reversal failed for sale {}: {}", sale_id, _loyalty_void_exc)

    try:
        uid = current_user_id(request)
        user_id = str(uid) if uid is not None else "operator"
        reason_clean = (reason or "").strip() or None
        void_sale(session, sale_id, reason=reason_clean, voided_by=user_id)
    except ValueError as e:
        # P0 cerrar-puertas: dedicated message for void-after-EOD-close.
        # The domain layer raises `void_after_eod_close:<iso_date>` when the
        # sale belongs to a day whose EOD has been completed. Operators see
        # the clean Spanish message; the audit log retains the original.
        err = str(e)
        if err.startswith("void_after_eod_close:"):
            sale_date_iso = err.split(":", 1)[1]
            raise Conflict(
                f"No se puede anular esta venta: el día {sale_date_iso} ya fue cerrado.",
                context={"sale_id": str(sale_id), "sale_date": sale_date_iso, "eod_status": "closed"},
            ) from e
        raise Conflict(
            "No se puede anular la venta.",
            context={"sale_id": str(sale_id), "original_error": err},
        ) from e
    # Forensic completeness: the void must leave an audit-log row, not just
    # the sale's own void_* columns (found by the tests/e2e audit-sweep —
    # every other mutation writes one, voids silently didn't).
    try:
        from app.rms.observability import record_audit

        record_audit(
            request, session=session,
            action="write.sale.void", target_type="sale", target_id=sale_id,
            detail={"reason": reason_clean, "voided_by": user_id},
        )
        session.commit()  # void_sale already committed; the audit row needs its own
    except Exception as exc:  # best-effort: never block the void  # noqa: BLE001
        from loguru import logger as _logger

        _logger.warning("audit for void sale {} failed: {}", sale_id, exc)
    return RedirectResponse(url="/ventas/historial?flash=sale_void_ok", status_code=303)


__all__ = ["router", "public_router"]


# --- BACKLOG #17: /ventas/{id}/share (auth) + /r/{token} (public) ------------
# Operator-only POST that issues a fresh public_token (and 30-day expiry),
# then redirects to the detail page with the URL surfaced in the flash
# banner. The token is regenerated on every call — operators can rotate by
# clicking "Compartir" again, which immediately invalidates the prior URL.


@router.post("/{sale_id}/share")
def share_sale_recibo(
    request: Request,
    sale_id: int,
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Generate (or rotate) a public digital-recibo link for this sale.

    On success, redirect back to the detail page with the URL in the
    query string so the template can show a copy-paste box. We use a
    redirect-after-POST pattern so refresh doesn't re-issue the token.
    """
    sale = session.get(Sale, sale_id)
    if sale is None:
        raise NotFound("venta", id=sale_id)

    from app.rms.public_tokens import issue_token

    token, expires_at = issue_token()
    sale.public_token = token
    sale.public_token_expires_at = expires_at
    sale.public_token_shared_at = datetime.now(timezone.utc)
    safe_commit(session)

    # Audit the share issuance for forensics.
    try:
        audit_record(
            session,
            user_id=None,
            action="write.sale.share",
            request=request,
            target_type="sale",
            target_id=str(sale_id),
            detail={"public_token_suffix": token[-4:], "expires_at": expires_at.isoformat()},
        )
        session.commit()
    except Exception:  # noqa: BLE001 — audit best-effort
        session.rollback()

    public_url = f"/r/{token}"
    return RedirectResponse(
        url=f"/ventas/{sale_id}?shared=1&url={public_url}",
        status_code=303,
    )


@public_router.get("/r/{token}", response_class=HTMLResponse)
def public_recibo(request: Request, token: str) -> HTMLResponse:
    """Public, no-auth digital-recibo page rendered for the customer.

    Used as a WhatsApp-shareable link so the customer can re-open their
    receipt at home ("mi número de venta / cliente / tems"). Mirrors
    public_pedido exactly: same token shape, same 30-day expiry, same
    rate-limit and audit hooks.
    """
    with request.app.state.session_factory() as session:
        # Cheap first — rate-limit before the DB hit. Shared helper
        # delegates to AuditLog.action == "public.recibo.view" counting
        # so /r/{token} and /p/{token} use the same enforcement shape.
        public_token_enforce_rate_limit(
            request, session, action_label="public.recibo.view"
        )

        # Sale.id is int PK; look up by public_token so /r/{token} resolves
        # to the sale that owns it. Same shape as public_pedido.
        sale = session.execute(
            select(Sale)
            .where(Sale.public_token == token)
            .options(selectinload(Sale.product), selectinload(Sale.customer))
        ).scalar_one_or_none()
        if sale is None:
            raise HTTPException(
                status_code=404, detail="Recibo no encontrado"
            )

        # 410 Gone (not 404) for expired tokens — the customer should
        # understand the link aged out, not that the sale never existed.
        if not is_token_valid(sale.public_token_expires_at):
            raise HTTPException(
                status_code=410,
                detail=(
                    "Este link venció. Pedile a la panadería que te mande "
                    "uno nuevo."
                ),
            )

        # Audit the view for forensics + rate-limit counting.
        audit_record(
            session,
            user_id=None,
            action="public.recibo.view",
            request=request,
            target_type="sale",
            target_id=str(sale.id),
            detail={"public_token_suffix": token[-4:]},
        )
        try:
            session.commit()
        except Exception:  # noqa: BLE001 — audit best-effort
            session.rollback()

        # Reuse the same recibo.html template the cashier sees. The
        # public_mode flag hides nav chrome and the "back to history"
        # button so the customer sees a clean receipt, but keeps the
        # print stylesheet so they can save as PDF.
        loyalty_snapshot = None
        if sale.customer_id:
            from app.rms.models import Customer as _Cust, LoyaltyTransaction as _LT

            cust = session.get(_Cust, sale.customer_id)
            if cust is not None:
                earn_row = session.execute(
                    select(_LT)
                    .where(_LT.sale_id == sale.id)
                    .where(_LT.reason == "earn_sale")
                    .limit(1)
                ).scalar_one_or_none()
                redeemed_row = session.execute(
                    select(_LT)
                    .where(_LT.sale_id == sale.id)
                    .where(_LT.reason == "redeem")
                    .limit(1)
                ).scalar_one_or_none()
                earn_abs = int(earn_row.delta) if earn_row else 0
                redeem_abs = -int(redeemed_row.delta) if redeemed_row else 0
                loyalty_snapshot = {
                    "customer_name": cust.name or cust.phone or "Cliente",
                    "earn_points": earn_abs,
                    "redeemed_points": redeem_abs,
                    "current_balance": int(cust.loyalty_points or 0),
                    "redeemed_discount_gs": discount_gs_for_points(redeem_abs),
                }

        return render(
            request,
            "recibo.html",
            {
                "sale": _decorated(sale),
                "loyalty_snapshot": loyalty_snapshot,
                "public_mode": True,
            },
        )
