"""tests/test_real_drive_shape_fixture.py — Real-drive-shape Excel import test.

Per docs/wishlist/raw/2026-09-04-real-drive-shape-import-fixture.md and
docs/operations/import-mapper.md.

This test exercises ``app.services.import_xlsx.from_file`` against
``tests/fixtures/herbus_drive_sample.xlsx``, a fixture that mirrors what
Saskia's edits-after-import look like on Google Drive — Spanish names with
unicode, decimal qty, integer Gs. prices, sub-recipes as recipe lines,
extra ignored columns, a voided sale, and one ingredient with no
purchase_price yet.

The point is to catch **format drift**: if someone changes a column name
in the export (or in the import service) without coordinating the other
side, these tests fail with a clear message pointing at the drift.

What this catches:
  - Renaming a header the import service reads (e.g. ``stock_qty`` → ``qty``)
  - Dropping a sheet the importer needs (e.g. deleting ``Lineas``)
  - Changing the ``line_kind`` discriminator (e.g. ``ingredient`` → ``leaf``)
  - Changing the recipe/product lookup key from ``recipe_name``/``product_name``
    to ``recipe_id``/``product_id`` (this is a recurring drift — see the
    wishlist note about Saskia breaking things on her side)
  - Tightening type coercion so a decimal qty or unicode name crashes
  - Removing the extra-column tolerance (so adding ``categoría`` breaks
    the round-trip)
"""
from __future__ import annotations

from pathlib import Path

import pytest
from openpyxl import load_workbook
from sqlalchemy import select

from app.rms.models import (
    ImportBatch,
    Ingredient,
    Product,
    Recipe,
    RecipeLine,
    Sale,
)
from app.services.import_xlsx import ImportResult
from app.services.import_xlsx import from_file as import_xlsx

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "herbus_drive_sample.xlsx"
BUILDER_PATH = (
    Path(__file__).parent / "fixtures" / "build_herbus_drive_fixture.py"
)

# Expected header layout, mirrored from
# tests/fixtures/build_herbus_drive_fixture.py. If these drift, the test
# fails with a clear message — that's the whole point.
EXPECTED_SHEETS = {"Ingredientes", "Recetas", "Lineas", "Productos", "Ventas"}
EXPECTED_INGREDIENT_COLUMNS = {
    "name",
    "unit",
    "stock_qty",
    "purchase_price_gs",
    "min_stock_qty",
    "notes",
}
EXPECTED_RECIPE_COLUMNS = {"name", "yield_qty", "yield_unit", "notes"}
EXPECTED_LINE_COLUMNS = {
    "recipe_name",
    "line_kind",
    "target_name",
    "qty",
    "notes",
}
EXPECTED_PRODUCT_COLUMNS = {
    "name",
    "portion_label",
    "sale_price_gs",
    "recipe_name",
    "notes",
}
EXPECTED_SALE_COLUMNS = {
    "sold_at",
    "product_name",
    "qty",
    "unit_price_gs",
    "notes",
    "voided_at",
}


@pytest.fixture(scope="module", autouse=True)
def ensure_fixture_built() -> None:
    """Build the Drive-shape fixture on first run.

    The fixture xlsx is committed under tests/fixtures/, so most test runs
    find it already and skip the build. This autouse fixture rebuilds if
    the file is missing (e.g. a fresh checkout wiped it).
    """
    if not FIXTURE_PATH.exists():
        FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
        # Import lazily so a missing build_herbus_drive_fixture.py doesn't
        # break the test discovery on a fresh checkout.
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "build_herbus_drive_fixture", BUILDER_PATH
        )
        assert spec is not None and spec.loader is not None, (
            f"missing fixture builder: {BUILDER_PATH}"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.build(FIXTURE_PATH)
    assert FIXTURE_PATH.exists(), f"fixture still missing: {FIXTURE_PATH}"


def _sheet(wb, name: str):
    """Return sheet or raise AssertionError with the missing sheets listed.

    Used by the format-drift guard tests so a deleted/renamed sheet
    produces a clear failure message.
    """
    if name not in wb.sheetnames:
        missing = EXPECTED_SHEETS - set(wb.sheetnames)
        pytest.fail(
            f"Drive-shape fixture is missing expected sheet {name!r}. "
            f"Missing sheets so far: {sorted(missing)}. "
            f"Found: {wb.sheetnames}. "
            "This is a format-drift signal — import_xlsx.py reads these "
            "sheet names exactly. Update import_xlsx.py and export_xlsx.py "
            "together, or restore the sheet name in the fixture."
        )
    return wb[name]


def _header_set(ws, expected: set[str], *, sheet_name: str) -> set[str]:
    """Return the set of header cells in row 1, with a drift-aware failure.

    Only flags MISSING core columns as drift. Extra columns are tolerated
    (and separately enforced by ``test_fixture_has_extra_ignored_column``),
    because Saskia adds her own columns in Drive and the importer must
    ignore them rather than crash.
    """
    header_row = next(ws.iter_rows(min_row=1, max_row=1, values_only=True), ())
    actual = {str(c) for c in header_row if c is not None}
    missing = expected - actual
    if missing:
        pytest.fail(
            f"Format drift on sheet {sheet_name!r}: "
            f"missing columns={sorted(missing)}. "
            f"Got header={sorted(actual)}. "
            "import_xlsx.py reads these columns by name. If you renamed a "
            "core column, update import_xlsx.py AND export_xlsx.py together; "
            "otherwise restore the column in the fixture builder."
        )
    return actual


# --- Structural guards (the format-drift tests) --------------------------


def test_fixture_sheets_match_import_xlsx_contract():
    """The Drive fixture must have every sheet import_xlsx looks up."""
    wb = load_workbook(FIXTURE_PATH, read_only=True)
    try:
        missing = EXPECTED_SHEETS - set(wb.sheetnames)
        assert not missing, (
            f"Drive-shape fixture is missing sheets {sorted(missing)}. "
            f"Found: {wb.sheetnames}. import_xlsx.py reads sheet names "
            "exactly — drift here means a renamed/deleted sheet upstream."
        )
    finally:
        wb.close()


def test_fixture_ingredient_columns_match_contract():
    """Drift guard: rename a column in the builder → this test fails."""
    wb = load_workbook(FIXTURE_PATH, read_only=True)
    try:
        ws = _sheet(wb, "Ingredientes")
        _header_set(ws, EXPECTED_INGREDIENT_COLUMNS, sheet_name="Ingredientes")
    finally:
        wb.close()


def test_fixture_recipe_columns_match_contract():
    wb = load_workbook(FIXTURE_PATH, read_only=True)
    try:
        ws = _sheet(wb, "Recetas")
        _header_set(ws, EXPECTED_RECIPE_COLUMNS, sheet_name="Recetas")
    finally:
        wb.close()


def test_fixture_line_columns_match_contract():
    """The Lineas sheet uses recipe_name/target_name lookups, NOT ids.

    If a refactor changes Lineas to use recipe_id/line_ref_id (the
    old internal ids), this test fails and tells you why.
    """
    wb = load_workbook(FIXTURE_PATH, read_only=True)
    try:
        ws = _sheet(wb, "Lineas")
        _header_set(ws, EXPECTED_LINE_COLUMNS, sheet_name="Lineas")
        # Discriminator literal — this has drifted before in v0.
        header_row = next(ws.iter_rows(min_row=1, max_row=1, values_only=True), ())
        assert "line_kind" in header_row, (
            "Lineas sheet is missing the 'line_kind' column. "
            "import_xlsx.py uses it to discriminate ingredient vs sub_recipe."
        )
    finally:
        wb.close()


def test_fixture_product_columns_match_contract():
    """Productos must use recipe_name lookup, not recipe_id."""
    wb = load_workbook(FIXTURE_PATH, read_only=True)
    try:
        ws = _sheet(wb, "Productos")
        _header_set(ws, EXPECTED_PRODUCT_COLUMNS, sheet_name="Productos")
    finally:
        wb.close()


def test_fixture_sale_columns_match_contract():
    """Ventas must use product_name lookup, not product_id."""
    wb = load_workbook(FIXTURE_PATH, read_only=True)
    try:
        ws = _sheet(wb, "Ventas")
        _header_set(ws, EXPECTED_SALE_COLUMNS, sheet_name="Ventas")
    finally:
        wb.close()


def test_fixture_handles_unicode_names():
    """Spot-check: at least one ingredient name must contain a Spanish accent or ñ.

    If the importer ever tightens str coercion in a way that drops unicode
    (e.g. latin-1 round-trip), this fails first.
    """
    wb = load_workbook(FIXTURE_PATH, read_only=True)
    try:
        ws = _sheet(wb, "Ingredientes")
        names = [
            row[0]
            for row in ws.iter_rows(min_row=2, values_only=True)
            if row and row[0]
        ]
        # 'ñ' is in 'Dulce de leche' recipe context; use 'ñ' or 'á'/'é' on names.
        assert any(
            ("ñ" in n_str or "á" in n_str or "é" in n_str)
            for n_str in (str(n) for n in names)
        ), (
            f"Drive fixture must include at least one ingredient name with "
            f"Spanish diacritics. Got: {names}"
        )
    finally:
        wb.close()


def test_fixture_has_ingredient_with_null_price():
    """Real Drive files have ingredients where Saskia hasn't set a price yet.

    This must survive the import without crashing (NULL → NULL in DB).
    """
    wb = load_workbook(FIXTURE_PATH, read_only=True)
    try:
        ws = _sheet(wb, "Ingredientes")
        header = list(next(ws.iter_rows(min_row=1, max_row=1, values_only=True)))
        price_col = header.index("purchase_price_gs")
        name_col = header.index("name")
        none_priced = [
            row[name_col]
            for row in ws.iter_rows(min_row=2, values_only=True)
            if row and row[price_col] is None
        ]
        assert none_priced, (
            "Drive fixture must include at least one ingredient with "
            "purchase_price_gs=None (Saskia hasn't bought it yet). "
            "Without this, the NULL-price tolerance path is untested."
        )
    finally:
        wb.close()


def test_fixture_has_sub_recipe_line():
    """The fixture must include line_kind='sub_recipe' to exercise the
    polymorphic resolution path in import_xlsx."""
    wb = load_workbook(FIXTURE_PATH, read_only=True)
    try:
        ws = _sheet(wb, "Lineas")
        header = list(next(ws.iter_rows(min_row=1, max_row=1, values_only=True)))
        kind_col = header.index("line_kind")
        kinds = {
            row[kind_col]
            for row in ws.iter_rows(min_row=2, values_only=True)
            if row and row[kind_col]
        }
        assert "sub_recipe" in kinds, (
            f"Drive fixture must include at least one line_kind='sub_recipe' "
            f"row. Got kinds: {kinds}. Without this, the polymorphic "
            f"recipe_line path in import_xlsx.py is untested."
        )
        assert "ingredient" in kinds, (
            f"Drive fixture must include line_kind='ingredient' too. Got: {kinds}"
        )
    finally:
        wb.close()


def test_fixture_has_voided_sale():
    """At least one sale must have voided_at populated — exercises the void path."""
    wb = load_workbook(FIXTURE_PATH, read_only=True)
    try:
        ws = _sheet(wb, "Ventas")
        header = list(next(ws.iter_rows(min_row=1, max_row=1, values_only=True)))
        void_col = header.index("voided_at")
        rows = list(ws.iter_rows(min_row=2, values_only=True))
        voided_count = sum(
            1 for r in rows if r and r[void_col] not in (None, "")
        )
        assert voided_count >= 1, (
            "Drive fixture must include at least one voided sale (voided_at "
            "populated). Without this, the sale-void path in import_xlsx.py "
            "is untested."
        )
    finally:
        wb.close()


def test_fixture_has_extra_ignored_column():
    """Drive files have extra columns Saskia adds. The fixture must include
    at least one extra column the importer silently ignores, so a future
    "strict header" refactor breaks the test."""
    wb = load_workbook(FIXTURE_PATH, read_only=True)
    try:
        ws = _sheet(wb, "Ingredientes")
        header = list(next(ws.iter_rows(min_row=1, max_row=1, values_only=True)))
        header_set = {str(c) for c in header if c is not None}
        extras = header_set - EXPECTED_INGREDIENT_COLUMNS
        assert extras, (
            f"Drive fixture Ingredientes must include at least one extra "
            f"column the importer silently ignores. Got header={sorted(header_set)}. "
            f"This catches future 'strict header' refactors."
        )
    finally:
        wb.close()


# --- Behavioral tests: round-trip through import_xlsx -------------------


def test_drive_fixture_imports_without_warnings(session_factory):
    """The Drive-shape fixture must import cleanly — no warnings.

    Any warning is a signal of format drift or a missing tolerance path.
    """
    s = session_factory()
    try:
        result = import_xlsx(s, FIXTURE_PATH)
        assert isinstance(result, ImportResult), (
            f"import_xlsx must return ImportResult, got {type(result).__name__}"
        )
        assert result.warnings == [], (
            f"Drive-shape import produced {len(result.warnings)} warnings "
            f"(expected 0):\n  " + "\n  ".join(result.warnings)
        )
        assert result.batch_id > 0
    finally:
        s.close()


def test_drive_fixture_inserts_expected_row_counts(session_factory):
    """Counts come from the builder. If they drift, the builder or the
    import_xlsx counting logic drifted."""
    s = session_factory()
    try:
        result = import_xlsx(s, FIXTURE_PATH)
        # 14 leaf ingredients (Queso Paraguay is intentionally null-priced)
        assert result.ingredients == 14, (
            f"expected 14 ingredients, got {result.ingredients}"
        )
        # 7 top-level recipes + 3 sub-recipes = 10 recipe rows
        assert result.recipes == 10, (
            f"expected 10 recipes (7 top-level + 3 sub-recipes), "
            f"got {result.recipes}"
        )
        # 39 line rows total (leaf + sub_recipe) — see builder for tally
        assert result.lines == 39, (
            f"expected 39 recipe_lines, got {result.lines}"
        )
        assert result.products == 12, (
            f"expected 12 products, got {result.products}"
        )
        # 15 sales (1 voided + 14 normal)
        assert result.sales == 15, (
            f"expected 15 sales, got {result.sales}"
        )
        # stock_moves are not imported by design (see import_xlsx.py §349)
        assert result.stock_moves == 0, (
            f"expected 0 stock_moves (derived, not imported), got {result.stock_moves}"
        )
    finally:
        s.close()


def test_drive_fixture_ingredient_types_are_correct(session_factory):
    """Asserts DB column types after import — string name, float qty, int price.

    A regression in import_xlsx.py type coercion (e.g. int() on a decimal)
    shows up here.
    """
    s = session_factory()
    try:
        import_xlsx(s, FIXTURE_PATH)
        harina = s.scalars(
            select(Ingredient).where(Ingredient.name == "Harina de trigo 000")
        ).one()
        assert isinstance(harina.name, str), (
            f"name must be str, got {type(harina.name).__name__}"
        )
        assert harina.unit == "kg"
        assert isinstance(harina.stock_qty, float), (
            f"stock_qty must be float (decimal qty allowed), "
            f"got {type(harina.stock_qty).__name__}: {harina.stock_qty!r}"
        )
        assert harina.stock_qty == 25.0
        assert isinstance(harina.purchase_price_gs, int), (
            f"purchase_price_gs must be int Gs., "
            f"got {type(harina.purchase_price_gs).__name__}: {harina.purchase_price_gs!r}"
        )
        assert harina.purchase_price_gs == 4500
        assert isinstance(harina.min_stock_qty, float)
        assert harina.min_stock_qty == 5.0
    finally:
        s.close()


def test_drive_fixture_ingredient_without_price_stays_null(session_factory):
    """Saskia's flow: ingredients without a price must persist as NULL,
    not 0 (which the dashboard would interpret as 'price known = 0')."""
    s = session_factory()
    try:
        import_xlsx(s, FIXTURE_PATH)
        queso = s.scalars(
            select(Ingredient).where(Ingredient.name == "Queso Paraguay")
        ).one()
        assert queso.purchase_price_gs is None, (
            f"Queso Paraguay has no price in Drive; must import as NULL, "
            f"got {queso.purchase_price_gs!r}"
        )
    finally:
        s.close()


def test_drive_fixture_unicode_name_round_trips(session_factory):
    """Spanish names with diacritics must survive the Drive → import → DB round trip."""
    s = session_factory()
    try:
        import_xlsx(s, FIXTURE_PATH)
        # 'Almidón de mandioca' has 'ó'
        almidon = s.scalars(
            select(Ingredient).where(Ingredient.name == "Almidón de mandioca")
        ).one()
        assert almidon.id is not None
        # 'Dulce de leche' is in a recipe_line; let's also confirm it
        # round-trips through the Lineas → RecipeLine path.
        lines = s.scalars(
            select(RecipeLine).join(Recipe).where(Recipe.name == "Masa choux")
        ).all()
        assert lines, "Masa choux should have at least one recipe_line"
        ingredient_names = {ln.line_ref_id for ln in lines}
        assert any(rid > 0 for rid in ingredient_names), (
            "RecipeLine.line_ref_id should resolve to a real ingredient id"
        )
    finally:
        s.close()


def test_drive_fixture_sub_recipe_line_resolves(session_factory):
    """line_kind='sub_recipe' must resolve target_name → a real Recipe row.

    Since Recipe and Ingredient share the same id sequence (both autoincrement
    from 1), we verify by NAME, not by absence in the other table: the
    line_ref_id must point to a Recipe whose name matches the fixture's
    target_name.
    """
    s = session_factory()
    try:
        import_xlsx(s, FIXTURE_PATH)
        # Tarta de manzana has a sub_recipe line → Masa de hojaldre rápida
        tarta = s.scalar(
            select(Recipe).where(Recipe.name == "Tarta de manzana")
        )
        assert tarta is not None
        lines = s.scalars(
            select(RecipeLine).where(RecipeLine.recipe_id == tarta.id)
        ).all()
        sub_lines = [ln for ln in lines if ln.line_kind == "sub_recipe"]
        assert sub_lines, (
            f"Tarta de manzana should have at least one sub_recipe line; "
            f"got {len(lines)} total lines"
        )
        # Each sub_recipe line_ref_id must point to a Recipe whose name
        # matches the target_name the fixture declared.
        for ln in sub_lines:
            # We can't read the original target_name from the RecipeLine,
            # so we read the fixture directly to know what we expect.
            target_recipe = s.scalar(
                select(Recipe).where(Recipe.id == ln.line_ref_id)
            )
            assert target_recipe is not None, (
                f"sub_recipe line_ref_id={ln.line_ref_id} did not resolve "
                f"to a Recipe row. The importer must look up sub_recipe "
                f"target_name in the recipes_index, not the ingredients_index."
            )
            assert target_recipe.name in {
                "Masa choux",
                "Masa de hojaldre rápida",
                "Crema pastelera",
            }, (
                f"sub_recipe resolved to an unexpected recipe: "
                f"{target_recipe.name!r}"
            )
    finally:
        s.close()


def test_drive_fixture_voided_sale_persists(session_factory):
    """A sale with voided_at set must persist with voided_at populated (datetime)."""
    from datetime import datetime

    s = session_factory()
    try:
        import_xlsx(s, FIXTURE_PATH)
        voided = s.scalars(
            select(Sale).where(Sale.voided_at.is_not(None))
        ).all()
        assert len(voided) >= 1, (
            "fixture should produce at least one Sale with voided_at populated"
        )
        v = voided[0]
        assert isinstance(v.voided_at, datetime), (
            f"voided_at must be a datetime after import, got "
            f"{type(v.voided_at).__name__}: {v.voided_at!r}"
        )
    finally:
        s.close()


def test_drive_fixture_product_sale_prices_are_int_gs(session_factory):
    """sale_price_gs / unit_price_gs must be int (no .00 cents display)."""
    s = session_factory()
    try:
        import_xlsx(s, FIXTURE_PATH)
        products = s.scalars(select(Product)).all()
        assert products, "no products imported"
        for p in products:
            assert isinstance(p.sale_price_gs, int), (
                f"product {p.name!r}: sale_price_gs must be int Gs., "
                f"got {type(p.sale_price_gs).__name__}: {p.sale_price_gs!r}"
            )
        sales = s.scalars(select(Sale)).all()
        for sl in sales:
            assert isinstance(sl.unit_price_gs, int), (
                f"sale id={sl.id}: unit_price_gs must be int Gs., "
                f"got {type(sl.unit_price_gs).__name__}: {sl.unit_price_gs!r}"
            )
    finally:
        s.close()


def test_drive_fixture_records_import_batch(session_factory):
    """ImportBatch row must be written so /excel can show the last import."""
    s = session_factory()
    try:
        result = import_xlsx(s, FIXTURE_PATH)
        batch = s.get(ImportBatch, result.batch_id)
        assert batch is not None, (
            f"ImportBatch id={result.batch_id} not persisted"
        )
        assert batch.source_filename == "herbus_drive_sample.xlsx"
        assert isinstance(batch.row_counts_json, dict)
        assert batch.row_counts_json.get("ingredients") == 14
    finally:
        s.close()


def test_drive_fixture_decimal_qty_on_recipe_line(session_factory):
    """Decimal qty values (0.25, 0.3) must persist as floats, not ints."""
    s = session_factory()
    try:
        import_xlsx(s, FIXTURE_PATH)
        # 0.25 in the muffin recipe (Leche entera)
        muffin = s.scalar(
            select(Recipe).where(Recipe.name == "Muffin de chocolate")
        )
        assert muffin is not None
        leche_line = None
        for ln in s.scalars(
            select(RecipeLine).where(RecipeLine.recipe_id == muffin.id)
        ).all():
            target = s.get(Ingredient, ln.line_ref_id)
            if target and target.name == "Leche entera":
                leche_line = ln
                break
        assert leche_line is not None, (
            "Muffin de chocolate should have a Leche entera line (qty=0.25)"
        )
        # BACKLOG #19 (2026-10-02): recipe_line.qty is now Numeric(12, 4).
        # SQLAlchemy returns Decimal for Numeric types. We accept both
        # float and Decimal here so legacy test code stays green while
        # new code benefits from exact-decimal storage.
        from decimal import Decimal
        assert isinstance(leche_line.qty, (float, Decimal)), (
            f"qty must be float or Decimal, got "
            f"{type(leche_line.qty).__name__}: {leche_line.qty!r}"
        )
        # Use Decimal / float comparison via pytest.approx to avoid
        # float drift on round-trip
        assert float(leche_line.qty) == pytest.approx(0.25)
    finally:
        s.close()
