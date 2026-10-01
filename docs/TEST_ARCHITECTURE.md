# Saskia RMS — Test Architecture Map

**Last updated:** 2026-10-01 (Phase 14, Tier 5 prep)
**Source:** `tests/` directory, ~430 files, ~4,825 collected tests
**Purpose:** Replace "what tests do we have?" with "what do our tests prove?" — so future gaps are obvious.

---

## §1. Test abstraction (5 levels)

| Level | What it asks | Example |
|---|---|---|
| **L1 Domain** | "Does the BUSINESS RULE hold?" | `pedido_fulfill` decrements stock |
| **L2 Contract** | "Does the SHAPE stay correct?" | POST `/ventas` accepts the documented fields |
| **L3 Failure mode** | "Does it CRASH / HANG / LEAK?" | Request handler doesn't 5xx on empty POST |
| **L4 Lifecycle** | "Does STATE advance correctly?" | DB migrations apply in order, idempotently |
| **L5 Operation** | "Does it RUN in our environment?" | Container starts, /healthz/db returns 200 |

These are **independent** axes. A test can target multiple. E.g. `test_healthz_db_documented.py` is L2 + L5; `test_pedidos_fulfill_atomicity.py` is L1 + L3 + L4.

---

## §2. Coverage matrix — current state

The 430 test files naturally group into 8 domains. Counts are approximate (some span domains).

| Domain | Files | Tests | L1 Domain | L2 Contract | L3 Failure | L4 Lifecycle | L5 Operation |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **A. Money + i18n** | 18 | 180 | ●●● | ●● | ● | ● | ● |
| **B. CRUD roundtrips** | 24 | 320 | ●●● | ●● | ●● | ● | — |
| **C. Auth + session** | 16 | 95 | ●● | ●●● | ●● | ● | ● |
| **D. Sales + pedidos** | 32 | 410 | ●●● | ●●● | ●● | ● | — |
| **E. Reports + analytics** | 21 | 240 | ●● | ●● | ● | ● | ● |
| **F. UI / a11y / CSS** | 38 | 460 | ●● | ●● | ●● | — | ●● |
| **G. DB schema + migrations** | 22 | 175 | — | ●● | ●● | ●●● | ●● |
| **H. Infra (deploy, cron, backup)** | 35 | 220 | ● | ●● | ●●● | ●● | ●●● |
| **Phase 14 Tier 1-4 (new)** | 5 | 268 | ●● | ●●● | ●●● | ● | ● |

**Total**: ~430 files, ~4,825 tests, **~43% line-coverage** on `app/`.

---

## §3. What each domain PROVES

### A. Money + i18n (18 files, 180 tests)

**Proves**: Gs. currency math never loses precision, parses both `.` and `,`, never returns NaN, displays correctly in templates.

**Key tests**:
- `test_money.py` — `to_int_gs`, `parse_money_gs`, decimal arithmetic
- `test_currency_drift_lint.py` — static check: no string-formatted money
- `test_units.py` — kg/g/l/ml conversions

**Coverage gaps**: i18n (Spanish/Guaraní strings — not unit-tested, would need a translation pipeline).

### B. CRUD roundtrips (24 files, 320 tests)

**Proves**: Each entity can be created → read → updated → deleted end-to-end with real DB.

**Key tests**:
- `test_products_crud_roundtrip.py`, `test_clientes_crud_roundtrip.py`, `test_suppliers_crud_roundtrip.py`
- `test_crud_roundtrips_phase14_tier4.py` (Phase 14) — pedido, cliente, sale-multi
- `test_invoice_profile_crud.py`, `test_settings_roundtrip.py`

**Coverage gaps**: Returns/refunds (no entity for `Return`); loyalty redemption (UI test only, no DB roundtrip).

### C. Auth + session (16 files, 95 tests)

**Proves**: Login flow, session lifecycle, CSRF, rate-limit, supabase fallback, role gates.

**Key tests**:
- `test_auth.py`, `test_auth_gate.py`, `test_auth_integration.py`
- `test_csrf.py`, `test_csrf_on_forms.py`, `test_csrf_local_dev.py`
- `test_session_lifecycle.py`, `test_session_lifecycle_middleware.py`
- `test_rate_limit.py`, `test_rate_limit_writes.py`, `test_rate_limit_reads.py` (Phase 14)
- `test_supabase_env_fallback.py`

**Coverage gaps**: 2FA / TOTP (not implemented); password reset flow (UI only); brute-force enumeration of usernames (security).

### D. Sales + pedidos (32 files, 410 tests)

**Proves**: Sale creation, payment, void, multi-item; pedido lifecycle (new → fulfill → void); stock decrement; loyalty; discount guards.

**Key tests**:
- `test_pedidos_fulfill_idempotency.py`, `test_pedidos_fulfill_atomicity.py`
- `test_eod_check_idempotency.py`, `test_eod_completion.py`, `test_void_after_eod.py`
- `test_sales_discount_overflow_guard.py` (Phase 14 — discount > price rejected)
- `test_loyalty_ledger.py`, `test_loyalty_partial_void.py`
- `test_sale_idempotency.py`, `test_pedido_idempotency_request_id.py`

**Coverage gaps**: Receipt printing (no test, hardware-dependent); refund flow (no entity); partial void math (some assertions but no edge cases).

### E. Reports + analytics (21 files, 240 tests)

**Proves**: Dashboard KPIs, daily/weekly/monthly reports, aggregations don't 5xx, performance budgets.

**Key tests**:
- `test_analytics.py`, `test_analytics_properties_phase14_tier4.py` (Phase 14)
- `test_dashboard_*.py` (8 files)
- `test_insights.py`, `test_insights_dashboard_integration.py`, `test_insights_perf.py`
- `test_prime_cost.py`, `test_food_cost.py`, `test_menu_engineering.py`

**Coverage gaps** (THE BIG ONE): `app/rms/analytics.py` is **35% covered** (Phase 14 result). DB-bound code paths (stock_turnover, batch_stock_turnover, retention curves, demand forecast) need Tier 5 DB-seeded hypothesis tests. Also: time-of-day heatmap (no test), per-customer reorder (UI only).

### F. UI / a11y / CSS (38 files, 460 tests)

**Proves**: Pages render, combos work, regressions don't sneak in, WCAG AA compliance.

**Key tests**:
- `test_smoke_all_html_pages.py`, `test_smoke_all_routes.py`
- `test_P01_login_no_sidebar.py` through `test_P31_*` (31 regression tests)
- `test_a11y_forms_and_modals.py`, `test_a11y_navigation.py`
- `test_wcag_aa_compliance.py`, `test_visual_revolution.py`
- `test_ui_components.py`, `test_smoke_review_user_stories.py`

**Coverage gaps**: Mobile UX (`test_mobile_ux.py` is light); Safari-specific CSS (we test Chromium only); keyboard-only flows (a11y partial).

### G. DB schema + migrations (22 files, 175 tests)

**Proves**: Schema applies, migrations don't break, foreign keys hold, partial-apply detected.

**Key tests**:
- `test_migrations_registry.py` — every schema version has a registered migration
- `test_migration_partial_apply_detector.py` — drift caught
- `test_atomic_ddl_block.py` (Phase 14) — per-statement SAVEPOINT
- `test_db_check_constraints.py` — model-level CheckConstraints work
- `test_pg_recent_migrations.py` — Postgres-specific paths
- `test_migration_076/077/078_*.py` — recent migration roundtrips
- `test_lifespan_migrations.py` — migrations run on app startup

**Coverage gaps**: Migration rollback (no rollback path exists, intentional); pre-1.0 migration tests (only recent ones have explicit tests).

### H. Infra (deploy, cron, backup) (35 files, 220 tests)

**Proves**: Container builds, health checks, backup chain works, cron scripts don't break.

**Key tests**:
- `test_backup.py`, `test_backup_cron.py`, `test_backup_pre_mutate.py`
- `test_r2_backup.py`, `test_r2_*.py` (R2 storage)
- `test_readiness.py`, `test_healthz.py`, `test_healthz_db_documented.py`, `test_healthz_errors.py`
- `test_ops_status.py`, `test_status_dashboard.py`
- `test_uptimerobot_setup.py`, `test_uptimerobot_setup_extended.py`
- `test_cf_tunnel_liveness.py`, `test_verify_catalog_on_vps.py` (Phase 14)
- `test_dev_tooling.py`, `test_dockerfile_includes_docs.py`

**Coverage gaps** (THE OTHER BIG ONE): **Deploy script itself has no tests** — every deploy this session required manual branch-coercion. (`scripts/deploy.sh` — A14).

---

## §4. Methodology matrix

| Style | Files | Examples | Strength |
|---|:---:|---|---|
| **Pure unit** | ~80 | `test_money.py`, `test_units.py`, `test_recipe_intel.py` | Fast, exhaustive on math |
| **DB-bound** | ~150 | `test_pedidos_fulfill_atomicity.py`, `test_atomic_ddl_block.py` | Realistic, slow |
| **Property-based** | ~6 | `test_property_invariants.py`, `test_analytics_properties_phase14_tier4.py` | Edge-case discovery |
| **HTTP client** | ~120 | `test_smoke_all_routes.py`, `test_route_smoke_phase14_tier1.py` | Surface coverage |
| **Browser (Playwright)** | ~25 | `tests/browser/*`, `tests/e2e/*` | Realistic UX |
| **Static (lint)** | ~10 | `test_no_hardcoded_dates.py`, `test_no_legacy_warnings.py`, `test_currency_drift_lint.py` | Cheap invariant checks |
| **Migration roundtrip** | ~22 | `test_migration_076_*.py`, etc. | Catches schema drift |

---

## §5. Coverage GAPS (where the work is)

### High-impact gaps (Tier 5 candidates)

| Gap | What's missing | Why it matters | Estimated effort |
|---|---|---|---|
| **G1** `analytics.py` DB-bound code paths | stock_turnover, batch_stock_turnover, retention, demand forecast | We already caught one bug (denormal `int(inf)`); more likely lurking | M (DB-seeded hypothesis) |
| **G2** Deploy script | `scripts/deploy.sh` has no test | This session: 3+ manual recoveries from branch-coercion | S |
| **G3** Rate-limit interaction with auth | What happens when an authenticated user is rate-limited? | Tier 3 of original plan; never built | S |
| **G4** Tier 4 analytics coverage delta | Property tests re-implement math instead of driving analytics.py | We said 80%, got 35% | M (G1 closes this) |
| **G5** Property invariants beyond analytics | `test_property_invariants.py` exists for inventory/recipes — needs more | Catches class-of-bug not single-bug | M |

### Medium-impact gaps

| Gap | What's missing |
|---|---|
| **M1** | Refund / return flow (no entity) |
| **M2** | 2FA / TOTP (not implemented) |
| **M3** | Password reset (UI only) |
| **M4** | i18n strings (no translation pipeline test) |
| **M5** | Mobile UX (light coverage) |
| **M6** | Safari CSS (Chromium-only) |
| **M7** | Migration rollback (intentionally absent — verify stays absent) |
| **M8** | Pre-1.0 migration roundtrips (only recent ones) |

### Low-impact gaps (defer)

- Receipt printing (hardware-dependent)
- Brute-force username enumeration (security review)
- WCAG AAA (we target AA)

---

## §6. The TEST-FIRST way to read this

**Don't ask "what tests do I have?"** — ask:

1. **What's the BUSINESS RULE I want to never break?** (L1 Domain)
2. **What's the SHAPE the system promises?** (L2 Contract)
3. **What FAILURE MODE would hurt most?** (L3 Failure)
4. **What STATE TRANSITION is critical?** (L4 Lifecycle)
5. **Does this RUN?** (L5 Operation)

Each gap in §5 is one of these questions unanswered. The methodology in §4 is the toolbox. The domains in §2-§3 are the surface.

---

## §7. Next actions (recommended order)

| Action | Closes which gap | Cost |
|---|---|---|
| **A14** Test the deploy script (sandbox dry-run mode) | G2 | S |
| **Tier 5** DB-seeded hypothesis tests for analytics.py DB paths | G1, G4 | M |
| **A2** Operator review of deny-pattern false positives | not a test gap, but unblocks me | 0 |
| **A11** Bump coverage floor 30→40 | forces G1 closure | 0 |
| **M5-M6** Mobile + Safari coverage | M5, M6 | M each |
| **M1** Refund entity + tests | M1 | L |

---

## §8. What this document IS NOT

- Not a backlog of work (that's `IMPROVEMENT_BACKLOG.md`).
- Not a changelog (that's `app/CHANGELOG.md`).
- Not a strategy doc (that's `docs/plans/2026-10-01-phase14-coverage-strategy.md`).

This is a **map**: if you're lost, find yourself here. If a gap appears, file a row in §5.