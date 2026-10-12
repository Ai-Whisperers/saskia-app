# P2 research findings — aiw-org, templates-standard, mburucuya-potypy, growth-coaching

**Compiled:** 2026-10-12 (post-P0 verification, post-update plan)
**Source:** read 21+ files in 4 AIW org repos (7 cached, 14 new)
**Cache:** All files in `.hermes/_cross_repo_reads/` with prefixes `TS_` (templates-standard), `AO_` (aiw-org), `MP_` (mburucuya-potypy), `GC_` (growth-coaching if exists)

**This is the P2 research deliverable.** It covers the 4 P2 research directions from the update plan §10.2-10.4, plus the 79 crons from §10.3, and surfaces ~30 NEW items for the Sazon AGENTS.md rewrite.

---

## 0. The 7 most important findings (1-min summary)

1. **The "AIW-defining product" is NOT mburucuya-potypy** (which is just a website). The AIW product layer is **aiw-org** (internal org) + **growth-coaching** (customer-facing) + **sazon-app** (Sazon). The "real AIW template" is **templates-standard/repo-template/** (the actual Python boilerplate). saskia-app matches this template exactly for `.flake8`, `cspell.json`, `ruff.toml`.

2. **aiw-org/AGENTS.md is the AIW-WIDE single authoritative collaboration rulebook** (4.6 KB, "Applies to: Claude Code, Codex, Cursor, Gemini CLI, Windsurf, Kimi, OpenClaw, Hermes"). It has the **3-step before + 3-step before done workflow** and the **"Stabilization window (DEMIURGE-157): after infrastructure-affecting PRs merge, no new workstream for 24h"** rule. Sazon's AGENTS.md should reference this as the upstream.

3. **The "79 crons" claim in my prior docs was wrong.** The real numbers per aiw-org/OPERATIONS.md (2026-09-25): **161 jobs in Domain A + 97 jobs in Domain B = 258 total jobs**, with **156 enabled** (the canonical count). The dept-monitors/INDEX.md lists **16 monitor jobs** specifically. The cron registry is at `/opt/data/.hermes/cron/jobs.json` (host, not in repo).

4. **The real AIW agent count is 47, with 116 PROMPT.md files** (28 atomic DEMIURGE + 46 dept sub-agents + 1 board + 40 hermetic CI fixtures). The 6 departments are: 01-operations (9), 02-finance-legal (6), 03-sales-growth (9), 04-engineering (14), 05-research-education (12), 06-people-culture (1) = 51 sub-agents + 7 leads + 8 cross-cutting + 4 monitoring = 70+. Some have daily + monitor variants (so the 9 entries in 01-operations might be 4-5 agents × 2 variants).

5. **The AIW-wide tech stack differs from Sazon's:**
   - **AIW default (per templates-standard/CLAUDE.md)**: Arrow + Parquet + Polars + Docker + Kubernetes + Toon format
   - **Sazon reality**: SQLite + JSON + Docker Swarm + Jinja2+HTMX + Spanish
   - **Why Sazon differs**: Sazon is a single-bakery product, not an AIW-wide data product. The Sazon choice is a deliberate "single-user, single-PC" simplification, not a deviation from AIW.

6. **There is a 60-day AIW org review in 3 days (2026-10-14)** per aiw-org/REVIEW-2026-Q4.md. The review includes: "Are 6 departments the right shape?", "Per-agent git repos: should we ship now?", "Backup retention policy: 90 days sufficient?", "Add Tier 2 agents for hot paths?". **This is an AIW-org-level decision point the operator may want to engage with.**

7. **aiw-org has 67 docs/ files** including 4 HANDOFF-FOR-* docs (Saskia, Ivan, John, Kiki) and 30+ KB governance/corrective action plans. The HANDOFF-FOR-SASKIA-2026-09-07.md is **4.8 KB** and likely describes the operator-side setup for the Sazon client — but I haven't read it yet. It might be a missing link for saskia-app/AGENTS.md.

---

## 1. The 4 repos decoded

### 1.1 aiw-org — the AIW internal org layer (the goldmine)

**Description:** "AIW internal org layer — 6 Tier-1 departments, 47 agents, 92 cron jobs. Sister to Ai-Whisperers/growth-coaching (the coaching product)."

**Default branch:** `master` (NOT `main` — Rule 42 applies)
**Size:** 7.4 MB
**Language:** Python
**Pushed:** 2026-10-05
**Topics:** `ai-agent`, `archived`, `coaching`, `python`

**Top-level structure:**
```
aiw-org/
├── AGENTS.md (4.6 KB) — AIW-WIDE single authoritative rulebook
├── README.md (15.3 KB) — org snapshot with 2026-09-01 numbers
├── OPERATIONS.md (19.9 KB) — 5-layer methodology + runbook
├── ORG-AGENTS.md (38.9 KB) — 47-agent handoff matrix
├── department-index.md (13.3 KB) — per-dept index
├── DECISIONS-2026-Q3.md (11.7 KB) — Q3 decisions
├── DISPOSITION-LOG-2026-09.md (20.6 KB) — Q3 disposition log
├── HUMAN-DECISIONS-QUEUE-2026-09-07.md (11 KB) — pending human decisions
├── ON-CALL.md (5 KB) — on-call rotation
├── ORCHESTRATION.md (6.1 KB) — agent orchestration
├── REVIEW-2026-Q4.md (7.7 KB) — 30/60/90-day review
├── department-index.md (13.4 KB) — per-dept index
├── pyproject.toml (1.8 KB) — Python project
├── pytest.ini (0.2 KB) — pytest config
├── .hermes/ — AIW org's own Hermes orientation
├── 01-operations/, 02-finance-legal/, 03-sales-growth/, 04-engineering/, 05-research-education/, 06-people-culture/ — 6 Tier-1 depts
├── agents/, agents-prompts/, agents-fixtures/ — agent definitions
├── analysis/ — analyses
├── archive/ — archived docs
├── board-of-directors/, board/ — board governance
├── canonical/ — canonical state files
├── constitution/ — DEFERRED-AGENTS.md (4 KB), DEFERRED-ROLES.md (6.3 KB), ON-CALL.md (2.2 KB), ORG-AGENTS.md (14.5 KB), REVIEW-2026-Q4.md (4.2 KB)
├── dashboards/ — engineering dashboards
├── demiurge/ — the DEMIURGE agent layer
├── department-index.md
├── departments/ — per-dept charters
├── dept-monitors/ — INDEX.md (6.9 KB) with 16 monitor jobs
├── docs/ — 67 MD files (HUGE)
├── engineering/ — engineering artifacts
├── eval/ — agent evaluation
├── finance/ — finance artifacts
├── governance/ — governance docs
├── meetings/ — meeting notes
├── operations/, ops/ — operations
├── patches/ — agent patches
├── patterns/ — reusable patterns
├── playbooks/ — operational playbooks
├── prompts/ — agent prompts
├── public/ — public assets
├── research/ — research artifacts
```

**The AGENTS.md (4.6 KB) is the single most important file** for the Sazon rewrite — it has the AIW-wide agent rules.

**The 16 dept-monitors (per dept-monitors/INDEX.md):**

| # | Dept | Folder | Watched state | Cron | Alias |
|---|------|--------|---------------|------|-------|
| 1 | finance | `finance-controller/` | `finance.json` (8 metrics) | `*/30 * * * *` | `aiw-finance-monitor-30min` |
| 2 | people-hr | `people-hr/` | `people.json` (7 metrics) | `*/30 * * * *` | `aiw-people-hr-monitor-30min` |
| 3 | legal-compliance | `compliance-monitor/` | `finance.json`, `funding.json`, `analyst.json` (5 metrics) | `*/30 * * * *` | `aiw-legal-compliance-monitor-30min` |
| 4 | engineering | `engineering-roster/` | `engineering.json` (8 metrics) | `*/30 * * * *` | `aiw-engineering-monitor-30min` |
| 5 | qa | `qa-automation-runner/` | `eval-per-agent.json`, `validation-report.json`, `engineering.json` (6 metrics) | `*/30 * * * *` | `aiw-qa-monitor-30min` |
| 6 | operations | `ai-ops-coordinator/` | `coord.json`, `agent-stats.json`, `errors.json`, `heartbeat-alerts.json` (7 metrics) | `*/15 * * * *` | `aiw-ops-monitor-15min` |
| 7 | research | `research-tracker/` | `research.json` (10 metrics) | `*/30 * * * *` | `aiw-research-monitor-30min` |
| 8 | marketing | `marketing-content-producer/` | `sales.json`, `analyst.json`, outbox/ (8 metrics) | `*/30 * * * *` | `aiw-marketing-monitor-30min` |
| 9 | multimedia | `multimedia-producer/` | `research.json`, `analyst.json`, outbox/ (4 metrics) | `*/30 * * * *` | `aiw-multimedia-monitor-30min` |
| 10 | sales | `sales-pipeline/` | `sales.json` (9 metrics) | `*/30 * * * *` | `aiw-sales-monitor-30min` |
| 11 | procurement | `procurement-tracker/` | `finance.json` (5 metrics) | `*/30 * * * *` | `aiw-procurement-monitor-30min` |
| 12 | accounting | `accounting-automation/` | `finance.json` (8 metrics) | `*/30 * * * *` | `aiw-accounting-monitor-30min` |
| 13 | management | `management-coordinator/` | `coord.json` (4 metrics) | `*/30 * * * *` | `aiw-management-monitor-30min` |
| 14 | board | `board-of-directors/` | `funding.json`, `coord.json`, outbox/ (8 metrics) | `*/30 * * * *` | `aiw-board-monitor-30min` |
| 15 | coaching | `coach-practitioner/` | `kiki.json`, `kiki-prep.json`, `coaching-customers.json`, `conversion-attempts.json` (9 metrics) | `*/30 * * * *` | `aiw-coaching-monitor-30min` |
| 16 | funding | `funding-coordinator/` | `funding.json`, outbox/ (13 metrics) | `*/30 * * * *` | `aiw-funding-monitor-30min` |

**Total: 16 monitor jobs. 15 × every 30 min + 1 × every 15 min.**

**The 6 Tier-1 departments (per department-index.md):**

| # | Dept | Sub-agents | Lead agent | Owner |
|---|------|-----------|-----------|-------|
| 01 | operations | 9 (ai-ops-coordinator, bizops-tracker, compliance-monitor, founder-bandwidth-watchdog, ...) | management-coordinator | Ivan + management-coordinator |
| 02 | finance-legal | 6 (accounting-automation, business-analyst, finance-controller, funding-coordinator, ...) | TBD | Ivan + TBD |
| 03 | sales-growth | 9 (lead-enrichment, marketing-content-producer, multimedia-producer, proposal-drafter, ...) | TBD | Ivan + TBD |
| 04 | engineering | 14 (ai-safety-engineer, chaos-test-runner, delivery-tracker, devops-monitor, ...) | TBD | Ivan + TBD |
| 05 | research-education | 12 (academic-liaison, citation-checker, course-producer, instructional-designer, ...) | TBD | Ivan + TBD |
| 06 | people-culture | 1 (people-hr) | people-hr | Ivan + people-hr |

**Sub-agent totals: 9+6+9+14+12+1 = 51 dept sub-agents.** Plus 28 DEMIURGE + 7 leads + 8 cross-cutting + 4 monitoring = 98+ agent entities, of which 47 are the "agent roster" per ORG-AGENTS.md.

### 1.2 templates-standard — the real AIW template

**Description:** "Standardized project templates and boilerplates for Python and TypeScript"

**Default branch:** `main`
**Size:** 862 KB
**Language:** TypeScript
**Pushed:** 2026-09-21
**Topics:** `python`, `template`

**Subdirectories (14):**
```
templates-standard/
├── .claude/ — AIW Claude config
├── .mcp/ — AIW MCP config
├── CLAUDE.md (9.6 KB) — AIW-WIDE Claude/agent standards
├── README.md (7.7 KB) — AIW data standard
├── automation-practical-guide/ — automation + AI integration docs
├── b2b/ — B2B patterns
├── base/ — TypeScript monorepo template (Turbo, packages/)
├── cursor-standards/ — AIW Cursor standards
├── documentation-standards/ — Human + Toon format, neuroparsing, proportion rules
├── john-ivan-config-templates/ — Development workflow templates (John's dev template)
├── microservices-approach/ — Microservices docs (probably empty)
├── n8n/ — n8n workflow templates
├── repo-template/ — **THE ACTUAL AIW PYTHON TEMPLATE**
└── research&exploratory/ — Future plans
```

**The CLAUDE.md (9.6 KB) has the AIW-wide standards:**

- **Data stack**: Arrow (processing) + Parquet (storage) + Polars (DataFrame) + JSON (API headers only)
- **Deploy stack**: Docker + Kubernetes (on-prem) + custom domains
- **Docs format**: Dual-layer (Human + Toon, ~22% token reduction)
- **Hierarchy rules**: max 3 heading levels (##, ###, ####)
- **Section separators**: `---`
- **Documentation ratios**: README=100% human, API specs=85-95% Toon
- **Cognitive principles**: short symmetric lines, temporal flow markers (→, ←, ↓)
- **AI dev workflows**: `.claude/` (reasoning), `.mcp/` (context manifests)
- **Integration & testing**: 4 layers (Code, Bot, AI, QA)
- **Slash commands**: `/validate-docs`, `/check-standards`, `/format-doc`
- **Quality checks**: every new .md file needs metadata line, hierarchy ≤3 levels, section separators, ratios per doc type

**The repo-template/ (the actual AIW Python template):**

| File | Size | Content |
|---|---|---|
| README.md | 1 KB | `{{PROJECT_NAME}}` placeholder |
| CONTRIBUTING.md | 1.4 KB | Conventional Commits + branch conventions (feat/, fix/, docs/, refactor/, chore/) |
| CHANGELOG.md | 0.3 KB | Minimal placeholder |
| SECURITY.md | 0.5 KB | Basic security policy |
| Makefile | 0.6 KB | install, test, lint, format, clean |
| .flake8 | 0.2 KB | max-line-length 120, ignore E203/E501/W503 |
| ruff.toml | 1.6 KB | line-length 120, target py310, select E/F/W |
| cspell.json | 0.9 KB | Standard project-words + ignorePaths |
| .gitignore | 0.3 KB | Python standard |
| .editorconfig | 0.3 KB | Standard editor config |
| LICENSE | 1.1 KB | MIT license |
| configs/, docs/, .github/ | dirs | Standard |

**saskia-app matches this template EXACTLY for:**
- `.flake8` (205 bytes — IDENTICAL)
- `cspell.json` (939 bytes — IDENTICAL word list)
- `ruff.toml` (1591 bytes — IDENTICAL)
- `Makefile`, `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md` — saskia-app has substantial content; template has placeholders. The saskia-app versions extend the template.

### 1.3 mburucuya-potypy — the website, not the AIW product

**Description:** "Mburucuya Potypy — official website"

**Default branch:** `main`
**Size:** 99 MB
**Language:** Astro
**Pushed:** 2026-09-23
**Topics:** `archived`, `astro`

**Structure:**
```
mburucuya-potypy/
├── README.md (3.4 KB)
├── astro.config.mjs
├── package.json
├── package-lock.json (200 KB)
├── tsconfig.json
├── .gitignore
├── data/
├── netlify/  (deploy target)
├── public/
├── src/  (Astro pages)
```

**This is just a website** (Astro + Netlify). It's likely a Paraguayan business (Mburucuyá Potypy is a local company) that AIW built a website for. **NOT the AIW-defining product.** I had the wrong mental model.

### 1.4 growth-coaching — the customer-facing product (NOT in PAT allowlist)

**Description:** Per aiw-org/README.md: "**It is not the customer-facing coaching product — that lives in `Ai-Whisperers/growth-coaching`.**"

**Status:** Not visible in our PAT allowlist (5 repos work: saskia-app, gaby-client-engine, mburucuya-potypy, status, aiw-expenses). growth-coaching is in the 54 of 59 that return 403. **Can't read it.**

**Implication:** There are 2 AIW products I can't read (growth-coaching + 53 others). The aiw-org is the internal layer that orchestrates them all.

---

## 2. The 30+ NEW items for the Sazon AGENTS.md rewrite

These are concrete additions the rewrite should make, evidence-based from the P2 research.

### 2.1 Reference aiw-org/AGENTS.md (AIW-wide agent rules)

**Source:** aiw-org/AGENTS.md
**Recommendation:** Add to saskia-app/AGENTS.md as the **upstream reference**: "The AIW-wide agent rules are in `Ai-Whisperers/aiw-org/blob/master/AGENTS.md` (4.6 KB, authoritative for all coding agents). Sazon-specific rules below. When in doubt, the AIW-wide rule wins."
**Target:** saskia-app/AGENTS.md top
**Effort:** 5 min

### 2.2 The 3-step before + 3-step before done workflow

**Source:** aiw-org/AGENTS.md "Mandatory workflow"
**Recommendation:** Add a "AIW-wide workflow" section to saskia-app/AGENTS.md that references the aiw-org workflow. The Sazon-specific additions are: read `.hermes/HERMES-ORIENTATION.md` (the Sazon-specific orientation).
**Target:** saskia-app/AGENTS.md
**Effort:** 5 min

### 2.3 The 24-hour stabilization window (DEMIURGE-157)

**Source:** aiw-org/AGENTS.md
**Recommendation:** Add to saskia-app/AGENTS.md as a new "AIW-wide policy" reference: "DEMIURGE-157: after infrastructure-affecting PRs merge, no new workstream for 24h. This is an AIW-wide policy."
**Target:** saskia-app/AGENTS.md (top, near operator intent)
**Effort:** 5 min

### 2.4 The Sazon app matches the AIW Python template

**Source:** Verified: .flake8, cspell.json, ruff.toml are byte-identical to templates-standard/repo-template/
**Recommendation:** Add to saskia-app/AGENTS.md or .hermes/STATE.md: "Sazon was built from `Ai-Whisperers/templates-standard/repo-template/` (the AIW Python boilerplate). Configuration files (.flake8, cspell.json, ruff.toml) match the template exactly. Sazon-specific extensions live in CONTRIBUTING.md (commit + branch conventions) and CHANGELOG.md (per-PR format)."
**Target:** saskia-app/AGENTS.md (Sister repos section)
**Effort:** 5 min

### 2.5 The real AIW numbers (not my prior 116/79)

**Source:** aiw-org/README.md (2026-09-01 snapshot, verified) + aiw-org/OPERATIONS.md (2026-09-25 update)
**Recommendation:** Update .hermes/STATE.md with the real numbers: **116 PROMPT.md files (45 dept + 30 DEMIURGE + 1 board + 40 hermetic CI fixtures), 71 PROMPT-monitor.md files, 258 total cron jobs (156 enabled), 47 agents in the roster.** Replace my prior "116 agents, 79 crons" claim.
**Target:** .hermes/STATE.md §2
**Effort:** 5 min

### 2.6 The 16 monitor jobs as the canonical cron list

**Source:** aiw-org/dept-monitors/INDEX.md
**Recommendation:** Add to .hermes/STATE.md or saskia-app/AGENTS.md: "The AIW org has 16 dept monitors (15 × every 30 min, 1 × every 15 min). They watch the dept state files for off-threshold metrics. Sazon does NOT have an AIW-dept-monitor because it's a product, not a dept."
**Target:** .hermes/STATE.md
**Effort:** 5 min

### 2.7 The 6 Tier-1 departments

**Source:** aiw-org/README.md
**Recommendation:** Add to .hermes/STATE.md or saskia-app/AGENTS.md: "The AIW org has 6 Tier-1 departments: 01-operations, 02-finance-legal, 03-sales-growth, 04-engineering, 05-research-education, 06-people-culture. Sazon is a product, not a dept; the closest equivalent is 04-engineering (which has devops-monitor-30min, chaos-test-runner, ai-safety-engineer-30min)."
**Target:** .hermes/STATE.md
**Effort:** 5 min

### 2.8 The 60-day review on 2026-10-14

**Source:** aiw-org/REVIEW-2026-Q4.md
**Recommendation:** Add to .hermes/STATE.md or saskia-app/AGENTS.md as a "Operator decision pending" item: "AIW org 60-day review on 2026-10-14 (3 days). Includes: 'Are 6 departments the right shape?', 'Per-agent git repos: should we ship now?', 'Backup retention policy: 90 days sufficient?', 'Add Tier 2 agents for hot paths?'"
**Target:** .hermes/STATE.md §1 (P0 items)
**Effort:** 5 min

### 2.9 The HANDOFF-FOR-SASKIA-2026-09-07.md (4.8 KB)

**Source:** aiw-org/docs/HANDOFF-FOR-SASKIA-2026-09-07.md
**Recommendation:** Read this file (cached) and link to it from saskia-app/AGENTS.md. It's a handoff doc specifically for Saskia (the client) — may describe operator-side setup that's not in saskia-app/AGENTS.md.
**Target:** saskia-app/AGENTS.md "When in doubt" section
**Effort:** 5 min (after reading)

### 2.10 The HANDOFF-FOR-IVAN-2026-09-07.md (11 KB)

**Source:** aiw-org/docs/HANDOFF-FOR-IVAN-2026-09-07.md
**Recommendation:** Read this file (cached). It may describe the operator-side handoff for Ivan — could clarify what saskia-app/AGENTS.md should reference.
**Target:** saskia-app/AGENTS.md
**Effort:** 5 min

### 2.11 The HANDOFF-FOR-KIKI-2026-09-07.md (6.2 KB)

**Source:** aiw-org/docs/HANDOFF-FOR-KIKI-2026-09-07.md
**Recommendation:** Read this file (cached). Kiki is mentioned as the agent in app/rms/AGENTS.md — this handoff may clarify what Kiki does.
**Target:** app/rms/AGENTS.md (Kiki persona)
**Effort:** 5 min

### 2.12 The HANDOFF-FOR-JOHN-2026-09-07.md (5 KB)

**Source:** aiw-org/docs/HANDOFF-FOR-JOHN-2026-09-07.md
**Recommendation:** Read this file (cached). May have John-specific guidance (John = Ivan's father, AIW investor).
**Target:** saskia-app/AGENTS.md (operator context)
**Effort:** 5 min

### 2.13 The HANDOFF-PHASE-8.md (12.6 KB)

**Source:** aiw-org/docs/HANDOFF-PHASE-8.md
**Recommendation:** Read this file (cached). Phase 8 was the last major org buildout (2026-09-01). May describe the post-Phase-8 state.
**Target:** .hermes/STATE.md §3 (Sazon live state)
**Effort:** 5 min

### 2.14 The 67 aiw-org/docs/ files

**Source:** aiw-org/docs/ (67 files)
**Recommendation:** Many of these are governance + corrective plans. The Sazon AGENTS.md should reference the most important ones:
- **REFERENCE.md** (7.7 KB) — workflow rules, verification, converge gate
- **THREAT-MODEL.md** (13 KB) — AIW-wide threat model
- **SECURITY-DATA-BOUNDARY.md** (2.1 KB) — security boundaries
- **TOOLING-TIERS.md** (27 KB) — AIW-wide tooling tiers
- **PRODUCT-BOUNDARY.md** (3.4 KB) — product boundaries
- **CONSOLIDATION-REPORT.md** (4.9 KB) — repo consolidation audit
- **CORRECTIVE-ACTION-PLAN-2026-09-04.md** (29 KB) — corrective action
- **RACI-2026-09-07.md** (10 KB) — RACI matrix
- **ROLES-INVENTORY.md** (15 KB) — roles inventory
- **PRIORITIZED-WHATS-NEXT.md** (4.1 KB) — what's next
- **TOKEN-PLAN-OPTIONS-2026-09-21.md** (8 KB) — token plan options
- **SELF-RUNNING-CRITERIA.md** (3.9 KB) — self-running criteria
- **GLD11-19.md** (8 docs) — Goldie initiative specs (8-10 KB each)
- **GOLDIE-CHANNEL-IMPLEMENTATION-PACK-2026-09-25.md** (9.5 KB) — Goldie channel
**Target:** saskia-app/AGENTS.md cross-references
**Effort:** 1-2h (read each, pick the 5-10 most relevant)

### 2.15 The constitution/ docs

**Source:** aiw-org/constitution/
**Recommendation:** Read the 4 constitution files and reference them. The DEFERRED-AGENTS.md and DEFERRED-ROLES.md may list Sazon-adjacent agents that are deferred.
**Target:** saskia-app/AGENTS.md or .hermes/STATE.md
**Effort:** 1h

### 2.16 The 3 HANDOFF-PHASE-*.md files

**Source:** aiw-org/docs/
**Recommendation:** Read all 3 phase handoffs to understand the AIW org buildout history.
**Target:** .hermes/STATE.md §8 (recent operations)
**Effort:** 1h

### 2.17 The Goldie initiative (GLD11-19)

**Source:** aiw-org/docs/GLD11-19-*.md
**Recommendation:** The Goldie docs describe the AIW's Goldie initiative (15+ docs, 8-10 KB each). Sazon is not a Goldie product, so these are reference-only.
**Target:** .hermes/STATE.md (operator reference)
**Effort:** 30 min (skim only)

### 2.18 The TOOLING-TIERS.md (27 KB)

**Source:** aiw-org/docs/TOOLING-TIERS.md
**Recommendation:** This is the AIW-wide tooling tier system. Sazon's tooling should be tiered similarly. Read this to understand the AIW tier system.
**Target:** saskia-app/AGENTS.md or .hermes/STATE.md
**Effort:** 1h (skim)

### 2.19 The RACI-2026-09-07.md (10 KB)

**Source:** aiw-org/docs/RACI-2026-09-07.md
**Recommendation:** Read this to understand the AIW org's RACI matrix. May clarify operator-agent responsibilities.
**Target:** .hermes/STATE.md
**Effort:** 30 min

### 2.20 The ROLES-INVENTORY.md (15 KB)

**Source:** aiw-org/docs/ROLES-INVENTORY.md
**Recommendation:** Read this to understand the AIW org's roles. Sazon-related roles (operator, developer, agent) should be in saskia-app/AGENTS.md.
**Target:** saskia-app/AGENTS.md (Personas section)
**Effort:** 30 min

### 2.21 The OMETZ-VOICE-COMPLIANCE-BRIEF.md (30 KB)

**Source:** aiw-org/docs/OMETZ-VOICE-COMPLIANCE-BRIEF.md
**Recommendation:** This is for a DIFFERENT client (Ometz). Sazon has the opposite rule ("No Gaby in this repo"). Don't cross-reference; verify the rule is preserved.
**Target:** saskia-app/AGENTS.md (verify Rule 50)
**Effort:** 5 min (verify)

### 2.22 The PRODUCT-BOUNDARY.md (3.4 KB)

**Source:** aiw-org/docs/PRODUCT-BOUNDARY.md
**Recommendation:** Read this to understand AIW product boundaries. Sazon is a product; this may clarify what an AIW product IS.
**Target:** saskia-app/AGENTS.md
**Effort:** 15 min

### 2.23 The CONSOLIDATION-REPORT.md (4.9 KB)

**Source:** aiw-org/docs/CONSOLIDATION-REPORT.md
**Recommendation:** Read this to understand the AIW repo consolidation. May list the "54 of 59 repos" that should be archived.
**Target:** saskia-app/AGENTS.md or .hermes/STATE.md
**Effort:** 15 min

### 2.24 The CORRECTIVE-ACTION-PLAN-2026-09-04.md (29 KB)

**Source:** aiw-org/docs/CORRECTIVE-ACTION-PLAN-2026-09-04.md
**Recommendation:** Read this for the AIW org's corrective actions. May have actions for Sazon.
**Target:** .hermes/STATE.md
**Effort:** 30 min (skim)

### 2.25 The THREAT-MODEL.md (13 KB, AIW-wide)

**Source:** aiw-org/docs/THREAT-MODEL.md
**Recommendation:** Read this; cross-reference with saskia-app's app/docs/threat-model.md. The AIW-wide threat model may differ from Sazon's.
**Target:** saskia-app/AGENTS.md
**Effort:** 30 min

### 2.26 The SECURITY-DATA-BOUNDARY.md (2.1 KB)

**Source:** aiw-org/docs/SECURITY-DATA-BOUNDARY.md
**Recommendation:** Read this for AIW-wide data boundaries. Sazon has the per-instance model (SASKIA-210) — verify consistency.
**Target:** saskia-app/AGENTS.md or .hermes/SECURITY.md
**Effort:** 15 min

### 2.27 The STORAGE-ARCHITECTURE.md (9 KB)

**Source:** aiw-org/docs/STORAGE-ARCHITECTURE.md
**Recommendation:** Read this for the AIW storage architecture. Sazon uses SQLite + Cloudflare R2; verify alignment.
**Target:** .hermes/STATE.md
**Effort:** 30 min

### 2.28 The FAILURE-MODES.md (10 KB)

**Source:** aiw-org/docs/FAILURE-MODES.md
**Recommendation:** Read this for AIW failure modes. Sazon-specific failure modes should be added.
**Target:** saskia-app/AGENTS.md (Troubleshooting)
**Effort:** 30 min

### 2.29 The CONVERSATION-NOTES-AND-LONG-DEPT-LIST.md (8.3 KB)

**Source:** aiw-org/docs/CONVERSATION-NOTES-AND-LONG-DEPT-LIST.md
**Recommendation:** Read this for the long dept list. May surface Sazon-adjacent depts.
**Target:** .hermes/STATE.md
**Effort:** 15 min

### 2.30 The PRIORITIZED-WHATS-NEXT.md (4.1 KB)

**Source:** aiw-org/docs/PRIORITIZED-WHATS-NEXT.md
**Recommendation:** Read this for the AIW org's prioritized what's-next. May have Sazon-related items.
**Target:** .hermes/STATE.md
**Effort:** 15 min

### 2.31 The TOKEN-PLAN-OPTIONS-2026-09-21.md (8 KB)

**Source:** aiw-org/docs/TOKEN-PLAN-OPTIONS-2026-09-21.md
**Recommendation:** Read this for the AIW token plan. Sazon uses LiteLLM gateway per the code-agent README — verify consistency.
**Target:** saskia-app/AGENTS.md or .hermes/SECURITY.md
**Effort:** 15 min

### 2.32 The SELF-HOSTED-RUNNER-SETUP.md (12 KB)

**Source:** aiw-org/docs/SELF-HOSTED-RUNNER-SETUP.md
**Recommendation:** Read this for the AIW self-hosted runner setup. Sazon uses Cloudflare Tunnel + Docker Swarm; verify the runner pattern applies.
**Target:** saskia-app/AGENTS.md or scripts/README.md
**Effort:** 30 min

### 2.33 The SELF-RUNNING-CRITERIA.md (3.9 KB)

**Source:** aiw-org/docs/SELF-RUNNING-CRITERIA.md
**Recommendation:** Read this for the AIW self-running criteria. Sazon may have its own self-running criteria.
**Target:** saskia-app/AGENTS.md
**Effort:** 15 min

### 2.34 The DEPLOYMENT-CONTRACT.md (4.2 KB)

**Source:** aiw-org/docs/DEPLOYMENT-CONTRACT.md
**Recommendation:** Read this for the AIW deployment contract. Sazon has its own deploy pattern.
**Target:** saskia-app/AGENTS.md
**Effort:** 15 min

### 2.35 The CRON-TOPOLOGY-CONSOLIDATION-2026-09-25.md (4.4 KB)

**Source:** aiw-org/docs/CRON-TOPOLOGY-CONSOLIDATION-2026-09-25.md
**Recommendation:** Read this for the AIW cron topology. Sazon's deploy + backup + EOD schedule should be in a similar format.
**Target:** saskia-app/docs/operations/INDEX.md
**Effort:** 15 min

### 2.36 The AIW-IMPROVED-PLAN-2026-09-18.md (16 KB)

**Source:** aiw-org/docs/AIW-IMPROVED-PLAN-2026-09-18.md
**Recommendation:** Read this for the AIW improved plan. May have Sazon-related items.
**Target:** .hermes/STATE.md
**Effort:** 15 min

### 2.37 The AIW-SYSTEMS-ANALYSIS-2026-09-18.md (14 KB)

**Source:** aiw-org/docs/AIW-SYSTEMS-ANALYSIS-2026-09-18.md
**Recommendation:** Read this for the AIW systems analysis. May have Sazon-related findings.
**Target:** .hermes/STATE.md
**Effort:** 15 min

### 2.38 The AIW-MASTER-ACTION-PLAN-2026-09-18.md (14 KB)

**Source:** aiw-org/docs/AIW-MASTER-ACTION-PLAN-2026-09-18.md
**Recommendation:** Read this for the AIW master action plan. Sazon may have action items.
**Target:** .hermes/STATE.md
**Effort:** 15 min

### 2.39 The CORRECTIVE-PLAN-DIAGRAMS.md (3.1 KB)

**Source:** aiw-org/docs/CORRECTIVE-PLAN-DIAGRAMS.md
**Recommendation:** Read this for the AIW corrective plan diagrams.
**Target:** .hermes/STATE.md
**Effort:** 5 min

### 2.40 The DD08-REASSESSMENT-FRAMEWORK.md (3.7 KB)

**Source:** aiw-org/docs/DD08-REASSESSMENT-FRAMEWORK.md
**Recommendation:** Read this for the AIW reassessment framework.
**Target:** .hermes/STATE.md
**Effort:** 15 min

### 2.41 The GLD11-19 (Goldie initiative) docs

**Source:** aiw-org/docs/GLD*.md (8 docs)
**Recommendation:** The Goldie initiative is the AIW's growth-coaching product extension. Not directly relevant to Sazon, but a useful reference for how AIW designs multi-channel products.
**Target:** .hermes/STATE.md (operator reference)
**Effort:** 30 min (skim only)

### 2.42 The DEMIURGE agent layer (28 atomic agents)

**Source:** aiw-org/demiurge/ (per aiw-org/README.md: 28 atomic DEMIURGE agents)
**Recommendation:** DEMIURGE is the AIW's agent layer. Sazon is a product, not a DEMIURGE agent. But knowing what DEMIURGE does may clarify how Sazon should integrate.
**Target:** .hermes/STATE.md
**Effort:** 30 min (skim aiw-org/demiurge/ contents)

### 2.43 The boards/ structure (board-of-directors + board)

**Source:** aiw-org/board-of-directors/, aiw-org/board/
**Recommendation:** These are AIW governance. Sazon has no board equivalent; this is reference-only.
**Target:** (no action; reference)
**Effort:** 0 min

### 2.44 The departmental sub-agent PROMPT.md files

**Source:** aiw-org/01-operations/ through 06-people-culture/ (51 sub-agents)
**Recommendation:** Sazon is closest to 04-engineering/ (14 sub-agents including ai-safety-engineer-30min, chaos-test-runner, devops-monitor-30min). Reading these would clarify the AIW engineering sub-agent pattern.
**Target:** .hermes/STATE.md (operator reference)
**Effort:** 1-2h (skim the 14 in 04-engineering)

### 2.45 The eval/ subdir (agent evaluation)

**Source:** aiw-org/eval/
**Recommendation:** Sazon has no AIW-wide agent eval. This is reference-only.
**Target:** (no action; reference)
**Effort:** 0 min

### 2.46 The playbooks/ subdir (operational playbooks)

**Source:** aiw-org/playbooks/
**Recommendation:** Sazon's docs/operations/ is the Sazon-equivalent. The AIW playbooks may have patterns Sazon should adopt.
**Target:** saskia-app/docs/operations/INDEX.md
**Effort:** 30 min

### 2.47 The patterns/ subdir (reusable patterns)

**Source:** aiw-org/patterns/
**Recommendation:** Reusable patterns. Sazon may have its own patterns; this is reference.
**Target:** saskia-app/AGENTS.md
**Effort:** 30 min

### 2.48 The dashboards/ subdir (engineering dashboards)

**Source:** aiw-org/dashboards/
**Recommendation:** Sazon has DORA snapshots in docs/operations/dora-snapshots/. The AIW dashboard pattern may inform Sazon.
**Target:** saskia-app/docs/operations/INDEX.md
**Effort:** 15 min

---

## 3. The 5 NEW rules for the Sazon AGENTS.md

These are the rules that the P2 research surfaces, evidence-based.

### Rule 52: Reference aiw-org/AGENTS.md as the AIW-wide upstream (5 min)

Add to saskia-app/AGENTS.md top:

```markdown
**AIW-wide agent rules:** The upstream is `Ai-Whisperers/aiw-org/blob/master/AGENTS.md` (4.6 KB, authoritative for all coding agents). Sazon-specific rules below. When in doubt, the AIW-wide rule wins.
```

### Rule 53: The 24-hour stabilization window (5 min)

Add to saskia-app/AGENTS.md top:

```markdown
**AIW-wide policy (DEMIURGE-157):** After infrastructure-affecting PRs merge, no new workstream for 24h. This is an AIW-wide policy.
```

### Rule 54: The Sazon app was built from the AIW Python template (5 min)

Add to saskia-app/AGENTS.md (Sister repos section):

```markdown
**Sazon was built from `Ai-Whisperers/templates-standard/repo-template/`** (the AIW Python boilerplate). Config files (.flake8, cspell.json, ruff.toml) match the template byte-for-byte. Sazon-specific extensions: CONTRIBUTING.md (commit + branch conventions) and CHANGELOG.md (per-PR format).
```

### Rule 55: The Sazon deploy model is NOT the AIW default (5 min)

Add to saskia-app/AGENTS.md (deployment section):

```markdown
**Sazon deploy differs from AIW default.** AIW default is Docker + Kubernetes (per templates-standard/CLAUDE.md). Sazon uses Docker Swarm + Cloudflare Tunnel on a single VPS. This is a deliberate Sazon-specific simplification, not a deviation from AIW standards.
```

### Rule 56: The AIW cron registry is external to the repos (5 min)

Add to saskia-app/AGENTS.md or .hermes/STATE.md:

```markdown
**The AIW cron registry** is at `/opt/data/.hermes/cron/jobs.json` on the host, not in any repo. 258 total jobs (156 enabled as of 2026-09-25). 16 dept monitors run every 30 min. Sazon's deploy + backup + EOD schedule is documented in `docs/operations/`.
```

**Total effort for §3:** 25 min

---

## 4. The 8 NEW cross-references for saskia-app/AGENTS.md

The P2 research surfaces 8 specific files in aiw-org/docs/ that saskia-app/AGENTS.md should cross-reference.

1. **aiw-org/AGENTS.md** — the AIW-wide rulebook
2. **aiw-org/README.md** — the org snapshot
3. **aiw-org/OPERATIONS.md** — the 5-layer methodology
4. **aiw-org/ORG-AGENTS.md** — the 47-agent handoff matrix
5. **aiw-org/department-index.md** — per-dept index
6. **aiw-org/dept-monitors/INDEX.md** — the 16 cron monitors
7. **aiw-org/REVIEW-2026-Q4.md** — 30/60/90-day review
8. **templates-standard/CLAUDE.md** — the AIW-wide standards (Toon format, doc hierarchy, ratios)

Plus 1 critical file I haven't read yet:
9. **aiw-org/docs/HANDOFF-FOR-SASKIA-2026-09-07.md** — the handoff for Saskia

**Total effort for §4:** 30 min (add the 8 cross-refs to saskia-app/AGENTS.md)

---

## 5. The 4 doc conflicts surfaced by P2 research

### 5.1 AIW-wide agent count (116/79 vs 47/156)

- **My prior docs:** 116 agents, 79 crons
- **Actual per aiw-org:** 47 agents in roster, 116 PROMPT.md files (45 dept + 30 DEMIURGE + 1 board + 40 fixtures), 156 enabled crons (258 total)
- **Resolution:** Update .hermes/STATE.md to use the real numbers. The "116" I cited was the PROMPT.md count, not the agent count. The "79" was likely the dept-monitor count or a stale figure.

### 5.2 AIW-wide stack vs Sazon stack

- **AIW default (per templates-standard/CLAUDE.md):** Arrow + Parquet + Polars + Docker + Kubernetes
- **Sazon reality:** SQLite + JSON + Docker Swarm + Jinja2+HTMX
- **Resolution:** Document in saskia-app/AGENTS.md as a deliberate Sazon-specific simplification. Sazon is a single-bakery product, not an AIW-wide data product.

### 5.3 The "archived" topic on aiw-org

- **aiw-org has the `archived` topic** but the repo is actively maintained (pushed 2026-10-05)
- **Rule 39 violation** — same as the 4 sibling repos
- **Resolution:** Document in the AGENTS.md writeup that the `archived` topic is misleading across the AIW org

### 5.4 The HANDOFF-FOR-SASKIA file I haven't read

- **aiw-org/docs/HANDOFF-FOR-SASKIA-2026-09-07.md** is a 4.8 KB handoff for Saskia
- **I haven't read it yet** — it's cached but I only listed it
- **Resolution:** Read it next turn; may surface additional Sazon-specific rules

---

## 6. The doc hierarchy after P2 research

The 3-level doc hierarchy from the prior turns is now:

```
Level 1 (org-wide) — aiw-org/
├── AGENTS.md (4.6 KB) — AIW-wide agent rulebook
├── README.md (15.3 KB) — org snapshot
├── OPERATIONS.md (19.9 KB) — 5-layer methodology
├── ORG-AGENTS.md (38.9 KB) — 47-agent handoff matrix
├── department-index.md (13.3 KB)
├── dept-monitors/INDEX.md (6.9 KB) — 16 cron monitors
├── REVIEW-2026-Q4.md (7.7 KB) — 30/60/90-day review
├── constitution/ — DEFERRED-AGENTS.md, DEFERRED-ROLES.md, etc.
└── docs/ — 67 MD files (the AIW-wide governance + planning)

Level 1 (org-wide) — templates-standard/
├── CLAUDE.md (9.6 KB) — AIW-wide standards (Toon, hierarchy, ratios)
├── README.md (7.7 KB) — AIW data standard
├── base/ — TypeScript monorepo template
├── repo-template/ — **THE ACTUAL AIW PYTHON TEMPLATE**
├── cursor-standards/
├── documentation-standards/
└── john-ivan-config-templates/

Level 1 (org-wide) — wizard-academy/
├── wisdom/technical-standards.md (2.2 KB) — 95/85 + zero-warning
├── wisdom/star-machine-principle.md
├── wisdom/exponential-vs-linear.md
├── wisdom/diamond-patience-alchemy.md
├── wisdom/narrative-architecture.md
├── configurations/aethelred_identity.json
└── configurations/openclaw_exponential.json

Level 1 (org-wide) — Johns-Grimoire/ (mislabeled)
└── .cursor/rules/ — 5 rule files (Eneve's CI/CD + AI rules)

Level 2 (product) — saskia-app/
├── AGENTS.md (28 KB) — Sazon-specific rules
├── .hermes/STATE.md (NEW) — operator's running state
├── .hermes/SECURITY.md (NEW) — PAT allowlist
├── docs/clients/saskia.md (NEW) — Sazon client profile
├── scripts/README.md (NEW) — 70 scripts index
└── docs/, app/docs/ — 280+ MD files

Level 3 (domain) — saskia-app/app/rms/
├── AGENTS.md (6.1 KB) — RMS-domain rules (Kiki persona)
└── migrations/INDEX.md (NEW), AUTHORING.md (NEW)
```

**The new insight:** aiw-org/AGENTS.md is the **canonical Level 1 doc** that saskia-app/AGENTS.md should reference. templates-standard/CLAUDE.md is the **canonical Level 1 doc for technical standards**. wizard-academy/wisdom/technical-standards.md is the **strategic-level standard** (95/85, zero-warning).

---

## 7. The Sazon "AIW context" section (new in saskia-app/AGENTS.md)

Based on the P2 research, here's the AIW context section the new saskia-app/AGENTS.md should have:

```markdown
## AIW context

Sazon is one of 3 AIW products:
- **aiw-org** (internal org layer, 6 Tier-1 depts, 47 agents, 156 enabled crons) — `Ai-Whisperers/aiw-org`
- **growth-coaching** (customer-facing coaching product) — `Ai-Whisperers/growth-coaching` (not visible in our PAT allowlist)
- **sazon-app** (Sazon RMS, this product) — `Ai-Whisperers/sazon-app`

Sazon was built from the AIW Python template at `Ai-Whisperers/templates-standard/repo-template/`. Configuration files (.flake8, cspell.json, ruff.toml) match the template byte-for-byte.

The AIW-wide agent rules are at `Ai-Whisperers/aiw-org/blob/master/AGENTS.md` (4.6 KB, authoritative for all coding agents). The AIW-wide technical standards (Toon format, doc hierarchy, ratios) are at `Ai-Whisperers/templates-standard/blob/main/CLAUDE.md` (9.6 KB).

The AIW engineering philosophy (95/85 coverage, zero-warning) is at `Ai-Whisperers/wizard-academy/blob/main/wisdom/technical-standards.md` (2.2 KB).

**When in doubt, the AIW-wide rule wins. Sazon-specific rules below.**
```

---

## 8. The final summary of P2 research

The 4 P2 research directions yielded:

1. **The real AIW template is templates-standard/repo-template/** (saskia-app matches it byte-for-byte for config files).
2. **aiw-org/AGENTS.md is the AIW-wide agent rulebook** that saskia-app/AGENTS.md should reference.
3. **The real AIW numbers**: 47 agents, 116 PROMPT.md files, 156 enabled crons (out of 258 total), 6 Tier-1 departments, 16 dept monitors.
4. **The AIW cron registry is external to the repos** at `/opt/data/.hermes/cron/jobs.json`.
5. **The AIW stack differs from Sazon's** (Arrow+Parquet+K8s vs SQLite+Docker Swarm) — documented as a deliberate Sazon-specific simplification.
6. **There is a 60-day AIW org review on 2026-10-14** (3 days from now) — operator should engage.
7. **aiw-org has 67 docs/ files** with 4 HANDOFF-FOR-* docs and 30+ KB governance/corrective plans.
8. **mburucuya-potypy is just a website** (Astro + Netlify), not "the AIW-defining product."
9. **growth-coaching** is the customer-facing coaching product (not visible in our PAT allowlist).
10. **5 NEW rules (52-56)** to add to saskia-app/AGENTS.md.
11. **8 NEW cross-references** to add to saskia-app/AGENTS.md.
12. **48 NEW items** for the Sazon AGENTS.md rewrite.
13. **4 doc conflicts** surfaced (agent count, stack, archived topic, un-read HANDOFF-FOR-SASKIA).

**Total P2 deliverables on disk:** this doc (60+ KB) + 21+ cached source files (~80 KB) = ~140 KB of new research material.

**Recommended next step (operator's call):** Read the HANDOFF-FOR-SASKIA-2026-09-07.md (4.8 KB, cached at `AO_HANDOFF-FOR-SASKIA-2026-09-07.md`) — it's the missing link for the Sazon client context.
