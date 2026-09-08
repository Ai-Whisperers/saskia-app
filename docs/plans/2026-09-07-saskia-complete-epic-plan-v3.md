# Saskia RMS — Complete Epic Plan (v3, "Gem Project" Edition)

**Date:** 2026-09-07
**Author:** Iván van der Pol (via Hermes)
**Status:** Executable; supersedes 50h critical-path plan
**Scope:** Full remaining backlog + 25 new epics covering every relevant area of work, every wishlist feature, every seed-able insight, every prep-able data surface.
**Philosophy:** Saskia is Iván's sister. No time budget. This is a gem project — every detail polished, every edge case handled, every insight surfaced, every prep done so conversion is zero-friction.

## How to read this

**25 epics**, organized into 6 phases. Each epic has:
- **Why** (business outcome)
- **Stories** (user-visible deliverables, formatted `E#.S#`)
- **Tasks** (engineering tasks, numbered)
- **Effort** (hours, by task + total)
- **Depends on** (other epics)
- **Acceptance** (definition of done)
- **Refs** (related wishlist files)

Tickets use format `SASKIA-NNN`. Epic+story codes: `E3.S1` = Epic 3, Story 1. File naming for tickets: `SASKIA-NNN-<short-slug>.md`. Tickets live in `docs/tickets/` once created.

## Phase map

| Phase | Name | Epics | Status |
|---|---|---|---|
| P0 | Round 1 close-out + Fase 1.5 hardening | E1-E5 | 41/50h done; 9h carry |
| P1 | Data + insights | E6, E7, E8 | new |
| P2 | Operator UX + workflow | E9, E10, E11, E12 | new |
| P3 | Customer + retention (Fase 2) | E13, E14 | new |
| P4 | Scale + multi-tenant readiness | E15, E16 | new |
| P5 | Polish + future-facing | E17-E25 | new |

**Total scope:** 25 epics, ~400h estimated, no cap. Saskia is Iván's sister — gem project means polished.

---

# PHASE 0 — Round 1 close-out (carried over from 50h plan)

## Epic 1 — Round 1 close-out ✅ COMPLETE

- E1.S1 installer patches ✅ DONE (`94f9a24`, `6fef4a2`)
- E1.S2 Round-1 feedback sweep + log ✅ DONE
- E1.S3 CF tunnel rotation runbook ✅ DONE (`0286929`)

---

## Epic 2 — Make deploy CI-catchable ⚠️ 3/4 done

- E2.S1 15 fail-closed regression tests ✅ DONE (`04c6aa7`)
- E2.S2 Real Postgres test infra (testcontainers) ⏳ OPEN
- E2.S3 `aiw-saskia migrate` idempotent ✅ DONE (`b0f06ef`)
- E2.S4 refresh.sh autodetects cwd + CI migrate smoke ✅ DONE (`a82b7be`)

### E2.S2 — Real Postgres test infra (testcontainers)
**Why:** 5 production hotfixes in 2026-09-04 happened because we couldn't reproduce hosted data shape locally. A PG testcontainer would have caught 4/5.

**Stories:**
- E2.S2.1: `testcontainers[postgresql]` dep in pyproject.toml
- E2.S2.2: `pg_engine` + `pg_session_factory` fixtures
- E2.S2.3: Migrations applied on first connection (not per-test)
- E2.S2.4: Tag regression tests with `@pytest.mark.pg`

**Tasks:**
1. Add `testcontainers[postgresql] ~= 4.0` to dev deps
2. Write `tests/conftest_pg.py` with pg_engine, pg_session_factory (boots container, runs `init_db()`)
3. Tag `test_hotfix_regressions.py` with `@pytest.mark.pg`
4. CI step runs `-m pg` after main suite
5. Test: PG roundtrip of migrate + audit_log + audit middleware
6. Test: JSONB column works (the 2026-09-04 hotfix path)

**Effort:** 4h
**Depends on:** Docker available in CI
**Acceptance:** `pytest -m pg` boots real PG, all 15 regression tests pass

---

## Epic 3 — Harden runtime ⚠️ 3/4 done

- E3.S1 Audit log ✅ DONE (`5903d26`)
- E3.S2 Rate-limit on /login ✅ DONE (`85a32d4`)
- E3.S3 SecurityHeadersMiddleware ✅ DONE (`0286929`)
- E3.S4 /healthz/db runbook + UptimeRobot wiring ⏳ OPEN

### E3.S4 — /healthz/db runbook + UptimeRobot
**Why:** `/healthz/db` exists in code but no operator doc, no UptimeRobot config captured. UptimeRobot 5-min probe catches DB outages before customers do.

**Stories:**
- E3.S4.1: `/healthz/db` returns 200 + JSON `{db, schema_version, migrations_pending, last_audit_at}`
- E3.S4.2: Runbook `docs/operations/uptime-monitoring.md` with UptimeRobot config

**Tasks:**
1. Enhance `/healthz/db` to return structured JSON
2. Write `docs/operations/uptime-monitoring.md`
3. Document WhatsApp Evolution alert routing
4. Audit log every `/healthz/db` failure
5. Test: JSON shape + schema_version reflects CURRENT_SCHEMA_VERSION

**Effort:** 1.5h
**Acceptance:** `/healthz/db` returns JSON; runbook exists; alert route documented

---

## Epic 4 — Fase 1.5 UX polish ⏳ 0/4 done

### E4.S1 — Round-2 items triage + ship
**Why:** First 30 days of Fase 1 will surface 5-10 small bugs. Make triage cheap.

**Stories:**
- E4.S1.1: Round-2-NOTES.md template
- E4.S1.2: Triage workflow doc (raw → triaged → shipped/rejected)
- E4.S1.3: Cap Round-2 at 12h

**Tasks:**
1. Create `installer/ROUND-2-NOTES.md` template
2. Write `docs/operations/round-2-triage-process.md`
3. Add Round-N feedback label to GitHub templates
4. Define "ship-it" criteria (≤2h fix + clear repro + 1 acceptance test)

**Effort:** 4h setup + 8h buffer

### E4.S2 — daily_sales_series() + SVG chart
**Why:** Dashboard shows totals but no trend. A daily-trend SVG is the highest-signal visualization for a small business.

**Stories:**
- E4.S2.1: `daily_sales_series(session, days=30)` returns `[{date, total_gs, sale_count, top_product_id}]`
- E4.S2.2: SVG bar chart, server-rendered (no JS)
- E4.S2.3: Toggle: 7d / 30d / 90d / this month / last month

**Tasks:**
1. Add `daily_sales_series()` to `app/services/reports.py`
2. Add `top_product_id_for_day()` helper
3. Write `app/templates/components/sales_chart.svg.j2`
4. Wire to dashboard with period toggle
5. Tests: data shape, 0-sales day, month boundary

**Effort:** 4h

### E4.S3 — /excel/exportar?period=current_month
**Why:** Monthly close requires export. Currently dumps everything; she wants current month by default.

**Stories:**
- E4.S3.1: `period` query param: `today | current_week | current_month | last_month | last_30 | all` (default `current_month`)
- E4.S3.2: Export includes period header sheet

**Tasks:**
1. Update `app/routers/excel_io.py:exportar` to accept `period`
2. Add period→date-range resolver
3. Header sheet with period name + range
4. Tests for each period + Feb 28-29 edge case

**Effort:** 3h

### E4.S4 — Mobile tweaks
**Why:** Saskia uses phone at shop. Current CSS works; a few tweaks for thumb-friendly buttons + bottom-nav help.

**Stories:**
- E4.S4.1: Touch targets ≥44px
- E4.S4.2: Bottom-nav on mobile (≤768px)
- E4.S4.3: Sale-entry single-hand usable

**Tasks:**
1. Audit interactive elements; bump padding to 44px
2. `@media (max-width: 768px)` rules for bottom-nav
3. Reflow sale-entry form with sticky bottom button bar
4. Lighthouse mobile audit

**Effort:** 4h

---

## Epic 5 — Tracking infrastructure ⚠️ 3/4 done

- E5.S1 Wishlist scaffold ✅ DONE (`8126827`)
- E5.S2 STATUS.html.tmpl refresh in CI ⏳ OPEN
- E5.S3 CHANGELOG discipline gate ✅ DONE (`a82b7be`)
- E5.S4 Issue templates ✅ DONE (`4b68d0d`)

### E5.S2 — STATUS.html.tmpl update + refresh.sh in CI
**Why:** Dashboard doc is stale. Auto-refreshing on every CI run keeps it as one-glance project health.

**Stories:**
- E5.S2.1: STATUS.html.tmpl shows current test count, coverage, last deploy SHA, open wishlist count
- E5.S2.2: refresh.sh runs in CI on every main push

**Tasks:**
1. Update `docs/operations/dashboard/STATUS.html.tmpl` with new sections
2. Add `refresh.sh` invocation to `.github/workflows/ci.yml`
3. Generate `docs/operations/dashboard/index.html` as artifact
4. Tests: template renders, all data fields present

**Effort:** 1.5h

---

# PHASE 1 — Data + Insights

## Epic 6 — Realistic demo data seed ⭐⭐⭐

**Why:** Saskia opens the app → sees ~20 products, ~12 recipes, ~200 historical sales. No blank-state anxiety. Instant demo value. Zero-friction conversion.

**Stories:**
- E6.S1: 30 universal bakery ingredients
- E6.S2: 12 recipes with standard baking ratios
- E6.S3: 20 products tied to recipes (sale_price_gs, prep_minutes, category)
- E6.S4: 90-day synthetic sales (~200, weekday/weekend skew, payday spikes)
- E6.S5: Stock moves tied to sales + realistic `min_stock` per ingredient
- E6.S6: Demo user (bcrypt path) `demo@herbus.local / demo1234`
- E6.S7: 1 voided_sale example + 1 encargo example (filter UI demo)
- E6.S8: Audit log seeded with `system.startup` + `seed.complete`
- E6.S9: `aiw-saskia seed [--reset]` CLI subcommand
- E6.S10: Seed report (counts: {ingredients: 30, recipes: 12, products: 20, sales: 200})

**Tasks:**
1. `app/rms/seed.py` with `seed_demo_data(engine, *, overwrite=False) -> SeedReport`
2. 30 ingredients: flour, sugar, butter, eggs, milk, salt, yeast, baking_powder, vanilla, cinnamon, cream_cheese, condensed_milk, dulce_de_leche, coconut, chocolate_chips, walnuts, raisins, oil, water, cornstarch, gelatin, lemon_zest, orange_zest, honey, almond_flour, cocoa_powder, baking_soda, powdered_sugar, strawberries, blueberries
3. 12 recipes: muffin_vainilla, muffin_chocolate, muffin_nueces, cheesecake, hojaldre, appeltaart, tompoezen, oliebollen, babka, stroopwafel, pan_lactal, facturas
4. 20 products: each product has category, sale_price_gs, prep_minutes
5. ~80 recipe_lines: standard baking ratios per recipe
6. Synthetic sales generator: 200 sales over 90 days, weekend +40%, morning +30%, occasional 3x spikes
7. Stock moves auto-tied to sales
8. Demo user with bcrypt password
9. 1 voided_sale (notes: "cliente cambió de opinión") + 1 encargo (notes: "para cumpleaños, recoger 16h")
10. Audit log: 1 `system.startup`, 1 `seed.complete`
11. Add `aiw-saskia seed [--reset]` CLI in `app/rms/main.py`
12. Tests: idempotency, reset, seed report counts, no PII

**Effort:** 6h
**Acceptance:** `aiw-saskia seed` populates fresh DB; `--reset` destructive-safe; tests cover all paths

---

## Epic 7 — Real-Drive-shape Excel fixture ⭐⭐

**Why:** Saskia keeps editing Drive Excel after import (v1 plan §11). Fixture mirroring her real Drive shape catches merge regressions.

**Stories:**
- E7.S1: `tests/fixtures/herbus_demo.xlsx` (6 sheets, ~200 rows, polymorphic Recipe → RecipeLine resolution)
- E7.S2: `tests/fixtures/herbus_mini.xlsx` (6 sheets, ~10 rows, fast path)
- E7.S3: Edge-case fixtures: renamed_sheets, extra_rows, with_formulas, hidden_sheets
- E7.S4: Import tests against all 5 fixtures (additive merge, no-wipe, match-by-name)
- E7.S5: Verify polymorphic Recipe → RecipeLine resolution by name

**Tasks:**
1. Build `tests/fixtures/herbus_demo.xlsx` (binary commit, openpyxl script)
2. Build `tests/fixtures/herbus_mini.xlsx`
3. Sheet structure: Ingredientes / Recetas / Lineas / Productos / Ventas / StockMoves
4. Build 4 edge-case fixtures
5. Tests for each edge case (graceful merge or skip, never crash)
6. CI: ensure fixtures committed in LFS if >1MB

**Effort:** 4h
**Depends on:** E6 (knows seed shape)
**Acceptance:** `test_import_xlsx.py` exercises all 5 fixtures

---

## Epic 8 — Operational analytics dashboard ⭐⭐⭐

**Why:** 90 days of data → answer 10 questions Saskia asks daily. Highest-ROI dashboard work.

**Stories:**
- E8.S1: Stock turnover ratio per ingredient
- E8.S2: Days-of-stock remaining (predicts stockouts 7-14 days out)
- E8.S3: Dead-stock report (last_consumed_at > 30d)
- E8.S4: Margin erosion alerts (purchase_price change vs sale_price change)
- E8.S5: Day-of-week heatmap (avg sales per weekday)
- E8.S6: Top-margin products by period
- E8.S7: Ingredient concentration (top 5 cost share)
- E8.S8: Recipe complexity + cost-per-prep-minute

**Tasks:**
1. Add `Ingredient.last_consumed_at` (schema v3)
2. Add `Ingredient.purchase_price_updated_at` (schema v3)
3. Add `Recipe.prep_minutes` (schema v3)
4. `app/services/analytics.py`: stock_turnover, days_of_stock, dead_stock
5. margin_erosion_alerts() → list of {product_id, old_margin, new_margin, ingredient_name, price_delta_pct}
6. day_of_week_heatmap(days=90) → 7-element array
7. top_margin_products(period, limit=10)
8. ingredient_concentration() → top 5 by cost share
9. recipe_complexity() → list of {recipe_id, score, cost_per_prep_minute}
10. Wire 8 panels into `app/routers/dashboard.py` (`/analisis`)
11. Tests for each query (empty, normal, edge cases)

**Effort:** 8h
**Depends on:** E6 (realistic data) + E3.S1 (audit log for change tracking)
**Acceptance:** `/analisis` shows 8 panels, each backed by tests

---

# PHASE 2 — Operator UX + Workflow

## Epic 9 — Tags + filtering ⭐⭐

**Why:** Tags are highest-leverage way to add segmentation without schema redesign. Filters = 80% of operator productivity.

**Stories:**
- E9.S1: `tag` table + 3 M:N tables (product_tag, ingredient_tag, recipe_tag)
- E9.S2: Tag picker in forms (multi-select autocomplete)
- E9.S3: 15 starter tags (5 product, 5 ingredient, 5 recipe)
- E9.S4: Filter UI on Ventas (date range, product multi-select, time-of-day, qty, amount)
- E9.S5: Filter UI on Inventario (stock status, supplier, last purchase, cost band, tags)
- E9.S6: Filter UI on Recetas (margin tier, component count, has sub-recipe, cost-per-portion)
- E9.S7: Filter UI on Productos (category, active, has recipe, margin %)
- E9.S8: "Export filtered" button on each filtered page

**Tasks:**
1. New tables: `tag (id, name, tag_type, color)`, `product_tag`, `ingredient_tag`, `recipe_tag` (schema v3)
2. Tag CRUD endpoints
3. Tag picker Jinja2 component
4. Wire picker into product/ingredient/recipe forms
5. Seed 15 starter tags (vegano, sin-gluten, sin-lactosa, premium, festivo, perecedero, alergeno:gluten, alergeno:lactosa, alergeno:frutos-secos, precio-volatil, sub-receta, temporada, alto-costo, encargo, devolución)
6. `?date_from=&date_to=&product_id=&time_of_day=&qty_min=&amount_min=` on Ventas
7. `?stock_status=&cost_band=&tag_id=` on Inventario
8. `?margin_tier=&has_sub_recipe=&cost_min=&cost_max=` on Recetas
9. `?category=&is_active=&has_recipe=&margin_min=` on Productos
10. "Export filtered" button on each page
11. Tests for each filter combination

**Effort:** 12h
**Acceptance:** All 4 main pages filterable; tags first-class on 3 entities

---

## Epic 10 — Easy settings ⭐⭐

**Why:** Most "small things that annoy daily" are configuration knobs. Surface the 30 most common ones.

**Stories:**
- E10.S1: `setting` table (key, value, scope, updated_at)
- E10.S2: Settings UI (`/settings`) with sections
- E10.S3: Currency, decimal handling, date format
- E10.S4: Business hours (day_start_hour, day_end_hour, operating_days)
- E10.S5: Inventory defaults (min_stock_strategy, critical_pct, overstock_days, spoilage_lead_days)
- E10.S6: Dashboard defaults (default_period, currency_in_reports, auto_refresh)
- E10.S7: Sales entry (default_unit, repeat_last_sale, customer_name_required, notes_required_on_void)
- E10.S8: Backup (auto_backup_time, local_retention_days, r2_retention_policy)
- E10.S9: Session (session_timeout, idle_timeout, login_language)
- E10.S10: Demo mode banner (visible when logged in as demo user)

**Tasks:**
1. New `setting` table (schema v3) — single-row-per-key, JSON value
2. Settings page UI with sections + form
3. Apply settings everywhere (sales, recipes, dashboard)
4. Defaults seeded at first run
5. Tests for setting read/write + apply logic

**Effort:** 8h
**Depends on:** E9 (shares pattern)
**Acceptance:** Operator can change 30 settings via UI without touching code

---

## Epic 11 — Mobile + offline ⭐

**Why:** Saskia uses phone at shop. Internet drops happen; offline-first is real ask.

**Stories:**
- E11.S1: PWA manifest + service worker
- E11.S2: Bottom-nav mobile layout
- E11.S3: Offline sale entry (queue → sync on reconnect)
- E11.S4: Touch-friendly buttons (≥44px) — extends E4.S4

**Tasks:**
1. Add `manifest.json` + service-worker.js
2. Cache app shell on install
3. Queue offline mutations in IndexedDB
4. Sync queue on `online` event
5. Mobile-first CSS audit
6. Tests: queue persists across reload, sync dedupes by client-generated UUID

**Effort:** 16h
**Depends on:** E4.S4
**Acceptance:** App loads offline, sales queue and sync on reconnect

---

## Epic 12 — Operator workflow tools ⭐⭐

**Why:** Daily rituals (open, mid-day, close) are scripted. Bake them into the app.

**Stories:**
- E12.S1: End-of-day checklist (auto-generated):
  1. Reconciliar caja
  2. Marcar ingredientes que se vencieron (merma)
  3. Revisar alertas de stock bajo
  4. Hacer backup
  5. Imprimir reporte del día
- E12.S2: Supplier order template (print PDF "Lo que hay que pedir esta semana")
- E12.S3: Recipe costing worksheet (preview margin when sale price changes)
- E12.S4: Manual snapshot button "Create backup now" in operator panel
- E12.S5: Operator dashboard `/admin` (audit log, settings, backup, EOD checklist)

**Tasks:**
1. New `eod_checklist_run` table (date, items_completed, signed_off_at, notes)
2. EOD checklist UI component (5 items + checkboxes)
3. Supplier order PDF template (groups low-stock ingredients by supplier, qty suggested)
4. Recipe costing worksheet UI (slider for hypothetical sale_price)
5. Manual backup button (calls existing r2_backup + local backup)
6. `/admin` route (operator-only) with all the above
7. Tests for each workflow tool

**Effort:** 12h
**Depends on:** E10 (settings), E3.S1 (audit)
**Acceptance:** Operator opens app, sees EOD checklist, can do backup in 1 click

---

# PHASE 3 — Customer + Retention (Fase 2)

## Epic 13 — Customer directory + loyalty ⭐⭐⭐

**Why:** Walk-in repeat customers are real revenue. Even a simple "remember last 10 customers" unlocks targeted prep + loyalty.

**Stories:**
- E13.S1: `customer` table (id, name, phone, email, notes, tags, created_at, last_seen_at)
- E13.S2: Customer picker on sale entry (autocomplete by name or phone)
- E13.S3: Customer detail page (purchase history, lifetime spend, last visit, tag list)
- E13.S4: Top customers by spend (period)
- E13.S5: Customers inactive > 30 days (reactivation list)
- E13.S6: Loyalty points (1 point per 10,000 Gs. spent; redeem at 100 points = 5% off)
- E13.S7: Add `customer_id` to `sale` table (schema v4)
- E13.S8: CSV import for customer list (from WhatsApp contacts export)

**Tasks:**
1. New tables: `customer`, `customer_tag`, `loyalty_ledger (customer_id, delta, reason, sale_id)` (schema v4)
2. Customer CRUD routes
3. Customer picker component (autocomplete)
4. Customer detail page
5. Top customers query (period filter)
6. Inactive customers query
7. Loyalty points calculation in sale entry
8. Loyalty redemption flow (UI + ledger entry)
9. CSV import (validate phone format)
10. Tests for each path

**Effort:** 16h
**Depends on:** E9 (tag infra)
**Acceptance:** Customer picker works on sale entry; loyalty ledger is accurate

---

## Epic 14 — Customer-facing features ⭐⭐

**Why:** Once you have customers, give them reasons to come back.

**Stories:**
- E14.S1: WhatsApp bot (Twilio or Evolution API) — daily summary + reorder ping
- E14.S2: Online ordering webhook (WhatsApp Business "what do you want?" → confirm → prep)
- E14.S3: Pickup time slot booking (calendar with 30-min slots)
- E14.S4: Subscription boxes (weekly muffin basket for offices)
- E14.S5: Receipt printer integration (ESC/POS, 58mm/80mm thermal)
- E14.S6: Kitchen printer (separate station) — prints "2 docenas muffins, sin azúcar"

**Tasks:**
1. WhatsApp bot: message templates for daily summary, reorder ping
2. Twilio/Evolution integration with Evolution API (already wired for AIW team)
3. Online order webhook endpoint + confirmation flow
4. Pickup slot model + booking page
5. Subscription model (frequency, items, customer_id, next_delivery)
6. Receipt printer: python-escpos integration, ESC/POS commands
7. Receipt template: header (logo + RUC), line items, total, IVA breakdown, footer
8. Kitchen ticket template: 58mm, only line items + customer notes
9. Tests for each integration (mock the printer, mock the WhatsApp API)

**Effort:** 24h
**Depends on:** E13 (customer directory)
**Acceptance:** WhatsApp bot sends daily summary; receipt printer prints on sale; kitchen ticket prints

---

# PHASE 4 — Scale + Multi-tenant readiness

## Epic 15 — Multi-tenant schema + isolation ⭐⭐

**Why:** Saskia is the only customer today, but if a future engagement materializes, multi-tenant is the only way to scale without a rewrite.

**Stories:**
- E15.S1: Add `tenant_id` to all data tables (schema v5)
- E15.S2: Login routes to correct tenant (Subdomain or path-based)
- E15.S3: All queries include `WHERE tenant_id = ?` (SQLAlchemy event listener)
- E15.S4: Backups per-tenant (R2 path: `tenants/{tenant_id}/...`)
- E15.S5: Tenant settings page (RUC, logo, currency, timezone)
- E15.S6: Migration from single-tenant → multi-tenant (data migration for existing single-tenant installs)

**Tasks:**
1. Add `tenant` table (id, slug, name, ruc, logo_url, currency, timezone, created_at)
2. Add `tenant_id` to all data tables (schema v5)
3. SQLAlchemy event listener to enforce tenant filter
4. Login flow resolves tenant from subdomain or path
5. R2 backup path includes tenant_id
6. Tenant settings UI
7. Migration script: assign all existing rows to default tenant
8. Tests: cross-tenant queries return empty; backup/restore per-tenant

**Effort:** 16h
**Depends on:** Nothing (do this before more customers onboard)
**Acceptance:** Adding a second tenant doesn't bleed data; backup per-tenant works

---

## Epic 16 — Performance + scale infrastructure ⭐

**Why:** Once you're multi-tenant, you have to be fast enough that nobody notices the database is shared.

**Stories:**
- E16.S1: Connection pooling (PgBouncer for hosted mode)
- E16.S2: Query performance dashboard (slow query log + index advisor)
- E16.S3: Redis cache for dashboard queries (TTL 60s)
- E16.S4: Read replicas for analytics (E8 queries don't hit primary)
- E16.S5: Backup encryption rotation (key rollover without data loss)
- E16.S6: Disaster recovery drill (quarterly restore-from-backup test)

**Tasks:**
1. Configure PgBouncer in `docker-compose.hosted.yml`
2. Slow query log + Grafana panel for p95 latency
3. Redis cache layer for `daily_sales_series`, `top_margin_products`, etc.
4. Read replica routing for analytics queries
5. Backup key versioning (3 keys, last-N-encrypted)
6. Quarterly DR drill script (boots fresh DB, restores latest backup, runs smoke tests)
7. Tests: cache invalidation, replica routing

**Effort:** 20h
**Depends on:** E15 (multi-tenant)
**Acceptance:** p95 query latency <50ms; DR drill passes quarterly

---

# PHASE 5 — Polish + future-facing

## Epic 17 — Accounting + tax ⭐⭐

**Why:** Saskia's accountant needs clean monthly reports. IVA (10% in Paraguay) on every sale.

**Stories:**
- E17.S1: IVA field on `sale` (5% or 10% per product)
- E17.S2: `RUC` setting (Paraguayan tax ID, printed on receipts)
- E17.S3: Daily cash reconciliation report (expected vs actual)
- E17.S4: Monthly close bundle (PDF for accountant: P&L, IVA breakdown, expense summary)
- E17.S5: Expense tracking (rent, salaries, supplier invoices — opposite side of income)
- E17.S6: `IRP` (personal income tax) annual report (if Saskia runs as sole proprietor)

**Tasks:**
1. New tables: `iva_rate`, `expense (date, category, amount, supplier, notes, receipt_url)` (schema v5)
2. IVA rate per product (5% / 10%)
3. RUC setting (E10)
4. Daily reconciliation: shift_open_amount + cash_counted + expected_total → diff
5. Monthly close PDF generator (uses existing reports)
6. Expense CRUD routes
7. IRP calculator (tier brackets from current Paraguayan tax law)
8. Tests for each calculation

**Effort:** 16h
**Depends on:** E10 (settings)
**Acceptance:** Monthly close bundle is one PDF click away

---

## Epic 18 — Print + customer-facing material ⭐

**Why:** Real-world bakery still uses paper. Labels, tickets, daily sheets.

**Stories:**
- E18.S1: A4 sheet of ingredient labels (30-40 per page, Avery template)
- E18.S2: Perishable date labels ("Usar antes de DD/MM/YYYY")
- E18.S3: Daily sales sheet (printable PDF: 1 page, today's totals + top 5 products)
- E18.S4: Weekly summary poster (for kitchen whiteboard — A3 size)
- E18.S5: QR code on receipts (links to online menu / reorder page)

**Tasks:**
1. Ingredient label PDF generator (Avery 5160 or local equivalent)
2. Date label generator with shelf_life_days per ingredient
3. Daily sales PDF template
4. Weekly summary A3 template
5. QR code generation (python-qrcode)
6. Tests: PDF generation, page count, content presence

**Effort:** 8h
**Depends on:** E6 (ingredient data), E14 (printer infra)
**Acceptance:** Print a sheet of ingredient labels in 1 click

---

## Epic 19 — Seasonal + calendar intelligence ⭐

**Why:** Paraguayan holidays drive 2-3x sales spikes. Bake them in.

**Stories:**
- E19.S1: Holiday calendar (Día de la Madre, Navidad, Año Nuevo, Semana Santa, Día del Niño)
- E19.S2: Pre-holiday prep reminders ("Maidana es Día de la Madre; ¿tenés suficientes tortas encargadas?")
- E19.S3: Back-to-school, summer, winter seasonal tagging
- E19.S4: Holiday sales comparison (this holiday vs last year same holiday)
- E19.S5: Holiday-specific product suggestions (pan dulce in Dec, roscón in Reyes)

**Tasks:**
1. New `holiday` table (id, date, name, type, expected_multiplier)
2. Seed Paraguayan holidays 2026-2030
3. Holiday reminder UI component (in EOD checklist)
4. Holiday sales comparison query
5. Seasonal product suggestion engine (rules-based)
6. Tests for each

**Effort:** 6h
**Depends on:** E8 (analytics), E6 (data)
**Acceptance:** Holiday reminders surface in EOD checklist 7 days before

---

## Epic 20 — Disaster recovery + backup hardening ⭐⭐

**Why:** A backup that's never tested isn't a backup. Encrypt + rotate + drill.

**Stories:**
- E20.S1: R2 retention policy (30 daily + 12 monthly + 7 yearly)
- E20.S2: Backup encryption key rotation (3-key versioning)
- E20.S3: Quarterly restore-from-backup drill
- E20.S4: Local backup retention (already 30 days; verify + extend to 90)
- E20.S5: Backup health check (size, age, encryption status — surfaced in `/admin`)
- E20.S6: Backup restore from local OR R2 (single command)

**Tasks:**
1. Implement R2 retention sweep script (called nightly)
2. Key versioning: each backup tagged with `key_version=1|2|3`
3. DR drill script: pick random backup, restore to temp DB, run smoke tests
4. Local backup retention extended to 90 days
5. `/admin` backup health panel
6. `aiw-saskia restore [--source=local|r2] [--backup=path]` CLI
7. Tests: retention sweep, key rotation, restore roundtrip

**Effort:** 8h
**Depends on:** Nothing (parallel)
**Acceptance:** Quarterly DR drill passes; restore works from both local and R2

---

## Epic 21 — Wishlist feature: production worksheet ⭐

**Why:** "Producción del día" — tomorrow's prep sheet from last 4 weeks of sales.

**Stories:**
- E21.S1: `ProductionPlan` table (date, expected_sales, recipe_quantities)
- E21.S2: Forecast function (4-week moving average per product)
- E21.S3: Print-friendly A4 worksheet (recipe, qty, ingredient qty)
- E21.S4: Daily generation cron (06:00, saves to operator's local dir)

**Tasks:**
1. New `ProductionPlan` table (schema v5)
2. Forecast function (`moving_avg_per_product(session, weeks=4)`)
3. Worksheet PDF template
4. Cron job (06:00 daily)
5. Manual trigger button in `/admin`
6. Tests for forecast accuracy on synthetic data

**Effort:** 10h
**Depends on:** E6 (realistic sales data)
**Acceptance:** Tomorrow's worksheet is in operator's local dir by 06:05

---

## Epic 22 — Wishlist feature: merma (waste) tracking ⭐

**Why:** Waste is real money leak Saskia doesn't measure. Quick to ship.

**Stories:**
- E22.S1: `WasteEvent` table (id, ingredient_id, qty, reason, occurred_at, notes)
- E22.S2: `/merma` route (register waste event)
- E22.S3: Monthly merma report (per ingredient, per reason, cost impact)
- E22.S4: Audit log hook (`waste.recorded`)

**Tasks:**
1. New `WasteEvent` table (schema v4)
2. `/merma` route (GET form + POST handler)
3. Monthly merma report
4. Audit log integration
5. Tests for each path

**Effort:** 4h
**Depends on:** Nothing
**Acceptance:** Merma recorded → cost surfaced in monthly report

---

## Epic 23 — Wishlist feature: barcode scanner ⭐

**Why:** As SKUs grow, hand-typing gets slow. Foundation for auto-reorder.

**Stories:**
- E23.1: `barcode` field on `ingredient` (schema v5)
- E23.2: USB barcode-scanner keyboard wedge support (just an input field that takes focus)
- E23.3: Printable barcode label sheet (Avery 5160 with barcode + name)
- E23.4: Excel import supports barcode column

**Tasks:**
1. Add `barcode` to ingredient (schema v5)
2. Barcode input field with autofocus on `/inventario/receive`
3. python-barcode + ReportLab for label generation
4. Update Excel import to recognize barcode column
5. Tests

**Effort:** 8h
**Depends on:** E18 (label infra)
**Acceptance:** Scan a barcode → ingredient loads; print labels with barcodes

---

## Epic 24 — Operator dev-quality tooling ⭐⭐

**Why:** Polish the developer experience so future work is cheap.

**Stories:**
- E24.S1: `Makefile` with setup / test / lint / run / migrate / seed entry points
- E24.S2: `CONTRIBUTING.md` (bug reports, features, dev workflow, security disclosure)
- E24.S3: `.github/CODEOWNERS` (review routing)
- E24.S4: Dependabot / Renovate config (weekly PR cadence)
- E24.S5: `docker-compose.dev.yml` (PG + app for local dev)
- E24.S6: mypy strict mode (gradual typing)
- E24.S7: pre-commit hooks (ruff + black + mypy)

**Tasks:**
1. Write `Makefile` with standard targets
2. Write `CONTRIBUTING.md`
3. Write `.github/CODEOWNERS`
4. Write `.github/dependabot.yml`
5. Write `docker-compose.dev.yml`
6. Configure mypy strict + add types module-by-module
7. Configure pre-commit
8. Tests for each

**Effort:** 8h
**Depends on:** Nothing
**Acceptance:** `make test` works on a fresh checkout

---

## Epic 25 — Future-facing exploration ⭐

**Why:** Gem project means every angle is considered. Some won't ship but the thinking matters.

**Stories:**
- E25.S1: Voice input for sale entry (Spanish, Sphinx/Kaldi — high effort, listed but not for 2026)
- E25.S2: Photo of custom cake attached to sale record
- E25.S3: Multi-tenant SaaS pricing model + Stripe integration
- E25.S4: Public read-only "Today's menu" page (PWA)
- E25.S5: Supplier portal (supplier logs in, sees orders, confirms delivery)
- E25.S6: Native mobile app (React Native wrapper around PWA)
- E25.S7: Spanish + Guaraní UI strings
- E25.S8: AI-powered recipe suggestion ("what can I make with leftover cream cheese + chocolate?")

**Tasks:**
Each story has its own ticket file when promoted from wishlist to triaged.

**Effort:** Variable (8-100h each)
**Acceptance:** Tickets exist in `docs/wishlist/raw/` with cost/phase estimates

---

## Summary

**25 epics across 6 phases.** All actionable, all with concrete tasks, all backed by Acceptance criteria.

| Phase | Epic | Status | Effort |
|---|---|---|---|
| P0 | E1-E5 (carry from 50h) | 3/5 done, 9h carry | 50h |
| P1 | E6, E7, E8 | all new | 18h |
| P2 | E9, E10, E11, E12 | all new | 48h |
| P3 | E13, E14 | all new | 40h |
| P4 | E15, E16 | all new | 36h |
| P5 | E17-E25 | all new | 76h |
| **Total** | | | **268h** |

**Plus 8h buffer for unknowns.**

Gem project. Saskia is Iván's sister. Every detail polished.

---

## How to execute

1. Pick a story from any epic
2. Create ticket file `SASKIA-NNN-<short-slug>.md` (NNN = ticket number)
3. Mark `in_progress`
4. Build + test + commit
5. Mark `shipped`
6. Move to next story

Ticket format:
```markdown
# SASKIA-NNN: <short title>

**Date:** 2026-09-07
**Epic / Story:** E#.S#
**Owner:** Iván
**Estimate:** Xh
**Status:** in_progress | shipped | blocked | cancelled

## What

<description>

## Why

<business outcome>

## Tasks

- [ ] Task 1
- [ ] Task 2

## Acceptance

<definition of done>
```
