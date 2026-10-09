"""app/rms/tagging/model.py — Tag entity types.

Sprint 2.2 of the 2026-10-02 backend overhaul: tags consolidation.

Single source of truth for tag entity types (``TagKind`` enum) — the
enum was previously defined in ``app/rms/tags.py``. The SQLAlchemy
``Tag`` / ``TagLink`` classes live in ``app/rms/models.py`` (they're
heavy ORM entities; moving them would require touching dozens of files).
This module only owns the lightweight enum + helpers.
"""

from __future__ import annotations

from enum import Enum


class TagKind(str, Enum):
    """Tag targets (the entity type a Tag can attach to).

    Used by ``ensure_tag`` and the listings filters to scope queries.
    """

    PRODUCT = "product"
    INGREDIENT = "ingredient"
    RECIPE = "recipe"


__all__ = ["TagKind"]
