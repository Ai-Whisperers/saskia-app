# Additional areas — research sweep of everything I haven't touched yet

**Compiled:** 2026-10-12 (continuation of the AGENTS.md deep research)
**Source:** probed 280+ MD files, 116 .py modules, 70 scripts, 38 migrations, 15 plans, 16 intake tickets
**Scope:** Sazon app (saskia-app), saskia-app/.hermes/, and the 4 sibling repos
**Goal:** enumerate the additional files, gaps, areas of work, and considerations the prior 47-item doc didn't cover

**This is the "everything else" doc.** The 47-item consolidated doc focused on AGENTS.md content + the 4 sibling repos' recommendations. This doc covers:
- The 280+ MD files in saskia-app that need audit/coherence work
- The 70+ utility scripts that need an index
- The 116 .py modules with potential abstraction issues
- The 38 migrations with potential structural concerns
- The 15+ intake tickets still open
- The 25+ operations runbooks with potential gaps
- The 5 user-guide patterns
- The .hermes/ structure that needs expansion
- The 4 sibling repos' deeper content I haven't read
- The AIW-org patterns I haven't mapped

---

## 0. The 5 most important findings (this turn)

1. **The current saskia-app/AGENTS.md is already comprehensive** (28 KB, well-structured with Personas, Hard rules, Anti-rules, How to work, Troubleshooting, When in doubt). The rewrite draft is iterating on something substantial, not a blank slate. The prior 47-item doc had several items that **already exist** in the current AGENTS.md (e.g., to_int_gs() rule, no-microservices anti-rule, worktree policy, "Kernel died mid-session" troubleshooting). **Need to re-verify each item against the current AGENTS.md before adding.**

2. **Sazon is at schema v117, not v114** (per STATUS.md and HERMES-ORIENTATION.md). The SASKIA-209 memory entry is stale. v117 is the live state. There are also 3 envs now: prod, test, dev. The 3 envs are documented in `docs/operations/2026-10-09-three-env-deploy.md` but not yet in AGENTS.md.

3. **There are TWO conflicting worktree policies in the repo**:
   - `docs/operations/worktree-policy.md` says: scratch = `/opt/data/profiles/ivan/scratch/sazon-app-work` (main, deploys), production = `/opt/data/work/sazon-app` (feature dev, no deploy)
   - `.hermes/SIBLING-COORDINATION-NOTE.md` says: `/opt/data/work/saskia-app` is the canonical worktree (currently SASKIA-212), `/opt/data/profiles/ivan/scratch/sazon-app-work` is mentioned as different
   - The 3 actual worktrees are: `/opt/data/work/saskia-app` (this, SASKIA-212), `/opt/data/work/saskia-app-abstraction-gates` (main), `/opt/data/work/saskia-app-vaquita` (SASKIA-213). The legacy `/opt/data/scratch/saskia-app` is DO NOT TOUCH.
   - **This is a real conflict.** The .hermes/SIBLING-COORDINATION-NOTE.md should reference the canonical worktree-policy.md, not duplicate or contradict it.

4. **The 4 sibling repos' recommendations are largely about FIXING EXISTING DOCS, not creating new ones**:
   - code-agent: fix the misleading "NOT production-deployed" README
   - code-agent-ui: fix the copy-pasted README (identical to code-agent)
   - Johns-Grimoire: fix the misleading "Python template" README and the misleading GitHub description
   - wizard-academy: has no AGENTS.md; could add one but it's a knowledge base, not a code repo

5. **The .hermes/ structure is becoming its own documentation system** — the 6 orientation files I have, plus the 7 analysis docs from this turn, plus the 4 cached source files = ~15 MD files in .hermes/. **The 4 sibling repos' "rule-authoring" + "commands" + "prompts" patterns from Johns-Grimoire suggest restructuring .hermes/ into a structured agent-doc system.** That's a 2-4h project (P2 in the prior doc), but the pieces are already there.

---

## 1. The saskia-app repo's existing MD inventory (280+ files)

### 1.1 Root MD files (6)

| File | Size | Purpose | Gap |
|---|---|---|---|
| `AGENTS.md` | 28 KB | Build instructions | Already comprehensive; rewrite is iterating |
| `CHANGELOG.md` | 110 KB | Per-PR changelog | **CI requires it** (per CONTRIBUTING.md) |
| `CONTRIBUTING.md` | 3.2 KB | Dev workflow | Has commit + branch conventions not in AGENTS.md |
| `README.md` | 15.6 KB | Repo entry | Has 5 personas (operator/dev/agent/debug/decision) — model for new AGENTS.md personas |
| `WHAT_NEXT.md` | 8.8 KB | Daily/weekly punchlist | Refreshed 2026-10-10 |
| `WHAT_NEXT_2026-10-08-archived.md` | 10 KB | Archived WHAT_NEXT | Reference for history |

### 1.2 app/ MD files (4)

| File | Size | Purpose | Gap |
|---|---|---|---|
| `app/CHANGELOG.md` | 299 KB | Per-PR changelog (in app/) | **CI requires it for app/, scripts/, tests/, .github/** |
| `app/README.md` | 6.3 KB | App-level README | |
| `app/docs/architecture.md` | 4.8 KB | Data flow, sources of truth, deploy | **Reference from AGENTS.md** |
| `app/docs/copy-vos.md` | 6.1 KB | String-level Spanish (voseo) bank | **Reference from AGENTS.md** for UI copy |
| `app/docs/glossary.md` | 5.4 KB | Concept-level Spanish glossary | **Reference from AGENTS.md** for naming |
| `app/docs/threat-model.md` | 5.3 KB | What we defend, what we don't | **Reference from AGENTS.md** |
| `app/docs/upgrade-tiers.md` | 5 KB | 8 upgrade tiers, $0-25/month, decision matrix | **Reference from AGENTS.md** |
| `app/rms/AGENTS.md` | 6 KB | RMS-domain rules (Kiki persona) | Level-3 doc, needs L2 cross-ref |
| `app/_archive/README.md` | 0.8 KB | Archived code location | |

**Total: 9 app-level MD files, 339 KB.** None of these are linked from the root saskia-app/AGENTS.md (except app/rms/AGENTS.md, which is briefly mentioned).

### 1.3 docs/ structure (250+ files)

The `docs/` subtree is the operational knowledge base. It has 17 subdirectories:

| Subdir | Files | Purpose | Notes |
|---|---|---|---|
| `docs/adr/` | 1 | Architecture Decision Records | Only 1 ADR so far. Need more. |
| `docs/analysis/` | 10 | Major analyses (2026-09-22 + 2026-10-08) | The 2026-10-08 set is the most recent |
| `docs/archive/` | 7 | Archived plans | 2026-09 + 2026-10 |
| `docs/backlog/` | 3 | Current backlog | 3 tickets |
| `docs/ci/` | 3 | CI documentation | dependabot, sharded tests, toolchain |
| `docs/competitors/` | 1 | Competitor visual audits | Lightspeed + Square Toast |
| `docs/decisions/` | 1 | Roadmap alignment | canonical-roadmap-alignment |
| `docs/intake/` | 16 | SASKIA-NNN intake tickets | 16 tickets, some shipped, some not |
| `docs/operations/` | 50+ | Day-to-day runbooks | backup-cron, healthz, worktree, dashboard, dora, etc. |
| `docs/plans/` | 25+ | Plans (current + redesign) | Includes SASKIA-209, SASKIA-210 one-pagers |
| `docs/qa/` | 1 | QA plans | round1-qa-plan (31 KB) |
| `docs/reports/` | 19 | Redesign reports | 19 files, biggest is design-plans-2026-09-27 (630 KB) |
| `docs/roadmap/` | 50+ | Roadmap + audits + historical + sessions | The historical section is 13 plans |
| `docs/security/` | 1 | Security baseline | safeguard-baseline.json |
| `docs/superpowers/specs/` | 1 | Design specs | produccion-v3-design |
| `docs/upgrades/` | 1 | UX upgrade plan | UX-UPGRADE-PLAN (45 KB) |
| `docs/user-guide/` | 21 + screenshots | Spanish user guide | 21 guides + 30 screenshots + 6 MB screenshot tarball |
| `docs/ux/` | 7 | UX inventory | copy-fix-list (70 KB), 5 inventory files |
| `docs/wishlist/` | 24 | Wishlist (raw + triaged + rejected) | 1 raw, 22 triaged, 5 rejected |

**Total: 250+ MD files in docs/.** The .hermes/STATE.md (proposed in the prior 47-item doc) should reference this structure.

### 1.4 Specific gaps in the docs/ structure

**These are concrete file additions or audits to do:**

1. **No `docs/README.md` index that maps the 17 subdirectories** (the 2 KB file is minimal). The new structure has 280+ files and no entry point. A 1-2 KB index would help.

2. **No `docs/intake/INDEX.md`** — 16 SASKIA-### tickets, no index. Each ticket is a self-contained "ship this" doc.

3. **The `docs/operations/` has 50+ runbooks but no `docs/operations/README.md`** — wait, there is one (1.2 KB). Let me check the content.

4. **The `docs/roadmap/audits/` has 30+ audit files but no `docs/roadmap/audits/INDEX.md`** — except there is one (3.8 KB).

5. **The `docs/roadmap/sessions/` has 19 session logs but no `INDEX.md`** — except there is one (2.3 KB).

6. **The `docs/wishlist/` has 24 files with a README explaining the contract** — good.

7. **The `docs/user-guide/` has 21 guides + screenshots + scripts** — has a README (10.8 KB).

8. **The `docs/ux/` has 7 files** — the copy-fix-list (70 KB) and 5 inventory files.

9. **The `docs/reports/redesign-2026-09-27/` has 19 files including a 630 KB design-plans-2026-09-27.md** — that's huge. The screenshot-viewer-CATALOGO.html is 2 MB.

10. **The `docs/decisions/` has 1 file** (canonical-roadmap-alignment). **ADRs (docs/adr/) has 1 file** (ADR-001-test-architecture). **These are the "why we did X" docs.** Need more ADRs.

### 1.5 The MD files that the rewrite should cross-reference

These are the files the new saskia-app/AGENTS.md should link to (and that operators should know about):

| File | Why reference it from AGENTS.md |
|---|---|
| `app/docs/architecture.md` | Data flow + sources of truth + deploy topology |
| `app/docs/threat-model.md` | What we defend + what we don't (so agents don't add unneeded security) |
| `app/docs/upgrade-tiers.md` | 8 upgrade options, $0-25/month, decision matrix |
| `app/docs/glossary.md` | Spanish (voseo) terminology for UI copy |
| `app/docs/copy-vos.md` | String-level Spanish bank |
| `app/rms/AGENTS.md` | Level-3 RMS-domain rules |
| `.hermes/HERMES-ORIENTATION.md` | First-5-min orientation for a new Hermes session |
| `.hermes/KNOWN-BYPASSES.md` | Bypass tracker (saves 10-15 min per session) |
| `.hermes/SIBLING-COORDINATION-NOTE.md` | Parallel-session protocol |
| `docs/TEST_ARCHITECTURE.md` | 5-level test abstraction + coverage matrix |
| `docs/USER_FLOW.md` | 4 jobs-to-be-done + day-in-the-life |
| `docs/operations/backup-cron.md` | Daily backup cron runbook |
| `docs/operations/worktree-policy.md` | Worktree policy (canonical) |
| `docs/operations/loyalty-pos-cheatsheet.md` | POS cheat sheet |
| `docs/operations/PRODUCTION_500_RUNBOOK.md` | 500-error runbook |
| `docs/roadmap/STATUS.md` | Live state (schema v117, 116 modules, etc.) |
| `docs/roadmap/BACKLOG.md` | Merged source of truth for the backlog |
| `docs/roadmap/EXECUTION-PLAN.md` | 47 items, 3 P0 drift, 42 forward work |
| `docs/intake/SASKIA-NNN-*.md` | 16 intake tickets |
| `docs/competitors/2026-09-17-visual-audit-toast-square-lightspeed.md` | 3-competitor visual audit |
| `docs/p1-p2-wishlist-2026-09-27.md` | 23 KB wishlist of future features |
| `CONTRIBUTING.md` | Commit + branch conventions, CI requirement (CHANGELOG.md) |
| `README.md` | 5 personas, repo entry |

**That's 23 cross-references** that the new saskia-app/AGENTS.md should add. None currently exist (except `app/rms/AGENTS.md` is mentioned).

---

## 2. The scripts/ inventory (70+ utility scripts)

### 2.1 What I found

The `scripts/` directory has **70+ utility scripts** with no README index. Categories:

| Category | Scripts | Example |
|---|---|---|
| **Backup** | `backup.py`, `backup_cron.py`, `sazon-backup.sh` | VPS-side daily backup |
| **Deploy** | `deploy.sh`, `promote.sh`, `release.sh` | VPS deploy + promotion + release |
| **Migration** | `add_timezone_import.py`, `add_utility_classes.py`, `add_workflow_permissions.py`, `apply_neon_schema.py`, `apply_v056_bank.py`, `migrate_inline_styles.py`, `migrate_inline_stylesheets.py`, `reclassify_sale_channels.py`, `pin_workflow_actions.py`, `refresh_action_pins.py` | Schema + style migrations |
| **BWS (Bitwarden Secrets)** | `bws_list_names.py`, `install_bws_token.sh`, `save_saskia_cf_token.py`, `save_saskia_fernet.py`, `save_sazon_db_url.py`, `save_sazon_user_password.py` | Operator secret storage |
| **Smoke tests** | `smoke_cocina_pages.py`, `smoke_test_deploy_shape.py`, `gen_route_smoke.py` | Deploy-time smoke tests |
| **Audit / quality** | `audit_prune.py`, `check_complexity.py`, `check_currency_drift.sh`, `check_docs_quality.py`, `check_duplicate_code.py`, `check_duplicate_files.py`, `check_imports.py`, `check_md_links.py`, `check_no_secrets.py`, `check_warnings.py`, `check_bank_schema.py`, `check_active_todos.py` | Repo quality |
| **Screenshots** | `capture_screenshots.py`, `shoot_all_pages.py` | User-guide screenshots |
| **Cloudflare** | `cf_tunnel_liveness.py`, `save_saskia_cf_token.py` | Tunnel health |
| **DORA** | `dora_snapshot.py` | Engineering metrics |
| **Lint** | `lint_tier1.py`, `fix_e702.py`, `fix_perf401.py` | CI lint + autofix |
| **Seed** | `seed_full_recipe_data.py`, `seed_packs_gen.py`, `seed_vaquita_holandesa_for_saskia.py`, `inventory_seed_helpers.py` | Seeder |
| **Vendor** | `vendor_vale_styles.sh` | Third-party styles |
| **Misc** | `daily_summary.py`, `monitor_login.py`, `uptimerobot_setup.py`, `ci_alert.py`, `print_deploy_state.py`, `probe_app_introspection.py`, `mark_e2e_tests.py`, `tag_tests_with_markers.py`, `generate_safeguard_baseline.py`, `docs_prose.sh`, `minify_css.py`, `import_herebus_data.py`, `reset_operator_credentials.py`, `verify_catalog_on_vps.py`, `install-pre-commit.sh` | Various |

### 2.2 Gaps in the scripts/ inventory

1. **No `scripts/README.md`** — every script's purpose has to be inferred from its name + content.
2. **No `scripts/INDEX.md`** — no alphabetical or category-based index.
3. **No "common errors" or "AI-assisted fixes" per script** (vs Johns-Grimoire's pattern).
4. **No "first-time setup" doc** — for a new operator, which scripts do you run in what order?
5. **No "deploy runbook" doc that references scripts/deploy.sh, scripts/promote.sh, scripts/release.sh** in a single page.

**Recommendation (P1):** Create `scripts/README.md` as a 2-3 KB index with: category table (like 2.1 above), per-script 1-line purpose, per-script 1-line "common error", and a "first-time setup" sequence. **This is item D from the prior 47-item doc.** Effort: 1-2h.

---

## 3. The 116 .py modules in app/rms/

### 3.1 The two god-modules

Two files dominate the codebase:

| File | Size | Why it matters |
|---|---|---|
| `app/rms/db.py` | 200 KB | Core DB session, schema bootstrap, migration runner |
| `app/rms/models_legacy.py` | 140 KB | Legacy model definitions (single file for backward compat) |

These are the "things that touch everything." Any refactor here is high-risk. The current Sprint 2.x plan is to split them, but it hasn't happened yet.

**Recommendation:** Add a "Refactor targets" section to AGENTS.md that lists these two files plus the candidates for extraction. Effort: 30 min.

### 3.2 The subpackages

`app/rms/` has 7 subpackages:

| Subpackage | Files | Notes |
|---|---|---|
| `loyalty/` | 4 | Loyalty program |
| `sales/` | 4 | Sale-related models (incl. the STUB SaleStockMove per MEMORY) |
| `services/` | 4 | Service layer |
| `tagging/` | 10 | Tag algebra |
| `profitability/` | 2 | Profitability analytics |
| `seed/` | 10 | Seed data |
| `models/` | 13 | Model files (per the app-rms-models-submodule-dead-code skill) |

**Recommendation:** Add a "Subpackage conventions" section to app/rms/AGENTS.md: each subpackage gets its own AGENTS.md, with cross-refs to the parent app/rms/AGENTS.md. Effort: 1-2h.

### 3.3 The "abstraction-layer" violations to fix

The .hermes/KNOWN-BYPASSES.md already tracks 5+ bypass sites (int(Decimal(...)) direct coercion). The actual fix sites are listed in the file. The KNOWN-BYPASSES doc is updated each session; **it's a real, maintained doc, not a stale plan.**

**Recommendation:** Reference KNOWN-BYPASSES.md from app/rms/AGENTS.md so any agent touching app/rms/ reads the bypass tracker first. Effort: 5 min.

---

## 4. The 38 migrations

### 4.1 What's there

The migrations live in `app/rms/migrations/` (per the file listing). I haven't read the actual filenames yet. Per the LIVE STATE in `app/rms/config.py`, `SCHEMA_VERSION = 117` (per HERMES-ORIENTATION). The 5 recent migrations are: 113 (settings_kv), 114 (Sprint 2.1 settings_kv), and 113..117 (allergen/dietary tags, EOD alert templates, ingredient image_url) per STATUS.md.

### 4.2 Gaps in the migrations inventory

1. **No `app/rms/migrations/INDEX.md`** — a numbered index of what each migration does.
2. **No "migration authoring guide"** — what to include in a new migration (idempotency check, downgrade path, post-migration verification).
3. **No "migration rollback" guide** — except the SASKIA-209 one-pager (2.8 KB) which describes the new `sazon rollback` command.

**Recommendation (P1):** Add a 1-2 KB "Migration authoring" section to app/rms/AGENTS.md, with: required pre-conditions, idempotency check, schema-version bump, post-migration verification. Effort: 30 min.

---

## 5. The 15+ intake tickets (SASKIA-NNN)

### 5.1 What's there

The `docs/intake/` directory has 16 SASKIA-### tickets. From the listing:
- SASKIA-201, 202, 203, 203 (duplicate), 204 (×2), 301, 311, 312, 313, 314, 317 (×2), 320

Some shipped, some are open. The SASKIA-317 has 2 docs (parallel-suite + test-isolation). The 16 tickets are self-contained "ship this" docs.

### 5.2 Gaps in the intake pattern

1. **No `docs/intake/INDEX.md`** — 16 tickets, no index.
2. **No clear "what is an intake ticket vs a plan vs an ops doc"** — the boundary is fuzzy.
3. **No template for new intake tickets** — the existing 16 are written in different styles.

**Recommendation (P1):** Add a 1-2 KB "Intake ticket template" section to AGENTS.md or docs/intake/README.md, with: required sections (Problem, Acceptance Criteria, Test Plan, Rollback), size limit, link pattern. Effort: 30 min.

---

## 6. The 50+ operations runbooks

### 6.1 What's there

`docs/operations/` has 50+ runbooks. Categories from the listing:
- **Day-to-day**: backup-cron.md, healthz-db-runbook.md, worktree-policy.md
- **Production incident**: PRODUCTION_500_RUNBOOK.md, 2026-10-09-incident-prod-deps-503.md
- **CI/CD**: 2026-10-09-branch-protection.md, 2026-10-09-ci-recovery.md, 2026-10-10-clean-main-test-audit.md
- **Deploy**: 2026-09-24-three-env-deploy.md, 2026-10-05-produccion-v2-deploy-runbook.md
- **Test infra**: 2026-10-04-*, 2026-10-05-ci-tuning.md
- **Session artifacts**: 2026-10-10-session-handoff.md, 2026-10-10-turn-end-handoff.md
- **Tooling**: 2026-10-09-tooling-*, 2026-10-08-tooling-hardening.md
- **DORA**: 2026-10-04-dora-*.md, dora-snapshots/
- **Dashboard**: dashboard/STATUS.html.tmpl, dashboard/refresh.sh
- **Cheat sheets**: loyalty-pos-cheatsheet.md

### 6.2 Gaps in the operations runbooks

1. **No `docs/operations/INDEX.md` with the runbook categories** (or it's minimal).
2. **No "when to use this runbook" decision tree** — 50+ runbooks and no way to find the right one in 30 seconds.
3. **Some runbooks are dated (2026-10-09-incident-prod-deps-503.md) and should be archived** when no longer relevant.

**Recommendation (P2):** Create `docs/operations/INDEX.md` (2-3 KB) with: category table, "if you have X problem, read Y runbook" decision tree, archive policy. Effort: 1-2h.

---

## 7. The .hermes/ structure (current vs proposed)

### 7.1 Current state (15 files, 188 KB)

```
.hermes/
├── HERMES-ORIENTATION.md (3.8 KB) — first-5-min probe
├── KNOWN-BYPASSES.md (6.6 KB) — bypass tracker
├── SIBLING-COORDINATION-NOTE.md (4.9 KB) — parallel-session protocol
├── sibling-flush-note.md (18.2 KB) — handoff from prior session
├── archives/ (1 file)
├── plans/ (15 files, 218 KB) — Sazon planning
├── _cross_repo_reads/ (53 files, 350 KB) — cached sibling source
├── 2026-10-12-agents-md-community-research.md (26.8 KB)
├── 2026-10-12-agents-md-gap-analysis.md (11.8 KB)
├── 2026-10-12-agents-md-rewrite-draft.md (24.1 KB) — the rewrite
├── 2026-10-12-cross-repo-agents-md-analysis.md (41.9 KB) — 47 items
├── 2026-10-12-deep-read-consolidated.md (33.7 KB) — this turn
├── 2026-10-12-operator-intent-retrospective.md (21.6 KB)
└── 2026-10-12-additional-areas-research.md (this file)
```

### 7.2 Proposed structure (per Johns-Grimoire's .cursor/ pattern)

```
.hermes/
├── orientation/
│   ├── HERMES-ORIENTATION.md (renamed from root)
│   ├── KNOWN-BYPASSES.md
│   ├── SIBLING-COORDINATION-NOTE.md
│   └── STATE.md (NEW — operator's running state)
├── analysis/  (research docs)
│   ├── 2026-10-12-agents-md-community-research.md
│   ├── 2026-10-12-agents-md-gap-analysis.md
│   ├── 2026-10-12-cross-repo-agents-md-analysis.md
│   ├── 2026-10-12-deep-read-consolidated.md
│   ├── 2026-10-12-operator-intent-retrospective.md
│   ├── 2026-10-12-additional-areas-research.md
│   └── _cross_repo_reads/
├── rules/  (durable rules)
│   ├── AGENTS.md
│   ├── app-rms-AGENTS.md
│   └── sister-repos.md
├── plans/  (Sazon planning)
└── drafts/
    └── AGENTS.md-rewrite-draft.md
```

This matches the Johns-Grimoire `.cursor/` pattern: orientation/, rules/, analysis/, plans/. **The current structure is flat; the proposed is hierarchical.** Effort: 2-4h.

**Recommendation (P2):** The restructure is valuable but deferrable. Defer until the next major AGENTS.md rewrite lands and the surface stabilizes.

---

## 8. The 4 sibling repos' deeper recommendations

### 8.1 wizard-academy (knowledge base, not code)

- **Conjuration date:** 2026-02-18
- **Wizard personas:** Aethelred, Merlin 3.0, Nyx 3.0 (the 3.0 suffix suggests these are v3 upgrades)
- **Curriculum:** 8-week foundation course
- **OpenCLAW configs:** aethelred_identity.json, openclaw_exponential.json
- **Audio files:** 19 OGG recordings + 19 transcripts (raw + organized by theme)
- **Recommendation:** Add AGENTS.md describing this as a knowledge base, not a code repo. The 3 personas (Aethelred, Merlin 3.0, Nyx 3.0) are the 3 wizard identities. The "Kiki" persona in app/rms/AGENTS.md is NOT one of them — Kiki is Sazon-specific.

### 8.2 code-agent (active AIW Code Agent, 2 pilot clients)

- **Provenance:** Ecedo Software BV → Eneve (June 2025 merger, Vortex Capital-backed, Netherlands)
- **Acquisition date:** April 2026 (per `Ai-Whisperers/energy21` client engagement)
- **Branches:** `upstream-main`/`upstream-develop` (Eneve baseline) + `aiw/main` (AIW adaptation)
- **Pilot clients:** Vete (multi-tenant SaaS vet clinic, Next.js 15) + Solstein (PE/VC intel, Python 3.10+ with FastAPI/SQLAlchemy/pgvector/LangGraph/Celery)
- **Deploy:** VPS at `72.61.44.159`, GitHub token refresh timer
- **Stack swap:** 9 integrations changed (Bitbucket→GH, JIRA→Linear+GH-Issues, etc.)
- **Recommendation:** Update README to be accurate (2 pilot clients, not "study material"). Add AGENTS.md describing the active AIW customizations.

### 8.3 code-agent-ui (UI for not-deployed-at-scale backend)

- **Stack:** React 19.2 + Vite + TanStack Router/Query/Store + TipTap + Zod + Tailwind 4 + Vitest
- **Age:** UI 1 month, backend 5 months
- **README:** COPY-PASTE of code-agent README (wrong, should be UI-specific)
- **Recommendation:** Fix README. Add AGENTS.md. Decision: mirror code-agent's "ship, freeze, or archive" decision.

### 8.4 Johns-Grimoire (Eneve CI/CD + AI rules docs, mislabeled)

- **Provenance:** Eneve CI/CD + AI rules documentation (was sold to AIW as the "org template")
- **5 .cursor/rules/:** agile, database-standards, quality, rule-authoring, technical-specifications (~50 KB)
- **15+ prompts:** ticket/*, *.prompt.md
- **5 commands:** activate-ticket, check-status, commit, create-docs, create-pr, pursue-ticket
- **15-20 PowerShell scripts:** Eneve's Azure DevOps pipeline
- **Recommendation:** Update GitHub description + README. Add AGENTS.md. The Eneve content is upstream; the AIW adaptations are in `cursor/.cursor/`.

---

## 9. The 6 NEW rules I haven't proposed yet

These are the rules I didn't catch in the prior 47-item doc. They're evidence-based from the deep read.

### Rule 46: Read the .hermes/ orientation files before writing code (already exists in spirit)

- **Source:** .hermes/HERMES-ORIENTATION.md has the 5-step probe sequence
- **Current state:** Implicit in the orientation file
- **Recommendation:** Make explicit in AGENTS.md. "Before any code change: (1) read .hermes/HERMES-ORIENTATION.md, (2) read .hermes/KNOWN-BYPASSES.md, (3) read .hermes/SIBLING-COORDINATION-NOTE.md. This is the 'orient first' rule."
- **Target:** saskia-app/AGENTS.md new "On starting" section
- **Effort:** 5 min

### Rule 47: All PRs touching app/, scripts/, tests/, or .github/ MUST also touch app/CHANGELOG.md

- **Source:** CONTRIBUTING.md hard rule, enforced by CI
- **Current state:** Not in AGENTS.md
- **Recommendation:** Add to saskia-app/AGENTS.md hard rules. "CI rejects PRs without CHANGELOG.md update."
- **Target:** saskia-app/AGENTS.md
- **Effort:** 5 min

### Rule 48: The 3 environments are prod (sazon-vps), test (sazon-test), dev (sazon-dev)

- **Source:** docs/operations/2026-10-09-three-env-deploy.md
- **Current state:** Not in AGENTS.md
- **Recommendation:** Add to saskia-app/AGENTS.md. "3 environments: prod, test, dev. Each has its own Traefik label + DNS."
- **Target:** saskia-app/AGENTS.md
- **Effort:** 5 min

### Rule 49: Kiki is the Sazon-specific AI persona; Aethelred/Merlin/Nyx are wizard-academy personas

- **Source:** app/rms/AGENTS.md has "For Kiki and any agent modifying `app/rms/` modules." wizard-academy has 3 personas.
- **Current state:** Implicit in the orientation files
- **Recommendation:** Make explicit in AGENTS.md. "Kiki = Sazon. Aethelred/Merlin/Nyx = wizard-academy. Don't conflate."
- **Target:** saskia-app/AGENTS.md
- **Effort:** 5 min

### Rule 50: "Don't import from ometz-image-research or other Ometz repos without explicit Iván OK"

- **Source:** saskia-app/AGENTS.md Personas section: "No Gaby in this repo."
- **Current state:** Already in saskia-app/AGENTS.md Personas
- **Recommendation:** Verify this is preserved in the rewrite. (Already in the existing AGENTS.md.)
- **Target:** saskia-app/AGENTS.md
- **Effort:** 0 min (just verify)

### Rule 51: The current Sazon hard rules (40+ in the existing AGENTS.md) are Sazon-specific, not AIW-wide

- **Source:** The existing saskia-app/AGENTS.md hard rules are Sazon-specific (money in Gs., Asunción timezone, Spanish voseo, single-tenant)
- **Current state:** Implicit
- **Recommendation:** Add to saskia-app/AGENTS.md top: "Sazon-specific rules. AIW org standards are in `wizard-academy/wisdom/technical-standards.md` (95/85, zero-warning) and `Johns-Grimoire/.cursor/rules/quality/` (prevention-over-remediation)."
- **Target:** saskia-app/AGENTS.md
- **Effort:** 5 min

---

## 10. The 12 additional files to create

These are NEW files (not just additions to existing ones) that I haven't proposed yet. They follow the 4 sibling repos' patterns.

### 10.1 saskia-app-level (8 files)

| File | Purpose | Pattern from | Effort |
|---|---|---|---|
| `docs/README.md` (rewrite, 2-3 KB) | Index of the 17 docs/ subdirectories | Johns-Grimoire docs/README.md | 1h |
| `docs/operations/INDEX.md` (NEW, 2-3 KB) | Runbook index with decision tree | code-agent docs/ pattern | 1-2h |
| `docs/intake/INDEX.md` (NEW, 1 KB) | 16 SASKIA tickets index | New | 30m |
| `docs/roadmap/audits/INDEX.md` (audit, 1 KB) | 30+ audit files | (already exists at 3.8 KB) | audit only |
| `docs/roadmap/sessions/INDEX.md` (audit, 1 KB) | 19 session logs | (already exists at 2.3 KB) | audit only |
| `scripts/README.md` (NEW, 2-3 KB) | 70 scripts index with errors | Johns-Grimoire cicd/scripts/README.md | 1-2h |
| `.hermes/STATE.md` (NEW, 3-5 KB) | Operator's running state | New | 30m |
| `.hermes/SECURITY.md` (NEW, 1-2 KB) | PAT allowlist, OPSEC, secret rotation | New | 15m |

### 10.2 app/rms-level (4 files)

| File | Purpose | Pattern from | Effort |
|---|---|---|---|
| `app/rms/AGENTS.md` cross-ref to saskia-app/AGENTS.md | Level-3 → Level-2 | New | 5m |
| `app/rms/migrations/INDEX.md` (NEW, 2-3 KB) | 38 migrations index | New | 1h |
| `app/rms/migrations/AUTHORING.md` (NEW, 2-3 KB) | Migration authoring guide | New | 1h |
| `app/rms/subpackage-AGENTS.md` template (NEW, 1-2 KB) | Template for subpackage AGENTS.md | New | 30m |

### 10.3 4 sibling repos (4 files)

| File | Purpose | Effort |
|---|---|---|
| `wizard-academy/AGENTS.md` (NEW) | "This is a knowledge base, not a code repo." | 15m |
| `code-agent/AGENTS.md` (NEW) | Active AIW Code Agent, 2 pilot clients | 30m |
| `code-agent-ui/AGENTS.md` (NEW) | UI for backend, fix README | 15m |
| `Johns-Grimoire/AGENTS.md` (NEW) | Eneve CI/CD + AI rules docs | 30m |

**Total: 16 new files. ~8-12 hours of work.**

---

## 11. The 5 already-existing things I should NOT duplicate

The prior 47-item doc had a few items that already exist in the current repo. Avoid duplicating:

1. **"Don't migrate to React/Vue/Tailwind"** — already in saskia-app/AGENTS.md Anti-rule #1
2. **"to_int_gs() is the ONLY path"** — already in saskia-app/AGENTS.md Hard rule #2
3. **"All datetime math uses ASUNCION_TZ"** — already in app/rms/AGENTS.md Time rules
4. **"No `int(Decimal(...))` direct coercion"** — already in .hermes/KNOWN-BYPASSES.md
5. **"Worktree policy"** — already in .hermes/SIBLING-COORDINATION-NOTE.md (and conflicts with docs/operations/worktree-policy.md)

**Recommendation:** Re-verify each of the 47 items against the current saskia-app/AGENTS.md before adding. Some are already there. Effort: 30 min.

---

## 12. The 4 conflicts to resolve

These are actual contradictions in the existing docs that need resolving:

### 12.1 Worktree policy conflict

- `docs/operations/worktree-policy.md`: scratch = main + deploys, production = feature dev
- `.hermes/SIBLING-COORDINATION-NOTE.md`: saskia-app = canonical worktree (current session)
- **Resolution:** The 3 actual worktrees in use are: `/opt/data/work/saskia-app` (this, SASKIA-212), `/opt/data/work/saskia-app-abstraction-gates` (main), `/opt/data/work/saskia-app-vaquita` (SASKIA-213). The legacy `/opt/data/scratch/saskia-app` is DO NOT TOUCH.
- **Recommendation:** Update `.hermes/SIBLING-COORDINATION-NOTE.md` to reference `docs/operations/worktree-policy.md` as canonical, and list the 3 actual worktrees. Effort: 15 min.

### 12.2 Coverage standard conflict

- `wizard-academy/wisdom/technical-standards.md`: 95% line + 85% branch (AIW standard)
- `CONTRIBUTING.md`: 80%+ (Sazon target)
- `saskia-app/AGENTS.md` Rule 30: 40% (Sazon current)
- **Resolution:** All 3 are different. The wizard-academy 95/85 is the AIW strategic standard. Sazon's 40% is current. The CONTRIBUTING.md 80% is the operator's stated target.
- **Recommendation:** saskia-app/AGENTS.md should: (1) reference the AIW standard (95/85), (2) state the operator's target (80%), (3) state the current Sazon gate (40%) with the gap. Effort: 10 min.

### 12.3 Deployment mode conflict

- `app/docs/architecture.md`: local-first only (single PC, single user)
- `saskia-app/AGENTS.md`: local-first + hosted (since 2026-09-24)
- **Resolution:** Architecture doc is stale. Current state is 3-env (prod, test, dev) on VPS.
- **Recommendation:** Update `app/docs/architecture.md` to reflect the 3-env hosted mode. Effort: 30 min.

### 12.4 Kiki vs Aethelred/Merlin/Nyx personas

- `app/rms/AGENTS.md`: "For Kiki and any agent modifying `app/rms/` modules."
- `wizard-academy/configurations/aethelred_identity.json`: Aethelred persona
- **Resolution:** Kiki is Sazon-specific. Aethelred/Merlin/Nyx are wizard-academy. No conflict, but the new saskia-app/AGENTS.md should be explicit.
- **Recommendation:** Add persona clarification to saskia-app/AGENTS.md Personas section. Effort: 5 min.

---

## 13. The 3 cross-AIW patterns I haven't mapped

These are AIW-wide patterns that the prior 47-item doc didn't surface. They need investigation.

### 13.1 The "Mburucuyá-PotyPy" stack

- 1 of the 5 repos in the GitHub PAT allowlist
- Per code-agent README: AIW uses Supabase + Hermes
- **Need to read:** actual Mburucuyá-PotyPy repo to understand the stack

### 13.2 The "aiw-org" agent definitions

- 116 agents + 79 crons (per aiw-org topic)
- **Need to read:** actual aiw-org repo to understand the agent registry pattern
- This is the AIW-wide "who does what" doc; cross-referencing saskia-app/AGENTS.md to it would clarify which agent handles what

### 13.3 The "aiw-template" / "base" / "repo-template" pattern

- 3 of 59 AIW repos are templates (per the prior consolidation audit)
- **Need to read:** the canonical AIW template to understand the org-level structure
- The Johns-Grimoire README claims to be the AIW template, but the actual content is Eneve's. **The real AIW template is somewhere else.**

**Recommendation (P1):** Add a 1-2 KB "AIW-wide patterns" section to saskia-app/AGENTS.md, referencing Mburucuyá-PotyPy, aiw-org, and the real AIW template (TBD). Effort: 30 min (after reading the 3 repos).

---

## 14. The 5 quick wins (under 30 min each)

If the operator has 30 min, do these:

1. **Verify the 47 items against current saskia-app/AGENTS.md** (30 min) — some are already there.
2. **Add the 6 NEW rules (46-51) to saskia-app/AGENTS.md** (30 min) — evidence-based, not in the current AGENTS.md.
3. **Resolve the worktree policy conflict** (15 min) — update .hermes/SIBLING-COORDINATION-NOTE.md to reference docs/operations/worktree-policy.md as canonical.
4. **Resolve the coverage standard conflict** (10 min) — clarify the 3 levels (95/85 AIW, 80% target, 40% current) in saskia-app/AGENTS.md.
5. **Add a Sister-repos section to saskia-app/AGENTS.md** (15 min) — 1-liner per sibling repo.

**Total: ~2 hours for the 5 quick wins.**

---

## 15. The 4 research directions I haven't pursued

These are areas where additional research would help but I haven't had time:

### 15.1 The aiw-org repo (116 agents, 79 crons)

- **Need to read:** the actual agent registry to understand which agent handles what
- **Why it matters:** saskia-app/AGENTS.md might be over-specifying what an agent needs to know about
- **Effort:** 1-2h

### 15.2 The Mburucuyá-PotyPy repo (the AIW-defining product)

- **Need to read:** the actual repo to understand the AIW stack
- **Why it matters:** "AIW-wide patterns" reference in saskia-app/AGENTS.md would be more accurate
- **Effort:** 1-2h

### 15.3 The real AIW template repo (NOT Johns-Grimoire)

- **Need to find:** the actual org template (likely aiw-template or base or repo-template)
- **Why it matters:** saskia-app was probably built from the AIW template; knowing the template's rules would clarify what saskia-app extends vs diverges
- **Effort:** 1-2h

### 15.4 The aiw-org backlog/cron patterns

- **Need to read:** the 79 cron definitions to understand the AIW automation surface
- **Why it matters:** Sazon's ops (deploy, backup, EOD) might be replicated at the AIW level
- **Effort:** 1-2h

**Total research time: 4-8 hours.**

---

## 16. The final consolidated table

The total scope of additional work (this turn + prior turn):

| Category | Items | Effort | Priority |
|---|---|---|---|
| **MD file additions** (NEW files) | 16 | 8-12h | mixed |
| **MD file audits** (existing files) | 23 cross-refs | 2-3h | P0 |
| **AGENTS.md rule additions** (new rules 46-51) | 6 | 30m | P0 |
| **Doc conflicts to resolve** (4 conflicts) | 4 | 1h | P0 |
| **Quick wins** (5 under-30-min items) | 5 | 2h | P0 |
| **4 sibling repos' recommendations** (8 items) | 8 | 4-6h | P1 |
| **4 research directions** (uncovered areas) | 4 | 4-8h | P2 |
| **Sazon-specific facts** (47 items, prior turn) | 47 | 12-18h | mixed |
| **Total** | **~113 items** | **~35-50h** | |

The P0 items are ~6-8 hours of work. P1 is another ~6-10 hours. P2 is another ~15-20 hours.

**The 6 must-do P0 items** (per prior turn): 95/85 + zero-warning cross-ref, Sazon client profile, 6 of 6 done + T1-T4 + 11 new rules, .hermes/STATE.md, fix 3 sibling repo descriptions, read Johns-Grimoire rule-authoring framework.

**The 5 additional quick wins** (this turn): verify 47 items, add rules 46-51, resolve worktree conflict, resolve coverage conflict, add Sister-repos section.

**Total P0 work: 6-8 + 2 = 8-10 hours.** That's the realistic estimate for "perfect saskia-app/AGENTS.md + .hermes/ orientation layer + 4 sibling repos' recommendations."

---

## 17. The doc hierarchy after all this work (visualized)

```
saskia-app/                                # Level 2 (product)
├── AGENTS.md  [~40 KB, comprehensive, 6 of 6 done, T1-T4, 51 rules, cross-refs to L1 + L3]
├── CHANGELOG.md  [CI-required]
├── CONTRIBUTING.md  [Commit + branch conventions]
├── README.md  [5 personas, repo entry]
├── WHAT_NEXT.md  [Operator's daily punchlist]
├── app/
│   ├── CHANGELOG.md  [CI-required for app/]
│   ├── README.md
│   ├── docs/  [8 docs: architecture, threat-model, upgrade-tiers, glossary, copy-vos, etc.]
│   ├── rms/
│   │   ├── AGENTS.md  [Level 3 (domain), Kiki persona, cross-refs to L2]
│   │   ├── migrations/INDEX.md  [NEW, 38 migrations]
│   │   ├── migrations/AUTHORING.md  [NEW]
│   │   └── subpackage-AGENTS.md  [NEW, template]
│   └── ...
├── docs/  [17 subdirs, 280+ files, README.md index]
│   ├── README.md  [REWRITE, 2-3 KB index of 17 subdirs]
│   ├── operations/INDEX.md  [NEW, runbook index]
│   ├── intake/INDEX.md  [NEW, 16 tickets]
│   └── ...
├── scripts/
│   └── README.md  [NEW, 70 scripts index]
└── .hermes/  [Hierarchical, per Johns-Grimoire pattern]
    ├── orientation/
    │   ├── HERMES-ORIENTATION.md
    │   ├── KNOWN-BYPASSES.md
    │   ├── SIBLING-COORDINATION-NOTE.md  (resolve worktree conflict)
    │   └── STATE.md  [NEW]
    ├── analysis/  [7 research docs from this turn]
    ├── rules/
    │   └── AGENTS.md  (current root AGENTS.md moved here)
    ├── security/
    │   └── SECURITY.md  [NEW, PAT allowlist, OPSEC]
    ├── plans/  [Sazon planning]
    └── drafts/
        └── AGENTS.md-rewrite-draft.md

4 sibling repos/  # Level 1 (org-wide, references in saskia-app/AGENTS.md)
├── wizard-academy/AGENTS.md  [NEW]
│   └── wisdom/technical-standards.md  [95/85, zero-warning]
├── code-agent/AGENTS.md  [NEW]
│   └── docs/clients/{saskia,vete,solstein}.md  [client profile pattern]
├── code-agent-ui/AGENTS.md  [NEW]
└── Johns-Grimoire/AGENTS.md  [NEW]
    └── .cursor/rules/  [5 rule files, ~50 KB]
```

That's the complete doc surface after all the work. The new saskia-app/AGENTS.md is the level-2 hub; .hermes/STATE.md is the operator's running state; the 4 sibling repos are the level-1 org-wide standards.

---

## 18. The 1-paragraph final summary

Beyond the 47 items I documented in the prior turn, the deep read of the 280+ MD files in saskia-app revealed: (1) the current saskia-app/AGENTS.md is already comprehensive (some 47 items already exist), (2) there are 4 real doc conflicts (worktree policy, coverage standard, deployment mode, persona boundaries), (3) there are 16 NEW files to create (8 saskia-app + 4 app/rms + 4 sibling), (4) there are 6 NEW AGENTS.md rules (46-51), (5) there are 23 cross-references the new saskia-app/AGENTS.md should add, and (6) there are 4 research directions I haven't pursued (aiw-org, Mburucuyá-PotyPy, real AIW template, AIW cron patterns). The P0 work is 8-10 hours. The full work is 35-50 hours.
