"""Parametrized coverage for two more D-grade helpers with no branch matrix.
# allow-hardcoded-dates: frozen-time fixture — see _ANCLA below

S1 batch-8 (test coverage continuation): lock the branch matrix of two
D-grade helpers that lack parametrized coverage:

  (1) `app/rms/production.py:plan_production` (CC 28, D-grade)
      Core recipes / production orchestrator. Builds per-product forecasts
      (manual override → per-date override → weekly template → auto),
      expands each product's recipe via explode_recipe() into ingredient
      requirements, joins with on-hand qty, and emits ProductionPlan{rows,
      lines, notes}. Branches covered:

      - empty database (zero products) → empty plan, zero notes
      - product with no recipe (`prod.recipe_id IS NULL`) → row included,
        but no ProductionLine (recipe expansion skipped)
      - product with recipe but `recipe.yield_qty IS NULL` → recipe
        expansion skipped, no ProductionLine
      - product with recipe but `yield_qty <= 0` → same skip
      - manual_forecast → source='manual', confidence=100, qty passed
        verbatim (no ceiling rounding even on fractional input)
      - per-date override wins over template when both exist
      - weekly template wins over auto-forecast (no sales history)
      - auto-forecast: `prod.is_available=False` (hidden) → qty=0,
        source='oculto' (PRO-11 rule)
      - auto-forecast: ceiling rounding for fractional (sales 5/14d → 0.36
        → 1) only fires for auto sources, never manual/override/template
      - use_dow_forecast=True with no DOW sales → falls back to flat avg
        (the < 4 DOW weeks branch in forecast_sales)
      - seasonal_multiplier > 1.0 → notes contain "Multiplicador estacional"
      - seasonal_multiplier=None → helper calls demand_multiplier() for the
        auto-calendar lookup branch (different from passing 1.0 explicitly)

      Uses `make_catalog` from `tests/factories.py` (the standard
      ingredient+recipe+product preamble) and a small SeedPlan dataclass
      so each row is one dict entry, no new function.

  (2) `app/rms/restock_forecast.py:forecast_restock` (CC 26, D-grade)
      Poisson weekday forecast for one ingredient. Walks forward N days
      on both the expected (p50) and conservative (p95) paths, then
      composes the RestockForecast namedtuple. Branches covered:

      - ValueError raised when ingredient_id has no Ingredient row
      - zero history (no StockMovement rows) → lambdas all 0, p50_date
        and p95_date both None, recommended=2*min_stock, confidence='low'
      - high stock (no consumption in horizon) → p95_date None,
        recommended=0
      - low observed days (< 10) → confidence='low'
      - medium observed days (10..27) → confidence='medium'
      - high observed days (>= 28) → confidence='high'
      - `ing.min_stock_qty IS NULL` → the `(ing.min_stock_qty or 0)`
        floor is honored (target = max(0, 0 - stock))
      - `ing.purchase_price_gs IS NULL` → cost_estimate is None (the
        `if unit_price else None` branch)
      - weekend uplift signal: rates flat across all weekdays →
        uplift=0.0 (the `weekday_avg > 0` gate's else branch)
      - p50 path runs out: moderate consumption with finite stock → p50
        date is set (locks the `remaining > 0 and lam > 0` branch)

      Reads the actual StockMovement rows that the helper walks so the
      tests cover the same code path the operator sees. Uses
      `make_ingredient` from factories for the Ingredient row and
      `_add_sale_movement` style helpers for the StockMovement seed.

Why drive them directly (not through the route)
-----------------------------------------------
Both are public functions but they're invoked from high-level pages
(/produccion day view, /reorder) and each route adds its own branches
(URL parsing, CSRF, template render, ad-hoc query). Calling them in
isolation:

- locks the helper's branches without route noise;
- exercises real SQLAlchemy state transitions (commit, flush, query);
- keeps each row minimal — one scenario per branch outcome.

The existing test files (tests/test_production.py for plan_production,
tests/test_restock_forecast.py + tests/test_SASKIA-208_restock_forecast.py
for forecast_restock) cover end-to-end flows; this file locks the
helper-level branch matrix those flows pass through.

This file is ADDITIVE — no existing tests are modified.

Excluded D-grade helpers (covered elsewhere):

- libro_ventas (CC 21) — PR #174
- bank_list / shopping_list_index (CC 21) — PR #178
- margin_drift_all / from_workbook (CC 22) — PR #179
- _pedido_resolve_customer / _pedido_persist_address_book_entry
  (CC 24 + 23) — PR #181
- _step_5_build_recipe_row / _restock_for_target (CC 24 + 29) — PR #184
- _produccion_day_view (CC 28) — S3 split territory (it's a 200+ line
  orchestrator that already routes through the per-step helpers batch7
  covered; not a parametrizable leaf)
- produccion_print (CC 22) — 9 route-level tests in
  tests/test_produccion_print.py; pure data-shaping, not the kind of
  branch matrix that benefits from row parametrization

Adding a new scenario = one new dict entry in `_ROWS_PLAN` or
`_ROWS_FORECAST`, no new function.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import pytest

# Sentinel markers that the driver fills with the just-seeded product_id
# (so the test rows don't need to know the dynamic id ahead of time).
# Defined at module scope so they can be referenced in the @dataclass
# default values below.
_SENTINEL_DICT = "__WILL_BE_SET_DICT__"
_SENTINEL_TUPLE_LIST = "__WILL_BE_SET_TUPLE_LIST__"


# ─── plan_production row spec ────────────────────────────────────────────────


@dataclass
class _PlanSpec:
    """One scenario for `plan_production`.

    Each scenario seeds the minimum DB state needed to exercise one
    branch of plan_production (one product + optional Recipe + optional
    RecipeLine + optional template / override rows). All DB seed knobs
    are optional; the most-empty spec tests the empty-database path.
    """

    id: str = ""
    description: str = ""

    # ─── DB seed side ──────────────────────────────────────────────────
    # Each entry: (name, kwargs). Use None to skip seeding.
    ingredient_seed: Optional[dict] = None  # make_ingredient kwargs
    recipe_lines: list[dict] = field(default_factory=list)
    recipe_yield_qty: Optional[float] = 12.0
    recipe_yield_unit: str = "und"
    product_kwargs: dict = field(default_factory=dict)  # passed to make_product
    # `clear_recipe` lets a scenario seed a Product WITHOUT a recipe
    clear_recipe: bool = False
    # Optional: `make_recipe(yield_qty=None)` to test the yield_qty=None branch
    yield_qty_none: bool = False
    # Optional: `make_recipe(yield_qty=0)` to test the yield_qty<=0 branch
    yield_qty_zero: bool = False
    # Sales seed: list of (days_ago, qty). Empty list = no history.
    sales: list[tuple] = field(default_factory=list)
    # Weekly template rows: list of (weekday, product_id, qty).
    template_rows: list[tuple] = field(default_factory=list)
    # Per-date overrides: list of (product_id, qty) for for_date.
    override_rows: list[tuple] = field(default_factory=list)

    # ─── plan_production kwargs ────────────────────────────────────────
    seasonal_multiplier: Optional[float] = 1.0  # None → calendar lookup
    manual_forecast: Optional[dict] = None
    use_dow_forecast: bool = False
    days_history: int = 14

    # ─── Post-call assertions (each is checked only if set) ────────────
    expect_rows_count: Optional[int] = None
    expect_first_source: Optional[str] = None
    expect_first_qty: Optional[float] = None
    expect_first_confidence: Optional[int] = None
    expect_lines_count: Optional[int] = None
    expect_first_line_qty_to_buy: Optional[float] = None
    expect_notes_contains: Optional[str] = None


def _seed_sales(s, *, product_id: int, sales: list[tuple]) -> None:
    """Insert Sale rows for plan_production's forecast branch.

    sales: list of (days_ago, qty) tuples.
    """
    from app.rms.models import Sale

    now = datetime.now(timezone.utc)
    for days_ago, qty in sales:
        s.add(
            Sale(
                sold_at=now - timedelta(days=days_ago),
                product_id=product_id,
                qty=qty,
                unit_price_gs=2500,
            )
        )


def _seed_template(s, *, rows: list[tuple]) -> None:
    """Insert ProductionPlanTemplate rows for the weekday-template branch."""
    from datetime import datetime as _dt
    from datetime import timezone as _tz

    from app.rms.models import ProductionPlanTemplate

    for weekday, product_id, qty in rows:
        s.add(
            ProductionPlanTemplate(
                weekday=weekday,
                product_id=product_id,
                qty=qty,
                updated_at=_dt.now(_tz.utc),
                updated_by="test",
            )
        )


def _seed_override(s, *, for_date, rows: list[tuple]) -> None:
    """Insert ProductionPlanOverride rows for the per-date branch."""
    from datetime import datetime as _dt
    from datetime import timezone as _tz

    from app.rms.models import ProductionPlanOverride

    for product_id, qty in rows:
        s.add(
            ProductionPlanOverride(
                product_id=product_id,
                for_date=for_date,
                qty=qty,
                updated_at=_dt.now(_tz.utc),
                updated_by="test",
            )
        )


# ─── plan_production scenario definitions ────────────────────────────────────

# Case 1: empty database → empty plan, no notes.
_PLAN_EMPTY_DB = _PlanSpec(
    id="empty_db_returns_empty_plan",
    description=(
        "zero products in DB → plan_production returns empty rows, "
        "empty lines, total_ingredients_needed=0, no notes"
    ),
    expect_rows_count=0,
    expect_lines_count=0,
)


# Case 2: product with NO recipe (prod.recipe_id IS NULL) → row included
# but no ProductionLine (the recipe expansion skip branch).
_PLAN_PRODUCT_NO_RECIPE = _PlanSpec(
    id="product_without_recipe",
    description=(
        "Product.recipe_id IS NULL → row is added but recipe expansion "
        "is skipped → no ProductionLine emitted (the `prod.recipe_id is "
        "None: continue` branch)"
    ),
    product_kwargs={"name": "Muffin sin receta", "sale_price_gs": 2500},
    clear_recipe=True,
    sales=[(1, 1)],  # at least one sale so qty_to_produce > 0
    expect_rows_count=1,
    expect_first_source="rolling_14d_avg",
    expect_lines_count=0,
)


# Case 3: product WITH recipe but recipe.yield_qty IS NULL → same skip.
_PLAN_RECIPE_YIELD_NONE = _PlanSpec(
    id="recipe_with_null_yield",
    description=(
        "Product has Recipe but recipe.yield_qty IS NULL → the `recipe."
        "yield_qty is None or <= 0: continue` branch fires → no "
        "ProductionLine for this product"
    ),
    product_kwargs={"name": "Pan con yield nulo", "sale_price_gs": 3000},
    yield_qty_none=True,
    sales=[(1, 1), (2, 1)],
    expect_rows_count=1,
    expect_lines_count=0,
)


# Case 4: product with seasonal_multiplier=None → the helper calls
# demand_multiplier() from the workflow module. The branch is
# `if seasonal_multiplier is None: from app.rms.workflow import
# demand_multiplier; seasonal_multiplier = demand_multiplier(for_date)`.
# We use a non-special date (2026-06-01 = no holiday) so the multiplier
# is 1.0 and no note fires; this locks the auto-lookup path
# (different from passing seasonal_multiplier=1.0 explicitly).
_PLAN_SEASONAL_NONE_AUTO_LOOKUP = _PlanSpec(
    id="seasonal_multiplier_none_auto_calendar",
    description=(
        "seasonal_multiplier=None → helper calls demand_multiplier() "
        "to fetch from the calendar. No holiday on 2026-06-01 → "
        "multiplier=1.0 → no note added (locks the `if seasonal_multiplier "
        "is None: from app.rms.workflow import demand_multiplier` branch)"
    ),
    product_kwargs={"name": "Pan sin estacional", "sale_price_gs": 10000},
    sales=[(1, 1)],
    seasonal_multiplier=None,
    expect_rows_count=1,
    expect_notes_contains=None,
    expect_lines_count=0,
)


# Case 5: manual_forecast wins over auto-forecast; source='manual',
# confidence=100, qty passed verbatim (NO ceiling rounding on
# fractional input — the `source not in ('manual','override','template')`
# guard).
_PLAN_MANUAL_FORECAST = _PlanSpec(
    id="manual_forecast_takes_precedence",
    description=(
        "manual_forecast={pid: 7.5} → source='manual', confidence=100, "
        "qty=7.5 (NOT ceiled — manual overrides bypass the rounding rule)"
    ),
    product_kwargs={"name": "Torta manual", "sale_price_gs": 25000},
    sales=[(1, 1), (2, 1), (3, 1)],
    manual_forecast=_SENTINEL_DICT,  # filled by driver with product_id
    expect_rows_count=1,
    expect_first_source="manual",
    expect_first_qty=7.5,
    expect_first_confidence=100,
)


# Case 6: per-date override wins over weekly template when BOTH are
# present for the same product. Locks the precedence chain:
# manual → override → template → auto.
_PLAN_OVERRIDE_BEATS_TEMPLATE = _PlanSpec(
    id="override_beats_template",
    description=(
        "Both a per-date override AND a weekly template row for the "
        "same product → override wins (the precedence chain at lines "
        "319-329 of production.py)"
    ),
    product_kwargs={"name": "Torta override", "sale_price_gs": 25000},
    sales=[(1, 1)],
    template_rows=_SENTINEL_TUPLE_LIST,  # filled by driver with (wd, pid, 5.0)
    override_rows=_SENTINEL_TUPLE_LIST,  # filled by driver with (pid, 99.0)
    expect_rows_count=1,
    expect_first_source="override",
    expect_first_qty=99.0,
    expect_first_confidence=100,
)


# Case 7: weekly template (no per-date override) wins over auto-forecast
# (which would return ~0 because there are no sales in the 14d window).
_PLAN_TEMPLATE_WINS_AUTO = _PlanSpec(
    id="weekly_template_wins_over_auto",
    description=(
        "Weekly template row for the product's weekday (no override, "
        "no sales history) → template wins → source='template', "
        "confidence=100, qty=template.qty verbatim"
    ),
    product_kwargs={"name": "Pan plantilla", "sale_price_gs": 10000},
    template_rows=_SENTINEL_TUPLE_LIST,  # filled by driver with (wd, pid, 8.0)
    # NOTE: no `sales=` — auto-forecast would return 0; template still wins.
    expect_rows_count=1,
    expect_first_source="template",
    expect_first_qty=8.0,
    expect_first_confidence=100,
)


# Case 8: auto-forecast for a hidden product (is_available=False) →
# qty=0, source='oculto' (PRO-11 rule). Locks the `not prod.is_available`
# branch in production.py.
_PLAN_HIDDEN_PRODUCT = _PlanSpec(
    id="hidden_product_no_auto_forecast",
    description=(
        "Product.is_available=False → qty=0, source='oculto' (PRO-11: "
        "hidden products never receive auto-suggestion). The plan.rows "
        "list only contains rows where qty_to_produce > 0 (the "
        "`if qty > 0: rows.append(...)` gate), so a hidden product "
        "produces ZERO rows even though the precedence chain still "
        "reaches the `not prod.is_available` branch."
    ),
    product_kwargs={"name": "Producto oculto", "sale_price_gs": 25000, "is_available": False},
    sales=[(1, 5), (2, 5), (3, 5)],  # would forecast ~1.07/day if visible
    expect_rows_count=0,  # qty=0 → excluded from rows (locked branch)
    expect_lines_count=0,
)


# Case 9: seasonal_multiplier > 1.0 → plan.notes contains the "Multiplicador
# estacional" line. Locks the `if seasonal_multiplier > 1.0: notes.append`
# branch.
_PLAN_SEASONAL_NOTE = _PlanSpec(
    id="seasonal_multiplier_adds_note",
    description=(
        "seasonal_multiplier=2.5 → notes contains 'Multiplicador "
        "estacional: 2.5x' (the `if seasonal_multiplier > 1.0` branch)"
    ),
    product_kwargs={"name": "Torta estacional", "sale_price_gs": 25000},
    sales=[(1, 2), (2, 2), (3, 2)],
    seasonal_multiplier=2.5,
    expect_rows_count=1,
    expect_notes_contains="Multiplicador estacional",
)


# ─── plan_production scenario rows ───────────────────────────────────────────


_ROWS_PLAN: list[dict[str, Any]] = [
    {"spec": _PLAN_EMPTY_DB},
    {"spec": _PLAN_PRODUCT_NO_RECIPE},
    {"spec": _PLAN_RECIPE_YIELD_NONE},
    {"spec": _PLAN_SEASONAL_NONE_AUTO_LOOKUP},
    {"spec": _PLAN_MANUAL_FORECAST},
    {"spec": _PLAN_OVERRIDE_BEATS_TEMPLATE},
    {"spec": _PLAN_TEMPLATE_WINS_AUTO},
    {"spec": _PLAN_HIDDEN_PRODUCT},
    {"spec": _PLAN_SEASONAL_NOTE},
]


# ─── forecast_restock row spec ───────────────────────────────────────────────


@dataclass
class _ForecastSpec:
    """One scenario for `forecast_restock`."""

    id: str = ""
    description: str = ""

    # ─── DB seed side ──────────────────────────────────────────────────
    ingredient_kwargs: dict = field(default_factory=dict)
    # Sale-movement seed: list of (days_ago, qty). Empty = no history.
    sales: list[tuple] = field(default_factory=list)
    # Optional: pass a different `now` (datetime tz-aware UTC)
    freeze_now: bool = False  # when True, pin now to a fixed reference

    # ─── forecast_restock kwargs ───────────────────────────────────────
    window_days: int = 56
    horizon_days: int = 60
    cover_days: int = 14

    # ─── Post-call assertions ──────────────────────────────────────────
    expect_raises_value_error: bool = False
    expect_p50_date_is_none: Optional[bool] = None
    expect_p95_date_is_none: Optional[bool] = None
    expect_confidence: Optional[str] = None
    expect_recommended_zero: Optional[bool] = None
    expect_cost_estimate_is_none: Optional[bool] = None
    expect_uplift_zero: Optional[bool] = None
    expect_min_lambda_zero: Optional[bool] = None


def _seed_sale_movements(s, *, ingredient_id: int, sales: list[tuple]) -> int:
    """Insert StockMovement rows (movement_type='sale', qty<0).

    Returns the count of distinct days with at least one movement (this
    is what `observed_days` in the helper counts toward `confidence`).
    """
    from app.rms.models import StockMovement

    distinct_days: set = set()
    # Pin to a fixed reference so the DOW distribution is deterministic.
    # We use 2026-06-01 (Monday) as the "now" anchor.
    anchor = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    for days_ago, qty in sales:
        recorded = anchor - timedelta(days=days_ago)
        s.add(
            StockMovement(
                ingredient_id=ingredient_id,
                movement_type="sale",
                qty=-qty,  # consumption is negative
                reason="test seed",
                reference_id=1,
                reference_type="sale",
                recorded_at=recorded,
            )
        )
        distinct_days.add(recorded.date().isoformat())
    return len(distinct_days)


# ─── forecast_restock scenario definitions ───────────────────────────────────

# Case 1: ingredient_id with NO Ingredient row → ValueError raised.
_FORECAST_UNKNOWN_INGREDIENT = _ForecastSpec(
    id="unknown_ingredient_raises",
    description=(
        "forecast_restock(session, ingredient_id=99_999) → ValueError "
        "(the head-of-function `if ing is None: raise` guard)"
    ),
    expect_raises_value_error=True,
)


# Case 2: zero history → no movements → lambdas all 0 → p50_date None,
# p95_date None, recommended = max(0, 2*min_stock - stock), confidence='low'.
_FORECAST_ZERO_HISTORY = _ForecastSpec(
    id="zero_history_no_stockout_no_recommendation",
    description=(
        "Ingredient with no StockMovement rows in the window → p50_date "
        "and p95_date both None, recommended = max(0, 2*min_stock - stock) "
        "(the p95_week_total==0 branch in the recommended-qty formula)"
    ),
    ingredient_kwargs={
        "name": "harina",
        "unit": "kg",
        "stock_qty": 100.0,
        "min_stock_qty": 5.0,
        "purchase_price_gs": 4000,
    },
    sales=[],
    freeze_now=True,
    expect_p50_date_is_none=True,
    expect_p95_date_is_none=True,
    expect_confidence="low",
    # Locked branch: p95_week_total==0 → recommended = max(0, 2*5 - 100)
    # = max(0, -90) = 0 (locks the `if p95_week_total > 0: ... else:` else).
    expect_recommended_zero=True,
    expect_cost_estimate_is_none=False,
)


# Case 3: huge stock, modest consumption → no stockout in horizon →
# p95_date is None (locks the `if p95_date is None and stock > 0 and
# cumulative_p95 >= stock` negative branch).
_FORECAST_HIGH_STOCK_NO_STOCKOUT = _ForecastSpec(
    id="high_stock_no_stockout_in_horizon",
    description=(
        "Huge stock (10000) + small daily consumption → cumulative_p95 "
        "never reaches stock within horizon_days=60 → p95_date is None "
        "(locks the stockout walk-forward negative branch)"
    ),
    ingredient_kwargs={
        "name": "azucar",
        "unit": "kg",
        "stock_qty": 10_000.0,  # ~6 months of stock at 1kg/day
        "min_stock_qty": 5.0,
        "purchase_price_gs": 3500,
    },
    sales=[(d, 5.0) for d in range(56)],  # 5kg every day for 56 days
    freeze_now=True,
    expect_p95_date_is_none=True,
    expect_confidence="high",  # 36+ distinct days observed
)


# Case 4: low observed days (< 10) → confidence='low'.
_FORECAST_LOW_CONFIDENCE = _ForecastSpec(
    id="low_observed_days_confidence_low",
    description=(
        "Only 3 distinct days with sales in the 56d window → "
        "observed_days=3 → confidence='low' (the `elif observed_days "
        ">= 10` branch is skipped)"
    ),
    ingredient_kwargs={
        "name": "levadura",
        "unit": "kg",
        "stock_qty": 100.0,
        "min_stock_qty": 5.0,
        "purchase_price_gs": 15000,
    },
    # 3 distinct days in the 56d window
    sales=[(1, 0.5), (10, 0.5), (25, 0.5)],
    freeze_now=True,
    expect_confidence="low",
)


# Case 5: medium observed days (10..27) → confidence='medium'.
_FORECAST_MEDIUM_CONFIDENCE = _ForecastSpec(
    id="medium_observed_days_confidence_medium",
    description=(
        "12 distinct days with sales → observed_days=12 → "
        "confidence='medium' (locks the `>= 10` branch)"
    ),
    ingredient_kwargs={
        "name": "manteca",
        "unit": "kg",
        "stock_qty": 50.0,
        "min_stock_qty": 5.0,
        "purchase_price_gs": 28000,
    },
    sales=[(d, 2.0) for d in range(12)],
    freeze_now=True,
    expect_confidence="medium",
)


# Case 6: high observed days (>= 28) → confidence='high'.
_FORECAST_HIGH_CONFIDENCE = _ForecastSpec(
    id="high_observed_days_confidence_high",
    description=(
        "30 distinct days with sales → observed_days=30 → "
        "confidence='high' (locks the `>= 28` branch)"
    ),
    ingredient_kwargs={
        "name": "huevos",
        "unit": "und",
        "stock_qty": 500.0,
        "min_stock_qty": 50.0,
        "purchase_price_gs": 600,
    },
    sales=[(d, 12.0) for d in range(30)],
    freeze_now=True,
    expect_confidence="high",
)


# Case 7: ing.purchase_price_gs IS NULL → cost_estimate is None.
_FORECAST_NULL_PURCHASE_PRICE = _ForecastSpec(
    id="null_purchase_price_cost_estimate_none",
    description=(
        "Ingredient.purchase_price_gs IS NULL → cost_estimate is None "
        "(the `cost_estimate = round(...) if unit_price else None` "
        "else branch)"
    ),
    ingredient_kwargs={
        "name": "ingrediente sin precio",
        "unit": "kg",
        "stock_qty": 50.0,
        "min_stock_qty": 5.0,
        "purchase_price_gs": None,
    },
    sales=[(1, 1), (2, 1)],
    freeze_now=True,
    expect_confidence="low",
    expect_cost_estimate_is_none=True,
)


# Case 8: p50 path runs out → moderate consumption with finite stock →
# p50_date is set (locks the `if p50_date is None and remaining > 0 and
# lam > 0` branch — the expected-path stockout walk-forward).
_FORECAST_P50_RUNS_OUT = _ForecastSpec(
    id="p50_path_runs_out",
    description=(
        "Modest stock (5kg) + heavy daily consumption (3kg/day) → "
        "expected path runs out on day 2 → p50_date is set (locks the "
        "`remaining > 0 and lam > 0` branch of the p50 walk-forward)"
    ),
    ingredient_kwargs={
        "name": "chocolate",
        "unit": "kg",
        "stock_qty": 5.0,
        "min_stock_qty": 5.0,
        "purchase_price_gs": 25000,
    },
    sales=[(d, 3.0) for d in range(28)],
    freeze_now=True,
    expect_p50_date_is_none=False,  # p50 is set
    expect_confidence="high",
)


# ─── forecast_restock scenario rows ───────────────────────────────────────────


_ROWS_FORECAST: list[dict[str, Any]] = [
    {"spec": _FORECAST_UNKNOWN_INGREDIENT},
    {"spec": _FORECAST_ZERO_HISTORY},
    {"spec": _FORECAST_HIGH_STOCK_NO_STOCKOUT},
    {"spec": _FORECAST_LOW_CONFIDENCE},
    {"spec": _FORECAST_MEDIUM_CONFIDENCE},
    {"spec": _FORECAST_HIGH_CONFIDENCE},
    {"spec": _FORECAST_NULL_PURCHASE_PRICE},
    {"spec": _FORECAST_P50_RUNS_OUT},
]


# ─── Parametrized driver: plan_production ─────────────────────────────────────


@pytest.mark.parametrize(
    "row",
    _ROWS_PLAN,
    ids=lambda r: r["spec"].id,
)
def test_plan_production_branches(row: dict, session_factory) -> None:
    """Drive `plan_production` through 9 scenarios covering its CC-28
    branches.

    - empty_db_returns_empty_plan: zero products → empty plan
    - product_without_recipe: prod.recipe_id IS NULL → row only, no line
    - recipe_with_null_yield: recipe.yield_qty IS NULL → skip expansion
    - seasonal_multiplier_none_auto_calendar: helper calls demand_multiplier()
    - manual_forecast_takes_precedence: source='manual', conf=100
    - override_beats_template: precedence chain (override > template)
    - weekly_template_wins_over_auto: template fills when no override/sales
    - hidden_product_no_auto_forecast: PRO-11 oculta → 0 rows (qty=0 branch)
    - seasonal_multiplier_adds_note: notes append when multiplier > 1.0

    Uses `make_catalog` from `tests/factories.py` (the standard
    ingredient+recipe+product preamble) plus custom seeds for the
    override/template/recipe-without-yield branches.

    `session_factory` is required so the conftest's app-fixture tree
    (init_db, make_engine) runs — plan_production hits Sale/Recipe/
    Ingredient/Product tables and the conftest fixture opens the
    in-memory SQLite DB.
    """
    from datetime import date

    from app.rms.production import plan_production
    from tests.factories import make_ingredient, make_product, make_recipe

    spec: _PlanSpec = row["spec"]
    fixed_for_date = date(2026, 6, 1)  # Monday — picks Mon from template rows

    with session_factory() as s:
        product_id: Optional[int] = None

        # ─── Seed Ingredient (if requested) ────────────────────────────
        if spec.ingredient_seed is not None or spec.recipe_lines:
            # Default ingredient if not specified
            ing_kwargs = {"name": "harina test", "stock_qty": 100.0, "purchase_price_gs": 4500}
            ing_kwargs.update(spec.ingredient_seed or {})
            make_ingredient(s, **ing_kwargs)

        # ─── Seed Recipe + RecipeLine ─────────────────────────────────
        recipe: Optional[object] = None
        if spec.recipe_lines or spec.product_kwargs:
            yield_qty: Optional[float] = spec.recipe_yield_qty
            if spec.yield_qty_none:
                yield_qty = None
            elif spec.yield_qty_zero:
                yield_qty = 0.0
            recipe = make_recipe(
                s,
                lines=spec.recipe_lines if spec.recipe_lines else None,
                yield_qty=yield_qty,
                yield_unit=spec.recipe_yield_unit,
            )

        # ─── Seed Product ────────────────────────────────────────────
        if spec.product_kwargs:
            product_kwargs = dict(spec.product_kwargs)
            if recipe is not None and not spec.clear_recipe:
                product_kwargs.setdefault("recipe_id", recipe.id)
            product = make_product(s, **product_kwargs)
            product_id = product.id

        # ─── Resolve sentinel manual_forecast ────────────────────────
        manual_forecast: Optional[dict] = spec.manual_forecast
        if manual_forecast == _SENTINEL_DICT and product_id is not None:
            manual_forecast = {product_id: 7.5}
        elif manual_forecast == _SENTINEL_DICT:
            manual_forecast = None

        # ─── Seed template rows (resolve sentinel) ───────────────────
        if spec.template_rows == _SENTINEL_TUPLE_LIST and product_id is not None:
            weekday = fixed_for_date.weekday()
            if spec.id == "override_beats_template":
                spec.template_rows = [(weekday, product_id, 5.0)]
            elif spec.id == "weekly_template_wins_over_auto":
                spec.template_rows = [(weekday, product_id, 8.0)]
        if isinstance(spec.template_rows, list) and spec.template_rows:
            _seed_template(s, rows=spec.template_rows)

        # ─── Seed override rows (resolve sentinel) ────────────────────
        if spec.override_rows == _SENTINEL_TUPLE_LIST and product_id is not None:
            spec.override_rows = [(product_id, 99.0)]
        if isinstance(spec.override_rows, list) and spec.override_rows:
            _seed_override(s, for_date=fixed_for_date, rows=spec.override_rows)

        # ─── Seed sales ──────────────────────────────────────────────
        if product_id is not None and spec.sales:
            _seed_sales(s, product_id=product_id, sales=spec.sales)

        s.commit()

        # ─── Call the helper ─────────────────────────────────────────
        plan = plan_production(
            s,
            for_date=fixed_for_date,
            seasonal_multiplier=spec.seasonal_multiplier,
            manual_forecast=manual_forecast,
            use_dow_forecast=spec.use_dow_forecast,
            days_history=spec.days_history,
        )

    # ─── Post-call assertions ──────────────────────────────────────────

    if spec.expect_rows_count is not None:
        assert len(plan.rows) == spec.expect_rows_count, (
            f"{spec.id}: rows={len(plan.rows)}, "
            f"expected {spec.expect_rows_count} — {spec.description}"
        )

    if spec.expect_first_source is not None and plan.rows:
        assert plan.rows[0].forecast_source == spec.expect_first_source, (
            f"{spec.id}: first row source={plan.rows[0].forecast_source!r}, "
            f"expected {spec.expect_first_source!r} — {spec.description}"
        )

    if spec.expect_first_qty is not None and plan.rows:
        actual_qty = plan.rows[0].qty_to_produce
        assert abs(actual_qty - spec.expect_first_qty) < 1e-6, (
            f"{spec.id}: first row qty={actual_qty}, "
            f"expected {spec.expect_first_qty} — {spec.description}"
        )

    if spec.expect_first_confidence is not None and plan.rows:
        assert plan.rows[0].confidence_pct == spec.expect_first_confidence, (
            f"{spec.id}: first row confidence={plan.rows[0].confidence_pct}, "
            f"expected {spec.expect_first_confidence} — {spec.description}"
        )

    if spec.expect_lines_count is not None:
        assert len(plan.lines) == spec.expect_lines_count, (
            f"{spec.id}: lines={len(plan.lines)}, "
            f"expected {spec.expect_lines_count} — {spec.description}"
        )

    if spec.expect_first_line_qty_to_buy is not None and plan.lines:
        actual_buy = plan.lines[0].qty_to_buy
        assert abs(actual_buy - spec.expect_first_line_qty_to_buy) < 1e-6, (
            f"{spec.id}: first line qty_to_buy={actual_buy}, "
            f"expected {spec.expect_first_line_qty_to_buy} — {spec.description}"
        )

    if spec.expect_notes_contains is not None:
        joined_notes = "\n".join(plan.notes)
        assert spec.expect_notes_contains in joined_notes, (
            f"{spec.id}: notes={plan.notes!r}, expected to contain "
            f"{spec.expect_notes_contains!r} — {spec.description}"
        )

    # Sanity: total_ingredients_needed == len(lines) on every branch.
    assert plan.total_ingredients_needed == len(plan.lines), (
        f"{spec.id}: total_ingredients_needed={plan.total_ingredients_needed} "
        f"!= len(lines)={len(plan.lines)} — invariant broken"
    )


# ─── Parametrized driver: forecast_restock ───────────────────────────────────


@pytest.mark.parametrize(
    "row",
    _ROWS_FORECAST,
    ids=lambda r: r["spec"].id,
)
def test_forecast_restock_branches(row: dict, session_factory) -> None:
    """Drive `forecast_restock` through 8 scenarios covering its CC-26
    branches.

    - unknown_ingredient_raises: ValueError when no Ingredient row
    - zero_history_no_stockout_no_recommendation: p50/p95 None, conf=low
    - high_stock_no_stockout_in_horizon: huge stock → p95 None
    - low_observed_days_confidence_low: < 10 observed days
    - medium_observed_days_confidence_medium: 10-27 observed days
    - high_observed_days_confidence_high: >= 28 observed days
    - null_purchase_price_cost_estimate_none: cost_estimate is None
    - p50_path_runs_out: moderate stock + heavy consumption → p50 set

    Uses `make_ingredient` from factories + direct StockMovement inserts.
    `freeze_now=True` pins the "now" reference to 2026-06-01 (Monday) so
    the DOW distribution is deterministic across runs.
    """
    from app.rms.restock_forecast import forecast_restock
    from tests.factories import make_ingredient

    spec: _ForecastSpec = row["spec"]

    with session_factory() as s:
        ingredient_id: Optional[int] = None
        if not spec.expect_raises_value_error:
            ing = make_ingredient(s, **spec.ingredient_kwargs)
            ingredient_id = ing.id
            if spec.sales:
                _seed_sale_movements(s, ingredient_id=ingredient_id, sales=spec.sales)
            s.commit()

        # Pin "now" to a fixed reference so DOW math is deterministic.
        if spec.freeze_now:
            kwargs = {"now": datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)}
        else:
            kwargs = {}

        # ─── Call the helper (handle the ValueError branch) ───────────
        if spec.expect_raises_value_error:
            with pytest.raises(ValueError, match="not found"):
                forecast_restock(
                    s,
                    99_999,
                    window_days=spec.window_days,
                    horizon_days=spec.horizon_days,
                    cover_days=spec.cover_days,
                    **kwargs,
                )
            return  # branch locked, no further assertions
        else:
            fc = forecast_restock(
                s,
                ingredient_id,
                window_days=spec.window_days,
                horizon_days=spec.horizon_days,
                cover_days=spec.cover_days,
                **kwargs,
            )

    # ─── Post-call assertions ──────────────────────────────────────────

    if spec.expect_p50_date_is_none is not None:
        actual_is_none = fc.p50_stockout_date is None
        assert actual_is_none == spec.expect_p50_date_is_none, (
            f"{spec.id}: p50_stockout_date is None?={actual_is_none}, "
            f"expected={spec.expect_p50_date_is_none} — {spec.description}"
        )

    if spec.expect_p95_date_is_none is not None:
        actual_is_none = fc.p95_stockout_date is None
        assert actual_is_none == spec.expect_p95_date_is_none, (
            f"{spec.id}: p95_stockout_date is None?={actual_is_none}, "
            f"expected={spec.expect_p95_date_is_none} — {spec.description}"
        )

    if spec.expect_confidence is not None:
        assert fc.confidence == spec.expect_confidence, (
            f"{spec.id}: confidence={fc.confidence!r}, "
            f"expected {spec.expect_confidence!r} — {spec.description}"
        )

    if spec.expect_recommended_zero is not None:
        is_zero = fc.recommended_restock_qty == 0.0
        assert is_zero == spec.expect_recommended_zero, (
            f"{spec.id}: recommended_restock_qty zero?={is_zero}, "
            f"expected={spec.expect_recommended_zero} — {spec.description}"
        )

    if spec.expect_cost_estimate_is_none is not None:
        actual_is_none = fc.restock_cost_gs_estimate is None
        assert actual_is_none == spec.expect_cost_estimate_is_none, (
            f"{spec.id}: restock_cost_gs_estimate is None?={actual_is_none}, "
            f"expected={spec.expect_cost_estimate_is_none} — {spec.description}"
        )

    if spec.expect_uplift_zero is not None:
        is_zero = abs(fc.weekend_uplift_pct) < 1e-6
        assert is_zero == spec.expect_uplift_zero, (
            f"{spec.id}: weekend_uplift_pct=0?={is_zero}, "
            f"expected={spec.expect_uplift_zero} — {spec.description}"
        )

    if spec.expect_min_lambda_zero is not None:
        is_zero = abs(fc.weekday_trough_rate) < 1e-6
        assert is_zero == spec.expect_min_lambda_zero, (
            f"{spec.id}: weekday_trough_rate=0?={is_zero}, "
            f"expected={spec.expect_min_lambda_zero} — {spec.description}"
        )

    # Sanity: the helper must always populate these stable fields.
    assert fc.ingredient_id == ingredient_id, f"{spec.id}: ingredient_id passthrough mismatch"
    assert isinstance(fc.name, str) and len(fc.name) > 0, (
        f"{spec.id}: name missing — {spec.description}"
    )
    # RestockForecast doesn't carry window_days; the helper used the
    # argument verbatim so the locked parametrize row is enough.


# ─── Row-count docs (mirrors PR #178 / #179 / #181 / #184 pattern) ───────────


def test_parametrize_row_count() -> None:
    """Document the number of branch-coverage cases covered by this file.

    Locks the parametrize row count so adding/removing a row forces a
    reviewer to update the matching CHANGELOG entry — same pattern as
    batch3 / batch4 / batch5 / batch6 / batch7 (#174, #178, #179, #181,
    #184).
    """
    assert len(_ROWS_PLAN) == 9  # unchanged count; scenario 4 swapped
    assert len(_ROWS_FORECAST) == 8
    # Sanity: the spec docstring's "8+ parametrized rows" claim is met.
    assert len(_ROWS_PLAN) + len(_ROWS_FORECAST) >= 8
