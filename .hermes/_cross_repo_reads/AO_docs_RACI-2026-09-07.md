# RACI — AIW Approval Register, 2026-09-07

> **Purpose**: Single source of truth for every approval-list item from the 2026-09-07 Drive governance audit. Replaces the scattered tickets + Drive docs + APPROVAL-LIST markers across the repo.
> **Format**: RACI = Responsible / Accountable / Consulted / Informed. Here I use the simplified form **Owner** / **Co-owner** / **External** (Professional Reviewer) / **Reference ticket**.
> **Audit baseline**: commit `9e5a644da6ea77cdf4318cca1f76353223e7db03` (2026-09-05).
> **Status legend**: `pending` = awaiting owner action · `drafted` = Sunstein drafted · `BLOCKED` = missing preconditions · `DISPOSITION` = needs sign-off, not fresh approval · `in-progress` = owner working.
> **Last updated**: 2026-09-07 (this file).
> **Related**: `HANDOFF-FOR-IVAN-2026-09-07.md`, `HANDOFF-FOR-KIKI-2026-09-07.md`, `HANDOFF-FOR-JOHN-2026-09-07.md`, `HANDOFF-FOR-SASKIA-2026-09-07.md`, `DISPOSITION-LOG-2026-09.md`, `docs/POST-AUDIT-WORK-PLAN-2026-09-07.md`.

---

## A. Professional Reviewer (external — not founder-signable)

| ID | Item | Scope | Owner | Co-owner | Ticket | Status |
|---|---|---|---|---|---|---|
| **PR-A** | Tax structure comparison | Paraguay EAS · Dutch BV rates/VAT/payroll · Estonian e-Residency · cross-border/PE risk | **External (PY/NL/ES)** | Ivan + Sunstein | DEMIURGE-193 | drafted · awaiting referral send |
| **PR-B** | LATAM/PY regulatory claims | Maquila 7547 applicability · 1% maquila rate · SIFEN status · DPA for EU clients | **External (PY/NL/ES)** | Ivan + Sunstein | DEMIURGE-194 | drafted · BLOCKED on missing files |

> **Founder agreement is not a substitute.** These require a qualified professional to sign before the org changes structure.

---

## B. Ivan (CEO + Founder) — 11 items

| ID | Item | Co-owner | Ticket | Status | Time est. |
|---|---|---|---|---|---|
| **Ivan-A** | Domain Model gate | John | DEMIURGE-008, DEMIURGE-172 | pending · contradiction flagged | 2-3h |
| **Ivan-B** | Sprint 1 architecture gate | John | DEMIURGE-015, DEMIURGE-173 | pending · contradiction flagged | 2-3h |
| **Ivan-C** | Terminology (6 defs) | — | DEMIURGE-077 | pending · `[PENDING IVAN REVIEW]` markers | 30-45m |
| **Ivan-D** | Co-chair M4 decision | Kiki | DEMIURGE-176 | drafted (80%) · RESCOPE v2 | 1h |
| **Ivan-E** | DD-O1/O2/O3/O5/O6/O7 | Kiki | DEMIURGE-102 + family | mixed · see below | 2-3h |
| **Ivan-F** | Funding cron registration | — | **NEW DEMIURGE-222** (in PR) | pending | 1h |
| **Ivan-G** | Engineering gap audit disposition | Sunstein | DEMIURGE-205 | pending · 8 recs to disposition | 30m |
| **Ivan-H** | Tax structure | External (PR-A) | DEMIURGE-193 | see PR-A | — |
| **Ivan-I** | Kernel-vs-Project architecture | — | DEMIURGE-174 | pending · tied to Saskia | 30m |
| **Ivan-J** | LATAM/PY market gate (BLOCKED) | Kiki + John | DEMIURGE-194 | BLOCKED · 5 missing files | 2h+ |
| **Ivan-K** | UPGRADE-PROPOSAL-2026-09 disposition | — | **NEW DEMIURGE-213** (in PR) | drafted · awaiting sign | 5m |

**Ivan-E sub-items** (DD-O1..O7):
- DD-O1 (Product Owner): **RESOLVED 2026-09-04** — John van der Pol
- DD-O2 (Athena subordinate PO): pending
- DD-O3 (PRODUCT-BOUNDARY.md): blocked on DD-O1 (unblocked), needs ratification
- DD-O5 (Q1 2027 sales-funnel deferral): DEMIURGE-179
- DD-O6 (token-plan/credits): DEMIURGE-180
- DD-O7 (GitHub PAT rotation): DEMIURGE-199 — 30m confirm-only

---

## C. John (Human Product Owner) — 3 items + 1 missing-file blocker

| ID | Item | Co-owner | Ticket | Status | Time est. |
|---|---|---|---|---|---|
| **John-A** | Domain Model gate | Ivan | DEMIURGE-008, DEMIURGE-172 | pending · see Ivan-A | 1-2h |
| **John-B** | Sprint 1 architecture gate | Ivan | DEMIURGE-015, DEMIURGE-173 | pending · see Ivan-B | 1-2h |
| **John-C** | LATAM/PY market gate (BLOCKED) | Ivan + Kiki | DEMIURGE-194 | BLOCKED · nl-direct-sales-motion.md missing | 2h+ |
| **(blocker)** | NL sales-motion file | — | DEMIURGE-191 | BLOCKED · file absent | 30m (write) or 5m (withdraw) |

Plus **DEMIURGE-178a** (track John ratification of PRODUCT-BOUNDARY.md) — separate item, joint with Ivan.

---

## D. Kiki (Co-Founder + Tech Director "Kyrian") — 8 items

| ID | Item | Co-owner | Ticket | Status | Time est. |
|---|---|---|---|---|---|
| **Kiki-A** | Co-chair M4 decision | Ivan | DEMIURGE-176 | see Ivan-D | 1h |
| **Kiki-B** | DD-O1 / DD-O4 / DD-O6 | Ivan | DEMIURGE-102, DEMIURGE-198, DEMIURGE-180 | mixed | 1-2h |
| **Kiki-C** | LATAM/PY market gate | Ivan + John | DEMIURGE-194 | BLOCKED | 2h+ |
| **Kiki-D** | AI safety posture disposition | — | **NEW DEMIURGE-217** (in PR) | drafted · awaiting sign | 5m |
| **(extra)** | LAYER-1-HYGIENE disposition | — | **NEW DEMIURGE-215** (in PR) | drafted · awaiting sign | 5m |
| **(extra)** | Funnel-revival disposition | Ivan | **NEW DEMIURGE-218** (in PR) | drafted · joint sign | 5m |
| **(extra)** | Marketing dept REVIEW.md | — | **NEW DEMIURGE-219** (in PR) | pending · reconciliation work | 1-2h |
| **(extra)** | Sales dept REVIEW.md | — | **NEW DEMIURGE-220** (in PR) | pending · reconciliation work | 1-2h |
| **(extra)** | Product Discovery dept REVIEW.md | Ivan | **NEW DEMIURGE-221** (in PR) | pending · joint reconciliation | 1-2h |

---

## E. Saskia (direct input, not approval)

| ID | Item | Owner | Ticket | Status | Time est. |
|---|---|---|---|---|---|
| **Saskia** | 8 direct questions about restaurant instance | Sunstein (drafts) → Ivan (sends) → Saskia (answers) | DEMIURGE-106 (input) + DEMIURGE-192 (send) | drafted · awaiting Ivan to send channel | 15-30m for Saskia |

> **Critical**: this is **direct input**, not approval. Do not ask Saskia to sign the AIW instance design — only to answer the 8 questions.

---

## F. ADR-STD-001 — Standards Decision (Ivan + Kyrian + John)

| Item | Owner | Co-owner | Ticket | Status | Time est. |
|---|---|---|---|---|---|
| **ADR-STD-001** — Standards stack (SKOS/ORG/APQC/BPMN/PROV/DCMI/JSON Schema/DACI/RACI/COSO/NIST/OWASP/OpenAPI/AsyncAPI/RFC3339/BCP14/ArchiMate-deferred/TOGAF-rejected) | Ivan | Kiki · John (proposed) | DEMIURGE-176 + DEMIURGE-177 + DEMIURGE-181 | pending · Open Q #1 must close first | 1-2h |

---

## G. Disposition sign-offs (stale files, not fresh approvals)

Each entry exists in `DISPOSITION-LOG-2026-09.md`. Sign-off tickets are **NEW** in this PR.

| Log ID | File | Owner | Co-owner | Sign-off ticket |
|---|---|---|---|---|
| DISP-2026-001 | `analysis/UPGRADE-PROPOSAL-2026-09.md` | Ivan | — | **NEW DEMIURGE-213** |
| DISP-2026-002 | `analysis/GAP-RESEARCH-FINDINGS-2026-09.md` | Ivan | — | **NEW DEMIURGE-214** |
| DISP-2026-003 | `analysis/LAYER-1-HYGIENE-COMPLETION-REPORT.md` | Kiki | — | **NEW DEMIURGE-215** |
| DISP-2026-004 | `engineering/cron-heartbeat-strategy.md` | Ivan | — | **NEW DEMIURGE-216** |
| DISP-2026-005 | `engineering/ai-safety-posture-2026.md` | Kiki | — | **NEW DEMIURGE-217** |
| DISP-2026-006 | `sales/funnel-revival-2026.md` | Ivan | Kiki | **NEW DEMIURGE-218** |

After all 6 are signed, Sunstein will apply `disposition: SUPERSEDED` frontmatter (per DEMIURGE-165).

---

## H. Department REVIEW.md reconciliation (Kiki + Ivan)

Trackers say "approved" but REVIEW.md files don't exist. Three reconciliation tickets **NEW** in this PR:

| Department | Tracker says | Co-owner | Reconciliation ticket |
|---|---|---|---|
| Marketing | DEMIURGE-033 tracker approved | Kiki | **NEW DEMIURGE-219** |
| Sales | DEMIURGE-041 tracker approved | Kiki | **NEW DEMIURGE-220** |
| Product Discovery | DEMIURGE-047 tracker approved | Ivan + Kiki | **NEW DEMIURGE-221** |

---

## I. Broken references (missing files in public master)

| Missing file | Status | Owner | Ticket |
|---|---|---|---|
| `community/revenue-stack/language/es-py-legal.md` | absent | Sunstein | DEMIURGE-187 |
| `community/revenue-stack/language/es-py-coaching.md` | absent | Sunstein | DEMIURGE-188 |
| `community/revenue-stack/language/es-py-general-smb.md` | absent | Sunstein | DEMIURGE-189 |
| `community/cm-marketing/language/es-py-sales-motion.md` | absent | Sunstein | DEMIURGE-190 |
| `nl-direct-sales-motion.md` | absent | Sunstein + John | DEMIURGE-191 |
| `departments/marketing/REVIEW.md` | absent | Kiki | DEMIURGE-219 |
| `departments/sales/REVIEW.md` | absent | Kiki | DEMIURGE-220 |
| `departments/product-discovery/REVIEW.md` | absent | Ivan + Kiki | DEMIURGE-221 |

---

## J. Summary statistics

- **Total items**: 24 (matches Drive audit count)
- **Tickets existing**: 14
- **Tickets NEW in this PR**: 10 (DEMIURGE-213..221 + DEMIURGE-222 if added)
- **BLOCKED items**: 2 (PR-B LATAM regulatory, John-C LATAM gate) — both blocked on the same missing files
- **Disposition items awaiting sign-off**: 6 (DISP-2026-001..006)
- **Items needing Sunstein execution after owner sign**: 13
- **Items requiring external (Professional Reviewer)**: 2
- **Items requiring Saskia direct input**: 1 (8 questions, draft ready)

---

## K. Critical path (sequenced)

1. **DEMIURGE-200 + DEMIURGE-201** (Phase 8 CRITICAL fixes, Engineering) → unblock CI
2. **DEMIURGE-164** (DISPOSITION-LOG drafted, awaiting Ivan+Kiki sign) → unblock DISP-001..006
3. **DEMIURGE-183** (trademark banlist codification) → regulatory hygiene
4. **DEMIURGE-211-fix-sales-funnel-r2-worker-404** (sales funnel deploy) → revenue blocker
5. **DEMIURGE-176** (M4 decision) → unlocks every HIGH/CRITICAL item downstream
6. **DEMIURGE-187..191** (5 missing LATAM files) → unblocks PR-B + John-C
7. **DEMIURGE-008 + DEMIURGE-015** (Ivan + John gates) → unblocks all schema work
8. **DEMIURGE-193 + DEMIURGE-194** (referrals to Professional Reviewer) → regulatory hygiene
9. **DEMIURGE-192** (Saskia questions sent) → unblocks DEMIURGE-106
10. **DEMIURGE-181** (ADR-STD-001 acceptance) → governance hygiene

---

**Doc version**: 2026-09-07 v1 · **Sunstein signature** (autonomous) · **Reviewer**: all named parties · **Effective**: on next update cycle
