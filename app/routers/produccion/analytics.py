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
    short_lines: list,  # list of ProductionLine (ingredient_id, ingredient_name, unit, qty_required, stock_on_hand, qty_to_buy)
    plan_rows_view: list[dict],
    top_n: int = 3,
    similarity_min: float = 0.3,
) -> list[dict]:
    """T-2026-10-04 (C.4) + 2026-10-07 (P37) — Operator-friendly substitution suggestions.

    For every ingredient the plan is short on, group the affected recipes and
    surface alternative products the cook can bake INSTEAD. The substitutes are
    only useful if the substitute's OWN ingredients are actually in stock —
    suggesting a recipe that needs 5 other things you don't have is noise. So
    we cross-check each candidate against the current stock.

    Output shape (grouped by short ingredient, not by recipe):
      {
        "ingredient_id": int,
        "ingredient_name": str,
        "unit": str,
        "shortage_qty": float,        # total qty missing across the plan
        "shortage_recipes": [str],    # human names of the affected recipes
        "n_recipes": int,
        "substitutes": [
            {
                "product_id": int,
                "product_name": str,
                "similarity": float,           # Jaccard of ingredient sets
                "own_ingredients_ok": bool,    # can we actually bake this?
                "own_short_ingredients": [str],# names of ingredients this sub needs but we're short on
            }
        ],
      }

    Sorted by shortage_qty desc (biggest problem first).
    """
    if not short_lines or not plan_rows_view:
        return []

    from app.rms.product_similarity import (
        jaccard_similarity,
        product_ingredient_set,
    )
    from app.rms.variants import rollup_ingredient_stock

    # Build a quick map: ingredient name → id (case-insensitive)
    name_to_id: dict[str, int] = {}
    for ing in session.execute(select(Ingredient)).scalars().all():
        name_to_id[ing.name.lower().strip()] = ing.id

    # Cache of variant-bearing ingredients with their rollup, so we can
    # verify a substitute's own ingredients are actually in stock.
    stock_by_ingredient: dict[int, float] = {}
    stock_unit_by_ingredient: dict[int, str] = {}
    for ing in session.execute(select(Ingredient)).scalars().all():
        stock_unit_by_ingredient[ing.id] = ing.unit
        # Try the rollup first (variants-aware), fall back to legacy column.
        try:
            rollup = rollup_ingredient_stock(session, ing.id)
            stock_by_ingredient[ing.id] = rollup.base_qty if rollup else float(ing.stock_qty or 0)
        except Exception:
            stock_by_ingredient[ing.id] = float(ing.stock_qty or 0)

    # Build plan-demand map: ingredient_id → total qty_required in the plan
    # (used to know whether a substitute's own ingredients are "in stock for
    # the plan" not just "in stock at rest").
    plan_demand: dict[int, float] = {}
    for ln in short_lines:
        plan_demand[ln.ingredient_id] = plan_demand.get(ln.ingredient_id, 0.0) + ln.qty_required

    # Map: product_id → (Product, ingredient_set with qty map)
    # We need qty per ingredient so we can scale the recipe to a target
    # production qty and verify availability.
    product_cache: dict[int, tuple[Product, list[tuple[int, str, float]]]] = {}
    for r in plan_rows_view:
        pid = r.get("product_id")
        if not pid or pid in product_cache:
            continue
        prod = session.get(Product, pid)
        if prod is None or prod.recipe_id is None:
            continue
        try:
            ing_set = product_ingredient_set(session, prod)
        except Exception as exc:  # noqa: BLE001 — best-effort cache build
            logger.debug(f"produccion.substitutions: ingredient lookup failed: {exc!r}")
            ing_set = set()
        # Get qty per ingredient for this recipe
        qty_map: list[tuple[int, str, float]] = []
        for ing_id in ing_set:
            line = session.execute(
                select(RecipeLine).where(
                    RecipeLine.recipe_id == prod.recipe_id,
                    RecipeLine.line_kind == "ingredient",
                    RecipeLine.line_ref_id == ing_id,
                )
            ).scalar_one_or_none()
            if line is not None:
                qty_map.append((ing_id, line.line_unit, float(line.qty or 0)))
        product_cache[pid] = (prod, qty_map)

    # For each short ingredient, build one suggestion group
    short_by_id: dict[int, list] = {}
    for ln in short_lines:
        short_by_id.setdefault(ln.ingredient_id, []).append(ln)

    suggestions: list[dict] = []
    for ing_id, lines in short_by_id.items():
        # Find the human ingredient_name (use the first line's name)
        ing_name = lines[0].ingredient_name
        ing_unit = lines[0].unit
        total_shortage = sum(max(0, ln.qty_required - ln.stock_on_hand) for ln in lines)

        # Recipes in the plan that need this ingredient
        affected_recipes = sorted({
            r["product_name"]
            for r in plan_rows_view
            if r.get("product_id") in product_cache
            and ing_id in {iid for iid, _, _ in product_cache[r["product_id"]][1]}
        })

        # Find substitute products — other products in the catalogue whose
        # recipes DO NOT need this short ingredient, ranked by Jaccard.
        # Skip products that need a different short ingredient too (we'd
        # just be trading one problem for another).
        other_short_ing_ids = {iid for iid in short_by_id if iid != ing_id}

        candidate_subs: list[dict] = []
        for other in session.execute(select(Product)).scalars().all():
            if other.id in product_cache:
                other_qty_map = product_cache[other.id][1]
            else:
                if other.recipe_id is None:
                    continue
                try:
                    ing_set = product_ingredient_set(session, other)
                except Exception:
                    continue
                other_qty_map = []
                for oid in ing_set:
                    line = session.execute(
                        select(RecipeLine).where(
                            RecipeLine.recipe_id == other.recipe_id,
                            RecipeLine.line_kind == "ingredient",
                            RecipeLine.line_ref_id == oid,
                        )
                    ).scalar_one_or_none()
                    if line is not None:
                        other_qty_map.append((oid, line.line_unit, float(line.qty or 0)))
                product_cache[other.id] = (other, other_qty_map)
            other_set = {iid for iid, _, _ in other_qty_map}
            # Skip if this recipe also needs the short ingredient
            if ing_id in other_set:
                continue
            # Skip if this recipe needs ANOTHER short ingredient (the plan
            # is already broken in that direction; substituting won't help)
            if other_set & other_short_ing_ids:
                continue

            # Compute Jaccard vs one of the affected original products
            # (use the first affected for tie-breaking).
            orig_pid = next(
                (r["product_id"] for r in plan_rows_view
                 if r.get("product_id") in product_cache
                 and ing_id in {iid for iid, _, _ in product_cache[r["product_id"]][1]}),
                None,
            )
            if orig_pid is None:
                continue
            orig_set = {iid for iid, _, _ in product_cache[orig_pid][1]}
            sim = jaccard_similarity(orig_set, other_set)
            if sim < similarity_min:
                continue

            # Verify the substitute's own ingredients are stocked
            # (in stock at rest, ignoring plan demand — the operator might
            # bake only the substitute, not the original).
            own_short: list[str] = []
            for sub_ing_id, sub_unit, sub_qty in other_qty_map:
                have = stock_by_ingredient.get(sub_ing_id, 0.0)
                if have < sub_qty:
                    ing_obj = session.get(Ingredient, sub_ing_id)
                    name = ing_obj.name if ing_obj else f"#{sub_ing_id}"
                    own_short.append(name)
            candidate_subs.append({
                "product_id": other.id,
                "product_name": other.name,
                "similarity": round(sim, 2),
                "own_ingredients_ok": len(own_short) == 0,
                "own_short_ingredients": own_short[:3],  # cap to 3 names
            })

        # Sort: feasible substitutes (own ingredients OK) first, then by sim
        candidate_subs.sort(
            key=lambda s: (not s["own_ingredients_ok"], -s["similarity"])
        )

        suggestions.append({
            "ingredient_id": ing_id,
            "ingredient_name": ing_name,
            "unit": ing_unit,
            "shortage_qty": round(total_shortage, 3),
            "shortage_recipes": affected_recipes[:8],  # cap display
            "n_recipes": len(affected_recipes),
            "substitutes": candidate_subs[:top_n],
        })

    # Sort suggestions: biggest shortage first
    suggestions.sort(key=lambda s: -s["shortage_qty"])
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
