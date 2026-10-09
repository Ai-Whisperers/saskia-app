"""app/routers/produccion/_helpers.py — Pure helpers + constants for /produccion.

Sazon-Improvement v2 (2026-10-06) Phase E: extracted from
app/routers/produccion/_full.py. These are pure functions + module-level
constants used by every other module in the produccion package. No
router dependencies, no DB writes — easy to unit test and safe to
import anywhere.

Conventions:
- Public re-exports live in __init__.py so existing
  `from app.routers.produccion import source_to_bucket` still works.
- Constants are namespaced with the helper that uses them most.
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from loguru import logger
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.rms.production import plan_production

# ──────────────────────────────────────────────────────────────────
#  Constants
# ──────────────────────────────────────────────────────────────────

# Spanish labels for each granular forecast_source. The /produccion UI
# uses these in the "Fuente" column (before the PRODUCCION-V3 Phase 2
# design that collapsed them into 4 buckets).
FORECAST_SOURCE_LABELS = {
    "rolling_14d_avg": "Sugerido por ventas",
    "oculto": "Oculto (sin auto-sugerencia)",
    "seasonal_event": "Sugerido por evento",
    "manual": "Manual",
    "template": "Plan semanal",  # PRO-01
    "override": "Ajuste del día",  # PRO-01
}

# PRODUCCION-V3 Phase 2: 4 source buckets per the design spec.
# Each granular `forecast_source` rolls up into one of these. The
# UI shows a single colored badge + a 4-row legend below the table.
SOURCE_BUCKETS = {
    # Order matters — it defines the legend order top-to-bottom.
    "receta": "Sugerido por receta / plantilla",
    "historial": "Calculado de las últimas ventas",
    "override": "Ajuste manual del panadero",
    "horneado-extra": "Horneado extra (no estaba en el plan)",
}

# PRODUCCION-V3 Phase 2: 5-band confidence explanation.
# Each band: (Spanish name, copy in the modal, CSS modifier class).
# The pill on the row is replaced with a `?` help link that opens
# the modal — the modal explains what the bands mean.
CONFIDENCE_BANDS = [
    ("Muy baja", "0–24% · muy pocos días con datos — revisá y ajustá manualmente", "conf-vlow"),
    ("Baja", "25–49% · algunos datos, pero la sugerencia es tentativa", "conf-low"),
    ("Media", "50–69% · datos suficientes, pero conviene revisar antes de hornear", "conf-med"),
    ("Alta", "70–84% · buenas ventas y muchos días de datos — usá como base", "conf-high"),
    (
        "Muy alta",
        "85–100% · dato muy sólido — la sugerencia refleja lo que vas a vender",
        "conf-vhigh",
    ),
]
FORECAST_SOURCE_HELP = {
    "rolling_14d_avg": "Calculado del promedio de ventas de los últimos 14 días",
    "seasonal_event": "Ajustado por evento estacional en la fecha",
    "manual": "Cantidad cargada a mano",
    "template": "Viene del plan semanal (se repite cada semana)",
    "override": "Anulado solo para esta fecha; no afecta otras semanas",
}

# Default bake start time for Asunción panaderías (per the QA Hats playbook):
# most local bakeries start the first shift at 06:00. Recipes with bulk
# fermentation need to be started N hours before that — surfaced as a
# reminder so the cook can decide when to start the ferment.
DEFAULT_BAKE_START_HOUR = 6  # 06:00


# ──────────────────────────────────────────────────────────────────
#  Pure helpers
# ──────────────────────────────────────────────────────────────────


def source_to_bucket(forecast_source: str | None, is_ad_hoc: bool = False) -> str:
    """Map a row's forecast_source to one of the 4 design buckets.

    `is_ad_hoc=True` always wins (it's a manual addition outside the
    plan). Unknown sources fall back to `historial` (auto-suggested).
    """
    if is_ad_hoc:
        return "horneado-extra"
    if forecast_source == "override":
        return "override"
    if forecast_source in ("template", "manual", "seasonal_event"):
        return "receta"
    # rolling_14d_avg and any unknown value → historial
    return "historial"


def _asuncion_today() -> date:
    """Today's date in America/Asuncion TZ (DST-aware via IANA zone)."""
    return datetime.now(ZoneInfo("America/Asuncion")).date()


def _batch_surplus(qty_demand: float, yield_qty: float) -> dict[str, float]:
    """T-2026-10-05 (B.9) — Estimate the unsold surplus when baking batches.

    A recipe with yield_qty=12 produces a batch of 12 portions. If the
    cook needs 10 portions, they must still bake a full batch — leaving
    2 unsold at close. The model-based scheduler doesn't catch this
    because it just sums daily demand.

    Returns:
      - batches: int — number of batches required to cover demand (ceil)
      - baked_qty: float — total units actually produced (batches * yield)
      - surplus_qty: float — leftover units (baked - demand); 0 if exact-fit
      - surplus_pct: float — surplus / demand × 100; 0 if exact-fit

    Saved ~150-300k Gs/mes when >3 batches/turn are over-baked. The
    cook can then decide to lower the forecast, promo at close, or
    swap to a smaller-batch recipe.
    """
    if qty_demand <= 0 or yield_qty <= 0:
        return {"batches": 0, "baked_qty": 0.0, "surplus_qty": 0.0, "surplus_pct": 0.0}
    batches = math.ceil(qty_demand / yield_qty)
    baked_qty = float(batches * yield_qty)
    surplus = max(0.0, baked_qty - qty_demand)
    surplus_pct = (surplus / qty_demand * 100.0) if qty_demand > 0 else 0.0
    return {
        "batches": batches,
        "baked_qty": baked_qty,
        "surplus_qty": round(surplus, 2),
        "surplus_pct": round(surplus_pct, 1),
    }


def _fermentation_reminder(
    fermentation_minutes: int | None,
    bake_start_hour: int = DEFAULT_BAKE_START_HOUR,
) -> dict | None:
    """T-2026-10-05 (B.3) — Compute when to START a recipe's bulk ferment so it
    finishes at the typical 06:00 bake start.

    Returns None when fermentation_minutes is null/0 (no ferment step).

    Returns a dict with:
      - fermentation_minutes: int (echo)
      - fermentation_hours: float (rounded to 1 decimal)
      - start_at: ISO string (start datetime in America/Asuncion TZ)
      - start_label: human-readable "HH:MM DD/MM" string in es-PY locale
      - ready_label: "HH:MM DD/MM" of when ferment completes (matches bake_start)
      - days_before: int — 0 if ferment fits same day, 1 if it crosses midnight

    Saved ~150k Gs/mes (1 salvaged batch that wasn't forgotten overnight).
    """
    if not fermentation_minutes or fermentation_minutes <= 0:
        return None

    asuncion_now = datetime.now(ZoneInfo("America/Asuncion"))
    bake_start = asuncion_now.replace(hour=bake_start_hour, minute=0, second=0, microsecond=0)
    # The ferment must FINISH at bake_start. So START = bake_start - N minutes.
    start_at = bake_start - timedelta(minutes=fermentation_minutes)
    days_before = (bake_start.date() - start_at.date()).days

    fmt = "%H:%M %d/%m"
    return {
        "fermentation_minutes": fermentation_minutes,
        "fermentation_hours": round(fermentation_minutes / 60.0, 1),
        "start_at": start_at.isoformat(),
        "start_label": start_at.strftime(fmt),
        "ready_label": bake_start.strftime(fmt),
        "days_before": days_before,
    }


def _week_monday(any_date: date) -> date:
    return any_date - timedelta(days=any_date.weekday())


def _day_counts(session: Session, days: list[date]) -> dict[str, int]:
    """item_count per day: number of products with qty>0 in that day's plan."""
    counts: dict[str, int] = {}
    for d in days:
        plan = plan_production(session, for_date=d)
        counts[d.isoformat()] = len([r for r in plan.rows if r.qty_to_produce > 0])
    return counts


def _parse_overrides(params: object) -> dict[int, float]:
    """Override params look like ov_12=10.5 -> {12: 10.5}."""
    out: dict[int, float] = {}
    for key, value in params.items():
        if key.startswith("ov_"):
            try:
                out[int(key[3:])] = float(value)
            except (TypeError, ValueError):
                continue
    return out


def _confidence_band_for_pct(pct: int | float | None) -> str:
    """Map a 0-100 confidence percentage to a 5-band CSS modifier.

    Matches the CONFIDENCE_BANDS table in this module (used by the
    modal in the template). 0 / None → conf-vlow (the cook should
    define a quantity manually).
    """
    if pct is None or pct <= 0:
        return "conf-vlow"
    if pct < 25:
        return "conf-vlow"
    if pct < 50:
        return "conf-low"
    if pct < 70:
        return "conf-med"
    if pct < 85:
        return "conf-high"
    return "conf-vhigh"


def _current_user_display_name(request: Request) -> str:
    """Return the cook's display name for print headers + audit footers.

    Looks up the username stored in the session by `login_user_local`
    (bcrypt backend) or `login_user_supabase` (Supabase backend). Falls
    back to "Cocina" when no user is logged in (test/auth-disabled
    paths) so the print header still has a sensible label.

    T-2026-10-04 (D.4): introduced for the print-pack header so the
    operator can verify which cook took which day at a glance.
    """
    # Bcrypt backend
    from app.auth import LOCAL_SESSION_KEY_USERNAME

    username = request.session.get(LOCAL_SESSION_KEY_USERNAME)
    if username:
        return str(username)
    # Supabase backend — read email from claims
    try:
        from app.auth_supabase import get_session_user

        user = get_session_user(request)
        if user is not None and getattr(user, "email", None):
            return str(user.email).split("@", 1)[0]
    except Exception as exc:
        logger.debug(f"produccion.user_short: Supabase lookup failed: {exc!r}")
    return "Cocina"
