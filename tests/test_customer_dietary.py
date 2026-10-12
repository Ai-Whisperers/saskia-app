"""tests/test_customer_dietary.py — Test app/rms/customer_dietary.py (Phase 4.5).

The module parses and serializes customer dietary profile columns:
  - restrictions_raw: CSV of canonical dietary tags
  - preferences_raw: JSON list of {tag, rank, note}
  - confirm_always: bool

Functions tested:
  - parse_restrictions(raw) / format_restrictions(tags)
  - parse_preferences(raw) / format_preferences(prefs)
  - load_profile(...)
  - is_canonical_tag(tag)
  - DietaryProfile.has_alerts property

A regression here would either:
  - Crash the order page when a customer has restrictions (CSV
    with whitespace) — could mean an order is taken WITHOUT the
    red warning showing
  - Drop the customer's preference order (serves "leche de coco"
    before "leche de almendra")
  - Treat confirm_always truthy as False (skip the required prompt)
"""

from __future__ import annotations

import json

import pytest

from app.rms.customer_dietary import (
    DietaryPreference,
    DietaryProfile,
    format_preferences,
    format_restrictions,
    is_canonical_tag,
    load_profile,
    parse_preferences,
    parse_restrictions,
)


class TestParseRestrictions:
    def test_empty_returns_empty_list(self):
        assert parse_restrictions(None) == []
        assert parse_restrictions("") == []

    def test_single_tag(self):
        assert parse_restrictions("vegano") == ["vegano"]

    def test_csv_with_whitespace(self):
        # Whitespace is trimmed — sloppy operator input must not break parsing.
        assert parse_restrictions("vegano, sin_gluten , vegano") == [
            "vegano",
            "sin_gluten",
        ]

    def test_dedupes(self):
        assert parse_restrictions("vegano,vegano,vegano") == ["vegano"]

    def test_preserves_order(self):
        # The first occurrence wins — operators read this top-to-bottom in
        # the warning panel.
        assert parse_restrictions("sin_gluten,vegano") == ["sin_gluten", "vegano"]

    def test_unknown_tags_pass_through(self):
        # Vocabulary may evolve; newer tags are not rejected.
        assert parse_restrictions("brand_new_tag") == ["brand_new_tag"]

    def test_empty_tokens_skipped(self):
        assert parse_restrictions(",,vegano,,") == ["vegano"]


class TestFormatRestrictions:
    def test_empty_list(self):
        assert format_restrictions([]) == ""

    def test_single(self):
        assert format_restrictions(["vegano"]) == "vegano"

    def test_multiple(self):
        assert format_restrictions(["vegano", "sin_gluten"]) == "vegano,sin_gluten"

    def test_roundtrip(self):
        original = ["vegano", "sin_gluten", "vegano"]  # contains dup
        rt = parse_restrictions(format_restrictions(original))
        # Round-trip is lossless on deduped set, but format doesn't dedupe
        # (it just re-joins). Caller dedupes on parse.
        assert rt == ["vegano", "sin_gluten"]


class TestParsePreferences:
    def test_empty_returns_empty(self):
        assert parse_preferences(None) == []
        assert parse_preferences("") == []

    def test_invalid_json_returns_empty(self):
        # Garbage in → empty out (fail-soft, not crash).
        assert parse_preferences("{not json}") == []
        assert parse_preferences("[]") == []  # valid empty

    def test_non_list_returns_empty(self):
        # "dict" instead of "list" is a schema violation — fail-soft.
        assert parse_preferences(json.dumps({"tag": "almendra"})) == []

    def test_single_preference(self):
        raw = json.dumps([{"tag": "leche_almendra", "rank": 1, "note": "marca X"}])
        prefs = parse_preferences(raw)
        assert len(prefs) == 1
        assert prefs[0].tag == "leche_almendra"
        assert prefs[0].rank == 1
        assert prefs[0].note == "marca X"

    def test_ranks_are_sorted(self):
        # Input is unordered; output is sorted by rank ascending.
        raw = json.dumps(
            [
                {"tag": "coco", "rank": 3, "note": ""},
                {"tag": "almendra", "rank": 1, "note": ""},
                {"tag": "avena", "rank": 2, "note": ""},
            ]
        )
        prefs = parse_preferences(raw)
        assert [p.tag for p in prefs] == ["almendra", "avena", "coco"]

    def test_missing_rank_defaults_to_position(self):
        # rank omitted → 1-based position in input array
        raw = json.dumps(
            [
                {"tag": "first", "note": "no rank"},
                {"tag": "second", "note": "no rank"},
            ]
        )
        prefs = parse_preferences(raw)
        assert [p.rank for p in prefs] == [1, 2]

    def test_invalid_rank_falls_back_to_position(self):
        raw = json.dumps(
            [
                {"tag": "first", "rank": "not a number"},
                {"tag": "second"},
            ]
        )
        prefs = parse_preferences(raw)
        assert [p.rank for p in prefs] == [1, 2]

    def test_non_dict_items_skipped(self):
        # Mixed valid/invalid: only valid dicts are kept.
        raw = json.dumps(
            [
                {"tag": "valid", "rank": 1},
                "not a dict",
                42,
                None,
                {"tag": "also_valid", "rank": 2},
            ]
        )
        prefs = parse_preferences(raw)
        assert [p.tag for p in prefs] == ["valid", "also_valid"]

    def test_empty_tag_items_skipped(self):
        raw = json.dumps(
            [
                {"tag": "", "rank": 1},
                {"tag": "   ", "rank": 2},  # whitespace-only → empty after strip
                {"tag": "valid", "rank": 3},
            ]
        )
        prefs = parse_preferences(raw)
        assert [p.tag for p in prefs] == ["valid"]

    def test_tag_and_note_are_stripped(self):
        raw = json.dumps([{"tag": "  coco  ", "rank": 1, "note": "  marca  "}])
        prefs = parse_preferences(raw)
        assert prefs[0].tag == "coco"
        assert prefs[0].note == "marca"


class TestFormatPreferences:
    def test_empty(self):
        assert format_preferences([]) == "[]"

    def test_single(self):
        prefs = [DietaryPreference(tag="coco", rank=1, note="marca X")]
        out = json.loads(format_preferences(prefs))
        assert out == [{"tag": "coco", "rank": 1, "note": "marca X"}]

    def test_unicode_preserved(self):
        prefs = [DietaryPreference(tag="leche_almendra", rank=1, note="marca ñoño")]
        out = format_preferences(prefs)
        # ensure_ascii=False → utf-8, not \u escapes
        assert "ñ" in out

    def test_roundtrip(self):
        original = [
            DietaryPreference(tag="almendra", rank=1, note="A"),
            DietaryPreference(tag="coco", rank=2, note="B"),
        ]
        rt = parse_preferences(format_preferences(original))
        assert [(p.tag, p.rank, p.note) for p in rt] == [
            ("almendra", 1, "A"),
            ("coco", 2, "B"),
        ]


class TestLoadProfile:
    def test_all_empty(self):
        p = load_profile(None, None, None)
        assert p.restrictions == []
        assert p.preferences == []
        assert p.confirm_always is False

    def test_full_profile(self):
        restrictions = "vegano,sin_gluten"
        preferences = json.dumps([{"tag": "almendra", "rank": 1, "note": ""}])
        p = load_profile(restrictions, preferences, True)
        assert p.restrictions == ["vegano", "sin_gluten"]
        assert len(p.preferences) == 1
        assert p.preferences[0].tag == "almendra"
        assert p.confirm_always is True

    def test_confirm_always_coerces_truthy(self):
        # DB sometimes returns 0/1 instead of True/False. Coerce to bool.
        p = load_profile(None, None, 1)
        assert p.confirm_always is True
        p = load_profile(None, None, 0)
        assert p.confirm_always is False


class TestIsCanonicalTag:
    def test_canonical_tags(self):
        assert is_canonical_tag("vegano") is True
        assert is_canonical_tag("sin gluten") is True

    def test_case_insensitive(self):
        # Vocabulary is lowercase; uppercase must still match.
        assert is_canonical_tag("Vegano") is True
        assert is_canonical_tag("VEGANO") is True

    def test_whitespace_tolerated(self):
        assert is_canonical_tag("  vegano  ") is True

    def test_unknown_tag(self):
        assert is_canonical_tag("not_a_real_tag") is False
        assert is_canonical_tag("") is False


class TestDietaryProfile:
    def test_defaults(self):
        p = DietaryProfile()
        assert p.restrictions == []
        assert p.preferences == []
        assert p.confirm_always is False

    def test_has_alerts_false_when_empty(self):
        p = DietaryProfile()
        assert p.has_alerts is False

    def test_has_alerts_true_with_restrictions(self):
        p = DietaryProfile(restrictions=["vegano"])
        assert p.has_alerts is True

    def test_has_alerts_true_with_preferences(self):
        p = DietaryProfile(preferences=[DietaryPreference(tag="almendra", rank=1)])
        assert p.has_alerts is True
