"""app/services/export_csv.py — write all tables as CSVs.

Per docs/operations/2026-09-02-saskia-stack-audit.md (Change 1).

Adds CSV export alongside xlsx. CSVs are diffable, restorable row-by-row,
and importable anywhere (Excel, pandas, psql \\copy). The xlsx export
remains for human-readable monthly reports.

Per-table files written:
- rms-csv-YYYYMMDD-HHMMSS-ingredient.csv
- rms-csv-YYYYMMDD-HHMMSS-recipe.csv
- rms-csv-YYYYMMDD-HHMMSS-recipe_line.csv
- rms-csv-YYYYMMDD-HHMMSS-product.csv
- rms-csv-YYYYMMDD-HHMMSS-sale.csv
- rms-csv-YYYYMMDD-HHMMSS-sale_stock_move.csv
- rms-csv-YYYYMMDD-HHMMSS-import_batch.csv
- rms-csv-YYYYMMDD-HHMMSS-app_meta.csv

Money columns are written as raw integers (Gs. integer), not formatted,
so a CSV roundtrip preserves precision.

Polymorphic recipe_line: we write line_kind + line_ref_id (the FK-like
int), NOT the denormalized name. Importer resolves the FK by name.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rms.models import (
    AppMeta,
    ImportBatch,
    Ingredient,
    Product,
    Recipe,
    RecipeLine,
    Sale,
    SaleStockMove,
)

# (filename_suffix, model_class, ordered_columns)
TABLE_EXPORTS = [
    (
        "ingredient",
        Ingredient,
        [
            "id",
            "name",
            "unit",
            "stock_qty",
            "purchase_price_gs",
            "min_stock_qty",
            "notes",
        ],
    ),
    (
        "recipe",
        Recipe,
        [
            "id",
            "name",
            "yield_qty",
            "yield_unit",
            "notes",
        ],
    ),
    (
        "recipe_line",
        RecipeLine,
        [
            "id",
            "recipe_id",
            "line_kind",
            "line_ref_id",
            "qty",
            "notes",
        ],
    ),
    (
        "product",
        Product,
        [
            "id",
            "name",
            "portion_label",
            "sale_price_gs",
            "recipe_id",
            "notes",
        ],
    ),
    (
        "sale",
        Sale,
        [
            "id",
            "sold_at",
            "product_id",
            "qty",
            "unit_price_gs",
            "notes",
            "voided_at",
        ],
    ),
    (
        "sale_stock_move",
        SaleStockMove,
        [
            "id",
            "sale_id",
            "affected_recipe_id",
            "ingredient_id",
            "qty_delta",
        ],
    ),
    (
        "import_batch",
        ImportBatch,
        [
            "id",
            "imported_at",
            "source_filename",
            "note",
            "row_counts_json",
        ],
    ),
    (
        "app_meta",
        AppMeta,
        [
            "key",
            "value",
            "updated_at",
        ],
    ),
]


def _row_for(model_obj, columns: list[str]) -> list:
    """Build a CSV row from a model instance + column list."""
    row = []
    for col in columns:
        value = getattr(model_obj, col, None)
        # Handle datetime -> ISO string for stable diffs
        if isinstance(value, datetime):
            value = value.isoformat()
        # JSON columns arrive as dicts — serialize for CSV
        if isinstance(value, dict):
            value = json.dumps(value, ensure_ascii=False)
        row.append(value)
    return row


def to_dir(session: Session, path: str | Path) -> list[Path]:
    """Export all tables as CSVs into the directory `path`.

    Filenames are prefixed with `rms-csv-<timestamp>-<table>.csv`.
    Returns a list of written paths.

    The timestamp is shared across all tables in this export so the
    files can be grouped.
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    written: list[Path] = []

    for table_name, model_cls, columns in TABLE_EXPORTS:
        file_path = path / f"rms-csv-{timestamp}-{table_name}.csv"
        with file_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            # Special handling for AppMeta which uses Text primary key
            if hasattr(model_cls, "id"):
                rows = session.scalars(select(model_cls).order_by(model_cls.id)).all()
            else:
                rows = session.scalars(select(model_cls)).all()
            for obj in rows:
                writer.writerow(_row_for(obj, columns))
        written.append(file_path)

    return written


__all__ = ["to_dir", "TABLE_EXPORTS"]
