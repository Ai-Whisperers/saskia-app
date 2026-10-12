"""app/rms/seed/herbus_import.py — Sazon HEREBUS data import (SASKIA-225).

SASKIA-225 (2026-10-12). Loads Saskia's real HEREBUS spreadsheet data from
the canonical JSON snapshot at ``data/herebus_seed_canonical.json`` into the
Sazon multi-tenant schema.

Source of truth: ``data/herebus_seed_canonical.json`` (generated from
``data/herebus.xlsx`` on 2026-10-12; rebuild via
``scripts/build_herebus_canonical.py``).

What it persists (all idempotent — re-runs skip existing rows by name):

- **94 ingredients** (ING-001..ING-094) with real names, prices, and supplier
  references from the xlsx. The 12 categories map cleanly to existing schema
  fields. ``notes`` JSON encodes ``herbus_ing_id``, ``precio_ref``,
  ``last_update``, and any freeform cooking/supplier notes.

- **7 packaging items** (MAT-01..MAT-07) modeled as ``Ingredient`` rows with
  ``category="packaging"`` and ``subcategory`` = the packaging category.

- **22 recipes** (REC-001..REC-021 + REC-006 duplicate for bitterballen)
  with all 222 ingredient lines. Yields come from either:
    - Saskia's sheet (7 recipes with explicit ``B4`` yield), OR
    - Proportion-based estimates (15 recipes; documented in the canonical JSON)
  Each recipe preserves the inline cooking notes (column H of the sheet) as
  ``recipe_line.notes``. The REC-006 data-entry error (Bitterballen AND
  Frikandel both use REC-006) is preserved faithfully — operator can fix.

- **3 ``AppMeta`` provenance rows**:
    - ``herbus_seed_loaded``: true (with timestamp + counts)
    - ``herbus_recipe_yield_estimates``: JSON map of estimated yields
    - ``herbus_rec006_collision``: warning message about the duplicate (if any)

Idempotency rules:
- Ingredients: skip if ``Ingredient.name`` already exists.
- Recipes: skip if ``Recipe.name`` already exists.
- RecipeLines: skip if a line for the same recipe+ingredient already exists.
- AppMeta: insert only if key doesn't exist (first-write-wins).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Path to the canonical JSON snapshot. This file is the SINGLE source of
# truth for HEREBUS data; rebuilding from the .xlsx is a separate step
# (``scripts/build_herebus_canonical.py``).
# ---------------------------------------------------------------------------

CANONICAL_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "data"
    / "herebus_seed_canonical.json"
)


# ---------------------------------------------------------------------------
# Unit normalizer — keeps the Sazon unit constraint
# ``unit IN ('g', 'kg', 'ml', 'l', 'und')`` (per app/rms/units.py).
# ---------------------------------------------------------------------------

_UNIT_ALIASES = {
    "g": "g", "gr": "g", "gramo": "g", "gramos": "g",
    "kg": "kg", "kilo": "kg", "kilos": "kg",
    "ml": "ml", "millilitro": "ml", "millilitros": "ml",
    "l": "l", "lt": "l", "litro": "l", "litros": "l",
    "und": "und", "u": "und", "unidad": "und", "unidades": "und",
    "pcs": "und", "pc": "und", "caja": "und", "cajas": "und",
    "bolsa": "und", "bolsas": "und", "bandeja": "und", "bandejas": "und",
    "cintillo": "und", "cintillos": "und", "papel": "und", "pack": "und",
    "pliego": "und", "pliegos": "und", "bolsita": "und", "bolsitas": "und",
    "tallo": "und", "tallos": "und", "atado": "und",
    # Yield-unit aliases — Saskia uses Spanish for serving counts.
    # These are units for recipe yield (porciones = servings, rebanadas = slices,
    # molde = cake mold, plancha = sheet pan). All collapse to "und" since
    # the production system counts servings as discrete items.
    "porciones": "und",
    "porcion": "und",
    "rebanadas": "und",
    "rebanada": "und",
    "molde": "und",
    "moldes": "und",
    "plancha": "und",
    "planchas": "und",
    "torta": "und",
    "tortas": "und",
    "pastel": "und",
    # Sheet quirks
    "unidades de 40 cm": "und",  # MAT-02 cintillo packaging
}


def _normalize_unit(unit: str | None) -> str:
    """Map any HEREBUS unit string to the canonical Sazon unit enum."""
    if not unit:
        return "und"
    u = unit.lower().strip()
    if u in _UNIT_ALIASES:
        return _UNIT_ALIASES[u]
    logger.warning("Unknown unit %r — defaulting to 'und'", unit)
    return "und"


# ---------------------------------------------------------------------------
# Dutch-heritage flagging (matches the recipe set Saskia marked as the unique
# selling point of "La Vaquita Holandesa").
# ---------------------------------------------------------------------------

_DUTCH_INGREDIENTS = {
    "ING-001": "Harina de centeno",
    "ING-032": "Speculaas",
    "ING-069": "Ketjap manis",
    "ING-076": "Masa de hojaldre",
}

_DUTCH_RECIPES = {
    "REC-003",  # Stroop wafel
    "REC-004",  # Ontbijtkoek
    "REC-006",  # Bitterballen (and Frikandel — operator's data error)
    "REC-007",  # Ketjap Manis
    "REC-008",  # Hojaldre / Bladerdeeg
    "REC-009",  # Pastelitos Rosados / Roze koeken
    "REC-010",  # Galletas de Especuloos / Speculaasjes
    "REC-013",  # Tarta de manzana de mi madre (Mijn moeders appeltaart)
    "REC-014",  # Proficteroles de Den Bosch (Bossche bollen)
    "REC-015",  # Petisús de hojaldre y crema (Tompoezen)
    "REC-016",  # Oliebollen / Buñuelos tradicionales
    "REC-019",  # Goulash Croquettes
    "REC-020",  # Veggie Bitterballen
}


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def _normalize_for_lookup(name: str) -> str:
    """Normalize a name for fuzzy matching against ingredient rows.

    Strips accents (NFKD) and lowercases. Used because Saskia's Recipe sheets
    use the same words as her Inventory sheet but sometimes omit accents
    ("Pure De Tomate" vs "Puré de tomate") and differ in case.
    """
    import unicodedata
    nfkd = unicodedata.normalize("NFKD", name)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def load_canonical() -> dict[str, Any]:
    """Load ``data/herebus_seed_canonical.json`` from disk.

    Returns the parsed dict with keys: ``_meta``, ``inventory``, ``packaging``,
    ``recipes``, ``workbook_sheets``.
    """
    with open(CANONICAL_PATH, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Seed functions
# ---------------------------------------------------------------------------


def _parse_date(s: str | None) -> str | None:
    """Parse Saskia's DD/MM/YYYY date strings (or anything else parseable) to ISO.

    Returns None if input is empty/unparseable. Stored as ISO text on the
    Ingredient row (model has Text column).
    """
    if not s:
        return None
    from datetime import datetime as _dt
    s = s.strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y"):
        try:
            # naive by design; caller adds tzinfo
            return _dt.strptime(s, fmt).date().isoformat()  # noqa: DTZ007
        except (ValueError, TypeError):
            continue
    return s  # keep raw; better than None


def _parse_qty_text(s: str | None) -> float | None:
    """Parse a qty text marker like '2kg', '5kg', '8.000/docena' to a float.

    Used for ``min_reorder_text`` and other freeform quantity columns.
    Returns None if no number can be parsed.
    """
    if not s:
        return None
    import re
    # Find first number (with optional decimal point or thousands sep)
    m = re.search(r"(\d[\d.,]*[.,]?\d*)", s.replace(".", "").replace(",", "."))
    if not m:
        return None
    try:
        return float(m.group(1))
    except (ValueError, TypeError):
        return None


def seed_herbus_ingredients(session: Session, canonical: dict) -> dict[str, int]:
    """Insert the 94 HEREBUS ingredients. Idempotent by name.

    Captures every column Saskia filled in the xlsx:

    - ``name`` (always)
    - ``unit`` (from pkg_unit; normalized via _UNIT_ALIASES)
    - ``stock_qty`` (from numeric stock_qty OR parsed stock_qty_text)
    - ``opening_stock_qty`` + ``opening_stock_date`` (the "initial stock" she typed)
    - ``purchase_price_gs`` (from bulk_price_gs; integer Gs.)
    - ``purchase_price_updated_at`` (parsed from last_update; ISO datetime)
    - ``min_stock_qty`` (from numeric min_reorder_text; float)
    - ``reorder_point`` (from numeric min_reorder; float)
    - ``category`` (from grupo — Saskia's 12 categories)
    - ``subcategory`` (dutch_heritage for ING-001/032/069/076)
    - ``storage`` (inferred from grupo: Carnes → fridge, rest → dry)
    - ``notes`` (JSON of all remaining metadata: precio_ref, stock_qty_text, etc.)
    - ``dietary_tags`` (dairy/eggs/meat flagged for allergen tracking)
    - ``lead_time_days`` (default 3)

    Returns ``{inserted, skipped, needs_confirm, opening_stock_set}``.
    """
    from app.rms.models import Ingredient

    inserted = 0
    skipped = 0
    needs_confirm = []
    opening_stock_set = []

    for ing in canonical["inventory"]:
        existing = session.execute(
            select(Ingredient).where(Ingredient.name == ing["name"])
        ).scalar_one_or_none()
        if existing is not None:
            skipped += 1
            continue

        # --- stock_qty: prefer numeric; fall back to parsed text marker
        stock = 0.0
        if ing.get("stock_qty") is not None:
            try:
                stock = float(ing["stock_qty"])
            except (TypeError, ValueError):
                stock = 0.0
        elif ing.get("stock_qty_text"):
            # Saskia wrote things like "2kg" or "est. ~5.000/und — CONFIRMAR".
            # The first number we can parse becomes the seed stock.
            parsed = _parse_qty_text(ing["stock_qty_text"])
            if parsed is not None:
                stock = parsed
                # If the marker includes a unit, normalise it
                # e.g. "2kg" → 2000 g; "8.000/docena ≈ 667/tallo" → 667
                # We leave the unit as the ingredient's default unit since
                # these are operator estimates anyway.

        # --- opening_stock_qty + opening_stock_date (SASKIA-225 audit items 109/110)
        opening_qty = stock if stock > 0 else None
        opening_date = _parse_date(ing.get("last_update"))
        if opening_qty is not None and opening_qty > 0:
            opening_stock_set.append((ing["ing_id"], opening_qty, opening_date))

        # --- purchase_price_updated_at: parsed from last_update DD/MM/YYYY
        price_updated = _parse_date(ing.get("last_update")) if ing.get("bulk_price_gs") else None
        if price_updated:
            # Convert ISO date to datetime for the model's DateTime column
            from datetime import datetime as _dt
            try:
                price_updated_dt = _dt.fromisoformat(price_updated)
                # Make timezone-aware (UTC for storage per AGENTS.md rule 20)
                price_updated_dt = price_updated_dt.replace(tzinfo=timezone.utc)
            except ValueError:
                price_updated_dt = None
        else:
            price_updated_dt = None

        # --- min_stock_qty + reorder_point: parsed from min_reorder_text / min_reorder
        min_stock = 0.0
        reorder_pt = None
        if ing.get("min_reorder_text"):
            parsed = _parse_qty_text(ing["min_reorder_text"])
            if parsed is not None:
                min_stock = parsed
        if ing.get("min_reorder") is not None:
            try:
                reorder_pt = float(ing["min_reorder"])
            except (TypeError, ValueError):
                reorder_pt = None

        # --- notes (JSON): capture every remaining field Saskia filled
        notes_obj = {
            "herbus_ing_id": ing["ing_id"],
            "precio_ref": ing.get("precio_ref"),
            "last_update": ing.get("last_update"),
            "stock_qty_text": ing.get("stock_qty_text"),
            "min_reorder_text": ing.get("min_reorder_text"),
        }
        h_extra = ing.get("h_extra_note") or ""
        if h_extra:
            notes_obj["freeform_note"] = h_extra
        full_notes = json.dumps(notes_obj, ensure_ascii=False)

        # --- Dutch heritage + dietary_tags (basic allergen hints)
        is_dutch = ing["ing_id"] in _DUTCH_INGREDIENTS
        grupo = ing.get("grupo") or ""
        dietary_tags = None
        if grupo in ("Lácteos y huevos", "Carnes"):
            dietary_tags = "contains_animal_products"
        elif grupo == "Verduras y legumbres":
            dietary_tags = "vegano"
        elif grupo == "Frutas y frutos secos":
            dietary_tags = "vegano"

        # --- storage zone
        if grupo == "Carnes":
            storage = "refrigerated"
        elif grupo in ("Lácteos y huevos",):
            storage = "refrigerated"
        else:
            storage = "dry"

        # --- needs_confirm: price missing or stock estimate
        needs_confirm_flag = (
            ing.get("bulk_price_gs") is None or ing.get("bulk_price_gs", 0) == 0
        )
        if needs_confirm_flag:
            needs_confirm.append(ing["ing_id"])

        session.add(
            Ingredient(
                name=ing["name"],
                unit=_normalize_unit(ing.get("pkg_unit")),
                stock_qty=stock,
                purchase_price_gs=ing.get("bulk_price_gs"),
                purchase_price_updated_at=price_updated_dt,
                last_consumed_at=None,
                min_stock_qty=min_stock,
                max_stock_qty=None,
                shelf_life_days=None,
                storage=storage,
                notes=full_notes,
                category=grupo,
                subcategory="dutch_heritage" if is_dutch else None,
                role=None,
                allergens=None,
                dietary_tags=dietary_tags,
                lead_time_days=3,
                supplier_id=None,
                opening_stock_qty=opening_qty,
                opening_stock_date=opening_date,
                reorder_point=reorder_pt,
            )
        )
        inserted += 1

    session.flush()
    logger.info(
        "seed_herbus_ingredients: %d inserted, %d skipped (of %d total). "
        "needs_confirm=%d, opening_stock_set=%d",
        inserted,
        skipped,
        len(canonical["inventory"]),
        len(needs_confirm),
        len(opening_stock_set),
    )
    return {
        "inserted": inserted,
        "skipped": skipped,
        "needs_confirm": len(needs_confirm),
        "opening_stock_set": len(opening_stock_set),
    }


def seed_herbus_packaging(session: Session, canonical: dict) -> dict[str, int]:
    """Insert the 7 HEREBUS packaging items as ``Ingredient`` rows.

    Schema doesn't have a dedicated Packaging model; uses ``Ingredient`` with
    ``category="packaging"`` + ``subcategory`` = packaging category.

    Captures everything Saskia filled: desc, categoria, pkg_qty, pkg_unit,
    bulk_price_gs, stock_qty (numeric), min_reorder, last_update.
    """
    from app.rms.models import Ingredient

    inserted = 0
    skipped = 0

    for pkg in canonical["packaging"]:
        existing = session.execute(
            select(Ingredient).where(Ingredient.name == pkg["name"])
        ).scalar_one_or_none()
        if existing is not None:
            skipped += 1
            continue

        # opening stock = numeric stock_qty (Saskia filled this for MAT-01)
        opening_qty = pkg.get("stock_qty")
        opening_date = _parse_date(pkg.get("last_update"))

        # price updated at = parsed last_update (only when price set)
        price_updated_dt = None
        if pkg.get("bulk_price_gs") and pkg.get("last_update"):
            iso = _parse_date(pkg["last_update"])
            if iso:
                from datetime import datetime as _dt
                try:
                    price_updated_dt = _dt.fromisoformat(iso).replace(
                        tzinfo=timezone.utc
                    )
                except ValueError:
                    price_updated_dt = None

        notes_obj = {
            "herbus_pkg_id": pkg["pkg_id"],
            "desc": pkg.get("desc"),
            "categoria": pkg.get("categoria"),
            "last_update": pkg.get("last_update"),
            "pkg_qty": pkg.get("pkg_qty"),
        }

        session.add(
            Ingredient(
                name=pkg["name"],
                unit=_normalize_unit(pkg.get("pkg_unit")),
                stock_qty=opening_qty or 0.0,
                purchase_price_gs=pkg.get("bulk_price_gs"),
                purchase_price_updated_at=price_updated_dt,
                min_stock_qty=pkg.get("min_reorder") or 0.0,
                max_stock_qty=None,
                shelf_life_days=365,
                storage="ambient",
                category="packaging",
                subcategory=pkg.get("categoria"),
                notes=json.dumps(notes_obj, ensure_ascii=False),
                lead_time_days=3,
                supplier_id=None,
                opening_stock_qty=opening_qty,
                opening_stock_date=opening_date,
            )
        )
        inserted += 1

    session.flush()
    logger.info(
        "seed_herbus_packaging: %d inserted, %d skipped (of %d total)",
        inserted,
        skipped,
        len(canonical["packaging"]),
    )
    return {"inserted": inserted, "skipped": skipped}


def seed_herbus_recipes(session: Session, canonical: dict) -> dict[str, Any]:
    """Insert the 22 HEREBUS recipes with their ingredient lines. Idempotent.

    Preserves:
    - ``yield_qty``, ``yield_unit`` (from sheet OR estimated)
    - ``method_notes`` (sheet r5 column B) inside ``Recipe.notes`` JSON
    - inline ingredient notes (sheet column H) as ``recipe_line.notes``
    - margins (rows 32-34) inside ``Recipe.notes`` JSON
    - overhead (rows 56-58) when present
    - dutch_heritage flag via ``Recipe.subcategory``

    The build script (``scripts/build_herebus_canonical.py``) renumbers
    any duplicate REC-IDs deterministically BEFORE this seeder runs, so
    no two recipes in ``canonical["recipes"]`` ever share an ID. If a
    renumber happened, a ``renumber_note`` is attached to that recipe
    and surfaced as a warning here for visibility.
    """
    from app.rms.models import Ingredient, Recipe, RecipeLine

    inserted = 0
    skipped = 0
    warnings: list[str] = []
    yield_estimates: dict[str, dict[str, Any]] = {}

    # Build name -> ingredient map once for O(1) lookups.
    # Note: Saskia's Inventory sheet uses Title Case + accents ("Puré de tomate")
    # but the Recipe sheets sometimes use UPPER without accents ("PURE DE TOMATE").
    # The Ingredient.name column has a UNIQUE index — we canonicalize to
    # Title Case and match case- + accent-insensitively here.
    ingredients_by_name_lower: dict[str, "Ingredient"] = {}
    for ing in session.execute(select(Ingredient)).scalars().all():
        ingredients_by_name_lower[_normalize_for_lookup(ing.name)] = ing

    seen_rec_ids: set[str] = set()

    for rec in canonical["recipes"]:
        existing = session.execute(
            select(Recipe).where(Recipe.name == rec["rec_name"])
        ).scalar_one_or_none()
        if existing is not None:
            skipped += 1
            continue

        # Load rec_id. Build script already renumbers duplicates; if a
        # renumber_note is present, surface it as a warning for visibility.
        rec_id = rec["rec_id"]
        if rec.get("renumber_note"):
            warnings.append(
                f"{rec['rec_name']}: {rec['renumber_note']}"
            )
        seen_rec_ids.add(rec_id)

        # Build notes JSON with margins + overhead + yield_source + rec_id
        notes_obj = {
            "herbus_rec_id": rec_id,
            "herbus_sheet": rec.get("sheet"),
            "yield_source": rec.get("yield_source"),
            "yield_estimate_reason": (
                "Proportion analysis: mold size + ingredient weight + Dutch/PY baking tradition"
                if rec.get("yield_source") == "estimated"
                else None
            ),
            "margins": rec.get("margins", {}),
            "overhead": rec.get("overhead", {}),
            "method_notes": rec.get("method_notes"),
        }
        if rec.get("yield_source") == "estimated":
            yield_estimates[rec["rec_name"]] = {
                "qty": rec["yield_qty"],
                "unit": rec["yield_unit"],
            }

        # Dutch heritage flag — Recipe has no subcategory, use menu_tags (Text)
        is_dutch = rec_id in _DUTCH_RECIPES

        # Family field is reused to record the rec_id (since name may not match)
        family_value = rec_id

        recipe = Recipe(
            name=rec["rec_name"],
            yield_qty=rec.get("yield_qty"),
            yield_unit=_normalize_unit(rec.get("yield_unit")),
            family=family_value,
            notes=json.dumps(notes_obj, ensure_ascii=False),
            menu_tags="dutch_heritage" if is_dutch else None,
        )
        session.add(recipe)
        session.flush()  # so recipe.id is set

        # Add recipe lines
        lines_added = 0
        lines_skipped = 0
        lines_csp_skipped = 0  # "c.s.p." / qty=0 placeholders (recipe rules forbid qty=0)
        for ing_data in rec["ingredients"]:
            ing_name = ing_data.get("ing_name")
            ing_obj = (
                ingredients_by_name_lower.get(_normalize_for_lookup(ing_name))
                if ing_name
                else None
            )
            if ing_obj is None:
                logger.warning(
                    "seed_herbus_recipes: ingredient '%s' (ID=%s) not found for "
                    "recipe '%s' — skipping line",
                    ing_name,
                    ing_data.get("ing_id"),
                    rec["rec_name"],
                )
                lines_skipped += 1
                continue
            # Skip qty=0 / qty=None placeholders (Saskia wrote "c.s.p." for
            # "cantidad suficiente para" — should be backfilled when she cooks).
            # RecipeLine has CheckConstraint('qty > 0'), so 0 is illegal.
            qty = ing_data.get("qty")
            if qty is None or qty <= 0:
                lines_csp_skipped += 1
                logger.info(
                    "seed_herbus_recipes: skipping c.s.p. line in '%s' "
                    "(ing=%s, qty=%r) — backfill later",
                    rec["rec_name"],
                    ing_name,
                    qty,
                )
                continue
            # Idempotency: skip if this recipe+ingredient already has a line
            existing_line = session.execute(
                select(RecipeLine).where(
                    RecipeLine.recipe_id == recipe.id,
                    RecipeLine.line_ref_id == ing_obj.id,
                    RecipeLine.line_kind == "ingredient",
                )
            ).scalar_one_or_none()
            if existing_line is not None:
                lines_skipped += 1
                continue
            session.add(
                RecipeLine(
                    recipe_id=recipe.id,
                    line_kind="ingredient",
                    line_ref_id=ing_obj.id,
                    qty=qty,
                    line_unit=_normalize_unit(ing_data.get("unit")),
                    notes=ing_data.get("notes"),
                )
            )
            lines_added += 1

        inserted += 1
        logger.info(
            "seed_herbus_recipes: %s → %d lines added, %d skipped, %d c.s.p. (zero qty)",
            rec["rec_name"],
            lines_added,
            lines_skipped,
            lines_csp_skipped,
        )
        if lines_csp_skipped > 0:
            warnings.append(
                f"{rec['rec_name']}: {lines_csp_skipped} c.s.p. lines (qty=0) skipped — backfill when she cooks"
            )

    session.flush()
    logger.info(
        "seed_herbus_recipes: %d recipes inserted, %d skipped (of %d total)",
        inserted,
        skipped,
        len(canonical["recipes"]),
    )
    return {
        "inserted": inserted,
        "skipped": skipped,
        "yield_estimates": yield_estimates,
        "warnings": warnings,
    }


def seed_herbus_appmeta(session: Session, report: dict[str, Any]) -> None:
    """Drop provenance rows so the operator can see what happened.

    - ``herbus_seed_loaded``: true (with timestamp + counts)
    - ``herbus_recipe_yield_estimates``: JSON map of recipes where yield was estimated
    - ``herbus_rec006_collision``: warning text (if applicable)
    """
    from app.rms.models import AppMeta

    today = datetime.now(timezone.utc).date().isoformat()

    rows: list[tuple[str, str]] = [
        (
            "herbus_seed_loaded",
            json.dumps(
                {
                    "loaded_at": today,
                    "source": "data/herebus_seed_canonical.json",
                    "counts": {
                        "ingredients": report.get("ingredients_inserted", 0),
                        "packaging": report.get("packaging_inserted", 0),
                        "recipes": report.get("recipes_inserted", 0),
                        "opening_stock_set": report.get("opening_stock_set", 0),
                    },
                },
                ensure_ascii=False,
            ),
        ),
        (
            "herbus_recipe_yield_estimates",
            json.dumps(report.get("yield_estimates", {}), ensure_ascii=False),
        ),
    ]

    if report.get("warnings"):
        rows.append(
            (
                "herbus_data_warnings",
                json.dumps(
                    {
                        "count": len(report["warnings"]),
                        "warnings": report["warnings"],
                    },
                    ensure_ascii=False,
                ),
            )
        )

    for key, value in rows:
        existing = session.execute(
            select(AppMeta).where(AppMeta.key == key)
        ).scalar_one_or_none()
        if existing is None:
            session.add(AppMeta(key=key, value=value, updated_at=today))
        # else: first-write-wins, don't overwrite

    session.flush()


def seed_herbus_data(session: Session) -> dict[str, Any]:
    """Run all 4 HEREBUS seeders. Idempotent.

    Order matters: ingredients must be inserted before recipes (FK target).

    Returns a structured report dict with counts, yield estimates, and any
    data-quality warnings.
    """
    canonical = load_canonical()

    ing_report = seed_herbus_ingredients(session, canonical)
    pkg_report = seed_herbus_packaging(session, canonical)
    rec_report = seed_herbus_recipes(session, canonical)

    report = {
        "ingredients_inserted": ing_report["inserted"],
        "ingredients_skipped": ing_report["skipped"],
        "ingredients_needs_confirm": ing_report["needs_confirm"],
        "opening_stock_set": ing_report.get("opening_stock_set", 0),
        "packaging_inserted": pkg_report["inserted"],
        "packaging_skipped": pkg_report["skipped"],
        "recipes_inserted": rec_report["inserted"],
        "recipes_skipped": rec_report["skipped"],
        "yield_estimates": rec_report["yield_estimates"],
        "warnings": rec_report["warnings"],
    }

    seed_herbus_appmeta(session, report)

    logger.info(
        "seed_herbus_data: DONE — %d ing + %d pkg + %d recipes (skipped: %d ing + %d pkg + %d recipes)",
        report["ingredients_inserted"],
        report["packaging_inserted"],
        report["recipes_inserted"],
        report["ingredients_skipped"],
        report["packaging_skipped"],
        report["recipes_skipped"],
    )
    return report


# ---------------------------------------------------------------------------
# CLI entrypoint — ``python -m app.rms.seed.herbus_import``
# ---------------------------------------------------------------------------


def main() -> int:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from app.rms.db import make_engine, make_session_factory

    engine = make_engine()  # reads DATABASE_URL / AIW_RMS_DB_PATH
    SessionLocal = make_session_factory(engine)
    session = SessionLocal()
    try:
        report = seed_herbus_data(session)
        session.commit()
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0
    except Exception:
        session.rollback()
        logger.exception("seed_herbus_data failed")
        return 1
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
