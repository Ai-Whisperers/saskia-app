"""app/routers/pedidos.py — Pre-orders (pedidos) for the operator's WhatsApp-heavy flow.

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
path stays short when shared over WhatsApp: `https://sazon.app/p/AbCd1234`.
"""

from __future__ import annotations

import json
import secrets
from collections.abc import Iterable
from datetime import date, datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Path, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from loguru import logger
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, selectinload

from app.auth import current_user_id
from app.auth import require_login_or_disabled as require_login
from app.rms.audit import record as audit_record
from app.rms.config import ASUNCION_TZ
from app.rms.costing import apply_sale
from app.rms.csrf import verify_form_csrf
from app.rms.db import safe_commit
from app.rms.dependencies import get_session
from app.rms.models import Customer, Pedido, PedidoLine, Product, Recipe, Sale
from app.rms.models.channels import Channel
from app.rms.production_demand import invalidate_demand_for_dates


def _as_date(d: "date | datetime | None") -> date | None:
    """PRODUCCION-V2 Fase 4 helper: normalize a column value to a date.

    `pedido.promised_date` is a SQLAlchemy DateTime column but is
    populated by callers passing either a `date` or a `datetime`.
    `.date()` is only valid on `datetime`. Snapshot rows are keyed by
    `date.isoformat()` (no time component), so we must normalize.

    Returns None for None so callers can short-circuit if needed.
    """
    if d is None:
        return None
    if isinstance(d, datetime):
        return d.date()
    return d
from app.rms.public_tokens import (
    enforce_rate_limit as public_token_enforce_rate_limit,
)
from app.rms.public_tokens import (
    generate_public_token as public_token_generate_token,
)
from app.rms.public_tokens import (
    is_token_valid as is_pedido_token_valid,
)

try:
    from app.rms.models import Ingredient
except ImportError:
    Ingredient = None
from decimal import Decimal

from app.rms.money import to_int_gs
from app.rms.schemas import ALLOWED_PAYMENT_METHODS

# Phase 3: customer-prefill service for /pedidos/nuevo
from app.services.customer_prefill import customer_defaults_as_json

# Phase 4: timeline + customer history for the detail page
from app.services.pedido_history import (
    build_pedido_timeline,
    customer_recent_pedidos,
)
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

CHANNELS = (Channel.WHATSAPP.value, Channel.PEDIDOSYA.value, Channel.MOSTRADOR.value, Channel.OTHER.value)

# Channel value normalisation map — raw input → canonical value
# P39 (2026-10-07, Ivan): values must match Channel enum (lowercase) so
# analytics can group sales by channel without case-sensitive matching.
# The map previously returned display strings ("WhatsApp", "PedidosYa")
# which contradicted ALLOWED_CHANNELS (lowercase) and created duplicate
# channels in reports ("whatsapp" vs "WhatsApp"). The key input is now
# forced lowercase and the values are the canonical lowercase strings.
# P42 (2026-10-07): normalize all inputs to Channel enum so the DB
# CHECK constraint (migration 111) accepts them. Phone/instagram are
# legacy display names — both are merged into Channel.OTHER since the
# canonical enum doesn't have a phone/instagram variant today.
# Adding "phone" or "instagram" as separate enum values is a follow-up
# if the operator wants to split them out in reports.
_CHANNEL_NORMALIZE: dict[str, str] = {
    "whatsapp": Channel.WHATSAPP.value,
    "wa": Channel.WHATSAPP.value,
    "whats": Channel.WHATSAPP.value,
    "wsp": Channel.WHATSAPP.value,
    "pedidosya": Channel.PEDIDOSYA.value,
    "mostrador": Channel.MOSTRADOR.value,
    "phone": Channel.OTHER.value,
    "tel": Channel.OTHER.value,
    "telefono": Channel.OTHER.value,
    "other": Channel.OTHER.value,
    "instagram": Channel.OTHER.value,
    "ig": Channel.OTHER.value,
}


def normalize_channel(raw: str) -> str:
    """Return a canonical channel code from a free-text input.

    Returns the lowercase code (e.g. "whatsapp", "pedidosya") — matches
    the Channel enum so /produccion analytics and sales channel filters
    stay consistent. Falls back to "mostrador" if the input is empty
    or unknown, instead of silently picking "whatsapp" as the prior
    version did (which masked data-entry errors).
    """
    key = (raw or "").strip().lower()
    return _CHANNEL_NORMALIZE.get(key, Channel.MOSTRADOR.value)


def generate_public_token() -> str:
    """Re-export the shared public-token helper so existing imports in
    tests and call sites keep working unchanged.

    The implementation lives in ``app.rms.public_tokens`` so that
    /p/{token} and /r/{token} share one entropy source and one TTL.
    """
    return public_token_generate_token()


def _is_token_valid(pedido: Pedido, now: datetime | None = None) -> bool:
    """Backwards-compatible wrapper around the shared helper.

    The shared ``is_token_valid`` accepts the bare ``expires_at``
    value (datetime, naive datetime, or string from SQLite). The
    P1-2-era call sites pass the ORM object — this wrapper unwraps
    it. Behavior matches the original P1-2 hardening:
    NULL/unparseable → False, naive UTC compared as UTC-aware.
    """
    expires_at = getattr(pedido, "public_token_expires_at", None)
    if now is not None:
        # Replicate the original "naive-utc-now when expiry is naive" rule
        # so the existing test suite passes unchanged. The shared helper
        # always tags naive datetimes as UTC, so we just pass `now` as-is
        # — both flavors reach the same boolean for any well-formed input.
        return is_pedido_token_valid(expires_at, now=now)
    return is_pedido_token_valid(expires_at)


def _pedido_total_gs(p: Pedido) -> int:
    """Compute the pedido's total in Gs. (qty * unit_price_gs per line)."""
    return sum(
        to_int_gs(Decimal(str(ln.qty or 0)) * Decimal(str(ln.unit_price_gs or 0))) for ln in p.lines
    )


def _int_or_none(value: Any) -> int | None:
    """Phase 13 (2026-10-01): parse a form FK field. Returns None for
    empty/missing/invalid (vs raising HTTPException) so the cashier
    who didn't pick a profile gets a pedido without invoice_profile_id
    instead of a 500. The legacy invoice_ruc/invoice_name still get
    populated from the form below."""
    s = (str(value or "")).strip()
    if not s:
        return None
    try:
        return int(s)
    except (ValueError, TypeError):
        return None


def _parse_date_or_none(value: Any) -> date | None:
    """Phase 13: parse a YYYY-MM-DD date string. Returns None for empty
    or invalid. The Pedido column is Date (not DateTime), so callers
    receive a date object back."""
    s = (str(value or "")).strip()
    if not s:
        return None
    try:
        # ISO date; we'll coerce at the SQLAlchemy level
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


from app.services.customer_address import (
    PARAGUAY_DEPARTMENTS,
)
from app.services.customer_address import (
    ventana_text as _ventana_text_helper,
)


def _ventana_text_for(pedido_or_decorated: Any) -> str:
    """Phase 13 (2026-10-01): render the preferred-arrival-window text
    for the pedido detail page. Uses the helper from
    app.services.customer_address so the wording is consistent across
    the receipt, the pedido detail, and the customer detail.

    Accepts both a Pedido ORM row and a decorated dict (the detail
    handler passes the decorated version that already has string dates).
    """

    def g(k: Any) -> Any:
        # ORM-row style (attribute access) or dict-style (key access)
        try:
            v = getattr(pedido_or_decorated, k)
        except AttributeError:
            v = pedido_or_decorated.get(k)
        return v or None

    pref = g("delivery_preference")
    start = g("delivery_window_start")
    end = g("delivery_window_end")
    scheduled = g("delivery_scheduled_date")
    # scheduled_date is a date object on the ORM; the decorated dict
    # converts it to ISO YYYY-MM-DD via the existing _decorate_pedido.
    if scheduled and hasattr(scheduled, "strftime"):
        scheduled = scheduled.strftime("%Y-%m-%d")
    if start and hasattr(start, "strftime"):
        start = start.strftime("%H:%M")
    if end and hasattr(end, "strftime"):
        end = end.strftime("%H:%M")
    return _ventana_text_helper(pref, start, end, scheduled)


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
    today = datetime.now(ASUNCION_TZ).date()
    promised = p.promised_date.date() if isinstance(p.promised_date, datetime) else p.promised_date
    age_days = (today - promised).days
    return {
        "id": p.id,
        "customer_id": p.customer_id,
        "customer_name": p.customer_name or (p.customer.name if p.customer else "(sin nombre)"),
        "customer_phone": p.customer_phone or (p.customer.phone if p.customer else None),
        "promised_date": promised,
        "promised_date_iso": promised.isoformat() if promised else "",
        "promised_time": p.promised_time or "",
        "channel": normalize_channel(p.channel),  # normalized display name
        "channel_raw": p.channel,  # original DB value for CSV export
        "status": p.status,
        "payment_intent": p.payment_intent,
        # Phase 14 (2026-10-01): template alias — `payment_method` is
        # the human-readable name on the list view; `payment_intent` is
        # the DB column. Both surface the same data so the cashier sees
        # "efectivo" / "transferencia" without a snake_case mismatch.
        "payment_method": p.payment_intent,
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
        # Phase 13 (2026-10-01): delivery-window fields used by the
        # ventana badge on the detail template (and by `_ventana_text_for`
        # which falls back gracefully when any of these is None).
        "delivery_preference": p.delivery_preference,
        "delivery_window_start": (
            p.delivery_window_start.strftime("%H:%M")
            if hasattr(p.delivery_window_start, "strftime")
            else p.delivery_window_start
        ),
        "delivery_window_end": (
            p.delivery_window_end.strftime("%H:%M")
            if hasattr(p.delivery_window_end, "strftime")
            else p.delivery_window_end
        ),
        "delivery_scheduled_date": (
            p.delivery_scheduled_date.isoformat()
            if hasattr(p.delivery_scheduled_date, "isoformat")
            else p.delivery_scheduled_date
        ),
        # Phase 13 (2026-10-01): the FK pointers back to the structured
        # address + the invoice profile that were used at pedido time.
        "customer_address_id": p.customer_address_id,
        "customer_invoice_profile_id": p.customer_invoice_profile_id,
        "address_text": p.address_text,
        "invoice_ruc": p.invoice_ruc,
        "invoice_name": p.invoice_name,
        # Phase 14 (2026-10-01): ventana_text precomputed here (single
        # source of truth — all templates read it). Lets the list view,
        # board kanban, recibo, and pedido_publico share one render.
        "ventana_text": _ventana_text_for(p),
        # Phase 14 (2026-10-01): columns that the ORM has but the
        # decorator previously dropped. The
        # `test_decorate_pedido_exposes_all_orm_columns` regression test
        # catches any drift here. These five are used by the
        # detail/public/board/recibo flows but the helper used to forget
        # them.
        "delivery_zone_id": p.delivery_zone_id,
        "payment_receipt_path": p.payment_receipt_path,
        "payment_receipt_uploaded_at": (
            p.payment_receipt_uploaded_at.isoformat() if p.payment_receipt_uploaded_at else None
        ),
        "public_token_expires_at": (
            p.public_token_expires_at.isoformat() if p.public_token_expires_at else None
        ),
        "updated_at": (p.updated_at.isoformat() if p.updated_at else None),
    }


def _group_pedidos(session: Session, pedidos: Iterable[Pedido]) -> dict[str, list[dict]]:
    """Split pedidos into 3 sections: Hoy/Mañana, Esta semana, Pendientes viejos.

    - Hoy/Mañana: promised_date in [today, today+1]
    - Esta semana: promised_date in [today+2, today+7]
    - Pendientes viejos: status='pending' AND promised_date < today
    """
    today = datetime.now(ASUNCION_TZ).date()
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
    today = datetime.now(ASUNCION_TZ).date()
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
            (Pedido.customer_name.ilike(f"%{search}%") | Pedido.customer_phone.ilike(f"%{search}%"))
        )

    # Count total for pagination (reuse the base where, no order/offset/limit)
    count_stmt = select(func.count()).select_from(stmt_base.subquery())
    total_count = session.scalar(count_stmt) or 0

    # Paginate: apply order then offset/limit
    stmt = (
        stmt_base.order_by(Pedido.promised_date.asc(), Pedido.promised_time.asc())
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
        "prev_url": f"/pedidos?status_filter={status_filter}&search={search}&page={page - 1}"
        if page > 1
        else None,
        "next_url": f"/pedidos?status_filter={status_filter}&search={search}&page={page + 1}"
        if page < total_pages
        else None,
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
    today = datetime.now(ASUNCION_TZ).date()
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
    def _kanban(col: object) -> list[dict]:
        from app.services.customer_address import ventana_text

        rows = []
        for p in pedidos:
            if p.status != col:
                continue
            # Phase 14 (2026-10-01): ventana + structured address hint on
            # the kitchen card so prep staff can see at a glance whether
            # it's ASAP vs scheduled (affects pacing).
            start = (
                p.delivery_window_start.strftime("%H:%M")
                if hasattr(p.delivery_window_start, "strftime")
                else p.delivery_window_start
            )
            end = (
                p.delivery_window_end.strftime("%H:%M")
                if hasattr(p.delivery_window_end, "strftime")
                else p.delivery_window_end
            )
            scheduled = (
                p.delivery_scheduled_date.isoformat()
                if hasattr(p.delivery_scheduled_date, "isoformat")
                else p.delivery_scheduled_date
            )
            rows.append(
                {
                    "id": p.id,
                    "label": f"#{p.id}",
                    "status": p.status,
                    "customer": p.customer.name if p.customer else None,
                    "promised": f"{p.promised_date} {p.promised_time or ''}".strip(),
                    "lines": [
                        f"{ln.qty:g} × {(ln.product.name if ln.product else '#' + str(ln.product_id))}"
                        for ln in (p.lines or [])
                    ][:6],
                    "created_at": p.created_at,
                    # Phase 14: ventana + invoice + address summary on the card
                    "ventana_text": ventana_text(p.delivery_preference, start, end, scheduled),
                    "address_text": p.address_text or "",
                    "invoice_ruc": p.invoice_ruc or "",
                    "invoice_name": p.invoice_name or "",
                }
            )
        return rows

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
    customer_id: int | None = Query(None, ge=1),
    from_: int | None = Query(None, alias="from", ge=1),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Render the new-pedido form with the product picker.

    Query params:
      ?customer_id=N (POS bridge from /clientes/{id}): preselects that
        customer so the cashier skips the picker entirely. Also computes
        smart defaults (phone, zone, RUC, time window, etc.) from the
        customer's history and passes them as `customer_prefill` for the
        page to apply on load.
      ?from=N (Pedir de nuevo): clone the lines from pedido N (which must
        belong to ?customer_id). Otherwise the most recent pedido's lines
        are used as a default suggestion.

    The template renders a hidden `<script id="customer-prefill" type="application/json">`
    with the defaults; static/pedido-prefill.js reads it and patches the
    form fields once the customer is picked.
    """
    from app.services.customer_prefill import compute_customer_defaults

    preset_customer = None
    prefill: dict = {}
    clone_lines: list[dict] = []
    if customer_id:
        preset_customer = session.get(Customer, customer_id)
        if preset_customer:
            defaults = compute_customer_defaults(session, customer_id, from_pedido_id=from_)
            prefill = defaults.to_dict()
            clone_lines = defaults.clone_lines

    products = session.scalars(select(Product).order_by(Product.name)).all()
    customers = session.scalars(
        select(Customer).order_by(Customer.created_at.desc()).limit(50)
    ).all()
    tomorrow = datetime.now(ASUNCION_TZ).date() + timedelta(days=1)

    # Load active delivery zones for the picker
    from app.rms.models import DeliveryZone

    delivery_zones = session.scalars(
        select(DeliveryZone).where(DeliveryZone.is_active.is_(True)).order_by(DeliveryZone.position)
    ).all()

    return render(
        request,
        "pedidos_nuevo.html",
        {
            "products": products,
            "customers": customers,
            "preset_customer": preset_customer,
            "customer_prefill": prefill,
            "clone_lines": clone_lines,
            "from_pedido_id": from_,
            "channels": CHANNELS,
            "payment_methods": sorted(set(ALLOWED_PAYMENT_METHODS)),
            "delivery_zones": delivery_zones,
            "today_iso": datetime.now(ASUNCION_TZ).date().isoformat(),
            "default_promised_date": tomorrow.isoformat(),
            # Phase 14 (2026-10-01): 18 PY departments + Asunción Capital
            # for the address_departamento combo (was a hand-rolled
            # <select> with a duplicate "Amambay" entry as a bug).
            "paraguay_departments": PARAGUAY_DEPARTMENTS,
            "paraguay_departments_src": [{"value": d, "label": d} for d in PARAGUAY_DEPARTMENTS],
        },
    )


@router.get("/api/customer-defaults/{customer_id}")
def pedidos_customer_defaults(
    customer_id: int = Path(..., ge=1),
    from_: int | None = Query(None, alias="from", ge=1),
    session: Session = Depends(get_session),
) -> JSONResponse:
    """Return smart-default JSON for a customer. Called by the picker JS.

    Response shape matches CustomerPrefill.to_dict() — see
    app.services.customer_prefill. The frontend patches form fields
    without re-rendering.
    """
    payload = customer_defaults_as_json(session, customer_id)
    if from_:
        from app.services.customer_prefill import compute_customer_defaults

        payload = compute_customer_defaults(session, customer_id, from_pedido_id=from_).to_dict()
    return JSONResponse(payload)


@router.get("/api/customer/{customer_id}/addresses")
def pedidos_customer_addresses(
    customer_id: int,
    session: Session = Depends(get_session),
) -> JSONResponse:
    """P3 delivery: address book for the pedido form's customer picker.

    Returns the customer's saved addresses (label + text + zone) so the
    form can autofill address/zone when a known customer is picked, plus
    their preferred zone id.
    """
    from app.rms.models import CustomerAddress

    cust = session.get(Customer, customer_id)
    if cust is None:
        return JSONResponse({"addresses": [], "preferred_zone_id": None})
    addrs = session.scalars(
        select(CustomerAddress)
        .where(CustomerAddress.customer_id == customer_id)
        .order_by(CustomerAddress.is_default.desc(), CustomerAddress.id)
    ).all()
    return JSONResponse(
        {
            "addresses": [
                {
                    "id": a.id,
                    "label": a.label,
                    "address_text": a.address_text,
                    "zone_id": a.zone_id,
                    "is_default": bool(a.is_default),
                }
                for a in addrs
            ],
            "preferred_zone_id": cust.preferred_zone_id,
        }
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
    channel: str = Form(Channel.WHATSAPP.value),
    payment_intent: str = Form("efectivo"),
    notes: str = Form(""),
    delivery_zone_id: str = Form(""),
    # P3 delivery batch: address snapshot + arrival window + factura
    address_text: str = Form(""),
    delivery_window_start: str = Form(""),
    delivery_window_end: str = Form(""),
    invoice_ruc: str = Form(""),
    invoice_name: str = Form(""),
    save_address: str = Form(""),  # "1" → persist to customer_address
    address_label: str = Form("casa"),
    # Phase 13 (2026-10-01): preferred-arrival window (not a promise)
    delivery_preference: str = Form("asap"),  # asap | window | scheduled
    delivery_scheduled_date: str = Form(""),  # YYYY-MM-DD for scheduled
    # Phase 13: FK to the chosen invoice profile + chosen address.
    # The form also keeps the legacy invoice_ruc/invoice_name/address_text
    # fields so existing callers don't break.
    customer_invoice_profile_id: str = Form(""),
    customer_address_id: str = Form(""),
    # Phase 13: structured address fields (all optional; composed into
    # address_text at write time so the receipt stays a single line)
    address_calle_principal: str = Form(""),
    address_calle_secundaria: str = Form(""),
    address_numero: str = Form(""),
    address_edificio: str = Form(""),
    address_piso: str = Form(""),
    address_unidad: str = Form(""),
    address_barrio: str = Form(""),
    address_ciudad: str = Form(""),
    address_departamento: str = Form(""),
    address_codigo_postal: str = Form(""),
    address_recipient_name: str = Form(""),
    address_delivery_instructions: str = Form(""),
    address_kind: str = Form("HOME"),
    # T-2026-10-01: client-generated UUID, deduplicates accidental
    # double-submits within ~5s of each other. Mirrors the
    # sale_multi_idem pattern from app/routers/sales.py.
    idempotency_key: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Create a new pedido with one or more lines.

    Lines are POSTed as repeated form fields:
        product_id, qty, unit_price_gs   (one set per line)

    We pull from the form via request.form() to support a dynamic number of
    lines without exploding the function signature.
    """
    form = await request.form()

    # T-2026-10-01: idempotency reservation. If a request with the same
    # idempotency_key arrives, we return the previously-created pedido
    # via redirect) instead of creating a duplicate. Mirrors the
    # `sale_multi_idem` pattern from app/routers/sales.py.
    if idempotency_key:
        from sqlalchemy.exc import IntegrityError

        from app.rms.models import AppMeta as _AppMeta

        # Check for an existing reservation first (read-then-write).
        existing = session.scalar(
            select(_AppMeta).where(_AppMeta.key == f"pedido_idem:{idempotency_key}")
        )
        if existing is not None:
            # Try to parse {pedido_id, request_id} from the cached value.
            try:
                cached = json.loads(existing.value or "{}")
            except (ValueError, TypeError):
                cached = {}
            existing_id = cached.get("pedido_id")
            if existing_id:
                return RedirectResponse(url=f"/pedidos/{existing_id}", status_code=303)
            # Cache was a placeholder ("pending") from a request that died
            # mid-transaction. Fall through and try to reserve again.
            session.delete(existing)
            session.flush()

        try:
            session.add(
                _AppMeta(
                    key=f"pedido_idem:{idempotency_key}",
                    value="pending",
                    updated_at=datetime.now(timezone.utc).isoformat(),
                )
            )
            session.flush()
        except IntegrityError:
            session.rollback()
            # Lost the race; re-read and redirect to the winner.
            existing = session.scalar(
                select(_AppMeta).where(_AppMeta.key == f"pedido_idem:{idempotency_key}")
            )
            if existing is not None:
                try:
                    cached = json.loads(existing.value or "{}")
                except (ValueError, TypeError):
                    cached = {}
                existing_id = cached.get("pedido_id")
                if existing_id:
                    return RedirectResponse(url=f"/pedidos/{existing_id}", status_code=303)

    cust_id_str = str(customer_id or "").strip()
    cust_id_int: int | None = None
    if cust_id_str:
        try:
            cust_id_int = int(cust_id_str)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"customer_id inválido: {cust_id_str!r}",
            ) from None
    # Build list of lines from the form
    product_ids = form.getlist("line_product_id")
    qtys = form.getlist("line_qty")
    unit_prices = form.getlist("line_unit_price_gs")
    if not product_ids:
        raise HTTPException(status_code=400, detail="Al menos una línea es obligatoria")

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
        lines.append({"product_id": pid, "qty": qty, "unit_price_gs": price})
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
        # Keep the customer's ficha fresh: pedido form is often where the
        # operator learns the phone / RUC / razón social. Write back if the
        # form carries values (never blank out existing data).
        if cust_phone and cust_phone != (cust_obj.phone or ""):
            cust_obj.phone = cust_phone
        if invoice_ruc and not (cust_obj.invoice_ruc or ""):
            cust_obj.invoice_ruc = invoice_ruc
        elif invoice_ruc and invoice_ruc != (cust_obj.invoice_ruc or ""):
            cust_obj.invoice_ruc = invoice_ruc  # newest wins (operator typed it)
        if invoice_name and invoice_name != (cust_obj.invoice_name or ""):
            cust_obj.invoice_name = invoice_name

    # If user typed a name but didn't pick an existing customer, auto-create.
    if cust_obj is None and cust_name:
        existing = session.scalar(
            select(Customer).where(func.lower(Customer.name) == cust_name.lower())
        )
        if existing is not None:
            cust_obj = existing
            if cust_phone and not (existing.phone or ""):
                existing.phone = cust_phone
        else:
            cust_obj = Customer(
                name=cust_name,
                phone=cust_phone,
                invoice_ruc=(invoice_ruc or "").strip() or None,
                invoice_name=(invoice_name or "").strip() or None,
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
            pedido_total_gs = sum(round((ln["qty"] or 0) * (ln["price"] or 0)) for ln in lines)
            if pedido_total_gs < zone.min_order_gs:
                notes = (
                    (notes or "").strip()
                    + f" [WARN: pedido ₲{pedido_total_gs:,} < mínimo zona ₲{zone.min_order_gs:,}]"
                ).strip()

    # P3 profile batch: default facturación from the customer's profile
    # when the operator didn't type invoice data on the order.
    if cust_obj is not None:
        invoice_name = (invoice_name or "").strip() or (cust_obj.invoice_name or "")
        invoice_ruc = (invoice_ruc or "").strip() or (cust_obj.invoice_ruc or "")

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
        address_text=(address_text or "").strip() or None,
        delivery_window_start=(delivery_window_start or "").strip() or None,
        delivery_window_end=(delivery_window_end or "").strip() or None,
        # Phase 13 (2026-10-01): preferred-arrival window semantics
        delivery_preference=(delivery_preference or "asap").strip() or "asap",
        delivery_scheduled_date=_parse_date_or_none(delivery_scheduled_date),
        invoice_ruc=(invoice_ruc or "").strip() or None,
        invoice_name=(invoice_name or "").strip() or None,
        # Phase 13: FKs to chosen profile + chosen address
        customer_invoice_profile_id=_int_or_none(customer_invoice_profile_id),
        customer_address_id=_int_or_none(customer_address_id),
        notes=(notes or "").strip() or None,
        public_token=generate_public_token(),
        # P1-2: token expires 30 days from creation. Set at insert time
        # so the customer can always see "expires X" from the moment
        # the pedido is created (not from when migration 067 ran).
        public_token_expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    )
    session.add(pedido)
    session.flush()  # assigns pedido.id

    # P3: persist the address to the customer's address book (opt-in
    # checkbox) so the next pedido to this person is one click.
    if save_address == "1" and cust_obj and (address_text or "").strip():
        from app.rms.models import CustomerAddress

        first_for_customer = not session.scalar(
            select(CustomerAddress.id).where(CustomerAddress.customer_id == cust_obj.id).limit(1)
        )
        session.add(
            CustomerAddress(
                customer_id=cust_obj.id,
                label=(address_label or "casa").strip()[:32] or "casa",
                address_text=address_text.strip(),
                zone_id=zone_int,
                is_default=first_for_customer,
                # Phase 13: structured address columns from the form
                calle_principal=address_calle_principal.strip() or None,
                calle_secundaria=address_calle_secundaria.strip() or None,
                numero=address_numero.strip() or None,
                edificio=address_edificio.strip() or None,
                piso=address_piso.strip() or None,
                unidad=address_unidad.strip() or None,
                barrio=address_barrio.strip() or None,
                ciudad=address_ciudad.strip() or None,
                departamento=address_departamento.strip() or None,
                pais="PRY",
                codigo_postal=address_codigo_postal.strip() or None,
                recipient_name=address_recipient_name.strip() or None,
                delivery_instructions=address_delivery_instructions.strip() or None,
                address_kind=(address_kind or "HOME").strip() or "HOME",
            )
        )
        # Remember the zone as the customer's preference too
        if zone_int and not cust_obj.preferred_zone_id:
            cust_obj.preferred_zone_id = zone_int

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

    # Phase 11 — record PedidoEvent rows so the timeline surfaces this
    # pedido's lifecycle in the detail view. We use the cheap batch-add
    # pattern: add all events at once, then flush once.
    from app.services.pedido_events import PedidoEventService

    actor = str(current_user_id(request) or "operator")
    PedidoEventService.record(
        session,
        pedido.id,
        "created",
        actor=actor,
        payload={
            "n_lines": len(lines),
            "channel": channel_normalized,
            "promised_date": pedido.promised_date.isoformat(),
            "total_gs": sum(ln["qty"] * ln["unit_price_gs"] for ln in lines),
        },
    )
    for ln in lines:
        PedidoEventService.record(
            session,
            pedido.id,
            "line_added",
            actor=actor,
            payload={
                "product_id": ln["product_id"],
                "qty": ln["qty"],
                "unit_price_gs": ln["unit_price_gs"],
            },
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
            "total_gs": sum(ln["qty"] * ln["unit_price_gs"] for ln in lines),
        },
        request=request,
    )
    # PRODUCCION-V2 Fase 4: a new pedido shifts the demand for the
    # promised date. Invalidate the cache so the next /produccion
    # render recomputes. Best-effort: errors are swallowed.
    # pedido.promised_date is a datetime OR date depending on caller;
    # snapshot rows are keyed by date.isoformat() so normalize here.
    # Note: do this BEFORE safe_commit so the DELETE joins the same
    # transaction and persists without a second commit dance.
    promised_date_norm = _as_date(pedido.promised_date)
    if promised_date_norm is not None:
        try:
            invalidate_demand_for_dates(session, [promised_date_norm])
        except Exception:
            pass  # cache stays stale; 5-min TTL will eventually catch up
    safe_commit(session)

    # T-2026-10-01: stamp the idempotency reservation with the new
    # pedido_id so a follow-up POST with the same key redirects back.
    if idempotency_key:
        from app.rms.models import AppMeta as _AppMeta

        session.execute(
            update(_AppMeta)
            .where(_AppMeta.key == f"pedido_idem:{idempotency_key}")
            .values(
                value=json.dumps(
                    {
                        "pedido_id": pedido.id,
                        "request_id": getattr(request.state, "request_id", "") or "",
                    }
                ),
                updated_at=datetime.now(timezone.utc).isoformat(),
            )
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

    today = datetime.now(ASUNCION_TZ).date()
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
            (Pedido.customer_name.ilike(f"%{search}%") | Pedido.customer_phone.ilike(f"%{search}%"))
        )

    stmt = stmt.order_by(Pedido.promised_date.asc())
    pedidos = list(session.scalars(stmt))

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "ID",
            "Fecha prometida",
            "Hora prometida",
            "Cliente",
            "Teléfono",
            "Canal",
            "Estado",
            "Líneas",
            "Total Gs.",
            "Notas",
            "Razón cancelación",
            "Creado",
            "Cumplido",
        ]
    )
    for p in pedidos:
        _decorate_pedido(p, session)
        writer.writerow(
            [
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
            ]
        )

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=pedidos_{datetime.now(ASUNCION_TZ).date().isoformat()}.csv"
        },
    )


# --- Public pickup-share endpoint (NO AUTH) ---------------------------------
# Lives at root so the URL is short enough for WhatsApp messages:
# https://sazon.app/p/{token}


@public_router.get("/p/{token}", response_class=HTMLResponse)
def public_pedido(request: Request, token: str) -> HTMLResponse:
    """Public, no-auth pickup-share page rendered for the customer.

    Used as a WhatsApp-shareable confirmation link so the customer can see
    "what they ordered + when to come" without logging in. The token is a
    22-char public_token generated when the pedido was created; collision-
    resistance comes from the random token + the bounded single-tenant
    volume of pedidos.

    P1-2 (2026-09-29) hardening:
      - The public_token now expires 30 days after creation (see
        migration 067 + Pedido.public_token_expires_at). An expired
        link returns 410 Gone, prompting the customer to ask the
        bakery for a fresh one.
      - This endpoint is rate-limited per client IP via the shared
        ``public_tokens.enforce_rate_limit`` helper (30 views per
        5 minutes).
      - The token-shape + expiry-validation helpers are the shared
        ``public_tokens`` ones (refactored 2026-10-02 so /p/{token}
        and /r/{token} share one source of truth).

    Uses ``request.app.state.session_factory`` so the test engine
    (injected by the ``client`` fixture's monkey-patch of
    ``make_engine_dialect``) is honored — calling ``make_engine()`` here
    would bypass the test engine and read the production DB, breaking
    the round-trip test that posts a pedido in the test DB and reads it
    back via this endpoint.
    """
    with request.app.state.session_factory() as session:
        # P1-2: rate-limit first (cheap, before the DB hit). The shared
        # helper counts AuditLog.action == "public.pedido.view" so this
        # is the same enforcement as before the refactor — the change
        # is only that the count + window now live in public_tokens.
        public_token_enforce_rate_limit(request, session, action_label="public.pedido.view")

        # Pedido.id is an Integer PK; look up by public_token instead
        # so /p/{token} resolves to the pedido sharing that token.
        # (Earlier this used session.get(Pedido, token), which queried
        # by the int PK and silently returned None for valid string
        # tokens — making the page 404 for every real customer.)
        pedido = session.execute(
            select(Pedido).where(Pedido.public_token == token).options(selectinload(Pedido.lines))
        ).scalar_one_or_none()
        if pedido is None:
            raise HTTPException(status_code=404, detail="Pedido no encontrado")

        # P1-2: enforce token expiry. Returns 410 Gone (not 404) so the
        # customer understands the link has aged out, not that the
        # pedido never existed.
        if not _is_token_valid(pedido):
            raise HTTPException(
                status_code=410,
                detail=("Este link venció. Pedile a la panadería que te mande uno nuevo."),
            )

        # Audit the view for forensics + rate-limit counting.
        audit_record(
            session,
            user_id=None,
            action="public.pedido.view",
            request=request,
            target_type="pedido",
            target_id=pedido.id,
            detail={"public_token_suffix": token[-4:]},
        )
        try:
            session.commit()
        except Exception:
            session.rollback()
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
                "shop_name": "Sazón",
                "currency_label": "Gs.",
            },
        )


# P1-B3: public comprobante upload from /p/{token}
# No auth, no CSRF (public endpoint by design — the random 8-char token IS
# the auth). Files saved under /data/payment_receipts/{pedido_id}/.
_ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}
_MAX_BYTES = 8 * 1024 * 1024  # 8 MB


@public_router.post("/p/{token}/comprobante", response_class=HTMLResponse)
async def pedido_publico_comprobante(
    request: Request,
    token: str,
    file: UploadFile = File(...),
    _csrf_check: None = Depends(verify_form_csrf),
) -> HTMLResponse:
    """Receive a payment receipt uploaded from /p/{token}.

    The page rendered after the upload is the same /p/{token} page, but
    with ?upload=ok or ?upload=error in the query string so the template
    can show a banner. We deliberately avoid redirect-after-POST here
    because the customer has no browser history with this URL and the
    inline banner keeps it self-contained.
    """
    from app.rms.config import DATA_DIR

    with request.app.state.session_factory() as session:
        pedido = session.execute(
            select(Pedido).where(Pedido.public_token == token)
        ).scalar_one_or_none()
        if pedido is None:
            raise HTTPException(status_code=404, detail="Pedido no encontrado")

        # P1-2: same expiry enforcement as the GET route. An expired
        # link can't be used to upload either — customers must ask the
        # bakery for a fresh one.
        if not _is_token_valid(pedido):
            raise HTTPException(
                status_code=410,
                detail=("Este link venció. Pedile a la panadería que te mande uno nuevo."),
            )

        # Validate file extension (cheap, prevents shell-pasted junk)
        filename = (file.filename or "comprobante.jpg").lower()
        ext = "." + filename.rsplit(".", 1)[-1] if "." in filename else ""
        if ext not in _ALLOWED_EXT:
            return _render_public_with_flash(
                request,
                pedido,
                token,
                "error",
                f"Formato no permitido: {ext or 'sin extensión'}. Subí JPG, PNG, WEBP o PDF.",
            )

        # Read with a hard cap (8 MB) so a malicious client can't OOM us.
        contents = await file.read(_MAX_BYTES + 1)
        if len(contents) > _MAX_BYTES:
            return _render_public_with_flash(
                request,
                pedido,
                token,
                "error",
                "Archivo demasiado grande (máx 8 MB).",
            )

        # Save to /data/payment_receipts/{pedido_id}/{timestamp}_{safe_name}.
        # pedido_id namespaces the directory so a re-upload overwrites cleanly.
        receipts_root = DATA_DIR / "payment_receipts" / str(pedido.id)
        receipts_root.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in filename)
        stored_name = f"{timestamp}_{safe_name}"
        stored_path = receipts_root / stored_name
        stored_path.write_bytes(contents)

        # Store relative path so it survives data-dir moves.
        relative_path = f"payment_receipts/{pedido.id}/{stored_name}"
        pedido.payment_receipt_path = relative_path
        pedido.payment_receipt_uploaded_at = datetime.now(timezone.utc)
        session.commit()

        # Rate-limit-style audit: every upload is recorded even though the
        # endpoint is unauthenticated (the public_token is the audit subject).
        audit_record(
            session,
            user_id=None,
            action="public.pedido.comprobante.upload",
            request=request,
            detail={
                "pedido_id": pedido.id,
                "filename": stored_name,
                "bytes": len(contents),
                "ext": ext,
            },
        )
        session.commit()

        return _render_public_with_flash(
            request,
            pedido,
            token,
            "ok",
            "Comprobante recibido. Te avisamos por WhatsApp cuando confirmemos.",
        )


def _render_public_with_flash(
    request: Request,
    pedido: Pedido,
    token: str,
    flash_kind: str,
    flash_msg: str,
) -> HTMLResponse:
    """Re-render the /p/{token} page with a flash banner."""
    with request.app.state.session_factory() as session:
        # re-fetch with lines loaded (session may have been closed)
        pedido = session.execute(
            select(Pedido).where(Pedido.public_token == token).options(selectinload(Pedido.lines))
        ).scalar_one()
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
                "shop_name": "Sazón",
                "currency_label": "Gs.",
                "flash_kind": flash_kind,
                "flash_msg": flash_msg,
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
        Pedido,
        pedido_id,
        options=[
            selectinload(Pedido.lines).selectinload(PedidoLine.product),
            selectinload(Pedido.customer),
        ],
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

    # Phase 4: build the timeline + customer pedido history
    timeline = build_pedido_timeline(session, pedido)
    decorated["timeline"] = [ev.to_dict() for ev in timeline]
    if pedido.customer_id:
        recent = customer_recent_pedidos(
            session, pedido.customer_id, limit=8, exclude_pedido_id=pedido.id
        )
        decorated["recent_pedidos"] = [s.to_dict() for s in recent]
    else:
        decorated["recent_pedidos"] = []

    # Tier 6.3 (2026-10-01): linked sales (migration 076) + loyalty impact.
    # Pedido.sales relationship returns every Sale whose
    # linked_pedido_id == this pedido.id (vs. the legacy single
    # fulfilled_sale_id which only pointed at the FIRST sale). The
    # detail page now shows the full set so the operator can verify
    # each line was fulfilled.
    from app.rms.models import LoyaltyTransaction
    from app.rms.models import Sale as SaleModel

    linked_sales: list[dict] = []
    if pedido.customer_id:
        sales = session.scalars(
            select(SaleModel)
            .where(SaleModel.linked_pedido_id == pedido.id)
            .order_by(SaleModel.id.asc())
        ).all()
        linked_sales = [
            {
                "id": s.id,
                "product_name": (s.product.name if s.product else f"#{s.product_id}"),
                "qty": float(s.qty),
                "unit_price_gs": int(s.unit_price_gs or 0),
                "sold_at": s.sold_at,
            }
            for s in sales
        ]
    decorated["linked_sales"] = linked_sales

    # Loyalty impact: sum up the points earned / redeemed on the
    # LoyaltyTransaction rows whose sale_id points at a sale generated
    # by this pedido. Operators use this to confirm "this pedido le
    # sumó X puntos al cliente".
    loyalty_impact: dict = {
        "earned_points": 0,
        "redeemed_points": 0,
        "net_points": 0,
        "transactions": [],
    }
    if pedido.customer_id and linked_sales:
        sale_ids = [s["id"] for s in linked_sales]
        txs = session.scalars(
            select(LoyaltyTransaction)
            .where(LoyaltyTransaction.customer_id == pedido.customer_id)
            .where(LoyaltyTransaction.sale_id.in_(sale_ids))
            .order_by(LoyaltyTransaction.recorded_at.desc())
            .limit(20)
        ).all()
        for tx in txs:
            loyalty_impact["transactions"].append(
                {
                    "delta": int(tx.delta or 0),
                    "reason": tx.reason or "",
                    "recorded_at": tx.recorded_at,
                    "sale_id": tx.sale_id,
                }
            )
            if (tx.reason or "") == "earn_sale":
                loyalty_impact["earned_points"] += int(tx.delta or 0)
            elif (tx.reason or "") == "redeem":
                # `delta` for a redeem row is NEGATIVE (e.g. -50). We
                # store the absolute amount in `redeemed_points` so the
                # display "pts canjeados" shows "50" not "-50". The
                # net_points math then becomes earned + redeemed (where
                # redeemed is already positive) only when subtracting.
                loyalty_impact["redeemed_points"] += abs(int(tx.delta or 0))
        loyalty_impact["net_points"] = (
            loyalty_impact["earned_points"] - loyalty_impact["redeemed_points"]
        )
    decorated["loyalty_impact"] = loyalty_impact

    return render(
        request,
        "pedido_detalle.html",
        {
            "pedido": decorated,
            "transitions": PedidoStateMachine.allowed_next(pedido.status),
            "can_fulfill": PedidoStateMachine.is_fulfillable(pedido.status),
            "channels": CHANNELS,
            "payment_methods": sorted(
                set(ALLOWED_PAYMENT_METHODS)
                | {"efectivo", "transferencia", "qr", "tarjeta", "otro"}
            ),
            # Phase 13 (2026-10-01): the rendered ventana text for the
            # template's badge (uses "ventana preferida" wording + the
            # "(no es garantía)" suffix that the cashier should always
            # see). Scheduled_date comes from the pedido; preference
            # defaults to "asap" for legacy rows that predate migration 081.
            "ventana_text": _ventana_text_for(decorated),
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
    # PRODUCCION-V2 Fase 4: a status change shifts qty_pedidos for the
    # promised date (e.g., pending → cancelled removes the line from
    # demand; pending → confirmed/ready adds to qty_pedidos_confirmed).
    # Best-effort: do this BEFORE safe_commit so the DELETE joins the
    # same transaction.
    promised_date_norm = _as_date(pedido.promised_date)
    if promised_date_norm is not None:
        invalidate_demand_for_dates(session, [promised_date_norm])
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
            initial_value = __import__("json").dumps(
                {
                    "pedido_id": str(pedido_id),
                    "sale_id": "",  # updated below
                    "request_id": request_id_pedido,
                }
            )
            session.add(
                _AppMeta(
                    key=f"pedido_fulfill_idem:{idempotency_key}",
                    value=initial_value,
                    updated_at=datetime.now(timezone.utc).isoformat(),
                )
            )
            session.flush()  # surface IntegrityError without committing
        except IntegrityError:
            session.rollback()
            return RedirectResponse(
                url=f"/pedidos/{pedido_id}?flash=pedido_fulfill_duplicate",
                status_code=303,
            )

    pedido = session.get(Pedido, pedido_id, options=[selectinload(Pedido.lines)])
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
            except Exception as exc:
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
                    shortfalls.append(
                        {
                            "ingredient": ing.name if ing else f"# {ingredient_id}",
                            "shortfall": round(abs(after), 3),
                            "product": line_product.name,
                        }
                    )
    except Exception as exc:
        # Defensive: if the calc itself blows up, do not block the fulfill;
        # log loudly so ops sees it, but proceed (matches pre-fix behavior).
        logger.warning(
            f"pedidos.fulfill: stock-preview calc failed for pedido {pedido.id}: {exc!r}"
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

    # T-2026-10-04: when force=true and there are real shortfalls, temporarily
    # disable the stock_qty >= 0 BEFORE INSERT/UPDATE triggers so the
    # operator's explicit override can actually push stock negative. Without
    # this, BACKLOG #3's safety triggers fire BEFORE the force path can act,
    # crashing with IntegrityError on the first negative UPDATE. Triggers are
    # recreated at the end of the function so the constraint is durable.
    force_bypass_active = bool(force_flag and shortfalls)
    bind = session.get_bind()
    if force_bypass_active and bind.dialect.name == "sqlite":
        from sqlalchemy import text as _sa_text

        try:
            session.execute(_sa_text("DROP TRIGGER IF EXISTS ingredient_stock_qty_positive_insert"))
            session.execute(_sa_text("DROP TRIGGER IF EXISTS ingredient_stock_qty_positive_update"))
        except Exception as _drop_exc:  # pragma: no cover - defensive
            logger.warning(f"force-fulfill: could not drop stock triggers: {_drop_exc!r}")

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
            # Migration 076: link this sale back to the pedido so the
            # detail timeline can show every sale generated by this pedido
            # (not just the first via pedido.fulfilled_sale_id).
            linked_pedido_id=pedido.id,
        )
        # apply_sale commits internally — refresh from the new identity.
        ln.fulfilled_qty = float(ln.qty)
        first_sale_id = first_sale_id or result.sale_id
        n_sales += 1

    # Update the pedido itself.
    pedido.fulfilled_at = datetime.now(ASUNCION_TZ)
    pedido.fulfilled_sale_id = first_sale_id
    pedido.status = "fulfilled"

    # Phase 11 — record status_change + sales for the pedido timeline.
    # We use the actor on the request so the timeline shows who fulfilled it.
    from app.services.pedido_events import PedidoEventService

    fulfill_actor = str(current_user_id(request) or "operator")
    PedidoEventService.record(
        session,
        pedido.id,
        "status_change",
        actor=fulfill_actor,
        payload={
            "from": "pending",
            "to": "fulfilled",
            "n_sales": n_sales,
            "first_sale_id": first_sale_id,
            "total_gs": _pedido_total_gs(pedido),
        },
    )

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
            **(
                {"force_fulfilled_over_shortfall": shortfalls}
                if (shortfalls and force_flag)
                else {}
            ),
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
            __import__("sqlalchemy")
            .select(_AppMeta)
            .where(_AppMeta.key == f"pedido_fulfill_idem:{idempotency_key}")
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

    # PRODUCCION-V2 Fase 4: fulfilling a pedido removes the lines from
    # qty_pedidos for the promised date (status → fulfilled) AND
    # creates a Sale row that shifts the 14d rolling forecast. Invalidate
    # both dates. The sale date is "today" by clock at fulfill time
    # (Asunción local — the cook lives in PY, not UTC).
    # Best-effort: do this BEFORE safe_commit so the DELETEs join the
    # same transaction.
    today_local = datetime.now(ASUNCION_TZ).date()
    dates_to_invalidate = [today_local]
    promised_date_norm = _as_date(pedido.promised_date)
    if promised_date_norm is not None:
        dates_to_invalidate.append(promised_date_norm)
    invalidate_demand_for_dates(session, dates_to_invalidate)
    safe_commit(session)

    # T-2026-10-04: recreate the stock_qty safety triggers we dropped at the
    # top of the function. Best-effort — if safe_commit raised, the triggers
    # are gone for the rest of this session, but Postgres uses a model-level
    # CheckConstraint that can't be temporarily dropped, so we accept that
    # edge case here (the operator would notice on the next fulfill).
    if force_bypass_active and bind.dialect.name == "sqlite":
        from sqlalchemy import text as _sa_text2

        try:
            session.execute(
                _sa_text2(
                    "CREATE TRIGGER IF NOT EXISTS ingredient_stock_qty_positive_insert "
                    "BEFORE INSERT ON ingredient "
                    "FOR EACH ROW WHEN NEW.stock_qty < 0 "
                    "BEGIN SELECT RAISE(ABORT, 'ingredient.stock_qty must be >= 0'); END"
                )
            )
            session.execute(
                _sa_text2(
                    "CREATE TRIGGER IF NOT EXISTS ingredient_stock_qty_positive_update "
                    "BEFORE UPDATE ON ingredient "
                    "FOR EACH ROW WHEN NEW.stock_qty < 0 "
                    "BEGIN SELECT RAISE(ABORT, 'ingredient.stock_qty must be >= 0'); END"
                )
            )
            session.commit()
        except Exception as _recreate_exc:  # pragma: no cover - defensive
            logger.warning(f"force-fulfill: could not recreate stock triggers: {_recreate_exc!r}")

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

        # P43 (2026-10-07): was comparing against "WhatsApp" (uppercase)
        # which never matches because channel values are lowercase
        # (Channel.WHATSAPP.value = "whatsapp"). This silently disabled
        # the pedido_listo / whatsapp template path.
        template_key = "pedido_listo" if pedido.channel == Channel.WHATSAPP.value else "generic"
        template_channel = Channel.WHATSAPP.value if pedido.channel == Channel.WHATSAPP.value else "email"
        row = session.execute(
            _select(MT).where(
                MT.channel == template_channel,
                MT.key == template_key,
                MT.is_active.is_(True),
            )
        ).scalar_one_or_none()
        if row is not None:
            from app.routers.settings_runtime import render_template

            msg = render_template(
                row.body,
                {
                    "customer_name": pedido.customer_name or "",
                    "pedido_id": pedido.id,
                    "total_gs": pedido.total_gs or 0,
                    "business_name": "Sazón",
                },
            )
    except Exception as exc:
        logger.warning(
            f"pedidos._send_fulfill_notification: render_template failed (fallback to legacy msg): {exc!r}"
        )
    if msg is None:
        msg = (
            f"¡Tu pedido #{pedido.id} esta listo para retirar! Te esperamos 😊"
            if pedido.channel == Channel.WHATSAPP.value  # P43: lowercase comparison (was "WhatsApp")
            else f"Tu pedido #{pedido.id} esta listo para retirar. Gracias!"
        )

    import logging
    import os

    twilio_sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
    twilio_token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
    twilio_from_wa = os.getenv("TWILIO_WHATSAPP_FROM", "").strip()
    twilio_from_ph = os.getenv("TWILIO_PHONE_FROM", "").strip()

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
        except Exception as exc:
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
        except Exception as exc:
            logger.warning(
                f"pedidos.stock_preview: _compute_stock_moves failed for product {product.id}: {exc!r}"
            )
            continue
        for _affected_recipe_id, ingredient_id, qty_delta in moves:
            ing = session.get(Ingredient, ingredient_id) if Ingredient else None
            ing_name = ing.name if ing else f"# {ingredient_id}"
            current = ing.stock_qty if ing else 0
            after = current - abs(qty_delta)
            consumed.append(
                {
                    "ingredient": ing_name,
                    "product": product.name,
                    "qty_needed": round(abs(qty_delta), 3),
                    "current_stock": round(current, 3) if current else 0,
                    "after_stock": round(after, 3),
                    "warning": after < 0,
                }
            )
            if after < 0:
                warnings.append(
                    {
                        "ingredient": ing_name,
                        "shortfall": round(abs(after), 3),
                        "product": product.name,
                    }
                )

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
    original = session.get(Pedido, pedido_id, options=[selectinload(Pedido.lines)])
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
        # P1-2: see create_pedido above — same 30-day expiry policy.
        public_token_expires_at=datetime.now(timezone.utc) + timedelta(days=30),
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
    # PRODUCCION-V2 Fase 4: a duplicate pedido adds a new line to the
    # promised date. Invalidate. Best-effort: do this BEFORE safe_commit
    # so the DELETE joins the same transaction.
    copy_promised_norm = _as_date(copy.promised_date)
    if copy_promised_norm is not None:
        invalidate_demand_for_dates(session, [copy_promised_norm])
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
    affected_dates: set[date] = set()
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
        affected_norm = _as_date(pedido.promised_date)
        if affected_norm is not None:
            affected_dates.add(affected_norm)
        fulfilled += 1
    # PRODUCCION-V2 Fase 4: each fulfilled pedido shifts its promised
    # date's demand. Invalidate all distinct dates in one call.
    # Best-effort: do this BEFORE safe_commit so the DELETEs join the
    # same transaction.
    if affected_dates:
        try:
            invalidate_demand_for_dates(session, list(affected_dates))
        except Exception:
            pass
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
    affected_dates: set[date] = set()
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
        affected_norm = _as_date(pedido.promised_date)
        if affected_norm is not None:
            affected_dates.add(affected_norm)
        cancelled += 1
    # PRODUCCION-V2 Fase 4: each cancelled pedido removes its lines
    # from qty_pedidos for the promised date. Invalidate.
    # Best-effort: do this BEFORE safe_commit so the DELETEs join the
    # same transaction.
    if affected_dates:
        try:
            invalidate_demand_for_dates(session, list(affected_dates))
        except Exception:
            pass
    safe_commit(session)
    flash = f"{cancelled} pedido(s) cancelado(s)"
    return RedirectResponse(url=f"/pedidos?flash={flash}", status_code=303)
