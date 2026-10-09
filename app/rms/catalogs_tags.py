"""app/rms/catalogs_tags.py — Batch C (2026-10-08) helpers for Allergen + DietaryTag lists.

Replaces the hardcoded ``_codes`` / ``_dtags`` lists in
``app/templates/inventario_form.html``. Operators can edit labels and
reorder from ``/settings/catalog`` without a code deploy.

These tables back the chip-toggle-groups on the Ingredient form. The
stable ``code`` column matches the comma-separated codes stored on
Ingredient.allergens / dietary_tags, so renaming a label never breaks
existing data, only the chip-toggle UI updates.

We use raw ``text()`` queries (no ORM) to stay consistent with the
migrations, which also use raw DDL — adding full ORM models for two
small helper tables would be overkill and wouldn't unlock any feature
that an index lookup doesn't.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class TagEntry:
    """A single row from ``allergen`` or ``dietary_tag``."""

    id: int
    code: str
    label: str
    sort_order: int
    is_active: bool


def list_allergens(session: Session, include_inactive: bool = False) -> list[TagEntry]:
    """Return active allergens sorted by sort_order (then code).

    Falls back to the prior hardcoded list when the table is empty or
    missing — keeps tests deterministic and lets pages render before
    the migration runs.
    """
    try:
        sql = (  # noqa: S608
            """
            SELECT id, code, label, sort_order, is_active
            FROM allergen
            {where_clause}
            ORDER BY sort_order ASC, code ASC
            """
        ).format(where_clause="" if include_inactive else "WHERE is_active = 1")
        rows = session.execute(text(sql)).fetchall()
    except Exception:
        # Table doesn't exist yet (pre-migration) — fall through to defaults.
        rows = []

    if rows:
        return [
            TagEntry(
                id=r[0],
                code=r[1],
                label=r[2],
                sort_order=r[3],
                is_active=bool(r[4]),
            )
            for r in rows
        ]

    # Fallback when catalog is empty (either pre-migration or operator
    # cleared everything — we still need *some* defaults to render).
    return [
        TagEntry(0, code, label, sort_order, True)
        for (code, label, sort_order) in _FALLBACK_ALLERGENS
    ]


def list_dietary_tags(session: Session, include_inactive: bool = False) -> list[TagEntry]:
    """Return active dietary tags sorted by sort_order (then code)."""
    try:
        sql = (  # noqa: S608
            """
            SELECT id, code, label, sort_order, is_active
            FROM dietary_tag
            {where_clause}
            ORDER BY sort_order ASC, code ASC
            """
        ).format(where_clause="" if include_inactive else "WHERE is_active = 1")
        rows = session.execute(text(sql)).fetchall()
    except Exception:
        rows = []

    if rows:
        return [
            TagEntry(
                id=r[0],
                code=r[1],
                label=r[2],
                sort_order=r[3],
                is_active=bool(r[4]),
            )
            for r in rows
        ]

    return [
        TagEntry(0, code, label, sort_order, True)
        for (code, label, sort_order) in _FALLBACK_DIETARY_TAGS
    ]


def allergen_codes(session: Session) -> list[str]:
    """Return just the codes — useful for validation."""
    return [t.code for t in list_allergens(session)]


def dietary_tag_codes(session: Session) -> list[str]:
    """Return just the codes — useful for validation."""
    return [t.code for t in list_dietary_tags(session)]


# Fallback lists preserve the prior hardcoded behavior exactly when the
# catalog is empty or the migration hasn't run yet. These mirror the seed
# data in app/rms/migrations/_115_allergen_dietary_tags.py.
_FALLBACK_ALLERGENS = [
    ("gluten", "Gluten", 1),
    ("dairy", "Lácteos", 2),
    ("eggs", "Huevos", 3),
    ("nuts", "Frutos secos", 4),
    ("soy", "Soja", 5),
    ("sesame", "Sésamo", 6),
    ("sulfites", "Sulfitos", 7),
]

_FALLBACK_DIETARY_TAGS = [
    ("vegan", "Vegano", 1),
    ("vegetarian", "Vegetariano", 2),
    ("gluten_free", "Sin gluten", 3),
    ("sugar_free", "Sin azúcar", 4),
    ("keto_friendly", "Keto", 5),
    ("high_protein", "Alto en proteína", 6),
]


__all__ = [
    "TagEntry",
    "allergen_codes",
    "dietary_tag_codes",
    "list_allergens",
    "list_dietary_tags",
]
