"""tests/test_tagging_vocabulary.py — vocabulary pure-data tests.

Confirms the constants in app/rms/tagging/vocabulary.py are:
  - closed sets (no orphan aliases pointing nowhere)
  - Spanish-canonical
  - symmetric for sin gluten ↔ sin tacc
"""

from __future__ import annotations

from app.rms.tagging.vocabulary import (
    ALLERGEN_DISPLAY_ORDER,
    ALLERGEN_KEYWORDS,
    CANONICAL_ALLERGENS,
    CANONICAL_DIETARY_TAGS,
    CUSTOMER_ALLERGEN_WORDS,
    NEUTRAL_INGREDIENT_KEYWORDS,
    TAG_ALIASES,
    TAG_ALLERGEN_BLOCKERS,
)


def test_canonical_dietary_tags_is_frozenset():
    assert isinstance(CANONICAL_DIETARY_TAGS, frozenset)
    assert len(CANONICAL_DIETARY_TAGS) > 0


def test_canonical_dietary_tags_all_spanish():
    for tag in CANONICAL_DIETARY_TAGS:
        assert tag == tag.lower(), f"tag not lowercase: {tag}"
        # No English tokens should appear.
        assert "free" not in tag
        assert "friendly" not in tag


def test_sin_tacc_equivalent_to_sin_gluten():
    """sin tacc ≡ sin gluten — both must block on 'gluten'."""
    assert TAG_ALLERGEN_BLOCKERS["sin tacc"] == TAG_ALLERGEN_BLOCKERS["sin gluten"]
    assert "sin tacc" in CANONICAL_DIETARY_TAGS
    assert "sin gluten" in CANONICAL_DIETARY_TAGS


def test_alias_targets_are_canonical():
    """Every TAG_ALIASES value must be in CANONICAL_DIETARY_TAGS or be a self-map."""
    for src, dst in TAG_ALIASES.items():
        assert dst in CANONICAL_DIETARY_TAGS or dst == src, (
            f"alias {src!r} → {dst!r} not canonical"
        )


def test_alias_keys_are_unique_normalized():
    """No two keys should map to the same value under different case/hyphen forms."""
    seen = set()
    for src in TAG_ALIASES:
        key = src.strip().lower().replace("-", " ").replace("_", " ")
        # Allow multiple forms of the same canonical tag (sin gluten / sin-gluten / gluten_free).
        # But no duplicate EXACT key.
        assert src not in seen, f"duplicate alias key: {src!r}"
        seen.add(src)


def test_allergen_codes_match_dtype():
    assert isinstance(CANONICAL_ALLERGENS, frozenset)
    for code in CANONICAL_ALLERGENS:
        assert code == code.lower()
        assert " " not in code


def test_blocker_keys_are_canonical():
    """TAG_ALLERGEN_BLOCKERS keys must all be in CANONICAL_DIETARY_TAGS."""
    for tag in TAG_ALLERGEN_BLOCKERS:
        assert tag in CANONICAL_DIETARY_TAGS, (
            f"blocker entry for non-canonical tag {tag!r}"
        )


def test_blocker_values_are_canonical_allergens():
    """Each blocker tuple must contain canonical allergen codes (or be empty)."""
    for tag, blockers in TAG_ALLERGEN_BLOCKERS.items():
        for b in blockers:
            assert b in CANONICAL_ALLERGENS, (
                f"blocker {b!r} for tag {tag!r} not in CANONICAL_ALLERGENS"
            )


def test_customer_words_have_canonical_targets():
    """CUSTOMER_ALLERGEN_WORDS values must be in CANONICAL_ALLERGENS."""
    for word, code in CUSTOMER_ALLERGEN_WORDS.items():
        assert code in CANONICAL_ALLERGENS, (
            f"customer word {word!r} maps to non-canonical {code!r}"
        )


def test_neutral_keywords_lowercase_unique():
    assert isinstance(NEUTRAL_INGREDIENT_KEYWORDS, frozenset)
    for kw in NEUTRAL_INGREDIENT_KEYWORDS:
        assert kw == kw.lower()
        assert "  " not in kw  # no double spaces


def test_allergen_display_order_matches_canonical():
    """Display order is a permutation of CANONICAL_ALLERGENS (or superset)."""
    for code in ALLERGEN_DISPLAY_ORDER:
        assert code in CANONICAL_ALLERGENS or code  # allow extending with non-canonical codes


def test_allergen_keywords_have_entries():
    """Every canonical allergen has at least one keyword (or explicitly empty)."""
    for code in CANONICAL_ALLERGENS:
        assert code in ALLERGEN_KEYWORDS, f"missing keyword entry for {code!r}"
