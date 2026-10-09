# `docs/intake/` — new tickets before triage

> Append-only bucket for brand-new ticket seeds that have NOT been triaged yet. Once a ticket gets planned into a sprint, it graduates to `docs/backlog/` or `docs/roadmap/BACKLOG.md`. Once shipped, the commit hash + PR number are the source of truth (the .md here is kept for git archaeology only).

## Lifecycle

```
intake/  ──(triage at sprint boundary)──▶  backlog/  ──(PR opened)──▶  closed (commit hash)
                                                   ╰──(deferred to wishlist)──▶  wishlist/rejected/
```

## How to add a ticket

1. File: `docs/intake/SASKIA-NNN-<short-slug>.md` (use the next free `SASKIA-NNN` number).
2. Use the template at the bottom of any existing file (e.g. `SASKIA-201-visual-revolution-phase0.md`).
3. Don't agonize over estimates — that's what triage is for.

## How to triage

- **Accept into current sprint** → move file to `docs/backlog/` + add a row to `docs/roadmap/BACKLOG.md`.
- **Accept into future sprint** → keep at `docs/intake/` + add a row to `docs/roadmap/WISHLIST.md`.
- **Reject** → move to `docs/wishlist/rejected/` + add a one-line reason.

## See also

- [`docs/roadmap/BACKLOG.md`](../roadmap/BACKLOG.md) — the canonical merged backlog
- [`docs/backlog/`](../backlog/) — currently-active backlog
- [`docs/wishlist/`](../wishlist/) — long-shot ideas
