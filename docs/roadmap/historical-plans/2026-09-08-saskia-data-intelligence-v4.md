# Saskia RMS — Data Intelligence Plan v4 (E26-E35)

**Date:** 2026-09-08
**Author:** Iván (via Hermes)
**Status:** Executable
**Scope:** 10 new epics covering everything derivable from client data that the human didn't tag explicitly.

## Why v4

Plan v3 (E1-E25) shipped 25 epics. The user's audit (2026-09-08) surfaced that
the client provided only **explicit fields** (names, prices, recipe lines,
sales rows). Anything that needs *joining + classification + statistical
inference* was missing. This plan fills those gaps:

- **Ingredient intelligence** (auto-categorize, allergens, shelf-life)
- **Recipe intelligence** (prep-time, dietary tags, difficulty)
- **Menu engineering** (star/puzzle/plowhorse/dog quadrant)
- **Inventory intelligence** (days-of-stock, reorder, dead stock, overstock)
- **Sales intelligence** (hourly/DOW/monthly patterns, affinity, churn)
- **Product similarity** (Jaccard overlap, substitution)
- **Production scheduler** (bake-this-much-by-this-time)
- **True food cost** (theoretical vs actual reconciliation)
- **Dashboard intelligence** (surfaced insights panel)

## How to read this

10 epics in one phase (Phase 1.6 — Data Intelligence). Each epic:
- **Why** (business outcome)
- **Stories** (E#.S# format)
- **Tasks** (numbered, atomic)
- **Effort** (per task + per epic)
- **Depends on** (other epics)
- **Acceptance** (definition of done)

Tickets: `SASKIA-NNN`. Epic+story codes: `E26.S1` = Epic 26, Story 1.

## Phase map

| Phase | Name | Epics | Status |
|---|---|---|---|
| 1.0  | Foundation (auth, schema, CRUD) | E1-E5 | ✅ COMPLETE |
| 1.5  | Hardening (migrations, analytics, tags) | E6-E10 | ✅ COMPLETE |
| 1.55 | Scale (customers, accounting, mobile) | E11-E17 | ✅ COMPLETE |
| 1.6  | Data Intelligence (this plan) | E26-E35 | ⏳ NEW |
| 1.7  | Print/Label/Production/Seasonal | E18-E25 | ✅ COMPLETE |

---

# PHASE 1.6 — Data Intelligence

## Epic 26 — Ingredient intelligence (auto-classify)

**Why:** Every ingredient in the DB is a free-form `name`. Without
category, allergens, or shelf-life defaults, the system can't answer
"is this safe for nut-allergic customers?", "how long does this keep?",
or "what's my dairy spend share?". This epic auto-infers those fields.

### E26.S1 — Categorize every ingredient

**Why:** Category unlocks filtering, shopping lists, supplier grouping,
and cost-share analysis.

**Tasks:**
1. Build `app/rms/ingredient_intel.py::infer_category(name) → str` — keyword
   classifier (lácteos, harinas, endulzantes, grasas, leudantes, frutas,
   frutos-secos, decoración, otros).
2. Add `category` column to `ingredient` (migration 009, VARCHAR(32)).
3. Build `infer_subcategory(name, category) → str | None` — finer split.
4. Build `infer_role(name) → str` (leavening, sweetener, fat, structure, flavor, decoration).
5. Batch-infer on seed + write `ingredient.category` for every row.
6. Test: every seeded ingredient has a category from the closed set.
7. Test: unknown names fall back to "otros".

**Effort:** 4h
**Depends on:** E6 seed
**Acceptance:** `pytest tests/test_ingredient_intel.py -q` passes ≥12 tests;
all 30 seeded ingredients have a non-null category; unknown words map to "otros".

### E26.S2 — Allergen detection

**Why:** Food-safety compliance + customer dietary filtering.

**Tasks:**
1. Add `allergens` column (JSONB, list of strings) to `ingredient` (migration 009).
2. Build `infer_allergens(name) → list[str]` — set of {gluten, dairy, eggs, nuts, soy, sesame}.
3. Build `infer_dietary_tags(name) → list[str]` — set of {vegan, vegetarian, keto_friendly}.
4. Batch-populate on seed.
5. Test: `harina` → gluten, `leche` → dairy+vegetarian (NOT vegan), `almendra` → nuts+vegan.

**Effort:** 3h
**Depends on:** E26.S1
**Acceptance:** Allergens populated for every seed; dietary filter query works on product page.

### E26.S3 — Shelf-life + storage defaults

**Why:** Replaces random `shelf_life_days` with category-based defaults.

**Tasks:**
1. Build `CATEGORY_SHELF_LIFE` dict (lácteos=7, harinas=180, frutos-secos=90,
   grasas=120, endulzantes=730, leudantes=180, frutas=5, decoración=180).
2. Build `infer_storage(name, category) → str` (ambient / refrigerated / frozen).
3. Backfill `ingredient.shelf_life_days` from defaults when null.
4. Test: every category has a default; storage inferred correctly.

**Effort:** 2h
**Depends on:** E26.S1
**Acceptance:** All ingredients have shelf_life_days from defaults; storage field populated.

### E26.S4 — Substitutability detection

**Why:** "What can I use instead of eggs?" — operators ask this daily.

**Tasks:**
1. Build `substitutability_graph(session) → dict[ingredient_id, list[ingredient_id]]`
   using recipe co-occurrence (if A and B appear in same recipes at similar qty, they're substitutable).
2. Test: `mantequilla` and `margarina` co-occur in ≥3 recipes → substitutable.

**Effort:** 2h
**Depends on:** E26.S1
**Acceptance:** Graph built; queryable via `app/rms/ingredient_intel.py::find_substitutes(session, ingredient_id)`.

**Epic total:** 11h

---

## Epic 27 — Recipe intelligence (auto-classify recipes)

**Why:** Recipes have `prep_minutes` field but it's always NULL. Difficulty,
dietary compatibility, oven temp, and recipe family are unknown. This epic
fills them.

### E27.S1 — Prep-time + cook-time estimates

**Tasks:**
1. Add `cook_minutes` column to `recipe` (migration 010, INT NULL).
2. Build `estimate_prep_minutes(recipe) → int` — heuristic: yield_qty × 2 +
   ingredient count × 1.5.
3. Build `estimate_cook_minutes(recipe, category) → int` — category-based
   (panadería=30, pastelería=45, fríos=0).
4. Backfill `recipe.prep_minutes` and `recipe.cook_minutes` from estimates.
5. Test: recipe with yield 12 muffins + 8 ingredients → ~25min prep.

**Effort:** 3h
**Depends on:** E26.S1 (need category)
**Acceptance:** Every recipe has prep+cook estimate within ±20% of operator's mental model.

### E27.S2 — Dietary compatibility

**Tasks:**
1. Add `dietary_tags` column (JSONB list) to `recipe` (migration 010).
2. Build `infer_recipe_dietary(recipe) → set[str]` — intersect of all
   ingredient dietary tags (if all are vegan, recipe is vegan).
3. Test: `muffin_vainilla` contains `leche`, `huevo`, `harina` → NOT vegan;
   NOT gluten-free.

**Effort:** 2h
**Depends on:** E26.S2
**Acceptance:** Every recipe has dietary_tags; `recipe.is_vegan` etc. methods work.

### E27.S3 — Difficulty + family classification

**Tasks:**
1. Add `difficulty` column (INT 1-5) and `family` column (VARCHAR(32)) to
   `recipe` (migration 010).
2. Build `infer_difficulty(recipe) → int` — count(ingredient_lines) +
   depth(sub_recipes) → clamp 1-5.
3. Build `infer_family(recipe) → str` — keyword on recipe.name (panadería,
   pastelería, salados, fríos, heladería).
4. Test: `cheesecake` with 12 ingredients → difficulty 4, family pastelería.

**Effort:** 3h
**Depends on:** E26.S1
**Acceptance:** Every recipe has difficulty 1-5 and family from closed set.

### E27.S4 — Yield-in-grams + cost-per-gram

**Tasks:**
1. Build `recipe_yield_grams(recipe) → Decimal | None` — converts yield to
   grams using unit_conversion (kg→g, l→ml for liquids).
2. Build `recipe_cost_per_gram(recipe) → Decimal | None` — total_cost / yield_grams.
3. Test: 12 muffins × 50g each = 600g yield.

**Effort:** 2h
**Depends on:** E26.S1
**Acceptance:** Yield-in-grams and cost-per-gram computable for every recipe.

**Epic total:** 10h

---

## Epic 28 — Menu engineering (star/puzzle/plowhorse/dog)

**Why:** Classic restaurant consulting tool. Classifies every product by
margin × volume quadrant. Tells operator where to push, prune, reprice.

### E28.S1 — Quadrant classifier

**Tasks:**
1. Build `app/rms/menu_engineering.py::classify_products(session) → dict[product_id, Quadrant]`.
2. Quadrants: STAR (high margin + high volume), PLOWHORSE (low margin + high volume),
   PUZZLE (high margin + low volume), DOG (low margin + low volume).
3. Thresholds: median margin and median volume across the active catalog.
4. Test: products with synthetic sales pattern classify correctly.

**Effort:** 4h
**Depends on:** E26.S1, E27.S1
**Acceptance:** Every product gets a quadrant label; 4 quadrants non-empty in seed.

### E28.S2 — Menu engineering report

**Tasks:**
1. Build `menu_engineering_report(session) → dict` — per-quadrant count,
   total margin contribution, action recommendations.
2. Test: report has 4 keys (star, plowhorse, puzzle, dog).

**Effort:** 2h
**Depends on:** E28.S1
**Acceptance:** Report computable; renderable as a 2×2 table on dashboard.

**Epic total:** 6h

---

## Epic 29 — Inventory intelligence

**Why:** `stock_qty` is just a number. Doesn't tell operator when to reorder,
what's dead stock, what's overstocked.

### E29.S1 — Days-of-stock + reorder point

**Tasks:**
1. Add `lead_time_days` column to `ingredient` (migration 011, INT default 3).
2. Build `days_of_stock(ingredient, sales_history) → float` — stock_qty / avg_daily_consumption.
3. Build `reorder_point(ingredient, sales_history, lead_time, safety_pct=0.2) → float`
   — lead_time × avg_daily × (1 + safety_pct).
4. Test: ingredient with 1kg stock + 100g/day consumption → 10 days_of_stock.

**Effort:** 4h
**Depends on:** E26.S1
**Acceptance:** Days-of-stock + reorder-point computable for every ingredient with sales history.

### E29.S2 — Dead stock + overstocked detection

**Tasks:**
1. Build `dead_stock(session, days_threshold=30) → list[Ingredient]` — ingredients
   not consumed in N days.
2. Build `overstocked(session, multiplier=3) → list[Ingredient]` — stock > 3 × avg_daily_use × 30.
3. Build `stock_value_gs(session) → Decimal` — total capital tied up in stock at purchase price.
4. Test: seed contains at least 1 dead + 1 overstocked ingredient after consumption simulation.

**Effort:** 3h
**Depends on:** E29.S1
**Acceptance:** All 3 queries runnable; produce meaningful output on seed data.

**Epic total:** 7h

---

## Epic 30 — Sales intelligence

**Why:** 920 sales over 90 days. Operator should see hourly/DOW/monthly
patterns, product affinity (people who buy X also buy Y), churn detection.

### E30.S1 — Time-pattern distributions

**Tasks:**
1. Build `sales_by_hour(session) → dict[int, int]` — count per hour 0-23.
2. Build `sales_by_day_of_week(session) → dict[int, int]` — Mon-Sun.
3. Build `sales_by_month(session) → dict[str, int]` — YYYY-MM keys.
4. Build `peak_hour(session) → int` + `peak_dow(session) → int`.
5. Test: synthetic data → hour 12 has highest count, etc.

**Effort:** 4h
**Depends on:** E6 seed
**Acceptance:** All 5 functions return correct shapes; seed data shows non-uniform distribution.

### E30.S2 — Product affinity (market basket)

**Tasks:**
1. Build `product_affinity(session, min_cooccurrence=2) → dict[(p1, p2), int]`.
   Since each sale has 1 product, group sales by day+customer-or-hour to form baskets.
2. Build `top_pairs(session, n=10) → list[(p1, p2, count)]`.
3. Test: synthetic sales with pair patterns → top_pairs reflects them.

**Effort:** 4h
**Depends on:** E30.S1
**Acceptance:** Affinity computable; top_pairs sorted descending.

### E30.S3 — Churn + trend detection

**Tasks:**
1. Build `churning_products(session, threshold_pct=0.3) → list[Product]`
   — sales in last 14 days < threshold × prior 14-day avg.
2. Build `rising_products(session, threshold_pct=0.3) → list[Product]`
   — sales in last 14 days > threshold × prior 14-day avg.
3. Test: synthetic declining product is flagged as churning.

**Effort:** 3h
**Depends on:** E30.S1
**Acceptance:** Churning/rising both produce non-empty lists on realistic data.

**Epic total:** 11h

---

## Epic 31 — Product similarity

**Why:** "What's the closest product to X?" — for upsells, substitutions,
menu rationalization.

### E31.S1 — Jaccard ingredient overlap

**Tasks:**
1. Build `app/rms/product_similarity.py::jaccard_similarity(product_a, product_b) → float`
   — |A ∩ B| / |A ∪ B| over ingredient sets.
2. Build `most_similar_products(session, product_id, top_n=5) → list[(Product, float)]`.
3. Build `product_ingredient_set(product) → set[int]`.
4. Test: products sharing 3 of 4 ingredients → similarity 3/5 = 0.6.

**Effort:** 4h
**Depends on:** E26.S1
**Acceptance:** Jaccard returns 0.0-1.0; most_similar excludes self.

### E31.S2 — Substitution suggestions

**Tasks:**
1. Build `suggest_substitute(product, available_recipes) → list[Product]`
   — products with similarity > 0.7 AND matching sale price band (±20%).
2. Test: 2 products with 80% ingredient overlap + similar price → suggested.

**Effort:** 2h
**Depends on:** E31.S1
**Acceptance:** Substitution list non-empty for at least 1 product in seed.

**Epic total:** 6h

---

## Epic 32 — Production scheduler

**Why:** Operator asks "what should I bake tomorrow morning?" The answer:
predicted sales × yield → produce just enough to satisfy demand without waste.

### E32.S1 — Velocity-based production plan

**Tasks:**
1. Build `production_plan(session, target_date, safety_pct=0.2) → dict[Recipe, int]`
   — predicted_units = avg_daily_sales × (1 + safety_pct) × seasonal_multiplier
   → batches_needed = ceil(predicted_units / yield_qty).
2. Build `production_schedule(session, target_date) → list[(hour, Recipe, qty)]`
   — schedules batches at appropriate hours (morning breads 5am, pastries 7am, etc.).
3. Test: plan non-empty on seed; total predicted units within ±20% of avg daily.

**Effort:** 5h
**Depends on:** E30.S1, E27.S1
**Acceptance:** Plan computable; yields sensible batches (no 1000-muffin orders).

**Epic total:** 5h

---

## Epic 33 — True food cost (theoretical vs actual)

**Why:** Sales × recipe_cost tells you what ingredients SHOULD have been
consumed. (ingredient_purchases − current_stock) tells you what WAS
consumed. The difference = waste/theft/error.

### E33.S1 — Theoretical consumption

**Tasks:**
1. Build `theoretical_consumption(session, date_range) → dict[Ingredient, Decimal]`
   — sum over sales × recipe ingredient lines.
2. Test: 10 sales of muffin × 0.18kg milk = 1.8kg theoretical milk consumption.

**Effort:** 3h
**Depends on:** E6 seed
**Acceptance:** Theoretical consumption matches recipe math.

### E33.S2 — Actual consumption + variance

**Tasks:**
1. Build `actual_consumption(session, date_range) → dict[Ingredient, Decimal]`
   — sum(sale_stock_move.qty_delta where qty_delta<0) over period.
2. Build `consumption_variance(session, date_range) → dict[Ingredient, VarianceResult]`
   — actual − theoretical per ingredient.
3. Build `food_cost_variance_pct(session) → float` — total variance / total theoretical.
4. Test: when actual > theoretical, variance is positive (waste indicator).

**Effort:** 4h
**Depends on:** E33.S1
**Acceptance:** Variance computable; positive values indicate waste.

**Epic total:** 7h

---

## Epic 34 — Dashboard intelligence panel

**Why:** All the above computations need to surface on `/` for the operator
to act on them.

### E34.S1 — Insights panel template

**Tasks:**
1. Build `app/templates/_components/intelligence_panel.html` — shows top 5
   alerts (low stock, churning products, dead stock, overstocked, fast movers).
2. Wire into `app/templates/inicio.html` as a new section.
3. Compute insights in `app/routers/dashboard.py::get_intelligence_summary(session) → dict`.

**Effort:** 4h
**Depends on:** E26-E33
**Acceptance:** Dashboard shows ≥5 actionable insights.

**Epic total:** 4h

---

## Epic 35 — Integration tests + fixtures

**Why:** All the above need shared fixtures and tests for confidence.

### E35.S1 — Shared intelligence fixtures

**Tasks:**
1. Build `tests/fixtures/intelligence.py` — seeded dataset with known
   patterns (one churning product, one overstocked ingredient, etc.).
2. Test: fixture produces expected counts for each intelligence function.

**Effort:** 3h
**Depends on:** E26-E34
**Acceptance:** Fixture works; each intelligence function has ≥3 tests.

**Epic total:** 3h

---

# Execution footer

## Total effort estimate
- E26: 11h
- E27: 10h
- E28: 6h
- E29: 7h
- E30: 11h
- E31: 6h
- E32: 5h
- E33: 7h
- E34: 4h
- E35: 3h
- **Total: 70h**

## How to execute (per Iván's directive: ship all in one turn)
1. Each epic ships as 1 commit: module + tests + CHANGELOG bump.
2. Working tree stays clean between commits.
3. Final verification: `pytest -q` ≥ 700 passing, `ruff check .` clean.
4. Dashboard integration test confirms insights render.
5. Live site verifies post-deploy (Render picks up latest commit on push).
