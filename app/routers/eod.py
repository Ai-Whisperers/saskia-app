"""app/routers/eod.py — /eod (End-of-day checklist).

Built on app/rms/workflow.py which has fresh_eod_checklist() + eod_progress().

GET /eod                      → today's checklist (default)
GET /eod?start=YYYY-MM-DD&end=YYYY-MM-DD
                             → range summary (weekend batch view):
                               total ventas + merma + producción completada
                               for each day in the range. Checklist is
                               NOT shown in range mode (it's per-day only);
                               link to each individual /eod?date=... from
                               the summary.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from loguru import logger
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import require_login_or_disabled as require_login
from app.rms.config import ASUNCION_TZ
from app.rms.dependencies import get_session
from app.rms.eod_completions import completions_for_date, upsert_completion
from app.rms.errors import BadRequest
from app.rms.models import Sale, WasteLog
from app.rms.money import to_int_gs
from app.rms.observability import record_audit
from app.rms.production import plan_production
from app.rms.workflow import EODItemStatus, eod_progress, fresh_eod_checklist
from app.services.template_render import render

router = APIRouter(prefix="/eod", dependencies=[Depends(require_login)])


def _parse_range_date(raw: str | None) -> date | None:
    """Parse YYYY-MM-DD; return None on bad input."""
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()  # noqa: DTZ007
    except ValueError:
        return None


@router.get("", response_class=HTMLResponse)
def eod_view(
    request: Request,
    start: str | None = Query(None, description="Range start YYYY-MM-DD (inclusive)"),
    end: str | None = Query(None, description="Range end YYYY-MM-DD (inclusive)"),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Show today's EOD checklist + today's production plan summary.

    With ?start=YYYY-MM-DD&end=YYYY-MM-DD show a weekend-batch summary
    card instead: ventas, merma, producción plan vs completada per day.
    Checklist stays per-day and is only rendered for "today".
    """
    items = fresh_eod_checklist()
    progress = eod_progress(items)
    # Today's production plan — "se debe registrar cuánto de la producción se completó"
    # (the operator review, T5). We display the forecast so she can reconcile against
    # what was actually produced. Persistence of completions deferred to a future
    # phase; this view surfaces the forecast side.
    today = datetime.now(ASUNCION_TZ).date()
    today_plan = plan_production(session, for_date=today)
    completions = completions_for_date(session, today)

    # P40 (2026-10-07, Ivan): warm the demand snapshot for today + the
    # next 6 days so the morning /produccion/manana finds fresh data
    # without forcing a recompute. Best-effort: a failure here does
    # NOT block the EOD page (operators can still close the day).
    # Excluded from the rendered HTML — just a side effect of opening
    # /eod, the same place the operator already is.
    try:
        from app.rms.production_demand import warm_snapshots_for_dates

        upcoming = [today + timedelta(days=offset) for offset in range(7)]
        warmed = warm_snapshots_for_dates(session, upcoming)
        logger.debug("eod_view: warmed demand snapshots for {} dates", warmed)
    except Exception as exc:
        logger.debug("eod_view: warm_snapshots_for_dates failed: {!r}", exc)

    # Load saved EOD checklist progress from app_meta so refreshing the
    # page shows the operator's checked items.
    saved_keys = set()
    saved_notes = ""
    saved_prefix = f"eod_check_{today.isoformat()}_"
    saved_notes_key = f"eod_notes_{today}"
    from app.rms.models import AppMeta

    rows = session.scalars(select(AppMeta).where(AppMeta.key.like(f"{saved_prefix}%"))).all()
    for r in rows:
        # key is "eod_check_<date>_<item_key>"
        item_key = r.key[len(saved_prefix) :]
        if r.value == "1":
            saved_keys.add(item_key)
    notes_row = session.scalar(select(AppMeta).where(AppMeta.key == saved_notes_key))
    if notes_row:
        saved_notes = notes_row.value or ""

    # Mark each checklist item as DONE using the saved set so the form
    # renders with the operator's progress preserved across reloads.
    from app.rms.workflow import EODItemStatus

    for item in items:
        if item.key in saved_keys:
            item.status = EODItemStatus.DONE

    # PRODUCCION-V3 Phase 5: EOD progress (X of Y done) so the operator
    # can see at a glance how much of the checklist is left before
    # they can submit "Guardar cierre". Mirrors the /produccion hero
    # pattern (4 stat cards) but tuned for the EOD operator surface.
    eod_items_total = len(items)
    eod_items_done = sum(1 for it in items if it.key in saved_keys)
    eod_items_pct = round((eod_items_done * 100) / eod_items_total) if eod_items_total else 0

    # CIE-02: restock step — show ingredients below minimum with a link to
    # /reorder. Checking the close step means she has looked at it.
    from app.rms.reorder import compute_reorder_list

    reorder_items = compute_reorder_list(session)
    # Cap at top 5 most urgent for the dashboard
    reorder_items_top = reorder_items[:5]
    reorder_count = len(reorder_items)
    reorder_total_gs = sum(i.estimated_cost_gs for i in reorder_items if i.has_price)

    # BACKLOG #15: surface "today is closed" state on the EOD header so the
    # operator can see at a glance that the day's books are finalized.
    # eod_is_day_closed returns True iff all mandatory items are checked.
    from app.rms.eod_closed import eod_get_open_days, eod_is_day_closed

    today_is_closed = eod_is_day_closed(session, today)
    # 14-day trailing window for the "open days" reminder so the operator
    # can act on any stale days even when this one is closed.
    open_days = (
        eod_get_open_days(session, today - timedelta(days=14)) if not today_is_closed else []
    )

    # ── Weekend batch: ?start=&end= ──────────────────────────────────────
    # When the operator passes both start and end (e.g. closing Sat+Sun at
    # once on Monday morning), show a per-day summary instead of the
    # today's checklist. Cap at 31 days to avoid pathological queries.
    range_start = _parse_range_date(start)
    range_end = _parse_range_date(end)
    range_summary: list[dict] = []
    range_total_ventas_gs = 0
    range_total_merma_gs = 0
    range_total_operaciones = 0
    range_days = 0
    is_range_mode = False

    # P-39: inline anomaly summary. Same best-effort contract as
    # /eod/print - detection failure must never block the EOD page.
    from app.services.eod_anomaly import detect_anomalies

    try:
        _anomalies = detect_anomalies(session)
        anomaly_count = len(_anomalies) if _anomalies else 0
    except Exception:
        anomaly_count = 0

    if range_start and range_end and range_end >= range_start:
        span_days = (range_end - range_start).days + 1
        if span_days <= 31:
            is_range_mode = True
            range_days = span_days
            # Aggregate sales in range
            range_sales = session.scalars(
                select(Sale).where(
                    Sale.sold_at.isnot(None),
                    Sale.voided_at.is_(None),
                    Sale.sold_at
                    >= datetime.combine(range_start, datetime.min.time()).replace(
                        tzinfo=ASUNCION_TZ
                    ),
                    Sale.sold_at
                    < (
                        datetime.combine(range_end, datetime.min.time()) + timedelta(days=1)
                    ).replace(tzinfo=ASUNCION_TZ),
                )
            ).all()
            for s in range_sales:
                range_total_ventas_gs += to_int_gs(
                    Decimal(str(s.qty)) * Decimal(str(s.unit_price_gs))
                )
                range_total_operaciones += 1
            # Waste in range (WasteLog.value_lost_gs)
            waste_rows = session.scalars(
                select(WasteLog).where(
                    WasteLog.recorded_at
                    >= datetime.combine(range_start, datetime.min.time()).replace(
                        tzinfo=ASUNCION_TZ
                    ),
                    WasteLog.recorded_at
                    < (
                        datetime.combine(range_end, datetime.min.time()) + timedelta(days=1)
                    ).replace(tzinfo=ASUNCION_TZ),
                )
            ).all()
            for w in waste_rows:
                range_total_merma_gs += int(getattr(w, "cost_gs", 0) or 0)
            # Per-day production: completions + plan rows
            cur = range_start
            while cur <= range_end:
                day_plan = plan_production(session, for_date=cur)
                day_comp = completions_for_date(session, cur)
                range_summary.append(
                    {
                        "date_iso": cur.isoformat(),
                        "plan_rows": len(day_plan.rows) if hasattr(day_plan, "rows") else 0,
                        "completed": sum(day_comp.values()),
                    }
                )
                cur += timedelta(days=1)

    # P-39: inline anomaly summary on the EOD page itself (not just print).
    from app.rms.settings_runtime import get_eod_config
    from app.services.eod_anomaly import detect_anomalies

    try:
        eod_cfg = get_eod_config(session)
        _anomalies = detect_anomalies(session, eod_cfg=eod_cfg)
        anomaly_count = len(_anomalies) if _anomalies else 0
    except Exception:
        anomaly_count = 0

    return render(
        request,
        "eod.html",
        {
            "items": items,
            "progress": progress,
            "today_plan": today_plan,
            "completions": completions,
            "today_iso": today.isoformat(),
            # P-39: inline anomaly summary (count; template gates the banner)
            "anomaly_count": anomaly_count,
            # BACKLOG #15 — closed-day state surfaced on the page header
            "today_is_closed": today_is_closed,
            "open_days": [d.isoformat() for d in open_days],
            "saved_notes": saved_notes,
            # CIE-02: restock context for the close
            "reorder_items": reorder_items_top,
            "reorder_count": reorder_count,
            "reorder_total_gs": reorder_total_gs,
            # PRODUCCION-V3 Phase 5: EOD checklist progress. X of Y done
            # so the operator can see what's left before "Guardar cierre"
            # is meaningful. Surfaced in the hero block + progress bar.
            "eod_items_total": eod_items_total,
            "eod_items_done": eod_items_done,
            "eod_items_pct": eod_items_pct,
            # Weekend batch (prelaunch roadmap 2026-09-17)
            "is_range_mode": is_range_mode,
            "range_start_iso": range_start.isoformat() if range_start else "",
            "range_end_iso": range_end.isoformat() if range_end else "",
            "range_days": range_days,
            "range_summary": range_summary,
            "range_total_ventas_gs": range_total_ventas_gs,
            "range_total_merma_gs": range_total_merma_gs,
            "range_total_operaciones": range_total_operaciones,
        },
    )


@router.post("/check")
def eod_check_save(
    request: Request,
    session: Session = Depends(get_session),
    idempotency_key: str = Form(""),
    cash_count: str = Form(""),
    sales_reconciled: str = Form(""),
    low_stock_reviewed: str = Form(""),
    ingredients_reordered: str = Form(""),
    waste_logged: str = Form(""),
    tomorrow_prep: str = Form(""),
    cash_deposit: str = Form(""),
    equipment_cleaned: str = Form(""),
    receipts_archived: str = Form(""),
    notes_for_next: str = Form(""),
) -> RedirectResponse:
    """Persist the operator's EOD checklist progress.

    Cocina does not own these checkboxes. A save from that station
    returns without writing, so piece counts already stored stay as they are.
    """
    from app.rms.stations import escritorio_writes_desk

    if not escritorio_writes_desk(request.session.get("station")):
        return RedirectResponse(
            url="/eod?flash=eod_wrong_station_gerencia",
            status_code=303,
        )

    from datetime import datetime, timezone

    from app.rms.models import AppMeta

    # BACKLOG #9: idempotency. Reserve the AppMeta row before doing any
    # work so a double-click from the cashier (form re-submitted before
    # the 303 redirect lands) lands here as a no-op rather than a second
    # audit + second backup attempt. Mirrors pedidos.py line ~1410
    # pattern (close the F3 race window documented in
    # SASKIA_ARCHITECTURE_REFACTOR_PLAN_2026-09-24.md §F3).
    idem_reserved = False
    if idempotency_key:
        try:
            request_id_eod = getattr(request.state, "request_id", None) or ""
            session.add(
                AppMeta(
                    key=f"eod_save_idem:{idempotency_key}",
                    value=__import__("json").dumps(
                        {
                            "saved_at": datetime.now(timezone.utc).isoformat(),
                            "request_id": request_id_eod,
                        }
                    ),
                    updated_at=datetime.now(timezone.utc).isoformat(),
                )
            )
            session.flush()  # surface IntegrityError without committing
            idem_reserved = True
        except IntegrityError:
            session.rollback()
            return RedirectResponse(
                url="/eod?flash=eod_duplicate",
                status_code=303,
            )

    today = datetime.now(ASUNCION_TZ).date().isoformat()
    now_iso = datetime.now(timezone.utc).isoformat()
    checkboxes = {
        "cash_count": cash_count,
        "sales_reconciled": sales_reconciled,
        "low_stock_reviewed": low_stock_reviewed,
        "ingredients_reordered": ingredients_reordered,
        "waste_logged": waste_logged,
        "tomorrow_prep": tomorrow_prep,
        "cash_deposit": cash_deposit,
        "equipment_cleaned": equipment_cleaned,
        "receipts_archived": receipts_archived,
    }
    for key, value in checkboxes.items():
        is_done = value in ("on", "true", "1", "yes")
        meta_key = f"eod_check_{today}_{key}"
        existing = session.scalar(select(AppMeta).where(AppMeta.key == meta_key))
        if is_done:
            if existing:
                existing.value = "1"
                existing.updated_at = now_iso
            else:
                session.add(AppMeta(key=meta_key, value="1", updated_at=now_iso))
        elif existing:
            session.delete(existing)

    # Notes for next shift (optional free text)
    if notes_for_next.strip():
        meta_key = f"eod_notes_{today}"
        existing = session.scalar(select(AppMeta).where(AppMeta.key == meta_key))
        if existing:
            existing.value = notes_for_next.strip()[:2000]
            existing.updated_at = now_iso
        else:
            session.add(
                AppMeta(
                    key=meta_key,
                    value=notes_for_next.strip()[:2000],
                    updated_at=now_iso,
                )
            )

    items_done = [k for k, v in checkboxes.items() if v in ("on", "true", "1", "yes")]
    record_audit(
        request,
        session=session,
        action="write.eod.checklist.save",
        target_type="eod",
        target_id=today,
        detail={
            "items_done": items_done,
            "idempotency_reserved": idem_reserved,
        },
    )

    # P0 cerrar-puertas (B8 backup): when ALL EOD checklist items are done
    # for the day, fire a backup. backup_scheduler.run_backup is idempotent
    # — re-running for a day that already backed up is a no-op. We wrap in
    # try/except because a backup failure must NOT block the operator from
    # saving the checklist (audit trail takes priority over backup scheduling).
    if len(items_done) == len(checkboxes):
        try:
            from app.rms.config import DB_PATH
            from app.services.backup_scheduler import run_backup

            backup_result = run_backup(session, DB_PATH)
            if not backup_result.skipped:
                record_audit(
                    request,
                    session=session,
                    action="write.backup.triggered",
                    target_type="backup",
                    target_id=0,
                    detail={
                        "trigger": "eod_checklist_complete",
                        "local_path": str(backup_result.local_path)
                        if backup_result.local_path
                        else None,
                        "r2_uploaded": backup_result.r2_uploaded,
                        "local_pruned": backup_result.local_pruned,
                    },
                )
        except Exception as exc:
            from loguru import logger as _logger

            _logger.warning("Backup after EOD close failed: {}", exc)

    session.commit()
    return RedirectResponse(url="/eod?flash=eod_saved", status_code=303)


@router.post("/completar")
def eod_completar(
    request: Request,
    product_id: int = Form(...),
    for_date: date = Form(...),
    completed_qty: float = Form(...),
    notes: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Record how much of a planned product was actually produced (T5).

    Escritorio can read the counts. Saving them from that station is a no-op
    so a checkbox close cannot overwrite what Cocina already wrote.
    """
    from app.rms.stations import cocina_writes_pieces

    if not cocina_writes_pieces(request.session.get("station")):
        return RedirectResponse(
            url="/eod?flash=eod_wrong_station_cocina",
            status_code=303,
        )

    from app.rms.rate_limit import is_write_rate_limited

    if is_write_rate_limited(session, request):
        raise HTTPException(
            status_code=429,
            detail="Demasiadas acciones en 1 minuto. Esperá un momento.",
        )
    try:
        upsert_completion(
            session,
            product_id=product_id,
            for_date=for_date,
            completed_qty=completed_qty,
            notes=notes or None,
        )
    except ValueError as exc:
        # BadRequest inherits HTTPException via the global handler, but
        # now carries reason_code="bad_request" + AppError.context for
        # the audit log. The original str(exc) is preserved via
        # `cause` so the Python repr stays in the local traceback
        # (visible to operators) but the user sees a clean Spanish
        # message (no SQLAlchemy/internal text leak).
        raise BadRequest(
            "Datos inválidos en el cierre del día.",
            context={"original_error": str(exc)},
        ) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Producto no encontrado") from exc

    record_audit(
        request,
        session=session,
        action="write.eod.complete",
        target_type="eod",
        target_id=for_date.isoformat(),
        detail={
            "product_id": product_id,
            "for_date": for_date.isoformat(),
            "completed_qty": completed_qty,
        },
    )
    session.commit()
    return RedirectResponse(url="/eod", status_code=303)


# Tier 8.4 (2026-10-01): EOD anomaly detection endpoint. The operator
# can trigger it manually, and the cron-driven path (when we add one)
# will hit this same URL.
@router.post("/anomalies/run", response_class=HTMLResponse)
def eod_run_anomalies(
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Run EOD anomaly detection for today and email the operator.

    Idempotent. Returns a small HTML page listing the anomalies found
    so the operator sees what fired.
    """
    from app.observability.alerts import dispatch_anomalies
    from app.rms.settings_runtime import get_alerts_config, get_eod_config
    from app.services.eod_anomaly import detect_anomalies

    # Batch B2 + B3 (2026-10-07): fetch operator-tunable thresholds
    # from SettingsKV. Defaults are applied inside get_*_config() for
    # any missing key.
    eod_cfg = get_eod_config(session)
    alerts_cfg = get_alerts_config(session)
    anomalies = detect_anomalies(session, eod_cfg=eod_cfg)
    dispatched = dispatch_anomalies(anomalies, max_per_day=alerts_cfg["max_per_day"])
    return render(
        request,
        "eod_anomalies.html",
        {
            "anomalies": anomalies,
            "dispatched": dispatched,
        },
    )


# Sazon-Improvement v2 (2026-10-06) Phase B: /eod/print — print-friendly
# view for the binder archive. The full /eod view is 5 screens on mobile
# and not print-safe (sidebar + bottom nav + reactive forms). The print
# view is a minimal 1-page summary with: date, checklist status (X de Y),
# today's production plan (forecast side), reorder items, and notes for
# next. Operator files this in the binder at end of month for the close.
@router.get("/print", response_class=HTMLResponse)
def eod_print(
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Render a 1-page printable EOD summary.

    Same date as /eod (today, Asunción-local). Same checklist + plan
    data, but in a stripped-down template with @media print styles so
    it lays out cleanly on A4/Letter and hides nav chrome.
    """
    from app.rms.eod_closed import eod_is_day_closed
    from app.rms.reorder import compute_reorder_list

    today = datetime.now(ASUNCION_TZ).date()
    items = fresh_eod_checklist()
    _progress = eod_progress(items)

    # Checklist progress (X de Y)
    items_total = len(items)
    items_done = sum(1 for it in items if it.status == EODItemStatus.DONE)
    items_pct = round((items_done * 100) / items_total) if items_total else 0

    # Today's production plan
    today_plan = plan_production(session, for_date=today)

    # Reorder items — same as eod_view, but no cap (we want the full list on the print)
    reorder_items = compute_reorder_list(session)
    reorder_total_gs = sum(i.estimated_cost_gs for i in reorder_items if i.has_price)

    # Closed-state
    today_is_closed = eod_is_day_closed(session, today)

    # Anomaly count — surface today's anomalies in the print summary
    # so the binder shows what was flagged. Read from the eod anomaly
    # helper, returning (count, total) for the print section.
    from app.rms.settings_runtime import get_eod_config
    from app.services.eod_anomaly import detect_anomalies

    try:
        eod_cfg = get_eod_config(session)
        anomalies = detect_anomalies(session, eod_cfg=eod_cfg)
        anomaly_count = len(anomalies) if anomalies else 0
    except Exception:
        # If the anomaly helper isn't available in this version, skip silently
        anomaly_count = 0

    return render(
        request,
        "eod_print.html",
        {
            "today": today,
            "items": items,
            "items_total": items_total,
            "items_done": items_done,
            "items_pct": items_pct,
            "today_plan": today_plan,
            "reorder_items": reorder_items,
            "reorder_count": len(reorder_items),
            "reorder_total_gs": reorder_total_gs,
            "today_is_closed": today_is_closed,
            "anomaly_count": anomaly_count,
        },
    )


__all__ = ["router"]
