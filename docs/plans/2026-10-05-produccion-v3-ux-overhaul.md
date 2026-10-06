# Sazón Production Workflow — Complete Improvement Plan

**Date:** 2026-10-05
**Author:** Hermes (post Ivan's "analyze all of this" + "make a complete plan" request)
**Status:** v1 — ready for review
**Branch:** `feat/produccion-v3-ux-overhaul` (new)
**Target merge:** `main` after all 6 phases pass + e2e clean
**Supersedes:** `docs/plans/2026-10-03-ux-hardening-plan.md` for the **production workflow surface only** (it stays for non-production pages). The 10-03 plan's 15 DONE items remain DONE; the 2 SKIPPED items (`checkbox-state-POST`, `tab-focus-restoration`) are picked up here as P0-04 and P0-05.

---

## Why this plan exists

Ivan asked: *"analyze all of this and pass me the updated user and pass credentials to access and test the website"*, then *"analyze how the user defines what they will produce each day... any issues? any possible confusion? any naming and headers and titles etc to add to the page so we know what is what? any additional UX/UI considerations to improve on this?"*

The audit produced **1 blocker + 4 high + 16 medium + 20 low findings** (39 total) — see `docs/plans/2026-10-05-produccion-v2-audit.md` (the prior message). Most are not bugs; they're **vocabulary drift, missing navigation, silent data loss, and column headers that don't explain the math**.

This plan ships them all in 6 phases, **tests first, one phase per session**, with measurable acceptance per phase.

---

## Scope guardrails

**IN scope:**
- Templates: `produccion.html`, `produccion_manana.html`, `eod.html`, `produccion_accuracy.html`, `produccion_prep.html`, `produccion_print.html`, `produccion_calendario.html`, `produccion_haccp.html`
- Partial extraction: `_components/production_row_editor.html` (new), used by 2+ pages
- Router changes: ONLY the **silent-data-loss** fix (`produccion.py:close_day` + `produccion.py:shift_execute` for checkbox persistence) and the **for_date backdate cap**
- New helpers in `app/rms/forecast_explain.py` (confidence-band explanation data)
- New CSS components: `.badge-source-*`, `.qty-stepper--done`, `.shift-pill`, `.day-nav`, `.col-header-hint` (5 small additions; no new token layer)
- New JS helpers: `app/static/ui-day-nav.js`, augment `app/static/app-components.js` for the shift-checkbox auto-save

**OUT of scope** (flagged for separate plans):
- Tailwind removal (per `2026-10-03-ux-hardening-plan.md` scope guardrail #2)
- New pages, new routers, new DB columns (per the 10-03 plan guardrail #1)
- Full design system migration (the 740 inline styles; that is its own 5-phase plan)
- Internationalization beyond `es` (Guaraní is `i18n-guarani` plan, not this one)
- Mobile bottom-nav redesign (already exists, only the `/produccion` linkage needs verification)
- Bulk CSV import (already shipped 2026-10-05, not touched)

---

## Conventions

- **One phase per commit group** (1 PR per phase; squash-merged to keep history readable)
- **Tests first, then implementation, then visual verification**
- Each phase has explicit **Acceptance** criteria that the test suite can verify
- **CHANGELOG.md updated per phase** (CI gate enforces this)
- **Coverage gate:** stays at 35% floor; do NOT bump in this plan (separate effort)
- **No new prod dependencies** (per AGENTS.md rule #1)

---

# PHASE 0 — Stop the bleeding (P0 findings)

**Goal:** Fix the silent-data-loss and backdate bugs, plus the column headers that confuse new cooks. Ship in one session, 2-4h.

**Branch:** `feat/produccion-v3-ux-overhaul` (parent of all subsequent phases)

**Test files (write FIRST):**

- `tests/test_produccion_checkbox_persists.py` — 3 tests
  1. `test_checkbox_uncheck_persists_status_change`: POST `/produccion/close-day` with `status='cancelled'` → DB shows `closure_status='cancelled'`, NOT just `completed_qty=0`.
  2. `test_checkbox_check_creates_completion_row`: with no existing `ProductionCompletion` for `(product_id, for_date)`, POST `closure_status=done&qty=0` → row created with `status='done'`.
  3. `test_closing_one_row_does_not_affect_others`: close product A, verify product B's completion is unchanged.

- `tests/test_produccion_backdate_cap.py` — 2 tests
  1. `test_shift_execute_rejects_for_date_far_past`: POST with `for_date = today - 30 days` → 400 Bad Request.
  2. `test_shift_execute_rejects_future_date`: POST with `for_date = today + 7 days` → 400 Bad Request.

- `tests/test_produccion_close_day_idempotent.py` — 2 tests
  1. `test_closing_twice_does_not_duplicate_audit`: same closure posted twice within 60s → only ONE `production_completion` row exists, ONE audit row.
  2. `test_closing_then_reopening_then_closing_keeps_history`: open → close → reopen → close → audit log has all 3 events.

- `tests/test_produccion_vocabulary.py` — 4 tests (regression for column renames)
  1. `test_day_view_contains_meta_column`: GET `/produccion` body contains `<th>Meta (unidades)</th>`.
  2. `test_day_view_contains_lote_final_column`: contains `<th>Lote final</th>` and DOES NOT contain the literal `<th>Total a hornear</th>`.
  3. `test_day_view_contains_comprometido_column`: contains `<th>Ya comprometido</th>` and DOES NOT contain `<th>+ Pedidos</th>`.
  4. `test_day_view_contains_hecho_column`: contains `<th>Hecho</th>` and DOES NOT contain `<th>Progreso</th>`.

- `tests/test_produccion_page_titles.py` — 3 tests
  1. `test_today_title_includes_date`: GET `/produccion?for_date=2026-10-05` body contains `<title>Producción · 2026-10-05</title>`.
  2. `test_manana_title_includes_tomorrow`: GET `/produccion/manana` body contains `<title>Producción · Mañana 2026-10-06</title>` (date may vary).
  3. `test_accuracy_title_includes_preset`: GET `/produccion/accuracy?preset=7d` body contains `<title>Producción · Precisión (7 días)</title>`.

**Implementation:**

1. **`app/routers/produccion.py:1276` (`produccion_shift_execute`):**
   - Add `MAX(for_date) = today_asuncion` validation; raise `HTTPException(400, "for_date futura o muy pasada")` if `for_date > today` or `for_date < today - 7 days` (the 7-day window is a per-deployment setting; add to `app/rms/config.py` as `BACKDATE_WINDOW_DAYS = 7`).
   - **The shift-checkbox silent-loss fix:** the HTML form at `produccion.html:610-615` posts a `done_<product_id>=1` checkbox on the same form. Currently the route ignores it. Add: for every `done_<pid>=1` field, upsert a `ProductionCompletion` row with `status='done'` and `completed_qty=existing_or_0`. The stepper input `completed_<pid>` already updates the qty.
   - Add **idempotency**: store a `request_id` (UUID) on the form; if the same UUID is posted twice within 60s, return the same response (don't double-write audit / completion rows). Mirror the `/eod/check` pattern at `eod.py:122-129` (`idempotency_key`).

2. **`app/routers/produccion.py:1551` (`produccion_close_day`):**
   - Already has idempotency in the `eod_completions.close_day_for_product` helper. Verify the audit-row dedup with the new test. Fix any path that still duplicates.

3. **`app/templates/produccion.html` (the day view):**
   - **Rename columns** (M2 → blocker from audit):
     - `Meta` → `Meta (unidades)` with subtitle "lo que el plan dice" and a `?` icon that opens the confidence-band modal (Phase 2 deliverable, stub for now)
     - `+ Pedidos` → `Ya comprometido (pedidos)` with subtitle "no se puede obviar"
     - `Total a hornear` → `Lote final` with subtitle "= meta + comprometidos"
     - `Progreso` → `Hecho` (the input lives here; rename makes the intent clear)
   - **Title block (line 20):** `{% block title %}{% if view == 'day' %}Producción · {{ for_date }}{% elif view == 'week' %}Producción · Semana del {{ week_start }}{% elif view == 'month' %}Producción · {{ month_name }} {{ year }}{% endif %}{% endblock %}`
   - **Remove the dead `v2 ✨` pill** at `line 80-85` (v1 was removed per the inline comment, the toggle is misleading)

4. **`app/templates/produccion_manana.html:15`:** `{% block title %}Producción · Mañana {{ tomorrow }}{% endblock %}`

5. **`app/templates/produccion_accuracy.html:3`:** `{% block title %}Producción · Precisión ({{ days_in_period }} días){% endblock %}`

**Acceptance:**
- [ ] `pytest tests/test_produccion_checkbox_persists.py tests/test_produccion_backdate_cap.py tests/test_produccion_close_day_idempotent.py tests/test_produccion_vocabulary.py tests/test_produccion_page_titles.py -v` → all pass
- [ ] `pytest tests/ -q --no-cov` → no regressions (all 552 pre-existing tests still pass)
- [ ] Live: `curl -b cookies.txt https://saskia-vps.paragu-ai.com/produccion | grep -E "Meta|Hecho|Lote final"` shows the new headers
- [ ] Live: title `<title>Producción · 2026-10-05</title>` visible in the browser tab
- [ ] CHANGELOG entry under `## [unreleased]` → `### Fixed` → list all 4 fixes

**Hours:** 2-4h (3h typical)

---

# PHASE 1 — Day navigation + date nav (audit H2, M2, M7, M18)

**Goal:** Add a sticky date-nav control to the day view, fix the `for_date` URL pattern, and add prev/next/today/picker.

**Why phase 1:** The audit found 5 findings (H2, M2, M7, M18, M20) all rooted in missing date navigation. Without it, every other phase's UI changes still leave the cook unable to flip between days.

**Test files:**

- `tests/test_produccion_day_nav.py` — 4 tests
  1. `test_day_nav_renders_prev_today_next`: GET `/produccion?for_date=2026-10-05` body contains the day-nav HTML (`<nav class="day-nav" data-day-nav>`).
  2. `test_prev_link_computes_yesterday`: day-nav's prev link points to `/produccion?for_date=2026-10-04`.
  3. `test_today_link_always_returns_today`: day-nav's "Hoy" link points to `/produccion?for_date={{ today }}` regardless of `for_date` param.
  4. `test_date_picker_input_value_matches_for_date`: the `<input type="date">` in the day-nav has `value="2026-10-05"`.

- `tests/test_produccion_for_date_backdate_window.py` — 2 tests (extend Phase 0's backdate cap)
  1. `test_produccion_get_within_window_ok`: GET `/produccion?for_date=2026-09-28` (8 days ago) → 200 (within 7-day window from 2026-10-05 is the boundary; accept 7 or reject 8 based on config).
  2. `test_produccion_get_far_past_returns_400`: GET `/produccion?for_date=2020-01-01` → 400 with friendly Spanish error.

**Implementation:**

1. **`app/templates/_components/day_nav.html` (NEW partial):**
   ```jinja
   <nav class="day-nav" data-day-nav aria-label="Navegación de fecha" 
        style="display:inline-flex; align-items:center; gap:var(--space-2); 
               background:var(--color-surface-subtle); padding:var(--space-1) var(--space-2); 
               border-radius:var(--radius);">
     {% set prev = for_date_min_1 %}
     {% set next = for_date_plus_1 %}
     <a href="?for_date={{ prev }}{% if shift %}&shift={{ shift }}{% endif %}" 
        class="btn btn-ghost btn-icon" aria-label="Día anterior">‹</a>
     <form method="get" action="/produccion" style="display:inline-flex; gap:var(--space-1);">
       <input type="date" name="for_date" value="{{ for_date }}" 
              aria-label="Elegí una fecha" class="form-input">
       <button type="submit" class="btn btn-sm">Ir</button>
     </form>
     <a href="?for_date={{ today }}" class="btn btn-sm {% if for_date == today %}btn-primary{% else %}btn-ghost{% endif %}">Hoy</a>
     <a href="?for_date={{ next }}{% if shift %}&shift={{ shift }}{% endif %}" 
        class="btn btn-ghost btn-icon" aria-label="Día siguiente">›</a>
   </nav>
   ```

2. **`app/routers/produccion.py:217` (`produccion_worksheet`):** Compute `prev`, `next`, `today` (Asunción local) and pass to template.

3. **`app/templates/produccion.html:36-124`:** Insert the partial at the top of the day-view branch, before the v1 plan row. Pass `for_date` context. Hide on print (`@media print { .day-nav { display: none; } }` — add to `app.css`).

4. **`app/static/ui-day-nav.js` (NEW, ~40 lines):** Keyboard shortcut: pressing `t` jumps to today, `[` jumps to prev day, `]` jumps to next day. Add to the existing `app/static/shortcuts.js` registration.

5. **`app/static/app.css`:** Add the `.day-nav` + `.day-nav input[type=date]` styles (~20 lines). Re-theme for dark mode.

**Acceptance:**
- [ ] `pytest tests/test_produccion_day_nav.py tests/test_produccion_for_date_backdate_window.py -v` → all pass
- [ ] `pytest tests/ -q --no-cov` → no regressions
- [ ] Live: `curl -sS -b cookies.txt https://saskia-vps.paragu-ai.com/produccion?for_date=2026-10-05` shows the day-nav at the top
- [ ] Click "Día anterior" → URL changes to `?for_date=2026-10-04`
- [ ] Type a date in the picker, click "Ir" → navigates to that date
- [ ] CHANGELOG entry under `### Added`

**Hours:** 3-5h (4h typical)

---

# PHASE 2 — Vocabulary unification + badge legend (audit M1, M3, L17, H1, H3, H4, L11, M10)

**Goal:** One vocabulary across all production pages. Visible legend for the badges. Standard color tokens for confidence + source pills.

**Test files:**

- `tests/test_produccion_vocabulary_consistent.py` — 6 tests
  1. `test_only_one_adhoc_term_per_page`: `/produccion` body contains EITHER "Ad-hoc" OR "Horneado extra" but NOT both as the same concept in different places. (Pick **"Horneado extra"** in the UI; keep "ad_hoc" only in DB column names and the `is_ad_hoc` Python attribute.)
  2. `test_only_one_override_term`: body uses **"Manual"** (not "Override" / "Ajuste") in the UI; the badge text on the Origen column is "Manual" everywhere.
  3. `test_only_one_forecast_term`: body uses **"Sugerido por ventas"** (not "rolling_14d_avg" or "Forecast" or "rolling 14d") in user-facing copy.
  4. `test_manana_page_uses_same_vocabulary`: `/produccion/manana` body does NOT contain "rolling" as a label (it can be in `<title>` or `data-*` attrs but not in cell text).
  5. `test_source_legend_present`: `/produccion` body contains the legend block (`<aside class="source-legend" data-source-legend>`) with all 4 source names visible.
  6. `test_allergen_count_shown`: rows with `recipe_allergens` containing 5+ items show "+N más" in the badge (e.g. "gluten, maní, soja +3 más").

- `tests/test_produccion_badge_legend.py` — 2 tests
  1. `test_legend_has_4_distinct_colors`: the 4 source badges in the legend have 4 distinct `background-color` values (one per source).
  2. `test_legend_does_not_use_warning_color_for_manual`: the "Manual" badge in the legend does NOT use `var(--color-warning)` (which is amber-500-ish).

- `tests/test_produccion_recipe_allergens.py` — 3 tests
  1. `test_allergen_count_rendered`: POST a product with 6 allergens, GET `/produccion` body for that row contains "+3 más" (showing 3 + 3 more).
  2. `test_allergen_count_zero_hidden`: a product with no allergens does not render the allergen badge.
  3. `test_allergen_full_list_in_title`: the badge's `title` attribute contains the comma-joined full list (for hover/long-press).

**Implementation:**

1. **`app/templates/produccion.html:738-748` (Origen cell):** Replace the per-case `{% if %}` chain with a single macro call. New macro in `app/templates/_components/macros.html`:
   ```jinja
   {% macro source_badge(source, is_ad_hoc=False) -%}
     {%- if is_ad_hoc -%}
       <span class="badge badge-source-adhoc" data-source="adhoc" 
             title="Horneado no planeado (walk-in, decisión de último momento)">Horneado extra</span>
     {%- elif source == 'override' -%}
       <span class="badge badge-source-override" data-source="override" 
             title="Vos decidiste esta cantidad para este día">Manual</span>
     {%- elif source == 'template' -%}
       <span class="badge badge-source-template" data-source="template" 
             title="Plantilla semanal recurrente (mismo cada lunes)">Plantilla</span>
     {%- elif source == 'manual' -%}
       <span class="badge badge-source-manual" data-source="manual" 
             title="Ajuste explícito del operador (mismo que override)">Manual</span>
     {%- else -%}
       <span class="badge badge-source-forecast" data-source="forecast" 
             title="Promedio de los últimos 14 días de ventas">Sugerido por ventas</span>
     {%- endif -%}
   {%- endmacro %}
   ```
   Note: 'override' and 'manual' are merged conceptually in the UI (both = "you typed it") even though the DB distinguishes them.

2. **`app/templates/produccion.html` (NEW legend block, just above the day-view table):**
   ```jinja
   <aside class="source-legend" data-source-legend aria-label="Leyenda de fuentes del plan"
          style="background:var(--color-surface-subtle); padding:var(--space-2) var(--space-3); 
                 border-radius:var(--radius); margin-bottom:var(--space-3); 
                 display:flex; gap:var(--space-3); align-items:center; flex-wrap:wrap; font-size:var(--text-sm);">
     <strong>Origen del número:</strong>
     {{ m.source_badge('forecast') }}
     {{ m.source_badge('template') }}
     {{ m.source_badge('override') }}
     {{ m.source_badge('adhoc', is_ad_hoc=True) }}
     <button type="button" class="btn btn-ghost btn-sm" data-action="open-confidence-help" aria-label="¿Cómo se calcula la confianza?">¿Cómo se calcula?</button>
   </aside>
   ```

3. **`app/templates/produccion_manana.html:138-156`:** Replace the 3-branch `{% if row.forecast_source %}` chain with `{{ m.source_badge(row.forecast_source) }}`. Remove the duplicate `<style>` block at line 220-236 (move to `app.css`).

4. **`app/static/app.css` (or `app-components.css`):** Add `.badge-source-*` color tokens (5 variants: forecast, template, override, manual, adhoc). Distinct from existing `.badge-warning`, `.badge-info`, `.badge-primary`, `.badge-muted`. Use the semantic triad pattern (`--color-source-{name}-bg`, `--color-source-{name}-fg`) so dark mode flips cleanly.

5. **`app/templates/produccion.html:618` (the "Extra" badge in the Producto cell):** Rename to "Horneado extra" (matches the macro). Add a tooltip "Horneado no planeado (walk-in, decisión de último momento)".

6. **`app/templates/produccion.html:629-636` (allergen badge):** Add the count: `{% set remaining = allergen_list|length - 3 %}{% if remaining > 0 %} +{{ remaining }} más{% endif %}`.

7. **`app/templates/produccion_manana.html:52` (Ingreso estimado subtitle):** Rename `precio catálogo × cantidad` to `= precio catálogo × meta del plan` and add `<small>No incluye real ni pedidos</small>`.

**Acceptance:**
- [ ] All 3 test files pass
- [ ] `pytest tests/ -q --no-cov` → no regressions
- [ ] Live: `/produccion` shows the legend block above the table; the 4 source badges have 4 distinct background colors; "Manual" does NOT use amber/warning color
- [ ] Live: `/produccion/manana` uses the same source-badge macro (visually identical badges to `/produccion`)
- [ ] `grep -rE "Override|Override|Ajuste manual" app/templates/produccion*.html` returns 0 user-facing results (only in code comments / data attributes)
- [ ] CHANGELOG entry

**Hours:** 4-6h (5h typical)

---

# PHASE 3 — Shared `production_row_editor` partial + consolidate the qty input (audit M6, M11, M14, L4, L7)

**Goal:** One source of truth for the per-row qty + cierre + merma controls. Used by `/produccion` day view AND `/eod`. Both pages currently have divergent implementations writing to the same DB table.

**Test files:**

- `tests/test_produccion_row_editor_partial.py` — 3 tests
  1. `test_partial_renders_for_each_row`: GET `/produccion` body contains `_components/production_row_editor.html` references (e.g. `data-row-editor="..."` or `class="row-editor"` on each row).
  2. `test_eod_uses_same_partial`: GET `/eod` body for the "Producción del día" table contains the same `data-row-editor` markers.
  3. `test_partial_renders_stepper_with_correct_step`: products with `unit in ('kg', 'l')` have `step="0.5"`; products with `unit == 'und'` have `step="1"`.

- `tests/test_produccion_stepper_unit_step.py` — 3 tests
  1. `test_und_product_uses_step_1`: row for a product with `unit='und'` has `step="1"` on the qty input.
  2. `test_kg_product_uses_step_0_5`: row for a product with `unit='kg'` has `step="0.5"`.
  3. `test_pz_product_uses_step_1`: `unit='pz'` (pizza) uses integer step (it's a discrete unit).

- `tests/test_eod_inline_completion_uses_partial.py` — 2 tests
  1. `test_eod_qty_input_min_0`: `/eod` body qty input has `min="0"`.
  2. `test_eod_qty_input_persists_via_partial`: posting to `/eod/completar` writes to the same `production_completion` table that `/produccion/shift-execute` writes to (verify with raw SQL after both POSTs).

**Implementation:**

1. **`app/templates/_components/production_row_editor.html` (NEW partial):**
   ```jinja
   {# Per-row editor: qty stepper + cerrar turno + merma button.
      Used by /produccion and /eod. Context vars expected:
        - product: {id, name, recipe_id, unit, completed_qty, closure_status, closure_notes}
        - for_date: ISO date string
        - can_edit: bool (False when day is closed)
        - merma_url: pre-built URL or None
   #}
   <div class="row-editor" data-row-editor data-product-id="{{ product.id }}">
     <div class="qty-stepper" data-target-qty="{{ product.qty_to_produce or 0 }}">
       <button type="button" class="step-btn step-down" data-step="down" 
               aria-label="Restar 1 a {{ product.name }}" 
               onclick="stepRow(this, -1)"{% if not can_edit %} disabled{% endif %}>−</button>
       <input type="number" name="completed_{{ product.id }}" 
              class="progress-input" 
              value="{{ "%.1f"|format(product.completed_qty or 0) }}" 
              min="0" 
              step="{{ '0.5' if product.unit in ('kg', 'l') else '1' }}"
              style="width: 70px;" 
              aria-label="Cantidad hecha de {{ product.name }}"
              {% if not can_edit %}readonly{% endif %}>
       <button type="button" class="step-btn step-up" data-step="up" 
               aria-label="Sumar 1 a {{ product.name }}" 
               onclick="stepRow(this, +1)"{% if not can_edit %} disabled{% endif %}>+</button>
     </div>
     <div class="row-editor__closure" data-closure-status="{{ product.closure_status or 'open' }}">
       {%- set cs = product.closure_status or 'open' -%}
       {%- if cs == 'done' -%}
         <span class="closure-pill closure-done">✅ Cerrado</span>
         <button type="button" class="btn btn-ghost btn-sm" 
                 data-action="reopen-row" data-product-id="{{ product.id }}" 
                 data-product-name="{{ product.name }}">Reabrir</button>
       {%- elif cs == 'cancelled' -%}
         <span class="closure-pill closure-cancelled">⊘ No horneado</span>
         <button type="button" class="btn btn-ghost btn-sm" 
                 data-action="reopen-row" data-product-id="{{ product.id }}">Reabrir</button>
       {%- else -%}
         <button type="button" class="btn btn-primary btn-sm" 
                 data-action="close-row" 
                 data-product-id="{{ product.id }}" 
                 data-product-name="{{ product.name }}" 
                 data-completed-qty="{{ product.completed_qty or 0 }}" 
                 data-target-qty="{{ product.qty_to_produce or 0 }}">
           Cerrar turno ({{ "%.0f"|format(product.completed_qty or 0) }}/{{ "%.0f"|format(product.qty_to_produce or 0) }})
         </button>
       {%- endif -%}
     </div>
     {%- if merma_url -%}
     <button type="button" class="btn btn-sm btn-ghost" 
             data-quick-merma data-recipe-id="{{ product.recipe_id or '' }}" 
             data-product-name="{{ product.name }}" onclick="openQuickMerma(this)">
       🔥 Merma
     </button>
     {%- endif -%}
   </div>
   ```

2. **`app/templates/produccion.html:711-735` (Progreso cell) and `857-886` (Cierre cell):** Replace with `{% include "_components/production_row_editor.html" %}` passing the context. Drop the inline stepper / cerrar turno HTML.

3. **`app/templates/eod.html:245-275` (Producción del día table):** Replace the inline `<form action="/eod/completar">` with the partial. The `/eod` page can no longer have a divergent qty input.

4. **`app/static/app.css`:** Add `.row-editor`, `.row-editor__closure`, `.closure-pill` styles (~30 lines). Add the unit-based stepper step.

5. **`app/routers/eod.py:378` (`eod_completar`):** Ensure it writes via the SAME helper as `/produccion/close-day`. If they currently diverge, refactor to share `app/rms/eod_completions.close_day_for_product` (which they should already; verify).

6. **`app/static/app-components.js`:** Augment `openQuickMerma(this)` to handle products with `recipe_id == null` (currently the code probably crashes for those — verify and add a guard).

**Acceptance:**
- [ ] All 3 test files pass
- [ ] `pytest tests/ -q --no-cov` → no regressions
- [ ] Live: post a `completed_qty=5` to `/produccion/shift-execute`, then GET `/eod` → the "Hecho" cell for that row shows `5`
- [ ] Live: change stepper for a `unit='kg'` product → step is 0.5; for a `unit='und'` product → step is 1
- [ ] `grep -rE "display:inline-flex" app/templates/produccion.html` → 0 hits in the row editor (was ~3)
- [ ] CHANGELOG entry

**Hours:** 5-7h (6h typical)

---

# PHASE 4 — Confidence-band modal + heuristic help (audit M4, L11, M5)

**Goal:** A clickable `?` opens a modal explaining how the forecast and confidence are calculated. Replaces the inline `<small>` help text and the keyboard-hint clutter.

**Test files:**

- `tests/test_produccion_confidence_modal.py` — 4 tests
  1. `test_modal_present_in_dom`: `/produccion` body contains `<dialog id="confidence-help-modal">`.
  2. `test_modal_lists_5_bands`: the modal body lists 5 bands: sin datos, baja (1-49%), media (50-69%), alta (70-100%), 100% (manual).
  3. `test_modal_explains_heuristic`: the modal body contains the explanation text "rolling 14d" + "many sales" + "review manually".
  4. `test_modal_trigger_wired`: the `<button data-action="open-confidence-help">` exists somewhere in the day view.

- `tests/test_produccion_kbd_hint_responsive.py` — 2 tests
  1. `test_kbd_hint_visible_default`: the day-view body contains the `<small class="kbd-hint">` (existing).
  2. `test_kbd_hint_aria_hidden_on_mobile`: the kbd-hint has `aria-hidden="true"` when the viewport is <768px (verified via the inline class `.kbd-hint--mobile-hidden` — see impl).

**Implementation:**

1. **`app/templates/produccion.html` (NEW modal, near the end of the day view, before `{% endif %}`):**
   ```jinja
   <dialog id="confidence-help-modal" class="help-modal" 
            aria-labelledby="confidence-help-title" 
            style="border:none; border-radius:8px; padding:0; max-width:520px; box-shadow:var(--shadow-lg);">
     <form method="dialog" style="padding:var(--space-4);">
       <h3 id="confidence-help-title" style="margin:0 0 var(--space-3) 0;">
         ¿Cómo se calcula la sugerencia y la confianza?
       </h3>
       <p>El sistema mira las ventas de los últimos <strong>14 días</strong> del mismo día de la semana (lunes mira solo lunes, martes mira solo martes, etc.). Si no hay datos, usa el promedio de los 14 días sin importar el día.</p>
       <h4 style="margin:var(--space-3) 0 var(--space-1) 0;">Las 5 bandas de confianza</h4>
       <ul style="list-style:none; padding:0; margin:0;">
         <li><span class="confidence-pill conf-zero">0%</span> Sin datos de venta — definí manualmente</li>
         <li><span class="confidence-pill conf-low">25%</span> 1 venta registrada — muy poca información</li>
         <li><span class="confidence-pill conf-low">40%</span> 2 ventas — revisá antes de hornear</li>
         <li><span class="confidence-pill conf-medium">60%</span> 3-13 ventas — considerá ajustar</li>
         <li><span class="confidence-pill conf-high">85%</span> 14+ ventas en 14+ días — alta confianza</li>
       </ul>
       <h4 style="margin:var(--space-3) 0 var(--space-1) 0;">Cómo cambiar la sugerencia</h4>
       <ol>
         <li><strong>Una vez (hoy):</strong> usá el botón "Override" en la columna Origen</li>
         <li><strong>Todos los lunes:</strong> andá a <a href="/produccion?view=week">vista semana</a> y guardá un plan semanal</li>
         <li><strong>Para siempre:</strong> cambiá la cantidad de horneado histórico editando las ventas pasadas</li>
       </ol>
       <div style="display:flex; gap:var(--space-2); justify-content:flex-end; margin-top:var(--space-3);">
         <button type="submit" class="btn btn-primary">Cerrar</button>
       </div>
     </form>
   </dialog>
   ```

2. **`app/static/app-components.js`:** Add a listener for `data-action="open-confidence-help"` that calls `document.getElementById('confidence-help-modal').showModal()`.

3. **`app/templates/produccion.html:540-545` (kbd-hint):** Add `class="kbd-hint kbd-hint--mobile-hidden"` and add the CSS rule:
   ```css
   @media (max-width: 767px) { .kbd-hint--mobile-hidden { display: none; } }
   ```
   The "mobile-hidden" suffix is opt-in so we don't break other pages.

4. **`app/templates/produccion.html:447-466` (confidence summary banner):** Replace the `<span>` pill list with a single `<button data-action="open-confidence-help">` that opens the modal. The summary now reads:
   ```jinja
   <div class="card confidence-summary-banner" ...>
     <div>
       <strong>⚠️ {{ low_confidence_count }} producto{{ 's' if low_confidence_count != 1 else '' }} con baja confianza</strong>
       <p class="text-muted" style="...">Las cantidades son estimaciones. Revisá antes de hornear.</p>
     </div>
     <button type="button" class="btn btn-secondary" data-action="open-confidence-help">
       <svg class="icon"><use href="#icon-help"/></svg>
       ¿Cómo se calcula la confianza?
     </button>
   </div>
   ```

**Acceptance:**
- [ ] All 2 test files pass
- [ ] `pytest tests/ -q --no-cov` → no regressions
- [ ] Live: click the `?` button on the confidence banner → modal opens, explains 5 bands
- [ ] Live: on a 375px-wide viewport (mobile), the keyboard hint is hidden (no `J/K/O/C` text visible)
- [ ] CHANGELOG entry

**Hours:** 2-3h (2.5h typical)

---

# PHASE 5 — Inline-style cleanup on the 5 most common patterns (audit H2, L1, M13, M14, L3, L17)

**Goal:** Replace the 740 inline `style="..."` attributes on `/produccion` with component classes. Focus on the top-5 patterns (143 + 73 + 62 + 25 + 25 = 328 attributes = 44% of the inline styles).

**Test files:**

- `tests/test_produccion_no_common_inline_styles.py` — 5 tests
  1. `test_no_color_muted_foreground_inline`: body does NOT contain `style="color: var(--color-muted-foreground); font-size: 11px;"` (use `class="text-meta"` instead).
  2. `test_no_font_weight_600_inline_alone`: body does NOT contain `style="font-weight: 600;"` standalone (use `class="font-bold"` or context).
  3. `test_no_flex_wrap_gap_inline`: body does NOT contain `style="margin-top: var(--space-1); display: flex; flex-wrap: wrap; gap: var(--space-1);"` (use `class="chip-row"`).
  4. `test_no_margin_right_space_1_inline`: body does NOT contain `style="margin-right: var(--space-1);"` standalone (use `class="mr-1"`).
  5. `test_no_danger_red_alpha_inline`: body does NOT contain `style="background: rgba(220, 38, 38, 0.08);"` (use `class="alert-danger-soft"`).

- `tests/test_produccion_dark_mode_contrast.py` — 3 tests (uses `axe-core` if available, else manual contrast check)
  1. `test_shift_am_pill_dark_mode_contrast`: with `data-theme="dark"`, the `.shift-pill--am` background and text contrast ratio ≥ 4.5:1 (WCAG AA).
  2. `test_confidence_pill_medium_dark_mode_contrast`: with `data-theme="dark"`, the `.conf-medium` pill has contrast ≥ 4.5:1.
  3. `test_allergen_badge_dark_mode_contrast`: with `data-theme="dark"`, the `.allergen-badge` contrast ≥ 4.5:1.

**Implementation:**

1. **`app/static/app.css` (or new `app/static/production.css`):** Add 5 component classes:
   ```css
   .text-meta { color: var(--color-muted-foreground); font-size: 11px; }
   .font-semibold { font-weight: 600; }
   .chip-row { display: flex; flex-wrap: wrap; gap: var(--space-1); }
   .mr-1 { margin-right: var(--space-1); }
   .alert-danger-soft { background: rgba(220, 38, 38, 0.08); }
   .alert-warning-soft { background: rgba(245, 158, 11, 0.08); }
   .alert-success-soft { background: rgba(34, 197, 94, 0.08); }
   .alert-info-soft { background: rgba(59, 130, 246, 0.08); }
   .shift-pill--am { background: var(--color-warning-bg, #fef3c7); color: var(--color-warning-fg, #92400e); border: 1px solid var(--color-warning-border, #fbbf24); }
   .shift-pill--pm { background: var(--color-info-bg, #e0e7ff); color: var(--color-info-fg, #3730a3); border: 1px solid var(--color-info-border, #818cf8); }
   ```
   Define the dark-mode variants in `:root[data-theme="dark"]`.

2. **`app/templates/produccion.html` (and `produccion_manana.html`):** Use `sed` (or careful find-and-replace) to replace the 5 most common inline patterns with the classes. Run the existing test suite after each pattern to catch regressions.

3. **`app/templates/produccion.html:52` (shift-badge):** Replace the hard-coded `#fef3c7` / `#92400e` etc. with the new `.shift-pill--am` / `.shift-pill--pm` classes. Remove the inline `style="..."`.

4. **`app/static/shortcuts.js`:** Verify the `J/K/O/C/?` shortcuts work on the day view. Add a `t` shortcut (today) per Phase 1.

5. **Counting verification:** After all replacements:
   ```bash
   grep -c 'style="' /app/app/templates/produccion.html
   # Was: 740. Target after Phase 5: < 200.
   ```

**Acceptance:**
- [ ] All 2 test files pass
- [ ] `pytest tests/ -q --no-cov` → no regressions
- [ ] `wc -l app/static/app.css` does not grow by more than 100 lines (we're consolidating, not adding)
- [ ] Inline-style count on `/produccion` drops below 200 (from 740)
- [ ] Live: switch to dark mode → confidence pills, shift badge, allergen badge, ad-hoc row all re-theme correctly (no white-on-white or hard-coded amber-100)
- [ ] CHANGELOG entry

**Hours:** 4-6h (5h typical)

---

# PHASE 6 — Polish: date pickers, grouping, EOD progress, ad-hoc top placement (audit L1, L8, M12, M14, M17, M18, M19, L20, L5, L12)

**Goal:** Ship the remaining low/medium items as a single polish phase.

**Sub-tasks:**

| # | Audit ref | Change | Est. |
|---|---|---|---|
| 6.1 | L1 | Browser tab title includes the date / range for all 3 production pages | 0.5h |
| 6.2 | L8 | Translate "Worksheet en blanco" → "Planilla en blanco" (or "Hoja de trabajo en blanco") — pick one | 0.25h |
| 6.3 | M12 | Group the 5 header CTAs into "Primary" (Mañana + Imprimir) and "Secondary" (Worksheet + Precisión + Prep semanal) | 1h |
| 6.4 | M14 | Add `b` keyboard shortcut for the bulk CSV ad-hoc modal | 0.25h |
| 6.5 | L17 | Standardize "Horneado extra" everywhere; remove "Ad-hoc" badge text from UI | 0.5h |
| 6.6 | M18 | Move the "Horneado extra" form above the main table OR show a "Volver arriba" link after save | 1h |
| 6.7 | M19 | Add "Exportar a Excel" button on `/produccion` and `/produccion/manana` (uses `openpyxl`, already a dep) | 2h |
| 6.8 | L5 | `/eod?start=&end=` shows the date range in the heading subtitle | 0.25h |
| 6.9 | L12 | EOD checklist: milestone indicators at 50% and 100%, auto-scroll the Save button at 100% | 1h |
| 6.10 | L20 | `current_user.last_seen` bump on every authenticated GET (5-line `app.auth.bump_last_seen` helper) | 0.5h |
| 6.11 | M17 | Rename "Cerrar turno" cell header to "Cerrar / Reabrir" | 0.1h |
| 6.12 | L13 | Add `MAX(for_date) = today_asuncion - 7 days` GET-window for `/produccion` (read-only views OK far back, write POSTs are rejected) | 0.5h |
| 6.13 | M16 | `/produccion/manana` "Ingreso potencial" card adds a confidence sub-line | 0.5h |
| 6.14 | L6 | `/eod` reorder list: per-row "Marcar resuelto" CTA that POSTs to `/reorder/mark-resolved` (already a route — verify and add the link) | 0.5h |

**Test files:**

- `tests/test_produccion_tab_title_date.py` — 1 test
- `tests/test_produccion_export_xlsx.py` — 3 tests (download, content, no PHP errors)
- `tests/test_eod_milestones.py` — 2 tests
- `tests/test_last_seen_bumped.py` — 2 tests
- `tests/test_produccion_get_date_window.py` — 1 test
- `tests/test_reorder_mark_resolved.py` — 2 tests

**Total tests added in Phase 6:** ~11

**Acceptance:**
- [ ] All 6 test files pass
- [ ] `pytest tests/ -q --no-cov` → no regressions
- [ ] Live: open `/produccion` and `/produccion/manana` in two browser tabs → tab titles differ
- [ ] Live: click "Exportar a Excel" on the day view → downloads an `.xlsx` with one row per product
- [ ] Live: at EOD 50% checklist complete → a "¡Mitad del camino!" toast appears
- [ ] CHANGELOG entry

**Hours:** 9-10h total (spread across 1-2 sessions)

---

# Cross-cutting — Documentation updates

Per phase, update:

1. **`app/CHANGELOG.md`** — entry per phase under `## [unreleased]` with the bullet list
2. **`docs/user-guide/06-produccion.md`** — rewrite the "How production works" walkthrough to use the new vocabulary (Manual / Plantilla / Sugerido / Horneado extra)
3. **`docs/user-guide/07-eod.md`** — add a section on the new confidence-band modal and the "in plan / over / under" delta indicators
4. **`docs/operations/2026-09-24-deployment.md`** — note the new `BACKDATE_WINDOW_DAYS` env var (defaults to 7)
5. **Migration / DB note** — no DB changes in this plan, but the `ProductionCompletion.last_modified_by`/`last_modified_at` columns (audit M6) might be a follow-up; note in the post-merge doc that the future migration is needed

---

# Cross-cutting — Test gate (CI)

Add a single Playwright-free e2e test that catches the most critical flow end-to-end:

`tests/e2e/test_produccion_full_flow.py` — 1 scenario:

```python
def test_full_day_flow(client, db_session):
    """Cook opens /produccion, closes all rows, /eod shows the same numbers."""
    # 1. Login as demo
    # 2. POST /produccion/close-day for each row in today's plan
    # 3. GET /eod → assert "Hecho" column shows the closed values
    # 4. GET /produccion?view=week → assert the weekly aggregate reflects the day
    # 5. POST /produccion/shift-execute with checkbox unchecked → assert it persists
    # 6. GET /produccion?for_date=YESTERDAY → 200, shows yesterday's data
    # 7. GET /produccion?for_date=TOMORROW → 200, shows tomorrow's plan
```

This test catches regressions in: login, the close-day write, the /eod read, the week-view aggregation, the checkbox silent-loss fix, the day-nav, and the title format. It's the single test that fails if the whole plan is rolled back.

**Hours:** 1h to write + wire into CI

---

# Cross-cutting — Deploy discipline

Per `2026-09-30-deploy-urgent.md` and the `saskia-rms-deploy-flow` skill:

- Each phase ships as a **single PR → squash merge to `main` → auto-deploy to VPS**
- Before merge: `pytest tests/ -q --no-cov` (must pass with no new failures)
- After deploy: `curl -sk https://saskia-vps.paragu-ai.com/healthz` → 200; `curl -sk .../healthz/schema` → schema_version unchanged
- **No mid-day deploys** for the cook; batch all 6 phase deploys at 17:00 (after Asunción bakery close)
- **DB backup before Phase 0 deploy** (since the close-day path is exercised)

---

# Risk register

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Phase 0's checkbox-persistence fix breaks the existing `done_X` semantics in some test | Medium | Medium | Run full test suite after the change; the new test file catches the intended behavior, but other tests might assert the OLD behavior — update those |
| The `for_date` backdate cap is too strict (operator legitimately needs to backfill a week of missed days) | Low | Medium | Make the cap configurable via `BACKDATE_WINDOW_DAYS` env var (default 7); bump to 30 if needed |
| The shared `production_row_editor` partial changes the visual layout and a cook reports "the page looks different" | High | Low | This is intentional; document the change in the user-guide, NOT in the UI itself |
| Dark-mode contrast regressions after the inline-style cleanup | Medium | High | Phase 5 has explicit contrast tests; if they fail, fix the token, do NOT ship |
| The `production_row_editor` partial breaks the e2e flow because `/eod` and `/produccion` previously had different DOM selectors that some JS depended on | Medium | Medium | After Phase 3, run a full Playwright-style smoke test (the e2e one above) before merge |
| The 6-phase plan takes 4 weeks of work (worst case) and the cook gets impatient | Medium | Low | Ship Phase 0 + Phase 1 (the blockers) in the first session; show progress; the user has seen the audit and agrees to the plan |

---

# Hours total

| Phase | Min | Typical | Max |
|---|---|---|---|
| 0 — Blockers | 2h | 3h | 4h |
| 1 — Day nav | 3h | 4h | 5h |
| 2 — Vocabulary | 4h | 5h | 6h |
| 3 — Row editor partial | 5h | 6h | 7h |
| 4 — Confidence modal | 2h | 2.5h | 3h |
| 5 — Inline-style cleanup | 4h | 5h | 6h |
| 6 — Polish | 9h | 9.5h | 10h |
| Cross-cutting (e2e + docs) | 4h | 5h | 6h |
| **TOTAL** | **33h** | **40h** | **47h** |

Spread across 6-8 sessions of 4-6 hours each = 1-2 weeks of part-time work, or 4-5 days of focused work.

---

# What ships NOT in this plan (and why)

These came up in the audit but are out of scope. Each is a separate plan to avoid scope creep.

1. **The full design-system migration** (740 inline styles → 100% tokens) — Phase 5 only handles the top-5 patterns. A complete migration is a 5-phase plan of its own.
2. **Tailwind removal** (the `producto_detalle.html` page uses Tailwind classes that aren't loaded) — already flagged in `2026-10-03-ux-hardening-plan.md` scope guardrail #2.
3. **The bulk ad-hoc CSV import has no help text on product_id lookup** — minor; fix in 30 min as a 1-line PR.
4. **The `last_login_at` not updating after the user works** — addressed in Phase 6 (L20) but only the `last_seen` bump; `last_login_at` is a separate concern (it's set at login time only).
5. **The i18n to Guaraní** — out of scope; this is a Spanish-only app for now.
6. **The `production_completion` ownership/edited-by column** (audit M6) — needs a DB migration; deferred to a follow-up.
7. **Reorder-list "mark resolved" functionality** (audit L6) — covered by `tests/test_reorder_mark_resolved.py` if the route exists; otherwise, follow-up.

---

# Acceptance for the whole plan

When all 6 phases + cross-cutting are done:

- [ ] **No new tests fail:** `pytest tests/ -q --no-cov` shows 0 failures (current baseline: 552 passing, X failing pre-existing)
- [ ] **The 5-blocker audit items are all closed:** Meta column explains units, Progreso renamed, + Pedidos / Total a hornear disambiguated, DEMANDA column not hidden, Cerrar turno shows qty preview
- [ ] **The 16-medium audit items are all closed:** day nav exists, vocabulary is one, allergen count shown, etc.
- [ ] **The 20-low audit items are all closed or deferred with a comment** in `IMPROVEMENT_BACKLOG.md`
- [ ] **The e2e flow test passes:** `pytest tests/e2e/test_produccion_full_flow.py` shows the cook's full day works
- [ ] **No new prod dependencies** (per AGENTS.md rule #1)
- [ ] **Coverage does not drop below 35%** (per the current floor; do not bump in this plan)
- [ ] **CHANGELOG.md is updated per phase**
- [ ] **User guide (`docs/user-guide/06-produccion.md`) reflects the new vocabulary**
- [ ] **No midnight deploys; the operator (cook) is not surprised by a UI change mid-shift**

---

# Open question for the operator (Ivan)

Before I start Phase 0, **one clarification** that affects the column renames and the vocabulary unification:

> The audit's recommendation is to use the term **"Horneado extra"** (instead of "Ad-hoc" or "Extra") because it's the most descriptive Spanish term. But your existing user-guide and CHANGELOG use "Ad-hoc" in 14 places. Two paths:
>
> 1. **Replace everywhere** (UI + docs) → cleaner long-term, but a doc rewrite
> 2. **Keep "Ad-hoc" in code/DB; use "Horneado extra" only in UI** → less doc churn
>
> Which do you prefer? (My recommendation: option 1; the doc rewrite is ~1h and the result is consistent for new users.)

**Everything else in this plan is decided.** Send me a one-word answer (`replace` or `keep`) and I'll start Phase 0.
