"""app/rms/production_scheduler.py — REMOVED in Fase 5 (2026-10-05).

This module was deprecated on 2026-10-05 (Fase 1 of the Producción v2
redesign). On 2026-10-05 (Fase 5) the only remaining caller
(`app/rms/insights.py`) was migrated to use `app.rms.production`'s new
helpers (`_top_products_by_velocity` + per-product `forecast_sales`).

The production code that USED to live here — `_recipe_yield`,
`batch_expected_daily_sales`, `batch_production_plans`, `production_calendar`,
`expected_daily_sales`, `production_plan_for_day`, `ingredient_requirements`,
`check_ingredient_availability`, and the dataclasses `ProductionPlan`,
`ProductionDay`, `IngredientShortage` — has been either ported to
`app/rms.production` or removed because no caller remains.

This file is kept as an empty module so any stale `import` lines
elsewhere raise `ImportError` with a clear message instead of a
cryptic "module has no attribute X". Delete the file in a follow-up
commit once a `git grep production_scheduler` shows no live imports.
"""

__all__ = []
