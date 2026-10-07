# Saskia — Architecture & Design Principles Refactor Plan

**Date:** 2026-09-24
**Scope:** `/opt/data/scratch/saskia-app/app/` (~30K LOC, 1,999 tests, 6 in-flight branches)
**Method:** 3 parallel subagents scanned SOLID/architecture, performance/concurrency, and types/validation. ~60 grounded findings with file:line, named principle, and worst-case consequence. This plan groups findings into actionable phases.

---

## Executive Summary

**Health score: 6/10** — Functional, well-tested, but accumulating technical debt that already produces incidents (2026-09-08 Neon outage, 2026-09-22 schema_postgres drift). The codebase is **at the inflection point where refactoring becomes cheaper than continuing to patch around the smells.**

**Top 3 architectural bottlenecks** (each ties to multiple findings + recent incidents):

1. **Atomicity / Idempotency violations in money paths** — `sales.py:553` and `pedidos.py:757` commit before consulting idempotency keys. This is a **regulatory risk** (duplicate fiscal invoices, double stock deductions) under Paraguayan tax authority (SET) requirements. *Findings: F2, F3, F10, F9.*
2. **God-files with cross-cutting concerns inlined** — `app/rms/db.py` (1670 LOC, 38 migrations + engine + drift + meta), `app/rms/models.py` (1350 LOC, 30+ ORM classes across 8 domains), `app/rms/main.py` (866 LOC, 7-job lifespan). Merge conflicts block every PR. *Findings: SRP-2, Modularity, Bootstrap.*
3. **Pydantic Contracts absent on 21 of 25 routers** — Zero `response_model=` on state-changing POST endpoints. API surface is implicit; refactoring an ORM field breaks no test because nothing pins the contract. *Findings: Contract, Payload, LSP.*

**What is NOT broken:** test coverage (~2K tests, mostly green), domain modeling (the SQLAlchemy models are sound, they just live in the wrong file), operator ergonomics (CHANGELOG discipline, drift gate, runtime fail-fast already shipped today).

---

## Mapping: Principles → Grounded Findings

The plan below applies ALL the principles you listed. The principle column tells you which findings each phase addresses — every finding traces back to a subagent scan report (F1–F60).

| Principle | Findings (where violated) | Phase |
|---|---|---|
| **Idempotency** | F2 (sales.py:553), F3 (pedidos.py:757) | Phase 1A |
| **Atomic Operation** | F4, F18 (50+ bare commits), F9 (rate_limit) | Phase 1A |
| **Concurrency** | F10 (no FOR UPDATE), F16 (function-attribute state) | Phase 1A |
| **Fail-Fast** | F4 (migrations), F12 (silent except: pass x84), F6, F8 | Phase 1B |
| **Sanitization** | F4 (f-string DDL), F6 (any-typed audit) | Phase 1B |
| **Bounded Context** | SRP-2 (models.py), Modularity (routers/pedidos.py 1165 LOC, herebus.py 831) | Phase 2A |
| **Open/Closed** | OC-1 (MIGRATIONS dict), OC-2 (PEDIDO_TRANSITIONS), OC-3 (herebus router wiring) | Phase 2A |
| **Liskov Substitution** | LSP-1 (pedidos_fulfill vs pedidos_bulk_fulfill) | Phase 2A |
| **Registry** | R-1 (PEDIDO_TRANSITIONS dict), R-2 (ingredient_intel 5 keyword dicts), R-3 (MIGRATIONS) | Phase 2A |
| **Interface Segregation** | IS-1 (costing.py:355 9-param), IS-2 (accounting.py 8 funcs share window+mode) | Phase 2A |
| **Discriminated Union** | DU-1 (pedido.status str), DU-2 (Sale.channel/payment_method/invoice_type) | Phase 2A |
| **Discriminator / Canonical** | C-1 (channels defined twice), C-2 (5 query copies in sales.py:105-141) | Phase 2A |
| **Decoupling / Dependency Inversion** | DI-1 (accounting.py imports ORM), DI-2 (main.py imports private symbols), DI-3 (auth→schema_postgres) | Phase 2B |
| **Adapters / Facade** | A-1 (db_dialect parallel adapter), F-1 (db.py exposes 13 symbols) | Phase 2B |
| **Modularization** | M-1 (db.py split), M-2 (models.py split), M-3 (herebus.py split) | Phase 2B |
| **Bootstrap** | B-1 (lifespan 7 jobs, 866 LOC main.py) | Phase 2B |
| **Middleware** | MW-1 (accounting.py:189-198 inlines name lookup), MW-2 (audit/observability parallel APIs) | Phase 2C |
| **Parameter Object** | PO-1 (products.py 12-param form), PO-2 (pedidos.py:367 Form signature lies) | Phase 2C |
| **Method Extraction** | ME-1 (pedidos.py:367-570 200 LOC), ME-2 (db.py:1356 _bump_schema_version), ME-3 (lifespan), ME-4 (import_xlsx 190 LOC) | Phase 2C |
| **Contract** | C-1 (no Pydantic DTOs on 21 routers) | Phase 3A |
| **Payload** | C-1 (ORM leak in responses) | Phase 3A |
| **Strict Typing** | T-1 (Optional in auth.py vs `|` elsewhere), T-2 (comment-typed insights.py), T-3 (Any in audit/backup) | Phase 3A |
| **Runtime Validation** | C-1 (no request schemas) | Phase 3A |
| **Self-Documenting** | T-2 (`p, x, tmp, data`) | Phase 3A |
| **Side-Effect-Free** | SF-1 (audit/observability dual API), SF-2 (lifespan mutations) | Phase 3A |
| **Telemetry / Instrumentation** | Tel-1 (no metrics counters), Tel-2 (silent except), Tel-3 (no OTel) | Phase 3A |
| **Memoization** | Mem-1 (auth dispatch re-imports every call) | Phase 3B |
| **Lazy Evaluation** | LE-1 (Supabase client pre-warm OK, others eager) | Phase 3B |
| **Pipelining** | P-1 (search.py 4 sequential queries) | Phase 3B |
| **Batching** | N+1 (F5 pedidos, F6 food_cost, F7 backup restore) | Phase 3B |
| **Circuit Breaker** | CB-1 (Twilio in request path), CB-2 (R2 storage) | Phase 3B |
| **Worker Pool** | WP-1 (XLSX import in POST handler) | Phase 3B |
| **Connection Pooling** | F1 (auth/dependencies ad-hoc engines) | Phase 3B |
| **Determinism** | D-1 (datetime.now() in business logic), D-2 (secrets truncation) | Phase 3B |
| **Immutability** | I-1 (analytics dataclasses not frozen) | Phase 3C |
| **Guard Clause** | GC-1 (pedidos_fulfill 4-nest), GC-2 (costing.py:130-185 3-nest) | Phase 3C |
| **Inline Temp** | IT-1 (costing/accounting single-use locals) | Phase 3C |
| **Pruning / Dead Code** | DC-1 (settings_original.py 416 LOC), DC-2 (_StaticFiles re-export), DC-3 (schema_postgres.py — already in cleanup branch), DC-4 (accounting.py:299 `expenses_gs=0` placeholder) | Phase 3C |
| **Consolidation** | Con-1 (sales_intel.py duplicated threshold logic), Con-2 (accounting.py 8× same query), Con-3 (audit/observability parallel APIs) | Phase 3C |
| **Deprecation** | DP-1 (settings_original.py) | Phase 3C |
| **Tree Shaking** | TS-1 (auto — covered by ruff F401 lint after pruning) | Phase 3C |
| **Shotgun Surgery** | SS-1 (Pedido.status change = 5 files), SS-2 (invoice_type change = 4 files), SS-3 (Ingredient column = 5 files) | Phase 3C |
| **Feature Envy** | FE-1 (accounting.py talks to Sale/Ingredient more than itself) | Phase 3C |
| **Primitive Obsession** | PO-1 (channel/payment_method/invoice_type/status as strings) | Phase 3C |
| **Throttling / Debouncing** | TL-1 (rate_limit check-then-act race) | Phase 3C |
| **Backpressure** | BP-1 (long ops in request path) | Phase 3C |
| **Jitter** | (no retries exist yet — Phase 3B) | — |
| **Zero-Copy** | (Python; not a hot path issue today) | — |
| **Vectorization** | (already used in analytics where appropriate) | — |
| **Type Narrowing** | TN-1 (manual `(ln.qty or 0)` instead of isinstance narrowing) | Phase 3A |

---

## Coordination With In-Flight Branches

| Branch | Status | Plan relationship |
|---|---|---|
| `fix/postgres-schema-drift` | MERGEABLE | Already shipped; drift detection underlying this plan |
| `cleanup/remove-schema-postgres` | MERGEABLE | Removes DC-3 (schema_postgres.py) — merges cleanly with Phase 1 |
| `feature/drift-to-startup` | MERGEABLE | Adds runtime gate; complements Phase 1A atomicity fixes |
| `ci/schema-drift-gate` | MERGEABLE | Adds CI gate; covers Drift-Detection portion of Phase 1A |
| `refactor/models-split-by-domain` | IN-PROGRESS | Hits M-2 (models.py split). Land before Phase 2A begins. |
| `fix/p0-apply-sale-pedidos-fulfill-atomicity` | IN-PROGRESS | Hits F2, F3. **Critical: this is Phase 1A. Land before anything else.** |
| `refactor/phase1-phase2` | IN-PROGRESS | Unknown contents — needs inventory before Phase 2 starts |

**Dependency:** Phase 1A depends on `fix/p0-apply-sale-pedidos-fulfill-atomicity` (F2/F3) landing first or in parallel. Phase 2A depends on `refactor/models-split-by-domain` (M-2). Phase 2B/C depend on the audit-of-`refactor/phase1-phase2`.

---

## Phase 1 — Quick Wins (atomicity, fail-fast, observability)

**Why first:** These are the bugs that can lose data or money. They are surgical (single-file changes), each has a known reproduction, and the test infrastructure already exists.

**Effort:** 1–2 days per ticket. **Impact:** Eliminates the regulatory-risk bugs and the silent-failure data drift that the audit referenced.

### 1A. Money-path atomicity (CRITICAL — land first)

| # | Finding | File:Line | Fix sketch | Test |
|---|---|---|---|---|
| 1 | F2 — Sale idempotency-after-commit | `app/routers/sales.py:553–574` | Move `idempotency_key` INSERT to BEFORE Sale INSERT, in same transaction. Wrap entire flow in one `try/except IntegrityError: rollback; return existing`. | Existing `test_apply_sale_atomicity` + new `test_sale_duplicate_post_returns_existing_sale` |
| 2 | F3 — Pedido fulfillment race | `app/routers/pedidos.py:757–771` | Same pattern: `pedido_fulfill_idem:*` INSERT first, catch IntegrityError to return early. | Existing `test_pedidos_fulfill_atomicity` + new `test_fulfill_concurrent_double_stock` |
| 3 | F10 — Missing FOR UPDATE on invoice counter | `app/rms/invoicing.py:80+` | Wrap `SELECT ComplianceInfo.next_factura_number` with `.with_for_update()` on Postgres; SQLite uses single-writer serialization. | New `test_invoice_number_concurrent_no_collision` (use threading) |
| 4 | F16 — Function-attribute shared state | `app/routers/sales.py:593` | Replace `_fire_printer_for_sale._last_sale_id` with `request.app.state.last_printer_sale_id` (lifespan-initialized) OR pass `last_sale_id` via Depends. | New `test_printer_state_isolated_per_request` |
| 5 | F9 — Rate limit check-then-act race | `app/rms/rate_limit.py:164–176` | Use `INSERT ... ON CONFLICT DO UPDATE` with `RETURNING count` to atomically increment and read. | New `test_rate_limit_concurrent_no_bypass` |
| 6 | F18 — Bare `commit()` no rollback (50+ sites) | Across all routers | Add a `safe_commit(session)` helper in `app/rms/db.py` that wraps `commit()` in `try/except/rollback`. Replace bare commits in critical paths (sales, pedidos, inventory). | New `test_safe_commit_rolls_back_on_integrity_error` |

**Acceptance:** All atomicity tests green; manual concurrency stress test (50 parallel POSTs to /ventas/nueva) produces exactly 50 unique sales.

### 1B. Fail-fast + observability

| # | Finding | File:Line | Fix sketch | Test |
|---|---|---|---|---|
| 7 | F12 — Silent `except Exception: pass` (84 sites) | 12+ routers | Replace with `except Exception as e: logger.exception(...)` + re-raise for hot paths; keep silent only where the design says "best-effort" (e.g. CSV row skip). Add a `# noqa: BLE001` + justification comment per retained site. | Lint rule via ruff `B904` or custom check. |
| 8 | F4 — Migrations swallow DDL errors | `app/rms/db.py:277,332,353,…` | Add `logger.exception` per swallowed exception; collect failures into a list surfaced at end of `_init_db_inner`; if any failed, raise with table+column context. | New `test_migration_ddl_error_logs_and_raises` |
| 9 | F8 — `verify_password` returns False on every error | `app/auth.py:95–104` | Split into `verify_password(plain, hash)` (returns False on known-bad-format) and `verify_password_or_raise(...)` for paths that want to distinguish corruption. | New `test_corrupt_hash_returns_distinguishable_error` |
| 10 | Tel-2 — Missing request_id on idempotency keys | sales.py:600, pedidos.py:770 | Add `request_id` column to idempotency tables (or include in value JSON). | New `test_idempotency_record_carries_request_id` |
| 11 | F14 — Non-deterministic `datetime.now()` | sales.py:597, pedidos.py:767, +6 more | Inject a `clock: Callable[[], datetime]` via FastAPI dependency; default to `datetime.utcnow` but tests can override. | Refactor only; behavior unchanged. |

**Acceptance:** Ruff passes; sample migration failure now logs `table=foo col=bar error=...`; pytest `-k concurrency` all green.

---

## Phase 2 — Structural Refactors (bounded contexts, decoupling, contracts)

**Why second:** Money-path is safe, now we untangle the god-files so future features don't compound the smells. Each ticket here is a multi-file PR with regression risk; needs the Phase 1 tests as a safety net.

**Effort:** 3–7 days per ticket. **Impact:** Unblocks parallel development, enables test isolation, reduces merge-conflict surface.

### 2A. Bounded contexts (split the god-files)

| # | Finding | File:Line | Fix sketch | Test |
|---|---|---|---|---|
| 12 | SRP-2 / M-2 — `models.py` 1350 LOC | `app/rms/models.py` | Per-domain modules (`models/auth.py`, `models/inventory.py`, `models/sales.py`, `models/recipes.py`, `models/pedidos.py`, `models/herebus.py`, `models/compliance.py`, `models/settings.py`). Re-export via `models/__init__.py`. **Already in progress:** `refactor/models-split-by-domain` branch. | Already covered by `test_*` suites — every domain has tests. |
| 13 | M-3 — `routers/pedidos.py` 1165 LOC | `app/routers/pedidos.py` | Split into `pedidos_api.py` (JSON), `pedidos_pages.py` (HTML), `pedidos_public.py` (token endpoints). Keep `pedidos.py` as a re-export hub. | Existing tests; new module imports. |
| 14 | M-3 — `routers/herebus.py` 831 LOC, 8 sub-routers | `app/routers/herebus.py` | Each sub-router (wishlist/riesgos/pricing/bank/benchmarks/dashboard/planner/delivery) becomes its own file under `routers/herebus/`. | Existing tests. |
| 15 | SRP-1 / M-1 — `db.py` 1670 LOC, 38 migrations | `app/rms/db.py` | Split migrations to `db/migrations/NNN_<name>.py` loaded via `pkgutil.iter_modules`. Keep engine/session/drift in `db/__init__.py`. **Cross-cuts with** OC-1 (Open/Closed migration registry). | New `test_migration_loaded_via_pkgutil` |

### 2A-Open/Closed + Registry

| # | Finding | Fix sketch | Test |
|---|---|---|---|
| 16 | OC-1 — `MIGRATIONS` dict requires 3-place edit per migration | Replace dict with `iter_modules`-loaded registry; migration N's filename = migration N. Self-registering. | New `test_migration_n_plus_1_auto_picked_up` |
| 17 | OC-2 / R-1 — `PEDIDO_TRANSITIONS` plain dict | Introduce `PedidoStatus(str, Enum)` and `PedidoStateMachine` class with `transition(from_status, to_status, session, pedido)` method that validates + persists + fires side-effects. Eliminates 5 if/elif branches at :605, :632, :728, :1098, :1142. | New `test_pedido_state_machine_validates_transitions` |
| 18 | DU-1 — Pedido.status is str | Use `PedidoStatus` enum column via SQLAlchemy `Enum` type. | New `test_invalid_pedido_status_rejected_at_db` |
| 19 | DU-2 — Sale.channel/payment_method/invoice_type are str | Define `SaleChannel(str, Enum)`, `PaymentMethod(str, Enum)`, `InvoiceType(str, Enum)`. | Migrate test fixtures; new contract tests. |
| 20 | C-1 — Two channel lists (sales vs pedidos) | Single `Channel` enum referenced by both. | New `test_canonical_channel_used_by_both_subsystems` |
| 21 | R-2 — Ingredient classifiers (5 keyword dicts) | Move to `app/rms/ingredient_intel/_classifiers/{category,subcategory,role,allergen,storage}.py` with uniform `Classifier` protocol. | Refactor only; behavior unchanged. |
| 22 | OC-3 — `routers/herebus.py` router registration in main.py | Introduce `ROUTER_REGISTRY` dict in `app/rms/router_registry.py`; main.py loops over it. New modules add one entry. | New `test_router_registry_discovers_modules` |

### 2A-LSP / IS / Canonical consolidation

| # | Finding | Fix sketch | Test |
|---|---|---|---|
| 23 | LSP-1 — pedidos_fulfill vs pedidos_bulk_fulfill disagree on preconditions | Extract `_check_fulfillable(pedido) -> tuple[bool, str]` shared by both endpoints. | New `test_fulfill_precondition_unified` |
| 24 | IS-1 — `apply_sale` 9-param | Introduce `ApplySaleContext` dataclass (product_id, qty, sold_at, customer_id, payment_method, channel, discount_gs, notes). | Refactor only. |
| 25 | IS-2 — Accounting 8 functions all take `(start, end, tax_mode)` | Introduce `ReportWindow` dataclass; threading tz-aware semantics becomes one edit. | Refactor only. |
| 26 | C-1 — `accounting.py` 8× same `select(Sale).where(...)` query | Extract `sales_in_window(session, start, end, *, voided_only=False) -> list[Sale]`. 8 callers use it. | Refactor only. |
| 27 | C-2 — Sales search 3× OR filter | Extract `_apply_sales_search_filter(q, search_text)` used by `sales_q`, `count_q`, `totals_q`. | New `test_sales_search_count_page_csv_agree` |

### 2B. Decoupling + Dependency Inversion

| # | Finding | Fix sketch | Test |
|---|---|---|---|
| 28 | DI-1 — accounting.py imports concrete ORM | Introduce `ReportRepository` protocol in `app/rms/accounting/ports.py`. Real implementation wraps session; tests use in-memory fake. | New `test_accounting_decoupled_from_orm_via_protocol` |
| 29 | DI-2 — main.py imports private `_is_postgres` | Add public `is_postgres_url(url)` to db_dialect. Remove underscore-prefixed public-ish usage. | Lint rule. |
| 30 | A-1 — `make_engine_dialect` parallels `make_engine` | Pick one as canonical (db_dialect, since it handles env), delete the other. | Existing tests use session_factory, which is unaffected. |
| 31 | F-1 — `db.py` exports 13 public symbols | Split: `db/engine.py` (engine+session), `db/migrations/` (loader), `db/drift.py` (verify), `db/meta.py` (app_meta CRUD). Re-export from `db/__init__.py`. | New `test_db_module_surface_narrowed` |

### 2B-Bootstrap + Middleware

| # | Finding | Fix sketch | Test |
|---|---|---|---|
| 32 | B-1 — `lifespan` 7 jobs, 866 LOC main.py | Extract per-task functions: `sentry_init(app)`, `engine_init(app)`, `migrate_and_drift(app)`, `password_sync(app)`, `haccp_seed(app)`, `supabase_prewarm(app)`, `backup_scheduler_start(app)`. Lifespan calls them in order. Each function has its own try/except. | New `test_lifespan_each_step_has_isolated_failure` |
| 33 | ME-3 — `lifespan` 180 LOC | Subsumed by #32. | (same) |
| 34 | ME-1 — `pedidos_create` 200 LOC | Extract `_validate_customer`, `_build_pedido_from_form`, `_create_lines`, `_notify`. Compose. | New `test_pedidos_create_composition_pieces` |
| 35 | ME-2 — `_bump_schema_version` 65 LOC nested try/except | Extract `_pg_upsert_with_savepoint(conn, key, value)` and `_sqlite_upsert(conn, key, value)`. Top-level picks dialect. | Refactor only. |
| 36 | ME-4 — `import_xlsx._import_full` 190 LOC, 7 sheets in one loop | Extract per-sheet `_import_<sheet>(session, df, errors)` functions. _import_full becomes a dispatch loop. | New `test_xlsx_import_per_sheet_isolation` |
| 37 | MW-1 — accounting.py:189-198 inlines name lookup | Use `selectinload(Sale.customer)` or expose `session.expire_all()` policy in `app/rms/observability.py` as a Session-extending middleware. | New `test_report_customer_name_lookup_is_one_query` |
| 38 | MW-2 — audit/observability dual API | Pick `audit.record(session, ...)` as canonical. Have observability.record_audit call into audit.record with structured detail. Mark deprecated. | Refactor only. |

### 2C. Parameter Objects + Extraction (Phase 2 finish-line)

| # | Finding | Fix sketch | Test |
|---|---|---|---|
| 39 | PO-1 — products.py 12-param form | Introduce `ProductCreateForm` Pydantic model with `Form()` fields. | Existing tests use form-encoded POST. |
| 40 | PO-2 — sales.py 13-param form | Introduce `SaleCreateForm`. | Existing tests. |
| 41 | settings.py 18-param form | Introduce `BusinessSettingsForm`. | Existing tests. |
| 42 | pedidos.py:367 Form signature lies | Pydantic `PedidoCreateForm` matching actual fields read. | New `test_pedido_form_signature_matches_runtime` |

---

## Phase 3 — Deep Architecture (contracts, telemetry, perf, cleanup)

**Why last:** Phase 3 work is open-ended — could be partial-month projects. Each ticket here either enables future work or removes a debt that compounds over time.

**Effort:** 1–4 weeks per ticket depending on scope. **Impact:** API contracts enable client SDKs, telemetry enables SLO-driven ops, perf fixes unblock scale.

### 3A. Contracts + Type System (BIG — multi-week)

| # | Finding | Fix sketch | Test |
|---|---|---|---|
| 43 | Contract — 21 routers with no `response_model=` | Add Pydantic response DTOs to every POST/PUT. Start with sales, pedidos, products, recipes (the money/audit paths). Reuse enums from Phase 2A. | New `test_every_post_endpoint_has_response_schema` |
| 44 | Payload — ORM models leak into responses | DTOs translate from ORM. No raw ORM in API responses. | (covered by #43) |
| 45 | T-1 — `Optional[T]` in auth.py vs `T \| None` | Mechanical replacement. | Lint rule via ruff UP007. |
| 46 | T-2 — Comment-typed code (`# ProductionPlan list`) | Replace with real types or `from __future__ import annotations`. | Lint rule. |
| 47 | T-3 / TN-1 — `Any` in audit/backup/insights; manual `(ln.qty or 0)` | Define `AuditRow`, `BackupRow` typed dicts (or dataclasses); narrow via `isinstance(ln.qty, (int, float))`. | New `test_audit_function_signature_strict` |
| 48 | Runtime Validation — request bodies | Pydantic models on POST request bodies (where not form-encoded). | New `test_every_post_validates_input_via_pydantic` |
| 49 | SF-1 — audit/observability dual API | (covered by #38) | (covered) |

### 3A-Telemetry (BIG — observability investment)

| # | Finding | Fix sketch | Test |
|---|---|---|---|
| 50 | Tel-1 — No metrics counters | Add `prometheus_client` integration in `app/rms/metrics.py`: counters for endpoint hits/errors, histograms for latency, gauges for DB pool size. `/metrics` endpoint (gated by env). | New `test_metrics_endpoint_exposes_expected_names` |
| 51 | Tel-3 — No OTel tracing | Wrap SQLAlchemy + httpx + FastAPI with OpenTelemetry. Span propagation via request_id. | New `test_otel_spans_attach_to_request` |
| 52 | MW-2 — Audit trail gaps | Wrap `audit.record` with retries + circuit breaker (see Phase 3B). On failure, emit loguru CRITICAL with request_id. | (covered by Tel) |

### 3B. Performance & Concurrency (BIG — multi-week)

| # | Finding | Fix sketch | Test |
|---|---|---|---|
| 53 | F1 — Ad-hoc engines per request (auth, dependencies) | Both paths should `app.state.session_factory()` instead of creating engines. | New `test_no_ad_hoc_engine_under_load` |
| 54 | F5 — N+1 `_customer_30d_spend_gs` per pedido | Single GROUP BY query, then dict lookup. | New `test_pedidos_list_uses_single_aggregate_query` |
| 55 | F6 — N+1 `_recipe_total_cost` Ingredient fetch | `selectinload(Recipe.lines).joinedload(Ingredient)`. | New `test_recipe_cost_uses_selectinload` |
| 56 | F7 — `restore_database` per-row merge | `bulk_save_objects` + `executemany`. | New `test_restore_uses_bulk_insert` |
| 57 | P-1 — search.py 4 sequential queries | `asyncio.gather` with thread-pool offload. | New `test_search_uses_concurrent_queries` |
| 58 | CB-1 — Twilio in request path | Move to worker queue (rq or arq); POST returns 202 with job_id. | New `test_twilio_call_dispatched_to_queue` |
| 59 | CB-2 — R2 storage no breaker | Wrap with `tenacity` retry + circuit breaker. | New `test_r2_storage_retries_on_transient` |
| 60 | WP-1 — XLSX import in POST handler | Same worker queue pattern; POST returns 202 + progress polling endpoint. | New `test_xlsx_import_dispatched_to_worker` |
| 61 | Mem-1 — Auth dispatch re-imports every call | `@lru_cache` on `_supabase_enabled()` (already exists) but the dispatch dict lookup should also cache. | New `test_auth_dispatch_memoized` |
| 62 | D-1 — `datetime.now()` everywhere | `Clock` protocol injected via FastAPI `Depends`. | Refactor; behavior unchanged. |
| 63 | LE-1 — Eager computation | (mostly OK after Phase 1B's clock injection; revisit per-route as needed) | n/a |

### 3C. Cleanup, Consolidation, Decay-prevention

| # | Finding | Fix sketch | Test |
|---|---|---|---|
| 64 | DC-1 — `settings_original.py` 416 LOC orphaned | Delete. Add `git rm` + CHANGELOG entry. | (covered by ruff) |
| 65 | DC-2 — `_StaticFiles` re-export never used | Delete the import. | (covered by ruff F401) |
| 66 | DC-4 — accounting.py:299 `expenses_gs=0` placeholder | Either implement the missing Expense model or rename to `_expenses_unavailable` and add `# TODO(n)` with linked audit ticket. | (covered by lint) |
| 67 | DP-1 — Deprecation of `settings_original` (covered by 64) | n/a | n/a |
| 68 | TS-1 — Tree shaking | Run ruff `F401`, `F841` in CI as blocking. | (CI gate) |
| 69 | SS-1/2/3 — Shotgun surgery on Pedido.status / invoice_type / Ingredient | Mitigated by Phase 2A enums + per-domain model split. Tests on enum transitions replace 5-place edits. | (covered) |
| 70 | FE-1 — accounting.py talks to Sale more than itself | After #28's Repository pattern, FE-1 is structurally impossible. | (covered) |
| 71 | PO-1 — Primitive obsession (channels/methods/statuses) | All enums by Phase 2A. | (covered) |
| 72 | TL-1 — Rate limit check-then-act | Atomic upsert in Phase 1A. | (covered) |
| 73 | GC-1/2 — Deep nesting | Apply during Phase 2C method extraction. | (covered) |
| 74 | IT-1 — Inline temp | Apply during Phase 2C refactors. | (covered) |
| 75 | I-1 — Analytics dataclasses not frozen | Mechanical `@dataclass(frozen=True, slots=True)`. | New `test_analytics_dataclasses_are_frozen` |
| 76 | Con-1 — Sales_intel threshold logic duplicated | After 2A's registry pattern, consolidate. | New `test_sales_intel_trend_logic_unified` |
| 77 | Con-3 — Audit/observability consolidation | (covered by #38, #49) | (covered) |
| 78 | BP-1 — Backpressure on long ops | (covered by worker queue in 58/60) | (covered) |

---

## Sequenced Roadmap

```
WEEK 1    ── Phase 1A: Money-path atomicity ─────────────────────► [MERGE]
            └─ depends on: fix/p0-apply-sale-pedidos-fulfill-atomicity
            └─ ticket #1-6, ~1 dev-day each

WEEK 2    ── Phase 1B: Fail-fast + observability ────────────────► [MERGE]
            └─ ticket #7-11

WEEK 3-4  ── Phase 2A-BoundedContexts (models + routers split) ──► [MERGE in waves]
            └─ depends on: refactor/models-split-by-domain
            └─ ticket #12-15

WEEK 5-6  ── Phase 2A-Open/Closed + Enums ──────────────────────► [MERGE]
            └─ ticket #16-22

WEEK 7-8  ── Phase 2A-LSP/IS/Canonical ────────────────────────► [MERGE]
            └─ ticket #23-27

WEEK 9-10 ── Phase 2B-Decoupling + Bootstrap ───────────────────► [MERGE]
            └─ ticket #28-38

WEEK 11-12 ── Phase 2C-Parameter Objects + Extraction ─────────► [MERGE]
            └─ ticket #39-42

WEEK 13-18 ── Phase 3A-Contracts + Types ────────────────────────► [MERGE]
            └─ ticket #43-52
            └─ multi-week; gate on internal SDK consumers

WEEK 19-22 ── Phase 3B-Performance & Concurrency ──────────────► [MERGE]
            └─ ticket #53-63
            └─ requires perf baseline established first

WEEK 23+   ── Phase 3C-Cleanup & Decay-prevention ────────────► [MERGE]
            └─ ticket #64-78 (mostly covered by earlier phases)
            └─ add CI gates to prevent regression
```

---

## Before/After Example: Phase 1A #1 (sale idempotency)

**Before** (`app/routers/sales.py:553–574`, current state):
```python
# Insert the sale row, commit it, THEN check idempotency
sale = Sale(...)
session.add(sale)
session.commit()  # ← race window begins

# Idempotency check happens AFTER the sale exists
idempotency_key = f"sale_create:{request_id}"
existing = session.execute(
    text("SELECT value FROM app_meta WHERE key = :k"), {"k": idempotency_key}
).first()
if existing:
    session.rollback()
    return RedirectResponse(f"/ventas/{existing.value}")
session.execute(
    text("INSERT INTO app_meta(key, value) VALUES (:k, :v)"),
    {"k": idempotency_key, "v": str(sale.id)},
)
session.commit()  # ← race window ends here; duplicate sale already committed
```

**After** (proposed):
```python
# Single transaction: idempotency check FIRST, INSERT only if new
idempotency_key = f"sale_create:{request_id}"
existing = session.execute(
    text("SELECT value FROM app_meta WHERE key = :k"),
    {"k": idempotency_key},
).first()
if existing:
    return RedirectResponse(f"/ventas/{existing.value}")  # no work done

# Reserve the invoice number inside the same transaction (FOR UPDATE)
invoice_number = allocate_invoice_number(session, sale.tax_mode)  # Phase 1A #3

# Build and insert the sale
sale = Sale(..., invoice_number=invoice_number)
session.add(sale)
# Idempotency record lives in the same transaction
session.execute(
    text("INSERT INTO app_meta(key, value) VALUES (:k, :v)"),
    {"k": idempotency_key, "v": str(sale.id)},
)
# One commit, no window
safe_commit(session)  # Phase 1A #6 — wraps commit() in try/except/rollback
return RedirectResponse(f"/ventas/{sale.id}", status_code=303)
```

**What changed:**
1. Idempotency check moved BEFORE sale INSERT (no race window).
2. Invoice number allocation now uses `FOR UPDATE` (Phase 1A #3) — no duplicate fiscal numbers.
3. Single `safe_commit()` rolls back on any failure.
4. Outcome: a duplicate POST always returns the same `sale.id` and same `invoice_number` — REG-compliant.

---

## How to Use This Plan

1. **Open one ticket per row** above. Each row has file:line, fix sketch, and a test name.
2. **Pick from the top of the week** for the current week. Don't skip ahead — Phase 1A is gating.
3. **Run the full pytest suite before each merge.** The ~2K tests are the safety net.
4. **Update CHANGELOG.md** per the existing discipline check (`.github/workflows/ci.yml` enforces).
5. **One PR per ticket.** Don't bundle Phase 1A #1-#6 — they each have independent test coverage and independent rollback risk.

**Total scope:** 78 findings grouped into 78 tickets across 3 phases over ~23 weeks. Realistic delivery: 6–9 months with 1 senior engineer, or 3–4 months with 2.

**What this plan is NOT:** a commitment to ship all 78. The first 12 (Phase 1A) are non-negotiable. Phases 2 and 3 should be re-scoped after Phase 1 ships and the team learns what compounds fastest in practice.
