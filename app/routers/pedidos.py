"""app/routers/pedidos.py — Pre-orders (pedidos) for Saskia's WhatsApp-heavy flow.

Phase 3 of the 2026-09-17 prelaunch roadmap.

Most pedidos come in via WhatsApp the day before or morning-of for pickup.
This router exposes:

- `GET  /pedidos` — list grouped by Hoy/Mañana, Esta semana, Pendientes viejos
- `GET  /pedidos/{id}` — detail with status transitions
- `GET  /pedidos/nuevo` — new-pedido form (renders product picker)
- `POST /pedidos/nuevo` — create pedido + lines
- `POST /pedidos/{id}/status` — transition status (pending → confirmed → ready → fulfilled)
- `POST /pedidos/{id}/fulfill` — the key workflow: creates Sale rows + decrements stock
- `GET  /p/{public_token}` — NO AUTH public pickup-share page (WhatsApp-shareable)

The public `/p/{token}` endpoint lives at the root (not under /pedidos) so the
path stays short when shared over WhatsApp: `https://saskia.app/p/AbCd1234`.
"""
from __future__ import annotations

import secrets
from collections.abc import Iterable
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Form, HTTPException, Path, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.auth import current_user_id, require_login_or_disabled as require_login
from app.rms.audit import record as audit_record
from app.rms.config import ASUNCION_TZ
from app.rms.costing import apply_sale
from app.rms.dependencies import get_session
from app.rms.models import Customer, Pedido, PedidoLine, Product, Sale
from app.rms.schemas import ALLOWED_PAYMENT_METHODS
from app.services.template_render import render

router = APIRouter(prefix="/pedidos", dependencies=[Depends(require_login)])

# Public router for /p/{token} — no auth. We use a dedicated, prefix-less
# APIRouter so the route is registered at exactly /p/{token}, and we mount
# it onto the app during the include_router step.
public_router = APIRouter()

# --- Status state machine ----------------------------------------------------

PEDIDO_STATUSES = ("pending", "confirmed", "ready", "fulfilled", "cancelled")

# Status transition rules. Key is the current status; value is the set of
# statuses it can transition to. fulfilled and cancelled are terminal.
PEDIDO_TRANSITIONS: dict[str, frozenset[str]] = {
    "pending": frozenset({"confirmed", "cancelled"}),
    "confirmed": frozenset({"ready", "cancelled"}),
    "ready": frozenset({"fulfilled", "cancelled"}),
    "fulfilled": frozenset(),  # terminal
    "cancelled": frozenset(),  # terminal
}

CHANNELS = ("whatsapp", "pedidosya", "mostrador", "phone", "other")


def generate_public_token() -> str:
    """Generate an 8-char URL-safe token for /p/{token} pickup-share links.

    Uses token_urlsafe(8) which yields ~11 chars; we slice to keep URLs
    short for WhatsApp. 8 chars (62^8 = 218T) is plenty for a single-tenant
    bakery — collisions would require ~14M active pedidos before we hit a
    1% birthday-paradox probability.
    """
    return secrets.token_urlsafe(8)[:8]


def _pedido_total_gs(p: Pedido) -> int:
    """Compute the pedido's total in Gs. (qty * unit_price_gs per line)."""
    return sum(int(round((ln.qty or 0) * (ln.unit_price_gs or 0))) for ln in p.lines)


def _pedido_qty_total(p: Pedido) -> float:
    """Total quantity across all lines."""
    return sum((ln.qty or 0) for ln in p.lines)


def _customer_30d_spend_gs(session: Session, customer_id: int | None) -> int:
    """Lifetime spend for a customer over the last 30 days. 0 if no customer."""
    if customer_id is None:
        return 0
    cutoff = datetime.now(ASUNCION_TZ) - timedelta(days=30)
    row = session.execute(
        select(func.coalesce(func.sum(Sale.qty * Sale.unit_price_gs), 0)).where(
            Sale.customer_id == customer_id,
            Sale.voided_at.is_(None),
            Sale.sold_at >= cutoff,
        )
    ).first()
    return int(row[0] or 0) if row else 0


def _decorate_pedido(p: Pedido, session: Session) -> dict:
    """Build the dict used in /pedidos list views.

    Denormalizes: customer_name (already on the model), 30d spend, total Gs,
    qty total, line count, age in days.
    """
    today = date.today()
    promised = p.promised_date.date() if isinstance(p.promised_date, datetime) else p.promised_date
    age_days = (today - promised).days
    return {
        "id": p.id,
        "customer_id": p.customer_id,
        "customer_name": p.customer_name or (
            p.customer.name if p.customer else "(sin nombre)"
        ),
        "customer_phone": p.customer_phone or (p.customer.phone if p.customer else None),
        "promised_date": promised,
        "promised_date_iso": promised.isoformat() if promised else "",
        "promised_time": p.promised_time or "",
        "channel": p.channel,
        "status": p.status,
        "payment_intent": p.payment_intent,
        "notes": p.notes,
        "public_token": p.public_token,
        "public_url": f"/p/{p.public_token}",
        "total_gs": _pedido_total_gs(p),
        "qty_total": _pedido_qty_total(p),
        "n_lines": len(p.lines),
        "age_days": age_days,
        "spend_30d_gs": _customer_30d_spend_gs(session, p.customer_id),
        "fulfilled_at": p.fulfilled_at,
        "fulfilled_sale_id": p.fulfilled_sale_id,
    }


def _group_pedidos(
    session: Session, pedidos: Iterable[Pedido]
) -> dict[str, list[dict]]:
    """Split pedidos into 3 sections: Hoy/Mañana, Esta semana, Pendientes viejos.

    - Hoy/Mañana: promised_date in [today, today+1]
    - Esta semana: promised_date in [today+2, today+7]
    - Pendientes viejos: status='pending' AND promised_date < today
    """
    today = date.today()
    out: dict[str, list[dict]] = {
        "hoy_manana": [],
        "esta_semana": [],
        "pendientes_viejos": [],
    }
    for p in pedidos:
        decorated = _decorate_pedido(p, session)
        promised = decorated["promised_date"]
        if promised is None:
            continue
        if promised < today:
            if p.status == "pending":
                out["pendientes_viejos"].append(decorated)
            # fulfilled/cancelled past-due pedidos don't surface anywhere
        elif promised <= today + timedelta(days=1):
            out["hoy_manana"].append(decorated)
        elif promised <= today + timedelta(days=7):
            out["esta_semana"].append(decorated)
        # Beyond 7 days: out of view (operator should chase these via search later).
    return out


# --- Routes -----------------------------------------------------------------


@router.get("", response_class=HTMLResponse)
def pedidos_list(
    request: Request,
    status_filter: str = Query(
        "pendientes",
        pattern="^(pendientes|terminados|todos)$",
    ),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """List pedidos grouped by urgency (Hoy/Mañana, Esta semana, viejos).

    `status_filter` controls the active scope:
      - pendientes (default): pending + confirmed + ready (anything not finished)
      - terminados: fulfilled only
      - todos: no status filter
    """
    today = date.today()
    horizon = today + timedelta(days=7)
    # Pull everything active (not cancelled/fulfilled) within 7-day horizon +
    # pending+past-due (old pending pedidos). One query with UNION would be
    # nicer but this is fine for a single-tenant bakery's volume.
    stmt = (
        select(Pedido)
        .options(selectinload(Pedido.lines), selectinload(Pedido.customer))
        .where(
            (Pedido.promised_date <= horizon)
            | ((Pedido.status == "pending") & (Pedido.promised_date < today))
        )
        .order_by(Pedido.promised_date.asc(), Pedido.promised_time.asc())
    )
    if status_filter == "pendientes":
        stmt = stmt.where(Pedido.status.in_(["pending", "confirmed", "ready"]))
    elif status_filter == "terminados":
        stmt = stmt.where(Pedido.status == "fulfilled")
    # "todos" leaves the where clause untouched (no status filter)
    pedidos = list(session.scalars(stmt))
    grouped = _group_pedidos(session, pedidos)
    return render(
        request,
        "pedidos.html",
        {
            "groups": grouped,
            "today_iso": today.isoformat(),
            "today_human": today.strftime("%d/%m/%Y"),
            "status_filter": status_filter,
            "group_labels": {
                "hoy_manana": "Hoy / Mañana",
                "esta_semana": "Esta semana",
                "pendientes_viejos": "Pendientes viejos",
            },
        },
    )


@router.get("/nuevo", response_class=HTMLResponse)
def pedidos_new_form(
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Render the new-pedido form with the product picker."""
    products = session.scalars(select(Product).order_by(Product.name)).all()
    customers = session.scalars(
        select(Customer).order_by(Customer.created_at.desc()).limit(50)
    ).all()
    tomorrow = date.today() + timedelta(days=1)
    return render(
        request,
        "pedidos_nuevo.html",
        {
            "products": products,
            "customers": customers,
            "channels": CHANNELS,
            "payment_methods": list(ALLOWED_PAYMENT_METHODS) + ["efectivo", "transferencia", "qr", "tarjeta", "otro"],
            "today_iso": date.today().isoformat(),
            "default_promised_date": tomorrow.isoformat(),
        },
    )


@router.post("/nuevo")
async def pedidos_create(
    request: Request,
    customer_id: int | None = Form(None),
    customer_name: str = Form(""),
    customer_phone: str = Form(""),
    promised_date: str = Form(...),
    promised_time: str = Form(""),
    channel: str = Form("whatsapp"),
    payment_intent: str = Form("efectivo"),
    notes: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Create a new pedido with one or more lines.

    Lines are POSTed as repeated form fields:
        product_id, qty, unit_price_gs   (one set per line)

    We pull from the form via request.form() to support a dynamic number of
    lines without exploding the function signature.
    """
    form = await request.form()
    # Build list of lines from the form
    product_ids = form.getlist("line_product_id")
    qtys = form.getlist("line_qty")
    unit_prices = form.getlist("line_unit_price_gs")
    if not product_ids:
        raise HTTPException(status_code=422, detail="Al menos una línea es requerida")

    lines: list[dict[str, Any]] = []
    for pid_raw, qty_raw, price_raw in zip(product_ids, qtys, unit_prices):
        try:
            pid = int(str(pid_raw))
            qty = float(str(qty_raw))
            price = int(str(price_raw))
        except (TypeError, ValueError):
            continue
        if qty <= 0 or price < 0:
            continue
        product = session.get(Product, pid)
        if product is None:
            continue
        # Snapshot the product's current sale_price_gs if user submitted 0/missing.
        if price <= 0:
            price = product.sale_price_gs
        lines.append(
            {"product_id": pid, "qty": qty, "unit_price_gs": price}
        )
    if not lines:
        raise HTTPException(
            status_code=422,
            detail="Las líneas deben tener producto, cantidad > 0 y precio ≥ 0",
        )

    # Parse promised_date
    try:
        promised = date.fromisoformat(promised_date)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Fecha inválida: {promised_date!r}") from exc

    # Resolve customer (optional)
    cust_name = (customer_name or "").strip()
    cust_phone = (customer_phone or "").strip() or None
    cust_obj: Customer | None = None
    if customer_id:
        cust_obj = session.get(Customer, int(customer_id))
        if cust_obj is None:
            raise HTTPException(status_code=422, detail="customer_id inválido")
        cust_name = cust_name or cust_obj.name

    pedido = Pedido(
        customer_id=cust_obj.id if cust_obj else None,
        customer_name=cust_name,
        customer_phone=cust_phone or (cust_obj.phone if cust_obj else None),
        promised_date=datetime.combine(promised, datetime.min.time()),
        promised_time=promised_time.strip() or None,
        channel=(channel or "whatsapp").strip().lower(),
        status="pending",
        payment_intent=(payment_intent or "efectivo").strip().lower(),
        notes=(notes or "").strip() or None,
        public_token=generate_public_token(),
    )
    session.add(pedido)
    session.flush()  # assigns pedido.id

    for ln in lines:
        session.add(
            PedidoLine(
                pedido_id=pedido.id,
                product_id=ln["product_id"],
                qty=ln["qty"],
                unit_price_gs=ln["unit_price_gs"],
                fulfilled_qty=0,
            )
        )

    audit_record(
        session,
        user_id=current_user_id(request) or "operator",
        action="write.pedido.create",
        target_type="pedido",
        target_id=str(pedido.id),
        detail={
            "n_lines": len(lines),
            "channel": pedido.channel,
            "promised_date": pedido.promised_date.isoformat(),
            "total_gs": sum(l["qty"] * l["unit_price_gs"] for l in lines),
        },
        request=request,
    )
    session.commit()

    return RedirectResponse(url=f"/pedidos/{pedido.id}", status_code=303)


@router.get("/{pedido_id}", response_class=HTMLResponse)
def pedidos_detail(
    request: Request,
    pedido_id: int = Path(...),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Show one pedido with customer, lines, status buttons, public share URL."""
    pedido = session.get(
        Pedido, pedido_id, options=[selectinload(Pedido.lines), selectinload(Pedido.customer)]
    )
    if pedido is None:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    spend_30d = _customer_30d_spend_gs(session, pedido.customer_id)
    decorated = _decorate_pedido(pedido, session)
    decorated["lines"] = [
        {
            "id": ln.id,
            "product_id": ln.product_id,
            "product_name": ln.product.name if ln.product else f"#{ln.product_id}",
            "qty": ln.qty,
            "unit_price_gs": ln.unit_price_gs,
            "line_total_gs": int(round(ln.qty * ln.unit_price_gs)),
            "fulfilled_qty": ln.fulfilled_qty,
        }
        for ln in pedido.lines
    ]
    decorated["spend_30d_gs"] = spend_30d
    return render(
        request,
        "pedido_detalle.html",
        {
            "pedido": decorated,
            "transitions": sorted(PEDIDO_TRANSITIONS.get(pedido.status, frozenset())),
            "can_fulfill": pedido.status in ("pending", "confirmed", "ready"),
            "channels": CHANNELS,
            "payment_methods": sorted(
                set(ALLOWED_PAYMENT_METHODS) | {"efectivo", "transferencia", "qr", "tarjeta", "otro"}
            ),
        },
    )


@router.post("/{pedido_id}/status")
async def pedidos_status(
    request: Request,
    pedido_id: int = Path(...),
    new_status: str = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Transition a pedido to a new status. Rejects invalid transitions.

    Used for the manual status buttons on the detail page. The /fulfill
    endpoint is a separate workflow that creates Sale rows + stock moves.
    """
    pedido = session.get(Pedido, pedido_id)
    if pedido is None:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    new = (new_status or "").strip().lower()
    if new not in PEDIDO_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"Estado inválido. Permitidos: {sorted(PEDIDO_STATUSES)}",
        )
    allowed = PEDIDO_TRANSITIONS.get(pedido.status, frozenset())
    if new not in allowed:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Transición no permitida: {pedido.status!r} → {new!r}. "
                f"Estados válidos desde {pedido.status!r}: {sorted(allowed) or '(terminal)'}"
            ),
        )

    old = pedido.status
    pedido.status = new
    audit_record(
        session,
        user_id=current_user_id(request) or "operator",
        action="write.pedido.status",
        target_type="pedido",
        target_id=str(pedido.id),
        detail={"from": old, "to": new},
        request=request,
    )
    session.commit()
    return RedirectResponse(url=f"/pedidos/{pedido.id}", status_code=303)


@router.post("/{pedido_id}/fulfill")
def pedidos_fulfill(
    pedido_id: int = Path(...),
    request: Request = ...,  # type: ignore[assignment]
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Fulfill a pedido: create one Sale per PedidoLine + decrement stock.

    Stream B's key workflow. Validates the pedido is in a fulfillable
    status, then calls apply_sale() once per line so each PedidoLine
    becomes a Sale row (with the line's qty + unit_price_gs snapshot).
    The first Sale is linked on pedido.fulfilled_sale_id so operators
    can navigate from the pedido back to its sale history.
    """
    pedido = session.get(
        Pedido, pedido_id, options=[selectinload(Pedido.lines)]
    )
    if pedido is None:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    if pedido.status not in ("pending", "confirmed", "ready"):
        raise HTTPException(
            status_code=409,
            detail=(
                f"Solo se pueden cumplir pedidos en pending/confirmed/ready. "
                f"Estado actual: {pedido.status!r}"
            ),
        )

    # Snapshot sold_at to now in Asunción TZ so /reportes groups by the
    # day the customer picked up, not when the order was placed.
    sold_at = datetime.now(ASUNCION_TZ)

    first_sale_id: int | None = None
    n_sales = 0
    for ln in pedido.lines:
        if ln.qty <= 0:
            continue
        result = apply_sale(
            session,
            product_id=ln.product_id,
            qty=float(ln.qty),
            sold_at=sold_at,
            notes=(pedido.notes or None),
            customer_id=pedido.customer_id,
            payment_method=pedido.payment_intent,
            discount_gs=0,
        )
        # apply_sale commits internally — refresh from the new identity.
        ln.fulfilled_qty = float(ln.qty)
        first_sale_id = first_sale_id or result.sale_id
        n_sales += 1

    # Update the pedido itself.
    pedido.fulfilled_at = datetime.now(ASUNCION_TZ)
    pedido.fulfilled_sale_id = first_sale_id
    pedido.status = "fulfilled"

    audit_record(
        session,
        user_id=current_user_id(request) or "operator",
        action="write.pedido.fulfill",
        target_type="pedido",
        target_id=str(pedido.id),
        detail={
            "n_sales": n_sales,
            "first_sale_id": first_sale_id,
            "total_gs": _pedido_total_gs(pedido),
        },
        request=request,
    )
    session.commit()

    return RedirectResponse(url=f"/pedidos/{pedido.id}", status_code=303)


# --- Public pickup-share endpoint (NO AUTH) ---------------------------------
# Lives at root so the URL is short enough for WhatsApp messages:
# https://saskia.app/p/AbCd1234


@public_router.get("/p/{token}", response_class=HTMLResponse)
def public_pedido(request: Request, token: str) -> HTMLResponse:
    """Public, no-auth pickup-share page rendered for the customer.

    Used as a WhatsApp-shareable confirmation link so the customer can see
    "what they ordered + when to come" without logging in. The token is the
    8-char public_token generated when the pedido was created; collision-
    resistance comes from the random token + the bounded single-tenant
    volume of pedidos.

    Uses ``request.app.state.session_factory`` so the test engine
    (injected by the ``client`` fixture's monkey-patch of
    ``make_engine_dialect``) is honored — calling ``make_engine()`` here
    would bypass the test engine and read the production DB, breaking
    the round-trip test that posts a pedido in the test DB and reads it
    back via this endpoint.
    """
    with request.app.state.session_factory() as session:
        # Pedido.id is an Integer PK; look up by public_token instead
        # so /p/{token} resolves to the pedido sharing that token.
        # (Earlier this used session.get(Pedido, token), which queried
        # by the int PK and silently returned None for valid string
        # tokens — making the page 404 for every real customer.)
        pedido = session.execute(
            select(Pedido)
            .where(Pedido.public_token == token)
            .options(selectinload(Pedido.lines))
        ).scalar_one_or_none()
        if pedido is None:
            raise HTTPException(
                status_code=404, detail="Pedido no encontrado"
            )
        decorated = _decorate_pedido(pedido, session)
        decorated["lines"] = [
            {
                "product_name": ln.product.name if ln.product else f"#{ln.product_id}",
                "qty": ln.qty,
                "unit_price_gs": ln.unit_price_gs,
                "line_total_gs": int(round(ln.qty * ln.unit_price_gs)),
            }
            for ln in pedido.lines
        ]
        return render(
            request,
            "pedido_publico.html",
            {
                "pedido": decorated,
                "shop_name": "Saskia RMS",
                "currency_label": "Gs.",
            },
        )


__all__ = ["router", "public_router"]
