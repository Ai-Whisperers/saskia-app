# HANDOFF-FOR-IVAN — 2026-09-07

> **Who**: Ivan (CEO + Founder)
> **From**: Sunstein (autonomous ops agent on the AIW stack)
> **Why**: The 2026-09-07 Drive governance audit identified 11 items assigned to you across 5 reviewers (Professional Reviewer, yourself, joint with John, joint with Kiki, ADR-STD-001). This doc is your single reading list — every item has a ticket, ticket has acceptance criteria, ticket has a "done" definition.
> **Action required from you**: read + sign / decide / defer each item. None of this is autonomous — every item needs a human verdict.
> **Source of truth**: `docs/RACI-2026-09-07.md` (master table) · `docs/POST-AUDIT-WORK-PLAN-2026-09-07.md` (16-epic plan) · `docs/SYNTHESIS-2026-09-07-DRIVE-AUDIT.md` (audit detail)

---

## TL;DR (read this first, 60 seconds)

You have **11 outstanding approval items** that I cannot sign, draft-as-signed, or auto-resolve on your behalf. They fall into 4 buckets:

| Bucket | Count | Tickets | What you need to do |
|---|---|---|---|
| **Joint with John** (domain model + Sprint 1 gates) | 3 | DEMIURGE-008, -015, -172, -173 | Pick a disposition: approve, revise, or declare superseded (per drive audit) |
| **Joint with Kiki** (governance decisions) | 3 | DEMIURGE-102, -176, -179, -181 | Make the decision (M4, DD-O*, ADR sign-off) |
| **Disposition sign-off** (6 stale files) | 4 | DEMIURGE-213, -214, -216, -218 | Sign the SUPERSEDED verdict (DISPOSITION-LOG already drafted by Sunstein) |
| **Single-decision items** | 1 | DEMIURGE-174 | Confirm/reject "kernel is the abstraction" (linked to Saskia design) |

Plus one **out-of-cycle deferral**: the 2026-09-07 PR for new tickets DEMIURGE-213..221 + handoff packs will land on master soon — review the 9 new tickets if you want, but they're scaffolding only, no decisions needed yet.

---

## Your items in detail

### 1. Domain Model Gate (joint with John) — **CRITICAL PATH**

**Ticket**: DEMIURGE-008, DEMIURGE-172 (contradiction fix)
**Source files**: `docs/demiurge/REVIEW-domain-model.md`, `docs/demiurge/domain-model.md`, 7 schemas under `docs/demiurge/schemas/`
**Time estimate**: 2-3 hours (including John sync)
**The trap**: `domain-model.md` says **"Locked Sprint 0"** but the gate says **PENDING APPROVAL**. Both can't be true. You must pick one.

**What to do**:
1. Read the 8 files in the gate (15 minutes)
2. Decide for each: **approve** / **revise** / **reject** — do NOT sign the wrapper only
3. Resolve the "Locked vs PENDING" contradiction explicitly (e.g., rewrite `domain-model.md` to say "PENDING APPROVAL — see REVIEW-domain-model.md" OR rewrite the gate to say "retroactively approved 2026-09-XX")
4. Co-sign with John
5. Update `docs/demiurge/REVIEW-domain-model.md` rows; mark DEMIURGE-008 + -172 done

**What "done" looks like**: every row in the gate has Ivan + John signature OR a revision note. The contradiction is gone.

### 2. Sprint 1 Architecture Gate (joint with John) — **CRITICAL PATH**

**Ticket**: DEMIURGE-015, DEMIURGE-173 (disposition fix)
**Source files**: `docs/demiurge/REVIEW-sprint-1.md`, 5 files (architecture.md, department-taxonomy-v1.md, naming-conventions.md, router-design.md, feature-list.md)
**Time estimate**: 2-3 hours (including John sync)
**The trap**: later sprint documents (Sprint 2-5) claim progress that assumes this gate was approved. The gate is still PENDING. Plus `department-taxonomy-v1.md` is named v1 but calls itself v2 internally.

**What to do**:
1. Read the 5 files (20 minutes)
2. Pick one explicit disposition: **(a)** retroactively approve, **(b)** revise and reapprove, or **(c)** declare bypassed/superseded
3. Resolve the v1/v2 naming contradiction
4. Co-sign with John
5. Update the gate file

**What "done" looks like**: one of the three dispositions is recorded explicitly. No "PENDING" + "complete" coexistence.

### 3. Terminology (6 definitions)

**Ticket**: DEMIURGE-077-terminology-lib
**Source files**: `docs/terminology/TERMS.md`, `tickets/DEMIURGE-077-terminology-lib/progress.md`
**Time estimate**: 30-45 minutes
**What's pending**: 6 definitions are explicitly marked `[PENDING IVAN REVIEW]`:
- urgency tier
- formality level
- tone
- directionality
- notification
- alert

**What to do**:
1. Open TERMS.md, search for `[PENDING IVAN REVIEW]`
2. For each definition: confirm or return a precise revision
3. Update TERMS.md directly, or reply with a revised draft for me to commit

**What "done" looks like**: zero `[PENDING IVAN REVIEW]` markers in TERMS.md.

### 4. Co-Chair M4 Decision Rights (joint with Kiki)

**Ticket**: DEMIURGE-176 (v2 RESCOPE)
**Source file**: `board/co-chair-decision-rights.md` (93 lines, 80% of M4 already drafted)
**Time estimate**: 1 hour (including Kiki sync)
**What to do**:
1. Read the M4 draft (15 minutes)
2. Decide: **adopt M4** (time-bounded consensus) or **reject** and pick a different mechanism
3. Name the first rotating tiebreaker (e.g., "Sept-Oct: Ivan; Nov-Dec: Kyrian; rotates quarterly")
4. Define HIGH/CRITICAL thresholds explicitly
5. Co-sign with Kiki
6. Extract into `board/M4-DECISION-RECORD-2026-09-07.md` decision-record format

**What "done" looks like**: a signed decision-record file at `board/M4-DECISION-RECORD-2026-09-07.md`.

### 5. DD-O1 / DD-O2 / DD-O3 / DD-O5 / DD-O6 / DD-O7 (joint with Kiki)

**Ticket**: DEMIURGE-102 (parent) + DEMIURGE-178a (John-PRODUCT-BOUNDARY tracker) + DEMIURGE-179 (DD-O5) + DEMIURGE-180 (DD-O6) + DEMIURGE-198 (DD-O4 Kiki-only) + DEMIURGE-199 (DD-O7)
**Source file**: `meetings/department-design/DECISIONS.md`
**Time estimate**: 2-3 hours total
**Items**:
- **DD-O1**: name the human Product Owner with Kiki → **already named**: John van der Pol, see DECISIONS.md
- **DD-O2**: expand Athena or create subordinate PO agent → decision needed
- **DD-O3**: blocked on DD-O1 (already unblocked)
- **DD-O5**: retain or reopen the Q1 2027 sales-funnel deferral → decision needed
- **DD-O6**: decide token-plan/credits response with Kiki → decision needed
- **DD-O7**: confirm GitHub PAT rotation (post-195e055) → CONFIRM needed (30m)

**What to do**:
1. Open DECISIONS.md, read all DD-O* items
2. For each: confirm the locked decision, OR return a precise revision
3. For DD-O5 specifically: evidence-based reassessment is DEMIURGE-158 (separate ticket)

**What "done" looks like**: every DD-O* has either LOCKED + signature OR CANCELLED + reason.

### 6. Funding Cron Registration (Ivan-F)

**Ticket**: **NEW DEMIURGE-213-funding-cron-registration** (will exist in PR for this work)
**Source file**: `02-finance-legal/funding-coordinator/cron-jobs.md`
**Time estimate**: 1 hour
**What's pending**: two jobs are documented but explicitly not registered until you confirm.

**What to do**:
1. Verify current provider, paths, cost, delivery, and duplication (the file predates later cron repairs)
2. Decide: **register both**, **register weekly sweep only**, **register daily check only**, or **revise + register**
3. Update cron-jobs.md with your decision
4. If approved, I will register them as actual Hermes cron jobs (no human-in-the-loop deploy needed)

**What "done" looks like**: cron-jobs.md has either a registration command in it OR a "rejected with reason" line.

### 7. Engineering Gap Recommendations (Ivan-G)

**Ticket**: DEMIURGE-205 (Sunstein-executes, you sign)
**Source file**: `research/dept-research/04-engineering-gap-audit.md`
**Time estimate**: 30 minutes (sign-only)
**What's pending**: 8 deferred recommendations listed in the file's footer.

**What to do**:
1. Read the 8 recommendations (15 minutes)
2. For each: mark **implemented** / **rejected** / **still valid** / **superseded**
3. Sunstein will execute the implementation per your direction

**What "done" looks like**: every recommendation has a disposition marker.

### 8. Project Architecture (kernel vs Project)

**Ticket**: DEMIURGE-174 (already exists)
**Source file**: `tickets/DEMIURGE-118-decide-project-architecture/plan.md`
**Time estimate**: 30 minutes
**What to do**:
1. Confirm or reject "**kernel is the abstraction; Project is not first-class**"
2. If rejected: define the alternative
3. Update DEMIURGE-118 plan.md status

**What "done" looks like**: DECISIONS-2026-Q3.md has a "kernel-vs-project" entry with your verdict.

### 9. LATAM/PY Market Gate (BLOCKED)

**Ticket**: DEMIURGE-194
**Status**: ⚠️ **BLOCKED** until 5 missing files are restored. See item 12 below.
**Time estimate**: 2 hours + missing-file work

### 10. UPGRADE-PROPOSAL-2026-09 Disposition

**Ticket**: **NEW DEMIURGE-213-disposition-upgrade-proposal-2026-09** (in same PR)
**Source file**: `analysis/UPGRADE-PROPOSAL-2026-09.md`
**Time estimate**: 30 minutes
**What to do**: sign the DISP-2026-001 entry as SUPERSEDED (Sunstein already drafted it)

### 11. ADR-STD-001 Acceptance

**Ticket**: DEMIURGE-181
**Source file**: `docs/ADR-STD-001-standards-decision.md` (the ADR text the approval list references)
**Time estimate**: 1 hour (with Kiki)
**What to do**: review + sign as ACCEPTED (was PROPOSED). Open Question #1 (is Kyrian a required approver?) must be closed first — see DEMIURGE-177.

---

## Items NOT on your list (don't action)

- **PR-A (tax structure), PR-B (LATAM regulatory)** — Professional Reviewer (external), you can monitor but not sign
- **John's items** (John-A/B/C) — John's, not yours
- **Kiki-only items** — see HANDOFF-FOR-KIKI
- **Saskia direct input** — Ivan + Sunstein send; Saskia answers, you don't

---

## Disposition sign-off (4 of the 6 stale files assigned to you)

**Tickets**: DEMIURGE-213 (UPGRADE-PROPOSAL), DEMIURGE-214 (GAP-RESEARCH-FINDINGS), DEMIURGE-216 (cron-heartbeat-strategy), DEMIURGE-218 (funnel-revival)
**Source**: `DISPOSITION-LOG-2026-09.md` entries DISP-2026-001/002/004/006
**Time estimate**: 4 × 5 minutes = 20 minutes total

Each entry is already fully populated with the superseding artifact. You only need to **sign** the verdict (Sunstein will apply the DEMIURGE-165 frontmatter after).

---

## What I (Sunstein) will do once you sign

- Apply `disposition: SUPERSEDED` frontmatter to each signed file
- Update cross-references (your PR-31 work plan, INDEX.md, etc.)
- Notify Kiki of joint dispositions (218)
- Register any approved funding crons via Hermes (autonomous, no human-in-loop)
- Generate a "close-out" report for the 2026-09-07 audit

---

## Escalation

If you're blocked on any item, send me a one-line note ("blocked on X because Y") and I'll either:
- Re-scope the ticket
- Find an alternative path
- Mark it as deferred with reason

I won't re-ask you for the same item twice. After 2 attempts, I move it to "deferred — needs Ivan bandwidth" and ticketize under DEMIURGE-212 (Ivan bandwidth audit).

---

**Doc version**: 2026-09-07 v1 · **Sunstein signature** (autonomous) · **Reviewer**: Ivan (human) · **Effective**: on operator sign-off
