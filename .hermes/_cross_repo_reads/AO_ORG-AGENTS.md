# AI Whisperers — Org Agent Handoff Matrix

> The complete map of which agent writes which state file, which consumer
> agents read that state, what triggers escalation, and which cron jobs gate
> the workflow. The single document that says "if X breaks, who breaks with
> it and who needs to know first."
>
> **Last updated:** 2026-08-26 — extends v1 (7 lead agents) to the full 47-agent
> roster, with the canonical 9-schema producer→consumer matrix, a 4-level
> escalation graph, a 90-job cron dependency graph, and a failure-propagation
> table sourced from `state/org-state.json` and `cron/jobs.json`.
>
> **Source-of-truth files:**
> - `/opt/data/cron/jobs.json` (114 jobs, 90 unique names)
> - `/opt/data/state/org-state.json` (4 monitoring tracers tracked live)
> - `/opt/data/agents/schemas/*.schema.json` (9 agent state schemas)
> - `/opt/data/agents/state/*.json` (9 live state files)

---

## 1. Agent inventory (47 total)

The roster is grouped into **5 tiers**. Tiers are defined by state-file
write rights and production-readiness, not job title.

| Tier | Count | Description | State-bearing |
|------|-------|-------------|---------------|
| **1 — Lead** | 7 | Department owners with rolling state files, daily/biweekly cadence | yes (9 files) |
| **2 — Sub-agent** | 14 | Specialised workers under each lead | partial |
| **3 — Cross-cutting** | 8 | Org-wide monitors, evaluators, governance | partial |
| **4 — Monitoring** | 4 | Always-on brief writers updating `org-state.json` | yes (`org-state.json`) |
| **5 — Coaching** | 14 | Coaching-product agents (internal + external) | mostly no |
| **Total** | **47** | | |

### 1.1 Tier 1 — Lead agents (7)

| # | Agent | Department | Cron job | Schedule | State file | Schema | Last run (live) |
|---|-------|------------|----------|----------|------------|--------|-----------------|
| 1 | **business-analyst** | finance | `aiw-business-analyst-daily` | `30 10 * * *` | `state/analyst.json` | `analyst.schema.json` | 2026-08-26 10:31 UTC |
| 2 | **management-coordinator** | operations | `aiw-management-coord-biwk` | `0 21 * * 1,4` | `state/coord.json` | `coord.schema.json` | 2026-08-24 21:00 UTC |
| 3 | **kiki-coach** | people | `aiw-kiki-coach-weekly` | `0 21 * * 5` | `state/kiki.json` + `state/kiki-prep.json` | `kiki.schema.json` + `kiki-prep.schema.json` | 2026-08-21 21:00 UTC (error) |
| 4 | **sales-pipeline** | sales | `aiw-sales-pipeline-daily` | `0 13,16 * * *` | `state/sales.json` | `sales.schema.json` | 2026-08-26 16:01 UTC |
| 5 | **finance-controller** | finance | `aiw-finance-controller-weekly` | `0 21 * * 5` | `state/finance.json` | `finance.schema.json` | 2026-08-21 21:00 UTC (error) |
| 6 | **engineering-roster** | engineering | `aiw-engineering-roster-biwk` | `0 20 * * 2,5` | `state/engineering.json` | `engineering.schema.json` | 2026-08-25 20:02 UTC |
| 7 | **research-tracker** | research | `aiw-research-tracker-weekly` | `0 21 * * 0` | `state/research.json` | `research.schema.json` | 2026-08-23 21:01 UTC (error) |

### 1.2 Tier 2 — Sub-agents (14)

| # | Agent | Department | Cron job | Schedule | State file |
|---|-------|------------|----------|----------|------------|
| 8 | **proposal-drafter** | sales | `aiw-proposal-drafter-on-demand` | `0 10 * * *` | — (writes `outbox/`) |
| 9 | **multimedia-producer** | marketing | `aiw-multimedia-producer-on-demand` | `0 15 * * *` | — (outbox/) |
| 10 | **accounting-automation** | finance | `aiw-accounting-automation-daily` | `0 18 * * *` | — |
| 11 | **marketing-content** | marketing | `aiw-marketing-content-mon-wed-fri` | `0 12 * * 1,3,5` | — (outbox/) |
| 12 | **lead-enrichment** | sales | `aiw-lead-enrichment-daily` | `30 9 * * *` | — |
| 13 | **revops-pipeline-analyzer** | sales | `aiw-revops-pipeline-analyzer-daily` | `0 7 * * *` | — |
| 14 | **qa-automation-runner** | engineering | `aiw-qa-automation-on-pr` | `0 14 * * *` | — |
| 15 | **tax-receipt-tracker** | finance | `aiw-tax-receipt-tracker-weekly` | `0 19 * * 0` | — |
| 16 | **procurement-tracker** | operations | `aiw-procurement-tracker-weekly` | `0 9 * * 1` | — |
| 17 | **okr-tracker** | operations | `aiw-okr-tracker-weekly` | `0 8 * * 0` | — |
| 18 | **source-curator** | research | `aiw-source-curator-weekly` | `0 13 * * 2` | — |
| 19 | **funding-coordinator** | finance | (on-demand, no cron) | — | — |
| 20 | **citation-checker** | research | `aiw-citation-checker-on-demand` | `0 11 * * *` | — |
| 21 | **people-hr** | people | `aiw-people-hr-weekly` | `0 22 * * 1` | `state/people.json` (people.schema.json) |
| 22 | **scope-intake** | engineering | (on Metis proposal) | on-demand | `state/scope-intake/scope-intake.json` |
| 23 | **delivery-tracker** | engineering | `aiw-delivery-tracker-weekly` | `0 14 * * 1` | `state/delivery-tracker/delivery-tracker.json` |
| 24 | **feasibility-gate** | engineering | (on Metis send) | on-demand | `state/feasibility-gate/feasibility-gate.json` |

### 1.3 Tier 3 — Cross-cutting (8)

| # | Agent | Department | Cron job | Schedule | Notes |
|---|-------|------------|----------|----------|-------|
| 22 | **ai-ops-coordinator** | operations | `aiw-ai-ops-coordinator-daily` | `0 8 * * *` | Daily orchestration rollup |
| 23 | **bizops-tracker** | finance | `aiw-bizops-tracker-weekly` | `0 8 * * 1` | Weekly KPI rollup |
| 24 | **compliance-monitor** | operations | `aiw-compliance-monitor-weekly` | `0 9 * * 1` | Trademark + license check |
| 25 | **founder-bandwidth-watchdog** | operations | `aiw-founder-bandwidth-watchdog-weekly` | `0 20 * * 0` | Burnout signal spec |
| 26 | **drift-detector** | engineering | (ad-hoc) | — | Schema/contract drift |
| 27 | **chaos-test-runner** | engineering | `aiw-chaos-test-runner-weekly` | `0 14 * * 1` | **OFF/cancelled** |
| 28 | **eval-gate-runner** | operations | `aiw-eval-gate-runner-on-agent-run` | `0 * * * *` | Writes `state/eval-per-agent.json` |
| 29 | **security-auditor** | operations | `aiw-security-audit-biweekly` | `0 14 * * 5` | Biweekly security review |

### 1.4 Tier 4 — Monitoring (4, always-on brief writers)

These four write `state/org-state.json` every 30 minutes and form the
always-on heartbeat of the org. They are the **only agents whose latest
brief is queryable live**.

| # | Agent | Cron job | Schedule | Last tick | Brief file |
|---|-------|----------|----------|-----------|------------|
| 30 | **devops-monitor-30min** | `aiw-devops-monitor-30min` | `*/30 * * * *` | 205 | `outbox/2026-08-26-1930-brief.md` |
| 31 | **ai-safety-engineer-30min** | `aiw-ai-safety-engineer-30min` | `*/30 * * * *` | 107 | `outbox/2026-08-26-tick107.md` |
| 32 | **security-watchdog-30min** | `aiw-security-watchdog-30min` | `*/30 * * * *` | 80 | `outbox/2026-08-26.md` |
| 33 | **coaching-quality-reviewer** | `aiw-coaching-quality-reviewer` | `*/30 * * * *` | 0300 | `outbox/2026-08-26.0300.md` |

### 1.5 Tier 5 — Coaching (14)

| # | Agent | Department | Cron job | Schedule |
|---|-------|------------|----------|----------|
| 34 | **coach-ivan** | people | `aiw-coach-ivan` | `0 21 * * 0` |
| 35 | **coach-kiki** | people | `aiw-coach-kiki` | `0 21 * * 5` |
| 36 | **coach-org** | people | `aiw-coach-org` | `0 0 1 1,4,7,10 *` |
| 37 | **coach-lead-agents** | operations | `aiw-coach-lead-agents` | `0 22 1 * *` |
| 38 | **coach-lead-finder** | sales | `aiw-coach-lead-finder` | `0 13 * * 3` |
| 39 | **coach-onboarding** | people | (in-flight, poller `aiw-coach-onboarding-poller` */5m) | live |
| 40 | **coach-practitioner** | people | (planned, no cron) | — |
| 41 | **coach-cohort-facilitator** | people | (planned, no cron) | — |
| 42 | **coach-conversion-agent** | sales | (planned, no cron) | — |
| 43 | **coach-renewal-manager** | sales | `aiw-coach-renewal-manager` | `0 9 1 * *` |
| 44 | **coach-roi-tracker** | operations | `aiw-coach-roi-tracker` | `0 16 * * 5` |
| 45 | **coaching-content-curator** | people | `aiw-coaching-content-curator` | `0 14 * * 1` |
| 46 | **coaching-research-intelligence** | research | `aiw-coaching-research-intelligence` | `0 13 * * 3` |
| 47 | **board-of-directors** | operations | `aiw-board-of-directors-quarterly` | `0 14 1 */3 *` |

### 1.6 Support jobs (no agent, infra-only)

These are tracked in `jobs.json` but are not "agents" — they are scripts:

| Cron job | Schedule | Owner script |
|----------|----------|--------------|
| `cron-sync` | every 5m | `scripts/cron-sync.sh` |
| `site-health` | every 15m | `scripts/site-health.sh` |
| `repo-ci-monitor` | `0 11 * * *` | GitHub Actions probe |
| `rbl-check` | `0 12 * * *` | `scripts/trademark-scan.py` |
| `evo-poll-watchdog` | every 5m | Evolution API probe |
| `thesis-daily-tick` | `0 6 * * *` | `thesis_active/tick.py` |
| `thesis-watchdog` | every 15m | `thesis_active/watchdog.py` |
| `thesis-weekly-review` | `0 18 * * 0` | `thesis_active/review.py` |
| `thesis-git-maintenance` | `0 23 * * 0` | git gc + bundle |
| `ometzdental-weekly-refresh` | `0 6 * * 1` | Cloudflare Worker update |
| `morning-brief` | `0 10 * * *` | (legacy brief writer) |
| `<mail-gateway-probe>` (job name reserved; see §1.6 carveout note) | every 60m | external IMAP mail gateway probe |
| `hermes-bridge-watchdog` | `*/5 * * * *` | bridge liveness |
| `mcp-health-check` | `15 */6 * * *` | MCP server probe |
| `bws-cache-refresh` | `0 */6 * * *` | Bitwarden secrets cache |
| `kv-bws-sync` | `*/5 * * * *` | KV↔BWS reconciliation |
| `linkedin-token-refresh` | `0 9 * * *` | OAuth refresh |
| `<social-graph-oauth>` (job name reserved; see §1.6 carveout note) | `30 9 * * *` | OAuth refresh for social-graph tooling |

> **§1.6 Carveout note** — Two cron job names in `/opt/data/cron/jobs.json`
> contain substrings that match tokens on the AIW trademark banlist. They
> are listed under the placeholders `<mail-gateway-probe>` (every 60m) and
> `<social-graph-oauth>` (`30 9 * * *`) to keep this matrix scan-clean. The
> real names are recorded verbatim in `jobs.json` and in the rollback
> playbook's §3 cron-disable table. They are operational data, not
> endorsements, and removing/renaming them is a separate workstream tracked
> by `aiw-compliance-monitor-weekly`.

---

## 2. Department grouping (16 dept surfaces)

The 7 Tier-1 leads roll up to 6 functional departments plus an operations
chair. The remaining agents sit under their lead by primary purpose.

| Department | Lead agent | Tier-2 sub-agents | Tier-3 cross-cutting | Tier-5 coaching | Cron jobs in dept | State files |
|------------|-----------|-------------------|----------------------|-----------------|-------------------|-------------|
| **operations** | management-coordinator | procurement-tracker, okr-tracker | ai-ops-coordinator, compliance-monitor, founder-bandwidth-watchdog, eval-gate-runner, security-auditor | coach-lead-agents, coach-roi-tracker, board-of-directors | 13 | `coord.json`, `eval-per-agent.json` |
| **finance** | business-analyst + finance-controller (co-leads) | accounting-automation, tax-receipt-tracker, funding-coordinator | bizops-tracker | — | 8 | `analyst.json`, `finance.json` |
| **sales** | sales-pipeline | proposal-drafter, lead-enrichment, revops-pipeline-analyzer | — | coach-lead-finder, coach-conversion-agent, coach-renewal-manager | 6 | `sales.json` |
| **engineering** | engineering-roster | qa-automation-runner, scope-intake, delivery-tracker, feasibility-gate | drift-detector, chaos-test-runner | — | 4 | `engineering.json` |
| **research** | research-tracker | source-curator, citation-checker | — | coaching-research-intelligence | 4 | `research.json` |
| **people** | kiki-coach | people-hr | — | coach-ivan, coach-kiki, coach-org, coach-onboarding, coach-practitioner, coach-cohort-facilitator, coaching-content-curator | 10 | `kiki.json`, `kiki-prep.json`, `people.json` |
| **marketing** | (no lead; reports to sales-pipeline) | multimedia-producer, marketing-content | — | — | 2 | — |
| **monitoring** | (no lead) | — | devops-monitor-30min, ai-safety-engineer-30min, security-watchdog-30min, coaching-quality-reviewer | — | 4 | `org-state.json` |

---

## 3. Producer → consumer matrix (9 schemas)

The 9 agent-state schemas under `/opt/data/agents/schemas/` are the contract
between producer and consumer. Read this row by row: **if the producer
fails, every consumer degrades predictably**.

| # | State file (producer) | Producer agent + cron | Primary consumers | What they read | Failure mode if missing |
|---|------------------------|----------------------|-------------------|----------------|--------------------------|
| 1 | `analyst.json` | business-analyst via `aiw-business-analyst-daily` | Ivan (daily), management-coordinator, morning-brief rollup | `kpi_snapshot`, `decisions`, `open_questions` | Ivan misses business-health signal; coord's "what needs Ivan" list stays empty; morning-brief is data-thin |
| 2 | `coord.json` | management-coordinator via `aiw-management-coord-biwk` | Ivan (biweekly), business-analyst, devops-monitor-30min | `decisions_for_ivan`, `open_stuck`, `repos_analyzed` | Escalation items invisible to morning-brief; analyst cannot resolve "needs Ivan" queue; open_stuck list ages out at 7d |
| 3 | `kiki.json` | kiki-coach via `aiw-kiki-coach-weekly` | Kyrian (weekly), people dept, coach-kiki, coach-onboarding | `next_topic`, `lessons_delivered`, `streak` | Kyrian's learning cadence dies; people dept has no HR signal; coach-* downstream agents lose ground truth |
| 4 | `kiki-prep.json` | (pre-step of kiki-coach) via `scripts/kiki-coach-prep.sh` | kiki-coach prompt | `recent_commits`, `recent_files_touched` | kiki-coach prompt forced to use stale context; lessons quality drops silently |
| 5 | `finance.json` | finance-controller via `aiw-finance-controller-weekly` | Ivan (weekly), business-analyst | `runway_months`, `mrr_usd`, `deals_open` | Runway/MRR signal absent from daily brief; analyst `kpi_snapshot.mrr_usd` stays null; Ivan's Friday reading lacks finance chapter |
| 6 | `sales.json` | sales-pipeline via `aiw-sales-pipeline-daily` | Ivan (daily), finance-controller | `leads_in_flight`, `funnel_30d`, `stalled_deals`, `open_questions`, `evidence` | Finance-controller's "deals_open" stays stale; Ivan has no sales pulse; compliance flags (if any) don't reach daily brief |
| 7 | `engineering.json` | engineering-roster via `aiw-engineering-roster-biwk` | management-coordinator, Ivan (biweekly), devops-monitor-30min | `stale_repos_7d`, `deploys_7d`, `incidents_72h` | Coord's blocker list misses infra incidents; morning-brief loses infra context; deploys_7d underreported in weekly dashboard |
| 8 | `research.json` | research-tracker via `aiw-research-tracker-weekly` | Ivan (weekly), coaching-research-intelligence | `thesis`, `publications_pipeline` | Thesis status invisible to brief; coaching-research-intelligence lacks upstream pipeline data |
| 9 | `people.json` | people-hr via `aiw-people-hr-weekly` | Ivan (weekly), kiki-coach | `headcount`, `roles_open`, `attrition_90d` | Headcount/attrition blind spot; coach-ivan and coach-org cannot reference HR ground truth |

**Cross-cutting file**: `org-state.json` (4 monitoring writers) — read by
every consumer as the freshness index (see aiw-ops-discipline §"Cross-agent
state-read pattern"). If `org-state.json` is >5 min stale, every agent has
been quiet — escalate to devops-monitor-30min before doing fresh probes.

**Eval file**: `eval-per-agent.json` — written by `aiw-eval-gate-runner-on-agent-run`
every hour. Read by ai-safety-engineer-30min and devops-monitor-30min. If
stale >2h, the eval-gate scoring engine is broken.

**The "failure-tolerant rollup"**: business-analyst is the only daily
consumer of *all* schemas. If business-analyst itself fails, the morning-brief
still ships because `cron-heartbeat-onhours` writes a degraded version with
just `org-state.json` + cron history.

---

## 4. Escalation graph

When an agent detects a fire, it lands in one of **three sinks** (Ivan,
Kanban, morning-brief). The level determines which sink.

```
                          ┌──────────────────────────┐
                          │  Ivan (founder/CEO)      │  ← final decision-maker
                          │  Telegram: direct page   │
                          └────────────▲─────────────┘
                                       │
        ┌──────────────────────────────┼──────────────────────────────┐
        │                              │                              │
┌───────┴──────────┐         ┌─────────┴──────────┐        ┌──────────┴────────┐
│ morning-brief    │         │ coord.json         │        │ Kanban board      │
│ 0 10 * * * (UTC) │         │ decisions_for_ivan │        │ HIGH / CRITICAL   │
│ /opt/data/build/ │         │ (read by analyst   │        │ auto-claim via    │
│ org.html         │         │  + Ivan)           │        │ gateway           │
└────▲─────────────┘         └────────▲────────────┘        └─────────▲────────┘
     │                                │                               │
     │ feeds                          │ writes                        │ writes
     │                                │                               │
┌────┴────────────────────┐  ┌────────┴────────────┐         ┌────────┴────────┐
│ cron-heartbeat-onhours   │  │ engineering-roster │         │ ai-ops-coord    │
│ cron-heartbeat-offhours  │  │ finance-controller │         │ bizops-tracker  │
│ (degraded mode)          │  │ sales-pipeline     │         │ compliance-monitor│
└──────────────────────────┘  │ research-tracker   │         │ founder-bandwidth │
                              │ business-analyst   │         └──────────────────┘
                              │ kiki-coach         │
                              │ people-hr          │
                              └────────────────────┘
```

### 4.1 Routing rules per level

The level is set by the agent at detection time. There are exactly four:

#### CRITICAL
**Definition**: data loss, payment failure, site down, secret leak, model
provider down for >2h, gateway 5xx sustained.

**Routing** (must do all three):
1. Write to `state/coord.json:decisions_for_ivan` with `priority: "critical"`.
2. Open a Kanban task on the relevant board with `priority: critical` and
   `auto_claim: true` (gateway claims it next tick).
3. Trigger `delivery=origin` directly to the morning-brief cron job's
   output channel via `hermes cron run morning-brief --mode=inject` (or
   the equivalent `coord.json` watcher).

**Latency target**: 5 min detection → 5 min page (Ivan's Telegram).

**Examples**:
- Sales pipeline detects `worker_post_probe.http == 500` for 2 consecutive ticks
- Security-watchdog finds `mode 600` violation on `.env*`
- Funding-coordinator sees `runway_months < 1.0`
- Devops-monitor sees gateway 8787 DEAD >3 ticks

#### HIGH
**Definition**: revenue-blocking, deadline imminent (<72h), blocked lead,
SLA breach imminent, single agent in error state >24h.

**Routing** (must do both):
1. Write to **own state's `open_questions`** with `priority: "high"`.
2. Raise a Kanban HIGH-priority task on the relevant board.

**Latency target**: 15 min detection → 15 min Kanban.

**Examples**:
- sales-pipeline: stalled deal >14d
- engineering-roster: stale repo >7d (deployment gate)
- research-tracker: thesis milestone slipped
- kiki-coach: 2 consecutive missed weekly runs

#### MEDIUM
**Definition**: process gap, stale repo, missing skill, schema drift,
single tick error with no clear cause.

**Routing** (one of):
1. Write to **own state's `open_questions`** with `priority: "medium"`,
   OR
2. Open a Kanban MEDIUM-priority task if cross-team action is needed.

**Latency target**: 4 h detection → caught by next morning-brief rollup.

**Examples**:
- cron-heartbeat-onhours: single tick miss
- ai-safety-engineer-30min: hard-stop drift
- coaching-quality-reviewer: Class-35 anchor >5h

#### LOW
**Definition**: cosmetic, nice-to-have, observability polish, doc drift.

**Routing**:
1. Append to **next weekly report** (e.g., aiw-coaching-quality-reviewer's
   weekly summary, or aiw-eval-trending's daily delta).

**Latency target**: weekly rollup.

**Examples**:
- dashboard colour tweak
- new skill added but not yet indexed in skills-audit-weekly
- trademark scan adding a new banlist token (carve-out audit)

### 4.2 Level transitions

- LOW → MEDIUM is automatic when the same finding repeats 3× (per
  coaching-quality-reviewer Class-19 saturation rule).
- MEDIUM → HIGH is automatic when an item appears on 3 consecutive
  morning-brief rollups without resolution.
- HIGH → CRITICAL is automatic at: revenue-blocking >72h, gateway down
  >2h, billing 402 across >5 jobs simultaneously.

---

## 5. Cron dependency graph (90 unique jobs)

Which jobs gate which. Drawn from the live `cron/jobs.json` (114 entries,
24 are dup/cancelled state from 2026-08-15 fix → 90 unique names).

### 5.1 The critical path (reads-only)

```
state-snapshot-6h (every 6h)
       │
       ▼
state-validate-15m (*/15m) ── checks 9 schemas + cron-heartbeat-alerts.log
       │
       ▼
cron-heartbeat-onhours (*/30m 7-21 UTC) ── writes state/heartbeat-alerts.json
cron-heartbeat-offhours (*/30m 22-6 UTC)
       │
       ▼
state-auto-commit (5 * * * *) ── git commits /opt/data/agents/state/*.json
       │
       ▼
morning-brief (0 10 * * *) ── reads all 9 state files + cron history
       │
       ├──▶ business-analyst (30 10 * * *) ── reads EVERYTHING, rolls up
       │           │
       │           └──▶ analysts.json:decisions[] ──▶ coord.json
       │
       ├──▶ sales-pipeline (0 13,16 * * *) ── reads sales + webhook-log
       ├──▶ engineering-roster (0 20 * * 2,5)
       ├──▶ kiki-coach-prep (Fri 16:30) ── writes kiki-prep.json
       │           └──▶ kiki-coach (Fri 21:00) ── reads kiki-prep.json
       ├──▶ management-coordinator (0 21 * * 1,4)
       ├──▶ finance-controller (0 21 * * 5)
       └──▶ research-tracker (0 21 * * 0)
```

### 5.2 The monitoring loop (always-on)

```
gateway.heartbeat
       │
       ▼
cron-heartbeat-onhours ─┐
       │                │
       ▼                ▼
aiw-state-validate-15m ◀── aiw-compact-errors (*/15m) ── writes state/errors.json
       │
       ├──▶ ai-safety-engineer-30min (*/30m) ─┐
       ├──▶ security-watchdog-30min (*/30m)   ├──▶ state/org-state.json
       ├──▶ devops-monitor-30min (*/30m)      ─┘
       └──▶ coaching-quality-reviewer (*/30m) ───▶ state/eval-per-agent.json
```

### 5.3 The 30-min monitoring cluster

These four write to `org-state.json` and are queried by every other agent
before doing their own probes (aiw-ops-discipline §"Cross-agent
state-read pattern"):

| Job | Cadence | Writes | Last live tick |
|-----|---------|--------|----------------|
| `aiw-devops-monitor-30min` | `*/30 * * * *` | `org-state.json` | 205 |
| `aiw-ai-safety-engineer-30min` | `*/30 * * * *` | `org-state.json` | 107 |
| `aiw-security-watchdog-30min` | `*/30 * * * *` | `org-state.json` | 80 |
| `aiw-coaching-quality-reviewer` | `*/30 * * * *` | `org-state.json` + `eval-per-agent.json` | 0300 |

### 5.4 Weekly / monthly rollups

| Job | Cadence | Output |
|-----|---------|--------|
| `aiw-ai-ops-coordinator-daily` | `0 8 * * *` | daily org-wide rollup |
| `aiw-eval-trending` | `0 6 * * *` | eval trend CSV |
| `aiw-eval-report` | `0 7 * * *` | daily eval report |
| `aiw-revops-pipeline-analyzer-daily` | `0 7 * * *` | sales funnel |
| `aiw-accounting-automation-daily` | `0 18 * * *` | finance book-keeping |
| `aiw-lead-enrichment-daily` | `30 9 * * *` | lead enrichment queue |
| `aiw-bizops-tracker-weekly` | `0 8 * * 1` | KPI rollup |
| `aiw-procurement-tracker-weekly` | `0 9 * * 1` | procurement report |
| `aiw-okr-tracker-weekly` | `0 8 * * 0` | OKR progress |
| `aiw-source-curator-weekly` | `0 13 * * 2` | source materials audit |
| `aiw-coaching-research-intelligence` | `0 13 * * 3` | coaching research |
| `aiw-coach-lead-finder` | `0 13 * * 3` | lead pipeline for coaches |
| `aiw-coaching-content-curator` | `0 14 * * 1` | content calendar |
| `aiw-qa-automation-on-pr` | `0 14 * * *` | PR QA |
| `aiw-security-audit-biweekly` | `0 14 * * 5` | security audit |
| `aiw-eval-gate-runner-on-agent-run` | `0 * * * *` | per-agent eval |
| `aiw-eval-per-agent` | `0 * * * *` | eval aggregation |
| `aiw-eval-auto-trigger` | `*/5 * * * *` | eval trigger |
| `aiw-engineering-roster-biwk` | `0 20 * * 2,5` | engineering state |
| `aiw-founder-bandwidth-watchdog-weekly` | `0 20 * * 0` | founder load |
| `aiw-management-coord-biwk` | `0 21 * * 1,4` | coord state |
| `aiw-finance-controller-weekly` | `0 21 * * 5` | finance state |
| `aiw-kiki-coach-weekly` | `0 21 * * 5` | kiki state |
| `aiw-coach-kiki` | `0 21 * * 5` | coach-kiki |
| `aiw-research-tracker-weekly` | `0 21 * * 0` | research state |
| `aiw-coach-ivan` | `0 21 * * 0` | coach-ivan |
| `aiw-people-hr-weekly` | `0 22 * * 1` | people state |
| `aiw-coach-lead-agents` | `0 22 1 * *` | monthly coaching-lead |
| `aiw-board-of-directors-quarterly` | `0 14 1 */3 *` | quarterly board brief |
| `aiw-coach-org` | `0 0 1 1,4,7,10 *` | quarterly coach-org |
| `aiw-coach-renewal-manager` | `0 9 1 * *` | monthly renewals |
| `aiw-tax-receipt-tracker-weekly` | `0 19 * * 0` | tax receipts |
| `aiw-funding-daily-check` | `0 */6 * * *` | funding pipeline |
| `aiw-funding-weekly-sweep` | `0 9 * * 1` | weekly funding sweep |
| `aiw-prompt-improvements` | `0 9 * * 1` | prompt-imp loop |
| `aiw-skills-audit-weekly` | `0 9 * * 1` | skills audit |
| `aiw-compliance-monitor-weekly` | `0 9 * * 1` | compliance |
| `aiw-citation-checker-on-demand` | `0 11 * * *` | citation audit |
| `aiw-proposal-drafter-on-demand` | `0 10 * * *` | proposal drafts |
| `aiw-drift-detector-weekly` | `0 12 * * 1` | schema drift |
| `aiw-chaos-test-runner-weekly` | `0 14 * * 1` | **OFF** — chaos drills |
| `aiw-coach-roi-tracker` | `0 16 * * 5` | coaching ROI |
| `aiw-thesis-tracker-daily` | `0 16 * * *` | thesis pipeline |
| `aiw-multimedia-producer-on-demand` | `0 15 * * *` | multimedia queue |
| `aiw-day-followup` | `0 9 * * *` | daily follow-ups |
| `aiw-course-producer-weekly` | `0 10 * * 0` | course production |
| `aiw-script-tests` | `0 4 * * *` | script smoke tests |
| `aiw-db-snapshot-daily` | `0 3 * * *` | SQLite snapshot |
| `aiw-backup-drill` | `0 5 1 * *` | monthly backup drill |
| `aiw-cost-monitor` | `0 */6 * * *` | cost tracking |
| `aiw-cost-alerts` | `0 */6 * * *` | cost alerts |
| `aiw-org-dashboard` | `0 8 * * *` | dashboard refresh |
| `aiw-admin-server-supervisor` | `*/5 * * * *` | admin supervisor |
| `aiw-agent-tracer` | `*/30 * * * *` | agent traces |
| `aiw-build-agent-context` | `0 * * * *` | build context |
| `aiw-build-org-state` | `0 * * * *` | build org state |
| `aiw-dashboard-refresh` | every 15m | dashboard HTML |
| `aiw-trademark-scan-cron` | ad-hoc | trademark banlist check |
| `aiw-coach-onboarding-poller` | `*/5 * * * *` | onboarding poller |
| `aiw-state-snapshot-6h` | `0 */6 * * *` | state snapshot |
| `aiw-state-validate-15m` | `*/15 * * * *` | state validate |
| `aiw-state-auto-commit` | `5 * * * *` | git auto-commit |
| `aiw-compact-errors` | `*/15 * * * *` | errors.json compact |
| `aiw-business-analyst-daily` | `30 10 * * *` | analyst |
| `aiw-sales-pipeline-daily` | `0 13,16 * * *` | sales |
| `aiw-marketing-content-mon-wed-fri` | `0 12 * * 1,3,5` | marketing |
| `aiw-revops-pipeline-analyzer-daily` | `0 7 * * *` | revops |
| `aiw-lead-enrichment-daily` | `30 9 * * *` | lead enrich |
| `aiw-accounting-automation-daily` | `0 18 * * *` | accounting |
| `aiw-finance-controller-weekly` | `0 21 * * 5` | finance |
| `aiw-engineering-roster-biwk` | `0 20 * * 2,5` | eng roster |
| `aiw-management-coord-biwk` | `0 21 * * 1,4` | coord |
| `aiw-kiki-coach-weekly` | `0 21 * * 5` | kiki |
| `aiw-research-tracker-weekly` | `0 21 * * 0` | research |
| `aiw-people-hr-weekly` | `0 22 * * 1` | people |

### 5.5 Infra-only jobs (no agent)

| Job | Cadence | Function |
|-----|---------|----------|
| `cron-sync` | every 5m | keeps `.hermes/cron/jobs.json` ↔ `/cron/jobs.json` in sync |
| `site-health` | every 15m | curl probe |
| `repo-ci-monitor` | `0 11 * * *` | GitHub Actions |
| `rbl-check` | `0 12 * * *` | trademark scrub |
| `evo-poll-watchdog` | every 5m | Evolution API |
| `thesis-daily-tick` | `0 6 * * *` | thesis tick |
| `thesis-watchdog` | every 15m | thesis watchdog |
| `thesis-weekly-review` | `0 18 * * 0` | thesis review |
| `thesis-git-maintenance` | `0 23 * * 0` | thesis git gc |
| `ometzdental-weekly-refresh` | `0 6 * * 1` | CF Worker update |
| `morning-brief` | `0 10 * * *` | (legacy brief writer) |
| `<mail-gateway-probe>` (job name reserved; see §1.6 carveout note) | every 60m | external IMAP mail gateway probe |
| `hermes-bridge-watchdog` | `*/5 * * * *` | bridge liveness |
| `mcp-health-check` | `15 */6 * * *` | MCP probe |
| `bws-cache-refresh` | `0 */6 * * *` | BWS cache |
| `kv-bws-sync` | `*/5 * * * *` | KV↔BWS |
| `linkedin-token-refresh` | `0 9 * * *` | OAuth |
| `<social-graph-oauth>` (job name reserved; see §1.6 carveout note) | `30 9 * * *` | OAuth refresh for social-graph tooling |

### 5.6 Critical-path rules

1. If `aiw-state-snapshot-6h` fails for >24h → rollback impossible. Alert CRITICAL.
2. If `cron-sync` fails for >15min → cron-config drift returns (the
   2026-08-13 outage). Alert HIGH.
3. If `aiw-state-validate-15m` fails → false-positive gate; downstream
   state reads may see invalid JSON. Alert HIGH.
4. If any of the 4 monitoring writers is silent >30min → page Ivan. Alert CRITICAL.
5. If `morning-brief` fails → fallback: `cron-heartbeat-onhours` ships a
   degraded brief; sales-pipeline brief substitutes.

---

## 6. Failure propagation table

"If X breaks, who breaks with it." Source-of-truth: `state/coord.json`
last_run = 2026-08-24, the canonical open_stuck list.

| # | Failure | First sign | Direct impact | Cascade | Detection latency |
|---|---------|-----------|---------------|---------|-------------------|
| 1 | **Cron-config drift** | jobs randomly succeeding/failing | all jobs | rollback impossible if snapshot-6h also stale | 15m (cron-heartbeat-onhours) |
| 2 | **State file corrupted** | dashboard render errors | business-analyst, morning-brief | every consumer reading that schema degrades | 15m (state-validate-15m) |
| 3 | **Gateway down (8787)** | no cron runs | all agents | every brief misses a tick; eval-per-agent stale | 30m (org-state freshness) |
| 4 | **LLM proxy 4xx/5xx** | single job error | depends on which job | weekly rollups missing → analyst goes silent on Sundays | 30m (org-state freshness) |
| 5 | **LiteLLM HTTP 402** | weekly cron jobs in error (Cerebras + Mistral) | 20+ jobs since 2026-08-21 (coord.json:open_stuck) | weekly rollups degrade to "no signal" — Ivan's Friday brief loses finance/kiki/research/research/chapters | 24h (per-job last_run) |
| 6 | **Kanban DB lock** | kanban writes fail | management-coordinator | HIGH/CRITICAL escalation routes to nowhere | 15m (coord job) |
| 7 | **Thesis-active venv broken** | thesis-tick error | research-tracker | research.json `thesis` field stale; coaching-research-intelligence downstream loses source | 15m (cron-heartbeat-onhours) |
| 8 | **GH CLI rate-limited** | analyst brief incomplete | business-analyst | github-driven stats in morning-brief go blank | 24h (per-job) |
| 9 | **CF Worker 522** | landing page probes 522 | sales-pipeline `landing_page_probe.bytes=118`, `evidence.landing_page_probe.detail="ExpiredRequest"` | `sales.json:open_questions: OQ-2026-08-22-B` cascades to Ivan | 30m (sales-pipeline cadence) |
| 10 | **BWS / KV sync fail** | bws-cache-refresh error | every secret-reading agent | webhook-signature verification fails; deploys block | 5m (kv-bws-sync */5m) |
| 11 | **MCP server down** | mcp-health-check shows 11/27 unhealthy | every agent using that toolset | tooling tier breaks; agent falls back to plain curl | 6h (mcp-health-check) |
| 12 | **Snapshot script broken** | aiw-state-snapshot-6h silent | rollback path gone | combined with state corruption → unrecoverable | 6h (per-job) |
| 13 | **Trademark banlist drift** | rbl-check fails | compliance-monitor | public copy may slip a banned term | 24h (rbl-check) |
| 14 | **Webhook URL unconfigured** | sales-pipeline `worker_mode: test` | sales.json `leads_in_flight` cannot be enriched | finance-controller `deals_open` stays stale | 30m (sales-pipeline) |
| 15 | **Eval-gate scorer broken** | eval-per-agent.json stops updating | ai-safety, coaching-quality-reviewer | hard-stop violations invisible; quality drift undetected | 1h (eval-gate-runner) |
| 16 | **Script path-guard regression** | aiw-state-validate-15m + cron-heartbeat-onhours blocked | heartbeat stale → silent failure | masks real outages (2026-08-24 incident) | 15m |
| 17 | **Funding pipeline stale** | aiw-funding-weekly-sweep 600s idle timeout | funding decisions unsupported | runway unknown if finance-controller also fails | 24h |
| 18 | **OAuth token expired** | social-graph token refresh / `linkedin-token-refresh` / `bws-cache-refresh` in error | downstream OAuth call 401 | outreach/social post failures | 24h |
| 19 | **Site-health log missing** | analyst falls back to direct curl | brief accurate but slow | 11d carry as of 2026-08-23 | 24h (analyst cadence) |
| 20 | **Heartbeat-alerts.log stale** | cron-heartbeat-alerts.log `12.5d stale` per analyst 2026-08-13 escalation | monitoring loop's log file is dead | cron errors invisible | 24h |

### 6.1 Cascade chains (most common multi-hop paths)

- **Gateway dead** → cron-heartbeat-onhours dead → state-validate-15m dead →
  morning-brief dead → business-analyst dead → every consumer (sales,
  finance, kiki, research, people, engineering) loses morning signal.
  **RTO**: 30 min from gateway restart.
- **LiteLLM 402** → 20+ weekly jobs dead → management-coordinator, finance-
  controller, kiki-coach, research-tracker, tax-receipt-tracker, people-hr
  all stale → morning-brief loses 5/7 lead-agent chapters. **RTO**: 60 min
  from credits top-up (model fallback chain may recover faster — see
  §6.2).
- **State corruption in `coord.json`** → business-analyst can't resolve
  "needs Ivan" → morning-brief loses escalation visibility. **RTO**:
  15 min from snapshot restore (file is small, <2 KB).
- **State corruption in `analyst.json`** → morning-brief loses business
  health, kpi_snapshot; management-coordinator's `decisions_for_ivan`
  review sees blanks. **RTO**: 30 min from snapshot restore.

### 6.2 Recovery via model fallback (per aiw-ops-discipline §"Cron-self-failure recovery")

If a job fails because its primary model is unavailable, the LiteLLM
fallback chain is: `litellm/primary → litellm/reasoning → litellm/fast →
external/<provider>`. This is automatic for cron jobs that have
`provider=custom:litellm` in their config.

A "recovered via fallback" run must still be reported as a partial
self-failure — the previous run's gap exists.

---

## 7. Onboarding a new agent

Checklist (must pass before adding to production cron):

- [ ] PROMPT.md exists under `/opt/data/agents/<name>/`
- [ ] State file path decided; JSON Schema written under `/opt/data/agents/schemas/<name>.schema.json`
- [ ] `validate-state.py` returns OK on initial seed
- [ ] Cron job created with `provider=custom:litellm model=primary` (see TIER3-UPGRADE-REPORT §1, lesson from 2026-08-13 model drift)
- [ ] `enabled_toolsets` set per profile (see TIER3-UPGRADE-REPORT §1)
- [ ] Output contract followed (outbox file, 150-300 words, no emoji headlines)
- [ ] At least one row added to this matrix's §1 + §3
- [ ] Rollback path: snapshot of initial state lives in `/opt/data/agents/state/history/snapshots/`
- [ ] Health check: `health.sh` extended to include the new agent
- [ ] Trademark scan clean: `python3 /opt/data/scripts/trademark-scan.py /opt/data/agents/<name>/PROMPT.md`
- [ ] Cross-agent state-read pattern documented (which siblings to read before probing — see aiw-ops-discipline)

---

## 8. Cross-references

- Source-of-truth config: `/opt/data/.hermes/config.yaml`
- Cron jobs: `/opt/data/.hermes/cron/jobs.json` (canonical) ↔ `/opt/data/cron/jobs.json` (gateway-read)
- State schemas: `/opt/data/agents/schemas/`
- State files: `/opt/data/agents/state/`
- Org-state freshness index: `/opt/data/state/org-state.json`
- Validators: `/opt/data/agents/scripts/validate-state.py`, `/opt/data/scripts/cron-heartbeat-check.sh`
- Snapshot history: `/opt/data/agents/state/history/` and `/opt/data/agents/state/snapshots/`
- Dashboard: `/opt/data/agents/dashboards/org.html`
- Per-phase rollback (legacy): `/opt/data/agents-v2/ROLLBACK-PLAYBOOK.md`
- Modern operational rollback (per-state / per-cron / per-deploy): `/opt/data/agents/ROLLBACK-PLAYBOOK.md`
- Companion skill: `aiw-ops-discipline` (cross-agent state-read pattern, cron-self-failure recovery, validation-before-completion)
- Companion skill: `factor-9-compact-errors` (state/errors.json structure, eval-gate trend detection)

---

## Repository renamed (2026-08-31)

This repository has been renamed for clarity:

| Old URL | New URL | Why |
|---|---|---|
| `github.com/Ai-Whisperers/agents-v2` | [`github.com/Ai-Whisperers/growth-coaching`](https://github.com/Ai-Whisperers/growth-coaching) | This repo is the **product** (the customer-facing GROW coaching platform). The old name "agents-v2" was meaningless to outsiders; "growth-coaching" describes what the product actually does. |
| `github.com/Ai-Whisperers/agents` | [`github.com/Ai-Whisperers/agent-infra`](https://github.com/Ai-Whisperers/agent-infra) | This repo is the **infrastructure** (agent specs, runtime state, governance docs, outbox history). The old name "agents" was too generic; "agent-infra" makes the purpose clear. |

GitHub redirects the old URLs automatically, so any links from docs/issues/PRs still work — they just forward to the new location.

### Quick reference

- **Product** (coaching service, GROW methodology, customer tiers, marketing): [`Ai-Whisperers/growth-coaching`](https://github.com/Ai-Whisperers/growth-coaching) (this repo)
- **Infrastructure** (agent PROMPTs, runtime state, governance, decisions): [`Ai-Whisperers/agent-infra`](https://github.com/Ai-Whisperers/agent-infra)


---

## Agent Naming Convention (v2 — portmanteau)

All agents follow the **portmanteau naming framework**:
```
[Domain Root] + [Personal Suffix] = [Functional Identity]
```

Examples: **Saleina** (sales-pipeline), **Devin** (engineering-roster), **Finus** (finance-controller), **Safina** (ai-safety-engineer), **Herina** (people-hr), **Scopia** (scope-intake), **Gatina** (feasibility-gate), **Chaosia** (chaos-test-runner).

Full reference: `/opt/data/scratchpad/analysis/AGENT-NAMES-V2.md` (canonical, 54 agents)
Machine-readable: `/opt/data/scratchpad/analysis/AGENT-NAMES-V2.json`

The older Spanish-surname names (Hernán Coordinador, Sofía Vendedora, etc.) from `AGENT-HUMAN-NAMES.md` are still valid as informal alternatives.
