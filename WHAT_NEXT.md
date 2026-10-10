# the operator · What Next? (refresh 2026-10-10)

> **Supersedes** `docs/operations/2026-10-10-late-WHAT_NEXT-archived.md` and
> `docs/operations/2026-10-10-early-WHAT_NEXT-archived.md` and
> `docs/operations/2026-10-10-midday-WHAT_NEXT-archived.md` (the
> midday archive was lost when #125 force-pushed main; the previous
> early version is the one from #121).
> Ground truth: `git log --oneline --since="2026-10-09"`.

## 📊 Current State (2026-10-10 ~19:00 UTC)

| Knob | Value | Source |
|------|-------|--------|
| Schema | v117 | `app/rms/config.py:92` |
| Migrations on disk | 36 | `app/rms/migrations/_*.py` |
| Tests collected | 7,997 (129 deselected) | `pytest --collect-only` |
| Open ruff findings | 0 (lint passes; 11 informational "Invalid `# noqa` directive" warnings on `arch-rule` lines) | `ruff check` |
| Active TODO comments | 5 (all in `scripts/check_active_todos.py` placeholder rows; the script itself) | `make todos` |
| Open issues | 0 | `gh issue list --state open` |
| Open PRs | 2 (Ivan's: #122, #124) | `gh pr list --state open` |
| Environments | prod + dev + test all `/healthz` 200 | saskia-vps / saskia-dev / saskia-test .paragu-ai.com |
| Branch protection | ruleset #24802688 active | 5 required checks |
| Supabase | disabled on prod (NXDOMAIN) | `a5499c51` (#98) |

## ✅ Closed since the last refresh (2026-10-10 ~07:30 → 19:00)

- **#123 — restore cierre monthly-close aggregates (`1adca996`)**:
  the 2026-10-09 complexity refactor (commit `eb1c28c9`) extracted
  helpers from `compute_monthly_close` but left the final
  `_build_monthly_close_result` returning
  `MonthlyClose(year=year, month=month, ...)` — a call signature the
  `MonthlyClose` dataclass does not accept. Result: 11 of 15 tests in
  `tests/test_cierre.py` failed, plus collateral failures in
  `tests/test_date_boundary.py` (60) and `tests/test_reports.py` +
  `tests/test_analytics_properties_phase14_tier4.py` (43). Same
  `test_total_ventas` failure Ivan flagged as out-of-scope in PR #120.

  Fix: rewrote `_build_monthly_close_result` to compute the full set
  of aggregate fields. Caller now passes `start`/`end`/`sales`. All
  15 + 60 + 43 = 118 tests now pass.

- **#125 — Ivan's pre-existing-failures rebased (`f873651b`)**: the
  same 13 pre-existing test failures from #120, but rebased onto
  current main (which had #118 in the meantime). Removed legacy
  "US 4.1 — restore packaging" block in `void_sale`, fixed
  `Sale.recorded_at` → `Sale.sold_at` rename in 2 dashboard chart
  functions, deleted 7 duplicate `_write_*_sheet` functions in
  `app/services/export_xlsx.py`. (The 3 `test_excel_patch` failures
  remain — addressed in #122.)

## 🎯 What's next? (ranked)

### #1 — PATCH-plantilla header parsing — 2-4h (Ivan's PR #122 in flight)

3 pre-existing test failures in `tests/test_excel_patch.py`:

- **Root cause**: `app/services/export_xlsx.py` writes the
  PATCH-plantilla headers with ` [REQUIRED]` / ` [OPTIONAL]` UX
  markers (e.g. `"name [REQUIRED]"`). The import side
  (`app/services/import_xlsx.py`) does not strip these markers when
  reading back, so `row.get("name")` raises `KeyError: 'name'` for
  every row.
- **Affected sheets**: Productos, Clientes, Ingredientes, Recetas.
- **Likely production impact**: PATCH-mode imports silently fail
  with "fila sin nombre" warnings.
- **Ivan's PR #122** is on it: 2 files, +103/-5. Branch
  `fix/excel-patch-template-columns-2026-10-10`. No need for
  duplicate work.

### #2 — VPS secrets rotation — 30 min (deferred to Ivan)

`deploy-dev` / `deploy-test` need a working BWS_ACCESS_TOKEN + VPS
SSH key. Until then, deploys land via VPS-side pulls (Ivan does
this manually). When BWS is populated, both deploys should light
up green.

### #3 — Backlog items (no rush)

- **SASKIA-210** — Supabase RLS + Storage; explicitly deferred per
  the per-client-instances decision
  (`docs/plans/SASKIA-210-supabase-rls-multitenant-onepager.md`).
- **ZAP promotion to high-only** — needs 2 consecutive clean weekly
  scans (calendar check, not work).
- **feature/station-shell** — sibling session (puesto cards UI) in
  flight; carries a stale `app/CHANGELOG.md` that will conflict on
  merge — sibling should drop it before merging.
- **Ruff noqa warnings on `arch-rule` lines (noise)** — 11
  informational warnings ("expected a comma-separated list of
  codes") on `# noqa: arch-rule — <reason>` lines. The lint check
  itself passes; the warnings are stderr noise. Two ways to silence
  would both break the test contract in
  `tests/test_check_imports_rules.py` (which parses the string
  literally). **Left as-is.**

## ⏸️ Parked / waiting on a condition

- **PR #101 refactor** (closed) — the 48-file complexity refactor
  is still valuable but needs re-authoring on the post-#117 base
  with annotations from the start. If anyone wants to do this,
  file a new SASKIA ticket.
- **PRs #122, #124** — all Ivan's, in flight.

## ❌ Explicitly deferred — do not pick up

- **Sentry→Telegram** — Iván: not until 30 customers ask.
- **Supabase RLS + Storage** — SASKIA-210 decision: per-client
  instances, all deferred until Saskia is happy with the product.
- **Tier 3 tools** — Semgrep CE, umbra-scan, prek (Vale was adopted
  locally as documented in PR #102).

## 🛠 Tooling & Plumbing notes

- WHAT_NEXT pattern: regenerate dated, archive previous. Don't
  in-place edit history. Four archived versions now exist in
  `docs/operations/`:
  - `2026-10-09-evening-WHAT_NEXT-archived.md`
  - `2026-10-10-early-WHAT_NEXT-archived.md` (from #121)
  - `2026-10-10-midday-WHAT_NEXT-archived.md` (lost in #125 force-push; kept as reference)
  - `2026-10-10-late-WHAT_NEXT-archived.md` (from this refresh)
- Backup discipline (AGENTS.md rule 17) enforced at `init_db()`;
  `sazon rollback --to N` is the recovery net (shipped in #209).
- `app/CHANGELOG.md` was removed in the docs reorg (commit
  `e9b80533`); CI gates now on root `CHANGELOG.md` (commit
  `f7ab4b24`).
- The 11 informational "Invalid `# noqa` directive" warnings from
  ruff are the cost of using `arch-rule` as a project-internal
  code; `tests/test_check_imports_rules.py` parses the string
  literally so we can't rename it without also updating the test.
  Left as-is (warnings don't fail checks).

---

**Generated:** 2026-10-10 ~19:00 UTC after #125 merge.
