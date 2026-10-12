# AGENTS.md — Sazón app repo (build instructions)

Read this BEFORE writing code in this repo. It applies to the entire repository
unless a nested `AGENTS.md` in a subdirectory overrides it. For rules specific
to `app/rms/`, see [`app/rms/AGENTS.md`](app/rms/AGENTS.md).

---

## What this is

The Sazón RMS — restaurant management system, built for one bakery (Saskia's
bakery, Paraguay). Two deployment modes: local-first (operator's PC, SQLite,
`127.0.0.1`) and hosted (VPS at paragu-ai, Docker Swarm + Traefik, active URL
https://sazon-vps.paragu-ai.com). Render.com is DEPRECATED since 2026-09-24
(see `docs/operations/2026-09-24-deployment.md`).

**Audience:** any AI coding agent (Hermes, Claude Code, Codex, GitHub Copilot,
Cursor) working this repo. **Not** for human contributors — see `CONTRIBUTING.md`.

### Operator intent (read this first)

1. **True North (Sazon):** Saskia uses the app 5+ days/week without asking for help.
   That is the leading indicator for every other metric.
2. **"Done" = 6 of 6:** code merged + tests added + deployed via `sazon deploy` +
   Sentry alert wired + 24h no-rollback + post-deploy sanity check. "PR merged" is
   **2 of 6**, not done.
3. **Decision authority:** T1 = AI decides, T2 = AI decides + surfaces to the index,
   T3 = AI drafts + operator approves, T4 = operator only. Default for new work is T2.
4. **Shim is permanent:** `app/rms/costing.py` is back-compat. New code imports from
   `app.rms.sales.lifecycle` and `app.rms.profitability.cost` directly.
5. **Forward-only, fail-closed:** migrations, backups, deploys. No "I'll just rewrite
   the prod DB" paths.
6. **AI-improved AGENTS.md is worse (ETH Zurich empirical data, Aug 2026):**
   every change to this file needs operator review. Don't `git commit` AI-suggested
   rewrites without reading them.
7. **Don't repeat past pain:** [`.hermes/STATE.md`](.hermes/STATE.md) has the 5 P0s
   for the next 4 weeks. [`.hermes/2026-10-12-operator-intent-retrospective.md`](.hermes/2026-10-12-operator-intent-retrospective.md)
   is the 8-ask retrospective that explains the why behind every rule here.

---

## Build & test commands

```bash
# Install
uv sync                           # Python deps (NOT pip; do not add requirements.txt)
uv run pre-commit install         # one-time, installs the secret/commit gates

# Run tests
uv run pytest -q tests/test_X.py         # one file
uv run pytest -q -k "name"                # one test by name
uv run pytest -q -n 4                     # full suite, parallel (the CI incantation)
SASKIA_TEST_AUTH_DISABLED=1 uv run pytest -q --no-cov   # auth-gated tests bypassed

# Lint & format
ruff check .                       # must be clean before PR
ruff format .                      # auto-fix style
make check                         # the lightweight gate (ruff + arch + duplicates)
make ci                            # full test suite
make complexity                    # radon CC≤10 ceiling check

# Migration
sazon migrate                      # apply pending migrations
sazon migrate --dry-run            # preview
sazon rollback --to N              # undo last migration (rule 17 fail-closed)
```

> **If a command above doesn't exist or doesn't work, that is a bug in this file.
> Edit AGENTS.md in the same PR that fixes the command.**

---

## Project layout

| Path | What lives here |
|---|---|
| `app/rms/` | Domain models, business logic, helpers — see [`app/rms/AGENTS.md`](app/rms/AGENTS.md) |
| `app/routers/` | FastAPI route handlers (sync, NOT async — Rule 32) |
| `app/templates/` | Jinja2 templates; Spanish voseo copy per `app/docs/copy-vos.md` |
| `app/services/` | External integrations (R2 encrypted backup only — no other HTTP) |
| `app/auth.py` | Auth (`current_operator`, `current_user_id`) — NOT in `app/rms/` |
| `tests/` | pytest; `conftest.py` provides fixtures; `client_with_caja` is the auth-gated one |
| `app/rms/migrations/` | Schema migrations (forward-only; never edit a shipped one — Rule 14) |
| `scripts/` | One-shot ops scripts (seeding, audit) |
| `docs/` | Operations runbooks, audits, design docs |
| `.hermes/` | Agent-orient files (plans, archives, sibling notes) — not in git |
| `AGENTS.md` | This file |
| `app/CHANGELOG.md` | Auto-managed; never edit directly — Rule 35 |

**Do NOT touch:** `.venv/`, `__pycache__/`, `.ruff_cache/`, `*.py.tmp` scratch files at root.

---

## Boundaries

### Always
- Run `uv run pytest` and `ruff check .` before opening a PR.
- Update `app/CHANGELOG.md` for any change in `app/`, `scripts/`, `tests/`, `.github/`.
- Reference a `SASKIA-NNN` ticket in every PR title.
- Use Asunción timezone (`ASUNCION_TZ`) for all datetime math — Rule 20.
- Use `to_int_gs(Decimal(...))` for money-to-int conversion — never `int(Decimal(...))`.
- Use `apply_stock_delta()` for non-sale stock changes; `apply_sale()`/`void_sale()` for sale paths.
- Import from `app.rms.profitability.cost` and `app.rms.sales.lifecycle` directly; `app/rms/costing.py` is a permanent Sprint 2.3 re-export shim.

### Ask first
- New dependencies (Rule 26).
- DB schema changes (Rules 12-19).
- Auth, security, scope, or sharing changes.
- Anything that touches Saskia's data or workflow.
- Adding a new `AGENTS.md` in a subdirectory.
- Anything in `infra/`, `docker-stack.yml`, or VPS-facing config.

### Never
- `git push origin main` directly (Rule 36; PRs go through `gh pr create`).
- Edit a shipped migration (Rule 14; create a new one).
- Commit credentials, `.env`, or real customer data (Rule 27; pre-commit `check-no-secrets`).
- Bypass the pre-commit hook with `--no-verify`.
- `git merge -X ours` or `git merge -X theirs` on `app/rms/` (new Rule 38; SASKIA-211d).
- Add a second migration with the same number — coordinate via `app/rms/db.py` and announce in chat.
- AI-edit `AGENTS.md` without operator review (ETH Zurich: AI-improved files reduce task success).
- Auto-generate AGENTS.md via `/init` or similar — community data shows ~3% success regression.

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
8. **Every sale decrements stock.** When a sale is recorded, the system MUST write `StockMovement` rows for every recipe line of every product in the sale. The router in `app/routers/sales.py` (`sale_create`, `sale_create_multi`) delegates to `apply_sale()` in `app/rms/sales/lifecycle.py` (NOT `app/rms/costing.py` — that file is a 1.3 KB deprecated shim since the SASKIA-212 refactor), which is the SINGLE place that writes the audit row. The shim re-exports for back-compat; new code imports from `sales.lifecycle` directly. **The chain is locked by 3 tests in `tests/test_sale_create_writes_stock_movement.py`** (and 7 tests in `tests/test_stock_drop.py`). A 2026-10-07 review initially thought this rule was broken (router doesn't write `StockMovement` directly) — but it's correctly delegated to `apply_sale()`. The test file exists to prevent future refactors from breaking the delegation. **Do not move the StockMovement write into the router** — that creates two write paths and the migration-090 single-table consolidation comment in `costing.py` will warn against it.
9. **Negative stock is allowed** (kitchen reality > accounting purity) but red-flashes on dashboard.
10. **Cross-recipe BOM cycles raise `CycleInRecipeTree`**; UI shows error, never silently truncates.
11. **Auto-overwrite of recipes during re-import** requires confirmation modal showing diff; auto-backup before mutation.

### Migrations (8 sub-rules)

12. **No Alembic.** Hand-rolled versioned migrations in `app/rms/db.py` (117 total: 82 inline `_migration_NNN_*` functions, 35 as separate files in `app/rms/migrations/`; range 1..117, no gaps).
13. **Every migration is forward-only.** No `downgrade` functions.
14. **Never edit a shipped migration.** Create a new one. The old one is the persisted contract.
15. **Never renumber or reorder.** Version number is the contract. **No two worktrees may create a migration with the same number** — coordinate via `app/rms/db.py` and announce in chat. (Active conflict: as of 2026-10-12, `_119_recipe_photo_autolink.py` exists in `saskia-app` and `_119_seasonal_event.py` exists in `saskia-app-vaquita`; these need to be reconciled before any branch merge to main.)
16. **Migrations are atomic** (one transaction per migration).
17. **Pre-migration auto-backup is mandatory** to `/tmp/sazon_backups/<db>-pre-v<A>-to-v<B>.json.gz` (or equivalent). Implemented in `app/rms/db.py` `sync_backup_before_migration()` — runs before the first pending migration in `init_db()`. Uses `app/rms/backup.py::backup_database()` for the gzipped JSON+manifest. **Fail-closed by default**: if the backup fails, `init_db` raises unless `AIW_RMS_PROCEED_WITHOUT_BACKUP=1` is set. Locked by 3 tests in `tests/test_migration_safety.py` (`test_sync_backup_before_migration_writes_file`, `test_sync_backup_before_migration_can_be_restored`, `test_init_db_writes_pre_migration_backup_before_applying`).
18. **`app_meta` table is the source of truth** for the current schema state. The schema version is read from `app_meta(key='schema_version')` (set by `app/rms/db.py` during `init_db()`). `PRAGMA user_version` is NOT used (deliberate decision 2026-10-09 — see `docs/operations/2026-10-09-schema-version-source.md`). The in-app `CURRENT_SCHEMA_VERSION` constant in `app/rms/config.py` is the build's intended version; the `app_meta` row is the runtime's current version.
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
27. **Never commit credentials.** Pre-commit hook `check-no-secrets` blocks any staged file containing GitHub PAT shapes (`ghp_*`, `ghs_*`, `gho_*`, `ghu_*`, `github_pat_*`), `x-access-token:***` URLs, AWS access keys, JWTs, Supabase user-password patterns, or long `key=value` strings. Use BWS for secrets. See `scripts/check_no_secrets.py` and the `credential-redacted-grep` skill. **If you find a leaked credential: rotate first, then scrub the transcript with `scripts/redact_key.py`, then fix the leak path.**
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

### Merge discipline (1 new rule, 2026-10-12)

38. **No `git merge -X ours` or `-X theirs` on `app/rms/`.** When merge conflicts happen on these files, resolve manually, never take either side whole. The Sprint 2.3 shim was replaced with 776 lines of duplicate code via `-X ours`; locked by `tests/test_profitability_sales_split.py` (thin-shim assertion), but only AFTER the damage. If you must use `-X`, scope it to the file you actually know to be correct (not the whole tree).

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

**21. (NEW, 2026-10-12) Don't reference a real production DB path in any test fixture.** `tests/conftest.py` and every `tests/**/conftest.py` are CI-gated against the literals `AIW_SASKIA_DB_PATH` / `DATABASE_URL` / `/tmp/sazon_backups/` (allow-list: only the test-factory constructor). Sibling-suite FD-exhaustion (SASKIA-317) was caused by a fixture leaking connections to prod. Proposed test: `tests/test_no_prod_db_in_fixtures.py`.

See the **IDEATION_PLAN** (`/opt/data/profiles/ivan/cache/scratch/sazon_migration/migration_plan/IDEATION_PLAN.md`) for the long version with rationale.

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

## Before opening a PR

- [ ] `uv run pytest -q` passes (or the failing test is in the PR and marked xfail)
- [ ] `ruff check .` clean
- [ ] `ruff format --check .` clean
- [ ] `app/CHANGELOG.md` updated (Rule 35)
- [ ] PR title references SASKIA-NNN (Rule 37)
- [ ] New behavior has a regression test
- [ ] No secrets, `.env`, or real customer data in the diff (Rule 27)
- [ ] Pre-commit hooks pass: `uv run pre-commit run --all-files`
- [ ] If migration added: pre-migration backup test runs (Rule 17)
- [ ] If schema touched: `sazon migrate --dry-run` succeeds
- [ ] If you touched `app/rms/`: read [`app/rms/AGENTS.md`](app/rms/AGENTS.md) first
- [ ] If you added a nested `AGENTS.md`: confirm it inherits (delta-only, not a copy)

---

## Recovery & coordination

- **Worktree policy** (parallel sessions): see `docs/operations/worktree-policy.md`. Use git worktrees for concurrent work; don't share branches between sessions.
- **Sibling session coordination**: see `docs/operations/2026-10-04-sibling-session-coordination.md`. When multiple AI agents work the same repo in parallel, coordinate via the worktree policy and `.hermes/`. Plans go in `.hermes/plans/`, archives in `.hermes/archives/`.
- **Healthz contract**: see Hard Rule 34.
- **Locked hotfixes**: see above.
- **Cross-tool compatibility**: a 1-line `CLAUDE.md` containing `@AGENTS.md` lets Claude Code read this file as its project instructions. On Linux/macOS a symlink also works.

---

## Ticket convention

Tickets use the format `SASKIA-NNN` (e.g. `SASKIA-001`). 5-character
codes like `E1.S2` are for epic+story (e.g. `E3.S1` = Epic 3, Story 1).
File naming: `SASKIA-NNN-<short-slug>.md`.

The full epic plan (25 epics, 6 phases, ~268h) lives at
`docs/plans/2026-09-07-sazon-complete-epic-plan-v3.md`. Pick from
there.

---

## Cross-references

For deeper context, read these in order:

1. [`app/rms/AGENTS.md`](app/rms/AGENTS.md) — rules specific to `app/rms/` (money, units, time, recipe, stock, testing, migration, tooling)
2. `research-repos/saskia/AGENTS.md` — Saskia's build context (OPSEC-clean)
3. `app/docs/copy-vos.md` — UI copy rules (Paraguayan Spanish)
4. `docs/ux/redesign-prompt.md` — master redesign prompt (simplify visibility, never functionality)
5. `docs/operations/2026-10-04-sibling-session-coordination.md` — worktree policy
6. `docs/operations/2026-10-04-test-execution-plan.md` — test plan
7. `IMPROVEMENT_BACKLOG.md` — what to work next
8. `WHAT_NEXT.md` — shorter punchlist
9. `app/CHANGELOG.md` — release history

---

## When in doubt

**Read these three docs first:**
1. This file (AGENTS.md)
2. [`app/rms/AGENTS.md`](app/rms/AGENTS.md)
3. `docs/operations/2026-10-04-sibling-session-coordination.md`

**Then ask Iván** if it's still unclear. Don't guess on hard rules, security, or anything that touches Saskia's data.
