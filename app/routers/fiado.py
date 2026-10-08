"""app/routers/fiado.py — Fase 2: fiado / cuentas por cobrar.

GET  /fiado                        → cartera (saldos, límites, aging)
GET  /fiado/{customer_id}          → historial del cliente + saldo
POST /fiado/{customer_id}/cargar   → cargo manual (ajuste)
POST /fiado/{customer_id}/cobrar   → pago del cliente (idempotente)
POST /fiado/{customer_id}/estado   → activar / suspender cuenta
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import current_operator
from app.auth import require_login_or_disabled as require_login
from app.rms.dependencies import get_session
from app.rms.fiado import (
    FiadoConflict,
    FiadoError,
    aging_report,
    cartera,
    get_or_create_account,
    registrar_cargo,
    registrar_pago,
    saldo,
)
from app.rms.models_legacy import CreditTransaction, Customer
from app.rms.observability import record_audit
from app.rms.rate_limit import is_write_rate_limited
from app.services.template_render import render

router = APIRouter(prefix="/fiado", dependencies=[Depends(require_login)])


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
def fiado_home(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    return render(
        request,
        "fiado.html",
        {
            "rows": cartera(session),
            "aging": aging_report(session),
        },
    )


@router.get("/resumen", response_class=HTMLResponse)
def fiado_resumen(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    return render(
        request,
        "fiado.html",
        {"rows": cartera(session), "aging": aging_report(session), "solo_resumen": True},
    )


@router.get("/{customer_id}", response_class=HTMLResponse)
def fiado_cliente(
    customer_id: int, request: Request, session: Session = Depends(get_session)
) -> HTMLResponse:
    cust = session.get(Customer, customer_id)
    if cust is None:
        return render(request, "fiado.html", {"error": "Cliente no encontrado"}, status_code=404)
    acc = get_or_create_account(session, customer_id)
    txs = (
        session.execute(
            select(CreditTransaction)
            .where(CreditTransaction.account_id == acc.id)
            .order_by(CreditTransaction.id.desc())
            .limit(50)
        )
        .scalars()
        .all()
    )
    return render(
        request,
        "fiado_cliente.html",
        {
            "cust": cust,
            "saldo": saldo(session, customer_id),
            "limit_gs": acc.limit_gs,
            "active": acc.active,
            "txs": txs,
        },
    )


@router.post("/{customer_id}/cargar")
def fiado_cargar(
    customer_id: int,
    request: Request,
    amount_gs: str = Form("0"),
    note: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    from app.rms.money import to_int_gs

    if is_write_rate_limited(session, request):
        return RedirectResponse(f"/fiado/{customer_id}?flash=rate_limited", status_code=303)
    try:
        tx = registrar_cargo(
            session,
            customer_id,
            to_int_gs(amount_gs),
            note=note or None,
            created_by=str(current_operator(request, fallback="operador")),
        )
        session.commit()
    except (FiadoError, FiadoConflict) as e:
        return RedirectResponse(f"/fiado/{customer_id}?flash=fiado_error&msg={e}", status_code=303)
    record_audit(
        request,
        session=session,
        action="fiado_cargo",
        target_type="customer",
        target_id=customer_id,
        detail={"amount_gs": tx.amount_gs, "note": note},
    )
    session.commit()
    return RedirectResponse(f"/fiado/{customer_id}?flash=fiado_cargo", status_code=303)


@router.post("/{customer_id}/cobrar")
def fiado_cobrar(
    customer_id: int,
    request: Request,
    amount_gs: str = Form("0"),
    idempotency_key: str = Form(""),
    note: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    from app.rms.money import to_int_gs

    if is_write_rate_limited(session, request):
        return RedirectResponse(f"/fiado/{customer_id}?flash=rate_limited", status_code=303)
    try:
        result = registrar_pago(
            session,
            customer_id,
            to_int_gs(amount_gs),
            idem_key=idempotency_key or None,
            note=note or None,
            created_by=str(current_operator(request, fallback="operador")),
        )
        session.commit()
    except (FiadoError, FiadoConflict) as e:
        return RedirectResponse(f"/fiado/{customer_id}?flash=fiado_error&msg={e}", status_code=303)
    if result is None:
        return RedirectResponse(f"/fiado/{customer_id}?flash=fiado_duplicado", status_code=303)
    nuevo_saldo = saldo(session, customer_id)
    record_audit(
        request,
        session=session,
        action="fiado_pago",
        target_type="customer",
        target_id=customer_id,
        detail={"amount_gs": result.amount_gs, "saldo_nuevo": nuevo_saldo},
    )
    session.commit()
    return RedirectResponse(
        f"/fiado/{customer_id}?flash=fiado_pago&saldo={nuevo_saldo}", status_code=303
    )


@router.post("/{customer_id}/estado")
def fiado_estado(
    customer_id: int,
    request: Request,
    active: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    acc = get_or_create_account(session, customer_id)
    acc.active = str(active).lower() in ("1", "true", "on", "si", "sí")
    session.commit()
    record_audit(
        request,
        session=session,
        action="fiado_estado",
        target_type="customer",
        target_id=customer_id,
        detail={"active": acc.active},
    )
    session.commit()
    return RedirectResponse(f"/fiado/{customer_id}?flash=fiado_estado", status_code=303)
