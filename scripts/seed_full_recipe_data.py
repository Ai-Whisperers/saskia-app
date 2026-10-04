#!/usr/bin/env python3
"""One-shot seed pass for the live Saskia RMS DB.

Fixes four production-visible gaps discovered in 2026-09-29 session:

  1. recipe.instructions column was missing from the live DB (ORM had it,
     DB didn't, so every Recipe SELECT crashed and /recetas/<id> rendered
     empty). Solved by migration _057_recipe_instructions.

  2. recipe.instructions was NULL for every recipe. Seeded with realistic
     Spanish-voseo JSON phases for the 19 clean recipes (recipe 13 has
     43 contaminated lines from an old import; left flagged).

  3. ingredient.allergens was NULL for many catalog rows. Backfilled
     using a name-keyed map (Spanish name → allergen vocabulary).

  4. tag_link had rows for products but not for recipes or ingredients,
     so the derived_tags derivation returned an empty intersection and
     every dietary tag rendered as vacuously OK. Backfilled from the
     recipe/ingredient columns.

The script is idempotent — every operation is an UPDATE or
INSERT-or-skip via existing-row checks, so re-running it is safe.

Run with::

    AIW_SASKIA_DB_PATH=/opt/data/.local/share/AIW-Saskia/rms.sqlite \\
        ./.venv/bin/python scripts/seed_full_recipe_data.py
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

# Allow running from project root without installing the package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.rms.db import (
    init_db,
    make_engine,
    make_session_factory,
    schema_version,
)
from app.rms.models import Ingredient, Recipe, TagLink
from app.rms.recipe_intel import (
    classify_recipe,
    infer_difficulty,
    infer_recipe_family,
    recipe_ingredient_count,
)
from app.rms.tags import ensure_tag

# ---------------------------------------------------------------------------
# 1. Recipe instructions seed (19 clean recipes)
# ---------------------------------------------------------------------------

# Recipe 13 is contaminated (43 lines mixing every recipe's ingredients
# from an old import) — explicitly skipped.
_CONTAMINATED_NAMES = {"1.0", "1", "RECETA", "test"}


_RECIPE_INSTRUCTIONS: dict[str, list[dict]] = {
    "appeltaart": [
        {
            "phase": "Sub-receta",
            "title": "Relleno de manzana",
            "steps": [
                "Pela y fileteá las manzanas en láminas finas.",
                "Mezclá con azúcar, canela y unas gotas de limón.",
                "Reservá 15 minutos para que largue jugo.",
            ],
        },
        {
            "phase": "Base",
            "title": "Masa brisée",
            "steps": [
                "Mezclá la harina con la manteca fría hasta formar un arenado.",
                "Agregá el azúcar y los huevos; uní sin trabajar de más.",
                "Reservá en heladera 30 minutos envuelta en film.",
            ],
        },
        {
            "phase": "Ensamblaje",
            "title": "Tarta de manzanas",
            "steps": [
                "Estirá la masa y forrá un molde enmantecado.",
                "Disponé las láminas de manzana en forma concéntrica.",
                "Cubrí con tiras de masa formando un enrejado.",
                "Horneá a 200 °C durante 35 a 40 minutos hasta dorar.",
            ],
        },
    ],
    "tarta de manzana": [
        {
            "phase": "Base",
            "title": "Masa",
            "steps": [
                "Tamá harina, azúcar y manteca hasta arenar.",
                "Sumá huevo y agua helada; uní sin amasar.",
                "Reposá 20 minutos en la heladera.",
            ],
        },
        {
            "phase": "Relleno",
            "title": "Manzanas acarameladas",
            "steps": [
                "Pelá y cortá las manzanas en gajos finos.",
                "Caramelizalas con azúcar y canela en una sartén.",
            ],
        },
        {
            "phase": "Horneado",
            "title": "Ensamblaje final",
            "steps": [
                "Estirá la masa, colocá el relleno y cerrá con un enrejado.",
                "Horneá a 180 °C durante 40 minutos.",
            ],
        },
    ],
    "brownie de chocolate": [
        {
            "phase": "Preparación",
            "title": "Base de chocolate",
            "steps": [
                "Derretí el chocolate con la manteca a baño María.",
                "Batí los huevos con el azúcar hasta punto cinta.",
            ],
        },
        {
            "phase": "Mezcla",
            "title": "Incorporación",
            "steps": [
                "Sumá el chocolate tibio a los huevos en forma envolvente.",
                "Incorporá harina y nueces picadas con movimientos suaves.",
            ],
        },
        {
            "phase": "Horneado",
            "title": "Cocción",
            "steps": [
                "Volcá en molde enmantecado y enharinado.",
                "Horneá a 170 °C durante 25 minutos (centro húmedo).",
            ],
        },
    ],
    "pan de banana": [
        {
            "phase": "Preparación",
            "title": "Puré de banana",
            "steps": [
                "Pisá las bananas maduras con un tenedor.",
                "Sumá el azúcar y los huevos; batí hasta integrar.",
            ],
        },
        {
            "phase": "Mezcla",
            "title": "Incorporación",
            "steps": [
                "Tamizá harina con polvo de hornear y canela.",
                "Alterná secos y manteca derretida con la mezcla de banana.",
            ],
        },
        {
            "phase": "Horneado",
            "title": "Cocción",
            "steps": [
                "Volcá en molde enmantecado.",
                "Horneá a 180 °C durante 50 minutos o hasta que al pinchar salga limpio.",
            ],
        },
    ],
    "cheesecake": [
        {
            "phase": "Base",
            "title": "Costra de galleta",
            "steps": [
                "Triturá las galletas y mezclá con manteca derretida.",
                "Presioná en el fondo de un molde desmontable.",
            ],
        },
        {
            "phase": "Relleno",
            "title": "Crema de queso",
            "steps": [
                "Batí el queso crema con azúcar y huevos.",
                "Sumá crema de leche y esencia de vainilla.",
            ],
        },
        {
            "phase": "Cocción",
            "title": "Horneado a baño María",
            "steps": [
                "Verté sobre la base y horneá a 150 °C a baño María durante 60 minutos.",
                "Enfriá en el horno apagado para evitar grietas.",
            ],
        },
    ],
    "galletas de avena": [
        {
            "phase": "Mezcla",
            "title": "Masa de avena",
            "steps": [
                "Batí manteca con azúcar hasta cremoso.",
                "Sumá huevo y esencia de vainilla.",
                "Incorporá avena, harina y polvo de hornear.",
            ],
        },
        {
            "phase": "Formado",
            "title": "Porcionado",
            "steps": [
                "Formá bolitas y disponé en bandeja con separación.",
                "Aplastá levemente con el dorso de una cuchara.",
            ],
        },
        {
            "phase": "Horneado",
            "title": "Cocción",
            "steps": [
                "Horneá a 180 °C durante 12 minutos hasta dorar.",
            ],
        },
    ],
    "galletas de chocolate": [
        {
            "phase": "Mezcla",
            "title": "Masa",
            "steps": [
                "Batí manteca con azúcar hasta cremoso.",
                "Sumá huevo y esencia de vainilla.",
                "Tamizá harina con cocoa y polvo de hornear; incorporá.",
                "Sumá chips de chocolate.",
            ],
        },
        {
            "phase": "Formado",
            "title": "Porcionado",
            "steps": [
                "Formá bolitas y disponé en bandeja enmantecada.",
            ],
        },
        {
            "phase": "Horneado",
            "title": "Cocción",
            "steps": [
                "Horneá a 180 °C durante 12 minutos.",
                "Enfriá sobre rejilla.",
            ],
        },
    ],
    "empanada de carne": [
        {
            "phase": "Relleno",
            "title": "Picadillo",
            "steps": [
                "Rehogá cebolla, ajo y pimiento.",
                "Sumá la carne picada; cociná hasta dorar.",
                "Agregá comino, pimentón y un toque de vinagre.",
                "Dejá enfriar antes de armar.",
            ],
        },
        {
            "phase": "Armado",
            "title": "Repulgue",
            "steps": [
                "Estirá la masa y cortá círculos de 10 cm.",
                "Rellená, cerrá en media luna y repulgá con un tenedor.",
            ],
        },
        {
            "phase": "Cocción",
            "title": "Horneado",
            "steps": [
                "Horneá a 200 °C durante 20 minutos hasta dorar.",
            ],
        },
    ],
    "budín de pan": [
        {
            "phase": "Preparación",
            "title": "Mezcla base",
            "steps": [
                "Cortá el pan en rebanadas y remojá en leche.",
                "Batí huevos con azúcar y esencia de vainilla.",
                "Sumá el pan remojado y procesá hasta homogeneizar.",
            ],
        },
        {
            "phase": "Cocción",
            "title": "Horneado a baño María",
            "steps": [
                "Sumá pasas de uva si lo deseás.",
                "Verté en molde enmantecado y caramelizado.",
                "Horneá a 170 °C a baño María durante 50 minutos.",
            ],
        },
    ],
    "crêpes": [
        {
            "phase": "Mezcla",
            "title": "Masa",
            "steps": [
                "Licuá huevos, leche, harina, manteca derretida y sal.",
                "Reposá la masa 30 minutos en la heladera.",
            ],
        },
        {
            "phase": "Cocción",
            "title": "Sellado",
            "steps": [
                "Calentá una sartén antiadherente enmantecada.",
                "Verté una porción fina y cociná 1 minuto por lado.",
            ],
        },
        {
            "phase": "Presentación",
            "title": "Servicio",
            "steps": [
                "Rellená al gusto: dulce de leche, frutas o queso.",
            ],
        },
    ],
    "tarta de chocolate": [
        {
            "phase": "Base",
            "title": "Masa",
            "steps": [
                "Tamá harina, cocoa y polvo de hornear.",
                "Batí manteca con azúcar; sumá huevo.",
                "Uní secos y húmedos sin amasar.",
            ],
        },
        {
            "phase": "Relleno",
            "title": "Ganache",
            "steps": [
                "Calentá crema y verté sobre el chocolate picado.",
                "Dejá reposar 2 minutos y emulsioná hasta brilloso.",
            ],
        },
        {
            "phase": "Ensamblaje",
            "title": "Armado y cocción",
            "steps": [
                "Forrá el molde con la masa, precociná 10 minutos.",
                "Verté el ganache y horneá 5 minutos más.",
            ],
        },
    ],
    "muffin de chocolate": [
        {
            "phase": "Húmedos",
            "title": "Mezcla líquida",
            "steps": [
                "Batí huevos con aceite y buttermilk (o leche + limón).",
                "Sumá esencia de vainilla.",
            ],
        },
        {
            "phase": "Secos",
            "title": "Mezcla seca",
            "steps": [
                "Tamizá harina, cocoa, polvo de hornear y sal.",
                "Incorporá chips de chocolate.",
            ],
        },
        {
            "phase": "Horneado",
            "title": "Cocción",
            "steps": [
                "Alterná húmedos y secos sin trabajar de más.",
                "Llená pirotines hasta 3/4 y horneá a 190 °C durante 22 minutos.",
            ],
        },
    ],
    "pasta fresca": [
        {
            "phase": "Masa",
            "title": "Amasado",
            "steps": [
                "Disponé la harina en forma de corona.",
                "Sumá huevos en el centro y amasá hasta homogeneizar.",
                "Reposá 30 minutos envuelta en film.",
            ],
        },
        {
            "phase": "Estirado",
            "title": "Laminado",
            "steps": [
                "Estirá la masa con máquina o palote hasta 1 mm de espesor.",
                "Cortá en fettuccine o ravioles según gusto.",
            ],
        },
        {
            "phase": "Cocción",
            "title": "Hervido",
            "steps": [
                "Herví en agua con sal durante 2 a 3 minutos.",
                "Serví con salsa a elección.",
            ],
        },
    ],
    "frikandel": [
        {
            "phase": "Mezcla",
            "title": "Picada especiada",
            "steps": [
                "Mezclá las carnes picadas con pan remojado en leche.",
                "Sumá cebolla rehogada, nuez moscada y pimienta.",
            ],
        },
        {
            "phase": "Formado",
            "title": "Embutido",
            "steps": [
                "Formá cilindros de 12 cm y pasá por pan rallado.",
            ],
        },
        {
            "phase": "Cocción",
            "title": "Fritura",
            "steps": [
                "Fritá en aceite caliente a 170 °C durante 6 minutos.",
                "Serví en pan con mostaza y cebolla.",
            ],
        },
    ],
    "pan ciabatta": [
        {
            "phase": "Masa madre",
            "title": "Poolish",
            "steps": [
                "Mezclá 100 g de harina, 100 ml de agua y 1 g de levadura.",
                "Reposá 12 a 16 horas a temperatura ambiente.",
            ],
        },
        {
            "phase": "Amasado",
            "title": "Masa final",
            "steps": [
                "Sumá harina, agua, sal y el poolish.",
                "Amasá plegando cada 30 minutos durante 3 horas.",
            ],
        },
        {
            "phase": "Horneado",
            "title": "Cocción",
            "steps": [
                "Volcá sobre placa enharinada y horneá a 230 °C durante 25 minutos.",
            ],
        },
    ],
    "bizcocho de chocolate": [
        {
            "phase": "Preparación",
            "title": "Masa",
            "steps": [
                "Derretí el chocolate con la manteca a baño María.",
                "Batí huevos con azúcar hasta punto cinta.",
                "Tamizá harina y polvo de hornear; alterná con la mezcla de chocolate.",
            ],
        },
        {
            "phase": "Horneado",
            "title": "Cocción",
            "steps": [
                "Volcá en molde enmantecado.",
                "Horneá a 180 °C durante 35 minutos.",
            ],
        },
    ],
    "bizcocho marmolado": [
        {
            "phase": "Masa base",
            "title": "Bizcocho neutro",
            "steps": [
                "Batí manteca con azúcar hasta cremoso.",
                "Sumá huevos uno a uno y esencia de vainilla.",
                "Incorporá harina con polvo de hornear alternando con leche.",
            ],
        },
        {
            "phase": "Veteado",
            "title": "Mezcla de cocoa",
            "steps": [
                "Separó un tercio de la masa y mezclá con cocoa tamizada.",
                "Alterná cucharadas de masa clara y oscura en el molde.",
                "Pasá un palote para marmolar.",
            ],
        },
        {
            "phase": "Horneado",
            "title": "Cocción",
            "steps": [
                "Horneá a 180 °C durante 40 minutos.",
            ],
        },
    ],
    "queque de yogur": [
        {
            "phase": "Mezcla",
            "title": "Masa en vaso",
            "steps": [
                "Usá el vaso de yogur como medida.",
                "Mezclá yogur, huevos y aceite.",
                "Sumá azúcar, harina y polvo de hornear.",
                "Ralladura de limón para perfumar.",
            ],
        },
        {
            "phase": "Horneado",
            "title": "Cocción",
            "steps": [
                "Volcá en molde enmantecado.",
                "Horneá a 180 °C durante 35 minutos.",
            ],
        },
    ],
    "queque de vainilla": [
        {
            "phase": "Mezcla",
            "title": "Masa",
            "steps": [
                "Batí manteca con azúcar hasta cremoso.",
                "Sumá huevos uno a uno y esencia de vainilla.",
                "Incorporá harina y polvo de hornear.",
            ],
        },
        {
            "phase": "Horneado",
            "title": "Cocción",
            "steps": [
                "Volcá en molde enmantecado.",
                "Horneá a 180 °C durante 35 minutos.",
            ],
        },
    ],
}


# ---------------------------------------------------------------------------
# 2. Ingredient allergens backfill (Spanish name → allergen vocabulary)
# ---------------------------------------------------------------------------

_INGREDIENT_ALLERGEN_MAP: dict[str, str] = {
    # gluten / flour family
    "harina": "gluten",
    "harina integral": "gluten",
    "harina de trigo": "gluten",
    "harina de centeno": "gluten",
    "pan rallado": "gluten",
    "galleta": "gluten",
    "galletas": "gluten",
    "pan": "gluten",
    "pan de molde": "gluten",
    "fideos": "gluten",
    # dairy
    "manteca": "dairy",
    "leche": "dairy",
    "leche entera": "dairy",
    "leche descremada": "dairy",
    "crema de leche": "dairy",
    "queso crema": "dairy",
    "queso": "dairy",
    "manteca derretida": "dairy",
    "buttermilk": "dairy",
    "yogur": "dairy",
    "yogurt": "dairy",
    # eggs
    "huevos": "eggs",
    "huevo": "eggs",
    "clara de huevo": "eggs",
    # nuts
    "nueces": "nuts",
    "nuez": "nuts",
    "almendras": "nuts",
    "avellanas": "nuts",
    "pistachos": "nuts",
    "castañas de cajú": "nuts",
    "maní": "nuts",
    "piñones": "nuts",
    # soy
    "aceite de soja": "soy",
    "leche de soja": "soy",
    "tofu": "soy",
    "salsa de soja": "soy",
    # sesame
    "semillas de sésamo": "sesame",
    "ajonjolí": "sesame",
    "tahini": "sesame",
    # sulfites
    "vino tinto": "sulfites",
    "vino blanco": "sulfites",
    "vinagre de vino": "sulfites",
}


# ---------------------------------------------------------------------------
# 3. tag_link backfill — derive from recipe/ingredient column data
# ---------------------------------------------------------------------------

_ALLERGEN_TO_TAG_NAME: dict[str, str] = {
    "gluten": "alergeno-gluten",
    "dairy": "alergeno-lactosa",
    "eggs": "con-huevo",
    "nuts": "alergeno-frutos-secos",
    "soy": "con-soja",
    "sesame": "con-sesamo",
    "sulfites": "con-sulfitos",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_allergens(value: Any) -> list[str]:
    if not value:
        return []
    return [s.strip() for s in value.split(",") if s.strip()]


def _seed_recipe_metadata(session: Any) -> tuple[int, int]:
    """Populate recipe.instructions + family + difficulty + yield_grams."""
    recipes = session.query(Recipe).all()
    updated = 0
    skipped = 0
    for r in recipes:
        # Skip the contaminated recipe 13
        if r.name in _CONTAMINATED_NAMES and len(r.lines or []) > 25:
            skipped += 1
            continue

        # Family (from name-based classifier; sets r.family)
        try:
            r.family = infer_recipe_family(r) or r.family
        except Exception:
            pass

        # Difficulty from line complexity
        if not r.difficulty or r.difficulty == 0:
            try:
                ing_count = recipe_ingredient_count(r)
                depth = 0  # already filtered
                r.difficulty = min(max(int(infer_difficulty(r, ing_count, depth)), 1), 5)
            except Exception:
                pass

        # Yield grams is not a stored column — it is computed on demand
        # by recipe_yield_grams(recipe) and used by downstream costing.

        # Instructions JSON
        if not r.instructions and r.name in _RECIPE_INSTRUCTIONS:
            r.instructions = json.dumps(_RECIPE_INSTRUCTIONS[r.name], ensure_ascii=False)

        # Classify (updates family/dietary/allergens if not already set)
        try:
            cls = classify_recipe(session, r)
            if cls:
                if not r.family and cls.get("family"):
                    r.family = cls["family"]
                if not r.dietary_tags and cls.get("dietary_tags"):
                    r.dietary_tags = ",".join(cls["dietary_tags"])
                if not r.allergens and cls.get("allergens"):
                    r.allergens = ",".join(cls["allergens"])
        except Exception:
            pass

        updated += 1
    return updated, skipped


def _seed_ingredient_allergens(session: Any) -> int:
    """Backfill ingredient.allergens from the Spanish→allergen map."""
    updated = 0
    for ing in session.query(Ingredient).all():
        if ing.allergens:
            continue  # already set
        key = (ing.name or "").strip().lower()
        if key in _INGREDIENT_ALLERGEN_MAP:
            ing.allergens = _INGREDIENT_ALLERGEN_MAP[key]
            updated += 1
    return updated


def _seed_tag_links(session: Any) -> tuple[int, int]:
    """Backfill tag_link rows for ingredient and recipe targets."""
    ing_links = 0
    rec_links = 0

    # ingredients
    for ing in session.query(Ingredient).all():
        allergens = _parse_allergens(ing.allergens)
        for allergen in allergens:
            tag_name = _ALLERGEN_TO_TAG_NAME.get(allergen)
            if not tag_name:
                continue
            tag = ensure_tag(session, tag_name, "ingredient", "#ff6f00")
            existing = (
                session.query(TagLink)
                .filter(
                    TagLink.tag_id == tag.id,
                    TagLink.target_kind == "ingredient",
                    TagLink.target_id == ing.id,
                )
                .first()
            )
            if existing is None:
                session.add(TagLink(tag_id=tag.id, target_kind="ingredient", target_id=ing.id))
                ing_links += 1

    # recipes
    for r in session.query(Recipe).all():
        allergens = _parse_allergens(r.allergens)
        for allergen in allergens:
            tag_name = _ALLERGEN_TO_TAG_NAME.get(allergen)
            if not tag_name:
                continue
            tag = ensure_tag(session, tag_name, "recipe", "#ff6f00")
            existing = (
                session.query(TagLink)
                .filter(
                    TagLink.tag_id == tag.id,
                    TagLink.target_kind == "recipe",
                    TagLink.target_id == r.id,
                )
                .first()
            )
            if existing is None:
                session.add(TagLink(tag_id=tag.id, target_kind="recipe", target_id=r.id))
                rec_links += 1

    return ing_links, rec_links


def _run_cascade_refresh(session: Any) -> int:
    """Refresh recipe.allergens + recipe.derived_dietary_tags caches."""
    from app.rms.tag_algebra import cascade_refresh

    refreshed = 0
    for r in session.query(Recipe).all():
        try:
            cascade_refresh(session, recipe_id=r.id)
            refreshed += 1
        except Exception:
            session.rollback()
    return refreshed


def main() -> None:
    db_path = os.environ.get("AIW_SASKIA_DB_PATH", "/opt/data/.local/share/AIW-Saskia/rms.sqlite")
    os.environ["AIW_SASKIA_DB_PATH"] = db_path

    engine = make_engine()
    init_db(engine)
    sf = make_session_factory(engine)

    with sf() as session:
        # 1. Recipe metadata + instructions
        updated, skipped = _seed_recipe_metadata(session)
        session.commit()
        print(f"recipes: updated={updated} skipped={skipped}")

        # 2. Ingredient allergens
        ing_count = _seed_ingredient_allergens(session)
        session.commit()
        print(f"ingredient allergens backfilled: {ing_count}")

        # 3. tag_link rows
        ing_links, rec_links = _seed_tag_links(session)
        session.commit()
        print(f"tag_links inserted: ingredients={ing_links} recipes={rec_links}")

        # 4. Cascade refresh
        refreshed = _run_cascade_refresh(session)
        session.commit()
        print(f"cascade_refresh: {refreshed} recipes")

        with engine.begin() as conn:
            print(f"schema_version: {schema_version(conn)}")


if __name__ == "__main__":
    main()
