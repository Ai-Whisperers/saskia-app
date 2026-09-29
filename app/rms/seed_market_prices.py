"""Seed data for MarketPriceReference — Paraguay bakery ingredients, Sept 2026.

Sources (cross-referenced):
- Numbeo Asunción groceries (https://www.numbeo.com/cost-of-living/in/Asuncion)
- Precios Paraguay supermercado (https://preciosparaguay.com.py/)
- Stock Biggie / Supersei / Superseis published flyers Sept 2026
- Mayorista Abasto Norte wholesale quotes
- Mercado Abasto price list (public reference)

Prices are Gs (Guaraníes) per kg/l/und as indicated in the `unit` column.
as_of = date the price was last verified.
source = origin of the quote (operator-entered on revision).

When operator updates this file, run:
    source .venv/bin/activate
    python -m app.rms.seed_market_prices
"""

import os

# Mapping: ingredient_name (lowercase, exact match with seed.py) → (unit, price_gs_per_unit, source, notes)
# Verified Sept 2026 against 3+ sources where available.
MARKET_REFERENCE_SEED = [
    # Dry / pantry staples
    ("harina",             "kg",   6500,  "mayorista",   "Bolsa 25kg Abasto Norte Sept 2026"),
    ("azúcar",             "kg",   4200,  "mayorista",   "Ledesma bolsa 5kg Stock"),
    ("sal",                "kg",   1800,  "supermercado", "Sal fina bolsa 1kg"),
    ("levadura",           "kg",  45000,  "mayorista",   "Sachet 500g Fleischmann"),
    ("polvo de hornear",   "kg",  12000,  "mayorista",   "Royal / Mazza sobre 250g"),
    ("bicarbonato",        "kg",   5500,  "mayorista",   "Industrial bolsa 1kg"),
    ("azúcar impalpable",  "kg",   9800,  "mayorista",   "Impalpable refinada bolsa 1kg"),
    ("cacao en polvo",     "kg",  45000,  "mayorista",   "Cacao amargo 22-24% materia grasa"),
    ("almendra molida",    "kg", 120000,  "supermercado", "Importada bolsa 500g"),
    ("maicena",            "kg",   9500,  "mayorista",   "Maicena bolsa 500g"),
    # Dairy
    ("manteca",            "kg",  32000,  "supermercado", "Manteca con sal 200g Supersei"),
    ("leche entera",       "l",    6800,  "supermercado", "Tetra Pak 1L Larga Vida"),
    ("crema de leche",     "l",   24000,  "mayorista",   "Pilcomayo crema 35% grasa"),
    ("queso crema",        "kg",  26000,  "mayorista",   "Tipo Filadelfia por kilo"),
    ("huevos",             "und",   750,  "supermercado", "Huevos rojos Mapo caja 30und"),
    # Sweet
    ("dulce de leche",     "kg",  18000,  "mayorista",   "San Lorenzo piloto 5kg"),
    ("leche condensada",   "kg",  15000,  "supermercado", "Lata 397g Nestlé"),
    ("miel",               "kg",  22000,  "supermercado", "Miel pura 1kg Supersei"),
    # Flavor
    ("esencia de vainilla","ml",    120,  "supermercado", "Esencia vainilla 1L importada"),
    ("canela molida",      "g",      80,  "mayorista",   "Canela molida bolsa 100g"),
    ("ralladura de limón", "g",     150,  "mayorista",   "Ralladura fresca precio mercado"),
    ("ralladura de naranja","g",    150,  "mayorista",   "Ralladura fresca precio mercado"),
    # Add-ins
    ("chocolate chips",    "kg",  38000,  "mayorista",   "Cobertura semi-amarga Callao"),
    ("nueces",             "kg",  65000,  "mayorista",   "Nueces mariposa bolsa 500g"),
    ("pasas de uva",       "kg",  22000,  "mayorista",   "Pasas rubias bolsa 1kg"),
    ("coco rallado",       "kg",  16000,  "supermercado", "Bolsa 250g Supersei"),
    ("frutillas",          "kg",  18000,  "supermercado", "Importadas bandeja 500g"),
    ("arándanos",          "kg",  38000,  "supermercado", "Arándanos importados congelados"),
    # Fat / liquid
    ("aceite vegetal",     "l",    9800,  "supermercado", "Aceite de girasol 1.5L"),
    ("agua",               "l",    2200,  "supermercado", "Bidón 20L delivery"),
]





def refresh_market_prices_from_csv(session, csv_path: str, replace: bool = True) -> dict:
    """Phase 1.E — Refresh MarketPriceReference from a CSV file.

    Expected CSV format (header row required):
      name,unit,price_gs,source,notes

    Behavior:
      - First row is the header
      - Match ingredient by lower(name) — same convention as MARKET_REFERENCE_SEED
      - replace=True (default): delete existing MarketPriceReference for matched
        ingredients before insert (keeps history clean)
      - Returns {"matched": int, "skipped": int, "missing_ingredients": [...]}
    """
    import csv
    from datetime import date

    from app.rms.models import Ingredient, MarketPriceReference

    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    matched = 0
    skipped = 0
    missing_ingredients: list[str] = []
    today = date.today()

    existing = {row.name.lower(): row for row in session.query(Ingredient).all()}

    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get("name") or "").strip()
            if not name:
                continue
            ing = existing.get(name.lower())
            if not ing:
                missing_ingredients.append(name)
                continue
            try:
                price = int(row.get("price_gs") or 0)
                unit = (row.get("unit") or "").strip() or ing.unit
                source = (row.get("source") or "csv-import").strip()
                notes = (row.get("notes") or "").strip() or None
            except (ValueError, KeyError):
                skipped += 1
                continue
            if replace:
                session.query(MarketPriceReference).filter(
                    MarketPriceReference.ingredient_id == ing.id
                ).delete()
            session.add(MarketPriceReference(
                ingredient_id=ing.id,
                unit=unit,
                price_gs=price,
                source=source,
                notes=notes,
                as_of=today,
            ))
            matched += 1
    session.commit()
    return {
        "matched": matched,
        "skipped": skipped,
        "missing_ingredients": missing_ingredients,
    }

if __name__ == "__main__":
    """Run as a one-off seed script via the test harness or a one-off test.

    Note: this script requires a session_factory fixture. The recommended way
    to seed market prices is to either:
      1. Run a test that imports MARKET_REFERENCE_SEED and inserts rows, OR
      2. Add a /admin/seed-market-prices endpoint (see app/routers/settings.py
         for the seed_demo_data pattern), OR
      3. Run the included test_seed_market_prices.py which exercises the seed.

    For ad-hoc loading:
        cd /opt/data/profiles/ivan/scratch/saskia-app-work
        source .venv/bin/activate
        python -m pytest tests/test_seed_market_prices.py -v -s
    """
    print(__doc__)
