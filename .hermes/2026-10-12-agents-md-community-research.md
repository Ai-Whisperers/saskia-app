# Community research — how people set up AGENTS.md (2026-10-12)

**Goal:** synthesize community conventions to compare against the current Sazón `AGENTS.md` (395 lines, 25 KB, 21 sections, 8 sub-sections, 2 tables, 12 path cross-refs) so the next session has a clear "what to keep vs. what to change" picture. **No AGENTS.md edits in this turn** — research only.

**Sources read (10):**
1. `https://github.blog/ai-and-ml/github-copilot/how-to-write-a-great-agents-md-lessons-from-over-2500-repositories/` — GitHub's own analysis of 2,500+ public `agents.md` files.
2. `https://agents.md/` — the open-convention spec site (60k+ projects).
3. `https://github.com/agentsmd/agents.md` — same project's source repo.
4. `https://blog.buildbetter.ai/agents-md-complete-guide-for-engineering-teams-in-2026/` — long-form engineering-team guide.
5. `https://agent-ready.dev/how-to-write-an-effective-agents-md` — practical write-up, Linux-Foundation context.
6. `https://www.agentpatterns.ai/standards/agents-md/` — schema + tooling-ecosystem analysis.
7. `https://continuumcode.ai/guides/agents-md/` — format + tool-support matrix.
8. `https://dylanengelbrecht.dev/insights/agents-md-standard` — "operating document" framing, 200-line budget.
9. `https://github.com/artificial-intelligence-first/ssot/blob/main/docs/README_AGENTS.md` — the *most prescriptive* SSOT/policy doc, 2025-12 revision.
10. `https://markdownformatting.com/agents-md` + `https://viewmarkdown.com/agents-md` + `https://fablerlabs.com/agents-md-example` — practical copy-paste templates.
11. `https://github.com/googlarz/agents-sync/blob/main/docs/agents-md-spec.md` — `agents-sync` tool's spec, defines a sync-from-AGENTS.md pattern.
12. `https://github.com/sno-ai/mda/blob/main/spec/v1.0/06-targets/agents-md.md` — formal JSON-Schema target spec for AGENTS.md frontmatter.
13. `https://community.openai.com/t/agents-md-file-optimization/1369152` — practitioner critique ("most of that generated content is just burning tokens").

---

## TL;DR — community converges on these rules

| Convention | Source consensus | Sazón current state |
|---|---|---|
| **Root location, exact-case `AGENTS.md`** | Universal | ✅ Correct |
| **Plain Markdown, no required schema** | Universal | ✅ Correct |
| **Load-bearing content: commands, boundaries, conventions, structure** | Universal | ✅ All present |
| **Three-tier boundaries (Always / Ask first / Never)** | Strong consensus (≥7/13 sources) | ⚠️ Partially — "Hard rules" + "Anti-rules" cover Never well; no formal Always/Ask-first split |
| **Keep root file short (100-200 lines, ≤500)** | Strong consensus (≥6/13) | ❌ Currently **395 lines** — at the upper bound |
| **Imperative, specific, falsifiable** ("DO NOT use `any`", not "write clean code") | Universal | ✅ Mostly — the hard rules are good examples |
| **Exact commands with flags** (not descriptions) | Universal | ⚠️ Partial — many rules reference paths but few show literal commands |
| **Negative examples ("DO NOT ...")** | Strong consensus (≥6/13) | ✅ Excellent — 20 anti-rules is a major strength |
| **Self-contained "Don't touch" / generated-files list** | Strong consensus (≥5/13) | ⚠️ "Locked hotfixes" section is good; missing `migrations/`, `__pycache__/`, generated dirs |
| **Per-package AGENTS.md for monorepos (delta-only)** | Strong consensus (≥4/13) | ⚠️ `app/rms/AGENTS.md` exists but is orphaned (Finding E in audit) |
| **Update AGENTS.md in the same PR as the convention** | Universal | ⚠️ "Treat it as code" is in the doc but not enforced (no CI check that AGENTS.md was updated) |
| **Treat tool-specific files (CLAUDE.md, .cursorrules) as symlinks/imports** | Strong consensus (≥3/13) | ❌ Not done — Sazón doesn't have a CLAUDE.md or import wiring |
| **Don't duplicate README content** | Universal | ⚠️ "What this repo is" section partly duplicates README.md |
| **Pin tool versions in the Tech Stack section** | Universal | ⚠️ Versions present but not as a table (the convention is "table with versions") |
| **Definition of Done checklist agents can self-verify** | Mentioned in 2/13 sources | ❌ Not present |
| **Frontmatter is optional; metadata under `metadata.mda.*` if used** | Spec (sources 12, 5) | ❌ No frontmatter — Sazón is one of the frontmatter-free ones (which is fine) |
| **Use Skills/extensions for task-specific content; keep AGENTS.md as the index** | Strong consensus (≥3/13) | ✅ Skills exist (`saskia-rms-development`, etc.) and are loaded on demand |
| **AGENTS.md degrades in 3 conditions: stale, oversized, mismatched-with-dynamic-envs** | Source 8 | ⚠️ Stale is real (6 stale facts in our audit); oversized is at the limit |

---

## The "200-line" question — and what the Sazón doc has earned its length on

Source 8 (Dylan Engelbrecht) argues for **~200 lines at the root, never more** because:
- every line is loaded on every session
- past one screen, instructions start competing
- deletion is the highest-value edit available

Sazón's AGENTS.md is **395 lines** — exactly double the budget. But it has earned most of its length. Per line, the highest-value content is:
- 37 numbered hard rules across 6 categories (money, data integrity, migrations, time zones, UI, security, deployment, process)
- 20 anti-rules
- Locked hotfixes with revert-impact lines
- Cross-references to 12 deeper docs

**The bloat is concentrated in two places:**
1. **The "Build brief" section** (lines ~280-320) — narrative about Iván's role vs "Kiki", the engagement model history, the IDEATION_PLAN. None of this changes what the agent does; it belongs in CONTRIBUTING.md or the worktree handoff doc.
2. **Some of the 12 cross-references** at the bottom — a link to `IMPROVEMENT_BACKLOG.md` and `WHAT_NEXT.md` (operator-facing punchlists) duplicates the role of "what should I work on next" already covered in the IDEATION_PLAN cross-ref.

**What's missing that the 200-line budget is currently buying with extra room:**

- **Three-tier boundaries** (Always / Ask first / Never) is the #1 community-consensus section. Sazón's split (Hard rules = "Never/Always-with-exceptions", Anti-rules = "Never this technology") is functionally equivalent but the formal split would let a new agent read boundaries in 30 seconds. Currently it has to read 37 + 20 = 57 numbered items.
- **"Don't touch" list** — generated files, vendored code, migrations directory. Locked hotfixes covers some; but `migrations/` is implicitly "never edit a shipped one" via Rule 14 — the file doesn't enumerate which dirs to leave alone.
- **Definition of Done checklist** — most of the elements are scattered: "tests pass", "ruff clean", "CHANGELOG updated", "PR references a ticket". A single "before opening a PR" list near the top would let a new agent self-verify.

---

## Concrete recommendations (organized by the 5-line checklist from source 10)

Source 10's 5-line checklist:

1. **Commands** — exact invocations. Sazón is partial (CI commands buried; no `make`/`sazon` CLI command at the top). **Add** a "Build & test commands" block at the top with the canonical incantations: `uv sync`, `uv run pytest -q`, `ruff check .`, `sazon migrate`, `sazon rollback`, `git push origin <branch>`.
2. **Layout** — where things live. Sazón's "What this repo is" section is good but doesn't include `app/rms/` (the actual model + business-logic layer), `app/routers/`, `tests/`, `scripts/`, or `.hermes/`. **Add** a 1-line "Map" pointing to each.
3. **Conventions** — non-obvious rules. Sazón's hard rules cover this; the 37 numbered rules ARE the conventions. **Keep**, but reorganize into Always/Ask-first/Never to match the community norm.
4. **Do-not** — generated/protected paths. Sazón has "Locked hotfixes" but no generated-file list. **Add** a one-line: "Do not edit `migrations/058_*` through `migrations/119_*` (only create new). Do not edit `__pycache__/`, `.venv/`, `.ruff_cache/`, `app/CHANGELOG.md` is auto-managed."
5. **Verify** — exercise changes, don't just typecheck. Sazón has "single test run" guidance but no "before PR, run: `uv run pytest -q -k <your_change> && ruff check . && sazon migrate --dry-run`" line. **Add** that.

---

## What other repos do that Sazón doesn't — but probably should (or shouldn't)

### Should consider

1. **Symlink `CLAUDE.md → AGENTS.md`** (sources 4, 5, 7, 8, 10). Sazón is a multi-agent repo (Hermes + Claude Code + Codex all work it). The cross-tool `AGENTS.md` is already in the right place; adding `CLAUDE.md` as a one-line `@AGENTS.md` import (or symlink) makes the repo work for Claude Code without duplicating instructions. **Cost: 1 line of code, ongoing zero**. **Verdict: ship**.

2. **Per-package AGENTS.md for sub-areas** that break root rules. Sazón already has `app/rms/AGENTS.md` (Finding E: it's orphaned). The community pattern is *delta-only* nested files. Either:
   - delete the orphan + add 1 line in root AGENTS.md referencing it, OR
   - rewrite the orphan as a delta-only file (no rule restatement, just the deltas).
   The first option is lower risk. **Verdict: Tier 2 add (already in audit).**

3. **"Before opening a PR" checklist** (sources 1, 2, 10). One bulleted list near the top. Sazón's rules 35 (CHANGELOG) and 37 (PR references ticket) cover two of the items; the rest are scattered. **Verdict: add as Tier 2**.

### Should NOT do (despite community pattern)

1. **Frontmatter**. Source 12 defines an optional YAML-frontmatter schema; sources 5 and 7 say it's fine to omit. Sazón's no-frontmatter choice is correct — adding it gains nothing because the file is loaded by tools that read it as Markdown, and the metadata would be redundant with the title and headings.

2. **Trimming the 37 hard rules to fit a 200-line budget**. The rules are the highest-value content in the file. A new agent reading only the boundaries would miss the money (to_int_gs) and migration (forward-only) specifics that have saved real incidents. Trimming would cost real value. **Better**: trim the narrative ("Build brief", "How to work a session" — these duplicate what skills like `saskia-rms-development` already encode) and keep all 37 rules.

3. **`agents-sync` style symlink fan-out** (source 11). The tool generates `CLAUDE.md`, `.cursorrules`, `GEMINI.md`, etc. from a single `AGENTS.md`. Sazón has 2-3 active agents but not 9+. The cost of adopting `agents-sync` (CI, generated-file review) is higher than the cost of a 1-line `CLAUDE.md` import. **Verdict: skip; do the 1-line import instead.**

4. **Restructure into Always/ Ask first/ Never exclusively**. The community pattern is clean but the 37 hard rules are *time-tested* and re-grouping them invites a session to "improve" a rule that wasn't broken. The pragmatic compromise: **add** a 3-line Always/Ask first/Never summary at the top that cross-references the 37 rules, don't re-group them.

---

## Bad practices the Sazón doc already has (per community criteria)

From the community's "common mistakes" lists (sources 4, 5, 8, 10):

1. **Vague conventions** — the Sazón doc is strong here. Almost every hard rule is falsifiable. **Score: A**.

2. **Copy-pasting README content** — `What this repo is` partly duplicates the GitHub repo description and `README.md`. **Score: C**; the section could be 3 lines instead of 12.

3. **Stale guidance** — 6 verified-stale facts in the audit (migrations 117→119, files 251→291, etc.). **Score: D**. This is the doc's biggest weakness — every stale fact teaches the agent to ignore the doc.

4. **Omitting build and test commands** — partial. The Testing section lists `uv run pytest` but doesn't list the canonical CI gate, the dry-run migration command, the rollback command, or the pre-commit setup. **Score: C+**.

5. **Over-stuffing** — at 395 lines, the doc is at the upper bound of "still readable." The "Build brief" + "How to work a session" sections are the main offenders. **Score: B-**.

6. **No negative examples** — 20 anti-rules is exemplary. **Score: A+**.

7. **No "don't touch" list** — partial. Locked hotfixes covers the must-not-revert list; missing is the generated-files / vendored / migrations directory list. **Score: C+**.

8. **Putting secrets in the file** — never happens. **Score: A+**.

---

## What to actually change — concrete Tier 2 deltas (rewritten for the new community-research context)

The original Tier 2 (in the analysis plan) had 6 stale-fact fixes + 5 session-grounded rules. Adding the community-research deltas, the new Tier 2 is:

| # | Change | Lines | Community-pattern source | Why |
|---|---|---|---|---|
| 1 | Add "Build & test commands" block at the top (5-7 commands) | +12 | 5-line checklist, source 10 | Highest-ROI section per community consensus |
| 2 | Add "Layout / Map" 1-liner per major dir | +6 | Source 8, 10 | Agents stop scattering files |
| 3 | Add "Don't touch" list (migrations, generated, vendored) | +8 | Sources 4, 5, 8, 10 | "Missing don't-touch section" is the most-cited mistake |
| 4 | Add 3-line Always/Ask first/Never cross-ref summary at top | +5 | Sources 4, 6, 8 | #1 community pattern; lets new agents read boundaries in 30s |
| 5 | Add "Before opening a PR" checklist | +8 | Sources 1, 2, 10 | Definition-of-done pattern |
| 6 | Add `CLAUDE.md` import (or symlink) | +1 (new file) | Sources 4, 5, 7, 8, 10 | Cross-tool support; one-line cost |
| 7 | Fix the 6 stale facts | -3 / +6 net | (audit) | Stale guidance is the biggest doc weakness |
| 8 | Trim "Build brief" + "How to work a session" to 1-line cross-refs | -40 | (audit) | Move narrative to skills + CONTRIBUTING.md |
| 9 | Add 5 session-grounded rules (Addendum 1) | +12 | (audit) | shim policy, -X ours ban, etc. |
| 10 | Cross-ref to `app/rms/AGENTS.md` | +1 | Source 9 SSOT pattern | Fixes the orphan |
| **Net** | | **+16 lines (≈411 total)** | | |

Net: file grows from 395 → ~411 lines, but density of actionable content goes up significantly, narrative bloat comes out, and the doc gains the 3 community-priority sections (commands, layout, don't-touch) that it currently lacks.

---

## Open questions for the next session (and for the operator)

1. **Do we want the 1-line `CLAUDE.md` import?** If yes, the import line is `@AGENTS.md` (Claude Code's import syntax) and the file is 1 line. If no, leave it.
2. **Is the "Build brief" narrative actually load-bearing for any agent?** If a session never reads it, deleting it loses nothing. If a new session ever needs the "who is Iván" context, it should live in a skill or in `CONTRIBUTING.md`.
3. **Should the 37 hard rules be regrouped into Always/Ask first/Never, or kept as-is with a 3-line summary cross-ref?** The audit's recommendation is the latter (less risk of "improving" working rules). Worth a 1-sentence decision.
4. **What about the 3 other docs that duplicate the rules** (`docs/operations/2026-10-04-sibling-session-coordination.md`, `docs/operations/2026-10-04-test-execution-plan.md`, `IMPROVEMENT_BACKLOG.md`)? The community pattern is "AGENTS.md as the index, link out for detail." Sazón already does this. Just confirming the 12 cross-refs at the bottom are all real links, not 404s.
5. **Frontmatter yes/no** — community says optional; spec says optional. Sazón has none. Adding it is a one-time cost but no benefit. Recommendation: don't add.

---

**End of community research. AGENTS.md is unchanged. No commits, no PRs, no code edits.**


---

# Addendum — empirical research + concrete rewrite plan

## Empirical data points (from sources read after Addendum 1)

| Source | Finding |
|---|---|
| **ETH Zurich AGENTbench** (cited in `Taiizor/agents-md-cookbook` README) | Auto-generated `/init` AGENTS.md files *reduce* task success by ~3% and *raise* inference cost by 20-23%. **Implication for Sazón**: the 395-line current file is past the point of measurable benefit. Trim, don't grow. |
| **Augment golden-PR eval** (cited in same README) | 100-150 line sweet spot. Numbered workflows boost correctness +25%. Decision tables and 3-10 line real-code examples boost reuse +20%. **Gains reverse beyond ~300 lines.** |
| **GitHub review of 2,500+ repos** | Best files lead with commands + flags. "Never commit secrets" is the most common helpful constraint. Six core areas: commands, testing, project structure, code style, git workflow, boundaries. |
| **Codex agentops pattern** (`iLashley/CodexAgentLedger`) | Real-world pattern: pair `AGENTS.md` (rules) + `TASKS.md` (state) + `STATUS.md` (snapshot) + `.agent/runs/*.json` (audit trail) + `Makefile` (tooling API). Sazón's `.hermes/` covers some of this (`plans/`, `archives/`) but not the `Makefile`+`STATUS.md`+`.agent/runs/` pattern. |
| **Codex customization layer cake** (OpenAI devs) | AGENTS.md = "small" persistent rules. Skills = reusable workflows. MCP = external tools. Subagents = delegation. Sazón already has skills (`saskia-rms-*`). The pattern is correct. |
| **OpenAI cookbook ExecPlan pattern** | Optional `PLANS.md` + `GOALS.md` + `PROMPTS.md` + `harness/build/<phase>.md` + `harness/context/<phase>.md`. Sazón has `.hermes/plans/` which is structurally similar but doesn't enforce the phase+context split. |
| **5-line "checklist for a good AGENTS.md"** (Fabler Labs) | (1) Commands (2) Layout (3) Conventions (4) Do-not (5) Verify. |

## The two key empirical truths to apply to Sazón

1. **Augment: 100-150 line sweet spot. Gains reverse past 300 lines.** Sazón is at 395. **Even after the Tier 2 additions, we should target ≤300 lines.**
2. **ETH Zurich: auto-generated `/init` files reduce task success by 3%.** Implication: don't "improve" the file by adding AI-suggested content. The current content is operator-curated; preserve the operator's voice.

## What "the right AGENTS.md for Sazón" actually looks like (concrete Tier 2 rewrite plan)

Target: **≤300 lines, lead with commands, 3 community-priority sections added, narrative trimmed, no AI-suggested bloat.**

### Order of sections (matches the 5-line checklist pattern)

```
1. What this is (1-2 sentences, Sazón, Paraguay bakery RMS, single-client)     [2 lines]
2. Build & test commands (canonical incantations)                              [12 lines]
3. Project layout (1 line per major dir)                                       [8 lines]
4. Boundaries — Always / Ask first / Never (summary, with cross-refs)           [10 lines]
5. Hard rules (37 numbered, kept as-is, organized by category)                 [180 lines]
   - Money math (6) [unchanged]
   - Data integrity (5) [+1 sentence: "costing.py shim is permanent"]
   - Migrations (8) [+1 sentence: "no `-X ours` on app/rms/"]
   - Time zones (2) [unchanged]
   - UI (4) [unchanged]
   - Security (5) [+1 sentence: "pre-commit hook covers Supabase passwords"]
   - Deployment (4) [unchanged]
   - Process (3) [unchanged]
6. Anti-rules (20, kept as-is)                                                 [60 lines]
7. Locked hotfixes (5, kept as-is)                                             [20 lines]
8. Before opening a PR (Definition of Done checklist)                          [12 lines]
9. Cross-references (to skills, docs, worktree policy)                          [8 lines]
                                                                Target: ~312 lines
```

**Why this order**: the first 4 sections (~32 lines) give a new agent everything it needs to *orient* in 30 seconds. The 5th and 6th sections are the *load-bearing content* — the 37 hard rules + 20 anti-rules are the highest-value part of the file and should not be trimmed. Section 8 is the *self-verification* step. Section 9 is the *escape hatch* to deeper docs.

### Trims (move to skills or CONTRIBUTING.md, not deleted)

- "Build brief" (~30 lines) → `CONTRIBUTING.md` or a new `docs/operations/2026-10-12-engagement-model.md`. The narrative about "Iván" and "Kiki" doesn't change agent behavior.
- "How to work a session" (~15 lines) → already in the `saskia-rms-development` skill. Remove from AGENTS.md.
- "Personas (who is who)" (~10 lines) → `CONTRIBUTING.md` or a session-start skill.

### New sections to add (with rough line counts)

**Build & test commands (12 lines, near the top):**
```bash
# Install:                uv sync
# Test (single file):      uv run pytest -q tests/test_X.py
# Test (full, parallel):   uv run pytest -q -n 4
# Lint:                    ruff check .
# Format:                  ruff format .
# Migration:               sazon migrate           # or: sazon migrate --dry-run
# Rollback:                sazon rollback --to N
# CHANGELOG (auto):        never edit directly — see Rule 35
# Pre-commit setup:        uv run pre-commit install
# Smoke (live):            make serve
```

**Project layout (8 lines):**
```
- `app/rms/`   — models, business logic, helpers (see `app/rms/AGENTS.md`)
- `app/routers/` — FastAPI route handlers
- `app/templates/` — Jinja2 templates (Spanish voseo copy)
- `tests/`     — pytest; conftest.py fixtures
- `scripts/`   — one-shot ops scripts
- `app/rms/migrations/` — schema migrations (forward-only, never edit shipped)
- `.hermes/`   — agent-orient files (plans, archives, sibling notes)
- `docs/`      — operations runbooks + design docs
```

**Boundaries summary at the top (10 lines):**
```
Always:
- Run `uv run pytest` and `ruff check .` before opening a PR
- Update `app/CHANGELOG.md` for any change in `app/`, `scripts/`, `tests/`, `.github/`
- Reference a SASKIA-NNN ticket in every PR

Ask first:
- New dependencies (Rule 26)
- DB schema changes (Rules 12-19)
- Changes to auth, security, scope, or sharing
- Anything that touches Saskia's data or workflow

Never:
- `git push origin main` directly (Rule 36)
- Edit a shipped migration (Rule 14)
- Commit credentials, .env, or real customer data
- Bypass the pre-commit `check-no-secrets` hook
- `-X ours` / `-X theirs` merges on `app/rms/` (new Rule 38)
```

**Before opening a PR (12 lines, near the bottom):**
```
- [ ] `uv run pytest -q` passes (or the failing test is in the PR and marked xfail)
- [ ] `ruff check .` clean
- [ ] `ruff format --check .` clean
- [ ] `app/CHANGELOG.md` updated
- [ ] PR title references SASKIA-NNN
- [ ] New behavior has a regression test
- [ ] No secrets, .env, or real customer data in the diff
- [ ] Pre-commit hooks pass (`uv run pre-commit run --all-files`)
- [ ] If migration added: pre-migration backup test runs (Rule 17)
- [ ] If schema touched: `sazon migrate --dry-run` succeeds
```

**CLAUDE.md cross-tool import (1 line, new file):**
```bash
# On Windows the import text is the only reliable form:
# CLAUDE.md contents: "@AGENTS.md"
# On Linux/macOS a symlink works: `ln -s AGENTS.md CLAUDE.md`
```

**Cross-reference to `app/rms/AGENTS.md` (1 line):**
```
For rules specific to `app/rms/` (modeling, business logic, helpers), see `app/rms/AGENTS.md`.
```

### Stale-fact fixes (already in audit, list here for completeness)

- Schema 117 → 119
- 251 files → 291
- 45 tables → 64 (in app/rms/db.py; cross-check this)
- "apply_sale in `app/rms/costing.py`" → "apply_sale in `app/rms/sales/lifecycle.py` (the costing.py shim re-exports it)"
- "35% coverage gate" → "40% coverage gate"
- Rule 21 numbering gap → renumber or note it (one is implicit in time-zones)

### What this Tier 2 PR is and is not

**It IS:**
- A docs-only PR (no code changes, no test changes, no migration)
- A single-commit change to AGENTS.md + 1 new file (CLAUDE.md, 1 line)
- The 6 stale-fact fixes from the audit + 5 session-grounded rules from Addendum 1
- The community-pattern deltas (commands, layout, boundaries, do-not, PR checklist, CLAUDE.md import)
- ~30 lines trimmed (narrative moved to skills/CONTRIBUTING.md)
- ~30 lines added (new community-priority sections)
- Net: -5 to +10 lines, but density goes up significantly

**It is NOT:**
- A Tier 3 (code) PR
- A Tier 4 (AGENTS.md split into 4 files) — deferred
- An "AI-improved" rewrite — operator's voice preserved
- A rewrite of the 37 hard rules or 20 anti-rules — those are load-bearing and time-tested
- An addition of frontmatter — community says optional, Sazón's choice (no frontmatter) is correct
- A rename of the file
- A change to the migration directory or any code

### Estimated effort to ship

- 30 min: read this research doc + the audit, confirm Tier 2 scope
- 60 min: edit AGENTS.md in one worktree, add CLAUDE.md
- 15 min: open the PR with the body pre-drafted below
- 0 min: tests (no code changes)
- 0 min: review (it's a 30-line diff in one file + 1 new file)

**PR body (draft, ready to paste into `gh pr create --body-file`):**
```markdown
# docs(AGENTS): community-pattern deltas + stale-fact refresh

## What
Refreshes `AGENTS.md` based on a 13-source community research review and a
session-grounded audit of 6 prior Sazón sessions.

## Why
Current `AGENTS.md` is 395 lines, at the empirical upper bound (Augment: gains
reverse past 300 lines; ETH Zurich: `/init`-generated files reduce task
success by 3%). This PR trims narrative bloat, adds the 3 community-priority
sections that were missing (commands, layout, boundaries summary), and
incorporates 5 rules that prior sessions established as load-bearing.

## Changes
- Adds `Build & test commands` block at the top
- Adds `Project layout` 1-liner per major dir
- Adds `Boundaries` summary (Always / Ask first / Never) at the top
- Adds `Before opening a PR` checklist
- Adds `CLAUDE.md` (1 line: `@AGENTS.md`) for cross-tool compatibility
- Adds 1-line cross-ref to `app/rms/AGENTS.md` (fixes the orphan)
- Trims "Build brief" + "Personas" + "How to work a session" (moves to
  `CONTRIBUTING.md` or skills)
- Fixes 6 stale facts (schema 117→119, files 251→291, tables 45→64,
  apply_sale path, coverage gate 35%→40%, rule-21 numbering)
- Adds 1 sentence to Rule 8 (shim policy clarification)
- Adds Rule 38 (no `-X ours` on `app/rms/`)
- Adds anti-rule 21 (no prod DB in fixtures) with CI hook note
- Expands Rule 27 (pre-commit hook covers Supabase passwords)

## Risk
None. Docs-only. No code, no tests, no migration, no behavior change.

## Verification
- `wc -l AGENTS.md` — should be ≤ 320 (was 395)
- Read-through: confirm 37 hard rules + 20 anti-rules still intact
- Confirm no broken cross-refs in the `Cross-references` section
- Confirm `CLAUDE.md` contains exactly `@AGENTS.md`

## Refs
- `.hermes/plans/2026-10-12-agents-md-deep-analysis.md` (the audit)
- `.hermes/2026-10-12-agents-md-community-research.md` (the research)
- Sources: see community research doc
```

---

**End of community research + rewrite plan. AGENTS.md is unchanged. No commits, no PRs, no code edits. Ready for the next clean operator message to ship the Tier 2 PR.**
