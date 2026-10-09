"""Migration 115 — Allergen / DietaryTag catalog tables (Batch C, 2026-10-08).

Replaces hardcoded tag lists in ``app/templates/inventario_form.html``:

  - _codes = [("gluten","Gluten"), ("dairy","Lácteos"), ...]     (allergens)
  - _dtags = [("vegan","Vegano"), ("vegetarian","Vegetariano"), ...] (dietary tags)

Each list becomes a real catalog table that operators can edit from
``/settings/catalog`` without a code deploy.

Two tables:
  - ``allergen`` — controlled substance declarations (must be globally stable
    since they're regulated terms in many jurisdictions, but operator can
    still add / disable).
  - ``dietary_tag`` — marketing-friendly labels ("Vegano", "Keto") that
    operators care more about.

Both seeded from the prior hardcoded values to preserve behavior. Seed only
happens when the table is empty (idempotent).

This is Batch C Tier 1 (real SQL table with FK hygiene, seed defaults).
Tight coupling with the existing ``allergens`` / ``dietary_tags`` columns
on Ingredient / Product — those store the *code* (e.g. ``"gluten"``) as a
comma-separated text. The catalog table is the human-readable label +
sort order source.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

# Seed values match the prior hardcoded lists (preserves behavior).
_DEFAULT_ALLERGENS = [
    ("gluten", "Gluten", 1),
    ("dairy", "Lácteos", 2),
    ("eggs", "Huevos", 3),
    ("nuts", "Frutos secos", 4),
    ("soy", "Soja", 5),
    ("sesame", "Sésamo", 6),
    ("sulfites", "Sulfitos", 7),
]

_DEFAULT_DIETARY_TAGS = [
    ("vegan", "Vegano", 1),
    ("vegetarian", "Vegetariano", 2),
    ("gluten_free", "Sin gluten", 3),
    ("sugar_free", "Sin azúcar", 4),
    ("keto_friendly", "Keto", 5),
    ("high_protein", "Alto en proteína", 6),
]


def _migration_115_allergen_dietary_tags(conn: Any) -> None:
    """Batch C (2026-10-08) — T1 catalog tables for allergens + dietary tags.

    Schema:
      - allergen: id, code (unique stable identifier), label, sort_order,
        is_active, updated_at
      - dietary_tag: id, code (unique), label, sort_order, is_active, updated_at

    Notes:
      - ``code`` is the stable identifier that gets stored on
        Ingredient.allergens / dietary_tags as a comma-separated string.
        Renaming labels does NOT break the data; renaming codes would.
      - ``sort_order`` lets operators reorder the chip UI.
      - ``is_active`` is a soft-delete flag — never hard-delete a code
        that may appear in existing rows.

    Local import to avoid circular dependency: this migration file is
    imported by ``app.rms.db`` at module load time.

    Idempotent: CREATE TABLE IF NOT EXISTS; seed only when empty.
    """
    from app.rms.db import _bump_schema_version

    # allergen table
    conn.execute(
        text(
            """
        CREATE TABLE IF NOT EXISTS allergen (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code VARCHAR(32) NOT NULL UNIQUE,
            label VARCHAR(64) NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 100,
            is_active INTEGER NOT NULL DEFAULT 1,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
        )
    )
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_allergen_sort ON allergen(sort_order)"))

    # dietary_tag table
    conn.execute(
        text(
            """
        CREATE TABLE IF NOT EXISTS dietary_tag (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code VARCHAR(32) NOT NULL UNIQUE,
            label VARCHAR(64) NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 100,
            is_active BOOLEAN NOT NULL DEFAULT 1,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
        )
    )
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_dietary_tag_sort ON dietary_tag(sort_order)"))

    # Seed allergens only if empty (idempotent — does not overwrite operator edits)
    existing = conn.execute(text("SELECT COUNT(*) FROM allergen")).scalar()
    if not existing:
        for code, label, sort_order in _DEFAULT_ALLERGENS:
            conn.execute(
                text(
                    """
                INSERT INTO allergen (code, label, sort_order, is_active)
                VALUES (:code, :label, :sort_order, 1)
                """
                ),
                {"code": code, "label": label, "sort_order": sort_order},
            )

    # Seed dietary tags only if empty
    existing = conn.execute(text("SELECT COUNT(*) FROM dietary_tag")).scalar()
    if not existing:
        for code, label, sort_order in _DEFAULT_DIETARY_TAGS:
            conn.execute(
                text(
                    """
                INSERT INTO dietary_tag (code, label, sort_order, is_active)
                VALUES (:code, :label, :sort_order, 1)
                """
                ),
                {"code": code, "label": label, "sort_order": sort_order},
            )

    # Bump schema version per convention — each migration owns its bump.
    _bump_schema_version(conn, 115)
