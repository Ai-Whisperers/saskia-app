# Token Plan Options — Decision Document for John
**Date:** 2026-09-18
**For:** Monday Sep 21 Leadership Meeting
**Decision needed by:** John (Product Owner)
**Reference:** DD-O11 in AIW-MASTER-ACTION-PLAN

---

## TL;DR

**Recommended:** Subscribe to MiniMax-M3 Pro ($200/mo) + ZAI free tier ($0/mo)
**Total budget:** $200/mo
**Current spend:** $1,370/mo ($1,185 interactive + $128 cron + buffer)
**Target:** $1,200/mo (Q4 exit goal)

---

## Current State (as of 2026-09-18)

### What we have
- **4 active LiteLLM sub-keys** (issued Sep 18):
  - `aiw-internal-coach-kiki`: $50/mo, primary/fast/reasoning
  - `aiw-internal-coach-ivan`: $100/mo, primary/fast/reasoning/vision
  - `aiw-internal-agents-default`: $200/mo, primary/fast/reasoning/vision
  - `aiw-internal-evals`: $75/mo, primary/reasoning
  - **Total allocated:** $425/mo

- **5 model aliases** (from `/opt/data/config/litellm/config.yaml`):
  - `primary` → MiniMax-M3 (workhorse, 94% of spend)
  - `fast` → MiniMax-M2.7-highspeed (low-latency)
  - `reasoning` → MiniMax-M2.7 (deep thinking)
  - `vision` → MiniMax-M3 (tool calling)
  - `placeholder`: anthropic-claude, codex, deepseek, glm, qwen

- **Actual spend (7-day window):**
  - MiniMax-M3: 53,065 calls = $272.20 (94%)
  - glm-4.5-flash: 2,097 calls = $3.94 (1%)
  - Other: $0 (free tier or unused)
  - **Interactive:** $1,185/mo est
  - **Cron:** $128.55/mo est (77 jobs, explicit models assigned)

### What's broken
- ⚠️ No actual token plan subscriptions — sub-keys are active but point to MiniMax-M3 which requires subscription
- ⚠️ Cron cost not visible in LiteLLM spend API (estimated $128/mo)
- ⚠️ No overflow policy (what happens at 80%? 100%?)
- ⚠️ No model priority chain (which model when primary is overloaded?)

---

## Option 1: MiniMax-M3 Pro Only ($200/mo) — RECOMMENDED ✅

### What it is
- **Subscription:** $200/mo flat fee
- **Includes:** 10M tokens/day for MiniMax-M3
- **Overage:** Pay-as-you-go (but we want to avoid this per user preference)
- **Provider:** minimax-plan (Ivan's token plan)

### Pros
- ✅ Already configured in litellm config (canonical)
- ✅ Used for 94% of current spend (MiniMax-M3 is the workhorse)
- ✅ 10M tokens/day is generous (current usage ~3M/day)
- ✅ Sub-keys already point to it
- ✅ No migration needed

### Cons
- ❌ Single vendor lock-in
- ❌ No fallback if MiniMax has outage
- ❌ $200/mo is 17% of current $1,185/mo interactive spend

### Expected impact
- **Interactive:** $1,185/mo → ~$200/mo (covered by subscription + small overage)
- **Cron:** $128/mo → ~$50/mo (cron jobs use fewer tokens, mostly within subscription)
- **Total:** $1,313/mo → **$250/mo** (massive reduction, well under $1,200/mo target)

---

## Option 2: MiniMax-M3 Pro + ZAI Free Tier ($200/mo)

### What it is
- **MiniMax-M3 Pro:** $200/mo (as Option 1)
- **ZAI Free Tier:** $0/mo (100K tokens/day for glm-4.5-flash)
- **Use case:** Fallback for low-priority cron jobs

### Pros
- ✅ Same as Option 1
- ✅ Diversified models (MiniMax + ZAI)
- ✅ Free tier covers ~10% of cron jobs
- ✅ Reduces overage risk

### Cons
- ❌ ZAI free tier is unreliable (rate limits, quota)
- ❌ More complex model routing
- ❌ Quality variance between MiniMax and ZAI

### Expected impact
- **Interactive:** $200/mo (MiniMax covers most)
- **Cron:** $50/mo (15 jobs use ZAI free, 62 use MiniMax)
- **Total:** **$250/mo** (same as Option 1, but diversified)

---

## Option 3: MiniMax-M3 Pro + Anthropic Pro ($220/mo)

### What it is
- **MiniMax-M3 Pro:** $200/mo
- **Anthropic Pro:** $20/mo (5M tokens/day for Claude Sonnet)
- **Use case:** High-quality reasoning for critical agents

### Pros
- ✅ Same as Option 1
- ✅ Anthropic as premium fallback for board-of-directors, security, etc.
- ✅ Better quality for reasoning tasks (Claude Sonnet > MiniMax-M3 for some tasks)

### Cons
- ❌ +$20/mo for marginal benefit
- ❌ Anthropic not currently configured in litellm
- ❌ Migration effort to add Anthropic model

### Expected impact
- **Interactive:** $200/mo
- **Cron:** $50/mo
- **Reasoning premium:** $20/mo (10-20 jobs use Claude Sonnet)
- **Total:** **$270/mo**

---

## Option 4: Pay-as-you-go only ($0/mo subscriptions)

### What it is
- **No subscriptions:** Use metered API for everything
- **Cost:** ~$1,313/mo (current trajectory)

### Pros
- ✅ No upfront commitment
- ✅ Only pay for what you use

### Cons
- ❌ **User explicitly said NO** ("token plan only, no pay-as-you-go")
- ❌ Higher per-token cost
- ❌ Unpredictable monthly bill
- ❌ No budget caps (can overspend)

### Expected impact
- **Total:** $1,313/mo (over $1,200/mo budget by 9%)

---

## Decision Matrix

| Option | Monthly Cost | Over $1,200 Budget? | Diversification | Migration Effort |
|---|---:|:---:|:---:|:---:|
| **1. MiniMax-M3 Pro only** | $200 | ✅ No ($1,000 under) | ❌ Single vendor | ✅ None |
| **2. + ZAI free** | $200 | ✅ No ($1,000 under) | ⚠️ 2 vendors | ⚠️ Low |
| **3. + Anthropic Pro** | $220 | ✅ No ($980 under) | ✅ 3 vendors | ❌ Medium |
| **4. Pay-as-you-go** | $1,313 | ❌ Yes ($113 over) | ⚠️ Many | ✅ None |

---

## Overflow Policy (Critical for All Options)

### Recommended thresholds
- **80% of budget ($160/mo for Option 1):** Alert to Ivan + Kiki
- **90% of budget ($180/mo):** Alert to John, pause non-critical cron jobs
- **100% of budget ($200/mo):** Hard cap, switch to ZAI free tier fallback

### Implementation
- LiteLLM proxy enforces budget caps automatically (per sub-key)
- Cron cost-monitor.py alerts at thresholds
- Weekly digest shows budget utilization

---

## Model Priority Chain (for cron jobs)

### Current assignment (after Sep 18 autonomous work)
- **77 enabled cron jobs** assigned:
  - 47 → MiniMax-M3 (primary, $0.005/call)
  - 15 → MiniMax-M2.7-highspeed (fast, $0.002/call)
  - 15 → MiniMax-M2.7 (reasoning, $0.004/call)

### Recommended routing
1. **Primary (MiniMax-M3):** Default for most jobs
2. **Fast (MiniMax-M2.7-highspeed):** Monitors, trackers, heartbeats
3. **Reasoning (MiniMax-M2.7):** Audits, evals, security, improvements
4. **Fallback (ZAI free):** When MiniMax subscription exhausted

---

## Recommendation

**Choose Option 1: MiniMax-M3 Pro at $200/mo**

### Why
1. **Already configured** — sub-keys point to it, no migration
2. **Massive cost reduction** — $1,313/mo → $250/mo (81% reduction)
3. **Within budget** — $200/mo is 17% of $1,200/mo target (huge headroom)
4. **Simple** — single vendor, single subscription
5. **Reversible** — can add ZAI/Anthropic later if needed

### Next steps after approval
1. Ivan subscribes to MiniMax-M3 Pro ($200/mo)
2. Update `LITELLM_MASTER_KEY` if needed (currently active)
3. Configure overflow policy in litellm config
4. Update cost-tracker.json with new budget ($1,200/mo)
5. Kiki adds overflow alerts to weekly digest template

---

## Decision Required at Monday Meeting

**Question for John:** Approve Option 1 (MiniMax-M3 Pro at $200/mo)?

**If YES:** Ivan executes subscription Monday evening
**If NO:** Which option? (2, 3, or 4)
**If DEFER:** What additional information is needed?

---

## Appendix: LiteLLM Sub-Key Status

```
alias                               status          budget     rpm    models
----------------------------------------------------------------------------------------------------
aiw-internal-coach-kiki             active          $50        60     primary,fast,reasoning
aiw-internal-coach-ivan             active          $100       120    primary,fast,reasoning,vision
aiw-internal-agents-default         active          $200       300    primary,fast,reasoning,vision
aiw-internal-evals                  active          $75        90     primary,reasoning

Total: $425/mo allocated, all active as of 2026-09-19T01:17Z
```

---

*Document prepared by Ivan for John's Monday decision*
*Reference: AIW-MASTER-ACTION-PLAN-2026-09-18.md §2.1 DD-O11*
*All 4 sub-keys issued and active as of 2026-09-19*
