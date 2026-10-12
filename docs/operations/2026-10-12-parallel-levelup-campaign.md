# Parallel Level-Up Campaign — 2026-10-12

> **Status:** 🟡 IN-FLIGHT · **Coordinator:** S5 (s5-org) · **Lanes:** 4 + 1 coordinator

This document tracks a 5-lane parallel level-up of `/opt/data/work/sazon-app`, run on
2026-10-12. Each lane has its own worktree, branch, and scope. The coordinator arbitrates
merge order, enforces documentation/changelog discipline, and ships the final report.

## Lanes at a glance

| Lane | Branch | Scope | Hard rules touched |
|------|--------|-------|---------------------|
| **s1-tests** | `hermes/levelup-s1-tests` | `tests/**` consolidation + dedupe + coverage-timeout fix | rule 35 (CHANGELOG), rule 12 (coverage gate) |
| **s2-robustness** | `hermes/levelup-s2-robustness` | logging, errors, retries, observability (Sentry/OTel wiring) | rule 35 |
| **s3-complexity** | `hermes/levelup-s3-complexity` | `app/**` complexity refactors (orchestrator pattern), abstractions, dead-code archival, naming, enums-over-strings, ADRs | rules 38 (no legacy shims), 40 (CC ≤ 10), 39 (no router import in rms), 36 (ADRs), 37 (PR ticket), 35 |
| **s4-tooling** | `hermes/levelup-s4-tooling` | `.github/**`, `pyproject.toml [tool.ruff]`, pre-commit, lint/format/typecheck | rule 35 |
| **s5-org** | `hermes/levelup-s5-org` | README navigation, AGENTS.md drift-fix (rule 45), `docs/` taxonomy, this campaign doc, final report | coordinator/organizer (no code writes) |

## Coordination bus

Live state lives at `/opt/data/coordination/sazon-app/`:

- `PLAN.md` — coordinator's authoritative plan (per-lane status, merge queue, risks, decisions)
- `LEDGER.md` — append-only event log
- `CLAIMS.json` — file/path claims per lane
- `SESSIONS/<lane>.json` — heartbeats (each lane updates every ~10min)
- `INBOX/s5-org/from-<lane>.md` — lane → coordinator audit summaries
- `INBOX/all/from-s5.md` — coordinator → all lanes status block
- `LOCKS/merge.json` — merge token (only one lane holds the lock at a time)

## Merge protocol

1. Lane finishes audit → writes summary to `INBOX/s5-org/from-<lane>.md`
2. Lane commits + pushes PR
3. Lane writes its session name to `LOCKS/merge.json` (`{"holder": "<lane>", "ts": "<iso>"}`)
4. Coordinator reviews: CHANGELOG entry present (rule 35), scope matches lane claim, diff size sensible
5. Coordinator grants merge: sequence = (unblocks-others) > (lower-risk) > (FIFO)
6. Lane verifies CI green on `main` (`gh run list`)
7. Lane releases lock (`{"holder": null, "ts": null}`)

## Critical constraints (ALL lanes)

- **Schema v121** (`CURRENT_SCHEMA_VERSION = 121` at `app/rms/config.py:92`).
- **CHANGELOG discipline (rule 35)** — every PR touching `app/`, `scripts/`, `tests/`, or `.github/` MUST update root `CHANGELOG.md`. CI fails otherwise. `app/CHANGELOG.md` MUST NOT exist.
- **Coverage gate = 35%** (`pyproject.toml` `[tool.pytest]` `--cov-fail-under=35`).
- **Docs taxonomy (rule 42)** — `docs/roadmap/` is the canonical home for plans/audits/sessions/decisions. `docs/operations/` for runbooks/sessions/audits. `docs/architecture/decisions/` for ADRs (s3 only). Other copies are redirect stubs, not full copies.
- **AGENTS.md (rule 45)** — numeric claims in AGENTS.md (schema, test counts, coverage) must match the live repo. Drift-fix PR #155 already did one pass on 2026-10-12. Coordinator will redo after all lanes land.

## Per-lane audit results

### s1-tests (audit delivered 2026-10-12T21:00:00Z; phase 1 staged)

- **754 test files** / **97,494 LOC** / **18 duplicate patterns** / **16 conftest fixtures** / **0 naming violations**
- **Coverage analysis timed out** (60s) — needs fix
- Top-5 largest files: `test_produccion_polish.py` (723), `test_production_demand.py` (680), `test_saskia_r2_data_models.py` (589), `test_reorder_supplier_redesign.py` (530), `test_p0_audit_log_coverage.py` (515)
- Staged files (untracked when runtime restarted 21:19Z):
  - `tests/seeders.py` — new seed-helpers registry (consolidates 58 helpers, dedupes 18 patterns)
  - `tests/test_route_smoke_generated.py` — 47 generated route smoke tests covering 373 routes
  - `tests/_lib/parametrization_examples.py` — parametrize-example helpers
  - `tests/_lib/invariants_expanded.py` — additional invariant testing capabilities
- **Phase 1 plan:** consolidate 18 duplicate seed helpers → `tests/seeders.py`; promote 58 flows.py helpers to conftest fixtures; dedupe 18 patterns; parametrize repeated test bodies; split largest files; expand invariants.py coverage.
- **Wave 3 directive:** commit Phase 1 (4 files), push, then start Phase 2.

### s2-robustness (PR1 + PR2 committed 2026-10-12T21:18Z; PR3 in flight)

- Scope: logging, errors, retries, observability (Sentry/OTel wiring)
- Audit delivered 21:05Z: **137 silent broad excepts** across 36 files (top: `app/rms/db.py` 58, `app/routers/health.py` 12, `app/rms/main.py` 8, `app/services/template_render.py` 7); **55 print() in app/** (mostly legit CLI banners); **247 app/ .py files without logger**; **12 typed exception classes that raise outside AppError**; **0 retry helpers**; **1 request_id middleware**; **10 healthz endpoints**.
- **PR1 — committed `ee6e26c1`**: `refactor(errors): extend AppError taxonomy with 13 domain subclasses` (+148 lines in `app/rms/errors.py`, new `tests/test_errors_extended.py` with 36 cases, CHANGELOG entry).
- **PR2 — committed `b415592b`**: `feat(rms): retry_transient helper for HTTP/DB transient errors` (new `app/rms/retry.py` 184 lines, new `tests/test_retry.py` 21 tests, CHANGELOG entry).
- **PR3 (in flight, wave 3)**: silent-except sweep in `app/rms/db.py` — 58 sites. Will preserve WAL/pragma/feature-detection behavior.
- **PR4-PR7 queued:** silent-except sweep in `app/routers/`, `app/services/` + `app/integrations/`, print→logger in migrations, request_id route binding via contextvars.
- Arbitration ruling 21:13Z: S2 granted CLAIM on 4 new test files (additive; S1 retains veto on test-pattern conformance).

### s3-complexity (4 commits landed locally; 5th split in progress)

- Scope: `app/**` complexity refactors (orchestrator pattern), abstraction/single-path, dead-code archival, naming, enums-over-strings, ADRs in `docs/architecture/decisions/`
- Hard rules locked: 38 (no legacy shims), 40 (CC ≤ 10), 39 (no router import in rms), 36 (ADRs), 37 (PR ticket)
- Excludes: tests/** (s1), logging/error structure (s2), .github/ + [tool.ruff] (s4)
- Audit delivered 21:02Z: **179 over-CC functions in app/** (excl. archive/venv/tests); `scripts/check_complexity.py` parsing bug found (gate was silently passing).
- **Commit `c06290b4`** — `fix(tooling): SASKIA-211x complexity gate parser — make complexity now actually fires`. Critical: gate was broken since 2026-10-08; restores rule 40 enforcement.
- **Commit `b5faf129`** — `refactor(reorder): SASKIA-211x split compute_reorder_list into 5 helpers (CC 13→4)`.
- **Commit `5645d20d`** — `docs(adr): SASKIA-211x ADR-0001 orchestrator pattern (CC refactors)`.
- **Commit `3a99599f`** — `refactor(help): SASKIA-211x split _md_to_html into 11 named handlers (CC 26→20)`.
- **Uncommitted (wave 3)**: CHANGELOG.md + app/routers/help.py — in-progress 5th split.
- Plan: 7 grade-F + 7 grade-E + 19 grade-D + 146 grade-C functions queued.

### s4-tooling (audit delivered 2026-10-12T21:12Z; executing 8-item plan)

- Scope: `.github/**`, `pyproject.toml [tool.ruff]`, pre-commit, lint/format/typecheck
- 8-item plan: (a) fast PR gate workflow (<5min), (b) full gate stays, (c) pre-commit security hooks (vulture/bandit/complexity), (d) ruff tightening, (e) pip-audit + cyclonedx SBOM on release, (f) dependabot.yml, (g) PR template with gap-tracking, (h) Makefile audit/test-fast targets.
- Risk: tooling PRs land isolated but touch pyproject — may need sequencing with s1 (pyproject [tool.pytest]).
- Wave 3 directive: execute plan; push.

## Risks (live — see PLAN.md § Risks for full list)

1. **Main NOT ahead** (correction 21:08:30Z) — `origin/main` = `d4fa75dc` = all 4 lane worktrees. The shim-removal commit `e9c9fac6` lives on `origin/feat/saskia-211a-shim-removal` (unmerged PR), not on main. Watch that PR; if it lands mid-campaign, lanes need rebase or `-X ours`.
2. **CHANGELOG gate** (rule 35) — every PR touching `app/`, `scripts/`, `tests/`, or `.github/` MUST update root `CHANGELOG.md`. CI fails otherwise. Coordinator verifies on each merge.
3. **Coverage timeout** — S1 audit caught this; needs fix.
4. **Rule 45 drift** — AGENTS.md numeric claims need re-verification after campaign lands. Drift-fix PR #155 already did one pass on 2026-10-12. Coordinator will redo after all lanes ship.
5. **Hermes runtime restart (NEW)** — runtime killed wave 2 at 21:19Z. All 5 lanes respawned as wave 3. Work preserved in worktrees. S2 had 2 commits; S3 had 4 commits + in-progress 5th; S1 had 4 untracked files; S4 had plan. No work lost.

## Timeline (rolling)

| Time (UTC) | Event |
|------------|-------|
| 20:53:05 | Campaign initialized. 5 sessions registered. |
| 21:00:00 | s1 audit delivered. |
| 21:02:00 | s3 respawned. |
| 21:03:40 | s2 heartbeat registered. |
| 21:05:00 | s5 coordinator online (respawn). PLAN.md initialized. |
| 21:08:00 | PLAN.md updated with full lane scopes + risks. |
| 21:08:30 | Correction: main NOT ahead of lanes (earlier risk was wrong). |
| 21:09:00 | s2 audit delivered (137 silent excepts / 55 prints / 0 retry helpers). |
| 21:10:00 | s3 audit delivered (179 over-CC; gate-parser bug). |
| 21:11:00 | s3 first commit `c06290b4` lands (gate-parser fix). |
| 21:12:00 | s4 audit delivered (8-item plan). |
| 21:13:00 | s3 commits `b5faf129` + `5645d20d` (reorder + ADR-0001). |
| 21:15:00 | s2 PR1 `ee6e26c1` committed (errors taxonomy +13 subclasses). |
| 21:18:00 | s2 PR2 `b415592b` committed (retry_transient helper). |
| 21:18:51 | **ORCH: Hermes runtime restarted 21:19Z — all 5 lanes killed mid-flight.** Wave 2 work preserved in worktrees. |
| 21:25:00 | **s5-org respawned (wave 3)** with resume pointers. Plan/LEDGER/Sessions re-synced. Doc state preserved. |
| _(TBD)_ | Wave-3 lanes heartbeat + resume work; first push to origin. |
| _(TBD)_ | Merge sequence (best guess: s3 → s2 → s4 → s1). |
| _(TBD)_ | All 4 lanes deliver final reports. |
| _(final)_ | Coordinator writes final report; drift-fix pass; push s5-org branch. |

## Final report

`docs/operations/2026-10-12-parallel-levelup-report.md` — written by coordinator after all 4 lanes deliver final reports. Per-lane measured outcomes + retro.

---

*This is a live doc — updated as the campaign lands.*
