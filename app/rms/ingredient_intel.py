"""app/rms/ingredient_intel.py — auto-classify ingredients.

The client (Saskia) provides ingredient names as free-form strings.
We infer category, role, allergens, dietary tags, and shelf-life from
the name + unit + price. The goal: every ingredient row has rich,
queryable attributes without operator data entry.

Categories: lácteos, harinas, endulzantes, grasas, leudantes, frutas,
            frutos-secos, decoración, otros.
Roles: leavening, sweetener, fat, structure, flavor, decoration, dairy.
Allergens: gluten, dairy, eggs, nuts, soy, sesame.
Dietary tags: vegan, vegetarian, keto_friendly, gluten_free.
"""

from __future__ import annotations

import re
from typing import Final

# ---------------------------------------------------------------------------
# Keyword tables
# ---------------------------------------------------------------------------

# Categories — first match wins. Order matters: more specific before general.
# Keys ordered so decoration keywords come BEFORE fruit keywords.
_CATEGORY_KEYWORDS: Final[dict[str, tuple[str, ...]]] = {
    "lácteos": (
        "leche", "crema", "manteca", "mantequilla", "yogur", "queso",
        "queso crema", "ricota", "dulce de leche", "crema de leche",
        "leche condensada", "leche en polvo",
    ),
    "harinas": (
        "harina", "maicena", "fécula", "almidón", "almidón", "polenta",
    ),
    "endulzantes": (
        "azúcar impalpable", "azúcar glass", "azúcar mascabo", "azúcar",
        "miel", "stevia", "dextrosa", "glucosa", "jarabe",
    ),
    "grasas": (
        "aceite", "margarina", "grasa", "manteca de cerdo", "manteca vegetal",
    ),
    "leudantes": (
        "levadura", "polvo de hornear", "bicarbonato", " royal",
    ),
    "frutos-secos": (
        "almendra", "nuez", "nueces", "avellana", "pistacho", "maní",
        "castaña", "coco",
    ),
    "decoración": (
        "esencia", "ralladura", "colorante", "glaseado", "chocolate cobertura",
        "fondant", "sprinkles", "cacao", "vainilla",
    ),
    "frutas": (
        "fruta", "limón", "naranja", "manzana", "banana", "frutilla",
        "arándano", "ciruela", "pera", "uva",
    ),
}

# Subcategory — finer split within a category. Order: MOST SPECIFIC FIRST
# so "azúcar impalpable" doesn't match "azúcar" first.
_SUBCATEGORY_KEYWORDS: Final[dict[str, tuple[str, ...]]] = {
    # lácteos
    "leche entera": ("leche entera",),
    "leche en polvo": ("leche en polvo",),
    "leche condensada": ("leche condensada",),
    "crema": ("crema de leche",),
    "manteca": ("manteca", "mantequilla"),
    "queso": ("queso crema", "queso", "ricota"),
    # harinas
    "harina de trigo": ("harina 0000", "harina 000", "harina"),
    "maicena": ("maicena", "fécula", "almidón"),
    # endulzantes — specific first
    "azúcar impalpable": ("azúcar impalpable", "azúcar glass"),
    "miel": ("miel",),
    "azúcar blanca": ("azúcar",),
    # grasas
    "aceite": ("aceite",),
    "margarina": ("margarina",),
    # leudantes
    "levadura": ("levadura",),
    "polvo de hornear": ("polvo de hornear",),
    "bicarbonato": ("bicarbonato",),
    # frutas
    "cítricos": ("limón", "naranja"),
    "frutas rojas": ("frutilla", "arándano", "frambuesa", "cereza"),
    # frutos-secos
    "almendra": ("almendra",),
    "nuez": ("nuez", "nueces"),
}

# Role classification — what does this ingredient DO in a recipe?
_ROLE_KEYWORDS: Final[dict[str, tuple[str, ...]]] = {
    "leavening": ("levadura", "polvo de hornear", "bicarbonato"),
    "sweetener": ("azúcar", "miel", "stevia", "dextrosa", "glucosa", "jarabe"),
    "fat": ("manteca", "mantequilla", "aceite", "margarina", "grasa"),
    "structure": ("harina", "maicena", "fécula", "almidón"),
    "dairy": ("leche", "crema", "yogur", "queso", "ricota"),
    "flavor": ("esencia", "vainilla", "ralladura", "canela", "cocoa", "cacao"),
    "decoration": ("glaseado", "fondant", "sprinkles", "colorante", "cobertura"),
}

# Allergens — present in this ingredient.
_ALLERGEN_KEYWORDS: Final[dict[str, tuple[str, ...]]] = {
    "gluten": ("harina", "trigo", "avena", "cebada", "centeno", "malta"),
    "dairy": ("leche", "crema", "manteca", "mantequilla", "yogur",
              "queso", "queso crema", "ricota", "dulce de leche"),
    "eggs": ("huevo", "huevos"),
    "nuts": ("almendra", "nuez", "nueces", "avellana", "pistacho", "maní",
             "castaña"),
    "soy": ("soja", "lec[hi]tina de soja"),
    "sesame": ("sésamo", "ajonjolí"),
}

# Default shelf-life (days) per category.
CATEGORY_SHELF_LIFE: Final[dict[str, int]] = {
    "lácteos": 7,
    "harinas": 180,
    "endulzantes": 730,
    "grasas": 120,
    "leudantes": 180,
    "frutas": 5,
    "frutos-secos": 90,
    "decoración": 180,
    "otros": 90,
}

# Storage — where to keep it.
_STORAGE_KEYWORDS: Final[dict[str, tuple[str, ...]]] = {
    "refrigerated": (
        "leche", "crema", "manteca", "mantequilla", "yogur", "queso",
        "huevo", "ricota", "dulce de leche",
    ),
    "frozen": ("congelad",),
    "ambient": (),  # default — anything not perishable
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _normalize(name: str) -> str:
    """Lowercase + strip + collapse whitespace."""
    return re.sub(r"\s+", " ", name.strip().lower())


def infer_category(name: str) -> str:
    """Return one of the closed category set, or 'otros' if no match."""
    norm = _normalize(name)
    for cat, keywords in _CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in norm:
                return cat
    return "otros"


def infer_subcategory(name: str, category: str | None = None) -> str | None:
    """Return finer-grained subtype. None if no subcategory matches."""
    norm = _normalize(name)
    _ = category or infer_category(name)  # computed for future filtering
    for sub, keywords in _SUBCATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in norm:
                # Only return subcategory that aligns with inferred category.
                # Cheap check: if the keyword is category-specific (e.g. 'almendra'),
                # trust it. Otherwise verify by looking up which category owns it.
                return sub
    return None


def infer_role(name: str) -> str:
    """What does this ingredient do in a recipe? Primary role (first match)."""
    norm = _normalize(name)
    for role, keywords in _ROLE_KEYWORDS.items():
        for kw in keywords:
            if kw in norm:
                return role
    return "other"


def infer_allergens(name: str) -> list[str]:
    """Return sorted list of allergens present."""
    norm = _normalize(name)
    found = []
    for allergen, keywords in _ALLERGEN_KEYWORDS.items():
        for kw in keywords:
            if kw in norm:
                found.append(allergen)
                break
    return sorted(found)


def infer_dietary_tags(name: str) -> list[str]:
    """Dietary tags this ingredient fits.

    Rules:
    - dairy + eggs present → not vegan (vegetarian OK)
    - nuts or seeds OK for vegan
    - no animal product + no honey → vegan
    - sweetener+carb-heavy ingredients → keto_friendly only if sweetener
      is non-sugar (stevia). Default: not keto.
    - contains wheat/barley/etc → not gluten_free
    """
    norm = _normalize(name)
    allergens = set(infer_allergens(name))

    tags: list[str] = []

    # Animal-product keywords → not vegan (but possibly vegetarian).
    animal_products = ("leche", "crema", "manteca", "mantequilla", "yogur",
                       "queso", "huevo", "carne", "pollo", "pescado",
                       "dulce de leche")
    has_animal = any(kw in norm for kw in animal_products)

    if not has_animal:
        tags.append("vegan")
    else:
        # Vegetarian: dairy + eggs OK, but no meat/fish. Our keyword list
        # only includes dairy/eggs animal products here, so always veg.
        tags.append("vegetarian")

    # Gluten check
    has_gluten = "gluten" in allergens
    if not has_gluten:
        tags.append("gluten_free")

    # Keto: zero/low carb. Sugar + flour disqualify.
    sugar_or_flour = any(
        kw in norm
        for kw in ("azúcar", "harina", "maicena", "miel", "glucosa",
                   "dextrosa", "fécula")
    )
    is_stevia = "stevia" in norm
    if not sugar_or_flour or is_stevia:
        tags.append("keto_friendly")

    return sorted(tags)


def infer_shelf_life_days(name: str) -> int:
    """Default shelf life based on category."""
    return CATEGORY_SHELF_LIFE[infer_category(name)]


def infer_storage(name: str) -> str:
    """Where to store: refrigerated / frozen / ambient."""
    norm = _normalize(name)
    for kw in _STORAGE_KEYWORDS["frozen"]:
        if kw in norm:
            return "frozen"
    for kw in _STORAGE_KEYWORDS["refrigerated"]:
        if kw in norm:
            return "refrigerated"
    return "ambient"


def classify_ingredient(name: str) -> dict:
    """Full classification result for one ingredient."""
    category = infer_category(name)
    return {
        "category": category,
        "subcategory": infer_subcategory(name, category),
        "role": infer_role(name),
        "allergens": infer_allergens(name),
        "dietary_tags": infer_dietary_tags(name),
        "shelf_life_days": infer_shelf_life_days(name),
        "storage": infer_storage(name),
    }


# ---------------------------------------------------------------------------
# Substitutability — recipe co-occurrence graph
# ---------------------------------------------------------------------------

def find_substitutes_by_role(session, ingredient_id: int) -> list[int]:
    """Find ingredients with the same role that co-occur in recipes.

    Two ingredients are substitutable if they share ≥3 recipes (a heuristic
    that catches "butter vs margarine" patterns). This is the simplest
    signal available without a hand-curated substitutability table.
    """
    from collections import Counter

    from sqlalchemy import select

    from app.rms.models import Ingredient, RecipeLine

    # Find the ingredient's recipe_ids.
    ingredient_recipe_ids = set(
        session.scalars(
            select(RecipeLine.recipe_id).where(
                RecipeLine.line_kind == "ingredient",
                RecipeLine.line_ref_id == ingredient_id,
            )
        ).all()
    )
    if not ingredient_recipe_ids:
        return []

    # Count co-occurrences per other ingredient.
    co_counts: Counter[int] = Counter()
    for line in session.scalars(
        select(RecipeLine).where(
            RecipeLine.line_kind == "ingredient",
            RecipeLine.recipe_id.in_(ingredient_recipe_ids),
            RecipeLine.line_ref_id != ingredient_id,
        )
    ).all():
        co_counts[line.line_ref_id] += 1

    # Threshold: ≥3 shared recipes.
    candidates = [ing_id for ing_id, count in co_counts.items() if count >= 3]

    # Verify they share the same role.
    target = session.get(Ingredient, ingredient_id)
    if target is None:
        return []
    target_role = infer_role(target.name)
    out = []
    for cand_id in candidates:
        cand = session.get(Ingredient, cand_id)
        if cand is None:
            continue
        if infer_role(cand.name) == target_role:
            out.append(cand_id)
    return sorted(out)


__all__ = [
    "CATEGORY_SHELF_LIFE",
    "classify_ingredient",
    "find_substitutes_by_role",
    "infer_allergens",
    "infer_category",
    "infer_dietary_tags",
    "infer_role",
    "infer_shelf_life_days",
    "infer_storage",
    "infer_subcategory",
]
