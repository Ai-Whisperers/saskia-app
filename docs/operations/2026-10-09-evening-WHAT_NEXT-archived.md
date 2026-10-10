# the operator · What Next? (refresh 2026-10-09 evening)

> **Supersedes** `WHAT_NEXT_2026-10-08-archived.md`. Ground truth:
> `git log --oneline --since="2026-10-08"`.

## 📊 Current State (2026-10-09 ~18:45 UTC)

| Knob | Value | Source |
|------|-------|--------|
| Schema | v117 | `app/rms/config.py:92` |
| Migrations on disk | 36 | `app/rms/migrations/_*.py` |
| Tests collected | 7,991 (129 deselected) | `pytest --collect-only` |
| Open ruff findings | 0 | `ruff check` (ruff pinned 0.16.10 via `uv.lock`) |
| Open PRs | 0 | all of #91–#99 merged |
| Environments | prod + dev + test all `/healthz` 200 | saskia-vps / saskia-dev / saskia-test .paragu-ai.com |
| Branch protection | ruleset #24802688 active | 5 required checks |
| Supabase | disabled on prod (NXDOMAIN) | `a5499c51` (#98) |

## ✅ Closed since 2026-10-08 (the big rocks)

- **Three-environment deployment** — `saskia-vps` (prod), `saskia-dev`,
  `saskia-test` all live and seeded with La Vaquita Holandesa pack data.
  BWS secret management, per-env image tags, dev auto-deploy on push.
- **CI recovery** — the sibling complexity-refactor wave left 594 ruff
  errors blocking every PR. Fixed 4 real F821 bugs (forecast.py undefined
  `ing`, dashboard.py lost chart helpers, reorder.py missing `import csv`,
  export_xlsx.py phantom `PLANTILLA_*_COLS`), 3 B904s, ANN per-file-ignores
  for the unannotated-helper wave, 22 reviewed noqas (#97).
- **CHANGELOG-path + shallow-clone gate bugs** — the discipline gate
  checked `app/CHANGELOG.md` (deleted in e9b80533) and diffed `HEAD~1`
  on fetch-depth-1 checkouts (exit 128). Could never pass. Fixed in
  dev-ci/ci/release.sh/check_currency_drift.sh (#99).
- **zizmor + SHA-pinning** — 37 actions SHA-pinned, template-injection /
  cache-poisoning / artipacked auto-fixed, excessive-permissions fixed,
  dead qa-gates.yml deleted, `pin_workflow_actions.py` +
  `add_workflow_permissions.py` idempotent scripts (#96, #95).
- **fastapi-safeguard wired** — baseline-triaged, opt-in via
  `SAFEGUARD_ENABLED` (#96).
- **OTel + Prometheus** — opt-in (`OTEL_ENABLED`, `PROMETHEUS_ENABLED`),
  `/metrics` bound 127.0.0.1 behind nginx (#95).
- **Docs-quality tooling** — pymarkdownlnt + audit (11,510 findings,
  9 duplicate pairs, 57 broken links, 235 TODOs) + `make docs-lint`,
  `jscpd`, `deadcode`, `tool-matrix` (#93, #94).
- **DORA measurement** — weekly `dora-snapshot.yml` cron + first
  snapshot W41 (#92).
- **Complexity refactor wave** — ~20 functions reduced from 25–29 to
  0–7 (sibling sessions; critical functions restored in `feaa2e68`).
- **uv.lock tracked** — CI toolchain pinned; ruff drift between local
  and CI eliminated; uv cache invalidation works (`eceeb1cd`).

## 🎯 What's next? (ranked)

### #1 — Docs-quality PR 2–3 (mechanical, big debt reduction) — 1–2 h

From the audit's 6-PR followup (`docs/operations/2026-10-09-docs-quality-audit.md`):
- **PR 2**: `pymarkdownlnt fix` repo-wide → resolves ~8,100 of 11,510 findings
- **PR 3**: delete the 3 real duplicate pairs (18-suscripciones, 17-lista-compras, designer-page-report)
- PR 4 (57 broken links) and PR 5 (CI gate) follow naturally after.

### #2 — Activate safeguard in dev + wire FAIL_ON_FINDING in CI — 30 min

`app/rms/safeguard.py` is wired and baseline-triaged but dormant
everywhere. Enable `SAFEGUARD_ENABLED=true` on dev env; add a CI step
with `SAFEGUARD_FAIL_ON_FINDING=true` so new findings block. Rationale:
63 routes audited in 50 ms — nearly free.

### #3 — Type-hint debt ticket — 15 min (then a later wave)

The ruff recovery hid ~311 ANN001 behind per-file-ignores
(`app/routers/**`, `app/rms/**`) with a "BACKLOG Tier 9" comment but no
ticket exists. File a GitHub issue so it's tracked; the actual hints
wave is a separate multi-hour effort.

### #4 — Monthly SHA-pin refresh automation — 30 min

`scripts/pin_workflow_actions.py` exists but nothing re-runs it. Add a
`schedule:` (monthly) workflow that runs it and opens a PR when pins
are stale. Alternative: Dependabot for actions.

## ⏸️ Parked / waiting on a condition

- **ZAP promotion to high-only** — needs 2 consecutive clean weekly
  scans (calendar check, not work).
- **OTel collector** — code ships opt-in; no collector configured.
  Point dev at one when observability is actually needed.
- **deploy-dev/test SSH exit 255** — explicitly deferred by Iván
  (2026-10-09). Not a required check; deploys still land via VPS-side
  pulls.
- **`feature/station-shell` in-flight** — sibling session actively
  pushing (puesto cards UI). Carries a stale `app/CHANGELOG.md` that
  will conflict on merge — the sibling should drop it before merging.

## ❌ Explicitly deferred — do not pick up

- **Sentry→Telegram** — Iván: not until 30 customers ask.
- **Supabase RLS + Storage (#37/#38)** — SASKIA-210 decision: per-client
  instances, wait until Saskia is happy.
- **Tier 3 tools** — Vale (network-blocked), Semgrep CE, umbra-scan,
  factory_boy audit, prek.

## 🛠 Tooling & Plumbing notes

- WHAT_NEXT pattern: regenerate dated, archive previous. Don't in-place
  edit history.
- Backup discipline (AGENTS.md rule 17) enforced at `init_db()`;
  `sazon rollback --to N` is the recovery net.
- 7 Python TODO/FIXMEs remain in `app/` (grep) — triage alongside
  docs-PR-6 (235 doc TODOs).

---

**Generated:** 2026-10-09 ~18:45 UTC after #91–#99 + uv.lock all merged.
