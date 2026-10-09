# LESSONS BOOK v2 — Sazón production system vs 10 competitors + 5 industry references (2026-10-08)

Second-pass, deeper analysis. v1 had several false negatives (I
flagged gaps that the Sazon codebase already closes) and missed several
features that exist locally. This v2 corrects those.

## CORRECTIONS FROM v1 — already shipped in Sazon

| v1 said missing | Actually shipped (file + line) |
|---|---|
| Forecast is flat 14d | `app/rms/restock_forecast.py` — **Poisson per-weekday MLE** with Wilson 95% CI and P95 stockout walk. No numpy. |
| SEASONAL_CALENDAR_2026 hardcoded | `app/rms/seasonal.py` — `calendar_for_year(year)` shifts to any year. Plus `upcoming_calendar_json()` for dashboard widget. |
| Demand algebra missing | `app/rms/demand_freshness.py:forecast_demand()` — base rate × weekday factor × trend (clamped [0.6, 1.6]) |
| Substitution engine missing | `app/rms/demand_freshness.py` §10 — substitution engine + price delta + tag preservation |
| Freshness / use-first missing | `app/rms/demand_freshness.py` §2 — use-first from shelf_life_days vs last receipt |
| Customer dedup missing | `app/rms/customer_merge.py` P1-B4 — full reassignment of Sales + Pedidos + contact fill, atomic |
| Customer dietary missing | `app/rms/customer_dietary.py` — RESTRICTIONS + PREFERENCES + CONFIRM_ALWAYS with canonical vocabulary |
| Fiado / AR ledger missing | `app/rms/fiado.py` — signed ledger, idempotent pago, FIFO aging 0-30/31-60/61+, void_reversal |
| WhatsApp-style summary missing | `app/rms/notifications.py` — `format_daily_summary_message` + delivery seam (Twilio/SMTP/dryrun) |
| Sentry→Telegram bridge missing | `app/rms/notify.py` — `sentry_before_send` hook mirror |
| Menu combo / pack missing | `app/rms/menu_ejecutivo.py` — `expand_menu_items()` priced as the menu, not sum |
| Menu OCR missing | `app/rms/menu_ocr.py` — GLM vision with anti-hallucination prompt + fuzzy match |
| Stock status hardcoded magic | `app/rms/stock_status.py` — per-category config in DB, falls back to DEFAULT_* |
| Limited audit log retention | `app/rms/maintenance.py:prune_audit_log` — config-driven retention, dry-run mode |
| Per-request observability | `app/rms/observability.py` — request_id + Loguru contextualize + structured error pages |

**v1 corrections summary:** I flagged 14 gaps that were already shipped.
This v2 audits only genuine open items.

---

## TABLE OF CONTENTS v2

1. Sazon-fleet inventory — what's actually there now (114 migrations, 116 rms modules)
2. Sazon's open gaps in production (the genuine, currently-open items)
3. Production planning refinements (5 lessons, all fine-tuning from current-state)
4. Stock & ingredient (5 lessons — mostly UX, not model)
5. KDS / KOT / printing (6 lessons — still optional per L-NO-7)
6. Sales / POS (4 lessons)
7. Reports / analytics (4 lessons)
8. Architecture / code patterns (6 lessons)
9. UI / page-layout (6 lessons)
10. Ops / compliance / safety (4 lessons)
11. Settings / config (4 lessons)
12. Industry-pattern cross-check (vs Supply'd, CafeKit, BakeOnyx, JRNI/Rinvy)
13. WHAT NOT TO COPY (8 forced exclusions, updated)
14. Sazon decision log (canonical)
15. Appendices — full repo + module inventory

---

## 1. SAZON-FLEET INVENTORY (verified by walking the tree)

**Modules by directory**:
- `app/rms/` — **116 modules** (sprint-includes E12-E22 + Phase 7 + Fase 5)
- `app/rms/models/` — 14 model files (audit, auth, catalogs_restored, channels, closure, common, core, delivery, herbus_drive, inventory, orders, procurement, production, sales)
- `app/rms/migrations/` — 10 hand-rolled migration modules
- `app/routers/` — **36 routers**, 301 total routes (117 production-relevant)
- `app/templates/` — 99 templates + 11 components

**Modules grouped by capability** (signals: what's already built):

| Capability | Module(s) | Status |
|---|---|---|
| Forecast (demand) | `production.py`, `forecast.py`, `restock_forecast.py`, `demand_freshness.py` | ✅ mature |
| Plan / completion | `production.py`, `production_demand.py`, `eod_completions.py` | ✅ |
| Plan accuracy | `plan_accuracy.py` | ✅ (read by `/produccion/accuracy`) |
| Stock ledger | `stock_ledger.py`, `stock_status.py`, `waste.py`, `inventory.py` | ✅ |
| Sale cost walk | `costing.py`, `prime_cost.py`, `food_cost.py`, `cost_freshness.py` | ✅ |
| Recipes (multi-level) | `recipes.py`, `recipes_consolidated.py`, `recipe_intel.py` | ✅ (sub-recipe recursion) |
| Customers (full) | `customers.py`, `customer_dietary.py`, `customer_merge.py` | ✅ |
| Pedidos (pre-orders) | `pedidos.py`, `orders.py` | ✅ |
| Fiado / credit | `fiado.py` | ✅ (AR ledger) |
| Menu combos | `menu_ejecutivo.py` | ✅ |
| Menu OCR | `menu_ocr.py` | ✅ (GLM vision) |
| Seasonal calendar | `seasonal.py` (refactored) | ✅ |
| Settings KV | `settings_registry.py` (sprint 2.1) | ✅ |
| Observability | `observability.py`, `audit.py`, `audit_analytics.py` | ✅ |
| Notifications | `notifications.py`, `notify.py` (Telegram) | ✅ |
| Daily maintenance | `maintenance.py` | ✅ |
| Migration discipline | `rollback.py`, `migrations/`, `archives/` | ✅ (rule 17) |
| Refunds (computed) | `refunds.py` | ✅ |
| Loyalty / points | `loyalty/`, `customers.py` | ✅ |
| HACCP / cold-chain | `haccp.py`, `haccp_seed.py`, `eod_closed.py` | ✅ |
| Production v2 / v3 | `produccion/_full.py` + 9-module split | ✅ |
| Bank reconciliation | `bank.py`, `accounting.py` | ✅ |
| Inflation / pricing | `pricing.py`, `price_history.py`, `cotizador.py` | ✅ |
| Reorder & suppliers | `reorder.py`, `reorder_supplier_prices.py`, `supplier_*.py` | ✅ |
| Subscriptions | `suscripciones.py`, `invoicing.py` | ✅ |
| Vs-mercado (competitive intelligence) | `market_intel.py`, `seed_market_prices.py` | ✅ |
| Risk register | `riesgos.py` | ✅ |
| Equipment wishlist | `wishlist.py` | ✅ |
| Excel import / export | `excel_io.py`, `excel_validate.py`, `streaming_csv.py` | ✅ |
| Held sales (parked cart) | `held_sales.py` | ✅ |
| Variants | `variants.py`, `tagging/` | ✅ |
| Cash session / register | `cash.py`, `cierre.py` | ✅ |
| Inventory intel | `inventory_intel.py`, `ingredient_intel.py` | ✅ |
| Sales intel | `sales_intel.py` | ✅ |
| Menu engineering | `menu_engineering.py` | ✅ |
| Tag algebra | `tag_algebra.py`, `tagging/` | ✅ |
| Derived intel | `derived_intel.py` | ✅ |
| Margin tiers | `margin_tier.py` | ✅ |
| Customer dietary | `customer_dietary.py` | ✅ |
| Delivery zones | `delivery_zones.py` | ✅ |

**The "what's NOT in Sazon" list (genuine open items):**
1. **Live KDS** (no SSE/WebSocket anywhere) — *intentional per SASKIA-210*
2. **Multi-tenant** — *intentional*
3. **Mobile app** — *intentional*
4. **Card processor** — *intentional*
5. **Self-order kiosk** — *intentional*
6. **Daily P&L rollup** (`/reportes/ply`) — **genuine gap**
7. **Pre-billing checklist** (URY pattern) — **genuine gap**
8. **KOT error log** (URY pattern) — **genuine gap**
9. **WhatsApp integration** (FloCafe's baileys-based) — *likely wanted eventually*
10. **Operator-configurable seasonal calendar** (move from code→DB) — **genuine gap** (small)
11. **Drag-and-drop row reorder on production grilla** (Flutter POS pattern) — **genuine UX gap**
12. **Maintenance middleware** (returns 503 during migrations) — **genuine gap**
13. **Wizard for first-run setup** — *intentional*
14. **AI assistant / chat** — there's `copilot.py` and `llm.py`. Inspect what they do.

---

## 2. GENUINE OPEN GAPS (corrected from v1)

Only items still genuinely open are below. v1 lessons L-PLAN-1, L-PLAN-2, L-PLAN-5, L-PLAN-8..11, L-STOCK-1..5, L-ARCH-1, L-ARCH-7, L-NO-1..8 stand without modification.

### G-OPEN-1: Daily P&L rollup ⭐
**File to create:** `app/rms/daily_p_and_l.py` (mirror `reportes_diario.html` but per-SKU and per-day totals with margin%)
**Source:** URY `ury_daily_p_and_l` JSON already verified — gross_sales, tax, cogs, gross_profit, net_profit, all percentages, expenses breakout, employee_costs.
**Sazon data:** has every input (`Sale + StockMovement + ChannelPrice + CreditTransaction`); just needs the rollup. Single SQL with GROUP BY date + SUM(qty*price_gs) + cogs_from_stock_movement.
**Effort / Risk:** 🟡 M. 1-2 days. Most "remove guess-work" ROI per industry refs (BakeOnyx, CafeKit).

### G-OPEN-2: Pre-billing checklist (URY `ury_pos_checklist_log`) ⭐
**Pattern:** URY's 3-docType trio: checklist_log (per-day), checklist_item (definitions), checklist_log_item (per-day completions).
**Sazon has the model already:** `eod_closed.py:assert_day_open_or_raise()` (raises if day is closed). Generalize this to a checklist pattern: day's plan won't be `Finalize`-able until HACP_logged + StockConfirmedBothProductAndIngredientVerified.
**Effort / Risk:** 🟡 M. 2 days.

### G-OPEN-3: KOT error log ⭐
**Pattern:** URY `ury_kot_error_log`. Wrap each `print_export.print_production()` in try/except; write to a new `production_print_errors` table.
**Effort / Risk:** 🟢 S. 0.5 day.

### G-OPEN-4: Operator-configurable seasonal calendar ⭐
**Move:** `app/rms/workflow.py:248:SEASONAL_CALENDAR_2026` → `settings_kv['seasonal_calendar']` (list of `SeasonalEvent`).
**Already started in `seasonal.py:calendar_for_year()`** which exposes a year-shift — so the production-side handling is fine. Just need the persistence layer.
**Effort / Risk:** 🟢 S. 0.5-1 day.

### G-OPEN-5: Confidence-badge on production grilla ⭐
**Source:** `production.py:_forecast_confidence()` returns 0-100 per row. Already called.
**What's missing:** render it on the template.
**Effort / Risk:** 🟢 S. 0.5 day.

### G-OPEN-6: plan_accuracy → forecast_sales feedback loop ⭐
**Source:** `plan_accuracy.py` never read by `forecast_sales()`. Currently ships 404 in the chain.
**Effort / Risk:** 🟡 M. 1-2 days, with bias-clamp tests.

### G-OPEN-7: Maintenance middleware ⭐
**Pattern:** FloCafe `main/db.ts:23-35`. New `MaintenanceModeMiddleware` in `app/main.py` that returns 503 + Retry-After when active, marks KDS + ventas as requiring-not-maintenance.
**Effort / Risk:** 🟢 S. 1 day.

### G-OPEN-8: Drag-and-drop row reorder (Flutter POS)
**Pattern:** Flutter POS `chart_reorder.dart` + `product_reorder.dart` + `product_ingredient_reorder.dart` (3 different reorder widgets, all on `package:reorderables` style.
**Sazon:** production grilla has column-sort only.
**Effort / Risk:** 🟡 M. 1-2 days + a `user_pinned_products` table.

### G-OPEN-9: Refactor `produccion/_full.py` (L-ARCH-1 from v1)
**Source:** Even after sprint 5 split, `_full.py` is still 1,000+ lines.
**Target:** split into `_views/day.py`, `_views/week.py`, `_views/month.py`, `_views/manana.py`.
**Effort / Risk:** 🟠 L. 3-5 days.

### G-OPEN-10: Read `copilot.py` & `llm.py` to understand what's there
**Action:** Open and document. Some AI features are already in production.

### G-OPEN-11: Copy the audit module to more domains
**Pattern:** Sazon's `audit.py` + `audit_analytics.py` model every domain event. Apply the same to `pedido_status_audit` (in lieu of a queue — `resto-nestjs order_processing_queue`).
**Effort / Risk:** 🟢 S. 1 day.

### G-OPEN-12: Maintenance-type cron job for ingredient-perishable alerts
**Source:** Sazon already has `cost_freshness.py` + `demand_freshness.py:use-first flags`. Add a daily cron that emails operator with "use these ingredients first today" before the morning shift.
**Effort:** 🟢 S. 0.5 day + email channel.

---

## 3. PRODUCTION PLANNING REFINEMENTS (5 lessons)

### L-PLAN-V2-1: Poisson weekday model is shipped; document it externally
**Source:** `app/rms/restock_forecast.py` — per-weekday Poisson MLE, Wilson 95% CI, P95 stockout walk-forward, narrow trend blending.
**Lesson:** ⭐ **This is Sazon's strongest forecasting tool and operators probably don't know it.** Expose "Forecast accuracy" on `/inicio` as a card. Also expose the Wilson CI per ingredient as a `_forecast_confidence_pct` (already true from `_forecast_confidence`).

### L-PLAN-V2-2: trend is clamped [0.6, 1.6] — already correct, but document
**Source:** `demand_freshness.py:forecast_demand()` clamps `max(0.6, min(1.6, trend))`. Prevents catering outlier from doubling bread order.
**Lesson:** Document rationale in template.

### L-PLAN-V2-3: Plan accuracy feedback loop (G-OPEN-6)
**Lesson:** Already v1 L-PLAN-6. Same.

### L-PLAN-V2-4: Calendar fallback year-shift is shipped (`seasonal.py:calendar_for_year()`)
**Source:** `app/rms/seasonal.py:53-79`. For year != 2026 with `fallback_to_2026=True`, copies events to requested year.
**Lesson:** This means operator asking "what's the seasonality for 2027?" already gets a sensible answer. Move it from code to DB (G-OPEN-4) but **keep** the year-shift logic as a fallback when DB has no calendar for that year.

### L-PLAN-V2-5: batches endpoint can drive per-product print/export
**Source:** `production.py:_compute_batch_count` → ceil(qty / recipe.yield_qty).
**Lesson:** Print the "5 batches of medialunas = 5 trays" on the grilla footer. Operator should see.

---

## 4. STOCK & INGREDIENT (5 lessons)

### L-STOCK-V2-1: packaging flag is best-in-class
(Same as v1 L-STOCK-2.) **Lesson:** Tag this on marketing page.

### L-STOCK-V2-2: ingredient variants are unique
(Same as v1 L-STOCK-4.) **Lesson:** Document in `/recetas/<id>/editar` UI with "Alternativa preferida" badge.

### L-STOCK-V2-3: stock_status thresholds already operator-configurable
**Source:** `app/rms/stock_status.py` + constants in `app/rms/constants.py` (DEFAULT_STOCK_RATIO_CRITICO, etc.).
**Lesson:** ⭐ Close L-ARCH-7 (settings_kv) gap by surface-thresholding in the settings_catalog.html. Currently the operator probably configures via DB only.

### L-STOCK-V2-4: Poisson-driven P95 stockout forecast is the killer feature
**Source:** `restock_forecast.py` — projects forward day-by-day; returns "P95 you run out in 8 days".
**Lesson:** ⭐ Surface on `/inventario` as a "Running-out-soon" badge per ingredient row. Currently it's computing in the shadows.

### L-STOCK-V2-5: Packaging item path may need a separate inventory view
**Source:** `Ingredient.is_packaging` boolean. Cook may want to see "I have 50 bags today" separately from "I have 5kg flour".
**Lesson:** Add a filter chip group on `/inventario` for "Materias primas / Packaging" (mirrors filter chips on production grilla).

---

## 5. KDS / KOT / PRINTING (6 lessons — STILL OPTIONAL per L-NO-7)

### L-KDS-V2-1: Sazon has print path but no error visibility
**Source:** Sazon `app/rms/print_export.py` writes to disk. No error listener.
**Lesson:** G-OPEN-3 same as before. **Add `production_print_errors` table.**

### L-KDS-V2-2: Reprint KOT (`kot/direct/print/{order_id}/{type}` pattern from RestoPOS)
Same as v1 L-KDS-3. **Add "Reimprimir" button on `/produccion`.**

### L-KDS-V2-3: Maintenance middleware pattern (FloCafe `db.ts`)
Same as v1 L-KDS-7 + G-OPEN-7.

### L-KDS-V2-4: Multi-printer auto-select only matters if multi-station
Same as v1 L-KDS-4. Skip unless multi-baker.

### L-KDS-V2-5: Tablet view exists (`menu_tablet.html`)!
**Source:** Found during template scan — `app/templates/menu_tablet.html`. Already there.
**Lesson:** Read this template to see how Sazon addresses "operator moves around the counter" without building a KDS. Probably PDF-on-tablet or similar.

### L-KDS-V2-6: Kitchen Order Ticket as separate path from production worksheet
**Source:** URY + RestoPOS distinguish. Sazon merges into one "production" workflow.
**Lesson:** KOT is for "make this single item NOW (customer waiting)"; Production Worksheet is "what's the daily plan". They're different artifacts. If you add KDS, **don't reuse the production sheet** — build a separate flow.

---

## 6. SALES / POS (4 lessons)

### L-SALES-V2-1: Held cart exists (`ventas/held`)
(Same as v1 L-SALES-1.) Already shipped.

### L-SALES-V2-2: Held-cart hygiene
**Source:** `app/rms/held_sales.py` exists. Reading should reveal if held carts are auto-aged-out (Z-report style).
**Lesson:** Verify — adding age-out (e.g. discard after 24h) prevents stale holds.

### L-SALES-V2-3: Single-bill split-payment not relevant
(Same as v1 L-SALES-2.) Skip per Sazon operator model.

### L-SALES-V2-4: Subscription-driven orders exist
**Source:** `app/rms/suscripciones.py` + `invoicing.py`. Recurring delivery orders + auto-invoice.
**Lesson:** Already best-in-class. Document.

---

## 7. REPORTS / ANALYTICS (4 lessons)

### L-RPT-V2-1: daily P&L rollup
Same as G-OPEN-1.

### L-RPT-V2-2: accuracy dashboard underused
Same as v1 L-RPT-3 + G-OPEN-6.

### L-RPT-V2-3: food_cost_variance exists (`/reportes/food-cost-variance`)
**Source:** `app/routers/insights_derived.py:food_cost_variance` route.
**Industry match:** Renowned industry pattern — "theoretical vs actual" food cost per SKU, per week (Otter, Supy, MangoApps templates, Rinvy).
**Lesson:** Verify the theoretical (recipe × qty sold) vs actual (stockout × price) calc is on the page. If not, add a Food Cost Variance widget and push it to the operator weekly.

### L-RPT-V2-4: variance threshold should be per-category (industry pattern)
**Industry best-practice (Otter, restaurant-menu.org):**
- "0-2pp delta = well-controlled; 3-5pp = investigate; >5pp = systemic"
- Protein category carries naturally 4-6pp noise from trim/moisture
- Dry goods variance < 1pp is already a leak
- Per-category calibration > global threshold
**Sazon currently:** Likely uses a single global threshold (verify in `food_cost.py`).
**Lesson:** Add per-category multipliers (protein ×2.0, dairy ×1.5, dry ×0.8 baseline) to the food-cost-variance alert, with separate soft and hard bands (industry standard 1× and 2× std dev).
**Effort:** 🟡 M. 1-2 days. Per industry: this is THE most impactful single piece of analytics in any food POS. Bakery operator sees 1 protein recipe creep up 3pp → they investigate before it's a $384 waste problem.

---

## 8. ARCHITECTURE / CODE PATTERNS (6 lessons)

### L-ARCH-V2-1: Bcrypt + Supabase dual-auth exists
**Source:** `app/auth.py` + `app/auth_supabase.py`. obs note `observability.py:31-...`: "Order matters: the bcrypt backend writes ``local_user_id``; Supabase backend writes ``supabase_user_id``. The previous lookup only checked ``user_id`` / ``uid`` / ``user`` — fixed 2026-09-29 (see IMPROVEMENT_BACKLOG.md #41)."
**Lesson:** Document the dual-auth on `/login` for ops clarity.

### L-ARCH-V2-2: Service-per-aggregate pattern is consistent
All 116 modules follow `app/rms/<feature>.py` with one service per domain. Pure functions where possible.
**Lesson:** Keep this discipline. Avoid adding controller-side domain logic.

### L-ARCH-V2-3: Migration inverse is mandatory (rule 17)
**Source:** `app/rms/rollback.py` (SASKIA-209) + `archives/migration_*_pre.sql`.
**Lesson:** Don't relax. Add a CI test that every new migration has an inverse archive within 24h of merge.

### L-ARCH-V2-4: Audit module is mature
**Source:** `app/rms/audit.py` + `audit_analytics.py` + `observability.py:record_audit()`. Auto-fills request_id, wraps DB failures safely.
**Lesson:** Apply to pedido_status_audit (G-OPEN-11).

### L-ARCH-V2-5: production_scheduler.py is deprecated but referenced from one place
**Source:** `production_scheduler.py` docstring: "REMOVED in Fase 5 (2026-10-05). The only remaining caller was migrated to use `app.rms.production`'s new helpers."
**Lesson:** Verify the caller really is gone. If any import still lingers, delete.

### L-ARCH-V2-6: SSE / WebSocket — none anywhere
**Source:** grep across `app/`. No `sse`, no `websocket` anywhere.
**Lesson:** Confirms L-NO-7. KDS without SSE is possible (just polling). Maintain that KDS path.

---

## 9. UI / PAGE-LAYOUT (6 lessons)

### L-UI-V2-1: per-feature widgets split (still doing)
Same as v1 L-UI-1 + L-ARCH-1. The 2366-line produccion.html is the prime target.

### L-UI-V2-2: drag-and-drop pin products
Same as v1 L-UI-2 + G-OPEN-8.

### L-UI-V2-3: reloadable cards on `/inicio`
Same as v1 L-UI-3.

### L-UI-V2-4: filter chips on other list pages
Same as v1 L-UI-7.

### L-UI-V2-5: Tablet read-only view
**Source:** `app/templates/menu_tablet.html` exists. Read it.
**Lesson:** If it works for "what to bake today on iPad", you may not need a KDS at all. Read it first before committing.

### L-UI-V2-6: EOD anomalies auto-display
**Source:** `app/routers/eod.py:eod_run_anomalies` (POST).
**Lesson:** Make sure EOD shows anomalies NOT-JUST on operator click — auto on dashboard load.

---

## 10. OPS / COMPLIANCE / SAFETY (4 lessons)

### L-OPS-V2-1: WhatsApp integration phased (FloCafe)
Same as v1 L-OPS-1.

### L-OPS-V2-2: pre-billing checklist
Same as G-OPEN-2.

### L-OPS-V2-3: KOT error log
Same as G-OPEN-3.

### L-OPS-V2-4: Maintenance middleware
Same as G-OPEN-7 + L-KDS-V2-3.

---

## 11. SETTINGS / CONFIG (4 lessons)

### L-SET-V2-1: settings_kv is the canonical store
Same as v1 L-SET-1.

### L-SET-V2-2: settings_catalog.html — generic editor
**Source:** 887-line template for editing every key in `settings_registry.py`.
**Lesson:** Use this pattern for ANY new config. Add a registry entry, the form auto-renders.

### L-SET-V2-3: No agentic onboarding wizard (intentional)
**Lesson:** Same as v1 L-SET-5. **Skip.**

### L-SET-V2-4: Plug-in seasonal calendar to settings_kv
**Lesson:** G-OPEN-4.

---

## 12. INDUSTRY-PATTERN CROSS-CHECK (5 references)

Three SaaS bakery products and two restaurant-food-cost resources publish their patterns publicly. Sazon-vs-industry:

### Supply'd (UK bakery ERP — supplyd.co)
- **Pattern:** Wholesale orders + standing orders + forecasts → production plan → picking → delivery. **Big shift vs Sazon:** they think of "standing orders" as first-class. Sazon's `suscripciones` is the same idea but in-span.
- **Pattern:** Compare expected vs actual production, yield, waste, sales. Sazon has `plan_accuracy` for the first part, missing the second (yield% vs planned) and the third (waste% over time).
- **Pattern:** Batch and expiry tracking with FEFO. Sazon has `demand_freshness:shelf_life_days` but no batch-level `received_at` per ingredient.
- **Industry gap for Sazon:** **Batch-level FEFO tracking.** Could be implemented as `ingredient_batch (batch_id, ingredient_id, received_at, expiry_date, qty_on_hand, qty_consumed)`. Effort: 🟠 L. May not be needed if ingredient shelf life is short.

### CafeKit (cafekit.io — single-day-row bakery planning)
- **Pattern:** Each row shows: last-4 same-weekday avg, low-high range, how-steady (variance), preorders due today. Operator sets the number (system surfaces signals, doesn't decide).
- **Pattern:** **Banner** if preordered item is missing from the plan.
- **Pattern:** One-click "copy last week's same weekday" button (Sazon has this as `produccion_copy_last_week`).
- **Pattern:** Multi-location = each location is a column. **Skip per SASKIA-210.**
- **Pattern:** Export to PRIMS file format (a third-party tool). Not relevant.
- **Pattern:** Print-as-ship-ticket = baking worksheet as packing list. Sazon has this as `produccion_print`.
- **Industry gap for Sazon:** **Variance band ("how steady") on each row.** Sazon has `_forecast_confidence` (0-100). Rename to "Confianza" and add a "Rango histórico" (low-high) column.

### BakeOnyx (bakeonyx.ai — AI forecasting bakery)
- **Pattern:** "Add Event" for ad-hoc forecast nudge (Father's Day promo). Sazon's `SeasonalEvent` already supports this.
- **Pattern:** Per-product trend colored green/yellow/red confidence. Same — Sazon has `_forecast_confidence_pct`.
- **Pattern:** Recurring evaluation: "Forecast accuracy this week: 94%. Sheet cakes: overforecast by 1. Cupcakes: underforecast by 2." Sazon has `compute_plan_accuracy` but only on `/reportes/accuracy`, not surfaced daily.
- **Pattern:** Ingredient list as PDF/ship ticket. Same.
- **Pattern:** "Sunday" prep view — what to batch-Sunday for the week. Sazon's `weekly_template` is exactly this idea. Note: it's _per-day_ today, not _per-week-batch-prep_. **Consider upgrade.**

### JRNI/Rinvy (`rinvy.app/docs/menu-items/food-cost-targets`)
- **Pattern:** Per-menu-item `target food cost %`. Sazon has `margin_tier.py` which is operator-configurable tiers (above 30% = healthy). Already on par.
- **Pattern:** Alert when actual > target. Auto-push 6AM, once per dish at each whole percent. **Sazon doesn't push**; only shows in `/inicio`.
- **Industry gap for Sazon:** **Push/notification on food-cost drift.** Effort: 🟢 S. Reuse `notify.py` (Telegram already wired) + food_cost watcher.

### Restaurant Menu (restaurant-menu.org theoretical-vs-actual threshold tuning)
- **Pattern:** **Per-category multipliers** (protein 2.0, dairy 1.5, dry 0.8) for the food-cost alert stddev.
- **Pattern:** **Soft band (mean + 1.0·σ·cat)** logs; **Hard band (mean + 2.0·σ·cat)** pages with 24h SLA.
- **Pattern:** **Two-tier routing** — don't merge them.
- **Pattern:** **Cold-start seeded baseline** — 14-30d history before paging; show "baseline_ready=False" distinctly.
- **Pattern:** **Hard-alert gated on day-close**: don't fire if `recon_status != "COMPLETED"`.
- **Pattern:** Unbiased std (ddof=1), not population std. Py and SQL difference matters.
- **Industry gap for Sazon:** Add per-category multiplier table; soft vs hard bands; gating on EOD. Effort: 🟡 M. Add `food_cost_alert` table with `severity ∈ {soft, hard}` and `triggered_at`, `resolved_at`. Tests for stddev with ddof=1.

---

## 13. WHAT NOT TO COPY (8 forced exclusions)

Same as v1. Restated because the formatting matters:

- ❌ Multi-tenant (SASKIA-210)
- ❌ Mobile app (operator at laptop)
- ❌ Self-order kiosk (no shared customer interface)
- ❌ Payments integration (cash + informal)
- ❌ Multi-locale i18n (Spanish-vos only)
- ❌ Worker/queue system (single-process)
- ❌ Live KDS without explicit request (tablet view exists)
- ❌ Monorepo split (migrations under one roof)

### New exclusion (v2): don't add closing-shift day-close alarm if unreconciled

Industry pattern (restaurant-menu.org): hard alerts gated on EOD recon. **Sazon already has this** (`eod_closed.assert_day_open_or_raise`). Don't relax — keep the gate even when adding real-time Slack alerts.

---

## 14. SAZON DECISION LOG (canonical)

Same as v1. Plus 6 new entries found:

| Decision | Date | Source |
|---|---|---|
| Use Poisson weekday forecast, not flat avg | 2026 | `restock_forecast.py` (BACKLOG #5) |
| Demand = base × weekday × trend, clamp [0.6, 1.6] | 2026-09-24 | `demand_freshness.py` |
| Substitution engine = ingredient_intel + price delta + tags | 2026-09-24 | `demand_freshness.py` §10 |
| Fiado ledger is signed, FIFO aging, idempotent pago | 2026 | `fiado.py` Fase 2 |
| Customer merge reassigns sales+pedidos atomically | 2026 | `customer_merge.py` P1-B4 |
| Menu OCR uses GLM vision with anti-hallucination prompt | 2026 | `menu_ocr.py` Fase 3 |
| Notification channel is Telegram-first; Sentry→Telegram mirror | 2026-10-07 | `notify.py` |
| HACCP defaults seeded per Res S.G. N° 213/2019 | founding | `haccp_seed.py` |
| Use Loguru contextualize for request-scoped logging | 2026 | `observability.py` |
| Production_scheduler deprecated in Fase 5 | 2026-10-05 | `production_scheduler.py` |

---

## 15. APPENDICES

### Appendix A — Full module list (115+ in `app/rms/`)

```
accounting, analytics, audit, audit_analytics, backup, bootstrap, cash,
catalogs, categories, charts, cierre, clock, config, constants, copilot,
cost_freshness, costing, cotizador, csrf, customer_dietary, customer_merge,
customers, date_presets, db, db_dialect, demand_freshness, dependencies,
derived_intel, display, eod_closed, eod_completions, errors, fiado,
food_cost, forecast, haccp_seed, held_sales, ingredient_intel, insights,
inventory_intel, invoicing, llm, loyalty/, maintenance, margin_tier,
market_intel, menu_ejecutivo, menu_engineering, menu_inventory, menu_ocr,
messages, metrics, migrations, models, models_legacy, money, nav,
notifications, notify, observability, perf, plan_accuracy, price_history,
prime_cost, product_price_history, product_similarity, production,
production_demand, production_scheduler, profitability/,
public_tokens, rate_limit, ready_static, recipe_intel, recipes_consolidated,
refunds, reorder, reorder_supplier_prices, restock_forecast, sales_intel,
sales/, schema_postgres, schemas, seasonal, security_headers, seed/,
seed_market_prices, services/, session_lifecycle, settings,
settings_original, settings_runtime, static_paths, stock_ledger,
stock_status, storage, storage_types, streaming_csv, supplier_history,
supplier_prices, tag_algebra, tagging/, units, upload_limits, validation,
variants, waste, workflow, AGENTS.md, __init__.py
```

### Appendix B — Competitor route inventories (consolidated)

(Full FloCafe 28-files-150-routes already in v1. Now adding the latest research:)

**RestoPOS 117 routes** (`routes/tenant.php`) — covered in v1.

**URY doctypes — full 45 + alias map** — covered in v1.

**Flutter POS — full file inventory** — covered in v1.

### Appendix C — TastyIgniter extension model summary

22 separate repos, each a Laravel package:
- `ti-ext-api` — REST + JSON:API endpoints
- `ti-ext-local` — Locations/Geocoder
- `ti-ext-payregister` — Payments base
- `ti-ext-coupons` — Discounts/coupons
- `ti-ext-user` — Roles/permissions
- Plus ~17 more (menus, themes, Stripe, Mollie, etc.)
**Sazon decision:** Single monorepo, no extensions. Skip.

### Appendix D — Industry references glossary

- **PRIMS** — A third-party baking production tool. CafeKit integrates with it via CSV export.
- **FEFO** — First-Expired First-Out. Standard for perishable batches (Supply'd pattern).
- **Standing orders** — Recurring weekly/monthly customer orders (Sazon's `suscripciones`).
- **Theoretical food cost** — recipe × qty sold (Otter/Supply'd standard).
- **Actual food cost** — beginning_stock + purchases − ending_stock (Otter/Supply'd standard).
- **Variance** = actual - theoretical, in either dollars or percentage points.
- **ddof=1** — Bessel-corrected sample stddev (divide by N-1). Industry-correct for small samples.

### Appendix E — Reference sources for industry patterns

- Supply'd: supplyd.co/industries/bakeries/ (UK bakery ERP)
- CafeKit: cafekit.io/bakery-production-planning (single-day-row bakery planning)
- BakeOnyx: bakeonyx.ai/features/demand-forecasting (AI forecasting)
- Rinvy: rinvy.app/docs/menu-items/food-cost-targets (per-item food-cost alerts)
- Otter: tryotter.com/blog/restaurant-tips/food-cost-variance
- restaurant-menu.org: threshold-tuning-for-alerts
- Supy: supy.io/blog/food-cost-variance-control
- JMJSoft: jmjsoft.com/solutions/bakery.php
- BakeOnyx baking management: bakeonyx.ai

---

## TOP-OF-PAGE — what to ship next (corrected from v1)

**Sprint Z — close the genuine 5-day backlog**:

1. ⭐ **L-RPT-V2-1 / G-OPEN-1: Daily P&L rollup** (🟡 M / 🟢 low) — biggest single gap
2. ⭐ **L-OPS-V2-2 / G-OPEN-2: Pre-billing checklist (URY pattern)** (🟡 M / 🟢 low)
3. ⭐ **L-RPT-V2-4: Per-category variance threshold + soft/hard bands** (🟡 M / 🟢 low) — industry best-practice
4. ⭐ **L-KDS-V2-1 / G-OPEN-3: KOT error log** (🟢 S / 🟢 low)
5. ⭐ **G-OPEN-4: Seasonal calendar → settings_kv** (🟢 S / 🟢 low)
6. ⭐ **G-OPEN-5: Confidence-badge on grilla** (🟢 S / 🟢 low)
7. ⭐ **G-OPEN-7 / L-OPS-V2-4: Maintenance middleware** (🟢 S / 🟢 low)

**Sprint A — UX polish (1 week)**:
8. ⭐ **G-OPEN-6: plan_accuracy → forecast_sales feedback** (🟡 M / 🟡 med) — biggest analytical win
9. ⭐ **G-OPEN-8 / L-UI-V2-2: drag-and-drop product pin on grilla** (🟡 M / 🟢 low)
10. ⭐ **G-OPEN-12: Use-first ingredient email before shift** (🟢 S / 🟢 low)
11. ⭐ **L-STOCK-V2-4: P95 stockout badge on /inventario** (🟢 S / 🟢 low)
12. ⭐ **G-OPEN-11: pedido_status_audit append-only** (🟢 S / 🟢 low)

**Sprint B — split the monolith (1-2 weeks)**:
13. ⭐ **G-OPEN-9 / L-UI-V2-1: Refactor `produccion/_full.py` into `_views/day.py`, `_views/week.py`, etc.** (🟠 L / 🟡 med) — biggest architectural cleanup

**Skip-list** (10 items from v1 + new v2 entries — Section 13).
