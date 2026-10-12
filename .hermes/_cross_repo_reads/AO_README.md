# AI Whisperers — Internal Org Layer (`aiw-org`)

> **This repo is the internal AI Whisperers organization layer.**
> It contains the people, departments, agents, and tooling that run AIW day-to-day.
> It is **not** the customer-facing coaching product — that lives in
> [`Ai-Whisperers/growth-coaching`](https://github.com/Ai-Whisperers/growth-coaching).

> **Source-of-truth (live)**: `/opt/data/agents/` (canonical), `/opt/data/state/` (live state), `/opt/data/.hermes/cron/jobs.json` (cron registry).
> **Source-of-truth (design meetings)**: [`meetings/department-design/README.md`](meetings/department-design/README.md) (department-design decisions).
> **Build conventions**: [`AGENTS.md`](AGENTS.md) (authoritative for all coding agents).

---

## What this repo is — at a glance (2026-09-01 snapshot)

All numbers verified against live state on 2026-09-01 via `find`/`grep` + `BASELINE-COVERAGE-2026-09-01.json`.

| Metric | Count | Where to find |
|---|---:|---|
| Tier-1 charter departments | 7 (6 + board) | `01..06-*/`, `board-of-directors/` |
| Atomic DEMIURGE agents | 28 | `demiurge/agents/` |
| Department sub-agents (Tier-2/Tier-3) | 46 | `0?-*/<agent>/PROMPT.md` |
| **PROMPT.md files (all agents)** | **116** | 45 dept + 30 DEMIURGE + 1 board + 40 hermetic CI fixtures (incl. 7 explicit stubs from DEMIURGE-095) |
| **PROMPT-monitor.md files** | **71** | one per monitored agent |
| **Cron jobs (heartbeat)** | **156** | `/opt/data/.hermes/cron/jobs.json` (254 total, 156 enabled; AI-free — all pure code since 2026-09-19) |
| KPI stacks (per dept) | 8 | `demiurge/kpi/*-stack.yaml` |
| Signal routes (per dept) | 7 | `demiurge/signals/*.yaml` |
| State files (live + versioned) | 86+ | `state/`, `/opt/data/state/`, `/opt/data/state-versioned/` |
| Research catalogs (per dept) | 7 | `research/dept-research/{01..06,board}-research-areas.md` |
| Research areas documented | **52** | per `DEPT-RESEARCH-METHODOLOGY.md` (6+8+10+10+8+6+4) |
| Research areas executed | 30+ | Phase 8 + ongoing Phase 9 |
| **Tests** | **66 pass** | `tests/` (44 test files, per `BASELINE-COVERAGE-2026-09-01.json`) |
| **Scripts (production)** | **97** | `scripts/` (incl. chaos-runner, token-ledger, eval-gate, cost-per-cron) |
| Smoke gate | 100% pass, **~2.2s** | `scripts/smoke-test.sh all` |
| Lint | 63/63 pass | `scripts/lint-prompts.py` |
| DEMIURGE tickets | 309 files | `tickets/DEMIURGE-*/` |
| **Live daily burn (LLM)** | **$93.61** | `state/cost-per-cron.json` (49/168 matched) |
| Live budget ceiling (24h, uncalibrated) | 50k credits | `DEFAULT_BUDGET_24H` in `/opt/data/agents/scripts/token-ledger.py:13` |
| Providers in fleet | 70× MiniMax-M3 + 58× litellm (incl. GLM) + 40 broken | `jobs.json` |

**Active phases**: 9 R-series close-out, plus ongoing phases 26-36 documented in `analysis/PHASE-2X-FEEDBACK.md`. Latest handoff: `analysis/PHASE-9-R10-handoff.md` → `docs/HANDOFF-PHASE-8.md` (historical anchor).

---

## What is NOT in this repo

| Concern | Where it lives | Why |
|---|---|---|
| GROW coaching product for paying customers | `Ai-Whisperers/growth-coaching` | Different audience (customers), different lifecycle (releases), different access control |
| The `packages/coaching/` distributable package | `Ai-Whisperers/growth-coaching` | Product code, not org code |
| DEMIURGE research / source catalog | `Ai-Whisperers/growth-coaching` | Framework + research belongs with the product that uses it |
| `kiki-coach`, `coach-lead-finder`, `coach-onboarding-poller` | `Ai-Whisperers/coach-agents` (sister repo) | Coaching-product agents that interact with the GROW product |
| Customer data | (not in repo at all — runs at runtime in `/opt/data/state/`) | PII must never leak into the org-as-code artifact |
| Live agent state | `/opt/data/state/` + `/opt/data/agents/state/` | Written by cron at runtime; mirrored to `state-versioned` repo hourly |
| BWS secrets | `/opt/data/.hermes/bws-secrets-cache.tsv` | Bitwarden-backed credentials cache (loaded from `/opt/data/scripts/`) |

---

## Quick links (in reading order for new operators)

### Start here

- **[AGENTS.md](AGENTS.md)** — authoritative collaboration rulebook for ALL coding agents (read first)
- **[README.md](README.md)** — this file (orientation)
- **[OPERATIONS.md](OPERATIONS.md)** — how the whole org works end-to-end
- **[department-index.md](department-index.md)** — per-dept overview (agents, monitors, research, KPIs, signals, executed artifacts)
- **[ON-CALL.md](ON-CALL.md)** — what to do when X breaks

### Org / governance

- **[REVIEW-2026-Q4.md](REVIEW-2026-Q4.md)** — current quarter review + Phase 26 candidates
- **[DECISIONS-2026-Q3.md](DECISIONS-2026-Q3.md)** — Q3 decision log
- **[ORCHESTRATION.md](ORCHESTRATION.md)** — orchestration patterns (⚠ dated 2026-08-13, scheduled for Phase 9 R4 rewrite)
- **[ORG-AGENTS.md](ORG-AGENTS.md)** — full 63-agent handoff matrix + producer→consumer
- **[constitution/DEFERRED-ROLES.md](constitution/DEFERRED-ROLES.md)** + **[constitution/DEFERRED-AGENTS.md](constitution/DEFERRED-AGENTS.md)** — roles/agents NOT yet built

### Departments (charters + directories)

- **[departments/](departments/)** — 4 dept charter files (03-06) + `NEXA-DEPARTMENT-SETUP-PLAN.md` + `archive/`
- **Tier-1 charters (live)**: `01-operations/`, `02-finance-legal/`, `03-sales-growth/`, `04-engineering/`, `05-research-education/`, `06-people-culture/`, `board-of-directors/`

### Research

- **[research/](research/)** — research areas + methodology + cross-dept research catalogs + new token-efficiency work
- **[research/dept-research/](research/dept-research/)** — 7 per-dept research catalogs (52 areas total)
- **[research/DEPT-RESEARCH-METHODOLOGY.md](research/DEPT-RESEARCH-METHODOLOGY.md)** — 7-question pattern + 4 depth levels
- **[research/token-efficiency-minimax-glm-2026-09-01.md](research/token-efficiency-minimax-glm-2026-09-01.md)** — Level 3 synthesis: token cost reduction across MiniMax + GLM fleet (just merged, 2026-09-01)

### Operations / monitoring

- **[dept-monitors/INDEX.md](dept-monitors/INDEX.md)** — 16 monitor pattern matrix (master reference)
- **[demiurge/](demiurge/)** — DEMIURGE agent framework (28 souls) + 8 KPI stacks + 7 signal routes
- **[agents/schemas/](agents/schemas/)** — 16 agent-state schemas (`additionalProperties: false` enforced)
- **[state/](state/)** — LIVE runtime state mirror (`/opt/data/state/`)
- **[state-versioned/](https://github.com/Ai-Whisperers/state-versioned)** — separate repo: hourly git-tracked snapshots (per `OPERATIONS.md:90`)
- **[patterns/](patterns/)** — hard-stop-wrapper, idempotency, trademark-scrub
- **[playbooks/](playbooks/)** — `00-INDEX.md`, 8 dept playbooks, `PACKAGE-INDEX.md`, `ROADMAP-DEPT-EXPANSION.md`, `ROLLBACK-PLAYBOOK.md`

### Design meetings (new, merged from `cursor/department-design-meeting-sot`)

- **[meetings/README.md](meetings/README.md)** — meetings index
- **[meetings/TEMPLATES/session.md](meetings/TEMPLATES/session.md)** — session template
- **[meetings/department-design/](meetings/department-design/)** — 5 docs + `DECISIONS.md` + `NEXT-AGENDA.md` + `README.md` (codifies 28 Aug + Magic Tower decisions)
- **[analysis/2026-09-01-IVAN-DEPT-DESIGN-TODO.md](analysis/2026-09-01-IVAN-DEPT-DESIGN-TODO.md)** — Ivan's dept-design action items

### Scripts + tests

- **[scripts/](scripts/)** — 97 production scripts organized by subdirectory: `cron/`, `cost/`, `state/`, `eval/`, `errors/`, `context/`, `observability/`, `dashboard/`, `deprecation/`, `demiurge/`, `webhook/`, `whatsapp/`, `conversion/`, `curator/`
- **[tests/](tests/)** — 44 test files, 66 tests, all green
- **Critical scripts** (run regularly):
  - `scripts/cost-per-cron.py` — per-cron cost correlation (`jobs.json` ↔ `cost-tracker.json`)
  - `scripts/cost-optimize.py` — find disabled/failing/overlapping crons + recommendations
  - `scripts/cost-cap.py` — $1/agent/day + $10 total cap (per `tool-stack-decisions.md:225-275`)
  - `scripts/smoke-test.sh` — L1-L4 gates
  - `scripts/lint-prompts.py` — frontmatter validation (63 PROMPTs)
  - `scripts/chaos-runner.py` — chaos scenarios
  - `scripts/state-validate.py` — schema validation
  - `scripts/cron-sync.sh` — gateway → canonical mirror sync
- **Pre-commit hooks** (when configured):
  - `lint-prompts.py`, `smoke-test.sh all`, `cron-guard`, `state-validate.py`

### Tickets + analysis

- **[tickets/](tickets/)** — 309 DEMIURGE ticket artifacts (`DEMIURGE-001` through `DEMIURGE-309`)
- **[analysis/](analysis/)** — 65 files: phase feedback (PHASE-26 through PHASE-36), L1-L4 hygiene, naming catalogs, BASELINE coverage, drift audits, dept-design TODO

---

## The 6 Tier-1 departments (one-line each)

| Dept | Charter | Lead agent | Sub-agents |
|---|---|---|---|
| **Operations** | Obs/automation/process excellence | `management-coordinator` | 9 (bizops, ai-ops, compliance, founder-bandwidth, source-curator, okr, procurement, + 2 cadence variants) |
| **Finance & Legal** | Compliance, funding, runway | `finance-controller` | 5 (business-analyst, accounting, funding, tax-receipts, + 1 cadence variant) |
| **Sales & Growth** | Revenue, pipeline, proposals | `sales-pipeline` | 6 (lead-enrichment, proposal-drafter, revops, marketing, multimedia, + 3 cadence variants) |
| **Engineering** | Code, infra, safety, quality | `engineering-roster` | 13 (ai-safety, devops, qa, security, chaos, drift, eval-gate, delivery, + 4 cadence variants) |
| **Research & Education** | Knowledge, thesis, courses | `research-tracker` | 3 (citation-checker, course-producer, thesis-tracker) |
| **People & Culture** | Founder health, first-FTE prep | `people-hr` | 1 (`people-hr` itself is monitored; `kiki-coach` lives in sister repo `coach-agents`) |
| **Board of Directors** | Cross-dept governance | `board-of-directors` | 0 (governance, not a charter dept) |

**For details per dept**: see [department-index.md](department-index.md). For execution artifacts, see [analysis/](analysis/).

---

## Provider stack (live, 2026-09-01)

| Provider | Jobs | % | Model | Notes |
|---|---:|---:|---|---|
| `minimax-oauth` | 70 | 42% | `MiniMax-M3` | Reasoning-tier, OAuth subscription (M3 default model) |
| `litellm` | 58 | 35% | `primary` (40), `fast` (18), `reasoning` (1) | Litellm-routed; `primary` resolves to unknown model — `[unverified]` |
| **None / unknown** | 40 | 24% | None | **Config drift** — invisible spend; same root cause as `OPERATIONS.md:124` `Unknown provider 'minimax-plan'` error |

**GLM (Z.AI / Zhipu)**: 0 jobs use it today (greenfield integration). Configured at `/opt/data/context_length_cache.yaml` (`cerebras-zai-glm@https://llm.paragu-ai.com/v1: 8192` context cap).

**Reference pricing** (2026-09-01, see [research/token-efficiency-minimax-glm-2026-09-01.md](research/token-efficiency-minimax-glm-2026-09-01.md) for sources):

| Provider | Input $/M | Output $/M | Cache $/M | Context |
|---|---:|---:|---:|---:|
| MiniMax M3 (≤512k, 50% off promo) | $0.30 | $1.20 | $0.06 | 1M tokens |
| GLM-4.6 | $0.60 | $2.20 | $0.11 | ~200k tokens |

---

## How to add a new agent

1. **Pick a name** — see `analysis/AGENT-NAMES-V2.md` (DEMIURGE: Greek myth; heritage: portmanteau)
2. **Pick a department** — see `analysis/DEPT-AGENTS-ROLES-COMPLETE.md`
3. **Create the directory**:
   ```
   /opt/data/agents/<dept>/<agent-name>/
   ├── PROMPT.md          ← 12-section template
   ├── PROMPT-monitor.md  ← if monitored (PROMPT-monitor.md template)
   └── outbox/            ← mkdir + .gitkeep (output sink)
   ```
4. **Add a cron job** to `/opt/data/.hermes/cron/jobs.json` (use any `aiw-<existing-agent>` as template)
5. **Update catalogs** — `analysis/DEPT-AGENTS-ROLES-COMPLETE.md` + relevant `demiurge/kpi/` + `demiurge/signals/`
6. **Verify** — `bash /opt/data/scripts/cron-sync.sh && /opt/data/.venv/bin/python3 scripts/lint-prompts.py && ./scripts/smoke-test.sh all`
7. **Commit + push** — pre-commit hook validates cron drift

---

## Cost-control + token-efficiency posture

The org is in active close-out on Phase 9 R-series (cost-control layer). Current state:

- **Live burn: $93.61/day** (49/168 crons matched in `state/cost-per-cron.json`; remaining 119 are unmeasured)
- **Cost-cap.py exists** but uses flat-rate USD assumptions; **does not fire on MiniMax OAuth credits**
- **Token-ledger.py exists** with `DEFAULT_BUDGET_24H = 50000` credits — **uncalibrated** (no empirical probe yet)
- **circuit_breaker.py exists** (cc-switch pattern) but only wired into signal routing, **not cron execution**
- **6-lever playbook** documented in `research/token-efficiency-minimax-glm-2026-09-01.md` §"Deep Dive" — estimated **$3,000/year** recoverable + elimination of 5/6 Sunday-evening HTTP 429 errors

**Phase 9 R-series close-out tickets** (`analysis/PHASE-2X-FEEDBACK.md` series) track individual fixes.

---

## Repo naming history

| Period | Repo name | Purpose |
|---|---|---|
| 2026-08-31 earlier | `Ai-Whisperers/agent-infra` | Original name (general "infra") |
| 2026-08-31 now | **`Ai-Whisperers/aiw-org`** | Renamed to signal "internal AIW org layer" — not the coaching product |

Old URLs auto-redirect to the new name.

---

## Sister repos

- **[`Ai-Whisperers/growth-coaching`](https://github.com/Ai-Whisperers/growth-coaching)** — the **customer-facing coaching product**. Contains:
  - 6 distributable packages (coaching, finance, sales, operations, engineering, research)
  - DEMIURGE framework + research catalog
  - Constitution charters + research archives
- **[`Ai-Whisperers/coach-agents`](https://github.com/Ai-Whisperers/coach-agents)** — coaching-product agents (`kiki-coach`, `coach-lead-finder`, `coach-onboarding-poller`) that interact with the GROW product
- **[`Ai-Whisperers/state-versioned`](https://github.com/Ai-Whisperers/state-versioned)** — hourly git-tracked snapshots of `/opt/data/state/` (cron: `state-versioned-push` per `OPERATIONS.md:90`)

The three repos share:
- Cron sync infrastructure (`/opt/data/.hermes/cron/jobs.json` is the canonical mirror)
- BWS secret store (`/opt/data/.hermes/bws-secrets-cache.tsv`, loaded from `/opt/data/scripts/`)
- Bitwarden-backed credentials (`github-pat-deploy`, `OPENAI_API_KEY`, `GLM_API_KEY`/`ZAI_API_KEY`, `MINIMAX_API_KEY` per `hermes-agent/references/providers-and-models.md`)
- The same Hermes runtime + state schema design

---

## See also (legacy / phase history)

- **[OPERATIONS.md](OPERATIONS.md)** — the operational runbook (read this to understand how the org works)
- **[department-index.md](department-index.md)** — per-department pointer file (regenerated when dept structure changes)
- **[ON-CALL.md](ON-CALL.md)** — what to do when X breaks
- **[ORG-AGENTS.md](ORG-AGENTS.md)** — full 63-agent handoff matrix
- **[dept-monitors/INDEX.md](dept-monitors/INDEX.md)** — 16 monitor pattern inventory
- **[analysis/PHASE-5-COMPLETION-REPORT.md](analysis/PHASE-5-COMPLETION-REPORT.md)** — setup parity 100%
- **[analysis/PHASE-6-REFINEMENT-FEEDBACK.md](analysis/PHASE-6-REFINEMENT-FEEDBACK.md)** — execution gap fixes
- **[analysis/PHASE-7-RESEARCH-FEEDBACK.md](analysis/PHASE-7-RESEARCH-FEEDBACK.md)** — 52 research areas
- **[analysis/PHASE-8-FEEDBACK.md](analysis/PHASE-8-FEEDBACK.md)** — 30 research areas executed
- **[research/DEPT-RESEARCH-METHODOLOGY.md](research/DEPT-RESEARCH-METHODOLOGY.md)** — the 7-question pattern
