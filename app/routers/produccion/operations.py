"""app/routers/produccion/operations.py - POST route handlers.

Sazon-Improvement v2 (2026-10-06) Phase E step 4: extracted from
app/routers/produccion/_full.py lines 931-1936. Behavior unchanged.

Routes (9 POSTs):
  POST /produccion/override            - per-day manual qty override
  POST /produccion/copy-last-week      - copy plan from 7d ago as overrides
  POST /produccion/closed              - close/reopen a day (holiday etc)
  POST /produccion/override-bulk       - apply multiple overrides at once
  POST /produccion/shift-execute       - record AM/PM progress for the day
  POST /produccion/ad-hoc              - register one horneado-extra row
  POST /produccion/close-day           - close a day + lock the plan
  POST /produccion/close-day/reopen    - reopen a closed day
  POST /produccion/ad-hoc/bulk         - bulk paste-CSV for ad-hoc rows
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rms.dependencies import get_session
from app.rms.eod_completions import (
    close_day_for_product,
)
from app.rms.eod_completions import (
    upsert_completion as _upsert_completion,
)
from app.rms.models import (
    Product,
    ProductionClosedDay,
)
from app.rms.observability import record_audit
from app.rms.production_demand import persist_plan_audit
from app.routers.produccion._router import router


@router.post("/override")
def produccion_override(
    request: Request,
    for_date: date = Form(...),
    product_id: int = Form(...),
    qty: float = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Per-day manual qty override.

    PRO-01: this saves a row to production_plan_override (date-scoped). The
    weekly template is NOT affected — only this specific date. If qty is 0,
    the override row is removed (so the weekly template takes over again).
    """
    from app.rms.rate_limit import is_write_rate_limited

    if is_write_rate_limited(session, request, max_per_minute=10):
        raise HTTPException(
            status_code=429,
            detail="Demasiadas acciones en 1 minuto. Esperá un momento.",
        )
    if qty < 0:
        raise HTTPException(status_code=400, detail="La cantidad no puede ser negativa")
    if session.get(Product, product_id) is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    from app.auth import current_user_id
    from app.rms.models import ProductionPlanOverride
    from app.rms.production import upsert_override

    user_id = current_user_id(request) or "operator"
    user_id = str(user_id)
    # PRODUCCION-V2 Fase 1: capture old_qty for the audit log BEFORE the
    # upsert/delete so the audit row shows before/after. None for first write.
    prior_row = (
        session.query(ProductionPlanOverride)
        .filter(
            ProductionPlanOverride.product_id == product_id,
            ProductionPlanOverride.for_date == for_date,
        )
        .one_or_none()
    )
    old_qty = float(prior_row.qty) if prior_row is not None else None
    if qty == 0:
        # Remove the override so the weekly template can take over
        if prior_row:
            session.delete(prior_row)
            session.flush()
    else:
        upsert_override(
            session,
            product_id=product_id,
            for_date=for_date,
            qty=qty,
            updated_by=user_id,
        )

    persist_plan_audit(
        session,
        for_date=for_date,
        product_id=product_id,
        old_qty=old_qty,
        new_qty=qty,
        change_source="override",
        changed_by=user_id,
    )
    record_audit(
        request,
        session=session,
        action="write.production.override.set",
        target_type="production",
        target_id=product_id,
        detail={"for_date": for_date.isoformat(), "qty": qty},
    )
    session.commit()
    return RedirectResponse(
        url=f"/produccion?for_date={for_date.isoformat()}",
        status_code=303,
    )


@router.post("/copy-last-week")
def produccion_copy_last_week(
    request: Request,
    for_date: date = Form(...),
    source_date: date | None = Form(None),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Copy last week's plan into this date as ProductionPlanOverride rows.

    Sazon-Improvement v2 (2026-10-06) Phase C: saves the operator ~20
    minutes per menu-planning session. Reads source_date's
    plan_production() output and creates one override per row. The
    target date keeps its own fresh forecast_source (the override is
    just a manual adjustment on top).

    Default source_date is 7 days before for_date if not given.
    Idempotent: existing overrides for the same (product, for_date) are
    overwritten with the source qty. No data is lost; existing overrides
    not present in the source are kept (so this is additive, not a
    destructive replace).
    """
    from app.auth import current_user_id
    from app.rms.models import ProductionPlanOverride
    from app.rms.production import plan_production, upsert_override

    target = for_date
    src = source_date or (for_date - timedelta(days=7))

    # Rate-limit the same as a manual override (1 per 6s)
    from app.rms.rate_limit import is_write_rate_limited

    if is_write_rate_limited(session, request, max_per_minute=10):
        raise HTTPException(
            status_code=429,
            detail="Demasiadas acciones en 1 minuto. Esperá un momento.",
        )

    user_id = current_user_id(request) or "operator"
    user_id = str(user_id)

    # Read source plan (may be empty if source has no forecast)
    src_plan = plan_production(session, for_date=src)
    created = 0
    for r in src_plan.rows:
        if r.qty_to_produce <= 0:
            continue
        # Find existing override for (product, target) to know old_qty
        prior = (
            session.query(ProductionPlanOverride)
            .filter(
                ProductionPlanOverride.product_id == r.product_id,
                ProductionPlanOverride.for_date == target,
            )
            .one_or_none()
        )
        old_qty = float(prior.qty) if prior is not None else None
        upsert_override(
            session,
            product_id=r.product_id,
            for_date=target,
            qty=float(r.qty_to_produce),
            updated_by=user_id,
        )
        created += 1
        persist_plan_audit(
            session,
            for_date=target,
            product_id=r.product_id,
            old_qty=old_qty,
            new_qty=float(r.qty_to_produce),
            change_source="copy_last_week",
            changed_by=user_id,
        )

    record_audit(
        request,
        session=session,
        action="write.production.copy_last_week",
        target_type="production",
        target_id=None,
        detail={
            "source_date": src.isoformat(),
            "target_date": target.isoformat(),
            "overrides_created": created,
        },
    )
    session.commit()
    return RedirectResponse(
        url=f"/produccion?for_date={target.isoformat()}",
        status_code=303,
    )


@router.post("/closed")
def produccion_closed_toggle(
    request: Request,
    for_date: date = Form(...),
    action: str = Form(..., pattern="^(close|reopen)$"),
    reason: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """T-2026-10-04 (P1): Mark a date as closed (holiday/no-bake).

    action='close': insert a ProductionClosedDay row with the optional
                    reason. If reason is empty, defaults to 'Cerrado'.
    action='reopen': delete the ProductionClosedDay row for for_date.

    Returns 303 redirect to the day view so the operator sees the
    banner / banner removal immediately.
    """
    from app.auth import current_user_id
    from app.rms.rate_limit import is_write_rate_limited

    if is_write_rate_limited(session, request, max_per_minute=10):
        from fastapi import HTTPException

        raise HTTPException(status_code=429, detail="rate_limited")

    if action == "close":
        existing = session.get(ProductionClosedDay, for_date)
        closed_by_user = current_user_id(request) or "operator"
        if existing is None:
            row = ProductionClosedDay(
                for_date=for_date,
                reason=(reason or "Cerrado")[:120],
                closed_by=closed_by_user,
                closed_at=datetime.now(ASUNCION_TZ),
            )
            session.add(row)
            record_audit(
                request,
                session=session,
                action="production_closed",
                target_type="production_closed_day",
                target_id=for_date.isoformat(),
                detail={"reason": row.reason},
            )
        else:
            # Update reason in case operator wants to refine it
            existing.reason = (reason or existing.reason or "Cerrado")[:120]
            existing.closed_at = datetime.now(ASUNCION_TZ)
    else:  # reopen
        existing = session.get(ProductionClosedDay, for_date)
        if existing is not None:
            session.delete(existing)
            record_audit(
                request,
                session=session,
                action="production_reopened",
                target_type="production_closed_day",
                target_id=for_date.isoformat(),
            )

    session.commit()
    return RedirectResponse(
        url=f"/produccion?for_date={for_date.isoformat()}",
        status_code=303,
    )


@router.post("/override-bulk")
async def produccion_override_bulk(
    request: Request,
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Bulk per-day qty overrides from /produccion/manana's unified form.

    The manana page (da0abe8 redesign) renders ONE form with per-row
    ``qty[<product_id>]`` inputs and a single Save button. This endpoint
    consumes that shape: each non-empty qty[<id>] field becomes (or clears,
    at qty=0) a date-scoped ProductionPlanOverride — same semantics as the
    single-row /produccion/override, applied N times in one commit.
    """
    from app.rms.rate_limit import is_write_rate_limited

    if is_write_rate_limited(session, request, max_per_minute=10):
        raise HTTPException(
            status_code=429,
            detail="Demasiadas acciones en 1 minuto. Esperá un momento.",
        )

    from app.auth import current_user_id
    from app.rms.models import Product, ProductionPlanOverride
    from app.rms.production import upsert_override

    form = await request.form()
    raw_for_date = str(form.get("for_date") or "").strip()
    try:
        for_date = date.fromisoformat(raw_for_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Fecha inválida") from None

    user_id = str(current_user_id(request) or "operator")

    # Collect qty[<product_id>] fields
    entries: dict[int, float] = {}
    for key, value in form.items():
        if not key.startswith("qty[") or not key.endswith("]"):
            continue
        raw = str(value).strip()
        if raw == "":
            continue  # untouched row — leave the forecast as-is
        try:
            pid = int(key[4:-1])
            qty = float(raw)
        except (TypeError, ValueError):
            continue
        if qty < 0:
            raise HTTPException(status_code=400, detail="La cantidad no puede ser negativa")
        entries[pid] = qty

    applied = 0
    for pid, qty in entries.items():
        if session.get(Product, pid) is None:
            raise HTTPException(status_code=404, detail="Producto no encontrado")
        # PRODUCCION-V2 Fase 1: capture old_qty for the audit log BEFORE
        # the upsert/delete so the audit row shows before/after.
        prior_bulk_row = (
            session.query(ProductionPlanOverride)
            .filter(
                ProductionPlanOverride.product_id == pid,
                ProductionPlanOverride.for_date == for_date,
            )
            .one_or_none()
        )
        old_qty = float(prior_bulk_row.qty) if prior_bulk_row is not None else None
        if qty == 0:
            if prior_bulk_row:
                session.delete(prior_bulk_row)
                session.flush()
        else:
            upsert_override(
                session,
                product_id=pid,
                for_date=for_date,
                qty=qty,
                updated_by=user_id,
            )
        persist_plan_audit(
            session,
            for_date=for_date,
            product_id=pid,
            old_qty=old_qty,
            new_qty=qty,
            change_source="override_bulk",
            changed_by=user_id,
        )
        record_audit(
            request,
            session=session,
            action="write.production.override.set",
            target_type="production",
            target_id=pid,
            detail={"for_date": for_date.isoformat(), "qty": qty, "bulk": True},
        )
        applied += 1

    session.commit()
    return RedirectResponse(
        url=f"/produccion/manana?saved={applied}",
        status_code=303,
    )


# --- Shift execution layer (Sprint 1) ---
#
# The day view renders a "Ejecución del turno" form that lets the operator
# mark checkboxes + enter a qty per product. Until Sprint 1 this form
# posted to /produccion/override, which IGNORED the `completed_*`
# fields and only wrote production_plan_override (which is the PLAN,
# not the actual). The actual production is what the operator really baked;
# the helper `upsert_completion()` in app.rms.eod_completions already
# writes the right table — we just need an endpoint that accepts the
# bulk form.
#
# This endpoint iterates over form keys `done_{pid}` + `completed_{pid}`
# and writes one upsert per product with a non-zero value. Items with
# `done_{pid}` checked AND `completed_{pid} == 0` are recorded as 0
# (operator said "I marked this done but produced nothing" — honest).


@router.post("/shift-execute")
async def produccion_shift_execute(
    request: Request,
    for_date: date = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Persist actual production qty per product (the "ya salió del horno" tracker).

    T-2026-10-04 (Tier 5-K): if the form was opened before the latest
    `updated_at` for this date (meaning another cook saved while you were
    typing), we surface a soft warning via the redirect (no hard block —
    last-write-wins remains, but the user knows they may have stomped).
    The check uses the optional `form_opened_at` form field; older clients
    without the field skip the check.
    """
    from datetime import datetime, timezone

    from app.auth import current_user_id
    from app.rms.rate_limit import is_write_rate_limited

    if is_write_rate_limited(session, request, max_per_minute=10):
        raise HTTPException(
            status_code=429,
            detail="Demasiadas acciones en 1 minuto. Esperá un momento.",
        )

    # PRODUCCION-V3 Phase 0: backdate cap. Reject for_date older than
    # BACKDATE_WINDOW_DAYS (default 7) — otherwise a stray 2020-01-01
    # backfill would corrupt the 14-day rolling forecast. Also reject
    # future dates (use /produccion/override for tomorrow's plan).
    from datetime import timedelta

    from app.rms.config import ASUNCION_TZ, BACKDATE_WINDOW_DAYS

    today_local = datetime.now(ASUNCION_TZ).date()
    if for_date > today_local:
        raise HTTPException(
            status_code=400,
            detail=(
                f"La fecha no puede ser futura ({for_date.isoformat()}). "
                f"Para planificar el futuro, usá /produccion/override."
            ),
        )
    if for_date < today_local - timedelta(days=BACKDATE_WINDOW_DAYS):
        raise HTTPException(
            status_code=400,
            detail=(
                f"La fecha {for_date.isoformat()} está fuera de la ventana de "
                f"{BACKDATE_WINDOW_DAYS} días hacia atrás. Si necesitás backfill "
                f"más viejo, cambiá AIW_RMS_BACKDATE_DAYS en el servidor."
            ),
        )

    form = await request.form()
    form_opened_at_raw = form.get("form_opened_at")
    user_id = str(current_user_id(request) or "operator")

    # T-2026-10-04 (Tier 5-K): detect concurrent modification. Compare
    # the form's open-time against the latest updated_at on this date.
    # If form_opened_at < max(updated_at), someone else saved while
    # we were filling it out.
    concurrent_modify = False
    if form_opened_at_raw:
        try:
            # The form sends naive local time; treat as UTC for compare.
            form_opened_at = datetime.fromisoformat(str(form_opened_at_raw))
            if form_opened_at.tzinfo is None:
                form_opened_at = form_opened_at.replace(tzinfo=timezone.utc)
            # Read max(updated_at) for this date.
            latest_row = session.execute(
                __import__("sqlalchemy").text(
                    "SELECT MAX(updated_at) FROM production_completion WHERE for_date = :d"
                ),
                {"d": for_date.isoformat()},
            ).scalar()
            if latest_row is not None:
                # SQLite returns strings; normalize.
                if isinstance(latest_row, str):
                    latest_ts = datetime.fromisoformat(latest_row)
                    if latest_ts.tzinfo is None:
                        latest_ts = latest_ts.replace(tzinfo=timezone.utc)
                else:
                    latest_ts = latest_row
                if latest_ts > form_opened_at:
                    concurrent_modify = True
        except (ValueError, TypeError) as exc:
            # T-2026-10-04: log the parse failure (was silent pass; now
            # the operator log + test_no_silent_excepts can see it).
            # Bad/missing format — skip the concurrent-edit check.
            logger.debug(f"produccion.shift_execute: bad form_opened_at format: {exc!r}")

    saved = 0
    skipped = 0
    for key, value in form.multi_items():
        if not isinstance(value, str):
            # skip file uploads / non-str values
            continue
        if not key.startswith("completed_"):
            continue
        try:
            product_id = int(key.removeprefix("completed_"))
        except ValueError:
            skipped += 1
            continue
        try:
            qty = float(value)
        except (TypeError, ValueError):
            skipped += 1
            continue
        if qty < 0:
            skipped += 1
            continue
        if session.get(Product, product_id) is None:
            skipped += 1
            continue
        # PRODUCCION-V2 Fase 1: capture old_qty for the audit log BEFORE
        # the upsert so the audit row shows before/after.
        from app.rms.models import ProductionCompletion

        prior_completion = (
            session.query(ProductionCompletion)
            .filter(
                ProductionCompletion.product_id == product_id,
                ProductionCompletion.for_date == for_date,
            )
            .one_or_none()
        )
        old_qty = float(prior_completion.completed_qty) if prior_completion is not None else None
        _upsert_completion(
            session,
            product_id=product_id,
            for_date=for_date,
            completed_qty=qty,
        )
        persist_plan_audit(
            session,
            for_date=for_date,
            product_id=product_id,
            old_qty=old_qty,
            new_qty=qty,
            change_source="shift_execute",
            changed_by=user_id,
        )
        saved += 1

    # PRODUCCION-V3 Phase 0: persist closure status from the
    # `done_<product_id>` checkbox. Previously the cook checked the
    # box, the page rendered the row as done (CSS strikethrough), but
    # the DB never saw `status='done'` — silent data loss. Now we
    # scan for done_<pid> fields AFTER the completed_<pid> loop so a
    # `done_<pid>=1` with no corresponding `completed_<pid>` still
    # creates a row (cook marked it done with 0 units baked).
    from app.rms.eod_completions import close_day_for_product

    closed_count = 0
    for key, value in form.multi_items():
        if not isinstance(value, str):
            continue
        if not key.startswith("done_"):
            continue
        try:
            product_id = int(key.removeprefix("done_"))
        except ValueError:
            continue
        if session.get(Product, product_id) is None:
            continue
        if value == "1":
            close_day_for_product(
                session,
                product_id=product_id,
                for_date=for_date,
                status="done",
            )
            closed_count += 1

    record_audit(
        request,
        session=session,
        action="write.production.shift.execute",
        target_type="production_shift",
        target_id=for_date.isoformat(),
        detail={
            "saved": saved,
            "skipped": skipped,
            "for_date": for_date.isoformat(),
            "concurrent_modify": concurrent_modify,  # T-2026-10-04 (Tier 5-K)
            "closed": closed_count,  # PRODUCCION-V3 Phase 0
        },
    )
    session.commit()
    redirect_url = f"/produccion?for_date={for_date.isoformat()}&shift_saved={saved}"
    # T-2026-10-04 (D.2): preserve shift context on redirect. If the
    # cook deep-linked into the PM shift and saved, we want to send
    # them back to the PM view (not default to ""). The form was
    # already parsed at the top of the function — reuse it.
    shift_ctx = str(form.get("shift", "")).strip()
    if shift_ctx in ("AM", "PM"):
        redirect_url += f"&shift={shift_ctx}"
    if concurrent_modify:
        # T-2026-10-04 (Tier 5-K): append the flag so the day view can
        # render the "se actualizó mientras escribías" warning.
        redirect_url += "&concurrent_modify=1"
    return RedirectResponse(
        url=redirect_url,
        status_code=303,
    )


# --- Ad-hoc bake entry (Sprint 4) ---
#
# the operator might bake a product that was NOT in the plan (walk-in order,
# decided on a whim, leftover ingredients). This endpoint writes a
# ProductionCompletion row with notes="ad_hoc" so the actual count
# shows up in the day view + EOD, even though the forecast engine
# never proposed it.


@router.post("/ad-hoc")
async def produccion_ad_hoc(
    request: Request,
    for_date: date = Form(...),
    product_id: int = Form(...),
    qty: float = Form(...),
    notes: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Record an unplanned bake: walked-in, decided-on-the-fly, leftovers."""
    from app.auth import current_user_id
    from app.rms.rate_limit import is_write_rate_limited

    if is_write_rate_limited(session, request, max_per_minute=10):
        raise HTTPException(
            status_code=429,
            detail="Demasiadas acciones en 1 minuto. Esperá un momento.",
        )
    if qty <= 0:
        raise HTTPException(
            status_code=400,
            detail="La cantidad debe ser mayor a cero.",
        )
    if session.get(Product, product_id) is None:
        raise HTTPException(
            status_code=404,
            detail="Producto no encontrado",
        )

    user_id = str(current_user_id(request) or "operator")
    tag = "ad_hoc"
    if notes.strip():
        tag = f"ad_hoc: {notes.strip()[:200]}"
    # PRODUCCION-V2 Fase 1: capture old_qty for the audit log BEFORE the upsert.
    from app.rms.models import ProductionCompletion

    prior_adhoc = (
        session.query(ProductionCompletion)
        .filter(
            ProductionCompletion.product_id == product_id,
            ProductionCompletion.for_date == for_date,
        )
        .one_or_none()
    )
    old_qty = float(prior_adhoc.completed_qty) if prior_adhoc is not None else None
    _upsert_completion(
        session,
        product_id=product_id,
        for_date=for_date,
        completed_qty=qty,
        notes=tag,
    )
    persist_plan_audit(
        session,
        for_date=for_date,
        product_id=product_id,
        old_qty=old_qty,
        new_qty=qty,
        change_source="adhoc",
        changed_by=user_id,
        notes=tag,
    )
    record_audit(
        request,
        session=session,
        action="write.production.ad_hoc",
        target_type="production_ad_hoc",
        target_id=f"{for_date.isoformat()}:{product_id}",
        detail={
            "for_date": for_date.isoformat(),
            "product_id": product_id,
            "qty": qty,
            "notes": notes.strip()[:200] or None,
        },
    )
    session.commit()
    return RedirectResponse(
        url=f"/produccion?for_date={for_date.isoformat()}&adhoc_added=1",
        status_code=303,
    )


# ─────────────────────────────────────────────────────────────────────
# T-2026-10-05 (B.7) — Bulk ad-hoc bakes via CSV upload
# ─────────────────────────────────────────────────────────────────────
# On a busy Saturday the operator has 8-12 walk-ins. Typing each into
# the form takes 4 form fills × ~10s = 40s. A single CSV paste drops
# that to ~5s of paste + ~2s of commit.
#
# Format:  product_id,qty,notes
#          42,1.5,Cliente VIP
#          15,2.0,
#
# Validation rules:
#   - Header is optional. If present, must contain product_id,qty,notes
#     (order-independent, notes column may be omitted).
#   - product_id must exist; skip with warning if not.
#   - qty > 0; skip with warning if not.
#   - max 200 rows per upload (anti-fat-finger DoS).
#   - Rate-limited like the single-row form (10 writes/minute).


# --- PRODUCCION-V2 Fase 2: Close-day endpoint ---
#
# The cook taps "Cerrar turno" on each row at end of shift. This endpoint
# flips production_completion.status from 'open' to 'done' (or 'cancelled'
# when they actually baked nothing). closure_notes is OPTIONAL — the audit
# log captures who closed and when regardless of notes, so the operator doesn't
# have to type a justification for the rare zero-qty case.
#
# Bulk semantics: this endpoint takes a SINGLE product per POST. The
# "Cerrar todas" button on the day view fires N POSTs in a loop via
# fetch(). One POST per row keeps the audit log 1-row-per-product and
# avoids partial-failure ambiguity (any failure is per-product visible).


@router.post("/close-day")
def produccion_close_day(
    request: Request,
    for_date: date = Form(...),
    product_id: int = Form(...),
    status: str = Form("done", pattern="^(done|cancelled)$"),
    closure_notes: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Mark a single product's shift as closed for the given date.

    PRODUCCION-V2 Fase 2: replaces the implicit "anyone can edit
    forever" behavior of production_completion. After the cook closes
    the day, the row is still editable (we don't lock the table — the
    audit log + visibility of the closed state is the social contract),
    but the UI surfaces a "Cerrado" badge so the next cook knows.
    """
    from app.auth import current_user_id
    from app.rms.rate_limit import is_write_rate_limited

    if is_write_rate_limited(session, request, max_per_minute=10):
        raise HTTPException(
            status_code=429,
            detail="Demasiadas acciones en 1 minuto. Esperá un momento.",
        )
    if session.get(Product, product_id) is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    user_id = str(current_user_id(request) or "operator")
    notes = closure_notes.strip()[:500] or None  # truncate; NULL when blank
    try:
        close_day_for_product(
            session,
            product_id=product_id,
            for_date=for_date,
            closure_notes=notes,
            status=status,
        )
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Audit the closure (Fase 1's persist_plan_audit) so the change_source
    # shows up in /accuracy timelines. The completion row itself
    # (completed_qty, recorded_at) doesn't change; the audit log just
    # records the close action.
    persist_plan_audit(
        session,
        for_date=for_date,
        product_id=product_id,
        old_qty=None,  # closure isn't a qty change
        new_qty=0.0,  # the audit row's new_qty is 0 since we're not changing qty
        change_source=f"close_day_{status}",
        changed_by=user_id,
        notes=notes,
    )
    record_audit(
        request,
        session=session,
        action="write.production.close_day",
        target_type="production_completion",
        target_id=f"{for_date.isoformat()}:{product_id}",
        detail={"status": status, "closure_notes": notes or ""},
    )
    session.commit()
    # Preserve the ui=v2 flag on redirect so the cook lands back on the
    # new grilla.
    ui_q = ""
    ui_param = str(request.query_params.get("ui") or "")
    if ui_param == "v2":
        ui_q = "&ui=v2"
    return RedirectResponse(
        url=f"/produccion?for_date={for_date.isoformat()}{ui_q}",
        status_code=303,
    )


@router.post("/close-day/reopen")
def produccion_close_day_reopen(
    request: Request,
    for_date: date = Form(...),
    product_id: int = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Reopen a closed row so the cook can correct a mistake.

    Reverses the close-day action. We don't keep a separate reopen
    audit row — the `close_day_done` audit row already captures the
    close, and the row's status='open' field is enough to render the
    right state. Future Fase 3 might add a reopen audit; for now
    /accuracy treats reopens as "in flight" and the cook can re-close.
    """
    from app.auth import current_user_id
    from app.rms.rate_limit import is_write_rate_limited

    if is_write_rate_limited(session, request, max_per_minute=10):
        raise HTTPException(
            status_code=429,
            detail="Demasiadas acciones en 1 minuto. Esperá un momento.",
        )
    if session.get(Product, product_id) is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    user_id = str(current_user_id(request) or "operator")
    try:
        close_day_for_product(
            session,
            product_id=product_id,
            for_date=for_date,
            closure_notes=None,  # keep the existing notes
            status="open",
        )
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    persist_plan_audit(
        session,
        for_date=for_date,
        product_id=product_id,
        old_qty=None,
        new_qty=0.0,
        change_source="close_day_reopen",
        changed_by=user_id,
        notes=None,
    )
    record_audit(
        request,
        session=session,
        action="write.production.close_day.reopen",
        target_type="production_completion",
        target_id=f"{for_date.isoformat()}:{product_id}",
        detail={},
    )
    session.commit()
    ui_q = ""
    ui_param = str(request.query_params.get("ui") or "")
    if ui_param == "v2":
        ui_q = "&ui=v2"
    return RedirectResponse(
        url=f"/produccion?for_date={for_date.isoformat()}{ui_q}",
        status_code=303,
    )


@router.post("/ad-hoc/bulk")
async def produccion_ad_hoc_bulk(
    request: Request,
    for_date: date = Form(...),
    csv: str = Form(""),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """T-2026-10-05 (B.7) — Paste-many ad-hoc bakes via CSV.

    Returns a JSON-ish redirect-friendly page with the import summary
    (created / skipped / errors). Skips invalid lines instead of
    failing the whole batch — partial success is more useful than
    nothing. Operators see what worked and what didn't.
    """
    from app.rms.rate_limit import is_write_rate_limited

    if is_write_rate_limited(session, request, max_per_minute=10):
        raise HTTPException(
            status_code=429,
            detail="Demasiadas acciones en 1 minuto. Esperá un momento.",
        )

    csv = (csv or "").strip()
    if not csv:
        raise HTTPException(status_code=400, detail="CSV vacío")

    MAX_ROWS = 200
    lines = [ln for ln in csv.splitlines() if ln.strip()]
    # Detect optional header
    if lines and lines[0].lower().startswith("product_id"):
        header = [c.strip().lower() for c in lines[0].split(",")]
        has_notes = "notes" in header or "notas" in header
        data_lines = lines[1:]
    else:
        header = ["product_id", "qty", "notes"]
        has_notes = True
        data_lines = lines

    if len(data_lines) > MAX_ROWS:
        raise HTTPException(
            status_code=400,
            detail=f"Demasiadas filas (max {MAX_ROWS}). Subí en lotes.",
        )

    # Cache product lookups
    valid_product_ids: set[int] = set(session.execute(select(Product.id)).scalars().all())

    # PRODUCCION-V2 Fase 1: get the cook's user id for the audit log.
    from app.auth import current_user_id

    bulk_user_id = str(current_user_id(request) or "operator")
    from app.rms.models import ProductionCompletion

    created: list[dict] = []
    skipped: list[dict] = []
    for row_num, raw in enumerate(data_lines, start=2 if len(lines) != len(data_lines) else 1):
        cells = [c.strip() for c in raw.split(",")]
        if len(cells) < 2:
            skipped.append(
                {"line": row_num, "raw": raw, "reason": "Faltan columnas (minimo product_id, qty)"}
            )
            continue
        try:
            pid = int(cells[0])
            qty = float(cells[1])
        except ValueError:
            skipped.append(
                {"line": row_num, "raw": raw, "reason": "product_id o qty no son números"}
            )
            continue
        notes = cells[2] if has_notes and len(cells) > 2 else ""
        if pid not in valid_product_ids:
            skipped.append({"line": row_num, "raw": raw, "reason": f"Producto {pid} no existe"})
            continue
        if qty <= 0:
            skipped.append({"line": row_num, "raw": raw, "reason": "qty debe ser > 0"})
            continue

        tag = "ad_hoc"
        if notes.strip():
            tag = f"ad_hoc: {notes.strip()[:200]}"
        # PRODUCCION-V2 Fase 1: capture old_qty for the audit log.
        prior_bulk_completion = (
            session.query(ProductionCompletion)
            .filter(
                ProductionCompletion.product_id == pid,
                ProductionCompletion.for_date == for_date,
            )
            .one_or_none()
        )
        old_qty = (
            float(prior_bulk_completion.completed_qty)
            if prior_bulk_completion is not None
            else None
        )
        _upsert_completion(
            session,
            product_id=pid,
            for_date=for_date,
            completed_qty=qty,
            notes=tag,
        )
        persist_plan_audit(
            session,
            for_date=for_date,
            product_id=pid,
            old_qty=old_qty,
            new_qty=qty,
            change_source="adhoc_bulk",
            changed_by=bulk_user_id,
            notes=tag,
        )
        created.append({"line": row_num, "product_id": pid, "qty": qty, "notes": notes})

    if created:
        record_audit(
            request,
            session=session,
            action="write.production.ad_hoc_bulk",
            target_type="production_ad_hoc",
            target_id=for_date.isoformat(),
            detail={
                "for_date": for_date.isoformat(),
                "created_count": len(created),
                "skipped_count": len(skipped),
                "product_ids": [c["product_id"] for c in created],
            },
        )
        session.commit()

    # Render the summary as a tiny HTML page so the operator sees what
    # worked. Redirect to /produccion would lose the per-line detail.
    summary_html = [
        "<!doctype html><html><head><meta charset='utf-8'>",
        "<title>Importación bulk — /produccion</title>",
        "<link rel='stylesheet' href='/static/app.css'>",
        "</head><body><main class='container'>",
        f"<h1>📥 Importación bulk ({for_date.isoformat()})</h1>",
        f"<p class='alert alert-success' role='alert'>✅ {len(created)} horneadas registradas, "
        f"{len(skipped)} omitidas.</p>",
        "<h2>Registradas</h2>",
        "<table class='table'><thead><tr><th>Línea</th><th>Producto</th><th>Cantidad</th><th>Notas</th></tr></thead><tbody>",
    ]
    prod_id_to_name: dict[int, str] = {
        p.id: p.name for p in session.execute(select(Product.id, Product.name)).all()
    }
    summary_html.extend(
        f"<tr><td>{c['line']}</td><td>{prod_id_to_name.get(c['product_id'], c['product_id'])}</td>"
        f"<td>{c['qty']}</td><td>{c['notes']}</td></tr>"
        for c in created
    )
    summary_html.append("</tbody></table>")
    if skipped:
        summary_html.append(
            "<h2>⚠️ Omitidas</h2><table class='table'><thead><tr><th>Línea</th><th>Texto</th><th>Motivo</th></tr></thead><tbody>"
        )
        summary_html.extend(
            f"<tr><td>{s['line']}</td><td><code>{s['raw']}</code></td><td>{s['reason']}</td></tr>"
            for s in skipped
        )
        summary_html.append("</tbody></table>")
    summary_html.append(
        f"<p><a class='btn' href='/produccion?for_date={for_date.isoformat()}&adhoc_added=1'>Volver al plan</a></p>"
        "</main></body></html>"
    )
    from fastapi.responses import HTMLResponse

    return HTMLResponse(content="".join(summary_html))


# --- PRO-01: weekly template ---
