"""tests/test_export_csv.py — CSV export tests.

Per docs/operations/2026-09-02-saskia-stack-audit.md (Change 1).

Tests cover:
- export_csv.to_dir writes 8 CSV files (one per table)
- Each CSV has the right header + rows
- Polymorphic recipe_line writes line_kind + line_ref_id (no denormalized name)
- Money columns written as raw integers (not formatted "Gs. 1.234")
- Datetime columns written as ISO strings
- Empty tables still write a header-only file (so the consumer knows the
  table was checked)
- Filename includes a shared timestamp prefix so all 8 files can be grouped
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

import pytest

from app.rms.models import (
    Ingredient,
    Product,
    Recipe,
    RecipeLine,
    Sale,
)
from app.services.export_csv import TABLE_EXPORTS, to_dir


@pytest.fixture
def sample_session(session_factory):
    """Session pre-populated with one row per table."""

    session = session_factory()
    # Use a unique name per test to avoid UNIQUE collisions
    suffix = datetime.now().strftime("%H%M%S%f")

    ingredient = Ingredient(
        name=f"Harina-{suffix}",
        unit="g",
        stock_qty=5000,
        purchase_price_gs=8500,
        min_stock_qty=1000,
    )
    recipe = Recipe(
        name=f"Torta-{suffix}",
        yield_qty=1,
        yield_unit="und",
    )
    product = Product(
        name=f"Torta Chica-{suffix}",
        portion_label="1 unidad",
        sale_price_gs=25000,
        recipe=recipe,
    )
    session.add_all([ingredient, recipe, product])
    session.flush()
    line = RecipeLine(
        recipe=recipe,
        line_kind="ingredient",
        line_ref_id=ingredient.id,
        qty=200,
    )
    sale = Sale(
        product=product,
        qty=1,
        unit_price_gs=25000,
        sold_at=datetime(2026, 9, 2, 12, 0, 0),
    )
    session.add_all([line, sale])
    session.flush()

    yield (
        session,
        {
            "ingredient": ingredient,
            "recipe": recipe,
            "product": product,
            "line": line,
            "sale": sale,
        },
    )
    session.close()


def test_export_writes_eight_files(sample_session, tmp_path: Path):
    """to_dir writes one CSV per table."""
    session, _ = sample_session
    written = to_dir(session, tmp_path)
    assert len(written) == 8
    # All files end with .csv
    assert all(p.suffix == ".csv" for p in written)
    # All files in tmp_path
    assert all(p.parent == tmp_path for p in written)


def test_export_filenames_share_timestamp(sample_session, tmp_path: Path):
    """All 8 files in one export share the same timestamp prefix."""
    session, _ = sample_session
    written = to_dir(session, tmp_path)
    # Filenames: rms-csv-YYYYMMDD-HHMMSS-<table>.csv
    timestamps = set()
    for p in written:
        parts = p.name.split("-", 4)
        assert len(parts) == 5, f"unexpected filename: {p.name}"
        ts = "-".join(parts[1:4])  # YYYYMMDD-HHMMSS
        timestamps.add(ts)
    assert len(timestamps) == 1, f"expected 1 timestamp, got {timestamps}"


def test_export_ingredient_csv(sample_session, tmp_path: Path):
    """Ingredient CSV has the right header + row."""
    session, data = sample_session
    written = to_dir(session, tmp_path)
    ingredient_csv = next(p for p in written if p.name.endswith("-ingredient.csv"))
    with ingredient_csv.open() as f:
        rows = list(csv.reader(f))
    assert rows[0] == [
        "id",
        "name",
        "unit",
        "stock_qty",
        "purchase_price_gs",
        "min_stock_qty",
        "notes",
    ]
    # Find our row (skip any from other tests sharing the session)
    ing = data["ingredient"]
    ing_row = next(r for r in rows[1:] if int(r[0]) == ing.id)
    assert ing_row[1] == ing.name
    assert ing_row[2] == "g"
    assert float(ing_row[3]) == 5000.0
    assert int(ing_row[4]) == 8500  # raw integer, not "Gs. 8.500"


def test_export_recipe_line_polymorphic(sample_session, tmp_path: Path):
    """recipe_line CSV writes line_kind + line_ref_id, no denormalized name."""
    session, data = sample_session
    written = to_dir(session, tmp_path)
    line_csv = next(p for p in written if p.name.endswith("-recipe_line.csv"))
    with line_csv.open() as f:
        rows = list(csv.reader(f))
    assert rows[0] == [
        "id",
        "recipe_id",
        "line_kind",
        "line_ref_id",
        "qty",
        "notes",
    ]
    line = data["line"]
    line_row = next(r for r in rows[1:] if int(r[0]) == line.id)
    assert line_row[2] == "ingredient"
    assert int(line_row[3]) == data["ingredient"].id
    assert float(line_row[4]) == 200.0
    # No "target_name" or denormalized name column
    assert len(line_row) == 6  # id, recipe_id, line_kind, line_ref_id, qty, notes


def test_export_sale_datetime_iso(sample_session, tmp_path: Path):
    """Sale.sold_at written as ISO string (not raw datetime repr)."""
    session, data = sample_session
    written = to_dir(session, tmp_path)
    sale_csv = next(p for p in written if p.name.endswith("-sale.csv"))
    with sale_csv.open() as f:
        rows = list(csv.reader(f))
    sale = data["sale"]
    sale_row = next(r for r in rows[1:] if int(r[0]) == sale.id)
    # ISO format: 2026-09-02T12:00:00 or similar
    assert "2026-09-02" in sale_row[1]
    assert "T" in sale_row[1]  # ISO separator
    # unit_price as raw int, not formatted
    assert int(sale_row[4]) == 25000


def test_export_empty_table_still_writes_header(session_factory, tmp_path: Path):
    """Tables with no user data still get a CSV (header + any meta rows).

    `app_meta` always has the `schema_version` row inserted by init_db(), so
    it will have 2 rows (header + 1). Other tables with no user data
    should have exactly 1 row (header only).
    """
    session = session_factory()
    written = to_dir(session, tmp_path)
    # All 8 files written
    assert len(written) == 8
    # Each file has at least the header line
    for p in written:
        with p.open() as f:
            rows = list(csv.reader(f))
        assert len(rows) >= 1, f"{p.name} has no rows"
        assert len(rows[0]) > 0, f"{p.name} has empty header"
        # app_meta has schema_version by default; other tables have just header
        if p.name.endswith("-app_meta.csv"):
            assert len(rows) >= 2, f"{p.name} should have schema_version row"
        else:
            assert len(rows) == 1, f"{p.name} should have header only, has {len(rows)} rows: {rows}"
    session.close()


def test_table_exports_listed_count():
    """The 8 tables we export are documented."""
    assert len(TABLE_EXPORTS) == 8
    table_names = {name for name, _, _ in TABLE_EXPORTS}
    assert table_names == {
        "ingredient",
        "recipe",
        "recipe_line",
        "product",
        "sale",
        "sale_stock_move",
        "import_batch",
        "app_meta",
    }
