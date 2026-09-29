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
from datetime import date, datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Form, HTTPException, Path, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from loguru import logger
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, selectinload

from app.auth import current_user_id
from app.auth import require_login_or_disabled as require_login
from app.rms.audit import record as audit_record
from app.rms.config import ASUNCION_TZ
from app.rms.costing import apply_sale
from app.rms.db import safe_commit
from app.rms.dependencies import get_session
from app.rms.models import Customer, Pedido, PedidoLine, Product, Recipe, Sale

try:
    from app.rms.models import Ingredient
except ImportError:
    Ingredient = None
from decimal import Decimal

from app.rms.money import to_int_gs
from app.rms.schemas import ALLOWED_PAYMENT_METHODS
from app.services.template_render import render

router = APIRouter(prefix="/pedidos", dependencies=[Depends(require_login)])

# Public router for /p/{token} — no auth. We use a dedicated, prefix-less
# APIRouter so the route is registered at exactly /p/{token}, and we mount
# it onto the app during the include_router step.
public_router = APIRouter()

# --- Status state machine ----------------------------------------------------

from enum import Enum


class PedidoStatus(str, Enum):
    """Pedido lifecycle states.

    String enum so existing str comparisons in templates, queries,
    and form parsing keep working. The state machine (PedidoStateMachine)
    owns the transition rules.
    """
    PENDING = "pending"
    CONFIRMED = "confirmed"
    READY = "ready"
    FULFILLED = "fulfilled"
    CANCELLED = "cancelled"


class PedidoStateMachine:
    """Encapsulates pedido transition rules.

    Replaces the scattered `if status in PEDIDO_TRANSITIONS[status]:`
    pattern with a single source of truth. Adding a new status now
    requires editing only this class.
    """

    # Source of truth for valid transitions.
    _TRANSITIONS: dict[PedidoStatus, frozenset[PedidoStatus]] = {
        PedidoStatus.PENDING: frozenset({PedidoStatus.CONFIRMED, PedidoStatus.CANCELLED}),
        PedidoStatus.CONFIRMED: frozenset({PedidoStatus.READY, PedidoStatus.CANCELLED}),
        PedidoStatus.READY: frozenset({PedidoStatus.FULFILLED, PedidoStatus.CANCELLED}),
        PedidoStatus.FULFILLED: frozenset(),  # terminal
        PedidoStatus.CANCELLED: frozenset(),  # terminal
    }

    @classmethod
    def can_transition(cls, from_status: str, to_status: str) -> bool:
        """True iff `from_status` may transition to `to_status`."""
        try:
            from_enum = PedidoStatus(from_status)
            to_enum = PedidoStatus(to_status)
        except ValueError:
            return False
        return to_enum in cls._TRANSITIONS[from_enum]

    @classmethod
    def allowed_next(cls, from_status: str) -> list[str]:
        """Sorted list of statuses reachable from `from_status`."""
        try:
            from_enum = PedidoStatus(from_status)
        except ValueError:
            return []
        return sorted(s.value for s in cls._TRANSITIONS[from_enum])

    @classmethod
    def is_known(cls, status: str) -> bool:
        """True iff `status` is a known PedidoStatus value."""
        try:
            PedidoStatus(status)
            return True
        except ValueError:
            return False

    @classmethod
    def is_terminal(cls, status: str) -> bool:
        """True iff `status` has no outgoing transitions."""
        try:
            from_enum = PedidoStatus(status)
        except ValueError:
            return False
        return len(cls._TRANSITIONS[from_enum]) == 0

    @classmethod
    def is_fulfillable(cls, status: str) -> bool:
        """True iff a pedido in this status can be fulfilled.

        Equivalent to: status in {pending, confirmed, ready} (the
        non-terminal pre-fulfill states). Centralized here so adding
        a new pre-fulfill state is a one-line change.
        """
        try:
            from_enum = PedidoStatus(status)
        except ValueError:
            return False
        return from_enum in (
            PedidoStatus.PENDING,
            PedidoStatus.CONFIRMED,
            PedidoStatus.READY,
        )


# Backwards-compat shim for existing callers that imported the dict
# and tuple. Tests in tests/test_pedido_status_enum.py pin this shape.
PEDIDO_STATUSES = tuple(s.value for s in PedidoStatus)
PEDIDO_TRANSITIONS: dict[str, frozenset[str]] = {
    s.value: frozenset(t.value for t in targets)
    for s, targets in PedidoStateMachine._TRANSITIONS.items()
}

CHANNELS = ("whatsapp", "pedidosya", "mostrador", "phone", "other")

# Channel value normalisation map — raw input → canonical value
_CHANNEL_NORMALIZE: dict[str, str] = {
    "whatsapp": "WhatsApp",
    "wa": "WhatsApp",
    "whats": "WhatsApp",
    "wsp": "WhatsApp",
    "pedidosya": "PedidosYa",
    "mostrador": "Mostrador",
    "phone": "Phone",
    "tel": "Phone",
    "telefono": "Phone",
    "other": "Other",
    "instagram": "Instagram",
    "ig": "Instagram",
}


def normalize_channel(raw: str) -> str:
    """Return a canonical channel display name from a free-text input."""
    key = (raw or "").strip().lower()
    return _CHANNEL_NORMALIZE.get(key, "WhatsApp")


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
    return sum(to_int_gs(Decimal(str(ln.qty or 0)) * Decimal(str(ln.unit_price_gs or 0))) for ln in p.lines)


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
    qty total, line count, age in days, normalized channel display.
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
        "channel": normalize_channel(p.channel),  # normalized display name
        "channel_raw": p.channel,  # original DB value for CSV export
        "status": p.status,
        "payment_intent": p.payment_intent,
        "notes": p.notes,
        "cancel_reason": p.cancel_reason,
        "public_token": p.public_token,
        "public_url": f"/p/{p.public_token}",
        "total_gs": _pedido_total_gs(p),
        "qty_total": _pedido_qty_total(p),
        "n_lines": len(p.lines),
        "age_days": age_days,
        "spend_30d_gs": _customer_30d_spend_gs(session, p.customer_id),
        "fulfilled_at": p.fulfilled_at,
        "fulfilled_sale_id": p.fulfilled_sale_id,
        "created_at": p.created_at,
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
    search: str = Query("", description="Buscar por nombre o teléfono del cliente"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """List pedidos grouped by urgency (Hoy/Mañana, Esta semana, viejos).

    `status_filter` controls the active scope:
      - pendientes (default): pending + confirmed + ready (anything not finished)
      - terminados: fulfilled only
      - todos: no status filter

    `search` filters by customer name or phone (partial match).

    Results are paginated; the groups are computed from the full filtered set,
    then sliced per page for display.
    """
    today = date.today()
    horizon = today + timedelta(days=7)

    stmt_base = (
        select(Pedido)
        .options(selectinload(Pedido.lines), selectinload(Pedido.customer))
        .where(
            (Pedido.promised_date <= horizon)
            | ((Pedido.status == "pending") & (Pedido.promised_date < today))
        )
    )
    if status_filter == "pendientes":
        stmt_base = stmt_base.where(Pedido.status.in_(["pending", "confirmed", "ready"]))
    elif status_filter == "terminados":
        stmt_base = stmt_base.where(Pedido.status == "fulfilled")

    # Search: customer name or phone
    if search := search.strip():
        stmt_base = stmt_base.where(
            (
                Pedido.customer_name.ilike(f"%{search}%")
                | Pedido.customer_phone.ilike(f"%{search}%")
            )
        )

    # Count total for pagination (reuse the base where, no order/offset/limit)
    count_stmt = select(func.count()).select_from(stmt_base.subquery())
    total_count = session.scalar(count_stmt) or 0

    # Paginate: apply order then offset/limit
    stmt = (
        stmt_base
        .order_by(Pedido.promised_date.asc(), Pedido.promised_time.asc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    pedidos = list(session.scalars(stmt))
    grouped = _group_pedidos(session, pedidos)

    # Pagination metadata
    total_pages = max(1, (total_count + per_page - 1) // per_page)
    pagination = {
        "page": page,
        "per_page": per_page,
        "total_count": total_count,
        "total_pages": total_pages,
        "has_prev": page > 1,
        "has_next": page < total_pages,
        "prev_url": f"/pedidos?status_filter={status_filter}&search={search}&page={page-1}" if page > 1 else None,
        "next_url": f"/pedidos?status_filter={status_filter}&search={search}&page={page+1}" if page < total_pages else None,
        "pages": list(range(max(1, page - 2), min(total_pages + 1, page + 3))),
    }
    return render(
        request,
        "pedidos.html",
        {
            "groups": grouped,
            "today_iso": today.isoformat(),
            "today_human": today.strftime("%d/%m/%Y"),
            "status_filter": status_filter,
            "search": search,
            "group_labels": {
                "hoy_manana": "Hoy / Mañana",
                "esta_semana": "Esta semana",
                "pendientes_viejos": "Pendientes viejos",
            },
            "pagination": pagination,
            "page_start": (page - 1) * per_page + 1,
            "page_end": min(page * per_page, total_count),
        },
    )


@router.get("/board", response_class=HTMLResponse)
def pedidos_board(
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Kitchen display: large cards for prep staff. Auto-refreshes every 30s.
    Shows pending + confirmed + ready orders grouped by time slot."""
    today = date.today()
    horizon = today + timedelta(days=3)

    stmt = (
        select(Pedido)
        .options(selectinload(Pedido.lines), selectinload(Pedido.customer))
        .where(
            Pedido.status.in_(["pending", "confirmed", "ready"]),
            Pedido.promised_date <= horizon,
        )
        .order_by(Pedido.promised_date.asc(), Pedido.promised_time.asc())
    )
    pedidos = list(session.scalars(stmt))

    # Separate into time buckets
    hoy = [p for p in pedidos if p.promised_date == today]
    manana = [p for p in pedidos if p.promised_date == today + timedelta(days=1)]
    semana = [p for p in pedidos if p.promised_date > today + timedelta(days=1)]

    # Kanban columns (redesign F5): group active pedidos by status
    def _kanban(col):
        return [
            {"id": p.id, "label": f"#{p.id}", "status": p.status,
             "customer": p.customer.name if p.customer else None,
             "promised": f"{p.promised_date} {p.promised_time or ''}".strip(),
             "lines": [f"{l.qty:g} × {(l.product.name if l.product else '#' + str(l.product_id))}" for l in (p.lines or [])][:6],
             "created_at": p.created_at}
            for p in pedidos if p.status == col
        ]

    return render(
        request,
        "pedido_board.html",
        {
            "pedidos_hoy": hoy,
            "pedidos_manana": manana,
            "pedidos_semana": semana,
            "kanban_pending": _kanban("pending"),
            "kanban_confirmed": _kanban("confirmed"),
            "kanban_ready": _kanban("ready"),
            "today": today,
            "now": datetime.now(ASUNCION_TZ),
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

    # Load active delivery zones for the picker
    from app.rms.models import DeliveryZone
    delivery_zones = session.scalars(
        select(DeliveryZone)
        .where(DeliveryZone.is_active.is_(True))
        .order_by(DeliveryZone.position)
    ).all()

    return render(
        request,
        "pedidos_nuevo.html",
        {
            "products": products,
            "customers": customers,
            "channels": CHANNELS,
            "payment_methods": sorted(set(ALLOWED_PAYMENT_METHODS)),
            "delivery_zones": delivery_zones,
            "today_iso": date.today().isoformat(),
            "default_promised_date": tomorrow.isoformat(),
        },
    )


@router.post("/nuevo")
async def pedidos_create(
    request: Request,
    # customer_id comes in as "" when the combobox has no selection (yet
    # the user may have entered a free-form name). Treat empty string as None.
    customer_id: str = Form(""),
    customer_name: str = Form(""),
    customer_phone: str = Form(""),
    promised_date: str = Form(...),
    promised_time: str = Form(""),
    channel: str = Form("whatsapp"),
    payment_intent: str = Form("efectivo"),
    notes: str = Form(""),
    delivery_zone_id: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Create a new pedido with one or more lines.

    Lines are POSTed as repeated form fields:
        product_id, qty, unit_price_gs   (one set per line)

    We pull from the form via request.form() to support a dynamic number of
    lines without exploding the function signature.
    """
    form = await request.form()
    cust_id_str = str(customer_id or "").strip()
    cust_id_int: int | None = None
    if cust_id_str:
        try:
            cust_id_int = int(cust_id_str)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"customer_id inválido: {cust_id_str!r}",
            )
    # Build list of lines from the form
    product_ids = form.getlist("line_product_id")
    qtys = form.getlist("line_qty")
    unit_prices = form.getlist("line_unit_price_gs")
    if not product_ids:
        raise HTTPException(
            status_code=400, detail="Al menos una línea es obligatoria"
        )

    lines: list[dict[str, Any]] = []
    skipped: list[str] = []  # human-readable reasons for ignored lines
    for idx, (pid_raw, qty_raw, price_raw) in enumerate(
        zip(product_ids, qtys, unit_prices, strict=False), start=1
    ):
        # BUG-00: surface WHY a line was rejected, not silently drop it.
        pid_s = str(pid_raw).strip()
        qty_s = str(qty_raw).strip()
        price_s = str(price_raw).strip()
        if not pid_s or not qty_s:
            skipped.append(f"Línea {idx}: producto o cantidad vacíos")
            continue
        try:
            pid = int(pid_s)
        except (TypeError, ValueError):
            skipped.append(f"Línea {idx}: producto inválido ({pid_raw!r})")
            continue
        try:
            qty = float(qty_s)
        except (TypeError, ValueError):
            skipped.append(f"Línea {idx}: cantidad inválida ({qty_raw!r})")
            continue
        try:
            price = int(price_s) if price_s else 0
        except (TypeError, ValueError):
            skipped.append(f"Línea {idx}: precio inválido ({price_raw!r})")
            continue
        if qty <= 0:
            skipped.append(f"Línea {idx}: cantidad debe ser mayor a 0")
            continue
        if price < 0:
            skipped.append(f"Línea {idx}: precio no puede ser negativo")
            continue
        product = session.get(Product, pid)
        if product is None:
            skipped.append(f"Línea {idx}: producto {pid} no existe")
            continue
        # Snapshot the product's current sale_price_gs if user submitted 0/missing.
        if price <= 0:
            price = product.sale_price_gs
        lines.append(
            {"product_id": pid, "qty": qty, "unit_price_gs": price}
        )
    if not lines:
        detail = "Las líneas válidas son obligatorias. "
        if skipped:
            detail += "Problemas: " + "; ".join(skipped[:5])
            if len(skipped) > 5:
                detail += f" (y {len(skipped) - 5} más)"
        raise HTTPException(status_code=400, detail=detail)

    # Parse promised_date
    try:
        promised = date.fromisoformat(promised_date)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Fecha inválida: {promised_date!r}") from exc

    # Resolve customer (optional)
    cust_name = (customer_name or "").strip()
    cust_phone = (customer_phone or "").strip() or None
    cust_obj: Customer | None = None
    if cust_id_int:
        cust_obj = session.get(Customer, cust_id_int)
        if cust_obj is None:
            raise HTTPException(status_code=400, detail="cliente no encontrado")
        cust_name = cust_name or cust_obj.name

    # If user typed a name but didn't pick an existing customer, auto-create.
    if cust_obj is None and cust_name:
        existing = session.scalar(
            select(Customer).where(
                func.lower(Customer.name) == cust_name.lower()
            )
        )
        if existing is not None:
            cust_obj = existing
            if cust_phone and not (existing.phone or ""):
                existing.phone = cust_phone
        else:
            cust_obj = Customer(
                name=cust_name,
                phone=cust_phone,
            )
            session.add(cust_obj)
            session.flush()  # assigns cust_obj.id

    # Normalize channel to canonical display name
    channel_normalized = normalize_channel(channel)

    # Auto-fill delivery zone from form + validate min order
    zone_int: int | None = None
    if delivery_zone_id:
        try:
            zone_int = int(delivery_zone_id)
        except ValueError:
            zone_int = None
    if zone_int:
        # Load zone to validate min order
        from app.rms.models import DeliveryZone
        zone = session.get(DeliveryZone, zone_int)
        if zone and zone.min_order_gs > 0:
            # Compute pedido total
            pedido_total_gs = sum(
                round((ln["qty"] or 0) * (ln["price"] or 0))
                for ln in lines
            )
            if pedido_total_gs < zone.min_order_gs:
                notes = (
                    (notes or "").strip()
                    + f" [WARN: pedido ₲{pedido_total_gs:,} < mínimo zona ₲{zone.min_order_gs:,}]"
                ).strip()

    pedido = Pedido(
        customer_id=cust_obj.id if cust_obj else None,
        customer_name=cust_name,
        customer_phone=cust_phone or (cust_obj.phone if cust_obj else None),
        promised_date=datetime.combine(promised, datetime.min.time()),
        promised_time=promised_time.strip() or None,
        channel=channel_normalized,
        status="pending",
        payment_intent=(payment_intent or "efectivo").strip().lower(),
        delivery_zone_id=zone_int,
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
            "channel": channel_normalized,
            "promised_date": pedido.promised_date.isoformat(),
            "total_gs": sum(l["qty"] * l["unit_price_gs"] for l in lines),
        },
        request=request,
    )
    safe_commit(session)

    return RedirectResponse(url=f"/pedidos/{pedido.id}", status_code=303)


@router.get("/export-csv")
def pedidos_export_csv(
    request: Request,
    status_filter: str = Query("todos", pattern="^(pendientes|terminados|todos)$"),
    search: str = Query(""),
    session: Session = Depends(get_session),
) -> StreamingResponse:
    """Export filtered pedidos as a CSV download.

    Respects the same search and status_filter as the list view.
    """
    import csv
    import io

    today = date.today()
    horizon = today + timedelta(days=365)  # full history

    stmt = (
        select(Pedido)
        .options(selectinload(Pedido.lines), selectinload(Pedido.customer))
        .where(Pedido.promised_date <= horizon)
    )
    if status_filter == "pendientes":
        stmt = stmt.where(Pedido.status.in_(["pending", "confirmed", "ready"]))
    elif status_filter == "terminados":
        stmt = stmt.where(Pedido.status == "fulfilled")

    if search := search.strip():
        stmt = stmt.where(
            (
                Pedido.customer_name.ilike(f"%{search}%")
                | Pedido.customer_phone.ilike(f"%{search}%")
            )
        )

    stmt = stmt.order_by(Pedido.promised_date.asc())
    pedidos = list(session.scalars(stmt))

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID", "Fecha prometida", "Hora prometida", "Cliente", "Teléfono",
        "Canal", "Estado", "Líneas", "Total Gs.", "Notas",
        "Razón cancelación", "Creado", "Cumplido",
    ])
    for p in pedidos:
        _decorate_pedido(p, session)
        writer.writerow([
            p.id,
            p.promised_date.strftime("%d/%m/%Y"),
            p.promised_time or "",
            p.customer_name,
            p.customer_phone or "",
            p.channel,
            p.status,
            len(p.lines),
            _pedido_total_gs(p),
            (p.notes or "").replace("\n", " "),
            p.cancel_reason or "",
            p.created_at.strftime("%d/%m/%Y %H:%M") if p.created_at else "",
            p.fulfilled_at.strftime("%d/%m/%Y %H:%M") if p.fulfilled_at else "",
        ])

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=pedidos_{date.today().isoformat()}.csv"
        },
    )


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
                "line_total_gs": to_int_gs(Decimal(str(ln.qty)) * Decimal(str(ln.unit_price_gs))),
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


__all__ = ["public_router", "router"]


@router.get("/{pedido_id}", response_class=HTMLResponse)
def pedidos_detail(
    request: Request,
    pedido_id: int = Path(...),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Show one pedido with customer, lines, status buttons, public share URL."""
    pedido = session.get(
        Pedido, pedido_id, options=[
            selectinload(Pedido.lines).selectinload(PedidoLine.product),
            selectinload(Pedido.customer),
        ]
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
            "line_total_gs": to_int_gs(Decimal(str(ln.qty)) * Decimal(str(ln.unit_price_gs))),
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
            "transitions": PedidoStateMachine.allowed_next(pedido.status),
            "can_fulfill": PedidoStateMachine.is_fulfillable(pedido.status),
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
    cancel_reason: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Transition a pedido to a new status. Rejects invalid transitions.

    Used for the manual status buttons on the detail page. If new_status is
    'cancelled', cancel_reason is saved to the pedido record. The /fulfill
    endpoint is a separate workflow that creates Sale rows + stock moves.
    """
    pedido = session.get(Pedido, pedido_id)
    if pedido is None:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    new = (new_status or "").strip().lower()
    if not PedidoStateMachine.is_known(new):
        raise HTTPException(
            status_code=422,
            detail=f"Estado inválido. Permitidos: {PEDIDO_STATUSES}",
        )
    allowed = PedidoStateMachine.allowed_next(pedido.status)
    if new not in allowed:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Transición no permitida: {pedido.status!r} → {new!r}. "
                f"Estados válidos desde {pedido.status!r}: {allowed or '(terminal)'}"
            ),
        )

    old = pedido.status
    pedido.status = new
    if new == "cancelled":
        reason = (cancel_reason or "").strip() or None
        pedido.cancel_reason = reason
    audit_record(
        session,
        user_id=current_user_id(request) or "operator",
        action="write.pedido.status",
        target_type="pedido",
        target_id=str(pedido.id),
        detail={
            "from": old,
            "to": new,
            **({"cancel_reason": pedido.cancel_reason} if new == "cancelled" else {}),
        },
        request=request,
    )
    safe_commit(session)
    return RedirectResponse(url=f"/pedidos/{pedido.id}", status_code=303)


@router.post("/{pedido_id}/fulfill")
def pedidos_fulfill(
    pedido_id: int = Path(...),
    request: Request = ...,  # type: ignore[assignment]
    idempotency_key: str = Form(""),
    force: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Fulfill a pedido: create one Sale per PedidoLine + decrement stock.

    Stream B's key workflow. Validates the pedido is in a fulfillable
    status, then calls apply_sale() once per line so each PedidoLine
    becomes a Sale row (with the line's qty + unit_price_gs snapshot).
    The first Sale is linked on pedido.fulfilled_sale_id so operators
    can navigate from the pedido back to its sale history.

    Idempotency: an `idempotency_key` form field prevents double-fulfillment
    on a double-click. Without one, a fast click could create duplicate
    Sales + double stock decrement for the same pedido.

    Negative-stock guard (P1): BEFORE apply_sale() we replay the preview's
    stock-move calculation against the current pedido + ingredient state.
    If any ingredient would go below zero and the operator has NOT sent
    ``force=true`` (form field or query param), we redirect back to the
    preview page without consuming the idempotency key, so the operator
    can buy the ingredient, refresh the preview, and retry. With
    ``force=true`` the fulfill proceeds, a warning is logged, and the
    audit record carries the shortfalls so ops can audit the override.
    """
    force_flag = str(force or "").strip().lower() in ("true", "1", "yes", "on")
    # Idempotency: reserve the AppMeta row BEFORE running apply_sale for
    # each line. AppMeta.key is the primary key; a duplicate INSERT raises
    # IntegrityError which we catch and redirect to the original fulfill.
    # This closes the F3 race window documented in
    # SASKIA_ARCHITECTURE_REFACTOR_PLAN_2026-09-24.md §F3.
    if idempotency_key:
        from sqlalchemy.exc import IntegrityError

        from app.rms.models import AppMeta as _AppMeta
        try:
            # Use JSON shape (forward-compatible) so we can store
            # request_id alongside the sale_id for duplicate-POST forensics.
            request_id_pedido = getattr(request.state, "request_id", None) or ""
            initial_value = __import__("json").dumps({
                "pedido_id": str(pedido_id),
                "sale_id": "",  # updated below
                "request_id": request_id_pedido,
            })
            session.add(_AppMeta(
                key=f"pedido_fulfill_idem:{idempotency_key}",
                value=initial_value,
                updated_at=datetime.now(timezone.utc).isoformat(),
            ))
            session.flush()  # surface IntegrityError without committing
        except IntegrityError:
            session.rollback()
            return RedirectResponse(
                url=f"/pedidos/{pedido_id}?flash=pedido_fulfill_duplicate",
                status_code=303,
            )

    pedido = session.get(
        Pedido, pedido_id, options=[selectinload(Pedido.lines)]
    )
    if pedido is None:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    if not PedidoStateMachine.is_fulfillable(pedido.status):
        raise HTTPException(
            status_code=409,
            detail=(
                f"Solo se pueden cumplir pedidos en pending/confirmed/ready. "
                f"Estado actual: {pedido.status!r}"
            ),
        )

    # Negative-stock guard (P1): reuse the preview's stock-move calc. If any
    # ingredient would go below zero and the operator has not passed
    # ``force=true``, redirect back to the preview page WITHOUT consuming
    # the idempotency key (we never call apply_sale / safe_commit here).
    # Mirrors the calculation in pedidos_stock_preview() at line ~1155;
    # if you change the rules there, change them here too.
    shortfalls: list[dict] = []
    try:
        from app.rms.costing import _compute_stock_moves

        for ln in pedido.lines:
            if ln.qty <= 0:
                continue
            # Need the product to know which recipe to walk; refresh via
            # the loaded line if available, else fall back to a fresh read.
            line_product = ln.product if hasattr(ln, "product") and ln.product is not None else None
            if line_product is None:
                line_product = session.get(Product, ln.product_id)
            if line_product is None or line_product.recipe_id is None:
                continue
            recipe = session.get(Recipe, line_product.recipe_id)
            if recipe is None:
                continue
            try:
                moves = _compute_stock_moves(session, recipe, float(ln.qty), set())
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    f"pedidos.fulfill: _compute_stock_moves failed for product "
                    f"{line_product.id}: {exc!r}"
                )
                continue
            for _affected_recipe_id, ingredient_id, qty_delta in moves:
                ing = session.get(Ingredient, ingredient_id) if Ingredient else None
                current = ing.stock_qty if ing else 0
                after = current - abs(qty_delta)
                if after < 0:
                    shortfalls.append({
                        "ingredient": ing.name if ing else f"# {ingredient_id}",
                        "shortfall": round(abs(after), 3),
                        "product": line_product.name,
                    })
    except Exception as exc:  # noqa: BLE001
        # Defensive: if the calc itself blows up, do not block the fulfill;
        # log loudly so ops sees it, but proceed (matches pre-fix behavior).
        logger.warning(
            f"pedidos.fulfill: stock-preview calc failed for pedido "
            f"{pedido.id}: {exc!r}"
        )
        shortfalls = []

    if shortfalls and not force_flag:
        user_id = current_user_id(request) or "operator"
        logger.warning(
            f"pedidos.fulfill: blocked pedido={pedido.id} user={user_id} "
            f"shortfall_count={len(shortfalls)} (operator must set force=true to override)"
        )
        # Roll back any pending flushes from the idempotency AppMeta reservation
        # so the operator can retry without a duplicate-key error.
        session.rollback()
        flash_msg = f"Stock+insuficiente+para+{len(shortfalls)}+ingredientes"
        return RedirectResponse(
            url=f"/pedidos/{pedido_id}/stock-preview?flash={flash_msg}",
            status_code=303,
        )

    if shortfalls and force_flag:
        user_id = current_user_id(request) or "operator"
        logger.warning(
            f"pedidos.fulfill: FORCE-FULFILL pedido={pedido.id} user={user_id} "
            f"shortfall_count={len(shortfalls)} (stock will go negative)"
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
            **({"force_fulfilled_over_shortfall": shortfalls} if (shortfalls and force_flag) else {}),
        },
        request=request,
    )

    # Update the idempotency record with the real first_sale_id. The AppMeta
    # row was reserved BEFORE apply_sale (see top of function), so the row
    # already exists by this point — we're just updating its value with the
    # real first_sale_id while preserving the JSON shape (pedido_id, request_id).
    if idempotency_key and first_sale_id is not None:
        import json as _json

        from app.rms.models import AppMeta as _AppMeta

        # Re-read current value to preserve pedido_id + request_id, then
        # add the just-created first_sale_id.
        existing = session.scalar(
            __import__("sqlalchemy").select(_AppMeta).where(
                _AppMeta.key == f"pedido_fulfill_idem:{idempotency_key}"
            )
        )
        try:
            payload = _json.loads(existing.value) if existing and existing.value else {}
        except (ValueError, TypeError):
            # Legacy plain-string value (created before this fix shipped)
            payload = {}
        payload["sale_id"] = str(first_sale_id)
        session.execute(
            update(_AppMeta)
            .where(_AppMeta.key == f"pedido_fulfill_idem:{idempotency_key}")
            .values(value=_json.dumps(payload))
        )

    safe_commit(session)

    # ── Notify customer via WhatsApp or SMS ──────────────────────────────────
    _send_fulfill_notification(session, pedido)

    return RedirectResponse(url=f"/pedidos/{pedido.id}", status_code=303)


def _send_fulfill_notification(session: Session, pedido: Pedido) -> None:
    """Send a WhatsApp/SMS notification to the customer when their order is fulfilled.

    WhatsApp is attempted first via Twilio; if credentials are absent it falls back
    to SMS.  When neither is configured, a console/structlog info line is produced.
    """
    if not pedido.customer_phone:
        return

    phone = pedido.customer_phone.strip()
    # Phase 6 — pull message body from MessageTemplate table when available.
    # Falls back to the legacy hardcoded copy if the template row is missing.
    msg = None
    try:
        from sqlalchemy import select as _select

        from app.rms.models import MessageTemplate as MT
        template_key = "pedido_listo" if pedido.channel == "WhatsApp" else "generic"
        template_channel = "whatsapp" if pedido.channel == "WhatsApp" else "email"
        row = session.execute(
            _select(MT).where(
                MT.channel == template_channel,
                MT.key == template_key,
                MT.is_active.is_(True),
            )
        ).scalar_one_or_none()
        if row is not None:
            from app.routers.settings_runtime import render_template
            msg = render_template(row.body, {
                "customer_name": pedido.customer_name or "",
                "pedido_id": pedido.id,
                "total_gs": pedido.total_gs or 0,
                "business_name": "Saskia RMS",
            })
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"pedidos._send_fulfill_notification: render_template failed (fallback to legacy msg): {exc!r}")
    if msg is None:
        msg = (
            f"¡Tu pedido #{pedido.id} esta listo para retirar! Te esperamos 😊"
            if pedido.channel == "WhatsApp"
            else f"Tu pedido #{pedido.id} esta listo para retirar. Gracias!"
        )

    import logging
    import os
    twilio_sid     = os.getenv("TWILIO_ACCOUNT_SID",     "").strip()
    twilio_token   = os.getenv("TWILIO_AUTH_TOKEN",       "").strip()
    twilio_from_wa = os.getenv("TWILIO_WHATSAPP_FROM",   "").strip()
    twilio_from_ph = os.getenv("TWILIO_PHONE_FROM",       "").strip()

    log = logging.getLogger("rms.pedidos")

    def _post_twilio(from_num: str, to_num: str) -> bool:
        try:
            import httpx
            r = httpx.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{twilio_sid}/Messages.json",
                auth=(twilio_sid, twilio_token),
                data={"From": from_num, "To": to_num, "Body": msg},
                timeout=15.0,
            )
            ok = r.status_code in (200, 201)
            if not ok:
                log.warning("Twilio error for pedido %s: %s %s", pedido.id, r.status_code, r.text)
            return ok
        except Exception as exc:  # noqa: BLE001 — defensive fallback — guarded response
            log.error("Twilio exception for pedido %s: %s", pedido.id, exc)
            return False

    if twilio_sid and twilio_token:
        if twilio_from_wa:
            if _post_twilio(f"whatsapp:{twilio_from_wa}", f"whatsapp:{phone}"):
                return
        if twilio_from_ph:
            _post_twilio(twilio_from_ph, phone)
            return
    # No Twilio configured
    log.info("[notify] Pedido #%s fulfilled — would send to %s: %s", pedido.id, phone, msg)


# --- Stock preview (pre-fulfill) ---------------------------------------------
# Preview what ingredients will be consumed before confirming fulfillment.


@router.get("/{pedido_id}/stock-preview", response_class=HTMLResponse)
def pedidos_stock_preview(
    request: Request,
    pedido_id: int = Path(...),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Show what ingredients will be consumed if this pedido is fulfilled.

    Used as a confirmation step before calling /fulfill — lets the operator
    see stock warnings before committing to the sale.
    """
    from app.rms.costing import _compute_stock_moves

    pedido = session.get(
        Pedido, pedido_id, options=[selectinload(Pedido.lines).selectinload(PedidoLine.product)]
    )
    if pedido is None:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    warnings: list[dict] = []
    consumed: list[dict] = []

    for ln in pedido.lines:
        if ln.qty <= 0:
            continue
        product = ln.product
        if product is None or product.recipe_id is None:
            continue
        recipe = session.get(Recipe, product.recipe_id)
        if recipe is None:
            continue
        try:
            moves = _compute_stock_moves(session, recipe, float(ln.qty), set())
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"pedidos.stock_preview: _compute_stock_moves failed for product {product.id}: {exc!r}")
            continue
        for _affected_recipe_id, ingredient_id, qty_delta in moves:
            ing = session.get(Ingredient, ingredient_id) if Ingredient else None
            ing_name = ing.name if ing else f"# {ingredient_id}"
            current = ing.stock_qty if ing else 0
            after = current - abs(qty_delta)
            consumed.append({
                "ingredient": ing_name,
                "product": product.name,
                "qty_needed": round(abs(qty_delta), 3),
                "current_stock": round(current, 3) if current else 0,
                "after_stock": round(after, 3),
                "warning": after < 0,
            })
            if after < 0:
                warnings.append({
                    "ingredient": ing_name,
                    "shortfall": round(abs(after), 3),
                    "product": product.name,
                })

    return render(
        request,
        "pedido_stock_preview.html",
        {
            "pedido_id": pedido_id,
            "consumed": consumed,
            "warnings": warnings,
            "idempotency_key": secrets.token_urlsafe(16),
        },
    )


# --- Duplicate pedido ----------------------------------------------------------


@router.post("/{pedido_id}/duplicate")
@router.get("/{pedido_id}/duplicate", deprecated=True)
def pedidos_duplicate(
    request: Request,
    pedido_id: int = Path(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Create a copy of an existing pedido with a new public token and status.

    The duplicated pedido is set to 'pending' with a fresh token so the
    customer can receive a new share link.

    This is a state-mutating operation — POST is required. The GET route
    is preserved as deprecated so any existing bookmarks don't 405.
    """
    original = session.get(
        Pedido, pedido_id, options=[selectinload(Pedido.lines)]
    )
    if original is None:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    copy = Pedido(
        customer_id=original.customer_id,
        customer_name=original.customer_name,
        customer_phone=original.customer_phone,
        promised_date=original.promised_date,
        promised_time=original.promised_time,
        channel=original.channel,
        status="pending",
        payment_intent=original.payment_intent,
        notes=original.notes,
        public_token=generate_public_token(),
    )
    session.add(copy)
    session.flush()

    for ln in original.lines:
        session.add(
            PedidoLine(
                pedido_id=copy.id,
                product_id=ln.product_id,
                qty=ln.qty,
                unit_price_gs=ln.unit_price_gs,
                fulfilled_qty=0,
            )
        )

    audit_record(
        session,
        user_id=current_user_id(request) or "operator",
        action="write.pedido.duplicate",
        target_type="pedido",
        target_id=str(copy.id),
        detail={"original_id": original.id},
        request=request,
    )
    safe_commit(session)

    return RedirectResponse(url=f"/pedidos/{copy.id}", status_code=303)


# --- CSV export --------------------------------------------------------------


@router.post("/bulk-fulfill")
def pedidos_bulk_fulfill(
    request: Request,
    ids: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Mark multiple pending pedidos as fulfilled in one click."""
    from sqlalchemy import update

    from app.rms.models import Pedido

    fulfilled = 0
    for pid in ids.split(","):
        pid = pid.strip()
        if not pid:
            continue
        try:
            pedido = session.get(Pedido, int(pid))
        except ValueError:
            continue
        if pedido is None or pedido.status != "pending":
            continue
        pedido.status = "fulfilled"
        session.execute(
            update(PedidoLine.__table__)
            .where(PedidoLine.pedido_id == pedido.id)
            .values(fulfilled_qty=PedidoLine.qty)
        )
        fulfilled += 1
    safe_commit(session)
    flash = f"{fulfilled} pedido(s) marcado(s) como completado(s)"
    return RedirectResponse(url=f"/pedidos?flash={flash}", status_code=303)


@router.post("/bulk-cancel")
def pedidos_bulk_cancel(
    request: Request,
    ids: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Cancel multiple pending pedidos in one click."""
    from app.rms.models import Pedido

    cancelled = 0
    for pid in ids.split(","):
        pid = pid.strip()
        if not pid:
            continue
        try:
            pedido = session.get(Pedido, int(pid))
        except ValueError:
            continue
        if pedido is None or pedido.status != "pending":
            continue
        pedido.status = "cancelled"
        cancelled += 1
    safe_commit(session)
    flash = f"{cancelled} pedido(s) cancelado(s)"
    return RedirectResponse(url=f"/pedidos?flash={flash}", status_code=303)
