# AGENTS.md gap analysis — 2026-10-08 audit vs 2026-10-12 state

**Date:** 2026-10-12
**Sources cross-referenced:**
- `2026-10-08-agents-md-analysis.md` (sibling audit, 16.3 KB, by session `ivan/20261008_231844_c3f34c`)
- `2026-10-12-agents-md-deep-analysis.md` (my prior turn, 30.4 KB)
- `2026-10-12-agents-md-community-research.md` (my prior turn, 26.8 KB)
- Live repo state (probed this turn)

**Question answered:** What does the 2026-10-08 audit say is wrong, and is it still wrong 4 days later? Did the sibling fix any of the 11 stale claims?

---

## 1. Status of the 11 stale claims from the 2026-10-08 audit

| # | 2026-10-08 claim | 2026-10-12 actual | Verdict |
|---|---|---|---|
| 1 | "Kiki" framing in Personas (L11) | Still says "Kiki, this assistant, future agents" (root AGENTS.md L11) | **STILL STALE** |
| 2 | "117 migrations, no gaps" (L18, L53) | `CURRENT_SCHEMA_VERSION = 117` is correct. Migration file count is 35 (range 56..117) with gaps 57-83 (these live inline in `app/rms/db.py` as `_migration_NNN_*` functions). | **PARTIALLY STALE** — the count "117" is right, the "no gaps" wording is misleading; the doc should say "82 inline in db.py, 35 as separate files, all numbered 1..117" |
| 3 | `apply_sale` path wrong: costing.py vs sales/lifecycle.py (L46) | Rule 8 has been UPDATED — now correctly says `app/rms/sales/lifecycle.py` and explicitly notes the costing.py shim | **FIXED** ✓ |
| 4 | "117 migrations" repeat (L53) | Same as #2 | same |
| 5 | "251 files, 45 tables, 117 migrations" (L109) | 289 files (verified). Tables: 64 (per my prior audit; sibling said 89 model classes which conflates tables with classes). | **STILL STALE** — counts drifted, but in different directions for different numbers |
| 6 | "Coverage gate: 80%; current is 35%" (L182) | `pyproject.toml` has `fail-under = 35`. So current is 35%, NOT 80% as the headline says. | **STILL STALE** — the 80% headline is aspirational, not current |
| 7 | Property tests cited (L184-185) | `test_money.py` (4.6 KB) and `test_units.py` (7.0 KB) still exist. `app/rms/AGENTS.md` adds 95% money / 90% costing gates not in root. | **STILL PARTIALLY STALE** — root doc has the file names, not the per-module coverage gates |
| 8 | "13 of 20 anti-rules enforced" (L210) | `tests/test_ci_anti_rules.py` has **14 test methods** (verified). | **STILL STALE** — count is 14, not 13 |
| 9 | Locked hotfix SHAs (L240-258) | All 5 SHAs verified present | **STILL CORRECT** ✓ |
| 10 | Ticket convention (L268) | Live branches SASKIA-211, 212, 213, 215 — all use the format | **STILL CORRECT** ✓ |
| 11 | `render.yaml` referenced but file removed (L2.2) | `render.yaml` still referenced in AGENTS.md L26 ("do not deploy to Render"). File STILL doesn't exist on disk (verified). | **STILL STALE** — reference is now actively misleading; the file is gone |

**Net:** of the 11 stale claims, **1 was fixed** (#3), **3 are partially stale** (#2, #5, #7), **5 are still stale** (#1, #6, #8, #11, plus #5's count drift), and **2 are correct** (#9, #10). 

## 2. New stale claims discovered this turn (not in the 2026-10-08 audit)

1. **Hard Rule 18 about `app_meta`**: doc says "`PRAGMA user_version` is NOT used (deliberate decision 2026-10-09 — see `docs/operations/2026-10-09-schema-version-source.md`)". I verified the doc referenced exists, so this one is correct. But: the doc also says "`SCHEMA_VERSION` constant in `app/rms/config.py`" but the actual constant is `CURRENT_SCHEMA_VERSION` — minor naming drift, low severity.

2. **`bump_schema.py.tmp` and `check_schema.py.tmp` at root** — these are scratch files, not committed anywhere per git status. They are real on disk and listed in `git status --short` as untracked. They shouldn't be on disk in the first place. The 2026-10-08 audit didn't mention them because git ignored them, but they exist now.

3. **Two separate migration 119 files in two different worktrees** (`_119_recipe_photo_autolink.py` in canonical, `_119_seasonal_event.py` in vaquita). The sibling flush note flagged this as a merge hazard. The current `CURRENT_SCHEMA_VERSION = 117` in canonical, so the 119 files are not yet "active" but they will become a real conflict when both branches try to merge. **AGENTS.md does NOT have a rule about migration-number coordination between worktrees.** This is a real gap — Finding B from my prior audit's `-X ours` ban is related but not the same.

4. **`app/rms/AGENTS.md` says "For Kiki and any agent modifying `app/rms/` modules"** — the same "Kiki" reference as the root doc, but worse because it's specifically directed at an outmoded persona. The 2026-10-08 audit missed this file's Kiki reference.

5. **`app/rms/AGENTS.md` Stock rule 4 about `sale_stock_move.affected_recipe_id`** — the 2026-10-08 audit correctly flagged this as outdated (table dropped in migration 092). **Verified still outdated.** This is a real bug in the docs — code following this rule would be referring to a non-existent table.

6. **The "Cycle 3" / abstraction-gates / sibling-state references**: the doc has nothing about the abstraction-gates worktree, the test_anti_rule suite (which exists, 14 tests), or the sibling-coordination protocol beyond the single line in §"Recovery & coordination" pointing to a deep doc.

## 3. Conflicts between the 2026-10-08 audit and the 2026-10-12 audit

My prior 2026-10-12 audit listed 6 stale claims. The 2026-10-08 audit listed 11. Intersection:

| 2026-10-08 (sibling) | 2026-10-12 (mine) | Resolution |
|---|---|---|
| Rule 8 costing.py → sales/lifecycle.py (L46) | Same | Both correct. **Now fixed in current AGENTS.md** ✓ |
| Rule 12 "117 migrations, no gaps" (L18, L53) | Same | Both correct. Still misleading. |
| Coverage 80% (L182) | "35%→40%" | Mine was wrong. Sibling's "80% gate / 35% current" is more accurate. |
| 251 files / 45 tables / 117 migrations (L109) | "251→291 files, 45→64 tables" | Both correct on direction. Actual: 289 files, 64 tables, 117 migrations |
| 13 anti-rules (L210) | (not in mine) | New. 14 currently. |
| `render.yaml` (L2.2) | (not in mine) | New. Still referenced, still missing. |
| 5 missing rules (Section 5) | Addendum 1 found 5 different missing rules | Different. Addendum 1's findings: shim policy, -X ours ban, anti-rule 21 (no prod DB), Supabase password regex, app/rms/AGENTS.md cross-ref. 2026-10-08's findings: apply_stock_delta, to_int_gs-only, reuse-abstractions, cross-session-writes. **Both sets are valid; Tier 2 should include ALL 9.** |

**Synthesis:** the combined Tier 2 docs PR should include:
- Fix 5 still-stale claims (1, 6, 8, 11, plus #2's "no gaps" wording)
- Add 9 new rules (5 from 2026-10-08 + 4 from 2026-10-12 + 1 from this turn = migration-number coordination)
- Trim "Personas" + "Build brief" + "How to work a session" (move to CONTRIBUTING.md or skills)
- Add community-pattern sections (Build & test commands, Project layout, Always/Ask first/Never summary, Before opening a PR checklist, CLAUDE.md import)

Total: ~30-line additions + ~30-line trims + 1 new file (CLAUDE.md). Net ~0 lines, much higher density.

## 4. Concrete draft of the proposed AGENTS.md rewrite (Tier 2 deliverable)

The actual proposed AGENTS.md content lives in a separate file: `2026-10-12-agents-md-rewrite-draft.md`. This gap-analysis doc is just the "why"; the rewrite draft is the "what."

**The rewrite is structured per the community 5-line checklist + Sazón's existing load-bearing content:**

1. What this is (1-2 sentences)
2. Build & test commands (12 lines, with flags)
3. Project layout (8 lines)
4. Boundaries summary (10 lines, Always / Ask first / Never)
5. Hard rules (37, kept as-is, organized by category) — ~180 lines
6. Anti-rules (20, kept as-is) — ~60 lines
7. Locked hotfixes (5, kept as-is) — ~20 lines
8. Before opening a PR checklist (12 lines)
9. Cross-references — ~8 lines

**Target line count:** ≤320 (currently 395). Per Augment eval, gains reverse past 300 lines; the rewrite must come under 320 to capture any of the empirical benefit.

## 5. The 5 things to NOT do (anti-patterns the Sazón doc should also document)

The community research (continuumcode.ai, dylanengelbrecht.dev, agentpatterns.ai) converged on 5 anti-patterns that AGENTS.md itself should warn against:

1. **Don't `git merge -X ours` on `app/rms/`.** Already in my Addendum 1 Finding B → New Rule 38.
2. **Don't add a second migration with the same number.** NEW (this turn). Migration 119 has two distinct files on two worktrees; coordination gap.
3. **Don't auto-edit AGENTS.md to "improve" it from an AI suggestion without operator review.** NEW (community ETH Zurich data). The empirical finding is that AI-improved AGENTS.md files are *worse*, not better.
4. **Don't keep `.tmp` files at the repo root.** NEW (this turn). `bump_schema.py.tmp` and `check_schema.py.tmp` are on disk; should be deleted.
5. **Don't put persona-specific framing ("For Kiki") in module-level AGENTS.md files.** NEW (this turn). The 2026-10-08 audit's recommendation to remove the "Kiki" reference from root AGENTS.md should also apply to `app/rms/AGENTS.md`.

## 6. Open questions for the operator

1. **Where should the "Personas" narrative go** after trim? Options: (a) `CONTRIBUTING.md`, (b) a session-start skill, (c) deleted entirely. The persona is in the doc because it was the original engagement model; the current reality is different. Recommendation: (a) — move to `CONTRIBUTING.md` as a historical note.
2. **What to do about the `app/rms/AGENTS.md` orphan.** It has 30 rules of load-bearing content (money, units, time, recipe, stock, testing, migration, tooling) — these are real, not a duplicate of the root doc. Recommendation: keep the file, but add a 1-line cross-ref from the root doc, and update the "Kiki" reference to current reality.
3. **Should Tier 2 add the 1-line `CLAUDE.md` import?** Cost: 1 line of code. Benefit: cross-tool compatibility. Recommend: yes.
4. **Should Tier 2 include the 9 new rules from §3 above, or be split?** All 9 are small (1-3 lines each). Single PR is fine. Recommend: include all 9.
5. **Should the rewrite target be ≤320 lines or ≤300?** Augment's "gains reverse past 300" suggests ≤300. Current is 395. Adding the new sections and trimming the narrative gets to ~320. To hit ≤300, would need to move more content to skills (e.g., the "Locked hotfixes" section, the "Tech stack" section). Recommend: target ≤300, move Tech stack to pyproject.toml cross-ref.

## 7. Process risk: the sibling discontinuity

The 2026-10-08 sibling session flagged a **worktree-discontinuity problem**: files the sibling wrote (canonical plan v2, sibling-state-readout, drift-numbers json, test-coverage-matrix json) **disappeared between writes**, while files from the SASKIA-212 sibling appeared and disappeared in `git status`. The most parsimonious explanation is another session using `git checkout -- <file>` or otherwise resetting working-tree state.

**Implication for my Tier 2 PR**: if I ship it in this canonical worktree, my changes could be reset by the sibling. Per `docs/operations/2026-10-04-sibling-session-coordination.md`, the right move is to:
1. Work on a fresh worktree (`/opt/data/work/saskia-app-211e-agents-md` or similar)
2. Branch off `main` (the abstraction-gates worktree, where the SASKIA-211 work is consolidated)
3. Open the PR via `gh pr create` against `Ai-Whisperers/saskia-app:main`
4. Do NOT touch the canonical worktree's AGENTS.md directly

**Recommendation:** the Tier 2 PR should be opened from a fresh worktree, not from `/opt/data/work/saskia-app`. The PR body draft in the community research doc assumes this.

---

**End of gap analysis. Files unchanged: AGENTS.md, app/rms/AGENTS.md, all worktrees.**
