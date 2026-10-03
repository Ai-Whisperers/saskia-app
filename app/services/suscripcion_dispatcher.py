"""app/services/suscripcion_dispatcher.py — Phase 13: weekly pedido generator.

For each active Suscripcion whose cadence falls due this week, generate
a Pedido in 'pending' status. Idempotent — running twice for the same
week is a no-op (we mark generated pedigios with a `suscripcion_id` FK
once that's wired in, or by storing the (suscripcion_id, year, iso_week)
tuple in an app_meta key as a quick dedupe).

Design choices:
  - Use Asunción local time for "today" (matches the rest of the app)
  - Weekly-only for now (the dominant cadence). Quincenal + mensual
    will be added when the operator asks.
  - Returns a structured result so /suscripciones can show what got
    generated this week without re-querying
  - Skips subscriptions whose end_date is past

Trade-offs vs. cron-style auto-creation:
  - The operador clicks "Generar pedidos de la semana" on Monday morning,
    reviews the list, then commits. NOT a cron (no implicit orders).
  - The Suscripcion docstring explicitly says "no cron, no implicit
    stock decrement" — this dispatcher is the operational tool that
    bridges subscriptions → pedidos, but stays operator-driven.

Idempotency:
  - The dispatcher uses an `app_meta` key per (suscripcion_id, ISO year-week)
    to record "we generated X on Y". Re-running in the same week skips
    already-generated subscriptions.
  - If the operator deletes the generated Pedido, the dedupe row is
    removed too (see ``_delete_dedupe_for_pedido``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from app.rms.config import ASUNCION_TZ
from app.rms.models import AppMeta, Pedido, Suscripcion

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@dataclass
class GeneratedPedido:
    """One pedido generated from one suscripcion."""

    suscripcion_id: int
    customer_id: int
    customer_name: str
    pedido_id: int
    promised_date: date
    notes: str


@dataclass
class DispatchResult:
    """Outcome of one dispatcher run."""

    generated: list[GeneratedPedido] = field(default_factory=list)
    skipped_already_done: list[int] = field(default_factory=list)  # suscripcion_ids
    skipped_paused: list[int] = field(default_factory=list)
    skipped_past_end_date: list[int] = field(default_factory=list)
    skipped_no_dow_match: list[int] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.generated)


def _iso_year_week(d: date) -> str:
    """ISO year-week like '2026-W40'."""
    iso = d.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def _dedupe_key(suscripcion_id: int, week_label: str) -> str:
    return f"suscripcion_dispatch:{suscripcion_id}:{week_label}"


def _dow_for_cadence(cadence: str, today: date) -> int | None:
    """Return the ISO day-of-week (1=Mon..7=Sun) that this cadence
    fires on for the week containing `today`. Returns None for cadences
    we don't handle yet.
    """
    if cadence == "semanal":
        # Suscripcion.preferred_day_of_week; default to today
        return None  # caller decides
    return None  # quincenal/mensual deferred


def generate_weekly_pedidos(
    session: Session,
    *,
    week_start: date | None = None,
    actor: str = "system",
) -> DispatchResult:
    """Generate pending Pedidos for all active Suscripciones due this week.

    Args:
        session: SQLAlchemy session.
        week_start: the Monday-ish anchor date. If None, we use this
            week's Monday in Asunción local time.
        actor: identifier for audit + PedidoEvent (e.g. 'operator:'
            username or 'system').

    Returns:
        DispatchResult with lists of generated, skipped (already done),
        skipped (paused), skipped (past end_date), and skipped
        (no day-of-week match) subscriptions.
    """
    if week_start is None:
        today = datetime.now(ASUNCION_TZ).date()
        week_start = today - timedelta(days=today.isoweekday() - 1)

    week_label = _iso_year_week(week_start)
    today = datetime.now(ASUNCION_TZ).date()

    result = DispatchResult()

    rows = session.execute(
        select(Suscripcion)
        .where(Suscripcion.status == "activa")
        .order_by(Suscripcion.id)
    ).scalars().all()

    for s in rows:
        # 1. Skip past-end-date
        if s.end_date and s.end_date < today:
            result.skipped_past_end_date.append(s.id)
            continue

        # 2. Skip if already generated this week
        key = _dedupe_key(s.id, week_label)
        already = session.scalar(
            select(AppMeta).where(AppMeta.key == key)
        )
        if already:
            result.skipped_already_done.append(s.id)
            continue

        # 3. Skip if not weekly cadence for now
        if s.cadence != "semanal":
            # Quincenal + mensual: not handled yet (Phase 13 scope is weekly)
            result.skipped_no_dow_match.append(s.id)
            continue

        # 4. Determine the promised date for this week's occurrence
        # Weekly: the preferred_day_of_week in the current week.
        if s.preferred_day_of_week is None:
            # Default: today (operator-friendly: see "what we'd send
            # right now")
            promised = today
        else:
            days_into_week = s.preferred_day_of_week - 1  # 1=Mon → 0
            promised = week_start + timedelta(days=days_into_week)
            # If the preferred day already passed this week, push to next
            if promised < today:
                promised = promised + timedelta(days=7)

        # 5. Build the Pedido
        cust = s.customer
        pedido = Pedido(
            customer_id=cust.id,
            customer_name=cust.name or "",
            customer_phone=cust.phone or "",
            promised_date=promised,
            promised_time=s.preferred_time or "",
            status="pending",
            channel="whatsapp",
            payment_intent="efectivo",
            notes=f"[Auto-generado desde suscripción #{s.id} · {s.product_summary}]",
            public_token=_new_public_token(),
        )
        session.add(pedido)
        session.flush()  # assign pedido.id

        # 6. Mark dedupe so re-running this week is a no-op
        session.add(AppMeta(
            key=key,
            value=f'{{"pedido_id": {pedido.id}, "generated_at": "{datetime.now(ASUNCION_TZ).isoformat()}"}}',
            updated_at=datetime.now(ASUNCION_TZ),
        ))

        # 7. Record a PedidoEvent so the timeline shows this came from
        # a subscription dispatch (Phase 11 integration).
        from app.services.pedido_events import PedidoEventService
        PedidoEventService.record(
            session, pedido.id, "created", actor=actor,
            payload={
                "n_lines": 0,
                "channel": "whatsapp",
                "promised_date": promised.isoformat(),
                "total_gs": 0,
                "source": "suscripcion_dispatch",
                "suscripcion_id": s.id,
                "product_summary": s.product_summary,
                "price_gs": s.price_gs,
            },
        )

        result.generated.append(GeneratedPedido(
            suscripcion_id=s.id,
            customer_id=cust.id,
            customer_name=cust.name or "",
            pedido_id=pedido.id,
            promised_date=promised,
            notes=pedido.notes,
        ))

    session.commit()
    return result


def _new_public_token() -> str:
    """Generate a URL-safe public token for the new pedido."""
    import secrets as _secrets
    return _secrets.token_urlsafe(16)


def undo_for_pedido(session: Any, pedido_id: int) -> bool:
    """If a Pedido was generated by the dispatcher, allow undo.

    Removes the dedupe row so re-running this week will recreate it.
    Returns True if the undo was performed (the pedido was marked as
    a dispatcher-generated one).
    """
    from sqlalchemy import delete
    pedido = session.get(Pedido, pedido_id)
    if pedido is None:
        return False
    # Look at the dedupe keys for this pedido: any one whose value
    # references this pedido_id. AppMeta's PK is the `key` column
    # (no `id`).
    rows = session.execute(
        select(AppMeta).where(AppMeta.key.like("suscripcion_dispatch:%"))
    ).scalars().all()
    removed = False
    for r in rows:
        if f'"pedido_id": {pedido_id}' in (r.value or ""):
            session.execute(delete(AppMeta).where(AppMeta.key == r.key))
            removed = True
    session.commit()
    return removed
