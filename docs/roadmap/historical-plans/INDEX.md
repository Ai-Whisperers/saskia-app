# Historical Plans (Index)

> **Purpose.** This folder preserves the original planning documents that
> informed the current [`docs/roadmap/`](../) structure. These docs are
> **read-only historical reference** — the actionable items have been
> extracted into `docs/roadmap/BACKLOG.md` and `docs/roadmap/epics/`.

## How to read this

| You want to know… | Read this |
|---|---|
| What was the original Fase 1 plan? | [`2026-08-31-rms-fase-1-dev-plan.md`](2026-08-31-rms-fase-1-dev-plan.md) (v1) and [`2026-09-rms-fase-1-dev-plan-v2.md`](2026-09-rms-fase-1-dev-plan-v2.md) (v2, current) |
| What was the full "gem project" scope? | [`epics/00-EPIC-PLAN-EXTRACT.md`](../epics/00-EPIC-PLAN-EXTRACT.md) (extracted from v3 epic plan) |
| What was the pre-launch roadmap? | [`2026-09-17-saskia-prelaunch-roadmap.md`](2026-09-17-saskia-prelaunch-roadmap.md) (all phases done) |
| What was the visual revolution plan? | [`2026-09-17-saskia-visual-revolution-plan.md`](2026-09-17-saskia-visual-revolution-plan.md) |
| What was the data intelligence plan? | [`2026-09-08-saskia-data-intelligence-v4.md`](2026-09-08-saskia-data-intelligence-v4.md) |
| What was the state analysis? | [`2026-09-08-saskia-state-analysis.md`](2026-09-08-saskia-state-analysis.md) |
| What was the image asset plan? | [`2026-09-27-image-asset-plan.md`](2026-09-27-image-asset-plan.md) |
| What was the HEREBUS integration plan? | [`HEREBUS_INTEGRATION_PLAN_2026-09.md`](HEREBUS_INTEGRATION_PLAN_2026-09.md) (sprint summary: [`../sessions/herebus-sprint/2026-09-23-herebus-sprint.md`](../sessions/herebus-sprint/2026-09-23-herebus-sprint.md)) |
| What was the redesign plan (26 Sep)? | [`2026-09-redesign/`](2026-09-redesign/) (master plan, work items, reuse abstraction) |
| What was the Phase 14 (Oct) coverage + TODO inventory? | [`2026-10-phase14/`](2026-10-phase14/) |

## Root-level plan files (preserved at `/` for git history; see redirect headers)

The following files live at the repo root and now start with a redirect
notice. They are NOT deleted because git history is the source of truth.

| Original (root) | Archived to | Status |
|---|---|---|
| `/COMPLETE_PLAN.md` | [`COMPLETE_PLAN_2026-09.md`](COMPLETE_PLAN_2026-09.md) | superseded by epic plan |
| `/COMPREHENSIVE_WORK_PLAN.md` | [`COMPREHENSIVE_WORK_PLAN_2026-09.md`](COMPREHENSIVE_WORK_PLAN_2026-09.md) | superseded |
| `/PHASE2_IMPLEMENTATION_PLAN.md` | [`PHASE2_IMPLEMENTATION_PLAN_2026-09.md`](PHASE2_IMPLEMENTATION_PLAN_2026-09.md) | superseded |
| `/PHASE2_WORK_PLAN.md` | [`PHASE2_WORK_PLAN_2026-09.md`](PHASE2_WORK_PLAN_2026-09.md) | superseded |
| `/HEREBUS_INTEGRATION_PLAN.md` | [`HEREBUS_INTEGRATION_PLAN_2026-09.md`](HEREBUS_INTEGRATION_PLAN_2026-09.md) | shipped; see sprint summary |
| `/SPRINT_SUMMARY.md` | [`../sessions/herebus-sprint/2026-09-23-herebus-sprint.md`](../sessions/herebus-sprint/2026-09-23-herebus-sprint.md) | shipped |
| `/WHAT_NEXT.md` | redirect header at top | superseded by STATUS + BACKLOG |
| `/SASKIA_BACKEND_AUDIT_2026-09-22.md` | [`../audits/SASKIA_BACKEND_AUDIT_2026-09-22.md`](../audits/SASKIA_BACKEND_AUDIT_2026-09-22.md) | superseded |
| `/FRONTEND_AUDIT_2026-09-22.md` | [`../audits/FRONTEND_AUDIT_2026-09-22.md`](../audits/FRONTEND_AUDIT_2026-09-22.md) | superseded |
| `/FULL_AUDIT_300.md` | [`../audits/FULL_AUDIT_300.md`](../audits/FULL_AUDIT_300.md) | superseded |
| `/COMPLETE_APP_MAP.md` | [`../audits/SASKIA_COMPLETE_APP_MAP_2026-09-22.md`](../audits/SASKIA_COMPLETE_APP_MAP_2026-09-22.md) | app map, not plan |
| `/DEPLOY_URGENT.md` | [`../audits/DEPLOY_URGENT_2026-09.md`](../audits/DEPLOY_URGENT.md) | incident note |
| `/DIAGNOSIS_VENTAS_500.md` | [`../audits/DIAGNOSIS_VENTAS_500.md`](../audits/DIAGNOSIS_VENTAS_500.md) | incident note |
| `/PRODUCTION_500_RUNBOOK.md` | [`../operations/PRODUCTION_500_RUNBOOK.md`](../../operations/PRODUCTION_500_RUNBOOK.md) | runbook |
| `/SASKIA_TEST_PLAN.md` | [`../audits/SASKIA_TEST_PLAN.md`](../audits/SASKIA_TEST_PLAN.md) | superseded |
| `/SPRINT_SUMMARY.md` | [`../sessions/herebus-sprint/2026-09-23-herebus-sprint.md`](../sessions/herebus-sprint/2026-09-23-herebus-sprint.md) | shipped |
| `/LOGGING_ERRORS_AUDIT_2026-09-29.md` | [`../audits/2026-09-29/LOGGING_ERRORS_AUDIT_2026-09-29.md`](../audits/LOGGING_ERRORS_AUDIT_2026-09-29.md) | superseded |
| `/LOGGING_STATUS_2026-09-29.md` | [`../audits/2026-09-29/LOGGING_STATUS_2026-09-29.md`](../audits/LOGGING_STATUS_2026-09-29.md) | superseded |
| `/CSS_AUDIT.md`, `/FORMS_INPUT_AUDIT.md`, `/UI_ANALYSIS_REPORT.md`, `/UI_PERF_AUDIT_REPORT.md`, `/PERFORMANCE_ANALYSIS_REPORT.md`, `/OBSERVABILITY_AUDIT.md` | [`../audits/`](../audits/) | superseded |
| `/SASKIA_BACKEND_AUDIT_2026-09-22.md` | [`../audits/SASKIA_BACKEND_AUDIT_2026-09-22.md`](../audits/SASKIA_BACKEND_AUDIT_2026-09-22.md) | superseded |

## Note on duplicates

`docs/plans/` still contains the original files; they remain there because
removing them would lose the git-blame trail. Going forward, all new
planning material should land in `docs/roadmap/`, not `docs/plans/`.
