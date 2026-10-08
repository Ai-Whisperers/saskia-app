"""Batch C (2026-10-08) tests for allergen + dietary_tag catalogs.

Covers:
  - Migration creates both tables
  - Defaults are seeded exactly once (idempotent on re-run)
  - list_allergens / list_dietary_tags return sort_order ordering
  - Helpers return code/label pairs (UI-friendly shape)
  - Operator can add a new allergen / dietary tag and the helper sees it
  - Operator can mark one inactive and ``include_inactive=False`` filters it out
  - Codes default to canonical set (match the prior hardcoded lists)
  - Falls back to default list when the catalog table doesn't exist
"""

from __future__ import annotations

from sqlalchemy import text

from app.rms.catalogs_tags import (
    allergen_codes,
    dietary_tag_codes,
    list_allergens,
    list_dietary_tags,
)

# Canonical defaults — must match the prior hardcoded lists in inventario_form.html.
CANONICAL_ALLERGENS = {
    "gluten", "dairy", "eggs", "nuts", "soy", "sesame", "sulfites",
}
CANONICAL_DIETARY_TAGS = {
    "vegan", "vegetarian", "gluten_free", "sugar_free",
    "keto_friendly", "high_protein",
}


class TestCatalogSeed:
    """Migration 115 should create + seed both tables."""

    def test_allergen_table_exists(self, app_engine):
        with app_engine.connect() as conn:
            rows = conn.execute(
                text("SELECT COUNT(*) FROM allergen")
            ).scalar()
        assert rows == 7, f"Expected 7 seeded allergens, got {rows}"

    def test_dietary_tag_table_exists(self, app_engine):
        with app_engine.connect() as conn:
            rows = conn.execute(
                text("SELECT COUNT(*) FROM dietary_tag")
            ).scalar()
        assert rows == 6, f"Expected 6 seeded dietary tags, got {rows}"

    def test_seed_runs_only_when_empty(self, app_engine):
        """Inserting an extra row must survive a re-run (NOT auto-overwritten)."""
        with app_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO allergen (code, label, sort_order) "
                    "VALUES ('shellfish','Mariscos', 99)"
                )
            )
            before = conn.execute(
                text("SELECT COUNT(*) FROM allergen")
            ).scalar()
            assert before == 8, "Extra row should be there before re-run"
        # Simulate migration re-run — idempotency lives in the seed-when-empty gate.
        from app.rms.migrations._115_allergen_dietary_tags import (
            _migration_115_allergen_dietary_tags,
        )
        with app_engine.begin() as conn:
            _migration_115_allergen_dietary_tags(conn)
            after = conn.execute(
                text("SELECT COUNT(*) FROM allergen")
            ).scalar()
        assert after == 8, f"Re-running migration clobbered operator data (got {after})"


class TestHelperAPI:
    """list_allergens / list_dietary_tags + helper functions."""

    def test_list_allergens_returns_sort_order(self, session_factory):
        with session_factory() as s:
            entries = list_allergens(s)
        codes = [e.code for e in entries]
        # Sort order from migration: gluten=1, dairy=2, eggs=3, etc.
        assert codes == [
            "gluten", "dairy", "eggs", "nuts", "soy", "sesame", "sulfites",
        ]

    def test_list_dietary_tags_returns_sort_order(self, session_factory):
        with session_factory() as s:
            entries = list_dietary_tags(s)
        codes = [e.code for e in entries]
        assert codes == [
            "vegan", "vegetarian", "gluten_free",
            "sugar_free", "keto_friendly", "high_protein",
        ]

    def test_entries_have_code_and_label(self, session_factory):
        with session_factory() as s:
            entries = list_allergens(s)
        for e in entries:
            assert e.code and e.label, f"Entry missing code/label: {e}"
            assert isinstance(e.is_active, bool)
            assert e.is_active is True

    def test_codes_helper_returns_set(self, session_factory):
        with session_factory() as s:
            al = set(allergen_codes(s))
            dt = set(dietary_tag_codes(s))
        assert al == CANONICAL_ALLERGENS
        assert dt == CANONICAL_DIETARY_TAGS


class TestOperatorEdits:
    """Operators can add or hide entries from the catalog."""

    def test_operator_can_add_allergen(self, session_factory):
        with session_factory() as s:
            s.execute(
                text(
                    "INSERT INTO allergen (code, label, sort_order) "
                    "VALUES ('shellfish','Mariscos', 8)"
                )
            )
            s.commit()
            codes = allergen_codes(s)
        assert "shellfish" in codes
        assert "mariscos" not in [c.lower() for c in codes]
        # Sort order: new allergen comes after the seeded ones (sort_order 8 > 7).
        with session_factory() as s:
            entries = list_allergens(s)
        codes_ordered = [e.code for e in entries]
        assert codes_ordered[-1] == "shellfish"

    def test_operator_can_add_dietary_tag(self, session_factory):
        with session_factory() as s:
            s.execute(
                text(
                    "INSERT INTO dietary_tag (code, label, sort_order) "
                    "VALUES ('organic','Orgánico', 7)"
                )
            )
            s.commit()
        with session_factory() as s:
            codes = dietary_tag_codes(s)
        assert "organic" in codes

    def test_inactive_allergen_excluded_by_default(self, session_factory):
        with session_factory() as s:
            s.execute(
                text("UPDATE allergen SET is_active = 0 WHERE code = 'sesame'")
            )
            s.commit()
            visible = allergen_codes(s)
        assert "sesame" not in visible

    def test_inactive_allergen_included_when_requested(self, session_factory):
        with session_factory() as s:
            s.execute(
                text("UPDATE allergen SET is_active = 0 WHERE code = 'sesame'")
            )
            s.commit()
            visible = allergen_codes(s)
            all_visible = [t.code for t in list_allergens(s, include_inactive=True)]
        assert "sesame" not in visible
        assert "sesame" in all_visible


class TestBackwardsCompatibility:
    """The pre-migration shape (hardcoded list) must still work."""

    def test_fallback_helpers_return_canonical_set(self, app_engine):
        """When called against a DB where the table doesn't exist, helpers
        return the fallback list (preserving prior hardcoded behavior)."""
        # Use a fresh in-memory-style approach: drop the tables, rebuild from
        # a session that hit a ``DROP TABLE`` and then call the helper.
        with app_engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS allergen"))
            conn.execute(text("DROP TABLE IF EXISTS dietary_tag"))
        from app.rms.db import make_session_factory
        factory = make_session_factory(app_engine)
        with factory() as s:
            al = allergen_codes(s)
            dt = dietary_tag_codes(s)
        # Restore the tables (so subsequent tests work).
        from app.rms.migrations._115_allergen_dietary_tags import (
            _migration_115_allergen_dietary_tags,
        )
        with app_engine.begin() as conn:
            _migration_115_allergen_dietary_tags(conn)
        assert set(al) == CANONICAL_ALLERGENS
        assert set(dt) == CANONICAL_DIETARY_TAGS


class TestCatalogSortedByCode:
    """Within the same sort_order, code is the tiebreaker."""

    def test_sort_order_then_code(self, session_factory):
        # Add two allergens with the same sort_order
        with session_factory() as s:
            s.execute(
                text(
                    "INSERT INTO allergen (code, label, sort_order) "
                    "VALUES ('zinc','Zinc', 50)"
                )
            )
            s.execute(
                text(
                    "INSERT INTO allergen (code, label, sort_order) "
                    "VALUES ('apple','Manzana', 50)"
                )
            )
            s.commit()
            entries = list_allergens(s)
        # Both have sort_order=50, so 'apple' < 'zinc' alphabetically.
        custom = [e.code for e in entries if e.sort_order == 50]
        assert custom == ["apple", "zinc"]
