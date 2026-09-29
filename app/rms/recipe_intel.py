"""app/rms/recipe_intel.py — auto-classify recipes.

Every recipe is just a name + yield + lines. We infer prep/cook time,
dietary compatibility, difficulty, family, yield-in-grams, cost-per-gram.

Used by:
- Dashboard intelligence panel (E34)
- Production scheduler (E32)
- Menu engineering report (E28)
"""

from __future__ import annotations

from typing import Final

from sqlalchemy.orm import Session

from app.rms.models import Recipe

# ---------------------------------------------------------------------------
# Family + difficulty + cook-time tables
# ---------------------------------------------------------------------------

# Family classification — keyword on recipe.name.
_FAMILY_KEYWORDS: Final[dict[str, tuple[str, ...]]] = {
    "panadería": ("pan", "factura", "croissant", "medialuna", "baguette",
                  "brioche", "hojaldre"),
    "pastelería": ("torta", "muffin", "cupcake", "brownie", "galleta",
                   "cookie", "macaron", "cheesecake", "tart", "pie", "roll",
                   "rolls", "budín", "budin", "cake"),
    "fríos": ("cheesecake", "tiramisu", "mousse", "pavlova"),
    "salados": ("empanada", "tarta", "quiche", "sandwich", "tostado",
                "chipá", "scon"),
    "dulces regionales": ("alfajor", "factura", "rosca"),
    "frituras": ("oliebollen", "donut", "buñuelo"),
}

# Family-level cook times (minutes).
_FAMILY_COOK_MINUTES: Final[dict[str, int]] = {
    "panadería": 30,
    "pastelería": 35,
    "fríos": 0,  # no bake
    "salados": 25,
    "dulces regionales": 20,
    "frituras": 8,
    "default": 30,
}

# Default yield-in-grams assumption when not specified.
DEFAULT_YIELD_GRAMS_PER_UNIT: Final[dict[str, int]] = {
    "und": 50,  # default unit weight for a baked item
    "g": 1,
    "kg": 1000,
    "ml": 1,
    "l": 1000,
}

# Sub-recipe depth (infinite recursion guard).
_MAX_RECIPE_DEPTH = 10


# ---------------------------------------------------------------------------
# Family + difficulty + cook-time
# ---------------------------------------------------------------------------

def infer_recipe_family_from_name(name: str) -> str:
    """Classify recipe by name string (no Recipe object needed).

    Used by recipe_create() to auto-fill the family before the recipe
    is saved. See infer_recipe_family() for the Recipe-object variant.
    """
    name = (name or "").lower()
    ordered_keywords = [
        ("frituras", ("oliebollen", "donut", "buñuelo", "frikandel")),
        ("salados", ("empanada", "quiche", "sandwich", "tostado",
                    "chipá", "scon", "pasta fresca", "pasta")),
        ("panadería", ("pan ", "pan de", "pan_", "medialuna", "croissant",
                       "baguette", "brioche", "hojaldre", "factura",
                       "rosca", "alfajor", "ciabatta", "bagel")),
        ("fríos", ("cheesecake", "tiramisu", "mousse", "pavlova")),
        ("dulces regionales", ("rosca", "alfajor")),
        ("pastelería", ("torta", "muffin", "cupcake", "brownie", "galleta",
                        "cookie", "macaron", "tart", "pie", "appeltaart",
                        "tarta", "roll", "rolls", "budín", "budin", "cake",
                        "bizcocho", "queque", "crêpes", "crepes",
                        "waffle", "chocolate")),
    ]
    for family, keywords in ordered_keywords:
        for kw in keywords:
            if kw in name:
                return family
    return "otros"


def infer_recipe_family(recipe: Recipe) -> str:
    """Classify recipe into a family by name keyword match.

    More specific keywords come first within their families.
    """
    return infer_recipe_family_from_name(recipe.name)


def infer_recipe_family_with_keywords(recipe: Recipe) -> tuple[str, str]:
    """Return (family, matched_keyword) for explainability + UI debug.

    Like infer_recipe_family() but also returns which keyword matched.
    Used by /recetas/inteligencia diagnostic page.
    """
    name = (recipe.name or "").lower()
    ordered_keywords = [
        ("frituras", ("oliebollen", "donut", "buñuelo", "frikandel")),
        ("salados", ("empanada", "quiche", "sandwich", "tostado",
                    "chipá", "scon", "pasta fresca", "pasta")),
        ("panadería", ("pan ", "pan de", "pan_", "medialuna", "croissant",
                       "baguette", "brioche", "hojaldre", "factura",
                       "rosca", "alfajor", "ciabatta", "bagel")),
        ("fríos", ("cheesecake", "tiramisu", "mousse", "pavlova")),
        ("dulces regionales", ("rosca", "alfajor")),
        ("pastelería", ("torta", "muffin", "cupcake", "brownie", "galleta",
                        "cookie", "macaron", "tart", "pie", "appeltaart",
                        "tarta", "roll", "rolls", "budín", "budin", "cake",
                        "bizcocho", "queque", "crêpes", "crepes",
                        "waffle", "chocolate")),
    ]
    for family, keywords in ordered_keywords:
        for kw in keywords:
            if kw in name:
                return (family, kw)
    return ("otros", "")


def estimate_prep_minutes(recipe: Recipe, ingredient_count: int | None = None) -> int:
    """Prep time estimate: yield_qty × 2 + ingredient_count × 1.5.

    Returns rounded-up integer minutes. Minimum 5.
    """
    yield_qty = float(recipe.yield_qty or 1)
    n_ingredients = ingredient_count if ingredient_count is not None else 0
    base = (yield_qty * 2) + (n_ingredients * 1.5)
    return max(5, int(base + 0.5))


def estimate_cook_minutes(recipe: Recipe) -> int:
    """Cook minutes from recipe family. 0 for 'fríos'."""
    family = infer_recipe_family(recipe)
    return _FAMILY_COOK_MINUTES.get(family, _FAMILY_COOK_MINUTES["default"])


def estimate_total_minutes(recipe: Recipe, ingredient_count: int | None = None) -> int:
    """Prep + cook."""
    return estimate_prep_minutes(recipe, ingredient_count) + estimate_cook_minutes(recipe)


def infer_difficulty(recipe: Recipe, ingredient_count: int, sub_recipe_depth: int) -> int:
    """Difficulty 1-5 from line count + sub-recipe depth.

    Heuristic: difficulty = clamp(ingredient_count / 4 + sub_recipe_depth, 1, 5).
    """
    raw = (ingredient_count / 4.0) + sub_recipe_depth
    return max(1, min(5, int(raw + 0.5)))


# ---------------------------------------------------------------------------
# Dietary compatibility
# ---------------------------------------------------------------------------

def infer_recipe_dietary(session: Session, recipe: Recipe) -> set[str]:
    """Recipe is vegan/vegetarian/etc. only if ALL ingredients qualify.

    Returns set of tags. Recipe has no tag if any ingredient disqualifies it.
    """
    ingredients = _recipe_ingredients(session, recipe)
    if not ingredients:
        return set()

    # For each ingredient, determine which categories it disqualifies:
    # - not vegan: contains animal-product keywords
    # - not vegetarian: contains meat/fish (we don't have these in our seed, so
    #   anything with dairy/eggs is still vegetarian)
    # - not gluten_free: contains gluten
    # - not keto_friendly: sugar/flour (sugar-heavy)
    has_animal = False
    has_meat_fish = False  # dairy/eggs OK for vegetarian; meat/fish not.
    has_gluten = False
    has_sugar = False

    animal_keywords = ("leche", "crema", "manteca", "mantequilla", "yogur",
                       "queso", "huevo", "carne", "pollo", "pescado",
                       "dulce de leche")
    meat_fish_keywords = ("carne", "pollo", "pescado", "cerdo", "res",
                          "atún", "marisco")
    gluten_keywords = ("harina", "trigo", "avena", "cebada", "centeno",
                       "malta")
    sugar_keywords = ("azúcar", "miel", "glucosa", "dextrosa", "jarabe",
                      "fécula", "maicena")

    for ing in ingredients:
        n = (ing.name or "").lower()
        if any(kw in n for kw in animal_keywords):
            has_animal = True
        if any(kw in n for kw in meat_fish_keywords):
            has_meat_fish = True
        if any(kw in n for kw in gluten_keywords):
            has_gluten = True
        if any(kw in n for kw in sugar_keywords):
            # stevia is sugar-substitute, allowed for keto
            if "stevia" not in n:
                has_sugar = True

    tags: set[str] = set()
    if not has_meat_fish:
        tags.add("vegetarian")
    if not has_animal:
        tags.add("vegan")
    if not has_gluten:
        tags.add("gluten_free")
    if not has_sugar:
        tags.add("keto_friendly")
    return tags


# ---------------------------------------------------------------------------
# Yield-in-grams + cost-per-gram
# ---------------------------------------------------------------------------

def recipe_yield_grams(recipe: Recipe) -> float | None:
    """Convert yield to grams using yield_unit. None if unit unknown."""
    unit = (recipe.yield_unit or "").lower()
    factor = DEFAULT_YIELD_GRAMS_PER_UNIT.get(unit)
    if factor is None:
        return None
    return float(recipe.yield_qty or 0) * factor


def recipe_cost_per_gram(session: Session, recipe: Recipe) -> float | None:
    """Total batch ingredient cost / yield-in-grams.

    Uses recipe_batch_cost_gs (total batch) divided by yield in grams.
    """
    from app.rms.costing import recipe_batch_cost_gs

    yield_g = recipe_yield_grams(recipe)
    if yield_g is None or yield_g <= 0:
        return None
    batch = recipe_batch_cost_gs(session, recipe.id)
    if batch.batch_cost_gs is None:
        return None
    return float(batch.batch_cost_gs) / yield_g


# ---------------------------------------------------------------------------
# Recipe ingredients helper
# ---------------------------------------------------------------------------

def _recipe_ingredients(session: Session, recipe: Recipe) -> list:
    """Resolve ingredient lines to Ingredient objects."""
    from app.rms.models import Ingredient

    ing_ids = [
        ln.line_ref_id
        for ln in recipe.lines
        if ln.line_kind == "ingredient"
    ]
    if not ing_ids:
        return []
    return list(session.scalars(
        Ingredient.id.in_(ing_ids).select() if False else
        # Use select() for clarity.
        __import__("sqlalchemy").select(Ingredient).where(Ingredient.id.in_(ing_ids))
    ).all())


def recipe_ingredient_count(recipe: Recipe) -> int:
    """Number of distinct ingredient lines (excluding sub-recipes)."""
    return sum(1 for ln in recipe.lines if ln.line_kind == "ingredient")


def recipe_sub_recipe_depth(session: Session, recipe: Recipe, _seen: set | None = None) -> int:
    """Max depth of sub-recipe nesting. Returns 0 if no sub-recipes."""
    if _seen is None:
        _seen = set()
    if recipe.id in _seen:
        return 0
    if len(_seen) > _MAX_RECIPE_DEPTH:
        return 0
    _seen = _seen | {recipe.id}

    sub_recipe_ids = [
        ln.line_ref_id for ln in recipe.lines if ln.line_kind == "sub_recipe"
    ]
    if not sub_recipe_ids:
        return 0

    sub_recipes = session.scalars(
        __import__("sqlalchemy").select(Recipe).where(Recipe.id.in_(sub_recipe_ids))
    ).all()

    return 1 + max(
        (recipe_sub_recipe_depth(session, r, _seen) for r in sub_recipes),
        default=0,
    )


# ---------------------------------------------------------------------------
# classify_recipe — composite result
# ---------------------------------------------------------------------------

def classify_recipe(session: Session, recipe: Recipe) -> dict:
    """Full classification result for one recipe."""
    n_ingredients = recipe_ingredient_count(recipe)
    depth = recipe_sub_recipe_depth(session, recipe)
    return {
        "family": infer_recipe_family(recipe),
        "prep_minutes": estimate_prep_minutes(recipe, n_ingredients),
        "cook_minutes": estimate_cook_minutes(recipe),
        "total_minutes": estimate_prep_minutes(recipe, n_ingredients)
        + estimate_cook_minutes(recipe),
        "difficulty": infer_difficulty(recipe, n_ingredients, depth),
        "dietary_tags": sorted(infer_recipe_dietary(session, recipe)),
        "yield_grams": recipe_yield_grams(recipe),
        "cost_per_gram": recipe_cost_per_gram(session, recipe),
    }


def classify_all_recipes(session: Session) -> dict[int, dict]:
    """Bulk-classify all recipes. Returns {recipe_id: classification}."""
    from app.rms.models import Recipe

    return {r.id: classify_recipe(session, r) for r in session.scalars(
        __import__("sqlalchemy").select(Recipe)
    ).all()}


__all__ = [
    "classify_all_recipes",
    "classify_recipe",
    "estimate_cook_minutes",
    "estimate_prep_minutes",
    "estimate_total_minutes",
    "infer_difficulty",
    "infer_recipe_dietary",
    "infer_recipe_family",
    "recipe_cost_per_gram",
    "recipe_ingredient_count",
    "recipe_sub_recipe_depth",
    "recipe_yield_grams",
]
