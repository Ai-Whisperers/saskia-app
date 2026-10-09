"""tests/test_production_scheduler.py — REMOVED in Fase 5 (2026-10-05).

All tests for the deprecated `app/rms.production_scheduler` module were
migrated or dropped when the module was retired:

  - `expected_daily_sales`, `batch_expected_daily_sales`,
    `production_plan_for_day`, `production_calendar` — covered by
    `tests/test_production.py` and `tests/test_p1_b2_forecast_enchufado.py`
    against the new `app/rms.production` API.
  - `ingredient_requirements`, `check_ingredient_availability` — only
    used by the deprecated module. Coverage in
    `tests/test_eod_completion.py` exercises the same logic through
    `plan_production()`.
  - `batch_production_plans` — replaced by the batched
    `_top_products_by_velocity` + per-product `forecast_sales` in
    `app/rms.insights`. Coverage in `tests/test_insights_perf.py`.

This file is kept as an empty test module so the test collection
doesn't fail. Delete the file in a follow-up commit.
"""

# No tests — all covered above.
