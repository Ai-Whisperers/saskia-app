"""app/rms/cash.py — WP-1.3 arqueo de caja X/Z.

expected(session) = opening_gs + pagos en efectivo (sale_payment, WP-1.2
ledger uniforme) de ventas NO anuladas con sold_at dentro de la sesión.
close() escribe counted/expected/diff y cierra. Una sola sesión abierta.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rms.config import ASUNCION_TZ


class CashSessionError(ValueError):
    """Datos inválidos para la operación de caja."""


class CashSessionConflict(CashSessionError):
    """Ya hay una sesión de caja abierta."""


def get_open_session(db: Session) -> Any | None:
    from app.rms.models_legacy import CashSession

    return (
        db.execute(
            select(CashSession)
            .where(CashSession.status == "open")
            .order_by(CashSession.opened_at.desc())
        )
        .scalars()
        .first()
    )


def open_session(
    db: Session,
    opening_gs: int,
    opened_by: str,
    channel: str | None = None,
    note: str | None = None,
) -> Any:
    from app.rms.models_legacy import CashSession

    if get_open_session(db) is not None:
        raise CashSessionConflict("Ya hay una caja abierta. Cerrala antes de abrir otra.")
    if opening_gs < 0:
        raise CashSessionError("El monto inicial no puede ser negativo.")
    sess = CashSession(
        opened_at=datetime.now(ASUNCION_TZ),
        opened_by=opened_by or "operador",
        opening_gs=int(opening_gs),
        status="open",
        channel=(channel or None),
        note=(note or None),
    )
    db.add(sess)
    db.flush()
    return sess


def expected_gs(db: Session, sess: Any) -> int:
    """Apertura + pagos en efectivo del período (ventas no anuladas)."""
    from app.rms.models_legacy import Sale, SalePayment

    end = sess.closed_at or datetime.now(ASUNCION_TZ)
    q = (
        select(SalePayment.amount_gs)
        .join(Sale, Sale.id == SalePayment.sale_id)
        .where(
            SalePayment.method == "efectivo",
            Sale.voided_at.is_(None),
            Sale.sold_at >= sess.opened_at,
            Sale.sold_at <= end,
        )
    )
    cash = db.execute(q).scalars().all()
    return int(sess.opening_gs) + sum(int(a) for a in cash)


def close_session(db: Session, counted_gs: int, closed_by: str) -> Any:

    sess = get_open_session(db)
    if sess is None:
        raise CashSessionError("No hay caja abierta que cerrar.")
    if counted_gs < 0:
        raise CashSessionError("El conteo no puede ser negativo.")
    exp = expected_gs(db, sess)
    sess.counted_gs = int(counted_gs)
    sess.expected_gs = exp
    sess.diff_gs = int(counted_gs) - exp
    sess.closed_at = datetime.now(ASUNCION_TZ)
    sess.closed_by = closed_by or "operador"
    sess.status = "closed"
    db.flush()
    return sess
