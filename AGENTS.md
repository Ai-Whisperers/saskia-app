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
8. **Every sale decrements stock.** When a sale is recorded, the system MUST write `StockMovement` rows for every recipe line of every product in the sale. The router in `app/routers/sales.py` (`sale_create`, `sale_create_multi`) delegates to `apply_sale()` in `app/rms/sales/lifecycle.py` (NOT `app/rms/costing.py` — that file is a 1.3 KB deprecated shim since the SASKIA-212 refactor), which is the SINGLE place that writes the audit row. **The chain is locked by 3 tests in `tests/test_sale_create_writes_stock_movement.py`** (and 7 tests in `tests/test_stock_drop.py`). A 2026-10-07 review initially thought this rule was broken (router doesn't write `StockMovement` directly) — but it's correctly delegated to `apply_sale()`. The test file exists to prevent future refactors from breaking the delegation. **Do not move the StockMovement write into the router** — that creates two write paths and the migration-090 single-table consolidation comment in `sales/lifecycle.py` warns against it.
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

**Sazon is SINGLE-TENANT per-client** (per SASKIA-210, 2026-10-07: Saskia/La Vaquita Holandesa is the only current client; the product is deployed as per-client INSTANCES — each client gets their own site + fully loaded data — not shared-DB multi-tenant). The `tenant` table from migration 008 is legacy infrastructure, not active multi-tenanting. So "don't go multi-tenant" IS right *as a forward direction*; the right anti-rule is "don't build RLS / ORM-level tenancy / cross-tenant analytics until we have ≥2 paying clients and a 1-base-Supabase template pattern to clone from". The `tenant` table is dormant and may be repurposed or dropped when we revive the multi-instance work.

1. **Don't migrate to React/Vue/Tailwind/SPA.** Server-rendered Jinja2 + HTMX is correct. (HTMX IS already in use in `receta_form.html` and `produccion*.html`.) The fix for UX is design system + components, not a framework. **Enforce in CI: fail if templates/ add a React import.**

2. **Don't migrate to microservices.** The monolith is right for this scale. Sazon has 289 app/ python files, 64 tables, 117 migrations — well within monolith territory. The right answer is "extract a function" or "extract a module", not "extract a service".

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
- Coverage gate: 80% (CI fails below). Current gate is 40% (43% actual coverage, 9-areas migration landed 2026-10-12); Phase 1-4
  plan bumps it in 4 stages. See `state/test-coverage-2026-10-04.json` and `state/test-coverage-9-areas-43pct.json`.
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

## Abstraction-usage enforcement

Beyond the hard rules above, the codebase has a small but tightly-defined
set of abstractions in `app/rms/`:

- `app/rms/money.py:to_int_gs()` — the ONLY Decimal→int path
- `app/rms/units.py:Unit.coerce()` — the ONLY unit input path
- `app/rms/clock.py:now/today_local/utcnow/to_utc/to_asuncion` — single
  source of truth for `now()` (every datetime is tz-aware)
- `app/rms/sales/lifecycle.py:apply_sale()` — sale-path SSOT
  (the `app/rms/costing.py` shim re-exports for backwards compat only)
- `app/rms/stock_ledger.py:apply_stock_delta()` — the single helper
  for non-sale stock deltas + audit rows

`tests/test_abstraction_usage.py` enforces that these abstractions
are used and not bypassed. **24 tests in this file**; 20 pass today,
4 fail with documented violations that are content for follow-up PRs.

| Test | Catches | Status |
|---|---|---|
| `test_no_int_decimal_in_tests` | `int(Decimal(...))` in tests (rule 2) | FAIL — 3 hits |
| `test_no_bare_datetime_now_in_app` | `datetime.now()` in app/ (rule 20) | PASS |
| `test_no_datetime_utcnow_in_app` | `datetime.utcnow()` in app/ (rule 20) | FAIL — 6 hits in seed/packs.py |
| `test_apply_sale_imported_from_canonical_path_in_tests` | `apply_sale` imported from shim (rule 8) | FAIL — 18 test files |
| `test_no_direct_stockmovement_outside_sale_path` | direct `StockMovement()` in non-sale paths | FAIL — 6 hits (211a targets) |
| `test_abstraction_module_has_dunder_all[*]` | abstraction modules lack `__all__` | PASS |
| `test_to_int_gs_imports_canonical_path` | `to_int_gs` imported from wrong module | PASS |
| `test_no_deprecated_costing_imports_for_non_shimmed_names` | shim imports of non-shimmed names | PASS |
| `test_unit_input_goes_through_unit_coerce` | direct `unit = "kg"` assignments | INFO — candidates for migration |
| `test_auth_checks_go_through_is_auth_disabled` | env-var reads for auth state | PASS |
| `test_tier_tests_use_fixtures_not_inline_setup` | tier tests with inline TestClient | INFO — sibling-branch migration |
| `test_no_subprocess_in_app` | `subprocess`/`os.system` in app/ | INFO — review for services layer |
| `test_test_file_is_self_consistent` | self-test (AST-based) | PASS |

When you add a new abstraction, three steps are required:
1. Add the file to `ABSTRACTION_MODULES` in the test file (so it's
   exempt from "no direct X" checks that would be self-referential).
2. Give it an `__all__` so the `__all__` test passes.
3. Add a specific test below that pins the bypass-detection regex
   (so a future refactor that breaks the abstraction fails CI).

When you add a new bypass-detection test, two steps are required:
1. Use `_walk_py()` + `_scan_for_pattern()` to find violations; don't
   write custom file-walking code.
2. Have the test fail with `file:line:context` so the operator can
   fix the violation. A list of 50 truncated paths is not actionable.

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

<!-- origin additions (AGENTS.md) -->
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
- **Hosted** (since 2026-09-24): VPS at paragu-ai (ServaRica), Docker Swarm + Traefik + Cloudflare DNS-01. **Three environments** (saskia-prod / saskia-test / saskia-dev services on one Traefik) — see `.github/workflows/deploy-*.yml` and the `saskia-rms-deploy-flow` skill. Active URL: https://sazon-vps.paragu-ai.com. Render.com was the prior hosted target (2026-09-02 → 2026-09-23) but is now DEPRECATED — see `docs/operations/2026-09-24-deployment.md`. The `render.yaml` at the repo root is **historical only, do not deploy to Render.**

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
8. **Every sale decrements stock.** When a sale is recorded, the system MUST write `StockMovement` rows for every recipe line of every product in the sale. The router in `app/routers/sales.py` (`sale_create`, `sale_create_multi`) delegates to `apply_sale()` in `app/rms/sales/lifecycle.py` (NOT `app/rms/costing.py` — that file is a 1.3 KB deprecated shim since the SASKIA-212 refactor), which is the SINGLE place that writes the audit row. **The chain is locked by 3 tests in `tests/test_sale_create_writes_stock_movement.py`** (and 7 tests in `tests/test_stock_drop.py`). A 2026-10-07 review initially thought this rule was broken (router doesn't write `StockMovement` directly) — but it's correctly delegated to `apply_sale()`. The test file exists to prevent future refactors from breaking the delegation. **Do not move the StockMovement write into the router** — that creates two write paths and the migration-090 single-table consolidation comment in `sales/lifecycle.py` warns against it.
9. **Negative stock is allowed** (kitchen reality > accounting purity) but red-flashes on dashboard.
10. **Cross-recipe BOM cycles raise `CycleInRecipeTree`**; UI shows error, never silently truncates.
11. **Auto-overwrite of recipes during re-import** requires confirmation modal showing diff; auto-backup before mutation.

### Migrations (8 sub-rules)

12. **No Alembic.** Hand-rolled versioned migrations — **121 as of `_121_seasonal_event` (SASKIA-216, 2026-10-12)**, no gaps. Early migrations live as `_migration_NNN_*` functions in `app/rms/db.py` (through 083); newer ones as files in `app/rms/migrations/` imported into the db.py registry. (Note: 118+119 = SASKIA-212 recipe work; 120+121 = SASKIA-215/216, renumbered to avoid collision — see `config.py:92`.)
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

### Process (3 sub-rules; hard rules now number 1-49 across all groups)

35. **CHANGELOG discipline.** Every PR that changes `app/`, `scripts/`, `tests/`, or `.github/` MUST also update the **root `CHANGELOG.md`** — the CI gate (`grep -qx "CHANGELOG.md"`) matches the root path only, and ci.yml now fails outright if `app/CHANGELOG.md` reappears. Root `CHANGELOG.md` is the ONLY changelog (decision 2026-10-12; the former `app/CHANGELOG.md` contents were folded into root, preserving all ticket history).
36. **Single-developer bus factor.** All code is written and reviewed by one person. To mitigate: ADRs in `docs/architecture/decisions/` (when needed), every commit has a clear message, every PR has a ticket, every behavior change has a regression test, every fix has a runbook.
37. **PRs reference a ticket.** Use the `SASKIA-NNN-<slug>.md` convention.

### Coordination & org context (7 sub-rules, added 2026-10-12)

42. **This file is the single rulebook.** All agent rules live here; per-directory AGENTS.md files were consolidated on 2026-10-12 (the `app/rms/` file became the "package conventions" section above). Don't create new AGENTS.md files in subdirectories — extend this one. Same principle repo-wide: ONE changelog (root `CHANGELOG.md` only — CI fails if `app/CHANGELOG.md` reappears) and ONE location per document (`docs/roadmap/` is the canonical home for plans/audits/sessions/decisions; other copies must be redirect stubs, not full copies).

43. **Three environments, one VPS.** saskia-prod / saskia-test / saskia-dev run as separate Docker Swarm services behind one Traefik (see `docs/operations/worktree-policy.md` and `.github/workflows/deploy-*.yml`). Never deploy to prod without a green test-env run of the same build. A `docker service update` against the wrong env service name is a silent no-op — verify with `docker service ps saskia-<env>_web`.

44. **Check `.hermes/` and sibling sessions before starting work.** Read `.hermes/HERMES-ORIENTATION.md` and check `git worktree list` + other branches' freshness. Two sessions landing the same feature hours apart has happened (loyalty-redeem, 2026-10-01): before implementing anything from a plan doc, `git log --all --grep="<keyword>"` to check whether a sibling already shipped it.

45. **Docs drift — always measure, never trust counts.** Any numeric claim in any doc (test counts, coverage %, migration count, file counts) is stale within days. Before citing a baseline in a PR/plan, grep the source of truth (`CURRENT_SCHEMA_VERSION` in config.py, `pytest --collect-only`, `ls app/rms/migrations/`). This file's counts were last verified 2026-10-12.

46. **AIW context (upstream, read-only).** This repo was generated from the AIW Python template (`templates-standard/repo-template/` — byte-identical `.flake8`/`cspell.json`/`ruff.toml`). The AIW org rulebook lives in `Ai-Whisperers/aiw-org` AGENTS.md. When an AIW-org rule conflicts with this file, THIS FILE WINS for Sazon work. Do not edit aiw-org repos from this repo's sessions.

47. **Name collisions — don't conflate.** "Saskia" here = Saskia Weiss Vander, the bakery client. (An unrelated AIW design exercise uses "Saskia" for a hypothetical restaurant instance — different entity.) "Kiki" here = the assistant-agent persona for this repo. (AIW's human co-founder is also called Kiki/"Kyrian" — different entity.) Never mix client data or governance authority between them.

48. **Data tier discipline.** Business data (Saskia's sales, suppliers, prices) is treated as local-only — it lives on the VPS/SQLite, never in free-tier cloud services. LLM API calls are the only routine external data flow. Any new integration that moves business data off-host requires explicit Iván OK.

49. **Stabilization window after infrastructure changes.** After a schema migration lands on prod, a deploy-topology change, or any infra-affecting merge: no new workstream on that surface for 24h; verify prod (`/healthz` ×3, `/healthz/backup`, spot-check a page) before piling the next change.

---

## `app/rms/` package conventions (merged from app/rms/AGENTS.md 2026-10-12)

**This is the ONLY AGENTS.md in the repo.** The former `app/rms/AGENTS.md` was merged
into this section (its money/time/migration/testing rules were restatements of rules
1-6, 20-21, 12-19 above and were dropped; only package-specific content survives here).

### Units (extends rule 7)

- All unit input goes through `app/rms/units.py:Unit.coerce()`.
- Cross-family unit conversion (g→L, kg→und, etc.) is forbidden — raises `ValueError`.
- Adding new units to the `Unit` enum requires operator OK + alias-map update.
- Never store units as free-text in DB. Enum values only.

### Recipe internals (extends rules 8-11)

- `recipe_line` is polymorphic via `line_kind` ∈ {'ingredient', 'sub_recipe'}; `line_ref_id` points to `ingredient.id` or `recipe.id` depending on `line_kind`.
- `yield_qty` is required for sales to be applied; sales with NULL `yield_qty` are rejected.
- Void reverses stock moves fully, including sub-recipe expansion.
- `sale_stock_move.affected_recipe_id` is for audit, not for re-walking — the tree walk during void uses the CURRENT recipe state, not the historical one.

### Postgres DDL atomicity (migration gotcha, extends rules 12-19)

**Postgres DDL auto-commits.** On SQLite this is a non-issue (DDL is transactional).
On Postgres, each `ALTER TABLE` / `CREATE INDEX` is its own implicit commit — a failing
5th ALTER leaves the first 4 applied. **Fix:** use `atomic_ddl_block(conn, [sql1, ...])`
(defined in `app/rms/db.py`) instead of looping `conn.exec_driver_sql(sql)` in plain
try/except — it wraps each statement in a SAVEPOINT on Postgres (no-op on SQLite).
Per-statement try/except is still allowed **inside** the helper. Migration 081
(`_migration_081_pedido_delivery_window`) is the reference example.

### Module structure (when adding new files)

- Pure logic (no DB, no IO): `app/rms/<module>.py` with public function exports.
- DB-touching logic: `app/rms/<module>.py` taking `session: Session` as first arg.
- Routers: `app/routers/<module>.py` exporting `router` (FastAPI APIRouter).
- Templates: `app/templates/<page>.html` extending `base.html`.
- Services (file IO, external): `app/services/<module>.py`.

### Tooling rules (2026-10-08 hardening sweep)

38. **No new `*_original.py` / `*_legacy.py` / `*_v2.py` files.** The pre-commit hook `forbid-legacy-modules` blocks these. For a fallback path use a `__deprecated__` attribute with a removal deadline.
39. **No `from app.routers import X` from inside `app/rms/`.** Routers import rms; rms must never import routers. `scripts/check_imports.py` CI gate enforces this (violations are circular-import at startup).
40. **Cyclomatic complexity ceiling: CC ≤ 10.** `make complexity` fails the commit. Extract helpers, use table lookup, split by concern.
41. **No silent except blocks in `app/routers/`.** Pre-commit hook `no-silent-excepts` (AST scan). Always log + re-raise. Known violations tracked in IMPROVEMENT_BACKLOG.md Tier 9.

### Make cheat sheet

- `make check` — lightweight gate (ruff + warnings + duplicates + arch)
- `make ci` — full test suite (what CI runs) · `make ci-extra` — slow static analysis
- `make dead-code` (vulture) · `make complexity` (radon) · `make duplicates` / `make duplicates-code` · `make arch` (cycles + layered imports) · `make security` (bandit) · `make audit-cve` (pip-audit) · `make licenses` (reuse)

---

## Anti-rules (what NOT to migrate — already considered)

These are ideas that look good on paper but are wrong for Sazon at its current scale. Don't re-litigate them in PRs. **Each anti-rule was verified against the current repo state on 2026-10-07.**

**Sazon is SINGLE-TENANT per-client** (per SASKIA-210, 2026-10-07: Saskia/La Vaquita Holandesa is the only current client; the product is deployed as per-client INSTANCES — each client gets their own site + fully loaded data — not shared-DB multi-tenant). The `tenant` table from migration 008 is legacy infrastructure, not active multi-tenanting. So "don't go multi-tenant" IS right *as a forward direction*; the right anti-rule is "don't build RLS / ORM-level tenancy / cross-tenant analytics until we have ≥2 paying clients and a 1-base-Supabase template pattern to clone from". The `tenant` table is dormant and may be repurposed or dropped when we revive the multi-instance work.

1. **Don't migrate to React/Vue/Tailwind/SPA.** Server-rendered Jinja2 + HTMX is correct. (HTMX IS already in use in `receta_form.html` and `produccion*.html`.) The fix for UX is design system + components, not a framework. **Enforce in CI: fail if templates/ add a React import.**

2. **Don't migrate to microservices.** The monolith is right for this scale. Sazon has 286 app/ python files, ~45 distinct tables (more if counting per-migration CREATE TABLE IF NOT EXISTS), 121 migrations (counts verified 2026-10-12 + 2026-10-12 wave-3 respawn) — well within monolith territory. The right answer is "extract a function" or "extract a module", not "extract a service".

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
- Coverage gate: **35% enforced today** (`--cov-fail-under=35` in `pyproject.toml` addopts + CI; verified 2026-10-12). The long-term target is 80%; the 9-areas test migration (2026-10-12) is stage 1 of the staged bumps. See `state/test-coverage-9-areas-43pct.json`.
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

## Abstraction-usage enforcement

Beyond the hard rules above, the codebase has a small but tightly-defined
set of abstractions in `app/rms/`:

- `app/rms/money.py:to_int_gs()` — the ONLY Decimal→int path
- `app/rms/units.py:Unit.coerce()` — the ONLY unit input path
- `app/rms/clock.py:now/today_local/utcnow/to_utc/to_asuncion` — single
  source of truth for `now()` (every datetime is tz-aware)
- `app/rms/sales/lifecycle.py:apply_sale()` — sale-path SSOT
  (the `app/rms/costing.py` shim re-exports for backwards compat only)
- `app/rms/stock_ledger.py:apply_stock_delta()` — the single helper
  for non-sale stock deltas + audit rows

`tests/test_abstraction_usage.py` enforces that these abstractions
are used and not bypassed. **24 tests in this file**; 20 pass today,
4 fail with documented violations that are content for follow-up PRs.

| Test | Catches | Status |
|---|---|---|
| `test_no_int_decimal_in_tests` | `int(Decimal(...))` in tests (rule 2) | FAIL — 3 hits |
| `test_no_bare_datetime_now_in_app` | `datetime.now()` in app/ (rule 20) | PASS |
| `test_no_datetime_utcnow_in_app` | `datetime.utcnow()` in app/ (rule 20) | FAIL — 6 hits in seed/packs.py |
| `test_apply_sale_imported_from_canonical_path_in_tests` | `apply_sale` imported from shim (rule 8) | FAIL — 18 test files |
| `test_no_direct_stockmovement_outside_sale_path` | direct `StockMovement()` in non-sale paths | FAIL — 6 hits (211a targets) |
| `test_abstraction_module_has_dunder_all[*]` | abstraction modules lack `__all__` | PASS |
| `test_to_int_gs_imports_canonical_path` | `to_int_gs` imported from wrong module | PASS |
| `test_no_deprecated_costing_imports_for_non_shimmed_names` | shim imports of non-shimmed names | PASS |
| `test_unit_input_goes_through_unit_coerce` | direct `unit = "kg"` assignments | INFO — candidates for migration |
| `test_auth_checks_go_through_is_auth_disabled` | env-var reads for auth state | PASS |
| `test_tier_tests_use_fixtures_not_inline_setup` | tier tests with inline TestClient | INFO — sibling-branch migration |
| `test_no_subprocess_in_app` | `subprocess`/`os.system` in app/ | INFO — review for services layer |
| `test_test_file_is_self_consistent` | self-test (AST-based) | PASS |

When you add a new abstraction, three steps are required:
1. Add the file to `ABSTRACTION_MODULES` in the test file (so it's
   exempt from "no direct X" checks that would be self-referential).
2. Give it an `__all__` so the `__all__` test passes.
3. Add a specific test below that pins the bypass-detection regex
   (so a future refactor that breaks the abstraction fails CI).

When you add a new bypass-detection test, two steps are required:
1. Use `_walk_py()` + `_scan_for_pattern()` to find violations; don't
   write custom file-walking code.
2. Have the test fail with `file:line:context` so the operator can
   fix the violation. A list of 50 truncated paths is not actionable.

---

## CI

GitHub Actions runs on every PR to `main`:
- `ruff check .`
- `ruff format --check .`
- `pytest --cov=app` (35% coverage gate enforced; 80% is the target, not the gate)
- Typer check (informational; not blocking yet)
- **Coverage gate 35%** (`--cov-fail-under=35` — do not confuse with the 80% target)
- `sazon migrate` smoke test (fresh SQLite)
- CHANGELOG discipline check (fails PR if `app/`, `scripts/`, `tests/`, or
  `.github/` changed but the root `CHANGELOG.md` did not — the step's own
  comment saying `app/CHANGELOG.md` is stale; the script greps `CHANGELOG.md`)
- **Anti-rule enforcement** (14 of 20 anti-rules enforced via tests in
  `tests/test_ci_anti_rules.py` + grep gates in `.github/workflows/ci.yml`)

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

1. `/opt/data/work/research-repos/saskia/AGENTS.md` — Saskia's build context (OPSEC-clean; **separate checkout on the host, NOT inside this repo** — path verified 2026-10-12)
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
| DB looks weird | `sqlite3 ~/Documents/aiw-restaurant/db.sqlite` then `.schema`; check schema version via `SELECT * FROM app_meta WHERE key='schema_version'` (NOT `PRAGMA user_version` — see rule 18) |
| Migration not applied | Check `CURRENT_SCHEMA_VERSION` in `app/rms/config.py` vs `app_meta` row (see rule 18); check `/tmp/sazon_backups/` for pre-migration backup |
| `/healthz` failing | Check `/healthz/deps` for env var issues; check `/healthz/backup` for backup age |
| Stuck on a task | Check `state/test-coverage-2026-10-04.json`, `IMPROVEMENT_BACKLOG.md`, `WHAT_NEXT.md` |
| Kernel died mid-session | Use `mcp__filesystem__read_file` instead of `terminal`; see `execute-code-ssh-mode` skill |
| Session_search returns nothing | Try different keywords; the session_id is in the Hermes runtime environment block |

---

## When in doubt

**Read these three docs first:**
1. This file (AGENTS.md)
2. `/opt/data/work/research-repos/saskia/AGENTS.md` (Saskia's context — separate host checkout)
3. `/opt/data/profiles/ivan/cache/scratch/sazon_migration/PLAN_INDEX.md` (migration plan)

**Then ask Iván** if it's still unclear. Don't guess on hard rules, security, or anything that touches Saskia's data.

