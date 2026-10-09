"""app/rms/fiado.py — Fase 2: fiado / cuentas por cobrar.

Ledger firmado en credit_transaction: positivo = cargo (venta a fiado
o ajuste), negativo = pago del cliente. saldo() = suma firmada.
registrar_pago() es idempotente por idem_key (UNIQUE).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.rms.config import ASUNCION_TZ


class FiadoError(ValueError):
    """Datos inválidos para la operación de fiado."""


class FiadoConflict(FiadoError):
    """Cuenta inexistente, inactiva, o idempotencia violation."""


def get_or_create_account(db: Session, customer_id: int) -> Any:
    from app.rms.models_legacy import CreditAccount

    acc = (
        db.execute(select(CreditAccount).where(CreditAccount.customer_id == customer_id))
        .scalars()
        .first()
    )
    if acc is None:
        acc = CreditAccount(customer_id=customer_id, active=True)
        db.add(acc)
        db.flush()
    return acc


def get_account(db: Session, customer_id: int) -> Any | None:
    from app.rms.models_legacy import CreditAccount

    return (
        db.execute(select(CreditAccount).where(CreditAccount.customer_id == customer_id))
        .scalars()
        .first()
    )


def saldo(db: Session, customer_id: int) -> int:
    """Suma firmada del ledger. Positivo = el cliente debe."""
    from app.rms.models_legacy import CreditTransaction

    acc = get_account(db, customer_id)
    if acc is None:
        return 0
    total = db.execute(
        select(func.coalesce(func.sum(CreditTransaction.amount_gs), 0)).where(
            CreditTransaction.account_id == acc.id
        )
    ).scalar()
    return int(total or 0)


def registrar_cargo(
    db: Session,
    customer_id: int,
    amount_gs: int,
    sale_id: int | None = None,
    note: str | None = None,
    created_by: str | None = None,
) -> Any:
    """Cargo por venta a fiado (o ajuste manual positivo). Valida límite."""
    from app.rms.models_legacy import CreditTransaction

    if amount_gs <= 0:
        raise FiadoError("El cargo debe ser positivo.")
    acc = get_or_create_account(db, customer_id)
    if not acc.active:
        raise FiadoConflict("La cuenta de fiado del cliente está suspendida.")
    if acc.limit_gs is not None:
        nuevo = saldo(db, customer_id) + int(amount_gs)
        if nuevo > int(acc.limit_gs):
            raise FiadoConflict(
                f"Límite de fiado excedido: Gs. {nuevo:,} > límite Gs. {acc.limit_gs:,}".replace(
                    ",", "."
                )
            )
    tx = CreditTransaction(
        account_id=acc.id,
        ts=datetime.now(ASUNCION_TZ),
        kind="cargo",
        amount_gs=int(amount_gs),
        sale_id=sale_id,
        note=note,
        created_by=created_by,
    )
    db.add(tx)
    db.flush()
    return tx


def registrar_pago(
    db: Session,
    customer_id: int,
    amount_gs: int,
    idem_key: str | None = None,
    note: str | None = None,
    created_by: str | None = None,
) -> Any | None:
    """Pago del cliente (ledger negativo). Idempotente por idem_key."""
    from app.rms.models_legacy import CreditTransaction

    if amount_gs <= 0:
        raise FiadoError("El pago debe ser positivo.")
    if idem_key:
        existing = (
            db.execute(select(CreditTransaction).where(CreditTransaction.idem_key == idem_key))
            .scalars()
            .first()
        )
        if existing is not None:
            return None  # duplicate POST → no-op
    acc = get_or_create_account(db, customer_id)
    tx = CreditTransaction(
        account_id=acc.id,
        ts=datetime.now(ASUNCION_TZ),
        kind="pago",
        amount_gs=-int(amount_gs),
        idem_key=idem_key,
        note=note,
        created_by=created_by,
    )
    db.add(tx)
    db.flush()
    return tx


def void_reversal(db: Session, sale_id: int) -> int:
    """Anular el cargo de una venta anulada: ledger opuesto (negativo)."""
    from app.rms.models_legacy import CreditTransaction

    cargos = (
        db.execute(
            select(CreditTransaction).where(
                CreditTransaction.sale_id == sale_id,
                CreditTransaction.kind == "cargo",
            )
        )
        .scalars()
        .all()
    )
    total = 0
    for c in cargos:
        db.add(
            CreditTransaction(
                account_id=c.account_id,
                ts=datetime.now(ASUNCION_TZ),
                kind="void_reversal",
                amount_gs=-int(c.amount_gs),
                sale_id=sale_id,
                note=f"Reversa por anulación de venta #{sale_id}",
                created_by="system",
            )
        )
        total += int(c.amount_gs)
    if total:
        db.flush()
    return total


def aging_report(db: Session) -> dict[str, int]:
    """Buckets 0-30 / 31-60 / 61+ días sobre saldos positivos por cliente."""
    from app.rms.models_legacy import CreditAccount

    accounts = db.execute(select(CreditAccount)).scalars().all()
    buckets = {"b0_30": 0, "b31_60": 0, "b61_mas": 0}
    now = datetime.now(ASUNCION_TZ)

    for acc in accounts:
        txs = _fetch_account_transactions(db, acc.id)
        queue = _compute_fifo_queue(txs)
        _accumulate_buckets(buckets, queue, now)

    return buckets


def _fetch_account_transactions(db, account_id: int) -> list:
    """Fetch all transactions for an account, ordered by timestamp.

    Extracted from aging_report to reduce complexity.
    """
    from app.rms.models_legacy import CreditTransaction

    return list(
        db.execute(
            select(CreditTransaction)
            .where(CreditTransaction.account_id == account_id)
            .order_by(CreditTransaction.ts)
        )
        .scalars()
        .all()
    )


def _compute_fifo_queue(txs: list) -> list[tuple[datetime, int]]:
    """Compute the FIFO queue of unpaid amounts with their original timestamps.

    FIFO: los pagos cubren los cargos más viejos; lo que queda debe
    es lo que envejece desde su ts original.
    Extracted from aging_report to reduce complexity.
    """
    queue: list[tuple[datetime, int]] = []
    for tx in txs:
        amt = int(tx.amount_gs)
        if amt > 0:
            queue.append([tx.ts, amt])
        else:
            _apply_payment(queue, -amt)
    return queue


def _apply_payment(queue: list, payment: int) -> None:
    """Apply a payment to the oldest charges in the queue (FIFO).

    Extracted from _compute_fifo_queue to reduce complexity.
    """
    rest = payment
    while queue and rest > 0:
        oldest = queue[0]
        take = min(oldest[1], rest)
        oldest[1] -= take
        rest -= take
        if oldest[1] == 0:
            queue.pop(0)


def _accumulate_buckets(buckets: dict, queue: list[tuple[datetime, int]], now: datetime) -> None:
    """Accumulate queue amounts into aging buckets based on days.

    Extracted from aging_report to reduce complexity.
    """
    for ts, amt in queue:
        days = (now - _ensure_aware(ts)).days
        if days <= 30:
            buckets["b0_30"] += amt
        elif days <= 60:
            buckets["b31_60"] += amt
        else:
            buckets["b61_mas"] += amt


def _ensure_aware(dt: datetime) -> datetime:
    """Ensure a datetime is timezone-aware (Asuncion TZ if naive).

    Extracted from _accumulate_buckets to reduce complexity.
    """
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=ASUNCION_TZ)


def cartera(db: Session) -> list[dict[str, Any]]:
    """Filas para fiado.html: cliente, saldo, límite, último movimiento."""
    from app.rms.models_legacy import CreditAccount, Customer

    rows: list[dict[str, Any]] = []
    accounts = db.execute(select(CreditAccount)).scalars().all()
    for acc in accounts:
        cust = db.get(Customer, acc.customer_id)
        rows.append(
            {
                "customer_id": acc.customer_id,
                "nombre": getattr(cust, "name", None) or f"Cliente #{acc.customer_id}",
                "saldo": saldo(db, acc.customer_id),
                "limit_gs": acc.limit_gs,
                "active": acc.active,
            }
        )
    rows.sort(key=lambda r: -r["saldo"])
    return rows
