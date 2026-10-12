# Complete update plan — saskia-app + 4 sibling repos + .hermes/ + AIW org

**Compiled:** 2026-10-12 (synthesis of 3 prior research turns)
**Sources:**
- `.hermes/2026-10-12-agents-md-community-research.md` (26.8 KB) — community research
- `.hermes/2026-10-12-agents-md-gap-analysis.md` (11.8 KB) — gap analysis
- `.hermes/2026-10-12-agents-md-rewrite-draft.md` (24.0 KB) — the rewrite draft
- `.hermes/2026-10-12-operator-intent-retrospective.md` (21.6 KB) — operator intent
- `.hermes/2026-10-12-cross-repo-agents-md-analysis.md` (41.9 KB) — cross-repo analysis
- `.hermes/2026-10-12-deep-read-consolidated.md` (33.7 KB) — 47-item consolidated
- `.hermes/2026-10-12-additional-areas-research.md` (39.6 KB) — 113 additional items
- 53 cached source files in `.hermes/_cross_repo_reads/`
- Current saskia-app/AGENTS.md (28.3 KB), app/rms/AGENTS.md (6.1 KB), and 280+ other MD files

**This is the master update plan.** Every file to add, update, archive, or remove is listed below with exact line-level changes, the rationale, the source of evidence, the effort, the priority, the order of operations, and the verification step.

**Total scope: ~113 items, ~35-50 hours of work, broken into:**
- **P0 (8-10 hours)**: saskia-app/AGENTS.md rewrite + 6 new rules + 4 doc conflicts resolved + 4 new files
- **P1 (6-10 hours)**: 4 sibling repos' fixes + 6 new files + 23 cross-references
- **P2 (15-20 hours)**: .hermes/ restructure + 4 research directions + remaining cleanups

**The order is: 1) P0 verification first (30 min), 2) P0 work (8-10h), 3) P1 (6-10h), 4) P2 (15-20h).** Each phase has explicit verification gates.

---

## 0. Verification gate — read first (30 min)

Before any of the work below, do these 4 verification steps. Each catches a class of "I added a rule that already exists" or "I missed a conflict" errors.

### V1. Verify the 47 items against the current saskia-app/AGENTS.md (30 min)

Open `/opt/data/work/saskia-app/AGENTS.md` and the 47-item list in `.hermes/2026-10-12-deep-read-consolidated.md` §3. For each item, search the current AGENTS.md for the key phrase. Mark:

- **EXISTS** — already in AGENTS.md, no change needed
- **PARTIAL** — similar but not identical, needs update
- **MISSING** — not in AGENTS.md, add to rewrite

The expected result is roughly: 20-25 EXIST, 10-15 PARTIAL, 10-15 MISSING. The EXIST items should be deleted from the rewrite draft. The PARTIAL items should be modified to match the current state. The MISSING items should be added as-is.

### V2. Verify the live state (5 min)

```bash
cd /opt/data/work/saskia-app
grep CURRENT_SCHEMA_VERSION app/rms/config.py   # expect 117
git rev-parse --abbrev-ref HEAD                  # confirm branch
git log --oneline -5                             # check who wrote recent commits
git worktree list                                # see sibling worktrees
```

Confirm the 3 active worktrees:
- `/opt/data/work/saskia-app` (this, SASKIA-212)
- `/opt/data/work/saskia-app-abstraction-gates` (main)
- `/opt/data/work/saskia-app-vaquita` (SASKIA-213)

The legacy `/opt/data/scratch/saskia-app` is DO NOT TOUCH.

### V3. Verify the 4 doc conflicts are still conflicts (10 min)

- Read `docs/operations/worktree-policy.md` and `.hermes/SIBLING-COORDINATION-NOTE.md` side by side. Confirm the worktree policy conflict.
- Read `wizard-academy/wisdom/technical-standards.md` (cached at `_cross_repo_reads/WA_wisdom__technical-standards.md`), `CONTRIBUTING.md`, and the current AGENTS.md Rule 30. Confirm the 95/80/40 coverage conflict.
- Read `app/docs/architecture.md` and the current AGENTS.md deployment section. Confirm the local-first-only vs 3-env conflict.
- Read `app/rms/AGENTS.md` and `wizard-academy/configurations/aethelred_identity.json`. Confirm the Kiki vs Aethelred/Merlin/Nyx persona conflict (this one is actually a non-conflict — Kiki is Sazon-specific — but it's worth verifying).

### V4. Verify the 5 already-existing things (5 min)

From the additional-areas doc §11:
- "Don't migrate to React/Vue/Tailwind" — in current AGENTS.md Anti-rule #1
- "to_int_gs() is the ONLY path" — in current AGENTS.md Hard rule #2
- "All datetime math uses ASUNCION_TZ" — in app/rms/AGENTS.md Time rules
- "No `int(Decimal(...))` direct coercion" — in .hermes/KNOWN-BYPASSES.md
- "Worktree policy" — in .hermes/SIBLING-COORDINATION-NOTE.md (and conflicts with docs/operations/worktree-policy.md — see V3)

The 4 EXIST items should not be duplicated. The 1 conflict should be resolved per V3.

---

## 1. P0 — saskia-app/AGENTS.md rewrite (3-4 hours)

### 1.1 Files to update (1 file, ~3,400 lines change)

**File:** `/opt/data/work/saskia-app/AGENTS.md`
**Current:** 28,345 bytes, 443 lines
**Target:** ~32,000 bytes, ~500 lines (net +4,000 bytes for the 6 of 6 done, T1-T4, 11 new rules, sister-repos section, 23 cross-references, and AIW context section)

**What to do:**

1. Open `.hermes/2026-10-12-agents-md-rewrite-draft.md` (the 24 KB rewrite draft)
2. Open the current `/opt/data/work/saskia-app/AGENTS.md` (the 28 KB live file)
3. Per V1, identify which of the 47 items are EXIST, PARTIAL, MISSING
4. Apply the 11 NEW rules from the prior turn (Rules 39-45 + the 6 of 6 done + T1-T4 + shim is permanent + no `-X ours` + no prod DB in fixtures + no AI-edit of AGENTS.md)
5. Apply the 6 NEW rules from this turn (Rules 46-51): read .hermes/ first, CHANGELOG.md CI-required, 3 envs, Kiki ≠ Aethelred, preserve "no Ometz" rule, Sazon-specific vs AIW org
6. Add the Sister-repos section with 1-liner per sibling repo
7. Add the AIW context section (95/85 + zero-warning + 39/41/40+/2 numbers + Vete/Solstein pilots)
8. Add the 23 cross-references to existing MD files (see §3 of additional-areas doc)
9. Resolve the 4 doc conflicts inline (worktree, coverage, deployment, personas)
10. Update the verification gate (V1) result in the rewrite draft

**Specific changes (with line-level guidance):**

| Section | Change | Source |
|---|---|---|
| **Top — On starting** (NEW) | Add 4-step "before any code change" rule | Rule 46 (this turn) |
| **Personas** | Clarify Kiki (Sazon) vs Aethelred/Merlin/Nyx (wizard-academy) | Rule 49 |
| **Personas** | Preserve "No Gaby in this repo" + "no Ometz imports" | Rule 50 (verify) |
| **Hard rules — new sub-section** (NEW) | 6 of 6 done definition | Operator intent |
| **Hard rules — new sub-section** (NEW) | T1-T4 decision authority tiers | Operator intent |
| **Hard rules — add Rules 39-45** | Topic tags, OPSEC, language, branch, Telegram, tenancy, deploy | Prior turn |
| **Hard rules — add Rule 47** | CHANGELOG.md is CI-required | CONTRIBUTING.md |
| **Hard rules — add Rule 48** | 3 envs (prod, test, dev) | 2026-10-09-three-env-deploy |
| **Hard rules — clarify Rule 30** | 95/85 AIW, 80% target, 40% current | Wizard-academy + CONTRIBUTING |
| **Hard rules — add zero-warning** | "A warning is a bug" | Wizard-academy technical-standards |
| **Anti-rules — add Rules 21-22** | No prod DB in fixtures; no AI-edit of AGENTS.md | Prior turn |
| **Anti-rules — add Rule 38** | No `-X ours` | Prior turn |
| **Sister repos** (NEW section) | 1-liner per sibling repo + 6 NEW rules (Rules 41-45) | Prior turn + cross-repo analysis |
| **AIW context** (NEW section) | 39/41/40+/2 numbers + Vete/Solstein pilots + code-agent in pilot phase | code-agent README + docs/ |
| **Cross-references** (throughout) | 23 links to existing MD files | Additional-areas doc §1.5 |
| **Deployment** (clarify) | 3 envs (prod, test, dev), not just local-first + VPS | 2026-10-09-three-env-deploy |
| **Worktree policy** (clarify) | Reference docs/operations/worktree-policy.md as canonical, list 3 actual worktrees | Conflict resolution |
| **Coverage** (clarify) | 95/85 AIW, 80% target, 40% current (gap to close) | Conflict resolution |
| **Personas** (clarify) | Kiki = Sazon, Aethelred/Merlin/Nyx = wizard-academy, no conflation | Rule 49 |
| **Troubleshooting — add 500-runbook cross-ref** | Reference docs/operations/PRODUCTION_500_RUNBOOK.md | Existing runbook |
| **When in doubt — add 5 NEW docs** | architecture.md, threat-model.md, upgrade-tiers.md, glossary.md, copy-vos.md | Existing docs |

**Verification after the rewrite:**

- `git diff --stat AGENTS.md` should show ~+4,000 bytes net
- `wc -l AGENTS.md` should show ~500 lines
- Search for "Kiki" — should be mentioned
- Search for "Aethelred" — should NOT be mentioned in the Sazon AGENTS.md (only in the comment about wizard-academy personas)
- Search for "sazon-vps.paragu-ai.com" — should be in the deployment section
- Search for "SPRINT" or "95%" — should be in the coverage section
- Search for "Sister repos" — should be a section
- Search for "Gaby" — should mention "no Gaby in this repo"
- Search for "CHANGELOG.md" — should mention CI-required

**Effort:** 3-4 hours (assuming V1 already done; if V1 is included, 3.5-4.5 hours)

---

## 2. P0 — 4 NEW files in saskia-app/ (3-4 hours)

### 2.1 `saskia-app/docs/clients/saskia.md` (NEW, 1-2 hours)

**Pattern from:** code-agent `docs/clients/vete.md` (9.4 KB) and `docs/clients/solstein.md` (11.3 KB)

**Sections to include (per the Vete/Solstein template):**

```markdown
# Client Profile: Saskia (La Vaquita Feliz)

> Multi-tenant SaaS restaurant management for a single bakery. Single client (Saskia/La Vaquita Feliz) on per-client INSTANCES (SASKIA-210).

## Repository

| Field | Value |
|---|---|
| **GitHub** | `Ai-Whisperers/sazon-app` (private) |
| **Default branch** | `main` |
| **Target branch for PRs** | `main` |
| **Size** | ~9.7 MB (per STATUS.md) |
| **LOC (app/)** | 96,306 lines across 116 modules |
| **LOC (tests/)** | 124,258 lines |
| **Test files** | 734 files, 6,855 test functions |
| **Migrations** | 117 (schema v117) |
| **Routes** | 372 (350 in routers + 22 in app root) |
| **Language** | Python 3.10+ (target 3.12), src-layout |
| **Stack** | FastAPI · SQLAlchemy 2.0 sync · SQLite (local) + Postgres (hosted) · Jinja2 + HTMX · Pydantic · ruff · pytest · Alembic-style migrations |
| **Auth** | bcrypt + session cookies (local); Supabase JWT (hosted, in transition) |
| **Deploy** | Docker Swarm + Traefik + Cloudflare DNS-01 (3 envs: prod, test, dev) |
| **Observability** | Sentry (since 2026-10-01) · Resend (transactional email, in transition) · OpenTelemetry (since 2026-10-01) · 4 EOD anomaly checks |
| **Tenancy** | Single-tenant per SASKIA-210 (one client = one DB instance) |
| **Topics** | bakery · restaurant-management · paraguay · fastapi · sqlalchemy · htmx |
| **Live URL** | https://sazon-vps.paragu-ai.com (prod) |
| **Backup** | Daily VPS-side cron at 03:15 (14-day retention) + in-app startup backup to ~/Documents/aiw-restaurant/backups/ + encrypted Cloudflare R2 snapshot |

## Tenancy model (CRITICAL)

Sazon is **single-tenant** (SASKIA-210, 2026-10-07). One client (Saskia/La Vaquita Holandesa) gets one fully-loaded instance. The `tenant` table from migration 008 is **legacy**, not active multi-tenanting. Future multi-tenant work deferred until we have ≥2 paying clients.

## Monorepo layout

- Root: `AGENTS.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `README.md`, `WHAT_NEXT.md`
- `app/`: FastAPI app, CHANGELOG.md, docs/, rms/ (core domain), migrations/, models/, routers/
- `docs/`: 280+ MD files (operations, plans, reports, roadmap, user-guide, etc.)
- `scripts/`: 70+ utility scripts (deploy, backup, seed, smoke, audit, CI)
- `tests/`: 734 files, 6,855 tests
- `.hermes/`: Hermes agent orientation (3 files), analysis (7 docs from 2026-10-12), plans (15 files)

## Key conventions

- **Money math:** `Decimal` only; `to_int_gs()` is the ONLY Decimal → int path; see `app/rms/AGENTS.md` Money rules
- **Time math:** All datetime uses `zoneinfo.ZoneInfo("America/Asuncion")` via `ASUNCION_TZ`; see `app/rms/AGENTS.md` Time rules
- **Units:** All unit input through `Unit.coerce()`; cross-family conversion forbidden
- **CI:** PRs touching `app/`, `scripts/`, `tests/`, or `.github/` MUST touch `app/CHANGELOG.md`
- **Coverage:** AIW standard 95/85; Sazon target 80%; current 32% (per 2026-10-12 test-suite-analysis)
- **Zero-warning:** Per wizard-academy/technical-standards, "a warning is a bug"

## Sister repos

| Repo | Purpose | Status |
|---|---|---|
| `Ai-Whisperers/wizard-academy` | AIW knowledge base (4 wisdom pillars, 3 wizard personas) | Active, knowledge |
| `Ai-Whisperers/code-agent` | AIW Code Agent (2 pilot clients: Vete + Solstein) | Pilot phase |
| `Ai-Whisperers/code-agent-ui` | UI for code-agent | Active, UI-only |
| `Ai-Whisperers/Johns-Grimoire` | Eneve CI/CD + AI rules docs (mislabeled "Python template") | Reference |

## Current state (2026-10-12)

- Schema v117, 116 app modules, 6,855 tests, ~32% coverage
- 3 envs live: prod, test, dev
- 8 open issues on code-agent (AIW customizations in flight)
- Deferrals: Supabase Storage for product images, Supabase RLS multi-tenant (per SASKIA-210)
- Open PRs: 0
```

**Verification:** File size ~5-7 KB, 100+ lines. `git diff --stat` should show +1 file.

**Effort:** 1-2 hours (template from Vete/Solstein is ready, just adapt to Sazon)

### 2.2 `saskia-app/.hermes/STATE.md` (NEW, 1-2 hours)

**Sections to include:**

```markdown
# STATE — operator's running state for saskia-app

**Last updated:** 2026-10-12
**Why this exists:** The 5 P0 items for the next 4 weeks + the AIW-wide numbers + the 4 sibling repos' state + the OPSEC-sensitive deploy info. Single source of truth for "what's the current state?"

---

## 1. The 5 P0 items for the next 4 weeks

1. **SASKIA-212 recipe-instructions-editor** (this branch) — ship the recipe instructions editor
2. **SASKIA-211e** — apply the AGENTS.md rewrite (per the rewrite draft)
3. **SASKIA-213 vaquita-seed-data-update** — apply the vaquita seed updates
4. **Coverage sprint to 80%** — currently 32%, target 80% per CONTRIBUTING.md (gap of 48 percentage points)
5. **Schema v118** — likely the next migration; TBD by operator

## 2. AIW-wide numbers (per code-agent/README + 2026-10-09-three-env-deploy + saskia-app STATUS)

- **59 repos** in Ai-Whisperers org
- **39 active repos** on GitHub
- **41 of 59 use Supabase Auth** (Sazon is one of the 19 that don't — uses bcrypt + session cookies locally; Supabase JWT in transition for hosted)
- **40+ of 59 use Telegram via Hermes gateway** (Sazon is one of the 19 that don't — bakery customers don't see Telegram)
- **2 pilot clients** on AIW Code Agent: Vete (multi-tenant vet, Next.js 15 + Supabase RLS) + Solstein (PE/VC intel, Python 3.10+ + FastAPI + pgvector)
- **112K LOC Java + 57K LOC TS** in code-agent + code-agent-ui
- **116 app modules + 70 scripts + 734 test files** in saskia-app
- **3 envs** on Sazon VPS: prod, test, dev (since 2026-10-09)

## 3. Sazon live state (per STATUS.md + HERMES-ORIENTATION)

- **Schema:** v117
- **Main branch:** `main` @ `640c21e5` (per STATUS.md 2026-10-09)
- **Live URL:** https://sazon-vps.paragu-ai.com
- **Deploys:** Docker Swarm + Traefik + Cloudflare DNS-01 on VPS (paragu-ai/ServaRica)
- **Code stats:** 96,306 app LOC + 124,258 test LOC = 1.29× test-to-app ratio
- **Test stats:** 734 files, 6,855 test functions, ~32% line coverage
- **Routes:** 372 (350 in routers + 22 in app root)
- **Migrations:** 117
- **Commits:** ~1,530
- **Last schema bump:** 2026-10-09 (allergen/dietary tags, EOD alert templates, ingredient image_url)

## 4. The 3 worktrees

| Worktree | Branch | Owner | Notes |
|---|---|---|---|
| `/opt/data/work/saskia-app` | `SASKIA-212-recipe-instructions-editor` | this session | current work |
| `/opt/data/work/saskia-app-abstraction-gates` | `main` | abstraction-gates sibling | previous session |
| `/opt/data/work/saskia-app-vaquita` | `SASKIA-213-vaquita-seed-data-update` | vaquita sibling | TBD |
| `/opt/data/scratch/saskia-app` | `main` (legacy) | **DO NOT TOUCH** | old git history |

## 5. The 4 sibling repos (sister repos)

- **`wizard-academy`** (27.7 MB, 5 months stale, Python/Shell) — AIW knowledge base, 4 wisdom pillars, 3 wizard personas, 19 audio recordings. Not a code repo. **Issue:** misleading GitHub description, no AGENTS.md, `archived` topic is wrong.
- **`code-agent`** (4.8 MB, 5 months stale, Java/Quarkus) — AIW Code Agent in pilot, 2 clients (Vete + Solstein). **Issue:** README says "NOT production-deployed" but it IS in pilot; `archived` topic is wrong.
- **`code-agent-ui`** (2.8 MB, 1 month stale, React/Vite) — UI for code-agent. **Issue:** README is copy-paste of code-agent; `archived` topic is wrong.
- **`Johns-Grimoire`** (1.7 MB, 1 month stale, PowerShell/Python) — Eneve CI/CD + AI rules docs, mislabeled as "Python template." **Issue:** GitHub description + README both misleading; `archived` topic is wrong.

## 6. OPSEC-sensitive info (redacted in shared docs)

- **VPS IP (code-agent):** `72.61.44.159` (root SSH, per code-agent docs/OPERATIONS.md)
- **VPS provider:** Servarica (paragu-ai)
- **Backup retention:** 14 days daily VPS-side cron at 03:15
- **Backup location:** VPS at `/tmp/sazon_backups/`
- **GitHub PAT:** "hermes all access" — **ROTATED 2026-10-12** (operator action — replace with BWS-stored token)
- **Per-client DB instances:** Sazon uses per-instance DBs (SASKIA-210); Supabase RLS multi-tenant deferred

## 7. The Sazon backlog (47 items, per EXECUTION-PLAN.md)

- **3 P0 drift items** (redeploy, migration 098, env vars) — block 1+ Done items
- **42 forward work items** — see EXECUTION-PLAN.md
- **2 open items from IMPROVEMENT_BACKLOG:** #37 (Supabase Storage for product images) + #38 (Supabase RLS for multi-tenant)

## 8. Recent operations (last 7 days)

- 2026-10-12: this turn — AGENTS.md rewrite analysis
- 2026-10-10: Sprint 2.1 closeout, v2026.10.1 released (commit `e54c4571`), 6 PRs
- 2026-10-09: All 6 tiers of deferred-work plan landed, no deferrals
- 2026-10-08: docs-quality PRs 1-5 landed (235-marker TODO resolved)
- 2026-10-01: Phase 14 observability + CF tunnel cron landed
- 2026-09-24: Migration from Render to VPS (3 envs)
```

**Verification:** File size ~6-8 KB, 100+ lines. `git diff --stat` should show +1 file.

**Effort:** 1-2 hours (most content is synthesized from the prior research)

### 2.3 `saskia-app/.hermes/SECURITY.md` (NEW, 30 min)

**Sections to include:**

```markdown
# SECURITY — PAT allowlist, OPSEC, secret rotation

**Last updated:** 2026-10-12

---

## 1. GitHub PAT setup

For any PAT used to access Ai-Whisperers repos, the following permissions are required:

**Repository permissions (add at the repo level):**
- `Contents: Read-only` — required for `GET /repos/.../contents/`
- `code: Read and Write` — required for the Contents API
- `Issues: Read-only` — for the Issues API
- `Pull requests: Read-only` — for the PR API

**Repository access:**
- Either set to "All repositories" or add the specific repos needed

**Without `Contents: Read-only` at the repo level, the Contents API returns 403 even on "all access" tokens.** This is a GitHub fine-grained-PAT permission, not visible in the page description.

## 2. Secret rotation policy

- All PATs rotate every 90 days
- All PATs are stored in BWS (Bitwarden Secrets), never in chat
- If a PAT appears in chat, ROTATE IMMEDIATELY (treat as compromised)

**Procedure to rotate:**
1. Open https://github.com/settings/personal-access-tokens/
2. Find the token, click Edit
3. Click "Regenerate token" (this revokes the old one)
4. Copy the new secret
5. Store in BWS: `bws secret create --name "github-pat-hermes" --value "<new-secret>"`
6. Test: `curl -H "Authorization: Bearer $NEW_TOKEN" https://api.github.com/user`
7. Update any scripts that reference the old token

## 3. OPSEC markers for repos

For repos touching credentials, network access, or operator data, add:
- `CONFIDENTIAL.md` at the repo root with provenance + usage rules
- GitHub topic: `confidential` or `client-private` or `ops` or `secrets`
- GitHub visibility: `private`
- Code-agent pattern: `code-agent/CONFIDENTIAL.md` is the model

## 4. Sazon-specific OPSEC

- **Customer data** (Saskia/La Vaquita Feliz): never export without operator OK
- **Family data** (Sonia, John, Gaby): separate repo, OPSEC-clean, `research-repos/saskia/`
- **Investor data** (Sonia, John): NOT in Sazon, in WPG systems
- **BWS-stored secrets:** all operator credentials (cf-token, fernet, db-url, user-password) live in BWS, not in env

## 5. Incident response

If a secret is leaked:
1. Rotate immediately (don't wait for the analysis to finish)
2. Notify the operator (Ivan)
3. Document the leak in this file under "Recent incidents"
4. Update the rotation schedule

## 6. Recent incidents

- **2026-10-12:** "hermes all access" PAT pasted in chat (operator-pasted, ~6 hours). Token was in memory only, not persisted. Operator should rotate.
```

**Verification:** File size ~2-3 KB, 50+ lines. `git diff --stat` should show +1 file.

**Effort:** 30 min

### 2.4 `saskia-app/scripts/README.md` (NEW, 1-2 hours)

**Pattern from:** Johns-Grimoire `cicd/scripts/README.md` (6.6 KB) — every script documented with purpose + common errors + AI-assisted fixes.

**Sections to include:**

```markdown
# scripts/ — utility scripts index

**Last updated:** 2026-10-12
**Pattern from:** Johns-Grimoire `cicd/scripts/README.md` — every script has purpose + common errors + AI-assisted fixes.

**70+ scripts** organized by category:

| Category | Scripts | Example |
|---|---|---|
| **Backup** | backup.py, backup_cron.py, sazon-backup.sh | VPS-side daily backup at 03:15 |
| **Deploy** | deploy.sh, promote.sh, release.sh | VPS deploy + promotion + release |
| **Migration** | add_timezone_import.py, add_utility_classes.py, add_workflow_permissions.py, apply_neon_schema.py, apply_v056_bank.py, migrate_inline_styles.py, migrate_inline_stylesheets.py, reclassify_sale_channels.py, pin_workflow_actions.py, refresh_action_pins.py | Schema + style migrations |
| **BWS (Bitwarden Secrets)** | bws_list_names.py, install_bws_token.sh, save_saskia_cf_token.py, save_saskia_fernet.py, save_sazon_db_url.py, save_sazon_user_password.py | Operator secret storage |
| **Smoke tests** | smoke_cocina_pages.py, smoke_test_deploy_shape.py, gen_route_smoke.py | Deploy-time smoke tests |
| **Audit / quality** | audit_prune.py, check_complexity.py, check_currency_drift.sh, check_docs_quality.py, check_duplicate_code.py, check_duplicate_files.py, check_imports.py, check_md_links.py, check_no_secrets.py, check_warnings.py, check_bank_schema.py, check_active_todos.py | Repo quality |
| **Screenshots** | capture_screenshots.py, shoot_all_pages.py | User-guide screenshots |
| **Cloudflare** | cf_tunnel_liveness.py, save_saskia_cf_token.py | Tunnel health |
| **DORA** | dora_snapshot.py | Engineering metrics |
| **Lint** | lint_tier1.py, fix_e702.py, fix_perf401.py | CI lint + autofix |
| **Seed** | seed_full_recipe_data.py, seed_packs_gen.py, seed_vaquita_holandesa_for_saskia.py, inventory_seed_helpers.py | Seeder |
| **Vendor** | vendor_vale_styles.sh | Third-party styles |
| **Misc** | daily_summary.py, monitor_login.py, uptimerobot_setup.py, ci_alert.py, print_deploy_state.py, probe_app_introspection.py, mark_e2e_tests.py, tag_tests_with_markers.py, generate_safeguard_baseline.py, docs_prose.sh, minify_css.py, import_herebus_data.py, reset_operator_credentials.py, verify_catalog_on_vps.py, install-pre-commit.sh | Various |

## First-time setup sequence

```bash
# 1. Install BWS token
bash scripts/install_bws_token.sh

# 2. Save operator secrets
python scripts/save_sazon_db_url.py
python scripts/save_sazon_user_password.py
python scripts/save_saskia_cf_token.py
python scripts/save_saskia_fernet.py

# 3. Run database migrations
python -m app.rms.db migrate

# 4. Seed demo data
python scripts/seed_full_recipe_data.py

# 5. Start the app
make serve   # binds to 127.0.0.1:8765
```

## Deploy sequence

```bash
# 1. Test locally
make check   # ruff + tests
make test-coverage

# 2. Deploy to test
bash scripts/deploy.sh test
# wait for smoke tests
python scripts/smoke_test_deploy_shape.py --env=test

# 3. Promote test to prod
bash scripts/promote.sh

# 4. Verify prod
python scripts/smoke_test_deploy_shape.py --env=prod
```

## Common errors + AI-assisted fixes

(For each script, document the most common error + a one-line fix. Pattern from Johns-Grimoire.)
```

**Verification:** File size ~3-5 KB, 80+ lines. `git diff --stat` should show +1 file.

**Effort:** 1-2 hours

---

## 3. P0 — 4 doc conflict resolutions (1 hour)

### 3.1 Worktree policy conflict (15 min)

**Files affected:** `.hermes/SIBLING-COORDINATION-NOTE.md` + `docs/operations/worktree-policy.md`

**The conflict:**
- `docs/operations/worktree-policy.md` says: scratch = main + deploys, production = feature dev
- `.hermes/SIBLING-COORDINATION-NOTE.md` says: saskia-app = canonical worktree (current session)

**The actual state:** 3 active worktrees (this, abstraction-gates, vaquita) + 1 DO NOT TOUCH.

**Resolution:**
1. Update `.hermes/SIBLING-COORDINATION-NOTE.md` to reference `docs/operations/worktree-policy.md` as canonical
2. List the 3 actual worktrees explicitly
3. Add a "If worktree-policy.md and SIBLING-COORDINATION-NOTE.md disagree, worktree-policy.md wins" note

**Verification:** Both files cross-reference each other; the 3 worktrees are listed in both.

### 3.2 Coverage standard conflict (10 min)

**Files affected:** `saskia-app/AGENTS.md` Rule 30 + `CONTRIBUTING.md` + `wizard-academy/wisdom/technical-standards.md` (already cached)

**The conflict:**
- wizard-academy: 95% line + 85% branch (AIW standard)
- CONTRIBUTING.md: 80%+ (Sazon target)
- AGENTS.md Rule 30: 40% (Sazon current)

**Resolution:**
1. In saskia-app/AGENTS.md Rule 30, add a 3-line clarification:
   - "AIW standard: 95% line + 85% branch (per wizard-academy/wisdom/technical-standards.md)"
   - "Sazon target: 80% (per CONTRIBUTING.md)"
   - "Sazon current: 40% (gap to close)"
2. Add a "Path to 80%" sub-section with the sprint-by-sprint plan
3. Reference the AIW source doc

**Verification:** AGENTS.md Rule 30 mentions all 3 numbers and the AIW source.

### 3.3 Deployment mode conflict (15 min)

**Files affected:** `app/docs/architecture.md` + saskia-app/AGENTS.md deployment section

**The conflict:**
- `app/docs/architecture.md`: local-first only (single PC, single user)
- saskia-app/AGENTS.md: local-first + hosted (since 2026-09-24)
- 3 envs (prod, test, dev) added 2026-10-09

**Resolution:**
1. Update `app/docs/architecture.md` to add a "Deploy topology" section:
   - 3 envs (prod, test, dev)
   - Each env: VPS, Docker Swarm stack, Traefik label, DNS (sazon-vps.paragu-ai.com, sazon-test.paragu-ai.com, sazon-dev.paragu-ai.com)
   - Local-first still supported for solo dev
2. Update saskia-app/AGENTS.md deployment section to reference architecture.md

**Verification:** `app/docs/architecture.md` mentions all 3 envs.

### 3.4 Persona boundary clarification (5 min)

**Files affected:** `app/rms/AGENTS.md` (Kiki persona)

**The clarification:**
- Kiki is the Sazon-specific AI persona
- Aethelred/Merlin/Nyx are wizard-academy personas
- No conflict, but worth being explicit

**Resolution:**
1. Add a 1-line note to saskia-app/AGENTS.md Personas section: "Kiki (Sazon) is distinct from Aethelred/Merlin/Nyx (wizard-academy). Don't conflate."

**Verification:** Search for "Kiki" + "Aethelred" in saskia-app/AGENTS.md — both should appear with the distinction.

---

## 4. P0 — 4 NEW AGENTS.md rules (30 min)

These are the 6 NEW rules from this turn (46-51) to add to saskia-app/AGENTS.md. Each is one paragraph.

### Rule 46: Read .hermes/ orientation before code (5 min)

Add to saskia-app/AGENTS.md as a new "On starting" section at the top:

```markdown
## On starting (before any code change)

1. Read `.hermes/HERMES-ORIENTATION.md` (3.8 KB) — the 5-step probe sequence
2. Read `.hermes/KNOWN-BYPASSES.md` (6.6 KB) — the current bypass sites (saves 10-15 min per session)
3. Read `.hermes/SIBLING-COORDINATION-NOTE.md` (4.9 KB) — the parallel-session protocol
4. Read `.hermes/STATE.md` (3-5 KB, after §2.2) — the live state + the 4 sibling repos

**This is the 'orient first' rule.** Skipping this is a recipe for duplicating work or stepping on a sibling session.
```

### Rule 47: CHANGELOG.md is CI-required (5 min)

Add to saskia-app/AGENTS.md Hard rules:

```markdown
**Hard rule (CI-enforced):** All PRs touching `app/`, `scripts/`, `tests/`, or `.github/` MUST also touch `app/CHANGELOG.md`. CI rejects PRs without the CHANGELOG.md update. This is a hard rule from CONTRIBUTING.md, enforced at the CI gate level.
```

### Rule 48: 3 environments (5 min)

Add to saskia-app/AGENTS.md deployment section:

```markdown
**3 environments (since 2026-10-09):** prod, test, dev. Each has its own VPS Docker Swarm stack + Traefik label + DNS. Live URLs: sazon-vps.paragu-ai.com (prod), sazon-test.paragu-ai.com (test), sazon-dev.paragu-ai.com (dev). Each env has its own DB instance. Per-client instances (SASKIA-210).
```

### Rule 49: Kiki vs Aethelred/Merlin/Nyx (5 min)

Add to saskia-app/AGENTS.md Personas section:

```markdown
**Persona boundaries:** Kiki (Sazon) is distinct from Aethelred, Merlin 3.0, Nyx 3.0 (wizard-academy). Kiki lives in `app/rms/AGENTS.md`. The wizard-academy personas live in `wizard-academy/configurations/aethelred_identity.json` (and similar). Don't conflate.
```

### Rule 50: Preserve "no Ometz" rule (5 min)

Verify this is in saskia-app/AGENTS.md Personas section. If not, add:

```markdown
**No Ometz in this repo.** Gaby is a different client (Ometz Dental). Do not import, reference, or mention her. Do not copy patterns from `ometz-image-research` (or other Ometz repos) into this one without explicit Iván OK.
```

### Rule 51: Sazon-specific rules vs AIW org standards (5 min)

Add to saskia-app/AGENTS.md top:

```markdown
**Sazon-specific vs AIW org standards:** The hard rules in this file are Sazon-specific (money in Gs., Asunción timezone, Spanish voseo, single-tenant). AIW org standards are in `wizard-academy/wisdom/technical-standards.md` (95/85, zero-warning) and `Johns-Grimoire/.cursor/rules/quality/` (prevention-over-remediation). When in doubt, the AIW standard wins; Sazon may be a deliberate compromise.
```

**Total effort for §4:** 30 min

---

## 5. P0 — TOTAL effort (3-4 + 3-4 + 1 + 0.5 = 7.5-9.5 hours)

Sum of P0:
- §1 (saskia-app/AGENTS.md rewrite): 3-4 hours
- §2 (4 NEW files): 3-4 hours
- §3 (4 doc conflicts): 1 hour
- §4 (6 NEW rules): 0.5 hour
- V1-V4 (verification gate): 0.5 hour

**Total P0: 8-10 hours** of focused work, deliverable as SASKIA-211e.

---

## 6. P1 — 4 sibling repos' fixes (4-6 hours)

### 6.1 wizard-academy/AGENTS.md (NEW, 15 min)

**Pattern:** A knowledge base, not a code repo.

```markdown
# AGENTS.md — wizard-academy (AIW knowledge base)

## What this is

This is a **knowledge base**, not a code project. It contains:
- 4 wisdom pillars (star-machine, exponential-vs-linear, diamond-patience, narrative-architecture)
- 16 "spells" (techniques)
- 8-week foundation course
- 3 wizard personas (Aethelred, Merlin 3.0, Nyx 3.0)
- 19 audio recordings + 19 transcripts (raw + organized by theme)
- OpenCLAW agent configuration files

## What agents should do

- **READ** the wisdom files (`wisdom/*.md`) for AIW strategic philosophy
- **REFERENCE** the 95/85 + zero-warning standard from `wisdom/technical-standards.md`
- **DO NOT** treat the 6.4 KB of Python as a code project — those are config-validation scripts for OpenCLAW

## What agents should NOT do

- Do NOT add new code without explicit operator instruction
- Do NOT modify the wizard personas without operator OK
- Do NOT add CI/CD pipelines — this is a knowledge base

## Related

- The 3 wizard personas (Aethelred, Merlin 3.0, Nyx 3.0) are NOT the same as Kiki (Sazon)
- The 95/85 coverage standard is the AIW-wide engineering standard; Sazon's 40% is a deliberate compromise
```

**Verification:** File ~1-2 KB, 30+ lines.

### 6.2 code-agent/AGENTS.md (NEW, 30 min)

**Pattern:** Active AIW Code Agent, not study material.

```markdown
# AGENTS.md — code-agent (AIW Code Agent)

## What this is

This is the **AIW Code Agent** in pilot phase. It is **NOT** study material (despite the README's "Status: Study/adaptation phase" line — that line is wrong).

**Two branches:**
- `upstream-main` / `upstream-develop` — Eneve baseline (read-only, do NOT push)
- `aiw/main` (this branch) — AIW adaptation

## Pilot clients (active)

1. **Vete** (`Ai-Whisperers/Vete`) — multi-tenant SaaS vet clinic, Next.js 15 + Supabase + Drizzle, 2 live beta clients (Terrapet + CavillPet)
2. **Solstein** (`Ai-Whisperers/solstein`) — PE/VC intel, Python 3.10+ + FastAPI + SQLAlchemy + pgvector + LangGraph + Celery

**Per-client profile docs:** `docs/clients/{vete,solstein}.md`

## Stack swap (AIW vs Eneve)

| Eneve | AIW |
|---|---|
| Bitbucket | GitHub (39 of 39 active repos) |
| JIRA | Linear + GitHub Issues |
| Confluence | Markdown + Notion |
| Microsoft Teams | Telegram via Hermes gateway (40+ repos) |
| Aikido | GitHub code scanning + Dependabot |
| Keycloak | Supabase Auth (41 of 59 repos) |
| Anthropic-only | LiteLLM gateway (OpenRouter + Anthropic + Groq + Cerebras) |
| AWS Bedrock embeddings | Voyage + OpenAI + Ollama local |
| Java 21 + Quarkus | Python + TypeScript (Java kept for study) |

## Deploy

- VPS: `72.61.44.159` (Servarica)
- Deploy: Docker Swarm + Traefik + Cloudflare DNS-01
- Token rotation: `aiw-refresh-github-token.timer` (systemd)

## What agents should do

- READ `docs/AIW-CUSTOMIZATION-PLAN.md` for the AIW delta plan
- READ `docs/STUDY-NOTES.md` for the 7 backend patterns + 6 frontend patterns worth stealing
- READ `docs/OPERATIONS.md` for day-to-day commands
- READ `docs/clients/{vete,solstein}.md` for the per-client profile pattern

## What agents should NOT do

- Do NOT push to `upstream-main` or `upstream-develop` (Eneve baseline, read-only)
- Do NOT make the repo public (CONFIDENTIAL, internal study only)
- Do NOT redistribute, resell, or production-deploy under the AIW brand without re-implementation

## Related

- 8 open issues track the AIW customizations in flight
- AIW-wide standards apply (95/85, zero-warning, OPSEC, tenancy)
```

**Verification:** File ~2-3 KB, 50+ lines.

### 6.3 code-agent-ui/AGENTS.md (NEW, 15 min)

```markdown
# AGENTS.md — code-agent-ui (UI for the AIW Code Agent)

## What this is

UI for the AIW Code Agent. The backend (code-agent) is in pilot phase with 2 clients; this UI is the frontend.

**Stack:** React 19.2 + Vite + TanStack Router/Query/Store + TipTap + Zod + Tailwind 4 + Vitest

**Note:** The current README is a copy-paste of the backend's README. This AGENTS.md replaces that.

## State

- UI: 1 month old, actively iterated
- Backend: 5 months old, frozen at 2026-05-25 Eneve baseline
- Keycloak → Supabase Auth swap: NOT done (frontend still imports Keycloak-JS)

## What agents should do

- READ the UI's actual content in `src/` and `public/`
- FOLLOW the React + Vite conventions
- TEST with Vitest

## What agents should NOT do

- Do NOT use the misleading README's "study material" framing
- Do NOT add features that depend on a backend that isn't deployed at scale

## Related

- See `code-agent/AGENTS.md` for the backend context
- 7 backend patterns + 6 frontend patterns documented in `code-agent/docs/STUDY-NOTES.md`
```

**Verification:** File ~1-2 KB, 30+ lines.

### 6.4 Johns-Grimoire/AGENTS.md (NEW, 30 min)

```markdown
# AGENTS.md — Johns-Grimoire (Eneve CI/CD + AI rules docs)

## What this is (and isn't)

**This is NOT a Python template repo.** Despite the README's claim to be the "standard starter template for all Ai-Whisperers Python projects," the actual content is:
- Eneve's CI/CD documentation (eneva.domain / eneve.ebase.foundation / eneve.ebase.datamigrator)
- Eneve's AI rules + prompts framework (`.cursor/`)
- Eneve's Azure DevOps pipeline scripts (PowerShell)

**Codename:** "John's Grimoire" is the AIW internal name for this Eneve content. The "occult/magic" framing is in-joke, not a real category.

**The 1.4 MB of "PowerShell"** is Eneve's Azure DevOps pipeline scripts, not a real PowerShell product.

## What agents should do

- READ `.cursor/rules/quality/README.md` for the Eneve quality philosophy (prevention-over-remediation, zero warnings, zero errors)
- READ `.cursor/rules/rule-authoring/README.md` (10 KB) for the 8-step rule-authoring framework
- READ `.cursor/rules/database-standards/README.md` for the MSSQL standards (with Oracle phase-out guidelines)
- READ `.cursor/README.md` (22 KB) for the full system overview

## What agents should NOT do

- Do NOT "improve" the Eneve content without explicit operator instruction
- Do NOT add new "AIW Python template" content here — this is not a template
- Do NOT treat the `ruff.toml` / `.flake8` / `cspell.json` as the AIW standard — those are from a different context

## Related

- The 5 `.cursor/rules/` files are the canonical rule-authoring framework
- The 15+ `.cursor/prompts/` files are the canonical agent-prompt templates
- The 5 `.cursor/commands/` files (activate-ticket, check-status, commit, create-docs, create-pr, pursue-ticket) are the canonical agent commands
```

**Verification:** File ~1-2 KB, 40+ lines.

### 6.5 Fix 3 misleading descriptions (15 min)

**GitHub descriptions to update:**

- **code-agent:** Currently says "Confluence Document" or similar (per the discovery audit). Should say: "AIW Code Agent — AI-powered issue fixing, dependency upgrades, code reviews, test generation. Adapted from Eneve. 2 pilot clients (Vete + Solstein)."
- **code-agent-ui:** Currently same as code-agent. Should say: "AIW Code Agent UI — React 19 + Vite + TanStack. Frontend for the AIW Code Agent."
- **Johns-Grimoire:** Currently says "John's Grimoire — occult/magic reference tool." Should say: "Eneve CI/CD + AI rules documentation (codename John's Grimoire)."

**Verification:** GitHub UI shows the new descriptions.

### 6.6 Add 4 new AGENTS.md cross-references in saskia-app/AGENTS.md (15 min)

Add to the Sister-repos section:

```markdown
## Sister repos

| Repo | AGENTS.md | Purpose | Status |
|---|---|---|---|
| `Ai-Whisperers/wizard-academy` | [wizard-academy/AGENTS.md](https://github.com/Ai-Whisperers/wizard-academy/blob/main/AGENTS.md) | AIW knowledge base | Active, knowledge |
| `Ai-Whisperers/code-agent` | [code-agent/AGENTS.md](https://github.com/Ai-Whisperers/code-agent/blob/aiw/main/AGENTS.md) | AIW Code Agent in pilot | Pilot, 2 clients |
| `Ai-Whisperers/code-agent-ui` | [code-agent-ui/AGENTS.md](https://github.com/Ai-Whisperers/code-agent-ui/blob/aiw/main/AGENTS.md) | UI for code-agent | Active, UI-only |
| `Ai-Whisperers/Johns-Grimoire` | [Johns-Grimoire/AGENTS.md](https://github.com/Ai-Whisperers/Johns-Grimoire/blob/main/AGENTS.md) | Eneve CI/CD + AI rules | Reference |
```

**Total effort for §6:** 4-6 hours

---

## 7. P1 — 6 more NEW files in saskia-app/ (4-6 hours)

### 7.1 `saskia-app/docs/README.md` (REWRITE, 1-2 hours)

Current 2 KB file is minimal. Rewrite to be a 2-3 KB index of the 17 docs/ subdirectories.

```markdown
# docs/ — saskia-app documentation

**17 subdirectories, 280+ MD files.** This README is the entry point.

| Subdir | Purpose | Files | Key docs |
|---|---|---|---|
| `adr/` | Architecture Decision Records | 1 | ADR-001-test-architecture |
| `analysis/` | Major analyses | 10 | sazon_decision_book_v3, sazon_lessons_book (50 KB) |
| `archive/` | Archived plans | 7 | FRONTEND_AUDIT_2026-09-22 (64 KB) |
| `backlog/` | Current backlog | 3 | 3 active tickets |
| `ci/` | CI documentation | 3 | dependabot, sharded-test-design, toolchain-versions |
| `competitors/` | Competitor audits | 1 | 3-competitor visual audit |
| `decisions/` | Roadmap alignment | 1 | canonical-roadmap-alignment |
| `intake/` | SASKIA-### intake tickets | 16 | 16 tickets, some shipped, some open |
| `operations/` | Day-to-day runbooks | 50+ | backup-cron, healthz, worktree, dashboard, dora |
| `plans/` | Plans (current + redesign) | 25+ | SASKIA-209, SASKIA-210 one-pagers |
| `qa/` | QA plans | 1 | round1-qa-plan (31 KB) |
| `reports/` | Redesign reports | 19 | 19 files, biggest is design-plans-2026-09-27 (630 KB) |
| `roadmap/` | Roadmap + audits + historical | 50+ | STATUS, BACKLOG, EXECUTION-PLAN |
| `security/` | Security baseline | 1 | safeguard-baseline.json |
| `superpowers/specs/` | Design specs | 1 | produccion-v3-design |
| `upgrades/` | UX upgrade plan | 1 | UX-UPGRADE-PLAN (45 KB) |
| `user-guide/` | Spanish user guide | 21 + 30 screenshots | 21 guides + 30 PNGs + 6 MB tarball |
| `ux/` | UX inventory | 7 | copy-fix-list (70 KB), 5 inventory files |
| `wishlist/` | Wishlist (raw + triaged + rejected) | 24 | 1 raw, 22 triaged, 5 rejected |

## When to use which subdir

- **Need to ship a feature?** → `intake/SASKIA-NNN-*.md` (16 self-contained tickets)
- **Need to debug a prod issue?** → `operations/` (50+ runbooks)
- **Need to know "what's the live state?"** → `roadmap/STATUS.md` (9.5 KB)
- **Need to know "what's the backlog?"** → `roadmap/BACKLOG.md` (16.7 KB)
- **Need to know "what to do next?"** → `roadmap/EXECUTION-PLAN.md` (18.9 KB) or `../WHAT_NEXT.md`
- **Need a UX/copy decision?** → `ux/` (7 files)
- **Need a competitive comparison?** → `competitors/`
- **Need a security baseline?** → `security/`
```

**Verification:** File 2-3 KB, 30+ lines.

### 7.2 `saskia-app/docs/operations/INDEX.md` (NEW, 1-2 hours)

Index of the 50+ runbooks with a decision tree.

```markdown
# docs/operations/ — runbook index

**50+ runbooks.** This INDEX is the entry point.

## By category

| Category | Runbooks |
|---|---|
| **Day-to-day** | backup-cron.md, healthz-db-runbook.md, worktree-policy.md |
| **Production incident** | PRODUCTION_500_RUNBOOK.md, 2026-10-09-incident-prod-deps-503.md |
| **CI/CD** | 2026-10-09-branch-protection.md, 2026-10-09-ci-recovery.md, 2026-10-10-clean-main-test-audit.md |
| **Deploy** | 2026-10-09-three-env-deploy.md, 2026-10-05-produccion-v2-deploy-runbook.md |
| **Test infra** | 2026-10-04-*, 2026-10-05-ci-tuning.md |
| **Session artifacts** | 2026-10-10-session-handoff.md, 2026-10-10-turn-end-handoff.md |
| **Tooling** | 2026-10-09-tooling-*, 2026-10-08-tooling-hardening.md |
| **DORA** | 2026-10-04-dora-*.md, dora-snapshots/ |
| **Dashboard** | dashboard/STATUS.html.tmpl, dashboard/refresh.sh |
| **Cheat sheets** | loyalty-pos-cheatsheet.md |

## Decision tree

- **500 errors in prod?** → PRODUCTION_500_RUNBOOK.md
- **Backup failing?** → backup-cron.md
- **DB healthz failing?** → healthz-db-runbook.md
- **Worktree confusion?** → worktree-policy.md (canonical) + .hermes/SIBLING-COORDINATION-NOTE.md
- **CI red on main?** → 2026-10-10-clean-main-test-audit.md + 2026-10-09-ci-recovery.md
- **Deploy failing?** → 2026-10-09-three-env-deploy.md
- **Test infra issues?** → 2026-10-04-test-*.md
- **Loyalty POS questions?** → loyalty-pos-cheatsheet.md

## Archive policy

Runbooks older than 30 days that are no longer relevant should be moved to `archive/`. The current 2026-10-* runbooks are still active.
```

**Verification:** File 2-3 KB, 40+ lines.

### 7.3 `saskia-app/docs/intake/INDEX.md` (NEW, 30 min)

```markdown
# docs/intake/ — SASKIA-### tickets

**16 tickets, mix of shipped + open.** Each ticket is a self-contained "ship this" doc.

| Ticket | Title | Status |
|---|---|---|
| SASKIA-201 | visual-revolution-phase0 | shipped |
| SASKIA-202 | back-to-top-button | shipped |
| SASKIA-203 | format-utility-js | shipped |
| SASKIA-203 | shopping-list-affordance | shipped |
| SASKIA-204 | ruff-cleanup | shipped |
| SASKIA-204 | sale-channel-mismatch | shipped |
| SASKIA-301 | copy-globals | shipped |
| SASKIA-311 | main-ci-red | shipped |
| SASKIA-312 | wave2b-reading-state | shipped |
| SASKIA-313 | wave2c-input-perf | shipped |
| SASKIA-314 | wave2d-ux-safety | shipped |
| SASKIA-317 | parallel-suite-fd-exhaustion | shipped |
| SASKIA-317 | test-isolation-full-suite | shipped |
| SASKIA-320 | host-path-tests | shipped |
```

**Verification:** File 1 KB, 30+ lines.

### 7.4 `saskia-app/app/rms/migrations/INDEX.md` (NEW, 1-2 hours)

**Pattern:** Indexed by migration number + 1-line description.

```markdown
# app/rms/migrations/ — migration index

**117 migrations (schema v117).** Each migration is a forward-only step; rollback is via `sazon rollback` (SASKIA-209).

## Recent migrations (113-117)

- **113** — Sprint 2.1 settings_kv (KV-wins, empty-skip, non-settings rows untouched)
- **114** — Sprint 2.1 follow-up (settings.py + settings_original.py deleted)
- **115** — Allergen tags (per 2026-10-09 STATUS)
- **116** — Dietary tags + EOD alert templates
- **117** — Ingredient image_url

## Migration authoring guide

**Pre-conditions:**
1. Schema version bumped in `app/rms/config.py:CURRENT_SCHEMA_VERSION`
2. Backward-compatible: old code can read new DB

**Idempotency check:**
- Every migration must be safe to re-run (e.g., `IF NOT EXISTS` for DDL)

**Post-migration verification:**
- `sazon migrate --check` confirms schema is at expected version
- `sazon healthz --db` confirms DB integrity
- `sazon rollback --dry-run --to N-1` confirms rollback is possible

**Reference:** SASKIA-209 one-pager (`docs/plans/SASKIA-209-migration-rollback-onepager.md`)
```

**Verification:** File 2-3 KB, 30+ lines.

### 7.5 `saskia-app/app/rms/migrations/AUTHORING.md` (NEW, 1-2 hours)

```markdown
# Migration authoring guide

## When to write a new migration

You need a new migration when:
- Adding a new table or column
- Changing a column type (with backfill)
- Adding an index
- Adding a constraint
- Changing seed data

You do NOT need a migration when:
- Changing Python code (no schema change)
- Changing templates (no schema change)
- Changing scripts/ (no schema change)

## The 6-step process

1. **Create the migration file** in `app/rms/migrations/` with a descriptive name
2. **Implement up + down** (down is for `sazon rollback`)
3. **Add idempotency check** (e.g., `IF NOT EXISTS`)
4. **Bump CURRENT_SCHEMA_VERSION** in `app/rms/config.py`
5. **Test locally** with `sazon migrate` then `sazon rollback --to N-1` then `sazon migrate`
6. **Add to INDEX.md** with 1-line description

## Common pitfalls

- Forgetting to bump CURRENT_SCHEMA_VERSION → migration won't apply
- Forgetting `IF NOT EXISTS` → second run crashes
- Adding a non-idempotent backfill (e.g., `UPDATE`) → second run double-applies
- Forgetting to add the new column to the model → ORM queries crash
- Adding a new index without `CONCURRENTLY` → blocks the table on Postgres

## See also

- `docs/plans/SASKIA-209-migration-rollback-onepager.md`
- `.hermes/KNOWN-BYPASSES.md` (bypass sites to avoid)
```

**Verification:** File 2-3 KB, 30+ lines.

### 7.6 `saskia-app/app/rms/subpackage-AGENTS.md` template (NEW, 30 min)

```markdown
# AGENTS.md — `app/rms/<subpackage>/` engineering conventions

> Template for subpackage-level AGENTS.md files. Copy and adapt.

## What this subpackage does

<1-2 sentence description>

## Money rules (inherits from app/rms/AGENTS.md)

- Same `Decimal` + `to_int_gs()` rules apply
- Subpackage-specific notes here

## Unit rules (inherits from app/rms/AGENTS.md)

- Same `Unit.coerce()` rules apply

## Time rules (inherits from app/rms/AGENTS.md)

- Same `ASUNCION_TZ` rules apply

## Subpackage-specific rules

<Add 5-10 rules specific to this subpackage>

## Cross-references

- `app/rms/AGENTS.md` — parent RMS-domain rules
- `app/docs/architecture.md` — data flow + sources of truth
- `app/docs/threat-model.md` — what we defend against
```

**Verification:** File 1-2 KB, 30+ lines.

**Total effort for §7:** 4-6 hours

---

## 8. P1 — 23 cross-references in saskia-app/AGENTS.md (1-2 hours)

The 23 cross-references are listed in additional-areas doc §1.5. They go in saskia-app/AGENTS.md as inline links. Each reference is a single line in the relevant section.

**Distribution:**
- **3 in Personas section** — link to app/rms/AGENTS.md, wizard-academy/AGENTS.md, the "no Gaby" rule
- **5 in Hard rules section** — link to CONTRIBUTING.md, app/docs/architecture.md, app/docs/threat-model.md, app/docs/upgrade-tiers.md, the 3 envs runbook
- **3 in Anti-rules section** — link to the existing anti-rules references
- **5 in Tech stack section** — link to FastAPI, SQLAlchemy 2.0, Jinja2+HTMX, ruff, the test architecture
- **5 in Decision framework section** — link to the 4 sibling repos' AGENTS.md, the 95/85 standard, the OPSEC markers
- **2 in Troubleshooting section** — link to PRODUCTION_500_RUNBOOK.md, healthz-db-runbook.md

**Verification:** Search for each of the 23 docs in saskia-app/AGENTS.md.

**Effort:** 1-2 hours

---

## 9. P1 — TOTAL effort (4-6 + 4-6 + 1-2 = 9-14 hours)

Sum of P1:
- §6 (4 sibling repos' fixes): 4-6 hours
- §7 (6 more NEW files): 4-6 hours
- §8 (23 cross-references): 1-2 hours

**Total P1: 9-14 hours**

---

## 10. P2 — .hermes/ restructure + 4 research directions (15-20 hours)

### 10.1 .hermes/ restructure (2-4 hours)

Move files to the proposed hierarchical structure (per additional-areas doc §7.2):
- `orientation/`: HERMES-ORIENTATION.md, KNOWN-BYPASSES.md, SIBLING-COORDINATION-NOTE.md, STATE.md (NEW)
- `analysis/`: 7 research docs from 2026-10-12
- `rules/`: AGENTS.md (moved from root)
- `security/`: SECURITY.md (NEW)
- `plans/`: existing 15 plans
- `drafts/`: AGENTS.md-rewrite-draft.md

**Verification:** `ls -la .hermes/` shows the hierarchical structure; existing references still resolve.

**Effort:** 2-4 hours (mostly mechanical moves + reference updates)

### 10.2 Read 3 uncovered AIW repos (4-8 hours)

- **aiw-org** (116 agents, 79 crons) — the agent registry
- **Mburucuyá-PotyPy** — the AIW-defining product
- **The real AIW template** (NOT Johns-Grimoire) — likely aiw-template or base or repo-template

For each, write a 1-page summary doc in `.hermes/STATE.md` (or a new file) describing what it is + how it relates to saskia-app.

**Verification:** 3 new summary docs in `.hermes/`.

**Effort:** 4-8 hours

### 10.3 Read 79 AIW crons (4-8 hours)

- Read the 79 cron definitions in aiw-org
- Identify which crons Sazon's ops (deploy, backup, EOD) replicate
- Identify any Sazon-specific ops that should be promoted to AIW-wide

**Verification:** A `.hermes/STATE.md` update with the AIW cron summary.

**Effort:** 4-8 hours

### 10.4 Read Johns-Grimoire rule-authoring framework (1-2 hours)

- Read `.cursor/rules/rule-authoring/README.md` (10 KB) in full (already cached)
- Apply the 8-step rule-authoring framework to the saskia-app/AGENTS.md rewrite
- Document the application in `.hermes/2026-10-12-rule-authoring-application.md`

**Verification:** New doc in `.hermes/`.

**Effort:** 1-2 hours

### 10.5 P2 — TOTAL effort (15-20 hours)

---

## 11. Total scope (P0 + P1 + P2)

| Phase | Effort | Deliverable |
|---|---|---|
| P0 | 8-10 hours | saskia-app/AGENTS.md rewrite + 4 NEW files + 4 doc conflicts + 6 NEW rules |
| P1 | 9-14 hours | 4 sibling repos' fixes + 6 more NEW files + 23 cross-references |
| P2 | 15-20 hours | .hermes/ restructure + 3 AIW repos + 79 crons + rule-authoring framework |
| **Total** | **32-44 hours** | **~113 items, 16 NEW files, 4 sibling AGENTS.md, 4 doc conflicts resolved, 51 AGENTS.md rules** |

**Realistic estimate: 35-50 hours if we count unexpected issues + verification.**

---

## 12. Order of operations (the dependency graph)

The 113 items have dependencies. Here's the recommended order:

### Phase 1: P0 verification (30 min) — blocks all other work

- V1: Verify 47 items against current AGENTS.md (30 min)

### Phase 2: P0 saskia-app/AGENTS.md rewrite (3-4 hours) — depends on Phase 1

- Apply the EXIST/PARTIAL/MISSING results to the rewrite draft
- Add the 6 NEW rules (46-51)
- Add the Sister-repos section
- Add the AIW context section
- Add the 23 cross-references
- Resolve the 4 doc conflicts inline
- Verify

### Phase 3: P0 4 NEW files in saskia-app/ (3-4 hours) — depends on Phase 2

- docs/clients/saskia.md
- .hermes/STATE.md
- .hermes/SECURITY.md
- scripts/README.md

### Phase 4: P0 4 doc conflicts (1 hour) — depends on Phase 2

- Worktree policy conflict
- Coverage standard conflict
- Deployment mode conflict
- Persona boundary clarification

### Phase 5: P0 6 NEW rules (30 min) — depends on Phase 2

- Rules 46-51 in saskia-app/AGENTS.md

### Phase 6: P1 4 sibling repos (4-6 hours) — independent of P0

- wizard-academy/AGENTS.md
- code-agent/AGENTS.md
- code-agent-ui/AGENTS.md
- Johns-Grimoire/AGENTS.md
- Fix 3 misleading GitHub descriptions
- Add 4 cross-references in saskia-app/AGENTS.md Sister-repos section

### Phase 7: P1 6 more NEW files (4-6 hours) — independent of P0

- docs/README.md (rewrite)
- docs/operations/INDEX.md
- docs/intake/INDEX.md
- app/rms/migrations/INDEX.md
- app/rms/migrations/AUTHORING.md
- app/rms/subpackage-AGENTS.md template

### Phase 8: P1 23 cross-references (1-2 hours) — depends on Phases 2 + 7

- Add 23 inline links in saskia-app/AGENTS.md

### Phase 9: P2 .hermes/ restructure (2-4 hours) — independent

- Move files to hierarchical structure
- Update references

### Phase 10: P2 3 AIW repos (4-8 hours) — independent

- Read aiw-org, Mburucuyá-PotyPy, real AIW template
- Write 3 summary docs

### Phase 11: P2 79 crons (4-8 hours) — depends on Phase 10

- Read cron definitions
- Identify Sazon vs AIW-wide ops

### Phase 12: P2 rule-authoring framework (1-2 hours) — independent

- Read Johns-Grimoire rule-authoring
- Apply to saskia-app/AGENTS.md
- Document the application

**Critical path: V1 → Phase 2 (saskia-app/AGENTS.md) → Phase 3 (4 NEW files) → Phase 8 (23 cross-references). This is the 8-10 hour P0 path. Phases 6, 7, 9, 10, 11, 12 can run in parallel with the critical path.**

---

## 13. Verification gates (per phase)

Each phase has explicit verification steps. The operator should check these before moving to the next phase.

### After Phase 1 (V1):
- [ ] 47 items classified as EXIST/PARTIAL/MISSING
- [ ] Rewrite draft updated to reflect the V1 result

### After Phase 2 (saskia-app/AGENTS.md rewrite):
- [ ] File size ~32 KB (~500 lines)
- [ ] All 51 rules present
- [ ] Sister-repos section present
- [ ] AIW context section present
- [ ] 23 cross-references present
- [ ] 4 doc conflicts resolved inline
- [ ] `git diff --stat AGENTS.md` shows +4,000 bytes net

### After Phase 3 (4 NEW files):
- [ ] docs/clients/saskia.md exists, ~5-7 KB
- [ ] .hermes/STATE.md exists, ~6-8 KB
- [ ] .hermes/SECURITY.md exists, ~2-3 KB
- [ ] scripts/README.md exists, ~3-5 KB
- [ ] Each file has the 5 required sections

### After Phase 4 (4 doc conflicts):
- [ ] .hermes/SIBLING-COORDINATION-NOTE.md references docs/operations/worktree-policy.md
- [ ] saskia-app/AGENTS.md Rule 30 mentions all 3 coverage numbers
- [ ] app/docs/architecture.md mentions 3 envs
- [ ] saskia-app/AGENTS.md mentions Kiki ≠ Aethelred/Merlin/Nyx

### After Phase 5 (6 NEW rules):
- [ ] Rules 46-51 in saskia-app/AGENTS.md
- [ ] Each rule has evidence + rationale

### After Phase 6 (4 sibling repos):
- [ ] wizard-academy/AGENTS.md, code-agent/AGENTS.md, code-agent-ui/AGENTS.md, Johns-Grimoire/AGENTS.md exist
- [ ] 3 GitHub descriptions updated
- [ ] 4 cross-references in saskia-app/AGENTS.md Sister-repos section

### After Phase 7 (6 more NEW files):
- [ ] All 6 files exist
- [ ] Each file has the 5 required sections

### After Phase 8 (23 cross-references):
- [ ] 23 inline links in saskia-app/AGENTS.md
- [ ] Each link resolves (no broken refs)

### After Phase 9 (.hermes/ restructure):
- [ ] Hierarchical structure in place
- [ ] Existing references still resolve

### After Phase 10 (3 AIW repos):
- [ ] 3 summary docs in .hermes/

### After Phase 11 (79 crons):
- [ ] .hermes/STATE.md updated with AIW cron summary

### After Phase 12 (rule-authoring framework):
- [ ] .hermes/2026-10-12-rule-authoring-application.md exists
- [ ] saskia-app/AGENTS.md was authored per the framework

---

## 14. Rollback plan (if something goes wrong)

Each phase is independently reversible. The git history will show each commit, and `git revert <commit-hash>` will undo it.

**Critical:** Before starting Phase 2, commit the V1 verification result. Before starting Phase 3, commit the saskia-app/AGENTS.md rewrite. Each phase should be a separate commit (or set of commits) with clear messages.

**Commit message convention (per CONTRIBUTING.md):**
```
docs(agents-md): apply 6 NEW rules 46-51 per the 2026-10-12 update plan
docs(intake): add SASKIA-211e — the AGENTS.md rewrite
docs(clients): add saskia.md — the Sazon client profile
hermes(state): add STATE.md — the operator's running state
```

**Rollback if Phase 2 fails:**
- `git revert <commit-hash>` reverts the rewrite
- Current saskia-app/AGENTS.md is restored
- No data loss

**Rollback if Phase 6 fails (e.g., wizard-academy/AGENTS.md doesn't fit):**
- Each sibling repo is a separate repo, so rollback is per-repo
- `git revert <commit-hash>` in the sibling repo reverts the change

---

## 15. Operator decisions needed (before starting)

Before starting Phase 2, the operator should make these decisions:

### D1. Which of the 11 NEW rules (Rules 39-49) to add? (1 min)

The 11 NEW rules from prior turn are: 39 topic tags, 40 OPSEC, 41 language, 42 branch, 43 Sazon no-Telegram, 44 tenancy, 45 deploy, 38 no `-X ours`, 21 no prod DB, 22 no AI-edit AGENTS.md, 6 of 6 done, T1-T4.

**Recommendation:** Add all 11. They're evidence-based and add clarity.

### D2. Which of the 6 NEW rules (Rules 46-51) to add? (1 min)

46 read .hermes/ first, 47 CHANGELOG.md CI-required, 48 3 envs, 49 Kiki ≠ Aethelred, 50 preserve "no Ometz", 51 Sazon-specific vs AIW org.

**Recommendation:** Add all 6. They're evidence-based and add clarity.

### D3. How to resolve the worktree policy conflict? (1 min)

**Option A:** Make docs/operations/worktree-policy.md canonical, update SIBLING-COORDINATION-NOTE.md to reference it.
**Option B:** Make SIBLING-COORDINATION-NOTE.md canonical, update worktree-policy.md to reference it.
**Option C:** Merge them into a single worktree-policy.md in docs/operations/.

**Recommendation:** Option C. The single canonical doc eliminates the conflict.

### D4. How to resolve the coverage standard conflict? (1 min)

**Option A:** Add the 3-level clarification to saskia-app/AGENTS.md Rule 30.
**Option B:** Update CONTRIBUTING.md to match the AIW standard.
**Option C:** Update wizard-academy/technical-standards.md to acknowledge Sazon's compromise.

**Recommendation:** Option A. Sazon's 40% is a deliberate compromise, the AIW standard is the strategic target, the operator's 80% is the medium-term goal. All 3 are correct in context.

### D5. Which of the 4 NEW files in §2 to add first? (1 min)

**Option A:** Add all 4 in sequence.
**Option B:** Add only docs/clients/saskia.md + .hermes/STATE.md (the highest-value 2).
**Option C:** Defer all 4 to a separate ticket.

**Recommendation:** Option A. All 4 are P0 and add high value.

### D6. Which of the 4 sibling repos' fixes to do first? (1 min)

**Option A:** Fix all 4 in sequence.
**Option B:** Fix only code-agent + Johns-Grimoire (the 2 with the most misleading descriptions).
**Option C:** Defer all 4 to separate tickets per sibling repo.

**Recommendation:** Option B. code-agent and Johns-Grimoire have the worst description issues. code-agent-ui and wizard-academy can wait.

### D7. The 16 NEW files in §2 + §7: all at once or in batches? (1 min)

**Option A:** All 16 in this turn (8-12 hours).
**Option B:** 4 P0 in §2 first (3-4 hours), then 6 P1 in §7 (4-6 hours).
**Option C:** One at a time, with operator review between.

**Recommendation:** Option B. P0 first, then P1, with operator review between phases.

### D8. The .hermes/ restructure: now or later? (1 min)

**Option A:** Now (Phase 9 in §12).
**Option B:** After the P0 + P1 work is done.
**Option C:** Never (keep the flat structure).

**Recommendation:** Option B. The restructure is a P2; doing it after the main work avoids unnecessary churn.

---

## 16. The 1-paragraph final summary

The complete update plan for saskia-app + 4 sibling repos + .hermes/ + AIW org is: 113 items totaling 35-50 hours, broken into P0 (8-10h, saskia-app/AGENTS.md rewrite + 4 NEW files + 4 doc conflicts + 6 NEW rules), P1 (9-14h, 4 sibling repos' fixes + 6 more NEW files + 23 cross-references), and P2 (15-20h, .hermes/ restructure + 3 AIW repos + 79 crons + rule-authoring framework). The critical path is V1 → saskia-app/AGENTS.md rewrite → 4 NEW files → 23 cross-references (8-10h). Phases 6, 7, 9, 10, 11, 12 can run in parallel. Before starting, the operator should make 8 decisions (D1-D8) about which rules to add, how to resolve conflicts, and which sibling repos to fix first. The plan is reversible per-phase via git revert.
