"""tests/fixtures/build_herbus_drive_fixture.py — Build a Drive-shape fixture.

Per docs/wishlist/raw/2026-09-04-real-drive-shape-import-fixture.md and
docs/operations/import-mapper.md.

Builds a single file `tests/fixtures/herbus_drive_sample.xlsx` that mirrors
what Saskia's edits-after-import look like on Google Drive — the realistic
shape that flows back into the next import:

  - Sheet names match what export_xlsx writes (Ingredientes, Recetas, Lineas,
    Productos, Ventas) so it's symmetric with the round-trip.
  - Column names match what import_xlsx reads.
  - Spanish ingredient/recipe names with unicode (acentos, ñ).
  - Decimal qty values, integer Gs. prices.
  - Some empty cells (Saskia hasn't filled price for some ingredients yet).
  - Some rows reference sub-recipes via line_kind='sub_recipe' (Masa choux,
    Crema pastelera, Masa de hojaldre) — exercises the polymorphic line
    resolution path in import_xlsx.
  - Extra columns the importer must IGNORE without crashing (categoria, sku).
  - Sales include voided + non-voided, with UTF-8 notes.

Run directly to (re)build:

    uv run python tests/fixtures/build_herbus_drive_fixture.py
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from openpyxl import Workbook
from openpyxl.utils import get_column_letter

FIXTURE_DIR = Path(__file__).parent

# These are the exact column names import_xlsx.py reads off each sheet.
INGREDIENT_HEADER = [
    "name",
    "unit",
    "stock_qty",
    "purchase_price_gs",
    "min_stock_qty",
    "notes",
]
RECIPE_HEADER = ["name", "yield_qty", "yield_unit", "notes"]
LINE_HEADER = ["recipe_name", "line_kind", "target_name", "qty", "notes"]
PRODUCT_HEADER = [
    "name",
    "portion_label",
    "sale_price_gs",
    "recipe_name",
    "notes",
]
SALE_HEADER = [
    "sold_at",
    "product_name",
    "qty",
    "unit_price_gs",
    "notes",
    "voided_at",
]

# Spanish ingredients representative of what Saskia actually edits. Names
# are taken from the HEREBUS_FoodBiz.xlsx walk in import-mapper.md §1.1.
INGREDIENTS: list[dict] = [
    # name, unit, stock_qty, purchase_price_gs (None = not yet bought), min, notes
    {
        "name": "Harina de trigo 000",
        "unit": "kg",
        "stock_qty": 25.0,
        "purchase_price_gs": 4500,
        "min_stock_qty": 5.0,
        "notes": "Panadería",
    },
    {
        "name": "Cacao en polvo",
        "unit": "g",
        "stock_qty": 500.0,
        "purchase_price_gs": 85,
        "min_stock_qty": 100.0,
        "notes": "",
    },
    {
        "name": "Polvo de hornear",
        "unit": "g",
        "stock_qty": 250.0,
        "purchase_price_gs": 60,
        "min_stock_qty": 50.0,
        "notes": "",
    },
    {
        "name": "Bicarbonato de sodio",
        "unit": "g",
        "stock_qty": 200.0,
        "purchase_price_gs": 45,
        "min_stock_qty": 50.0,
        "notes": "",
    },
    {
        "name": "Café espresso molido",
        "unit": "g",
        "stock_qty": 250.0,
        "purchase_price_gs": 320,
        "min_stock_qty": 50.0,
        "notes": "",
    },
    {
        "name": "Sal",
        "unit": "g",
        "stock_qty": 1000.0,
        "purchase_price_gs": 8,
        "min_stock_qty": 200.0,
        "notes": "",
    },
    {
        "name": "Azúcar morena",
        "unit": "g",
        "stock_qty": 2000.0,
        "purchase_price_gs": 12,
        "min_stock_qty": 500.0,
        "notes": "",
    },
    {
        "name": "Manteca",
        "unit": "kg",
        "stock_qty": 4.0,
        "purchase_price_gs": 32000,
        "min_stock_qty": 1.0,
        "notes": "",
    },
    {
        "name": "Huevos",
        "unit": "und",
        "stock_qty": 60.0,
        "purchase_price_gs": 600,
        "min_stock_qty": 24.0,
        "notes": "maple\u200b/criollos",
    },
    {
        "name": "Leche entera",
        "unit": "l",
        "stock_qty": 10.0,
        "purchase_price_gs": 6500,
        "min_stock_qty": 3.0,
        "notes": "",
    },
    {
        "name": "Esencia de vainilla",
        "unit": "ml",
        "stock_qty": 100.0,
        "purchase_price_gs": 250,
        "min_stock_qty": 30.0,
        "notes": "",
    },
    {
        "name": "Dulce de leche",
        "unit": "kg",
        "stock_qty": 3.0,
        "purchase_price_gs": 28000,
        "min_stock_qty": 1.0,
        "notes": "",
    },
    # Empty purchase_price_gs on purpose — Saskia hasn't bought yet.
    {
        "name": "Queso Paraguay",
        "unit": "kg",
        "stock_qty": 1.5,
        "purchase_price_gs": None,
        "min_stock_qty": 0.5,
        "notes": "precio pendiente",
    },
    {
        "name": "Almidón de mandioca",
        "unit": "kg",
        "stock_qty": 2.0,
        "purchase_price_gs": 8500,
        "min_stock_qty": 0.5,
        "notes": "",
    },
]

# Sub-recipes — these are ingredients in OTHER recipes (line_kind='sub_recipe').
SUB_RECIPES: list[dict] = [
    # name, yield_qty, yield_unit, notes
    {"name": "Masa choux", "yield_qty": 16.0, "yield_unit": "und", "notes": "16-18 profiteroles"},
    {
        "name": "Masa de hojaldre rápida",
        "yield_qty": 1.0,
        "yield_unit": "kg",
        "notes": "sub-receta base",
    },
    {"name": "Crema pastelera", "yield_qty": 1.0, "yield_unit": "l", "notes": "~1L rinde"},
]

# Regular recipes — top-level sellable recipes.
RECIPES: list[dict] = [
    {
        "name": "Muffin de chocolate",
        "yield_qty": 12.0,
        "yield_unit": "und",
        "notes": "Lote 12 muffins",
    },
    {"name": "Cheesecake", "yield_qty": 1.0, "yield_unit": "und", "notes": "20x20 cm"},
    {"name": "Stroopwafel", "yield_qty": 24.0, "yield_unit": "und", "notes": ""},
    {
        "name": "Chipá",
        "yield_qty": 24.0,
        "yield_unit": "und",
        "notes": "Receta tradicional paraguaya",
    },
    {"name": "Tarta de manzana", "yield_qty": 1.0, "yield_unit": "und", "notes": ""},
    {
        "name": "Profiteroles",
        "yield_qty": 12.0,
        "yield_unit": "und",
        "notes": "Usa Masa choux + Crema pastelera",
    },
    {
        "name": "Torta de hojaldre",
        "yield_qty": 1.0,
        "yield_unit": "und",
        "notes": "Usa Masa de hojaldre rápida",
    },
]

# Recipe lines — each row references a leaf ingredient or a sub-recipe by NAME.
RECIPE_LINES: list[tuple[str, str, str, float, str]] = [
    # (recipe_name, line_kind, target_name, qty, notes)
    # Muffin de chocolate
    ("Muffin de chocolate", "ingredient", "Harina de trigo 000", 333, ""),
    ("Muffin de chocolate", "ingredient", "Cacao en polvo", 117, ""),
    ("Muffin de chocolate", "ingredient", "Polvo de hornear", 5, ""),
    ("Muffin de chocolate", "ingredient", "Bicarbonato de sodio", 5, ""),
    ("Muffin de chocolate", "ingredient", "Café espresso molido", 3, ""),
    ("Muffin de chocolate", "ingredient", "Sal", 17, ""),
    ("Muffin de chocolate", "ingredient", "Azúcar morena", 458, ""),
    ("Muffin de chocolate", "ingredient", "Huevos", 3, ""),
    ("Muffin de chocolate", "ingredient", "Leche entera", 0.25, ""),
    ("Muffin de chocolate", "ingredient", "Esencia de vainilla", 5, ""),
    # Cheesecake
    ("Cheesecake", "ingredient", "Queso Paraguay", 1.0, ""),
    ("Cheesecake", "ingredient", "Azúcar morena", 250, ""),
    ("Cheesecake", "ingredient", "Huevos", 4, ""),
    ("Cheesecake", "ingredient", "Esencia de vainilla", 10, ""),
    # Stroopwafel
    ("Stroopwafel", "ingredient", "Harina de trigo 000", 500, ""),
    ("Stroopwafel", "ingredient", "Manteca", 200, ""),
    ("Stroopwafel", "ingredient", "Azúcar morena", 300, ""),
    ("Stroopwafel", "ingredient", "Huevos", 2, ""),
    # Chipá
    ("Chipá", "ingredient", "Almidón de mandioca", 0.5, ""),
    ("Chipá", "ingredient", "Queso Paraguay", 0.4, ""),
    ("Chipá", "ingredient", "Huevos", 2, ""),
    ("Chipá", "ingredient", "Manteca", 0.08, ""),
    ("Chipá", "ingredient", "Leche entera", 0.2, ""),
    ("Chipá", "ingredient", "Sal", 5, ""),
    # Tarta de manzana — uses Masa de hojaldre rápida (sub_recipe) + leaf ingredients
    ("Tarta de manzana", "sub_recipe", "Masa de hojaldre rápida", 0.5, ""),
    # Profiteroles — uses two sub_recipes
    ("Profiteroles", "sub_recipe", "Masa choux", 12, ""),
    ("Profiteroles", "sub_recipe", "Crema pastelera", 0.3, ""),
    # Torta de hojaldre — uses one sub_recipe
    ("Torta de hojaldre", "sub_recipe", "Masa de hojaldre rápida", 0.8, ""),
    # Masa choux itself is built from leaves
    ("Masa choux", "ingredient", "Manteca", 80, ""),
    ("Masa choux", "ingredient", "Harina de trigo 000", 120, ""),
    ("Masa choux", "ingredient", "Huevos", 3, ""),
    ("Masa choux", "ingredient", "Leche entera", 0.15, ""),
    # Masa de hojaldre rápida itself
    ("Masa de hojaldre rápida", "ingredient", "Harina de trigo 000", 500, ""),
    ("Masa de hojaldre rápida", "ingredient", "Manteca", 250, ""),
    ("Masa de hojaldre rápida", "ingredient", "Sal", 10, ""),
    # Crema pastelera itself
    ("Crema pastelera", "ingredient", "Leche entera", 0.5, ""),
    ("Crema pastelera", "ingredient", "Azúcar morena", 150, ""),
    ("Crema pastelera", "ingredient", "Huevos", 3, ""),
    ("Crema pastelera", "ingredient", "Esencia de vainilla", 5, ""),
]

PRODUCTS: list[dict] = [
    # name, portion_label, sale_price_gs, recipe_name, notes
    {
        "name": "Muffin de chocolate (unidad)",
        "portion_label": "1 unidad",
        "sale_price_gs": 4500,
        "recipe_name": "Muffin de chocolate",
        "notes": "popular",
    },
    {
        "name": "Docena muffins chocolate",
        "portion_label": "docena",
        "sale_price_gs": 50000,
        "recipe_name": "Muffin de chocolate",
        "notes": "encargo",
    },
    {
        "name": "Cheesecake entero",
        "portion_label": "1 unidad",
        "sale_price_gs": 120000,
        "recipe_name": "Cheesecake",
        "notes": "",
    },
    {
        "name": "Porción cheesecake",
        "portion_label": "porción",
        "sale_price_gs": 25000,
        "recipe_name": "Cheesecake",
        "notes": "",
    },
    {
        "name": "Stroopwafel (unidad)",
        "portion_label": "1 unidad",
        "sale_price_gs": 3500,
        "recipe_name": "Stroopwafel",
        "notes": "",
    },
    {
        "name": "Docena stroopwafel",
        "portion_label": "docena",
        "sale_price_gs": 38000,
        "recipe_name": "Stroopwafel",
        "notes": "",
    },
    {
        "name": "Chipá unitario",
        "portion_label": "1 unidad",
        "sale_price_gs": 3500,
        "recipe_name": "Chipá",
        "notes": "",
    },
    {
        "name": "Docena de chipá",
        "portion_label": "docena",
        "sale_price_gs": 35000,
        "recipe_name": "Chipá",
        "notes": "encargo",
    },
    {
        "name": "Porción tarta de manzana",
        "portion_label": "porción",
        "sale_price_gs": 18000,
        "recipe_name": "Tarta de manzana",
        "notes": "",
    },
    {
        "name": "Profiterol unitario",
        "portion_label": "1 unidad",
        "sale_price_gs": 6000,
        "recipe_name": "Profiteroles",
        "notes": "",
    },
    {
        "name": "Docena profiteroles",
        "portion_label": "docena",
        "sale_price_gs": 65000,
        "recipe_name": "Profiteroles",
        "notes": "",
    },
    {
        "name": "Torta de hojaldre entera",
        "portion_label": "1 unidad",
        "sale_price_gs": 95000,
        "recipe_name": "Torta de hojaldre",
        "notes": "",
    },
]

# Sales — mix of recent and older, one voided for the voided_at path.
SALES_BASE_DT = datetime(2026, 9, 1, 8, 30, 0)


def _auto_width(ws) -> None:
    for col in ws.columns:
        max_len = max(len(str(c.value or "")) for c in col)
        ws.column_dimensions[get_column_letter(col[0].column)].width = min(max_len + 2, 40)


def build(path: Path) -> None:
    """Write the Drive-shape fixture to ``path``."""
    wb = Workbook()
    wb.remove(wb.active)

    # --- Ingredientes -------------------------------------------------------
    ing = wb.create_sheet("Ingredientes")
    # Drive-shape: an extra column ("categoría") at the END that the importer
    # must ignore. We don't put it in the canonical header list because
    # import_xlsx reads by header-name not position; an unknown column simply
    # is not referenced. This mirrors what happens when Saskia adds her own
    # columns in Google Drive.
    ing.append([*INGREDIENT_HEADER, "categoría"])
    for row in INGREDIENTS:
        ing.append(
            [
                row["name"],
                row["unit"],
                row["stock_qty"],
                row["purchase_price_gs"],
                row["min_stock_qty"],
                row["notes"],
                "Panadería"
                if "muffin" in row["name"].lower() or "harina" in row["name"].lower()
                else "Otros",
            ]
        )

    # --- Recetas ------------------------------------------------------------
    rec = wb.create_sheet("Recetas")
    rec.append(RECIPE_HEADER)
    # Recetas also include the sub-recipes — sub_recipes ARE recipes.
    for r in RECIPES + SUB_RECIPES:
        rec.append([r["name"], r["yield_qty"], r["yield_unit"], r["notes"]])

    # --- Lineas -------------------------------------------------------------
    lin = wb.create_sheet("Lineas")
    lin.append(LINE_HEADER)
    for recipe_name, kind, target_name, qty, notes in RECIPE_LINES:
        lin.append([recipe_name, kind, target_name, qty, notes])

    # --- Productos ----------------------------------------------------------
    prod = wb.create_sheet("Productos")
    # Drive-shape: extra "categoría" column on Productos. Importer ignores.
    prod.append([*PRODUCT_HEADER, "categoría"])
    for p in PRODUCTS:
        prod.append(
            [
                p["name"],
                p["portion_label"],
                p["sale_price_gs"],
                p["recipe_name"],
                p["notes"],
                "Panadería",
            ]
        )

    # --- Ventas -------------------------------------------------------------
    sales = wb.create_sheet("Ventas")
    sales.append(SALE_HEADER)
    # 15 sales spread over 10 days; one voided on day 3 (the voided_at path).
    base = SALES_BASE_DT
    for i in range(15):
        # Round-robin across products; cycle every 12
        product = PRODUCTS[i % len(PRODUCTS)]
        sold_at = base + timedelta(days=i // 2, hours=i * 3 % 8)
        notes_pool = [
            "",
            "Cliente: María pidió sin sal",
            "Encargo para cumpleaños",
            "Para llevar",
            "Repetición",
            "",
        ]
        # i==7 is the voided sale.
        voided_at = ""
        if i == 7:
            voided_at = (sold_at + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S")
        sales.append(
            [
                sold_at.strftime("%Y-%m-%dT%H:%M:%S"),
                product["name"],
                1.0 if i % 4 else 2.0,
                product["sale_price_gs"],
                notes_pool[i % len(notes_pool)],
                voided_at,
            ]
        )

    # --- StockMoves ---------------------------------------------------------
    # Sheet is intentionally omitted. import_xlsx does not import StockMoves
    # (see app/services/import_xlsx.py §349 comment) so its presence would
    # be ignored, and its absence is the safer default for the fixture.

    for ws in wb.worksheets:
        _auto_width(ws)

    wb.save(path)


def build_all() -> list[Path]:
    """Build the Drive-shape fixture file. Returns list of paths created."""
    out = FIXTURE_DIR / "herbus_drive_sample.xlsx"
    build(out)
    print(f"  built {out.relative_to(FIXTURE_DIR.parent.parent)} ({out.stat().st_size:,} bytes)")
    return [out]


if __name__ == "__main__":
    print(f"Building Drive-shape fixture in {FIXTURE_DIR}")
    build_all()
    print("Done.")
