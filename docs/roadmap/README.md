# Saskia RMS — Roadmap (Single Source of Truth)

> **Status as of:** 2026-10-05
> **Replaces:** the parallel `IMPROVEMENT_BACKLOG.md` (kept for git history) and
> the P0/P1/P2/P3 lists in `docs/decisions/2026-09-29-canonical-roadmap-alignment.md`
> (also kept for git history).

This folder is the **canonical place to look for what to do next** on the
Saskia RMS app. Everything else (top-level `*.md`, scattered `docs/plans/`,
old audit reports) is a **source** for this folder, or an **archive** of
material that already informed a decision.

## How to read this

| You want to know… | Read |
|---|---|
| What is the current state? | [`STATUS.md`](STATUS.md) |
| What should we ship next? | [`BACKLOG.md`](BACKLOG.md) |
| What are the long-term epics & stories? | [`epics/00-EPIC-PLAN-EXTRACT.md`](epics/00-EPIC-PLAN-EXTRACT.md) |
| What raw ideas are pending? | [`WISHLIST.md`](WISHLIST.md) (or `docs/wishlist/`) |
| What decisions have been made? | [`decisions/`](decisions/) (ADRs) |
| Where did this come from? | [`historical-plans/INDEX.md`](historical-plans/INDEX.md) |
| What audits/tests have we done? | [`audits/`](audits/) |
| What sessions have we run? | [`sessions/INDEX.md`](sessions/INDEX.md) |

## Folder layout

```
docs/roadmap/
├── README.md                              ← you are here
├── STATUS.md                              ← current state (live URL, schema, tests, deploy)
├── BACKLOG.md                             ← merged P0/P1/P2/P3 forward-looking work
├── WISHLIST.md                            ← index of docs/wishlist/
├── epics/
│   └── 00-EPIC-PLAN-EXTRACT.md            ← 25 epics E1-E25 across 6 phases
├── decisions/                             ← ADRs + canonical roadmap alignment
│   ├── ADR-001-test-architecture.md       (moved from docs/adr/)
│   └── 2026-09-29-canonical-roadmap-alignment.md
├── historical-plans/                      ← original plan docs, kept for reference
│   ├── INDEX.md
│   ├── 2026-08-31-rms-fase-1-dev-plan.md
│   ├── 2026-09-rms-fase-1-dev-plan-v2.md
│   ├── 2026-09-07-saskia-complete-epic-plan-v3.md
│   └── … (see INDEX.md for the full list)
├── audits/                                ← one-shot audit reports (post-fix summary)
│   ├── INDEX.md
│   ├── SASKIA_BACKEND_AUDIT_2026-09-22.md
│   ├── FRONTEND_AUDIT_2026-09-22.md
│   ├── LOGGING_ERRORS_AUDIT_2026-09-29.md
│   └── …
└── sessions/                              ← multi-session recovery & execution plans
    ├── INDEX.md
    ├── 2026-09-29-saskia-rms-multi-session-recovery-plan.md
    ├── 2026-09-29-post-p2-complete-plan.md
    └── …
```

## Sources (now consolidated)

The following files previously held planning material; they have been **read,
extracted into this folder, and the originals are now either archived here or
left in place with a redirect notice**:

| Original location | Status | Replaced by |
|---|---|---|
| `/IMPROVEMENT_BACKLOG.md` (root) | **Superseded by** [`BACKLOG.md`](BACKLOG.md) | (file kept at root with redirect header) |
| `/COMPLETE_PLAN.md` (root) | **Archived** | `historical-plans/2026-09-??-complete-plan.md` |
| `/COMPLETE_APP_MAP.md` (root) | **Archived** (app map, not plan) | `audits/SASKIA_COMPLETE_APP_MAP_2026-09-22.md` |
| `/COMPREHENSIVE_WORK_PLAN.md` (root) | **Archived** | `historical-plans/2026-09-??-comprehensive-work-plan.md` |
| `/PHASE2_IMPLEMENTATION_PLAN.md` (root) | **Archived** | `historical-plans/2026-09-??-phase2-implementation-plan.md` |
| `/PHASE2_WORK_PLAN.md` (root) | **Archived** | `historical-plans/2026-09-??-phase2-work-plan.md` |
| `/SASKIA_TEST_PLAN.md` (root) | **Archived** (test plan) | `audits/SASKIA_TEST_PLAN_2026-09.md` |
| `/SPRINT_SUMMARY.md` (root) | **Archived** (herebus sprint) | `sessions/2026-09-23-herebus-sprint.md` |
| `/SASKIA_BACKEND_AUDIT_2026-09-22.md` (root) | **Archived** | `audits/SASKIA_BACKEND_AUDIT_2026-09-22.md` |
| `/FRONTEND_AUDIT_2026-09-22.md` (root) | **Archived** | `audits/FRONTEND_AUDIT_2026-09-22.md` |
| `/FULL_AUDIT_300.md` (root) | **Archived** | `audits/FULL_AUDIT_300_2026-09-22.md` |
| `/HEREBUS_INTEGRATION_PLAN.md` (root) | **Archived** (herebus plan) | `historical-plans/HEREBUS_INTEGRATION_PLAN.md` |
| `/WHAT_NEXT.md` (root) | **Superseded** by STATUS + BACKLOG | redirect header at top |
| `/DEPLOY_URGENT.md` (root) | **Archived** (incident note) | `audits/DEPLOY_URGENT_2026-09.md` |
| `/DIAGNOSIS_VENTAS_500.md` (root) | **Archived** (incident note) | `audits/DIAGNOSIS_VENTAS_500.md` |
| `/PRODUCTION_500_RUNBOOK.md` (root) | **Moved** to `operations/` | `docs/operations/PRODUCTION_500_RUNBOOK.md` |
| `/docs/plans/2026-08-31-rms-fase-1-dev-plan.md` | **Archived** | `historical-plans/…` |
| `/docs/plans/2026-09-rms-fase-1-dev-plan-v2.md` | **Archived** | `historical-plans/…` |
| `/docs/plans/2026-09-07-saskia-complete-epic-plan-v3.md` | **Extracted → epics/** | `epics/00-EPIC-PLAN-EXTRACT.md` |
| `/docs/plans/2026-09-08-saskia-state-analysis.md` | **Archived** | `historical-plans/…` |
| `/docs/plans/2026-09-08-saskia-data-intelligence-v4.md` | **Archived** | `historical-plans/…` |
| `/docs/plans/2026-09-17-saskia-prelaunch-roadmap.md` | **Archived** (pre-launch plan, all phases done) | `historical-plans/…` |
| `/docs/plans/2026-09-17-saskia-visual-revolution-plan.md` | **Archived** (visual plan) | `historical-plans/…` |
| `/docs/plans/2026-09-23-second-review-execution-plan.md` | **Archived** | `sessions/…` |
| `/docs/plans/2026-09-25-*.md` (4 files) | **Archived** (visual/test critiques) | `audits/…` |
| `/docs/plans/2026-09-26-full-visual-critique.md` | **Archived** | `audits/…` |
| `/docs/plans/2026-09-27-image-asset-plan.md` | **Archived** | `historical-plans/…` |
| `/docs/plans/2026-09-29-saskia-rms-multi-session-recovery-plan.md` | **Moved** | `sessions/…` |
| `/docs/plans/2026-09-29-post-p2-complete-plan.md` | **Moved** | `sessions/…` |
| `/docs/plans/2026-10-01-phase14-*.md` (3 files) | **Archived** (Phase 14 work — all done) | `historical-plans/2026-10-phase14/…` |
| `/docs/plans/redesign-2026-09-26/*.md` (4 files) | **Archived** (redesign) | `historical-plans/2026-09-redesign/…` |
| `/docs/decisions/2026-09-29-canonical-roadmap-alignment.md` | **Kept** (decision doc, also linked from BACKLOG) | `decisions/…` |
| `/docs/decisions/v1/40-hats-pre-canonical.md` | **Kept** (historical decision) | `decisions/v1/…` |
| `/docs/upgrades/2026-09-29-UX-UPGRADE-PLAN.md` | **Archived** (UX upgrade plan) | `historical-plans/…` |
| `/docs/intake/SASKIA-201-visual-revolution-phase0.md` | **Archived** (intake) | `historical-plans/intake/…` |
| `/docs/p1-p2-wishlist-2026-09-27.md` | **Merged** into BACKLOG | (kept for reference, redirect header) |
| `/docs/HOUR-LOG.md`, `BANK-FEATURES-SUMMARY.md`, `TEST_ARCHITECTURE.md` | **Kept** (specialized) | (no move) |
| `/docs/operations/*` (runbooks, deploy, healthz, dashboard) | **Kept as-is** (operator-facing) | (no move) |
| `/docs/competitors/*`, `/docs/qa/*`, `/docs/reports/*`, `/docs/sessions/round-2-feedback.md` | **Kept as-is** (specialized) | (no move) |
| `/docs/adr/ADR-001-test-architecture.md` | **Moved** | `decisions/ADR-001-test-architecture.md` |
| `/docs/wishlist/*` | **Kept as-is** (append-only bucket) | indexed by [`WISHLIST.md`](WISHLIST.md) |
| `/docs/user-guide/*` | **Kept as-is** (Saskia-facing) | (no move) |

> **Move vs. archive.** "Archived" means the file's content is now reflected
> in `BACKLOG.md` / `epics/` / `STATUS.md`, and the original lives in
> `docs/roadmap/historical-plans/` or `docs/roadmap/audits/`. The git history
> is untouched. Old root-level `*.md` files are kept **in place** with a
> redirect notice at the top so external links don't 404.
