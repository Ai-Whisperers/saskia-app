"""app/routers/refunds.py — HTTP router for refund endpoints (BACKLOG M1).

Mounts at /refunds. Two endpoints:
  POST /refunds/         — create a new refund (operator-only)
  GET  /refunds/{id}     — fetch one refund as JSON
  GET  /refunds/target/{type}/{id}  — list all refunds for a target

The actual sale-creation endpoint delegates to `create_refund` in app.rms.refunds,
which owns all the business logic (loyalty proportional reversal, restock,
EOD-closure enforcement, cap trigger, etc.). This file is intentionally thin.

Mirrors `POST /ventas/{sale_id}/anular` (void) but for partial / different-day
refunds. Void = "this didn't happen" (full reversal). Refund = "this happened,
giving some money back" (partial, with optional restock).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from loguru import logger
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import current_user_id, require_login_or_disabled
from app.rms.dependencies import get_session
from app.rms.refunds import (
    VALID_TARGET_TYPES,
    RefundError,
    create_refund,
    get_refund,
    list_refunds_for,
)

router = APIRouter(prefix="/refunds", dependencies=[Depends(require_login_or_disabled)])


# Map domain error codes → user-facing Spanish messages.
# Operators see the clean Spanish text; the audit log retains the code.
_ERROR_MESSAGES: dict[str, str] = {
    "voided": "La venta ya fue anulada — no se puede reembolsar.",
    "not_found": "Venta o pedido no encontrado.",
    "invalid_target_type": "Tipo de objetivo inválido.",
    "amount_invalid": "El monto debe ser mayor a 0.",
    "cap_exceeded": "El reembolso excede el saldo pendiente.",
    "eod_closed": "No se puede reembolsar: el día ya fue cerrado.",
    "payment_method_mismatch": "El método de reembolso debe coincidir con el método de cobro.",
}


@router.post("/")
async def refund_create(
    request: Request,
    target_type: str = Form(...),
    target_id: int = Form(...),
    amount_gs: int = Form(...),
    reason: str = Form(""),
    restock_qty: bool = Form(False),
    restocked_qty: float = Form(0.0),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Create a refund for a Sale or Pedido.

    Form fields (mirror /ventas/{id}/anular):
        target_type — 'sale' | 'pedido' | 'pedido_line'
        target_id   — integer FK to the target row
        amount_gs   — Gs. to refund (always > 0, ≤ remaining target amount)
        reason      — free text (optional, e.g. "cliente devolvió torta")
        restock_qty — checkbox, "on" if the operator wants the items back
        restocked_qty — how many units to return to stock (default 0)

    On success: 303 redirect to the target detail page with a flash message.
    """
    if target_type not in VALID_TARGET_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"target_type inválido. Permitidos: {sorted(VALID_TARGET_TYPES)}",
        )

    uid = current_user_id(request)
    user_id = str(uid) if uid is not None else "operator"
    reason_clean = (reason or "").strip() or None

    try:
        result = create_refund(
            session,
            target_type=target_type,
            target_id=target_id,
            amount_gs=amount_gs,
            restock_qty=restock_qty,
            restocked_qty=float(restocked_qty or 0.0),
            reason=reason_clean,
            recorded_by=user_id,
        )
        session.commit()
    except RefundError as e:
        msg = _ERROR_MESSAGES.get(e.code, "No se pudo procesar el reembolso.")
        # Map RefundError to flash message + redirect back to the sale detail.
        from urllib.parse import quote as _quote

        flash_key = f"refund_err_{e.code}"
        if target_type == "sale":
            back_url = f"/ventas/{target_id}?flash={_quote(flash_key)}"
        else:
            back_url = f"/pedidos/{target_id}?flash={_quote(flash_key)}"
        logger.warning(
            "refund failed: type={} id={} amount={} code={} msg={}",
            target_type,
            target_id,
            amount_gs,
            e.code,
            msg,
        )
        return RedirectResponse(url=back_url, status_code=303)
    except IntegrityError as e:
        # DB trigger caught a violation that slipped through (shouldn't happen
        # if create_refund is correct, but defensive).
        session.rollback()
        logger.warning("refund DB integrity error: {}", e)
        raise HTTPException(
            status_code=409,
            detail="Conflicto con regla de base de datos (cap de reembolso).",
        ) from e

    # Audit row (mirror void-anonymous-void's pattern)
    try:
        from app.rms.observability import record_audit

        record_audit(
            request,
            session=session,
            action="write.refund.create",
            target_type=target_type,
            target_id=target_id,
            detail={
                "refund_id": result.refund.id,
                "amount_gs": amount_gs,
                "restock_qty": restock_qty,
                "restocked_qty": float(restocked_qty or 0.0),
                "reason": reason_clean,
                "loyalty_reversed": result.loyalty_reversed,
            },
        )
        session.commit()
    except Exception as exc:  # best-effort audit; never block the refund  # noqa: BLE001
        logger.warning("audit for refund {} failed: {}", result.refund.id, exc)

    # Redirect back to the source page
    if target_type == "sale":
        back_url = f"/ventas/{target_id}?flash=refund_ok"
    else:
        back_url = f"/pedidos/{target_id}?flash=refund_ok"
    return RedirectResponse(url=back_url, status_code=303)


@router.get("/{refund_id}")
async def refund_get(refund_id: int, session: Session = Depends(get_session)) -> dict:
    """Fetch one refund as JSON. Used by JS in the sale-detail page."""
    refund = get_refund(session, refund_id)
    if refund is None:
        raise HTTPException(status_code=404, detail="Reembolso no encontrado.")
    return {
        "id": refund.id,
        "target_type": refund.target_type,
        "target_id": refund.target_id,
        "target_amount_gs": refund.target_amount_gs,
        "amount_gs": refund.amount_gs,
        "payment_method": refund.payment_method,
        "restock_qty": refund.restock_qty,
        "restocked_qty": refund.restocked_qty,
        "reason": refund.reason,
        "recorded_at": refund.recorded_at.isoformat() if refund.recorded_at else None,
        "recorded_by": refund.recorded_by,
        "loyalty_reversed": refund.loyalty_reversed,
    }


@router.get("/target/{target_type}/{target_id}")
async def refund_list(
    target_type: str,
    target_id: int,
    session: Session = Depends(get_session),
) -> dict:
    """List all refunds for a target, oldest first."""
    if target_type not in VALID_TARGET_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"target_type inválido. Permitidos: {sorted(VALID_TARGET_TYPES)}",
        )
    refunds = list_refunds_for(session, target_type, target_id)
    total = sum(r.amount_gs for r in refunds)
    return {
        "target_type": target_type,
        "target_id": target_id,
        "count": len(refunds),
        "total_refunded_gs": total,
        "refunds": [
            {
                "id": r.id,
                "amount_gs": r.amount_gs,
                "payment_method": r.payment_method,
                "restock_qty": r.restock_qty,
                "restocked_qty": r.restocked_qty,
                "reason": r.reason,
                "recorded_at": r.recorded_at.isoformat() if r.recorded_at else None,
                "recorded_by": r.recorded_by,
                "loyalty_reversed": r.loyalty_reversed,
            }
            for r in refunds
        ],
    }


__all__ = ["router"]
