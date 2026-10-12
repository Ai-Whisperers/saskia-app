# Department Index — What's Where

> **For each Tier-1 dept**: agents, monitors, research, KPIs, signals, state files, scripts, executed artifacts.
> **Built**: 2026-09-01 (Phase 8 R5).
> **Source-of-truth (files on disk)**: this file is regenerated whenever dept structure changes (last regenerated: 2026-09-01).
> **Source-of-truth (design meetings)**: [`meetings/department-design/README.md`](meetings/department-design/README.md).

---

## How to read this

Each section follows the same shape:
1. **Lead agent** (the dept's `PROMPT.md` owner)
2. **Sub-agents** (Tier-2 / Tier-3 agents under the lead)
3. **Monitors** (PROMPT-monitor.md + cron wiring)
4. **State files** (what state this dept reads/writes)
5. **KPIs & signals** (`demiurge/kpi/*-stack.yaml`, `demiurge/signals/*.yaml`)
6. **Research** (`research/dept-research/{N}-{dept}-research-areas.md`)
7. **Executed artifacts** (Phase 8: what got built)
8. **Owner** (human + agent pair)

---

# 01-operations

**Purpose**: Process excellence, automation, observability, compliance.

| | |
|---|---|
| **Charter** | `departments/01-operations.md` |
| **Lead agent** | `management-coordinator/` |
| **Owner** | Ivan + management-coordinator |

### Sub-agents (9)

| Agent | Cadence | Notes |
|---|---|---|
| `ai-ops-coordinator/` | monitor + daily variant | Observability orchestration |
| `bizops-tracker/` | weekly | Business-ops analytics |
| `compliance-monitor/` | weekly | Trademark + GDPR + LGPD checks |
| `founder-bandwidth-watchdog/` | weekly | Ivan bandwidth tracking |
| `okr-tracker/` | monthly | OKR rollup |
| `procurement-tracker/` | weekly | Vendor spend review |
| `source-curator/` | monthly | Source-materials curation (cross-cut) |

### Monitors (5)

`ai-ops-coordinator`, `bizops-tracker`, `compliance-monitor`, `founder-bandwidth-watchdog`, `okr-tracker`, `procurement-tracker`, `source-curator`, `management-coordinator` (8 PROMPT-monitor.md files).

### State files

- `/opt/data/state/coord.json` (coordinator)
- `/opt/data/state/cron-error-watchdog.json` (observability)
- `/opt/data/state/errors.json` (errors)
- `/opt/data/agents/state/coord.json` (mirror)

### KPIs & signals

- KPI: `demiurge/kpi/operations-stack.yaml`
- Signals: `demiurge/signals/operations.yaml`

### Research

- **Catalog**: `research/dept-research/01-operations-research-areas.md` (6 areas)
- HOT: self-running criteria, hard-stops enforcement, cron heartbeat patterns

### Executed artifacts (Phase 8)

- `operations/self-running-scorecard-2026.md` — 4.5/7 score
- `operations/hard-stops-enforcement-audit.md` — 0/49 invoke wrapper
- `operations/cron-error-patterns-30d.md` — 6 jobs in error
- `operations/monitor-threshold-calibration-2026.md` — pre-calibration plan
- `operations/health-dashboard.md` — per-dept scoring

### Outbox pattern

- `01-operations/ai-ops-coordinator-daily/` — parent cron writes to `outbox/`. README explains.

---

# 02-finance-legal

**Purpose**: Compliance, funding, runway, contracts.

| | |
|---|---|
| **Charter** | `departments/02-finance-legal.md` |
| **Lead agent** | `finance-controller/` |
| **Owner** | Ivan + finance-controller |

### Sub-agents (5)

| Agent | Cadence | Notes |
|---|---|---|
| `accounting-automation/` | weekly + daily variant | Bookkeeping + invoicing |
| `business-analyst/` | weekly + daily variant | Cost + revenue analytics |
| `funding-coordinator/` | monthly | Grants + accelerators |
| `tax-receipt-tracker/` | weekly | Tax + receipts |

### Monitors (4)

`accounting-automation`, `business-analyst`, `finance-controller`, `tax-receipt-tracker` (4 PROMPT-monitor.md files).

### State files

- `/opt/data/agents/state/finance.json`
- `/opt/data/agents/state/funding.json`
- `/opt/data/agents/state/cash-flow-projection-v0.1.md`
- `/opt/data/state/finance.json` (live)

### KPIs & signals

- KPI: `demiurge/kpi/finance-stack.yaml`
- Signals: `demiurge/signals/finance-legal.yaml`

### Research

- **Catalog**: `research/dept-research/02-finance-legal-research-areas.md` (8 areas)
- HOT: margin reality check, EU AI Act compliance

### Executed artifacts (Phase 8)

- `finance/funding-landscape-2026-Q4.md` — 3 new leads (SIC, Google for Startups, OSC)
- `finance/compliance-jurisdiction-matrix.md` — PY/NL/EU/US matrix
- `finance/tax-structure-comparison.md` — 3 options comparison

### Outbox pattern

- `02-finance-legal/accounting-automation-daily/` — parent cron writes to `outbox/`. README explains.

---

# 03-sales-growth

**Purpose**: Revenue generation, pipeline, outreach, proposals.

| | |
|---|---|
| **Charter** | `departments/03-sales-growth.md` |
| **Lead agent** | `sales-pipeline/` |
| **Owner** | Ivan + sales-pipeline |

### Sub-agents (6)

| Agent | Cadence | Notes |
|---|---|---|
| `lead-enrichment/` | weekly + daily variant | Cadmus lead enrichment |
| `marketing-content-producer/` | weekly | Content generation |
| `multimedia-producer/` | weekly | Multimedia assets |
| `proposal-drafter/` | on-demand variant | Proposal drafting (Metis) |
| `revops-pipeline-analyzer/` | weekly + daily variant | RevOps analytics |
| `sales-pipeline/` | 2x/day | Core pipeline (currently broken — Worker 404) |

### Monitors (6)

All 6 sub-agents have PROMPT-monitor.md + cron wiring.

### State files

- `/opt/data/agents/state/sales.json` (currently empty: 0 leads, 0 deals)
- `/opt/data/state/customers.json`
- `/opt/data/state/coaching-customers.json`
- `/opt/data/state/conversion-attempts.json`

### KPIs & signals

- KPI: `demiurge/kpi/sales-stack.yaml`, `demiurge/kpi/revenue-stack.yaml`
- Signals: `demiurge/signals/sales-growth.yaml`

### Research

- **Catalog**: `research/dept-research/03-sales-growth-research-areas.md` (10 areas)
- HOT: **sales funnel revival** (Worker 404, 0 leads)

### Executed artifacts (Phase 8)

- `sales/funnel-revival-2026.md` — diagnosed Worker 404, recommended Formspree (1-2h vs 8-16h)
- `sales/customer-archaeology-2026.md` — ICP from real conversions
- `sales/whatsapp-outreach-playbook.md` — 3-phase ramp
- `sales/discovery-methodology-decision.md` — adopt Gap Selling
- `sales/lead-enrichment-pipeline.md` — Airtable Free pipeline
- `sales/competitive-positioning-matrix.md` — 3 ICPs × competitors

### Outbox pattern

- `03-sales-growth/{lead-enrichment-daily,proposal-drafter-on-demand,revops-pipeline-analyzer-daily}/` — parent cron writes to `outbox/`. README explains.

---

# 04-engineering

**Purpose**: Code, infrastructure, AI safety, observability, quality.

| | |
|---|---|
| **Charter** | `departments/04-engineering.md` |
| **Lead agent** | `engineering-roster/` |
| **Owner** | Kiki (CTO) + engineering-roster |

### Sub-agents (13)

| Agent | Cadence | Notes |
|---|---|---|
| `ai-safety-engineer/` + `-30min` | weekly + 30min | Gap G1 audit pending |
| `chaos-test-runner/` | weekly | NEW PROMPT (Phase 5). 5 scenarios ready. |
| `delivery-tracker/` | weekly | NEW PROMPT (Phase 5) |
| `devops-monitor/` + `-30min` | weekly + 30min | Infra monitoring |
| `drift-detector/` | weekly | NEW PROMPT (Phase 5). Calibration pending. |
| `engineering-roster/` | weekly | The lead itself |
| `eval-gate-runner/` | weekly | NEW PROMPT (Phase 5). Aggregate script ready. |
| `qa-automation-on-pr/` | on-PR | NEW PROMPT (Phase 5) |
| `qa-automation-runner/` | weekly | Test orchestration |
| `security-auditor/` | weekly | NEW PROMPT (Phase 5) |
| `security-watchdog/` + `-30min` | weekly + 30min | CVE + secret rotation |

### Monitors (13)

All 13 sub-agents have PROMPT-monitor.md (where applicable) + cron wiring. Most-tested dept.

### State files

- `/opt/data/agents/state/engineering.json`
- `/opt/data/state/eval-per-agent.json` (per-agent eval)
- `/opt/data/state/eval-trending.json` (aggregate; written by `scripts/eval-aggregate-pass-rate.py`)
- `/opt/data/state/validation-report.json`
- `/opt/data/state/llm-provider-health.json`
- `/opt/data/state/org-state.json`
- `/opt/data/state/agent-stats.json`

### KPIs & signals

- KPI: `demiurge/kpi/engineering-stack.yaml`
- Signals: `demiurge/signals/engineering.yaml`

### Research

- **Catalog**: `research/dept-research/04-engineering-research-areas.md` (10 areas)
- HOT: 12-factor re-audit, AI safety posture, eval aggregate

### Executed artifacts (Phase 8)

9 markdown + 1 Python script (10 areas):
- `engineering/12-factor-audit-2026-q3.md`
- `engineering/ai-safety-posture-2026.md` — 5 gaps identified
- `engineering/drift-detection-methodology.md`
- `engineering/chaos-test-runbook.md` — 5 scenarios ready
- **`scripts/eval-aggregate-pass-rate.py`** (DEPLOYED + tested + runs)
- `engineering/state-write-discipline-catalog.md` — 7 patterns
- `engineering/cron-heartbeat-strategy.md`
- `engineering/phase-25-revisit-2026.md` — 11/14 items done
- `engineering/mcp-maturity-tracking.md`
- `engineering/oss-dependency-audit.md`

---

# 05-research-education

**Purpose**: Knowledge management, thesis, courses, citations.

| | |
|---|---|
| **Charter** | `departments/05-research-education.md` |
| **Lead agent** | `research-tracker/` |
| **Owner** | Ivan + research-tracker |

### Sub-agents (3)

| Agent | Cadence | Notes |
|---|---|---|
| `citation-checker/` | weekly | Citation coverage audit |
| `course-producer/` | weekly | 12-module courses |
| `research-tracker/` | weekly | The lead |
| `thesis-tracker/` | weekly | GeoData v2 thesis |

### Monitors (4)

All 4 sub-agents have PROMPT-monitor.md + cron wiring.

### State files

- `/opt/data/agents/state/research.json`
- `/opt/data/agents/state/citation-coverage.json` (if exists)
- `/opt/data/state/prompt-improvements.md`

### KPIs & signals

- KPI: `demiurge/kpi/research-stack.yaml`
- Signals: `demiurge/signals/research-education.yaml`

### Research

- **Catalog**: `research/dept-research/05-research-education-research-areas.md` (8 areas)
- HOT: citation coverage audit (15% overall, 70% in research/)

### Executed artifacts (Phase 8)

- `research/citation-coverage-audit-2026.md` — 15% overall, 70% in research/
- `research/source-materials-curation-policy.md` — 4-dim scoring system
- `research/peer-review-process.md` — 3-step review

---

# 06-people-culture

**Purpose**: Founder health, first-FTE prep, coaching.

| | |
|---|---|
| **Charter** | `departments/06-people-culture.md` |
| **Lead agent** | `people-hr/` |
| **Owner** | Ivan + Kiki (co-owned) |

### Sub-agents (0 in this repo)

- `people-hr/` is the only dept-level agent here
- **Disposition (2026-09-04, DEMIURGE-152)**: `dormant-active` — keeps weekly cadence + monitor wiring, but output contract narrowed to ONE weekly brief: founder-bandwidth risks, unresolved human-ownership decisions, first-hire trigger status. Compensation/equity sections suspended (2-person org, no banding to manage). Re-activates fully at first hire. Rationale: a symbolic department that never runs is worse than an honest narrowed contract; the outbox + monitor already exist, so the cheapest honest state is a smaller promise kept.
- **`kiki-coach`** lives in sister repo `coach-agents/` (cross-repo coordination)

### Monitors (1)

`people-hr/` has PROMPT-monitor.md + cron wiring.

### State files

- `/opt/data/agents/state/people.json` (currently `last_run: null` — never fired)
- `/opt/data/agents/state/kiki.json`
- `/opt/data/agents/state/kiki-prep.json`

### KPIs & signals

- KPI: `demiurge/kpi/people-stack.yaml`
- Signals: `demiurge/signals/people-culture.yaml`

### Research

- **Catalog**: `research/dept-research/06-people-culture-research-areas.md` (6 areas)
- HOT: Ivan bandwidth audit, Kiki growth path (needs Kiki input)

### Executed artifacts (Phase 8)

None (all 6 research areas need Ivan or Kiki input — correctly deferred).

### Outbox pattern

- `06-people-culture/people-hr/outbox/` — daily cron writes here.

---

# board-of-directors

**Purpose**: Cross-dept governance, quarterly reviews, risk oversight. **Not a charter dept**.

| | |
|---|---|
| **Lead agent** | `board-of-directors/` |
| **Co-chairs** | Ivan + Kiki (per 2026-09-01 clarification; tiebreaker rotates monthly) |

### Sub-agents (0)

The board is the dept-lead itself; no sub-agents (doctrine: governance is light-touch).

### Monitors (1)

`board-of-directors/` has PROMPT-monitor.md.

### State files

- Reads from all dept state files (cross-cutting)
- Writes decision logs to `state/decisions/`

### KPIs & signals

- KPI: `demiurge/kpi/board-stack.yaml`
- Signals: `demiurge/signals/board-of-directors.yaml`

### Research

- **Catalog**: `research/dept-research/board-of-directors-research-areas.md` (4 areas)
- WARM: co-chair decision-making, quarterly review, risk oversight

### Executed artifacts (Phase 8)

- `board/co-chair-decision-rights.md` — M4 (time-bounded consensus) recommended
- `board/quarterly-review-template.md` — ready for 2026-10-01
- `board/risk-register-2026.md` — 12 risks, 3 CRITICAL

---

## Summary stats

| Dept | Sub-agents | Monitors | Research areas | Executed (Phase 8) |
|---|---:|---:|---:|---:|
| 01-operations | 9 | 8 | 6 | 5 |
| 02-finance-legal | 5 | 4 | 8 | 3 |
| 03-sales-growth | 6 | 6 | 10 | 6 |
| 04-engineering | 13 | 13 | 10 | 10 |
| 05-research-education | 4 | 4 | 8 | 3 |
| 06-people-culture | 1 | 1 | 6 | 0 |
| board-of-directors | 1 | 1 | 4 | 3 |
| **TOTAL** | **39** | **37** | **52** | **30** |

**Note**: Sub-agent counts include cadence variants (e.g., `-daily`, `-30min`).
