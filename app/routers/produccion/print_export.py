"""app/routers/produccion/print_export.py - Print + CSV export + prep preview.

Sazon-Improvement v2 (2026-10-06) Phase E step 4: extracted from
app/routers/produccion/_full.py lines 1302-1542. Behavior unchanged.

Routes (3 GETs):
  GET /produccion/print        - printable worksheet HTML
  GET /produccion/export.csv   - CSV download of the daily plan
  GET /produccion/prep         - prep/blank worksheet for printing
"""
from __future__ import annotations

import csv
import io
from datetime import date, timedelta

from fastapi import Depends, Query, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rms.dependencies import get_session
from app.rms.models import Product, Recipe
from app.rms.production import plan_production
from app.routers.produccion._helpers import (
    _asuncion_today,
    _current_user_display_name,
    _week_monday,
    source_to_bucket,
)
from app.routers.produccion._router import router
from app.services.template_render import render


@router.get("/print", response_class=HTMLResponse)
def produccion_print(
    request: Request,
    for_date: date | None = Query(None),
    days: int = Query(1, ge=1, le=14),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Printable worksheet for the kitchen shift.

    T-2026-10-04 (P0): Bakers need a paper sheet. The day-view HTML is too
    busy (nav, banners, source explanations, ad-hoc form) to print. This
    view is a stripped-down worksheet: title, date, products, qty,
    checkboxes. No CSS-included chrome — the @media print rules in
    produccion.html + base.html hide the nav/header/footer when printing.

    The handler reuses the same plan_production() call as the day view so
    the printed sheet always matches what the operator sees on screen.

    T-2026-10-04 (Tier 5-H): ?days=N renders N consecutive days as a
    single print job. Each day is its own printable section with
    page-break-after: always. Capped at 14 (2 weeks).
    """
    from app.rms.eod_completions import completions_for_date as _eod_for_date

    target_date = for_date or _asuncion_today()

    # T-2026-10-04 (Tier 5-H): build a list of date -> print_rows, one
    # entry per day in the pack. Single-day is the common case (days=1).
    days_pack: list[dict] = []
    for day_idx in range(days):
        d = target_date + timedelta(days=day_idx)
        plan = plan_production(session, for_date=d)
        completions_by_pid = _eod_for_date(session, d)

        recipes_by_id = {
            r.id: r for r in session.execute(select(Recipe).order_by(Recipe.name)).scalars().all()
        }
        products_by_id = {
            p.id: p for p in session.execute(select(Product).order_by(Product.name)).scalars().all()
        }

        # Build a flat list of (product, qty_to_produce, qty_completed) — one
        # row per product, no overrides, no forecast_source explanation.
        print_rows: list[dict] = []
        for r in plan.rows:
            if r.qty_to_produce <= 0 and r.product_id not in completions_by_pid:
                continue
            recipe = recipes_by_id.get(r.recipe_id) if r.recipe_id else None
            product = products_by_id.get(r.product_id)
            print_rows.append(
                {
                    "product_id": r.product_id,
                    "product_name": r.product_name,
                    "qty_to_produce": r.qty_to_produce,
                    "qty_completed": completions_by_pid.get(r.product_id, 0.0),
                    "recipe_id": r.recipe_id,
                    # T-2026-10-04 (P0): batch info.
                    "yield_qty": recipe.yield_qty if recipe and recipe.yield_qty else None,
                    "yield_unit": recipe.yield_unit if recipe and recipe.yield_qty else None,
                    "portion_label": product.portion_label if product else None,
                }
            )
        # Include ad-hoc bakes (walk-ins / on-the-fly decisions that the
        # forecast never proposed but the operator actually produced).
        planned_pids = {r["product_id"] for r in print_rows}
        for pid, qty in completions_by_pid.items():
            if pid in planned_pids:
                continue
            prod_obj = session.get(Product, pid)
            if prod_obj is None:
                continue
            print_rows.append(
                {
                    "product_id": pid,
                    "product_name": prod_obj.name,
                    "qty_to_produce": 0.0,
                    "qty_completed": qty,
                    "recipe_id": None,
                    "yield_qty": None,
                    "yield_unit": None,
                    "portion_label": prod_obj.portion_label if prod_obj else None,
                }
            )
        days_pack.append({"date": d.isoformat(), "rows": print_rows})

    # T-2026-10-04 (D.4): print-pack header metadata — the printed
    # sheet now shows the ISO week number and the cook's display name
    # so the operator can verify which cook took which day at a glance.
    # Multi-day packs get a "Semana N" header; single-day prints get
    # just the date.
    from datetime import date as _date

    target_date_obj = target_date if isinstance(target_date, _date) else None
    iso_year, iso_week, _ = target_date_obj.isocalendar() if target_date_obj else (None, None, None)
    cook_name = _current_user_display_name(request)
    return render(
        request,
        "produccion_print.html",
        {
            "for_date": target_date.isoformat(),
            "print_rows": days_pack[0]["rows"] if days_pack else [],  # backward compat
            "days_pack": days_pack,
            "days_count": days,
            "shift_saved": int(request.query_params.get("shift_saved", 0)),
            # T-2026-10-04 (Tier 3-D): worksheet mode strips filled-in
            # quantities so the operator can use the printout as a blank
            # sheet to fill by hand. Default = "filled" (current behavior).
            "worksheet_mode": request.query_params.get("mode") == "worksheet",
            # T-2026-10-04 (D.4): print-pack header metadata.
            "iso_week": iso_week,
            "iso_year": iso_year,
            "cook_name": cook_name,
        },
    )


# Sazon-Improvement v2 (2026-10-06) Phase A: CSV export of the daily plan.
# Operators want to paste the plan into WhatsApp for the team or import
# into Excel. The CSV mirrors the day-view columns and uses the same
# SOURCE_BUCKETS / confidence-band mapping as the HTML view so a printed
# row matches the screen. PII (customer names, phones) is NEVER included;
# this endpoint is for production plan only — sales / pedidos have their
# own /ventas/export.csv and /pedidos/export routes.
@router.get("/export.csv")
def produccion_export_csv(
    for_date: date | None = Query(None, description="Plan date (defaults to today Asunción-local)"),
    view: str = Query("day", pattern="^(day|week|month)$"),
    session: Session = Depends(get_session),
) -> Response:
    """Return the production plan as CSV. Columns: product_name, qty_to_produce, source, confidence, is_ad_hoc."""
    target = for_date or _asuncion_today()
    plan = plan_production(session, for_date=target)
    # Sort by descending qty so the largest batches are at the top of the
    # pasted-into-WhatsApp message (cook reads top-down).
    rows = sorted(
        plan.rows,
        key=lambda r: (-r.qty_to_produce, r.product_name),
    )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["product_name", "qty_to_produce", "source", "confidence", "is_ad_hoc"])
    for r in rows:
        bucket = source_to_bucket(r.forecast_source, is_ad_hoc=False)
        writer.writerow([
            r.product_name,
            # Format as int when possible so 50.0 doesn't show as "50.0"
            f"{r.qty_to_produce:g}" if r.qty_to_produce == int(r.qty_to_produce) else f"{r.qty_to_produce}",
            bucket,
            r.confidence_pct,
            False,  # Plan rows are not ad-hoc by definition
        ])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="produccion-{target.isoformat()}.csv"',
            # Cache for 1 minute so a retry doesn't hit the planner twice.
            # Plan computation is fast but no point redoing it.
            "Cache-Control": "private, max-age=60",
        },
    )


@router.get("/prep", response_class=HTMLResponse)
def produccion_prep(
    request: Request,
    week: date | None = Query(None),
    sort: str = Query("severity", pattern=r"^[a-z_]+$"),
    dir: str = Query("asc", pattern=r"^(asc|desc)$"),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """T-2026-10-04 (P2): Weekly ingredient prep sheet for the kitchen.

    Aggregates the production plan across 7 days (Monday → Sunday) and
    shows the ingredient totals the kitchen needs to buy and prep.
    Sorted by severity (Falta first, then Justo, then Suficiente) so
    the cook sees the urgent items first.
    """
    today = _asuncion_today()
    week_start = _week_monday(week or today)
    days = [week_start + timedelta(days=i) for i in range(7)]

    # Aggregate across the week (mirrors the week view's logic).
    ing_required: dict[int, dict] = {}
    for d in days:
        plan = plan_production(session, for_date=d)
        for ln in plan.lines:
            if ln.ingredient_id not in ing_required:
                ing_required[ln.ingredient_id] = {
                    "ingredient_name": ln.ingredient_name,
                    "unit": ln.unit,
                    "qty_required": 0.0,
                    "stock_on_hand": ln.stock_on_hand,
                    "ingredient_id": ln.ingredient_id,
                }
            ing_required[ln.ingredient_id]["qty_required"] += ln.qty_required

    # Compute severity (mirrors produccion.html's logic).
    prep_rows = []
    for v in ing_required.values():
        delta = v["stock_on_hand"] - v["qty_required"]
        if delta < 0:
            severity = "falta"
            to_buy = v["qty_required"] - v["stock_on_hand"]
        elif delta < v["qty_required"] * 0.2:
            severity = "justo"
            to_buy = 0.0
        else:
            severity = "suficiente"
            to_buy = 0.0
        prep_rows.append(
            {
                **v,
                "severity": severity,
                "to_buy": to_buy,
                "delta": delta,
            }
        )

    # Sort: severity (Falta first) then ingredient_name. The user can
    # override via ?sort= but unknown keys fall back to severity.
    severity_order = {"falta": 0, "justo": 1, "suficiente": 2}
    sort_key = sort if sort in (
        "severity", "ingredient", "required", "stock", "to_buy"
    ) else "severity"
    sort_dir = -1 if dir == "desc" else 1
    if sort_key == "severity":
        prep_rows.sort(
            key=lambda x: (
                severity_order.get(x["severity"], 9) * sort_dir,
                x["ingredient_name"],
            )
        )
    elif sort_key == "ingredient":
        prep_rows.sort(
            key=lambda x: x["ingredient_name"],
            reverse=(dir == "desc"),
        )
    elif sort_key == "required":
        prep_rows.sort(
            key=lambda x: x["qty_required"],
            reverse=(dir == "desc"),
        )
    elif sort_key == "stock":
        prep_rows.sort(
            key=lambda x: x["stock_on_hand"],
            reverse=(dir == "desc"),
        )
    elif sort_key == "to_buy":
        prep_rows.sort(
            key=lambda x: x["to_buy"],
            reverse=(dir == "desc"),
        )

    counts = {
        "falta": sum(1 for r in prep_rows if r["severity"] == "falta"),
        "justo": sum(1 for r in prep_rows if r["severity"] == "justo"),
        "suficiente": sum(1 for r in prep_rows if r["severity"] == "suficiente"),
    }

    return render(
        request,
        "produccion_prep.html",
        {
            "week_start": week_start.strftime("%d %b %Y"),
            "week_start_iso": week_start.isoformat(),
            "prev_week_iso": (week_start - timedelta(days=7)).isoformat(),
            "next_week_iso": (week_start + timedelta(days=7)).isoformat(),
            "prep_rows": prep_rows,
            "counts": counts,
            "current_sort": sort,
            "current_dir": dir,
        },
    )


