# Round 2 Triage Process

> **For**: Ivan (operator), Kiki (any future build agent).
> **Purpose**: keep Round 2 feedback cheap. Single source of truth for the triage workflow that decides whether a Saskia-reported item gets a hot-patch PR or moves to the gem-project backlog.

**Doc version:** 2026-09-16 v1 (initial — closes Phase 0 epic E4.S1)
**Refers to:** `installer/ROUND-2-NOTES.md`, `docs/plans/2026-09-07-saskia-complete-epic-plan-v3.md`

---

## TL;DR

Round 2 = hot-patch only. Items that meet **all 5 ship-it criteria** get a direct-to-main PR. Everything else gets a `SASKIA-NNN` ticket linked from `installer/ROUND-2-NOTES.md`.

| Step | Time | Owner | Output |
|---|---|---|---|
| 1. Capture | 1 min | operator / Kiki | row in `installer/ROUND-2-NOTES.md` with `Status: OPEN` |
| 2. Triage | 5 min | operator | ship-it checklist → `ACCEPTED` or `OUT-OF-SCOPE` |
| 3. Ship (if ACCEPTED) | ≤2h | Kiki | PR to `main` with regression test |
| 4. Route (if OUT-OF-SCOPE) | 10 min | operator | `SASKIA-NNN` ticket OR `WONT-FIX` |
| 5. Close | 30 days | operator | file moved to `installer/ROUND-2-NOTES-CLOSED.md` |

---

## Step 1: Capture

When Saskia reports something via WhatsApp (or anyone files a bug on GH), append a row to `installer/ROUND-2-NOTES.md` using the inline template. **No triage yet** — that's step 2.

Rules:
- Don't write a row without a clear repro. If Saskia says "está raro", ask once for specifics. If she doesn't reply in 48h, mark `WONT-FIX` with reason "no repro".
- Don't skip the row "to save time" — operator reviews the file weekly.
- Don't double-capture: if the same issue was filed via GH issue, link the issue number, don't paste the body twice.

## Step 2: Triage (5 minutes, no more)

Open the row. Run through the 5-point ship-it checklist:

```
[ ] ≤2h fix?
[ ] Clear repro?
[ ] One acceptance test planned?
[ ] No new dep?
[ ] No schema migration?
```

Mark each checkbox. If any are unchecked → `OUT-OF-SCOPE`. If all checked → `ACCEPTED` and proceed to step 3.

**Time-box at 5 minutes.** Anything you can't decide in 5 min goes to `OUT-OF-SCOPE` with rationale "needs deeper review → SASKIA-NNN ticket".

## Step 3: Ship (≤2h, direct to main)

ACCEPTED items become direct commits on `main` (Round 2 doesn't use branches — see [Why no branches](#why-no-branches) below).

PR template:

```
<one-line summary>

What:
- <bullet 1>
- <bullet 2>

Why:
<business outcome>

Test:
<regression test name> in tests/<file>.py
Refs: installer/ROUND-2-NOTES.md #NNN
```

After merge, update the row:
- `Status: FIXED`
- `PR: <commit SHA>`
- Link to the commit in the row.

## Step 4: Route (10 min for OUT-OF-SCOPE)

Four destinations:

| Destination | When | Action |
|---|---|---|
| **Gem-project backlog** | Real feature work | Create `SASKIA-NNN-<slug>.md` under `docs/tickets/`. Reference Epic+Story from `docs/plans/2026-09-07-saskia-complete-epic-plan-v3.md`. |
| **Rejected (WONT-FIX)** | Operator decision: cost > value | Document reason in the row. Examples: "out-of-scope of quote", "low value", "duplicate of #NNN". |
| **Deferred to Fase 2+** | Future feature | Same as backlog but tag with the Fase. |
| **NEEDS-INFO** | Unclear | Ask Saskia once. 48h timeout → WONT-FIX. |

## Step 5: Close (30 days)

When Round 2 closes (operator-decided date, target = 30 days post Round-1 close), the file moves to `installer/ROUND-2-NOTES-CLOSED.md` with:

1. **Header summary**: total items, ACCEPTED count, OUT-OF-SCOPE count, FIXED count, WONT-FIX count, total time spent.
2. **Buffer consumption**: how much of the 8h buffer was used.
3. **Top 3 lessons**: what surprised us, what should change for Round 3 (if any).

The closed file stays in the repo as the diff between Round-1-close and Round-2-close.

---

## Why no branches

Round 1 worked via branches + PRs. Round 2 doesn't, **deliberately**:

- Hot-patch territory. The bug is real, the fix is small, the test is the gate.
- Branches add PR-review overhead that costs more than the fix.
- `app/AGENTS.md` already mandates CI gates (ruff + pytest + coverage) that catch regressions.
- The 5-item ship-it checklist is the human gate.

If a Round 2 fix needs > 1 commit, that's a signal it was a bad Round 2 fit — revert and route to gem-project backlog.

---

## Edge cases

### "Saskia reports the same thing twice"

Link the rows. Mark the duplicate `WONT-FIX` with reason "duplicate of #NNN". Saskia shouldn't have to track this; the operator does.

### "Item is in Round 2 scope but requires touching the schema"

Stop. Re-read [ship-it criterion #5](#step-2-triage-5-minutes-no-more). Schema migrations go through normal epic review, not Round 2. Route to `SASKIA-NNN`.

### "Operator can't reproduce locally"

`NEEDS-INFO`. Ask Saskia for browser version + screenshot. If 48h passes with no answer, `WONT-FIX` with "no repro" reason.

### "Item is critical and ships the same day"

Mark `blocker` severity. Operator does the triage + ship in one sitting. Buffer accounting still applies — fast fixes still cost from the 8h budget.

---

## What this process does NOT cover

- **Gem-project work** (epics E1–E25) → see `docs/plans/2026-09-07-saskia-complete-epic-plan-v3.md`.
- **Architecture changes** (kernel, instance design) → see AIW org docs.
- **Saskia's first-time onboarding** → see `installer/ROUND-1-NOTES.md` + `docs/operations/herbus-discovery-prompt.md`.

---

**Owner:** Ivan (operator), Kiki (build agent for any PRs)