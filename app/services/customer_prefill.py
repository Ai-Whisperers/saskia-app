"""app.services.customer_prefill — phase 3 smart autofill for /pedidos/nuevo.

Given a customer (and optionally a past pedido to copy lines from),
compute every smart-default value the operator form needs:

  - phone: customer's primary phone
  - invoice_ruc / invoice_name: from customer.invoice_* (or CI/name fallback)
  - delivery_zone_id: customer.preferred_zone_id
  - address_text: default CustomerAddress text (casa/oficina)
  - delivery_window_start/end: most recent pedido's window (or sensible default)
  - promised_date: today + customer's average lead time (or tomorrow)
  - promised_time: most common promised_time in customer history
  - channel: customer.preferred_channel (or 'whatsapp')
  - payment_intent: customer's most common payment_intent in history
  - address_label: default address label (e.g. 'casa')
  - notes: last pedido's notes + dietary banner
  - save_address: True if customer has 0 or 1 addresses (auto-remember)
  - lines: from the source pedido (if ?from=<id> passed)
  - last_pedido_summary: short string for the "Pedir de nuevo" banner

Used by:
- /pedidos/nuevo GET handler (when ?customer_id=N is passed)
- A new JSON endpoint /pedidos/api/customer-defaults/<id> for the JS
  picker on /pedidos/nuevo to call when the customer is changed.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.rms.config import ASUNCION_TZ
from app.rms.models import Customer, CustomerAddress, Pedido, PedidoLine

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@dataclass
class CustomerPrefill:
    """Smart defaults for the new-pedido form when a customer is picked.

    All fields are JSON-serializable. None means "leave the field
    empty / fall back to global default". The frontend reads this and
    patches form fields without re-rendering.
    """

    # Contact
    phone: str | None = None
    invoice_ruc: str | None = None
    invoice_name: str | None = None

    # Delivery
    delivery_zone_id: int | None = None
    address_text: str | None = None
    address_label: str | None = None
    save_address: bool = False
    delivery_window_start: str | None = None
    delivery_window_end: str | None = None

    # When
    promised_date: str | None = None  # ISO date
    promised_time: str | None = None

    # How
    channel: str | None = None
    payment_intent: str | None = None

    # Free-form
    notes: str | None = None
    dietary_banner: str | None = None

    # Recent pedido to clone ("Pedir de nuevo")
    last_pedido_id: int | None = None
    last_pedido_summary: str | None = None
    clone_lines: list[dict] = field(default_factory=list)

    # Phase 7 — address picker: list of saved addresses for the customer.
    # Empty when the customer has 0 addresses. The frontend renders a
    # picker dropdown when length >= 2; with 1 address we auto-fill
    # without showing the picker; with 0 we just show the text input.
    available_addresses: list[dict] = field(default_factory=list)
    # Phase 13 (2026-10-01): list of invoice profiles for the customer.
    # Same shape as available_addresses — used by the new
    # /pedidos/nuevo "Perfil de facturación" dropdown. Empty list is OK
    # (the cashier falls back to typing RUC + Razón social manually).
    invoice_profiles: list[dict] = field(default_factory=list)
    # Loyalty balance + projected points (Phase 8 — for the banner)
    loyalty_points_balance: int = 0
    loyalty_points_projected: int = 0

    # Tier 6.4 (2026-10-01): tier display + suscripción prefill.
    # `tier` is the BRONZE/SILVER/GOLD/PLATINUM enum value as a string
    # (matches LoyaltyTier.value). The /pedidos/nuevo template renders
    # a small pill near the customer name so the operator sees the tier
    # at a glance while building a pedido. `active_subscriptions` is a
    # list of {product_summary, cadence, preferred_day_of_week, price_gs,
    # subscription_id} — the template renders an "Aplicar suscripción"
    # quick-pick that fills the notes field with the subscription's
    # product_summary so the operator doesn't have to retype it.
    tier: str | None = None
    active_subscriptions: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _most_common(values: list[str | None]) -> str | None:
    """Pick the most common non-null value; None if list is empty/None-only."""
    cleaned = [v for v in values if v]
    if not cleaned:
        return None
    counter = Counter(cleaned)
    return counter.most_common(1)[0][0]


def _recent_pedido_for(session: Session, customer_id: int) -> Pedido | None:
    """Return the most recent pedido for this customer."""
    return session.execute(
        select(Pedido)
        .where(Pedido.customer_id == customer_id)
        .order_by(Pedido.promised_date.desc(), Pedido.id.desc())
        .limit(1)
    ).scalar_one_or_none()


def _default_address(session: Session, customer_id: int) -> CustomerAddress | None:
    """Pick the customer's default address (is_default=True) or the first."""
    addr = session.execute(
        select(CustomerAddress)
        .where(CustomerAddress.customer_id == customer_id)
        .order_by(CustomerAddress.is_default.desc(), CustomerAddress.id.asc())
        .limit(1)
    ).scalar_one_or_none()
    return addr


def _pedido_lines_as_dicts(pedido_id: int, session: Session) -> list[dict]:
    """Return pedido lines as JSON-safe dicts for JS to recreate the rows."""
    lines = session.execute(
        select(PedidoLine).where(PedidoLine.pedido_id == pedido_id)
    ).scalars().all()
    return [
        {
            "product_id": line.product_id,
            "qty": float(line.qty),
            "unit_price_gs": int(line.unit_price_gs),
        }
        for line in lines
    ]


def compute_customer_defaults(
    session: Session,
    customer_id: int,
    *,
    from_pedido_id: int | None = None,
    today: date | None = None,
) -> CustomerPrefill:
    """Build the smart-defaults dict for a given customer.

    Args:
        session: SQLAlchemy session.
        customer_id: Customer.id whose defaults to compute.
        from_pedido_id: Optional source pedido to clone lines from
            (the "Pedir de nuevo" feature). If None, we use the most
            recent pedido's lines if any.
        today: Override for "today" — useful for tests. Defaults to
            Asunción-local today.

    Returns:
        CustomerPrefill populated with every smart-default we can derive.
    """
    today = today or datetime.now(ASUNCION_TZ).date()

    customer = session.get(Customer, customer_id)
    if customer is None:
        return CustomerPrefill()  # empty defaults; let the JS skip silently

    out = CustomerPrefill()

    # --- Contact ---
    out.phone = customer.phone
    out.invoice_ruc = customer.invoice_ruc or customer.cedula
    out.invoice_name = customer.invoice_name or customer.name

    # --- Delivery ---
    out.delivery_zone_id = customer.preferred_zone_id
    all_addresses = session.execute(
        select(CustomerAddress).where(CustomerAddress.customer_id == customer_id)
    ).scalars().all()
    out.available_addresses = [
        {
            "id": addr.id,
            "label": addr.label,
            "address_text": addr.address_text,
            "is_default": bool(addr.is_default),
            "delivery_zone_id": addr.zone_id,
            # Phase 13 (2026-10-01): include the structured columns so
            # the JS can prefill the structured disclosure if the
            # cashier picks a saved address.
            "calle_principal": addr.calle_principal,
            "calle_secundaria": addr.calle_secundaria,
            "numero": addr.numero,
            "edificio": addr.edificio,
            "piso": addr.piso,
            "unidad": addr.unidad,
            "barrio": addr.barrio,
            "ciudad": addr.ciudad,
            "departamento": addr.departamento,
            "codigo_postal": addr.codigo_postal,
            "recipient_name": addr.recipient_name,
            "delivery_instructions": addr.delivery_instructions,
            "address_kind": addr.address_kind,
        }
        for addr in all_addresses
    ]

    # --- Invoice profiles (Phase 13) ---
    from app.rms.models import CustomerInvoiceProfile as _InvoiceProfile
    all_profiles = session.execute(
        select(_InvoiceProfile)
        .where(_InvoiceProfile.customer_id == customer_id)
        .where(_InvoiceProfile.is_active.is_(True))
        .order_by(_InvoiceProfile.is_default.desc(), _InvoiceProfile.alias)
    ).scalars().all()
    out.invoice_profiles = [
        {
            "id": prof.id,
            "alias": prof.alias,
            "ruc_ci": prof.ruc_ci,
            "razon_social": prof.razon_social,
            "tipo_documento": prof.tipo_documento,
            "tipo_operacion": prof.tipo_operacion,
            "is_default": bool(prof.is_default),
        }
        for prof in all_profiles
    ]
    # If exactly one profile, prepopulate the legacy fields too so the
    # cashier sees RUC + Razón social pre-filled (matches legacy behavior).
    if all_profiles and not out.invoice_ruc:
        out.invoice_ruc = all_profiles[0].ruc_ci
    if all_profiles and not out.invoice_name:
        out.invoice_name = all_profiles[0].razon_social

    addr = _default_address(session, customer_id)
    if addr:
        out.address_text = addr.address_text
        out.address_label = addr.label
        # If the customer has 0 or 1 addresses total, "save" by default
        out.save_address = len(all_addresses) <= 1

    # --- When ---
    # Promised date: customer's average lead time (today → pedido.promised_date)
    # defaults to today if we have no history.
    pedidos = session.execute(
        select(Pedido)
        .where(Pedido.customer_id == customer_id, Pedido.status != "cancelled")
        .order_by(Pedido.promised_date.desc())
        .limit(20)
    ).scalars().all()
    if pedidos:
        lead_days = [(p.promised_date - p.created_at.date()).days for p in pedidos if p.created_at]
        avg_lead = round(sum(lead_days) / len(lead_days)) if lead_days else 0
        out.promised_date = (today + timedelta(days=max(0, avg_lead))).isoformat()
        out.promised_time = _most_common([p.promised_time for p in pedidos])
        out.delivery_window_start = _most_common([p.delivery_window_start for p in pedidos])
        out.delivery_window_end = _most_common([p.delivery_window_end for p in pedidos])
        out.payment_intent = _most_common([p.payment_intent for p in pedidos])
    else:
        out.promised_date = (today + timedelta(days=1)).isoformat()

    # Channel: customer preference OR most common history
    out.channel = customer.preferred_channel or _most_common([p.channel for p in pedidos])

    # --- Free-form ---
    recent = _recent_pedido_for(session, customer_id)
    if recent:
        out.notes = recent.notes
        out.last_pedido_id = recent.id
        # Short summary for the banner
        n_lines = len(recent.lines)
        out.last_pedido_summary = (
            f"{recent.promised_date.strftime('%d/%m')} · {n_lines} ítem"
            f"{'s' if n_lines != 1 else ''} · Gs. "
            f"{sum(int(ln.qty * ln.unit_price_gs) for ln in recent.lines):,}".replace(",", ".")
        )

    # Dietary banner
    if customer.dietary_restrictions:
        out.dietary_banner = f"⚠ Restricciones: {customer.dietary_restrictions}"

    # --- Clone lines (Pedir de nuevo) ---
    if from_pedido_id:
        source = session.get(Pedido, from_pedido_id)
        if source and source.customer_id == customer_id:
            out.clone_lines = _pedido_lines_as_dicts(source.id, session)
            out.last_pedido_id = source.id
    elif recent and recent.lines:
        # Default: copy most-recent pedido's lines (cheap "Pedir de nuevo")
        out.clone_lines = _pedido_lines_as_dicts(recent.id, session)

    # Phase 8 — Loyalty banner.
    # Show the customer's current points balance + a projection of what
    # they'll earn on this pedido if it's fulfilled today. Operators use
    # this to remind the customer at the counter ("sumás ~120 pts hoy").
    out.loyalty_points_balance = int(customer.loyalty_points or 0)
    # Projected: 1 point / 1.000 Gs. (matches the migration 074 earn rate).
    # Estimate the pedido total from the cloned lines, or 0 if none.
    projected_gs = sum(
        ln.get("qty", 0) * ln.get("unit_price_gs", 0)
        for ln in out.clone_lines
    )
    out.loyalty_points_projected = int(projected_gs // 1000)

    # Tier 6.4 (2026-10-01): tier display.
    # Compute the customer's tier from their lifetime spend (same source
    # as the /clientes list and cliente_detalle). Cheap: 1 stats query.
    from app.rms.customers import customer_stats
    from app.rms.loyalty.tiers import tier_for_spend

    stats = customer_stats(session, customer)
    out.tier = tier_for_spend(int(stats.lifetime_spend_gs or 0)).value

    # Tier 6.4 (2026-10-01): active suscripción prefill.
    # Query the customer's active suscripciones so the /pedidos/nuevo
    # template can offer an "Aplicar suscripción" quick-pick that fills
    # the notes field with the subscription's product_summary.
    from app.rms.models import Suscripcion

    subs = session.scalars(
        select(Suscripcion)
        .where(Suscripcion.customer_id == customer_id)
        .where(Suscripcion.status == "activa")
        .order_by(Suscripcion.id.desc())
    ).all()
    out.active_subscriptions = [
        {
            "id": s.id,
            "product_summary": s.product_summary,
            "cadence": s.cadence,
            "preferred_day_of_week": s.preferred_day_of_week,
            "preferred_time": s.preferred_time,
            "price_gs": int(s.price_gs or 0),
        }
        for s in subs
    ]

    return out


def customer_defaults_as_json(session: Session, customer_id: int) -> dict:
    """JSON-friendly wrapper for /pedidos/api/customer-defaults/<id>."""
    return compute_customer_defaults(session, customer_id).to_dict()
