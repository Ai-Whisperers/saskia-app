# Saskia RMS — Complete Epic Plan (Extracted)

> **Source:** `docs/plans/2026-09-07-saskia-complete-epic-plan-v3.md` (811 lines)
> **Extracted:** 2026-10-05
> **Scope:** 25 epics across 6 phases. This is a structured extract of the
> plan; the original is preserved at
> [`../historical-plans/2026-09-07-saskia-complete-epic-plan-v3.md`](../../archive/2026-09/plans/2026-09-07-saskia-complete-epic-plan-v3.md)
> for git-blame fidelity.
> **Status key:** ✅ = marked done in source · 🟡 = partially done / stories shipped
> · ⏳ = open · ➖ = out of scope (Saskia single-user). Status as of 2026-10-05.

## How to read

- **E# = Epic number** (1-25). **E#.S# = Story** within epic.
- **Tickets** use the format `SASKIA-NNN-<short-slug>.md`.
- **Effort** is the sum of all story tasks in the source plan; "Xh" in the
  per-epic table is from the source.
- **Phase map** is the canonical ordering. Within a phase, the order is also
  the recommended build order.

## Status as of 2026-10-05

| Phase | Epics | Status | Notes |
|---|---|---|---|
| P0 | E1–E5 | 🟡 ~95% | E1-E3 done; E2.S2 (PG testcontainers) and E3.S4 (healthz/db runbook) open |
| P1 | E6, E7, E8 | ✅ 100% | Demo seed, fixtures, analytics — all shipped |
| P2 | E9, E10, E11, E12 | ✅ 95% | Tags, filters, settings all shipped; PWA / offline (E11) explicitly deferred per Saskia context |
| P3 | E13, E14 | 🟡 70% | Customer directory (E13) shipped; customer-facing features (E14) partially — pedido share ✅, WhatsApp bot ⏳ |
| P4 | E15, E16 | ➖ Deferred | Multi-tenant and scale infra intentionally out of scope per Saskia single-user context |
| P5 | E17–E25 | 🟡 ~30% | Expense (E17) partly done (migration 082), merma (E22) shipped, dev tooling (E24) shipped; rest aspirational |

---

# PHASE 0 — Round 1 close-out

## Epic 1 — Round 1 close-out ✅ COMPLETE

- E1.S1 installer patches ✅ DONE (`94f9a24`, `6fef4a2`)
- E1.S2 Round-1 feedback sweep + log ✅ DONE
- E1.S3 CF tunnel rotation runbook ✅ DONE (`0286929`)

## Epic 2 — Make deploy CI-catchable 🟡 3/4 done

- E2.S1 15 fail-closed regression tests ✅ DONE (`04c6aa7`)
- E2.S2 Real Postgres test infra (testcontainers) ⏳ OPEN
- E2.S3 `aiw-saskia migrate` idempotent ✅ DONE (`b0f06ef`)
- E2.S4 refresh.sh autodetects cwd + CI migrate smoke ✅ DONE (`a82b7be`)

### E2.S2 — Real Postgres test infra (testcontainers)
**Why:** 5 production hotfixes in 2026-09-04 happened because we couldn't reproduce hosted data shape locally. A PG testcontainer would have caught 4/5.
**Stories:** E2.S2.1 (testcontainers dep), E2.S2.2 (pg_engine fixture), E2.S2.3 (migrations on first connection), E2.S2.4 (`@pytest.mark.pg`).
**Tasks:** add dep, write `conftest_pg.py`, tag hotfix tests, CI `-m pg` step, PG roundtrip tests, JSONB test.
**Effort:** 4h · **Acceptance:** `pytest -m pg` boots real PG, 15 regression tests pass.

## Epic 3 — Harden runtime 🟡 3/4 done

- E3.S1 Audit log ✅ DONE (`5903d26`)
- E3.S2 Rate-limit on /login ✅ DONE (`85a32d4`)
- E3.S3 SecurityHeadersMiddleware ✅ DONE (`0286929`)
- E3.S4 /healthz/db runbook + UptimeRobot wiring ⏳ OPEN

### E3.S4 — /healthz/db runbook + UptimeRobot
**Why:** `/healthz/db` exists in code but no operator doc, no UptimeRobot config captured.
**Tasks:** enhance `/healthz/db` to JSON, write `uptime-monitoring.md`, document WhatsApp alert routing, audit failures, test.
**Effort:** 1.5h

## Epic 4 — Fase 1.5 UX polish 🟡 partial

- E4.S1 Round-2 items triage + ship — round-2 process doc shipped
- E4.S2 daily_sales_series() + SVG chart ✅ shipped (BACKLOG #22/26)
- E4.S3 /excel/exportar?period=current_month — open
- E4.S4 Mobile tweaks — partial (touch targets in E9/E10)

### E4.S2 — daily_sales_series() + SVG chart
**Why:** Highest-signal viz for a small business.
**Tasks:** add `daily_sales_series()` to `app/services/reports.py`, add `top_product_id_for_day()`, write `sales_chart.svg.j2`, wire with period toggle (7d/30d/90d/this/last), tests.
**Effort:** 4h

### E4.S3 — /excel/exportar?period=current_month
**Why:** Monthly close requires export. Currently dumps everything.
**Tasks:** accept `period=`, add resolver, header sheet with period name + range, tests (incl. Feb 28-29).
**Effort:** 3h

### E4.S4 — Mobile tweaks
**Why:** Saskia uses phone at shop.
**Tasks:** bump interactive elements to 44px, `@media (max-width: 768px)` for bottom-nav, reflow sale-entry with sticky bottom bar, Lighthouse.
**Effort:** 4h

## Epic 5 — Tracking infrastructure 🟡 3/4 done

- E5.S1 Wishlist scaffold ✅ DONE (`8126827`)
- E5.S2 STATUS.html.tmpl refresh in CI ⏳ OPEN
- E5.S3 CHANGELOG discipline gate ✅ DONE (`a82b7be`)
- E5.S4 Issue templates ✅ DONE (`4b68d0d`)

### E5.S2 — STATUS.html.tmpl update + refresh.sh in CI
**Tasks:** update template with test count/coverage/SHA/wishlist, CI invocation, generate index.html, tests.
**Effort:** 1.5h

---

# PHASE 1 — Data + Insights

## Epic 6 — Realistic demo data seed ✅ COMPLETE

**Why:** Saskia opens the app → ~20 products, ~12 recipes, ~200 historical sales. No blank-state anxiety.

**Stories:** E6.S1 (30 ingredients) · E6.S2 (12 recipes) · E6.S3 (20 products) · E6.S4 (90-day synthetic sales) · E6.S5 (stock moves) · E6.S6 (demo user) · E6.S7 (1 voided + 1 encargo) · E6.S8 (audit log seed) · E6.S9 (`aiw-saskia seed [--reset]`) · E6.S10 (seed report).

**Tasks:** `app/rms/seed.py` with `seed_demo_data()`, ingredients list, recipes list, products list, ~80 recipe_lines, sales generator, stock moves, demo user, voided + encargo, audit log, CLI, tests.
**Effort:** 6h · **Acceptance:** `aiw-saskia seed` populates fresh DB; `--reset` destructive-safe; tests pass.

## Epic 7 — Real-Drive-shape Excel fixture ✅ COMPLETE

**Why:** Saskia keeps editing Drive Excel after import. Fixture mirroring her real Drive shape catches merge regressions.

**Stories:** E7.S1 (herbus_demo.xlsx ~200 rows) · E7.S2 (herbus_mini.xlsx ~10 rows) · E7.S3 (edge-case fixtures) · E7.S4 (import tests against all 5) · E7.S5 (polymorphic Recipe → RecipeLine).

**Tasks:** build 2 base fixtures (6 sheets each: Ingredientes/Recetas/Lineas/Productos/Ventas/StockMoves), 4 edge-case fixtures, tests, LFS if >1MB.
**Effort:** 4h · **Depends on:** E6.

## Epic 8 — Operational analytics dashboard ✅ COMPLETE

**Why:** 90 days of data → answer 10 questions Saskia asks daily. Highest-ROI dashboard work.

**Stories:** E8.S1 (stock turnover) · E8.S2 (days-of-stock) · E8.S3 (dead-stock) · E8.S4 (margin erosion alerts) · E8.S5 (DoW heatmap) · E8.S6 (top-margin) · E8.S7 (ingredient concentration) · E8.S8 (recipe complexity + cost-per-prep-minute).

**Tasks:** add columns (`last_consumed_at`, `purchase_price_updated_at`, `prep_minutes`), `app/services/analytics.py` with 8 functions, wire into `/analisis`, tests.
**Effort:** 8h · **Depends on:** E6 + E3.S1.

---

# PHASE 2 — Operator UX + Workflow

## Epic 9 — Tags + filtering ✅ COMPLETE

**Why:** Tags are highest-leverage way to add segmentation. Filters = 80% of operator productivity.

**Stories:** E9.S1 (tag + 3 M:N tables) · E9.S2 (tag picker in forms) · E9.S3 (15 starter tags) · E9.S4 (Ventas filter) · E9.S5 (Inventario filter) · E9.S6 (Recetas filter) · E9.S7 (Productos filter) · E9.S8 ("Export filtered" button).

**Tasks:** new tables (schema v3), tag CRUD, picker Jinja2, wire into forms, seed 15 tags, query params per page, export button, tests.
**Effort:** 12h · **Acceptance:** All 4 pages filterable; tags first-class on 3 entities.

## Epic 10 — Easy settings 🟡 ~80% done

**Why:** Most "small things that annoy daily" are configuration knobs. Surface the 30 most common ones.

**Stories:** E10.S1 (setting table) · E10.S2 (settings UI) · E10.S3 (currency/date) · E10.S4 (business hours) · E10.S5 (inventory defaults) · E10.S6 (dashboard defaults) · E10.S7 (sales entry) · E10.S8 (backup) · E10.S9 (session) · E10.S10 (demo mode banner).

**Tasks:** `setting` table, settings page UI, apply everywhere, defaults seeded, tests.
**Effort:** 8h · **Depends on:** E9.

## Epic 11 — Mobile + offline ➖ Deferred

**Why:** Saskia uses phone at shop. Internet drops happen; offline-first is real ask.

**Stories:** E11.S1 (PWA manifest + service worker) · E11.S2 (bottom-nav) · E11.S3 (offline sale entry) · E11.S4 (touch-friendly).

**Tasks:** manifest.json, service-worker, IndexedDB queue, sync on `online`, mobile CSS audit, tests.
**Effort:** 16h · **Depends on:** E4.S4. **Status:** explicitly deferred per Saskia context (PWA is in "Descartado" of canonical roadmap).

## Epic 12 — Operator workflow tools 🟡 ~80% done

**Why:** Daily rituals (open, mid-day, close) are scripted. Bake them into the app.

**Stories:** E12.S1 (EOD checklist) · E12.S2 (supplier order PDF) · E12.S3 (recipe costing worksheet) · E12.S4 (manual backup button) · E12.S5 (`/admin` operator dashboard).

**Tasks:** `eod_checklist_run` table, EOD UI, supplier order PDF, recipe costing UI, manual backup button, `/admin` route, tests.
**Effort:** 12h · **Depends on:** E10 + E3.S1.

---

# PHASE 3 — Customer + Retention (Fase 2)

## Epic 13 — Customer directory + loyalty ✅ MOSTLY COMPLETE

**Why:** Walk-in repeat customers are real revenue. Even a simple "remember last 10 customers" unlocks targeted prep + loyalty.

**Stories:** E13.S1 (customer table) · E13.S2 (customer picker) · E13.S3 (customer detail page) · E13.S4 (top customers) · E13.S5 (inactive >30d) · E13.S6 (loyalty points) · E13.S7 (customer_id on sale) · E13.S8 (CSV import).

**Tasks:** tables (schema v4), CRUD routes, picker, detail page, top/inactive queries, loyalty calc + redemption, CSV import, tests.
**Effort:** 16h · **Depends on:** E9. **Status:** loyalty ledger (BACKLOG #14) shipped; CSV import still open.

## Epic 14 — Customer-facing features 🟡 ~50% done

**Why:** Once you have customers, give them reasons to come back.

**Stories:** E14.S1 (WhatsApp bot) · E14.S2 (online ordering webhook) · E14.S3 (pickup time slot booking) · E14.S4 (subscription boxes) · E14.S5 (receipt printer) · E14.S6 (kitchen printer).

**Tasks:** WhatsApp templates, Twilio/Evolution integration, online order endpoint, pickup slot model, subscription model, ESC/POS integration, receipt template, kitchen ticket template, tests.
**Effort:** 24h · **Depends on:** E13. **Status:** pedido share `/p/{token}` ✅ (BACKLOG #17), suscripciones ✅ (B.5 shipped), printer integrations ⏳.

---

# PHASE 4 — Scale + Multi-tenant readiness ➖ Deferred

## Epic 15 — Multi-tenant schema + isolation ➖ Deferred

**Why:** Future-proofing. Intentionally out of scope per Saskia single-user context.

**Stories:** E15.S1 (tenant_id on all tables) · E15.S2 (login → tenant) · E15.S3 (queries include tenant_id) · E15.S4 (backups per-tenant) · E15.S5 (tenant settings page) · E15.S6 (migration from single-tenant).

**Tasks:** tenant table (schema v5), tenant_id columns, event listener, login flow, R2 path, settings UI, migration script, tests.
**Effort:** 16h · **Status:** Tenant model exists (per BACKLOG #38); RLS not implemented.

## Epic 16 — Performance + scale infrastructure ➖ Deferred

**Why:** Necessary once multi-tenant.

**Stories:** E16.S1 (PgBouncer) · E16.S2 (slow query log) · E16.S3 (Redis cache) · E16.S4 (read replicas) · E16.S5 (backup key rotation) · E16.S6 (DR drill).

**Tasks:** docker-compose.hosted.yml, Grafana, cache layer, replica routing, key versioning, DR drill script, tests.
**Effort:** 20h · **Depends on:** E15.

---

# PHASE 5 — Polish + future-facing

## Epic 17 — Accounting + tax 🟡 ~40% done

**Why:** Saskia's accountant needs clean monthly reports. IVA (10% in Paraguay) on every sale.

**Stories:** E17.S1 (IVA field) · E17.S2 (RUC setting) · E17.S3 (daily cash reconciliation) · E17.S4 (monthly close PDF) · E17.S5 (expense tracking) · E17.S6 (IRP).

**Tasks:** `iva_rate`, `expense` tables, IVA per product, RUC, daily recon, monthly close PDF, expense CRUD, IRP calc, tests.
**Effort:** 16h · **Depends on:** E10. **Status:** Expense table + daily_summary wiring ✅ (migration 082); rest open.

## Epic 18 — Print + customer-facing material ⏳ Open

**Why:** Real-world bakery still uses paper.

**Stories:** E18.S1 (A4 ingredient labels) · E18.S2 (perishable date labels) · E18.S3 (daily sales PDF) · E18.S4 (weekly summary A3) · E18.S5 (QR on receipts).

**Tasks:** Avery 5160 generator, date labels, daily sales PDF, weekly A3, QR generation, tests.
**Effort:** 8h · **Depends on:** E6 + E14.

## Epic 19 — Seasonal + calendar intelligence ⏳ Open

**Why:** Paraguayan holidays drive 2-3x sales spikes.

**Stories:** E19.S1 (holiday calendar) · E19.S2 (pre-holiday prep reminders) · E19.S3 (seasonal tags) · E19.S4 (holiday sales comparison) · E19.S5 (holiday product suggestions).

**Tasks:** `holiday` table, seed 2026-2030, reminder UI, comparison query, suggestion engine, tests.
**Effort:** 6h · **Depends on:** E8 + E6.

## Epic 20 — Disaster recovery + backup hardening 🟡 partial

**Why:** A backup that's never tested isn't a backup.

**Stories:** E20.S1 (R2 retention 30/12/7) · E20.S2 (key rotation 3-key) · E20.S3 (quarterly restore drill) · E20.S4 (local 90-day) · E20.S5 (backup health in /admin) · E20.S6 (restore CLI).

**Tasks:** retention sweep, key versioning, DR drill script, local retention, /admin panel, `aiw-saskia restore` CLI, tests.
**Effort:** 8h · **Status:** R2 retention shipped (canonical D.5); healthz/backup ✅ (BACKLOG #39); restore drill still open.

## Epic 21 — Wishlist: production worksheet 🟡 partial

**Why:** "Producción del día" — tomorrow's prep sheet from last 4 weeks of sales.

**Stories:** E21.S1 (ProductionPlan table) · E21.S2 (forecast 4-week moving avg) · E21.S3 (A4 worksheet PDF) · E21.S4 (06:00 daily cron).

**Tasks:** `ProductionPlan` table, `moving_avg_per_product()`, worksheet PDF, cron, manual trigger, tests.
**Effort:** 10h · **Depends on:** E6. **Status:** forecast module exists, enchufar (B.2 in canonical) is the open work.

## Epic 22 — Wishlist: merma (waste) tracking ✅ COMPLETE

**Why:** Waste is real money leak Saskia doesn't measure. Quick to ship.

**Stories:** E22.S1 (WasteEvent table) · E22.S2 (`/merma` route) · E22.S3 (monthly merma report) · E22.S4 (audit log hook).

**Tasks:** table (schema v4), GET form + POST, monthly report, audit, tests.
**Effort:** 4h · **Acceptance:** Merma recorded → cost surfaced in monthly report. **Status:** shipped; further UI work in `feat/prod-quick-merma` branch (15 commits, not deployed).

## Epic 23 — Wishlist: barcode scanner ⏳ Open

**Why:** As SKUs grow, hand-typing gets slow.

**Stories:** E23.1 (barcode field) · E23.2 (USB wedge) · E23.3 (label sheet) · E23.4 (Excel import).

**Tasks:** add field (schema v5), autofocus, ReportLab labels, Excel import, tests.
**Effort:** 8h · **Depends on:** E18.

## Epic 24 — Operator dev-quality tooling ✅ MOSTLY DONE

**Why:** Polish the developer experience.

**Stories:** E24.S1 (Makefile) · E24.S2 (CONTRIBUTING.md) · E24.S3 (CODEOWNERS) · E24.S4 (Dependabot) · E24.S5 (docker-compose.dev.yml) · E24.S6 (mypy strict) · E24.S7 (pre-commit hooks).

**Tasks:** Makefile, CONTRIBUTING, CODEOWNERS, dependabot.yml, docker-compose, mypy, pre-commit, tests.
**Effort:** 8h · **Status:** Makefile ✅, CONTRIBUTING ✅, pre-commit ✅, dependabot configured (3 PRs open).

## Epic 25 — Future-facing exploration ➖ Aspirational

**Why:** Gem project means every angle is considered. Some won't ship but the thinking matters.

**Stories:** E25.S1 (voice input) · E25.S2 (cake photo) · E25.S3 (multi-tenant SaaS) · E25.S4 (public menu PWA) · E25.S5 (supplier portal) · E25.S6 (native mobile) · E25.S7 (es/gn i18n) · E25.S8 (AI recipe suggestion).

**Acceptance:** Tickets exist in `docs/wishlist/raw/` with cost/phase estimates.

---

## Summary (from source)

| Phase | Epic | Status (source) | Effort |
|---|---|---|---|
| P0 | E1-E5 (carry from 50h) | 3/5 done, 9h carry | 50h |
| P1 | E6, E7, E8 | all new | 18h |
| P2 | E9, E10, E11, E12 | all new | 48h |
| P3 | E13, E14 | all new | 40h |
| P4 | E15, E16 | all new | 36h |
| P5 | E17-E25 | all new | 76h |
| **Total** | | | **268h** |

> Plus 8h buffer for unknowns. From the source plan, dated 2026-09-07.
