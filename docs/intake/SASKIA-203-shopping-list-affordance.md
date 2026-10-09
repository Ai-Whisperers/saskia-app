# SASKIA-203: Shopping-list affordance + test paths + doc sync

**Date:** 2026-10-07
**Epic / Story:** (operational polish, no epic)
**Owner:** Iván
**Estimate:** 30 min
**Status:** shipped

## What

Three small, related fixes that close the shopping-list feature's
last loose ends after the underlying endpoints shipped 2026-09-30
(`eaaf6a12` + `bc9a76ff` + `8edaefd6` + `ff0ed55e`):

1. **`/produccion` "Enviar faltantes a lista de compras" button** —
   operator one-click from the production plan view to
   `POST /shopping-list/from-production-plan`. Previously the
   endpoint worked but the UI affordance to trigger it from
   `/produccion` was missing.
2. **`test_shopping_benchmarks.py` stale paths** — 4 `Path(...)` calls
   referenced the old `/opt/data/sazon-app/` location from before
   the repo rename to `/opt/data/work/saskia-app/`. Always-RED tests
   in CI.
3. **`WHAT_NEXT.md` shopping-list item archived** — the file's #2
   item described `POST /plan/shopping-list` as TODO. Real endpoint
   shipped 2026-09-30; file was misleading future sessions.

## Why

- **Operator impact**: the production card now ships the shopping
  list in 1 click instead of 4 clicks + a page jump. Daily flow for
  every operator every morning.
- **CI hygiene**: 2 always-RED tests were masking real regressions in
  the benchmarks file.
- **Agent-onboarding hygiene**: future sessions (or Iván) re-auditing
  WHAT_NEXT.md would have wasted 20 min confirming the shopping-list
  feature already shipped, then either re-implementing it (bad) or
  proposing to move the URL to `/plan/shopping-list` (breaks
  templates + tests).

## Tasks

- [x] Add `<form method="post" action="/shopping-list/from-production-plan">`
      with hidden `for_date={{ plan.for_date.isoformat() }}` to
      `app/templates/produccion.html:1672-1695`
- [x] Fix 4 stale `Path("/opt/data/sazon-app/...")` calls in
      `tests/test_shopping_benchmarks.py` (lines 84, 96, 125, 178)
- [x] Archive current `WHAT_NEXT.md` to `WHAT_NEXT_2026-10-07-archived.md`
- [x] Rewrite `WHAT_NEXT.md`: move Production Planner → Shopping List
      to "Closed", promote C.1 Telegram env wiring to #2, keep sale
      channel mismatch at #3
- [x] Update `app/CHANGELOG.md` per AGENTS.md rule 35

## Acceptance

- [x] `tests/test_shopping_from_plan.py::test_produccion_page_has_send_to_list_button`
      passes
- [x] `tests/test_shopping_benchmarks.py::test_shopping_list_template_no_native_select`
      passes
- [x] `tests/test_shopping_benchmarks.py::test_recipe_photos_template_exists`
      passes
- [x] 14/14 shopping tests pass (was 11/14)
- [x] `ruff check` clean
- [x] `ruff format --check` clean
- [x] CHANGELOG.md updated per AGENTS.md rule 35

## Out of scope (deferred)

- **5 shopping-list enhancements** (print view, recurring auto-resync,
  supplier cost split, snapshotted price on ShoppingListItem, dismiss
  action). Each has its own ticket value. Full analysis in
  `scratch/shopping-list-audit-2026-10-07.md`.
- **~25 stale "sazon-app" mentions inside test docstrings** — not
  load-bearing, leave for a dedicated docstring sweep.
- **Migration 111 to ALTER sale.channel CHECK** — needed for #3
  "Sale channel mismatch". Separate ticket.

## Audit reference

Deep-dive analysis saved to
`/opt/data/profiles/ivan/cache/scratch/shopping-list-audit-2026-10-07.md`
(9.9 KB). Read before picking up any of the deferred enhancements.