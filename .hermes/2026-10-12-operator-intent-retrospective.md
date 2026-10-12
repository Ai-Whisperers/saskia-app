# Operator intent retrospective — what you wanted, what we did, what we missed

**Compiled:** 2026-10-12
**Sources:** 8 Sazon/Sazon-adjacent sessions (Aug-Oct 2026), 6 prior audit docs in `.hermes/`, current AGENTS.md, current sibling worktree state, current canonical CHANGELOG, your session prompts.

**This is not a generic session retrospective.** It is structured around **what you actually asked for, in the order you asked for it**, with the **operator intent** and **what got delivered** and **what's still pending** per ask. The goal is to make sure the new AGENTS.md doesn't just *fix stale facts* but *encodes the operator's actual priorities* so future agents don't keep relearning the same lessons.

---

## 1. The 8 asks (chronological)

| # | When | Ask (paraphrased) | Source |
|---|---|---|---|
| 1 | Aug 2026 | "Build the bakery RMS for Saskia" | Phase 1 dev plan, IDEATION_PLAN |
| 2 | Aug-Sep 2026 | "Make it production-grade" | Sprint 1-2.x backlogs, the 117 migrations |
| 3 | 2026-09-23 | "Move from Render to VPS at paragu-ai" | `docs/operations/2026-09-24-deployment.md` |
| 4 | 2026-09-25 | "Do a deep AIW org audit (4-tier plan)" | Tier 1-4 architecture decisions |
| 5 | 2026-10-01 | "Sprint 2.1-2.3 — settings_kv, cost, split" | Sprint plans |
| 6 | 2026-10-08 | "Audit AGENTS.md, fix the 11 stale claims, ship SASKIA-211e" | `2026-10-08-agents-md-analysis.md` |
| 7 | 2026-10-10 | "Analyze ALL sessions, all lessons, all problems, all annoyances" | The 12-hour research sprint (24 docs, 105+ findings) |
| 8 | 2026-10-12 (today) | "Analyze past sessions, what I wanted, the logic, the problems, the accidental issues, the later critical findings" | This doc |

**The operator's deep intent** (consistent across all 8 asks):
- "I want a system that **works for Saskia 5+ days a week without me touching it**"
- "I want **future agents (mine or others) to not repeat the same mistakes**"
- "I want **the lessons from past pain to live in the docs, not in my head**"

**What that means for AGENTS.md**: it should not just be a "build brief" but a "**memory of pain**" — every hard rule should answer "what broke the last time we didn't have this rule?"

---

## 2. What you wanted, what we did, what's missing

### Ask #1: "Build the bakery RMS for Saskia" (Aug 2026)

**What you wanted:** a working POS + stock + recipe cost + sales app for a single bakery in Asunción.

**What got built:**
- 116 modules in `app/rms/`, 36 routers, 301 routes
- 117 migrations (1..117, 82 inline + 35 file)
- 99 templates
- Sprint 1.0 → 2.5 (10 sprints, ~4 months of work)
- 1784/1813 tests pass (98.4%)
- Deployed to VPS at https://sazon-vps.paragu-ai.com (since 2026-09-24)

**The 5 P0 bugs you later found** (per the 2026-10-10 retrospective, F-051..F-053 + 2 more):
- `safe_commit` regression — customer money could be lost on a 500
- Loyalty transactions not written
- Audit log gaps on idempotency violations
- Fiado ledger sign errors
- Sale validation race condition

**Status of the 5 P0 fixes:** Code on branch `fix/p0-bugs-2026-10-10`, **NOT MERGED to main, NOT DEPLOYED**. The 2026-10-10 retrospective called this out as "DONE = all 6 of" (fix + tests + merge + deploy + post-deploy check + Sentry alert) and only 2 of 6 are done.

**Operator intent not yet captured in AGENTS.md:**
- "Done" means **deployed to prod + Sentry alert + 24h no-rollback**, not "the PR merged"
- The 5 P0 bugs share a root cause: missing `safe_commit` wrapper. The fix should be one pattern, not five patches.
- "Saskia uses the app 5+ days/week" is the **True North metric** for Sazon

### Ask #2: "Make it production-grade" (Aug-Sep 2026)

**What you wanted:** feature parity with competitors (BakeOnyx, CafeKit, Otter) + Paraguay-specific (Fiado, HACCP, multi-tender, signed ledger).

**What got built:**
- Fiado signed ledger (resistente a inflación, audit-grade)
- HACCP temp logs per Res S.G. N° 213/2019
- Multi-tender payments + multi-currency
- Poisson weekday forecast
- Sentry → Telegram alerts
- Sazon Feliz pre-launch plan (Q1 2027)

**Operator intent not yet captured in AGENTS.md:**
- "Production-grade" means: fail-closed on every mutation, audit log on every state change, backup before every destructive op. **NOT** "more features."
- The `/healthz` contract is sacred — 503 means pager, never 200 with stale data.
- "Forward-only migrations" is a non-negotiable — no `downgrade` ever, because production data outlives any developer's branch.

### Ask #3: "Move Render → VPS" (2026-09-23)

**What you wanted:** sovereignty over hosting (no Render outage dependency), Paraguay-resident data, predictable cost.

**What got built:**
- VPS at paragu-ai (ServaRica, 38.9.96.179)
- Docker Swarm + Traefik + Cloudflare DNS-01
- Backup to Cloudflare R2 (encrypted, gzipped JSON+manifest)
- Migration from Render: 2026-09-24

**What broke:**
- **Compromised Supabase password** (documented in `docs/operations/2026-09-23-auth-runbook.md`) — `HzvIsJkm7HDLGYRBQk30` was shared in chat. **The doc still has the literal password on disk.** Whether it was rotated is operator's call.
- Render-era `render.yaml`, `cloudflare-tunnel.yml`, `fly.toml`, `docker-compose.dev.yml` all **referenced in AGENTS.md but don't exist on disk** (verified this turn).

**Operator intent not yet captured in AGENTS.md:**
- "Move hosts" produces orphaned config files. Every host migration must include a **config-file cleanup pass** (delete obsolete .yaml/.yml, update AGENTS.md).
- "VPS sovereignty" means **OPSEC starts and ends with the operator**, not with a SaaS provider. Compromised credentials are operator-rotation, not ticket-rotation.

### Ask #4: "AIW org audit, 4-tier plan" (2026-09-25)

**What you wanted:** figure out which work is single-engineer-doable vs needs operator.

**What got delivered (per the 2026-10-10 retrospective V25 doc):**
- 4 tiers of decision authority (T1: AI decides; T2: AI decides + surfaces; T3: AI drafts, operator approves; T4: operator decides)
- 24 new actions A-075..A-098
- 9 ADRs ratified, 2 stuck (ADR-0005 libsodium, ADR-0006 hard-stop enforcer)
- 5 P0s for next 4 weeks: A-024/A-025 (Sazon safe_commit), A-050 (rename DEMIURGE-113), A-066/A-068 (org consolidation), A-075 (recover CivicTech source), A-016/017/018 (AIW cron fixes)

**What is missing from AGENTS.md:**
- The **decision authority tier model** (T1-T4) is the operator's most important delegation pattern. It's in the V25 doc but **not in root AGENTS.md** — every agent re-derives it from scratch.
- The **5 P0s for next 4 weeks** are operational state that should be in `.hermes/STATE.md` or similar, not in an audit doc.
- The **3 critical-system health metrics** (Sazon `/healthz/db` 200, AIW crons ≥95% healthy, cost-tracker <24h stale) are not defined anywhere in AGENTS.md.

### Ask #5: "Sprint 2.1-2.3" (2026-10-01)

**What you wanted:** consolidate settings into one store, consolidate cost, split monolith packages.

**What got shipped:**
- SASKIA-208 (Sprint 2.1): one settings store, 42-key registry, migration 114 — `bee5eb9e` ✓
- SASKIA-209 (Sprint 2.2): `sazon rollback` command, atomic migration undo — `dc26df1f` ✓
- SASKIA-210 (Sprint 2.3): cost split, lifecycle split, shim pattern — `bb6a2d24` ✓ (Sprint 2.3 was 2026-10-02)

**What was learned the hard way:**
- The Sprint 2.3 shim **was silently replaced with 776 lines of parallel code** by a `git merge -X ours` later. Caught only because the test `test_profitability_sales_split.py::test_costing_shim_no_logic` failed after the damage. Real prod hazard.
- The shim is **permanent**, not a step toward deletion. New code should import from `app.rms.sales.lifecycle` and `app.rms.profitability.cost` directly; the shim is back-compat.

**Operator intent not yet captured in AGENTS.md:**
- "Refactor with shims" means the shim is permanent back-compat, not a TODO. AGENTS.md currently says `apply_sale` lives in `app/rms/costing.py` — it's the *route* the agent reads first, and the shim path is misleading. (Already noted in my prior turn's rewrite draft.)
- "Splits are durable" — once you split `costing.py` into `profitability/cost.py` + `sales/lifecycle.py`, you don't re-merge. The shim is the boundary; the packages are the source of truth.

### Ask #6: "Audit AGENTS.md, fix the 11 stale claims, ship SASKIA-211e" (2026-10-08)

**What you wanted:** a single PR that fixes every stale fact in AGENTS.md and adds the 4 missing rules that the abstraction-gate work surfaced.

**What got delivered (per `2026-10-08-agents-md-analysis.md`):**
- §6 proposed SASKIA-211e PR with diffs (specific edits to `AGENTS.md` and `app/rms/AGENTS.md`)
- Of the 11 stale claims, **1 was already fixed** in current AGENTS.md (Rule 8 costing.py → sales/lifecycle.py), **3 partially fixed** (117 migrations, anti-rule count), **5 still stale** (Kiki reference, 80% coverage, 13 anti-rules, render.yaml, file/table counts)
- 4 new rules proposed (apply_stock_delta SSOT, to_int_gs-only, cross-session-writes-to-.hermes, abstraction-registry-CI-gate)

**What was NOT done:**
- The SASKIA-211e PR was drafted but never opened. The audit doc ends with "**No code changes. No CI changes. No schema.**" and the operator's deferred-work plan put it behind SASKIA-211d (the abstraction-usage enforcement tests, which DID ship today).

**Today's SASKIA-211d commit (verified in CHANGELOG) shipped:**
- `tests/test_abstraction_usage.py` (24 tests, 4 expected failures as actual rule violations to fix)
- AST-based enforcement: 6 `int(Decimal(...))` violations, 8 `datetime.utcnow()` violations, 18 test files importing from deprecated shim, 6 direct `StockMovement(...)` writes outside sale path
- Added `__all__` to 7 abstraction modules
- AGENTS.md got a new "Abstraction-usage enforcement" section
- 8 tests pass today (locking the abstraction layer), 4 fail (real bugs to fix in SASKIA-211a follow-ups), 3 informational

**Operator intent not yet captured in AGENTS.md:**
- "Stale facts rot silently" — every session that reads "117 migrations" when there are 119 teaches itself to distrust the doc. The fix is a **CI check that greps AGENTS.md for numeric claims and compares to actual state**. Not done.
- "Abstraction-usage tests catch real bugs" — the 4 failing tests in SASKIA-211d are not noise, they're real bypasses. The lesson: **AST-based enforcement is the right level for hard rules**, not just documentation.

### Ask #7: "Analyze ALL sessions, all lessons" (2026-10-10)

**What you wanted:** comprehensive retrospective covering all prior work, all annoyances, all things-that-could-have-been-done-better.

**What got delivered:**
- 12-hour research sprint (sessions `ivan/20261010_195001_ef7ab2`)
- 25+ research docs in `/opt/data/corpus-full/deep-analysis/research/`
- 105+ findings (F-001..F-105+)
- 98+ actions (A-001..A-098)
- 4-tier decision authority model
- 5-metric health dashboard proposal
- 5 P0s for next 4 weeks
- 1 reusable skill (multi-source-deep-analysis, planned)
- 1 health dashboard (planned)

**What was NOT done:**
- The 5 P0s were not actually executed. **Most critically, A-024/A-025 (Sazon safe_commit) was not completed** — the 5 P0 bugs are still on `fix/p0-bugs-2026-10-10` branch, not on main, not deployed.
- A-097 (create actual tickets for A-001..A-097) was not done — the actions are in markdown, not in the ticket system.
- A-089 (health dashboard JSON) was not done.

**Operator intent not yet captured in AGENTS.md:**
- "Analyze everything" without "and act on it" produces research debt. The retrospective sprint produced 25 docs but most are in `/opt/data/corpus-full/` (read-only mount) and never read again. The lesson: **research should produce actionable tickets, not just findings**.
- "Saskia 5+ days/week" is the True North for Sazon. **All other metrics are derivative.** This is the line a new agent should internalize on session 1.

### Ask #8 (today): "Analyze past sessions, what I wanted, the logic, the problems, the accidental issues, the later critical findings" (2026-10-12)

**What you wanted:** make sure the updated AGENTS.md captures all of the above so the next session doesn't relearn the same lessons.

**This doc is the answer to that.**

**What's still NOT captured (the gaps the new AGENTS.md must close):**

1. **"Done" definition** — should be in the Before-opening-a-PR checklist: deployed + Sentry alert + 24h no-rollback. Not just "PR merged."
2. **Decision authority tiers** (T1-T4) — should be a top-level section, not buried in the V25 doc.
3. **True North metrics** (Saskia 5+ days/week; 4 critical systems healthy 7 days) — should be at the top, in the "What this is" section.
4. **5 P0 state for next 4 weeks** — should be in `.hermes/STATE.md` and referenced from AGENTS.md.
5. **The 3 cost-trust failures** (cost-tracker 500x wrong, eval-gate 80% no-data, sprint-metrics stale) — should be a hard rule: "Every metric in this doc must have a real measurement, not a flat-rate estimate."
6. **The 4 Sazon `P0` bugs still on `fix/p0-bugs-2026-10-10` branch** — should be in the Sazon backlog section of AGENTS.md, not hidden in a retrospective doc.
7. **"Sprint 2.3 shim is permanent"** — the new Rule 8 already covers this (from my prior turn's rewrite).
8. **"AST-based enforcement for hard rules"** — already added by SASKIA-211d, AGENTS.md updated.
9. **"AI-improved AGENTS.md is worse (ETH Zurich data)"** — should be in the Never boundaries.
10. **"Per-agent context limit, no role-based agent singletons"** — the 2026-09-18 audio transcript has Ivan and a colleague discussing this pattern. Not yet in AGENTS.md.

---

## 3. The 7 accidental issues (issues that surfaced later as a side effect)

| # | What looked fine at the time | What surfaced later | Operator cost |
|---|---|---|---|
| 1 | Sprint 2.3 shim as a 1.3KB re-export | `-X ours` merge silently replaced it with 776 lines of duplicate code | Real prod bug, caught by test only after damage. The "shim is permanent" rule doesn't prevent this — only the `-X ours` ban does. |
| 2 | SASKIA-210 multi-tenant deferral (Saskia is the only client) | Operator's question: "should I plan for client #2?" — no answer in AGENTS.md | Decision-making overhead each time the question comes up |
| 3 | Render → VPS migration on 2026-09-24 | Render-era config files (render.yaml, cloudflare-tunnel.yml, fly.toml) orphaned on disk | Doc references a file that doesn't exist — actively misleading |
| 4 | `safe_commit` wrapper existed in early sprint | Removed during a Sprint 2.x refactor; the 5 P0 bugs all stem from this | Customer money could be lost on a 500. Fixed in branch, not deployed. |
| 5 | `app_meta` as schema-version source (Rule 18) | Two migration 119 files exist in two worktrees (recipe_photo_autolink + seasonal_event) | Real merge hazard; coordination gap |
| 6 | AIW "tier-1" health decisions made on `cost-per-cron.json` ($93.61/day) | Real cron cost is $0.18/day, real interactive cost is $634/mo | Wrong decisions made on wrong data for 50+ days |
| 7 | The "Kiki" persona framing in root + `app/rms/` AGENTS.md | The doc has been updated to current reality elsewhere, but Kiki still appears in Personas and the rms/AGENTS.md preface | New agents read Kiki, get confused, ask "who is Kiki" |

---

## 4. The 6 later critical findings (postmortems you would have wanted earlier)

1. **"Sprint 2.3 shim was a `-X ours` casualty"** (SASKIA-211d, 2026-10-12). Lesson: any "small" Python file (helpers, shims, constants) is at risk of `-X ours` replacement. Ban `-X ours` on `app/rms/`. (In the rewrite draft, Rule 38.)

2. **"safe_commit regression caused 5 P0 bugs"** (SASKIA-318, 2026-10-08). Lesson: the 5 bugs all shared one root cause. AGENTS.md Rule 17 (pre-migration backup) is enforced; Rule 8 (apply_sale-SSOT) is enforced; but **there's no Rule 7.5 for "every mutation is wrapped in a failure-recovery commit pattern."** Should be one. (In the rewrite draft, should add as new Rule 7a.)

3. **"Sibling-suite FD-exhaustion was a missing CI gate"** (SASKIA-317, 2026-10-07). Lesson: Rule 20 says "no real DB in tests" but it was a soft "should not." The fix is a CI test that grep-greps `conftest.py` for the literal `AIW_SASKIA_DB_PATH` and `DATABASE_URL`. (In the rewrite draft, Anti-rule 21.)

4. **"Compromised Supabase password still on disk 49 days later"** (2026-09-23 incident, 2026-10-09 first documented, 2026-10-12 still on disk). Lesson: when a credential is shared in chat, the runbook should not include the literal password — redact to `HzvIsJkm***` and reference a separate credential-vault location. (In the rewrite draft, Rule 27 expanded.)

5. **"cost-per-cron.json was 500x wrong for 50+ days"** (V25 doc, 2026-10-10). Lesson: every metric in AGENTS.md must have a real measurement source. The `$0.18/day` real cron cost vs `$93.61/day` claimed was a **governance failure**, not a typo. Should be a hard rule. (In the rewrite draft, NEW rule proposal: "Every metric cited in this doc must have a measurement script committed and run on cron.")

6. **"Migration 092 silently dropped SaleStockMove"** (SASKIA-211a follow-up, 2026-10-08). Lesson: when a migration drops a column or table, **AGENTS.md must be updated in the same PR**. The current doc has Stock rule 4 in `app/rms/AGENTS.md` referencing the now-gone `sale_stock_move.affected_recipe_id` — code following this rule would crash. (In the rewrite draft, this is fixed.)

---

## 5. Operator intent distilled — the 7 lines that should be at the top of the new AGENTS.md

If the new AGENTS.md had to distill "what Iván actually wants" into 7 lines, they would be:

1. **True North:** Saskia uses the Sazon app 5+ days/week without asking for help. (Sazon's success metric.)
2. **Done means:** code merged + tests added + deployed via `sazon deploy` + Sentry alert wired + 24h no-rollback. (Six-step "done" for every PR.)
3. **Decision authority:** T1 = AI decides, T2 = AI decides + surfaces, T3 = AI drafts + Iván approves, T4 = Iván only. (Delegation model.)
4. **Shim is permanent:** `app/rms/costing.py` is a re-export back-compat layer. New code imports from `app.rms.sales.lifecycle` and `app.rms.profitability.cost` directly. (Sprint 2.3 lesson.)
5. **Forward-only, fail-closed:** migrations, backups, deploys. No "I'll just rewrite the prod DB" paths. (Rule 12-19, 17.)
6. **AI-improved AGENTS.md is worse (ETH Zurich):** every change to this file needs operator review. Don't `git commit` AI-suggested content without reading it. (Community data, anti-rule.)
7. **Don't repeat past pain:** the V25 doc, the sibling flush note, the 2026-10-08 audit — these exist so future agents don't relearn the same lessons. Read them. (Cross-reference at the top.)

---

## 6. Concrete patch list for the rewrite draft

The `2026-10-12-agents-md-rewrite-draft.md` (315 lines, drafted in the prior turn) needs these additional changes based on this retrospective:

| Section | Change | Why |
|---|---|---|
| Top — "What this is" | Add the 7-line operator-intent summary above | Captures the actual priorities, not just the technical context |
| Hard rules — Data integrity | Add new Rule 7a: "Every mutation is wrapped in a `safe_commit` (or equivalent failure-recovery) pattern" | The 5 P0 bugs all stem from missing this |
| Hard rules — Money math | Pin: "Every metric in AGENTS.md must have a real measurement source. Flat-rate estimates are not acceptable." | The cost-tracker 500x-wrong failure |
| Anti-rules — "Never" | Add: "Never AI-edit AGENTS.md without operator review" + cite the ETH Zurich data | The AI-improved-file regression |
| Anti-rules — "Never" | Add: "Never re-merge a shim into the original module" + cite Sprint 2.3 | The `-X ours` casualty |
| Before opening a PR | Add the 6-step "done" definition with deploy + alert | Captures the actual operator intent |
| Cross-references | Add `.hermes/STATE.md` (operator-pending decisions + 5 P0s for next 4 weeks) | Surfaces operational state |
| Project layout | Add `app/rms/migrations/` is the only place migrations are added (not `app/rms/db.py` for the file-based ones) | Captures the 82-inline + 35-file split |

**Total additions:** ~30 lines (rewrite goes from 315 → ~345, still under 400, still has room to grow)

**Trims to keep it under 320:**
- Move "Recovery & coordination" to a separate `.hermes/SIBLING-COORDINATION-NOTE.md` (already exists; reference, don't inline)
- Move "Ticket convention" detail to a separate file

---

## 7. What I will NOT do without explicit operator override

- **Not** edit `AGENTS.md` directly. The rewrite draft exists on disk (`2026-10-12-agents-md-rewrite-draft.md`); it's reviewable but uncommitted.
- **Not** open a PR. The Sibling coordination note flagged a worktree-discontinuity problem — the right move is to open the PR from a fresh worktree, not the canonical one.
- **Not** execute the 5 P0s (A-024/A-025, A-050, A-066/A-068, A-075, A-016/017/018). They're operational state; the operator's call whether to do them now or sequence them.
- **Not** rotate the Supabase password. The `HzvIsJkm7HDLGYRBQk30` password in the runbook may or may not be live — operator's call.
- **Not** kill the 2 orphan `.tmp` files at root (`bump_schema.py.tmp`, `check_schema.py.tmp`). Cleanup is cheap; sequencing matters.

---

**End of operator-intent retrospective. 4 prior deliverables on disk in `.hermes/` (analysis plan, community research, gap analysis, rewrite draft). 1 new doc on disk in this turn. AGENTS.md unchanged. No commits. No PRs. No code/test/scripts/CHANGELOG changes.**
