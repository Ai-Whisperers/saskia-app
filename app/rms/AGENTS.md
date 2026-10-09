# AGENTS.md — `app/rms/` engineering conventions

> **For Kiki and any agent modifying `app/rms/` modules.** The hard rules that
> apply specifically to the `app/rms/` package (the core domain logic).

## Money rules (NEVER break these)

1. **All money calculations use `Decimal`, never `float`.**
2. **All money persistence paths go through `app/rms/money.py:to_int_gs()`.**
3. **No other integer-cast for money is allowed.** If you find one, it's a bug.
4. **No `Numeric` or `Float` SQLAlchemy columns for money.** If you find one, it's a bug.
5. **DB columns are INTEGER.** Adding `Numeric` requires explicit operator OK.

## Unit rules

1. **All unit input goes through `app/rms/units.py:Unit.coerce()`.**
2. **Cross-family unit conversion (g→L, kg→und, etc.) is forbidden.** Raises `ValueError`.
3. **Adding new units to `Unit` enum requires operator OK + alias-map update.**
4. **Never store units as free-text in DB.** Enum values only.

## Time rules

1. **All datetime math uses `zoneinfo.ZoneInfo("America/Asuncion")` via `ASUNCION_TZ`.**
2. **DB stores UTC datetime.** Display/period math uses Asunción local.
3. **Never use `datetime.now()` without a tz.** Always `datetime.now(ASUNCION_TZ)`.
4. **Period boundaries (today/week/month) are Asunción local calendar boundaries.**

## Recipe rules

1. **`recipe_line` is polymorphic via `line_kind` ∈ {'ingredient', 'sub_recipe'}.**
2. **`line_ref_id` points to either `ingredient.id` or `recipe.id` depending on `line_kind`.**
3. **Costing walks the recipe tree recursively.** Cycle detection raises `CycleInRecipeTree`.
4. **`yield_qty` is required for sales to be applied.** Sales with NULL `yield_qty` are rejected.

## Stock rules

1. **Stock moves are atomic with sale creation.** All-or-nothing.
2. **Negative stock is allowed.** No exception raised. UI shows red-flash alert.
3. **Void reverses stock moves fully, including sub-recipe expansion.**
4. **`sale_stock_move.affected_recipe_id` is for audit, not for re-walking.** The
   tree walk during void uses the current recipe state, not the historical one.

## Testing rules

1. **Money tests are in `tests/test_money.py`.** Property-based via hypothesis.
2. **Unit tests are in `tests/test_units.py`.** Property-based via hypothesis.
3. **Costing tests are in `tests/test_costing.py`.** TDD-first: write the test before the implementation.
4. **Coverage gate: 80% overall, 95% for money.py and units.py, 90% for costing.py.**
5. **No float in money test inputs.** Use `Decimal(str(value))`.

## Migration rules

**Postgres DDL auto-commits.** On SQLite this is a non-issue (DDL is
transactional) and `try/except` around ALTERs is fine. On Postgres,
each `ALTER TABLE` / `CREATE INDEX` is its own implicit commit — a
failing 5th ALTER leaves the first 4 applied. The next migration then
runs against a partial baseline.

**Fix:** use `atomic_ddl_block(conn, [sql1, sql2, ...])` (defined in
`app/rms/db.py`) instead of looping `conn.exec_driver_sql(sql)` in
plain try/except. The helper wraps each statement in a SAVEPOINT on
Postgres (no-op on SQLite), so a failure in statement N rolls back
ONLY N while statements 1..N-1 stay applied.

Per-statement try/except is still allowed **inside** the helper (for
migrations that want to skip-and-continue on individual ALTERs), but
batch DDL like `add_columns_sql` lists should pass the whole list to
`atomic_ddl_block` so the SAVEPOINT isolation kicks in.

Migration 081 (`_migration_081_pedido_delivery_window`) is the
reference example — it batches 6 ADD COLUMNs into one
`atomic_ddl_block(conn, list(add_columns_sql))` call.

## Module structure (when adding new files)

- Pure logic (no DB, no IO): `app/rms/<module>.py` with public function exports.
- DB-touching logic: `app/rms/<module>.py` taking `session: Session` as first arg.
- Routers: `app/routers/<module>.py` exporting `router` (FastAPI APIRouter).
- Templates: `app/templates/<page>.html` extending `base.html`.
- Services (file IO, external): `app/services/<module>.py`.

## Things to NOT do

- ❌ Don't add async def handlers. Sync only.
- ❌ Don't add third-party deps without operator OK.
- ❌ Don't change money rounding rules.
- ❌ Don't add HTTP calls to third parties (other than R2 encrypted backup).
- ❌ Don't change `BIND_HOST` from `127.0.0.1`.
- ❌ Don't write log lines containing customer notes, supplier phone numbers, etc.
