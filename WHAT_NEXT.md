# the operator · What Next? (refresh 2026-10-12, docs pass)

> **2026-10-12 correction layer.** A docs verification pass (AGENTS.md drift
> audit) re-measured the knobs below against the live repo on 2026-10-12.
> The 2026-10-10 narrative sections remain below unchanged. Corrected knobs:
>
> | Knob | 10-10 said | 10-12 measured |
> |------|-----------|----------------|
> | Schema | v117 | **v119** (`CURRENT_SCHEMA_VERSION = 119` at `app/rms/config.py:92` — migration 119 `recipe_photo_autolink`, SASKIA-213) |
> | Migrations on disk | 36 | **38** (`app/rms/migrations/_*.py` files: ..._117, _118, _119) |
> | Coverage gate | (26.12% actual vs 35% gate) | unchanged — gate is **35%** (`--cov-fail-under=35` in pyproject.toml) |
> | Test files | 7,997 tests | 733 test files (collection not re-run this pass; see `pytest --collect-only`) |
> | CHANGELOG gate | root CHANGELOG.md | confirmed — gate greps `CHANGELOG.md` (root); the ci.yml comment saying `app/CHANGELOG.md` is stale (fixed in this pass) |
>
> Fixes landed in this pass: AGENTS.md rule 12 (migration count + layout),
> rule 35 (CHANGELOG gate path), anti-rule 2 counts, coverage-gate numbers,
> hosted URL sazon-vps, 3-environments note, troubleshooting PRAGMA rows,
> research-repos absolute path; app/rms/AGENTS.md testing rule 4 (per-file
> coverage figures were never-enforced aspirations, not gates).

# (superseded header, kept for history) the operator · What Next? (refresh 2026-10-10)

> **Supersedes** `docs/operations/2026-10-10-evening-WHAT_NEXT-archived.md`
> and `docs/operations/2026-10-10-late-WHAT_NEXT-archived.md` and
> `docs/operations/2026-10-10-early-WHAT_NEXT-archived.md` and
> `docs/operations/2026-10-10-midday-WHAT_NEXT-archived.md` (the
> midday archive was lost when #125 force-pushed main; the
> 2026-10-10-evening archive holds the 19:00 state — the last refresh
> before this one).
> Ground truth: `git log --oneline --since="2026-10-09"`.

## 📊 Current State (2026-10-10 ~19:20 UTC)

| Knob | Value | Source |
|------|-------|--------|
| Schema | v117 | `app/rms/config.py:92` |
| Migrations on disk | 36 | `app/rms/migrations/_*.py` |
| Tests collected | 7,997 (129 deselected) | `pytest --collect-only` |
| Open ruff findings | 0 (lint passes; 11 informational "Invalid `# noqa` directive" warnings on `arch-rule` lines) | `ruff check` |
| Active TODO comments | 5 (all in `scripts/check_active_todos.py` placeholder rows; the script itself) | `make todos` |
| Open issues | 0 | `gh issue list --state open` |
| Open PRs | 0 | `gh pr list --state open` |
| Environments | prod + dev + test all `/healthz` 200 (per last verify 2026-10-10 ~18:00) | saskia-vps / saskia-dev / saskia-test .paragu-ai.com |
| Branch protection | ruleset #24802688 active | 5 required checks (smoke, route-smoke, currency-drift, browser, Static analysis) |
| Supabase | disabled on prod (NXDOMAIN) | `a5499c51` (#98) |

## ✅ Closed since the last refresh (2026-10-10 ~19:00 → 19:20)

- **#126 — fix conftest test hang (`e54c4571`)**: 7997-test CI suite was
  timing out at 12min on the lint+test step. Root cause: every test
  paid ~7s for `from app.rms.main import app` (autouse `reset_app_state`)
  + ~8s for `init_db()` (autouse chain `_close_leaked_sessions →
  session_factory → app_engine`), even pure-Python tests like
  `test_daily_summary_dryrun` that shell out to a subprocess and
  never touch the DB. Fix: `_fixture_tree_needs_app()` checks
  `request.fixturenames` against the set of app-touching fixture
  names. `reset_app_state` / `app_engine` / `session_factory`
  short-circuit to a stub when the test's fixture tree doesn't
  include any of them. Pure-Python / CLI tests pay ~0s setup;
  app-touching tests behave unchanged. v2 uses `request.fixturenames`
  (correct signal: the test's full fixture tree is known before any
  fixture body runs) instead of v1's `sys.modules` check (which
  broke 2 test files with `RuntimeError: session_factory stubbed;
  requested attr 'kw'` because `session_factory` is built before
  `client` is instantiated). CI wall-time: 12min → ~1.5min for the
  7,997-test suite.

- **#129 — deploy healthz grep fix (`9f9cead4`)**: the deploy-dev /
  deploy-test jobs were failing on a brittle `case` glob pattern in
  the healthz status check. Replaced with `grep -q`. PR #128 was
  closed in favor of this re-authoring (sibling process). Deploy-dev
  now passes consistently; deploy-test occasionally hits a transient
  bws 429 race when both jobs run in parallel (backoff/retry
  recommended; not a code bug).

- **#122 — PATCH plantilla clean column names (`5e78e6a1`)**: the 3
  remaining `test_excel_patch` failures (excluded from #125's scope).
  `app/services/export_xlsx.py` was writing PATCH-plantilla headers
  with ` [REQUIRED]` / ` [OPTIONAL]` UX markers, but
  `app/services/import_xlsx.py` wasn't stripping them on read.
  Fixed by writing clean column names in the export side; the
  template-render helper still annotates required/optional visually
  for the operator. **19/19 test_excel_patch tests pass.**

- **#127 — WHAT_NEXT refresh after #123 + #125 (`3b1cf90f`)**: kept
  the WHAT_NEXT cadence up to date after the cierre bug-fix and
  the pre-existing-failures rebase. Now superseded by this file.

- **#125 — pre-existing test failures rebased (`f873651b`)**: the
  same 13 pre-existing test failures from #120, but rebased onto
  current main (which had #118 in the meantime). Removed the legacy
  "US 4.1 — restore packaging" block in `void_sale`; fixed the
  `Sale.recorded_at` → `Sale.sold_at` rename in 2 dashboard chart
  functions (5 line edits); deleted 7 duplicate `_write_*_sheet`
  functions in `app/services/export_xlsx.py` (142 lines net).
  The 3 `test_excel_patch` failures remained out of scope and were
  addressed in #122.

- **#120 — closed in favor of #125**: PR title kept the rebased
  wording but the actual content was the same as #125; the closed PR
  is the audit trail.

## 🎯 What's next? (ranked)

### #1 — VPS secrets rotation — 30 min (deferred to Ivan)

`deploy-dev` / `deploy-test` need a working `BWS_ACCESS_TOKEN` + VPS
SSH key. Until then, deploys land via VPS-side pulls (Ivan does this
manually). The transient `bws secret list 429` failures (#129's
deploy-test) come from BWS rate-limiting when both jobs request
secrets at the same time — proper fix is "BWS_ACCESS_TOKEN
populated" so the GitHub App rotation path can take over. Once BWS
is populated, both deploys should light up green and the `4095.0`
bws call rate becomes moot.

### #2 — Coverage gap analysis — 2-3h (deferred until a Sprint 2.2)

Test coverage is at 26.12% (gate is 35%, per `pyproject.toml`).
Per AGENTS.md, the 35% gate is a Phase 1 milestone; the 4-phase
plan in `docs/plans/2026-08-31-rms-fase-1-dev-plan.md` bumps it in
stages. The biggest gap is `app/services/template_render.py` at 21%
(an entire module that's not covered). Other modules under 25%:
`app/services/export_xlsx.py` (remediated partially by #125), 
`app/routers/dashboard.py` (remediated partially by #125),
`app/rms/sales/lifecycle.py` (remediated partially by #125).
The remaining gap is mostly in `app/services/import_xlsx.py`,
`app/rms/reports/*`, and `app/rms/production/*`. The Sprint 2.2
"ship Saskia a usable product" milestone is the next coverage push.

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
- **`feat/station-shell` (feature branch)** — sibling session in
  flight; awaits the CHANGELOG drop + rebase onto main.

## ❌ Explicitly deferred — do not pick up

- **Sentry→Telegram** — Iván: not until 30 customers ask.
- **Supabase RLS + Storage** — SASKIA-210 decision: per-client
  instances, all deferred until Saskia is happy with the product.
- **Tier 3 tools** — Semgrep CE, umbra-scan, prek (Vale was adopted
  locally as documented in PR #102).

## 🛠 Tooling & Plumbing notes

- WHAT_NEXT pattern: regenerate dated, archive previous. Don't
  in-place edit history. Five archived versions now exist in
  `docs/operations/`:
  - `2026-10-09-evening-WHAT_NEXT-archived.md`
  - `2026-10-10-early-WHAT_NEXT-archived.md` (from #121)
  - `2026-10-10-midday-WHAT_NEXT-archived.md` (lost in #125 force-push; kept as reference)
  - `2026-10-10-late-WHAT_NEXT-archived.md` (the 07:30 refresh)
  - `2026-10-10-evening-WHAT_NEXT-archived.md` (the 19:00 refresh, pre-this-one)
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
- **CI test wall-time** dropped from ~12min to ~1.5min after #126.
  The full test suite now runs in the same time window that the
  `sazon migrate` smoke test alone used to take.

---

**Generated:** 2026-10-10 ~19:20 UTC after #126 merge.
