# Prioritized "What's Next" — Synthesis of All Transcriptions

**Compiled:** 2026-08-24 from synthesis of:
- August 13, 2026 conversation (departments brainstorm, 3 speakers)
- August 14, 2026 (PHASE-13 plan — Eneve + coaching)
- August 24, 2026 (this session — full execution)

---

## Bottom Line

We have **two unfinished bodies of work** from two earlier sessions:
1. **Org foundation** (Eneve migration) — *built but not self-running*
2. **Coaching product** (research → agents) — *researched but not built*

Plus a **third body of work emerged from this session's transcription**:
3. **Department monitor + tooling tiers + customer template** — *patterns surfaced in conversation, not yet built*

The **single bet**: hit the self-running milestone first (Days 15-30 of the 90-day plan), then build coaching product (Days 31-90), then scale (Days 91-120).

---

## Critical Missing Pieces (Priority Ordered)

### MUST DO (Business-Blocking)

| # | Action | Time | Cost | Why |
|---|--------|------|------|-----|
| 1 | **Send first prospect WhatsApp** | 5 min | $0 | Unblocks entire pipeline |
| 2 | **Top up $20 OpenRouter** | 2 min | $20 | Activates real agent runs |
| 3 | **Run first free quick-win** | 45 min | $0 | Tests pipeline end-to-end |

### SHOULD DO (Foundation Verification)

| # | Action | Time | Source |
|---|--------|------|--------|
| 4 | Hit 7-day self-running milestone | 0h (observe) | PHASE-13 §4.3 |
| 5 | Run chaos-test B + C | 1h | PHASE-13 §4.2 F1#4 |
| 6 | Wire eval-gate as cron post-brief hook | 2h | PHASE-13 §4.2 F1#5 |
| 7 | Verify 24 unverified sub-agents + 8 cross-cutting | 4h | PHASE-13 §4.2 F1#2 |

### COULD DO (From Aug 13 Transcription)

| # | Action | Time | Source |
|---|--------|------|--------|
| 8 | Build `dept-monitor` agent (16 watchers) | 6h | New — Aug 13 quote |
| 9 | Write tooling-tiers doc (1-5, 5-20, 20+) | 4h | New — Aug 13 quote |
| 10 | Build generic customer template | 12h | New — Aug 13 quote |
| 11 | Split into per-department repos | 8h | New — Aug 13 quote |

### WILL DO (Coaching Product)

| # | Action | Time | Source |
|---|--------|------|--------|
| 12 | Build 7 internal coaching agents | 50h | PHASE-13 §4.4 |
| 13 | Build 7 external coaching agents | 80h | PHASE-13 §4.5 |
| 14 | Build 11 coaching skills + 4 Sunstein/Solstein | 168h | PHASE-13 §4.5 |
| 15 | Ship coach-practitioner MVP | 16h | PHASE-13 §4.6 |

---

## The Strategic Question

**Q: Should we keep building, or sell first?**

**Arguments for STOPPING to sell:**
- All 49 agents built, 235 skills, 90 scripts, 83 cron jobs
- Conversion pipeline built (run-conversion.py + send-conversion-sequence.py)
- Webhook endpoints live
- $293/mo LLM cost tracked
- The next dollar requires a real customer, not another agent

**Arguments for KEEPING BUILDING:**
- Coaching product unlocks $500 MRR per customer (vs current $0)
- Self-running milestone not yet verified (7-day test pending)
- 24 Tier 2 agents unverified
- Department-monitor pattern not implemented (would improve 12-factor score)

**My answer: STOP BUILDING, START SELLING.** The system is at 9.0/10 audit, 17/17 eval-gate pass, $293/mo cost. Diminishing returns on more building.

---

## Concrete Next Actions (in order)

### Today (Do A)
1. Pick Rubicón EAS or Mark NL
2. Send 3-sentence WhatsApp
3. Wait for reply

### Tomorrow (Do B IF A succeeded)
4. Schedule 30-min Zoom
5. Run coach-practitioner agent
6. Use GROW framework + Sunstein ethics + ICF competencies

### This Week (Do C)
7. If session went well, run-conversion.py to score
8. If score >= 70, approve via WhatsApp
9. send-conversion-sequence.py triggers 3-email funnel

### This Month (Do D)
10. First customer → $500 MRR
11. Top up $20 OpenRouter
12. Run 7-day self-running verification (just observe)

---

## Sleep Note

The August 13 transcription has you saying "I have not slept since yesterday." This is real concern. The system is fully documented. Tonight's blocker is **rest**, not more building. The 3 business blockers can be addressed in 5 minutes total.

---

**Final recommendation:** Sleep. Tomorrow, send one WhatsApp.
