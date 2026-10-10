# the operator · What Next? (refresh 2026-10-10)

> **Supersedes** `docs/operations/2026-10-09-evening-WHAT_NEXT-archived.md`.
> Ground truth: `git log --oneline --since="2026-10-09"`.

## 📊 Current State (2026-10-10 ~03:30 UTC)

| Knob | Value | Source |
|------|-------|--------|
| Schema | v117 | `app/rms/config.py:92` |
| Migrations on disk | 36 | `app/rms/migrations/_*.py` |
| Tests collected | 7,997 (129 deselected) | `pytest --collect-only` |
| Open ruff findings | 0 | `ruff check` (ruff pinned 0.16.10 via `uv.lock`) |
| Open PRs | 0 (everything through #116 merged) | `gh pr list --state all` |
| PR #112 | open, CI green code-side, deploy blocked on VPS secrets | `docs/operations/2026-10-10-PR112-status.md` |
| Environments | prod + dev + test all `/healthz` 200 | saskia-vps / saskia-dev / saskia-test .paragu-ai.com |
| Branch protection | ruleset #24802688 active | 5 required checks |
| Supabase | disabled on prod (NXDOMAIN) | `a5499c51` (#98) |

## ✅ Closed since 2026-10-09 (the big rocks, cont'd)

- **Docs-quality followups (PRs #103, #107, #110, #112, #116)**:
  - **#103** pymarkdownlnt auto-fix (11,510 → 20 findings) + 3 duplicate
    pair deletions (18-suscripciones, 17-lista-compras, designer-page-report)
  - **#107** `scripts/check_active_todos.py` + 26 broken internal links
    fixed across docs/ and audits/INDEX
  - **#110** `docs-quality-baseline.json` written + docs-lint baseline
    gate wired into `ci.yml` (no-NEW-findings vs 11,327 triaged findings)
  - **#112** `scripts/check_md_links.py` (strict 0-broken-links gate) +
    `tests/test_docs_quality_gate.py` (4 pytest tests) + final dup-delete
    + baseline refresh (the 6-finding drift the gate caught) — open
  - **#116** `docs(todo): link active TODOs to SASKIA-212 and SASKIA-213 issues`
- **WHAT_NEXT #2 (safeguard activation)**: SAFEGUARD_ENABLED env-var is
  an operator-side change (deferred to VPS .env edit). The CI side
  (`make safeguard` + `SAFEGUARD_FAIL_ON_FINDING=true` semantics) is
  already wired in `.github/workflows/tooling.yml` from #96.
- **WHAT_NEXT #3 (ANN debt ticket)**: filed as **#100** —
  `type-hints: pay down ANN debt hidden by CI-recovery per-file-ignores (~311 ANN001)`.
- **WHAT_NEXT #4 (monthly SHA-pin refresh)**: shipped as
  `.github/workflows/refresh-pins.yml` — monthly cron (1st @ 09:00 UTC),
  drift detection via `scripts/refresh_action_pins.py`, auto-opens a PR
  on drift (human reviews upstream release notes before merge).

## 🎯 What's next? (ranked)

### #1 — Decide on PR #112 (merge vs extend) — 5 min

PR #112 is code-side green (lint+test ✅, ZAP ✅, zizmor ✅, browser ✅,
smoke ✅, route-smoke ✅, currency-drift ✅). Deploy-dev/test fail is
the pre-existing VPS secrets issue (BWS_ACCESS_TOKEN empty, SSH key
`error in libcrypto`) that has been blocking all 9/9 deploy runs
across the org. Two paths:

- **Merge now**: get the link-check gate, the 4 tests, and the baseline
  refresh onto main. Deploy will catch up when the VPS secrets are
  fixed. Low risk: no code paths changed; only CI/scripts.
- **Extend first**: refresh the WHAT_NEXT status (this file) and any
  other small followups into the same PR before merge.

### #2 — VPS secrets rotation — 30 min (deferred, see `deploy-dev.yml` notes)

The deploy-dev / deploy-test workflows need a working BWS_ACCESS_TOKEN
and a usable VPS SSH key. Until then, deploys land via VPS-side pulls
(Ivan has been doing this manually). Once BWS is populated, both
deploys should light up green.

### #3 — Backlog items (no rush)

- **#100** — pay down ~311 ANN001 hidden by per-file-ignores.
  Multi-hour; needs a sibling session with a fresh `dev` branch.
- **SASKIA-210** — Supabase RLS + Storage; explicitly deferred per
  the per-client-instances decision (see docs/plans/SASKIA-210-supabase-rls-multitenant-onepager.md).
- **ZAP promotion to high-only** — needs 2 consecutive clean weekly
  scans (calendar check, not work).

## ⏸️ Parked / waiting on a condition

- **`feature/station-shell` in-flight** — sibling session actively
  pushing (puesto cards UI). Carries a stale `app/CHANGELOG.md` that
  will conflict on merge — the sibling should drop it before merging.

## ❌ Explicitly deferred — do not pick up

- **Sentry→Telegram** — Iván: not until 30 customers ask.
- **Supabase RLS + Storage** — SASKIA-210 decision: per-client instances.
- **Tier 3 tools** — Semgrep CE, umbra-scan, prek (Vale was adopted
  locally as documented in PR #102).

## 🛠 Tooling & Plumbing notes

- WHAT_NEXT pattern: regenerate dated, archive previous. Don't in-place
  edit history. The 2026-10-09 evening version is at
  `docs/operations/2026-10-09-evening-WHAT_NEXT-archived.md`.
- Backup discipline (AGENTS.md rule 17) enforced at `init_db()`;
  `sazon rollback --to N` is the recovery net.
- 7 Python TODO/FIXMEs remain in `app/` (grep) — pinned in
  `docs/operations/2026-10-09-todo-triage.md`.

---

**Generated:** 2026-10-10 ~03:30 UTC after #112 push (CI green, awaiting merge decision).
