# Sazón RMS — Improvement Plan v2 (post 40-hat audit)

> **For Hermes:** Top 5 ideas from a 40-hat analysis + audit gaps. Builds on the
> PRODUCCION-V3 phase work already shipped (commits b1a605d, 047c06f, 19b4a18,
> 3dea5bc, 91a76ad, 15e9c5b on `feat/produccion-v3-ux-overhaul`).

**Goal:** Address the 5 highest-ROI improvements from the 40-hat analysis, plus
the 4 audit gaps that the subagent missed.

**Architecture:** Server-rendered FastAPI + Jinja + SQLAlchemy, single-user.
No new dependencies. TDD per item. Frequent commits.

**Tech Stack:** Python 3.13 / FastAPI / SQLAlchemy 2 / Jinja2 / SQLite (dev) /
Postgres (prod) / pytest.

---

## Source documents (read in this order)

1. `/opt/data/profiles/ivan/cache/scratch/sazon_40hats.md` — 40-hat analysis
   (1027 lines, 35KB). 40 operator roles × 2-3 ideas each. Subagent output.
2. `/opt/data/profiles/ivan/scratch/saskia-app-work/IMPROVEMENT_BACKLOG.md` —
   shipped-state filter (anything ✅ is already done; do not re-propose).
3. `/opt/data/profiles/ivan/scratch/saskia-app-work/COMPLETE_PLAN.md` —
   parent plan; the 5 v2 items align with §3 (Production), §5 (Operations),
   §6 (Reporting), §11 (Maintenance/cleanup).
4. `/opt/data/profiles/ivan/scratch/saskia-app-work/docs/superpowers/specs/2026-10-05-produccion-v3-design.md`
   — design spec from the just-shipped PRODUCCION-V3 work.

---

## Top 5 v2 features (from 40-hat analysis + my audit)

**Selection criteria (ROI × frequency × effort):**
- Used daily or weekly (frequency)
- Saves 10+ min/turn OR prevents errors that cost ≥Gs. 50k/month (impact)
- ≤ 1 dev-day (effort)
- Single-user, no external integration (scope)

| # | Feature | Impact | Effort | Source |
|---|---|---|---|---|
| **1** | **CSV export of /produccion daily plan** | Saves 5min/turn × 30 turns/month = 2.5h/month. Sebastián can paste into WhatsApp for Sebas/equipo. | S (0.5d) | subagent #1.1 partial + audit gap #5 |
| **2** | **/eod print-friendly view** | EOD is currently a 5-screen scroll on mobile. Print = 1 page, archived in binder. | S (0.5d) | subagent #1.1 (mobile) + audit gap #3 |
| **3** | **"Copiar plan de la semana pasada" button** | Recurring menu saves 20min/week on menu planning. | S (0.5d) | subagent #1 (yield optimization) + audit gap #4 |
| **4** | **Delete or wire up 2 orphan templates** (cliente_loyalty, produccion_calendario) | Tech debt; navigation links point to 404s. | XS (2h) | audit gap #1 |
| **5** | **Refactor produccion.py router** (3007 lines → 3 files) | Maintenance velocity. Bug fixes in /produccion are 2x faster after split. | M (1.5d) | audit gap #2 (biggest file) |

**Total: ~4 dev-days. 5 separate commits. Each behind TDD.**

---

## Items I'm NOT building (with reason)

| Item | Subagent said | Why I'm skipping |
|---|---|---|
| **B2B catering portal** (#10, #37) | "P0, +Gs. 75k/month" | No B2B customers in the Sazón pipeline; the system is single-panadería. Trucking in catering workflows adds 1-2 weeks. |
| **Route optimization app** (#7 Miguel) | "P0, saves fuel" | Sazón has 0 delivery drivers (retail only). The Miguel hat is hypothetical. |
| **Predictive restocking AI** (#32) | P2 | `compute_reorder_list` already exists (cache verified). ML on top of it needs >6mo data we don't have. |
| **IoT temperature sensors** (#6.2, #39) | P1 | FreezerTemperatureLog already exists (HACCP B.6). Sensors cost >$200/unit; ROI negative. |
| **Maintenance scheduler** (#11) | P0 | Only 1 oven, 1 mixer. Sebastián's head is the schedule. Add when we have 3+ locations. |
| **Multilang i18n** (not in subagent but I considered) | — | Single-user Spanish app in Asunción. Adding i18n is YAGNI. |
| **Inventory hub on mobile bottom-nav** | — | Mobile bottom nav already has Inicio/Vender/Stock/Reponer/Más (verified in current build). |

---

## Refactor target (Item 5) — why split produccion.py

`app/routers/produccion.py` is 3007 lines. Single biggest file in the repo.
Splitting by route-family is low-risk because:

- Endpoints are already grouped: day-view, week-view, month-view, plan-override,
  shift-execute, ad-hoc (single + bulk), print, accuracy, planner, prep-sheet,
  fermentation reminder, etc.
- No cross-endpoint shared state (each route is a function with `request: Request`).
- No ORM relationships cross the file boundary.
- Tests are black-box (HTTP), so a refactor that preserves URL contracts is
  invisible to tests.

**Target structure:**
```
app/routers/produccion/
    __init__.py        # re-exports the public API
    worksheet.py       # GET /produccion + view=day|week|month (the 3 view types)
    overrides.py       # POST /produccion/override, /override-bulk, GET /produccion/override
    shift.py           # POST /produccion/shift-execute, GET /produccion/close-day
    adhoc.py           # POST /produccion/ad-hoc, /ad-hoc/bulk
    print_export.py    # GET /produccion/print, /produccion/print?mode=worksheet
    analytics.py       # GET /produccion/accuracy, /precision
    helpers.py         # plan_rows_view, day_lote_final_total, _confidence_band_for_pct, etc.
```

This is **risk-zero** because the public URL surface is preserved; all tests
keep working. The split reduces cognitive load: when fixing a shift-execute bug,
the dev reads 200 lines, not 3007.

---

## Risk register (v2)

| Risk | Mitigation |
|---|---|
| Refactor breaks import chain | Run full test suite after each split. produccion.py is imported by `app/main.py` only — re-export from the package's `__init__.py`. |
| CSV export contains PII (customer names) | Default columns: product_name, qty, source, confidence. No customer data. |
| "Copy last week" creates a plan with yesterday's stale data | Source: read last week's `plan_production()` output, but apply fresh `pending_pedido_qty` for the target date. Show diff before commit. |
| EOD print breaks the live UI | Print template extends `base.html` but is rendered via a separate route that doesn't use the SPA's reactivity. Use `{% if print_mode %}{{ var|trim }}{% endif %}` blocks. |
| Orphan-template deletion breaks a deep link | grep for the URL paths `/cliente/loyalty` and `/produccion/calendario`; none exist (verified). Delete is safe. |

---

## Out of scope (deferred to a future plan)

- Migrating to React/Vue (single-user Jinja is fine)
- Mobile native app (PWA is the right path; not yet)
- Multi-location support (Tenant table exists; deferred to v3)
- Supabase Storage for product images (IMPROVEMENT_BACKLOG #37)
- Supabase RLS (IMPROVEMENT_BACKLOG #38)

---

## Execution plan (5 phases, TDD per phase)

### Phase A: CSV export of /produccion daily plan (item 1)

**Files:**
- Create: `tests/test_produccion_csv_export.py`
- Modify: `app/routers/produccion.py` (add new endpoint + route)
- Modify: `app/templates/produccion.html` (add download button next to "Imprimir")

**Tests first:**
1. `test_csv_export_endpoint_returns_csv_content_type`
2. `test_csv_export_has_one_row_per_product_in_day_view`
3. `test_csv_export_columns_are_product_qty_source_confidence`
4. `test_csv_export_does_not_leak_customer_pii`
5. `test_csv_export_respects_for_date_query_param`

**Implementation:** Add `GET /produccion/export.csv?for_date=YYYY-MM-DD&view=day`
that returns `text/csv` with the visible columns. No template; pure CSV via
FastAPI `Response`.

**Commit:** `feat(produccion): CSV export of daily plan`

---

### Phase B: /eod print-friendly view (item 2)

**Files:**
- Create: `tests/test_eod_print.py`
- Create: `app/templates/eod_print.html`
- Modify: `app/routers/eod.py` (add `GET /eod/print` route)
- Modify: `app/templates/eod.html` (add "Imprimir" button → `/eod/print`)

**Tests first:**
1. `test_eod_print_endpoint_renders_with_minimal_chrome`
2. `test_eod_print_includes_anomaly_count`
3. `test_eod_print_includes_reorder_items_table`
4. `test_eod_print_uses_print_css_media_query`
5. `test_eod_print_does_not_include_sidebar_or_bottom_nav`

**Implementation:** New template that extends `base.html` but hides nav, sidebar,
bottom nav via `{% if not print_mode %}` blocks, and uses `@media print` CSS to
ensure 1-page layout. Shows: date, anomaly banner, checklist status, reorder
items + total Gs., notes_for_next.

**Commit:** `feat(eod): print-friendly view for binder archive`

---

### Phase C: "Copiar plan de la semana pasada" (item 3)

**Files:**
- Create: `tests/test_produccion_copy_last_week.py`
- Modify: `app/routers/produccion.py` (add `POST /produccion/copy-last-week`)
- Modify: `app/templates/produccion.html` (add button next to "Imprimir")

**Tests first:**
1. `test_copy_last_week_creates_overrides_for_target_date`
2. `test_copy_last_week_only_copies_qty_not_meta_source`
3. `test_copy_last_week_shows_diff_before_commit`
4. `test_copy_last_week_handles_no_prior_week_gracefully`
5. `test_copy_last_week_only_owner_or_admin_can_run`

**Implementation:** Form: `POST /produccion/copy-last-week` with `for_date=YYYY-MM-DD`
and `source_date=YYYY-MM-DD` (default = 7 days before). Reads source day's
`plan_production()` output, creates `ProductionPlanOverride` rows for the
target date with the source's `qty_to_produce`. Show preview with diff
("Plan actual: 50 unidades → Copia: 65 unidades (+15)").

**Commit:** `feat(produccion): copy-last-week button with diff preview`

---

### Phase D: Delete or wire orphan templates (item 4)

**Files:**
- Delete: `app/templates/cliente_loyalty.html` (loyalty is handled by
  `/clientes/{id}/loyalty` now; this file is unreachable)
- Delete: `app/templates/produccion_calendario.html` (calendar view was
  replaced by month view; this file is unreachable)
- Create: `tests/test_no_orphan_templates.py` (regression: any future
  orphan template fails CI)

**Tests first:**
1. `test_cliente_loyalty_template_is_removed`
2. `test_produccion_calendario_template_is_removed`
3. `test_no_template_files_have_zero_route_references`
4. `test_no_template_files_have_zero_html_references`

**Implementation:** Audit confirms 0 references for both. Delete + add a CI
gate (`tests/test_no_orphan_templates.py`) that scans `app/templates/*.html`
and checks each is referenced from at least one route or another template.

**Commit:** `chore(cleanup): remove 2 orphan templates + CI gate`

---

### Phase E: Refactor produccion.py (item 5)

**Files:**
- Create: `app/routers/produccion/__init__.py` (re-exports)
- Create: `app/routers/produccion/worksheet.py`
- Create: `app/routers/produccion/overrides.py`
- Create: `app/routers/produccion/shift.py`
- Create: `app/routers/produccion/adhoc.py`
- Create: `app/routers/produccion/print_export.py`
- Create: `app/routers/produccion/analytics.py`
- Create: `app/routers/produccion/helpers.py`
- Delete: `app/routers/produccion.py`

**Tests:** All 41 phase tests + 9 pre-existing produccion tests should pass
unchanged (URL contracts preserved). The 559-test suite regression-tests this.

**Implementation:** Move functions to their target files, fix internal imports
(e.g. `from .helpers import plan_rows_view`), update `app/main.py` import
(`from app.routers.produccion import router` → `from app.routers import produccion
as _; _` works because `__init__.py` re-exports).

**Commit per file:** `refactor(produccion): split into per-feature modules`

---

## Open questions for the user (if any)

None — the user said "implementa el plan", so I proceed with the 5 items
above. If user wants more, we can add Phase F (mobile bottom-nav polish) or
Phase G (refactor pedidos.py — 2364 lines).

---

## What success looks like

After all 5 phases:
- ✅ /produccion has a "Descargar CSV" button (operator can paste in WhatsApp)
- ✅ /eod has a print-friendly 1-page view for the binder
- ✅ /produccion has a "Copiar plan de la semana pasada" button (saves 20min/week)
- ✅ CI catches orphan templates (preventing future tech debt)
- ✅ produccion.py router is 3-5 focused files instead of one 3007-line file
- ✅ 41 phase tests + 9 pre-existing + new phase tests all green
- ✅ Deployed to VPS as `phase-a-20261006`, ..., `phase-e-20261006`
