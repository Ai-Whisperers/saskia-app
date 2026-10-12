# Self-Running Milestone — Definition + Check

> Definition of "self-running org" + how to verify we're there.
> **Last updated**: 2026-08-14

---

## Definition (per OP-4)

**A self-running org is one where:**
1. All 7 Tier-1 lead agents deliver reliably for 7+ consecutive days
2. 0 cron jobs in error state for the same period
3. 0 "is X live?" messages from Ivan in any 7-day window

If all three conditions hold for 7 consecutive days, the org is **self-running at v0.2.0**.

---

## Verification procedure

### Daily check (automated)

`/opt/data/agents/scripts/self-running-check.py` (to be implemented in 30-day loop):

```python
# Pseudocode
deliveries_ok = check_deliveries_last_7_days()  # 7/7 agents delivered
cron_ok = check_cron_errors_last_7_days()      # 0 in error
is_x_live = count_is_x_live_messages()         # 0 in chat history

if deliveries_ok and cron_ok and is_x_live:
    return {"status": "self-running", "as_of": today()}
else:
    return {"status": "not-yet", "missing": [...what's missing...]}
```

### 7-day rolling window

- Day 1: cron-health, all 7 agents deliver
- Day 2: same
- Day 3: same
- Day 4: same
- Day 5: same
- Day 6: same
- Day 7: same → **SELF-RUNNING ACHIEVED**

If any day fails, reset window to day 1.

---

## What "deliver reliably" means

| Agent | Cadence | Required deliveries in 7d |
|-------|---------|---------------------------|
| business-analyst | Daily 06:30 PYT | 7 |
| management-coordinator | Mon+Thu 17:00 PYT | 2 |
| kiki-coach | Fri 17:00 PYT | 1 |
| finance-controller | Fri 18:00 PYT | 1 |
| sales-pipeline | Daily 12:00 PYT | 7 |
| engineering-roster | Tue+Fri 17:00 PYT | 2 |
| research-tracker | Sun 18:00 PYT | 1 |

**Total**: 21 deliveries in 7 days (acceptable with weekend variation)

## What "cron in error" means

A cron job with `last_status == 'error'` for > 24 hours.

## What "is X live?" means

Telegram/WhatsApp messages from Ivan containing:
- "is X live?"
- "are you running?"
- "did X deploy?"
- "did you do Y?"

Counted by keyword scan in chat logs (Phase 9B).

---

## What breaks self-running

Common reasons:
1. **LLM rate limit** → all agents pause → 0 deliveries → not self-running
2. **Cron job in error** → 1+ jobs miss delivery → not self-running
3. **Hard-stop blocks action** → Ivan needs to intervene → "is X blocked?" messages
4. **Cost cap breach** → agents halt → not self-running
5. **State corruption** → recovery takes time → not self-running

---

## How to recover from non-self-running

1. **Identify root cause**: heartbeat log, cron error, cost log
2. **Fix root cause**: per FAILURE-MODES.md
3. **Manual run affected agents**: `hermes cron run <id>`
4. **Verify recovery**: outbox file written, state updated
5. **Restart 7-day counter**: from day 1

---

## Current state (as of 2026-08-14)

- All 7 agents built ✅
- 6 of 7 agents deliverable (some in pending state, awaiting cron trigger)
- 4 cron jobs in error state (per heartbeat)
- 3 P0 gaps remaining (per gap audit)

**Self-running status**: NOT-YET (just kicked off)

**Target**: 7-day self-running by 2026-09-15 (30 days from now)

---

## When self-running is achieved

Write `/opt/data/agents-v2/SELF-RUNNING-ACHIEVED.md`:

```markdown
# Self-Running Achieved — {date}

**Status**: v0.2.0 self-running

## Evidence
- 7-day deliveries: {count}/{expected}
- 7-day cron errors: {count}
- 7-day "is X live?" messages: {count}

## Next milestone
- v0.3.0 review (90-day)
```

---

## Cross-references

- `/opt/data/agents-v2/PLAN-v5.md` Part 9 (operational disciplines)
- `/opt/data/agents-v2/FAILURE-MODES.md` (what breaks self-running)
- `/opt/data/agents-v2/THREAT-MODEL.md` (what attacks could break self-running)
- `/opt/data/agents/DECISIONS-2026-Q3.md` (OP-4: self-running milestone)
- `/opt/data/agents/REVIEW-2026-Q4.md` (30/60/90-day review)
