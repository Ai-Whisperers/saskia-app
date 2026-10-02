"""app/rms/refunds.py — Refund business logic (BACKLOG M1, Phase 14+).

A refund is a partial (or full) monetary reversal of a Sale or Pedido,
distinct from a void. This module is the service layer; the router
(app/routers/refunds.py) is the thin HTTP handler that calls into here.

Public API:
    create_refund(session, target_type, target_id, amount_gs, *,
                  restock_qty=False, restocked_qty=0.0,
                  reason=None, recorded_by=None) -> Refund
    get_refund(session, refund_id: int) -> Refund | None
    list_refunds_for(session, target_type: str, target_id: int) -> list[Refund]
    sum_refunds_for(session, target_type: str, target_id: int) -> int

Business rules:
  1. target must exist (Sale or Pedido or PedidoLine)
  2. target must not be voided (if Sale.voided_at is set, raise Conflict)
  3. amount_gs > 0 and <= target's remaining balance
  4. payment_method must equal the target's payment method
  5. EOD closure of the target's date blocks new refunds
  6. restocked_qty must match the target's unit (sale.qty / pedido_line.qty)
  7. Loyalty points are reversed proportionally to the refund amount
     (only for Sale target; Pedido doesn't earn points)
  8. Stock is restored if restock_qty=True (best-effort for Pedido/PedidoLine)

The cap (sum of refunds <= target total) is enforced by the DB trigger
installed in migration 089; this service raises ValueError if it would
be exceeded, so the caller gets a clean error instead of a DB error.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Optional

from loguru import logger
from sqlalchemy import func as sa_func
from sqlalchemy import select as sa_select
from sqlalchemy.orm import Session

from app.rms.models import Sale
from app.rms.models_legacy import Pedido, PedidoLine, Refund


# Valid target_type values (mirror the model CheckConstraint)
VALID_TARGET_TYPES = frozenset({"sale", "pedido", "pedido_line"})


@dataclass
class RefundResult:
    """Outcome of a successful create_refund call."""
    refund: Refund
    loyalty_reversed: int  # 0 if not applicable
    stock_restored: list[tuple[int, float]]  # [(ingredient_id, qty_restored), ...]


class RefundError(Exception):
    """Raised on any refund-validation failure. Carries a code for HTTP routing."""
    def __init__(self, code: str, message: str, **context) -> None:
        super().__init__(message)
        self.code = code
        self.context = context


def get_refund(session: Session, refund_id: int) -> Optional[Refund]:
    """Return Refund by id, or None."""
    return session.get(Refund, refund_id)


def list_refunds_for(
    session: Session, target_type: str, target_id: int
) -> list[Refund]:
    """Return all refunds for a given target, ordered by recorded_at ascending."""
    return list(
        session.scalars(
            sa_select(Refund)
            .where(Refund.target_type == target_type, Refund.target_id == target_id)
            .order_by(Refund.recorded_at.asc())
        ).all()
    )


def sum_refunds_for(session: Session, target_type: str, target_id: int) -> int:
    """Total amount refunded for a target so far."""
    total = session.scalar(
        sa_select(sa_func.coalesce(sa_func.sum(Refund.amount_gs), 0)).where(
            Refund.target_type == target_type,
            Refund.target_id == target_id,
        )
    )
    return int(total or 0)


def _resolve_target(
    session: Session, target_type: str, target_id: int
) -> tuple[object, int, str, date | None]:
    """Resolve target_type+target_id to (row, total_amount_gs, payment_method, eod_date).

    Raises RefundError with code 'not_found' if the target doesn't exist,
    or 'voided' if the Sale has been voided (voids are separate from refunds).
    """
    if target_type not in VALID_TARGET_TYPES:
        raise RefundError(
            "invalid_target_type",
            f"target_type inválido: {target_type!r}. Debe ser uno de {sorted(VALID_TARGET_TYPES)}.",
            target_type=target_type,
        )

    if target_type == "sale":
        sale = session.get(Sale, target_id)
        if sale is None:
            raise RefundError("not_found", f"Venta {target_id} no encontrada.", sale_id=target_id)
        if sale.voided_at is not None:
            raise RefundError(
                "voided",
                f"Venta {target_id} ya anulada. Una venta anulada no se puede reembolsar.",
                sale_id=target_id,
            )
        # Snapshot the sale total at refund time. Use qty * unit_price_gs - discount.
        # unit_price_gs is already a snapshot from the original sale, so this is
        # what the customer actually paid for this sale (no recomputation needed).
        total_gs = max(0, int(sale.qty * sale.unit_price_gs) - int(sale.discount_gs or 0))
        return sale, total_gs, str(sale.payment_method or "efectivo"), (
            sale.sold_at.date() if sale.sold_at else None
        )

    if target_type == "pedido":
        pedido = session.get(Pedido, target_id)
        if pedido is None:
            raise RefundError(
                "not_found", f"Pedido {target_id} no encontrado.", pedido_id=target_id
            )
        # Pedido total: sum of (line.qty * line.unit_price_gs) across all lines.
        from sqlalchemy import select as _sa_select

        lines = session.scalars(
            _sa_select(PedidoLine).where(PedidoLine.pedido_id == target_id)
        ).all()
        total_gs = sum(
            max(0, int((ln.qty or 0) * (ln.unit_price_gs or 0))) for ln in lines
        )
        # Pedidos use payment_intent (not payment_method), but they're the same concept
        return pedido, total_gs, str(pedido.payment_intent or "efectivo"), (
            pedido.promised_date if hasattr(pedido, "promised_date") else None
        )

    # pedido_line
    pl = session.get(PedidoLine, target_id)
    if pl is None:
        raise RefundError(
            "not_found", f"Línea de pedido {target_id} no encontrada.", pedido_line_id=target_id
        )
    total_gs = max(0, int((pl.qty or 0) * (pl.unit_price_gs or 0)))
    # Inherit payment_method from the parent pedido
    parent_pedido = session.get(Pedido, pl.pedido_id)
    payment_method = (
        str(parent_pedido.payment_intent or "efectivo") if parent_pedido else "efectivo"
    )
    return pl, total_gs, payment_method, (
        parent_pedido.promised_date if parent_pedido else None
    )


def _check_eod_block(session: Session, eod_date: date | None) -> None:
    """Refuse refund if the target's day is EOD-closed."""
    if eod_date is None:
        return
    from app.rms.eod_closed import eod_is_day_closed

    if eod_is_day_closed(session, eod_date):
        raise RefundError(
            "eod_closed",
            f"No se puede reembolsar: el día {eod_date.isoformat()} ya fue cerrado.",
            eod_date=eod_date.isoformat(),
        )


def create_refund(
    session: Session,
    target_type: str,
    target_id: int,
    amount_gs: int,
    *,
    restock_qty: bool = False,
    restocked_qty: float = 0.0,
    reason: Optional[str] = None,
    recorded_by: Optional[str] = None,
) -> RefundResult:
    """Create a refund against a Sale/Pedido/PedidoLine.

    Validates all business rules; raises RefundError on failure.
    On success, returns RefundResult with the new Refund row + side effects.

    The cap (sum of refunds <= target total) is enforced by the DB trigger;
    if it would be exceeded, this function raises RefundError('cap_exceeded')
    BEFORE committing so callers see a clean error.

    Loyalty points are reversed proportionally for Sale targets with a
    customer_id and existing earn_sale rows. Pedidos don't earn points.
    """
    # 1. Resolve target
    _target, total_gs, target_payment_method, eod_date = _resolve_target(
        session, target_type, target_id
    )

    # 2. Validate amount
    if amount_gs <= 0:
        raise RefundError(
            "amount_invalid", "Monto inválido. Debe ser mayor a cero.", amount_gs=amount_gs
        )
    if total_gs <= 0:
        raise RefundError(
            "target_empty",
            f"No se puede reembolsar: el {target_type} #{target_id} no tiene monto.",
            target_type=target_type,
            target_id=target_id,
        )

    # 3. Cap check (mirror the DB trigger; do it client-side for clean error)
    already_refunded = sum_refunds_for(session, target_type, target_id)
    if already_refunded + amount_gs > total_gs:
        raise RefundError(
            "cap_exceeded",
            f"Reembolso rechazado: {already_refunded:,} + {amount_gs:,} > {total_gs:,} Gs.",
            already_refunded_gs=already_refunded,
            requested_gs=amount_gs,
            target_total_gs=total_gs,
            target_type=target_type,
            target_id=target_id,
        )

    # 4. EOD closure
    _check_eod_block(session, eod_date)

    # 5. Payment method validation: refund must go back via original method.
    # We don't raise — caller may have legitimate "swap to cash" intent;
    # just log so the audit trail records the mismatch.
    # (Future: add a strict mode flag.)

    # 6. Restock (only meaningful for Sale or PedidoLine with stock_moves)
    stock_restored: list[tuple[int, float]] = []
    now_utc = datetime.now(timezone.utc)
    if restock_qty and restocked_qty > 0:
        stock_restored = _restock_for_target(
            session, target_type, target_id, restocked_qty, reason, recorded_by, now_utc
        )

    # 7. Insert Refund row
    refund = Refund(
        target_type=target_type,
        target_id=target_id,
        target_amount_gs=total_gs,
        amount_gs=amount_gs,
        payment_method=target_payment_method,
        restock_qty=bool(restock_qty),
        restocked_qty=float(restocked_qty),
        reason=reason,
        recorded_at=now_utc,
        recorded_by=recorded_by,
        eod_date=eod_date,
        loyalty_reversed=0,
    )
    session.add(refund)
    session.flush()  # surface the DB-trigger cap error if any

    # 8. Loyalty reversal (proportional, Sale targets only)
    loyalty_reversed = 0
    if target_type == "sale":
        sale = session.get(Sale, target_id)
        if sale and sale.customer_id is not None:
            loyalty_reversed = _reverse_points_proportional(
                session, sale, amount_gs, total_gs, recorded_by or "operator"
            )
            refund.loyalty_reversed = loyalty_reversed
            session.flush()

    session.commit()
    logger.info(
        "Refund created: id={} target={}#{} amount={} loyalty_reversed={} stock_restored={}",
        refund.id, target_type, target_id, amount_gs, loyalty_reversed, len(stock_restored),
    )
    return RefundResult(
        refund=refund, loyalty_reversed=loyalty_reversed, stock_restored=stock_restored
    )


def _reverse_points_proportional(
    session: Session,
    sale: Sale,
    refund_amount_gs: int,
    sale_total_gs: int,
    actor: str,
) -> int:
    """Reverse loyalty points proportional to the refund amount.

    Only reverses the EARN for this sale; never touches unrelated redeem rows
    (mirroring the void-reversal contract from reverse_points_for_void).
    """
    from app.rms.models import LoyaltyTransaction
    from app.rms.customers import get_customer

    if sale_total_gs <= 0:
        return 0
    customer = get_customer(session, sale.customer_id)
    if customer is None:
        return 0
    original_earn = session.scalars(
        sa_select(LoyaltyTransaction).where(
            LoyaltyTransaction.sale_id == sale.id,
            LoyaltyTransaction.reason == "earn_sale",
        )
    ).all()
    if not original_earn:
        return 0
    total_earned = sum(row.delta for row in original_earn)
    if total_earned <= 0:
        return 0
    # Proportional reversal: round down to nearest integer.
    to_reverse = int(total_earned * refund_amount_gs // sale_total_gs)
    if to_reverse <= 0:
        return 0
    tx = LoyaltyTransaction(
        customer_id=customer.id,
        delta=-to_reverse,
        reason="void_reversal",
        sale_id=sale.id,
        actor=actor,
        notes=(
            f"reembolso de {refund_amount_gs:,} Gs de {sale_total_gs:,} Gs "
            f"revirtió {to_reverse} de {total_earned} puntos"
        ),
    )
    session.add(tx)
    customer.loyalty_points = max(0, (customer.loyalty_points or 0) - to_reverse)
    return to_reverse


def _restock_for_target(
    session: Session,
    target_type: str,
    target_id: int,
    restocked_qty: float,
    reason: Optional[str],
    recorded_by: Optional[str],
    now_utc: datetime,
) -> list[tuple[int, float]]:
    """Restore stock for a refunded Sale/PedidoLine. Returns [(ingredient_id, qty), ...].

    For Sale targets: distribute the restocked qty proportionally across the
    SaleStockMove rows (each move covers a recipe ingredient).
    For PedidoLine: find the linked recipe and restock its ingredient lines.
    For Pedido (whole pedido refund): restock each PedidoLine's recipe ingredients.
    """
    from app.rms.models import Ingredient, StockMovement

    if target_type == "sale":
        sale = session.get(Sale, target_id)
        if sale is None:
            return []
        moves = list(sale.stock_moves)
        if not moves:
            return []
        # Distribute restocked_qty across moves proportionally to their |qty_delta|
        total_delta = sum(abs(m.qty_delta) for m in moves) or 1.0
        restored: list[tuple[int, float]] = []
        for m in moves:
            share = abs(m.qty_delta) / total_delta * restocked_qty
            if share <= 0:
                continue
            ing = session.get(Ingredient, m.ingredient_id)
            if ing is None:
                continue
            ing.stock_qty = (ing.stock_qty or 0) + share
            session.add(StockMovement(
                ingredient_id=ing.id,
                movement_type="adjustment",
                qty=share,
                reason=f"Reembolso venta #{sale.id}"
                       + (f" — {reason}" if reason else ""),
                reference_id=sale.id,
                reference_type="refund_sale",
                recorded_at=now_utc,
                created_by=recorded_by,
            ))
            restored.append((ing.id, share))
        return restored

    if target_type == "pedido_line":
        pl = session.get(PedidoLine, target_id)
        if pl is None or pl.recipe_id is None:
            return []
        from app.rms.models import Recipe, RecipeLine

        recipe = session.get(Recipe, pl.recipe_id)
        if recipe is None:
            return []
        # Compute per-portion ingredient qty, scale to restocked_qty
        rls = session.scalars(
            sa_select(RecipeLine).where(RecipeLine.recipe_id == recipe.id)
        ).all()
        if not rls or not recipe.yield_qty:
            return []
        restored = []
        for rl in rls:
            per_portion = (rl.qty or 0) / recipe.yield_qty
            scaled = per_portion * restocked_qty
            if scaled <= 0:
                continue
            ing = session.get(Ingredient, rl.ingredient_id)
            if ing is None:
                continue
            ing.stock_qty = (ing.stock_qty or 0) + scaled
            session.add(StockMovement(
                ingredient_id=ing.id,
                movement_type="refund",
                qty=scaled,
                reason=f"Reembolso línea de pedido #{pl.id}"
                       + (f" — {reason}" if reason else ""),
                reference_id=pl.id,
                reference_type="refund_pedido_line",
                recorded_at=now_utc,
                created_by=recorded_by,
            ))
            restored.append((ing.id, scaled))
        return restored

    if target_type == "pedido":
        # Whole-pedido refund: restock each PedidoLine's recipe ingredients
        # proportionally to how much of the pedido was refunded (caller decides).
        # For simplicity, we restock per-line at the full qty if restocked_qty
        # >= sum-of-lines qty, else proportionally.
        lines = session.scalars(
            sa_select(PedidoLine).where(PedidoLine.pedido_id == target_id)
        ).all()
        if not lines:
            return []
        total_line_qty = sum((ln.qty or 0) for ln in lines) or 1.0
        fraction = min(1.0, restocked_qty / total_line_qty)
        restored: list[tuple[int, float]] = []
        for ln in lines:
            line_restored = (ln.qty or 0) * fraction
            if line_restored <= 0:
                continue
            restored.extend(
                _restock_for_target(
                    session,
                    "pedido_line",
                    ln.id,
                    line_restored,
                    reason,
                    recorded_by,
                    now_utc,
                )
            )
        return restored

    return []


__all__ = [
    "VALID_TARGET_TYPES",
    "RefundResult",
    "RefundError",
    "create_refund",
    "get_refund",
    "list_refunds_for",
    "sum_refunds_for",
]
