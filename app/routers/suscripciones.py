"""app/routers/suscripciones.py — P1-B5: suscripciones (recurring customer orders).

Suscripciones are standing customer requests (e.g., "1 kg de chipa cada
sábado a las 9"). They are CRUD-only — no cron, no automatic pedido
generation, no implicit stock decrement. The operator reads the list
when planning and pre-loads the corresponding pedidos manually.

Endpoints:
    GET  /suscripciones                 — list with status/cadence filters
    GET  /suscripciones/nuevo           — new form
    POST /suscripciones/nuevo           — create
    GET  /suscripciones/{id}/editar     — edit form
    POST /suscripciones/{id}/editar     — update
    POST /suscripciones/{id}/estado     — soft state transition
    POST /suscripciones/{id}/eliminar   — delete (only if status=cancelada)
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth import require_login_or_disabled as require_login
from app.rms.dependencies import get_session
from app.rms.models import Customer, Suscripcion
from app.rms.observability import record_audit
from app.services.template_render import render

router = APIRouter(prefix="/suscripciones", dependencies=[Depends(require_login)])

# Cadence options exposed to the form/template.
CADENCES: tuple[tuple[str, str], ...] = (
    ("semanal", "Semanal"),
    ("quincenal", "Quincenal"),
    ("mensual", "Mensual"),
)

# Status options (the state machine — operators can only move
# activa↔pausada; cancelada is terminal).
STATUSES: tuple[tuple[str, str], ...] = (
    ("activa", "Activa"),
    ("pausada", "Pausada"),
    ("cancelada", "Cancelada"),
)

# Day-of-week labels (ISO weekday 1=Monday).
DOW_LABELS: dict[int, str] = {
    1: "Lunes",
    2: "Martes",
    3: "Miércoles",
    4: "Jueves",
    5: "Viernes",
    6: "Sábado",
    7: "Domingo",
}


def _cadence_choices() -> list[tuple[str, str]]:
    return list(CADENCES)


def _status_choices() -> list[tuple[str, str]]:
    return list(STATUSES)


def _validate_cadence(value: str) -> str:
    """Return the cleaned cadence or raise HTTPException(400)."""
    allowed = {c for c, _ in CADENCES}
    if value not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Cadence inválida. Permitidas: {', '.join(sorted(allowed))}.",
        )
    return value


def _validate_status(value: str) -> str:
    """Return the cleaned status or raise HTTPException(400)."""
    allowed = {s for s, _ in STATUSES}
    if value not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Estado inválido. Permitidos: {', '.join(sorted(allowed))}.",
        )
    return value


def _validate_dow(value: int | None) -> int | None:
    if value is None:
        return None
    if value < 1 or value > 7:
        raise HTTPException(
            status_code=400,
            detail="Día de la semana debe estar entre 1 (Lunes) y 7 (Domingo).",
        )
    return value


# --- Routes -----------------------------------------------------------------


@router.get("", response_class=HTMLResponse)
def suscripciones_list(
    request: Request,
    status_filter: str = "todas",
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """List all suscripciones with optional status filter."""
    stmt = select(Suscripcion).options(selectinload(Suscripcion.customer))
    if status_filter in {s for s, _ in STATUSES}:
        stmt = stmt.where(Suscripcion.status == status_filter)

    # Order: activas first, then by customer name (via relationship
    # ordering handled in Python since the relationship has no
    # order_by), then by start_date desc.
    rows = session.scalars(stmt).all()

    # Sort: activas first (alphabetical customer name within group),
    # then pausadas, then canceladas. Most-recently-updated first.
    order = {"activa": 0, "pausada": 1, "cancelada": 2}

    def _sort_key(s: Suscripcion) -> tuple[int, str, float]:
        cust_name = (s.customer.name if s.customer else "").lower()
        return (order.get(s.status, 9), cust_name, -(s.updated_at.timestamp() if s.updated_at else 0))

    rows.sort(key=_sort_key)

    counts = {
        "activa": sum(1 for r in rows if r.status == "activa"),
        "pausada": sum(1 for r in rows if r.status == "pausada"),
        "cancelada": sum(1 for r in rows if r.status == "cancelada"),
    }
    counts["todas"] = len(rows)

    return render(
        request,
        "suscripciones.html",
        {
            "suscripciones": rows,
            "total": len(rows),
            "status_filter": status_filter,
            "counts": counts,
            "dow_labels": DOW_LABELS,
            "page_start": 1 if rows else 0,
            "page_end": len(rows),
        },
    )


@router.get("/nuevo", response_class=HTMLResponse)
def suscripcion_new(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    """New suscripción form. Customer picker comes from app/rms/customers."""
    customers = session.scalars(
        select(Customer).order_by(Customer.name)
    ).all()
    return render(
        request,
        "suscripcion_form.html",
        {
            "mode": "new",
            "suscripcion": None,
            "customers": customers,
            "cadences": _cadence_choices(),
            "statuses": _status_choices(),
            "dow_labels": DOW_LABELS,
        },
    )


@router.post("/nuevo")
def suscripcion_create(
    request: Request,
    customer_id: int = Form(...),
    product_summary: str = Form(""),
    cadence: str = Form("semanal"),
    preferred_day_of_week: str = Form(""),
    preferred_time: str = Form(""),
    start_date: str = Form(""),
    end_date: str = Form(""),
    price_gs: str = Form("0"),
    status: str = Form("activa"),
    notes: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Create a new suscripción."""
    from app.rms.validation import (
        optional_text,
        parse_date_iso,
        parse_money_gs,
        require_text,
    )

    # customer_id must point at a real customer.
    customer = session.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=400, detail="Cliente no encontrado.")

    summary_clean = require_text(product_summary, field="descripción", max_len=500)
    cadence_clean = _validate_cadence(cadence)
    status_clean = _validate_status(status)

    dow_int: int | None = None
    if preferred_day_of_week.strip():
        try:
            dow_int = _validate_dow(int(preferred_day_of_week))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    time_clean = optional_text(preferred_time, max_len=8)
    start_clean = parse_date_iso(start_date) if start_date else None
    end_clean = parse_date_iso(end_date) if end_date else None
    if not start_clean:
        raise HTTPException(status_code=400, detail="Fecha de inicio es requerida.")
    if end_clean and end_clean < start_clean:
        raise HTTPException(
            status_code=400,
            detail="La fecha de fin no puede ser anterior a la fecha de inicio.",
        )

    price_int = parse_money_gs(price_gs, allow_zero=True)
    notes_clean = optional_text(notes, max_len=2000)

    sub = Suscripcion(
        customer_id=customer.id,
        product_summary=summary_clean,
        cadence=cadence_clean,
        preferred_day_of_week=dow_int,
        preferred_time=time_clean,
        start_date=date.fromisoformat(start_clean),
        end_date=date.fromisoformat(end_clean) if end_clean else None,
        price_gs=price_int,
        status=status_clean,
        notes=notes_clean,
    )
    session.add(sub)
    session.commit()
    record_audit(
        request,
        session=session,
        action="write.suscripcion.create",
        target_type="suscripcion",
        target_id=sub.id,
        detail={
            "customer_id": customer.id,
            "customer_name": customer.name,
            "cadence": sub.cadence,
            "status": sub.status,
        },
    )
    session.commit()
    return RedirectResponse(url="/suscripciones", status_code=303)


@router.get("/{s_id}/editar", response_class=HTMLResponse)
def suscripcion_edit(
    s_id: int, request: Request, session: Session = Depends(get_session)
) -> HTMLResponse:
    """Edit suscripción form."""
    sub = session.get(Suscripcion, s_id)
    if sub is None:
        raise HTTPException(status_code=404, detail="Suscripción no encontrada")
    customers = session.scalars(
        select(Customer).order_by(Customer.name)
    ).all()
    return render(
        request,
        "suscripcion_form.html",
        {
            "mode": "edit",
            "suscripcion": sub,
            "customers": customers,
            "cadences": _cadence_choices(),
            "statuses": _status_choices(),
            "dow_labels": DOW_LABELS,
        },
    )


@router.post("/{s_id}/editar")
def suscripcion_update(
    s_id: int,
    request: Request,
    customer_id: int = Form(...),
    product_summary: str = Form(""),
    cadence: str = Form("semanal"),
    preferred_day_of_week: str = Form(""),
    preferred_time: str = Form(""),
    start_date: str = Form(""),
    end_date: str = Form(""),
    price_gs: str = Form("0"),
    status: str = Form("activa"),
    notes: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Update an existing suscripción."""
    from app.rms.validation import (
        optional_text,
        parse_date_iso,
        parse_money_gs,
        require_text,
    )

    sub = session.get(Suscripcion, s_id)
    if sub is None:
        raise HTTPException(status_code=404, detail="Suscripción no encontrada")

    customer = session.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=400, detail="Cliente no encontrado.")

    sub.customer_id = customer.id
    sub.product_summary = require_text(product_summary, field="descripción", max_len=500)
    sub.cadence = _validate_cadence(cadence)
    sub.status = _validate_status(status)

    if preferred_day_of_week.strip():
        try:
            sub.preferred_day_of_week = _validate_dow(int(preferred_day_of_week))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
    else:
        sub.preferred_day_of_week = None

    sub.preferred_time = optional_text(preferred_time, max_len=8)

    start_clean = parse_date_iso(start_date) if start_date else None
    if not start_clean:
        raise HTTPException(status_code=400, detail="Fecha de inicio es requerida.")
    sub.start_date = date.fromisoformat(start_clean)
    end_clean = parse_date_iso(end_date) if end_date else None
    if end_clean and end_clean < start_clean:
        raise HTTPException(
            status_code=400,
            detail="La fecha de fin no puede ser anterior a la fecha de inicio.",
        )
    sub.end_date = date.fromisoformat(end_clean) if end_clean else None

    sub.price_gs = parse_money_gs(price_gs, allow_zero=True)
    sub.notes = optional_text(notes, max_len=2000)

    session.commit()
    record_audit(
        request,
        session=session,
        action="write.suscripcion.update",
        target_type="suscripcion",
        target_id=sub.id,
        detail={
            "customer_id": sub.customer_id,
            "cadence": sub.cadence,
            "status": sub.status,
        },
    )
    session.commit()
    return RedirectResponse(url="/suscripciones", status_code=303)


@router.post("/{s_id}/estado")
def suscripcion_set_status(
    s_id: int,
    request: Request,
    status: str = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Soft state transition: activa/pausada/cancelada."""
    sub = session.get(Suscripcion, s_id)
    if sub is None:
        raise HTTPException(status_code=404, detail="Suscripción no encontrada")

    new_status = _validate_status(status)
    if sub.status == new_status:
        return RedirectResponse(url="/suscripciones", status_code=303)

    prior = sub.status
    sub.status = new_status
    session.commit()
    record_audit(
        request,
        session=session,
        action="write.suscripcion.status",
        target_type="suscripcion",
        target_id=sub.id,
        detail={"from": prior, "to": new_status},
    )
    session.commit()
    return RedirectResponse(url="/suscripciones", status_code=303)


@router.post("/{s_id}/eliminar")
def suscripcion_delete(
    s_id: int, request: Request, session: Session = Depends(get_session)
) -> RedirectResponse:
    """Delete a suscripción. Only allowed when status=cancelada."""
    sub = session.get(Suscripcion, s_id)
    if sub is None:
        raise HTTPException(status_code=404, detail="Suscripción no encontrada")

    if sub.status != "cancelada":
        raise HTTPException(
            status_code=400,
            detail="Solo se pueden eliminar suscripciones canceladas. Cancelá primero.",
        )

    snapshot = {
        "customer_id": sub.customer_id,
        "cadence": sub.cadence,
        "product_summary": sub.product_summary,
    }
    sid = sub.id
    session.delete(sub)
    session.commit()
    record_audit(
        request,
        session=session,
        action="write.suscripcion.delete",
        target_type="suscripcion",
        target_id=sid,
        detail=snapshot,
    )
    session.commit()
    return RedirectResponse(url="/suscripciones", status_code=303)


@router.post("/dispatch")
def suscripciones_dispatch(
    request: Request,
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Generate pending pedidos for every active suscripcion due this week.

    Phase 13 — bridges the gap between Suscripcion (a description) and
    Pedido (a concrete order). Operator-triggered, idempotent per week.

    POST (not GET) because it's a write — creates Pedido rows + AppMeta
    dedupe keys + per-petido_event 'created' rows.
    """
    from app.auth import current_user_id
    from app.services.suscripcion_dispatcher import generate_weekly_pedidos

    actor = str(current_user_id(request) or "operator")
    result = generate_weekly_pedidos(session, actor=actor)

    record_audit(
        request,
        session=session,
        action="write.suscripcion.dispatch",
        target_type="suscripcion",
        target_id="batch",
        detail={
            "generated": result.total,
            "skipped_already_done": len(result.skipped_already_done),
            "skipped_paused": len(result.skipped_paused),
            "skipped_past_end_date": len(result.skipped_past_end_date),
            "skipped_no_dow_match": len(result.skipped_no_dow_match),
        },
    )
    session.commit()
    return RedirectResponse(
        url=f"/suscripciones?dispatched={result.total}", status_code=303
    )


__all__ = ["router"]
