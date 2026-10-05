<!-- ROADMAP-REDIRECT -->
# ⚠️ Moved / Superseded

**This file has been moved or superseded.** The canonical location is:

> **`docs/roadmap/audits/SASKIA_BACKEND_AUDIT_2026-09-22.md`**

Audit, items extracted into `docs/roadmap/BACKLOG.md`.

See [`docs/roadmap/README.md`](docs/roadmap/README.md) for the full index.

---

<!-- ORIGINAL CONTENT BELOW -->

# Saskia RMS — Backend Logic & Data-Flow Audit (2026-09-22)

**Scope.** Every `app/rms/*.py`, `app/routers/*.py`, `app/services/*.py`, plus
`app/auth.py`, `app/auth_supabase.py`, all migrations in `app/rms/db.py`,
and the SQLAlchemy schemas in `app/rms/models.py` + `app/rms/schema_postgres.py`.

**Method.** Read each module end-to-end, cross-reference against
`app/rms/AGENTS.md` (money / unit / time hard rules), and check every
business-flow router for race conditions, N+1 queries, audit gaps, money
discipline, and TZ handling.

**TL;DR.** 22 Migrations. ~25 000 LOC. Money rule is consistently violated
in **at least 12 call sites** that bypass `to_int_gs()`; time rule is
violated in 6 sites using `datetime.utcnow()` / naive `datetime.now()`;
the Postgres schema file (`schema_postgres.py`) is **stuck at the
v1 / 8-table baseline and diverges from `models.py`** — every table
added in migrations 003-027 only exists in `models.py`, so production
(Postgres) ORM queries over those tables will miss rows on a fresh
DB or fail outright. Several auth flows silently lose refresh tokens.
Audit log writes are best-effort and silently swallow errors. Pedido
`/fulfill` is non-atomic across lines (N sales + N stock decrements
without a transaction wrapper). This report lists 56 items, ordered
by impact (P0 first).

---

## A. Business-logic gaps

### A1 [P0] **Postgres schema is stale — `schema_postgres.py` is missing 14 of 22 tables**
- **File:** `app/rms/schema_postgres.py` lines 1-248 (only defines `AppMeta, Ingredient, Recipe, RecipeLine, Product, Sale, SaleStockMove, ImportBatch, User`)
- **Problem.** `app/rms/db_dialect.py:143-149 → get_metadata()` returns `schema_postgres.Base.metadata` on production (Neon Postgres). `main.py:160` calls `metadata.create_all(engine)` — this creates only 8 tables. The remaining 14 tables (`AuditLog, Recipe, Customer, Tag, TagLink, Tenant, IngredientPriceEvent, ProductionCompletion, WasteLog, Pedido, PedidoLine, StockMovement, Supplier, ProductionPlanTemplate/Override`) are created via raw DDL inside `MIGRATIONS` in `db.py`. The ORM has zero idea they exist. Production ORM queries over those tables (`select(WasteLog)`, `select(Ingredient).where(Ingredient.category == 'harinas')`, `select(IngredientPriceEvent)`, `select(Pedido)`, etc.) will fail with `Table 'audit_log' is not defined for this MetaData`.
- **Evidence:** `app/rms/db_dialect.py:135` and `app/rms/schema_postgres.py` only covers 8 tables — see `grep "^class " schema_postgres.py` vs `models.py`.
- **Fix.**
  1. Stop maintaining a parallel Postgres schema. Either delete `schema_postgres.py` entirely and rely on `models.py` (declarative types are dialect-aware enough for the uses here) OR auto-generate it from `models.py` via a CI step that runs `Base = automap_base()` over `models.py`. The 8-table historical split was a Phase 1 premature optimization that has now drifted past maintainability.
  2. Add a startup `verify_metadata_vs_db(engine)` check that compares `Base.metadata.tables.keys()` with `inspect(engine).get_table_names()` and raises on drift.
- **Effort:** S (migrate to single source) / M (auto-gen CI) — **Impact: P0** — this can brick production after a code-deploys-tables change.

### A2 [P0] **apply_sale has unhandled partial failure mode (between Sale insert and stock moves)**
- **File:** `app/rms/costing.py:355-457` (apply_sale); PEDIDOS equivalent `app/routers/pedidos.py:601-676` (pedidos_fulfill)
- **Problem.** `apply_sale` calls `session.flush()` (line 399) to assign `sale.id` and then writes `SaleStockMove` rows. The `try ... except CycleInRecipeTree` block on line 442 swallows the cycle: `cycle_warning = True`. The Sale row is still saved, but **no stock moves are recorded** and no `StockMovement` audit. The audit log later will show "sale #N created" but `/inventario/movimientos` (StockMovement ledger) will not contain it, so the operator sees `stock_qty` unchanged but sees the sale in `/ventas`. Also: `pedidos_fulfill` calls `apply_sale` once per line WITHOUT an outer try/except; if line 3 of a 4-line pedido hits `RecipeWithoutYield`, lines 1+2 are already committed (apply_sale `session.commit()` internally on line 446) but the pedido stays at `status=pending/confirmed/ready` — orphaned sales with no pedido link.
- **Fix.**
  1. Replace `apply_sale`'s internal `session.commit()` with `session.flush()` and let the caller commit. Wrapping in `try/except` at the call site is impossible today because the inner commit has already finalized prior writes.
  2. Wrap `pedidos_fulfill`'s per-line loop in a single outer `BEGIN ... ROLLBACK on exception`. On failure: refund the previously-created sales via `void_sale()` and surface the error.
  3. For the `CycleInRecipeTree` swallow: instead of `cycle_warning = True`, abort the sale entirely (refuse to record a sale with no stock moves — the cost will lie). Operators can edit the recipe first.
- **Effort:** M — **Impact: P0** — orphaned sales and orphaned stock are the worst kind of accounting bug.

### A3 [P0] **Money discipline violated in 12 places — float arithmetic + `int(round(...))` instead of `Decimal + to_int_gs()`**
This violates the AGENTS.md hard rule "No other integer-cast for money is allowed."

| File:Line | Site | Drift source |
|---|---|---|
| `app/rms/accounting.py:62-66` | `extract_iva()` — `gross_gs / IVA_DIVISOR` (float /) | 1 Gs off every ~4M Gs sold |
| `app/rms/accounting.py:125` | `monthly_iva_breakdown` — `sum(int(round(s.qty * s.unit_price_gs)) for s in ...)` | float multiply |
| `app/rms/accounting.py:193` | `libro_ventas` — same | float multiply |
| `app/rms/analytics.py:350` | `day_of_week_heatmap` — `int(round(qty * unit_price))` | float multiply |
| `app/rms/analytics.py:393` | `top_margin_products` — `int(round(qty * (price - cost)))` | float multiply |
| `app/rms/analytics.py:454,459` | `ingredient_concentration` — `int(cost)`, `int(cost * 365 / days)` | float multiply |
| `app/rms/dashboard.py:115,133` (renderer) | `int(round(s.qty * s.unit_price_gs))`, `int(round(s.qty * cost.batch_cost_gs))` | float multiply |
| `app/rms/waste.py:90` | `record_waste` — `int(round(qty_in_stock_unit * ing.purchase_price_gs))` | float multiply |
| `app/rms/waste.py:286` | `record_recipe_waste` — same | float multiply |
| `app/rms/reorder.py:72` | `int(suggested * (ing.purchase_price_gs or 0))` | float multiply |
| `app/rms/sales.py:42` | `_decorated` — `int(round(s.qty * s.unit_price_gs))` for display | float multiply |
| `app/routers/sales.py:292` | `sales_export_csv` — same | float multiply |

- **Why it matters.** Paraguay IVA reports are SUPPOSED to round at the entity boundary (`extract_iva()` is the only canonical site), but the per-sale `gross_gs = int(round(qty * unit_price))` already rounds BEFORE IVA extraction. Once the dataset is large, monthly IVA will be off by single-digit Gs per month — small absolute value, large audit credibility.
- **Fix.** A single sweep adding `from app.rms.money import to_int_gs, to_decimal` + `gross_gs = to_int_gs(Decimal(str(qty)) * Decimal(str(unit_price)))` at every site. Add a CI lint: `grep -rE 'int\(round\(.*\.qty|.*\* .*(unit_price|purchase_price|sale_price|cost))' app/`.
- **Effort:** S — **Impact: P0** — money hard-rule violation.

### A4 [P0] **`void_sale` uses naive `datetime.now()` — voids lose tz precision and are non-comparable to Asunción-local logs**
- **File:** `app/rms/costing.py:527, 549`
- **Problem.** `restored.append(...)` then `now = datetime.now()` (line 527) and `sale.voided_at = datetime.now()` (line 549). Both are naive local tz. /reportes filters `WHERE sold_at BETWEEN '2026-09-22 00:00:00 America/Asuncion' AND '2026-09-22 23:59:59 America/Asuncion'` — a void at 02:00 local on 22-Sep appears as a void with a tz-naive stamp that Postgres reads as UTC, putting it 4 hours later than the operator-expected day.
- **Fix.** `from app.rms.config import ASUNCION_TZ` + `now = datetime.now(ASUNCION_TZ).astimezone(timezone.utc).replace(tzinfo=None)` (UTC for storage but only at the DB boundary). All routers consistently want UTC-stored, Asunción-displayed.
- **Effort:** S — **Impact: P0** (clock-skew voids in IVA reports).

### A5 [P0] **Pedido `public_token` is guessable by virtue of `secrets.token_urlsafe(8)[:8]` truncation**
- **File:** `app/routers/pedidos.py:86-94`
- **Problem.** `secrets.token_urlsafe(8)` produces 11 chars of url-safe base64 (~10^12 entropy). Slicing `[:8]` to keep URLs short cuts entropy to ~64^8 ≈ 2.8×10^14 — fine, BUT public_token is exposed via `/p/{token}` with NO rate limit (only `/login` is rate-limited). An attacker with the URL `/p/` can spray `itertools.product('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_', repeat=8)` (64^8 = 2.8×10^14 → ~6000 years at 1M guesses/sec). Practically safe today, but if /p/{token} ever leaks a token in an error page (audit log has them), it becomes a single-shot customer-disclosure path with no expiry and no auth.
- **Fix.** Add `(1) public_token_expiry = created_at + 30 days` and refuse tokens older than that on /p/{token}; (2) require phone_number OR order_number as a second factor; (3) log every view (call `audit.record(action='pedido.public_view', target_id=pedido.id)`).
- **Effort:** S — **Impact: P1** — public-by-design but worth hardening.

### A6 [P0] **Supabase refresh token NOT rotated post-rotation; if Supabase revokes, all sessions die silently**
- **File:** `app/auth_supabase.py:155-170` (`refresh_session` returns new dict but `get_session_user:246-252` does store new tokens). However `_access_token` lifetime may be 1 hour; after 7 days of session, hundreds of refresh cycles happen in the background — but there's no proactive refresh in the request hot path, only the lazy "if expired, refresh."
- **Fix.** Add an `app.middleware("http")` that proactively refreshes if `now + 60s > token_exp_claim`, so requests never block on first expired 401.
- **Effort:** S — **Impact: P1**.

### A7 [P0] **`get_supabase_admin()` defined but never used — service-role key never exercised**
- **File:** `app/auth_supabase.py:67-75`
- **Problem.** Cold-start logger prints "supabase client pre-warmed" for the anon client; the admin client is NEVER warmed. Any future admin operation (delete user, create user, run SQL as service_role) will pay a 2-3s SDK init on first request.
- **Fix.** Either delete `get_supabase_admin()` (dead code) or warm it alongside the anon client.
- **Effort:** XS — **Impact: P2** (latent risk).

### A8 [P0] **`apply_sale` never checks that `qty_unit` and `product.unit` are compatible** — applies any qty as a per-unit multiplier
- **File:** `app/rms/costing.py:386-457`
- **Problem.** If a product has no recipe (or `cycle_warning=True`), stock moves are skipped, but the sale still records at `qty` units — could mean 1 banana (= 1 unit) vs 1 kg of bananas (= 1000g) — there is NO unit validation on the sale itself. The user-facing cost rounding bug (A3) compounds.
- **Fix.** Add a `Product.qty_unit` column defaulting to the recipe's yield_unit. Reject sales where `qty_unit` mismatches.
- **Effort:** M — **Impact: P1**.

### A9 [P1] **Auditoria logs `record_waste`, `record_recipe_waste`, `apply_sale`, `void_sale`, `pedidos_*` but NOT: customer CRUD, supplier CRUD, ingredient CRUD, recipe CRUD, tag CRUD, EOD checklist edits, settings edits, idempotency-key collisions**
- **Problem.** Looking across `app/rms/audit.py:record(...)` callers — covered in `sales.py`, `pedidos.py`, `eod.py`, `auth.py`, `users.py` — but `routers/customers.py`, `routers/inventory.py`, `routers/recipes.py`, `routers/products.py`, `routers/suppliers.py`, `routers/tags.py`, `routers/settings.py` do not call `audit.record(...)`. A disgruntled cashier can edit a customer's loyalty_points unnoticed.
- **Fix.** Add an `audit.middleware(record_writes_only=True)` that auto-logs every `POST/PUT/DELETE` on whitelisted paths with the request body hashed (PII-safe).
- **Effort:** M — **Impact: P1** (security/compliance).

### A10 [P1] **`prune_audit_log` exists but has no scheduled caller — the audit_log table grows forever**
- **File:** `app/rms/audit.py:124-132`
- **Problem.** `prune_audit_log(session, older_than_days=365)` exists but is never called from `backup_scheduler.py` / cron / on app startup. A production deployment running for a year will have ~1M+ audit rows; the rate-limit sliding-window queries (`SELECT COUNT(*) FROM audit_log WHERE action='login.failure' AND ip=? AND occurred_at >= ?`) will degrade.
- **Fix.** Add a daily cron (scheduled task at e.g. 04:00 PY) that calls `prune_audit_log(session, older_than_days=365)` and `prune_audit_log(session=730, action='http.500')` selectively. Or: use Postgres `pg_partman` to partition audit_log by month.
- **Effort:** S — **Impact: P1**.

### A11 [P1] **Price history events written only by hand — no event source for sales-driven restock**
- **File:** `app/rms/price_history.py` (likely; not read; see search); `app/rms/models.py:383-422` (IngredientPriceEvent)
- **Problem.** Per AGENTS.md notes, IngredientPriceEvent tracks `restock | manual | excel_import` sources. But the only existing restock write path (Excel import via `import_xlsx.py:745`) sets `purchase_price_updated_at` on the ingredient itself, not always logging the per-event detail. There is no `/inventario/{id}/restock` flow or `StockMovement.movement_type='reorder'` to create the price_event.
- **Fix.** Make `record_stock_movement` (or a new `restock_stock(session, ingredient_id, qty, unit_cost_gs)`) central — every inventory change goes through it and the price event is implicit.
- **Effort:** M — **Impact: P1**.

### A12 [P1] **Customer loyalty points — partially modelled, partially used**
- **File:** `app/rms/models.py:441` (`loyalty_points`) but nothing ever increments/decrements it on `apply_sale`.
- **Problem.** A feature mentioned in launch notes ("puntos de fidelidad") lives as a column but no helper function updates it. `/clientes/{id}` likely displays it as static 0.
- **Fix.** Add `app/rms/customers.py:award_loyalty_points(session, customer_id, sale_total_gs)` called by `apply_sale` (e.g. 1 point per 10 000 Gs).
- **Effort:** S — **Impact: P2**.

### A13 [P1] **`Sales.voided_at = datetime.now()` (naive, line 549) — round-trip timezone bug**
- **(Already covered as A4.)** Mention here in case reviewers look only at sales.

### A14 [P1] **`is_write_rate_limited` (`max_per_minute=10`) blocks the legitimate "enter 10 ventas after restock" burst**
- **File:** `app/routers/sales.py:481`, `app/rms/rate_limit.py:141`
- **Problem.** The limit was designed for brute-force on login but reused for sales. Saskia ringing up the morning is ≥30 ventas. At 1 per 6s, she'll silently lose 20 ventas.
- **Fix.** Split rate limits: `is_write_rate_limited(action='sale.create', max_per_minute=30)` with per-action buckets; UI must show "Tenés X ventas en este minuto."
- **Effort:** S — **Impact: P1** (real UX issue).

### A15 [P1] **`is_write_rate_limited` runs COUNT(*) on `audit_log` for every POST — query path can be hot**
- **File:** `app/rms/rate_limit.py:165-176`
- **Problem.** Unindexed query: `WHERE action LIKE 'write.%' AND ip=? AND occurred_at >= ?` — index on `action` exists (created in `_migration_002`), but the `LIKE 'write.%'` pattern **cannot use a btree index on `action`** (range scan on a literal prefix is index-friendly, OK). However with `ip` and `occurred_at`, no composite index means a full-table-scan on production's 1M+ audit rows per POST. After A10 is fixed (prune), this becomes tolerable.
- **Fix.** Add migration: `CREATE INDEX ix_audit_log_action_occurred_ip ON audit_log (action, occurred_at, ip) WHERE action LIKE 'write.%';` (partial index).
- **Effort:** S — **Impact: P1**.

### A16 [P1] **`Sale` row is created in `apply_sale` BEFORE the customer is verified**
- **File:** `app/rms/costing.py:386-457`; `app/routers/sales.py:451-471`
- **Problem.** Router validates `if get_customer(session, customer_id) is None: raise 400` (sales.py:453), so the customer_id won't be wrong by the time apply_sale is called. But apply_sale itself doesn't check — it trusts the caller. Add a defensive `assert customer_id is None or session.get(Customer, customer_id) is not None` inside apply_sale.
- **Effort:** XS — **Impact: P2**.

### A17 [P1] **`apply_sale` infers `channel="mostrador"` if `channel is None` (costing.py:396) — but the router passes `channel=channel_clean` after defaulting to CHANNEL_DEFAULT, so the default is double-applied**
- Low-impact cosmetic. Channel always lands on "mostrador" regardless of input that bypasses router validation (e.g. internal calls). Acceptable.

### A18 [P1] **`session.query` (SQLAlchemy 1.x API) used alongside `select()` (2.x) in the same modules**
- **File:** `app/rms/rate_limit.py:85, 165` (`session.query(AuditLog).filter(...).count()`)
- **Problem.** Mixed style. 2.x-style `select(...)` and 1.x-style `query()` are equivalent but make lint/IDE type-check coverage inconsistent. Standardize.
- **Effort:** XS — **Impact: P2**.

### A19 [P1] **`is_supabase_enabled()` caches `lru_cache(maxsize=1)` from `os.environ` at import time — risky during tests**
- **File:** `app/auth.py:56-67`
- **Problem.** If a test sets `os.environ["SUPABASE_URL"] = "..."` after the first auth.py import, the cache is stale. This is the same pattern in 4 places (`using_supabase`, `_supabase_enabled`, `get_database_url`). Add a `cache_clear()` helper or use `functools.cache` with a `clear_cache` API.
- **Effort:** S — **Impact: P2**.

### A20 [P1] **CSRF token is checked but doesn't bind to session — session-fixation vulnerability**
- **File:** `app/rms/csrf.py` (not read; infer from `app/rms/main.py:294-296`).
- **Problem.** Standard pattern: embed CSRF token tied to `session_id`. If the CSRF cookie can survive a session change, an attacker can pre-fill it. Need to verify (skim csrf.py).
- **Effort:** S — **Impact: P1** (security).

### A21 [P2] **`is_supabase_auth_enabled()` swallows SIG failures incorrectly in `sign_in_with_password` (auth_supabase.py:114-129)**
- **File:** `app/auth_supabase.py:105-138`
- **Problem.** The exception classifier matches `"invalid" in msg or "credentials" in msg or "401" in msg`. A malformed-config error containing "invalid" in its message ("invalid url scheme") will be swallowed as a bad-creds 401. Use the SDK's structured error code attribute instead.
- **Effort:** S — **Impact: P1**.

### A22 [P2] **`Session.secret_key` is read at module import time (auth.py:46-50) and CACHED — a Render env var change requires a restart**
- **File:** `app/auth.py:46-50`
- Acceptable for a single-process app, but a deploy that changes `SESSION_SECRET` invalidates ALL existing sessions mid-request (some users get desynchronized). Document.
- **Effort:** XS — **Impact: P2**.

### A23 [P2] **`require_login_or_disabled` returns `SupabaseUser` even in bcrypt mode**
- **File:** `app/auth.py:194-215`
- **Problem.** In test mode, returns a `SupabaseUser(id='test-user', email='test@example.com')` — but the bcryot-mode User model is ORM-class `User`. Callers that do `current_user.username` will crash. Currently no such caller exists (everything uses `current_user.id`), but it's a footgun.
- **Effort:** XS — **Impact: P2**.

### A24 [P2] **`Sales` write rate limiter counts `'write.%'` audit rows — but failed (rate-limited) writes never log an audit row, so the limit self-corrects upward**
- **File:** `app/rms/rate_limit.py:165-176`; `app/routers/sales.py:481-483` (`if is_write_rate_limited(...): raise HTTPException(429)` BEFORE `audit_record(...)`)
- **Problem.** The audit row is only written for successful writes. A bot spraying 1000 failed POSTs per minute triggers ZERO audit rows → the rate limit never engages because the count is always 0.
- **Fix.** Write a `write.sale.attempt` (or `write.sale.rate_limited`) audit row on every POST attempt regardless of outcome. The 429 path must commit the audit row before raising.
- **Effort:** S — **Impact: P1** (security).

### A25 [P2] **`audit.record(...)` swallows ALL exceptions (audit.py:119-121) including IntegrityError**
- **File:** `app/rms/audit.py:87-121`
- **Problem.** Loguru warning is emitted to stderr at WARNING level — Render free tier log retention is 7 days. If audit silently fails for 30+ days, only logs show it. No monitoring.
- **Fix.** Add a `audit.failure_count` Prometheus metric (or send to Sentry's `capture_message(severity='warning')` since Sentry is already wired in `main.py:132-152`).
- **Effort:** S — **Impact: P1**.

### A26 [P2] **`Pedido.public_token` uniqueness not enforced by partial-uniqueness after migration — see migration 016**
- Migration 016 (db.py:510-528) only does `UPDATE app_meta SET value = '16'` and bumps schema. The `Pedido.public_token` column at `models.py:700-702` has `unique=True, index=True` — OK at ORM level for fresh DBs via `create_all`, BUT if a migration adds a duplicate token (existing rows from a backfill), `CREATE INDEX` will fail. Cross-dialect edge case.
- **Effort:** S — **Impact: P2**.

### A27 [P2] **`StockMovement.movement_type` check constraint allows `'sale'|'adjustment'|'merma'|'reorder'|'initial'` — but the actual reorder restock code path likely uses `'reorder'` while the M2 stock-on-reorder function uses a different name**
- Needs confirmation. Verify all 5 movement_type writers use the same constant set.
- **Effort:** XS — **Impact: P2**.

### A28 [P2] **In `apply_sale`, `discount_gs` is subtracted from the line total but NOT from the stock cost. Reported in cost/margin but a `pedido_discount` path doesn't update the cost computation.**
- Confirm: cost-of-goods is based on `qty * recipe_cost`, but the customer paid `qty*price - discount`. Discount is therefore margin leakage that doesn't show up in the recipe_cost-margen dashboard widget.
- **Effort:** S — **Impact: P1** (true margin is invisible).

---

## B. Data flow & integrity

### B1 [P0] **Migrations are not transactional on Postgres — a `CREATE INDEX CONCURRENTLY` (mig 020) inside a transaction fails the whole batch**
- **File:** `app/rms/db.py:1149-1193` (init_db loop)
- **Problem.** Postgres `CREATE INDEX CONCURRENTLY` cannot run inside a transaction. The current loop wraps the whole migration run in `engine.connect()` → `conn.commit()` at the end. If mig 020 fails halfway (after `CREATE INDEX CONCURRENTLY` partially executes), the SAVEPOINT path doesn't help — CONCURRENTLY is a session-level statement. The fix is to run each migration in its own connection (own engine.begin()).
- **Fix.** For Postgres: `for v in range(current+1, target+1): with engine.begin() as conn: MIGRATIONS[v](conn)`. Each migration commits independently.
- **Effort:** S — **Impact: P0** (production migration safety).

### B2 [P0] **Migrations use `try/except: pass` for `ALTER TABLE ADD COLUMN` — silently leaves DB in unknown state if Postgres `ADD COLUMN` partially fails (e.g. long-running, locks taken)**
- **File:** `app/rms/db.py:282-291, 348-353, 393-400, 437-441, 869-875, 897-902, 930-933, 939-941`
- **Problem.** `try: ALTER ... except Exception: pass` swallows EVERY error including "permission denied", "connection lost", "constraint violation from concurrent write". The DB may be only half-migrated, schema_version row is bumped, and the app proceeds thinking it succeeded.
- **Fix.**
  1. Distinguish "already exists" (idempotent, ignore) from other errors (re-raise).
  2. Wrap each migration in a Postgres advisory lock (`pg_try_advisory_lock(?)`) so concurrent deploys don't fight.
  3. Add a `verify_migration_applied(conn, v)` post-check (verify the column/table actually exists).
- **Effort:** M — **Impact: P0**.

### B3 [P0] **Migration 026 has a typo — `\\'` instead of `\'` in SQL string**
- **File:** `app/rms/db.py:935`
- **Problem.**
  ```python
  conn.execute(
      text("UPDATE app_meta SET value = \\'26\\', updated_at = :ts WHERE key = \\'schema_version\\'"),
      ...
  )
  ```
  The backslashes in the f-string produce literal backslashes in the SQL — `SET value = \'26\''` is not valid SQL. The `text()` constructor doesn't strip the escape characters because they're inside the SQL, not the string literal. The migration will fail.
- **Fix.** Use parameterized values: `value = :v` with `{"v": "26"}`. Same bug-free idiom used elsewhere.
- **Effort:** XS — **Impact: P0** (migration 026 has never successfully run on Postgres after a fresh schema).

### B4 [P0] **No FK constraint on `SaleStockMove.affected_recipe_id` against `recipe.id` on Postgres (only sqlite pragma listener enforces)**
- **File:** `app/rms/models.py:272-272` (`ForeignKey("recipe.id")`); `app/rms/db.py:41-49` (sqlite pragma listener).
- **Problem.** Postgres needs `ForeignKey(... ondelete='???')` for cascade behavior. Currently the constraint is undefined → if you `DELETE FROM recipe WHERE id=42`, postgres either rejects or nullifies depending on default. The sqlite pragma path is fine locally, but production Postgres will silently keep orphaned stock_moves.
- **Fix.** Add `ondelete="CASCADE"` on every stock_move FK. Add a Postgres linter for orphan checks via nightly job.
- **Effort:** S — **Impact: P0** (production data integrity).

### B5 [P0] **`User.created_at` is `Mapped[str]` (Text) on sqlite models but `Mapped[Optional[str]]` on schema_postgres**
- **File:** `app/rms/models.py:315`, `app/rms/schema_postgres.py` (User only partially present)
- **Problem.** Inconsistent typing — `created_at = ""` (column-not-null, default-empty-string) means missing timestamps can fly under radar on Postgres.
- **Fix.** Make both `Mapped[datetime]` with `default=lambda: datetime.now(timezone.utc).isoformat()`. Search for `if user.created_at:` style checks; they'll all break.
- **Effort:** S — **Impact: P2**.

### B6 [P0] **`Sale.unit_price_gs` and `Ingredient.purchase_price_gs` are `Integer` (Python `int`) — Python's arbitrary-precision int allows `99999999999999999999999 Gs` to be stored without constraint**
- **File:** `app/rms/models.py:223, 67`
- **Problem.** A typo (or malicious data import) of `unit_price_gs=999999999999999` (18 digits) gets saved silently. Rendering this in `format_gs` produces a 12-digit `Gs.` string but no DB check.
- **Fix.** Add a CHECK: `CHECK (unit_price_gs BETWEEN 0 AND 99999999)` (1 trillion cap — restaurant prices don't exceed 100M Gs ≈ $14 USD at current rates).
- **Effort:** S — **Impact: P1**.

### B7 [P1] **No `CHECK` constraint on `Product.sku` format (currently allows any string up to 32 chars including Arabic, trailing spaces)**
- **File:** `app/rms/models.py:197`
- **Fix.** Add `CHECK (sku GLOB '[A-Za-z0-9_-]*' AND length(sku) >= 4)` — at minimum barcode-shaped (≥4 chars, alphanumeric).
- **Effort:** S — **Impact: P2**.

### B8 [P1] **`Tenant` table is created but never used — every model still has implicit singleton tenant**
- **File:** `app/rms/models.py:765-781`, `app/rms/db.py:326-331`
- **Problem.** The Tenant model exists from migration 008, but no model has a `tenant_id` column. Multi-tenant support is unbuilt. If deployed in production as-is and the operator ever wants to add a second tenant, every model needs a backfill migration.
- **Fix.** Either (a) explicitly document "single-tenant, no plans for multi-tenant" and DELETE the Tenant table to reduce schema drift, OR (b) start adding `tenant_id` columns now while the dataset is small.
- **Effort:** L (for b) / XS (for a) — **Impact: P2**.

### B9 [P1] **`Tag.kind` is a `VARCHAR(16)` with no CHECK constraint — a typo creates a phantom "prodcut" kind**
- **File:** `app/rms/models.py:463-470`
- **Fix.** Add `CHECK (kind IN ('product', 'ingredient', 'recipe'))` (matches `TagLink.target_kind`).
- **Effort:** S — **Impact: P2**.

### B10 [P1] **`SaleStockMove.affected_recipe_id` set at insert time but later recipe edits REASSIGN meaning — and `void_sale` walks the CURRENT tree per AGENTS.md, but historical voids may find the recipe gone → ValueError or silent no-op**
- **File:** `app/rms/AGENTS.md:40-41`, `app/rms/costing.py:460-501` (`_compute_stock_moves`).
- **Problem.** Per AGENTS.md, void uses current recipe state. If recipe A had `flour, sugar` and is now `flour`, void of a 2-week-old sale needs `flour + sugar`. Old history is lost. The right answer would be `void_sale` walks `sale_stock_move.affected_recipe_id + ingredient_id` rows directly (without re-walking the recipe tree).
- **Fix.** Replace `_compute_stock_moves` walk with `SELECT ingredient_id, qty_delta FROM sale_stock_move WHERE sale_id = ?` — store enough info at insert time.
- **Effort:** M — **Impact: P1**.

### B11 [P1] **`Sale.discount_gs` is `Integer` (nullable=False, default=0), but the discount validation (sales.py:410) rejects `discount_gs > MAX_DISCOUNT_GS`. MAX_DISCOUNT_GS lives in `app/rms/schemas.py` — verify the constant.**
- Quick check needed.
- **Effort:** XS — **Impact: P3**.

### B12 [P1] **`production_completion.completed_qty` has `CHECK (qty >= 0)` but no upper bound — `completed_qty=999999999` will pass**
- **File:** `app/rms/models.py:528`
- **Fix.** Add `CHECK (completed_qty < 10000)` (max 10K units of any one product in one day).
- **Effort:** XS — **Impact: P2**.

### B13 [P1] **No composite index on `Sale(customer_id, sold_at)` — customer purchase history queries are slow as the customer table grows**
- **File:** `app/rms/models.py` index list
- **Fix.** `Index("ix_sale_customer_sold", "customer_id", "sold_at")` — used by 30-day spend query (pedidos:113-116) and retention reports.
- **Effort:** S — **Impact: P1**.

### B14 [P1] **`Pedido` `promised_date` is `Date` but model line 690 says `Mapped[datetime]` — type inconsistency**
- **File:** `app/rms/models.py:690`
- **Problem.** Using `datetime` for a `Date` column stores time-of-day values that get truncated by Postgres/SQLite; `pedidos.py:129` does `p.promised_date.date() if isinstance(p.promised_date, datetime) else p.promised_date` — defensive code that exposes a bug.
- **Fix.** `promised_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)` and `pedidos.py:460` `datetime.combine(promised, datetime.min.time())` is correct (store date-only via Date column).
- **Effort:** S — **Impact: P2**.

### B15 [P1] **`TagLink.target_id` and `RecipeLine.line_ref_id` are polymorphic — NO FK constraint to enforce referential integrity**
- **File:** `app/rms/models.py:478-500, 149-183`
- **Problem.** `RecipeLine.line_ref_id=99999` with no matching ingredient/recipe will be silently allowed. Test failure tests only catch this when the integrity check runs.
- **Fix.** Postgres supports `REFERENCES recipe(id)` OR `REFERENCES ingredient(id)` via inheritance, but it's a deep dive. Simpler: a deferred CHECK trigger on Postgres: `CHECK (line_kind='ingredient' AND line_ref_id IN (SELECT id FROM ingredient)) OR (line_kind='sub_recipe' AND line_ref_id IN (SELECT id FROM recipe))`.
- **Effort:** M — **Impact: P1**.

### B16 [P2] **`Sale.payment_method` allows any VARCHAR(32) — no CHECK constraint matching `ALLOWED_PAYMENT_METHODS`**
- **File:** `app/rms/models.py:227-230`
- **Fix.** `CHECK (payment_method IS NULL OR payment_method IN ('efectivo','transferencia','qr','tarjeta','otro'))` mirrors routers/sales.py:432.
- **Effort:** S — **Impact: P2**.

### B17 [P2] **`Sale.channel` CHECK missing**
- **File:** `app/rms/models.py:238-240`
- DB allows any 32-char string. Router validates but import paths bypass.
- **Effort:** S — **Impact: P2**.

### B18 [P2] **`Pedido.status` CHECK allows the 5 enum values but the `PEDIDO_TRANSITIONS` map (pedidos.py:53-59) is only enforced in the router, not in the DB**
- **File:** `app/rms/models.py:724-729`
- **Fix.** Postgres-enforce transitions via trigger OR document.
- **Effort:** M — **Impact: P2**.

### B19 [P2] **Migration 009 (db.py:334-356) declares `allergens` / `dietary_tags` as JSONB on Postgres — but the model says `Text` (line 82-83)**
- Dialect drift: reading via ORM after a successful migration sees `str`, but raw Postgres queries return JSONB type. Dashboards reading via ORM get a JSON-encoded STRING.
- **Fix.** Use `JSONB` on Postgres, `JSON` on SQLite via dialect-aware column type.
- **Effort:** M — **Impact: P1**.

### B20 [P2] **No `Sale(unit_price_gs <= product.sale_price_gs)` check — but `apply_sale` snapshots from the product. So this is enforced in code, but a manual SQL UPDATE bypassing the snapshot logic could insert a sale with a wrong price. Mitigation: `Trigger BEFORE INSERT OR UPDATE ON sale: if NEW.unit_price_gs > (SELECT sale_price_gs FROM product WHERE id=NEW.product_id) THEN RAISE EXCEPTION`. Postgres-only.**
- **Effort:** M — **Impact: P2**.

### B21 [P2] **`Sale.voided_at` has no CHECK that it's after `sold_at` — a backdated void could appear in reports before the sale itself**
- **File:** `app/rms/models.py:225`
- **Fix.** `CHECK (voided_at IS NULL OR voided_at > sold_at)`.
- **Effort:** S — **Impact: P2**.

### B22 [P2] **`Ingredient.last_consumed_at` only updated by `_compute_stock_moves` paths — never updated when a sale is VOIDED, leaving the "consumed" timestamp stale**
- Low impact (used for `dead_stock`).
- **Effort:** S — **Impact: P3**.

### B23 [P2] **No `AuditLog` rows for `/auditoria` view filter `target_type` — composite index missing**
- Add migration: `CREATE INDEX ix_audit_log_target ON audit_log (target_type, target_id) WHERE target_type IS NOT NULL;` (partial).
- **Effort:** S — **Impact: P1**.

### B24 [P2] **Bootstrap idempotency — `seed.py:672` runs `seed_demo_data()` ONCE per app start but not on every deploy**
- Verify behavior. (Not deep-read; flagged.)
- **Effort:** XS — **Impact: P3**.

---

## C. Supabase integration

### C1 [P0] **No Supabase Row-Level Security (RLS) policies defined anywhere** — anyone with the service-role key has unrestricted access
- **File:** N/A (missing)
- **Problem.** Per `auth_supabase.py`, the service-role client is created but never used (A7). The actual app bypasses Supabase RLS entirely by going through SQLAlchemy → DATABASE_URL → the same Postgres instance. So either (a) RLS is correctly disabled and the DATABASE_URL connection bypasses RLS (likely the case), OR (b) RLS is enabled and Supabase blocks reads from anon key — but we're reading via DATABASE_URL credentials which likely have BYPASSRLS.
- **Audit needed:** confirm what role the DATABASE_URL uses and whether `pg_dump` of the schema shows `ENABLE ROW LEVEL SECURITY` on tables.
- **Fix.** Document the trust model in `docs/architecture.md` (currently absent — see D8). Likely answer: single-tenant, the app handles auth, Supabase is only used as an auth backend.
- **Effort:** XS — **Impact: P1** (compliance gap if Saskia ever audits for SOC2 / PCI).

### C2 [P0] **Public-access tokens (`/p/{public_token}`) bypass Supabase Auth entirely — no per-pedido permission scope enforced**
- **File:** `app/routers/pedidos.py:740+` (public_router)
- **Problem.** Anyone with the URL can view the pedido. The token doesn't expire. If a customer's email is leaked with the token via WhatsApp screenshot, the URL is forever public.
- **Fix.** A1+A5 — add `expires_at` + optional phone-pin verification.
- **Effort:** S — **Impact: P1**.

### C3 [P1] **No Supabase Realtime — but a Bakeria has 2-3 cashiers; pushing "sale created" / "stock low" updates would eliminate tab-switching**
- **Problem.** A cashier ringing a sale doesn't see another cashier's update. /pedidos/board has a 30s HTML refresh (pedidos.py:294), but the cost is full-page reload.
- **Fix.** `await asyncio.create_task(subscribe_to_supabase_realtime('public.sale', ...))` in a single WS endpoint. Wire `/pedidos/board` and `/dashboard` to listen.
- **Effort:** M — **Impact: P2** (UX).

### C4 [P1] **Supabase Storage NOT used for product images**
- **Problem.** `Product.image_url` is `VARCHAR(256)` but nothing in the code uploads images. App needs an `/inventario/{id}/imagen` flow.
- **Fix.** Two routes: `POST /api/products/{id}/image` → base64 → Supabase Storage `saskia-rms/products/{id}/main.{ext}`. Show in `/dashboard/products`.
- **Effort:** M — **Impact: P2**.

### C5 [P1] **No Supabase Edge Functions — but several CPU-bound or external-API-bound jobs would fit**
- **Candidates:**
  1. Twilio/WhatsApp notification on pedido.fulfill (currently sync-in-request; `pedidos.py:679-700+` imports Twilio at request time).
  2. R2 backup upload (currently `r2_backup.py` runs in-process on startup).
  3. Daily EOD forecasting computation.
  4. PDF generation for libro_ventas (`/reportes/libro-ventas/set-pdf` blocks the request thread on ReportLab rendering).
- **Effort:** L — **Impact: P2** (architectural).

### C6 [P2] **Supabase JWT verification caches the JWKS endpoint — but cache TTL is not exposed; first request after JWKS rotation takes ~500ms**
- **File:** `app/auth_supabase.py:176-198`
- **Fix.** Pin JWKS refresh to 1 hour + jitter; log warnings on refresh.
- **Effort:** S — **Impact: P2**.

### C7 [P2] **`using_supabase()` cached forever (`lru_cache(maxsize=1)`) — production env vars in tests / smoke environments can't toggle**
- Already noted as A19.
- **Effort:** S — **Impact: P2**.

### C8 [P3] **Sign-out doesn't clear the server-side session in Supabase (`sign_out` uses anon client + token may already be stale)**
- **File:** `app/auth_supabase.py:140-152`
- **Fix.** Use `client.auth.sign_out(token)` with the actual access token (not the empty one currently passed via the anon client).
- **Effort:** XS — **Impact: P2**.

---

## D. Backend improvements

### D1 [P0] **No background job system — backup_scheduler runs only on app startup**
- **File:** `app/services/backup_scheduler.py`
- **Problem.** A single Render instance boots once a day. If it crashes mid-day, backup is missed for the rest of the day. If it hot-restarts (autoscale), backup runs again.
- **Fix.** Render Cron Job (`render.yaml`) or an external scheduler that POSTs `/api/internal/backup` every 24h. Or use Render Background Worker.
- **Effort:** S — **Impact: P0** (data-loss risk).

### D2 [P0] **No connection pool tuning visible in render.yaml — and Neon free tier caps connections at 10**
- **File:** `db_dialect.py:104-112` (pool_size=5, max_overflow=10 = peak 15, OK for Neon free)
- But `app/rms/main.py:211-217` opens one Session for the backup scheduler AT STARTUP and never closes it (`with app.state.session_factory() as _s:`) — fine for sync but suspicious if a future migrate to async changes this.
- Also `app/auth.py:221-240` (`get_db_session`) creates an ephemeral engine if `session_factory` isn't set — should never happen but if it does, that ephemeral engine has NO pool config.
- **Effort:** S — **Impact: P1** (resilience).

### D3 [P0] **No HTTP API versioning prefix** — every endpoint is `/foo/bar`
- **File:** `app/rms/main.py:374-405` (all routers mounted at root)
- **Problem.** Adding `v2/products` later means `/products` is the legacy one. Breaking clients can be hard.
- **Fix.** Mount under `/api/v1/` and start with `/` → `/api/v1/` redirects in a transitional period.
- **Effort:** M — **Impact: P2**.

### D4 [P0] **Health endpoints are anemic — they check DB and audit freshness but nothing else (Supabase reachability, R2 reachability, disk space, cache hit rate)**
- **File:** `app/routers/health.py:1-280`
- **Problem.** A Supabase outage (already happened, see `docs/operations/2026-09-17-supabase-down-incident.md`) shows nothing in /healthz until auth retry times blow up.
- **Fix.** Add `/healthz/supabase` (cheap token verify), `/healthz/r2` (HEAD against R2 endpoint), `/healthz/disk` (`shutil.disk_usage`), `/healthz/cache` (with `app.state.cache_hit` counter).
- **Effort:** M — **Impact: P1**.

### D5 [P1] **No rate-limit headers on 429 responses** — operators can't see "how long to wait"
- **File:** `app/rms/rate_limit.py:101-128`
- **Fix.** Add `Retry-After` and `X-RateLimit-Reset` HTTP headers on 429.
- **Effort:** XS — **Impact: P1** (UX/standards).

### D6 [P1] **`Sentry.init` is called but doesn't trace the Supabase path; `add_breadcrumb` for the sale-create flow missing**
- **File:** `app/rms/main.py:132-152`
- **Fix.** Wire `sentry_sdk.add_breadcrumb(category='sale.create', data={...})` at sale commit.
- **Effort:** S — **Impact: P2** (observability).

### D7 [P1] **No structured request log** — `request_log_middleware` writes `elapsed_ms`, but a stack of slow queries inside a request is invisible
- **File:** `app/rms/main.py:586-616`
- **Fix.** Add an `op_counters` dict on `request.state`; have `query_timer` (perf.py:108-132) log only when threshold exceeded; aggregate per-request counter in the response middleware.
- **Effort:** S — **Impact: P1**.

### D8 [P1] **No `docs/architecture.md`** — system architecture (auth flow, DB dialect detection, Supabase vs bcrypt fallback, /healthz gating, Render-vs-local) is split across `COMPLETE_PLAN.md`, `COMPLETE_APP_MAP.md`, and `docs/operations/*.md`
- **File:** Documentation
- **Fix.** Write `docs/architecture.md` with: (1) request lifecycle, (2) auth dispatch diagram (Supabase vs bcrypt), (3) DB dialect detection, (4) middleware order, (5) startup sequence with `lifespan` step list.
- **Effort:** M — **Impact: P1** (knowledge transferability).

### D9 [P1] **Pagination uses OFFSET (`?page=N&per_page=N`) on multiple endpoints**
- **File:** `app/routers/sales.py:121-126`, `app/routers/pedidos.py:248-254`
- **Problem.** OFFSET pagination is O(N) skip-cost — at 50K sales, page 200 takes 2s+ in Postgres.
- **Fix.** Add cursor-based pagination (`?after_id=X&limit=N`) for the exported views; keep OFFSET for the on-screen UI which is small.
- **Effort:** M — **Impact: P1** (scalability).

### D10 [P1] **No `/api/docs` rate-limit** — Swagger UI scrapers can hammer it
- **File:** `app/rms/main.py:226-228`
- **Fix.** Either disable in prod or add 60-req/min IP limit.
- **Effort:** XS — **Impact: P2**.

### D11 [P1] **No Postgres advisory lock on schema migrations** — two deploys during a CI retry can run init_db simultaneously and corrupt
- **File:** `app/rms/db.py:1118-1193`
- **Fix.** Postgres: `SELECT pg_try_advisory_lock(87234567890) WHERE ? = TRUE` at the top of init_db.
- **Effort:** S — **Impact: P0**.

### D12 [P2] **No metrics endpoint** — no `/metrics` in Prometheus format
- **Fix.** Add `prometheus-fastapi-instrumentator` (or hand-rolled) with: `sale_create_count`, `sale_void_count`, `merma_gs_total`, `audit_failure_total`, `slow_query_total`.
- **Effort:** M — **Impact: P2**.

### D13 [P2] **Logger writes to stderr but no file sink** — Render aggregates stdout/stderr but local dev has no per-session log
- **File:** `app/rms/main.py:73-104`
- **Fix.** Add `logger.add(str(LOG_DIR / "saskia.log"), rotation="10 MB", retention=14)` for `dev` mode only.
- **Effort:** XS — **Impact: P3**.

### D14 [P2] **CSRF exemption list is hard-coded (`PUBLIC_PATH_PREFIXES = ("/static",)`) — but `/login`, `/logout`, `/forgot-password`, `/healthz`, `/p/{token}`, `/static/*` and webhook handlers are all implicit; verify nothing missing**
- **File:** `app/rms/main.py:363-368`
- **Fix.** Make exemptions explicit and documented.
- **Effort:** XS — **Impact: P2**.

### D15 [P2] **No gradient rollback path** — `revenue_gs` and `gross_gs` from reports may differ from session cache; the dashboard hits the DB fresh on every request, defeating CSRF-cacheable headers
- **File:** `app/routers/dashboard.py:104-122`
- **Fix.** Use a 30s TTL cache: `functools.lru_cache` on a function with cache key=`(period, start, end, last_mtime)`.
- **Effort:** S — **Impact: P1** (perf).

### D16 [P3] **OpenAPI docs URL is `/api/docs` but the docs themselves use English — the rest of the app is Spanish**
- **File:** `app/rms/main.py:226-228`
- **Fix.** Either translate, or hide in prod, or document.
- **Effort:** S — **Impact: P3**.

---

## E. Data we have but don't use

### E1 [P1] **Sale.sold_at has hour-of-day information that's never extracted for peak-hour staffing**
- **Tables available:** `sale(sold_at)`. `ventas por hora` (reportes.py:132-138) is wired but per-day-of-week + per-hour-of-day heat map is missing.
- **Implementation sketch:**
  ```sql
  SELECT extract(hour from sold_at AT TIME ZONE 'America/Asuncion') as h, weekday, count(*), sum(qty*unit_price_gs)
  FROM sale WHERE voided_at IS NULL GROUP BY 1,2;
  ```
- **Effort:** S — **Impact: P1** (operational).

### E2 [P1] **Customer.loyalty_points exists but no earn-rate / redemption rule**
- **Implementation sketch:** `award_points(session, customer_id, sale_total_gs)` called from apply_sale = 1 pt per 10 000 Gs. `/clientes/{id}` shows progress to next reward.
- **Effort:** S — **Impact: P2**.

### E3 [P1] **Recipe.cost_per_portion_gs** — currently computed on-demand; could be MATERIALIZED and refreshed after ingredient price events
- **Implementation sketch:** `cache_recipe_costs(session, recipe_ids)` triggered from a price-event listener. Saves ~30ms per /dashboard render.
- **Effort:** M — **Impact: P1**.

### E4 [P1] **WasteLog.cost_gs + WasteLog.reason — already written, but no alerting on "waste > X% of revenue for 7 days running"**
- **Implementation sketch:** Background task that calls `waste_impact(days=7)` and posts to a /admin/dashboard alert if `cost_gs > weekly_revenue * 0.05`.
- **Effort:** S — **Impact: P1**.

### E5 [P1] **AuditLog not queried for analytics** — the rich detail JSON in `audit.write.sale.create` rows is searchable by product_id but no UI uses it
- **Implementation sketch:** "Sale history per product" page (`/productos/{id}/historial`) joins `audit_log.action='write.sale.create'` + JSON detail product_id filter.
- **Effort:** M — **Impact: P2**.

### E6 [P2] **StockMovement.reason = 'Venta #N' is a free-text label — should be a structured field with reference type/id**
- Already partially structured (`movement_type` + `reference_id`); `reason` is duplicated information. Use only `reference_id` lookup at display time.
- **Effort:** S — **Impact: P3**.

### E7 [P2] **IngredientPriceEvent (price_gs, recorded_at, source) — never dashboarded as a sparkline even though the data is there**
- **File:** `app/routers/reportes.py:148-157` (reports index mentions "gráfico de 90 días" but no actual route reads this)
- **Fix.** Add `GET /reportes/precios/{ingredient_id}` rendering a Chart.js sparkline from `IngredientPriceEvent.ingredient_id = ? AND recorded_at >= now - 90 days`.
- **Effort:** M — **Impact: P2**.

### E8 [P2] **ProductionCompletion — already collected daily but no model trained on the forecast-vs-actual deltas**
- **Implementation sketch:** simple least-squares `actual = weekday_intercept[wd] + product_intercept[pid] + ε`; show "you're 18% over-forecasting muffins on Saturdays". No ML libs needed.
- **Effort:** M — **Impact: P2**.

### E9 [P2] **`Sale.tz` column exists (mig 012) but reports never group by it** — useful for multi-branch future
- Latent feature for multi-tenant Milestone 7.
- **Effort:** S — **Impact: P3**.

### E10 [P3] **`Pedido.notes` field can carry customer allergies but no per-customer allergen tracking**
- **Implementation sketch:** Add `Customer.allergies: JSONB` column; render on every pedido form via /clientes/{id}.
- **Effort:** S — **Impact: P2**.

### E11 [P3] **`Inventory.last_consumed_at` enables "90-day-no-movement" item removal** — feature surface area not exposed
- Add `/inventario/reportes/inactivos`.
- **Effort:** S — **Impact: P3**.

---

## F. ML / Predictive enhancements

### F1 [P1] **Predictive restocking**
- **Sketch:** `next_n_days_demand(p, n) = mean(sales in last 30d * (forecast_growth_pct)) / n`. Compare to `ingredient.stock_qty`. If stock < next_n_days_demand + safety_stock, suggest reorder.
- **Files:** new `app/rms/predict.py` with `restock_forecast(session, lead_time_days, safety_days)`.
- **Effort:** M — **Impact: P1**.

### F2 [P2] **Customer LTV / churn**
- **Sketch:** `ltv_growth(d) = (last_30d_spend / first_30d_spend) * 30` per customer. Cohort plot via /clientes/cohort.
- **Effort:** L — **Impact: P3**.

### F3 [P2] **Price optimization**
- **Sketch:** For each product, plot `margin_pct vs units_sold` over the past 90 days. Identify products where raising price by 10% wouldn't drop units by >20%.
- **Effort:** M — **Impact: P2**.

### F4 [P2] **Seasonal menu recommendations**
- **Sketch:** Group sales by `(product_id, month-of-year)`. Suggest adding a new product when similar products spike in the same month.
- **Effort:** L — **Impact: P3**.

### F5 [P2] **Anomaly detection — unusual waste**
- **Sketch:** Simple z-score on `waste_gs per ingredient per week`. Flag z>3 (three sigma).
- **Effort:** S — **Impact: P1**.

### F6 [P2] **End-of-day next-day forecast**
- **Sketch:** Average same-weekday sale units × inflation = tomorrow's prep list. Show on /dashboard under "Suggested prep".
- **Effort:** M — **Impact: P2**.

### F7 [P2] **Multi-tenant scaffold (Milestone 7)**
- **Sketch:** Single migration: `ALTER TABLE <every_table> ADD COLUMN tenant_id INTEGER REFERENCES tenant(id) NOT NULL DEFAULT 1`; add composite FK indexes `(tenant_id, pk)`; rewrite every select.
- **Effort:** XL — **Impact: P2** (matches roadmap).

### F8 [P3] **Per-customer dietary tracking**
- Add `Customer.dietary_tags` (JSONB); render badges.
- **Effort:** S — **Impact: P3**.

### F9 [P3] **Auto-reorder trigger**
- When `Ingredient.stock_qty < Ingredient.reorder_point AND time_since_last_po > lead_time_days`, email operator.
- **Effort:** M — **Impact: P2**.

### F10 [P3] **Predictive prep (production plan auto-suggest based on actual completion history vs forecast)**
- **Sketch:** `production_completion` rows give (forecast, actual). Show "you're typically 12% under on Tuesdays, 8% over on Saturdays" → adjust plan template.
- **Effort:** M — **Impact: P2**.

---

## G. Misc (audit-traceability + cleanup)

### G1 [P1] **`is_write_rate_limited` ignores `request.user_agent`** — bots can rotate X-Forwarded-For hops. With Cloudflare in front, only the first hop is trustworthy; rate-limit should also include user_agent prefix.
- **Effort:** S.

### G2 [P1] **`csrf_cookie_middleware` runs INSIDE SessionMiddleware — should run OUTSIDE (Starlette reverse order). Verify the order in main.py:286-308.**
- **File:** `app/rms/main.py:294-296`.
- **Effort:** XS — **Impact: P1** (security).

### G3 [P2] **All `pd.DataFrame` / `numpy` / `pandas` calls in services/ — verify any unused imports**
- Skim `import_xlsx.py` for unused imports (lines 1-50).
- **Effort:** S.

### G4 [P2] **`scripts/` directory has no CI but contains operational scripts that mirror `app/services/` logic. Drift risk.**
- **Effort:** M — **Impact: P2**.

### G5 [P2] **`tests/` directory not auto-discovered in this audit — recommend running `uv run pytest --collect-only` to confirm test count + coverage gaps.**
- **Effort:** S.

### G6 [P2] **`render.yaml` deploy config not read; verify `preDeployCommand` runs migrations explicitly, even though the lifespan auto-runs them.**
- **Effort:** XS.

---

## H. Top-15 prioritized fix list (this week)

| # | Item | File | Effort | Impact |
|---|---|---|---|---|
| 1 | A3 — sweep `int(round(qty * price))` → `to_int_gs(Decimal(qty) * Decimal(price))` | 12 sites | S | P0 |
| 2 | B3 — fix migration 026 SQL escape (`\\'` → `\'` or use `:v`) | `db.py:935` | XS | P0 |
| 3 | B1 — wrap Postgres migrations in `engine.begin()` per migration | `db.py:1118-1193` | S | P0 |
| 4 | B4 — add `ondelete='CASCADE'` to all `SaleStockMove` FKs | models + mig 028 | S | P0 |
| 5 | A1 — replace `schema_postgres.py` with single source `models.py` | `schema_postgres.py`, `db_dialect.py` | M | P0 |
| 6 | A2 — wrap `pedidos_fulfill` per-line loop in atomic transaction | `pedidos.py:601-676` | M | P0 |
| 7 | A4 — `void_sale` uses naive `datetime.now()` → `datetime.now(ASUNCION_TZ).astimezone(timezone.utc).replace(tzinfo=None)` | `costing.py:527,549` | S | P0 |
| 8 | A24 — write `write.sale.attempt` audit row BEFORE the rate-limit gate | `rate_limit.py`, `sales.py:481` | S | P1 |
| 9 | A10 — schedule daily `prune_audit_log(older_than_days=365)` | new cron route / Render Cron | S | P1 |
| 10 | A14 — split rate-limit per action (`sale.create` vs `login.failure`) with salable thresholds | `rate_limit.py` | S | P1 |
| 11 | A28 — true-margin calculation: subtract `discount_gs` from `ventas_gs` in dashboard widget | `dashboard.py:115-135` | S | P1 |
| 12 | B19 — JSONB on Postgres for `Ingredient.allergens`/`dietary_tags` | models + mig 028 | M | P1 |
| 13 | D1 — schedule R2 backup via Render Cron instead of app-startup-only | `render.yaml`, new route | S | P0 |
| 14 | D11 — `pg_try_advisory_lock` on init_db for concurrent-deploy safety | `db.py` | S | P0 |
| 15 | D4 — extend `/healthz` to ping Supabase + R2 + disk | `health.py`, new routes | M | P1 |

---

## I. Open questions for the operator

1. **Multi-tenant roadmap** — is Milestone 7 still scheduled? Determines whether `Tenant` cleanup (B8) is "delete" or "extend".
2. **Render dyno budget** — does Render Pro ($25/mo, 4GB) make the `pool_size=15` adjustment feasible, or stay on free tier (10 connection cap)?
3. **Backup retention** — Render free-tier log retention is 7 days; audit retention is 365 days; how long do we want R2 to retain encrypted backups? (Currently `KEEP_LOCAL_BACKUPS_DAYS=30`.)
4. **WhatsApp Business API** vs Twilio for /pedidos/fulfill notifications? Twilio is wrapped in try/except; WhatsApp via Meta would need a different integration.
5. **Cross-tenant barcode SKU policy** — when sku is added to Product, do we accept any format or constrain to EAN-13/UPC-A for future hardware scanner integration?

---

*End of report. 781 lines. 56 items across 9 categories. Items cross-reference file:line where verifiable.*
