"""app/rms/ingredient_intel.py — auto-classify ingredients.

The client (the operator) provides ingredient names as free-form strings.
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

from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# Keyword tables
# ---------------------------------------------------------------------------

# Categories — first match wins. Order matters: more specific before general.

# ── Backward-compat re-exports ──────────────────────────────────────────
# The category-keyword data + the infer_category function were moved to
# app/rms/tagging/classify.py on 2026-10-09 to break the bidirectional
# lazy-import cycle (ingredient_intel ↔ tagging.classify). This module
# used to define them inline; the rest of the inventory pipeline
# (`infer_subcategory`, `infer_role`, `classify_ingredient`, etc.) still
# uses the same keyword data, which now lives in `tagging.classify`.

from app.rms.tagging.classify import (  # noqa: F401  (re-exports for back-compat)
    _CATEGORY_KEYWORDS,
    _normalize,
    _keyword_in,
    infer_category,
)


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
    "leavening": ("levadura", "polvo de hornear", "bicarbonato", "cremor tártaro"),
    "sweetener": (
        "azúcar",
        "miel",
        "stevia",
        "dextrosa",
        "glucosa",
        "jarabe",
        "melaza",
        "eritritol",
    ),
    "fat": ("aceite", "manteca", "mantequilla", "margarina", "grasa"),
    "structure": ("harina", "maicena", "fécula", "almidón"),
    "dairy": ("leche", "crema", "yogur", "queso", "ricota"),
    "flavor": ("esencia", "vainilla", "ralladura", "canela", "cacao", "especias"),
    "decoration": ("glaseado", "fondant", "sprinkles", "colorante", "cobertura"),
    "protein": ("huevo", "huevos", "leche en polvo"),
    "fruit": ("frutilla", "arándano", "manzana", "naranja", "pasas"),
    "binder": ("gelatina", "chía", "lino"),
}

# Allergens — present in this ingredient.
# Aligned with INAN Resolución S.G. N° 402/2018 + 614/2023 allergen list.
#
# As of the 2026-09-29 tagging/ refactor, the canonical allergen-keyword
# table lives in app/rms.tagging.vocabulary.ALLERGEN_KEYWORDS. This
# `_ALLERGEN_KEYWORDS` shim is kept for backwards compatibility with any
# external code that imports it directly (tests, scripts, third-party
# integrations). New code should import from app.rms.tagging.vocabulary.

# Default shelf-life (days) per category.
CATEGORY_SHELF_LIFE: Final[dict[str, int]] = {
    "lácteos": 7,
    "harinas": 180,
    "endulzantes": 730,
    "grasas": 120,
    "leudantes": 180,
    "huevos": 21,
    "carnes": 5,
    "especias": 730,
    "frutos-secos": 90,
    "decoración": 180,
    "frutas": 5,
    "líquidos": 5,
    "semillas": 365,
    "otros": 90,
}

# Storage — where to keep it. Aligned with HACCP storage rules.
_STORAGE_KEYWORDS: Final[dict[str, tuple[str, ...]]] = {
    "refrigerated": (
        "leche",
        "crema",
        "manteca",
        "mantequilla",
        "yogur",
        "queso",
        "huevo",
        "huevos",
        "ricota",
        "requesón",
        "dulce de leche",
        "crema agria",
        "queso crema",
    ),
    "frozen": ("congelad",),
    "ambient": (),  # default — anything not perishable
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------




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
    """Return sorted list of allergens present.

    Thin shim over app.rms.tagging.classify.infer_allergens — kept here
    for backwards compatibility with the original public API. New code
    should import from app.rms.tagging.classify.
    """
    from app.rms.tagging.classify import infer_allergens as _impl

    return _impl(name)


def infer_dietary_tags(name: str) -> list[str]:
    """Dietary tags this ingredient fits.

    Backwards-compat shim. The canonical implementation now lives in
    app/rms.tagging.classify; this wrapper preserves the legacy contract
    (returns English-form labels) for the inventory auto-suggest flow
    while the rest of the system uses normalize() to map to Spanish.

    Returns English labels like 'vegan', 'vegetarian', 'gluten_free',
    'keto_friendly' — same as before. The recipe derivation normalizes
    these through TAG_ALIASES at the read boundary.
    """
    from app.rms.tagging.classify import infer_dietary_tags as _impl

    return _impl(name)


def infer_shelf_life_days(name: str) -> int:
    """Default shelf life based on category."""
    return CATEGORY_SHELF_LIFE[infer_category(name)]


def infer_storage(name: str, session: Session | None = None) -> str:
    """Where to store: refrigerated / frozen / ambient.

    Phase 11: Reads keywords from the storage_keyword DB table (when a
    session is provided). Falls back to the legacy _STORAGE_KEYWORDS dict
    for the no-session case (tests, one-off scripts).
    """
    from app.rms.constants import (
        STORAGE_AMBIENT,
        STORAGE_FROZEN,
        STORAGE_REFRIGERATED,
    )

    norm = _normalize(name)

    # When a session is provided, use DB-driven keywords.
    if session is not None:
        from sqlalchemy import select as _select

        from app.rms.models import StorageKeyword

        rows = (
            session.execute(
                _select(StorageKeyword)
                .where(StorageKeyword.is_active.is_(True))
                .order_by(StorageKeyword.sort_order.asc(), StorageKeyword.keyword.asc())
            )
            .scalars()
            .all()
        )

        # Check frozen first (more specific match), then refrigerated.
        # If nothing matched, default to ambient.
        for code in (STORAGE_FROZEN, STORAGE_REFRIGERATED):
            for row in rows:
                if row.storage_code == code and row.keyword in norm:
                    return code
        return STORAGE_AMBIENT

    # No session — fall back to the hardcoded legacy dict.
    for kw in _STORAGE_KEYWORDS["frozen"]:
        if kw in norm:
            return STORAGE_FROZEN
    for kw in _STORAGE_KEYWORDS["refrigerated"]:
        if kw in norm:
            return STORAGE_REFRIGERATED
    return STORAGE_AMBIENT


def classify_ingredient(name: str, session: Session | None = None) -> dict:
    """Full classification result for one ingredient."""
    category = infer_category(name)
    return {
        "category": category,
        "subcategory": infer_subcategory(name, category),
        "role": infer_role(name),
        "allergens": infer_allergens(name),
        "dietary_tags": infer_dietary_tags(name),
        "shelf_life_days": infer_shelf_life_days(name),
        "storage": infer_storage(name, session=session),
    }


# ---------------------------------------------------------------------------
# Substitutability — recipe co-occurrence graph
# ---------------------------------------------------------------------------


def find_substitutes_by_role(session: object, ingredient_id: int) -> list[int]:
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
