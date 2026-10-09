# AGENTS.md — Sazón app repo (build instructions)

Read this BEFORE writing code in this repo.

---

## Personas (who is who)

- **Iván** — AIW founder, sole developer-operator of this codebase. Writes code, runs tests, ships releases, deploys to VPS. Reads this.
- **Saskia Weiss Vander** — the client. The owner of the bakery that uses Sazon. Does **not** read this. Uses the installed app.
- **AI agents (Kiki, this assistant, future agents)** — read this to understand the build brief and hard rules. Do not assume operator context from sazon-context unless explicitly told to look.

**Don't conflate the personas.** Iván is the developer; Saskia is the client. OPSEC questions go to Iván-as-developer. UX questions about what Saskia sees go to Iván-as-developer (Saskia does not review code or AGENTS.md).

**No Gaby in this repo.** Gaby is a different client (Ometz Dental). Do not import, reference, or mention her. Do not copy patterns from `ometz-image-research` (or other Ometz repos) into this one without explicit Iván OK.

**Saskia's full context lives in `research-repos/saskia/` (separate repo, OPSEC-clean).** Read it for what the operator wants; never read it to make changes without Iván OK.

---

## What this repo is

**`Ai-Whisperers/sazon-app`** is the source code for the Sazon RMS app — the restaurant management system, built for one bakery (Saskia's). All product decisions are filtered through "does Saskia's bakery need this?" If yes, build it. If no, defer.

Supports **two deployment modes**:

- **Local-first** (legacy): single-user install on the operator's PC, binds to `127.0.0.1`, SQLite, no third-party SaaS.
- **Hosted** (since 2026-09-24): VPS at paragu-ai (ServaRica), Docker Swarm + Traefik + Cloudflare DNS-01. Active URL: https://sazon-vps.paragu-ai.com. Render.com was the prior hosted target (2026-09-02 → 2026-09-23) but is now DEPRECATED — see `docs/operations/2026-09-24-deployment.md`. The `render.yaml` at the repo root is **historical only, do not deploy to Render.**

---

## Hard rules (read before opening any PR)

### Money math (6 sub-rules)

1. `Decimal` for all intermediate math. NEVER `float` for money.
2. `to_int_gs()` is the ONLY path that converts `Decimal → int`. Never `int(Decimal("1.50"))`.
3. Property-based tests in `tests/test_money.py` lock the behavior.
4. Display rounding: half-up at the persistence site only; never at the read site.
5. CSV imports: parse as string, not float. Use `Decimal(s, "1.50")` not `float(s)`.
6. External integrations: round to integer Gs. at the boundary, then store as int.

### Data integrity (5 sub-rules)

7. **Integer Gs. in the DB.** Money columns are `int`, not `Decimal`.
8. **Every sale decrements stock.** When a sale is recorded, the system MUST write `StockMovement` rows for every recipe line of every product in the sale. The router in `app/routers/sales.py` (`sale_create`, `sale_create_multi`) delegates to `apply_sale()` in `app/rms/costing.py`, which is the SINGLE place that writes the audit row. **The chain is locked by 3 tests in `tests/test_sale_create_writes_stock_movement.py`** (and 7 tests in `tests/test_stock_drop.py`). A 2026-10-07 review initially thought this rule was broken (router doesn't write `StockMovement` directly) — but it's correctly delegated to `apply_sale()`. The test file exists to prevent future refactors from breaking the delegation. **Do not move the StockMovement write into the router** — that creates two write paths and the migration-090 single-table consolidation comment in `costing.py` will warn against it.
9. **Negative stock is allowed** (kitchen reality > accounting purity) but red-flashes on dashboard.
10. **Cross-recipe BOM cycles raise `CycleInRecipeTree`**; UI shows error, never silently truncates.
11. **Auto-overwrite of recipes during re-import** requires confirmation modal showing diff; auto-backup before mutation.

### Migrations (8 sub-rules)

12. **No Alembic.** Hand-rolled versioned migrations in `app/rms/db.py` (117 migrations, no gaps).
13. **Every migration is forward-only.** No `downgrade` functions.
14. **Never edit a shipped migration.** Create a new one. The old one is the persisted contract.
15. **Never renumber or reorder.** Version number is the contract.
16. **Migrations are atomic** (one transaction per migration).
17. **Pre-migration auto-backup is mandatory** to `/tmp/sazon_backups/<db>-pre-v<A>-to-v<B>.json.gz` (or equivalent). Implemented in `app/rms/db.py` `sync_backup_before_migration()` — runs before the first pending migration in `init_db()`. Uses `app/rms/backup.py::backup_database()` for the gzipped JSON+manifest. **Fail-closed by default**: if the backup fails, `init_db` raises unless `AIW_RMS_PROCEED_WITHOUT_BACKUP=1` is set. Locked by 3 tests in `tests/test_migration_safety.py` (`test_sync_backup_before_migration_writes_file`, `test_sync_backup_before_migration_can_be_restored`, `test_init_db_writes_pre_migration_backup_before_applying`).
18. **`app_meta` table is the source of truth** for the current schema state. The schema version is read from `app_meta(key='schema_version')` (set by `app/rms/db.py` during `init_db()`). `PRAGMA user_version` is NOT used (deliberate decision 2026-10-09 — see `docs/operations/2026-10-09-schema-version-source.md`). The in-app `SCHEMA_VERSION` constant in `app/rms/config.py` is the build's intended version; the `app_meta` row is the runtime's current version.
19. **Two fail-closed rules** (FloCafe pattern):
    - Missing DB on a previously-initialized install → throw, don't recreate.
    - DB schema newer than build → throw, don't auto-downgrade. **ENFORCED** via `fail_closed_on_newer_schema()` in `app/rms/db.py`. Locked by `tests/test_migration_safety.py::test_fail_closed_on_newer_schema_db_raises`.

### Time zones (2 sub-rules)

20. All datetime math uses `zoneinfo.ZoneInfo("America/Asuncion")`. Stored UTC, displayed local.
21. Conversion only at the edge (UI render or external integration), never in business logic.

### UI (4 sub-rules)

22. **No React/Vue/Tailwind/SPA build step.** UI is server-rendered Jinja2 + HTMX for inline interactivity. The pyproject comment "Phase 1: pure server-rendered HTML (NOT HTMX)" is **STALE**; HTMX is in active use in `receta_form.html` and `produccion*.html`.
23. **User-facing UI strings in Paraguayan Spanish (vos) per `app/docs/copy-vos.md`** (or `sazon-context/docs/operations/copy-vos-request.md`). Verb forms: "guardá", "tenés", "querés" (not Argentine "vos" forms). Money: "Gs. 729.167" (period thousands sep, no decimals). Date: "31/08/2026" (DD/MM/YYYY).
24. **Code identifiers, error logs, and developer-facing documentation are in English.** This is the explicit carve-out — only user-facing strings are Spanish.
25. **Spanish (vos) form for verb conjugations.** "Guardá", not "Salvá".

**Redesign (mandatory).** Simplify visibility, never functionality. Before changing what a page shows, follow `docs/ux/redesign-prompt.md`. Show the essential step first. Keep secondary and advanced controls one interaction away, labeled in Spanish (vos). Never delete a field, action, setting, filter, calculation, or workflow to make a screen cleaner, and never change business logic to fit the layout. Context-sensitive fields appear when the choice that needs them is made (Mostrador vs Delivery, recipe-linked portion details). A page is not done until every previously reachable capability still works for the roles that could use it.

### Security (5 sub-rules)

26. **No new dependencies without explicit Iván OK.** Each new dep is a security review. If you think you need pandas / numpy / pint / py-moneyed / SQLModel / anything not in `pyproject.toml`, **ask first**.
27. **Never commit credentials.** Pre-commit hook `check-no-secrets` blocks any staged file containing GitHub PAT shapes (`ghp_*`, `ghs_*`, `gho_*`, `ghu_*`, `github_pat_*`), `x-access-token:*** URLs, AWS access keys, JWTs, or long `key=value` strings. Use BWS for secrets. See `scripts/check_no_secrets.py` and the `credential-redacted-grep` skill. **If you find a leaked credential: rotate first, then scrub the transcript with `scripts/redact_key.py`, then fix the leak path.**
28. **No live customer PII.** The app doesn't have a customer table; if you add one, follow AGENTS.md rule #4 of `sazon-context`.
29. **No silent overwrite.** Every mass-write (import, re-import) requires explicit user confirmation; auto-backup before destructive ops.
30. **Bind to `127.0.0.1` for local; `0.0.0.0` allowed for hosted.** `app/rms/main.py` has an assertion that refuses to start on any other host. Hosted (VPS via Traefik + Cloudflare Tunnel) uses `0.0.0.0` because TLS is terminated upstream and the port is not reachable from the public internet.

### Deployment (4 sub-rules)

31. **WAL mode + `secure_delete = ON`.** Set in `app/rms/db.py` event listener.
32. **No `async def` in route handlers.** Sync mode.
33. **Hosted uses Docker** (Dockerfile + docker-stack.yml). Local dev does NOT require Docker.
34. **Healthz contract.** `/healthz` returns 200 only when the app can serve requests. `/healthz/deps` checks external deps (env vars present, no leaked secrets). `/healthz/backup` checks that the most recent DB backup is < 26h old. **All three endpoints MUST be fast (< 100ms) and MUST NOT return sensitive data.** A failed `/healthz` should not log the error to Sentry; it should page on-call.

### Process (3 sub-rules)

35. **CHANGELOG discipline.** Every PR that changes `app/`, `scripts/`, `tests/`, or `.github/` MUST also update `app/CHANGELOG.md`. CI fails otherwise.
36. **Single-developer bus factor.** All code is written and reviewed by one person. To mitigate: ADRs in `docs/architecture/decisions/` (when needed), every commit has a clear message, every PR has a ticket, every behavior change has a regression test, every fix has a runbook.
37. **PRs reference a ticket.** Use the `SASKIA-NNN-<slug>.md` convention.

---

## Anti-rules (what NOT to migrate — already considered)

These are ideas that look good on paper but are wrong for Sazon at its current scale. Don't re-litigate them in PRs. **Each anti-rule was verified against the current repo state on 2026-10-07.**

**Sazon IS multi-tenant** (per `pyproject.toml` `description = "Sistema de gestión de restaurante — multi-tenant"` and the `tenant` table from migration 008). So "don't go multi-tenant" is WRONG — it already is. The right anti-rule is "don't ADD multi-tenant SaaS complexity" (e.g. tenant-tiered billing, white-labeling, per-tenant DBs).

1. **Don't migrate to React/Vue/Tailwind/SPA.** Server-rendered Jinja2 + HTMX is correct. (HTMX IS already in use in `receta_form.html` and `produccion*.html`.) The fix for UX is design system + components, not a framework. **Enforce in CI: fail if templates/ add a React import.**

2. **Don't migrate to microservices.** The monolith is right for this scale. Sazon has 251 app/ python files, 45 tables, 117 migrations — well within monolith territory. The right answer is "extract a function" or "extract a module", not "extract a service".

3. **Don't add GraphQL.** REST + OpenAPI is sufficient until 3+ external consumers. No graphene, strawberry, ariadne, hasura, stepzen, etc.

4. **Don't add a new JWT library.** Supabase already uses JWT for hosted auth (their concern); local auth is bcrypt + session cookies. Don't pull in `pyjwt`, `python-jose`, `authlib`, etc.

5. **Don't add Kafka / RabbitMQ / any message queue.** Sazon doesn't have event volume that needs a queue. Use Postgres LISTEN/NOTIFY or in-process pub/sub if needed. No Celery, RQ, Dramatiq, Huey either.

6. **Don't migrate to Kubernetes.** Docker Swarm is the right level for a 1-3 VPS deployment.

7. **Don't add a mobile app.** Sazon is laptop-first. The browser works on a tablet.

8. **Don't add a public marketplace / online ordering portal.** Sazon has `pedidos` for the operator's use; not a customer-facing ordering site. If customer ordering is ever needed, it's a separate product.

9. **Don't add another ORM.** SQLAlchemy 2.0 sync is the only one. No Peewee, Tortoise, Piccolo, SQLModel, SQLModel-async.

10. **Don't go to async.** Sync handlers throughout. Async adds no win for Sazon's workload. `pyproject.toml` enforces this: "SQLAlchemy sync mode (NOT async)".

11. **Don't add a NoSQL database (MongoDB, Redis-as-DB, DynamoDB).** SQLite + Postgres is the only DB. Redis is for caching if at all.

12. **Don't add WebSockets (except via Supabase real-time).** Sazon's API is HTTP request/response. Supabase real-time is for live KOT/mosaic if added.

13. **Don't add a serverless framework (Lambda, Cloud Functions, Vercel Functions).** Sazon is a long-running FastAPI process, not a function.

14. **Don't add gRPC.** REST is fine.

15. **Don't add CDC (Kafka Connect, Debezium).** Sazon doesn't have multiple services syncing data.

16. **Don't add Elasticsearch / Meilisearch / Typesense.** Postgres FTS is sufficient.

17. **Don't add an ORM migration tool other than the hand-rolled one.** No Alembic, yoyo-migrations, dbmate, sqlx-cli.

18. **Don't add a feature flag system (LaunchDarkly, Unleash, Flagsmith).** The `app_meta` table + `SETTINGS` table is the only switchboard. Operator-editable, no SaaS.

19. **Don't add Sentry log of `/healthz` failures.** `/healthz` is monitored externally (UptimeRobot). Log to operator-visible log only; do not spam Sentry with healthz noise.

20. **Don't add tests that depend on wall-clock time, network access, or the real Sazon DB.** All tests use a SQLite test fixture (`tests/conftest.py` provides one). Property-based tests for invariants; integration tests against a fresh DB; E2E with Playwright in `tests/e2e/`.

See the **IDEATION_PLAN** (`/opt/data/profiles/ivan/cache/scratch/sazon_migration/migration_plan/IDEATION_PLAN.md`) for the long version with rationale.

---

## Tech stack (locked)

Per `docs/operations/2026-09-tech-stack-review.md`:

- **Python 3.13**, **FastAPI 0.115**, **uvicorn[standard]**, **SQLAlchemy 2.0 sync**,
  **openpyxl 3.1**, **jinja2 3.1**, **pydantic 2.9**, **loguru**.
- Dev: pytest 8, pytest-cov, hypothesis 6 (property-based tests), ruff 0.7, Playwright (E2E), httpx, hypothesis, testcontainers.
- Install: **`uv sync`** (NOT pip).
- Pin all deps in `pyproject.toml`; use `uv.lock` for reproducibility.
- **No `async def`** in route handlers. Sync mode.
- **No Alembic**. Hand-rolled versioned migrations in `app/rms/db.py`.
- **Server-rendered HTML + HTMX.** No Tailwind, no React/Vue, no SPA build.
- **Hosted uses Docker** (Dockerfile + docker-stack.yml).
- **E2E tests use Playwright** (added 2026-10-07, already in `pyproject.toml` `[project.optional-dependencies] dev`). See Testing section.

---

## Build brief (current reality)

This codebase is maintained by **Iván directly**, not by an external "Kiki" anymore. The original engagement model (signed quote + first cuota + Drive + PC named) is historical. Current work:

- Pick tasks from the **IDEATION_PLAN** in `/opt/data/profiles/ivan/cache/scratch/sazon_migration/` (or its repo-mirrored copy when one exists).
- Follow the locked dev plan Tasks 1-10 in `docs/plans/2026-08-31-rms-fase-1-dev-plan.md` for the original Phase 1 scope.
- Each task has a demo; don't start the next task until the current task's demo passes.
- Read BEFORE Task 1: `docs/plans/2026-08-31-rms-fase-1-dev-plan.md`, `docs/operations/2026-09-fase-1-specs.md`, `docs/operations/import-mapper.md`, `docs/operations/herbus-discovery-prompt.md`.

---

## Testing

- Pytest with `uv run pytest`.
- Coverage gate: 80% (CI fails below). Current gate is 35%; Phase 1-4
  plan bumps it in 4 stages. See `state/test-coverage-2026-10-04.json`.
- Property-based tests for money (`test_money.py`); unit tests for unit
  coercion (`test_units.py`); roundtrip tests for import.
- **E2E tests with Playwright** (added 2026-10-07, in `pyproject.toml` `dev` extra). Lives in `tests/e2e/`.
  - One framework, pinned in `pyproject.toml`.
  - Runs against a dev server with a SQLite test fixture, never against production.
  - CI gates on E2E for PRs to `main`; smoke subset on every PR, full suite on push to main.
  - See `docs/operations/2026-10-04-test-execution-plan.md` for the master plan, `docs/TEST_ARCHITECTURE.md` for 5 levels × 8 domains, `docs/operations/2026-10-04-qa-hats-playbook.md` for 12 hats × wishlists, `docs/operations/2026-10-04-test-infra-one-pager.md` for condensed.

**Test strategy + roadmap**:
- `docs/operations/2026-10-04-test-execution-plan.md` (master plan)
- `docs/TEST_ARCHITECTURE.md` (5 levels × 8 domains)
- `docs/operations/2026-10-04-qa-hats-playbook.md` (12 hats × wishlists)
- `docs/operations/2026-10-04-test-infra-one-pager.md` (condensed)

---

## CI

GitHub Actions runs on every PR to `main`:
- `ruff check .`
- `ruff format --check .`
- `pytest --cov=app` (80% coverage gate)
- Typer check (informational; not blocking yet)
- `sazon migrate` smoke test (fresh SQLite)
- CHANGELOG discipline check (fails PR if `app/`, `scripts/`, `tests/`, or
  `.github/` changed but `app/CHANGELOG.md` did not)
- **Anti-rule enforcement** (13 of 20 anti-rules enforced via grep in CI;
  see `.github/workflows/ci.yml` and `tests/test_ci_anti_rules.py`)

**Weekly scheduled workflow:**
- `.github/workflows/date-boundary.yml` — runs the full pytest suite
  with the runner's clock pinned to the last day of the current month.
  Catches the class of bug where a test (or production code) assumes
  "tomorrow" is reachable from "today" without saying so. Runs Mondays
  03:00 UTC. Locked by `tests/test_date_boundary.py` (60 tests).
  Ported from `karanshukla/openresto` (MIT-licensed) with pytest
  substituted for Jest + Playwright.

The TODO line about anti-rule enforcement was removed when the
implementation shipped (see commit `50c35082` for wave 1, `18668813`
for wave 2).

See `.github/workflows/ci.yml`.

---

## Issue templates

When filing an issue, pick the right template:

- **Bug report** (`.github/ISSUE_TEMPLATE/bug.md`) — defect in deployed code.
- **Feature request** (`.github/ISSUE_TEMPLATE/feature.md`) — proposal for a new feature. **Check `docs/wishlist/raw/` first** — the idea may already be there. If so, link rather than duplicate.
- **Epic / story** (`.github/ISSUE_TEMPLATE/epic.md`) — multi-PR initiative with several stories. Use for any work scoped across multiple PRs.

---

## Locked hotfixes (DO NOT REVERT without understanding)

The commits on `main` below address real production incidents from
2026-09-04. Each is locked in by a fail-closed test in
`tests/test_hotfix_regressions.py`. If a refactor breaks one of those
tests, the right answer is almost always to update the code to match the
test, NOT to relax the test.

- `f1af406` — HEAD /healthz for UptimeRobot
- `c093a75` — SUPABASE_SECRET_KEY / SUPABASE_PUBLISHABLE_KEY aliases
- `99b37c6` — supabase SDK in Dockerfile pip list
- `bb21eff` — /healthz/deps env fingerprint (debug-only, never leaks values)
- `501bcff` — `row_counts_json` ORM type matches Postgres JSONB

For each locked hotfix, the revert-impact line is:
- `f1af406`: reverting breaks `tests/test_hotfix_regressions.py::test_healthz_endpoint`. Production impact: UptimeRobot monitoring breaks; no alerts on app down.
- `c093a75`: reverting breaks `tests/test_hotfix_regressions.py::test_supabase_key_aliases`. Production impact: Supabase SDK looks for one env var name, app looks for the other, hosted auth fails.
- `99b37c6`: reverting breaks `tests/test_hotfix_regressions.py::test_supabase_in_dockerfile`. Production impact: Supabase SDK missing from Docker image, hosted auth fails.
- `bb21eff`: reverting breaks `tests/test_hotfix_regressions.py::test_healthz_deps_fingerprint`. Production impact: `/healthz/deps` starts logging secret values; OPSEC violation.

---

## Recovery & coordination

- **Worktree policy** (parallel sessions): see `docs/operations/worktree-policy.md`. Use git worktrees for concurrent work; don't share branches between sessions.
- **Sibling session coordination**: see `docs/operations/2026-10-04-sibling-session-coordination.md`. When multiple AI agents work the same repo in parallel, coordinate via the worktree policy and `.hermes/`.
- **Healthz contract**: see Hard Rule 34.
- **Locked hotfixes**: see above.

---

## Ticket convention

Tickets use the format `SASKIA-NNN` (e.g. `SASKIA-001`). 5-character
codes like `E1.S2` are for epic+story (e.g. `E3.S1` = Epic 3, Story 1).
File naming: `SASKIA-NNN-<short-slug>.md`.

The full epic plan (25 epics, 6 phases, ~268h) lives at
`docs/plans/2026-09-07-sazon-complete-epic-plan-v3.md`. Pick from
there.

Ticket template:

```markdown
# SASKIA-NNN: <short title>

**Date:** YYYY-MM-DD
**Epic / Story:** E#.S#
**Owner:** Iván
**Estimate:** Xh
**Status:** in_progress | shipped | blocked | cancelled

## What

<description>

## Why

<business outcome>

## Tasks

- [ ] Task 1
- [ ] Task 2

## Acceptance

<definition of done>
```

---

## Cross-references

For deeper context, read these in order:

1. `research-repos/saskia/AGENTS.md` — Saskia's build context (OPSEC-clean)
2. `/opt/data/profiles/ivan/cache/scratch/sazon_migration/PLAN_INDEX.md` — entry point for migration plan
3. `/opt/data/profiles/ivan/cache/scratch/sazon_migration/migration_plan/IDEATION_PLAN.md` — 183 items, 5 tracks
4. `/opt/data/profiles/ivan/cache/scratch/sazon_migration/migration_plan/MASTER_PLAN.md` — 34 specific migration tasks
5. `app/docs/upgrade-tiers.md` — what can be removed/simplified
6. `app/docs/threat-model.md` — security posture
7. `app/docs/architecture.md` — system architecture
8. `app/docs/copy-vos.md` — UI copy rules (Paraguayan Spanish)
8b. `docs/ux/redesign-prompt.md` — master redesign prompt (simplify visibility, never functionality)
9. `docs/operations/2026-10-04-sibling-session-coordination.md` — worktree policy
10. `docs/operations/2026-10-04-test-execution-plan.md` — test plan
11. `IMPROVEMENT_BACKLOG.md` — what to work next
12. `WHAT_NEXT.md` — shorter punchlist

---

## Decision framework

**ASK Iván before doing:**
- New dependencies
- Breaking changes (DB schema, API, auth)
- Security-sensitive changes (encryption, OPSEC, scope, sharing)
- Deviation from a hard rule above
- New deployment mode (multi-region, white-label, etc.)
- Decisions that affect Saskia's workflow (UI/UX, copy, what buttons to add)

**AGENT decides without asking:**
- Variable names, comment style
- Helper function extraction (within a single file)
- Test organization (which test file, which fixture)
- Implementation of an already-approved feature
- Bug fixes that match the documented behavior
- Documentation rewrites that don't change the rules

**ESCALATE (postpone the task, surface to Iván):**
- Hard rule conflicts
- "Best practice" suggestions that require a hard rule change
- Cross-cutting refactors that touch 5+ files
- Anything that involves Saskia directly (asking her, sending her data, sharing her data with a third party)

---

## How to work a session

1. **Read PLAN_INDEX.md** in the migration workspace (5 min).
2. **Check `migration_state.json`** for current task status.
3. **Pick ONE task** to work on. Don't try to do multiple.
4. **Work the task** — implement, test, lint, commit.
5. **Append a session log** to `session_logs/YYYY-MM-DD.md` in the workspace.
6. **Update `migration_state.json`** to mark the task done.
7. **Update the IDEATION_PLAN/MASTER_PLAN** with new findings.

If the session is interrupted: commit the WIP, update the state file, log what was done, and end. Next session will pick up where you left off.

---

## Troubleshooting

| Symptom | First check |
|---|---|
| Lost the working directory | `cd /opt/data/work/saskia-app` |
| Tests failing after migration | `uv run pytest -k <name>` to isolate; check `app/rms/db.py` `_migration_NNN_*` functions |
| DB looks weird | `sqlite3 ~/Documents/aiw-restaurant/db.sqlite` then `.schema`, `PRAGMA user_version` |
| Migration not applied | Check `app/rms/db.py` for `SCHEMA_VERSION` or `PRAGMA user_version`; check `/tmp/sazon_backups/` for pre-migration backup |
| `/healthz` failing | Check `/healthz/deps` for env var issues; check `/healthz/backup` for backup age |
| Stuck on a task | Check `state/test-coverage-2026-10-04.json`, `IMPROVEMENT_BACKLOG.md`, `WHAT_NEXT.md` |
| Kernel died mid-session | Use `mcp__filesystem__read_file` instead of `terminal`; see `execute-code-ssh-mode` skill |
| Session_search returns nothing | Try different keywords; the session_id is in the Hermes runtime environment block |

---

## When in doubt

**Read these three docs first:**
1. This file (AGENTS.md)
2. `research-repos/saskia/AGENTS.md` (Saskia's context)
3. `/opt/data/profiles/ivan/cache/scratch/sazon_migration/PLAN_INDEX.md` (migration plan)

**Then ask Iván** if it's still unclear. Don't guess on hard rules, security, or anything that touches Saskia's data.
