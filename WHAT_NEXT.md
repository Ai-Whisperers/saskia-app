# the operator · What Next? (refresh 2026-10-10)

> **Supersedes** `docs/operations/2026-10-10-early-WHAT_NEXT-archived.md`.
> Ground truth: `git log --oneline --since="2026-10-09"`.

## 📊 Current State (2026-10-10 ~07:30 UTC)

| Knob | Value | Source |
|------|-------|--------|
| Schema | v117 | `app/rms/config.py:92` |
| Migrations on disk | 36 | `app/rms/migrations/_*.py` |
| Tests collected | 7,997 (129 deselected) | `pytest --collect-only` |
| Open ruff findings | 0 | `ruff check` (ruff pinned 0.16.10 via `uv.lock`) |
| Active TODO comments | 5 (all in `scripts/check_active_todos.py` placeholder rows) | `make todos` |
| Open issues | 0 | `gh issue list --state open` |
| Open PRs | 2 (Ivan's: #118, #120) | `gh pr list --state open` |
| Environments | prod + dev + test all `/healthz` 200 | saskia-vps / saskia-dev / saskia-test .paragu-ai.com |
| Branch protection | ruleset #24802688 active | 5 required checks |
| Supabase | disabled on prod (NXDOMAIN) | `a5499c51` (#98) |

## ✅ Closed since the last refresh (the big rocks)

### Tier 3 — backlog paid off

- **SASKIA-100 (ANN debt) — #117 merged `a1db5495`**: removed
  per-file-ignore `"ANN"` from `app/routers/**` and `app/rms/**`;
  added `"ANN401"` (so `Any` annotations on dynamic args are allowed).
  22 files annotated, 339 type hints applied. The helper
  `scripts/add_type_hints.py` (260 lines, idempotent) is committed so
  the next ANN sweep is mechanical. Issue #100 closed.
- **SASKIA-212 — #119 merged `9a469af2`**: deleted the 3 legacy
  channel constants (`ALLOWED_CHANNELS`, `CHANNELS_DISPLAY`,
  `CHANNEL_DEFAULT`) from `app/rms/models/channels.py`. Only one
  importer remained (`tests/test_P42_channel_enum_integration.py`),
  migrated to call `Channel.default()` directly. Issue #114 closed.
- **SASKIA-213 — same PR #119**: the `# TODO: Fix _period_window`
  in `tests/test_dashboard_kpis_end_to_end.py` was already fixed in
  code (via `_resolve_period_window` → `_period_window("custom")`
  fallback). Test was tightened to assert exactly 200 (was
  `in (200, 303, 422, 500)`) and renamed
  `test_dashboard_filter_custom_no_dates_falls_back_to_today`.
  Issue #115 closed.
- **PR #101 (refactor restoration) — closed-not-merged**: the
  48-file complexity refactor was working at cross purposes with #117
  (would re-add the per-file-ignore that #117 removed). Closed with
  explanation; the refactor is still valuable but needs to be
  re-authored on the post-#117 base with annotations from the start.
- **`make todos` now reports 0 actionable code TODOs** (the 2
  SASKIA-21X tickets were the entire active set; 5 noise
  "TODO/FIXME/XXX" strings remain in `scripts/check_active_todos.py`
  itself, which is the script that finds them).

### Ivan's parallel work in flight (do not touch)

- **PR #118 — `fix/void-sale-and-xlsx-duplicates`** (Ivan):
  `void_sale` was leaving orphan `SalePayment` rows + xlsx had
  duplicate sheet-writer functions. 3 files, +60/-4, all required
  checks pass; deploy blocked on VPS secrets as usual.
- **PR #120 — `fix/pre-existing-test-failures-2026-10-10`** (Ivan):
  fixes 13 of 16 pre-existing test failures on main (4 void +
  9 export). The 3 remaining `test_excel_patch` failures are
  explicitly out of scope; see "Backlog" below.

## 🎯 What's next? (ranked)

### #1 — PATCH-plantilla header parsing — 2-4h (BLOCKING production)

3 pre-existing test failures in `tests/test_excel_patch.py` (out of
scope of PR #120) expose a real production bug:

- **Root cause**: `app/services/export_xlsx.py` writes the
  PATCH-plantilla headers with ` [REQUIRED]` / ` [OPTIONAL]`
  UX markers (e.g. `"name [REQUIRED]"`). The import side
  (`app/services/import_xlsx.py`) does not strip these markers when
  reading back, so `row.get("name")` raises `KeyError: 'name'` for
  every row.
- **Affected sheets**: Productos, Clientes, Ingredientes, Recetas
  (every sheet using `*_COLS` with markers).
- **Likely production impact**: PATCH-mode imports silently fail
  with "fila sin nombre" warnings. Operator would only notice if
  they looked at the warnings list.
- **Branch already started**: `fix/excel-patch-template-columns-2026-10-10`
  (no PR yet — sibling session draft).
- **Suggested fix**:
  1. In `app/services/import_xlsx.py:_rows()`, strip the
     ` [REQUIRED]` / ` [OPTIONAL]` suffix from header cells before
     using them as dict keys.
  2. Add a regression test in `tests/test_excel_patch.py` that
     round-trips a PATCH plantilla (download → re-upload → all
     rows processed with no `KeyError` / "fila sin nombre"
     warnings).
  3. Also fix the data-row alignment in
     `_build_patch_plantilla_wb` Productos sheet (5 values
     written, 7 columns in header — `id` and `recipe_name` columns
     end up blank but `name [REQUIRED]` lands in column B
     correctly only because the data array starts with `prod.name`).
- **Recommend filing an issue** to track this; whoever picks it up
  has a clear scope and a starting branch.

### #2 — VPS secrets rotation — 30 min (deferred, see `deploy-dev.yml` notes)

The deploy-dev / deploy-test workflows need a working BWS_ACCESS_TOKEN
and a usable VPS SSH key. Until then, deploys land via VPS-side pulls
(Ivan has been doing this manually). Once BWS is populated, both
deploys should light up green. Ivan is the one to do this.

### #3 — Backlog items (no rush)

- **SASKIA-210** — Supabase RLS + Storage; explicitly deferred per
  the per-client-instances decision (see
  `docs/plans/SASKIA-210-supabase-rls-multitenant-onepager.md`).
- **ZAP promotion to high-only** — needs 2 consecutive clean weekly
  scans (calendar check, not work).
- **`feature/station-shell`** — sibling session (puesto cards UI) is
  in flight; carries a stale `app/CHANGELOG.md` that will conflict on
  merge — the sibling should drop it before merging.
- **Ruff noqa warnings (noise)** — 11 "Invalid `# noqa` directive"
  warnings on lines like `# noqa: arch-rule — <reason>`. The
  `arch-rule` string isn't a real ruff code, so ruff warns. Two
  options: (a) add `ARCH-RULE` to `[tool.ruff.lint] external = []`,
  or (b) update the comments to `# noqa: ARCH, arch-rule — <reason>`
  so ruff sees a real code. Low priority — warnings only, lint
  passes. Tracked here, not filed.

## ⏸️ Parked / waiting on a condition

- **PR #101 refactor** — branch was
  `fix/refactor-restoration-2026-10-09` (now closed). If anyone
  wants the refactor, re-author on the post-#117 base with
  annotations from the start.

## ❌ Explicitly deferred — do not pick up

- **Sentry→Telegram** — Iván: not until 30 customers ask.
- **Supabase RLS + Storage** — SASKIA-210 decision: per-client
  instances, all deferred until Saskia is happy with the product.
- **Tier 3 tools** — Semgrep CE, umbra-scan, prek (Vale was adopted
  locally as documented in PR #102).

## 🛠 Tooling & Plumbing notes

- WHAT_NEXT pattern: regenerate dated, archive previous. Don't
  in-place edit history. Previous versions at
  `docs/operations/2026-10-09-evening-WHAT_NEXT-archived.md` and
  `docs/operations/2026-10-10-early-WHAT_NEXT-archived.md`.
- Backup discipline (AGENTS.md rule 17) enforced at `init_db()`;
  `sazon rollback --to N` is the recovery net (shipped in #209).
- `app/CHANGELOG.md` was removed in the docs reorg (commit
  `e9b80533`); CI gates now on root `CHANGELOG.md` (commit `f7ab4b24`).
- The "11 invalid noqa warnings" ruff emits are the cost of using
  `arch-rule` as a project-internal code; `tests/test_check_imports_rules.py`
  parses the string literally so we can't rename it without also
  updating the test. Left as-is (warnings don't fail checks).

---

**Generated:** 2026-10-10 ~07:30 UTC after #119 merge + tier-3 close.
