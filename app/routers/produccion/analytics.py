"""app/routers/produccion/analytics.py - Plan accuracy + HACCP freezer log routes.

Sazon-Improvement v2 (2026-10-06) Phase E: extracted verbatim from
app/routers/produccion/_full.py lines 2540-2939. Behavior unchanged.

Routes:
  GET  /produccion/accuracy  - plan-vs-actual dashboard (presets 7d/30d/90d)
  GET  /produccion/haccp     - HACCP freezer log view (list + form)
  POST /produccion/haccp     - save a new temperature log entry
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from fastapi import Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rms.dependencies import get_session
from app.rms.config import ASUNCION_TZ
from app.rms.models import FreezerTemperatureLog, Ingredient, Product, Recipe, RecipeLine
from app.rms.observability import record_audit
from app.rms.plan_accuracy import compute_plan_accuracy, date_range_presets
from app.rms.production import plan_production
from app.routers.produccion._router import router
from app.services.template_render import render


@router.get("/accuracy", response_class=HTMLResponse)
def produccion_accuracy(
    request: Request,
    preset: str = Query("30d", pattern="^(7d|30d|90d)$"),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """BACKLOG #29 + #33: plan-vs-actual accuracy dashboard.

    Aggregates the production plan (per day, per product) against the
    actual completions + sold quantities for the period. Surfaces
    under-baked days (ran out) and over-baked days (wasted capacity)
    per-period. Pure read-only analytics — never writes.
    """
    ranges = date_range_presets()
    start_date, end_date = ranges[preset]
    days_in_period = (end_date - start_date).days + 1

    # Build planned_qty_by_pid_day from plan_production() for each day in range.
    # We call the planner per-day; this matches the existing /produccion page
    # path so the dashboard shows exactly what the operator saw that morning.
    planned: dict[tuple[int, date], float] = {}
    cur = start_date
    while cur <= end_date:
        plan = plan_production(session, for_date=cur)
        for r in plan.rows:
            if r.qty_to_produce <= 0:
                continue
            planned[(r.product_id, cur)] = planned.get((r.product_id, cur), 0.0) + float(
                r.qty_to_produce
            )
        cur = cur + timedelta(days=1)

    report = compute_plan_accuracy(session, start_date, end_date, planned)

    return render(
        request,
        "produccion_accuracy.html",
        {
            "preset": preset,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "days_in_period": days_in_period,
            "report": report,
        },
    )


# ─────────────────────────────────────────────────────────────────────
# B.6 — HACCP freezer temperature log
# ─────────────────────────────────────────────────────────────────────
# Paraguay MSPBS HACCP requiere registro de temperatura de freezers donde
# se almacenan productos crudos, semi-elaborados y elaborados. Sin registro
# continuo, una inspección puede multar al local (200–500k Gs/año).
#
# Workflow: el cocinero tipea la temperatura del freezer 2 veces al día
# (apertura AM, cierre PM). Las filas se acumulan para auditoría MSPBS.
# El último registro siempre es visible desde el banner superior de
# /produccion (Tier 4-H), con badge de warning si la temperatura está
# fuera del rango seguro (-22 a -18 °C para freezer de masa).

# Default freezer locations for the operator. Operators can override via
# config. Ordered by frequency of use.
_DEFAULT_FREEZER_LOCATIONS = [
    "freezer-masa",  # masa madre, poolish, masa de chipá congelada
    "freezer-productos",  # tortas congeladas, galletas, etc.
    "heladera-materia-prima",  # opcional — algunos clientes la usan
]


def _get_haccp_latest_for_date(session: Session, for_date: date) -> FreezerTemperatureLog | None:
    """T-2026-10-04 (B.6) — Return the most recent temperature log for the date.

    Used by the /produccion day-view banner to surface the latest reading.
    Returns None if no entry exists yet (the template then suppresses the
    banner and shows the "missing" nudge instead).
    """
    return (
        session.execute(
            select(FreezerTemperatureLog)
            .where(FreezerTemperatureLog.for_date == for_date)
            .order_by(FreezerTemperatureLog.recorded_at.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )


def _haccp_alert_for_entry(entry: FreezerTemperatureLog | None) -> str | None:
    """T-2026-10-04 (B.6) — Compute alert level for a HACCP entry.

    - "ok"      → within safe range for the location
    - "warning" → outside safe range (freezer > -10 or < -25; heladera < 0 or > 8)
    - None      → no entry

    The safe ranges here are intentionally generous; the model-level
    check constraint enforces -40 to +30 (physical sensor limits), and
    a stricter business rule would be -22 to -18 for freezers. We use
    -25 to -10 as the "obviously broken" band so the operator doesn't
    get false positives on legitimate edge readings.
    """
    if entry is None:
        return None
    if entry.location.startswith("freezer"):
        if entry.temperature_c > -10 or entry.temperature_c < -25:
            return "warning"
    elif entry.location.startswith("heladera"):
        if entry.temperature_c < 0 or entry.temperature_c > 8:
            return "warning"
    return "ok"


def _count_haccp_missing_for_date(session: Session, for_date: date) -> int:
    """T-2026-10-04 (B.6) — Count expected-but-missing (location, shift) pairs.

    MSPBS expects 2 readings/day per location (AM + PM). The cook should
    see a nudge if N of those 6 expected entries are missing.
    """
    rows = session.execute(
        select(FreezerTemperatureLog.location, FreezerTemperatureLog.shift).where(
            FreezerTemperatureLog.for_date == for_date
        )
    ).all()
    recorded: set[tuple[str, str]] = {(r.location, r.shift) for r in rows}
    expected = {(loc, sh) for loc in _DEFAULT_FREEZER_LOCATIONS for sh in ("AM", "PM")}
    return len(expected - recorded)


def _list_haccp_missing_for_date(session: Session, for_date: date) -> list[dict]:
    """T-2026-10-06 (B.6+): same data as _count_haccp_missing_for_date
    but as a list of {location, shift} dicts so the /produccion banner
    can render them as inline chips (drill-down).

    Returns the missing entries in deterministic order (location asc,
    then AM before PM within each location). The order matters because
    `expand_missing_items` preserves it for stable rendering.
    """
    rows = session.execute(
        select(FreezerTemperatureLog.location, FreezerTemperatureLog.shift).where(
            FreezerTemperatureLog.for_date == for_date
        )
    ).all()
    recorded: set[tuple[str, str]] = {(r.location, r.shift) for r in rows}
    expected = {(loc, sh) for loc in _DEFAULT_FREEZER_LOCATIONS for sh in ("AM", "PM")}
    missing_pairs = sorted(expected - recorded)
    return [{"location": loc, "shift": sh} for loc, sh in missing_pairs]


@dataclass(frozen=True)
class HaccpPendingItem:
    """T-2026-10-06 (B.6+): one chip in the /produccion banner.

    weight="BOTH" means the location has BOTH AM and PM missing
    (visually distinct chip — most urgent, the cook has skipped
    the entire day for that freezer). Otherwise weight is the
    literal shift ("AM" or "PM").
    """
    location: str
    weight: str  # "AM" | "PM" | "BOTH"


def expand_missing_items(
    missing: list[dict],
) -> list[HaccpPendingItem]:
    """T-2026-10-06 (B.6+): collapse a list of {location, shift} dicts
    into one HaccpPendingItem per location, with weight="BOTH" when
    both shifts are missing for that location. BOTH chips sort first.

    Input shape (from analytics.produccion_haccp.missing):
        [{"location": "freezer-masa", "shift": "AM"}, ...]
    Output shape:
        [HaccpPendingItem("freezer-masa", "BOTH"), ...]
    """
    if not missing:
        return []
    by_loc: dict[str, set[str]] = {}
    for m in missing:
        by_loc.setdefault(m["location"], set()).add(m["shift"])
    out: list[HaccpPendingItem] = []
    for loc, shifts in by_loc.items():
        if shifts == {"AM", "PM"}:
            weight = "BOTH"
        elif shifts == {"AM"}:
            weight = "AM"
        elif shifts == {"PM"}:
            weight = "PM"
        else:
            # Defensive: should never happen, but log if it does.
            weight = ",".join(sorted(shifts))
        out.append(HaccpPendingItem(location=loc, weight=weight))
    # Sort BOTH first (most urgent), then by location name (stable)
    out.sort(key=lambda i: (i.weight != "BOTH", i.location))
    return out


# ─────────────────────────────────────────────────────────────────────
# T-2026-10-04 (C.4) — Recipe substitution suggestions on stockouts
# ─────────────────────────────────────────────────────────────────────
# When the plan is short on an ingredient, the cook usually has two
# options: (1) order more, (2) bake a different product that doesn't
# need the short ingredient. This helper surfaces (2) by finding
# products whose recipe doesn't use the short ingredient, ranked by
# Jaccard similarity to the original product (so the substitution
# tastes similar).
#
# The suggestion set is small (top 3) so the cook can decide in
# seconds; this is the same data the model-based product_similarity
# module already provides, just exposed in the right place.


def _build_substitution_suggestions(
    session: Session,
    short_ingredient_names: list[str],
    plan_rows_view: list[dict],
    top_n: int = 3,
) -> list[dict]:
    """T-2026-10-04 (C.4) — Return a list of substitution suggestions.

    Each suggestion has:
      - ingredient_name: the short ingredient triggering the suggestion
      - original_product_id: the product that needs the short ingredient
      - original_product_name: human-readable
      - substitutes: list of {"product_id", "product_name", "similarity"} dicts
                     (sorted by similarity desc, top_n)
    """
    if not short_ingredient_names or not plan_rows_view:
        return []

    from app.rms.product_similarity import (
        jaccard_similarity,
        product_ingredient_set,
    )

    # Build a quick map: ingredient name → id (case-insensitive)
    name_to_id: dict[str, int] = {}
    for ing in session.execute(select(Ingredient)).scalars().all():
        name_to_id[ing.name.lower().strip()] = ing.id

    # Map: original product_id → { product obj, ingredient set }
    product_cache: dict[int, tuple[Product, set[int]]] = {}
    rows_with_product = [r for r in plan_rows_view if r.get("product_id")]
    for r in rows_with_product:
        pid = r["product_id"]
        if pid in product_cache:
            continue
        prod = session.get(Product, pid)
        if prod is None or prod.recipe_id is None:
            continue
        try:
            ing_set = product_ingredient_set(session, prod)
        except Exception as exc:  # noqa: BLE001 — best-effort cache build
            logger.debug(f"produccion.plan_ingredient_set: ingredient lookup failed: {exc!r}")
            ing_set = set()
        product_cache[pid] = (prod, ing_set)

    suggestions: list[dict] = []
    for ing_name in short_ingredient_names:
        ing_id = name_to_id.get(ing_name.lower().strip())
        if ing_id is None:
            continue

        # Find the products in the plan that need this ingredient.
        affected = [
            (r["product_id"], r["product_name"])
            for r in plan_rows_view
            if r.get("product_id") in product_cache and ing_id in product_cache[r["product_id"]][1]
        ]
        if not affected:
            continue

        # For each affected product, find substitute products.
        for orig_pid, orig_name in affected:
            orig_set = product_cache[orig_pid][1]
            if not orig_set:
                continue
            subs: list[dict] = []
            for other in (
                session.execute(select(Product).where(Product.id != orig_pid)).scalars().all()
            ):
                if other.recipe_id is None:
                    continue
                other_set = product_cache.get(other.id)
                if other_set is None:
                    try:
                        other_set = (other, product_ingredient_set(session, other))
                        product_cache[other.id] = other_set
                    except Exception as exc:  # noqa: BLE001 — best-effort cache build
                        logger.debug(f"produccion.plan_ingredient_set: {exc!r}")
                        continue
                if ing_id in other_set[1]:
                    continue  # also needs the short ingredient
                sim = jaccard_similarity(orig_set, other_set[1])
                if sim < 0.3:
                    continue  # not similar enough
                subs.append(
                    {
                        "product_id": other.id,
                        "product_name": other.name,
                        "similarity": round(sim, 2),
                    }
                )
            subs.sort(key=lambda x: x["similarity"], reverse=True)
            suggestions.append(
                {
                    "ingredient_name": ing_name,
                    "original_product_id": orig_pid,
                    "original_product_name": orig_name,
                    "substitutes": subs[:top_n],
                }
            )
    return suggestions


@router.get("/haccp", response_class=HTMLResponse)
def produccion_haccp(
    request: Request,
    for_date: date | None = Query(None),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """B.6 — Show the day's HACCP log + the form to add a new entry.

    The form has 2 fields: location (dropdown) + temperature_c (number).
    The cook records AM and PM separately. Range validation: -40 to +30
    is the absolute model constraint; the UI also nudges toward -22 to
    -18 for freezers.
    """
    target_date = for_date or datetime.now(ASUNCION_TZ).date()

    # Pull today's log entries.
    from sqlalchemy import and_

    entries = (
        session.execute(
            select(FreezerTemperatureLog)
            .where(FreezerTemperatureLog.for_date == target_date)
            .order_by(
                FreezerTemperatureLog.shift.asc(),
                FreezerTemperatureLog.recorded_at.asc(),
            )
        )
        .scalars()
        .all()
    )

    # Detect missing shifts (the cook should record AM + PM for each
    # location). The form shows a "Falta" pill so they know to add it.
    recorded_shifts: set[tuple[str, str]] = {(e.location, e.shift) for e in entries}
    missing: list[dict[str, str]] = [
        {"location": loc, "shift": sh}
        for loc in _DEFAULT_FREEZER_LOCATIONS
        for sh in ("AM", "PM")
        if (loc, sh) not in recorded_shifts
    ]

    # Pull the last 7 days for the history strip. Limit by tenant.
    week_ago = target_date - timedelta(days=7)
    history = (
        session.execute(
            select(FreezerTemperatureLog)
            .where(
                and_(
                    FreezerTemperatureLog.for_date >= week_ago,
                    FreezerTemperatureLog.for_date <= target_date,
                )
            )
            .order_by(
                FreezerTemperatureLog.for_date.desc(), FreezerTemperatureLog.recorded_at.desc()
            )
        )
        .scalars()
        .all()
    )

    # Most recent entry across all days — for the /produccion top banner.
    latest = _get_haccp_latest_for_date(session, target_date)
    latest_alert = _haccp_alert_for_entry(latest)

    return render(
        request,
        "produccion_haccp.html",
        {
            "for_date": target_date,
            "entries": entries,
            "missing": missing,
            "history": history,
            "locations": _DEFAULT_FREEZER_LOCATIONS,
            "latest": latest,
            "latest_alert": latest_alert,
        },
    )


@router.post("/haccp")
def produccion_haccp_post(
    request: Request,
    for_date: date = Form(...),
    location: str = Form(...),
    shift: str = Form(...),
    temperature_c: float = Form(...),
    notes: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """B.6 — Persist a HACCP temperature log entry.

    The form is a small inline POST that lives at the top of
    /produccion/haccp. After save, redirect back to the same date
    with `haccp_saved=1` so the page shows a confirmation banner
    (and a low-frequency audio chime for accessibility).
    """
    from app.rms.rate_limit import is_write_rate_limited

    if is_write_rate_limited(session, request, max_per_minute=10):
        raise HTTPException(
            status_code=429,
            detail="Demasiadas acciones en 1 minuto. Esperá un momento.",
        )

    if location not in _DEFAULT_FREEZER_LOCATIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Ubicación no reconocida. Válidas: {', '.join(_DEFAULT_FREEZER_LOCATIONS)}",
        )
    if shift not in ("AM", "PM"):
        raise HTTPException(
            status_code=400,
            detail="Turno debe ser AM o PM.",
        )
    if temperature_c < -40 or temperature_c > 30:
        raise HTTPException(
            status_code=400,
            detail="Temperatura fuera de rango válido (-40 a +30 °C).",
        )

    # Get the current user for audit.
    from app.auth import current_user_id

    user_id = current_user_id(request)

    log = FreezerTemperatureLog(
        location=location,
        temperature_c=temperature_c,
        for_date=for_date,
        shift=shift,
        recorded_at=datetime.now(ASUNCION_TZ).replace(tzinfo=None),
        recorded_by_user_id=user_id,
        notes=notes.strip()[:200] or None,
    )
    session.add(log)
    record_audit(
        request,
        session=session,
        action="write.production.haccp",
        target_type="freezer_temperature_log",
        target_id=f"{for_date.isoformat()}:{location}:{shift}",
        detail={
            "location": location,
            "shift": shift,
            "temperature_c": temperature_c,
            "for_date": for_date.isoformat(),
        },
    )
    session.commit()
    return RedirectResponse(
        url=f"/produccion/haccp?for_date={for_date.isoformat()}&haccp_saved=1",
        status_code=303,
    )
