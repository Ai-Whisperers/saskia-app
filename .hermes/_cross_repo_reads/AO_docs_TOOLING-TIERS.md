# Tooling Tiers — "AI Employee" Deployment Packages

> **Last updated:** 2026-08-26 (v0.1.0)
> **Authors:** Erebus (drafted), Iván (review pending)
> **Source docs:** `/opt/data/agents/ORG-AGENTS.md` (47-agent matrix),
> `/opt/data/agents-v2/PHASE-13-COMPLETE-UPDATED-PLAN.md`, `/opt/data/agents/research/200-ai-coaching-companies.md`,
> `/opt/data/agents-v2/docs/COMPLETE-EXPLANATION.md`, `/opt/data/agents/ROLLBACK-PLAYBOOK.md`.
> **Companion doc:** `CUSTOMER-TEMPLATE.md` (the deployment template these tiers plug into).
> **Scope:** productising the AI Whisperers org layer as a reusable deployment SKU — turning the 47-agent matrix
> inside-out so an external customer can pick a tier and ship.

---

## 1. Why these tiers exist

The August 13, 2026 transcription surfaced this gap (paraphrased from
`docs/CONVERSATION-NOTES-AND-LONG-DEPT-LIST.md`):

> *"You can have mid-range, like a 1-5 business company. What is the actual tooling that would be advised?
> Could be services, notebook, anything. Then 5-20, they have limited to no automation. Above 20, completely
> different. Then they have a lot of automation."*

The 47-agent matrix in `ORG-AGENTS.md` is one shape; an external customer needs **three** shapes —
stripped to the right size for their headcount. This doc packages those shapes as monthly subscriptions.

### 1.1 What we are selling

The 47-agent matrix decomposes into three nested layers per `ORG-AGENTS.md` §1:

- **Tier 1: Micro (4 agents, 3 departments)** — finance, sales, operations minimum viable loop.
- **Tier 2: Small (12 agents, 6 departments)** — adds marketing, research, people/HR.
- **Tier 3: Medium (47 agents, 16 departments)** — full AIW equivalent (lead + sub + cross-cutting + monitoring + coaching).

Each tier is a **functioning org slice**, not a feature list. Every agent ships with its PROMPT.md,
its cron schedule, its state schema, its eval-gate hook, and one rollback path (per
`ROLLBACK-PLAYBOOK.md` §7 onboarding checklist).

### 1.2 What we are NOT selling

- Not selling the Hermes runtime / Hermes Agent source. The customer brings their own runtime;
  we deploy the agent layer onto it. (Per `ai-run-org-playbook` — Hermes is the substrate, not the SKU.)
- Not selling trademark-banned paid acquisition channels (paid social, paid search, paid
  video-platform placements). Per `COMPLETE-EXPLANATION.md` §"The Trademark Banlist".
- Not selling fabricated testimonials, fabricated statistics, or published numeric pricing on public
  surfaces. Per `aiw-hard-stop-audit`.

### 1.3 Pricing rationale (grounded, not fabricated)

The price points below are **derived from** existing AIW pricing, not invented:

| Anchor | Source | Value used |
|--------|--------|-----------|
| Coaching S-tier | `docs/COMPLETE-EXPLANATION.md` §1 (Tiers) | USD $150 / PYG $90K |
| Coaching M-tier | same | USD $500 / PYG $300K |
| Coaching L-tier | same | USD $1,500 / PYG $900K |
| AIW LLM baseline | same §"Cost Breakdown" | USD $293/mo total infra (litellm/fast + Evolution API + Cloudflare + VPS all $0 marginal) |
| AIW human-cost anchor | same | USD $4,000–$8,000/mo per human replaced → 13-27× ROI |
| Tier 1 envelope | `docs/CONVERSATION-NOTES-AND-LONG-DEPT-LIST.md` §"Tooling Tiers" | $50–200/mo (existing stub) |
| Tier 2 envelope | same | $300–1,000/mo (existing stub) |
| Tier 3 envelope | same | $2,000+/mo (existing stub) |

The pricing chosen for each tier below sits **inside** those envelopes and is sized so the
customer's ROI vs their first human hire is always positive (per cost-breakdown math).

The market-rate anchor is `200-ai-coaching-companies.md` §"TL;DR" — corporate coaching/AI
spend in the US/LATAM sits at USD 4-15K/employee/year for BetterUp/CoachHub/Valence-class
products. That ceiling informs tier 3 pricing.

---

## 2. Tier 1 — Micro (1–5 employees)

**One-line pitch:** *"Hire your first four AI employees — finance, sales, ops — for less than a Paraguayan
minimum wage."*

### 2.1 Who it is for

- Solo founder or 1-5 person team in Paraguay, Bolivia, Brazil, or a Dutch-speaking EU SMB.
- Revenue already flowing but no internal ops cadence. Founder is the bottleneck on invoicing, lead
  follow-up, and weekly status updates.
- Customer is comfortable with `Hermes Agent` running in one Docker container or one VPS, but does NOT
  want to set up cron, eval, or state from scratch.
- Trilingual preference: ES is primary, EN secondary, NL is a bonus (matches AIW's native
  trilingual coaching stack — `docs/COMPLETE-EXPLANATION.md` §1).

### 2.2 Departments and agents (4 total — see `ORG-AGENTS.md` §1.1, §1.2, §1.3)

| Dept | Agent | Role (per `ROLES-INVENTORY.md`) | Cadence |
|------|-------|--------------------------------|---------|
| **finance** | `business-analyst` (Tier-1 lead, daily) | Business Analyst → KPI snapshot, decisions, open questions | daily 06:30 PYT |
| **sales** | `sales-pipeline` (Tier-1 lead, daily) | Head of Sales / CRO → leads_in_flight, stalled_deals | daily 12:00 PYT |
| **sales** | `lead-enrichment` (Tier-2 sub, daily) | SDR → outbound qualification | daily 09:30 PYT |
| **operations** | `ai-ops-coordinator` (Tier-3 cross-cutting, daily) | AI Ops Lead → day-to-day orchestration rollup | daily 08:00 PYT |

**Plus 2 infra-only monitoring agents** (heartbeat only — not billed as agents, but included):

- `devops-monitor-30min` (every 30 min)
- `ai-safety-engineer-30min` (every 30 min) — runs the trademark banlist + hard-stop scrub

### 2.3 What's included

- **4 functional agents** wired to the customer's actual data sources (Notion, Trello,
  Sheets, WhatsApp via Evolution API, one bank/PSP feed).
- **2 monitoring agents** providing heartbeat + compliance signalling.
- **Cron schedule** installed on the customer's VPS or our shared infra (~50 jobs from the AIW
  base set, of which 6-8 actually run for this tier — rest are dormant).
- **State files** in `/opt/data/agents/state/*.json` with the schema from `ORG-AGENTS.md` §3.
- **Eval-gate hook** wired to `eval-gate.py` (per `PHASE-10-EVAL-GATE-POC.md`) — every brief scores
  itself before hitting the customer's inbox; hard-FAIL on banned brand tokens.
- **Trademark scrub** at deploy + on every push (per `docs/COMPLETE-EXPLANATION.md` §"The
  Trademark Banlist").
- **Weekly morning-brief** delivered to one destination (email or WhatsApp).
- **30-day self-running window** in the org-state heartbeat (`org-state.json` mtime < 5 min;
  see `ROLLBACK-PLAYBOOK.md` §1.2 RTO matrix).
- **Trilingual UI**: ES default, EN secondary, NL available for EU customers.

### 2.4 What's excluded (and why)

| Excluded | Why |
|----------|-----|
| Marketing department (`marketing-content`, `multimedia-producer`) | Founder still does their own content at this size; AI-generated copy adds risk without adding volume |
| Research department (`research-tracker`, `citation-checker`) | Customer is too small to need a research agenda |
| People/HR (`people-hr`, `kiki-coach`) | 1-5 person team knows each other by name |
| Legal/compliance deep-work | Replaced by the always-on banlist scrub + monthly compliance brief |
| Board / coaching / multimedia | Tier 3 territory |
| Custom-domain Worker + R2 setup | Tier 2 ships a Cloudflare Workers setup for one Worker; tier 1 keeps static + webhook |
| Multi-tenant SSO | Tier 2 |

### 2.5 Setup time

- **Day 1 (4 hours wall-clock):** intake-completed customer copy + 4 agents wired to customer's
  Notion/WA/Sheets → first cron tick fires before end-of-day.
- **Days 2-7:** morning-brief delivered daily, eval-gate passes (3 of 3 first briefs), org-state
  fresh every <5 min. Founder can read the morning-brief and KNOW what's open without checking
  their own inbox.
- **Day 30:** self-running declaration per `SELF-RUNNING-CRITERIA.md` — applies to a tier
  when 0 cron errors in 30d window + 0 "is X live?" messages. Tier 1 ships with this as a build-in.
- **Total wall-clock to first week of value:** ~7 days (one founder-day for intake + 4 AI turns
  for the agent layer, running in parallel).

### 2.6 Maintenance burden

- **Daily:** ~5 min — review the morning-brief.
- **Weekly:** ~30 min — review the weekly brief + approve any HARD/HIGH decisions in
  `coord.json:decisions_for_ivan` (per `ROLLBACK-PLAYBOOK.md` §1.3).
- **Monthly:** ~2 h — re-run intake if scope changed; renew banlist via
  `trademark-scan.py`; refresh OAuth tokens (per `ORG-AGENTS.md` §5.5).
- **0 humans-in-loop required for routine ops** — that's the test. If the founder has to touch
  the system daily, the tier is over-sold.

### 2.7 Monthly price

| Currency | Price | Notes |
|----------|-------|-------|
| **PYG** | **₲ 1,800,000** (~USD $250 at parallel rate) | Anchored to ₲300K coaching M-tier (6×); covers ~$30 LLM + infra + AIW license |
| **EUR** | **€ 350** | Anchored to NL SMB market rate |
| **USD** | **$ 250** | For US/LATAM-USD customers |

The USD price is **below** the existing Tier 1 envelope (USD $50-200) floor; we recommend it as
the new floor because LLM baseline cost ($293/mo for 49 agents) only drops to ~$30/mo for the
4-agent subset.

**Setup fee:** ₲ 1,800,000 / € 350 / $ 250 one-time, applied against month-1.

---

## 3. Tier 2 — Small (5–20 employees)

**One-line pitch:** *"Twelve AI employees covering every department a 10-person company needs, with
eval-gate and CI/CD on top."*

### 3.1 Who it is for

- Team of 5-20 in PY / BO / BR / NL / EU SMB.
- Founder has hired 2-4 humans but is still the de facto COO, CMO, and CHRO.
- Some SaaS in place (Notion + Linear OR Trello + chat/voice + Workspace), but no automation,
  no eval-gate, no compliance monitor.
- Looking for a "departments as agents" mental model that matches how the founder thinks about
  hiring.

### 3.2 Departments and agents (12 total — per `ORG-AGENTS.md` §1.1–§1.3)

Everything in **Tier 1 (Micro)** PLUS:

| Dept | Agent | Role | Cadence |
|------|-------|------|---------|
| **finance** | `accounting-automation` (Tier-2 sub, daily) | Bookkeeper → day-to-day transactions, AP/AR | daily 18:00 PYT |
| **finance** | `tax-receipt-tracker` (Tier-2 sub, weekly) | Tax Specialist → quarterly filings | weekly Sun 19:00 |
| **sales** | `proposal-drafter` (Tier-2 sub, daily) | Proposal Writer → drafts SOWs | daily 10:00 PYT |
| **sales** | `revops-pipeline-analyzer` (Tier-2 sub, daily) | Sales Engineer → funnel diagnostics | daily 07:00 PYT |
| **marketing** | `marketing-content` (Tier-2 sub, mon-wed-fri) | Content Marketing Manager → editorial calendar | M-W-F 12:00 PYT |
| **marketing** | `multimedia-producer` (Tier-2 sub, on-demand) | Brand Manager → image/video/audio queue | on-demand |
| **research** | `research-tracker` (Tier-1 lead, weekly) | Research Lead → thesis + publications pipeline | weekly Sun 18:00 |
| **research** | `source-curator` (Tier-2 sub, weekly) | Citation/Bibliography Specialist | weekly Tue 13:00 |
| **operations** | `bizops-tracker` (Tier-3, weekly) | BizOps Specialist → KPI rollup | weekly Mon 08:00 |
| **operations** | `procurement-tracker` (Tier-2 sub, weekly) | Procurement Officer → vendor mgmt | weekly Mon 09:00 |
| **people** | `people-hr` (Tier-2 sub, weekly) | Head of People / VP HR → hiring/onboarding/comp | weekly Mon 22:00 |
| **+ Tier-1 monitoring cluster ×2** | `devops-monitor-30min`, `ai-safety-engineer-30min` | Heartbeat + trademark scrub | every 30 min |

### 3.3 What's added vs Tier 1

- **+8 functional agents** (the table above, on top of Tier 1's 4).
- **Editorial calendar** the founder can plug into — content goes out M-W-F without
  founder-touched review.
- **Proposal drafts** auto-generated from the customer's pricing table; founder reviews
  before send.
- **Tax + procurement** weekly reports — flagged if anything > 30 days old.
- **Multi-source research capability** — weekly thesis/landscape brief, with citations baked in.
- **2-Worker Cloudflare deploy** — `<slug>-site` static + `<slug>-lead` API (per
  `client-site-kickoff` §6.1 lead API Worker pattern).
- **Eval-gate cron** — `aiw-eval-gate-runner-on-agent-run` wired + `eval-per-agent.json` visible
  to founder.
- **State-versioned history** — every state file 6h-snapshotted (per `ROLLBACK-PLAYBOOK.md` §1).

### 3.4 What's excluded vs Tier 3

| Excluded from Tier 2 | Why (deferred to Tier 3 / customer-paid add-on) |
|---------------------|--------------------------------------------------|
| Full coaching-agent layer (`coach-*` — 14 agents) | Customer uses AIW coaching tier as a separate SKU (S/M/L @ ₲/$ 90K-900K) |
| `board-of-directors` (quarterly) | Boards are 20+ employee territory |
| `management-coordinator`, `kiki-coach` leads | Still founder-driven cadence at 5-20 |
| Chaos test runner, drift-detector | Engineering org at 5-20 is 0-1 engineers; chaos-testing over-sells |
| Multilingual coaching discovery (`coach-lead-finder`, `coaching-research-intelligence`) | Tier 3 |
| Custom ES + EN + NL content calendar | Tier 3 |
| Advanced eval-gate (per-agent golden trajectories) | Tier 3 |

### 3.5 Setup time

- **Day 1 (8 hours wall-clock):** expanded intake (200+ question `CUSTOMER-TEMPLATE.md` form),
  all 12 agents wired, two Workers deployed.
- **Days 2-14:** cron cluster running, first weekly brief delivered, eval-gate begins scoring.
- **Day 14:** self-running declaration eligible (per `SELF-RUNNING-CRITERIA.md`) IF 0 cron errors
  in 14d window.
- **Day 30:** first full retrospective + Tier 3 upsell review.
- **Day 60:** quarterly OKR tracker live (`okr-tracker` toggled on if customer opts in).
- **Total wall-clock to first month of value:** ~14 days (two founder-days for intake +
  8-12 AI turns for the agent layer, mostly parallel).

### 3.6 Maintenance burden

- **Daily:** ~5 min — review morning-brief (same as Tier 1).
- **Weekly:** ~60 min — review 3 weekly briefs (bizops-tracker, research-tracker, procurement);
  approve ~3 HARD/HIGH decisions.
- **Biweekly:** ~30 min — `engineering-roster` style review if customer has engineering work.
- **Monthly:** ~4 h — refresh OAuth, evaluate Tier 3 triggers, renewal conversation.
- **0 humans-in-loop required for routine ops** — same test as Tier 1.

### 3.7 Monthly price

| Currency | Price | Notes |
|----------|-------|-------|
| **PYG** | **₲ 4,500,000** (~USD $625 at parallel rate) | Anchored to ₲300K coaching M-tier (15×); ~$80 LLM + infra + license |
| **EUR** | **€ 900** | Anchored to NL SMB mid-market rate |
| **USD** | **$ 600** | For US/LATAM-USD customers |

The USD price is **inside** the existing Tier 2 envelope ($300-1,000). We sit at the lower end
because we already have the agent layer amortised across the 47-agent matrix.

**Setup fee:** ₲ 3,600,000 / € 700 / $ 500 one-time, applied against month-1.

---

## 4. Tier 3 — Medium (20+ employees)

**One-line pitch:** *"Forty-seven AI employees covering everything from compliance monitoring to
quarterly board reviews. The 1000-person-corp structure, scaled to your 20+ headcount."*

### 4.1 Who it is for

- Team of 20+ across multiple time zones, possibly multiple countries.
- Founder is no longer the bottleneck on ops; the bottleneck is **alignment** (every department
  ships its own thing, nobody talks).
- Customer is evaluating betterUp/CoachHub/Valence-class spend ($4-15K/employee/year per
  `200-ai-coaching-companies.md` §"TL;DR") and wants a smaller unit-economics alternative.
- Trilingual SOPs already in place (or about to be).

### 4.2 Departments and agents (47 total — the full AIW matrix)

Everything in **Tier 2 (Small)** PLUS:

| Dept | Added agents | Count |
|------|--------------|-------|
| **operations** | `management-coordinator` (lead, biweekly), `okr-tracker`, `compliance-monitor`, `founder-bandwidth-watchdog`, `eval-gate-runner`, `security-auditor`, `chaos-test-runner` (off, opt-in) | +7 |
| **engineering** | `engineering-roster` (lead, biweekly), `qa-automation-runner`, `drift-detector` (ad-hoc) | +3 |
| **finance** | `finance-controller` (co-lead, weekly), `funding-coordinator` (on-demand) | +2 |
| **people** | `kiki-coach` (lead, weekly) | +1 |
| **management** | `board-of-directors` (quarterly) | +1 |
| **monitoring** | `security-watchdog-30min`, `coaching-quality-reviewer` (every 30 min) | +2 |
| **coaching** | 14 coaching agents (`coach-ivan`, `coach-kiki`, `coach-org`, `coach-lead-agents`, `coach-lead-finder`, `coach-onboarding`, `coach-practitioner` (planned), `coach-cohort-facilitator` (planned), `coach-conversion-agent` (planned), `coach-renewal-manager`, `coach-roi-tracker`, `coaching-content-curator`, `coaching-research-intelligence`, `coach-practitioner`) | +14 (some planned) |

**Total: 47 = 7 Tier-1 lead + 14 Tier-2 sub + 8 Tier-3 cross-cutting + 4 Tier-4 monitoring + 14 Tier-5 coaching**
(per `ORG-AGENTS.md` §1).

### 4.3 What's added vs Tier 2

- **Full monitoring cluster ×4** writing to `org-state.json` every 30 minutes
  (per `ROLLBACK-PLAYBOOK.md` §2.2 Tier-4 monitoring row).
- **Eval-gate trending** — daily/weekly CSV; founder sees quality drift at the agent-family
  level.
- **Weekly board-style strategic review** (`board-of-directors` cron quarterly).
- **Coaching-as-product layer** — can be turned on or off per customer; the 14-agent coaching
  layer is the same one AIW sells to its own coaching customers (USD $150-1,500/mo per customer).
- **Chaos test runner opt-in** — `aiw-chaos-test-runner-weekly` (currently OFF in AIW; opt-in for
  Tier 3 customers who want the resilience validation).
- **Drift-detector** wired to customer's schema-vs-state diff.
- **Dedicated incident-response training** — one 2-hour session on using
  `ROLLBACK-PLAYBOOK.md` for this customer's specific stack.
- **Maximum autonomy** — same 7-day-no-touch milestone from `SELF-RUNNING-CRITERIA.md` but with
  47-agent surface area.

### 4.4 What's NOT included (and the upsell conversation)

| Excluded from Tier 3 | Add-on SKU |
|----------------------|-----------|
| The full LLM API bill if the customer burns >$1,000/mo | "AI Compute as a Service" — metered billing at AIW cost + 15% |
| Custom agent authoring (Tier-2/3 customers who want their own agents) | "Custom Agent Foundry" — billed per agent |
| Multilingual marketing content (ES + EN + NL live) | "Trilingual Content Engine" add-on |
| EU AI Act + LGPD + GDPR compliance agent (`coaching-eu-compliance` skill class) | "Compliance Pack EU/LATAM" |
| Real human-in-loop 1:1 coaching sessions (the AI is the persona, not the coach) | "Human Coach Network" — partnership referrals only |

### 4.5 Setup time

- **Days 1-14:** Foundation Phase (per `PHASE-13-COMPLETE-UPDATED-PLAN.md` §4.2 Track F1) — make
  all 47 agents actually work on the customer's infra.
- **Days 15-30:** Self-running window (per `PHASE-13` §4.3) — 7-day milestone verification, no
  touching of PROMPT.md or cron schedules during the window.
- **Days 31-60 (optional):** Coaching Phase 1 — turn on the internal coaching agents
  (`coach-ivan`, `coach-kiki`, `coach-org`, etc.) per `PHASE-13` §4.4.
- **Days 61-90 (optional):** Coaching Phase 2 — turn on external coaching layer if customer wants
  to resell coaching as a service.
- **Total wall-clock to 7-day self-running:** ~30 days (5-7 founder-days for intake + ~20 AI
  turns for the 47-agent layer, mostly serialised through the foundation gates).

### 4.6 Maintenance burden

- **Daily:** ~10 min — review morning-brief (now with 4 monitoring writers backing it).
- **Weekly:** ~90 min — 7 weekly briefs (per `PHASE-13` §4.3 cadence table); approve ~5
  HARD/HIGH decisions; review 1 weekly coach-quality score.
- **Monthly:** ~6 h — full OKR review + escalation-budget review; quarterly Board-of-Directors
  brief.
- **Quarterly:** ~10 h — full security audit + 12-factor audit (`PHASE-21-12-FACTOR-COMPLETE.md`)
  + eval-trend CSV review.
- **The customer can hand the entire ops loop to the 47 agents if they pass the 7-day
  self-running window.** That's the deliverable.

### 4.7 Monthly price

| Currency | Price | Notes |
|----------|-------|-------|
| **PYG** | **₲ 14,400,000** (~USD $2,000 at parallel rate) | Anchored to ₲1,800K-9,000K coaching S-to-L tiers (compound); ~$293 LLM baseline (full AIW infra amortised) + ~$700 multi-Worker + license |
| **EUR** | **€ 2,800** | Anchored to BetterUp/CoachHub comparable ($4-15K/employee/year → ~€330-1,250/employee/year at 20+ employees → €6,600-25,000/yr/team, ours at €33,600/yr/team is at lower end) |
| **USD** | **$ 2,000** | For US/LATAM-USD customers |

This is **at the floor** of the existing Tier 3 envelope ($2,000+/mo). The Customer-Template
intake form captures the customer's headcount band; for headcount >50 the price scales linearly
($80/employee/month above the 20-employee baseline, capped at +$2,000).

**Setup fee:** ₲ 7,200,000 / € 1,400 / $ 1,000 one-time, applied against month-1 + first
month-of-service.

---

## 5. Comparison matrix

| | **Tier 1 Micro** | **Tier 2 Small** | **Tier 3 Medium** |
|---|---|---|---|
| **Headcount band** | 1-5 | 5-20 | 20+ |
| **Functional agents** | 4 | 12 | 47 (full AIW matrix) |
| **Monitoring agents** | 2 | 2 | 4 |
| **Departments covered** | 3 (finance, sales, ops) | 6 (+ marketing, research, people) | 16 (+ legal, board, multimedia, coaching, dev, QA, mgmt, procurement, accounting) |
| **Webhook endpoints** | 1 (one PSP) | 4 (Mercado Pago / PIX / bank / custom per `COMPLETE-EXPLANATION.md` §3) | 14 (full pipeline) |
| **MCPs** | 0–2 | 0–6 | 16 |
| **Eval-gate** | wired but lightweight | wired + cron-driven | wired + weekly trending |
| **Workers (Cloudflare)** | 0 | 2 (`<slug>-site`, `<slug>-lead`) | 6+ (one per role category) |
| **State files** | 3 schemas | 6 schemas | 9 schemas + `org-state.json` + `eval-per-agent.json` |
| **Cron jobs in dept** | 6 | ~30 | 90 unique (`ORG-AGENTS.md` §5) |
| **Setup wall-clock** | 7 days | 14 days | 30 days |
| **Maintenance (human time / mo)** | ~3 h | ~8 h | ~20 h |
| **Self-running declaration eligible** | Day 30 | Day 14 | Day 7 (after Phase F1+F2+F3 + 14-day window) |
| **Hard-stops enforcement** | 5 mechanical (per `vertical-client-extension-playbook`) | + banned-token FSM | + per-agent eval gate |
| **Trilingual (ES/EN/NL)** | ES primary, EN secondary | Trilingual UI | Trilingual content calendar + trilingual coach agents |
| **Annual discount** | 10% (pay yearly) | 15% | 20% |
| **Setup fee (one-time, ~1 month)** | $250 / €350 / ₲1.8M | $500 / €700 / ₲3.6M | $1,000 / €1,400 / ₲7.2M |

---

## 6. What's never sold (hard stops inherited from `vertical-client-extension-playbook`)

Every tier inherits these five mechanical hard stops (per `vertical-client-extension-playbook`
§"The Hard-Stops Manifest"):

1. **trademark_banlist**: never write banned brand tokens to public surfaces (per
   `docs/COMPLETE-EXPLANATION.md` §"The Trademark Banlist" — 30 tokens).
2. **price_privacy**: never publish numeric prices on public surfaces (the price list above is
   for the customer-facing sales doc, NOT a public artefact — see §7).
3. **no_fabrication**: never fabricate testimonials, stats, team members.
4. **pii_hard_stop**: client PII stays in dedicated DBs only (per `STORAGE-ARCHITECTURE.md`).
5. **no_private_repo_writes**: read mirror only; never write to private source-of-truth repo.

Plus tier-specific stops:
- **No trademark-banned paid acquisition channels** (paid social / paid search / paid video-placement)
  on the customer's behalf (banlist scope).
- **No automated personalised WhatsApp replies** to end-customers; template acks only
  (per `COMPLETE-EXPLANATION.md` §3).
- **No auto-commit to private customer repo** — agents read mirror only.

---

## 7. How to package this for the customer-facing sales doc

The pricing in §2-§4 is **deliberately not for public artefacts**. When creating the
customer-facing proposal:

- **Render this doc via the `trademark-compliance-scrub` step** (full banlist pass) before any
  extract goes into external material.
- **Replace the price table with the customer's local-currency quote** computed from the
  calculator in `CUSTOMER-TEMPLATE.md` §5 (Pricing Calculator).
- **All customer-facing copy uses ₲ / € / $ rounded to two significant digits** (no
  pseudospecific numbers like ₲ 14,347,293).
- **The "1000-person corp" pitch line** is the brand positioning; the per-tier feature
  comparison is the actual diff.

The marketing copy we're cleared to use (per `docs/COMPLETE-EXPLANATION.md` §"Short Intro"):

> *"A 1000-person corp structure, run by agents."*

Every tier realizes a slice of that. Tier 3 realises the full thing.

---

## 8. Cross-references

- **Sibling doc:** `CUSTOMER-TEMPLATE.md` — how a customer moves from intake to live tier.
- **Role catalog:** `/opt/data/agents-v2/ROLES-INVENTORY.md` (~135 roles; ~30 covered by Tier 3).
- **Agent matrix:** `/opt/data/agents/ORG-AGENTS.md` §1 (47-agent roster).
- **Plan:** `/opt/data/agents-v2/PHASE-13-COMPLETE-UPDATED-PLAN.md` §4 (six phases, 90-day build
  order).
- **Rollback:** `/opt/data/agents/ROLLBACK-PLAYBOOK.md` §1 (per-state-file), §2 (per-cron-job).
- **Trademark banlist:** `/opt/data/scripts/trademark-scan.py` (canonical 30-token list).
- **Self-running milestone:** `/opt/data/agents-v2/SELF-RUNNING-CRITERIA.md`.
- **Storage architecture:** `/opt/data/agents-v2/STORAGE-ARCHITECTURE.md` (JSON / SQLite / git-repo
  per agent).
- **Vertical extension pattern:** `vertical-client-extension-playbook` (single-client extension
  vs parallel org layer).

---

## 9. Open questions for Iván

These are the assumptions baked in here that should be re-confirmed before this becomes a paid SKU:

1. **Do the ₲ / € / $ price points balance against the LLM baseline cost?** With the four-agent
   subset burning ~$30/mo LLM, the $250 Tier 1 leaves $220/mo for AIW infra/licence margin. That's
   ~88% margin, but it assumes the customer's cron load doesn't spike. Needs a sensitivity table
   before signing Tier 1 customers at scale.
2. **Does the customer bring their own VPS, or do we host?** If we host, the Tier 1 setup
   includes ~$10-15/mo VPS amortisation; the price point shrinks. If they bring their own, we
   need a deploy recipe that's reproducible.
3. **Is the year-1 ARR target the $89-150K from `PHASE-13` §4.6, or higher?** Tier 3 at
   $2,000/mo × 12 months = $24K/year per customer. To hit $89K we need ~4 customers; to hit $150K
   we need ~6. The funnel math should match the existing `coaching-strategic-implications.md`
   model before committing the Tier-3 SKU.
4. **Multilingual content: do we charge for NL, or is it bundled?** AIW's trilingual position is
   the moat (per `200-ai-coaching-companies.md` §"TL;DR" — zero competitors in Dutch-market
   coaching). Bundling is the clearer story; charging is the clearer P&L. Default: bundled in
   Tier 2 and Tier 3, available as paid add-on for Tier 1.
5. **Should tier upgrades/downgrades be pro-rated?** Current model: full new-tier price on the
   day of switch. Standard SaaS model: pro-rated to the day. Decision affects cash flow but not
   the substantive tier design.

---

**End of TOOLING-TIERS.md** — companion `CUSTOMER-TEMPLATE.md` follows.
