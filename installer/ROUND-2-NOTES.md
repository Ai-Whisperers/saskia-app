# Round 2 Review — the operator RMS

> **For the operator and Kiki.** Working agreement for the **second review round** of Fase 1.5, building on `installer/ROUND-1-NOTES.md`.
>
> **Period:** 30 days of daily use after Round 1 close.
> **Focus:** Round 2 accepts **only Round-1-style "ship-it" items** (≤2h fix). Anything else moves to Fase 2 (gem-project backlog, `docs/plans/2026-09-07-sazon-complete-epic-plan-v3.md`) or is rejected with rationale.
>
> **Generated:** 2026-09-16 by AIW operator. Closes Phase 0 epic E4.S1.

---

## Why Round 2 is different from Round 1

Round 1 accepted anything in-scope — blockers, majors, minors, cosmetics. That round is closed.

Round 2's posture is **conservative**:

- The gem-project plan (`docs/plans/2026-09-07-sazon-complete-epic-plan-v3.md`) already covers ~390h of scoped work. Don't sneak Round 2 items into the bug-fix pipeline.
- the operator's daily use surfaces real bugs (cold-start races, mobile quirks, browser-specific layout breaks). Round 2 catches those cheaply.
- Anything bigger than 2h is a **new ticket** linked from here, not a row in this file.

## Ship-it criteria (the only items that get fixed in Round 2)

An item is "ship-it" only if **all** of these hold:

1. **≤2h fix** — operator-estimated, including test + commit. Bigger goes to gem-project backlog.
2. **Clear repro** — exact steps, expected vs actual, browser + version, screenshot if visual.
3. **One acceptance test** — fails on `main` today, passes after the fix. The test is the merge gate.
4. **No new dependency** — per `app/AGENTS.md` rule #1. If a fix requires a new dep, it stops being Round 2.
5. **No schema migration** — Round 2 is hot-patch territory. Schema changes go through the normal epic-review flow.

If any criterion fails, the item is **out** of Round 2 — see [Routing out-of-scope items](#routing-out-of-scope-items).

---

## How Round 2 works

1. **the operator** sends feedback via WhatsApp. Operator (or Kiki) captures each item as a row in [Round 2 items](#round-2-items) below.
2. Operator does a **5-minute triage** on the item:
   - Meets all 5 ship-it criteria → mark `ACCEPTED`, create PR with `Refs #NNN`.
   - Fails any → mark `OUT-OF-SCOPE` with rationale, link to gem-project epic or reject.
3. PRs land on `main` directly (Round 2 is hot-patch territory; no separate branches).
4. When Round 2 closes (30 days OR buffer exhausted — whichever first), this file becomes the diff against the Round-1-close deploy.

## Status legend

| Status | Meaning |
|---|---|
| `OPEN` | Not yet triaged |
| `ACCEPTED` | Meets ship-it criteria; PR in progress |
| `OUT-OF-SCOPE` | Fails ship-it; routed to gem-project backlog or rejected |
| `FIXED` | Implemented; commit SHA noted |
| `WONT-FIX` | Explicitly rejected with reason |
| `NEEDS-INFO` | Can't reproduce or unclear; asked the operator for more |

## Severity ladder (same as Round 1)

| Severity | Meaning | Example |
|---|---|---|
| `blocker` | Cannot use the app | "Sale entry crashes when qty is 0" |
| `major` | Significant friction | "Cost column always shows '—' even when prices are set" |
| `minor` | Polish / UX | "Tab order in sale entry skips qty field" |
| `cosmetic` | Spanish copy / wording | "'Guardá' should be 'Guardar' in this context" |
| `data` | Real bug, not UX | "Stock went negative after a void" |
| `perf` | Slow / freezes | "Excel import takes 30s for 100 rows" |

---

## Routing out-of-scope items

When an item fails the ship-it criteria, link it from this file and route it:

| Destination | When |
|---|---|
| **Gem-project backlog** | Real feature work. Add a `SASKIA-NNN` ticket under `docs/tickets/`. Reference the Epic+Story code from `2026-09-07-sazon-complete-epic-plan-v3.md`. |
| **Rejected (WONT-FIX)** | Operator decision: cost > value. Document the reason in the row. |
| **Deferred to Fase 2+** | Same as gem-project but explicitly out-of-Fase-1.5. |
| **NEEDS-INFO** | the operator didn't give enough detail. Ask once; if no answer in 48h, mark `WONT-FIX` with reason "no repro". |

## Buffer

Phase 0 epic E4.S1 budgets **4h setup + 8h buffer** for Round 2. Track consumption:

```
Setup:        2h used (this doc + GH labels + template + process doc)
Buffer used:  0h / 8h (updated as items ship)
```

When buffer hits 6h, operator pauses Round 2 PRs and reassesses: bigger items move to Fase 2 + new quote; Round 2 stays hot-patch only.

---

## Round 2 items

<!--
Copy this template for each new item:

### #NNN — <short title>

**Severity:** blocker | major | minor | cosmetic | data | perf
**Reported:** YYYY-MM-DD via <WhatsApp | in-person | email>
**Reported by:** the operator | operator | Kiki
**Status:** OPEN

**Repro:**
1.
2.
3.

**Expected:**
**Actual:**
**Environment:** Chrome 142 / Firefox 124 / Safari 17 / Edge; hosted / local; date observed.

**Triage (operator, 5min):**
- [ ] ≤2h fix?
- [ ] Clear repro?
- [ ] One acceptance test planned?
- [ ] No new dep?
- [ ] No schema migration?

**Result:** ACCEPTED → PR #NNN | OUT-OF-SCOPE → ticket SASKIA-NNN / WONT-FIX / DEFERRED
-->

*No items yet. Round 2 opens the day after Round 1 closes (operator decision).*

---

## Acceptance for Round 2 close

- All `ACCEPTED` rows are `FIXED` or rolled into gem-project backlog with `SASKIA-NNN` tickets.
- All `NEEDS-INFO` rows past 48h are `WONT-FIX` with reason.
- This file is moved to `installer/ROUND-2-NOTES-CLOSED.md` with a one-paragraph summary at the top.

---

**Doc version:** 2026-09-16 v1 (initial — closes Phase 0 epic E4.S1)
**Owner:** Ivan (operator), Kiki (build agent for any PRs)
**Refers to:** `installer/ROUND-1-NOTES.md`, `docs/operations/round-2-triage-process.md`, `docs/plans/2026-09-07-sazon-complete-epic-plan-v3.md`