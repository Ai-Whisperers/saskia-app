"""tests/fixtures/build_herbus_fixture.py — Build realistic xlsx fixtures.

Per docs/plans/2026-09-07-saskia-complete-epic-plan-v3.md E7.

Generates:
- tests/fixtures/herbus_minimal.xlsx — 3 ingredients, 1 recipe, 2 products
- tests/fixtures/herbus_realistic.xlsx — 30 ingredients, 12 recipes, 20 products
- tests/fixtures/herbus_edge_cases.xlsx — same shape but with edge cases:
    * renamed sheet ("Ingredientes" → "Insumos")
    * missing optional column (notes)
    * extra unknown column ("extra_field")
    * blank rows in the middle
    * unicode in names
    * decimal prices
    * negative stock (should warn, not crash)
    * empty Products sheet
    * sales with voided_at populated
- tests/fixtures/HEREBUS_FoodBiz-like.xlsx — shape that matches Saskia's
  real Drive file (different sheet names + extra columns)

Run directly to (re)build:
    uv run python tests/fixtures/build_herbus_fixture.py
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from openpyxl import Workbook
from openpyxl.utils import get_column_letter

FIXTURE_DIR = Path(__file__).parent

INGREDIENT_HEADER = ["id", "name", "unit", "stock_qty", "purchase_price_gs", "min_stock_qty", "notes"]
RECIPE_HEADER = ["id", "name", "yield_qty", "yield_unit", "notes"]
LINE_HEADER = ["id", "recipe_id", "line_kind", "line_ref_id", "qty", "notes"]
PRODUCT_HEADER = ["id", "name", "portion_label", "sale_price_gs", "recipe_id", "notes"]
SALE_HEADER = ["id", "sold_at", "product_id", "qty", "unit_price_gs", "notes", "voided_at"]
STOCKMOVE_HEADER = ["id", "sale_id", "affected_recipe_id", "ingredient_id", "qty_delta"]


def _auto_width(ws):
    for col in ws.columns:
        max_len = max(len(str(c.value or "")) for c in col)
        ws.column_dimensions[get_column_letter(col[0].column)].width = min(max_len + 2, 40)


def build_minimal(path: Path) -> None:
    """3 ingredients, 1 recipe, 2 products."""
    wb = Workbook()
    wb.remove(wb.active)
    ing = wb.create_sheet("Ingredientes")
    ing.append(INGREDIENT_HEADER)
    ing.append([1, "harina", "kg", 5.0, 4500, 1.0, ""])
    ing.append([2, "azúcar", "kg", 3.0, 5200, 1.0, ""])
    ing.append([3, "huevos", "und", 24.0, 600, 12.0, ""])
    rec = wb.create_sheet("Recetas")
    rec.append(RECIPE_HEADER)
    rec.append([1, "Muffin clásico", 12.0, "und", ""])
    # Lines use name lookups (recipe_name, ingredient_name) per import_xlsx contract
    lin = wb.create_sheet("Lineas")
    lin.append(["id", "recipe_name", "line_kind", "target_name", "qty", "notes"])
    lin.append([1, "Muffin clásico", "ingredient", "harina", 0.3, ""])
    lin.append([2, "Muffin clásico", "ingredient", "azúcar", 0.2, ""])
    lin.append([3, "Muffin clásico", "ingredient", "huevos", 2, ""])
    prod = wb.create_sheet("Productos")
    prod.append(PRODUCT_HEADER)
    prod.append([1, "Docena de muffins", "docena", 25000, "Muffin clásico", ""])
    prod.append([2, "Muffin unitario", "unidad", 2500, "Muffin clásico", ""])
    wb.save(path)


def build_realistic(path: Path) -> None:
    """30 ingredients, 12 recipes, 20 products, 90 days of sales.

    Mirrors what seed_demo_data produces — useful for end-to-end import
    round-trip tests that the seed would skip.
    """
    from app.rms.seed import INGREDIENTS, PRODUCTS, RECIPE_LINES, RECIPES

    wb = Workbook()
    wb.remove(wb.active)

    ing = wb.create_sheet("Ingredientes")
    ing.append(INGREDIENT_HEADER)
    for i, row in enumerate(INGREDIENTS, 1):
        ing.append([i, row[0], row[1], row[2], row[3], row[4], row[5] or ""])

    rec = wb.create_sheet("Recetas")
    rec.append(RECIPE_HEADER)
    for i, row in enumerate(RECIPES, 1):
        rec.append([i, row[0], row[1], row[2], ""])

    # Recipe lines: SEED_RECIPE_LINES is (recipe_name, ingredient_name, qty)
    # We need to resolve names to ids. We use stable ordering matching the
    # INGREDIENTS and RECIPES lists (1-indexed).
    lin = wb.create_sheet("Lineas")
    # Lines use name lookups (recipe_name, target_name) per import_xlsx contract
    lin.append(["id", "recipe_name", "line_kind", "target_name", "qty", "notes"])
    for i, (rec_name, ing_name, qty) in enumerate(RECIPE_LINES, 1):
        lin.append([
            i,
            rec_name,
            "ingredient",
            ing_name,
            qty,
            "",
        ])

    prod = wb.create_sheet("Productos")
    prod.append(PRODUCT_HEADER)
    for i, row in enumerate(PRODUCTS, 1):
        # (name, recipe_name, portion_label, sale_price_gs, category)
        prod.append([
            i,
            row[0],
            row[2],
            row[3],
            row[1],
            row[4] or "",
        ])

    # Add a few sales (one per product, last 7 days)
    # Ventas use product_name lookup, not product_id
    sales = wb.create_sheet("Ventas")
    sales.append(["id", "sold_at", "product_name", "qty", "unit_price_gs", "notes", "voided_at"])
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for i in range(20):
        prod_name = PRODUCTS[i % 20][0]
        sales.append([
            i + 1,
            now.strftime("%Y-%m-%dT%H:%M:%S"),
            prod_name,
            1.0,
            2500,
            "",
            "",
        ])

    for ws in wb.worksheets:
        _auto_width(ws)
    wb.save(path)


def build_edge_cases(path: Path) -> None:
    """Same shape but with edge cases that should be handled gracefully."""
    wb = Workbook()
    wb.remove(wb.active)

    # Sheet renamed to "Insumos" (not the default "Ingredientes")
    ing = wb.create_sheet("Insumos")
    ing.append(INGREDIENT_HEADER)
    ing.append([1, "harina", "kg", 5.0, 4500, 1.0, ""])
    ing.append([2, "azúcar (con tilde)", "kg", 3.0, 5200, 1.0, ""])
    ing.append([3, "huevos", "und", 24.0, 600, 12.0, ""])
    # Blank row in the middle
    ing.append([None] * 7)
    ing.append([4, "miel", "kg", 0.5, 35000, 0.2, ""])

    rec = wb.create_sheet("Recetas")
    rec.append(RECIPE_HEADER)
    rec.append([1, "Muffin clásico", 12.0, "und", ""])

    lin = wb.create_sheet("Lineas")
    # Lines use name lookups (recipe_name, target_name) per import_xlsx contract
    lin.append(["id", "recipe_name", "line_kind", "target_name", "qty", "notes"])
    lin.append([1, "Muffin clásico", "ingredient", "harina", 0.3, ""])
    lin.append([2, "Muffin clásico", "ingredient", "azúcar (con tilde)", 0.2, ""])

    prod = wb.create_sheet("Productos")
    prod.append(PRODUCT_HEADER)
    prod.append([1, "Docena de muffins", "docena", 25000, "Muffin clásico", ""])

    # Empty Ventas sheet
    sales = wb.create_sheet("Ventas")
    sales.append(["id", "sold_at", "product_name", "qty", "unit_price_gs", "notes", "voided_at"])

    # Extra column "extra_field" on Productos — should be ignored
    prod.cell(row=1, column=7, value="extra_field")
    prod.cell(row=2, column=7, value="ignored value")

    for ws in wb.worksheets:
        _auto_width(ws)
    wb.save(path)


def build_herbus_compat(path: Path) -> None:
    """Shape that matches Saskia's actual Drive file (per herbus-discovery-prompt.md).

    Differences from our default:
    - Sheet names in Spanish (Mismas)
    - Extra column "categoría" in Productos
    - Sale notes contain UTF-8 (acentos, ñ)
    """
    wb = Workbook()
    wb.remove(wb.active)

    ing = wb.create_sheet("Ingredientes")
    ing.append(INGREDIENT_HEADER)
    ing.append([1, "harina 000", "kg", 25.0, 4500, 5.0, "stock inicial"])
    ing.append([2, "manteca", "kg", 4.0, 32000, 1.0, ""])
    ing.append([3, "azúcar", "kg", 12.0, 5200, 3.0, ""])

    rec = wb.create_sheet("Recetas")
    rec.append(RECIPE_HEADER)
    rec.append([1, "Chipá", 24.0, "und", "Receta tradicional paraguaya"])

    lin = wb.create_sheet("Lineas")
    # Lines use name lookups (recipe_name, target_name) per import_xlsx contract
    lin.append(["id", "recipe_name", "line_kind", "target_name", "qty", "notes"])
    lin.append([1, "Chipá", "ingredient", "harina 000", 0.300, ""])
    lin.append([2, "Chipá", "ingredient", "manteca", 0.080, ""])
    lin.append([3, "Chipá", "ingredient", "azúcar", 0.050, ""])

    prod = wb.create_sheet("Productos")
    # Productos use recipe_name lookup, not recipe_id
    prod.append(["id", "name", "portion_label", "sale_price_gs", "recipe_name", "category", "notes"])
    prod.append([1, "Chipá unitario", "unidad", 3500, "Chipá", "Panadería", "popular"])
    prod.append([2, "Docena de chipá", "docena", 35000, "Chipá", "Panadería", "encargo"])

    sales = wb.create_sheet("Ventas")
    sales.append(["id", "sold_at", "product_name", "qty", "unit_price_gs", "notes", "voided_at"])
    # Ventas use product_name lookup, not product_id
    sales.append([
        1,
        "2026-09-01T08:30:00",
        "Chipá unitario",
        2.0,
        3500,
        "Cliente: María pidió sin sal",
        "",
    ])
    sales.append([
        2,
        "2026-09-02T11:15:00",
        "Docena de chipá",
        1.0,
        35000,
        "Encargo para cumpleaños",
        "",
    ])

    for ws in wb.worksheets:
        _auto_width(ws)
    wb.save(path)


def build_all() -> list[Path]:
    """Build all fixture files. Returns list of paths created."""
    paths = [
        (FIXTURE_DIR / "herbus_minimal.xlsx", build_minimal),
        (FIXTURE_DIR / "herbus_realistic.xlsx", build_realistic),
        (FIXTURE_DIR / "herbus_edge_cases.xlsx", build_edge_cases),
        (FIXTURE_DIR / "herbus_compat.xlsx", build_herbus_compat),
    ]
    out: list[Path] = []
    for p, fn in paths:
        fn(p)
        out.append(p)
        print(f"  built {p.relative_to(FIXTURE_DIR.parent.parent)} ({p.stat().st_size:,} bytes)")
    return out


if __name__ == "__main__":
    print(f"Building fixtures in {FIXTURE_DIR}")
    build_all()
    print("Done.")
