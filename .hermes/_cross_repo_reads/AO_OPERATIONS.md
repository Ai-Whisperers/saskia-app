# AI Whisperers Org — Operational Runbook

> **How the whole org works end-to-end.** Read this to understand the system.
> **Audience**: Ivan, Kiki, new operators, future FTE hires, and any agent that needs to understand its environment.
> **Last updated**: 2026-09-01 (after Phase 8).

---

## 1. The org in one paragraph

AI Whisperers Paraguay EAS is a **2-person co-founder org** (Ivan + Kiki) that runs a **layered agent organization** on top of Hermes Agent + cron. Agents are organized into **6 charter departments + 1 board**, with per-agent PROMPT.md + PROMPT-monitor.md files, state under `/opt/data/state/` and `/opt/data/agents/state/`, and output in per-agent `outbox/` directories.

> **Canonical fleet counts (R5, Decision C1)**: the live cron numbers come from the `aiw-dashboard-refresh` job output — **as of its 2026-09-25 18:15 UTC run: 161 jobs in Domain A** (`/opt/data/cron/`, 108 enabled scripts) **+ 97 jobs in Domain B** (ivan profile, 8 enabled). Do not hand-edit counts here; cite the job output with its date. The "63 agents / 167 cron jobs" figures below are historical (pre-2026-09-21 fleet rework) and kept only in older sections for provenance.

---

## 2. The 5-layer model

The org follows a **5-layer methodology** (L1 hygiene → L5 soul-improvement), where each layer enables the next:

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 5: Adaptive (Soul-Improvement) — DEFERRED per gate    │
├─────────────────────────────────────────────────────────────┤
│ Layer 4: Adaptive (Self-run Org) — DEFERRED per gate        │
├─────────────────────────────────────────────────────────────┤
│ Layer 3: Quality (Drift, Chaos, Eval Gates, Hard-stops)     │
│   Phase 5: 4 PROMPTs built. Phase 8: eval-aggregate script │
├─────────────────────────────────────────────────────────────┤
│ Layer 2: Foundation (PROMPT.md, State, Monitors)            │
│   Phase 5: 100% setup parity. Phase 6: 18 crons wired.     │
├─────────────────────────────────────────────────────────────┤
│ Layer 1: Hygiene (Lint, Smoke, Cron-sync) — 100% pass       │
└─────────────────────────────────────────────────────────────┘
```

### Layer definitions

| Layer | What it ensures | Phase | Status |
|---|---|---|---|
| **L1 Hygiene** | Lint, smoke, cron-sync, gitignore correctness | L1 audit complete (Aug 2026) | ✅ 100% |
| **L2 Foundation** | Every agent has PROMPT.md, state schema, monitor wiring | Phase 5 | ✅ 100% |
| **L3 Quality** | Drift detection, chaos testing, eval gates, hard-stops | Phase 5 (PROMPTs) + Phase 8 (script) | 🟡 Partial |
| **L4 Self-run Org** | Org runs itself without daily operator input | Deferred (per gate) | ⏸️ |
| **L5 Soul-Improvement** | Org improves its own behavior over time | Deferred (per gate) | ⏸️ |

**Why L4 is deferred**: The L4 gate requires $1000+ MRR OR 30 days of L1-L3 stability. We're at $240 MRR + 0d stability. Per doctrine: don't unlock L4 until triggers fire.

**Why L5 is deferred**: L5 builds on L4. Same doctrine applies.

---

## 3. The agent hierarchy

### Tier 1 — Charter departments (6 + 1)

| Tier-1 dept | Lead agent | Reports to |
|---|---|---|
| 01-operations | `management-coordinator` | board-of-directors |
| 02-finance-legal | `finance-controller` | board-of-directors |
| 03-sales-growth | `sales-pipeline` | board-of-directors |
| 04-engineering | `engineering-roster` | board-of-directors + Kiki (co-chair) |
| 05-research-education | `research-tracker` | board-of-directors |
| 06-people-culture | `people-hr` | board-of-directors |
| board-of-directors | (self) | — |

### Tier 2 — Department sub-agents (39)

Each Tier-1 lead has Tier-2 sub-agents that specialize. Examples:
- `04-engineering/engineering-roster/` is the lead → sub-agents: `ai-safety-engineer`, `devops-monitor`, `qa-automation-runner`, `security-watchdog`, `chaos-test-runner`, `drift-detector`, `eval-gate-runner`, `deliver-tracker`, `security-auditor`, `qa-automation-on-pr`, + 2 cadence variants

### Tier 3 — Cross-cutting + Deferred

- **Active**: `compliance-monitor` (01), `procurement-tracker` (01), `source-curator` (01)
- **Deferred (per doctrine)**: Chief of Staff, Trust & Safety, DevRel, IR, Workplace Manager, Fraud/Risk, Treasury, Internal Audit, Workplace Ops, DEI Specialist, Public Relations, Government Relations, + 5 enterprise (Internal Comms, M&A, CDO, CAIO, D&I Lead)

### Tier 4 — DEMIURGE atomic layer (24 souls)

DEMIURGE = canonical atomic-layer agents. Greek-mythology names. Live in `demiurge/agents/`. They are **reusable across the org** (one cadmus for sales, another for ops if needed). Examples: `apollo` (search), `cadmus` (lead enrichment), `metis` (proposal drafting), `hecate` (router).

### Tier 5 — Sister repo

- `coach-agents/` (sister repo) contains `kiki-coach`, `coach-lead-finder`, `coach-onboarding-poller` — coaching-product agents that interact with the Growth-Coaching product.

---

## 4. The state system

### Two-tier state path layout

```
/opt/data/state/                      ← eval/cron/webhook state (live, written by cron)
/opt/data/agents/state/               ← dept state (live, written by dept agents)
/opt/data/state-versioned/            ← hourly snapshots (git-tracked)
```

**Why split?** Cron jobs run in the gateway context and have access to `/opt/data/state/`. Dept agents run in the agent context and write to `/opt/data/agents/state/`. Both locations are kept in sync via the `state-versioned-push` cron (hourly).

### State-write discipline (7 patterns)

Per `engineering/state-write-discipline-catalog.md`:

| Pattern | Rule |
|---|---|
| **P1** | `additionalProperties: false` in JSON schema |
| **P2** | Atomic write with `.tmp` + rename + `.bak` |
| **P3** | Monitor notes in separate `monitor-notes/{agent}-{date}.md` files |
| **P4** | Combine P1 (strict) + P5 (rolling archive) |
| **P5** | Rolling archive via `aiw-state-roll` cron (30d retention) |
| **P6** | Every state file has `last_updated_at` + `version` fields |
| **P7** | Hourly snapshot to `Ai-Whisperers/state-versioned` repo |

### Critical state files

| File | Owner | Schema |
|---|---|---|
| `coord.json` | management-coordinator | strict, versioned |
| `finance.json` | finance-controller | strict, versioned |
| `sales.json` | sales-pipeline | strict, versioned |
| `engineering.json` | engineering-roster | strict, versioned |
| `research.json` | research-tracker | strict, versioned |
| `people.json` | people-hr | strict, versioned (currently `last_run: null`) |
| `funding.json` | funding-coordinator | strict, versioned |
| `kiki.json` + `kiki-prep.json` | people-hr | strict, versioned |
| `cron-error-watchdog.json` | cron-error-watchdog | strict, rolling |
| `eval-per-agent.json` | eval-gate-runner | `{by_agent: {...}}` |
| `eval-trending.json` | eval-aggregate-pass-rate.py (Phase 8) | aggregate metrics |

---

## 5. The cron system

### 131 cron jobs

Total: **131** (after Phase 6 wired the 18 missing sub-agent monitors).

Distribution by category:

| Category | Approximate count | Notes |
|---|---:|---|
| Heartbeat (on-hours/off-hours) | 2 | `*/30` on, `*/15` off |
| Dept-lead monitors (7) | 7 | `weekly` cadence mostly |
| Sub-agent monitors (28) | 28 | Phase 6 wired |
| Weekly dept reviews | 21 | `0 X * * 0` patterns |
| Daily variants | 6 | `-daily` dirs |
| On-demand variants | 3 | `-on-demand` dirs |
| 30min variants | 4 | `-30min` dirs |
| Management / infra | 60+ | `cron-sync`, `state-roll`, `versioned-push`, etc. |

### Cron sync invariant

`/opt/data/cron/jobs.json` ↔ `/opt/data/.hermes/cron/jobs.json`. The pre-commit `cron-guard` hook blocks on drift — `bash /opt/data/scripts/cron-sync.sh` resolves it.

### Cron health

Per `state/cron-error-watchdog.json` (snapshot 2026-08-31 21:38 UTC):
- **6 jobs in error** out of 131
- 5 = HTTP 429 (token-plan exhaustion on Sunday-evening weekly stack)
- 1 = `Unknown provider 'minimax-plan'` (config drift)

**Fix**: spread Sunday-evening weekly crons; correct provider name.

---

## 6. The monitor system

### PROMPT-monitor.md pattern

Every monitored agent has:
- `PROMPT.md` — what the agent does
- `PROMPT-monitor.md` — threshold rules for the monitor to check
- `monitor-notes/{date}.md` — log of past ticks (P3 pattern)
- `outbox/` — output sink

The monitor cron prompt says: **"Read `<path>/PROMPT-monitor.md` for full threshold rules."** The PROMPT-monitor.md is the source of truth.

### Current coverage

- **35 PROMPT-monitor.md files** (one per monitored agent)
- **28 of 28 sub-agents monitored** (100%)
- **7 of 7 dept-leads monitored** (100%)

### Threshold calibration

80% of thresholds are educated guesses (educated-guess Phase 5 default). Calibration plan: 30d of real data → empirical thresholds. See `operations/monitor-threshold-calibration-2026.md`.

---

## 7. The KPI / signal system

### Per-dept KPI stacks (7)

Each dept has a `demiurge/kpi/{dept}-stack.yaml` file. These are the KPIs the dept should track. Some are populated automatically; others require cron wiring.

### Per-dept signal routes (7)

Each dept has a `demiurge/signals/{dept}.yaml` file. These define what signals flow to the dept-lead's monitor.

### Status

- All 7 KPI stacks exist (Phase 5 R1 added `sales-stack.yaml` + `board-stack.yaml`).
- All 7 signal routes exist.
- Data population is partial (some depts have never fired).

---

## 8. The research system

### Per-dept research catalogs (7)

Per `research/dept-research/`, each dept has a catalog of research areas:
- `01-operations-research-areas.md` (6 areas)
- `02-finance-legal-research-areas.md` (8 areas)
- `03-sales-growth-research-areas.md` (10 areas)
- `04-engineering-research-areas.md` (10 areas)
- `05-research-education-research-areas.md` (8 areas)
- `06-people-culture-research-areas.md` (6 areas)
- `board-of-directors-research-areas.md` (4 areas)
- **Total: 52 research areas**

### Methodology

Per `research/DEPT-RESEARCH-METHODOLOGY.md`:
- Each research area answers the **7 questions**: Question / Why / Method / Output / Owner / Cadence / Cross-references
- Cadence tier: 🔴 HOT / 🟡 WARM / 🔵 COOL
- 4 depth levels: enumerate / analyze / synthesize / recommend

### Phase 8 execution

**30 of 52 areas autonomously executed**. 20 areas need Ivan/Kiki input (correctly deferred).

---

## 9. The demo/deploy system

### Scripts (36 production scripts in `scripts/`)

Critical scripts:
- `cron-sync.sh` — sync gateway → canonical
- `smoke-test.sh` — L1-L4 gates
- `lint-prompts.py` — frontmatter validation
- `eval-aggregate-pass-rate.py` (NEW Phase 8) — eval aggregate metric
- `chaos-test-runner.py` — chaos scenarios
- `state-validate.py` — schema validation
- `state-write.sh` — atomic write wrapper
- `cron-heartbeat-onhours.sh` / `-offhours.sh` — heartbeats

### Tests (38 test files, 278 tests)

- All 278 pass (canonical gate)
- New `tests/test_eval_aggregate.py` (Phase 8) — 6 tests for the eval aggregate script
- `tests/test_agent_composition.py` (Phase 8) — 7 tests for crosscut agents
- Pre-commit runs lint + smoke + tests

### Pre-commit hooks

- `lint-prompts.py` (63 PROMPTs)
- `smoke-test.sh all` (4 layers, ~9s)
- `cron-guard` (prevents cron drift)
- `state-validate.py` (schema correctness)

---

## 10. Decision-making

### The decision rights matrix

Per `constitution/ORG-AGENTS.md`:

| USD impact | Decision rights |
|---|---|
| < $50 | Logged (auto) |
| $50 - $500 | Surfaced for next-day review |
| $500 - $5K | Ivan decides |
| > $5K | Ivan + Kiki co-decide |

### Co-chair model (per Phase 8 R2)

Ivan + Kiki are co-chairs of board-of-directors. Per `board/co-chair-decision-rights.md`, we recommend **M4 — time-bounded consensus**:
1. Within 24h: each chair writes a 1-page position
2. Within 48h: joint discussion
3. Tiebreaker: rotates monthly

### Pending decisions (Phase 8 surfaced)

| Decision | Owner | Recommendation |
|---|---|---|
| Sales funnel fix (Formspree vs Worker revival) | Ivan | **Formspree** (1-2h vs 8-16h) |
| Hard-stops wrapper invocation | Kiki | Phase 8 #2 audit ready |
| Decline richar-ruiz deal | Ivan | **YES** (22d stalled, anonymized) |
| Resurrect Rubicon EAS Worker | Ivan | **LATER** (after $5K MRR) |
| `minimax-plan` provider name fix | ai-ops-coordinator | trivial fix |

---

## 11. The deferred roles doctrine

### What "deferred" means

Per `DEFERRED-ROLES.md` and `DEFERRED-AGENTS.md`, Tier-3 and Tier-4 roles are NOT built until **explicit triggers fire**.

### Triggers (examples)

| Role | Trigger |
|---|---|
| Customer Success | 5+ active clients |
| Investor Relations | Pre-seed round + 1+ investor intro |
| Chief of Staff | 5+ FTE hires (so 1+ FTE is required) |
| Trust & Safety | User-generated content + 1000+ users |
| DevRel | OSS repo + 100+ stars |
| Workplace Manager | Office lease + 5+ employees |
| Fraud/Risk | Payment processing + $10K+/mo |
| Treasury Manager | Cash > $100K |
| Internal Audit | SOC2 / ISO27001 pursuit |
| Workplace Operations | Same as Workplace Manager |
| DEI Specialist | 10+ employees |
| Public Relations | Public-facing flagship launch |
| Government Relations | EU AI Act compliance work |

**Tier-4 enterprise**: Internal Comms, M&A, CDO, CAIO, D&I Lead — require $1M+ revenue.

### Why the doctrine matters

Building a Tier-3 dept before its trigger:
1. Wastes engineering time (the agent does nothing)
2. Creates dead code (PROMPT.md that no cron invokes)
3. Confuses the org (operators wonder who owns the area)
4. Doesn't actually help (the trigger is what creates the work)

**Better**: research the area (so we know what to do when the trigger fires) but don't build the agent.

---

## 12. The feedback loop

### How we improve

Every phase produces a **feedback doc** in `analysis/`:
- `PHASE-1-L1-AUTONOMOUS-PRECHECKS-FEEDBACK.md`
- `PHASE-2-FOUNDATION-FEEDBACK.md`
- `PHASE-3-QUALITY-FEEDBACK.md`
- `PHASE-4-ADAPTIVE-FEEDBACK.md` (deferred)
- `PHASE-5-COMPLETION-REPORT.md`
- `PHASE-6-REFINEMENT-FEEDBACK.md`
- `PHASE-7-RESEARCH-FEEDBACK.md`
- `PHASE-8-FEEDBACK.md`

Each feedback doc captures:
1. What was planned
2. What worked (templates, patterns)
3. What didn't (mistakes, gaps)
4. Pattern updates for next iteration
5. Time spent
6. Numeric delta

### Time spent on improvements

Per phase: ~30 min feedback doc + 5-15 min atomic commits. The total feedback loop is ~2-3% of execution time, but yields disproportionately better future phases.

---

## 13. The commit-and-sync rhythm

### Commit cadence

- **Atomic commits** — one logical change per commit
- **Granular messages** — what + why + delta
- **Weekly summaries** — phase-level rollup
- **Layer reports** — at each phase boundary

### Pre-commit sequence

```bash
# 1. Cron sync (resolve drift)
bash /opt/data/scripts/cron-sync.sh

# 2. Lint (validate PROMPTs)
/opt/data/.venv/bin/python3 scripts/lint-prompts.py

# 3. Smoke (validate gates)
./scripts/smoke-test.sh all

# 4. Tests
/opt/data/.venv/bin/python3 -m pytest tests/

# 5. Commit
git add .
git commit -F /tmp/commit-msg.txt

# 6. Push (BWS-auth'd)
/opt/data/.venv/bin/python3 scripts/push.py  # or manual token + gh
```

**Pre-commit hooks automate steps 1-3.** Steps 4-6 are manual but quick.

### Cron-guard hook

If `/opt/data/cron/jobs.json` ≠ `/opt/data/.hermes/cron/jobs.json`, pre-commit **fails**. Fix with `bash /opt/data/scripts/cron-sync.sh`.

---

## 14. The "is it working?" check

### Quick health check (60 seconds)

```bash
# 1. Smoke gate
./scripts/smoke-test.sh all  # expect: 100% pass, 9s

# 2. Cron health
cat /opt/data/state/cron-error-watchdog.json | python3 -m json.tool | head -20

# 3. Eval aggregate
/opt/data/.venv/bin/python3 scripts/eval-aggregate-pass-rate.py

# 4. Drift
ls /opt/data/state/drift-alerts.json  # exists? recent?
```

### Red flags

| Symptom | Likely cause |
|---|---|
| Smoke gate fails | Pre-commit hook will block. Read the output. |
| Cron errors > 5% | Sunday-evening token-plan exhaustion. Spread crons. |
| Eval aggregate pass_rate < 0.5 | Eval system not populating. Investigate. |
| Drift alerts firing daily | Threshold too sensitive. Calibrate. |
| Health dashboard score < 60 for any dept | Cross-reference `operations/health-dashboard.md` |

---

## 15. How a new operator gets oriented

**Day 1**:
1. Read this file (OPERATIONS.md) — top to bottom
2. Read `department-index.md` — understand what's where
3. Skim `analysis/PHASE-5-COMPLETION-REPORT.md` — see where we are
4. Read `ON-CALL.md` — know what to do when X breaks
5. Read `DEFERRED-ROLES.md` — know what NOT to build

**Day 2**:
1. Read `constitution/ORG-AGENTS.md` (skim — it's long)
2. Read `analysis/DEPT-AGENTS-ROLES-COMPLETE.md` (skim)
3. Pick ONE dept to deep-dive (their charter, their PROMPTs, their state, their research)
4. Run smoke gate + verify it works

**Day 3+**:
1. Pick a research area (🔴 HOT first) from `research/dept-research/`
2. Execute it (write the artifact, run the script, document)
3. Add a feedback note in the dept's research area doc

---

## 16. The doc inventory

| Document | Purpose | Read order |
|---|---|---|
| `README.md` | Top-level orientation | 1 |
| `OPERATIONS.md` (this file) | How it all works | 2 |
| `department-index.md` | Per-dept file map | 3 |
| `ON-CALL.md` | What to do when broken | 4 |
| `REVIEW-2026-Q4.md` | Current quarter + Phase 26 | 5 |
| `ORG-AGENTS.md` | Full agent matrix | 6 (reference) |
| `analysis/DEPT-AGENTS-ROLES-COMPLETE.md` | 135-role inventory | 7 (reference) |
| `analysis/PHASE-*-FEEDBACK.md` | Phase feedback loops | 8 (background) |
| `research/DEPT-RESEARCH-METHODOLOGY.md` | Research methodology | 9 (when doing research) |
| `dept-monitors/INDEX.md` | 35 monitor patterns | 10 (reference) |

---

## 17. Glossary

| Term | Definition |
|---|---|
| **Agent** | A LLM-driven program with a `PROMPT.md` that defines its role |
| **Monitor** | A specialized agent that watches other agents' state + alerts on threshold violations |
| **Cron job** | A scheduled LLM call (Hermes + agent prompt + state check) |
| **State** | JSON files at `/opt/data/state/` and `/opt/data/agents/state/` |
| **Schema** | JSON schema with `additionalProperties: false` (P1 pattern) |
| **Outbox** | Per-agent output directory; cron jobs write here |
| **Cadence** | How often a cron fires (`weekly`, `daily`, `30min`, etc.) |
| **Tier-1/2/3/4** | Agent hierarchy levels (charter → cross-cut → deferred → DEMIURGE) |
| **Hermetic pattern** | Self-contained unit (monitor = PROMPT-monitor.md + cron) |
| **L1/L2/L3/L4/L5** | The 5-layer methodology (hygiene → soul-improvement) |
| **L4 gate** | $1000+ MRR OR 30d L1-L3 stability (must fire to unlock L4) |

---

## 18. The future (Phase 26+ candidates)

From `engineering/phase-25-revisit-2026.md`:

1. **Drift detection calibration** (run for 30d, calibrate thresholds)
2. **Eval aggregate cron wiring** (run nightly)
3. **Chaos test first run** (Scenario #1: state corruption)
4. **Hard-stops wrapper enforcement** (Kiki decision + 16h implementation)
5. **Eval gate enforcement** (block low-pass agents)
6. **Heartbeat self-validation** (heartbeat of the heartbeat)
7. **Cost reporting per cron** (visibility into $6/day heartbeat cost)

**From Phase 8 R3 (sales revival)**:
8. **Sales funnel revival** (Formspree in 1-2h vs Worker revival 8-16h)

**From Phase 8 R2 (risk register)**:
9. **Sales: Ivan decide Formspree vs Worker revival** (URGENT)
10. **AI safety: Kiki decide hard-stops enforcement** (HIGH)

---

**TL;DR**: The org is 49 agents + 131 cron jobs + ~50 state files, organized into 6 charter depts + 1 board, monitored by 35 PROMPT-monitor.md files, and documented in 52 research areas across 7 dept catalogs. L1-L2 is 100% complete; L3 is partial; L4-L5 are deferred per gate. Read [department-index.md](department-index.md) for what's where, [meetings/department-design/README.md](meetings/department-design/README.md) for design-meeting decisions, and [ON-CALL.md](ON-CALL.md) for what to do when X breaks.
