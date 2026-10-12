# SASKIA-223: HEREBUS data import (100 ingredients, 23 recipes, 7 packaging, 24 products, 20 suppliers)

**Date:** 2026-10-12
**Status:** drafted (post-HEREBUS-discovery)
**Author:** AIW Bot
**Estimate:** 4-5 days
**Sister tickets:** SASKIA-221 (drafted — remaining settings), SASKIA-224 (drafted — yield backfill)
**Source spreadsheet:** Google Sheet `1z43h66KulWS4QS8wJAKoIMV3sk6yZqfC` (30 sheets, full HEREBUS data)

## Why

Saskia has a **complete working spreadsheet** (HEREBUS) with 100 ingredients, 23 recipes, 7 packaging items, and 3 operational tracking sheets. The Sazon app currently has **22 placeholder products and 0 recipes** — the operator (Saskia) has the real data in HEREBUS but it's not in the Sazon app.

The OOB says "the website of sazon should load all of the thigns" — without importing HEREBUS, the Sazon app shows fake products with placeholder prices. With HEREBUS imported:
- 100 real ingredients with supplier names + 2026-10-07 prices
- 23 real recipes (REC-001 to REC-023) with real ingredients, real costs, real yield
- 7 real packaging items with bulk + unit prices
- 24 real products linked to REC-NNN recipes (1 product per recipe, plus the seasoning)
- ~20 real suppliers (from HEREBUS Notas)
- 11 Dutch heritage recipes + 4 Dutch heritage ingredients flagged
- 17 ingredients flagged for price re-confirmation

## What

### Part A: Import the 100 ingredients

Add a new function `seed_ingredients_from_herbus(session)` in `app/rms/seed/sazon.py` that:
1. Reads the Inventory data (already in `docs/operations/2026-10-12-saskia-full-seed-data-plan.md` §2.2)
2. Inserts 100 Ingredient rows (idempotent: skip if SKU exists)
3. Sets the `category` to one of 12 values (matching HEREBUS Grupos)
4. Sets `package_size`, `package_unit`, `package_price_gs`, `unit_price_gs`, `stock_qty`, `min_reorder` from the spreadsheet
5. Sets `last_price_update = 2026-10-07` (the date of the HEREBUS export)
6. Sets `dutch_heritage_flag = true` for ING-001, 032, 051, 069, 076, 087, 097-100
7. Sets `needs_confirm_flag = true` for ING-082 to ING-100 (the 17 "CONFIRMAR" rows)
8. Computes and stores `unit_price_gs = bulk_price / package_size` (matches the spreadsheet formula)

### Part B: Import the 23 recipes

Add `seed_recipes_from_herbus(session)`:
1. Reads the 23 Recipe_* sheets (already in §2.4 of the data plan)
2. For each recipe, insert a Recipe row (idempotent on slug)
3. Sets `name`, `slug`, `yield_qty` (from B4), `yield_unit` (from D4), `dutch_heritage_flag`
4. Inserts RecipeLine rows (one per ingredient, from the INGREDIENTES block)
5. Marks REC-006 Frikandel and REC-006 Bitterballen correctly: assign REC-006 to Frikandel (already in DB), create REC-024 for Bitterballen (the lowercase variant)
6. Notes: 16 of 23 recipes have empty yield_qty (B4). Default to 1 molde for bizcochos, 12 unidades for individual products. Operator backfills later (SASKIA-224).

### Part C: Import the 7 packaging items

Add `seed_packaging_from_herbus(session)`:
1. Reads the Packaging sheet (already in §2.3 of the data plan)
2. Inserts 7 Packaging rows (idempotent on SKU MAT-01..MAT-07)
3. Sets `package_size`, `package_unit`, `bulk_price_gs`, `unit_price_gs`

### Part D: Rewrite the products seeder to use HEREBUS recipes

The current `seed_sazon()` has 22+ products with placeholder names and no recipe linkage. Replace with a **HEREBUS-aware product list**:

| Product | Recipe | Channel |
|---|---|---|
| Muffin de Chocolate (molde 20x20) | REC-001 | retail |
| Cheesecake (rebanada) | REC-002 | retail |
| Stroopwafel (unidad) | REC-003 | retail, NL heritage |
| Ontbijtkoek (rebanada) | REC-004 | retail, NL heritage |
| Carrot Cake (rebanada) | REC-005 | retail |
| Frikandel (unidad) | REC-006 | retail, NL heritage |
| Bitterballen (unidad) | REC-024 (was REC-006b) | retail, NL heritage |
| Ketjap Manis (botella 250ml) | REC-007 | retail, NL heritage |
| Hojaldre / Bladerdeeg (plancha 30x40) | REC-008 | wholesale + retail |
| Pastelitos Rosados (pack 12) | REC-009 | retail, NL heritage |
| Galletas de Especuloos (pack 200g) | REC-010 | retail, NL heritage |
| Bizcocho Básico 25cm | REC-011 | eventos |
| Bizcocho Básico 30cm | REC-012 | eventos |
| Tarta de Manzana | REC-013 | retail, eventos |
| Profiteroles Den Bosch (pack 6) | REC-014 | retail, NL heritage |
| Petisús de Hojaldre y Crema (pack 12) | REC-015 | retail, eventos |
| Oliebollen (pack 6) | REC-016 | retail, NL heritage (New Year) |
| Babka (rebanada) | REC-017 | retail, eventos |
| Bombones de Chocolate (caja 12) | REC-018 | retail, eventos |
| Goulash Croquettes (pack 6) | REC-019 | retail, NL heritage |
| Veggie Bitterballen (pack 6) | REC-020 | retail, NL heritage |
| Supplì Cacio e Pepe (pack 6) | REC-021 | retail, catering |
| Everything Bagels (pack 4) | REC-022 | retail |
| Everything Bagel Seasoning (frasco 57g) | REC-023 | retail |

**Total: 24 products** (1 per recipe, plus 1 for the seasoning).

For each product:
- `cost_gs` = `recipe.total_cost / recipe.yield_qty` (or 1 if yield is empty)
- `price_retail_gs` = `cost_gs × 3.5` (standard panadería retail markup; verify with Saskia)
- `price_wholesale_gs` = `cost_gs × 2.0`
- `price_eventual_gs` = `cost_gs × 4.0` (eventos)
- `category_id` = derived from "panaderia" / "pasteleria" / "catering" / "eventos" / "otros"

### Part E: Import the ~20 suppliers

The HEREBUS Notas field has ~20 unique suppliers:
- Supermas, Ypacaraí, Tregar, TodoNegocio, cocinar.com.py, preciosdelagro, Dietetica, Cervecería Nacional, Local Harina, etc.
- Most don't have contact info in the Notas. Operator (Saskia) needs to provide phone/email/address for each.

Add `seed_suppliers_from_herbus(session)`:
1. Inserts ~20 Supplier rows (idempotent on name)
2. Sets the name, type (supermarket/mill/dairy/etc.), and a default phone/email if known
3. The operator (Saskia) updates contact details later via the suppliers admin page

### Part F: Mark dutch_heritage products and recipes

For each of the 11 Dutch recipes, set `dutch_heritage_flag = true` on:
- The Recipe row
- The corresponding Product row
- The RecipeLine rows that use a Dutch heritage ingredient (ING-001, 032, 051, 069, 076, 087, 097-100)
- The Supplier rows that supply Dutch ingredients (Local Harina, etc.)

This enables the Sazon UI to filter the menu by "Dutch heritage" tag.

### Part G: Update the Sazon app to display HEREBUS data

The Sazon app needs to render:
- `/recetas` — list of 23 recipes (from `Recipe.query.all()`)
- `/recetas/<id>` — recipe detail with steps (already from SASKIA-212) + ingredient list
- `/menu` — list of 24 products with prices
- `/menu/<product>` — product detail with "Ver ingredientes" toggle that shows the recipe's ingredient list + cost
- `/admin/inventory` — 100 ingredients with stock, prices, suppliers
- `/admin/recipes` — 23 recipes with cost, margin
- `/admin/products` — 24 products with cost, margin, sales velocity
- `/admin/dutch-heritage` (new) — filtered view: only Dutch recipes + products

## Out of scope (deferred)

- **SASKIA-224** — Recipe yield backfill (16 of 23 recipes have empty B4)
- **SASKIA-220** — 5 new packs (this ticket stays on Panadería only)
- **Supplier contact details** — operator fills in after first onboarding
- **Recipe photos** — out of scope (no photos in HEREBUS)

## Risks

1. **REC-006 conflict**: Frikandel AND Bitterballen share REC-006 in HEREBUS. The Sazon import assigns REC-006 to Frikandel and REC-024 to Bitterballen. Operator (Saskia) must confirm.
2. **16 missing yields**: 70% of recipes have empty B4. Default in seeder, backfill later.
3. **17 "CONFIRMAR" prices**: flagged in DB but not corrected. Operator (Saskia) re-quotes when she buys next.
4. **Product price markup**: 3.5x retail / 2.0x wholesale / 4.0x eventual is a Sazon convention, not Saskia's. Verify with her before mass-importing.
5. **Test coverage**: 100 ingredients × 1 test = 100 tests. Use parametrize + 5 representative tests (1 per category).

## Acceptance

- `Ingredient.query.count() == 100` (was 0; current seeder has no ingredients, only product templates)
- `Recipe.query.count() == 23` (was 0; current seeder has no recipes)
- `RecipeLine.query.count() >= 250` (avg 12 per recipe × 23; some recipes have more)
- `Packaging.query.count() == 7` (was 0)
- `Product.query.count() == 24` (was 22+ with different names; this rewrites the product list)
- `Supplier.query.count() >= 15` (was 0 or fewer; depends on current state)
- Each product has a non-null `recipe_id` FK
- Each Dutch recipe + product has `dutch_heritage_flag = true`
- Each "CONFIRMAR" ingredient has `needs_confirm_flag = true`
- All 41 existing tests + 5 new test files pass
- `make ruff` + `make format-check` clean
- CHANGELOG.md entry per AGENTS.md rule 35

## Reference

- **Full data plan**: `docs/operations/2026-10-12-saskia-full-seed-data-plan.md` (especially §2.2 for ingredients, §2.4 for recipes, §2.3 for packaging)
- **Sazon PACKS**: `app/rms/seed/packs.py::PACKS` (11 packs, Panadería is the target for this ticket)
- **OOB-2026-10-12**: "the website of sazon should load all of the thigns la vaquita holnadesa iis a just the first client later we will have many more"
- **SASKIA-212 (sister)**: recipe detail pages with real procedure steps (3-phase Spanish-voseo) — extends to all 23 recipes after this ticket
