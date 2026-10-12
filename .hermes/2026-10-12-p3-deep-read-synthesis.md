# Phase 3 deep-read synthesis — 4 HANDOFFs + 12 aiw-org/docs/ + 2 toon-pattern addendum

**Compiled:** 2026-10-12 (post-P2 research, post-update plan)
**Sources:** 4 HANDOFF-FOR-* (28 KB) + 12 aiw-org/docs/ files (125 KB) + 2 follow-up reads
**Method:** full read of every cached file, extract every operational fact

---

## 0. The single most important finding

**The AIW has a real, named, working, ticket-tracked multi-human org with 4 named persons (Ivan + Kiki + John + Saskia-as-hypothetical) and ~5 named AI agent personas (Sunstein + Erebus + Hermes + the dept monitors + tier-specific agents).** The 4 HANDOFF-FOR-* files are a snapshot of the **2026-09-07 Drive governance audit**, which identified 24 items across 4 humans. Sazon's AGENTS.md (Kiki persona) is one of the 116 PROMPT.md files, but **Sazon is NOT a Tier 1-2-3 deployment** — Sazon is a **custom product built from the AIW Python template**.

The 12 aiw-org/docs/ files reveal the **AIW's complete operating system** for the org layer. The Sazon project **should reference this**, not duplicate it.

---

## 1. The 4 humans + 5+ AI personas

### 1.1 Humans (per HANDOFF-FOR-* + RACI-2026-09-07)

| Human | Role | AIW name | Items in audit | Status |
|---|---|---|---|---|
| **Ivan** | CEO + Founder | Iván (Spanish) | **11 items** (Ivan-A to Ivan-K) | Co-signs Domain Model + Sprint 1 + product boundaries + M4 + DD-O series |
| **Kiki** | Co-Founder + Tech Director | "Kyrian" | **8 items** (Kiki-A to Kiki-D + 4 extras) | Owns disposition sign-offs, dept REVIEW.md reconciliation, marketing/sales/product discovery |
| **John** | Human Product Owner | John van der Pol | **3 items + 1 blocker** (John-A to John-C) | Owns Domain Model + Sprint 1 + PRODUCT-BOUNDARY ratification + nl-direct-sales-motion |
| **Saskia** | Hypothetical end-user (not Sazon) | Saskia (hypothetical) | **1 item** | Answers 8 questions about restaurant instance; this is a DESIGN exercise, not a Sazon client |

**Name collision alert**: "Kiki" the human co-founder = "Kiki" the Sazon AI agent persona. **They are different entities.** The Sazon agent is the AIW's Sazon-orchestrator; the human is the AIW's co-founder. Don't conflate.

### 1.2 AI personas (per ORG-AGENTS.md + dept files + handoffs)

| Persona | Repo | Role | Evidence |
|---|---|---|---|
| **Sunstein** | aiw-org (autonomous ops) | Drafts HANDOFFs, drafts DEMIURGE ticket proposals, autonomous | HANDOFF-FOR-* signature lines |
| **Erebus** | aiw-org (autonomous) | Repo consolidation (2026-08-23) | CONSOLIDATION-REPORT.md byline |
| **Hermes Agent** | aiw-org (autonomous) | Corrective action plan, eval gates, kanban | CORRECTIVE-ACTION-PLAN byline |
| **Aethelred / Merlin / Nyx** | wizard-academy | Methodology research | wizard-academy/AGENTS.md |
| **Kiki** (AI agent) | saskia-app | Sazon orchestrator | saskia-app/AGENTS.md |
| **The 47 dept agents** | aiw-org | Tier 1-3 lead/sub agents | ORG-AGENTS.md |
| **The 16 dept monitors** | aiw-org/dept-monitors | Heartbeats every 30 min | dept-monitors/INDEX.md |

**There is no "main AI agent" at AIW — it's a multi-agent mesh with Sunstein as the autonomous ops agent for Ivan.** The Sazon's "Kiki" is a single-agent persona for a single product.

---

## 2. The 8 questions to Saskia (HANDOFF-FOR-SASKIA)

These are the **canonical questions for any new AIW client instance**. Sazon has answers baked in. The questions are:

1. **Goal**: What does the restaurant want from an AIW instance?
2. **Activity**: What activities does the restaurant do daily/weekly?
3. **Hosting**: Where will the AIW instance live (VPS, local, hybrid)?
4. **Integrations**: What existing systems need to connect (POS, accounting, supplier)?
5. **Data access**: What data sources can the AIW read?
6. **Action approval**: What actions require human approval before execution?
7. **Manager authority**: Who has final authority on decisions?
8. **Language/digest/pause/export**: Communication preferences?

**For Sazon**: goal=operations automation, activity=production+inventory+sales, hosting=VPS, integrations=WhatsApp+basic accounting, data access=products+sales+stock, action approval=HIGH/CRITICAL needs Iván (now uses Sazon-specific approval tiers), manager authority=Iván, language=Spanish (Asunción PY).

---

## 3. The AIW-wide product list (PRODUCT-BOUNDARY.md, 3.4 KB)

| # | Product | Audience | Pricing signal |
|---|---|---|---|
| **P1** | **GROW coaching for individuals** (kiki-coach + coach-ivan + growth-coaching repo) | Founders & professionals in PY/EU | Coaching pricing skill: S/M/L tiers (₲90K-900K) |
| **P2** | **Hermes deployment + org layer for small org** (2-10 person) | 2-10 person organizations (PY-first) | client-vps-provisioning / hermes-vps-onboarding skills |
| **P3** | **Civic-tech data products (Paraguay)** (paragu-ai.com subdomains) | Journalists, NGOs, researchers | paraguai-civictech skills |
| **P4** | **Research/analysis as a service** (multi-stage research) | Thesis-adjacent clients, partners | market-deep-research-brief skill |

**Sazon is NOT in the product list.** Sazon is a custom product — like a Tier 3 (47 agents, 16 depts) deployment configured for a single bakery. The 3 tooling tiers in TOOLING-TIERS.md are the SKU pattern that Sazon doesn't fit; Sazon is closer to **P2 + a heavy custom config + 2-3 Tier 3 departments enabled for a single client**.

**Implication for saskia-app/AGENTS.md**: don't claim Sazon is a "P2 deployment"; rather, document Sazon as **"P2 deployment with custom Tier 3 extensions (production planning, recipe instructions, stock movements) for a single client (Saskia Weiss Vander / La Vaquita Holandesa)"**.

---

## 4. The 24-item audit summary (RACI-2026-09-07)

| Section | Owner | Items | Status |
|---|---|---|---|
| **A. Professional Reviewer (external)** | PR | 2 (PR-A tax, PR-B LATAM regulatory) | drafted · awaiting referral send |
| **B. Ivan** | Ivan | 11 (Ivan-A to Ivan-K) | mostly pending · 3 BLOCKED |
| **C. John** | John | 3 + 1 blocker (John-A to John-C, nl-direct-sales-motion missing) | mostly pending · LATAM BLOCKED |
| **D. Kiki** | Kiki | 8 (Kiki-A to Kiki-D + 4 extras) | mostly pending · 3 sign-only |
| **E. Saskia** | Saskia (hypothetical) | 1 (8 questions) | drafted · awaiting Ivan to send channel |
| **F. ADR-STD-001** | Ivan + Kyrian + John | 1 (standards decision) | pending · Open Q #1 must close first |
| **G. Disposition sign-offs** | Ivan + Kiki | 6 (DISP-2026-001..006) | drafted · awaiting sign |
| **H. Dept REVIEW.md reconciliation** | Kiki + Ivan | 3 (Marketing/Sales/Product Discovery) | pending · reconciliation work |
| **I. Missing files** | Sunstein | 8 (LATAM/REVIEW.md files) | BLOCKED · file absent |

**Total: 24 items, 14 existing tickets, 10 NEW tickets (DEMIURGE-213..222), 2 BLOCKED, 6 dispositions awaiting sign, 1 Saskia direct input, 13 items needing Sunstein execution after owner sign, 2 external professional reviewer, 8 missing files.**

**The 10-step critical path** (RACI §K): DEMIURGE-200+201 (CI fixes) → 164 (DISP-LOG) → 183 (trademark banlist) → 211 (sales funnel deploy) → 176 (M4 decision) → 187-191 (5 missing LATAM files) → 008+015 (Ivan+John gates) → 193+194 (PR referrals) → 192 (Saskia send) → 181 (ADR-STD-001 acceptance).

---

## 5. The 6 epics + 41 stories (CORRECTIVE-ACTION-PLAN-2026-09-04)

| Epic | Title | Stories | Tickets | Timeline | Owner |
|---|---|---|---|---|---|
| **E-CI** | CI Green + Hermetic Test Suite | 7 | DEMIURGE-126..131 (+ 099 existing) | First 48h | AI + Ivan |
| **E-PORT** | Path Portability + Deployment Contract | 5 | DEMIURGE-132..138 (+ 098 existing) | First week | AI + Ivan |
| **E-SAFE** | Enforced Safety + Self-Improvement Truth | 6 | DEMIURGE-115, 139..143 | First week | AI + Ivan |
| **E-OBS** | Observability over Self-Improvement | 4 | DEMIURGE-159..162 | Week 1-2 | AI |
| **E-CRON** | Cron Fleet Reliability + Cost Truth | 6 | DEMIURGE-144..147 (+ 113, 121 existing) | First 2 weeks | AI + Ivan |
| **E-PROD** | Product Ownership + Org Discipline | 7 | DEMIURGE-148..154 | First 2 weeks | Ivan + AI |
| **E-EVID** | Evidence Maturity + Process Reset | 6 | DEMIURGE-155..158 (+ 096, 108 existing) | Weeks 3-4 | AI + Ivan |

**Total: 41 stories, 33 NEW tickets (DEMIURGE-126..158), 8 Ivan-gated decisions (DEMIURGE-115, 136, 148, 149, 150, 152, 157, 158).**

**The 15 operating rules (CAP §6) — the AIW's "no X without Y" principles**:

1. No green baseline, no feature merge.
2. No consumer, no agent or monitor.
3. No measured source, no precise cost claim.
4. No executable gate, no safety claim.
5. No closed feedback loop, no self-improvement claim.
6. No clean-root test, no portability claim.
7. No direct approval, no requirements attributed to another person.
8. No human owner, no strategic agent delegation.
9. No repeated successful operation, no "complete."
10. No deployment contract, no copied runtime script.
11. No generated inventory, no hand-maintained headline count.
12. No WIP limit, no new workstream.
13. No dated evidence, no timeless operational fact.
14. No pre/post evaluation, no retained automated prompt change.
15. No explicit retirement condition, no recurring job.

**Sazon can adopt all 15 verbatim** — they're AIW-agnostic, product-agnostic. Add them as Rule 52-66 in saskia-app/AGENTS.md.

---

## 6. The 3 tooling tiers (TOOLING-TIERS.md, 27 KB)

| Tier | Employees | Agents | Depts | Price (USD/mo) | Price (PYG/mo) |
|---|---|---|---|---|---|
| **Tier 1 (Micro)** | 1-5 | 4 + 2 monitoring | 3 (finance, sales, operations) | $250 | ₲ 1.8M |
| **Tier 2 (Small)** | 5-20 | 12 + 2 monitoring | 6 (+ marketing, research, people/HR) | ~$2K | ~₲ 14M |
| **Tier 3 (Medium)** | 20+ | 47 + monitoring | 16 (full AIW equivalent) | $2K+ | ₲ 14M+ |

**Tier 1 agents (4 functional + 2 monitoring)**:
- finance: `business-analyst` (daily 06:30 PYT)
- sales: `sales-pipeline` (daily 12:00 PYT) + `lead-enrichment` (daily 09:30 PYT)
- operations: `ai-ops-coordinator` (daily 08:00 PYT)
- monitoring: `devops-monitor-30min` + `ai-safety-engineer-30min`

**Tier 2 additions (8 more)**: accounting-automation, tax-receipt-tracker, proposal-drafter, revops-pipeline-analyzer, marketing-content, multimedia-producer, research-tracker, source-curator, bizops-tracker, procurement-tracker, people-hr.

**Excluded from Tier 1**: marketing dept, research dept, people/HR, legal/compliance deep-work, board/coaching/multimedia, custom-domain Worker+R2, multi-tenant SSO.

**Trilingual**: ES primary, EN secondary, NL available.

**Setup fee**: ₲ 1.8M / € 350 / $ 250 one-time, applied against month-1.

**30-day self-running declaration**: 0 cron errors in 30d window + 0 "is X live?" messages.

**Sazon's tier mapping**: Sazon is closest to **Tier 2 (Small)**, but with custom Tier 3 extensions (production-planning, recipe-instructions, stock-movements) for a single client. Sazon is NOT a generic SMB deployment.

---

## 7. The AIW-wide tech stack (TOOLING-TIERS + AIW-AGENTS + PRIORITIZED-WHATS-NEXT)

| Component | AIW default | Sazon reality | Why different |
|---|---|---|---|
| **LLM provider** | MiniMax-M3 (94% of spend) + MiniMax-M2.7-highspeed + MiniMax-M2.7 | MiniMax-M3 (per system prompt) | Same |
| **LLM routing** | LiteLLM proxy + 4 sub-keys | Direct API call (per system prompt) | Sazon is single-user, not multi-tenant |
| **Data store** | Arrow + Parquet + Polars (per templates-standard/CLAUDE.md) | SQLite + JSON | Single bakery, not multi-org |
| **Deploy** | Docker + Kubernetes on-prem (per templates-standard/CLAUDE.md) | Docker Swarm + single VPS | Single instance, no K8s needed |
| **Cron** | Host-based `/opt/data/.hermes/cron/jobs.json` (258 jobs) | Host-based + Python `schedule` module | Smaller scope, same pattern |
| **Tickets** | DEMIURGE-### (Drive-based) | SASKIA-### (in-repo) | Sazon tracks in git; AIW tracks in Drive |
| **Spec layer** | `tickets/DEMIURGE-XXX/plan.md` | `docs/operations/YYYY-MM-DD-NAME.md` | Different naming, same pattern |
| **Execution layer** | Hermes kanban + 42 subcommands | git branches + pytest | Different tool, same pattern |
| **Truth layer** | PR with conventional commit + local-verified evidence | PR with conventional commit + local-verified evidence | Same |
| **Hard stops** | `hard-stops-wrapper.py` (declared but not enforced, MAA-2) | `app/rms/main.py` PRO-SEC guard (deployed & enforced, Rule 9) | **Sazon is MORE advanced** |
| **Eval gate** | `eval-gate.py` (per PHASE-10-EVAL-GATE-POC.md) | `pytest --cov` with 40% gate | Sazon uses test coverage as eval gate |
| **Trademark scrub** | `trademark-scan.py` per pre-commit | None yet | Sazon doesn't have customer-facing content yet |

**Sazon's PRO-SEC guard (Rule 9) is MORE advanced than AIW's hard-stops-wrapper (MAA-2 HIGH residual risk)**. The AIW's `hard-stops-wrapper.py` is declared in 34/34 PROMPTs but 0 agents invoke it (MAA-2). Sazon's PRO-SEC guard is in the runtime path and enforced.

---

## 8. The 5 threat actors + 7 assets + 7 threats (THREAT-MODEL.md)

| Threat actor | Profile | Likelihood | Impact |
|---|---|---|---|
| T-1 | External script kiddie | High (volume) | Medium |
| T-2 | External targeted | Low | High |
| T-3 | Insider contractor | Medium | Medium |
| T-4 | Insider founder | Medium (accidents) | High |
| **T-5** | **Compromised agent (Kiro-class)** | Medium | High |

| Asset | Sensitivity | Threats |
|---|---|---|
| A-1 | State files (`/opt/data/agents/state/*.json`, `/opt/data/db/*.db`) — High (commercial secrets) | T-1, T-2, T-3, T-5 |
| A-2 | Per-agent git repos (`/opt/data/git-repos/aiw-agents-*`) — Medium | T-1, T-2 |
| A-3 | Source materials (`/opt/data/source-materials/`) — Medium-High (IP) | T-1, T-2, T-3 |
| A-4 | Credentials (`/opt/data/.env`, `/opt/data/.gh_token`) — Critical | T-1, T-2, T-3, T-5 |
| A-5 | Customer data (client repos, leads) — Critical (PII) | T-1, T-2, T-3, T-5 |
| A-6 | Cron jobs (`/opt/data/.hermes/cron/jobs.json`) — Medium | T-1, T-2, T-5 |
| A-7 | Agent layer (`/opt/data/agents-v2/`) — Medium | T-1, T-2, T-5 |

| Threat | Defense | Residual risk |
|---|---|---|
| TH-1 | Prompt injection → external send. Hard stops AFTER LLM output, BEFORE action. | Low |
| TH-2 | Hard stop bypass via tool chaining. All write_data to external DBs requires approval. | Medium |
| TH-3 | GitHub token leak via agent. `.gitignore` + pre-commit secret-leak-check.sh (TODO). | Medium |
| TH-4 | State file tampering. `chmod 600`, SQLite WAL, snapshot diff, audit log. | Low |
| TH-5 | Cron job injection via jobs.json. `chmod 600`, backup cron, manual review. | Medium |
| TH-6 | DoS via expensive agent run. cost-cap.sh hourly, $1/agent, $10 total daily. | Low |
| TH-7 | Trademark infringement attack. trademark-scrub.sh + pre-commit hook. | Low |

**Addendum A — Multi-Agent Attack Surface**:
- MAA-1: Atomic agent compromise via composition chain. Defense: 4-agent max composition, argus-health-monitor.
- **MAA-2: Hard-stops wrapper enforcement gap. 34/34 PROMPTs declare, 0 invoke. Residual: HIGH.**
- MAA-3: Frontmatter-as-attack-vector. Defense: lint-prompts.py + git diff visibility.
- MAA-4: Cron job prompt injection. Defense: pre-commit cron-guard + sha256 sync.
- **MAA-5: Cross-repo leak vectors. `/opt/data/work/research-repos/*/.env` (P5), `/opt/data/scratchpad/*/.env` (P7), `/opt/data/.git/config` (P8). Defense: .gitignore L2.3 (96% match), security-watchdog-30min. Residual: Medium-High. Operator action: revoke 3 GitHub PATs.**
- MAA-6: AI agent prompt-injection at scale. Defense: hard_stops in PROMPTs + L1 security-watchdog.

**For Sazon**: T-1, T-2, T-3 are LOW priority (single bakery, no public exposure). T-4 (insider founder) and T-5 (compromised agent) are HIGHER priority for Sazon. Sazon's PRO-SEC guard handles T-5 well.

---

## 9. The ~136 roles (ROLES-INVENTORY.md)

**Tier 1 active (36 roles)**: Operations Lead, Repo Steward, Asset Tracker, Vendor Coordinator, Compliance Watchdog, Watchdog Engineer, CFO, Bookkeeper, Procurement, Legal Counsel, Compliance Officer, Tax, Contract Drafter, Pricing Analyst, CRO, SDR, AE, Proposal Writer, Marketing Manager, CTO, Frontend, Backend, Full-stack, DevOps, QA, Security, AI Safety Engineer, Research Lead, Researcher, Writer, Citation Specialist, Course Designer, Head of People, Performance Coach, Recognition Lead, AI Ops Lead, Compliance Officer (duplicate?), Trademark Specialist, Knowledge Manager (?), AI Safety Engineer (duplicate?), CSM Lead (?).

**Trademark-restricted roles** (can't be sold as Tier 1-2 features due to Hostinger-class incident):
- 3.10 Performance Marketing Manager
- 3.13 Social Media Manager

**Sazon has the equivalent of these roles (mapped from saskia-app)**: Operations Lead = Kiki agent, Bookkeeper = invoice system, Pricing Analyst = product pricing, CRO/SDR/AE = WhatsApp order intake, Marketing Manager = no, Compliance Officer = Rule 9 PRO-SEC guard, AI Safety Engineer = Rule 8 (no agent_target bypass), Researcher = audit logs.

**Sazon has ~10-15 active "roles" mapped to AI agents + features**, which is comparable to a Tier 1 (Micro) deployment with 4 functional + 2 monitoring = 6 agents, but with extra custom features (production planning, recipe instructions).

---

## 10. The 47-agent roster + 156 cron jobs (from aiw-org/README + ORG-AGENTS)

| Dept | Tier 1 lead | Tier 2 sub | Tier 3 cross-cutting |
|---|---|---|---|
| **01-operations** | ai-ops-coordinator, bizops-tracker, compliance-monitor, founder-bandwidth-watchdog, ops-management-monitor | 4 more | + dept-monitor |
| **02-finance-legal** | accounting-automation, business-analyst, finance-controller, funding-coordinator | 2 more | + dept-monitor |
| **03-sales-growth** | lead-enrichment, marketing-content-producer, multimedia-producer, proposal-drafter, revops-pipeline-analyzer, sales-pipeline | 3 more | + dept-monitor |
| **04-engineering** | ai-safety-engineer, chaos-test-runner, delivery-tracker, devops-monitor, engineering-management-monitor, eval-gate-runner | 8 more | + dept-monitor |
| **05-research-education** | academic-liaison, citation-checker, course-producer, instructional-designer, research-management-monitor, research-tracker, source-curator | 5 more | + dept-monitor |
| **06-people-culture** | people-hr | 0 | + dept-monitor |
| **Total agents** | **~25** | **~22** | **+ 6 dept-monitors** |

**Crons**: 156 enabled / 258 total / 102 disabled (per README; 79 crons was my prior number from CONVERGE-gate doc).

**Cost**: $1,370/mo ($1,185 interactive + $128 cron + buffer). Target: $1,200/mo. Recommended: MiniMax-M3 Pro at $200/mo (saves $1,063/mo).

**Sazon's 6 dept monitors equivalent**: not a 1:1 mapping. Sazon has 0 monitors (no cron jobs); the dept monitors pattern is AIW-specific. But the principle ("agent that monitors a department, not executes the work") is a Sazon-relevant pattern for future cron adoption.

---

## 11. The 16 dept monitors (dept-monitors/INDEX.md, 6.9 KB)

| Dept | Folder | Watched state files | Metrics | Cron |
|---|---|---|---|---|
| 01-operations | operations/dept-monitor | state/org-state.json, state/coord.json | org-state mtime, cron errors, blockers | */15 * * * * |
| 02-finance-legal | finance/dept-monitor | state/pipeline-value.json, state/deferred-revenue.json | pipeline value, deal stages, contacts | */30 * * * * |
| 03-sales-growth | sales/dept-monitor | state/sales-funnel.json, state/lead-pipeline.json | leads, conversion, stalled deals | */30 * * * * |
| 04-engineering | engineering/dept-monitor | state/cron-health.json, state/build-status.json | cron health, CI, deploys | */30 * * * * |
| 05-research-education | research/dept-monitor | state/research-pipeline.json, state/citations.json | publications, citations, deadlines | */30 * * * * |
| 06-people-culture | people/dept-monitor | state/people-pipeline.json | hiring, onboarding, comp | */30 * * * * |
| board-of-directors | board/dept-monitor | state/board-minutes.json | meeting cadence, decisions | */30 * * * * |

**Plus 10 more domain-specific monitors** (per aiw-org/OPERATIONS.md): board-monitor, funding-monitor, lead-enrichment-monitor, marketing-monitor, multimedia-monitor, okr-tracker-monitor, procurement-monitor, qa-monitor, research-monitor, source-curator-monitor, thesis-tracker-monitor, chaos-test-runner-monitor, devops-monitor-tick, domain-monitor-tick, eval-gate-runner-monitor, founder-bandwidth-watchdog-monitor, finance-accounting-monitor, bizops-tracker-monitor, coaching-monitor, course-producer-monitor, corrective-kanban-workflow, people-hr-monitor, ai-safety-engineer-monitor, legal-compliance-monitor, sales-monitor, engineering-monitor, cron-fleet-governance-audit, management-monitor, ops-monitor, revops-pipeline-analyzer-monitor.

**For Sazon**: the dept-monitor pattern is the AIW's "agent that monitors a department, not executes the work" pattern. Sazon could adopt it as a single Sazon-health-monitor that watches: app uptime, DB size, last migration, deploy timestamp, CI status, env parity (prod vs test vs dev).

---

## 12. The data boundary (SECURITY-DATA-BOUNDARY.md, GLD-16, 2.1 KB)

| Tier | Workload | Allowed surfaces |
|---|---|---|
| **T1 LOCAL-ONLY** | Patient-identifiable data, clinical, NDA-restricted | Jan / local weights / client-on-prem |
| **T2 CLOUD-PLAN** | Operational + content: SEO, marketing, research, code | Paid flat plans (zai, MiniMax when provisioned) |
| **T3 NEVER-ANYWHERE-FREE** | Credentials, auth, client-identifying datasets | Paid surfaces only |

**Rules**:
1. Default when in doubt: T1
2. Free-tier routing: dual-run sidecars may carry only synthetic/public fixtures
3. Bench fixtures (`eval/bench/`): synthetic only
4. **Prompts are a data surface**: job prompts referencing client names/PII make that job T1
5. Vendor terms gate: NOASSERTION-license or unaudited-terms surfaces are T3

**For Sazon**: Sazon's data is T1 (La Vaquita Holandesa's customer data, supplier data, pricing data is PII / commercial secrets). Sazon should be served by **T2 (paid cloud) only for the LLM API calls**, not for the data itself. The data lives on the VPS (local), with backup to a separate VPS (local). LLM API calls are T2.

---

## 13. The self-running milestone (SELF-RUNNING-CRITERIA.md, 3.9 KB)

**Definition (per OP-4)**: A self-running org has:
1. All 7 Tier-1 lead agents deliver reliably for 7+ consecutive days
2. 0 cron jobs in error state for the same period
3. 0 "is X live?" messages from Ivan in any 7-day window

If all three hold for 7 days, the org is **self-running at v0.2.0**.

**Required deliveries in 7 days (21 total)**:
- business-analyst: daily 06:30 PYT → 7
- management-coordinator: Mon+Thu 17:00 PYT → 2
- kiki-coach: Fri 17:00 PYT → 1
- finance-controller: Fri 18:00 PYT → 1
- sales-pipeline: daily 12:00 PYT → 7
- engineering-roster: Tue+Fri 17:00 PYT → 2
- research-tracker: Sun 18:00 PYT → 1

**5 things that break self-running**:
1. LLM rate limit → all agents pause
2. Cron job in error → 1+ jobs miss delivery
3. Hard-stop blocks action → Ivan intervenes
4. Cost cap breach → agents halt
5. State corruption → recovery takes time

**Current state (2026-08-14)**: NOT-YET. 6/7 agents deliverable. 4 cron errors. 3 P0 gaps. **Target: 7-day self-running by 2026-09-15 (PAST, 30 days ago).**

**For Sazon**: the "is X live?" question is the operator's #1 frustration. Sazon should adopt a self-running check: "has the operator sent 'is Sazon live?' to chat in the last 7 days? If 0, the system is self-running." This is Rule 67 candidate.

---

## 14. The token plan (TOKEN-PLAN-OPTIONS-2026-09-21.md, 8 KB)

| Sub-key | Status | Budget | RPM | Models |
|---|---|---|---|---|
| `aiw-internal-coach-kiki` | active | $50 | 60 | primary, fast, reasoning |
| `aiw-internal-coach-ivan` | active | $100 | 120 | primary, fast, reasoning, vision |
| `aiw-internal-agents-default` | active | $200 | 300 | primary, fast, reasoning, vision |
| `aiw-internal-evals` | active | $75 | 90 | primary, reasoning |
| **Total allocated** | | **$425/mo** | | |

**5 model aliases**:
- primary → MiniMax-M3 (workhorse, 94% of spend)
- fast → MiniMax-M2.7-highspeed
- reasoning → MiniMax-M2.7
- vision → MiniMax-M3 (tool calling)
- placeholder: anthropic-claude, codex, deepseek, glm, qwen

**Current spend**: $1,370/mo ($1,185 interactive + $128 cron). **Target: $1,200/mo. Recommended: MiniMax-M3 Pro at $200/mo (Option 1) → reduces to $250/mo (81% reduction).**

**77 enabled cron jobs** assigned:
- 47 → MiniMax-M3 (primary, $0.005/call)
- 15 → MiniMax-M2.7-highspeed (fast, $0.002/call)
- 15 → MiniMax-M2.7 (reasoning, $0.004/call)

**For Sazon**: the "primary/fast/reasoning" model aliasing pattern is a Sazon-relevant pattern. Sazon uses just "primary" (MiniMax-M3) today; could add "fast" for routine queries to save cost.

---

## 15. The repo consolidation (CONSOLIDATION-REPORT.md, 4.9 KB)

**3 AIW operational repos** (decision 2026-08-23):
- **`agents-v2`** (private, canonical): 24 PHASE reports, 49 agents, constitution, scripts
- **`agents`** (public, legacy): Tier 1/3/4 + MCP upgrade reports, frozen
- **`state-versioned`** (private, runtime): auto-committed every 5min, contains org-state, customers, cost, errors

**Why 3, not 1**: different access patterns (org-internal vs public-archive vs runtime), different update cadences (PR vs frozen vs cron), different review policies (PR-required vs none vs auto-push).

**What was NOT done**: NousResearch/hermes-agent (3634 commits behind), Company-Information (archived), personal repos.

**For Sazon**: saskia-app is the equivalent of `agents-v2` (canonical, private). Sazon doesn't need a public-archive (`agents`) or a runtime state-versioned repo, because the data is in SQLite and the state is small.

---

## 16. The 10 "what NOT to change" (CORRECTIVE-ACTION-PLAN §7)

1. ✅ Keep the six-department freeze (DD-02)
2. ✅ Keep separating aiw-org, growth-coaching, coach-agents, state-versioned
3. ✅ Keep using ADRs and explicit locked/open decisions
4. ✅ Keep auditing downstream damage after incidents
5. ✅ Keep closing bad branches rather than merging for activity credit
6. ✅ Keep reverting changes when evidence disproves them
7. ✅ Keep deleting unwired code that creates false confidence
8. ✅ Keep distinguishing internal human-in-the-loop from future client-grade autonomy
9. ✅ Keep the David Ondrej analysis bounded to content strategy (not engineering validation)
10. ✅ Keep the Saskia design as a disposable hypothesis (do not implement without consent)
11. ✅ Keep the kernel as a future direction (do not build until a second instance proves the need)

**For Sazon**: items 8, 10, 11 are directly Sazon-relevant. Sazon is **internal human-in-the-loop** (Iván approves HIGH/CRITICAL). The hypothetical "Saskia instance" in HANDOFF-FOR-SASKIA is a **disposable hypothesis** (do not implement without consent). The "kernel" idea (DEMIURGE-174, kernel-vs-Project architecture) is **deferred** — Sazon doesn't need it until a second client proves the need.

---

## 17. The 8 questions per HANDOFF-FOR-SASKIA + Sazon's answers

| Q | Question | Sazon's answer |
|---|---|---|
| 1 | Goal | Bakery operations automation (production, inventory, sales) |
| 2 | Activity | Daily: take WhatsApp orders, update stock, bake production. Weekly: reconcile accounts, plan next week. Monthly: review prices, supplier orders. |
| 3 | Hosting | VPS (Servarica, 8GB/2-core), Docker Swarm, 3 envs (prod, test, dev) |
| 4 | Integrations | WhatsApp Business (Evolution API), basic accounting (CSV exports), Google Drive for invoices |
| 5 | Data access | Products (161), recipes (161), ingredients (271), sales (real + synthetic), suppliers (4-5), prices (PY 2026) |
| 6 | Action approval | HIGH/CRITICAL require Iván (Sazon Rule 7); LOW auto-approve; demo mode requires admin login (Rule 9) |
| 7 | Manager authority | Iván = sole authority for production-affecting changes; Kiki agent = orchestrator for routine operations |
| 8 | Language/digest/pause/export | Spanish (Asunción PY), no daily digest (operator-driven), no scheduled pause (Sazon is interactive), export to CSV/PDF for accounting |

---

## 18. NEW items for saskia-app/AGENTS.md (Phase 3 adds)

### 18.1 NEW rules (52-66)

Based on Phase 3 deep-read:

- **Rule 52**: The 15 AIW operating rules (no X without Y) — adopt verbatim
- **Rule 53**: The dept-monitor pattern (agent that monitors, not executes) — relevant for future Sazon cron adoption
- **Rule 54**: The "is X live?" metric — Sazon self-running check (0 messages in 7 days)
- **Rule 55**: T1/T2/T3 data boundary (GLD-16) — Sazon data is T1, LLM calls are T2
- **Rule 56**: Trademark banlist scrub — required for any customer-facing content (Rule 56: Sazon doesn't have customer-facing content yet, but Rule applies when it does)
- **Rule 57**: The 5 things that break self-running (LLM rate limit, cron error, hard-stop, cost cap, state corruption) — Sazon-relevant
- **Rule 58**: The 30-day self-running window — Sazon's 6-of-6 done pattern is the same (30 days, 0 breaks)
- **Rule 59**: The hard-stops-wrapper enforcement gap (MAA-2) — Sazon's PRO-SEC guard is the answer
- **Rule 60**: MAA-5 cross-repo leak vectors — applies if Sazon work touches research-repos or scratchpad
- **Rule 61**: The "prompts are a data surface" rule (GLD-16 R4) — job prompts referencing client names make that job T1
- **Rule 62**: The "Kiri-class" agent threat (T-5) — Sazon's PRO-SEC guard is the defense
- **Rule 63**: The converge gate (2x consecutive green: pytest + readme-counts + lint-prompts + restore-prompt-bodies) — Sazon's "6 of 6 done" is a simplified version
- **Rule 64**: The "stability window after infrastructure PRs" (DEMIURGE-157) — 24h freeze after schema/deploy/infrastructure changes
- **Rule 65**: The "Saskia design as disposable hypothesis" (CAP §7 item 10) — Sazon is the only client; don't build a "Saskia instance" without consent
- **Rule 66**: The 8 questions per HANDOFF-FOR-SASKIA — Sazon's answers are the canonical instance design

### 18.2 NEW cross-references

| Refers to | Path | Use |
|---|---|---|
| aiw-org/AGENTS.md | `https://github.com/Ai-Whisperers/aiw-org/blob/master/AGENTS.md` | AIW-wide single authoritative rulebook |
| aiw-org/ORG-AGENTS.md | `https://github.com/Ai-Whisperers/aiw-org/blob/master/ORG-AGENTS.md` | 47-agent matrix, producer-consumer map |
| aiw-org/dept-monitors/INDEX.md | `https://github.com/Ai-Whisperers/aiw-org/blob/master/dept-monitors/INDEX.md` | 16 dept-monitor pattern |
| aiw-org/docs/RACI-2026-09-07.md | `https://github.com/Ai-Whisperers/aiw-org/blob/master/docs/RACI-2026-09-07.md` | 24-item approval register |
| aiw-org/docs/THREAT-MODEL.md | `https://github.com/Ai-Whisperers/aiw-org/blob/master/docs/THREAT-MODEL.md` | AIW-wide threat model (5 actors, 7 assets, 7 threats) |
| aiw-org/docs/SECURITY-DATA-BOUNDARY.md | `https://github.com/Ai-Whisperers/aiw-org/blob/master/docs/SECURITY-DATA-BOUNDARY.md` | T1/T2/T3 data boundary |
| aiw-org/docs/SELF-RUNNING-CRITERIA.md | `https://github.com/Ai-Whisperers/aiw-org/blob/master/docs/SELF-RUNNING-CRITERIA.md` | self-running milestone definition |
| aiw-org/docs/PRODUCT-BOUNDARY.md | `https://github.com/Ai-Whisperers/aiw-org/blob/master/docs/PRODUCT-BOUNDARY.md` | 4-product list (Sazon is custom) |
| aiw-org/docs/TOOLING-TIERS.md | `https://github.com/Ai-Whisperers/aiw-org/blob/master/docs/TOOLING-TIERS.md` | 3-tier deployment packages |
| aiw-org/docs/CORRECTIVE-ACTION-PLAN-2026-09-04.md | `https://github.com/Ai-Whisperers/aiw-org/blob/master/docs/CORRECTIVE-ACTION-PLAN-2026-09-04.md` | 6 epics, 41 stories, 15 operating rules |
| templates-standard/CLAUDE.md | `https://github.com/Ai-Whisperers/templates-standard/blob/main/CLAUDE.md` | AIW-wide standards doc (Toon, data stack, deploy) |
| templates-standard/repo-template/ | `https://github.com/Ai-Whisperers/templates-standard/tree/main/repo-template` | The AIW Python template saskia-app was built from |

### 18.3 NEW context to capture in saskia-app/AGENTS.md

The top section should add a "**AIW context**" with:
- Sazon is built on `templates-standard/repo-template/` (byte-for-byte match for .flake8, cspell.json, ruff.toml)
- Sazon follows the AIW patterns in `aiw-org/AGENTS.md` (the AIW-wide single authoritative rulebook)
- Sazon adopts the 15 AIW operating rules (CAP §6) as Rules 52-66
- Sazon's data tier is T1 (per GLD-16); LLM calls are T2
- Sazon's "self-running" definition: 0 "is X live?" messages in 7 days
- Sazon's PRO-SEC guard is more advanced than AIW's MAA-2 (declared but not enforced)
- The 4-tier-1 lead agents equivalent in Sazon: business-analyst, sales-pipeline, lead-enrichment, ai-ops-coordinator (Kiki is the AI-ops-coordinator)
- The 6-dept-monitor pattern: Sazon could adopt a single Sazon-health-monitor

### 18.4 NEW doc conflicts surfaced by Phase 3

| Conflict | Document A | Document B | Resolution |
|---|---|---|---|
| **Cron registry location** | aiw-org/AGENTS.md says `/opt/data/.hermes/cron/jobs.json` | aiw-org/dept-monitors/INDEX.md has 16 monitors | Same; both are host-based, not in repo |
| **AIW agent count** | aiw-org/README says 47 agents + 156 enabled crons | aiw-org/ORG-AGENTS.md says 28 + 46 + 116 PROMPT.md | 47 is lead+sub, 116 is PROMPT.md count, both correct |
| **Standard count** | aiw-org/AGENTS.md + templates-standard/CLAUDE.md: Toon + 17 standards stack | aiw-org/docs/TOOLING-TIERS.md doesn't reference | Toon is the format, 17 standards is the data taxonomy |
| **Saskia as client** | Sazon's `app/rms/AGENTS.md` says "Saskia = THE client" | aiw-org/HANDOFF-FOR-SASKIA.md says "Saskia = hypothetical end-user" | Name collision; Sazon's Saskia = La Vaquita Holandesa owner; AIW's hypothetical Saskia = restaurant instance design |
| **Kiki persona** | saskia-app/AGENTS.md: Kiki = Sazon orchestrator AI | aiw-org/HANDOFF-FOR-KIKI.md: Kiki = human co-founder (Kyrian) | Different Kiki's; document both in saskia-app/AGENTS.md as "Kiki (Sazon) ≠ Kiki (human co-founder)" |
| **Product list** | aiw-org/docs/PRODUCT-BOUNDARY.md: 4 products, Sazon not listed | saskia-app/AGENTS.md: Sazon is a "product" | Sazon is a custom Tier 2-3 deployment, not in the 4-product SKU list; document as "custom instance" |
| **Hard stops enforcement** | aiw-org/THREAT-MODEL.md: 34/34 declare, 0 invoke (MAA-2 HIGH) | saskia-app/AGENTS.md: PRO-SEC guard deployed & enforced | Sazon is AHEAD of AIW on this; document as Sazon's contribution |
| **Threat model scope** | aiw-org/THREAT-MODEL.md: AIW agent layer only, NOT customer-facing | saskia-app/AGENTS.md + docs/threat-model.md: Sazon = single-user + customer-facing | Different scopes; document both |
| **Spec layer** | aiw-org/OPERATIONS.md: tickets/DEMIURGE-XXX/plan.md | saskia-app/AGENTS.md: docs/operations/YYYY-MM-DD-NAME.md | Different naming; same pattern |

---

## 19. The 60-day AIW org review (REVIEW-2026-Q4.md) — decisions on 2026-10-14 (3 days from now)

| # | Decision | Affects Sazon? |
|---|---|---|
| 1 | Are 6 departments the right shape? | No (Sazon doesn't follow dept model) |
| 2 | Marketing split from Sales? | No |
| 3 | Customer Success split? | No |
| 4 | Per-agent git repos: ship now? | Possibly (Sazon is a single repo, not per-feature) |
| 5 | Qdrant: need it? | Possibly (Sazon could use it for recipe search) |
| 6 | Backup retention: 90 days? | Yes (Sazon backup is 14 days, could match AIW) |
| 7 | Bump ORG-AGENTS to v0.3.0? | No |
| 8 | Add Tier 2 agents for hot paths? | No |
| 9 | Cross-cutting concern to standalone dept? | No |

**Sazon-relevant**: items 4, 5, 6. The 60-day review is in 3 days.

---

## 20. The 3 concrete actions for Sazon from Phase 3

1. **Add a 2-line "AIW context" header to saskia-app/AGENTS.md** (top of file): "Sazon is a custom instance built on the AIW Python template (templates-standard/repo-template/). It follows the AIW patterns in aiw-org/AGENTS.md (the AIW-wide single authoritative rulebook)."

2. **Add 15 new rules (52-66)** from CAP §6 verbatim, with Sazon-specific annotations.

3. **Update saskia-app/AGENTS.md Section 5 (Personas)** to clarify: "Kiki (Sazon AI agent) ≠ Kiki (AIW human co-founder 'Kyrian'). They are different entities with the same name. The Sazon Kiki is the orchestrator; the AIW Kiki is a human co-signer of governance items."

---

## 21. The single most important 5-min finding

**Sazon is built on the AIW Python template (byte-for-byte match for .flake8, cspell.json, ruff.toml).** This is the **most concrete evidence** that Sazon is part of the AIW family. The Sazon AGENTS.md should:
- Acknowledge this ancestry in the top section
- Reference aiw-org/AGENTS.md as the upstream rulebook
- Adopt the 15 AIW operating rules verbatim
- Document the Sazon-specific deviations (3 envs, 40% coverage, Kiki persona, etc.)
- Adopt the data boundary T1/T2/T3 framework
- Adopt the self-running milestone definition

This is the bridge from "Sazon is its own thing" to "Sazon is a Sazon-specific instance of the AIW pattern."

---

## 22. Files on disk (final inventory, post-Phase 3)

| Path | Size | Purpose |
|---|---|---|
| `2026-10-12-p3-deep-read-synthesis.md` | **~30 KB** | **this doc** |
| `2026-10-12-p2-research-findings.md` | 40.3 KB | P2 research findings |
| `2026-10-12-update-plan.md` | 61.0 KB | comprehensive update plan |
| `2026-10-12-additional-areas-research.md` | 39.6 KB | 113 additional items |
| `2026-10-12-cross-repo-agents-md-analysis.md` | 41.9 KB | cross-repo analysis |
| `2026-10-12-deep-read-consolidated.md` | 33.7 KB | 47-item consolidated |
| `2026-10-12-agents-md-community-research.md` | 26.8 KB | community research |
| `2026-10-12-agents-md-rewrite-draft.md` | 24.1 KB | the rewrite |
| `2026-10-12-operator-intent-retrospective.md` | 21.6 KB | operator intent |
| `2026-10-12-agents-md-gap-analysis.md` | 11.8 KB | gap analysis |
| 3 orientation + 1 sibling-flush + 15 plans + 1 archive | 250 KB | operational |
| **94 cached source files** | **~970 KB** | from 6 repos |

**Total: ~1.4 MB of research + plan + cached source material on disk.**

**Cached source distribution (post-Phase 3)**:
- AO_ (aiw-org): 7 meta + 12 docs + 4 handoffs = 23 files
- CA_ (code-agent): 11 files
- JG_ (Johns-Grimoire): 25 files
- SA_ (saskia-app): 7 files (orientation)
- TS_ (templates-standard): 11 files
- WA_ (wizard-academy): 17 files

---

## 23. Recommended next step

**Read the remaining 4 aiw-org/docs/ files** (~80 KB) that I haven't read yet but are referenced in §2.14:
- `HERMES-ANSWERS-2026-09-02.md` (28 KB) — comprehensive Hermes Q&A
- `OMETZ-VOICE-COMPLIANCE-BRIEF.md` (30 KB) — Ometz voice compliance
- `ORGANIGRAM-AND-DETAILED-ANALYSIS.md` (30 KB) — org analysis
- `TOOLING-TIERS.md` (27 KB) — already read
- `CONSOLIDATION-REPORT.md` (4.9 KB) — already read

**One-word choices**:
- `hermes-answers` — read HERMES-ANSWERS-2026-09-02 (28 KB, ~15 min)
- `all-large` — read all 3 remaining large docs (~45 min)
- `ometz` — read OMETZ-VOICE-COMPLIANCE-BRIEF (30 KB, ~20 min) — voice compliance is Sazon-relevant
- `organigram` — read ORGANIGRAM-AND-DETAILED-ANALYSIS (30 KB, ~20 min) — org structure
- `phase2` — stop research, go to saskia-app/AGENTS.md rewrite (3-4h)
- `consolidate` — synthesize all 4 research turns into a single FINAL doc
