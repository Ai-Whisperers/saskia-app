# Round 2 Triage Process

> **For Iván, Kiki, and any future agent.** Working agreement for triaging
> items that arrive during the Round 2 review window
> (see [`installer/ROUND-2-NOTES.md`](../../installer/ROUND-2-NOTES.md) for the
> scope and the ≤2h cap).
>
> **Generated:** 2026-10-11 by the Round 2 contract test. Companion to
> `installer/ROUND-2-NOTES.md`.

---

## Why this doc exists

The Round 2 ship-it cap (≤2h, see `installer/ROUND-2-NOTES.md`) only holds
if every incoming item goes through a triage step. Without an explicit
process, a "2-minute fix" silently becomes a 4-hour refactor and Round 2
becomes Round 3.

This doc fixes the workflow. The state machine below is the contract.

---

## Triage workflow (state machine)

Every item starts in **open**, moves to **triaged** once classified, and
ends in one of three terminal states.

```text
   open
     │
     │  capture from WhatsApp / Drive / daily-use note
     ▼
   triaged
     │
     ├──→ ship-it        (≤2h, in-scope, see installer/ROUND-2-NOTES.md)
     │       │
     │       └──→ shipped (PR merged + acceptance test green)
     │
     ├──→ epic (out-of-scope, link to gem-project backlog ticket)
     │       │
     │       └──→ rejected (won't fix this round; rationale documented)
     │
     └──→ wont-fix (rejected outright; rationale documented)
```

### State definitions

- **open** — captured but not yet classified. Default source: WhatsApp
  message, Drive comment, daily-use note, or a one-line GitHub issue with
  the `round-2` label.

- **triaged** — classified into one of `ship-it`, `epic`, or `wont-fix`,
  with rationale written into the row.

- **ship-it** — meets all 5 ship-it criteria from `installer/ROUND-2-NOTES.md`.
  Wait in the queue.

- **shipped** — PR merged to `main`, acceptance test green on the daily
  CI run, deployment shipped to VPS. Row archived.

- **epic** — out of scope for Round 2 (>2h, new dep, or migration). A
  ticket is created in the gem-project backlog
  (`docs/plans/2026-09-07-sazon-complete-epic-plan-v3.md`) and linked from
  the row. The row stays in the Round 2 log for traceability.

- **wont-fix** — explicitly out of scope or invalid. Rationale documented
  on the row so the operator can see why.

- **rejected** — terminal state for `epic` and `wont-fix` items after
  the rationale is written. Synonym: `closed`.

---

## Routing decision tree

For every new item, walk this in order. The first match wins.

1. **>2h estimate?** → `epic`. Open a ticket in the gem-project backlog
   and link it. Item is out of Round 2.

2. **Requires a new dep?** → `epic`. Per `app/AGENTS.md` rule #1, new deps
   are not ship-it. Open an ADR + ticket.

3. **Requires a schema migration?** → `epic`. Round 2 is hot-patch only.
   Follow the normal epic-review flow
   (`docs/operations/2026-10-04-test-execution-plan.md`).

4. **No clear repro?** → `wont-fix`. The operator must provide repro steps
   before re-queueing.

5. **Cosmetic / no acceptance test possible?** → `wont-fix`. Round 2 ships
   fixes that have a regression test. Visuals go to the wishlist.

6. **All 5 ship-it criteria hold?** → `ship-it`. Queue for the next
   Round 2 batch.

---

## Where the rows live

- The captured list lives in `installer/ROUND-2-NOTES.md` under
  **Captured items** (Kiki maintains it; the operator reviews on Monday).

- The shipped list lives in `installer/ROUND-2-NOTES.md` under
  **Shipped this round** (Kiki appends after each merge).

- Epic-routed items are linked, not duplicated. The link is the source of
  truth.

## Round 2 cap (the 2h rule)

The cap is **≤2h** per ship-it item, measured by the operator estimate
**including test + commit**. The cap cannot drift. If a fix balloons past
2h, the item is reclassified as `epic` mid-flight and the next batch
picks it up. See `installer/ROUND-2-NOTES.md` for the full cap and
exceptions.

## Triage cadence

- **Daily:** Kiki triages any open rows from the previous 24h. Ship-it
  items go in the next batch; out-of-scope rows get epic links or
  wont-fix rationale.

- **Weekly:** operator reviews the triage log on Mondays (post-deploy) to
  catch drift.

- **Per-ship:** any item that took >2h without reclassification triggers
  a process review.

## Cross-references

- `installer/ROUND-2-NOTES.md` — the actual items, the ship-it criteria,
  and the 2h cap. **Read this first.**

- `installer/ROUND-1-NOTES.md` — Round 1 close-out (historical).

- `docs/plans/2026-09-07-sazon-complete-epic-plan-v3.md` — gem-project
  backlog, where epic-routed items go.

- `app/AGENTS.md` — hard rules, especially rule #1 (no new deps without
  Iván OK) and the migration rules.

- `.github/ISSUE_TEMPLATE/bug.md` — bug template references this doc.
