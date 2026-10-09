# `docs/operations/` — day-to-day runbooks

> Replaces the old "scattered plans + cron postmortems" model. Each file is a one-shot operational artifact: a deploy, an incident, a test-execution plan, or a rollback.

## How to read this

| File pattern | Meaning |
|---|---|
| `YYYY-MM-DD-thing.md` | The actual runbook/incident for that day |
| `thing-runbook.md` (no date) | Standing runbook (always-current) |
| `dashboard/` | The dashboard sub-folder (HTML/templates) |
| `LOYALTY_POS_CHEATSHEET.md` | One-page operator cheat sheet |

## Standing runbooks (always-current)

- `backup-cron.md` — 03:15 daily backup cadence
- `healthz-db-runbook.md` — `/healthz`, `/healthz/deps`, `/healthz/backup` checks
- `loyalty-pos-cheatsheet.md` — POS workflow for loyalty points
- `PRODUCTION_500_RUNBOOK.md` — production 500 error triage
- `worktree-policy.md` — operator-owned policy on parallel worktrees

## Recent dates

The latest operations docs sit at the top of the directory listing.

## See also

- [`docs/roadmap/EXECUTION-PLAN.md`](../roadmap/EXECUTION-PLAN.md) — what to ship next
- [`docs/roadmap/sessions/`](../roadmap/sessions/) — multi-session coordination plans
- [`docs/roadmap/decisions/`](../roadmap/decisions/) — design decisions
