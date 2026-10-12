# SASKIA-224: Recipe yield backfill (16 of 23 recipes have empty B4)

**Date:** 2026-10-12
**Status:** drafted
**Author:** AIW Bot
**Estimate:** 1 day seeder default + 1 week operator backfill
**Sister tickets:** SASKIA-223 (HEREBUS data import — parent)
**Source:** HEREBUS spreadsheet, 23 Recipe_* sheets

## Why

The HEREBUS spreadsheet has 23 recipes. The "Rinde" cell (B4) — the most important data point for cost-per-portion calculation — is **empty in 16 of 23 recipes (70%)**:

Empty (no yield):
- REC-001 Chocolate Muffin
- REC-004 Ontbijtkoek
- REC-005 Carrot Cake
- REC-006 Frikandel
- REC-007 Ketjap Manis
- REC-008 Hojaldre
- REC-009 Pastelitos Rosados
- REC-010 Galletas Especuloos
- REC-011 Bizcocho 25cm
- REC-012 Bizcocho 30cm
- REC-013 Tarta de Manzana
- REC-014 Profiteroles Den Bosch
- REC-015 Petisús
- REC-016 Oliebollen
- REC-017 Babka
- REC-022 Everything Bagels

Filled (has yield):
- REC-002 Cheesecake: 170 portions
- REC-003 Stroop Waffle: 12 unidades
- REC-006b Bitterballen: 100 unidades (the lowercase variant)
- REC-018 Bombones de Chocolate: 20 unidades
- REC-019 Goulash Croquettes: 100 unidades
- REC-020 Veggie Bitterballen: 100 unidades
- REC-021 Supplì: 12 unidades

The Sazon seeder (SASKIA-223) can use a default of 1.0, but real product costing needs the actual yield. The operator (Saskia) needs to cook each recipe once and record the yield.

## What

### Part A: Seeder default (1 day, code)

In `app/rms/seed/sazon.py::_seed_recipes_from_herbus`:
- For each recipe with empty B4, set `yield_qty = 1.0` and `yield_unit = "molde"` for bizcochos or `"unidades"` for individual products
- Add a flag `yield_is_default = true` on the Recipe row (so the operator UI can show "Please verify this yield")
- Don't block the seeder; the DB can have recipes with default yields

### Part B: Operator backfill (1 week, manual)

For each of the 16 recipes:
1. Saskia cooks the recipe following HEREBUS steps
2. Counts the actual yield (e.g. 18 Stroopwafels instead of 12)
3. Updates the Sazon `/admin/recipes/<id>` page with the real yield
4. The Recipe row's `yield_qty` updates + `yield_is_default = false`
5. The cost-per-portion recomputes (since `cost_per_portion = total_cost / yield_qty`)

The Sazon app should provide:
- A "Verify yield" button on each Recipe row
- A checklist of recipes that need verification (filter `yield_is_default = true`)
- An audit log of yield changes (so the operator can see if a recipe's yield dropped over time — e.g. due to ingredient changes)

### Part C: Yield change audit (code, 1 day)

Add a `RecipeYieldHistory` table that records every yield change:
- `recipe_id` (FK)
- `old_yield_qty`, `new_yield_qty`
- `recorded_by` (user_id)
- `recorded_at` (timestamp)
- `notes` (e.g. "first batch", "after switching to harina de centeno real")

This is optional but useful for tracking quality. If the operator doesn't want it, skip Part C.

## Out of scope (deferred)

- **Recipe photos** (not in HEREBUS, operator adds via the recipe detail page)
- **Cooking time tracking** (HEREBUS doesn't track LaborMin; can be added later)
- **Recipe difficulty rating** (not in HEREBUS; can be added later)

## Risks

1. **Default yield is misleading**: if the operator (Saskia) doesn't backfill, the product prices will be wrong (cost_per_portion = total_cost / 1 = total_cost). For bizcochos, this means a 25cm cake shows as 1 portion = total cost, instead of 12 portions.
2. **Mitigation**: the Sazon UI must show a yellow warning "YIELD NOT VERIFIED" on every product whose recipe has `yield_is_default = true`. This makes the operator visually prioritize the backfill.
3. **The 16 recipes are the most important ones** (the 7 with yields are all small batches: 12 unidades, 20 bombones, 100 croquetas). The bizcochos (REC-011, 012, 013) are critical for eventos and have empty yields.

## Acceptance

- All 23 recipes have `yield_qty` set (1.0 default or operator-supplied)
- Recipes with `yield_is_default = true` are visible in a "Needs verification" filter on `/admin/recipes`
- Within 1 week of operator onboarding, all 16 default yields are backfilled
- `Product.cost_gs = recipe.total_cost / recipe.yield_qty` is correct for all 24 products after backfill
- CHANGELOG.md entry per AGENTS.md rule 35

## Reference

- **Full data plan**: `docs/operations/2026-10-12-saskia-full-seed-data-plan.md` §2.4 (the 23-recipe table)
- **HEREBUS sheet**: Google Sheet `1z43h66KulWS4QS8wJAKoIMV3sk6yZqfC`
- **SASKIA-223 (parent)**: HEREBUS data import — this ticket is its followup
