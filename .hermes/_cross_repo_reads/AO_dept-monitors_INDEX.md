# Department Monitors — INDEX

> Watchdog agents that monitor each department's state file and alert on off-threshold metrics. Pattern from August 13 transcription: *"Agent that is monitoring the department, not executing the work."*

Each monitor lives at `/opt/data/agents/<dept-folder>/PROMPT-monitor.md` alongside the existing lead `PROMPT.md`. They are read-only — no monitor mutates its watched state file. MEDIUM alerts go to a parallel `monitor-notes/YYYY-MM-DD.md` file because every owned schema has `additionalProperties: false`.

## Master matrix (16 monitors)

| # | Dept | Folder | Watched state file(s) | Metrics watched | Cron | Alias |
|---|------|--------|----------------------|------------------|------|-------|
| 1 | finance | `finance-controller/` | `finance.json` | 8 | `*/30 * * * *` | `aiw-finance-monitor-30min` |
| 2 | people-hr | `people-hr/` | `people.json` | 7 | `*/30 * * * *` | `aiw-people-hr-monitor-30min` |
| 3 | legal-compliance | `compliance-monitor/` | `finance.json`, `funding.json`, `analyst.json` | 5 | `*/30 * * * *` | `aiw-legal-compliance-monitor-30min` |
| 4 | engineering | `engineering-roster/` | `engineering.json` | 8 | `*/30 * * * *` | `aiw-engineering-monitor-30min` |
| 5 | qa | `qa-automation-runner/` | `eval-per-agent.json`, `validation-report.json`, `engineering.json` | 6 | `*/30 * * * *` | `aiw-qa-monitor-30min` |
| 6 | operations | `ai-ops-coordinator/` | `coord.json`, `agent-stats.json`, `errors.json`, `heartbeat-alerts.json` | 7 | `*/15 * * * *` | `aiw-ops-monitor-15min` |
| 7 | research | `research-tracker/` | `research.json` | 10 | `*/30 * * * *` | `aiw-research-monitor-30min` |
| 8 | marketing | `marketing-content-producer/` | `sales.json`, `analyst.json`, `marketing-content-producer/outbox/` | 8 | `*/30 * * * *` | `aiw-marketing-monitor-30min` |
| 9 | multimedia | `multimedia-producer/` | `research.json`, `analyst.json`, `multimedia-producer/outbox/` | 4 | `*/30 * * * *` | `aiw-multimedia-monitor-30min` |
| 10 | sales | `sales-pipeline/` | `sales.json` | 9 | `*/30 * * * *` | `aiw-sales-monitor-30min` |
| 11 | procurement | `procurement-tracker/` | `finance.json` | 5 | `*/30 * * * *` | `aiw-procurement-monitor-30min` |
| 12 | accounting | `accounting-automation/` | `finance.json` | 8 | `*/30 * * * *` | `aiw-accounting-monitor-30min` |
| 13 | management | `management-coordinator/` | `coord.json` | 4 | `*/30 * * * *` | `aiw-management-monitor-30min` |
| 14 | board | `board-of-directors/` | `funding.json`, `coord.json`, `funding-coordinator/outbox/` | 8 | `*/30 * * * *` | `aiw-board-monitor-30min` |
| 15 | coaching | `coach-practitioner/` | `kiki.json`, `kiki-prep.json`, `coaching-customers.json`, `conversion-attempts.json` | 9 | `*/30 * * * *` | `aiw-coaching-monitor-30min` |
| 16 | funding | `funding-coordinator/` | `funding.json`, `funding-coordinator/outbox/` | 13 | `*/30 * * * *` | `aiw-funding-monitor-30min` |

**Total**: 16 monitor jobs, 15 × `*/30 * * * *` + 1 × `*/15 * * * *` (operations).

## Threshold rules — quick reference

Every monitor uses the same severity ladder, inherited from `/opt/data/agents/ORG-AGENTS.md` §3:

| Severity | Channel | Example |
|----------|---------|---------|
| **CRITICAL** | `coord.json:decisions_for_ivan[]` (data loss / payment failure / site down) | `mrr_usd = 0`, runway < 1.5mo, P0 incident |
| **HIGH** | `coord.json:decisions_for_ivan[]` (revenue-blocking / deadline imminent) | stalled deal > 30d, renewal lapsed, streak broken |
| **MEDIUM** | `<dept-folder>/monitor-notes/YYYY-MM-DD.md` (process gap / stale repo) | length growth, stale but not broken |
| **LOW** | silent (cosmetic / nice-to-have) | long backlog growth, minor drift |

**Why a parallel notes file for MEDIUM?** Every owned schema (`finance`, `sales`, `engineering`, `research`, `people`, `coord`, `analyst`, `kiki`, `kiki-prep`) sets `additionalProperties: false`. A monitor that writes into the watched file would either violate the schema or pollute it. The parallel `monitor-notes/` directory keeps the lead agent's state file clean.

**Exception**: the operations and management monitors may write to `coord.json:decisions_for_ivan[]` for HIGH/CRITICAL only, because their job *is* coord-level escalation.

## Schemas referenced

All schemas live under `/opt/data/agents/schemas/`:

| Schema | File | Owner dept monitors |
|--------|------|---------------------|
| `finance.schema.json` | finance, legal-compliance, procurement, accounting | 4 |
| `sales.schema.json` | marketing, sales | 2 |
| `engineering.schema.json` | engineering, qa | 2 |
| `research.schema.json` | research, multimedia, marketing | 3 |
| `people.schema.json` | people-hr | 1 |
| `coord.schema.json` | operations, management, board | 3 |
| `analyst.schema.json` | marketing, multimedia, legal-compliance | 3 |
| `kiki.schema.json` | coaching | 1 |
| `kiki-prep.schema.json` | coaching | 1 |
| (no schema) `funding.json` | legal-compliance, board, funding | 3 |
| (no schema) `eval-per-agent.json`, `validation-report.json` | qa | 1 |
| (no schema) `agent-stats.json`, `errors.json`, `heartbeat-alerts.json` | operations | 1 |
| (no schema) `coaching-customers.json`, `conversion-attempts.json` | coaching | 1 |

## State-file write discipline (all monitors)

1. Read watched file(s).
2. Validate against schema (where one exists) via `python3 /opt/data/scripts/aiw-state-validate.py <schema-key>`. Schema-invalid → HIGH escalation with the validator output.
3. Evaluate every metric → fire per the routing table.
4. CRITICAL/HIGH → append to `coord.json:decisions_for_ivan[]` using the coord.schema.json item shape: `{question, context, raised_at}`.
5. MEDIUM → append to `<dept-folder>/monitor-notes/YYYY-MM-DD.md` (parallel, read-only on the watched state).
6. LOW → silent.
7. Never mutate the watched state file directly. Never contact Ivan outside the coord.json channel. Never act — only report.

## Adding a new monitor

1. Pick a real state file on disk + its schema (or a real file with no schema, like `funding.json`).
2. List every metric from `required` + every `properties` field that's relevant to the dept.
3. Map each metric to CRITICAL/HIGH/MEDIUM/LOW using the ladder above.
4. Decide the watched-folder location and the cron alias.
5. Write `PROMPT-monitor.md` ≤ 3 KB with the 5 mandatory sections (purpose, files watched, metrics, thresholds, alerts + cron).
6. Run `python3 /opt/data/scripts/trademark-scan.py <path>` — must be CLEAN.
7. Update this INDEX.md (new row + bump the total).

## Cross-references

- `/opt/data/agents/ORG-AGENTS.md` §3 — canonical escalation rules.
- `/opt/data/agents/schemas/*.json` — owned schemas.
- `/opt/data/scripts/aiw-state-validate.py` — schema validator (called by monitors).
- `/opt/data/scripts/trademark-scan.py` — 30-token banlist scanner (must pass).

## CHANGELOG

- v0.1.0 (2026-08-26): initial INDEX covering 16 monitors across all 16 departments.