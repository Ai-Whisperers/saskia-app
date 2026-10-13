"""Parametrized coverage for two more D-grade helpers with no branch matrix.
# allow-hardcoded-dates: frozen-time fixture: 2026-10-01T10:00 stamps in test data rows for stock-forecast

S1 batch-11 (test coverage continuation): lock the branch matrix of two
D-grade helpers that lack parametrized coverage:

  (1) `app/services/import_xlsx.py:_validate_workbook` (CC 28, D-grade)
      Pure validator that walks five sheets of an openpyxl Workbook
      (Ingredientes / Recetas / Lineas / Productos / Ventas) and returns
      (errors, warnings) without writing to the DB. The `mode` parameter
      is part of the signature but is currently unused. Branches covered:

      - empty workbook (no recognised sheets) → no errors, no warnings
        (locks the implicit no-rows branch on every sheet)
      - Ingredientes: name missing → error (locks the `if not name:
        _err(...)` branch)
      - Ingredientes: stock_qty < 0 → error (locks the `stock is not None
        and stock < 0` branch)
      - Ingredientes: purchase_price_gs unparseable → error (locks the
        `except (ValueError, TypeError)` for parse_gs/to_int_gs)
      - Ingredientes: purchase_price_gs as int → accepted (locks the
        `isinstance(price, (int, float))` → to_int_gs path)
      - Lineas: recipe_name empty → warn (locks the `if not recipe_name:
        _warn(...)` branch)
      - Lineas: line_kind not in ('ingredient', 'sub_recipe') → error
        (locks the `line_kind not in (...)` branch)
      - Lineas: qty <= 0 → error (locks the `qty <= 0` branch)
      - Productos: sale_price_gs unparseable → error (locks the same
        parse-failure branch for Productos)
      - Ventas: sold_at missing → error (locks the `if sold_at is None`)
      - Ventas: sold_at in the future → warning (locks the `sold_at >
        now()` branch)
      - Ventas: product_id missing → error (locks the `_opt_int(row.get
        ("product_id")) is None` branch)
      - Ventas: qty <= 0 → error (locks the qty guard for ventas)
      - mixed: a row missing name in Recetas → error (Receta has only the
        name-presence branch)

  (2) `app/services/import_xlsx.py:_import_patch_ingredientes`
      (CC 23, D-grade)
      PATCH-mode Ingredient mutator. Loads the lookup table
      `{name.lower(): Ingredient}`, walks the Ingredientes sheet, matches
      each row by case-insensitive name, and updates stock_qty,
      min_stock_qty, max_stock_qty, purchase_price_gs (also stamps
      purchase_price_updated_at), lead_time_days, and notes. Writes
      warnings + increments result.ingredients for matched rows.

      Branches covered:
      - Ingredientes sheet missing → returns silently (locks the
        `if sheet is None: return` early-exit)
      - row missing `name` → warning, row skipped (locks the `if not
        name_raw` branch)
      - row name not in DB → warning, no DB mutation (locks the `ing is
        None` branch + the "no auto-create" warning text)
      - empty stock_qty cell → not touched (locks the `if stock_v not in
        (None, "")` guard)
      - stock_qty < 0 → warning, no mutation (locks the `new_stock < 0`
        branch)
      - stock_qty >= 0 → applied (locks the `new_stock >= 0` branch)
      - min_stock_qty >= 0 → applied (locks min path)
      - max_stock_qty present and >= 0 → applied (locks `mx >= 0` path)
      - max_stock_qty cell with empty value → unset (locks the
        `mx_v not in (None, "")` guard)
      - purchase_price_gs parseable → applied + purchase_price_updated_at
        is stamped (locks the new_pp path + the timestamp side-effect)
      - purchase_price_gs unparseable → warning, no mutation (locks the
        `_money_int_gs returns None` branch)
      - lead_time_days >= 0 → applied (locks lead_time path)
      - notes present → notes updated (locks notes path)
      - full row → all fields applied + result.ingredients += 1
        (locks the happy-path counter increment)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional

import pytest
from openpyxl import Workbook

if TYPE_CHECKING:
    from app.rms.models_legacy import Ingredient

# NOTE: app.rms.models_legacy and app.services.import_xlsx are imported
# lazily INSIDE the test functions. Importing them at module top triggers
# a circular-import via app/rms/models/__init__.py → models_legacy
# (see the AppMeta / channels import chain). batch-9 follows the same
# lazy-import pattern (see tests/test_d_grade_helpers_batch9.py lines
# 941-943 / 1237-1239); we replicate it here.


# ─── helpers ────────────────────────────────────────────────────────────────


def _make_wb(sheets: dict[str, list[list]]) -> Workbook:
    """Build an openpyxl Workbook from a sheet → rows mapping.

    Mirrors the `_make_wb` helper in tests/test_d_grade_helpers_batch5.py
    so the scaffolding stays consistent across batches. The first row of
    each sheet is the header (column-name → cell-value map consumed by
    `_rows(_sheet(wb, ...))`).
    """
    wb = Workbook()
    default = wb.active
    if default is not None:
        wb.remove(default)
    for name, rows in sheets.items():
        ws = wb.create_sheet(name)
        for row in rows:
            ws.append(row)
    return wb


# ─── _validate_workbook row spec ────────────────────────────────────────────


@dataclass
class _ValidateSpec:
    """One scenario for `_validate_workbook`.

    The validator walks five sheets in a fixed order. The spec seeds a
    workbook with whichever subset is interesting and asserts the
    (errors, warnings) lists come back with the right shape.

    Each `errors_want` / `warnings_want` entry is a tuple of substrings
    that must all appear in the corresponding error/warning dict
    `message` field. A tuple of length 1 with the string "EMPTY" means
    "list should be empty".
    """

    id: str = ""
    # Sheet name → list of rows (header is row 0; data rows follow).
    sheets: dict[str, list[list]] = field(default_factory=dict)
    # expected_total_errors / expected_total_warnings used to lock counts
    expected_total_errors: int = 0
    expected_total_warnings: int = 0
    # Substring tuples that MUST appear in the corresponding messages.
    errors_want: list[tuple[str, ...]] = field(default_factory=list)
    warnings_want: list[tuple[str, ...]] = field(default_factory=list)


# ─── _validate_workbook scenario definitions ────────────────────────────────

_ROWS_VALIDATE: list[_ValidateSpec] = [
    pytest.param(
        _ValidateSpec(
            id="empty_workbook_no_errors_no_warnings",
            sheets={},  # no recognised sheets → all loops empty
        ),
        id="empty_workbook_no_errors_no_warnings",
    ),
    pytest.param(
        _ValidateSpec(
            id="ingredientes_missing_name_errors",
            sheets={
                "Ingredientes": [
                    ["name", "unit", "stock_qty", "purchase_price_gs"],
                    ["", "kg", 1.0, 5000],  # name missing → error
                ],
            },
            expected_total_errors=1,
            errors_want=[("Nombre requerido",)],
        ),
        id="ingredientes_missing_name_errors",
    ),
    pytest.param(
        _ValidateSpec(
            id="ingredientes_negative_stock_errors",
            sheets={
                "Ingredientes": [
                    ["name", "unit", "stock_qty", "purchase_price_gs"],
                    ["Harina", "kg", -1.5, 5000],  # stock < 0 → error
                ],
            },
            expected_total_errors=1,
            errors_want=[
                ("stock_qty no puede ser negativo",),
            ],
        ),
        id="ingredientes_negative_stock_errors",
    ),
    pytest.param(
        _ValidateSpec(
            id="ingredientes_unparseable_price_errors",
            sheets={
                "Ingredientes": [
                    ["name", "unit", "stock_qty", "purchase_price_gs"],
                    # Non-numeric price → parse_gs fails → error.
                    ["Harina", "kg", 10.0, "no-es-un-precio"],
                ],
            },
            expected_total_errors=1,
            errors_want=[
                ("No se pudo parsear precio",),
            ],
        ),
        id="ingredientes_unparseable_price_errors",
    ),
    pytest.param(
        _ValidateSpec(
            id="ingredientes_int_price_accepted",
            sheets={
                "Ingredientes": [
                    ["name", "unit", "stock_qty", "purchase_price_gs"],
                    # int price → to_int_gs branch → no error.
                    ["Harina", "kg", 10.0, 5000],
                ],
            },
        ),
        id="ingredientes_int_price_accepted",
    ),
    pytest.param(
        _ValidateSpec(
            id="recetas_missing_name_errors",
            sheets={
                "Recetas": [
                    ["name"],
                    [""],  # name missing → error
                ],
            },
            expected_total_errors=1,
            errors_want=[("Nombre requerido",)],
        ),
        id="recetas_missing_name_errors",
    ),
    pytest.param(
        _ValidateSpec(
            id="lineas_empty_recipe_name_warns",
            sheets={
                "Lineas": [
                    ["recipe_name", "line_kind", "qty"],
                    ["", "ingredient", 1.0],  # empty recipe_name → warn
                ],
            },
            expected_total_warnings=1,
            warnings_want=[("recipe_name vacío",)],
        ),
        id="lineas_empty_recipe_name_warns",
    ),
    pytest.param(
        _ValidateSpec(
            id="lineas_invalid_line_kind_errors",
            sheets={
                "Lineas": [
                    ["recipe_name", "line_kind", "qty"],
                    ["Brownie", "weird_kind", 1.0],  # not in enum → error
                ],
            },
            expected_total_errors=1,
            errors_want=[("line_kind debe ser",)],
        ),
        id="lineas_invalid_line_kind_errors",
    ),
    pytest.param(
        _ValidateSpec(
            id="lineas_zero_qty_errors",
            sheets={
                "Lineas": [
                    ["recipe_name", "line_kind", "qty"],
                    ["Brownie", "ingredient", 0.0],  # qty <= 0 → error
                ],
            },
            expected_total_errors=1,
            errors_want=[("qty debe ser > 0",)],
        ),
        id="lineas_zero_qty_errors",
    ),
    pytest.param(
        _ValidateSpec(
            id="productos_unparseable_price_errors",
            sheets={
                "Productos": [
                    ["name", "sale_price_gs"],
                    ["Brownie", "no-es-precio"],  # parse fails → error
                ],
            },
            expected_total_errors=1,
            errors_want=[("No se pudo parsear precio",)],
        ),
        id="productos_unparseable_price_errors",
    ),
    pytest.param(
        _ValidateSpec(
            id="ventas_missing_sold_at_errors",
            sheets={
                "Ventas": [
                    ["sold_at", "product_id", "qty"],
                    [None, 1, 1.0],  # sold_at None → error
                ],
            },
            expected_total_errors=1,
            errors_want=[("sold_at requerido",)],
        ),
        id="ventas_missing_sold_at_errors",
    ),
    pytest.param(
        _ValidateSpec(
            id="ventas_future_sold_at_warns",
            sheets={
                "Ventas": [
                    ["sold_at", "product_id", "qty"],
                    # Year 9999 → tz-aware datetime in the future →
                    # > now() → warning (we don't want a future-dated
                    # row to error out, just warn).
                    [datetime(9999, 1, 1, tzinfo=timezone.utc), 1, 1.0],
                ],
            },
            expected_total_warnings=1,
            warnings_want=[("Fecha en el futuro",)],
        ),
        id="ventas_future_sold_at_warns",
    ),
    pytest.param(
        _ValidateSpec(
            id="ventas_missing_product_id_errors",
            sheets={
                "Ventas": [
                    ["sold_at", "product_id", "qty"],
                    # product_id is missing → error.
                    ["2026-10-01T10:00:00", None, 1.0],
                ],
            },
            expected_total_errors=1,
            errors_want=[("product_id requerido",)],
        ),
        id="ventas_missing_product_id_errors",
    ),
    pytest.param(
        _ValidateSpec(
            id="ventas_zero_qty_errors",
            sheets={
                "Ventas": [
                    ["sold_at", "product_id", "qty"],
                    ["2026-10-01T10:00:00", 1, 0.0],  # qty <= 0 → error
                ],
            },
            expected_total_errors=1,
            errors_want=[("qty debe ser > 0",)],
        ),
        id="ventas_zero_qty_errors",
    ),
    pytest.param(
        _ValidateSpec(
            id="multi_sheet_multi_branch",
            sheets={
                # Ingredientes ok + 1 warning via empty stock (no warning).
                "Ingredientes": [
                    ["name", "unit", "stock_qty", "purchase_price_gs"],
                    ["Harina", "kg", 10.0, 5000],
                ],
                # Recetas missing name → error
                "Recetas": [
                    ["name"],
                    [""],
                ],
                # Lineas: valid recipe_name, valid line_kind, qty=0 → error
                "Lineas": [
                    ["recipe_name", "line_kind", "qty"],
                    ["Brownie", "ingredient", 0.0],
                ],
                # Productos ok
                "Productos": [
                    ["name", "sale_price_gs"],
                    ["Brownie", 5000],
                ],
                # Ventas ok
                "Ventas": [
                    ["sold_at", "product_id", "qty"],
                    ["2026-10-01T10:00:00", 1, 1.0],
                ],
            },
            expected_total_errors=2,  # Recetas + Lineas
            expected_total_warnings=0,
            errors_want=[
                ("Nombre requerido",),
                ("qty debe ser > 0",),
            ],
        ),
        id="multi_sheet_multi_branch",
    ),
]


# ─── _validate_workbook driver ──────────────────────────────────────────────


@pytest.mark.parametrize("row", _ROWS_VALIDATE, ids=lambda r: r.id)
def test_validate_workbook_branches(row: _ValidateSpec) -> None:
    """Drive `_validate_workbook` across the 15 scenario rows above.

    The validator is a pure function over an openpyxl Workbook (no
    Session, no DB writes), so we feed it a fresh workbook per scenario
    and assert on the returned `(errors, warnings)` lists. The `mode`
    arg is part of the signature but is unused — we pass `"FULL"` to
    exercise the contract.
    """
    # Lazy import: avoid the app.rms.models_legacy circular import
    # at collection time (see top-of-file note).
    from app.services.import_xlsx import _validate_workbook

    wb = _make_wb(row.sheets)
    errors, warnings = _validate_workbook(wb, "FULL")

    assert len(errors) == row.expected_total_errors, (
        f"[{row.id}] expected {row.expected_total_errors} errors, got {len(errors)}: {errors}"
    )
    assert len(warnings) == row.expected_total_warnings, (
        f"[{row.id}] expected {row.expected_total_warnings} warnings, got {len(warnings)}: {warnings}"
    )

    # Every wanted substring tuple must be matched against an entry's
    # `message` field. We don't pin row/field here (those vary across
    # helpers) — the message substring is the invariant.
    error_messages = [e.get("message", "") for e in errors]
    warning_messages = [w.get("message", "") for w in warnings]

    for want in row.errors_want:
        assert any(all(s in m for s in want) for m in error_messages), (
            f"[{row.id}] expected error matching {want!r}, got {error_messages!r}"
        )
    for want in row.warnings_want:
        assert any(all(s in m for s in want) for m in warning_messages), (
            f"[{row.id}] expected warning matching {want!r}, got {warning_messages!r}"
        )


# ─── _import_patch_ingredientes row spec ───────────────────────────────────


@dataclass
class _PatchSpec:
    """One scenario for `_import_patch_ingredientes`.

    The PATCH helper:
      - returns silently if the Ingredientes sheet is missing;
      - walks rows of the sheet, looking up each row by case-insensitive
        `name` in the DB;
      - for matched rows, applies stock_qty / min_stock_qty /
        max_stock_qty / purchase_price_gs (+ stamps
        purchase_price_updated_at) / lead_time_days / notes;
      - records a warning when a row can't be matched or when an input
        is rejected (negative stock, unparseable price, etc.);
      - increments result.ingredients for each matched row.

    Each spec seeds one or more Ingredients in the DB, runs the helper,
    and asserts on the warnings + the persisted fields.
    """

    id: str = ""
    # Initial ingredient state: list of dicts with name + initial fields.
    seed_ingredients: list[dict] = field(default_factory=list)
    # Sheet rows (header + data). Header is the first list.
    sheet_rows: Optional[list[list]] = None
    # Expected resulting state of the FIRST seeded ingredient (by id
    # order). Use field-only assertions (only the fields you care about).
    expected_first: dict = field(default_factory=dict)
    # Expected warnings (substring tuples).
    warnings_want: list[tuple[str, ...]] = field(default_factory=list)
    # Expected count of result.ingredients after the helper runs.
    expected_result_ingredients: int = 0


def _seed_ingredients(s: Any, specs: list[dict]) -> list[Ingredient]:
    """Seed Ingredient rows from a list of dicts.

    Mirrors tests.factories.make_ingredient shape but is local so we
    don't depend on a default `unit` that's already in the DB. Each dict
    may set name (required), unit, stock_qty, min_stock_qty, max_stock_qty,
    purchase_price_gs, lead_time_days, notes.
    """
    # Lazy import: avoid the app.rms.models_legacy circular import
    # at collection time (see top-of-file note).
    from app.rms.models_legacy import Ingredient as _Ingredient

    out: list[Ingredient] = []
    for spec in specs:
        ing = _Ingredient(
            name=spec["name"],
            unit=spec.get("unit", "kg"),
            stock_qty=spec.get("stock_qty", 0.0),
            min_stock_qty=spec.get("min_stock_qty", 0.0),
            max_stock_qty=spec.get("max_stock_qty", None),
            purchase_price_gs=spec.get("purchase_price_gs", None),
            lead_time_days=spec.get("lead_time_days", 3),
            notes=spec.get("notes", None),
        )
        s.add(ing)
        s.flush()
        out.append(ing)
    return out


# ─── _import_patch_ingredientes scenario definitions ────────────────────────

_ROWS_PATCH: list[_PatchSpec] = [
    pytest.param(
        _PatchSpec(
            id="sheet_missing_returns_silently",
            seed_ingredients=[
                {"name": "Harina", "stock_qty": 5.0},
            ],
            sheet_rows=None,  # → no Ingredientes sheet
            expected_result_ingredients=0,
            warnings_want=[],
        ),
        id="sheet_missing_returns_silently",
    ),
    pytest.param(
        _PatchSpec(
            id="row_missing_name_warns_and_skips",
            seed_ingredients=[
                {"name": "Harina", "stock_qty": 5.0},
            ],
            sheet_rows=[
                ["name", "stock_qty"],
                ["", 10.0],  # missing name → warning, no DB mutation
            ],
            expected_first={"stock_qty": 5.0},  # unchanged
            expected_result_ingredients=0,
            warnings_want=[
                ("sin name",),
            ],
        ),
        id="row_missing_name_warns_and_skips",
    ),
    pytest.param(
        _PatchSpec(
            id="name_not_in_db_warns_and_skips",
            seed_ingredients=[
                {"name": "Harina", "stock_qty": 5.0},
            ],
            sheet_rows=[
                ["name", "stock_qty"],
                # Name not in DB → no auto-create → warning.
                ["Azucar", 10.0],
            ],
            expected_first={"stock_qty": 5.0},  # unchanged
            expected_result_ingredients=0,
            warnings_want=[
                ("no encontrado en DB",),
            ],
        ),
        id="name_not_in_db_warns_and_skips",
    ),
    pytest.param(
        _PatchSpec(
            id="empty_stock_cell_not_touched",
            seed_ingredients=[
                {"name": "Harina", "stock_qty": 5.0},
            ],
            sheet_rows=[
                ["name", "stock_qty"],
                ["Harina", ""],  # empty → guard skips
            ],
            expected_first={"stock_qty": 5.0},  # unchanged
            expected_result_ingredients=1,
        ),
        id="empty_stock_cell_not_touched",
    ),
    pytest.param(
        _PatchSpec(
            id="negative_stock_warns_and_skips_mutation",
            seed_ingredients=[
                {"name": "Harina", "stock_qty": 5.0},
            ],
            sheet_rows=[
                ["name", "stock_qty"],
                ["Harina", -1.5],  # negative → warning, no mutation
            ],
            expected_first={"stock_qty": 5.0},  # unchanged
            expected_result_ingredients=1,
            warnings_want=[
                ("negativo",),
            ],
        ),
        id="negative_stock_warns_and_skips_mutation",
    ),
    pytest.param(
        _PatchSpec(
            id="stock_qty_applied",
            seed_ingredients=[
                {"name": "Harina", "stock_qty": 5.0},
            ],
            sheet_rows=[
                ["name", "stock_qty"],
                ["Harina", 12.5],  # applied
            ],
            expected_first={"stock_qty": 12.5},
            expected_result_ingredients=1,
        ),
        id="stock_qty_applied",
    ),
    pytest.param(
        _PatchSpec(
            id="min_stock_qty_applied",
            seed_ingredients=[
                {"name": "Harina", "min_stock_qty": 1.0},
            ],
            sheet_rows=[
                ["name", "min_stock_qty"],
                ["Harina", 2.5],
            ],
            expected_first={"min_stock_qty": 2.5},
            expected_result_ingredients=1,
        ),
        id="min_stock_qty_applied",
    ),
    pytest.param(
        _PatchSpec(
            id="max_stock_qty_present_applied",
            seed_ingredients=[
                {"name": "Harina", "max_stock_qty": None},
            ],
            sheet_rows=[
                ["name", "max_stock_qty"],
                ["Harina", 50.0],
            ],
            expected_first={"max_stock_qty": 50.0},
            expected_result_ingredients=1,
        ),
        id="max_stock_qty_present_applied",
    ),
    pytest.param(
        _PatchSpec(
            id="purchase_price_applied_and_timestamp_stamped",
            seed_ingredients=[
                {
                    "name": "Harina",
                    "purchase_price_gs": 3000,
                    "purchase_price_updated_at": None,
                },
            ],
            sheet_rows=[
                ["name", "purchase_price_gs"],
                ["Harina", 5000],  # int → to_int_gs → applied
            ],
            expected_first={
                "purchase_price_gs": 5000,
                # timestamp must be set (stamped) — we just check non-None.
                "purchase_price_updated_at_is_set": True,
            },
            expected_result_ingredients=1,
        ),
        id="purchase_price_applied_and_timestamp_stamped",
    ),
    pytest.param(
        _PatchSpec(
            id="purchase_price_unparseable_warns",
            seed_ingredients=[
                {
                    "name": "Harina",
                    "purchase_price_gs": 3000,
                },
            ],
            sheet_rows=[
                ["name", "purchase_price_gs"],
                ["Harina", "no-es-precio"],  # parse fails
            ],
            expected_first={"purchase_price_gs": 3000},  # unchanged
            expected_result_ingredients=1,
            warnings_want=[
                ("purchase_price_gs",),
            ],
        ),
        id="purchase_price_unparseable_warns",
    ),
    pytest.param(
        _PatchSpec(
            id="lead_time_days_applied",
            seed_ingredients=[
                {"name": "Harina", "lead_time_days": 3},
            ],
            sheet_rows=[
                ["name", "lead_time_days"],
                ["Harina", 7],
            ],
            expected_first={"lead_time_days": 7},
            expected_result_ingredients=1,
        ),
        id="lead_time_days_applied",
    ),
    pytest.param(
        _PatchSpec(
            id="notes_applied",
            seed_ingredients=[
                {"name": "Harina", "notes": "old note"},
            ],
            sheet_rows=[
                ["name", "notes"],
                ["Harina", "new note"],
            ],
            expected_first={"notes": "new note"},
            expected_result_ingredients=1,
        ),
        id="notes_applied",
    ),
    pytest.param(
        _PatchSpec(
            id="full_row_all_branches",
            seed_ingredients=[
                {
                    "name": "Harina",
                    "stock_qty": 5.0,
                    "min_stock_qty": 1.0,
                    "max_stock_qty": None,
                    "purchase_price_gs": 3000,
                    "lead_time_days": 3,
                    "notes": "old",
                },
            ],
            sheet_rows=[
                [
                    "name",
                    "stock_qty",
                    "min_stock_qty",
                    "max_stock_qty",
                    "purchase_price_gs",
                    "lead_time_days",
                    "notes",
                ],
                [
                    "Harina",
                    20.0,
                    2.0,
                    100.0,
                    5000,
                    5,
                    "updated via patch",
                ],
            ],
            expected_first={
                "stock_qty": 20.0,
                "min_stock_qty": 2.0,
                "max_stock_qty": 100.0,
                "purchase_price_gs": 5000,
                "lead_time_days": 5,
                "notes": "updated via patch",
                "purchase_price_updated_at_is_set": True,
            },
            expected_result_ingredients=1,
        ),
        id="full_row_all_branches",
    ),
]


# ─── _import_patch_ingredientes driver ─────────────────────────────────────


@pytest.mark.parametrize("row", _ROWS_PATCH, ids=lambda r: r.id)
def test_import_patch_ingredientes_branches(row: _PatchSpec, session_factory) -> None:
    """Drive `_import_patch_ingredientes` across the 13 scenario rows above.

    The helper is a pure SQLAlchemy consumer (no FastAPI Request/Depends),
    so it's called directly with session + workbook + result. We seed
    initial state, run the helper, then assert on the warnings + the
    persisted state.
    """
    # Lazy imports: avoid the app.rms.models_legacy circular import
    # at collection time (see top-of-file note).
    from sqlalchemy import select as _select

    from app.rms.models_legacy import Ingredient as _Ingredient
    from app.services.import_xlsx import ImportResult as _ImportResult
    from app.services.import_xlsx import _import_patch_ingredientes

    result = _ImportResult(batch_id=0, source_filename=f"{row.id}.xlsx", mode="PATCH")
    sheets: dict[str, list[list]] = {}
    if row.sheet_rows is not None:
        sheets["Ingredientes"] = row.sheet_rows
    wb = _make_wb(sheets)

    with session_factory() as s:
        seeded = _seed_ingredients(s, row.seed_ingredients)
        s.commit()  # so the helper's session.get lookups see the rows

        _import_patch_ingredientes(s, wb, result)

        s.flush()

        # Read back the first seeded ingredient (for assertions).
        first = s.execute(_select(_Ingredient).where(_Ingredient.id == seeded[0].id)).scalar_one()

        # Pin the fields specified by the spec.
        for field_name, expected in row.expected_first.items():
            if field_name == "purchase_price_updated_at_is_set":
                assert first.purchase_price_updated_at is not None, (
                    f"[{row.id}] expected purchase_price_updated_at to be set"
                )
                continue
            actual = getattr(first, field_name)
            assert actual == expected, (
                f"[{row.id}] expected {field_name}={expected!r}, got {actual!r}"
            )

        # Pin the counter.
        assert result.ingredients == row.expected_result_ingredients, (
            f"[{row.id}] expected result.ingredients={row.expected_result_ingredients}, "
            f"got {result.ingredients}"
        )

        # Pin the warnings.
        warning_messages = [str(w) for w in result.warnings]
        for want in row.warnings_want:
            assert any(all(sub in m for sub in want) for m in warning_messages), (
                f"[{row.id}] expected warning matching {want!r}, got {warning_messages!r}"
            )


# ─── Row-count doc-lock ────────────────────────────────────────────────────


# Locks the row counts so a future addition/removal forces a CHANGELOG note.
assert len(_ROWS_VALIDATE) == 15, (
    f"_validate_workbook scenarios: expected 15 rows, got {len(_ROWS_VALIDATE)}"
)
assert len(_ROWS_PATCH) == 13, (
    f"_import_patch_ingredientes scenarios: expected 13 rows, got {len(_ROWS_PATCH)}"
)
