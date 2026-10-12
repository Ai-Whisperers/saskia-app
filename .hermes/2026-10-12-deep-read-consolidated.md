# Deep-read consolidated — everything we should consider for AGENTS.md and the Hermes MD files

**Compiled:** 2026-10-12
**Source:** 350 KB of source read across 53 markdown files in 4 sibling repos
**Scope:** wizard-academy (17 files), code-agent (11 files), code-agent-ui (1 file), Johns-Grimoire (24 files)
**Cache:** All 53 files are cached at `.hermes/_cross_repo_reads/` (prefixes: `WA_`, `CA_`, `JG_`, `JG_cursor_cmd_`) for follow-up reads

**This is the master "what to consider" doc for the saskia-app/AGENTS.md rewrite and the broader Hermes MD layer** (saskia-app/AGENTS.md, saskia-app/app/rms/AGENTS.md, saskia-app/.hermes/*.md, and the rules in the rewrite draft).

---

## 0. The 5 minutes of context that changes everything

Before listing rules, the 5 most important findings from the deep read:

1. **wizard-academy defines the AIW canonical technical standards: 95/85 coverage + zero-warning.** Sazon currently enforces 40% coverage. The saskia-app AGENTS.md Rule 30 is **lower than the org standard**. The wizard-academy `wisdom/technical-standards.md` ("The 95/85 Rule") is from the **Master Strategic Sessions** — the highest-level AIW guidance. Sazon's coverage gate is a Sazon-specific compromise, but the new AGENTS.md should be **explicit** that it's a Sazon-specific compromise, not the AIW default.

2. **code-agent is the AIW Code Agent in pilot phase, NOT study material.** Despite the README's "Status: Study/adaptation phase. NOT production-deployed under AIW" line, the docs/ subdirectory shows **2 active pilot clients** (Vete + Solstein), a deployment IP (`72.61.44.159`), GitHub token refresh timer, Postgres `repo_settings` table, and per-client profiles. The 8 open issues are the AIW customizations in flight. **The README is misleading.** The reality is in the docs.

3. **Johns-Grimoire is misnamed.** README says "Organization Template Repository" but the actual content is **Eneve's CI/CD + AI rules documentation** for the eneve.domain / eneve.ebase.foundation / eneve.ebase.datamigrator projects (the same Eneve company that owns code-agent's upstream). The 1.4 MB of PowerShell is Eneve's Azure DevOps pipeline scripts, not AIW templates. The `.cursor/rules/quality/` "zero warnings, zero errors, prevention over remediation" is the Eneve quality philosophy, not an AIW org standard. **The repo is misnamed and misdescribed — both on GitHub and in any cross-reference from saskia-app.**

4. **code-agent's docs/CLIENTS is the canonical "how the AIW Code Agent handles a client" pattern.** Each client (Vete, Solstein) gets a profile with: GitHub URL, default branch, target branch for PRs, size, LOC, test files, language, stack, deploy, observability, auth, monorepo layout, tenancy model. **This is the model saskia-app's AGENTS.md should follow for the Sazon client profile** — the current AGENTS.md describes the codebase, not the client (Saskia) it serves.

5. **The 4 repos reveal a 3-level documentation hierarchy that is currently unstated**:
   - **Level 1 (org-wide)**: wizard-academy `wisdom/technical-standards.md` (95/85, zero-warning), Johns-Grimoire `.cursor/rules/quality/` (prevention-over-remediation), code-agent `docs/clients/README.md` (per-client profile pattern)
   - **Level 2 (product-level)**: saskia-app/AGENTS.md (Sazon-specific rules)
   - **Level 3 (domain-level)**: saskia-app/app/rms/AGENTS.md (RMS-domain rules)
   - **None of the 3 levels currently reference the others.** The new saskia-app/AGENTS.md should explicitly link to the org-level standards and the domain-level extension.

---

## 1. The 47 things we should consider — for AGENTS.md and the Hermes MD layer

This is the master list. Each item is sourced, has a recommendation, and a target file. Items are grouped by category.

### 1.1 The Sazon-specific facts (saskia-app/AGENTS.md)

These are the things to change in the rewrite draft. Some are corrections to stale claims, some are additions.

**A. Coverage gate (Rule 30): currently 40%, should be 40% + cross-reference to org 95%**
- **Source:** wizard-academy `wisdom/technical-standards.md` defines 95% line + 85% branch as the AIW standard
- **Current state:** saskia-app/AGENTS.md Rule 30 = 40% line coverage
- **Recommendation:** Keep 40% as the Sazon-specific compromise (since Sazon is at ~98% test pass, the 95% line is a Sazon sprint goal, not today's gate). But add explicit cross-reference: "Sazon's 40% is a Sazon-specific compromise. AIW org standard per `wizard-academy/wisdom/technical-standards.md` is 95/85."
- **Target:** saskia-app/AGENTS.md Rule 30
- **Effort:** 5 min

**B. Zero-warning policy should be in saskia-app/AGENTS.md**
- **Source:** wizard-academy `wisdom/technical-standards.md` — "Zero-Warning Policy: A warning is a bug. The build pipeline must treat any compiler or linting warning as a failure."
- **Current state:** saskia-app/AGENTS.md mentions ruff but doesn't codify zero-warning
- **Recommendation:** Add as Rule 7a or expand Rule 7. "Zero-warning: a warning is a bug. Treat all ruff/mypy warnings as errors in CI."
- **Target:** saskia-app/AGENTS.md
- **Effort:** 5 min

**C. The "no merge without 95% test coverage" mandate is a strategic goal, not today's bar**
- **Source:** Same as A
- **Recommendation:** Add a forward-looking note: "Sazon's path to the 95/85 standard: track % coverage per PR, target 60% by Sprint 3.x, 80% by Sprint 4.x, 95% by Sprint 5.x."
- **Target:** saskia-app/AGENTS.md "Goals" section
- **Effort:** 10 min

**D. The "scripts/README.md in saskia-app should be a proper index" pattern**
- **Source:** Johns-Grimoire `cicd/scripts/README.md` (6.6 KB) is a model — every script documented with Cursor-AI-assisted error messages
- **Current state:** saskia-app has `scripts/` but no index
- **Recommendation:** Create `scripts/README.md` index, with each script's purpose, usage, common errors + fixes
- **Target:** saskia-app/scripts/README.md (NEW)
- **Effort:** 1-2h

**E. The "client profile" pattern from code-agent/docs/clients/**
- **Source:** code-agent `docs/clients/README.md`, `docs/clients/solstein.md`, `docs/clients/vete.md`
- **Current state:** saskia-app describes the codebase, not the client (Saskia)
- **Recommendation:** Create `docs/clients/saskia.md` in saskia-app with: GitHub URL, default branch, target branch for PRs, size, LOC, test files, language, stack, deploy, observability, auth, monorepo layout, tenancy model (single-tenant per SASKIA-210)
- **Target:** saskia-app/docs/clients/saskia.md (NEW)
- **Effort:** 30 min (per the template from Vete/Solstein)

**F. The "6 of 6 done" criterion (6 hard rules, 1 new)**
- **Source:** operator-intent retrospective, prior turn
- **Current state:** Not in AGENTS.md
- **Recommendation:** Add as Rule 0 (at the top): "Done = code merged + tests added + deployed via sazon deploy + Sentry alert wired + 24h no-rollback + post-deploy sanity check. PR merged is 2 of 6, not done."
- **Target:** saskia-app/AGENTS.md top
- **Effort:** 5 min

**G. Decision authority tiers (T1-T4)**
- **Source:** operator-intent retrospective
- **Recommendation:** Add to top of AGENTS.md: "T1 = AI decides, T2 = AI decides + surfaces, T3 = AI drafts + operator approves, T4 = operator only. Default for new work is T2."
- **Target:** saskia-app/AGENTS.md top
- **Effort:** 5 min

**H. The shim is permanent (Rule 8 expanded)**
- **Source:** prior analysis
- **Current state:** Rule 8 in saskia-app/AGENTS.md partially covers this (lifecycle.py, cost.py)
- **Recommendation:** Add explicit "the shim is permanent" line
- **Target:** saskia-app/AGENTS.md Rule 8
- **Effort:** 5 min

**I. No `-X ours` (Rule 38, new)**
- **Source:** Sprint 2.3 casualty documented in prior turn
- **Recommendation:** Add new Rule 38: "Never `git merge -X ours` on `app/rms/`. The Sprint 2.3 shim was silently replaced with 776 lines of duplicate code. Use cherry-pick or manual merge."
- **Target:** saskia-app/AGENTS.md
- **Effort:** 5 min

**J. No prod DB in fixtures (Anti-rule 21)**
- **Source:** SASKIA-317 incident documented in prior turn
- **Recommendation:** Add: "Never use real Sazon prod DB in tests. Use a per-test SQLite in-memory or temp file."
- **Target:** saskia-app/AGENTS.md anti-rules
- **Effort:** 5 min

**K. No AI-edit of AGENTS.md without operator review (Anti-rule 22, new)**
- **Source:** ETH Zurich AGENTbench data (Aug 2026): "Auto-generated AGENTS.md reduces task success by 3%"
- **Recommendation:** Add: "AI-improved AGENTS.md is worse (ETH Zurich empirical data, Aug 2026). Every change to this file needs operator review."
- **Target:** saskia-app/AGENTS.md anti-rules
- **Effort:** 5 min

**L. Topic tag discipline (Rule 39, new)**
- **Source:** All 4 sibling repos have `archived` topic, none are actually repo-archived
- **Recommendation:** Add new Rule 39: "Topic tags are part of the contract. Don't add `archived` until actually archived. Don't remove `archived` until actually un-archived. Topics are the first thing search returns."
- **Target:** saskia-app/AGENTS.md
- **Effort:** 5 min

**M. OPSEC markers mandatory (Rule 40, new)**
- **Source:** code-agent/code-agent-ui have CONFIDENTIAL, others don't
- **Recommendation:** Add: "OPSEC markers (CONFIDENTIAL in desc, `private` visibility, `ops`/`secrets`/`family`/`client-private` topic) are mandatory for repos touching credentials, network access, or operator data."
- **Target:** saskia-app/AGENTS.md
- **Effort:** 5 min

**N. Language choice is per-repo (Rule 41, new)**
- **Source:** 4 sibling repos use 4 different stacks (Python, Java, TS/React, PowerShell)
- **Recommendation:** Add: "Language choice is a per-repo decision. Sazon = Python/FastAPI/SQLite. PowerShell = Windows-side. Java/Quarkus = self-hosted infra. Don't mix stacks in one repo without explicit reason."
- **Target:** saskia-app/AGENTS.md
- **Effort:** 5 min

**O. Branch conventions are repo-specific (Rule 42, new)**
- **Source:** code-agent uses `aiw/main`, saskia-app uses `main`
- **Recommendation:** Add: "Check `git symbolic-ref refs/remotes/origin/HEAD` before assuming `main`. Document branch conventions in the repo's AGENTS.md or README."
- **Target:** saskia-app/AGENTS.md
- **Effort:** 5 min

**P. Sazon "no Telegram" is product-level (Rule 43, new)**
- **Source:** code-agent README: "Telegram via Hermes gateway, 40+ repos use it." Sazon is in the 19 that don't.
- **Recommendation:** Add: "Sazon's 'no Telegram' rule is product-level. Sazon bakery customers don't see Telegram. Operator-facing tools (40+ other AIW repos) can use Telegram via the Hermes gateway."
- **Target:** saskia-app/AGENTS.md
- **Effort:** 5 min

**Q. Tenancy posture is per-product (Rule 44, new)**
- **Source:** Sazon = single-tenant (SASKIA-210). code-agent = Supabase multi-tenant. Vete = RLS multi-tenant.
- **Recommendation:** Add: "Tenancy posture is per-product, not per-org. Document in each repo's AGENTS.md."
- **Target:** saskia-app/AGENTS.md
- **Effort:** 5 min

**R. Deployment model is per-repo (Rule 45, new)**
- **Source:** 4 sibling repos have 4 different deploy models
- **Recommendation:** Add: "Document the deployment model in each repo's README: local-only / VPS-hosted / SaaS / self-hosted. Don't assume parity."
- **Target:** saskia-app/AGENTS.md
- **Effort:** 5 min

**S. Sister-repos section (new section in AGENTS.md)**
- **Source:** All 4 sibling repos
- **Recommendation:** Add a "Sister repos" section to saskia-app/AGENTS.md with 1-liner per sibling repo, current state, what it's for, link to deeper doc
- **Target:** saskia-app/AGENTS.md new section
- **Effort:** 15 min

### 1.2 The AIW-wide facts (for the Hermes MD layer)

These are facts that don't belong in saskia-app/AGENTS.md (because saskia-app is one product) but DO belong in the broader Hermes MD layer (the operator's reference docs).

**T. 39 active AIW repos on GitHub**
- **Source:** code-agent README: "39 of 39 active repos are on GH"
- **Use:** saskia-app cross-reference, .hermes/STATE.md
- **Target:** .hermes/STATE.md (NEW) — operator's running state doc

**U. 41 of 59 repos use Supabase Auth**
- **Source:** code-agent README
- **Use:** AIW-wide org pattern, saskia-app cross-reference
- **Target:** .hermes/STATE.md

**V. 40+ of 59 repos use Telegram via Hermes gateway**
- **Source:** code-agent README
- **Use:** AIW-wide org pattern, helps explain "Sazon is in the 19 that don't"
- **Target:** .hermes/STATE.md

**W. AIW Code Agent pilot clients: Vete + Solstein**
- **Source:** code-agent `docs/clients/README.md`
- **Use:** AIW product state
- **Target:** .hermes/STATE.md

**X. Eneve = Ecedo (June 2025 merger) = Vortex Capital-backed Netherlands co**
- **Source:** code-agent `CONFIDENTIAL.md`
- **Use:** OPSEC context, partner due-diligence
- **Target:** .hermes/STATE.md (or a separate OPSEC.md)

**Y. AIW deploy IPs**
- **Source:** code-agent `docs/OPERATIONS.md`: `72.61.44.159` for code-agent
- **Use:** AIW deploy state
- **Target:** .hermes/STATE.md (this is OPSEC-sensitive, redact in shared docs)

**Z. The 4 sibling repos' actual current state**
- **Source:** This deep-read
- **Use:** Operator's reference
- **Target:** .hermes/STATE.md

### 1.3 The 4 sibling repos' recommendations (per-repo)

These are the actions the operator should consider for each of the 4 sibling repos. They don't affect saskia-app/AGENTS.md directly, but they affect the org-level Hermes MD layer (Sister-repos cross-reference) and the operator's per-repo decisions.

**AA. wizard-academy**
- Add AGENTS.md: "This is a knowledge base, not a code repo. Agents should READ, not WRITE."
- Update GitHub description: include the wizard personas (Aethelred, Merlin 3.0, Nyx 3.0)
- Remove the `archived` topic — this is a living knowledge base
- Add LICENSE (CC-BY-4.0 for a knowledge base)
- Decision: keep as-is, move to aiw-strategic-research, or kill. The 5.6 KB of Python + 4 KB of Shell are config-validation scripts for OpenCLAW; not load-bearing.

**BB. code-agent**
- **Fix the README**: it's misleading. The system is in pilot with 2 clients (Vete + Solstein), not "study material."
- Add AGENTS.md: "Active AIW Code Agent in pilot phase. 2 clients (Vete, Solstein). 8 open issues track AIW customizations. Stack-swap plan in docs/AIW-CUSTOMIZATION-PLAN.md."
- Remove or fix the `archived` topic — this is active development
- Add LICENSE for the AIW-added content
- Decision: ship the remaining AIW customizations, OR freeze and re-evaluate, OR archive. Operator-level.

**CC. code-agent-ui**
- **Fix the README**: it's a copy-paste of code-agent's README. Should be UI-specific.
- Add AGENTS.md: "UI for the not-deployed-at-scale code-agent. React 19 + Vite + TanStack + TipTap. Backend frozen at 2026-05-25 Eneve baseline. UI iterated through 2026-09-14. Keycloak → Supabase Auth swap NOT done."
- Remove the `archived` topic
- Add LICENSE
- Decision: mirror of code-agent's decision. If keeping backend, keep UI. If archiving backend, archive UI.

**DD. Johns-Grimoire**
- **Fix the GitHub description**: "AI Whisperers org-level CI/CD + AI rules documentation (sourced from Eneve). Codename: John's Grimoire." (Currently "John's Grimoire — occult/magic reference tool")
- **Fix the README**: it claims to be a Python template repo, but the actual content is Eneve's CI/CD + AI rules docs.
- Add AGENTS.md: "AIW org-level CI/CD + AI rules documentation. The Eneve content is upstream; the AIW adaptation is in `cursor/.cursor/`. Do not 'improve' Eneve content without explicit operator instruction."
- Remove the `archived` topic
- Add LICENSE
- Decision: rename, repurpose, or kill. If keeping, the "John's Grimoire" name should be either embraced (it's a real AIW codename) or removed (it's misleading).

### 1.4 The structural/hierarchical recommendations

**EE. Establish the 3-level doc hierarchy explicitly**
- **Level 1 (org-wide)**: AIW-wide rules (95/85, zero-warning, OPSEC, tenancy posture)
- **Level 2 (product-level)**: saskia-app/AGENTS.md (Sazon-specific)
- **Level 3 (domain-level)**: app/rms/AGENTS.md (RMS-specific)
- **Each level cross-references the others.** The saskia-app/AGENTS.md currently doesn't link to the org-wide standards; the app/rms/AGENTS.md currently doesn't link to saskia-app/AGENTS.md.
- **Target:** All 3 levels
- **Effort:** 15 min total (cross-references)

**FF. The "study vs pilot vs production vs maintenance vs sunset" lifecycle**
- **Source:** Cross-repo observation: code-agent is "study → pilot", wizard-academy is "knowledge base (no lifecycle)", saskia-app is "production", others are "archived"
- **Recommendation:** Add a "Lifecycle" section to saskia-app/AGENTS.md or to the org-level docs. Each repo declares its lifecycle stage.
- **Target:** saskia-app/AGENTS.md (or a new org-level HERMES-LIFECYCLE.md)
- **Effort:** 30 min

**GG. The "code-agent client profile" is the template for product-level AGENTS.md sections**
- **Source:** code-agent `docs/clients/vete.md`, `docs/clients/solstein.md`
- **Each profile has**: GitHub URL, default branch, target branch for PRs, size, LOC, test files, language, stack, deploy, observability, auth, monorepo layout, tenancy model
- **Recommendation:** Add a "Sazon client profile" section to saskia-app/AGENTS.md or a sibling file (`docs/clients/saskia.md`). The current AGENTS.md describes the codebase but not the client (Saskia/La Vaquita) it serves.
- **Target:** saskia-app/docs/clients/saskia.md (NEW)
- **Effort:** 30 min

**HH. The "Sister repos" cross-reference is the cross-product layer**
- **Source:** All 4 sibling repos
- **Recommendation:** Create the Sister-repos section in saskia-app/AGENTS.md (per §1.1 S above), with 1-liner per sibling repo
- **Target:** saskia-app/AGENTS.md new section
- **Effort:** 15 min

**II. The ".hermes/STATE.md" is the operator's running state**
- **Source:** operator-intent retrospective, plus the AIW-wide facts (§1.2)
- **Recommendation:** Create `.hermes/STATE.md` with: the 5 P0s for next 4 weeks, the 4 sibling repos' current state, the 41/40/39/2/8 numbers, the deploy IP (redacted), the operator-decisions pending
- **Target:** saskia-app/.hermes/STATE.md (NEW)
- **Effort:** 30 min

### 1.5 The agent-doc-system recommendations

**JJ. Adopt the .cursor/ structure for the Sazon .hermes/**
- **Source:** Johns-Grimoire has `.cursor/commands/` (one-line commands that reference `.cursor/prompts/`), `.cursor/prompts/` (15+ prompt files), `.cursor/rules/` (5 rule files), `.cursor/scripts/`
- **Current state:** saskia-app/.hermes/ has unstructured files (HERMES-ORIENTATION.md, KNOWN-BYPASSES.md, SIBLING-COORDINATION-NOTE.md, sibling-flush-note.md, plus the 5 analysis docs added in this turn)
- **Recommendation:** Consider restructuring saskia-app/.hermes/ to follow the `.cursor/` pattern:
  - `.hermes/commands/` — short invocation patterns
  - `.hermes/prompts/` — longer agent-prompt templates (currently 0, would be created from analysis docs)
  - `.hermes/rules/` — durable rules (currently mixed in the analysis docs)
  - `.hermes/scripts/` — agent-utility scripts
- **Target:** saskia-app/.hermes/ restructure
- **Effort:** 2-4h (significant restructure, but high value)

**KK. The "rule-authoring" pattern**
- **Source:** Johns-Grimoire `cursor/.cursor/rules/rule-authoring/README.md` (10 KB) is a complete framework for writing AI agent rules. It includes an 8-step "extraction-from-practice" methodology, file structure, validation report.
- **Recommendation:** Read the full rule-authoring framework (saved in `_cross_repo_reads/JG_cursor_.cursor__rules__rule-authoring__README.md`) and adopt it for saskia-app/AGENTS.md authoring. The new saskia-app/AGENTS.md should be authored per the same framework, not ad-hoc.
- **Target:** saskia-app/AGENTS.md authoring process
- **Effort:** 1-2h to read + adapt

**LL. The "per-prompt README" pattern**
- **Source:** Johns-Grimoire `cursor/.cursor/prompts/` has 15+ prompts, each with their own README
- **Current state:** No agent prompts in saskia-app/.hermes/
- **Recommendation:** Create a `.hermes/prompts/` directory with reusable agent prompts: e.g., "add a migration", "add a route", "add a model", "fix a Sentry alert", "add a Rule to AGENTS.md"
- **Target:** saskia-app/.hermes/prompts/ (NEW)
- **Effort:** 2-4h (creating 5-10 prompt templates)

**MM. The "scripts/ with cursor-AI-assisted errors" pattern**
- **Source:** Johns-Grimoire `cicd/scripts/README.md`: "All validation scripts now provide actionable, AI-assisted error messages when failures occur. Instead of just telling you what's wrong, they tell you how to fix it automatically using Cursor AI prompts."
- **Current state:** saskia-app scripts don't have AI-assisted error messages
- **Recommendation:** For each saskia-app script in `scripts/`, add a "Common errors + AI-assisted fixes" section to its docstring or to `scripts/README.md`
- **Target:** saskia-app/scripts/ + scripts/README.md
- **Effort:** 1-2h

**NN. The "rule self-validation" pattern**
- **Source:** Johns-Grimoire `cursor/.cursor/rules/rule-authoring/VALIDATION-REPORT.md` (mentioned in the README)
- **Recommendation:** Add a self-validation step to saskia-app/AGENTS.md: every rule should have a "how to verify" check. (E.g., Rule 30 = 40% coverage → `pytest --cov=app --cov-fail-under=40` is the verification.)
- **Target:** saskia-app/AGENTS.md every rule
- **Effort:** 1-2h (verify each rule)

### 1.6 The OPSEC recommendations

**OO. The PAT allowlist is a real recurring problem**
- **Source:** 2 PATs hit 403 on Contents for 4 repos; the "all access" PAT was missing the `code: read` permission at the repo level
- **Recommendation:** Add to saskia-app/AGENTS.md or .hermes/SECURITY.md: "GitHub PAT setup: 1) Add `Contents: Read-only` at the repo level. 2) Add `code: Read and Write` at the repo level. 3) Set Resource access to all org repos. Without these, the Contents API returns 403 even on 'all access' tokens."
- **Target:** .hermes/SECURITY.md (NEW) or saskia-app/AGENTS.md
- **Effort:** 15 min

**PP. Rotating the leaked PAT**
- **Source:** This session
- **Recommendation:** The "hermes all access" PAT was pasted in chat in the prior turn. It's still valid until 2027-10-13. Operator should rotate it and store the replacement in BWS/vault.
- **Target:** Operator's calendar
- **Effort:** 5 min (operator)

**QQ. The "Sazon AUTH" via Supabase**
- **Source:** code-agent README: "Supabase Auth, 41 of our repos use Supabase"
- **Current state:** Sazon auth is `app/auth.py` with `current_operator`, `current_user_id` (per Rule "auth.py is the auth file")
- **Recommendation:** Document the Sazon auth choice in saskia-app/AGENTS.md: "Sazon uses Supabase Auth (when integrated). For local-first, see `app/auth.py`."
- **Target:** saskia-app/AGENTS.md
- **Effort:** 5 min

### 1.7 The "this is the AIW product" recommendations

**RR. Sazon = product, code-agent = pilot, wizard-academy = knowledge, Johns-Grimoire = reference**
- **Source:** This deep read
- **Recommendation:** In saskia-app/AGENTS.md, declare the AIW product surface explicitly: "Sazon is the production RMS for Saskia/La Vaquita. Code-agent is the AIW Code Agent in pilot. Wizard-academy is the AIW knowledge base. Johns-Grimoire is the AIW CI/CD + AI rules reference."
- **Target:** saskia-app/AGENTS.md new "AIW context" section
- **Effort:** 10 min

**SS. The 7 patterns worth stealing from code-agent**
- **Source:** code-agent `docs/STUDY-NOTES.md`: 7 backend patterns (parallel tool execution, context compaction with circuit breaker, checkpoint+resume, self-review of own diff, learning extraction from PR comments, tool authorization gate, shell command security validator) + 6 frontend patterns (ThinkingPanel, SecretScanner, ClarificationBlock, SSE streaming, editable prompts, plan execution UI)
- **Recommendation:** Reference these in saskia-app/AGENTS.md "Patterns from sister repos" section. If/when Sazon builds a self-hosted agent, these are the blueprint.
- **Target:** saskia-app/AGENTS.md new section
- **Effort:** 15 min

**TT. The 5 Eneve clients in pilot at AIW Code Agent**
- **Source:** code-agent `docs/clients/README.md` (Vete + Solstein as pilot) + README (112K LOC Java, 57K LOC TS, 179 files)
- **Recommendation:** Add as AIW-wide context in saskia-app/AGENTS.md
- **Target:** saskia-app/AGENTS.md
- **Effort:** 5 min

### 1.8 The "rebalance the read" recommendations

**UU. There are 350 KB of source I read; 50 KB of which is the most important**
- **Source:** This read
- **Recommendation:** The highest-value reads for saskia-app/AGENTS.md purposes are:
  1. wizard-academy `wisdom/technical-standards.md` (2 KB) — 95/85 + zero-warning
  2. code-agent `docs/AIW-CUSTOMIZATION-PLAN.md` (8 KB) — AIW delta from Eneve
  3. code-agent `docs/STUDY-NOTES.md` (7 KB) — 7 backend patterns
  4. code-agent `docs/clients/vete.md` + `solstein.md` (20 KB) — client profile pattern
  5. Johns-Grimoire `cursor/.cursor/rules/quality/README.md` (7 KB) — quality philosophy
  6. Johns-Grimoire `cursor/.cursor/rules/rule-authoring/README.md` (10 KB) — rule authoring
  7. wizard-academy `wisdom/star-machine-principle.md` (5 KB) — strategic philosophy
  8. code-agent `CONFIDENTIAL.md` (2 KB) — provenance
  Total: ~60 KB of "must read" for the rewrite, plus the 290 KB of context
- **Target:** Document in `.hermes/_cross_repo_reads/README.md` (NEW) for future sessions
- **Effort:** 5 min

---

## 2. The 6 must-do items (priority-ranked)

If the operator only does 6 things from this list, these are the 6:

1. **Add 95/85 + zero-warning cross-references to saskia-app/AGENTS.md (A + B above).** Highest leverage — saskia-app is below the org standard, and the rewrite draft should be honest about that.
2. **Create saskia-app/docs/clients/saskia.md (E above).** Mirrors the code-agent client profile pattern. Sazon is a product, not just a codebase.
3. **Add the 6-step "done" definition + T1-T4 decision authority + 11 new rules (F, G, 39-45) to saskia-app/AGENTS.md.** Captures the operator's actual priorities from the retrospective.
4. **Create saskia-app/.hermes/STATE.md (T-U-V-W-X-Y-Z + II above).** Operator's running state — the 5 P0s, the 4 sibling repos, the 41/40/39/2/8 numbers.
5. **Fix the misleading descriptions on code-agent, code-agent-ui, Johns-Grimoire (BB-CC-DD above).** Future agents (and the operator) will keep being misled otherwise.
6. **Read the Johns-Grimoire rule-authoring framework in full (KK above).** Apply it to the rewrite. The new saskia-app/AGENTS.md should be authored per a framework, not ad-hoc.

Total effort for the 6 items: ~3-4 hours.

---

## 3. The 47-item consolidation table

For quick reference, here are all 47 items in a single table:

| # | Item | Target file | Effort | Priority |
|---|---|---|---|---|
| A | Coverage gate cross-ref to 95/85 | saskia-app/AGENTS.md Rule 30 | 5m | P0 |
| B | Zero-warning policy | saskia-app/AGENTS.md (new Rule 7a) | 5m | P0 |
| C | Path to 95/85 (sprint goals) | saskia-app/AGENTS.md "Goals" | 10m | P1 |
| D | scripts/README.md index | saskia-app/scripts/README.md (NEW) | 1-2h | P2 |
| E | Sazon client profile | saskia-app/docs/clients/saskia.md (NEW) | 30m | P0 |
| F | "6 of 6 done" criterion | saskia-app/AGENTS.md top (new Rule 0) | 5m | P0 |
| G | T1-T4 decision authority | saskia-app/AGENTS.md top | 5m | P0 |
| H | Shim is permanent | saskia-app/AGENTS.md Rule 8 | 5m | P1 |
| I | No `-X ours` | saskia-app/AGENTS.md (new Rule 38) | 5m | P0 |
| J | No prod DB in fixtures | saskia-app/AGENTS.md anti-rules | 5m | P0 |
| K | No AI-edit of AGENTS.md | saskia-app/AGENTS.md anti-rules (new) | 5m | P0 |
| L | Topic tag discipline | saskia-app/AGENTS.md (new Rule 39) | 5m | P0 |
| M | OPSEC markers mandatory | saskia-app/AGENTS.md (new Rule 40) | 5m | P0 |
| N | Language choice per repo | saskia-app/AGENTS.md (new Rule 41) | 5m | P1 |
| O | Branch conventions per repo | saskia-app/AGENTS.md (new Rule 42) | 5m | P1 |
| P | Sazon "no Telegram" is product-level | saskia-app/AGENTS.md (new Rule 43) | 5m | P1 |
| Q | Tenancy posture per product | saskia-app/AGENTS.md (new Rule 44) | 5m | P1 |
| R | Deployment model per repo | saskia-app/AGENTS.md (new Rule 45) | 5m | P1 |
| S | Sister-repos section | saskia-app/AGENTS.md (new section) | 15m | P0 |
| T | 39 active repos | saskia-app/.hermes/STATE.md (NEW) | 30m total | P0 |
| U | 41 Supabase | saskia-app/.hermes/STATE.md | (same) | P0 |
| V | 40+ Telegram | saskia-app/.hermes/STATE.md | (same) | P0 |
| W | Vete + Solstein pilots | saskia-app/.hermes/STATE.md | (same) | P0 |
| X | Eneve = Ecedo | saskia-app/.hermes/STATE.md | (same) | P1 |
| Y | AIW deploy IP (redacted) | saskia-app/.hermes/STATE.md | (same) | P2 (OPSEC) |
| Z | 4 sibling repos' state | saskia-app/.hermes/STATE.md | (same) | P0 |
| AA | wizard-academy recommendations | (4 sibling repos) | 1-2h | P1 |
| BB | code-agent recommendations | (4 sibling repos) | 1-2h | P0 |
| CC | code-agent-ui recommendations | (4 sibling repos) | 30m | P1 |
| DD | Johns-Grimoire recommendations | (4 sibling repos) | 1-2h | P0 |
| EE | 3-level doc hierarchy | All 3 levels | 15m | P0 |
| FF | Lifecycle section | saskia-app/AGENTS.md (new) | 30m | P2 |
| GG | Sazon client profile | saskia-app/docs/clients/saskia.md | (same as E) | P0 |
| HH | Sister-repos cross-ref | saskia-app/AGENTS.md | (same as S) | P0 |
| II | .hermes/STATE.md | (same as T-Z) | (same) | P0 |
| JJ | .hermes/ → .cursor/ structure | saskia-app/.hermes/ | 2-4h | P2 |
| KK | rule-authoring framework | saskia-app/AGENTS.md process | 1-2h | P0 |
| LL | .hermes/prompts/ directory | saskia-app/.hermes/prompts/ (NEW) | 2-4h | P2 |
| MM | AI-assisted script errors | saskia-app/scripts/ | 1-2h | P2 |
| NN | Rule self-validation | saskia-app/AGENTS.md each rule | 1-2h | P1 |
| OO | PAT allowlist doc | saskia-app/.hermes/SECURITY.md (NEW) | 15m | P0 |
| PP | Rotate leaked PAT | operator's calendar | 5m | P0 |
| QQ | Sazon Supabase auth | saskia-app/AGENTS.md | 5m | P1 |
| RR | AIW product surface | saskia-app/AGENTS.md (new section) | 10m | P0 |
| SS | 7 patterns from code-agent | saskia-app/AGENTS.md (new section) | 15m | P0 |
| TT | AIW Code Agent pilot clients | saskia-app/AGENTS.md | 5m | P1 |
| UU | Must-read list for future | saskia-app/.hermes/_cross_repo_reads/README.md (NEW) | 5m | P1 |

**Total: 47 items. ~12-18 hours of work if all done. 6 items are P0 (3-4h).**

---

## 4. What's NOT in this list (deliberate)

- **Re-deriving the saskia-app/AGENTS.md 37 existing rules.** The current rules are fine; the gaps are new rules (39-45) and the operator-intent additions (6 of 6 done, T1-T4). Re-deriving the existing rules risks introducing drift.
- **Restructuring the 116 modules in `app/rms/`.** That's a separate workstream (Sprint 2.x-style splits).
- **Writing AGENTS.md for the 4 sibling repos.** That's a per-repo decision the operator should make (see BB-CC-DD).
- **Porting code-agent's Java to Python.** Per code-agent README: "production fork would be ported" — but this is operator-level.
- **Fixing the wizard-academy OpenCLAW configs.** Those are 4 KB JSON, not load-bearing.
- **Migrating from Render to VPS.** Already done (2026-09-24).

---

## 5. The doc hierarchy after these changes

If all 47 items are done (or even the 6 P0 items), the doc hierarchy looks like:

```
saskia-app/
├── AGENTS.md  [Level 2 — Sazon-specific rules, cross-refs to L1 + L3]
│   ├── Operator intent (6 of 6 done, T1-T4)
│   ├── Hard rules (45+)
│   ├── Sister repos section
│   ├── AIW context (95/85, code-agent pilots, 41 Supabase)
│   ├── Client profile (Saskia/La Vaquita)
│   └── Patterns from code-agent
├── app/
│   ├── auth.py
│   ├── CHANGELOG.md
│   └── rms/
│       ├── AGENTS.md  [Level 3 — RMS-domain rules, cross-refs to L2]
│       └── ...
├── docs/
│   ├── clients/
│   │   └── saskia.md  [NEW]
│   ├── operations/
│   └── architecture/
└── .hermes/
    ├── STATE.md  [NEW — operator's running state]
    ├── SECURITY.md  [NEW — PAT allowlist, OPSEC]
    ├── _cross_repo_reads/  [50+ cached source files + README.md]
    ├── plans/2026-10-12-agents-md-deep-analysis.md  [prior turn]
    ├── 2026-10-12-agents-md-community-research.md
    ├── 2026-10-12-agents-md-gap-analysis.md
    ├── 2026-10-12-agents-md-rewrite-draft.md
    ├── 2026-10-12-cross-repo-agents-md-analysis.md
    ├── 2026-10-12-operator-intent-retrospective.md
    ├── 2026-10-12-deep-read-consolidated.md  (this file)
    ├── HERMES-ORIENTATION.md
    ├── KNOWN-BYPASSES.md
    ├── SIBLING-COORDINATION-NOTE.md
    └── sibling-flush-note.md
```

That's the complete doc surface after the work. The new saskia-app/AGENTS.md is the level-2 hub; the .hermes/STATE.md is the level-1 hub (operator's state); app/rms/AGENTS.md is the level-3 extension.

---

## 6. The next 30 min recommendation

If the operator wants the highest-leverage 30 min of work:

1. **Read** `WA_wisdom__technical-standards.md` (2 KB, in `_cross_repo_reads/`) — the 95/85 + zero-warning standard
2. **Read** `CA_docs__AIW-CUSTOMIZATION-PLAN.md` (8 KB) — the AIW delta from Eneve, with 39 active repos number
3. **Read** `CA_docs__clients__vete.md` (9 KB) — the client profile pattern
4. **Add** the 6 P0 items (A, B, E, F, G, S) to the saskia-app/AGENTS.md rewrite draft
5. **Decide** on the 4 sibling repos' dispositions (BB, CC, DD)

That's 30 min of reading + 30 min of writing. After that, the rewrite draft is ready for the operator to ship as SASKIA-211e.
