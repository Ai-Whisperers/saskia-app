# SASKIA-204: Sale channel mismatch cleanup

**Status:** closed 2026-10-07
**Author:** Hermes (Ivan's AIW session)
**Branch:** main

## Problem

Revenue reports in /ventas/historial were skewed because:

1. **Import script fallback bug** (`scripts/import_herebus_data.py:622`): the raw `Canal de Venta` value from HEREBUS exports was being collapsed to `mostrador` via `channel or "mostrador"` for any non-recognized raw value. In a sample of 346 sales, 9 were misclassified this way.
2. **No place to put the 4 HEREBUS channels**: retail/wholesale/distributor/eventual exist in HEREBUS but had no enum slot, so they fell into the fallback.
3. **No /ventas/historial filter by channel**: operators couldn't slice the table to one channel for accounting.

## What shipped

- **Migration 112** (`app/rms/migrations/_112_extended_channel_check.py`): extends the SQLite CHECK constraint on `sale.channel` from 6 to 10 values via DROP TRIGGER + CREATE TRIGGER. Mirrors `Channel.allowed_values()` — the test `test_channel_enum_and_migration_have_same_allowed_set` enforces this alignment.
- **Channel enum extended** (`app/rms/models/channels.py`): added `RETAIL/WHOLESALE/DISTRIBUTOR/EVENTUAL`. `display_order()` keeps front-of-house first (operator's mental model).
- **Postgres CHECK constraint updated** (`app/rms/models_legacy.py`): the `CheckConstraint` on `sale.channel` and `pedido.channel` now allows the 4 new values. (Defense-in-depth — SQLite triggers handle the runtime check.)
- **Channel seed** (`app/rms/db.py:_migration_041_channel_catalog`): the `channel` table now seeds the 4 new channels.
- **`/ventas/historial` filter** (`app/routers/sales.py` + `app/templates/ventas_historial.html`): `channel` query param + combo_field in the filter form. Same filter applied to `sales_q`, `count_q`, and `totals_q` so pagination stays correct. Pagination links preserve the param.
- **CSV export filter** (`app/routers/sales.py:sales_export_csv`): operators exporting for IVA can now filter to one channel at a time.
- **Reclassify script** (`scripts/reclassify_sale_channels.py`): idempotent backfill. Reads the VENTAS export CSV, UPDATEs `sale.channel` where the canonical value differs. Idempotency key is `(sold_at ± 1s, qty)` — the 1s window handles the SQLAlchemy/Python microsecond format mismatch with SQLite text storage. Always dry-run first; `--apply` to actually run.
- **Import script fix** (`scripts/import_herebus_data.py`): now uses the same `_normalize_channel()` helper so future imports don't reintroduce the silent-skew bug. `_RAW_TO_CHANNEL` kept inline (so the import script doesn't depend on the reclassify script — separate invocation contexts).

## Bugs found + fixed during work

1. **Stale `/tmp/baseline-6ffe16d3` editable install** shadowing the real `app/` package via `_editable_impl_aiw_saskia_rms.pth`. Every `uv run python` invocation imported the OLD baseline's `app.rms.config` (where `CURRENT_SCHEMA_VERSION` was still 102), so migration 112 appeared to be missing from the runtime `MIGRATIONS` dict. Resolution: `uv sync` removed the stale `.pth`. 43 channel tests + 28 reclassify tests now pass against the real package.

2. **`parse_decimal` collapsed `2.0` → `20`**: the original `raw.replace(".", "").replace(",", ".")` stripped ALL periods, treating them as thousands separators. Fixed to only strip periods when both `.` and `,` are present (heuristic: only the last comma-separated part is fractional iff it's exactly 3 digits and the rest are integers).

3. **SQLAlchemy `DateTime` microsecond mismatch**: SQLAlchemy compiles `Sale.sold_at == datetime(2026,10,1,0,0)` to `WHERE sold_at = '2026-10-01 00:00:00.000000'` (with microseconds) but the SQLite test DB had `'2026-10-01 00:00:00'` (no microseconds). The ORM UPDATE returned rowcount=0 despite SELECT returning 1 match. Fix: use `Sale.sold_at BETWEEN (u["sold_at"] - 1s, u["sold_at"] + 1s)` so the format mismatch is absorbed.

4. **`test_channel_filter` failure**: pre-existing test used `channel="delivery"` (not a valid channel — the CHECK constraint was correctly rejecting it). Fixed to use `"whatsapp"` (valid in both old + new sets).

## Tests

- `tests/test_reclassify_sale_channels.py` (NEW): 28 tests — parametrized raw→canonical mapping + dry-run + actual-update paths + sales-table regression test.
- `tests/test_sale_channel.py`: `test_all_five_channels_accepted_by_apply_sale` extended from 5 to 10 channels.
- `tests/test_P42_channel_enum_integration.py`: `test_channel_enum_and_migration_have_same_allowed_set` now checks against the LATEST migration's `_ALLOWED_CHANNELS`.
- `tests/test_sales_history_filter.py`: `test_channel_filter` rewritten to count `<td>` cells instead of substring match (the page now contains channel labels in the filter UI).

84 channel/reclassify tests + 13 sales-history tests = **97 passing tests** across the ticket.

## What I did NOT do

- Did not run the reclassify script against production. That should be a manual operation: `uv run python scripts/reclassify_sale_channels.py --source-csv /path/to/VENTAS_2026.csv --dry-run` first, review the summary, then `--apply`.
- Did not update `/ventas/qa` or `/ventas/redesign` test pages. They still test the old layout.
- Did not add a `/dwh/channels` report. Operators use the existing `/reportes/ventas` views for that.

## References

- Channel enum source of truth: `app/rms/models/channels.py`
- Migration source of truth: `app/rms/migrations/_112_extended_channel_check.py`
- Reclassify script: `scripts/reclassify_sale_channels.py`
- Import script: `scripts/import_herebus_data.py:_normalize_channel()`
- UI filter: `app/routers/sales.py:_build_sales_context` (channel param), `app/templates/ventas_historial.html` (channel combo)