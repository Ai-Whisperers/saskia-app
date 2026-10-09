# Sazón — documentation map

> Every operator-facing or contributor-facing document lives below.
> **For "what to ship next", see [`docs/roadmap/EXECUTION-PLAN.md`](roadmap/EXECUTION-PLAN.md).**

| You want to… | Look here |
|---|---|
| Use the app as an operator | [`docs/user-guide/`](user-guide/) |
| Pick the next thing to build | [`docs/roadmap/BACKLOG.md`](roadmap/BACKLOG.md) and [`docs/roadmap/EXECUTION-PLAN.md`](roadmap/EXECUTION-PLAN.md) |
| Read the deep plan(s) | [`docs/plans/`](plans/) (SASKIA one-pagers) + [`docs/roadmap/epics/`](roadmap/epics/) |
| Drop a new ticket-seed idea | [`docs/intake/`](intake/) |
| Look up "what was that thing from Oct 8?" | [`docs/analysis/`](analysis/) |
| Drop a long-shot idea | [`docs/wishlist/`](wishlist/) |
| Operate the running system today | [`docs/operations/`](operations/) |
| Read a past design decision | [`docs/decisions/`](decisions/) and [`docs/adr/`](adr/) |
| Look up something historical | [`docs/archive/`](archive/) and [`docs/roadmap/historical-plans/`](roadmap/historical-plans/) |
| Understand a past week of changes | [`docs/roadmap/sessions/`](roadmap/sessions/) and [`docs/roadmap/audits/`](roadmap/audits/) |

## Folders that were collapsed in the 2026-10-09 reorg

- ❌ `docs/decisions/v1/` was a mirror of `docs/roadmap/decisions/` (kept the canonical copy in `roadmap/`).
- ❌ `docs/roadmap/audits/2026-09-22/`, `...2026-09-29/` were mirror-of-mirror subdirs (kept the canonical copies at `docs/roadmap/audits/<file>.md`).
- ❌ `docs/roadmap/historical-plans/intake/` was a 1-file mirror of `docs/intake/` (kept all 14 in `docs/intake/`).
- ❌ `docs/sessions/round-2-feedback.md` and `docs/operations/round-2-triage-process.md` were mirrors of `docs/roadmap/sessions/` (kept the canonical).
- ❌ `app/CHANGELOG.md` was a stale mirror of root `CHANGELOG.md` (dropped; root is canonical).

## See also

- [`AGENTS.md`](../AGENTS.md) — contributor rules (canonical)
- [`CHANGELOG.md`](../CHANGELOG.md) — release history
- [`.hermes/plans/`](../.hermes/plans/) — ephemeral session-internal plans
