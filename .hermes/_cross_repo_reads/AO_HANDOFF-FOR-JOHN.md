# HANDOFF-FOR-JOHN — 2026-09-07

> **Who**: John van der Pol (Human Product Owner)
> **From**: Sunstein (autonomous ops agent on the AIW stack)
> **Why**: The 2026-09-07 Drive governance audit identified 3 items assigned to you, all joint with Ivan. Plus 1 NL-file blocker on the LATAM gate. This is your single reading list.
> **Action required from you**: read + sign / decide each item. Most items require a 1-2 hour sync with Ivan.
> **Source of truth**: `docs/RACI-2026-09-07.md` (master table)

---

## TL;DR (60 seconds)

You have **3 active items** and **1 missing-file blocker**:

| Bucket | Count | Tickets | What you need to do |
|---|---|---|---|
| **Joint with Ivan** (gates) | 2 | DEMIURGE-008 (Domain Model), DEMIURGE-015 (Sprint 1) | Pick disposition per gate |
| **Joint with Ivan** (PRD ratification) | 1 | DEMIURGE-178a (PRODUCT-BOUNDARY.md) | Ratify the one-page product boundary |
| **Missing file** (LATAM/NL) | 1 | DEMIURGE-191 (nl-direct-sales-motion.md) | Write or withdraw |

Your role as named human Product Owner means every domain-model decision is yours to ratify or reject.

---

## Your items in detail

### 1. Domain Model Gate (joint with Ivan) — **CRITICAL PATH**

**Ticket**: DEMIURGE-008, DEMIURGE-172 (contradiction fix)
**Source files**: `docs/demiurge/REVIEW-domain-model.md` + 8 underlying docs (15 minutes to read)
**Time estimate**: 1-2 hours (joint with Ivan)

**The key question for you** (per the audit):
> Does this domain model give AIW a stable, comparable business structure, or is it too agent-centric and missing Product, Service, Customer, Capability, Process, DataAsset, System, Policy, Risk, and Control?

**What to do**:
1. Read the 8 files (15 minutes)
2. Decide for each: **approve** / **revise** / **reject**
3. Co-sign with Ivan
4. Resolve the "Locked vs PENDING" contradiction

**What "done" looks like**: every row in the gate has Ivan + John signature OR a revision note.

### 2. Sprint 1 Architecture Gate (joint with Ivan) — **CRITICAL PATH**

**Ticket**: DEMIURGE-015, DEMIURGE-173 (disposition fix)
**Source files**: `docs/demiurge/REVIEW-sprint-1.md` + 5 underlying docs (20 minutes to read)
**Time estimate**: 1-2 hours (joint with Ivan)

**The key question for you**:
> Approve the architecture as the intended direction, revise it to incorporate the enterprise-structure work, or label it historical. Do not let PENDING APPROVAL coexist indefinitely with later "complete" claims.

**What to do**: pick one of **(a)** retroactively approve, **(b)** revise and reapprove, or **(c)** declare bypassed/superseded. Resolve the v1/v2 naming contradiction in `department-taxonomy-v1.md`.

### 3. PRODUCT-BOUNDARY.md Ratification

**Ticket**: DEMIURGE-178a (this is the tracker ticket)
**Source file**: `analysis/PRODUCT-BOUNDARY.md` (or wherever Ivan placed it)
**Time estimate**: 30-45 minutes
**Context**: DD-O1, DD-O2, DD-O3 are RESOLVED (you're the human PO). The last remaining step is ratifying the one-page PRODUCT-BOUNDARY document.

**What to do**:
1. Read the PRODUCT-BOUNDARY.md file (10 minutes)
2. Decide: **ratify as-is** / **request revisions** / **reject with reason**
3. Co-sign with Ivan
4. Update DEMIURGE-178a tracker.md

**What "done" looks like**: DEMIURGE-178a status = done, PRODUCT-BOUNDARY.md has your signature line.

### 4. NL Sales Motion File (LATAM/PY gate dependency)

**Ticket**: DEMIURGE-191
**Status**: ⚠️ BLOCKED — file does not exist in public master
**Expected path**: `nl-direct-sales-motion.md` (referenced by `research/latam-py-market-REVIEW-GATE.md`)

**What to do**:
1. Either **write** the NL sales-motion file (using your existing NL contacts + ICP knowledge), OR
2. **Withdraw** the reference from the LATAM gate (state that NL is not in current market scope)
3. Reply to Sunstein with the file content or the withdrawal notice

**What "done" looks like**: file exists at the expected path, OR the LATAM gate no longer references it.

---

## Recommended sync pattern

Items 1, 2, 3 are all joint with Ivan. Recommend one 2-3 hour session:

1. Read the 13 files together (45 min)
2. Walk through each gate (60 min)
3. Resolve the "Locked vs PENDING" and v1/v2 contradictions (30 min)
4. Sign the dispositions (15 min)

Sunstein will be on standby to commit any cross-doc updates you decide.

---

## Items NOT on your list

- LATAM/PY regulatory claims — Professional Reviewer (external)
- Tax structure — Professional Reviewer (external)
- Saskia direct input — she answers directly
- DD-O4..O7 governance — Ivan + Kiki, you can observe but not sign
- ADR-STD-001 — Ivan + Kyrian, you are listed as "Proposed / pending confirmation" only

---

## Escalation

If you're unavailable for >7 days, send a one-line note ("deferred — return after YYYY-MM-DD") and I'll move items to "John bandwidth" status under DEMIURGE-212 (parallel to Ivan's bandwidth audit).

---

**Doc version**: 2026-09-07 v1 · **Sunstein signature** (autonomous) · **Reviewer**: John (human) · **Effective**: on operator sign-off
