# App CHANGELOG — Saskia RMS

> **For Kiki, Saskia, and any agent.** App-level changelog separate from the
> repo-level changelog. Tracks changes to the `app/` source code, not the docs.

## [Unreleased]

### Added (2026-09-16)

- **E3.S4 — `/healthz/db` enriched payload** — now reports `schema_version`,
  `code_schema_version`, `migrations_pending`, and `last_audit_at` alongside
  the existing DB-reachability fields. Operator dashboards and UptimeRobot
  alerts can now detect schema drift and write silence without hitting a
  separate `/healthz/schema` probe. Documented in
  `docs/operations/uptime-monitoring.md`. 1 regression test.

- **F1 — root-level `/favicon.svg` + `/favicon.ico`** — browsers auto-request
  these at the root, not under `/static/`. Two new `FileResponse` routes
  alias the existing files in `app/static/`. Bypasses `ReadyStaticFiles`
  intentionally (favicon must work during cold-start). 2 regression tests.

- **E4.S1 — Round 2 triage workflow** — `installer/ROUND-2-NOTES.md`
  template (30-day, ship-it criteria only), `docs/operations/round-2-triage-process.md`
  (the 5-step process), and `round-2` label hint added to GH bug + feature
  templates. Round 2 = hot-patch only; bigger items route to gem-project
  backlog as `SASKIA-NNN` tickets. Closes Phase 0 epic E4.S1.

- **E2.S2 — real Postgres test infra (testcontainers)** — new
  `tests/conftest_pg.py` + `tests/test_pg_roundtrip.py` boots a
  `postgres:16-alpine` container and provides `pg_engine`,
  `pg_session_factory`, `pg_session` fixtures. Tagged `@pytest.mark.pg`.
  Local runs without Docker skip cleanly (cached probe, 1× per session).
  CI runs `pytest -m pg` after the main suite.
  - `testcontainers[postgresql]>=4.8,<5` added to dev deps.
  - Closes the 5-hotfix (2026-09-04) gap: 4/5 would have been caught
    by a real PG roundtrip. The 2 dialect-sensitive regression tests
    in `tests/test_hotfix_regressions.py` (row_counts_json roundtrip +
    empty-dict) are now tagged `@pytest.mark.pg`.
  - 4 new pg tests in `test_pg_roundtrip.py`:
    init_db migrates to CURRENT_SCHEMA_VERSION, AuditLog roundtrip,
    ImportBatch.row_counts_json JSONB roundtrip, psycopg3 dialect
    recognized (hotfix 32c5d32 lock-in).
  Closes Phase 0 epic E2.S2.

### Added (2026-09-08)

- **`/produccion` production worksheet** — wires the existing
  `app/rms/production.py` module (E21) to a route. Shows tomorrow's
  forecast with seasonal multiplier, ingredient requirements, and stock
  shortfalls. Nav link added. 1 regression test.

- **`/eod` end-of-day checklist** — wires `EOD_CHECKLIST_TEMPLATE`
  (10 items) to a route showing progress + per-item checkboxes.

- **`/merma` waste log** — wires `app/rms/waste.py` (E22) to a route with
  record form, 30-day summary, and per-reason / per-ingredient breakdown.
  Industry benchmark shown (< 5% is healthy).

- **`/reportes` (hub + `/iva` + `/libro-ventas` + `/diario`)** — wires
  `app/rms/accounting.py` (E17) to 4 routes for IVA monthlies, libro de
  ventas, and daily summary. Legally required reports.

- **`/auditoria` audit log viewer** — wires `app/rms/audit.py` to a route
  with filterable / paginated view of AuditLog entries.

- **Sales page overhaul (Phase 5)** — `Sale` model gets 2 new columns via
  migration 011: `payment_method` (cash/transfer/card/other) and
  `discount_gs` (integer Gs. discount). The `/ventas` GET handler now
  also computes top-5 selling products for one-tap quick-sell buttons.
  The form gained fields for customer phone (auto-create customer +
  accrue loyalty points), payment method, and discount. 4 regression
  tests pin the model + form behavior. Schema v10 → v11.

- **Phase 6 nav/CSS polish** — added logout link to top nav
  (`<a href="/logout" class="logout-link">⎋</a>`). CSS additions:
  `.quick-sell-grid` + `.btn-large` for sales one-tap buttons,
  `.badge-tier-{bronze,silver,gold,platinum}` colored tier badges,
  `nav.breadcrumbs` styling, customer/summary `<dl>` grids. Mobile
  responsive: `@media (max-width: 768px)` makes tables horizontally
  scroll, nav flex-wraps, forms stack vertically. Print CSS was already
  present (verified by test). 4 regression tests in `tests/test_phase6_polish.py`.

- **Phase 7 UptimeRobot integration** — existing monitor
  (id `803916096`) was already configured for `https://saskia-rms.paragu-ai.com/healthz`
  every 5 min, keeping the free-tier Render container warm. Added
  `scripts/uptimerobot_setup.py` for idempotent verify / pause / delete
  operations (reads API key from BWS at runtime). 2 regression tests
  pin the script + verify both BWS keys exist.

### Added (reliability, 2026-09-08)

- **Global exception handler + structured 5xx** — when an unhandled
  error occurs, the app now logs the exception to stderr with full
  context (request_id, method, path) and returns a structured JSON
  response `{error, type, request_id, hint}` instead of FastAPI's
  default HTML 500. HTTPException (FastAPI's normal 4xx/5xx control
  flow) is preserved and returned as a JSON of the same shape.

- **Per-request access log middleware** — every non-/static, non-/healthz
  request now logs `request_id=<id> method=<m> path=<p> status=<s>
  elapsed_ms=<n>` and echoes the request_id back via `X-Request-Id`
  header for correlation. 2 regression tests in `tests/test_reliability.py`.

- **CSRF protection on state-changing endpoints** — new
  `app/rms/csrf.py` implements signed double-submit cookies: sets
  `csrf_token` (HMAC-signed) on every non-exempt GET response, requires
  a matching cookie on every POST/PUT/DELETE/PATCH. Exempt paths:
  `/login`, `/forgot-password`, `/healthz*`, `/static/*`. Uses
  `itsdangerous.URLSafeSerializer` (already in deps). 5 regression
  tests in `tests/test_csrf.py`. Test conftest auto-primes the cookie
  so existing POST tests work without modification.

- **Readiness gate on `/healthz` + `/healthz/deps`** — lifespan
  flips `app.state.ready = True` after create_all() + init_db()
  complete. `/healthz` returns 503 with
  `{status: "warming_up", detail: "..."}` while readiness is False,
  flips to 200 once the app finishes initializing. Eliminates the
  cold-start window where requests hit a half-initialized app and
  get raw 500s. 4 regression tests in `tests/test_readiness.py`.

- **5xx auto-logged to `audit_log`** — every unhandled error now
  writes an `action="http.500"` row with request_id, method, path,
  type, message (truncated to 500 chars). Operators can see error
  counts / types via the existing `/auditoria` page filtered by
  `action_filter=http.500`. Failures of the audit-recording are
  themselves caught and logged (never bubble up).

- **`/ventas` filter (q / product_id / days)** — operators can now
  search 920+ sales by substring (`?q=cabernet`), filter by product
  (`?product_id=N`), or by date range (`?days=7` for last week,
  `30`, `90`). Filter UI on the page with a search input + dropdowns +
  "Limpiar" reset. 4 regression tests in `tests/test_sales_overhaul.py`.

- **`/productos` filter (q / has_recipe)** — operators can search
  products by name (`?q=`) and filter by recipe status
  (`?has_recipe=yes` / `no`). Filter UI with search input +
  dropdown. 4 regression tests in `tests/test_productos_filter.py`.

- **`/healthz/errors` endpoint** — quick error-rate snapshot for
  operators. Returns counts of `action="http.500"` rows in the
  audit_log for the last 1h and last 24h. Gated on readiness (503
  during warm-up). Public read-only endpoint, no PII; just counts.
  3 regression tests in `tests/test_healthz_errors.py`. Tip: hit this
  URL to instantly know if there have been recent server errors.

- **OUTAGE FIX: migrations auto-run on startup** — the lifespan
  now defaults to running `init_db()` on every boot (set
  `AIW_SASKIA_RUN_MIGRATIONS=0` to disable). Previously gated behind
  `=1` opt-in, which left the production Neon DB at schema v10
  while the code expected v11 — causing `column sale.payment_method
  does not exist` 500s on the dashboard. Migration is wrapped in
  try/except so a failed migration never crashes the app. 4 regression
  tests in `tests/test_lifespan_migrations.py`.

- **`/clientes` list + detail pages** — wires the existing
  `app/rms/customers.py` module (E13) to actual routes. Operators can now
  see the customer directory with lifetime spend, visit count, points
  balance, and loyalty tier (Bronze/Silver/Gold/Platinum). The detail page
  shows purchase history. Customers are created automatically when a sale
  records a phone number. 5 regression tests in `tests/test_clientes_routes.py`.

### Fixed (performance, 2026-09-08)

- **GZip + static cache headers** — added `GZipMiddleware(minimum_size=500)`
  (compressed HTML/CSS/JS responses, ~70% bandwidth reduction) and a new
  `StaticCacheMiddleware` that sets `Cache-Control: max-age=3600, public`
  on `/static/*` responses. Browser revalidation on every page load is
  wasteful for assets that only change on deploys. 4 regression tests in
  `tests/test_middleware.py` pin both behaviors.

- **classify_products N+1 → batched** — `app/rms/menu_engineering.py`'s
  `classify_products()` was issuing one `_product_volume` query per product
  (~20 queries for 20 products) plus per-product batch costs. Replaced
  with 1 grouped query for all volumes + 1 `batch_products_cost_margin` call.
  1 regression test in `tests/test_menu_engineering_perf.py` asserts no
  per-product point queries against `sale`.

- **insights + sales_intel N+1 → batched** — `build_insights()` was calling
  `production_plan_for_day()` per product (one query each); `rising_products()`
  and `churning_products()` were calling `_trend_for_product()` per product
  (2 queries each). Added `batch_production_plans()` to
  `app/rms/production_scheduler.py` and `_batch_trend_counts()` /
  `_classify_trend()` helpers to `app/rms/sales_intel.py`. Both functions
  now do constant-query work regardless of product count. 2 regression
  tests in `tests/test_insights_perf.py` pin both behaviors.

- **Dashboard N+1 → batched** — `app/routers/dashboard.py` was issuing ~3,000
  DB queries per render (one `product_unit_cost_gs()` call per sale, plus
  per-product loops in ranking + recipes_no_cost + build_insights). Replaced
  three hot loops with batch helpers already in `app/rms/costing.py`:
  `batch_products_cost_margin()` and `batch_recipes_cost()`. Query count on
  an empty test DB dropped from 37 to 18; on the populated live Neon the
  savings will be much larger (the old code issued ~3 queries per sale × 920
  sales). Two regression tests in `tests/test_dashboard_perf.py` pin the
  behaviour: total query count must stay under 40, and no point-queries
  against the `ingredient` table.

### Added

- **Ingredient intelligence (E26)** — auto-classify every ingredient by
  category, role, allergens, dietary tags, shelf-life, and storage.
  `app/rms/ingredient_intel.py` exposes `infer_category`,
  `infer_subcategory`, `infer_role`, `infer_allergens`,
  `infer_dietary_tags`, `infer_shelf_life_days`, `infer_storage`,
  `classify_ingredient`, and `find_substitutes_by_role` (recipe
  co-occurrence graph). Schema bumped to v9 with new columns:
  `category`, `subcategory`, `role`, `allergens` (JSONB/Text),
  `dietary_tags` (JSONB/Text), `lead_time_days`. Idempotent migration.
- **Recipe intelligence (E27)** — auto-classify every recipe by family,
  difficulty, dietary compatibility, prep/cook time, yield-in-grams,
  cost-per-gram. `app/rms/recipe_intel.py` exposes `infer_recipe_family`,
  `estimate_prep_minutes`, `estimate_cook_minutes`,
  `infer_difficulty`, `infer_recipe_dietary`, `recipe_yield_grams`,
  `recipe_cost_per_gram`, `classify_recipe`, `classify_all_recipes`.
  Schema bumped to v10 with `family`, `difficulty`, `dietary_tags`,
  `cook_minutes`. Idempotent migration.
- **Menu engineering (E28)** — Kasavana/Donaldson star/puzzle/plowhorse/dog
  quadrant classification. `app/rms/menu_engineering.py` exposes
  `classify_products` (volume × margin matrix with median thresholds),
  `menu_engineering_report` (4-quadrant report with counts + total margin),
  `action_for` (recommendations per quadrant). Volume window 90 days,
  voided sales excluded.
- **Inventory intelligence (E29)** — days-of-stock, reorder points, dead
  stock, overstocked detection, total capital tied up. `app/rms/inventory_intel.py`
  exposes `days_of_stock`, `reorder_point`, `inventory_status`,
  `inventory_status_all`, `dead_stock`, `overstocked`, `stock_value_gs`,
  `low_stock_alerts`. Ingredient model gains 6 new fields
  (category/subcategory/role/allergens/dietary_tags/lead_time_days).
  Migration 009 backs the columns; idempotent.
- **Sales intelligence (E30)** — hourly/DOW/monthly patterns, market basket
  affinity, churn/rising detection. `app/rms/sales_intel.py` exposes
  `sales_by_hour`, `sales_by_day_of_week`, `sales_by_month`, `peak_hour`,
  `peak_day_of_week`, `product_affinity`, `top_pairs`,
  `churning_products`, `rising_products`, `sales_summary`.
- **Product similarity (E31)** — Jaccard ingredient overlap for menu
  rationalization, substitution suggestions, clone detection.
  `app/rms/product_similarity.py` exposes `product_ingredient_set`
  (walks sub-recipes recursively), `jaccard_similarity`,
  `most_similar_products`, `suggest_substitute`, `similarity_matrix`,
  `find_clones`.
- **Production scheduler (E32)** — when-to-bake-how-much optimizer. Uses
  velocity (from sales_intel) + DOW multiplier + safety stock + recipe yield
  to plan per-product batches per day. `app/rms/production_scheduler.py`
  exposes `expected_daily_sales`, `production_plan_for_day`,
  `production_calendar` (multi-day), `ingredient_requirements`,
  `check_ingredient_availability` (flags stock shortages that block a plan).
- **True food cost (E33)** — theoretical vs actual reconciliation. Recipe-based
  cost estimate vs. actual stock-move consumption vs. recorded waste.
  `app/rms/food_cost.py` exposes `sales_revenue`,
  `theoretical_food_cost`, `actual_ingredient_consumption`, `waste_cost`,
  `food_cost_report` (combined FoodCostReport dataclass with revenue,
  theoretical %, actual %, ratio). Ratio = actual/theoretical; >1.0 means
  waste, theft, or spillage; <1.0 means recipes/prices outdated.
- **Dashboard insights panel (E34)** — single consolidated panel for the
  dashboard route. `app/rms/insights.py` exposes `build_insights` which
  pulls together inventory capital + alerts, menu-engineering quadrants,
  tomorrow's production plans, food cost summary, peak hour/DOW, top
  rising/churning products. Returns `InsightsPanel` dataclass.
- **Dashboard insights integration (E35)** — wired `build_insights` into the
  existing `app/routers/dashboard.py` route and rendered new section in
  `app/templates/inicio.html`. Dashboard now shows capital en inventario,
  hora/día pico, food cost % (30d), star/dog quadrants, low-stock alerts,
  rising/churning products, and tomorrow's production plan.

### Fixed (login UX, 2026-09-08)

User-facing login was hostile: bad credentials rendered an unstyled text
div with no visual prominence, the page title was doubled
("Iniciar sesión — Saskia RMS — Saskia RMS"), and the forgot-password
recovery link had no tests. This commit:

- **`.alert-error` CSS rule added** — was completely missing. Now renders as
  a red filled box with warning icon (via `::before`). `.alert-info`
  variant also added for the forgot-password confirmation.
- **Login error rendering** — alert block placed above the form with
  `role="alert" aria-live="assertive"` so screen readers announce immediately.
  Error text is human-friendly ("No pudimos entrar.") not URL-encoded
  Spanish gibberish.
- **Form fields marked `aria-invalid="true"`** on error, with
  `aria-describedby="login-error"` so screen readers link the field to
  the error message.
- **Autofocus moves to password field on error** — more useful than
  re-focusing username (which already had the right value).
- **`<title>` deduplicated** — login.html no longer includes
  "— Saskia RMS" in its title block (base template adds the suffix).
- **Forgot-password link rewritten** — action label "Recuperar contraseña"
  instead of question "¿Olvidaste tu contraseña?". Added explicit Iván
  contact (`mailto:ivan@ai-whisperers.dev`) and "5 minutes + spam" hint.
- **Forgot-password inline validation** — the JS handler now uses an
  inline error div instead of `alert()` (better UX, accessibility).
- **`novalidate` on login form** — lets the server's rate-limit / redirect
  logic run instead of the browser blocking submission.

13 new regression tests in `tests/test_login_a11y_regression.py` cover:
alert rendering, aria-invalid on inputs, autofocus behavior, title
de-duplication, forgot-link presence in Supabase mode, message rendering,
forgot-password endpoint, no-enumeration leak, CSS rules present, alert
position (above form, inside main), and form novalidate.

### Operations

- **One-time migration bootstrap hook** — added opt-in `AIW_SASKIA_RUN_MIGRATIONS=1`
  env var that triggers `init_db()` from the FastAPI lifespan. Used to apply
  pending schema migrations (v8 → v10 for E26-E35 columns) on the deployed
  Render service, since Render doesn't expose a "run command" API and SSH
  access requires operator-side key registration. After the first successful
  deploy, the env var should be unset so subsequent deploys don't run
  migrations on every restart.

### Fixed (production deploy 2026-09-08)

- **`/healthz/db` 503 on live** — fixed in `f272e87`. Live site now returns
  `{"db":"ok","server_version":"18.6 (c5250a2)","dialect":"postgresql"}`.
- **Dead PAT stripped from `.git/config`** — found `ghp_u0Cs76...` (the
  known-dead PAT from the "Known dead values" table) embedded in the remote
  URL. Stripped via `git remote set-url origin https://github.com/Ai-Whisperers/saskia-app.git`.
  Re-authenticated via `git credential approve` with the live PAT from BWS.
  Push of 17 commits succeeded.

### Fixed

- **`_migration_007_product_sku` was a no-op** — bumped version but didn't
  add the `product.sku` column on existing databases (it relied on
  `create_all`, which is a no-op for existing tables). Added
  `_add_column_if_missing` helper (cross-dialect: SQLite PRAGMA table_info,
  Postgres information_schema.columns). Fresh DBs from v0 now correctly
  have the sku column after migration. Live Neon already had it (added
  manually earlier); this fix prevents future migrations from the same
  no-op pattern.

### Accessibility (audit 2026-09-08)

Live audit of every route in the app (16 GET + 1 POST across
`/`, `/login`, `/productos*`, `/recetas*`, `/inventario*`, `/ventas*`,
`/excel*`, `/healthz*`). Found and fixed:

- **Bug**: Nav `<a href="/api/healthz">` → 404. Changed to `/healthz`
  and added `aria-label="Estado del servidor"` (was relying only on
  the dot glyph).
- **No skip link**: Added `<a href="#main-content" class="skip-link">`
  as the first focusable element on every page. CSS hides it off-screen
  until keyboard focus, then slides it into view (`.skip-link { top: -40px; }
  .skip-link:focus { top: 8px; }`).
- **No active-page indicator**: Nav links now carry
  `aria-current="page"` on the active route via
  `request.url.path.startswith(...)`. Visual highlight matches the new
  attribute via `.nav-links a[aria-current="page"]`.
- **No alert announcement**: Flash messages were invisible to screen
  readers. Wrapped `{% block alerts %}` in
  `<div class="alerts-region" aria-live="polite" aria-atomic="true">`
  so new alerts are spoken as they appear.
- **No visible focus**: Added `:focus-visible { outline: 2px solid var(--primary); }`
  global rule so keyboard users can see which element is focused.
  `<main>` gets `tabindex="-1"` so the skip-link target can receive
  focus.

16 new regression tests in `tests/test_a11y_navigation.py` cover:
skip link, nav aria-label, aria-current (positive + negative cases),
aria-live, main id+tabindex, lang, h1 count, title, health-link
direction (regression for the 404), and all 7 nav targets returning 200.

- `.github/ISSUE_TEMPLATE/{bug,feature,epic}.md` for guided issue filing.
- AGENTS.md gains "Issue templates", "Locked hotfixes", and refreshed CI
  list sections.
- **Audit log (E3.S1)**: `audit_log` table + `app/rms/audit.py` record()
  helper. Captures `login.success`, `login.failure`, `logout` from the
  auth router with X-Forwarded-For IP + truncated User-Agent. Append-only
  by convention; surfaced later via /audit admin view.
- Schema migration `_migration_002_audit_log` (CURRENT_SCHEMA_VERSION
  bumped 1 -> 2). Idempotent. `aiw-saskia migrate` applies it on first
  run against existing DBs.
- **Seasonal events HTTP seam (E19 final)** — serialize_event +
  calendar_for_year (auto-shifts 2026 calendar to N year) +
  upcoming_calendar_json dashboard widget +
  product_hints_for_event (keyword-based recs).
- **Performance scaffolding (E16)** — paginate() helper with
  clamp-safe bounds; query_timer context manager (logs warning
  on slow ORM); INDEX_HINTS (8 model+column tuples);
  apply_postgres_indexes (idempotent CREATE INDEX); count_models
  diagnostics.
- **Multi-tenant scaffolding (E15)** — Tenant model + schema v8;
  app/rms/tenants.py with ensure_default_tenant (idempotent),
  resolve_tenant_id (env or subdomain), current_tenant context,
  assert_single_tenant warning on > 1 rows.
- **Progressive Web App seams (E11)** — PWA manifest (icons +
  theme_color), inline service worker (cache-first static /
  network-first API / offline HTML), UA-based is_mobile detector,
  offline.html fallback, pwa_meta_tags() for head injection.
- **WhatsApp + email daily summary (E14)** —
  format_daily_summary_message (concise text), NotifyKind
  (dryrun/whatsapp/email), Twilio REST over stdlib urllib (no SDK
  dep), SMTP send, spool-dir + notification log.
- **Future-facing seams (E25)** — RBAC stub (Role enum +
  ROLE_PERMISSIONS); report registry (5 built-in auto-registered);
  feature flags via app_meta (4 defaults: dark mode, void button,
  seasonal hint, drive-shape-only imports).
- **ESC/POS receipt printer + labels (E18)** — file/network/USB
  backends; vendor list (Epson/Star/Citizen/Brother); AIW_PRINTER_*
  env config. Default file backend for CI.
- **Barcode scanner support (E23)** — Product.sku column (optional,
  unique, indexed) + migration 007; normalize/validate/lookup helpers
  in app/rms/barcode.py; suggest_sku heuristic.
- **Backup + restore + DR retention (E20)** — JSON+gz archives with
  sha256 manifest; tamper detection; merge-restore; retention policy
  (keep newest N + last D days); scripts/backup.py CLI (backup/list/
  restore/prune/verify).
- **Production worksheet (E21)** — forecast_sales (rolling 14d
  avg) + plan_production (per-product forecast with seasonal
  multiplier + per-ingredient lines with stock_on_hand + qty_to_buy).
- **Operator workflow + seasonal calendar (E12 + E19 prep)** — EOD
  checklist (10 items), daily_summary_full with warnings (high void
  rate, low margin, low stock), 2026 seasonal calendar (11 events;
  Navidad 3x, Día de la Madre 2x, Independencia 1.8x).
- **Dev tooling (E24)** — Makefile (18 targets); CONTRIBUTING.md;
  docker-compose.dev.yml (Postgres 16); CODEOWNERS (security/dba routing);
  Dependabot weekly uv bumps.
- **Paraguay accounting/IVA reports (E17)** — 10% IVA extraction
  (included/excluded modes); monthly_iva_breakdown; libro_ventas;
  daily_summary; product_margin_summary.
- **Merma waste tracking (E22)** — schema v6; append-only waste log;
  7 reasons (vencida/quemada/derrame/robo/danio/receta_incompleta/otra);
  cost denormalized at insert; impact reports by reason/ingredient.
- **Customer directory + loyalty (E13)** — schema v5; phone-unique
  customer records; 1 pt/1000 Gs. loyalty; bronze/silver/gold/platinum
  tiers by lifetime spend; redeem 1 pt = 1000 Gs. discount.
- **Operator-facing settings (E10)** — 30 settings across 7 groups
  (general/inventory/sales/dashboard/backup/session/demo), backed by
  AppMeta with validators + audit-ready writes.
- **Tag system + filters (E9)** — schema v4; 31 starter tags;
  polymorphic M:N (product/ingredient/recipe); filter dataclasses for
  Ventas/Inventario/Recetas/Productos.
- **Drive-shape xlsx fixtures (E7)** — 4 fixtures under tests/fixtures/
  (minimal, realistic, edge cases, herbus-compat) + 10 round-trip tests.
  Rebuild with `uv run python tests/fixtures/build_herbus_fixture.py`.

- **Operational analytics dashboard (E8)** — `app/rms/analytics.py` adds
  stock turnover, dead-stock detection, margin-erosion alerts, day-of-week
  heatmap, top-margin ranking, ingredient concentration, recipe complexity.
  Schema v3 adds 4 nullable columns: ingredient.purchase_price_updated_at,
  last_consumed_at (indexed), shelf_life_days (E22 prep), recipe.prep_minutes.

- **Realistic demo data seed (E6)** — `app/rms/seed.py` +
  `aiw-saskia seed [--reset]`. 30 ingredients, 12 recipes, 80
  recipe_lines, 20 products, ~200 synthetic sales over 90 days with
  weekday/weekend skew + payday spikes, demo user, voided + encargo
  examples, import_batch + audit_log seed rows. Idempotent.

- **Dashboard TZ fix** — period_window now converts to UTC-naive
  before DB compare (was treating Asunción-local as naive-UTC which
  broke `today` filter outside UTC midnight).

- **Complete epic plan v3 (`docs/plans/2026-09-07-saskia-complete-epic-plan-v3.md`)** —
  25 epics across 6 phases, ~268h, no cap (gem project). Each epic has
  Why / Stories / Tasks / Effort / Depends on / Acceptance / Refs.
  Ticket convention `SASKIA-NNN` defined in `AGENTS.md`.

- **Security headers (E3.S3)**: `app/rms/security_headers.py` adds
  X-Frame-Options, X-Content-Type-Options, Referrer-Policy, restrictive
  CSP, and Permissions-Policy on every response (including /healthz
  and 3xx redirects). HSTS conditional on HTTPS_ONLY (off for local-dev
  over http). 9 tests lock the behavior in.
- **Login rate-limit (E3.S2)**: 5 failures / 5 min per IP → 429 with
  Retry-After. Backed by audit log (login.rate_limited rows for forensics).
  /healthz is exempt. AIW_SASKIA_AUTH_DISABLED=1 bypasses for tests.
- **CF tunnel rotation runbook (E1.S3)**:
  `docs/operations/cf-tunnel-rotation.md`. 7-step procedure with
  90-day cadence (next: 2026-12-04) and rollback. Operator-only;
  assistant cannot perform the rotation itself (CF dashboard access).

## [Unreleased-pre-templates] — pre-signoff skeleton

**Status:** Skeleton landed in pre-signoff commit `f82dfb3` of the engagement repo,
which migrated to `saskia-app` repo. **Not yet on her PC.**

### Added

- `pyproject.toml` with Python 3.13, FastAPI 0.115, uvicorn[standard], SQLAlchemy 2.0,
  openpyxl 3.1, Jinja2, pydantic 2.9, loguru. Dev: pytest, pytest-cov, hypothesis, ruff.
- `LICENSE` (MIT).
- `.gitignore` blocking `__pycache__/`, `.venv/`, `*.sqlite`, `*.log`, `.env`.
- `.pre-commit-config.yaml` (ruff + smoke tests + secret detection).
- `.github/workflows/ci.yml` (ruff + pytest + 80% coverage gate).
- `app/rms/__init__.py` (package marker).
- `app/rms/money.py` (Decimal helpers, Gs. formatting, strict parsing).
- `app/rms/units.py` (Unit enum with alias coercion, intra-family conversion).
- `app/routers/__init__.py`, `app/services/__init__.py`.
- `app/routers/health.py` (`/healthz`, `/healthz/db`).
- `app/services/auto_backup.py` (backup helper functions).
- `app/docs/copy-vos.md` (UI copy bank template).
- `app/docs/threat-model.md` (single-user, single-PC, single trust boundary).
- `app/docs/architecture.md` (data flow, sources of truth, timezone).
- `app/docs/upgrade-tiers.md` (Tier matrix for future upgrades).
- `app/rms/AGENTS.md` (engineering conventions for `app/rms/`).
- `tests/conftest.py`, `tests/test_money.py` (43 tests), `tests/test_units.py` (45 tests).
- `installer/README.md` (install-session checklist).
- `installer/run.bat` (Windows launcher using `uv`).
- `docs/sessions/round-2-feedback.md` (review template).

### Test results

- 88 tests pass (43 money + 45 units).
- ruff clean (lint + format).

### Known gaps (for next sprint)

- `app/rms/db.py` (SQLite engine + WAL + versioned migrations) — Task 1 of dev plan.
- `app/rms/models.py` (7 tables + polymorphic recipe_line) — Task 1.
- `app/rms/costing.py` (recipe_batch_cost, product_unit_cost, margin) — Task 2.
- `app/rms/main.py` (FastAPI app with lifespan) — Task 1.
- `app/routers/dashboard.py`, `products.py`, `recipes.py`, `inventory.py`, `sales.py`,
  `excel_io.py` — Tasks 3-7.
- `app/services/import_xlsx.py`, `export_xlsx.py`, `reports.py`, `r2_backup.py`
  — Tasks 6, 9, 12.
- `app/templates/base.html`, `inicio.html`, etc. — Tasks 3-7.
- `installer/run.sh` (Mac) — Task 9.
- `installer/r2-setup.md` — Task 9.
- `tests/test_costing.py`, `test_stock_drop.py`, `test_void_sale.py`,
  `test_import_roundtrip.py`, `test_healthz.py`, `test_r2_backup.py`,
  `test_recipe_polymorphic.py` — Tasks 1, 2, 6, 9.
- `tests/fixtures/stress.xlsx` (real-scale synthetic) — Task 6.

## [2026.09.0] — 2026-09-04 / 2026-09-07 — Fase 1.5 hardening

**Status:** Closed Fase 1 production hotfixes + hardened deploy CI. **On her PC** once operator syncs `main` branch.

### Added

- **`docs/wishlist/`** (append-only bucket for future ideas; 21 seeds from
  critical-path analysis). Includes `README.md` format spec and `raw/` /
  `triaged/` / `rejected/` subdirs.
- **`tests/test_hotfix_regressions.py`** — 15 fail-closed tests for the 5
  production hotfixes landed on 2026-09-04 (HEAD /healthz, SUPABASE_SECRET_KEY
  alias, supabase in Dockerfile pip list, /healthz/deps fingerprint,
  row_counts_json JSONB match). Proven fail-closed by reverting the HEAD route
  and confirming 2 tests fail with the original 405.
- **`tests/test_migrate_cli.py`** — 5 tests covering the new `aiw-saskia
  migrate` CLI (idempotent first/second run, schema detection across SQLite
  and Postgres dialects, argv dispatch).
- **CLI dispatch in `app/rms/main.py`**: `run()` now dispatches on sys.argv —
  `aiw-saskia migrate` invokes `migrate()` (idempotent schema apply);
  `aiw-saskia serve` and bare `aiw-saskia` start uvicorn (backward compatible).
- **`migrate()` entry point** in `app/rms/main.py`: idempotent (checks
  schema_version; no-op if already at target); supports both `DATABASE_URL`
  (Postgres) and `AIW_SASKIA_DB_PATH` (SQLite) so it works for hosted and
  local dev.
- **CI: migrate smoke test** in `.github/workflows/ci.yml` — runs
  `aiw-saskia migrate` against a fresh SQLite on every PR to catch migrate()
  regressions.
- **CI: CHANGELOG discipline check** — every PR touching `app/`, `scripts/`,
  `tests/`, or `.github/` must also touch `app/CHANGELOG.md` or CI fails.

### Changed

- **`scripts/apply_neon_schema.py`** — now a thin wrapper around `migrate()`
  with dialect-aware schema introspection (works on both PG and SQLite).
- **`docs/operations/dashboard/refresh.sh`** — autodetects when `$PWD` is a
  saskia-app git repo, falling back to the legacy scratch path only when
  both are absent. Previously the hard-coded path didn't exist.
- **`installer/README.md`** — clone URL corrected from `saskia.git` to
  `saskia-app.git` (commit `6fef4a2`).

### Test results

- 354 tests pass (was 334; +20 from `test_hotfix_regressions` and
  `test_migrate_cli`).
- Coverage: 82% (was 81%; held at >= 80% gate).

### Hotfixes locked in by the regression suite (commits on `main`)

- `f1af406` — HEAD /healthz for UptimeRobot
- `c093a75` — SUPABASE_SECRET_KEY / SUPABASE_PUBLISHABLE_KEY aliases
- `99b37c6` — supabase SDK in Dockerfile pip list
- `bb21eff` — /healthz/deps env fingerprint
- `501bcff` — `row_counts_json` ORM type matches Postgres JSONB column

## Versioning

- We use CalVer: `YYYY.MM.patch` (e.g., `2026.09.0`).
- Major = 0 until fase 1 ships.
- After fase 1: `1.0.0`, then `1.1.0` for Fase 1.5, `2.0.0` for Fase 2.
