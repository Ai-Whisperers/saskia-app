# REVIEW-2026-Q4.md

> 30/60/90-day review checklist for AI Whisperers org buildout.
> **Last updated**: 2026-09-01 (Phase 8 — appended "Phase 26 candidates" + status refresh)

---

## 30-day review (target: 2026-09-14)

### Health checks

- [ ] All 7 lead agents deliver on schedule for 30 consecutive days
- [ ] 0 cron jobs in error state for 30 days
- [ ] All hard-stop validators pass (7/7)
- [ ] All trademark scrubs clean on public artifacts
- [ ] Daily backup cron working (9 DBs backed up)
- [ ] State validate cron finding no schema violations

### Performance metrics

- [ ] Average brief length: 200-300 words (within target)
- [ ] Average brief delivery latency: < 1 minute after cron trigger
- [ ] Per-agent daily cost: < $1 (well under cap)
- [ ] Hard-stop actions triggered: count and review
- [ ] Escalation events: count and review

### Issues to address

- [ ] Review all errored cron jobs from gap audit
- [ ] Review cost-tracker.json for any anomalies
- [ ] Review sentiment indicators in chat (any signals?)
- [ ] Review bandwidth-watchdog reports (any signals?)

### Decisions to make

- [ ] Continue adding Tier 2 agents (which ones first?)
- [ ] Upgrade Cursor to Pro? (if MRR > $1K)
- [ ] Hire legal counsel? (if approaching $1K MRR)
- [ ] First EU client? (if pursuing)

---

## 60-day review (target: 2026-10-14)

### Org structure

- [ ] Are 6 departments the right shape, or do we need to split?
- [ ] Should Marketing split from Sales? (check marketing activity)
- [ ] Should Customer Success split? (check active client count)
- [ ] Are cross-cutting concerns (AI Ops, BizOps, etc.) earning their keep?

### Agent layer

- [ ] Any agents consistently delivering 500+ word briefs? (split trigger)
- [ ] Any agents with frequent idle? (remove or repurpose)
- [ ] Eval-gate POC on business-analyst: results review
- [ ] Chaos tests: results review

### Storage

- [ ] Per-agent git repos: should we ship now?
- [ ] Qdrant: do we have enough data to need it?
- [ ] Backup retention policy: 90 days sufficient?

### Compliance

- [ ] Trademark scrub: any violations caught?
- [ ] Hostinger incident: any new IP issues?
- [ ] EU client pursuit: still hard-stopped?

### Decisions to make

- [ ] Bump ORG-AGENTS to v0.3.0?
- [ ] Add Tier 2 agents for hot paths?
- [ ] Promote cross-cutting concern to standalone dept? (if triggers hit)

---

## 90-day review (target: 2026-11-14)

### Constitutional update (v0.3.0)

- [ ] Full audit of constitution vs reality
- [ ] Add any new departments/roles triggered in Q3
- [ ] Document any Tier 3 → Tier 4 promotions
- [ ] Re-validate all hard stops

### Phase 9 milestone check (per PLAN-v5)

- [ ] Self-running milestone achieved? (7 days all-green + 0 "is X live?" messages/week)
- [ ] If not: identify gap, add to next phase plan
- [ ] If yes: declare v0.2.0 self-running

### Business metrics

- [ ] MRR growth trajectory
- [ ] Lead pipeline coverage (3x quarterly target?)
- [ ] Conversion rate by stage
- [ ] Burn (still under $1K/mo?)
- [ ] Runway (3+ months?)

### Org metrics

- [ ] Hours worked per founder (under 70?)
- [ ] Decision latency (still fast?)
- [ ] Brief quality (Ivan reads them? Kiki reads them?)
- [ ] "Is X live?" messages from Ivan (target: 0/week)

### Plan v6

- [ ] Write `/opt/data/agents-v2/PLAN-v6.md` based on learnings
- [ ] Add Tier 3 dept promotions as triggers hit
- [ ] Expand agent layer to 50+ if MRR > $2K
- [ ] Plan next quarter's roadmap

---

## Continuous metrics (weekly)

| Metric | Target | Source |
|--------|--------|--------|
| Cron jobs in error | 0 | jobs.json |
| Agent deliveries | 7/day + sub-agents | outbox/ |
| Trademark violations | 0 | scrub output |
| Per-agent daily cost | < $1 | cost-tracker.json |
| Briefs read | 100% | (manual) |
| Ivan "is X live?" messages | 0/week | (manual) |
| Kiki lesson streak | continuous | state/kiki.json |

---

## Reviewer

All 30/60/90-day reviews conducted by **Erebus** (management-coordinator) and reported to Ivan.

---

## Cross-references

- `/opt/data/agents-v2/PLAN-v5.md` Part 9 (operational disciplines)
- `/opt/data/agents-v2/FAILURE-MODES.md` (chaos tests)
- `/opt/data/agents/DECISIONS-2026-Q3.md` (OP-4: self-running milestone)
- `/opt/data/agents-v2/BURNOUT-SIGNAL-SPEC.md`
- [`OPERATIONS.md`](./OPERATIONS.md) — how the org works (read first)
- [`department-index.md`](./department-index.md) — per-dept map

---

## Phase 8 status snapshot (2026-09-01)

**Current org scorecard** (per `operations/self-running-scorecard-2026.md` and `operations/health-dashboard.md`):

| Metric | Target | Current | Status |
|---|---|---|---|
| Cron health | 100% | 125/131 = 95.4% | 🟡 6 in error |
| Sub-agent monitors wired | 100% | 28/28 (100%) | ✅ |
| PROMPT.md lint pass | 100% | 63/63 (100%) | ✅ |
| Smoke gate | 100% | 100% pass, 9s | ✅ |
| Self-running criteria | 7/7 | 4.5/7 (64%) | 🟡 |
| Aggregate eval pass_rate | ≥95% | 0% (no data) | 🔴 |
| Ivan bandwidth audit | 2wk | not started | 🟡 |
| Sales funnel | ≥5 leads | 0 | 🔴 |
| Health dashboard | ≥60 | Ops 90 / Fin 48 / Sales 48 / Eng 96 / Res 58 / People 34 / Board 34 | mixed |

**Risk register** (per `board/risk-register-2026.md`): 3 CRITICAL (R1 hard-stops, R2 sales funnel, R11 Ivan bandwidth).

---

## Phase 26 candidates (ordered by impact)

| # | Action | Source | Impact | Effort |
|---|---|---|---|---|
| 1 | **Sales funnel revival** (Formspree) | Phase 8 #19 | 🔴 Unblocks revenue | 1-2h |
| 2 | **Hard-stops wrapper invocation** | Phase 8 #2 | 🔴 Closes AI safety hole | 16h (Kiki) |
| 3 | **Eval aggregate cron wiring** (nightly) | Phase 8 #10 | 🟠 First real eval signal | 4h |
| 4 | **Drift detection calibration** (30d) | Phase 8 #8 | 🟡 Tune thresholds | 0h (passive) |
| 5 | **Chaos-test scenario #1** (state corruption) | Phase 8 #9 | 🟡 Verify monitor path | 4h |
| 6 | **Spread Sunday-evening weekly crons** | Phase 8 #3 | 🟡 Fix 5 of 6 cron errors | 2h |
| 7 | **Fix `minimax-plan` provider** | Phase 8 OQ | 🟡 People dept score 34→50 | 1h |
| 8 | **Eval gate enforcement** | Phase 8 G2 | 🟠 Block low-pass agents | 8h |
| 9 | **Heartbeat self-validation** | Phase 26 #6 | 🟢 Detect silent failure | 4h |
| 10 | **Cost reporting per cron** | Phase 26 #7 | 🟢 Visibility | 4h |

**Total effort to ship all 10**: ~50h. At 2-person org, ~5 weeks of part-time work.

---

## What needs Ivan (decisions only Ivan can make)

| Decision | Recommendation | Source |
|---|---|---|
| Sales funnel: Formspree (1-2h) vs Worker revival (8-16h) | **Formspree** | `sales/funnel-revival-2026.md` |
| Decline richar-ruiz deal (22d stalled, anonymized) | **YES** | `state/sales.json` open_questions |
| Resurrect Rubicon EAS Worker later? | **LATER** (after $5K MRR) | `sales/funnel-revival-2026.md` |
| Apply to SIC (Start-Up Chile)? | **YES** (Q4) | `finance/funding-landscape-2026-Q4.md` |
| Open-source the agent framework? | **YES** (unlocks funding) | `finance/funding-landscape-2026-Q4.md` |

## What needs Kiki (technical decisions)

| Decision | Recommendation | Source |
|---|---|---|
| Invoke hard-stops wrapper globally? | **YES** (8-16h) | `operations/hard-stops-enforcement-audit.md` |
| Add eval gate enforcement (block low-pass)? | **YES** (8h) | `engineering/ai-safety-posture-2026.md` |
| Adopt M4 (time-bounded consensus) for board? | **YES** | `board/co-chair-decision-rights.md` |

## What agents can do autonomously

- Run chaos-test-runner scenario #1
- Wire eval-aggregate-pass-rate.py to nightly cron
- Spread Sunday-evening weekly crons
- Fix `minimax-plan` provider name
- Apply for SIC + Open Source Collective
- Run citation-coverage audit on full corpus

**Total autonomous work**: ~20h.
