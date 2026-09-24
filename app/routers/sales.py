"""app/routers/sales.py — Sale entry, history, void.

Per dev plan §9 Task 5.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi import Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.auth import require_login_or_disabled as require_login
from app.rms.config import ASUNCION_TZ
from app.rms.costing import RecipeWithoutYield, apply_sale, void_sale
from app.rms.dependencies import get_session
from app.rms.models import Customer, Product, Sale
from app.rms.schemas import (
    ALLOWED_CHANNELS,
    CHANNELS_DISPLAY,
    CHANNEL_DEFAULT,
    PAYMENT_METHODS_DISPLAY,
    PAYMENT_METHOD_DEFAULT,
)
from app.services.template_render import render
from app.rms.money import to_int_gs
from decimal import Decimal

router = APIRouter(prefix="/ventas", dependencies=[Depends(require_login)])


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
        "discount_gs": s.discount_gs,
        "channel": s.channel or "mostrador",
    }


def _generate_idem_key() -> str:
    """Generate a per-render idempotency key for the sale form.

    Server-side UUID so the template doesn't have to call Jinja2's
    `|random` filter (which doesn't exist in stock Jinja2 — only with
    the django-jinja extra). UUIDs are 12 hex chars, same shape the
    template was building with `range(1000000)|random|string`.
    """
    return uuid.uuid4().hex[:12]




def _get_tax_regime(session) -> str:
    """Return the configured tax_regime from ComplianceInfo. Defaults to 'resimple'."""
    from app.rms.models import ComplianceInfo
    ci = session.get(ComplianceInfo, 1)
    return ci.tax_regime if ci else "resimple"


def _build_sales_context(
    request: Request,
    q: str | None,
    product_id: int | None,
    days: int | None,
    offset: int | None,
    session: Session,
) -> dict:
    """Build the render context shared by /ventas and /ventas/historial.

    Computes products, filtered sales page, summary totals, and Quick-Sell
    top-5 in one pass. Both routes call this then render a different
    template (ventas.html for the POS, ventas_historial.html for history)
    so the filter logic stays in sync — US 4.3 split.
    """
    PAGE_SIZE = 20
    products = session.scalars(select(Product).order_by(Product.name)).all()
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
            })

    return {
        "products": products,
        "sales": [_decorated(s) for s in sales_page],
        "quick_sell": quick_sell,
        "q": q or "",
        "product_id": product_id or "",
        "days": days,
        "products_filtered": products,  # alias used by historial.html
        "now_local": datetime.now(ASUNCION_TZ).strftime("%Y-%m-%dT%H:%M"),
        "idem_key": _generate_idem_key(),
        # Phase 1.B — pass tax regime so the form defaults the invoice type
        "tax_regime": _get_tax_regime(session),
        "payment_methods": list(PAYMENT_METHODS_DISPLAY),
        "payment_method_default": PAYMENT_METHOD_DEFAULT,
        "channels": list(CHANNELS_DISPLAY),
        "channel_default": CHANNEL_DEFAULT,
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
    }


@router.get("", response_class=HTMLResponse)
async def sales_list(
    request: Request,
    q: str | None = None,
    product_id: int | None = None,
    days: int | None = None,
    offset: int | None = None,
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
    )
    return render(request, "ventas.html", ctx)


@router.get("/historial", response_class=HTMLResponse)
async def sales_history(
    request: Request,
    q: str | None = None,
    product_id: int | None = None,
    days: int | None = None,
    offset: int | None = None,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Sales history (US 4.3 split).

    Shares query logic with sales_list via _build_sales_context so the
    filter semantics stay in sync. Renders ventas_historial.html which
    shows the summary card, filter form, table of past sales, and the
    per-row Anular button.
    """
    ctx = _build_sales_context(
        request=request,
        session=session,
        q=q,
        product_id=product_id,
        days=days,
        offset=offset,
    )
    return render(request, "ventas_historial.html", ctx)


def _filter_summary(q, product_id, days, products):
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


def _build_filtered_sales_query(q, product_id, days):
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
    rows = session.scalars(sales_q).all()

    import csv
    import io

    buf = io.StringIO()
    # UTF-8 BOM — Excel reads this as "UTF-8 with BOM" and renders accents.
    buf.write("\ufeff")
    writer = csv.writer(buf)
    writer.writerow([
        "fecha", "producto", "cantidad", "precio_unitario_gs",
        "total_gs", "telefono_cliente", "forma_pago",
        "anulada", "notas", "canal",
    ])
    for s in rows:
        writer.writerow([
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
        ])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="ventas.csv"',
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
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    return render(
        request,
        "recibo.html",
        {
            "sale": _decorated(sale),
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
    from app.rms.barcode import get_product_by_sku

    if not sku:
        raise HTTPException(status_code=422, detail="sku requerido")
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
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Create a sale with stock drop.

    Validation: FastAPI's Form(...) enforces types + bounds before this
    handler runs. Bad input → 422.

    Either product_id (manual selection) or sku (barcode scan) is
    required. If sku is given, we look up the product first.
    """
    from app.rms.barcode import get_product_by_sku
    from app.rms.schemas import ALLOWED_PAYMENT_METHODS, MAX_DISCOUNT_GS, MAX_QTY

    # SKU path: if sku is provided and product_id is not, look up.
    if (not product_id or product_id == 0) and sku:
        result = get_product_by_sku(session, sku)
        if not result.ok or result.product is None:
            raise HTTPException(
                status_code=404,
                detail=f"SKU no encontrado: {sku!r}",
            )
        product_id = result.product.id
    if not product_id:
        raise HTTPException(
            status_code=400,
            detail="Elegí un producto o escaneá un SKU",
        )
    # Form(...) didn't enforce upper bounds here because Form() with `le=`
    # requires a literal value, not a constant. So we re-check explicitly.
    # The 422 path is hit when gt/le/... mismatch happens (handled by
    # FastAPI). For " > MAX_QTY specifically, raise 422 in the route via
    # the same alias — but that's overcomplicated. Keep 400 for these.
    if qty > MAX_QTY:
        raise HTTPException(
            status_code=400,
            detail=f"cantidad no puede ser mayor a {MAX_QTY}",
        )
    if discount_gs > MAX_DISCOUNT_GS:
        raise HTTPException(
            status_code=400,
            detail=f"descuento no puede ser mayor a {MAX_DISCOUNT_GS} Gs.",
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
                status_code=400, detail=f"Fecha inválida: {sold_at_raw!r}"
            ) from e
    else:
        sold_at_dt = datetime.now(ASUNCION_TZ)

    # payment_method: optional, must be in ALLOWED_PAYMENT_METHODS if set
    payment_method_clean = payment_method.strip() or None
    if payment_method_clean is not None and payment_method_clean not in ALLOWED_PAYMENT_METHODS:
        raise HTTPException(
            status_code=400,
            detail=f"Forma de pago inválida. Permitidas: {sorted(ALLOWED_PAYMENT_METHODS)}",
        )

    # channel: optional, must be in ALLOWED_CHANNELS if set.
    # Empty string defaults to CHANNEL_DEFAULT ('mostrador'). Unknown
    # values are rejected so we don't end up with 'bitcoin' rows.
    channel_clean = channel.strip() or CHANNEL_DEFAULT
    if channel_clean not in ALLOWED_CHANNELS:
        raise HTTPException(
            status_code=400,
            detail=f"Canal inválido. Permitidos: {sorted(ALLOWED_CHANNELS)}",
        )

    notes_clean = notes.strip() or None
    # Verify the customer exists if one was picked. We no longer
    # auto-create-by-phone; the picker modal is the only path to a new
    # customer. A bogus customer_id from a stale form is a 422.
    if customer_id is not None:
        from app.rms.customers import get_customer

        if get_customer(session, customer_id) is None:
            raise HTTPException(
                status_code=400, detail=f"cliente {customer_id} no existe"
            )

    # Phase 1.B — Compute fiscal invoice fields BEFORE apply_sale so we can
    # pass them as part of the Sale row creation.
    from app.rms.models import ComplianceInfo, Product as _Product
    from app.rms.invoicing import compute_invoice_snapshot

    invoice_type_clean = (invoice_type or "boleta_resimple").strip()
    if invoice_type_clean not in {"boleta_resimple", "factura", "none"}:
        invoice_type_clean = "boleta_resimple"
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
        raise HTTPException(status_code=409, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

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
    session.commit()

    # Audit + rate-limit (writes only — read paths not counted).
    from app.auth import current_user_id
    from app.rms.audit import record as audit_record
    from app.rms.rate_limit import is_write_rate_limited
    if is_write_rate_limited(session, request, max_per_minute=10):
        raise HTTPException(status_code=429, detail="Demasiadas ventas en 1 minuto. Esperá un momento.")

    # Idempotency: if the form was submitted twice with the same key, return
    # the original sale's redirect URL instead of creating a duplicate.
    # The key is a per-form UUID generated by the template's hidden input.
    if idempotency_key:
        from app.rms.models import AppMeta
        existing_sale_id = session.scalar(
            select(AppMeta).where(AppMeta.key == f"sale_idem:{idempotency_key}")
        )
        if existing_sale_id:
            return RedirectResponse(
                url=f"/ventas?flash=sale_duplicate&sale_id={existing_sale_id.value}",
                status_code=303,
            )

    audit_record(
        session,
        user_id=current_user_id(request) or "operator",
        action="write.sale.create",
        request=request,
        detail={"product_id": product_id, "qty": qty, "discount_gs": discount_gs, "channel": channel_clean},
    )
    session.commit()

    # Best-effort: fire the printer with the new receipt.
    # Failures are logged but never block the sale.
    _fire_printer_for_sale(session, request, product_id, qty, discount_gs, payment_method_clean, notes_clean)

    # Store idempotency key AFTER successful commit so retries return the
    # same redirect instead of doubling the sale.
    if idempotency_key:
        try:
            sale_id_str = str(getattr(_fire_printer_for_sale, "_last_sale_id", "") or "")
            session.add(AppMeta(
                key=f"sale_idem:{idempotency_key}",
                value=sale_id_str or idempotency_key,
                updated_at=datetime.now(timezone.utc).isoformat(),
            ))
            session.commit()
        except Exception:
            session.rollback()

    return RedirectResponse(url="/ventas?flash=sale_created", status_code=303)


def _fire_printer_for_sale(
    session,
    request,
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
    from app.rms.printer import (
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
        except Exception:
            from loguru import logger
            logger.warning("printer send failed (non-fatal)")
    except Exception as exc:
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

    try:
        uid = current_user_id(request)
        user_id = str(uid) if uid is not None else "operator"
        reason_clean = (reason or "").strip() or None
        void_sale(session, sale_id, reason=reason_clean, voided_by=user_id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return RedirectResponse(url="/ventas/historial?flash=sale_void_ok", status_code=303)


__all__ = ["router"]
