# Phase-2B refactor post-mortem + redo plan

**Date:** 2026-09-24
**Status:** main rescued (a8cb7a5); domain-package redo pending

## What happened

The Phase-2B "domain-driven model architecture" refactor (fb57f00) was merged
to main **without the test suite passing — or being run**. Main was broken on
arrival:

1. `app/rms/db.py`: the MIGRATIONS registry was spliced *inside*
   `_migration_005_customer`'s docstring → SyntaxError; the app could not
   even import. Entry 43 was lost. `_bump_schema_version`'s docstring had
   stray-quote corruption.
2. `app/rms/models/` (the new package): tables renamed to PascalCase
   (`__tablename__ = "Sale"`, `"Customer"`, `"Product"`) while every FK in
   the rest of the app (and the live database) uses lowercase → every
   relationship broken (`NoReferencedTableError`).
3. 12 model classes were dropped entirely (Category, PaymentMethod,
   StorageType, StorageKeyword, DateRangePreset, MarginTier,
   MessageTemplate, StockStatusConfig, ...) — all the Phase 1-11
   static-content-audit tables that routers import.
4. `sale_stock_move` was rewritten with a wrong schema (string sale_id,
   product_id, quantity instead of ingredient_id, qty_delta,
   affected_recipe_id).
5. `IngredientVariant` was lost.

## The rescue (a8cb7a5)

- db.py migration registry rebuilt: all 54 migrations, contiguous.
- `app/rms/models/__init__.py` now re-exports the last known-good
  monolith (`app/rms/models_legacy.py`, from b9b5288) plus the 4 new
  tag-algebra columns.
- The broken domain submodules remain on disk (`app/rms/models/sales/`
  etc.) for a proper redo.
- Suite after rescue: 2207 passed, 0 failed.

## Rules going forward

1. **The merge gate is `uv run pytest` green.** No exceptions, including
   "structural-only" refactors — especially structural refactors.
2. Renaming `__tablename__` is a **database migration**, not a code-style
   change. The live SQLite DB and every FK string must move together.
3. Dropping a model class drops its table from `create_all` — grep imports
   before deleting (`grep -rn "from app.rms.models import" app/`).
4. Refactor in slices that keep the suite green at every commit, or work
   on a branch with CI.

## Redo plan (when picked up)

1. Keep `models_legacy.py` as the seed. Create ONE domain module at a time,
   moving classes verbatim (same `__tablename__`, same columns), deleting
   them from legacy as they move. Run the suite between every module.
2. Order: `inventory` → `sales` → `orders` → `production` → `procurement`
   → `auth` → `herbus_drive` → catalogs.
3. Only after all classes live in domain modules: flip `__init__.py` to
   import from the package, delete legacy. Suite green = done.
4. Do NOT rename tables in this pass. A separate, deliberate migration
   (055+) can standardize names later if wanted.
