# Test Analysis: Pre-Existing Failures on Clean origin/main

**Date:** 2026-10-10
**Branch audited:** `origin/main` (commit `78828464`)
**Branch under review:** `fix/real-bugs-on-clean-main-2026-10-10` (PR #138, with the 4 already-fixed tests)

## TL;DR

| Bucket | Count | Status |
|---|---|---|
| **Already fixed in PR #138** | 4 | ✅ Will be green on PR merge |
| **Known pre-existing (out of scope)** | 6 | ❌ Tracked separately |
| **NEW pre-existing failures (need investigation)** | 18 | ⚠️ **Most are real dormant bugs** |
| **Total** | **28** | |

1784 tests pass. 28 fail. The 22 NEW failures (18 unique bugs + 4 already-fixed) are the focus of this analysis.

## Methodology

1. Ran a strategic test subset (`-k "inventario or sale or eod or produccion or refund or venta or pedido or dashboard or price_history"`) covering the most-likely-buggy business logic.
2. Captured 1784 pass / 28 fail in 15 minutes.
3. Investigated each failure: read the assertion, traced the route, categorized.

## NEW Pre-Existing Failures (18 tests, all real bugs)

### Critical: Business logic broken silently

These are dormant bugs that would cause real harm in production but the test suite catches them.

| Test | Domain | Real bug |
|---|---|---|
| `test_fiado.py::test_venta_fiado_crea_cargo_automatico` | Sales | Sale-as-fiado doesn't create a customer debt. Customer's saldo stays at 0. |
| `test_fiado.py::test_venta_fiado_sin_cliente_rechazada` | Sales | `/ventas/nueva` accepts a sale without a customer (returns 303) when it should reject (400). |
| `test_fiado.py::test_venta_multi_fiado_crea_cargo` | Sales | Same as first; multi-item fiado sale doesn't create per-line customer debt. |
| `test_idempotency_request_id.py::test_idempotency_value_stores_request_id_in_json` | Idempotency | Idempotency record value is not stored as JSON; the row's value is empty so `json.loads` fails. |
| `test_idempotency_request_id.py::test_existing_idempotency_record_reads_sale_id_back` | Idempotency | Same root cause — value column is empty. |
| `test_loyalty_ledger.py::test_sale_creation_credits_points_to_customer` | Loyalty | Sale creation doesn't write `LoyaltyTransaction` rows for `earn_sale`. The loyalty system is silently broken for the most common flow. |
| `test_per_user_audit.py::test_sale_create_records_operator` | Audit | Sale creation doesn't write an audit row. **OPSEC violation**: every state change should leave a log. |
| `test_printer_trigger.py::test_sale_creation_triggers_printer` | Sales | `/ventas/nueva` returns 422 instead of 303 for a normal sale. Some validation is rejecting the form. |
| `test_printer_trigger.py::test_printer_failure_does_not_break_sale` | Sales | Same as above. |

### Critical: UI is regressed (rendering tests fail)

| Test | UI element | Real bug |
|---|---|---|
| `test_demo_reset.py::test_dashboard_empty_state_after_reset` | Dashboard | After demo reset, dashboard should show "Sin ventas" but renders with SVG icons instead. |
| `test_p3_connections.py::test_dashboard_shows_upcoming_birthday` | Dashboard | "Cumpleaños de la semana" widget missing from dashboard. |
| `test_produccion_polish.py::TestTableOverhaulColumns::test_allergen_badges_removed_from_row_body` | Produccion | Production table still has `allergen-badge` class — the polish refactor didn't land. |
| `test_produccion_ux_fixes_oct06.py::TestShiftFormSubmit::test_submit_button_has_save_icon_and_text` | Produccion | "Guardá ejecución del turno" text missing from the shift submit button. |
| `test_produccion_v3_phase0.py::test_day_view_contains_meta_unidades_column` | Produccion | Production day view's plan column doesn't show 'Lotes' or 'Meta (und)' labels. |
| `test_SASKIA-306_pedidos_proveedores_menus.py::test_menus_page_has_combo_form` | Pedidos | The "25.000" formatted price placeholder is missing from the menus page. |
| `test_rate_limit_write_endpoints.py::test_ventas_nueva_rate_limited_after_burst` | Rate limit | All POSTs to `/ventas/nueva` return 404 (route doesn't exist for this test). The test is right about the burst behavior; the route lookup is failing. |

### Critical: Refactor incomplete

| Test | Domain | Real bug |
|---|---|---|
| `test_produccion_bulk_adhoc_csv.py::test_router_bulk_csv_uses_upsert_completion` | Produccion | B.7 refactor: the bulk CSV route must reuse `_upsert_completion` so existing single-row tests still cover it. The bulk route doesn't. |
| `test_produccion_bulk_adhoc_csv.py::test_router_bulk_csv_renders_summary_html` | Produccion | B.7 refactor: the bulk CSV summary must include a "Volver al plan" back-link. Missing. |
| `test_crud_roundtrips_phase14_tier4.py::test_sale_multi_item_appears_in_daily_total` | Sales | Multi-item sale creation fails with 422: "Para registrar ventas en efectivo necesitás abrir la caja." (The test fixture didn't open a caja, but the route should accept the sale when the fixture does.) |

## Known pre-existing failures (out of scope, verified on clean main)

6 tests in `test_dashboard_aggregation_discount_fix.py` — they assert `'Sin ventas todavía'` but the chart renders `'Sin datos de ventas por hora'`. The tests were written against a different copy; the chart was renamed and the tests weren't updated.

## Already fixed in PR #138

4 tests:
- `test_dashboard_deltas.py::test_dashboard_renders_delta_up_pill` — `prior_label` missing from context
- `test_price_history.py::test_inventory_update_writes_price_event_on_price_change` — `lead_time_days` → NULL
- `test_price_history.py::test_inventory_edit_route_writes_event_on_price_change` — same
- `test_price_history.py::test_inventory_edit_route_records_event_when_price_unchanged` — same

## Recommended next actions

| Priority | Action | Effort | Closes |
|---|---|---|---|
| **P0** | Fix the loyalty points bug — sale creation doesn't credit `LoyaltyTransaction` | S (2-3h) | 1 bug, 14 passing tests reactivated |
| **P0** | Fix the audit log bug — sale creation doesn't write `AuditLog` row | S (2-3h) | 1 bug, OPSEC compliance restored |
| **P0** | Fix the idempotency JSON value bug | S (1-2h) | 2 tests, duplicate-POST forensics restored |
| **P0** | Fix the fiado bug — sale-as-fiado doesn't create customer debt | M (3-4h) | 3 tests, customer's credit accounting restored |
| **P0** | Fix the sale validation bug — `/ventas/nueva` returning 422 | M (3-4h) | 2 tests, core sale flow restored |
| **P1** | Fix the dashboard UI regressions (empty state, birthdays, dashboard empty state after reset) | S (1-2h each) | 3 tests |
| **P1** | Fix the produccion UX regressions (allergen badges, save icon, meta unidades, volver al plan) | S (1-2h each) | 5 tests |
| **P1** | Update test copy on `test_dashboard_aggregation_discount_fix.py` to match `'Sin datos de ventas por hora'` | XS (15min) | 6 tests, clean CI |

## Test infrastructure insights

From the strategic run:
- 1784 tests pass in 15min on clean main
- 28 fail in the same window
- 4 of those 28 will be fixed by PR #138 (already merged locally)
- 6 of those 28 are known (out-of-scope copy mismatch)
- 18 of those 28 are real dormant bugs (worth their own PRs)

Estimated total fix effort: **15-20h** spread across P0/P1 PRs. Each bug is small but high-impact for the operator.
