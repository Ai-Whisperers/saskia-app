# QA Hats — Sazón Test Strategy

**Date:** 2026-10-04
**Sister docs:**
- `docs/TEST_ARCHITECTURE.md` — 5 levels × 8 domains (L1-L5 × A-H)
- `docs/operations/2026-10-04-test-infrastructure-upgrade.md` — 4 pillars plan
- `docs/plans/2026-10-01-phase14-coverage-strategy.md` — coverage growth plan
- `docs/plans/2026-09-25-test-improvement-complete-catalog.md` — 309-line improvement catalog

**The premise:** A single "QA" hat doesn't cover what we have. the operator's tests need **12 distinct hats** — each with a mission, primary domains, owned responsibilities, and a wishlist of ideas. This file is the playbook.

---

## The 5 abstraction levels (from TEST_ARCHITECTURE.md)

| Level | Question it asks | Example |
|---|---|---|
| **L1 Domain** | "Does the BUSINESS RULE hold?" | `pedido_fulfill` decrements stock |
| **L2 Contract** | "Does the SHAPE stay correct?" | POST `/ventas` accepts the documented fields |
| **L3 Failure mode** | "Does it CRASH / HANG / LEAK?" | Handler doesn't 5xx on empty POST |
| **L4 Lifecycle** | "Does STATE advance correctly?" | DB migrations apply in order, idempotently |
| **L5 Operation** | "Does it RUN in our environment?" | Container starts, /healthz/db returns 200 |

## The 8 domains (from TEST_ARCHITECTURE.md)

| Letter | Domain | Current state |
|---|---|---|
| **A** | Money + i18n | 18 files / 180 tests — strongest |
| **B** | CRUD roundtrips | 24 files / 320 tests — strong |
| **C** | Auth + session | 16 files / 95 tests — solid |
| **D** | Sales + pedidos | 32 files / 410 tests — strongest |
| **E** | Reports + analytics | 21 files / 240 tests — gap: analytics.py 35% covered |
| **F** | UI / a11y / CSS | 38 files / 460 tests — gap: Safari, mobile, keyboard |
| **G** | DB schema + migrations | 22 files / 175 tests — gap: rollback path |
| **H** | Infra (deploy, cron, backup) | 35 files / 220 tests — gap: deploy script |

## The 12 hats

```
QA Engineer           ─ owner of all test domains; the executor
Performance Engineer  ── owns response times, queries, load
Security Reviewer     ─── owns auth, csrf, rate-limit, secrets
Migration Guardian     ─── owns schema, migrations, cross-dialect
Accessibility Reviewer ─── owns WCAG, keyboard, mobile, combos
SRE / Reliability     ─── owns health, deploy, backup, monitoring
Localization Copy     ─── owns Spanish voseo, Paraguayan Spanish, i18n
Analytics Reviewer    ─── owns dashboard, KPIs, daily/weekly/monthly
Operator (Ivan)       ─── owns deploy, env vars, cron safety
Code Quality          ─── owns abstraction, factories, fixtures
Business SME (the operator) ─── owns field reality, user stories, manual QA
Doc Curator           ─── owns AGENTS, README, user-guide, decisions
```

---

# Hat 1 — QA Engineer (the test-writer)

> "Make failures obvious, fast, and actionable."

**Primary domains:** A (Money + i18n), B (CRUD roundtrips), C (Auth), D (Sales + pedidos)
**Owns:** test_archaeology, fixture_design, coverage_growth
**Persona:** Writes the actual tests. Lives in `tests/`. Reads production code to figure out edge cases.

## This week (top 5)

1. **Build `scripts/gen_route_smoke.py`** (4h) — auto-generate a parametrized smoke test for every `@router.{get,post,put,delete,patch}`. Closes 230-route coverage gap from §5 of TEST_ARCHITECTURE.md.
2. **Migrate the top 5 duplicated `_seed_*` helpers** (3h) — `_seed_sale` (5 copies), `_seed_basic` (3), `_seed_product` (3), `_seed_customer` (2), `_seed_pedido` (2). Use the migration map from `scripts/inventory_seed_helpers.py`.
3. **Add 4 new invariants to `tests/_lib/invariants.py`** (1h) — `audit_log_present_for`, `recipe_cost_within_margin`, `redirect_target`, `no_js_errors` (already shipped in commit `95d1619`). Use them in 5 existing tests as proof.
4. **Promote `tests/flows.py` helpers into conftest fixtures** (2h) — pick `create_pedido`, `void_sale`, `restock`, `eod_checklist_complete` first. Migrate 5 tests to use them.
5. **Build `tests/test_route_smoke_generated.py` first cut** (3h) — parametrized over 30 routes, one router at a time, validate the approach.

## This quarter (medium)

- **Extract business logic from top 10 routers into `app/services/`** (24h) — see Phase 4 in the test-infrastructure plan. Coverage +15%.
- **Tier 5 DB-bound hypothesis tests for `app/rms/analytics.py`** (12h) — close the "35% covered" gap in Domain E. Use `hypothesis` with seeded world.
- **Add `tests/test_model_invariants.py`** (6h) — auto-generate `@given` tests over SQLAlchemy column types (non-negative ints, enum values, FK cascades).
- **Property tests for recipe costing** (4h) — `compute_cost(recipe)` over varying line counts, qty ranges, ingredient availability.

## Backlog (long-term)

- **Universal test pattern for "session-spanning" assertions** — single-day flows already work; multi-day continuity (demand forecast uses observed sales span; freshness uses receipt dates). One flow spanning 3 frozen days would lock in the date math end-to-end.
- **Test-time budget enforcement** — fail the test run if any test takes >5s (without marking it `@pytest.mark.slow`). Push for module-scoped fixtures to keep most tests <100ms.
- **Auto-detect `assert status == 200` followed by `assert "x" in body`** patterns — extract into `tests/_lib/asserts.py:assert_page_ok(r, *needles)`.
- **Coverage floor in CI as a hard gate** — currently `--cov-fail-under=35` (advisory); bump per the Phase 14 plan: 35% → 45% → 60% → 80%.
- **Property tests the way `test_money.py` does it** for `recipe_polymorphic.py`, `units.py`, and `costing.py`. Already done for money; copy the pattern.

## Ideas to explore

- **Mutation testing with `mutmut`** — does the test suite catch a randomly introduced bug? If yes, we're tight. If no, we have zombie tests.
- **Spectre-style flag/switch fuzzing** — every feature flag flips; every test should still pass.
- **`pytest-snapshot` for HTML output** — detect visual regressions on response bodies without a browser.
- **Coverage of branch edges, not just lines** — `--cov-branch` catches guards that have a `True` path tested but the `False` path not.
- **Tag a test as "operator-visible"** — `pytest.mark.operator` — only this subset is run in the "manual QA" CI step.

## Counter-hats to invite

- **Performance Engineer** — review the new tests for accidentally N+1 queries.
- **Migration Guardian** — review the seed migrations for schema coupling.

---

# Hat 2 — Performance Engineer

> "Make 1s stay 1s at 100× load."

**Primary domains:** E (Reports + analytics), H (Infra)
**Owns:** perf_budgets, load_testing, db_query_profiles
**Persona:** Profiles SQL queries, sets response-time budgets, builds `loads()` fuzzers.

## This week

1. **Profile `app/rms/analytics.py`** (4h) — use `py-spy` or `cProfile` on the dashboard endpoints. Find the top 5 N+1 queries. Add `n_queries` fixture that uses `event.listen(engine, "before_cursor_execute")` to count SQL statements.
2. **Add `tests/test_dashboard_perf_budget.py`** (3h) — `@pytest.mark.perf` — response time test (E2.S2: dashboard <500ms; analytics <2s). Currently marked but no real assertion.
3. **Establish baseline per incident**. The `test_dashboard_perf_budget.py` is advisory today. Wire it into CI with hard limits.

## This quarter

- **`tests/test_perf_regression.py`** (6h) — snapshot timings on every test class; fail if any regresses 20%+ week-over-week.
- **`locust` load test for `/healthz` + `/login`** (12h) — measure the throughput under 100 concurrent users. Run nightly in CI.
- **DB query profiler for the slow path** (8h) — `app/services/perf_logger.py` middleware that logs every query >50ms to a separate file.
- **Allergen guard perf** (4h) — POS sale with allergen check should be <200ms. Profile the join.

## Backlog

- **Indexing review** — find the missing indices. EXPLAIN QUERY PLAN on every report.
- **JIT compilation of `app/rms/costing.py`** — Python-side, with `@functools.cache`.
- **Vectorized aggregation** — for the monthly sales report, currently loops in Python.
- **Async reporting endpoints** — `/reportes/mensual/{date}` returns a job_id; frontend polls. Skip if it costs more than it saves.
- **Static asset CDN** — currently every CSS/JS reload hits the origin.

## Ideas to explore

- **Track test time per file** — `pytest --durations=0` and dump to `state/test-timings.json`. Diff week-over-week; flag regressions.
- **`pytest-benchmark`** for micro-benchmarks — `compute_cost(recipe_with_5_lines) < 50ms` becomes a tracked invariant.
- **`EXPLAIN QUERY PLAN` in tests** — assert that a hot query uses the index, not a table scan. Catches regressions when migration adds a column without index.
- **Tail latency (p95/p99) test** — single test in CI: 1000 sales, measure p95 <500ms.

## Counter-hats to invite

- **Migration Guardian** — check that new indices exist for slow queries.
- **Data Quality Reviewer** — ensure perf numbers don't hide data drift.

---

# Hat 3 — Security Reviewer

> "Make breaches hard and recoverable."

**Primary domains:** C (Auth + session), H (Infra), A (Money)
**Owns:** auth_tests, csrf_testing, secrets_audit, supply_chain
**Persona:** Reads OWASP, hunts for CSRF gaps, audits secrets in CI.

## This week

1. **Audit `tests/test_csrf.py` against OWASP** (2h) — currently tests the missing-token case. Add: token-after-logout, token-after-session-rotation, token-after-timeout, double-submit-cookie pattern. Read OWASP CSRF Cheat Sheet.
2. **`tests/test_rate_limit_writes.py` + `tests/test_rate_limit_reads.py`** (1h) — these exist but check rate-limit on the login. Add: rate-limit on `POST /pedido`, `/ventas`, `/ventas/{id}/void`, `/eod/completar`.
3. **`tests/test_secrets_in_repo.py`** (3h) — scan the repo for AWS keys, Stripe keys, GitHub PATs (already a pre-commit hook; expand it). Add a test that asserts the hook is wired in `.pre-commit-config.yaml`.

## This quarter

- **`tests/test_auth_matrix.py`** (8h) — every route + every role (admin, operator, anon). Currently only one role (admin). Tests/check_role_gates.
- **Brute-force enumeration of usernames** (4h) — `/login` should rate-limit by IP AND username. Currently rate-limits only by IP.
- **CSRF + auth state-transition test** (4h) — log in, rotate token, attempt POST → 403. Log out, attempt POST → 403.
- **Session fixation test** (4h) — session id should rotate on login.
- **Backups: are they encrypted at rest?** (4h) — R2 backups use Fernet. Test the round-trip: encrypt → upload → download → decrypt.
- **Supply chain audit** (6h) — `pip-audit` weekly in CI, fails on CVSS ≥7.
- **`tests/test_audit_log_pii.py`** (4h) — every log line must be PII-clean. Regex-test the production loguru format string.

## Backlog

- **CSP (Content Security Policy) headers** — test for nonce-based CSP, no unsafe-inline.
- **HSTS preload** — `/healthz` should advertise HSTS.
- **Subresource Integrity (SRI)** for static assets.
- **2FA / TOTP** — currently not implemented. Add to wishlist (deferred).
- **Pen-test with `zap-baseline.py`** — OWASP ZAP weekly scan.

## Ideas to explore

- **`tests/test_injection_payloads.py`** — SQLi/XSS/path-traversal probes against every `@router.post`/`.get`. Library: `foolbox`.
- **`tests/test_session_hijack.py`** — assume the worst: copy cookie to another IP, expect rejection.
- **`tests/test_secrets_leak_via_lighthouse.py`** — Lighthouse audit on every deploy.
- **Audit every error message for info leak** — production errors must not echo SQL/paths.
- **`tests/test_csrf_cache_key_breakdown.py`** — already in TEST_ARCHITECTURE.md gap W1 — the lint regression class.

## Counter-hats to invite

- **SRE** — back the secret rotation cadence.
- **Operator** — verify BWS is the only secret source.

---

# Hat 4 — Migration / Schema Guardian

> "Make DB schema a living, testable artifact."

**Primary domains:** G (DB schema + migrations), B (CRUD roundtrips)
**Owns:** migration_tests, schema_drift, dialect_safety
**Persona:** Reviews every PR that touches `app/rms/db.py`, `app/rms/migrations/`, models.

## This week

1. **Migration cross-dialect rewrite** (already started in PR #46) — the 4 confirmed-broken migrations (65, 69, 74, 82) are now fixed. Continue auditing the remaining 9 that have manual `if/else` branches.
2. **`tests/test_migration_dialect_parity.py`** (4h) — for every migration that has SQLite + Postgres variants, assert that `init_db()` produces the same schema on both dialects. Use `testcontainers[postgresql]` (already in pyproject).
3. **Add a test for the `_serial_pk_type` helper** (1h) — verify the helper returns the right PK syntax per dialect, with each column type.

## This quarter

- **`tests/test_migration_roundtrip_each_version.py`** (16h) — for every schema version N (1 to 98), apply migrations 1..N, dump the schema, restore from the dump, verify it's identical. This is the boot-at-every-version smoke from §2.3 of `2026-09-25-test-suite-e2e-strategy.md`.
- **`tests/test_migration_data_preservation.py`** (8h) — seed data at vN, upgrade to vN+1, assert data shape is preserved (column renames don't lose values).
- **`tests/test_migration_no_partial_apply.py`** (already partial) — extend to all migrations.
- **`tests/test_lifespan_migrations.py`** (already exists) — extend to all migrations.
- **Schema diff viewer** (12h) — when 2 migration files change in the same PR, fail with a side-by-side diff of the schema.

## Ideas to explore

- **`tests/test_migration_index.sql`** — assert every foreign key has an index. Checks.
- **Auto-generate `test_migration_roundtrip_each_version.py`** — the test loop is uniform, the only depends on the migration registry. Use `migration_registry` from `db.py`.
- **PR-time migration review checklist** — every PR must declare which migrations it touches + which other migration tests need updating.
- **Migration compatibility matrix** — for every model, which SQLite version? which Postgres version? Track in `app/rms/migrations/_COMPAT.md`.
- **`tests/test_db_dialect_compat.py`** — every query in production code must work on both SQLite + Postgres. Audit the 1,500 query sites.

## Counter-hats to invite

- **QA Engineer** — review the schema-related tests.
- **Data Quality Reviewer** — verify migration preserves data semantics, not just column shapes.

---

# Hat 5 — Accessibility / UX Reviewer

> "Make the app usable by everyone."

**Primary domains:** F (UI / a11y / CSS), C (Auth + session)
**Owns:** wcag_compliance, keyboard_flows, mobile_test
**Persona:** Tests with keyboard only, with `prefers-reduced-motion`, with screen readers.

## This week

1. **WCAG AA compliance audit** (4h) — currently `tests/test_wcag_aa_compliance.py` exists. Run it; collect the violations; create a Gantt chart of fixes. Add 5 more pages to the audit.
2. **`tests/test_keyboard_only_flows.py`** (3h) — login, sale, pedido, void, all without a mouse. Every form should be tab-navigable, every button should be Enter-activatable, every modal should trap focus.
4. **Aria + 5 more dialog patterns** — the 38 UI tests should expand to 50.

## This quarter

- **`tests/test_screen_reader_compatibility.py`** (8h) — NVDA on Windows. ARIA labels match visible text. Landmarks present on every page.
- **`tests/test_reduced_motion.py`** (4h) — `@media (prefers-reduced-motion: reduce)` honored. No animation on login redirect.
- **`tests/test_color_contrast.py`** (4h) — every text/background combo meets 4.5:1 (3:1 for large text). Already partial in WCAG tests; expand.
- **`tests/test_focus_indicators.py`** (3h) — every interactive element has a visible focus ring. No `outline: none` without `:focus-visible` replacement.
- **Mobile-first responsive tests** (12h) — every page tested at 360px, 768px, 1024px, 1440px. Currently tested at 1280px only.
- **Touch target size tests** (8h) — every tap target ≥44px (iOS) or ≥48px (Android). Some buttons may be 36px.

## Backlog

- **`tests/test_safari_specific.py`** (12h) — Safari CSS differs from Chromium. Test on BrowserStack.
- **`tests/test_ie11_compatibility.py`** — defer (she's on Chrome/Firefox).
- **Print stylesheet test** (3h) — reports print correctly on paper.
- **High-contrast mode test** (3h) — `prefers-contrast: more`.
- **Internationalization for screen readers** (6h) — Spanish voseo pronounces correctly.

## Ideas to explore

- **Axe-core integration with Playwright** — `axe-playwright-python` for automated a11y on every page.
- **Storybook Lite** — component-level a11y testing. Currently we test pages, not components.
- **`tests/test_dark_mode.py`** — add dark-mode toggle, test contrast in dark mode.

## Counter-hats to invite

- **Localization Copy Reviewer** — Spanish ARIA labels should match visible text.
- **QA Engineer** — review the Playwright flows for keyboard coverage.

---

# Hat 6 — Production Reliability Engineer (SRE)

> "Make incidents short and recovery automatic."

**Primary domains:** H (Infra)
**Owns:** healthz_alerts, backup_restore, deploy_safety, monitoring
**Persona:** Builds deploy dry-runs, tests restore drills, owns the alert escalation.

## This week

1. **Test the deploy script** (3h, S priority) — `scripts/deploy.sh` has no test. Build `tests/_scripts/test_deploy_dry_run.py` with a sandbox mode. Closes TEST_ARCHITECTURE.md gap G2.
2. **Backup restore drill** (4h, M priority) — `tests/test_r2_backup.py` tests artifacts; no test boots the app against a restored DB. Add: take backup → wipe DB → restore → assert app starts → assert critical data present.
3. **Health check end-to-end** (2h) — `/healthz` returns 200 with valid DB; `/healthz/db` returns 200 even with bad config; `/healthz/deps` returns 503 when DB is down. UptimeRobot probe every 5 min.

## This quarter

- **`tests/test_failure_injection.py`** (16h) — fail every external dependency in turn: Neon (DB), Supabase (auth), Cloudflare (CF tunnel), R2 (backups). Assert the app fails gracefully.
- **`tests/test_alerting.py`** (8h) — every health check failure fires a corresponding alert. Use a webhook capture.
- **Backup restore cadence** (4h) — every Monday, restore last Sunday's backup to a sandbox; assert critical queries return expected values.
- **`tests/test_chaos_monkey.py`** (12h) — kill the app mid-request; assert it restarts without losing data. (SQLite WAL mode + connection cleanup.)
- **`tests/test_load_balancer_failover.py`** (8h) — when Docker Swarm reschedules, requests don't drop.

## Backlog

- **Multi-region backups** — currently single R2 bucket. Add: S3 mirror in different geography.
- **Disaster recovery RTO/RPO documentation** — what's the recovery time objective? What's the recovery point objective? Test by running the disaster scenario.
- **`tests/test_graceful_shutdown.py`** — SIGTERM during a request: request completes, then shutdown. Don't drop the user's sale.
- **Cron monitoring** — every cron has a documented "if missed, raise" alert.
- **Log aggregation** — currently single-file loguru; multi-host crashes. Use Loki or Vector.

## Ideas to explore

- **`tests/test_pgbouncer_failover.py`** — currently direct connection. Add connection pooling + failover.
- **`tests/test_dns_failover.py`** — when Cloudflare DNS is down, requests still serve from cached responses.
- **Active-passive Postgres failover** — Neon supports this; add the test.
- **`tests/test_observability_health.py`** — the Sentry + Resend integration should be tested end-to-end.

## Counter-hats to invite

- **Operator** — verify env vars are correct for backup auth.
- **Security Reviewer** — secrets in backups must be encrypted at rest.

---

# Hat 7 — Localization & Copy Reviewer

> "Make Spanish (voseo) feel native, not translated."

**Primary domains:** F (UI / a11y / CSS), D (Sales + pedidos)
**Owns:** copy_i18n, guarani_strings, locale_consistency
**Persona:** Reads all UI strings, hunts for Argentine/Mexican slips, audits Guaraní translations.

## This week

1. **Copy audit** (2h) — read every string in `app/docs/copy-vos.md`. Spot-check 10 random UI pages. Look for:
   - Argentine `vos sos/tenés` (we want `vos sos/tenés` Paraguayan)
   - Mexican `ustedes`
   - English-only strings
   - Wrong gender agreement
2. **`tests/test_copy_voz.py`** (3h) — static check: scan every Jinja template for forbidden words (`salvá`, `podés`, `tenés` outside Paraguay, etc.). AGENTS.md rule 5 + 6.
3. **`tests/test_currency_format.py`** (3h) — Gs. always formats as `1.234` (dot thousands, no decimals). Currently in `test_money.py`; expand.

## This quarter

- **Guaraní strings audit** (8h) — the app has some Guaraní strings (e.g. product categories). Audit for grammar correctness.
- **`tests/test_date_format.py`** (4h) — Paraguayan date format: `dd/mm/yyyy`. Currently partial.
- **`tests/test_number_format.py`** (3h) — Paraguayan number convention. Currently local dates, expand.
- **`tests/test_phone_format.py`** (3h) — Paraguay phone format: `+595 9XX XXXXXX`. Currently local.
- **`tests/test_address_format.py`** (3h) — Paraguayan address: street, number, neighborhood, city. Currently local.
- **`tests/test_currency_drift_lint.py`** (already exists) — extend to all templates.
- **Audio prompt localization** (6h) — the speech-to-text should support Guaraní voice.

## Backlog

- **`tests/test_email_format.py`** (3h) — Paraguay phone in email signature.
- **Translation memory** — track every translation decision in a translation memory file.
- **Glossary** — `docs/operations/glossary.md` — canonical translations for technical terms.
- **`tests/test_error_message_clarity.py`** — error messages should be in plain Spanish, not English.

## Ideas to explore

- **Translation workflow** — set up a translation pipeline (Pootle/Loci). Currently we manually edit copy-vos.md.
- **Quality gate on copy changes** — every PR that touches copy-vos.md must pass a Spanish grammar checker (languagetool-python).
- **`tests/test_copy_in_template.py`** — assert no string in a template is missing from copy-vos.md.
- **A/B test for voseo vs tuteo** — measure which one the operator prefers.

## Counter-hats to invite

- **Business SME (the operator)** — she's the only one who can validate "nativo".
- **Accessibility Reviewer** — Spanish ARIA labels should be consistent with visible text.

---

# Hat 8 — Data Quality / Analytics Reviewer

> "Make numbers in reports match reality."

**Primary domains:** E (Reports + analytics), A (Money + i18n)
**Owns:** analytics_tests, report_reconciliation, data_drift
**Persona:** Spent a week reconciling reports against Excel. Hunts for `Decimal(inf)` and `int(inf)`.

## This week

1. **Reconciliation review** (3h, Closes G1/G4 from TEST_ARCHITECTURE.md) — `app/rms/analytics.py` is 35% covered. The `int(inf)` bug was the tip. Audit the 7 DB-bound code paths: stock_turnover, batch_stock_turnover, retention_curves, demand_forecast, food_cost_variance, prime_cost, menu_engineering.
2. **`tests/test_analytics_db_seeded_phase14_tier5.py`** (4h) — already exists, but expand: each DB-bound code path gets a property test (Hypothesis seeded world).

## This quarter

- **Per-report reconciliation** (8h) — every report has a test that asserts the report's number matches a hand-calculated expected value. Currently partial; expand to daily/weekly/monthly close.
- **`tests/test_daily_summary_reconciliation.py`** (4h) — daily summary reconciles with seeded sales. Currently exists but partial.
- **`tests/test_insights_perf.py`** (3h, already exists) — assert insights load in <2s with 100k rows.
- **`tests/test_report_data_consistency.py`** (4h) — cross-report consistency: weekly = 7× daily; monthly = 4-5× weekly.
- **`tests/test_dashboard_kpi_correctness.py`** (3h) — each KPI has a hand-calculated expected value.

## Backlog

- **Time-of-day heatmap test** (4h) — currently untested. Every hour should aggregate.
- **Per-customer reorder test** (4h) — UI only. Add DB test.
- **`tests/test_export_correctness.py`** (4h) — CSV/XLSX exports should match the on-screen data.
- **`tests/test_audit_log_pii.py`** (4h) — every log line must be PII-clean. (also under Security)
- **`tests/test_drift_detection.py`** (8h) — between report run and report open, did the data change? Catch stale reports.

## Ideas to explore

- **`tests/test_seed_then_report_reconciliation.py`** — seed world → run report → assert every cell matches hand-calc.
- **`tests/test_concurrent_report_consistency.py`** — two clients running the same report concurrently get identical numbers.
- **Reconciliation as a property test** — given any seeded world, the report's numbers should match a closed-form expression.
- **Daily export reports to CSV** — for manual verification (operator runs weekly).

## Counter-hats to invite

- **Performance Engineer** — analytics must stay fast.
- **Migration Guardian** — analytics queries must survive schema changes.

---

# Hat 9 — Operator (Ivan, the deployer)

> "Make shipping painless."

**Primary domains:** H (Infra)
**Owns:** deploy_dry_run, env_audit, cron_safety
**Persona:** Owns the live VPS at `sazon-vps.paragu-ai.com`. Tests every deploy manually.

## This week

1. **Dry-run deploy script** (3h) — `tests/test_deploy_dry_run.py` should pass without the script calling. Closes G2.
2. **Env var audit** (2h) — assert every env var in `render.yaml` (legacy) and Docker Swarm config has a BWS counterpart. Add `tests/test_env_audit.py`.
3. **Cron safety test** (3h) — every cron has a "what if it fails" alert. Currently partial; expand to all cron jobs.

## This quarter

- **`tests/test_deploy_safety.py`** (8h) — every deploy step has a smoke check before the next step. Currently none.
- **`tests/test_rollback_safety.py`** (8h) — every deploy has a rollback path. Test it.
- **`tests/test_bws_secret_rotation.py`** (4h) — secrets can be rotated without restart. Test the rotation flow.
- **`tests/test_docker_swarm_failover.py`** (8h) — when one node fails, the service moves to another.
- **`tests/test_cloudflare_tunnel_failover.py`** (4h) — when CF tunnel is down, requests still serve from the origin.

## Backlog

- **`tests/test_uptime_robot_setup.py`** (3h) — every protected route has a UptimeRobot monitor. Already partial.
- **`tests/test_healthz_alerts.py`** (4h) — every health check failure fires an alert.
- **Operator dashboard** (16h) — single page showing: deploy status, cron status, backup status, alert status.
- **Post-mortem template** (4h) — every incident gets a post-mortem. Track in `docs/post-mortems/`.

## Ideas to explore

- **`tests/test_dns_failover.py`** — when Cloudflare is down, requests still serve.
- **`tests/test_certificate_rotation.py`** — TLS cert rotates without downtime.
- **`tests/test_database_failover.py`** — Neon failover doesn't lose data.
- **Operator runbook** — `docs/operations/operator-runbook.md` — every common operator task has a step-by-step.

## Counter-hats to invite

- **SRE** — back the operator on incident response.
- **Security Reviewer** — verify secret rotation cadence.

---

# Hat 10 — Code Quality / Refactorer

> "Make the next change small."

**Primary domains:** B (CRUD roundtrips), F (UI / a11y / CSS), all
**Owns:** abstraction_layer, duplication_hunt, test_smell_cleanup
**Persona:** Lives in `tests/factories.py`, `tests/conftest.py`, `tests/_lib/`. Refactors with care.

## This week

1. **Unify the two seed systems** (4h, Closes W1 from `2026-09-25-test-suite-e2e-strategy.md`) — 30 unique `_seed_*` helpers across 35 files. Move bodies to `tests/seeders.py` (new file). Replace call sites with `qseed("scenario_name")`. Delete the private helpers.
2. **Edge-case factories** (4h, Closes A2 from `2026-09-25-test-improvement-complete-catalog.md`) — add `make_recipe(with_n_lines=5, with_low_margin=True)`. Use builder pattern.
3. **Promote `flows.py` helpers to conftest fixtures** (4h) — already started.

## This quarter

- **Refactor 17 files > 500 lines** (16h) — split into focused test files. Top offenders: `test_analytics_properties_phase14_tier4.py` (731), `test_ui_components.py` (715), `test_saskia_r2_data_models.py` (703).
- **Merge 42 files < 50 lines** (8h) — group by topic, save LOC.
- **Builder composition sugar** (8h, Closes A2) — `make_catalog(scenario)`, `make_sellable(scenario, price=...)`.
- **`api_crud()` generic helper** (6h, Closes B2) — loops create/read/update/delete across 37 JSON routes.
- **Factory traits/mixins** (6h, Closes A5) — `make_ingredient(traits={"low_stock": True})`.

## Backlog

- **Polyfactory evaluation** (4h) — adopt for value objects, keep hand-rolled for business objects.
- **Module-scoped seed with per-test rollback** (16h, Phase 3 D1) — test time 15m → 6m.
- **CRUD roundtrip generator** (4h, Phase 3 A3) — auto-generate for 20 most-used CRUD endpoints.
- **Test pattern extraction** (8h) — find every `assert r.status_code == 200, f"..."` and extract into `assert_page_ok()`.

## Ideas to explore

- **`tests/_lib/` as the public abstraction API** — anything used by >3 tests goes here. Internal helpers stay local.
- **Test decorators for common setups** — `@with_sale`, `@with_pedido`, `@with_low_stock`.
- **Test class hierarchy** — `class MoneyTest(DecimalTest)` etc. for shared setup.
- **Auto-detect test smells** — `pytest-smell` or custom linter.

## Counter-hats to invite

- **QA Engineer** — review the refactor for test-coverage loss.
- **Migration Guardian** — review the refactor for schema-coupling.

---

# Hat 11 — Business / Domain SME (the operator)

> "Make tests match reality of a panadería."

**Primary domains:** D (Sales + pedidos), E (Reports + analytics), F (UI / a11y)
**Owns:** user_story_testing, manual_qa, field_bugs
**Persona:** Runs the bakery. Reads reports daily. Has opinions on UX. Doesn't write code.

## This week

1. **Manual smoke test** (1h) — log in to https://sazon-vps.paragu-ai.com, perform the daily routine: open dashboard, register a sale, register a pedido, complete EOD. Note any glitch.
2. **Review the user-guide** (2h) — `docs/user-guide/` — 20 chapters, each page has the actual UI. Anything wrong? Submit a feedback note per chapter.

## This quarter

- **Field bug reports** (90 days) — every time something doesn't match her workflow, file a bug in `installer/ROUND-N-NOTES.md`. Round 1, Round 2, etc.
- **User story testing** — write user stories like the Round 1 QA plan (`docs/qa/round1-qa-plan.md`) and ask the dev to add automated coverage for each AC.
- **Field reality check** — every quarter, do a 3-hour session where she uses the app while the dev watches. Note every "wait, what does this mean?" moment.

## Backlog

- **A/B test on common paths** — try one UI in production for 2 weeks; revert if adoption drops.
- **Wishes / needs backlog** — `docs/wishlist/raw/` — every UX idea she has.
- **Co-write the user-guide** — she writes the "what to click" steps; the agent writes the "what the code does" parts.

## Ideas to explore

- **Wizard of Oz tests** — for new features, she describes the workflow; the agent builds it; she validates.
- **Beta tests** — pre-release features go to her sandbox first.
- **Weekly office hours** — 30 min/week video call to discuss UX.

## Counter-hats to invite

- **UX Reviewer** — translate her feedback into testable patterns.
- **Documentation Curator** — turn her feedback into user-guide updates.

---

# Hat 12 — Documentation Curator

> "Make context findable."

**Primary domains:** None — Doc Curator cross-cuts all
**Owns:** docs_organization, test_docstrings, decision_log
**Persona:** Reads every doc, finds drift, cleans up. Lives in `AGENTS.md`, `docs/`.

## This week

1. **AGENTS.md review** (2h) — at 179 lines, it's getting long. Extract detailed rules to `docs/REFERENCE.md`. Keep `AGENTS.md` as a 70-line TOC.
2. **TEST_ARCHITECTURE.md update** (1h) — last updated 2026-10-01; today is 2026-10-04. Add the new files from this session's work (`inventory_seed_helpers.py`, expanded invariants).
3. **user-guide verification** (3h) — every chapter in `docs/user-guide/` (20 files). Verify the screenshots, links, steps. Step-by-step.

## This quarter

- **Decision log** (8h) — every ADR goes to `docs/decisions/`. Currently 6 of them. Format: `ADR-NNN-<short-slug>.md`.
- **Wishlist triage** (weekly, 30 min) — move items from `raw/` to `triaged/` or `rejected/` per the cadence in `wishlist/README.md`.
- **Cross-reference audit** (4h) — every doc reference should resolve. Use `scripts/check_doc_links.py`.
- **Operation docs review** (4h) — `docs/operations/` has 50+ files. Verify each is still relevant. Archive stale ones.

## Backlog

- **Test docstrings** (16h) — 1,450 of 2,018 tests have docstrings. Add docstrings to the remaining 568.
- **Code comment review** (8h) — every comment is a doc string that didn't make it.
- **Glossary** (4h) — `docs/operations/glossary.md` — every term, one place.
- **Onboarding doc** (8h) — for a new dev joining. Currently AGENTS.md; expand to dev/handoff docs.

## Ideas to explore

- **Auto-generate API docs from FastAPI** — already has `/docs` and `/redoc`. Make sure tests cover those endpoints.
- **Doc drift detector** — every PR that changes production code must update the relevant doc. CI-enforced.
- **Living documentation** — every test name becomes a doc section. Test results update docs.

## Counter-hats to invite

- **QA Engineer** — test docstrings make tests self-documenting.
- **Business SME (the operator)** — her feedback becomes user-guide updates.

---

# Hat × Domain matrix

```
Hat                                      |  A |  B |  C |  D |  E |  F |  G |  H
-----------------------------------------|----|----|----|----|----|----|----|----
QA Engineer                              |  ● |  ● |  ● |  ● |    |    |    |
Performance Engineer                     |    |    |    |    |  ● |    |    |  ●
Security Reviewer                        |  ● |    |  ● |    |    |    |    |  ●
Migration / Schema Guardian              |    |  ● |    |  ● |    |    |  ● |
Accessibility / UX Reviewer              |    |    |  ● |    |    |  ● |    |
SRE / Reliability                        |    |    |    |    |    |    |    |  ●
Localization Copy Reviewer               |    |    |  ● |  ● |    |  ● |    |
Data Quality / Analytics Reviewer        |  ● |    |    |    |  ● |    |    |
Operator (Ivan)                          |    |    |    |    |    |    |    |  ●
Code Quality / Refactorer                |    |  ● |  ● |  ● |    |  ● |    |
Business SME (the operator)                    |    |    |    |  ● |  ● |    |    |
Documentation Curator                    |    |    |    |    |    |    |    |
```

---

# Cross-cutting concerns (every hat needs these)

| Concern | Owner | Wishlist |
|---|---|---|
| **Money rule 4** (int in DB) | QA + Analytics + Security | Any hat touching money columns must assert int. |
| **Spanish voseo** | Localizer + UX | Every string must be Paraguayan Spanish, not Argentine. |
| **Backup safety** | SRE + Operator | Every destructive op must trigger a backup. |
| **Audit log coverage** | QA + Security | Every state change must leave a log. |
| **Schema safety** | Migration Guardian + QA | Every schema change must survive cross-dialect. |
| **CSRF / auth** | Security + UX | Every form must be CSRF-protected, keyboard-navigable. |

---

# What this doc is

- **Not** a backlog of work items (that's `IMPROVEMENT_BACKLOG.md`).
- **Not** a test plan (that's `docs/qa/round1-qa-plan.md`).
- **Not** a coverage strategy (that's `docs/plans/2026-10-01-phase14-coverage-strategy.md`).

This is the **hat playbook**: who's responsible for what, with concrete wishlists per hat. If a gap appears, add it to the relevant hat's wishlist.

---

# Open questions

1. **Single owner or shared?** — Many hats have overlap (e.g., QA + Code Quality on factories). Default: primary hat owns, others review.
2. **Cadence per hat** — How often does each hat "fire"? Weekly, monthly, per-PR?
3. **the operator's role** — She's the Business SME hat, but also the user. Decision: hat receives the user-aspective; her feedback goes to the QA hat.
4. **Wishes vs reality** — some wishlists are wishful (e.g., full mutation testing). Phase by impact.

---

# Refs

- `docs/TEST_ARCHITECTURE.md` — 5 levels × 8 domains (L1-L5 × A-H)
- `docs/operations/2026-10-04-test-infrastructure-upgrade.md` — 4 pillars plan
- `docs/plans/2026-10-01-phase14-coverage-strategy.md` — coverage growth plan
- `docs/plans/2026-09-25-test-improvement-complete-catalog.md` — 309-line improvement catalog
- `docs/plans/2026-09-25-test-suite-e2e-strategy.md` — E2E test plan
- `docs/plans/2026-09-25-e2e-gap-analysis.md` — gap analysis by route
- `docs/qa/round1-qa-plan.md` — Round 1 QA plan (T1–T8, Q1, Q2, Q3)
- `docs/operations/2026-10-04-test-infra-one-pager.md` — one-pager of the upgrade plan
- `scripts/inventory_seed_helpers.py` — seed helper migration map
- `tests/_lib/invariants.py` — invariant assertions
- `tests/factories.py` — entity factories
- `tests/flows.py` — HTTP-level action helpers
- `tests/conftest.py` — fixture spine
- `AGENTS.md` — repo build instructions
- `docs/wishlist/README.md` — wishlist organization rules
- `docs/wishlist/triaged/` — accepted ideas (16 files)