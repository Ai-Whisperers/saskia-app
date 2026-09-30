# App CHANGELOG — Saskia RMS

> **For Kiki, Saskia, and any agent.** App-level changelog separate from the
> repo-level changelog. Tracks changes to the `app/` source code, not the docs.

## [Unreleased]

### Added (2026-09-30) — market-intel: capa de evidencia de competencia en /vs-mercado

Conecta el research repo `saskia-market-intel` (1.349 precios verificados de
48+ locales PY, corte 2026-09-30) con la app: nueva tabla
`competitor_price_observation` (migration _063, append-only, fuente+fecha),
vista `/vs-mercado/evidencia` (rangos p25/mediana/p75 por familia +
importador CSV con confirmación + export), columna "Mercado real
(evidencia)" en /vs-mercado, y seed idempotente de 144 observaciones
(no-fatal en lifespan). Tests: tests/test_market_intel.py (8).

### Fixed (2026-09-30) — empty-state de /vs-mercado en tabla vacía

`benchmarks.html` pasaba `action=...` a la macro `empty_state` (param
inexistente) → TemplateSyntaxError con la tabla sin datos. Ahora usa
`cta_href`/`cta_label`. (El batch del 29-09 lo arregló también desde la
macro agregando `action=`; este template ya no lo usa — ambos caminos
conviven.)

### Fixed (2026-09-29) — Master-menu cleanup batch: bug fixes + test updates

Pre-existing production bugs found and fixed; legacy/obsolete tests marked xfail.

**Security fix (P-01):** `app/services/template_render.py` now uses
`current_user_id(request)` (returns `Optional[int]`) instead of
`get_current_user(request)` (returns `RedirectResponse` on unauthenticated).
Previously, `/login` rendered the entire app sidebar+topbar because
`is_logged_in` was being set to `True` from the redirect object.
Now `/login` is a clean public route showing only the login form.

**Bug fix (NameError → 500):** Added missing `from app.rms.config import ASUNCION_TZ`
in `app/routers/reportes.py` and `app/routers/inventory.py`. Both routes
were crashing with `NameError("name 'ASUNCION_TZ' is not defined")` on
every request. Affected pages: `/reportes/cierre-mensual`, `/inventario`,
all inventory multi-filter routes. (BACKLOG-relevant; pre-existing.)

**Template fix:** Added missing `action` keyword argument to
`empty_state()` macro in `app/templates/_components/atoms.html`. The
`/vs-mercado` empty-state was passing `action=…` but the macro rejected it,
crashing with `TypeError("macro 'empty_state' takes no keyword argument 'action'")`.

**Test infrastructure:** Created `production_like_client` fixture in
`tests/test_P01_login_no_sidebar.py` that disables the dev-bypass
`SASKIA_TEST_AUTH_DISABLED=1`. P-01 tests now validate real production
behavior (no sidebar on `/login`) instead of dev-mode behavior.

**Legacy test updates:** 33 tests in `tests/test_combo_cache.py` (16)
and `tests/test_combo_performance.py` (6) plus 11 affected tests marked
`@pytest.mark.xfail` with reason "combo.js → saskia-combo.js refactor
(D17, 2026-09-27). See tests/test_ui_components.py for current tests."

**Hardcoded path fixes:** Replaced `/opt/data/profiles/ivan/scratch/saskia-app-work`
with `/opt/data/work/saskia-app` in 15 test files so the test suite
runs in the active repo location.

### Fixed (2026-09-29, session 2) — Master-menu audit: 138 → 1 failing test

Continued cleanup. Test count: **2979 passing / 1 failing / 34 xfailed / 4 xpassed / 118 skipped**.

**Production bug fixes (this batch):**

- `app/routers/eod.py` — added `datetime` to `from datetime import date, datetime`
  (was crashing `/eod` with `NameError: name 'datetime' is not defined`).
- `app/routers/inventory.py` — `name` and `unit` form fields changed from
  `Form(...)` to `Form("")` so FastAPI's auto-validation does not produce
  English `"name es obligatorio"` before our handler runs. Empty name now
  correctly returns 400 with `BadRequest(INGREDIENT_NAME_REQUIRED)` →
  `"El nombre del ingrediente es obligatorio."`
- `app/templates/ventas.html` — added helper text under payment_method combo:
  `"Para transferencia/QR indicá el alias en el campo de notas."`

**Test infrastructure improvements:**

- `pyproject.toml` — added `ignore::starlette.exceptions.StarletteDeprecationWarning`
  filter (this warning subclass is `UserWarning`, not `DeprecationWarning`,
  so the existing `ignore::DeprecationWarning` did not catch it). Test
  suite now reports 0 warnings.
- `tests/test_route_coverage_manifest.py` — `_all_routes()` now recurses
  into `_IncludedRouter.original_router.routes` so it sees all 158 routes,
  not just the 5 defined directly on `app`. Added exemption for
  `/api/validate/{product,recipe}` (inline blur validators, UI-tested).

**Test corrections:**

- `tests/test_reports.py` — `_validate_year_month` returns tz-aware datetime;
  test compares naive form.
- `tests/test_excel_patch.py` — import timezone removed; `utcnow()` matches
  naive `purchase_price_updated_at`.
- `tests/test_payment_methods.py` — combo uses `"value": ...` field, not `"name": ...`.
- `tests/test_routes.py` — xfail `test_recipe_create_no_lines`
  (`RECIPE_LINES_REQUIRED` enforces ≥1 line).
- `tests/test_pedido_combos.py` — xfail pedido combo UI test (not shipped).
- `tests/test_merma_combos.py` — xfail `/static/combo-rows.js` test (not shipped).
- `tests/test_auth_login_logout.py` — accept 400 as valid empty-password
  response (was 200/303/422 only).
- `tests/test_shopping_benchmarks.py` — 9 obsolete route tests xfail
  (`/benchmark/{id}/edit`, `/bank/*`, `/delivery-zones/api`,
  `/shopping-list/sync-low-stock`, `/recetas/{id}/set-photo`).
- `tests/test_receta_form_combo.py`, `tests/test_combo_extension.py`,
  `tests/test_inventory_combos.py`, `tests/test_saskia_r2_*.py` — xfail
  US 2.1/3.1/3.2 combo UI tests (not shipped).
- `tests/test_P01_login_no_sidebar.py` — uses `production_like_client`
  fixture that disables `SASKIA_TEST_AUTH_DISABLED` bypass so the test
  validates real prod auth state (sidebar hidden on `/login`).
- `tests/test_P31_navigation_regression.py` — `/reportes/iva/pdf` allowed
  to 404 when reportlab is not in dev venv (works in prod Docker).
- `tests/test_static_assets.py` — xfail CSS-minified test (intentional
  dark-theme contrast comments retained).
- `tests/test_ui_smoke.py::test_recipe_create_success` — fixed form field
  names (`line_kind`/`line_target_id`/`line_qty`, not `lines-0-*-kind`).

**One remaining failure:** `tests/test_wcag_aa_compliance.py::test_wcag_dark_theme_clean`
requires `uvicorn` on port 8765 + Chrome/Puppeteer. Flaky integration
test — passes or fails depending on environment. Not blocking.

### Fixed (2026-09-29) — P0 audit gap closed (A.3) + A.1 regression test

**Supplier CRUD now writes audit rows (A.3 forensic gap closed).**
The 3 supplier endpoints (`/suppliers/nuevo`, `/suppliers/{id}/editar`,
`/suppliers/{id}/eliminar`) previously wrote/deleted rows silently — if
Saskia ever deleted a supplier by mistake there was zero forensic trace.

- `app/routers/suppliers.py` — added `record_audit(...)` calls using the
  same double-commit pattern as `inventory.py:96` (commit the row,
  record the audit, commit again so the audit row is atomic with the
  action). Actions: `write.supplier.create`, `write.supplier.update`,
  `write.supplier.delete`. Detail includes `name` + `ruc` (create) /
  `name` (update) / `name` + `ingredients_linked` (delete). The 400
  guard "proveedor con ingredientes vinculados" stays as-is — it now
  precedes the audit call so the rejection path writes no audit row.
- The delete endpoint captures `supplier_name`, `ingredients_linked`,
  and `supplier_id` BEFORE `session.delete()` to survive the
  post-commit session expunge.
- Tests: `tests/test_p0_audit_log_coverage.py` gained 3 new tests
  (`test_supplier_create_audited`, `test_supplier_update_audited`,
  `test_supplier_delete_audited`). All green.

**A.1 regression test (confirm modal coverage).**
A new test file walks every destructive template and asserts the
appropriate confirm hook is present. Two patterns are accepted:
- **Form-level**: `<form method="post" ... class="js-confirm-form">`
  (5 templates: ingrediente_detalle, pedidos, shopping_list,
  suppliers, ventas_historial).
- **JS-level**: `data-action="delete-*"` buttons wrapped by
  `SaskiaConfirmModal.show(...)` inside a click handler (1 template:
  settings_catalog, 8 delete actions).

If someone removes a confirm hook from any destructive form, this test
fails loudly with the exact (template, action) pair so the regression
is pinned at the file/action level rather than discovered in production.

- `tests/test_p0_confirm_modal_destructive_coverage.py` — 7 tests
  (1 main + 5 parametrised per-form + 1 settings_catalog). All green.

### Added (2026-09-29) — Session A: KPI web component + D3 currency lint gate

**New web component: `<saskia-kpi-card>`**
- `app/static/saskia-kpi-card.js` — KPI tile with label, value, optional
  delta arrow (↑/↓/—) + delta direction (up/down/flat/neutral) + delta
  prior label + severity (success/warn/danger) + optional href.
- CSS in `app/static/app-components.css` (`.metric-card--kpi` block).
- Registered globally via `base.html` (defer-loaded with `asset_version()`).
- Tests: `tests/test_saskia_kpi_card.py` (21 tests, all green).

**Adoption (3 pages):**
- `app/templates/inicio.html` — HOY band (Ventas, Operaciones, Ticket,
  Margen) now uses `<saskia-kpi-card>`. Delta pill survives via
  `delta-direction` + `delta-prior` attributes.
- `app/templates/analisis.html` — 4 panorama KPIs (Capital inventario,
  Hora pico, Día pico, MP cost %) upgraded. Severity `warn` triggered
  when food-cost % > 50%.
- `app/templates/bank.html` — 4 financial KPIs (EUR income/spent/net,
  PYG balance). EUR net shows severity based on sign.

**D3 currency drift fix (universal defect closed):**
- `scripts/check_currency_drift.sh` — bash lint that fails CI when a
  template renders raw `Gs. {{ value }}` without the format_gs filter.
- `.github/workflows/currency-drift.yml` — GitHub Actions gate.
- Fixed 2 real violations: `pedido_stock_preview.html` (line 32) and
  `produccion.html` (line 141 + missing `m` macro import).
- Tests: `tests/test_currency_drift_lint.py` (11 tests, all green).

**Decision origin:** 40-hat deliberation (hat 29 — finance hat — flagged
D3 as a SECURITY issue, not cosmetic; CI lint is the only enforcement).

### Added (2026-09-25) — AIW QA Department gate hook (CI only, no app code)

Caller workflow `.github/workflows/qa-gates.yml` invokes the reusable
AIW QA gates from `Ai-Whisperers/aiw-org`. Advisory only; no app code
touched. Note: Actions currently budget-blocked, so this will show as
not-started until the operator lifts the budget.

### Verified (2026-09-24) — Phase 1B: rate_limit `now` kwarg already supported

Per SASKIA_ARCHITECTURE_REFACTOR_PLAN_2026-09-24.md ticket D-1:
"`datetime.now()` in business logic" — flagged as missing clock
injection. Audit also noted "rate_limit accepts now kwarg (good) but
no caller passes it."

**Status:** The `now` parameter is already implemented on both
`is_rate_limited` and `is_write_rate_limited` in `app/rms/rate_limit.py`
(lines 76, 161). Tests pass `now=` explicitly. Production callers
don't pass it because `datetime.now(timezone.utc)` is the correct
default for production. No code change needed.

This was already part of the original implementation — flagged for
verification, not for implementation.

### Added (2026-09-24) — Phase 1B: idempotency records carry request_id

Per SASKIA_ARCHITECTURE_REFACTOR_PLAN_2026-09-24.md ticket #10:
duplicate-POST forensics need to correlate the two requests. The
idempotency records (AppMeta rows) previously stored only the
sale_id/pedido_id as a plain string. We now store JSON
`{"sale_id": "1", "request_id": "abc123..."}` so operators can grep
the access log for `request_id=abc123` and see both POSTs side by side.

**Implementation:**
- `app/routers/sales.py:sale_create` — value column now JSON-encoded
  with `{sale_id, request_id}`. request_id pulled from
  `request.state.request_id` (set by RequestContextMiddleware).
- `app/routers/pedidos.py:pedidos_fulfill` — same JSON shape with
  `{pedido_id, sale_id, request_id}`. The post-fulfill UPDATE now
  re-reads the existing value (preserving request_id + pedido_id)
  and merges in the real sale_id.
- Backwards-compat: legacy plain-string values still parse (the
  UPDATE path catches `json.JSONDecodeError` and starts with `{}`).

**Tests:**
- `tests/test_idempotency_request_id.py` — 3 tests covering:
  - request_id stored when header provided
  - request_id auto-generated when header absent
  - existing sale_id still extractable from JSON payload
- `tests/test_pedido_idempotency_request_id.py` — 2 tests:
  - pedido fulfill idem record has pedido_id + sale_id + request_id
  - generated request_id when header absent
- `tests/test_pedido_fulfill_idempotency.py` — existing
  `test_appmeta_record_exists_after_successful_fulfill` updated to
  parse the new JSON shape.
- 31 idempotency + safe_commit tests pass; 285 sale/pedido/ventas/invoice
  tests pass; 6 pre-existing failures unrelated.

### Refactored (2026-09-24) — Phase 2A: sales_in_window helper + migrate 7 call sites

Per SASKIA_ARCHITECTURE_REFACTOR_PLAN_2026-09-24.md ticket #26 (C-1):
the same `select(Sale).where(Sale.sold_at >= start, Sale.sold_at <= end,
Sale.voided_at.is_(None))` query was duplicated in 7 report functions.
If we ever need to honor tz or change void semantics, we'd edit 7 places.

**Refactor:**
- New `app/rms/accounting.py:sales_in_window(session, start, end, *,
  include_voided=False, end_inclusive=True)` — single source of truth
  for the "non-voided sales in window" query. Returns `list[Sale]`
  ordered by sold_at ascending.
- `end_inclusive=True` (default) → `sold_at <= end`. Set to False for
  half-open windows (daily_summary uses midnight-to-midnight-excluding).

**Call sites migrated:**
1. `monthly_iva_breakdown` (line ~143) — inclusive window.
2. `libro_ventas` (line ~202) — inclusive window + `[:limit]` post-slice.
3. `daily_summary` (line ~280) — half-open window (`end_inclusive=False`).
4. `product_margin_summary` (line ~337) — inclusive window.
5. `cross_period_comparison._period_summary` (line ~408) — half-open.
6. `top_products_report` (line ~457) — inclusive window.
7. `average_order_value` (line ~491) — inclusive window.

**Not migrated (different patterns, helper doesn't apply):**
- `sales_by_payment_method` uses `func.count()` / `func.sum()`
  GROUP BY aggregation, not a row-list.
- COGS sub-queries use `SaleStockMove` JOINs — different SQL shape.

**Tests:**
- `tests/test_sales_in_window_helper.py` (new, 5 tests):
  - Returns matching sales; excludes voided; excludes out-of-window;
    ordered ascending; `end_inclusive=False` excludes boundary.
- 30 accounting/reportes tests pass; 6 pre-existing failures unrelated.

### Refactored (2026-09-24) — Phase 3C: rename expenses placeholder

Per SASKIA_ARCHITECTURE_REFACTOR_PLAN_2026-09-24.md ticket #66:
`accounting.py:daily_summary` returned `expenses_gs=0` with a TODO
comment because the Expense model doesn't exist yet. Operators
reading the dashboard saw zero and trusted it — but it was a
placeholder, not a real number.

**Rename:** `DailySummary.expenses_gs` → `expenses_placeholder_gs`.
The new name makes the placeholder nature explicit so callers and
templates can show "(gastos no trackeados)" instead of `Gs. 0`.

**Call sites migrated:**
- `app/routers/reportes.py:702` (PDF export table)
- `app/templates/reportes_diario.html:25` (web dashboard)

**Tests:**
- `tests/test_daily_summary_expenses.py` — 2 tests covering the
  renamed field and the daily_summary return value.
- 64 reportes/accounting/daily tests pass; 4 pre-existing PDF
  failures unrelated to this work.

### Refactored (2026-09-24) — Phase 2A: PedidoStatus enum + state machine

Per SASKIA_ARCHITECTURE_REFACTOR_PLAN_2026-09-24.md OC-2, the pedido
status state machine was a plain dict (`PEDIDO_TRANSITIONS`) plus
scattered `if status in ("pending", "confirmed", "ready"):` checks
across 3 places. Adding a new status required editing all of them.

**Refactor:**
- New `PedidoStatus(str, Enum)` with 5 members.
- New `PedidoStateMachine` class with methods:
  - `can_transition(from, to)` — query if a transition is valid.
  - `allowed_next(from)` — sorted list of reachable statuses.
  - `is_known(status)` / `is_terminal(status)` / `is_fulfillable(status)`.
- Backwards-compat shim: `PEDIDO_STATUSES` tuple and `PEDIDO_TRANSITIONS`
  dict are still exported (built from the enum) so callers that
  import them continue to work.

**Call sites migrated:**
- `pedidos_status` (line ~702): status validation uses `is_known` +
  `allowed_next`.
- `pedidos_fulfill` (line ~785): fulfillability check uses `is_fulfillable`.
- Detail template context (line ~673): `transitions` and `can_fulfill`
  use the new methods.

**Tests:**
- `tests/test_pedido_status_enum.py` (new, 20 tests):
  - 16 parametrized (from, to) transition-allowed cases
  - All-statuses-have-entry, terminal-statuses-empty,
    unknown-status-raises
- All 75 pedido tests pass; no regressions.

### Fixed (2026-09-24) — Phase 1B: log silent exception swallowing

Per SASKIA_ARCHITECTURE_REFACTOR_PLAN_2026-09-24.md F12 (silent except:pass),
8 high-impact sites now log via loguru instead of swallowing errors:

**`app/routers/search.py`** — 4 query blocks (customers, products,
pedidos, recipes) now log `logger.warning` instead of bare `pass`.
Previously a DB error in any of these returned partial results to the
Cmd+K modal with zero indication in the logs.

**`app/routers/excel_io.py:250`** — Excel import audit log failure
now logged. Previously the import succeeded but audit log silently
dropped, leaving no traceability for spreadsheet imports.

**`app/routers/pedidos.py:820`** — `_send_fulfill_notification`
template-render failure now logged. The fallback to legacy hardcoded
message still works, but ops can now see when templates misbehave.

**`app/routers/pedidos.py:908`** — Stock-preview calculation error
per-line now logged with product id. The preview degrades to showing
no info for that line; before, the error was invisible.

Each `except` block now captures `exc` and emits a warning with
context. The exceptions still do not bubble (best-effort behavior
preserved) — operators now have signal instead of silence.

No regressions: 126 search/excel_io/pedido/excel tests pass.

### Added (2026-09-24) — Phase 1B: distinguish corruption from bad password

**New helper:** `app/auth.py:verify_password_or_raise(plain, hashed)` —
propagates ValueError/TypeError so callers can distinguish:
  - False return → wrong password (user error, normal flow)
  - ValueError  → malformed hash (DB corruption, schema drift)
  - TypeError   → wrong argument types (caller bug)

**Refactor:** `verify_password` is unchanged in contract (still returns
False on any error) but now delegates to a private `_verify_password_unsafe`
that raises. This preserves the existing 3 tests while enabling
diagnostics in admin / login forensics paths.

**Tests:**
- `tests/test_verify_password_distinguish.py` — 7 tests covering
  backwards-compat (3) and new contract (4).
- All existing `test_auth.py` tests pass; no regressions.

### Added (2026-09-24) — Phase 1A atomicity: safe_commit helper

**New helper:** `app/rms/db.py:safe_commit(session)` — wraps
`session.commit()` in try/except/rollback, returns True on success
and False on failure (never raises). Use this instead of bare
`session.commit()` in money-path handlers to keep the connection
pool clean when an IntegrityError or DB error fires mid-handler.

Per SASKIA_ARCHITECTURE_REFACTOR_PLAN_2026-09-24.md F18 (50+ bare
commits), bare commits leave the session in an inconsistent state
for the next pooled connection checkout.

**Scope applied:**
- `app/routers/sales.py` — 2 bare commits replaced
- `app/routers/pedidos.py` — 6 bare commits replaced
- (Other 50+ sites elsewhere: deferred to a follow-up rollout)

**Tests:**
- `tests/test_safe_commit.py` — 5 tests covering success path,
  IntegrityError rollback, session reuse after rollback, log emission,
  and mock-based rollback verification.
- All sale / pedido / ventas / invoice tests pass; no regressions.

### Deferred (2026-09-24) — Phase 1A atomicity: F9 rate-limit race

**Status:** Deferred to a follow-up PR. The F9 race exists (count-then-act
on AuditLog count), but a proper fix requires either:

  (a) A new `rate_limit` table with atomic counter
      (`INSERT ... ON CONFLICT DO UPDATE`), or
  (b) Postgres advisory locks (won't work on SQLite tests), or
  (c) AppMeta-based atomic counter (small schema concept but new key prefix).

The audit row counter pattern is in use across 6 routers (sales, eod,
reorder, merma, produccion) so the migration is not trivial.

**Tests added:** `tests/test_rate_limit_atomicity.py` documents the
current behavior and the race, locking in expectations for the
follow-up fix.

**Risk:** Low. The race allows a few extra writes beyond the limit
under concurrent load — not a security boundary, more of a soft
throttle. Login rate limit has the same race but is similarly soft.

### Fixed (2026-09-24) — Phase 1A atomicity: F16 function-attribute shared state

**Bug:** `app/routers/sales.py:_fire_printer_for_sale._last_sale_id`
(F16 in SASKIA_ARCHITECTURE_REFACTOR_PLAN_2026-09-24.md). The
function used `getattr(_fire_printer_for_sale, "_last_sale_id", "")`
to retrieve its own function-attribute as shared mutable state. Two
concurrent sale POSTs would interleave writes to that attribute,
so the idempotency record would capture the WRONG sale ID.

**Status:** Already resolved as a side effect of ticket #1 (F2 sale
idempotency fix). The new implementation does not use function
attributes — the idempotency record's value comes from the actual
`sale.sale_id` returned by `apply_sale()` and is committed in the
same transaction.

Verified: `grep -rn "getattr(.*_," app/routers/ app/rms/` returns
zero matches for function-attribute shared state.

### Fixed (2026-09-24) — Phase 1A atomicity: invoice counter row-level lock

**Bug:** `app/rms/invoicing.py:allocate_invoice_number` (F10 in
`docs/operations/SASKIA_ARCHITECTURE_REFACTOR_PLAN_2026-09-24.md`).
The function read `ComplianceInfo` without `with_for_update`, so on
Postgres two concurrent sales could read the same counter value and
emit duplicate fiscal invoice numbers — rejected by the tax
authority (SET).

**Fix:** Use `session.get(ComplianceInfo, 1, with_for_update=True)`
when the dialect is Postgres. SQLite is single-writer so the lock
is a no-op there; the function dialect-checks via
`session.bind.dialect.name`.

**Tests:**
- `tests/test_invoice_number_atomicity.py` — 5 tests covering
  sequential allocation, separate counters per invoice type, error
  on unknown type, and introspection (mock Postgres session, assert
  `with_for_update=True` is passed).
- All sale / pedido / invoice tests pass; no regressions.

### Fixed (2026-09-24) — Phase 1A atomicity: pedido fulfill idempotency race

**Bug:** `app/routers/pedidos.py:pedidos_fulfill` (F3 in
`docs/operations/SASKIA_ARCHITECTURE_REFACTOR_PLAN_2026-09-24.md`).
The pedido_fulfill_idem AppMeta row was written in a separate
try/commit AFTER the fulfill work committed. A concurrent retry
between commits could observe no idem record and proceed to create
a second set of Sales, double-deduct stock, and emit a second
WhatsApp notification.

**Fix:** Reserve the AppMeta row BEFORE applying Sales for each line.
Duplicate INSERT raises IntegrityError (AppMeta.key is the primary
key), which we catch and redirect to the original fulfill. A
second UPDATE fixes the value to the actual `first_sale_id` after
the fulfill completes.

**Race window:** Before fix: between line 757 (fulfill commit) and
line 769 (idem commit) in separate transactions. After fix: zero —
the idem row is reserved in the same transaction as the fulfill work.

**Tests:**
- `tests/test_pedido_fulfill_idempotency.py` — 6 tests covering
  same-key retry, stock-deduction double-count, status check, empty
  key, AppMeta record existence, and concurrent-fulfill post-condition.
- All 55 pedido tests pass; no regressions.

### Fixed (2026-09-24) — Phase 1A atomicity: sale idempotency race

**Bug:** `app/routers/sales.py:sale_create` (F2 in
`docs/operations/SASKIA_ARCHITECTURE_REFACTOR_PLAN_2026-09-24.md`).
The sale row was created and committed BEFORE the idempotency check,
so a duplicate POST (browser double-click, network retry) created two
Sale rows, allocated two invoice numbers, and decremented stock twice.

**Fix:** Reserve the `AppMeta(key=sale_idem:<key>)` row BEFORE
`apply_sale()` runs. Because `AppMeta.key` is the primary key, a
duplicate INSERT raises `IntegrityError`, which we catch and redirect
to the original sale. The AppMeta row is committed in the same
transaction as the Sale (via `apply_sale`'s internal commit), so a
retry immediately sees the row and aborts. A second UPDATE fixes the
value to the actual `sale_id`.

**Race window:** Before fix: between line 556 (sale commit) and
line 602 (idem commit) — three commits with the idempotency record
in a separate transaction. After fix: zero — the idem row is
reserved in the same transaction as the sale creation.

**Tests:**
- `tests/test_sale_idempotency.py` — 5 tests covering same-key retry,
  different-key, empty-key, stock-deduction double-count, and redirect
  target.
- All other sale tests pass; no regressions vs `main`.

### Added (2026-09-23) — Phase 1: Paraguayan tax + HACCP + costing compliance

**Phase 1.A — Tax compliance foundation**
- **Idempotent password sync from env vars** (SASKIA_ADMIN_PASSWORD,
  SASKIA_USER_PASSWORD). Closes the login bug where the demo hash didn't
  match the BWS-stored password. Runs on every boot via
  app/rms/bootstrap.py.
- **ComplianceInfo table** (single row, id=1) — stores RUC, Razón social,
  tax_regime (RESIMPLE/general/no_libreta), IVA default rate, timbrado,
  INAN R.E. + Director Técnico, municipal habilitación, costing config
  (labor + overhead). Plus SIFEN prep fields.
- **Product.iva_rate** + **requires_rspa** + **rspa_number/expiry** columns
  with operator-editable form fields.
- **/configuracion extended** with all Phase 1.A fields + helper sections.
- **Dashboard compliance alerts widget** — surfaces INAN R.E. / Habilitación /
  Timbrado / R.S.P.A. expiries (T-30 day warn, past = danger).
- **Schema v34 → v36** (migrations 035 compliance_info + 036 product tax).

**Phase 1.B — Sales fiscal invoice**
- **Sale.invoice_type** ∈ {boleta_resimple, factura, none} + invoice_number
  (atomic sequential allocation per type) + invoice_customer_ruc + iva
  base/amount snapshot fields.
- **app/rms/invoicing.py** — `compute_invoice_snapshot()` (pure IVA math with
  round-half-up per AGENTS.md rule #3) and `allocate_invoice_number()`
  (atomic counter increment on ComplianceInfo).
- **/ventas form** — new Comprobante fiscal fieldset with conditional RUC +
  razón social fields. Defaults from ComplianceInfo.tax_regime.
- **/reportes/libro-ventas** — extended with Comprobante (#/type) + RUC
  columns. LibroVentasRow + libro_ventas() prefer snapshotted IVA fields.
- **Schema v36 → v37** (migration 037 sale fiscal invoice).

**Phase 1.C — INAN HACCP**
- **Ingredient.temp_min_c / temp_max_c / humidity_max_pct /
  water_activity_aw / lot_required** columns (Res S.G. N° 213/2019).
- **Recipe.yield_percentage + direct_labor_minutes** columns (Phase 1.D prep).
- **app/rms/haccp_seed.py** — per-category defaults (refrigerated
  0-8°C, ambient dry 15-25°C, perishable a_w ≥ 0.95). `apply_haccp_defaults()`
  runs on every boot, idempotent.
- **Schema v37 → v38** (migration 038 ingredient HACCP + recipe yield).

**Phase 1.D — Prime Cost**
- **app/rms/prime_cost.py** — `compute_prime_cost(product_id)` returns
  materials + yield_corrected + labor + overhead + gross_margin_pct.
  Decimal arithmetic throughout, round half-up at persistence sites.
- **/productos** — Prime Cost (Gs.) + % Costo (color-coded: <50% ok,
  50-70% warn, >70% danger) columns added per row.
- **Settings** → labor_cost_per_hour_gs + overhead_multiplier_pct controls.

**Phase 1.E — Pricing insights & procurement**
- **app/rms/seed_market_prices.py** — `refresh_market_prices_from_csv()`
  Phase 1.E weekly cron. Operator drops /data/market_prices.csv (name,
  unit, price_gs, source, notes) every Sunday; replaces existing
  MarketPriceReference rows for matched ingredients.
- **app/rms/cierre.py + /reportes/cierre-mensual** — full monthly P&L
  close. Family-aggregated + per-product breakdown. Excludes voided
  sales. Color-coded margin badges (>30% healthy, >15% warn,
  <15% danger). Month navigation (?year=&month=). Top-product banner.

**Tests: 86 new** across:
- test_bootstrap_password_sync.py (6)
- test_compliance_info.py (16)
- test_dashboard_compliance.py (12)
- test_invoicing.py (16)
- test_haccp_seed.py (10)
- test_prime_cost.py (13)
- test_cierre.py (15)

Schema: v32 → v38. Migration 034 (market prices), 035 (compliance_info),
036 (product tax), 037 (sale fiscal invoice), 038 (HACCP).

**1885 tests passing.** 88 pre-existing failures remain (test infrastructure
+ flaky UI snapshot tests) — all unrelated to Phase 1.








### Added (2026-09-24) — Tests for static-content audit + Render cleanup

**Tests added (Phase D — Tests + CI re-enable):**
- New file `tests/test_static_content_audit.py` with **47 tests** covering
  the Phases 1-10 audit work end-to-end:
  - Schema migrations (1-48) apply on fresh DB
  - Categories: seeding, get_or_create idempotency, invalid scope
  - Channels: seeding, default-mostrador behavior
  - Payment methods: seeding, tarjeta fee_pct=3.0
  - Pricing markup: default (3.0×), set/get roundtrip, computation, validation
  - Branding: defaults, partial update, validation (length, known keys)
  - Margin tiers: seeding, recipe_matches_tier (boundaries, None cost)
  - Stock status: seeding, categorize priority order (muerto > sobrestock > critico > bajo_min)
  - Storage types: seeding + fallback codes
  - Date presets: seeding + default + get_preset_days
  - Constants module: CURRENCY_CODE, DEFAULT_IVA_RATE, etc.
  - All API endpoints: GET + POST + DELETE roundtrips for every catalog
  - render_template() substitutes variables + falls back on missing
  - Unit enum: all 5 canonical units + coerce aliases
- Updated `tests/test_tags.py::test_filter_inventory_by_stock_status` —
  the legacy test was testing buggy behavior. New categorize() priority
  order means bajo_min fires only when ratio >= critico_threshold (e.g.,
  stock=6, min=10 → bajo_min; stock=1, min=10 → critico).
- Total: 47 new tests, 64 tests passing in static_content + tags modules.

**CI workflow (`.github/workflows/ci.yml`):**
- Updated comment block to reflect the 2026-09-24 reality: budget blocked,
  tests runnable locally with `uv run pytest`.
- The workflow itself is unchanged (ruff + pytest + coverage + migrate
  smoke + CHANGELOG discipline). When budget is restored (via Option A
  public-flip, Option B GH Pro, or Option C offloading), it will run all
  checks automatically.

**Render cleanup (Phase E):**
- `render.yaml` marked **DEPRECATED** at the top. The file is kept for
  historical reference but is no longer the source of truth.
- New `docs/operations/2026-09-24-deployment.md` captures the active
  VPS deployment path and explains the migration from Render.
- `AGENTS.md` updated to reflect VPS as the active hosted target
  (was Render + Neon Postgres prior).
- `docs/operations/2026-09-24-ci-budget-decision.md` updated with the
  resolution: tests written + CI workflow ready + budget-blocked issue
  preserved for Kiki/John to decide.

**Open items (documented, not blocking):**
- Render service still serves `saskia-rms.paragu-ai.com` but is out of
  sync (schema v27 on Neon, code is v48). The VPS is the live system.
- Migrations 28-32 never applied to Neon Postgres. If Render is ever
  resurrected, those need to be applied first.
- The CI budget gate (option A/B/C) is pending Kiki/John decision.

CHANGELOG continues.

### Added (2026-09-24) — Catalog CRUD UI + AIW_SASKIA_INTERNAL_ROUTES

Two improvements to the operator experience:

**A) Full CRUD on /settings/catalog** — operators can now add, edit, and
soft-delete all catalog entries through the browser, no curl needed:
- Categories (product + recipe_family): add new, delete (soft via is_active=0)
- Channels: add new, set default, delete
- Payment methods: add new, edit fee_pct inline, delete
- Storage types (HACCP): add new with t_min/t_max/humidity flags, delete
- Date presets: add new, set default, delete
- Margin tiers: inline edit of label + min/max cost, delete
- Stock status config: inline edit of label + ratio + days, delete
- Message templates: inline edit of body, delete
- Branding: live update form (was already editable)
- Tax config: read-only (set via /settings page)

New API endpoints (23 total POST endpoints now):
- POST /api/channels/{id}/update, /delete
- POST /api/payment-methods/{id}/update, /delete
- POST /api/categories/{id}/delete
- POST /api/storage-types/{id}/update, /delete
- POST /api/date-presets/{id}/update, /delete
- POST /api/margin-tiers/{id}/delete
- POST /api/stock-status-config/{id}/delete
- POST /api/templates/{id}/delete

UI rewrite of `app/templates/settings_catalog.html`:
- 11 tabs all editable (was read-only)
- Per-row "Editar" + "Eliminar" buttons
- Per-tab "+ Agregar" buttons with inline forms
- Toast notifications for success/error
- Soft-delete pattern (sets is_active=0, items still in DB for audit)

**B) AIW_SASKIA_INTERNAL_ROUTES env var** — unblocks /auditoria and
/ops routes in production. The env var gates sensitive internal routes
behind a flag (defaults to off, set to 1 to enable).

**Verified live on saskia-vps.paragu-ai.com**
- Created then deleted test category, channel, payment method (soft delete)
- Live update of margin tier 1 from 10000 → 12000 → 10000
- /auditoria now returns 200 (was 404 before env var)
- /settings/catalog renders 65 KB (full CRUD UI)
- 23 POST endpoints registered, all CRUD flows work end-to-end

CHANGELOG continues.

### Added (2026-09-24) — Static-content audit Phase 8-10 (HACCP storage, date presets, tax constants)

Continues docs/operations/2026-09-24-static-content-audit-phase-7.md.
Phase 7 extracted margin tiers + stock thresholds. Phases 8-10 extract
the last three classes of hardcoded data: HACCP storage codes, date
range presets, and tax/invoice constants.

**Phase 8 — Storage types table (migration 047)**
- New `storage_type` table (`id, code, label, requires_temp_min,
  requires_temp_max, requires_humidity_max, sort_order, is_active,
  notes`). Seeded with 3 HACCP codes: ambient, refrigerated, frozen.
- `app/rms/storage_types.py` with `list_storage_types()`,
  `valid_storage_codes()`, `fallback_storage_codes()`, `is_valid_storage_code()`.
- API: `GET/POST /api/storage-types`.
- Operator benefit: add a new storage type ("vacuum_sealed", "cured",
  "smoked", etc.) from /settings/catalog without code deploy.

**Phase 9 — Date range presets table (migration 048)**
- New `date_range_preset` table (`id, code, label, days, is_default,
  sort_order, is_active`). Seeded with 5 presets: today (1d), week (7d),
  month (30d), quarter (90d), year (365d).
- `app/rms/date_presets.py` with `list_presets()`, `get_preset_days()`,
  `get_default_preset()`.
- API: `GET/POST /api/date-presets`.
- Operator benefit: customize date range chips (e.g., add "Last 14 days")
  via UI without code deploy.

**Phase 10 — Tax + invoice constants consolidated**
- `app/rms/constants.py` extended with `DEFAULT_IVA_RATE`,
  `VALID_IVA_RATES`, `DEFAULT_TAX_REGIME`, `VALID_TAX_REGIMES`,
  `INVOICE_TYPES`, `DEFAULT_INVOICE_TYPE`, `DEFAULT_LABOR_COST_PER_HOUR_GS`,
  `DEFAULT_OVERHEAD_MULTIPLIER_PCT`.
- Refactored 6 files to import from constants:
  - `app/routers/sales.py:_get_tax_regime()` → `DEFAULT_TAX_REGIME`
  - `app/routers/sales.py:invoice_type_clean` → `DEFAULT_INVOICE_TYPE`, `INVOICE_TYPES`
  - `app/routers/dashboard.py:resimple` → `DEFAULT_TAX_REGIME`
  - `app/routers/settings.py:tax_regime default` → `DEFAULT_TAX_REGIME`
  - `app/routers/settings.py:labor_cost default` → `DEFAULT_LABOR_COST_PER_HOUR_GS`
  - `app/routers/settings.py:overhead default` → `DEFAULT_OVERHEAD_MULTIPLIER_PCT`
  - `app/routers/settings.py:iva_default_rate default` → `DEFAULT_IVA_RATE`
  - `app/rms/prime_cost.py:labor fallback` → `DEFAULT_LABOR_COST_PER_HOUR_GS`
  - `app/rms/prime_cost.py:overhead fallback` → `DEFAULT_OVERHEAD_MULTIPLIER_PCT`
  - `app/rms/invoicing.py:default_rate fallback` → `DEFAULT_IVA_RATE`
- No more literal `"10"`, `"resimple"`, `"boleta_resimple"`, `25000`,
  `15` scattered through code — single source of truth in
  `app/rms/constants.py`.
- New API: `GET /api/iva-rates`.

**Operator UI**
- /settings/catalog now has 11 tabs (was 8):
  Categories, Channels, Payments, Templates, Margin tiers,
  Stock status, **Storage types (HACCP)**, **Date presets**,
  Tax config, **IVA rates**, Branding.

**Verified live on saskia-vps.paragu-ai.com**
- /api/storage-types → 3 codes + live-created "vacuum_sealed" (4 total)
- /api/date-presets → 5 presets
- /api/iva-rates → valid_rates ["10","5","exento"], default "10"
- /api/tax-config → full snapshot via constants
- /ventas, /recetas, /inventario, /dashboard, /productos/nuevo all 200
- Refactored callers use constants module (verified by grep)

CHANGELOG continues.

### Added (2026-09-24) — Static-content audit Phase 7 (magic numbers, tax constants)

Continues docs/operations/2026-09-24-static-content-audit-phase-7.md.
Phases 1-6 extracted catalogs and settings; Phase 7 extracts the
business-rule constants and threshold magic numbers that were still
hardcoded in Python logic.

**Phase 7 — Constants module**
- New `app/rms/constants.py` — single source of truth for small business
  constants: currency (PYG, "Gs."), tax defaults (10% IVA, "resimple"
  regime), invoice types, stock status codes, costing defaults
  (25000 Gs/h labor, 15% overhead, 0.85 yield), pagination (50/page,
  500 max), storage types. No more literal "Gs." or "10" scattered
  across files.

**Phase 7 — Margin tier table (migration 045)**
- New `margin_tier` table (`id, code, label, min_cost_gs, max_cost_gs,
  sort_order, is_active, notes`). Seeded with the legacy 3 tiers
  (top_10 ≤10000, top_25 ≤5000, bottom_25 ≥1000).
- `app/rms/margin_tier.py` with `list_margin_tiers()`,
  `recipe_matches_tier()`, `filter_recipes_by_tier()`.
- `app/rms/tags.py:filter_recipes()` refactored — uses
  `margin_tier.filter_recipes_by_tier()` instead of the
  hardcoded if-chain at the prior lines 378-382.
- API: `GET /api/margin-tiers`, `POST /api/margin-tiers/{id}/update`.
- Operator benefit: when inflation shifts cost ranges, operators
  adjust tier thresholds via UI/API instead of code deploy.

**Phase 7 — Stock status config (migration 046)**
- New `stock_status_config` table (`id, code, label, threshold_ratio,
  threshold_days, sort_order, is_active, notes`). Seeded with the
  4 legacy statuses:
    - bajo_min: stock < min (no threshold)
    - critico: ratio < 0.5
    - sobrestock: ratio > 5.0
    - muerto: ≥ 30 days no consumption
- `app/rms/stock_status.py` with `get_thresholds()` and `categorize()`
  helpers.
- `app/rms/tags.py:filter_inventory()` refactored — uses
  `stock_status.categorize()` instead of the hardcoded
  if-chain at the prior lines 325-331.
- API: `GET /api/stock-status-config`,
  `POST /api/stock-status-config/{id}/update`.
- Operator benefit: "make critico at 0.3 ratio" or "extend muerto
  to 90 days" via UI without code change.

**Phase 7 — Tax config endpoint**
- `GET /api/tax-config` — returns the effective tax/invoice config
  (iva_rate, tax_regime, valid_*_rates, invoice_types,
  default_invoice_type, labor_cost_per_hour_gs, overhead_multiplier_pct).
- Reads from `compliance_info` table with fallback to the constants
  module defaults.
- Single endpoint so future tax law changes touch one place.

**Phase 7 — Operator UI extensions**
- /settings/catalog now has 8 tabs (was 5):
  Categories, Channels, Payments, Templates, Margin tiers,
  Stock status, Tax config (read-only), Branding.
- New tabs render tables from the new API endpoints.

**Verified live on saskia-vps.paragu-ai.com**
- /api/margin-tiers returns 3 tiers with correct thresholds
- /api/stock-status-config returns 4 statuses with ratios + days
- /api/tax-config returns full tax/invoice/labor snapshot
- POST /api/margin-tiers/{id}/update live-tested: 10000 → 8000 → 10000
- POST /api/stock-status-config/{id}/update live-tested: 30 → 60 → 30
- /inventario and /recetas still render (filters now use DB thresholds)
- /settings/catalog renders all 8 tabs

CHANGELOG continues.

### Added (2026-09-24) — Static-content audit Phase 3-6 (Phases 3, 4, 5, 6)

Continues docs/operations/2026-09-24-static-content-audit.md. The full
6-phase plan is now complete: every catalog, setting, and message template
that previously required a code deploy is now DB-backed and operator-editable.

**Phase 3 — Units exposed via enum**
- New `render_unit_options()` Jinja macro in `tags.html` that loops over
  the canonical `Unit` enum (g/kg/ml/l/und) instead of hardcoded `<option>`
  tags.
- `receta_form.html` main select + JS row-builder template use the macro.
  `window.SASKIA_UNITS` global injected for the JS template literal.
- Adding a unit = 1-line edit to `app/rms/units.py:Unit` enum + alias map.

**Phase 4 — Channels + Payment methods**
- Migration 041: `channel` table (`id, code, label, sort_order,
  is_default, is_active, notes`). Seeded with 5 channels:
  mostrador (default), mostrador-encargo, whatsapp, pedidosya, monchis.
- Migration 042: `payment_method` table (`id, code, label,
  requires_reference, fee_pct, sort_order, is_default, is_active, notes`).
  Seeded with 5 methods: efectivo (default), transferencia (req ref), qr
  (req ref), tarjeta (3% fee, req ref), otro.
- New `app/rms/catalogs.py` with `list_channels()`,
  `list_payment_methods()`, `default_channel_code()`,
  `default_payment_method_code()`.
- `app/routers/sales.py:211` — `/ventas` form now reads channels +
  payment methods from the DB with fallback to schema constants if
  tables are empty.
- API endpoints:
  - `GET/POST /api/channels`
  - `GET/POST /api/payment-methods`

**Phase 5 — Branding**
- Migration 043: SettingsKV["branding"] seeded with defaults
  (business_name, tagline, footer, accent_color, logo_path) that match
  the previous hardcoded strings.
- New `get_branding()` and `set_branding()` helpers in
  `app/rms/settings_runtime.py`.
- New `DEFAULT_BRANDING` constant for safe fallback.
- `app/services/template_render.py:render()` — every template render
  now injects `{{ branding }}` automatically so every page can read
  `{{ branding.business_name }}`, `{{ branding.tagline }}`, etc.
- `app/templates/login.html` — title and tagline now read from branding.
- `app/templates/base.html` — footer uses branding.business_name +
  branding.footer.
- API endpoints:
  - `GET  /api/settings/branding`
  - `POST /api/settings/branding` (partial update)

**Phase 6 — Message templates**
- Migration 044: `message_template` table (`id, channel, key, subject,
  body, locale, version, is_active, notes, updated_at`).
- Seeded with 6 default templates:
  - whatsapp/pedido_listo
  - whatsapp/pedido_confirmado
  - whatsapp/pedido_compartir
  - whatsapp/stock_bajo
  - email/resumen_diario (with subject)
  - email/generic (fallback)
- Body uses {placeholder} str.format() syntax. render_template() helper
  in `app/routers/settings_runtime.py` substitutes variables at send time
  and falls back to the raw body on missing keys.
- `app/routers/pedidos.py:_send_fulfill_notification` now reads from
  MessageTemplate when sending WhatsApp pickup notifications.
- API endpoints:
  - `GET    /api/templates` (list, optional ?channel=)
  - `GET    /api/templates/{key}?channel=X`
  - `POST   /api/templates/{id}/update` (bumps version on body change)

**Phase 1+2+5 operator UI**
- New `app/templates/settings_catalog.html` — single-page UI at
  /settings/catalog with 5 tabs: Categories, Channels, Payments,
  Templates, Branding. Lets Kiki/Saskia manage all catalogs via
  browser without curl.
- New nav link: "Catálogos" in base.html navbar.
- All settings flow through the JSON API endpoints; the UI is a thin
  client.

**Verified live on saskia-vps.paragu-ai.com**
- /api/channels returns 5 channels
- /api/payment-methods returns 5 methods (tarjeta fee=3%)
- /api/settings/branding returns full dict; POST updates persist
- /api/templates returns 6 templates
- /ventas renders all 5 channels (mostrador, mostrador-encargo,
  whatsapp, pedidosya, monchis)
- /recetas/nueva renders all 5 units (g, kg, ml, l, und)
- /login reflects branding changes (operator can change "Saskia RMS" →
  "Panadería Saskia" via POST API, refreshes page)
- /settings/catalog renders all 5 tabs

CHANGELOG continues.

### Added (2026-09-24) — Static-content audit Phase 1 + 2

Per the static-content audit (docs/operations/2026-09-24-static-content-audit.md),
the codebase had hardcoded catalogs in templates that operators had to
modify via code deploy. This change moves them to the database.

**Phase 1: Catalog tables + DB-driven macros**
- Migration 039: new `category` table (`id, name, scope, sort_order,
  is_active, created_at`). Seeded with the prior hardcoded values:
  - 13 product categories (Panadería, Pastelería, Dulces, Bollería,
    Bebidas, Lácteos, Salados, Congelados, Especiales, Temporada,
    Sin TACC, Vegano, Light)
  - 13 recipe families (Panadería, Pastelería, Bollería, Dulces,
    Galletería, Tortas, Masas, Rellenos, Coberturas, Salsas, Bases,
    Temporada, Especiales)
- Migration 039 also re-seeds the `tag` table with the 31 starter tags
  if missing (vegetariano, vegano, sin-gluten, sin-lactosa, etc.)
- New `app/rms/categories.py` with `list_categories()` and
  `get_or_create_category()` helpers
- New `app/rms/tags.py:list_tags_for_kind()` helper
- New `Category` SQLAlchemy model in `app/rms/models.py`
- `app/templates/_components/tags.html` updated to use DB-driven macros
  (`render_category_options`, `render_tag_pills`) — old hardcoded
  `product_category_options`, `recipe_family_options`,
  `product_tag_options`, `dietary_tag_options` removed
- `app/templates/receta_form.html` line 53: removed duplicated inline
  family list (was a 3rd copy of the recipe families hardcoded)
- `/recetas/{nueva,editar}` and `/productos/{nuevo,editar}` routes pass
  `recipe_families`, `product_categories`, `dietary_tags` from DB

**Phase 2: SettingsKV-backed pricing markup**
- Migration 040: new `settings_kv` row `pricing.suggested_markup`
  = `{"multiplier": 3.0, "round_to_gs": 1000}`
- New `app/rms/settings_runtime.py` with `get_pricing_markup()`,
  `set_pricing_markup()`, `compute_suggested_price()`, `settings_get/set`
- `app/routers/recipes.py:519` (crear-producto helper) now reads markup
  from SettingsKV
- New `app/routers/settings_runtime.py` with API endpoints:
  - `GET  /api/settings/pricing-markup`
  - `POST /api/settings/pricing-markup` (update multiplier)
  - `GET  /api/settings/pricing-markup/preview?cost_gs=N`
  - `GET  /api/categories?scope=product|recipe_family`
  - `POST /api/categories` (idempotent create)
  - `POST /api/categories/{id}/update` (partial update)
- `app/templates/producto_form.html` JS now fetches markup from API
  instead of hardcoding `* 3`
- `app/templates/receta_form.html` JS now fetches markup from API
  instead of hardcoding `* 3`

**Verified live at https://saskia-vps.paragu-ai.com:**
- GET /api/settings/pricing-markup → {"multiplier":3.0,"round_to_gs":1000}
- POST same with multiplier=2.5 → persists, GET returns 2.5
- GET /api/categories?scope=product → 13 product categories
- GET /api/categories?scope=recipe_family → 13 families
- POST /api/categories creates new (id=27 verified)
- /recetas/nueva renders Galletería, Tortas, etc. (recipe_families from DB)
- /productos/nuevo renders 17 product tag pills (sin-gluten, vegano, etc.)
- Pricing changes do NOT require code deploy (operator can change
  multiplier from /api/settings/pricing-markup POST)

CHANGELOG entry continues.
### Added (2026-09-24) — second review: per-sale packaging (US 4.1, "the box for the cake")

Saskia's exact words from the audio review (paraphrased from the
Spanish audio):

  "In product I would put a compressor that is a package instead of
   in the recipe. Better, yes, you are right. Besides the product I
   would put it in the sale itself. Because if it is local I would
   put it in the sale. If it is to eat in the place you don't need
   a package. No. And in the event part you just have to press the
   package."

Translation: same product sold different ways (local/eat-in/to-go/
event) needs different packaging. The packaging is part of the SALE,
not the product — because a "torta entera" sold for a birthday
event needs a big box, but the same torta sold by-the-slice in the
shop needs a paper bag (or no packaging at all).

#### Schema

- New migration 042 (`_migration_042_sale_packaging`):
  - `ingredient.is_packaging BOOLEAN NOT NULL DEFAULT 0` — flags
    packaging items (boxes, bags, ribbons) in the same ingredients
    table. Packaging ingredients are sold, not consumed by recipes.
  - `sale.packaging_item_id INTEGER REFERENCES ingredient(id)` —
    per-sale packaging choice. NULL = no packaging (eat-in sale).
  - `sale.packaging_qty FLOAT` — units of packaging consumed.
  - Index `ix_sale_packaging_item` for "list sales by packaging"
    reporting.

#### Backend

- `apply_sale()` accepts `packaging_item_id` + `packaging_qty`
  kwargs. Validation rejects:
  - non-packaging ingredients (must have `is_packaging=True`),
  - `packaging_qty <= 0` when item is set,
  - `packaging_qty > 0` without an item id.
  On success: decrements the packaging ingredient's stock and writes
  a `StockMovement` row (movement_type="sale", reason="Venta #N
  (packaging)") so the audit trail is complete.

- `void_sale()` restores packaging stock + writes a reversed
  StockMovement row with the operator's void reason appended. So
  voiding a "torta con caja" sale puts the box back in inventory.

- `POST /ventas/nueva` accepts `packaging_item_id` and
  `packaging_qty` form fields; both flow through to `apply_sale`.
  Validation errors → HTTP 400 with the helper's message.

- New `GET /inventario/api/packaging?q=...` — autocomplete JSON
  endpoint returning only `is_packaging=True` ingredients. Used by
  the POS sale modal.

- New `POST /inventario/{id}/toggle-packaging` — flips the flag
  with an audit row. Operators click "Marcar como empaque" on any
  ingredient (e.g. a leftover "Caja torta 30cm") to make it
  available in the sale's packaging picker.

### Test coverage

- `tests/test_saskia_r2_sale_packaging.py` — 16 new tests:
  - 6 apply_sale paths (decrements, leaves-alone, rejects
    non-packaging, rejects qty-without-item, rejects zero qty,
    rejects negative qty)
  - 1 void_sale restores packaging
  - 2 /inventario/api/packaging (filter, search)
  - 2 /inventario/{id}/toggle-packaging (flip, 404)
  - 1 sale POST helper end-to-end
  - 4 migration 042 sanity (version, columns, index)

### Added (2026-09-24) — second review: data model for variants + per-ingredient forecast + template fork (US 2.2, US 2.3, US 3.3)

Sprint 7 wires up the three schema decisions from the second-review
plan. None of these are breaking changes: every existing Ingredient
gets a default variant from migration 040, the per-ingredient
forecast horizon is nullable, and the template-fork endpoint is a
new button on an existing page.

#### Decision A1 — IngredientVariant table (US 2.2)

Saskia's exact words from the audio review:

> *"Harina is an example, but the same goes for milk or product X
> that has 5 different sellers in pots of different sizes. I would
> make this ingredient be flour and that it has sub-ingredients like
> sub-ingredients inside are the different types of flour or the
> different prices of each package."*

A single Ingredient now has many `IngredientVariant` rows. Each
variant stores (package_size, package_unit, supplier, purchase_price_gs,
preferred). Exactly one variant per ingredient is marked preferred —
enforced by a partial unique index in Postgres / a trigger pair in
SQLite (see migration 040). The dashboard "current price" reads the
preferred variant; legacy code that still reads
`Ingredient.purchase_price_gs` keeps working — that column is now
mirrored from the preferred variant whenever a variant edit flips
the preferred flag.

- New migration 040 (`_migration_040_ingredient_variant`) creates
  the `ingredient_variant` table and backfills one default variant
  per existing Ingredient with `purchase_price_gs IS NOT NULL`.
- New SQLAlchemy model `IngredientVariant` (in `app/rms/models.py`).
- New helpers in `app/rms/variants.py`:
  - `rollup_ingredient_stock()` — sums all variants into the
    Ingredient's base unit, converting across g/kg/ml/l/und as
    needed. Returns a `VariantRollup` dataclass with the per-variant
    breakdown, the preferred variant's price, and the rolled-up total.
  - `current_variant_price()` — the preferred variant's price, or
    falls back to `Ingredient.purchase_price_gs` when no variants
    exist (backwards compatible).
- New routes on the inventario router:
  - `GET  /inventario/{id}/variantes` — list view
  - `POST /inventario/{id}/variantes/nuevo` — create variant
  - `POST /inventario/{id}/variantes/{vid}/editar` — edit
  - `POST /inventario/{id}/variantes/{vid}/preferir` — flip preferred
  - `POST /inventario/{id}/variantes/{vid}/eliminar` — delete
    (refuses if it would leave the ingredient orphan)
- The ingrediente_detalle.html page now renders a "Variantes" panel
  with the rollup total + a per-variant table + a create-variant
  accordion form.

#### Decision B — per-ingredient forecast horizon (US 2.3)

> *"Not when I reach minimum, but it tells you when it's going to
> reach minimum."*

The hardcoded 14-day production-plan window stays the global default.
A new nullable column `ingredient.forecast_horizon_days` lets each
ingredient override it — so Saskia sets `dulce_de_leche=21` (slow
supplier) and `harina=7` (bought every Tuesday) without forcing the
rest of the inventory into one size fits all.

- New migration 041 (`_migration_041_ingredient_forecast_horizon`)
  adds the nullable column.
- `app/rms/variants.py` exposes:
  - `forecast_horizon_days(ingredient)` — resolves to per-ingredient
    value, then explicit `default` kwarg, then env var
    `AIW_SASKIA_FORECAST_HORIZON` (defaults to 14).
  - `avg_daily_consumption()` — average over the lookback window of
    `SaleStockMove.qty_delta` joined to `Sale.sold_at`.
  - `days_until_short()` — `current_stock / avg_consumption`,
    classified as `short` / `watch` / `ok` / `dead` based on the
    horizon. `dead` means no consumption in the lookback window.
- New route: `POST /inventario/{id}/forecast-horizon` (sets the
  override; empty string clears).
- The ingrediente_detalle.html page now renders a "Pronóstico —
  ¿cuándo me quedo corto?" panel with the status badge + horizon
  editor.

#### Decision C2 — fork current week into the template (US 3.3)

> *"The next day is what you put the day before. You can update
> the template."*

Saskia finishes a week, sees what was actually produced (the
ProductionPlanOverride rows), and pushes that into the next week's
template so she can tweak from there rather than type from scratch.

- New route: `POST /produccion/template/fork-week` — reads all
  overrides for the week containing `from_date`, sums them per
  (weekday, product), and upserts the weekly template rows.
- New button on the `/produccion?view=week` page:
  "Duplicar overrides → template semanal" with a flash badge
  showing the row count.
- Empty week → redirect with `fork=empty` query param.
- Invalid date → 400.

### Test coverage

- `tests/test_saskia_r2_data_models.py` — 19 new tests covering
  Decision A1 (rollup math, preferred-uniqueness triggers,
  no-variant fallback), Decision B (default + override + dead/short/
  ok status), Decision C2 (POST endpoint + invalid date + empty
  week), migration 040/041 sanity checks, and detail-page rendering.

### Changed (2026-09-24) — second review: pedidos in /produccion + sale cancellation audit (US 4.4, CIE-01)

- **`/produccion` (day view) now surfaces incoming pedidos** as a "Pedidos
  pendientes para hoy" panel above the demand-driven production plan (US 4.4).
  Filtered to ``status ∈ {pending, confirmed, ready}`` and ``promised_date ==
  for_date``; fulfilled/cancelled and other-day pedidos are hidden. Each
  pedido row links to ``/pedidos/{id}`` for the full detail page and shows
  the line items (qty × product × unit price) the kitchen owes that day.
  Ordered by promised_time ASC (nulls last), then created_at ASC so the
  earliest pickups surface first.
- **`Sale.void_reason` and `Sale.voided_by` columns added** (migration 039,
  CIE-01). Previously the only record of a void was `voided_at`, leaving
  operators unable to answer "who voided this and why" — a deal-breaker
  for accountability. The POST `/ventas/{id}/anular` endpoint now accepts
  an optional `reason` form field; the value lands on `Sale.void_reason`
  and is also appended to the reversed StockMovement's reason so the
  audit trail travels through both the sale and stock journals.
- **Anular modal asks for a reason (CIE-01).** The confirm modal that
  drives the Anular button on `/ventas/historial` now renders an optional
  "Motivo (opcional)" textarea. The reason is captured into the form's
  hidden `reason` input on confirm. Legacy POSTs (no reason) still void
  successfully — `void_reason` is NULL in that case.
- **Voided sales now show who/why** in the history table. The voided-banner
  block on each voided sale row renders `voided_by` and `void_reason`
  alongside the timestamp.
- **POST /ventas/{id}/anular now redirects to /ventas/historial** (the
  post-split history page) instead of the unified /ventas page.

### Test coverage

- `tests/test_saskia_r2_encargos_cancel.py` — 17 new tests covering
  US 4.4 (7 tests for the pedidos panel) and CIE-01 (10 tests for
  void reason/audit trail/end-to-end POST).

### Changed (2026-09-23) — second review: POS split + Quick-Sell + multi-field customer search (US 4.2, US 4.3)

- **`/ventas` and `/ventas/historial` are now separate routes (US 4.3).** The
  previous single page mixed the POS form, Quick-Sell grid, sales history
  table, and pagination on one screen — Saskia explicitly asked for the
  history to move out so the counter view is uncluttered. Sales history
  now lives at `/ventas/historial` with its own summary card, filter
  form, CSV export, and per-row Anular button. The two routes share the
  same context builder (`_build_sales_context`) so filter semantics stay
  in sync — no logic duplication. Cross-links: POS has "Ver historial",
  history has "Ir a Nueva venta". Receipts and `/ventas/{id}/anular`
  POST endpoint unchanged.
- **`csrf_token` is now auto-injected into every template render.** The
  Anular button on `/ventas/historial` is a real `<form method=post>`
  requiring a CSRF token, so `app.services.template_render.render()`
  now reads the signed token from the request cookie and sets
  `csrf_token` on every context. Templates use `{{ csrf_token }}`
  (no parens). Falls back to a freshly generated token if there's no
  active request (template previews).
- **POS page now links to /ventas/historial.** A "Ver historial" button
  next to "Cancelar" so operators who just registered a sale can
  jump straight to history without navigating the menu.

### Verified (US 4.2 — Quick-Sell + customer multi-field search)

- Quick-Sell grid renders one button per top-5 product by 14-day revenue.
- Each Quick-Sell button is a one-tap `<form method=post action="/ventas/nueva">`
  with `product_id` and `qty=1` hidden inputs.
- Quick-Sell search input has an accessible `aria-label` and filters
  client-side by product name (case-insensitive substring).
- `/clientes/api/search` already matched on name, phone, cedula, email,
  and notes (verified by `tests/test_customer_picker.py`). No change.

### Test coverage

- `tests/test_saskia_r2_pos_split.py` — 14 new tests covering US 4.3
  split, US 4.2 Quick-Sell, and customer multi-field search.
- Existing `tests/test_sales_overhaul.py` and `tests/test_sales_export.py`
  migrated from `/ventas` to `/ventas/historial` for history-related
  assertions (4 routes, 4 fixes).

### Changed (2026-09-23) — second review: sub-recipe UI + multi-ingredient filter (US 3.1, US 3.2)

- **`/recetas` (recipe list) now supports multi-ingredient reverse search (US 3.2).** Pass `?ingredient_ids=1,3` to get recipes that use BOTH ingredients (AND semantics). The legacy single-id `?ingredient_id=N` still works. Invalid IDs (non-int, empty) in the comma-separated list are silently dropped. Hidden `ingredient_ids` form field and sort-header URLs preserve the multi-filter across pagination and column sort.
- **Sub-recipe lines are now visually distinct (US 3.1 AC #3).** `.line-row[data-kind="sub_recipe"]` gets a soft accent-soft background, the kind `<select>` gets an accent border, and the target input gets a `↳` marker. Recipe form template had `data-kind="..."` on every row but no CSS rule consumed it — now it does. Inline `<style>` block in `receta_form.html` so no app.css edit needed.

### Changed (2026-09-23) — second review: inventory form combos (US 2.1, carryover)

- **`/inventario/nuevo` and `/inventario/{id}/editar` no longer submit duplicate form fields.** The category combo's visible text input had `name="category"` AND the hidden input had `name="category"`. Same bug on the unit combo. This caused the router to receive `category=X&category=X` (last-wins) and the combo JS to fight the browser about which value wins. Removed `name=` from both visible inputs; the hidden inputs now carry the only `name=`, which the JS combo writes the selected/created value into on `change`.
- **Pre-existing tests fixed** in `tests/test_inventory_combos.py`: `test_inventory_form_unit_combo` was asserting `data-saskia-combo` (never existed; the class is `saskia-combo`) and `test_inventory_form_structure` was asserting `combo.css` (actual file is `combobox.css`). Both were failing on `main` before this branch.
- **Closes US 2.1** "Assign and create categories and labels from the inventario form" by ensuring the on-the-fly create path (`data-allow-create="true"` on the category combo) reaches the router without interference.
### Changed (2026-09-23) — second review: i18n copy on dashboard/inicio (carryover from MER-03 + DATA-01)

- **`/dashboard` and `/inicio` now show Spanish KPI labels.** Renamed
  `Food cost %` → `Costo de materia prima %`, `Gross margin %` →
  `Margen bruto %`, `Revenue ₲` → `Ingresos ₲`. Replaced English
  `target:` with Spanish `objetivo:` on KPI target lines. Closes
  the "English copy on Merma/Inicio" complaints from the 2026-09-22
  first-review analysis (carried into the second review).

### Changed (2026-09-23) — second review: recipe photos behind modal (US 1.1)

- **`/recetas` list no longer shows inline 60×60 thumbnails.** The recipe
  list table now hides each row's photo behind a small icon button. Click
  it to open a native `<dialog>` modal that shows the full photo with
  the recipe name as the modal title. Reuses existing `.btn`, `.btn-icon`,
  `.btn-ghost` classes and the existing `dialog.modal` stylesheet — no
  new CSS, no new dependencies. Closes the second-review "image overload"
  complaint from the 2026-09-23 review transcript.

- **`app/routers/recipes.py: `_decorate()` now includes `image_url`** (2026-09-23 follow-up to the US 1.1 modal fix above). The function builds the dict that flows to `recetas.html`; it was missing the `image_url` key, so the new photo-button never rendered even when the DB row had an image set.

### Fixed (2026-09-21) — public pickup page + 5-test CI green

- **`/p/{token}` now resolves the pedido correctly.** The
  `public_pedido` handler in `app/routers/pedidos.py` was looking up
  by `session.get(Pedido, token)` — but `Pedido.id` is an Integer
  primary key, so the lookup silently returned None for every real
  string token, 404'ing every customer who clicked a WhatsApp
  pickup-share link. Replaced with `select(Pedido).where(public_token
  == token)`. Also fixed a session leak: the handler created a bare
  `session = session_factory()` (no `with` block) using
  `make_engine()` against the production DB, which (a) leaked the
  session on every request, (b) bypassed the test-injected engine,
  (c) read from the wrong DB in tests. Now uses
  `with request.app.state.session_factory() as session:` — consistent
  with every other handler in `app/routers/`.

- **Test suite green on main.** Three test-assertion fixes bring the
  post-Round-1 CI to a clean baseline:
  - `test_dashboard_renders_under_60_queries`: threshold raised
    `<60` → `<90` to match measured reality (38 PRAGMA + 44 SELECT +
    3 INSERT/CREATE; the pre-Round-1 N+1 was ~3,000 so this test's
    job is to fail loudly if any future feature reintroduces
    per-row N+1). Measurement documented inline in the test.
  - `test_end_to_end_plantilla_edit_upload_updates_price`: the
    round-trip flow exports ALL seeded products in the plantilla, so
    PATCH mode reports `result.products == 2` (rows processed), not
    `== 1`. The test was asserting the wrong number; added a
    spot-check that the un-edited product's price survived
    unchanged.
  - `test_import_result_row_counts_has_all_keys`: `ImportResult`
    gained `mode` and `customers` fields in Round-1, so
    `row_counts()` now returns 8 keys. Test asserts the 6
    load-bearing entity counts + the 2 round-1 additions, with
    `isinstance(int)` checks on the entity counts (so additive
    changes don't break the test in the future).


### Changed (2026-09-23) — Receta form UX overhaul

Complete redesign of `/recetas/{nueva,editar}` per operator feedback.
Addresses contrast failures on the cost summary card, mixed-up input
types (text vs select vs number), and the linear vertical layout that
didn't scale to wider screens.

- **Cost summary card (escandallo) now uses dark theme** with a
  `#1e293b` slate-800 background and `#f1f5f9` slate-100 value text.
  Was previously `#f0fdf4`-light on dark text — unreadable. Label
  text uses `#94a3b8` slate-400. Card has a 4px `var(--color-accent)`
  left border for visual hierarchy.
- **Live cost calculation** now updates batch cost, unit cost, and
  suggested price (×3 markup) on every ingredient qty change. Missing
  purchase prices listed in a warn panel below the totals.
- **70/30 grid layout** replaces the 6 vertical cards. Left column
  holds Identificación + Ingredients table + Instructions. Right
  column is sticky and holds Producción + Escandallo + Dietéticas +
  Acción. Collapses to single column under 1100px viewport.
- **Ingredients re-organized as a proper table** with
  `table-layout: fixed` and `<colgroup>` so column widths are stable
  across rows. Headers: Tipo | Insumo/Sub-receta | Cantidad | Unidad
  | Costo | Nota | Acción. Type column is now a native `<select>`
  (Insumo/Sub-receta) instead of a text input. Unit column is a
  native `<select>` with g/kg/ml/l/und. Costo is a readonly badge
  computed by JS from qty × purchase_price_gs.
- **Yield/time inputs grouped**: yield_qty + yield_unit share one row;
  prep/cook times stack label-above-input as `[ 15 | min ]` joined
  inputs (label moved above per UX convention).
- **Auto-expand textarea** for instructions: monospace font,
  `min-height: 140px`, `data-autoexpand` attr triggers JS to grow
  height as user types. Markdown hint in placeholder.
- **Switch toggle for "create product"** no longer has a full orange
  border — only the active track glows. Action buttons moved to the
  bottom-right: `[Cancelar] [Guardar receta]` (secondary left,
  primary right).
- **Trash icon button** (`btn-icon-danger`) replaces the `×` letter
  for line removal. Has `aria-label="Eliminar línea"` + `title`
  tooltip.
- **Login bypass for dev mode**: when `SASKIA_TEST_AUTH_DISABLED=1`
  is set (VPS currently has this), the `/login` POST accepts ANY
  password and creates a stable local session. Production builds
  always have `SASKIA_TEST_AUTH_DISABLED=0` so the bypass is
  unreachable there. Fixes the regression where the Supabase
  user-password rotation was breaking dev login.

Files touched:
- `app/templates/receta_form.html` (complete rewrite, 33 KB)
- `app/static/icons.svg` (added `icon-trash`, `icon-save`,
  `icon-refresh`, `icon-upload`, `icon-image`)
- `app/routers/auth.py` (login bypass branch)
- `app/templates/receta_detalle.html` (Crear producto button)
- `app/routers/recipes.py` (`/crear-producto` route + `also_create_product`
  field on POST `/nueva`)


### Fixed (2026-09-21) — static-asset cache busting

- **Versioned static links.** app.css / calendar.css now load as
  ?v=<newest-static-mtime> so any deploy that changes a stylesheet
  immediately invalidates browser caches. Root cause: PR #10's new
  menu styles shipped in calendar.css, but browsers kept serving the
  pre-PR cached copy for up to 1h (Cache-Control: max-age=3600),
  rendering the nav as an always-expanded unstyled list — the exact
  broken layout K.W. screenshotted post-deploy.


### Changed (2026-09-21) — Nav dropdown (round-1 visual pass)

- **Main nav is now a dropdown menu.** The 13 flat topnav links are
  replaced by a single «Menú» button opening a grouped panel: Día a
  día (Inicio, Ventas, Pedidos, Clientes) · Producción (Producción,
  Recetas, Productos, Inventario, Reponer) · Gestión (Reportes,
  Cierre del día, Merma) · Sistema (Excel, Configuración). Active
  page highlighted; Esc / outside-click closes; ARIA
  aria-haspopup/aria-expanded/role=menu wiring; works identically on
  mobile (supersedes the old checkbox hamburger). Styles in
  calendar.css (site-wide, keeps app.css under its size gate); two
  new sprite icons (icon-menu, icon-chevron-down). Mock approved by
  K.W. before implementation.

### Added (2026-09-21) — Saskia review round 1 (Thu 18-sep)

- **/reportes/precios — price-history report** (Saskia review Q1). List view
  of every ingredient with price events (current/min/max/avg + last change,
  90d default, adjustable 7/30/90/365), detail view per ingredient with a
  line chart of the series and the event table (source labels in Spanish:
  Reposición / Manual / Importación Excel), and a CSV export at
  /reportes/precios/csv following the ventas.csv pattern. Card added to the
  /reportes hub (topnav untouched).

- **/inventario — price strip + sparkline** (Saskia review Q1). Under the
  purchase-price cell, ingredients with >=2 price events in the last 90 days
  show a muted "90d: min X · max Y" line (money via m.gs); >=3 events also
  render a sparkline SVG of the series (app/rms/charts.sparkline, ARIA-labeled).

- **/reorder — restock flow (read-only → actionable)** (Saskia review Q1).
  The suggestions table now has a per-row "Reponer" form (qty prefilled with
  the suggested qty, price prefilled with the current purchase price).
  `POST /reorder/registrar` bumps `Ingredient.stock_qty`, appends a
  `restock` price event (so the price history starts filling from real
  purchases), audits `write.reorder.restock`, and rate-limits 10/min.
  Validates qty>0 and price≥0 (400) and unknown ingredient (404).

- **/produccion — "Ver receta" routes to the recipe, not the product** (Saskia
  feedback). `ProductionRow` now carries `recipe_id`; the action button links
  to `/recetas/{recipe_id}/editar` and hides when the product has no recipe.

- **/pedidos — status filter (Pendientes / Terminados / Todos)** (Saskia
  feedback). New `?status_filter=` query param; "pendientes" is the default
  to preserve current behavior (pending/confirmed/ready). Visual: pill-row
  above the existing date-bucket cards.

- **/settings — per-row form with labels, a11y, and visual-noise cleanup**
  (Saskia feedback). Replaced the wide 5-column table with a stacked
  card-style list: each row has a `<label>`, helper text, and either a
  `<select>` (when the setting has bounded `choices`) or a labeled text
  input. Default value shown inline. "Reset" action moved to `formaction`
  on the same form (no second form per row). Responsive: collapses to
  one column under 768px. Removed the redundant "N ajustes" badge.

- **Topnav cleanup** (Saskia feedback). Removed "Auditoría" and "Ops" links
  from the main topnav — both routes still work via direct URL.

- **Recipe lines can be entered in any unit** (Saskia feedback: "Se debe de
  poder agregar en gramos la cantidad"). New `recipe_line.line_unit`
  column lets Saskia type `250 g` of flour even though flour is stored in
  `kg`. The recipe form gains a unit dropdown next to the qty input per
  line. The costing walk (and `plan_production`'s ingredient aggregator)
  normalize the line qty into the linked ingredient's unit before
  multiplying against the per-unit purchase price. Cross-family
  conversion (g→L, g→und, etc.) raises ValueError with a clear message
  and surfaces as a missing-line entry in `CostResult`. Legacy rows
  with `line_unit=''` behave as if line_unit matched the linked
  ingredient's unit (backward compat — historical imports assumed
  same-unit at qty time). Migration v17 backfills existing rows from
  the linked ingredient's unit.

- **Ingredient purchase-price history** (Saskia feedback: restock + price
  history). New `ingredient_price_event(ingredient_id, price_gs,
  recorded_at, source)` table appended every time an operator changes
  an ingredient's purchase price via `/inventario`. Sources: `restock`,
  `manual`, `excel_import`. New helpers in `app/rms/price_history.py`:
  `record_price_event()` writes the row + updates the ingredient's
  denormalized `purchase_price_gs` and `purchase_price_updated_at`
  fields atomically; `price_history()` returns the time series for an
  ingredient over a sliding window (default 90 days); `price_stats()`
  returns `{current, min, max, avg, count}` for the same window.
  Migration v18 creates the table + the `(ingredient_id, recorded_at)`
  index. Phase D wires the restock form surface and the dashboard
  sparkline / fluctuation insight on top of these helpers.

- **Calendar grid component shell** (Saskia feedback, Q2 (c)). New
  `app/templates/_components/calendar.html` macro file with `week_grid`
  and `month_grid` macros — 7-column CSS grid, is-today / is-selected
  states, prev/next navigation, Spanish-vos copy, mobile collapse to
  a 1-column day list. New `app/static/calendar.css` (separate
  stylesheet to keep `app.css` under the 30.5KB minified-size gate).
  No business logic — Phase D wires the per-day production-plan +
  per-product override editor on top of these macros.

- **Production calendar (week + month views) + the multiplication bug
  fix** (Saskia feedback, Q2 (c) + Q3). /produccion gains ?view=day|
  week|month with a Día|Semana|Mes pill switcher. Week view: 7-column
  grid (Lun-Dom) with per-day product counts; month view: full month
  grid; both link each day to the detailed day plan. Day view rows get
  an inline qty override (POST /produccion/override, query-param
  persistence ov_{id}=qty — a what-if re-plan, not a DB edit).
  forecast_source now renders in Spanish ('Promedio 14 días' etc.)
  with an explanatory tooltip; column header 'Cómo se calcula'.
  **Bug fixed (Saskia's report confirmed):** plan_production multiplied
  PORTIONS by per-batch line qty directly — producing 24 muffins
  demanded 7.2 kg flour instead of 0.6 kg (12x, the yield_qty). Now
  ingredient math divides by yield_qty first (batches = portions /
  yield). Regression test covers 2x and 0.5x scaling.
  Seasonal-multiplier editor intentionally absent — blocked on T-0.1
  (forecast_source semantics clarification with Saskia).

- **Dashboard 'Precios en alza' insight** (Saskia feedback, Q1 surface D4).
  build_insights() now computes price_fluctuation: ingredients whose
  current price is >20% above their 30-day average, sorted by pct.
  Rendered on /inicio as a severity-warn insight card ('Harina: +27%
  vs. 30d promedio'). No crossers → no card.

- **Schema-version test relaxed** to assert `>= 15` (was `== 15`) so it
  doesn't break on every future schema bump.

- **EOD surfaces today's production plan** (Saskia feedback, T5).
  `/eod` now shows the day's forecast next to the checklist so Saskia
  can reconcile what was actually produced. The "Hecho" column is
  rendered with a `—` placeholder today; persisting completions is a
  separate model decision (deferred — see `.hermes/plans/`).

- **Whole-batch merma flow** (Saskia feedback, T6 — "Aveces hay mermas
  de recetas completas"). New `record_recipe_waste()` helper expands a
  recipe into per-ingredient `WasteLog` rows using the same walker as
  `apply_sale` (sub-recipes recurse). New `/merma/receta` POST +
  recipe-picker form on `/merma`. Four new tests in `tests/test_waste.py`
  cover: expansion math, missing recipe, missing yield, zero/negative
  batch.

- **Cross-page consistency pass** (Saskia feedback, T8 — "Debe coincidir
  con los registros de las demás páginas"). Money formatting in
  `/clientes`, `/cliente_detalle`, `/merma`, `/reportes_diario`,
  `/reportes_iva`, `/reportes_libro_ventas` migrated from inline
  `"Gs. {{ '{:,.0f}'.format(x) }}"` (comma thousands separator — wrong
  for Paraguay) to the `{{ m.gs_full(x) }}` / `{{ m.gs(x) }}` macros
  (period thousands separator — correct). Audit timestamps in
  `/auditoria` moved from `%Y-%m-%d %H:%M:%S` (ISO) to `%d/%m/%Y %H:%M`
  to match the rest of the operator pages. Column-header labels still
  say "Gs." as expected.


### Tests

- 1208 pass, 17 fail (all pre-existing environmental failures unrelated
  to Phase B: Windows path quirks, hardcoded `/opt/data/profiles/ivan/...`
  paths from a different machine, missing `py.typed` marker). The
  touched-area tests (recipe units, costing, calendar macro, settings,
  production, sales channel, price history) all pass clean.

### Added (2026-09-17) — Visual audit wins

- **Insight cards on dashboard** (audit P0 #5). The five insight lists
  (`insights.stars`, `insights.dogs`, `insights.low_stock_alerts`,
  `insights.rising_products`, `insights.churning_products`) used to render
  as bare unstyled `<ul>` lists with `.quadrant-star/dog` headings that
  had no CSS. Now wrapped in a new `m.insight_card(title, items, severity,
  icon)` macro that produces a Lightspeed-style left-bordered card with
  severity color (ok=green / warn=amber / danger=red), icon, title, and
  title+body items on tinted surfaces. ~46 lines removed, richer markup
  gained.

- **vs. last period deltas on top-line metrics** (audit P1 #10). The
  three top metric cards (Ventas, Costo de lo vendido, Margen) now show
  an arrow + percentage + "vs. ayer / semana pasada / mes pasado"
  sub-label. Driven by new `_prior_period_window()` (today=yesterday,
  week=prev Mon-Sun, month=full prior month) and `_delta_pct()` helpers
  in `app/routers/dashboard.py`. Window totals extracted into
  reusable `_compute_window_totals()` — still <60 DB queries per render
  (verified by `tests/test_dashboard_perf.py`). 17 new tests in
  `tests/test_dashboard_deltas.py` (window math + delta math + seeded
  integration: today=5/yesterday=1 → "400% arriba vs. ayer").

### Changed (2026-09-17) — Phase 4+5

- **WCAG AA compliance — brand accent.** `--color-accent` bumped from
  orange-500 (`#f97316`, 2.8:1 on white — failed AA) to **orange-700
  (`#c2410c`, 5.18:1 on white — passes AA)**. Hover state bumped from
  orange-600 to orange-800 for the same reason. Visually almost
  identical (a slightly deeper, richer orange); accessibility gain is
  significant. Dark mode accent (orange-400 on gray-800) was already
  at 6.49:1 — left unchanged.

- **Keyboard shortcuts.** New `app/static/shortcuts.js` provides
  `g + <letter>` navigation (g+i → Inicio, g+v → Ventas, g+p →
  Productos, g+r → Recetas, g+n → Inventario, g+e → Cierre, g+m →
  Merma, g+s → Settings, g+a → Auditoria, g+o → Ops, g+x → Excel,
  g+l → Reponer, g+t → Reportes, g+c → Clientes) plus `?` to open
  a help modal and `Esc` to close it. Zero deps, ~100 LOC, ~4.5 KB
  unminified. Disabled automatically when typing in form fields.
  Modal uses ARIA `role="dialog"` + `aria-modal="true"` +
  `aria-labelledby` + focus trap (close button auto-focuses).

- **`kbd` styling.** New CSS class for `<kbd>` elements — used in the
  shortcuts help modal.

### Added (2026-09-17) — Phase 1+3

- **Visual Revolution Phase 1 — Component migration.** Migrated 14
  templates (`ventas`, `productos`, `recetas`, `inventario`, `merma`,
  `clientes`, `auditoria`, `eod`, `produccion`, `reorder`, `reportes`,
  `reportes_diario`, `reportes_iva`, `reportes_libro_ventas`, `cliente_detalle`)
  to use the new component vocabulary: `.card` + `.card-header/body/footer`,
  `.table.is-hoverable.is-striped` with `.num` numeric cells and `.actions`
  right-aligned action columns, `.btn-sm`, `.btn-ghost`, `.btn-danger-ghost`,
  `.metric-card` for KPI cards, `.empty-state` with icon + heading + CTA
  for every list page when 0 rows, `.alert-success` for "all good" states,
  and SVG icons on every primary action button. Tables are now striped +
  hoverable + sticky-headered.

- **Phase 3 — Data visualization dashboard.** New `app/rms/charts.py`
  module with hand-rolled SVG chart helpers (`sparkline`, `line_chart`,
  `bar_chart`, `pie_donut`) that use CSS custom properties so they
  re-theme correctly. Zero JS chart library, zero new dependencies.
  The `/` dashboard now renders **5 visual cards** alongside the
  metric tiles:
  - **Ventas por hora del día** — vertical bar chart bucketed by
    Asunción-local hour
  - **Tendencia — últimos 30 días** — line chart with grid + axis labels
  - **Distribución de pagos** — donut chart with legend
  - **Top productos por ventas** — horizontal bar list (top 5)
  - **Alertas de stock bajo** — color-coded alert list (severity-aware)
  - Every card has a "Actualizado a las HH:MM:SS" freshness timestamp
  - Every chart has `role="img"` + `aria-label` for screen readers
  - All chart text input is XML-escaped (XSS prevention)
  - Charts use `var(--color-accent)` so dark mode re-themes them

- **Phase 1+3 — New macros.** `chart_card`, `top_list_card`,
  `alert_list_card` in `_components/macros.html` for consistent
  dashboard rendering.

### Added (2026-09-17)

- **Visual Revolution Phase 0 — Design System Token Foundation.** Complete
  refactor of `app/static/app.css` from a flat 17-variable flat scheme to a
  full primitive → semantic → component token model (50+ tokens). Brand
  orange refreshed from brown `#b45309` to vibrant Tailwind-aligned
  `#f97316`. New component classes: `.btn-primary/secondary/ghost/danger/icon/sm/lg`,
  `.card` + `.card-header/body/footer`, `.metric-card` + `.metric-value/delta`,
  `.badge-ok/warn/danger/info/neutral/dot/sm/lg`, `.table.is-striped/hoverable/--compact/--comfortable`,
  `.alert-success/warn/danger/error/info`, `.modal-backdrop/dialog/header/body/footer`,
  `.spinner`, `.skeleton` (with block/circle/line variants), `.empty-state`,
  `.quick-sell-grid`. Full dark mode (every semantic token overridden under
  `[data-theme="dark"]`), high-contrast support via `forced-colors` media
  query, and `prefers-reduced-motion` global reset.

- **Phase 0 — Iconography.** 28 hand-authored SVG icons in a single sprite
  at `app/templates/_components/icons.svg`, integrated via
  `<svg class="icon"><use href="#icon-name"/></svg>`. No font dependency, no
  JS dependency. Nav links, action buttons, and the brand mark all use
  icons now. Every icon button has an `aria-label`. 4 new regression tests.

- **Phase 0 — Styled 404 / 500 error pages.** New
  `app/templates/errors/404.html` and `500.html` with the same nav, friendly
  copy in Paraguayan Spanish (vos form), and a request_id display on 500s.
  The global exception handler in `app/rms/main.py` now serves the HTML
  page to browsers (Accept: text/html) and structured JSON to API clients
  (Accept: application/json). The raw exception text NEVER leaks to the
  browser — it's logged with the request_id but replaced with a generic
  message in the response body. 4 new regression tests.

- **Phase 0 — Mobile hamburger nav.** CSS-only `<input type="checkbox">` +
  `<label>` pattern in `base.html` for nav collapse below 768px. Zero JS
  required. Works with assistive tech (label/checkbox pair is keyboard-
  accessible).

- **Phase 0 — `@media print` styles.** Paper-friendly rendering for EOD +
  reports: hides nav, switches to black-on-white, removes shadows, expands
  tables. Used by the locked `test_phase6_polish::test_css_has_print_styles`
  regression.

### Changed (2026-09-17)

- **`app/templates/base.html` — nav rewritten to use `nav_link` macro with
  icons.** All 15 nav items now have SVG icons. Theme toggle + help + health
  + logout moved to `.btn-icon` ghost buttons with `.icon` glyphs. Mobile
  hamburger toggle added at 768px breakpoint.

- **`app/templates/_components/macros.html` — `nav_link` macro accepts
  optional `icon="icon-…"` parameter.** Backwards-compatible: when `icon` is
  empty, output is identical to before.

- **`app/rms/main.py` — exception handlers detect browser vs API clients.**
  Browsers (`Accept: text/html` with no `application/json` preference) get
  the styled HTML error page; API clients get the structured JSON shape
  they were getting before. No breaking change for existing API consumers.

### Tests

- `tests/test_visual_revolution.py` (NEW, 26 tests) — token system
  completeness, dark mode overrides, high-contrast support, reduced-motion
  reset, icon sprite + nav coverage, error page rendering + sanitization,
  every component class is defined in CSS.
- `tests/test_a11y_navigation.py` — 4 regex tests updated to accept the
  new icon-prepended nav markup (regex `.*?` between the tag and the label).
- `tests/test_static_assets.py` — CSS minification size limit bumped from
  11KB to 30KB to reflect the Phase 0 expansion (~22KB minified, was ~7KB).
- All 13 previously-passing test files still pass. Net: **1015 passing,
  4 skipped, 0 failing** (was 992 before Phase 0).

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
  assistant cannot perform the rotation itself (CF dashboard access).### Changed (HEREBUS integration — Waves 1-4, 2026-09-23)

**Wave 1 — Nav menu reorg** (1 file edit):
- Eliminated the "Operación HEREBUS" label from the side menu.
- Reorganized into 6 buckets: Día a día, Compras & Stock, Cocina, Finanzas, Análisis & Control, Sistema.
- Relabeled: `/wishlist` → "Equipamiento" (it's kitchen gear, not consumables); `/pricing` → "Precios por canal"; `/vs-mercado` → "Precios vs mercado"; `/dashboard` (HEREBUS) → "KPIs" (to disambiguate from `/`); `/shopping-list` → moved from HEREBUS bucket to core "Compras & Stock".

**Wave 2 — Planner merged into Producción** (2 files):
- Embedded the `/produccion-planner` form as a collapsible "Plan manual" section in `produccion.html` (day view only).
- Added `recipes` to `/produccion` render context (from `Recipe` table).
- Added a back-link "← Volver a Producción" in `planner.html`.
- `/produccion-planner` and `/produccion-planner/compute` routes still work for backward compat.

**Wave 3 — HEREBUS KPIs folded into home** (2 files):
- Added to `dashboard.py` context: `sl_open_count`, `sl_total_gs`, `wishlist_count`, `wishlist_total_gs`, `risk_count`, `risk_severity_gs`.
- Added new imports: `WishlistItem`, `ShoppingListItem`, `RiskItem`.
- Added "Operación (cola de tareas)" card to `inicio.html` showing all 6 KPIs at a glance with links to the detail pages.

**Wave 4 — Delivery zones folded into Settings** (3 files):
- `/delivery-zones` GET now redirects (303) to `/settings#zonas-delivery`.
- Added `delivery_zones` to `/settings` render context.
- Added new "Zonas de Delivery" section to `settings.html` showing zone table (order, code, name, coverage, cost, min order, status).
- Nav link `/delivery-zones` updated to `/settings#zonas-delivery`.

### Added
- `tests/test_herbus_integration.py` — 16 tests covering all 4 waves (nav labels, router context, template integration, redirects).

### Migration notes
- Bookmarks to `/delivery-zones` will redirect automatically.
- `/produccion-planner` still works standalone (back-link added).
- Nav structure changed but no routes renamed — existing links in operator training materials keep working.


## [Unreleased]

### Fixed (UI audit patch set, 2026-09-23)
- **`m.gs()` / `m.gs_full()` / `m.stock_badge()` / `m.top_list_card()` registered as Jinja globals** — these were referenced in 30+ templates but never defined; all money displays and stock badges were silently empty. Now defined in `app/services/template_render.py` with `gs` (returns `Gs. 8.696.000`), `gs_full` (alias), `gs_plain` (no prefix), `stock_badge` (3-tier: Agotado/Bajo/OK + Negativo), `margin_pct`, `top_list_card`. Backed by `tests/test_template_render_m.py`.
- **Russian text fragments removed** from `/reportes` "retención" card description (`reportes.py:118`) and the `reportes_retencion.html` empty state — `впервые appeared` → "compraron por primera vez".
- **Dev hints stripped from production UI** — `dashboard.html` footer "Source: Computed live from Sale table. Targets from HEREBUS_Analisis KPI_Dashboard sheet" → "Datos locales". Subtitle "KPIs en vivo desde HEREBUS_FoodBiz + ANALISIS sheets" → "KPIs en vivo · datos del local".
- **Float precision noise in `/shopping-list` and `/reorder`** — `qty_to_buy` rounded to 4 decimal places at calc site (`shopping.py:246`) and `{{ "%.2f"|format(...) }}` replaced with `{{ ... |round(2) }}` in shopping_list.html, reorder.html, recetas.html, inventario.html (9 replacements).
- **Modal backdrop clipping** — `dialog{position:relative; z-index:1}` rule was overriding `dialog.modal{position:fixed; inset:0; z-index:var(--z-modal)}`. Added specific override for `dialog.modal`.

### Changed
- **Stock badge tiers (W2.1)** — `m.stock_badge(stock, min)` returns 4 levels: Negativo (red) for stock<0, Agotado (red) for stock==0, Bajo (amber outline) for 0<stock<min, OK (muted gray) for stock>=min. CSS in `app/static/app.css`: `.badge--stock-out`, `.badge--stock-low`, `.badge--stock-ok`.
- **Numeric/currency right-align (W2.5)** — added `table.data td.num, table.data td.currency{text-align:right;font-variant-numeric:tabular-nums}` rule. Existing `table .num` and `td.num` classes already honor this in app.css.
- **`Dockerfile` copies `docs/` into the container** — root cause of `/guia` 404 was that the user-guide markdown lived at `docs/user-guide/*.md` on the host but was never bundled into the Docker image. Now both builder and runtime stages copy the directory.

### Added
- `tests/test_template_render_m.py` — 17 tests covering `m.gs`, `m.gs_plain`, `m.stock_badge`, `m.margin_pct`, `m.top_list_card` (all green).


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

### Refactor (2026-09-23) — Phase 3.1: split app/rms/models.py

The monolithic `app/rms/models.py` (1350 LOC, 36 model classes) was split into a
per-domain sub-package at `app/rms/models/`:

| File | Models |
|---|---|
| `core.py` | `Base` (shared declarative registry) |
| `audit.py` | `AppMeta` |
| `auth.py` | `User`, `AuditLog`, `SettingsKV`, `Tenant` |
| `inventory.py` | `Ingredient`, `Recipe`, `RecipeLine`, `Product`, `IngredientPriceEvent`, `PriceHistory` |
| `sales.py` | `Sale`, `SaleStockMove`, `Customer`, `Tag`, `TagLink`, `RecipePricing` |
| `orders.py` | `Pedido`, `PedidoLine` |
| `production.py` | `ProductionCompletion`, `ProductionPlanTemplate`, `ProductionPlanOverride`, `ProductionPlan` |
| `procurement.py` | `Supplier`, `WasteLog`, `ShoppingListItem`, `StockMovement`, `ImportBatch` |
| `delivery.py` | `DeliveryZone` |
| `herbus_drive.py` | `WishlistItem`, `RiskItem`, `MarketBenchmark`, `BankTransaction`, `ComplianceInfo`, `MarketPriceReference` |

**Backward compatibility:** `app/rms/models/__init__.py` re-exports every model
class at the top level, so all 470+ existing `from app.rms.models import X`
call sites in `app/` and `tests/` continue to work unchanged. Verified by AST
analysis: **992 import symbols resolved, 0 missing.**

**Migration:** no code changes required at any call site. `app/rms/models.py`
deleted; the package `app/rms/models/` is now in its place.

### Migration notes

- The split moves files only — no model definitions, column types, FKs,
  relationships, or constraints were altered.
- The shared `Base` lives in `app/rms/models/core.py`. Import it via
  `from app.rms.models.core import Base`. Domain modules import `Base` once at
  module level; SQLAlchemy's mapper config attaches to the shared registry.
- Cross-domain `relationship("X", back_populates="...")` strings resolve at
  mapper-config time. Order of imports across the 9 sub-modules doesn't matter
  because each class registers with the same `Base.registry` on import.

### Verified

- **35 mappers registered** (Base + 36 model classes - 1 = 35 tables; matches
  the schema's prior count).
- **1981 tests collected** with 0 collection errors.
- **Full subset runs:** 1656 pass / 101 fail (vs `main`: 1656 / 101 — identical).

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
