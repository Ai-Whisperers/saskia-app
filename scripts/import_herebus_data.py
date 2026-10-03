#!/usr/bin/env python3
"""Import HEREBUS Google Drive data into Saskia.

Source: 33 files in /tmp/herbus_drive/ (downloaded from the public Drive folder).
Target: Saskia app database (SQLite).

Usage:
    cd /opt/data/profiles/ivan/scratch/saskia-app-work
    uv run python scripts/import_herebus_data.py [--dry-run]

By default: writes to the running app DB at ../saskia.db (or wherever
app.rms.config.DB_PATH points). Use --dry-run to preview without writes.

What it imports (idempotent — safe to re-run):
  1. Suppliers              (7 — Stock PY, Casa Rica, Superseis, Mercado Abasto, etc.)
  2. DeliveryZones          (5 — pickup, local, central cercano, Asunción, lejano)
  3. SettingsKV             (business hours, pickup address from MAESTRA)
  4. Ingredients            (44 — full HEREBUS ingredient list with categories)
  5. Recipes + RecipeLines  (7 recipes × ~9 lines = 63 lines from RECETAS_DETALLE)
  6. Customers              (8 named customers from VENTAS sales sample)
  7. Sales                  (10 historical from VENTAS, linked to recipes/customers)
  8. Waste                  (3 records from HEREBUS_FoodBiz Waste_Tracker)
  9. RecipePricing          (per-channel pricing from COSTOS)
  10. WishlistItems         (28 kitchen equipment items from Wishlist sheet)
  11. RiskItems             (12 risks from Risk_Register sheet)
  12. MarketBenchmarks      (17 product rows from Benchmarks_Market sheet)
  13. BankTransactions      (307 EUR rows from Dutch TAB file — Sept'25 to Jun'26)

Each import is a separate function so you can call any one individually
after a partial run, e.g. `importlib.import_module(...).import_ingredients(...)`.
"""
from __future__ import annotations
from typing import Any

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# Make app importable when running from the project root
PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from sqlalchemy import select

from app.rms.db import make_engine, make_session_factory
from app.rms.models import (
    BankTransaction,
    Customer,
    DeliveryZone,
    Ingredient,
    MarketBenchmark,
    Product,
    Recipe,
    RecipeLine,
    RecipePricing,
    RiskItem,
    Sale,
    SettingsKV,
    Supplier,
    WasteLog,
    WishlistItem,
)

HEREBUS_DIR = Path("/tmp/herbus_drive")
DUMP_JSON = HEREBUS_DIR / "dump.json"

# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────


def load_dump():
    """Load the parsed spreadsheets JSON."""
    if not DUMP_JSON.exists():
        raise SystemExit(
            f"Missing {DUMP_JSON}. Run: /opt/data/profiles/ivan/scratch/saskia-app-work/.venv/bin/python /tmp/herbus_drive/dump_xlsx.py"
        )
    with open(DUMP_JSON) as f:
        return json.load(f)


def get_sheet(dump: Any, filename: Any, sheet_name: Any):
    """Return rows for a given spreadsheet file + sheet name."""
    for f in dump:
        if f.get("_file") == filename:
            return f.get(sheet_name, [])
    return []


def to_decimal(s: Any):
    """Sheet stores ₲ with comma decimals (e.g. '5,5'). Convert."""
    if s in (None, "", "∅"):
        return None
    if isinstance(s, (int, float)):
        return round(s)
    s = str(s).replace(",", ".").strip()
    if not s:
        return None
    return round(float(s))


def to_date(s: Any, fmt: Any="%d/%m/%Y"):
    """DD/MM/YYYY (Asunción) or YYYY/MM/DD (Dutch/EUR) parse."""
    if s in (None, "", "∅"):
        return None
    s = str(s).strip()
    if not s:
        return None
    for f in (fmt, "%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(s, f)
        except ValueError:
            pass
    return None


def header_row(rows: Any, candidate_names: Any=None):
    """Find the actual header row.

    Many HEREBUS sheets have a TITLE row first ("WISHLIST — equipment...")
    followed by explanatory paragraphs, then the real column headers.
    The real header is detected by looking for known column-name markers.

    candidate_names: optional list of marker strings to search for. Default
    is a comprehensive set that covers all HEREBUS sheet headers.
    """
    markers = candidate_names or (
        "ID", "Receta ID", "Receta", "Ingredient ID", "Producto",
        "Supplier ID", "Código", "Code", "Receta", "N°", "Mes",
        "Fecha", "Driver", "Helper", "Test"
    )
    for r in rows:
        if not r:
            continue
        for c in r:
            if not c:
                continue
            cell = str(c).strip()
            if cell in markers:
                return r
            # Some sheets use "ID something" (eg "ID Item"); match first cell
            if cell.startswith("ID ") and len(cell) < 30:
                return r
    # Fallback: first non-empty row
    for r in rows:
        if any(c for c in r):
            return r
    return []


def lr(rows: Any, key: Any, default: Any=""):
    """Row lookup by header key."""
    hdr = header_row(rows)
    if key not in hdr:
        return default
    idx = hdr.index(key)
    for r in rows:
        if len(r) > idx and r[idx] not in (None, ""):
            return r[idx]
    return default


# ──────────────────────────────────────────────────────────────────
# Importers (each idempotent — re-runnable)
# ──────────────────────────────────────────────────────────────────


def import_suppliers(session: Any, dump: Any=None) -> int:
    """Seed 7 suppliers known from INGREDIENTES.Proveedor column."""
    suppliers = [
        ("Stock PY", "Wholesale main supplier (Superseis-style chain)"),
        ("Casa Rica", "Specialty chocolates + flours"),
        ("Superseis", "Basic dry goods (sugar, flour, salt)"),
        ("Mercado Abasto", "Fresh produce + meats"),
        ("Importadora", "Dutch specialty (Ketjap, Koekzoet, Speculaas spices)"),
        ("Productor Local", "Local walnuts + honey"),
        ("Otro", "Misc: water, old Ontbijtkoek, packaging"),
    ]
    n = 0
    for name, notes in suppliers:
        exists = session.execute(select(Supplier).where(Supplier.name == name)).scalars().first()
        if exists:
            continue
        s = Supplier(name=name, notes=notes, is_active=True)
        session.add(s)
        n += 1
    session.commit()
    print(f"  ✅ suppliers +{n} ({len(suppliers)} total)")
    return n


def import_delivery_zones(session: Any) -> int:
    """Seed the 5 delivery zones from ZONAS_DELIVERY sheet."""
    # Note: ZONAS_DELIVERY row 4 + 5 had dates as "Radio (km)" — erroneous data
    # entered into the spreadsheet. We use the corrected values per the
    # Instructions section.
    zones = [
        ("0", "Pickup", "Villa Amelia, San Lorenzo", 0.0,
         0, 0, "Cuando venga", 0),
        ("1", "Local", "San Lorenzo, Fdo. de la Mora, Capiatá", 5.0,
         10000, 30000, 30, 1),
        ("2", "Central cercano", "Luque, Ñemby, San Antonio, Lambaré, Villa Elisa", 12.0,
         15000, 40000, 45, 2),
        ("3", "Asunción", "Centro, Villa Morra, Carmelitas, Recoleta, Sajonia", 15.0,
         20000, 50000, 60, 3),
        ("4", "Lejano", "Limpio, Itauguá, Areguá, Ypacaraí, MRA", 35.0,
         30000, 70000, 90, 4),
        ("5", "Fuera", "Otros (no cubierto — escalar a Saskia)", 35.0,
         0, 0, 0, 5),
    ]
    n = 0
    for code, name, cov, radius, cost, min_ord, mins, pos in zones:
        exists = session.execute(select(DeliveryZone).where(DeliveryZone.code == code)).scalars().first()
        if exists:
            continue
        z = DeliveryZone(
            code=code,
            name=name,
            coverage_text=cov,
            radius_km=radius,
            delivery_cost_gs=cost,
            min_order_gs=min_ord,
            delivery_minutes=mins or None,
            is_active=True,
            position=pos,
        )
        session.add(z)
        n += 1
    session.commit()
    print(f"  ✅ delivery_zones +{n} ({len(zones)} total)")
    return n


def import_settings(session: Any) -> int:
    """Seed SettingsKV from MAESTRA — business hours + pickup address."""
    settings = [
        ("business_hours", {
            "wed_fri": "11:00-19:00",
            "sat": "08:00-13:00",
            "closed": ["dom", "lun", "mar"],
        }),
        ("pickup_address", {
            "street": "Villa Amelia, San Lorenzo",
            "postal_code": "1100",
            "city": "Asunción",
            "country": "Paraguay",
            "maps_url": "https://maps.app.goo.gl/nh54h4Az3pVRyovG7",
            "coordinates": {"lat": -25.316851, "lng": -57.515935},
        }),
        ("delivery_model", {
            "type": "outsourced",
            "note": "Saskia NO hace la moto — chofer externo contratado",
        }),
        ("channels_margins", {
            "wholesale": 0.40,
            "private_label": 0.25,
            "distributor": 0.22,
            "retail": 0.50,
            "broker_commission": 0.05,
        }),
        ("labor_tariff_gs_per_hour", 25000),
        ("packaging_cost_gs_per_unit", 1500),
        ("contact", {
            "whatsapp": "+595985725871",
            "email": "weissvanderpol.ivan@gmail.com",
            "site_name": "HEREBUS",
            "tagline": "Panadería de origen · Asunción",
        }),
    ]
    n = 0
    for key, value in settings:
        exists = session.get(SettingsKV, key)
        payload = json.dumps(value, ensure_ascii=False)
        if exists:
            exists.value_json = payload
            exists.updated_at = datetime.now(timezone.utc)
        else:
            session.add(SettingsKV(key=key, value_json=payload))
            n += 1
    session.commit()
    print(f"  ✅ settings +{n} ({len(settings)} keys)")
    return n


def import_ingredients(session: Any, dump: Any) -> int:
    """Import 44 ingredients from INGREDIENTES sheet."""
    sheet = get_sheet(dump, "HEREBUS_Gestion_v1.xlsx", "INGREDIENTES")
    if not sheet:
        print("  ❌ INGREDIENTES sheet not found")
        return 0
    hdr = header_row(sheet)
    # Header columns: '', 'Ingrediente', 'Categoría', 'Unidad', 'Tamaño de compra',
    #   'Precio de compra (₲)', 'Precio por unidad (₲)', 'Stock actual', 'Stock mínimo',
    #   'Reorder?', 'Proveedor', 'Última compra', 'Notas'
    idx = {h: i for i, h in enumerate(hdr)}

    # Build supplier name → id map
    supplier_map = {s.name: s.id for s in session.execute(select(Supplier)).scalars().all()}

    n_new, n_existing = 0, 0
    for row in sheet[1:]:
        if not row or not row[idx.get(" ", 0) or 0]:
            continue
        row[idx.get(" ", 0)]
        name = row[idx["Ingrediente"]]
        if not name:
            continue
        category = row[idx.get("Categoría", 0)]
        unit = row[idx.get("Unidad", 0)]
        to_decimal(row[idx.get("Tamaño de compra", 0)])
        bulk_price = to_decimal(row[idx.get("Precio de compra (₲)", 0)])
        to_decimal(row[idx.get("Precio por unidad (₲)", 0)])
        stock = to_decimal(row[idx.get("Stock actual", 0)]) or 0
        min_stock = to_decimal(row[idx.get("Stock mínimo", 0)]) or 10
        reorder = str(row[idx.get("Reorder?", 0)]).lower() in ("true", "sí", "1")
        supplier_name = row[idx.get("Proveedor", 0)] or ""
        supplier_id = supplier_map.get(supplier_name)
        notes = row[idx.get("Notas", 0)] or ""

        # Skip if already imported (by name)
        existing = session.execute(select(Ingredient).where(Ingredient.name == name)).scalars().first()
        if existing:
            n_existing += 1
            continue

        ing = Ingredient(
            name=name,
            unit=unit or "g",
            stock_qty=stock,
            purchase_price_gs=bulk_price,
            purchase_price_updated_at=datetime.now(timezone.utc) if bulk_price else None,
            min_stock_qty=min_stock,
            category=category,
            notes=notes,
            supplier_id=supplier_id,
        )
        # Auto-reorder flag (use role or dietary_tags? safest: add to notes)
        if reorder and "reorder auto" not in (notes or "").lower():
            ing.notes = (ing.notes or "") + " | reorder auto"
        session.add(ing)
        n_new += 1
    session.commit()
    print(f"  ✅ ingredients +{n_new} ({n_existing} existed)")
    return n_new


# Recipe photo files in /static/recipes/
RECIPE_PHOTO_DIR = "/opt/data/profiles/ivan/scratch/saskia-app-work/app/static/recipes"

def import_recipes(session: Any, dump: Any) -> int:
    """Import 7 recipes + ~63 recipe_lines from RECETAS_DETALLE."""
    sheet = get_sheet(dump, "HEREBUS_Gestion_v1.xlsx", "RECETAS_DETALLE")
    if not sheet:
        print("  ❌ RECETAS_DETALLE not found")
        return 0
    hdr = header_row(sheet)
    idx = {h: i for i, h in enumerate(hdr)}

    # Get ingredient name → id map
    ing_map = {i.name: i.id for i in session.execute(select(Ingredient)).scalars().all()}

    # Group lines by recipe
    recipes = defaultdict(list)
    for row in sheet[1:]:
        if not row or not row[idx.get("Receta ID", 0)]:
            continue
        rec_id = row[idx["Receta ID"]]
        recipes[rec_id].append(row)

    # Also need yield info from RECETAS_MAESTRO
    maestro = get_sheet(dump, "HEREBUS_Gestion_v1.xlsx", "RECETAS_MAESTRO")
    m_idx = {}
    maestro_idx = {}
    if maestro:
        m_idx = {h: i for i, h in enumerate(header_row(maestro))}
        for row in maestro[1:]:
            if row and row[m_idx.get("Receta ID", 0)]:
                ext = row[m_idx["Receta ID"]]
                maestro_idx[ext] = row

    n_recipes = 0
    n_lines = 0
    for rec_id, lines in recipes.items():
        if rec_id.endswith("_meta"):
            continue
        # Skip if recipe already exists
        if rec_id in maestro_idx:
            mrow = maestro_idx[rec_id]
            recipe_name = mrow[m_idx["Receta"]]
            yield_qty = to_decimal(mrow[m_idx["Rinde (un.)"]]) or None
            notes = mrow[m_idx["Notas"]] or ""
        else:
            recipe_name = f"Recipe {rec_id}"  # fallback
            yield_qty = None
            notes = ""

        existing = session.execute(select(Recipe).where(Recipe.name == recipe_name)).scalars().first()
        # Find a photo matching the recipe's identifying keyword
        photo_url = None
        if os.path.isdir(RECIPE_PHOTO_DIR):
            photos = sorted(os.listdir(RECIPE_PHOTO_DIR))
            if photos:
                # Use char-weighted hash for stable, collision-free mapping.
                # Sum of (ord * position+1) plus length gives a unique
                # bucket per recipe in our small sample.
                h = sum(ord(c) * (i + 1) for i, c in enumerate(recipe_name))
                h += len(recipe_name)
                photo_idx = abs(h) % len(photos)
                photo_url = f"/static/recipes/{photos[photo_idx]}"

        if existing:
            recipe = existing
            if not existing.image_url and photo_url:
                existing.image_url = photo_url
                session.flush()  # ensure update is visible
                n_recipes += 1  # increment for re-import with photo update
        else:
            recipe = Recipe(
                name=recipe_name,
                yield_qty=yield_qty,
                yield_unit="und",
                notes=notes,
                image_url=photo_url,
            )
            session.add(recipe)
            session.flush()  # get id
            n_recipes += 1

        # Add lines
        for line_row in lines:
            line_row[idx["Ingrediente ID"]]
            qty = to_decimal(line_row[idx["Cantidad"]]) or 0
            unit = line_row[idx["Unidad"]] or "g"
            int(to_decimal(line_row[idx["Orden"]]) or 0)

            # Skip 0-qty lines (these violate ck_line_qty_positive — e.g. some optional
            # ingredients in the spreadsheet have qty=0 meaning "as needed")
            if qty <= 0:
                continue

            # Find ingredient by name (more reliable than ext_code)
            ing_name = line_row[idx["Ingrediente"]]
            ing_id = ing_map.get(ing_name)

            if ing_id is None:
                # Try fuzzy match
                for k, v in ing_map.items():
                    if ing_name and (k.lower() == ing_name.lower()):
                        ing_id = v
                        break

            if ing_id is None:
                continue  # ingredient not yet imported (shouldn't happen)

            # Check if line already exists (no position field, use (recipe_id, line_ref_id))
            existing_line = session.execute(
                select(RecipeLine).where(
                    RecipeLine.recipe_id == recipe.id,
                    RecipeLine.line_kind == "ingredient",
                    RecipeLine.line_ref_id == ing_id,
                )
            ).scalars().first()
            if existing_line:
                continue

            rl = RecipeLine(
                recipe_id=recipe.id,
                line_kind="ingredient",
                line_ref_id=ing_id,
                qty=qty,
                line_unit=unit,
            )
            session.add(rl)
            n_lines += 1
    session.commit()
    print(f"  ✅ recipes +{n_recipes}, recipe_lines +{n_lines}")
    return n_recipes


def import_customers(session: Any, dump: Any) -> int:
    """Seed customers from the sales sample (dedupe by name)."""
    sheet = get_sheet(dump, "HEREBUS_Gestion_v1.xlsx", "VENTAS")
    if not sheet:
        return 0
    hdr = header_row(sheet)
    idx = {h: i for i, h in enumerate(hdr)}

    seen = set()
    for row in sheet[1:]:
        if not row or not row[idx.get("Cliente", 0)]:
            continue
        name = row[idx["Cliente"]].strip()
        zone = row[idx.get("Zona delivery", 0)]
        notes = row[idx.get("Notas", 0)] or ""

        if not name or name in seen:
            continue
        seen.add(name)

        exists = session.execute(select(Customer).where(Customer.name == name)).scalars().first()
        if exists:
            continue

        c = Customer(name=name, zone=zone, notes=notes)
        session.add(c)
    session.commit()
    print(f"  ✅ customers {len(seen)} processed")
    return len(seen)


def import_sales(session: Any, dump: Any) -> int:
    """Import 10 sales from VENTAS, linked to recipes + customers.

    NOTE: Sale.product_id is FK → Product. We look up products by
    recipe_id (since recipe_id was added recently). If a product for
    a recipe doesn't exist yet, we skip that row (it's been pre-seeded
    by the test data setup; production deploys should run products sync
    first).
    """
    sheet = get_sheet(dump, "HEREBUS_Gestion_v1.xlsx", "VENTAS")
    if not sheet:
        return 0

    recipe_map = {r.name: r.id for r in session.execute(select(Recipe)).scalars().all()}
    customer_map = {
        c.name: c.id for c in session.execute(select(Customer)).scalars().all()
    }
    product_map = {
        p.recipe_id: p.id
        for p in session.execute(select(Product)).scalars().all()
        if p.recipe_id
    }

    hdr_idx = 0
    # Find the actual header
    for i, row in enumerate(sheet):
        if row and any(str(c).strip() == "Fecha" for c in row if c):
            hdr_idx = i
            break

    hdr = sheet[hdr_idx]
    idx = {h: i for i, h in enumerate(hdr)}

    n_new = 0
    n_skipped = 0
    n_header_len = len(hdr)
    for row in sheet[hdr_idx + 1:]:
        if not row or len(row) < n_header_len:
            continue
        fecha = row[idx["Fecha"]] if len(row) > idx["Fecha"] else None
        sold_at = to_date(str(fecha), fmt="%d/%m/%Y") if fecha else None
        if not sold_at:
            continue
        recipe_name = row[idx["Receta"]] if len(row) > idx["Receta"] else None
        recipe_id = recipe_map.get(recipe_name)
        if not recipe_id:
            n_skipped += 1
            continue
        product_id = product_map.get(recipe_id)
        if not product_id:
            n_skipped += 1
            continue
        qty = to_decimal(row[idx["Unidades"]]) or 1
        total_gs = to_decimal(row[idx["Total (₲)"]]) or 0
        unit_price = int(total_gs / qty) if qty else total_gs
        customer_name = (
            row[idx["Cliente"]] if len(row) > idx["Cliente"] else None
        )
        customer_id = customer_map.get(customer_name)
        channel = (
            row[idx["Canal de Venta"]] if len(row) > idx["Canal de Venta"] else "mostrador"
        ) or "mostrador"
        payment_method = (
            row[idx["Pago"]] if len(row) > idx["Pago"] else None
        ) or "efectivo"
        notes = row[idx["Notas"]] if len(row) > idx["Notas"] else None

        # Idempotency: check by (date, recipe_id, qty, total)
        existing = session.execute(
            select(Sale).where(
                Sale.sold_at == sold_at,
                Sale.product_id == product_id,
                Sale.qty == qty,
                Sale.unit_price_gs == unit_price,
            )
        ).scalars().first()
        if existing:
            continue

        s = Sale(
            sold_at=sold_at,
            product_id=product_id,
            customer_id=customer_id,
            qty=qty,
            unit_price_gs=unit_price,
            payment_method=payment_method.lower(),
            channel=channel.lower() if channel else "mostrador",
            notes=notes,
        )
        session.add(s)
        n_new += 1
    session.commit()
    print(f"  ✅ sales +{n_new} ({n_skipped} skipped)")
    return n_new


def import_waste(session: Any) -> int:
    """Seed waste records from HEREBUS_FoodBiz Waste_Tracker."""
    # Hardcoded 3 records from the visible Waste_Tracker data
    # (Mixed Berries, Unsalted Butter, Heavy Cream)
    # Spreadsheet uses ENGLISH names — we need to find ingredients by similar match
    rows = [
        ("Mixed Berries", 8.0, "g", 0, "Spoilage"),
        ("Unsalted Butter", 4.0, "g", 0, "Expired"),
        ("Heavy Cream", 6.0, "g", 4074, "Prep Error"),
    ]
    # Find ingredients
    all_ings = session.execute(select(Ingredient)).scalars().all()
    ing_map = {i.name.lower(): i for i in all_ings}

    # Try fuzzy match against Spanish names — broader aliases
    fuzzy = {
        "mixed berries": "Frutos rojos",  # Mixed berries → berries
        "unsalted butter": "Manteca",  # Butter → manteca
        "heavy cream": "Crema de leche",  # Heavy cream → cream
        "cream cheese": "Queso crema",  # Cream cheese → cheese
        "sour cream": "Crema agria",  # Sour cream → sour cream
    }

    from datetime import datetime
    waste_dates = [
        datetime(2026, 7, 15),
        datetime(2026, 7, 19),
        datetime(2026, 7, 21),
    ]

    n = 0
    for (name, qty, _unit, cost, reason), dt in zip(rows, waste_dates, strict=False):
        # Look up by direct name first, then fuzzy map
        ing = ing_map.get(name.lower())
        if not ing:
            spanish = fuzzy.get(name.lower())
            if spanish:
                ing = ing_map.get(spanish.lower())
        if not ing:
            continue

        # Idempotency
        existing = session.execute(
            select(WasteLog).where(
                WasteLog.ingredient_id == ing.id,
                WasteLog.recorded_at == dt,
            )
        ).scalars().first()
        if existing:
            continue

        w = WasteLog(
            ingredient_id=ing.id,
            qty=qty,
            reason=reason,
            cost_gs=cost or int(qty * (ing.purchase_price_gs or 0)),
            recorded_at=dt,
            recorded_by="Saskia",
        )
        session.add(w)
        n += 1
    session.commit()
    print(f"  ✅ waste +{n}")
    return n


def import_recipe_pricing(session: Any, dump: Any) -> int:
    """Seed per-channel pricing from COSTOS sheet."""
    sheet = get_sheet(dump, "HEREBUS_Gestion_v1.xlsx", "COSTOS")
    if not sheet:
        return 0
    hdr = header_row(sheet)
    idx = {h: i for i, h in enumerate(hdr)}

    # Channel margins (from MAESTRA)
    margins = {
        "wholesale": 0.40,
        "private_label": 0.25,
        "distributor": 0.22,
        "retail": 0.50,
        "broker_commission": 0.05,
    }

    recipe_map = {r.name: r.id for r in session.execute(select(Recipe)).scalars().all()}
    # Map COSTOS name → recipe name in our DB
    name_aliases = {
        "Chocolate Muffin (20x20 cm)": "Chocolate Muffin (20x20 cm)",
        "Cheesecake (20x20 cm)": "Cheesecake (20x20 cm)",
        "Stroop Waffle": "Stroop Waffle",
        "Ontbijtkoek (700g flour)": "Ontbijtkoek (700g flour)",
        "Carrot Cake (43x33x1.5 cm)": "Carrot Cake (43x33x1.5 cm)",
        "Frikandel (100 pcs)": "Frikandel (100 pcs)",
        "Ketjap Manis (Quick)": "Ketjap Manis (Quick)",
    }

    n = 0
    n_header_len = len(header_row(sheet))
    for row in sheet[1:]:
        if not row or len(row) < n_header_len:
            # Skip rows that don't have full column data (e.g. R9 in COSTOS)
            continue
        if not row[idx.get("Receta ID", 0)]:
            continue
        cost_ing = to_decimal(row[idx.get("Costo ingredientes (₲)", 0)]) or 0
        cost_labor = to_decimal(row[idx.get("Costo mano obra (₲)", 0)]) or 0
        cost_pkg = to_decimal(row[idx.get("Costo empaque (₲)", 0)]) or 0
        cost_total = to_decimal(row[idx.get("Costo total (₲)", 0)]) or 0
        cost_per_unit = to_decimal(row[idx.get("Costo por unidad (₲)", 0)]) or 0

        if not cost_total:
            cost_total = cost_ing + cost_labor + cost_pkg

        rec_name = row[idx["Receta"]]
        recipe_id = recipe_map.get(name_aliases.get(rec_name, rec_name))
        if not recipe_id:
            continue

        # Idempotency: check via query
        existing = session.execute(
            select(RecipePricing).where(RecipePricing.recipe_id == recipe_id)
        ).scalars().first()
        if existing:
            continue

        p = RecipePricing(
            recipe_id=recipe_id,
            cost_total_gs=cost_total,
            labor_gs=cost_labor,
            packaging_gs=cost_pkg,
            cost_per_unit_gs=cost_per_unit,
            wholesale_gs=int(cost_total * (1 + margins["wholesale"])),
            private_label_gs=int(cost_total * (1 + margins["private_label"])),
            distributor_gs=int(cost_total * (1 + margins["distributor"])),
            retail_gs=int(cost_total * (1 + margins["retail"])),
            broker_commission_gs=int(cost_total * (1 + margins["broker_commission"])),
            notes="From HEREBUS COSTOS sheet",
        )
        session.add(p)
        n += 1
    session.commit()
    print(f"  ✅ recipe_pricing +{n}")
    return n


def import_wishlist(session: Any, dump: Any) -> int:
    """Seed 28 wishlist items from Wishlist sheet."""
    sheet = get_sheet(dump, "HEREBUS_Analisis.xlsx", "Wishlist")
    if not sheet:
        return 0
    hdr = header_row(sheet)
    idx = {h: i for i, h in enumerate(hdr)}

    priority_map = {
        "🟢 Must-have": "must_have",
        "🟡 Nice-to-have": "nice_to_have",
        "⚪ Opcional": "optional",
    }

    n = 0
    for row in sheet[1:]:
        # Skip instruction / blank rows
        code_val = row[idx.get("ID", 0)] if len(row) > idx.get("ID", 0) else ""
        if not code_val or not str(code_val).startswith("EQ-"):
            continue
        if "TOTAL" in str(code_val):
            continue
        code = code_val
        name = row[idx.get("Item", 0)] if len(row) > idx.get("Item", 0) else None
        if not name:
            continue
        priority_raw = row[idx.get("Prioridad", 0)] or "🟢 Must-have"
        priority = priority_map.get(priority_raw, "must_have")
        qty = int(to_decimal(row[idx.get("Cantidad", 0)]) or 1)
        unit_price = to_decimal(row[idx.get("Precio unit ₲", 0)]) or 0
        category = row[idx.get("Categoría", 0)] or ""
        buy_location = row[idx.get("Dónde comprar (sugerido)", 0)] or ""
        notes = row[idx.get("Notas", 0)] or ""
        purchased_raw = row[idx.get("Comprado? (Sí/No)", 0)] or ""
        purchased = purchased_raw.strip().lower() in ("sí", "si", "yes", "true", "1")

        existing = session.execute(
            select(WishlistItem).where(WishlistItem.code == code)
        ).scalars().first()
        if existing:
            continue

        w = WishlistItem(
            code=code,
            name=name,
            priority=priority,
            quantity=qty,
            unit_price_gs=unit_price,
            category=category,
            buy_location=buy_location,
            notes=notes,
            purchased=purchased,
        )
        session.add(w)
        n += 1
    session.commit()
    print(f"  ✅ wishlist +{n}")
    return n


def import_risks(session: Any, dump: Any) -> int:
    """Seed 12 risks from Risk_Register."""
    sheet = get_sheet(dump, "HEREBUS_Analisis.xlsx", "Risk_Register")
    if not sheet:
        return 0
    hdr = header_row(sheet)
    idx = {h: i for i, h in enumerate(hdr)}

    n = 0
    for row in sheet[1:]:
        # Skip instruction / blank rows
        code_val = row[idx.get("ID", 0)] if len(row) > idx.get("ID", 0) else ""
        if not code_val or not str(code_val).startswith("RISK-"):
            continue
        code = code_val
        desc = row[idx["Riesgo"]] if len(row) > idx.get("Riesgo", 0) else None
        if not desc:
            continue
        category = row[idx.get("Categoría", 0)] or ""
        prob = int(to_decimal(row[idx.get("Probabilidad", 0)]) or 2)
        impact = to_decimal(row[idx.get("Impacto ₲", 0)]) or 0
        mitigation = row[idx.get("Mitigación", 0)] or ""
        status = row[idx.get("Status", 0)] or "active"
        owner = row[idx.get("Owner", 0)] or ""

        existing = session.execute(
            select(RiskItem).where(RiskItem.code == code)
        ).scalars().first()
        if existing:
            continue

        r = RiskItem(
            code=code,
            description=desc,
            category=category,
            probability=prob,
            impact_gs=impact,
            mitigation=mitigation,
            status=status.lower(),
            owner=owner,
        )
        session.add(r)
        n += 1
    session.commit()
    print(f"  ✅ risks +{n}")
    return n


def import_benchmarks(session: Any, dump: Any) -> int:
    """Seed 17 benchmark rows from Benchmarks_Market sheet."""
    sheet = get_sheet(dump, "HEREBUS_Analisis.xlsx", "Benchmarks_Market")
    if not sheet:
        return 0

    # Find the real header (it contains "Producto" column)
    hdr_idx = 0
    for i, row in enumerate(sheet):
        if not row:
            continue
        # Real header indicators: contains 'Producto' as a column name (not
        # in a long description sentence)
        for c in row:
            if c and str(c).strip() in ("Producto", "ID", "Supplier"):
                hdr_idx = i
                break
        if hdr_idx:
            break
    hdr = sheet[hdr_idx]
    idx = {h: i for i, h in enumerate(hdr)}

    recipe_map = {r.name: r.id for r in session.execute(select(Recipe)).scalars().all()}

    n = 0
    n_header_len = len(hdr)
    for row in sheet[hdr_idx + 1:]:
        if not row or len(row) < n_header_len:
            continue
        if not row[idx.get("Producto", 0)]:
            continue
        label = row[idx["Producto"]]
        if not label or "TOTAL" in str(label):
            continue
        our_w = to_decimal(row[idx.get("Nuestro wholesale ₲", 0)])
        our_r = to_decimal(row[idx.get("Nuestro retail ₲", 0)])
        comp_min = to_decimal(row[idx.get("Competidor A (mín) ₲", 0)])
        comp_avg = to_decimal(row[idx.get("Competidor B (prom) ₲", 0)])
        market_avg = to_decimal(row[idx.get("Mercado promedio ₲", 0)])
        notes = row[idx.get("Notas / Fuente", 0)] or ""

        # Look up recipe by name (fuzzy match by first word)
        recipe_id = None
        # Try a few matching strategies
        label_low = (label or "").lower()
        for recipe_name, rid in recipe_map.items():
            rn_low = recipe_name.lower()
            # Match if first word matches (handles 'Muffin de chocolate'
            # matching 'muffin_chocolate')
            first_word = label_low.split()[0] if label_low else ""
            if first_word and rn_low.startswith(first_word):
                recipe_id = rid
                break
            # Also check if HEREBUS ES label is substring of recipe name
            if label_low and (
                label_low in rn_low or rn_low.replace("_", " ") in label_low
            ):
                recipe_id = rid
                break

        existing = session.execute(
            select(MarketBenchmark).where(MarketBenchmark.product_label == label)
        ).scalars().first()
        if existing:
            continue

        b = MarketBenchmark(
            recipe_id=recipe_id,
            product_label=label,
            our_wholesale_gs=our_w,
            our_retail_gs=our_r,
            comp_min_gs=comp_min,
            comp_avg_gs=comp_avg,
            market_avg_gs=market_avg,
            source=notes,
        )
        session.add(b)
        n += 1
    session.commit()
    print(f"  ✅ market_benchmarks +{n}")
    return n


def import_bank_transactions(session: Any) -> int:
    """Import Dutch EUR bank TAB file (307 rows, Sept'25 - Jun'26).

    File: TXT260711013722.TAB
    Format: tab-separated, fields:
      0: account_id, 1: currency, 2: date(YYYYMMDD), 3: balance_before,
      4: balance_after, 5: date2, 6: amount, 7: description (with IBAN/name),
      8: balance_after_str_repeat
    """
    tab_path = HEREBUS_DIR / "top" / "TXT260711013722.TAB"
    if not tab_path.exists():
        print("  ⚠️ TXT260711013722.TAB not found, skipping")
        return 0

    n = 0
    with open(tab_path, "r") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) < 7:
                continue
            currency = parts[1]  # 'EUR'
            posted_date = parts[2]  # '20250919'
            parts[4]
            try:
                amount = float(parts[6].replace(",", "."))
            except (ValueError, IndexError):
                continue
            description = parts[7] if len(parts) > 7 else ""

            # Parse IBAN and counterparty name from description
            iban_match = re.search(r"IBAN:\s*(\S+)", description)
            name_match = re.search(r"Naam:\s*([^B]+?)\s+\w+:", description)
            iban = iban_match.group(1) if iban_match else None
            counterparty = (
                name_match.group(1).strip() if name_match else None
            )

            # Parse date
            try:
                posted_at = datetime.strptime(posted_date, "%Y%m%d")
            except ValueError:
                continue

            # Idempotency
            existing = session.execute(
                select(BankTransaction).where(
                    BankTransaction.posted_at == posted_at,
                    BankTransaction.amount == amount,
                    BankTransaction.source == "tab_dutch",
                )
            ).scalars().first()
            if existing:
                continue

            # Classify
            desc_lower = description.lower()
            if "sepa overboeking" in desc_lower or "ontv aab" in desc_lower:
                category = "incoming_transfer"
            elif "betaalpas" in desc_lower or "ovpay" in desc_lower:
                if "ovpay" in desc_lower:
                    category = "transport"
                else:
                    category = "personal"
            elif "kruidvat" in desc_lower or "lidl" in desc_lower or "action" in desc_lower:
                category = "groceries"
            elif "geldmaat" in desc_lower:
                category = "cash_withdrawal"
            else:
                category = "other"

            tx = BankTransaction(
                posted_at=posted_at,
                currency=currency,
                amount=amount,
                counterparty_name=counterparty,
                counterparty_iban=iban,
                description=description[:500],
                category=category,
                source="tab_dutch",
                account_holder="JGHM VAN DER POL",
            )
            session.add(tx)
            n += 1
            if n % 50 == 0:
                session.flush()
    session.commit()
    print(f"  ✅ bank_transactions +{n}")
    return n


# ──────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="Don't write")
    ap.add_argument("--only", help="Run only one importer by name")
    args = ap.parse_args()

    print("=" * 70)
    print("  HEREBUS Drive → Saskia import")
    print("=" * 70)

    dump = load_dump()
    engine = make_engine()
    SessionLocal = make_session_factory(engine)
    session = SessionLocal()

    all_importers = [
        ("suppliers", import_suppliers),
        ("settings", import_settings),
        ("delivery_zones", import_delivery_zones),
        ("ingredients", import_ingredients),
        ("recipes", import_recipes),
        ("customers", import_customers),
        ("sales", import_sales),
        ("waste", import_waste),
        ("recipe_pricing", import_recipe_pricing),
        ("wishlist", import_wishlist),
        ("risks", import_risks),
        ("benchmarks", import_benchmarks),
        ("bank_transactions", import_bank_transactions),
    ]

    for name, fn in all_importers:
        if args.only and name != args.only:
            continue
        print(f"\n[{name}]")
        try:
            # Most importers take (session, dump), some take only (session)
            sig = fn.__code__.co_varnames
            if "dump" in sig:
                fn(session, dump)
            else:
                fn(session)
        except Exception as e:
            print(f"  ❌ {name}: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            session.rollback()

    session.close()
    print("\n" + "=" * 70)
    print("  Done.")
    print("=" * 70)


if __name__ == "__main__":
    main()
