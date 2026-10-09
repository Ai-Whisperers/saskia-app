"""app/rms/tagging/classify.py — Pure functions that decide tags/allergens.

All functions are pure (no DB, no I/O, no logging) so they're trivially
unit-testable and reusable from scripts / migrations / tests. They take
Python objects with the relevant attributes (name, allergens, dietary_tags,
may_contain_gluten) and return primitive results.

Public API:
    normalize(tag: str) -> str | None
    normalize_all(raw: str | None) -> frozenset[str]
    infer_allergens(name: str) -> list[str]
    ingredient_blocks(ing: object, tag: str) -> bool
    validate_ingredient(ing: object) -> list[str]
"""

from __future__ import annotations

import re
import unicodedata
from typing import Final

from app.rms.tagging.vocabulary import (
    ALLERGEN_KEYWORDS,
    CANONICAL_DIETARY_TAGS,
    NEUTRAL_INGREDIENT_KEYWORDS,
    TAG_ALIASES,
    TAG_ALLERGEN_BLOCKERS,
)

# -----------------------------------------------------------------------------
# Category inference (moved from app/rms/ingredient_intel.py on 2026-10-09
# to break the bidirectional lazy-import cycle). The data + helper functions
# + infer_category() now live here, where the validate_ingredient() cross-
# validation can use it directly (no lazy import needed). The
# ingredient_intel.py module re-exports these names for backward compat.
# -----------------------------------------------------------------------------

# Category keywords: first match wins. Order matters: more specific
# before general (e.g. "aceite de oliva" must beat "aceite").
_CATEGORY_KEYWORDS: Final[dict[str, tuple[str, ...]]] = {
    "grasas": (
        # Specific first so "manteca vegetal" beats generic "manteca"
        "aceite de oliva",
        "aceite de coco",
        "manteca vegetal",
        "manteca de cerdo",
        "manteca clarificada",
        "aceite",
        "margarina",
        "grasa",
    ),
    "lácteos": (
        "leche",
        "crema",
        "manteca",
        "mantequilla",
        "yogur",
        "queso",
        "queso crema",
        "ricota",
        "requesón",
        "dulce de leche",
        "leche condensada",
        "leche en polvo",
        "crema agria",
    ),
    "harinas": (
        "harina",
        "maicena",
        "fécula",
        "almidón",
        "polenta",
        "mandioca",  # chipa, empanadas
    ),
    "endulzantes": (
        "azúcar impalpable",
        "azúcar glass",
        "azúcar mascabo",
        "azúcar",
        "miel",
        "stevia",
        "dextrosa",
        "glucosa",
        "jarabe",
        "melaza",
        "panela",
        "rapadura",
        "eritritol",
    ),
    "leudantes": (
        "levadura",
        "polvo de hornear",
        "bicarbonato",
        "royal",
        "polvo para hornear",
        "cremor tártaro",
    ),
    "huevos": (
        "huevo",
        "huevos",
        "clara",
        "yema",
    ),
    "carnes": (
        # 2026-09-29: word-boundary issues with substring match — 'res'
        # matched 'fresco' (Jengibre fresco → carnes!). Use word-boundary
        # via the _KEYWORD_BOUNDARY pattern in infer_category instead.
        "carne",
        "pollo",
        "cerdo",
        "pavo",
        "pescado",
        "atún",
        "marisco",
        "pechuga",
        "panceta",
        "chorizo",
        "jamón",
        "res",
    ),
    "decoración": (
        "esencia",
        "ralladura",
        "colorante",
        "glaseado",
        "chocolate cobertura",
        "fondant",
        "sprinkles",
        "cacao",
        "perla",
        "confite",
    ),
    "especias": (
        "canela",
        "pimienta",
        "comino",
        "orégano",
        "pimentón",
        "nuez moscada",
        "clavo",
        "anís",
        "anís estrella",
        "vainilla",
        "vainilla en vaina",
        "extracto de vainilla",
        "jengibre",
        "curry",
        "azafrán",
    ),
    "frutos-secos": (
        "almendra",
        "nuez",
        "nueces",
        "avellana",
        "pistacho",
        "maní",
        "castaña",
        "coco",
    ),
    "frutas": (
        "fruta",
        "frutas",
        "limón",
        "limones",
        "naranja",
        "naranjas",
        "manzana",
        "manzanas",
        "banana",
        "bananas",
        "frutilla",
        "frutillas",
        "arándano",
        "arándanos",
        "ciruela",
        "ciruelas",
        "pera",
        "peras",
        "uva",
        "uvas",
        "frambuesa",
        "frambuesas",
        "cereza",
        "cerezas",
        "ananá",
        "ananás",
        "piña",
        "mango",
        "durazno",
        "duraznos",
        "damasco",
        "damascos",
        "kiwi",
        "melón",
        "sandía",
        "paltas",
        "palta",
    ),
    "líquidos": (
        "agua",
        "jugo",
        "caldo",
        "café",
        "espresso",
        "té",
        "mate",
    ),
    "semillas": (
        "semilla de chía",
        "semilla de lino",
        "semilla de girasol",
    ),
    "otros": (),  # sentinel — anything not matched
}


def _normalize(name: str) -> str:
    """Lowercase + strip + collapse whitespace."""
    return re.sub(r"\s+", " ", name.strip().lower())


def _keyword_in(keyword: str, normalized: str) -> bool:
    """Word-boundary containment for category keywords (2026-09-29).

    The old substring match caused `'res' in 'jengibre fresco'` to be
    True — classifying every ingredient containing 'fresco' as 'carnes'.
    Now keywords need a real token boundary on both sides.

    Multi-word keywords like 'aceite de oliva' still match if the phrase
    appears in the normalized name (the spaces in the keyword already
    act as boundaries for single-keyword sub-checks).
    """
    # Whole-token match: keyword must be at start, end, or surrounded by
    # whitespace, hyphen, slash, or punctuation. Use a small set of
    # word separators so 'café-' doesn't false-match inside 'café-con-leche'.
    pattern = r"(?:^|[\s\-/,.;:])" + re.escape(keyword) + r"(?:$|[\s\-/,.;:])"
    return re.search(pattern, normalized) is not None


def infer_category(name: str) -> str:
    """Return one of the closed category set, or 'otros' if no match."""
    norm = _normalize(name)
    for cat, keywords in _CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if _keyword_in(kw, norm):
                return cat
    return "otros"


# ─────────────────────────────────────────────────────────────────────────
# Normalization
# ─────────────────────────────────────────────────────────────────────────


def normalize(tag: str) -> str | None:
    """Map any common label form to the canonical Spanish tag. Returns
    None for unrecognized / empty input. Single read-boundary normalization
    point — every consumer that reads dietary_tags CSV MUST go through this.

    Recognized sources (case-insensitive, hyphen-tolerant):
      - English:  vegan, vegetarian, gluten_free, sugar_free, keto_friendly, ...
      - snake_case: same as above with underscores
      - Spanish:  vegano, sin gluten, sin tacc, sin lactosa, ...
      - Hyphenated: sin-gluten, sin-tacc, sin-azúcar
      - Unrecognized → None (defensive: caller drops)
    """
    if not tag:
        return None
    key = tag.strip().lower()
    if not key:
        return None
    if key in TAG_ALIASES:
        return TAG_ALIASES[key]
    if key in CANONICAL_DIETARY_TAGS:
        return key
    return None


def normalize_all(raw: str | None) -> frozenset[str]:
    """Normalize a CSV string of tags to a frozenset of canonical tags.

    Drops unrecognized tags silently (defensive against seed/data drift).
    Whitespace-only tags are dropped.
    """
    if not raw:
        return frozenset()
    out: set[str] = set()
    for t in raw.split(","):
        n = normalize(t)
        if n:
            out.add(n)
    return frozenset(out)


def ingredient_dietary_set(ing: object) -> frozenset[str]:
    """Return the canonical dietary tags on an Ingredient (or anything with
    a ``dietary_tags`` attribute).

    Sprint 2.2: lifted from ``app.rms.tag_algebra`` (the now-removed
    back-compat shim). The legacy name ``ingredient_dietary_set`` lives
    here as the canonical implementation; callers should import from
    ``app.rms.tagging`` rather than from the deleted ``tag_algebra``.
    """
    return normalize_all(getattr(ing, "dietary_tags", None))


# ─────────────────────────────────────────────────────────────────────────
# Allergen inference (bootstrap for Ingredient.allergens column)
# ─────────────────────────────────────────────────────────────────────────

_NAME_NORMALIZE_RE = re.compile(r"\s+")


def _normalize_name(name: str) -> str:
    """Lowercase + strip + collapse whitespace + strip accents.

    Accent stripping is essential for Spanish allergen matching:
    `maní` (peanut) and `mani` (Indonesian "sweet") are different words,
    but `maní` should match the Spanish keyword regardless of whether
    the operator typed it with or without accent.
    """
    norm = _NAME_NORMALIZE_RE.sub(" ", name.strip().lower())
    # Decompose accented chars (maní → mani + combining acute), drop the
    # combining marks. This is the canonical Unicode approach (NFD + Mn
    # filter) and handles every Spanish diacritic.
    return "".join(c for c in unicodedata.normalize("NFD", norm) if unicodedata.category(c) != "Mn")


def _keyword_matches(keyword: str, name: str) -> bool:
    """Word-boundary match for a single allergen keyword.

    EXACT-word match (no auto-plural). Operators must list both singular
    and plural forms in vocabulary.ALLERGEN_KEYWORDS if needed.

    Why no auto-plural: distinguishing language collisions.
      - "mani" (Spanish maní / peanut) vs "manis" (Indonesian "sweet")
      - "nuez" vs "nueces" — both are valid Spanish, must be listed
      - "almendra" vs "almendras" — both common, both must be listed

    Returns True if the keyword matches as a complete word (case- and
    accent-insensitive).
    """
    n = name.strip().lower()
    if not n:
        return False
    # Require: word boundary, the keyword, then word boundary.
    # Delimiters: whitespace, hyphen, slash, comma, period, semicolon, colon,
    # underscore (so test ingredient names like "leche_xyz" don't false-match).
    pat = r"(?:^|[\s\-/_,.;:])" + re.escape(keyword) + r"(?:[\s\-/_,.;:]|$)"
    return re.search(pat, n) is not None


def infer_allergens(name: str) -> list[str]:
    """Return sorted list of allergens present in this ingredient name.

    Uses WORD-BOUNDARY matching (not substring) to avoid false positives:

      ✓ "Maní tostado"          → ["nuts"]   (word: mani)
      ✗ "Ketjap Manis"          → []          (word: manis, no "mani" word)
      ✓ "Harina de almendras"   → ["gluten"]  (word: harina; operator's
                                              sin-gluten claim overrides)
      ✓ "Leche descremada"      → ["dairy"]   (word: leche)
      ✓ "Nuez moscada"          → ["nuts"]    (word: nuez)

    Bootstrap helper: when an operator adds a new ingredient without
    filling allergens, we suggest the matches here for them to confirm.
    Never auto-write to Ingredient.allergens — operator's job to verify.
    """
    norm = _normalize_name(name)
    found: list[str] = []
    for allergen, keywords in ALLERGEN_KEYWORDS.items():
        if any(_keyword_matches(kw, norm) for kw in keywords):
            found.append(allergen)
    return sorted(found)


# ─────────────────────────────────────────────────────────────────────────
# Per-ingredient dietary tag inference (English labels — read boundary
# normalizes to Spanish via normalize()). Replaces the old
# ingredient_intel.infer_dietary_tags() implementation; the shim in
# ingredient_intel.py delegates here.
#
# Rules:
#   - meat/fish/poultry present → not vegan, not vegetarian
#   - any other animal product (dairy/eggs/honey) → not vegan, vegetarian OK
#   - no animal product + no honey → vegan
#   - contains wheat/barley/etc → not gluten_free
#   - sugar/flour/syrup → not keto (stevia/erythritol are OK)
# ─────────────────────────────────────────────────────────────────────────

_DAIRY_EGG_HONEY: tuple[str, ...] = (
    "leche",
    "crema",
    "manteca",
    "mantequilla",
    "yogur",
    "queso",
    "queso crema",
    "ricota",
    "requesón",
    "huevo",
    "huevos",
    "clara",
    "yema",
    "dulce de leche",
    "miel",
    "gelatina",
)

_MEAT_FISH: tuple[str, ...] = (
    "carne",
    "pollo",
    "cerdo",
    "res",
    "pavo",
    "pescado",
    "atún",
    "marisco",
    "pechuga",
    "panceta",
    "chorizo",
    "jamón",
)

_SUGAR_FLOUR: tuple[str, ...] = (
    "azúcar",
    "harina",
    "maicena",
    "miel",
    "glucosa",
    "dextrosa",
    "fécula",
    "jarabe",
    "melaza",
    "panela",
    "rapadura",
    "almidón",
    "mandioca",
)

_KETO_SWEETENERS: tuple[str, ...] = ("stevia", "eritritol")


def infer_dietary_tags(name: str) -> list[str]:
    """Return English-form dietary tags this ingredient fits.

    Output: list like ["vegan", "vegetarian", "gluten_free", "keto_friendly"].
    These are auto-suggested; operator confirms in the inventory form.
    The rest of the system normalizes through app.rms.tagging.classify.normalize().
    """
    norm = _normalize_name(name)
    allergens = set(infer_allergens(name))

    tags: list[str] = []

    if any(_keyword_matches(kw, norm) for kw in _MEAT_FISH):
        # meat/fish → not vegan, not vegetarian
        pass
    else:
        tags.append("vegetarian")
        if not any(_keyword_matches(kw, norm) for kw in _DAIRY_EGG_HONEY):
            tags.append("vegan")

    if "gluten" not in allergens:
        tags.append("gluten_free")

    sugar_or_flour = any(_keyword_matches(kw, norm) for kw in _SUGAR_FLOUR)
    is_keto_sweetener = any(_keyword_matches(kw, norm) for kw in _KETO_SWEETENERS)
    if not sugar_or_flour or is_keto_sweetener:
        tags.append("keto_friendly")

    return sorted(tags)


# ─────────────────────────────────────────────────────────────────────────
# Neutral-ingredient check
# ─────────────────────────────────────────────────────────────────────────


def _is_neutral(name: str) -> bool:
    """True if the ingredient is on the explicit neutral allow-list
    (water, salt, common spices, leaveners, oils).

    Match rule: name equals keyword OR starts with keyword + " ".
    So "sal" matches "sal" / "sal gruesa" but not "salsa de soja".
    The trailing-space guard prevents accidental partial matches.
    """
    if not name:
        return False
    n = name.strip().lower()
    return any(n == kw or n.startswith(kw + " ") for kw in NEUTRAL_INGREDIENT_KEYWORDS)


# ─────────────────────────────────────────────────────────────────────────
# Blocking decision (the heart of derive_recipe_tags)
# ─────────────────────────────────────────────────────────────────────────


def ingredient_blocks(ing: object, tag: str) -> bool:
    """True if this ingredient DISQUALIFIES the recipe from `tag`.

    Blocking rules — hierarchical, allergen-driven, dietary_tags is a claim:

    1. **Neutral keywords** — `agua`, `sal`, `hielo`, common spices,
       leaveners never block any tag (they're pantry staples that don't
       disqualify).

    2. **Allergens column populated** → use it as source of truth.
       An ingredient blocks `sin X` if its `allergens` column contains
       any keyword that disqualifies X (per TAG_ALLERGEN_BLOCKERS).
       Example: Harina de trigo has allergens='gluten' → blocks sin_gluten
       and sin_tacc; manteca has allergens='dairy' → blocks sin_lactosa.

    3. **Allergens column empty/null** → fall back to infer_allergens(name)
       heuristic. This handles operators who haven't yet populated the
       allergens column (the UI shows these as "sin declarar").
       Zanahoria has no allergens and no name-keyword matches → does NOT
       block sin_x.  Harina de trigo (no allergens, but name matches
       `trigo`) → blocks sin_gluten.

    4. **sin tacc cross-contamination** — even with empty allergens,
       `may_contain_gluten=True` still blocks `sin tacc` (SINACLA rule for
       shared equipment).

    5. **dietary_tags cross-check** — if the ingredient CLAIMS the tag T
       (e.g. `vegano`, `sin gluten`) in its declared dietary set, that
       claim overrides a heuristic match.  e.g. `Harina de almendras`
       matches the `almendra` nut keyword for infer_allergens, but if it
       declares `sin frutos secos`, trust the claim and don't block.

    6. **Default: don't block.** If neither allergens nor name-heuristic
       yields a disqualifier, the ingredient is treated as not blocking.
       The UI shows it as "sin declarar" so the operator can fill
       inventory. This prevents the broken legacy behavior where carrots
       blocked sin_gluten because their allergens column was simply
       unpopulated.

    Inputs are tolerant of stubs / mocks (uses getattr for everything).
    """
    name = getattr(ing, "name", "") or ""
    if _is_neutral(name):
        return False

    # (4) sin tacc cross-contamination takes priority (operator-set flag).
    if tag == "sin tacc" and getattr(ing, "may_contain_gluten", False):
        return True

    # Resolve which allergens disqualify this tag.
    blockers = TAG_ALLERGEN_BLOCKERS.get(tag, ())
    if not blockers:
        # No allergen-driven rule (e.g. 'integral', 'orgánico' are cert
        # claims; 'vegetariano' depends on meat detection elsewhere).
        return False

    # (2) allergens column is the preferred source of truth.
    allergens_raw = getattr(ing, "allergens", None)
    if allergens_raw:
        allergens = {a.strip().lower() for a in allergens_raw.split(",") if a.strip()}
        return any(b in allergens for b in blockers)

    # (3) Allergens column unpopulated → heuristic from ingredient name.
    inferred = set(infer_allergens(name))
    if any(b in inferred for b in blockers):
        # (5) dietary_tags claim can override a heuristic match.
        declared = normalize_all(getattr(ing, "dietary_tags", None))
        if tag in declared:
            return False
        return True

    # (6) No allergens + no name-heuristic match → don't block.
    #     UI marks the ingredient "sin declarar alérgenos" so the operator
    #     knows to fill inventory.
    return False


# ─────────────────────────────────────────────────────────────────────────
# Internal consistency validation
# ─────────────────────────────────────────────────────────────────────────

# Meat / fish keywords — used by validate_ingredient for vegetarian check.
# Lives here (not vocabulary) because it's a classify-time heuristic.
_MEAT_FISH_KEYWORDS: tuple[str, ...] = (
    "carne",
    "pollo",
    "cerdo",
    "res",
    "pavo",
    "pescado",
    "atún",
    "marisco",
    "pechuga",
    "panceta",
    "chorizo",
    "jamón",
)


def validate_ingredient(ing: object) -> list[str]:
    """Returns list of logical contradictions in an ingredient's tags.

    Empty list = OK. Examples of contradictions:
      - declares 'vegano' but contains dairy/eggs allergens
      - declares 'vegetariano' but name suggests meat/fish
      - declares 'sin gluten' but contains 'gluten' allergen
      - declares 'sin lactosa' but contains 'dairy' allergen

    Called from the audit CLI and from the inventory form before save.
    The Ingredient table has a tag_validation_issues column where these
    are persisted (migration v61).
    """
    issues: list[str] = []

    declared = normalize_all(getattr(ing, "dietary_tags", None))
    allergens_raw = getattr(ing, "allergens", None)
    allergens: set[str] = set()
    if allergens_raw:
        allergens = {a.strip().lower() for a in allergens_raw.split(",") if a.strip()}

    name_lower = (getattr(ing, "name", "") or "").lower()

    # vegan + dairy/eggs allergens
    if "vegano" in declared and (allergens & {"dairy", "eggs"}):
        issues.append("declares 'vegano' but allergens include dairy/eggs")

    # vegetarian + meat/fish in name
    if "vegetariano" in declared:
        # Use word-boundary matching to avoid false positives like
        # 'maní' (peanut) being mistaken for a meat.
        if any(_keyword_matches(kw, name_lower) for kw in _MEAT_FISH_KEYWORDS):
            issues.append("declares 'vegetariano' but name suggests meat/fish")

    # sin gluten + gluten allergen
    if "sin gluten" in declared and "gluten" in allergens:
        issues.append("declares 'sin gluten' but allergens include gluten")

    # sin lactosa + dairy allergen
    if "sin lactosa" in declared and "dairy" in allergens:
        issues.append("declares 'sin lactosa' but allergens include dairy")

    # sin huevo + eggs allergen
    if "sin huevo" in declared and "eggs" in allergens:
        issues.append("declares 'sin huevo' but allergens include eggs")

    # sin frutos secos + nuts allergen
    if "sin frutos secos" in declared and "nuts" in allergens:
        issues.append("declares 'sin frutos secos' but allergens include nuts")

    # sin tacc + gluten allergen (should never happen if sin tacc == sin gluten)
    if "sin tacc" in declared and "gluten" in allergens:
        issues.append("declares 'sin tacc' but allergens include gluten")

    # may_contain_gluten without sin tacc declared — operator forgot to
    # mark this as cross-contaminated; we don't auto-add the tag but warn.
    if getattr(ing, "may_contain_gluten", False) and "sin tacc" in declared:
        issues.append("sin tacc cannot be true when may_contain_gluten is set")

    # Category mismatch (2026-09-29): if the inferred category from the
    # name disagrees with the stored category, surface a warning. The
    # operator may have intentionally miscategorized (e.g. an unusual
    # import), but most often this is a typo (Jengibre fresco → carnes).
    stored_category = (getattr(ing, "category", None) or "").strip().lower()
    if stored_category and stored_category != "otros":
        # 2026-10-09: infer_category now lives in this module (was in
        # ingredient_intel). The cycle is broken; no lazy import needed.
        inferred = infer_category(getattr(ing, "name", "") or "")
        if inferred and inferred != stored_category:
            issues.append(f"category '{stored_category}' may be wrong; name suggests '{inferred}'")

    return issues


__all__ = [
    "infer_allergens",
    "infer_dietary_tags",
    "ingredient_blocks",
    "normalize",
    "normalize_all",
    "validate_ingredient",
]
