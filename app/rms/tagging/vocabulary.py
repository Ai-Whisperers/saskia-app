"""app/rms/tagging/vocabulary.py — Single source of truth for tag strings.

All dietary-tag-related constants live here. No I/O, no DB access, no
side effects. Pure data. Importable from anywhere.

The split between canonical/aliases/blockers/keywords is deliberate:

  CANONICAL_DIETARY_TAGS   — Spanish names that appear in the UI and
                              get persisted to Recipe.derived_dietary_tags.

  CANONICAL_ALLERGENS      — canonical allergen codes. Stored in
                              Ingredient.allergens as CSV.

  TAG_ALIASES              — read-boundary normalization. Maps English,
                              snake_case, hyphenated variants to canonical.
                              Used by normalize() before any comparison.

  TAG_ALLERGEN_BLOCKERS    — which allergens disqualify which tag. This
                              is the heart of the "X blocks sin Y" logic.
                              sin gluten ↔ sin tacc equivalence is expressed
                              here (both block on 'gluten').

  ALLERGEN_KEYWORDS        — bootstrap for the allergens column. Used by
                              infer_allergens(name). Operator confirms in
                              inventory; we don't write allergens from this.

  NEUTRAL_INGREDIENT_KEYWORDS — ingredients that never block any tag
                                (water, salt, common spices, leaveners,
                                oils). This is the explicit allow-list.

  CUSTOMER_ALLERGEN_WORDS  — Spanish/Guaraní customer notes → allergen code.
                              Lives here because it's the same vocabulary
                              problem (different surface, same codes).
"""

from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────
# Canonical Spanish tag names. This is the ONLY set that gets written to
# Recipe.derived_dietary_tags / Product.inherited_tags / surfaced in UI.
# ─────────────────────────────────────────────────────────────────────────
CANONICAL_DIETARY_TAGS: frozenset[str] = frozenset({
    "vegano",
    "vegetariano",
    "sin gluten",
    "sin tacc",        # sin tacc ≡ sin gluten (Argentina / Paraguay usage)
    "sin lactosa",
    "sin huevo",
    "sin frutos secos",
    "sin azúcar",
    "keto",
    "integral",
    "orgánico",
})


# ─────────────────────────────────────────────────────────────────────────
# Canonical allergen codes. Stored as CSV in Ingredient.allergens and
# Recipe.allergens. Sorted alphabetically in derive_recipe_tags.
# ─────────────────────────────────────────────────────────────────────────
CANONICAL_ALLERGENS: frozenset[str] = frozenset({
    "gluten",
    "dairy",
    "eggs",
    "nuts",
    "soy",
    "sesame",
    "sulfites",
    # 2026-09-29: added to surface sin-azúcar / keto contradictions that
    # were silently allowed because sugar wasn't recognized as a blocker.
    # Treat as a "disqualifier code" used by the same infer/blocker
    # machinery. NOT a real allergen (INAN doesn't list it), but
    # functionally behaves identically from the recipe-derivation side.
    "sugar",
})


# ─────────────────────────────────────────────────────────────────────────
# Tag aliases. Every read boundary MUST run through normalize() so an
# English label written by an older seed/xlsx import resolves to its
# canonical Spanish form.
#
# Add new aliases HERE, not inline. If a label isn't in this map,
# normalize() returns None and the tag is dropped silently (defensive).
# ─────────────────────────────────────────────────────────────────────────
TAG_ALIASES: dict[str, str] = {
    # English → Spanish
    "vegan": "vegano",
    "vegetarian": "vegetariano",
    "gluten_free": "sin gluten",
    "gluten-free": "sin gluten",
    "sugar_free": "sin azúcar",
    "sugar-free": "sin azúcar",
    "keto_friendly": "keto",
    "keto-friendly": "keto",
    "lactose_free": "sin lactosa",
    "dairy_free": "sin lactosa",
    "egg_free": "sin huevo",
    "nut_free": "sin frutos secos",
    "whole_grain": "integral",
    "organic": "orgánico",
    # Spanish variants (case + hyphen) — pass-through / normalization
    "vegano": "vegano",
    "vegetariano": "vegetariano",
    "sin gluten": "sin gluten",
    "sin-gluten": "sin gluten",
    "sin tacc": "sin tacc",
    "sin-tacc": "sin tacc",
    "sin lactosa": "sin lactosa",
    "sin-lactosa": "sin lactosa",
    "sin huevo": "sin huevo",
    "sin-huevo": "sin huevo",
    "sin frutos secos": "sin frutos secos",
    "sin-frutos-secos": "sin frutos secos",
    "sin azúcar": "sin azúcar",
    "sin-azucar": "sin azúcar",
    "sin-azúcar": "sin azúcar",
    "integral": "integral",
    "orgánico": "orgánico",
    "organico": "orgánico",
    "keto": "keto",
}


# ─────────────────────────────────────────────────────────────────────────
# Tag → allergens that disqualify it. Empty tuple means the tag isn't
# allergen-driven (certifications like 'integral', 'orgánico', or
# 'vegetariano' which depends on meat detection not allergen codes).
#
# sin tacc shares blockers with sin gluten — they're the same concept
# under different labels. Paraguay bakery / Argentine food law uses both.
# ─────────────────────────────────────────────────────────────────────────
TAG_ALLERGEN_BLOCKERS: dict[str, tuple[str, ...]] = {
    "sin gluten":       ("gluten",),
    "sin tacc":         ("gluten",),       # sin tacc ≡ sin gluten
    "sin lactosa":      ("dairy",),
    "sin huevo":        ("eggs",),
    "sin frutos secos": ("nuts",),
    "sin azúcar":       ("sugar",),        # 2026-09-29: was () — see research notes
    "keto":             ("sugar",),        # 2026-09-29: simplified — sugar is the only keto-relevant blocker
    "vegano":           ("dairy", "eggs"), # excludes animal-derived; honey = debated
    "vegetariano":      (),                # only meat disqualifies (detected via name keyword)
    "integral":         (),                # whole-grain certification, not allergen-driven
    "orgánico":         (),                # certification, not allergen-driven
}


# ─────────────────────────────────────────────────────────────────────────
# Allergen keywords — bootstrap for Ingredient.allergens. Operator confirms
# the auto-suggested allergens in the inventory page; we never auto-write.
#
# Single source of truth: previously this lived in ingredient_intel.py
# (English/Spanish keywords) AND derived_intel.py (customer-side Spanish
# words). Customer words and ingredient keywords are different vocabularies
# — kept in separate constants below.
# ─────────────────────────────────────────────────────────────────────────
ALLERGEN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "gluten": (
        "harina", "trigo", "avena", "cebada", "centeno",
        "malta", "espelta", "cebada", "centeno",
    ),
    "dairy": (
        "leche", "crema", "manteca", "mantequilla", "yogur",
        "queso", "queso crema", "ricota", "requesón", "dulce de leche",
    ),
    "eggs": (
        "huevo", "huevos", "clara", "yema", "ovoalbúmina",
    ),
    "nuts": (
        "almendra", "nuez", "nueces", "avellana", "pistacho",
        "maní", "mani", "castaña", "pecán", "macadamia",
    ),
    "soy": (
        "soja", "soya", "lecitina de soja", "tofu",
    ),
    "sesame": (
        "sésamo", "sesamo", "ajonjolí", "ajonjoli",
    ),
    "sulfites": (
        "sulfito", "sulfitos", "metabisulfito",
    ),
    # 2026-09-29: sugar is added as a disqualifier code (not a true allergen
    # per INAN). Used by sin-azúcar / keto to block recipes that contain
    # any sweetener. Same mechanism as allergen blocking but conceptually
    # different — see vocabulary.CANONICAL_ALLERGENS note.
    "sugar": (
        "azúcar", "azucar",
        "miel",
        "jarabe", "jarabe de maíz", "jarabe de glucosa",
        "glucosa", "dextrosa",
        "fructosa",
        "panela", "rapadura",
        "melaza",
        "edulcorante", "stevia (azúcar)",  # explicit "sugar stevia" only — stevia alone OK
        "azúcar impalpable", "azúcar glas", "azúcar glass",
        "azúcar mascabado", "azúcar morena", "azúcar moreno",
        "azúcar blanca", "azúcar blanco",
        "azúcar negra", "azúcar negro",
        "azúcar rubia",
    ),
}


# ─────────────────────────────────────────────────────────────────────────
# Neutral ingredients — never block any tag. Pantry staples whose presence
# or absence doesn't change a recipe's dietary status. Explicit allow-list
# (rather than inference) so operators can audit it.
#
# Matching rule (in classify._is_neutral): name equals keyword OR starts
# with keyword + " ". So "sal" matches but "salsa" doesn't.
# ─────────────────────────────────────────────────────────────────────────
NEUTRAL_INGREDIENT_KEYWORDS: frozenset[str] = frozenset({
    # Water / salt / ice
    "agua", "sal", "sal fina", "sal gruesa", "hielo",
    # Common spices — never disqualify a recipe from any dietary tag
    "canela", "jengibre", "nuez moscada", "vainilla", "esencia",
    # Leaveners / acids / chemical inputs
    "bicarbonato", "polvo de hornear", "levadura", "vinagre",
    # Fats — oil is universally vegan / keto / sugar-free
    "aceite",
    # Note: sugars and flours are NOT neutral — they're the actual blockers.
    # Operator must declare their allergens (e.g. Harina de trigo → gluten).
})


# ─────────────────────────────────────────────────────────────────────────
# Customer-side Spanish allergen words. Used by derived_intel.parse_customer_allergies
# to extract allergen codes from free-text notes ("alérgica al maní").
#
# Different vocabulary from ALLERGEN_KEYWORDS — this is what CUSTOMERS say,
# not what the ingredient is named. e.g. "mani" is a customer word for
# nuts but it also appears in ALLERGEN_KEYWORDS because the Spanish
# ingredient naming uses the same word. Kept separate so the two can
# evolve independently.
# ─────────────────────────────────────────────────────────────────────────
CUSTOMER_ALLERGEN_WORDS: dict[str, str] = {
    "gluten": "gluten",
    "trigo": "gluten",
    "harina": "gluten",
    "celia": "gluten",
    "celiac": "gluten",
    "celíaco": "gluten",
    "lactosa": "dairy",
    "leche": "dairy",
    "lácteos": "dairy",
    "lacteo": "dairy",
    "huevo": "eggs",
    "huevos": "eggs",
    "frutos secos": "nuts",
    "nueces": "nuts",
    "nuez": "nuts",
    "almendra": "nuts",
    "maní": "nuts",
    "mani": "nuts",
    "cacahuete": "nuts",
    "avellana": "nuts",
    "soja": "soy",
    "soya": "soy",
    "sésamo": "sesame",
    "sesamo": "sesame",
    "ajonjolí": "sesame",
    "sulfitos": "sulfites",
    "sulfito": "sulfites",
}


# ─────────────────────────────────────────────────────────────────────────
# Display order for blocked-list UI (most-restrictive tags first so the
# "why isn't my pan sin gluten?" tooltip is scannable).
# ─────────────────────────────────────────────────────────────────────────
ALLERGEN_DISPLAY_ORDER: tuple[str, ...] = (
    "gluten", "dairy", "eggs", "nuts", "soy", "sesame", "sulfites",
)


__all__ = [
    "ALLERGEN_DISPLAY_ORDER",
    "ALLERGEN_KEYWORDS",
    "CANONICAL_ALLERGENS",
    "CANONICAL_DIETARY_TAGS",
    "CUSTOMER_ALLERGEN_WORDS",
    "NEUTRAL_INGREDIENT_KEYWORDS",
    "TAG_ALIASES",
    "TAG_ALLERGEN_BLOCKERS",
]
