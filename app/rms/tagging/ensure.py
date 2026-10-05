"""app/rms/tagging/ensure.py — Tag CRUD + link operations.

Sprint 2.2 of the 2026-10-02 backend overhaul: tags consolidation.

Lifted from ``app/rms/tags.py``. Owns the operational side of tags:
- ensure_tag / ensure_starter_tags / list_tags_for_kind
- tag_target / untag_target / tags_for_target / targets_with_tag

Public API contract unchanged — call sites continue to work with the
same signatures. New code should import from ``app.rms.tagging``.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rms.models import Tag, TagLink
from app.rms.tagging.model import TagKind


# ─── Starter data (the canonical starter-tag catalogue) ────────────────────

# Each tuple is (name, kind, color). Used by ensure_starter_tags + tests.
STARTER_TAGS: list[tuple[str, str, str]] = [
    # ── Products ──────────────────────────────────────────────
    ("vegetariano", TagKind.PRODUCT.value, "#7cb342"),
    ("vegano", TagKind.PRODUCT.value, "#558b2f"),
    ("sin-gluten", TagKind.PRODUCT.value, "#ff9800"),
    ("sin-lactosa", TagKind.PRODUCT.value, "#03a9f4"),
    ("sin-azucar", TagKind.PRODUCT.value, "#e91e63"),
    ("con-nueces", TagKind.PRODUCT.value, "#795548"),
    ("premium", TagKind.PRODUCT.value, "#9c27b0"),
    ("popular", TagKind.PRODUCT.value, "#ffc107"),
    ("festivo", TagKind.PRODUCT.value, "#d32f2f"),
    ("estacional", TagKind.PRODUCT.value, "#009688"),
    ("navidad", TagKind.PRODUCT.value, "#c62828"),
    ("dia-madre", TagKind.PRODUCT.value, "#ad1457"),
    ("verano", TagKind.PRODUCT.value, "#00bcd4"),
    ("requiere-encargo", TagKind.PRODUCT.value, "#5e35b1"),
    ("para-eventos", TagKind.PRODUCT.value, "#3949ab"),
    ("individual", TagKind.PRODUCT.value, "#546e7a"),
    ("docena", TagKind.PRODUCT.value, "#455a64"),
    # ── Ingredients ──────────────────────────────────────────
    ("perecedero", TagKind.INGREDIENT.value, "#ef5350"),
    ("congelable", TagKind.INGREDIENT.value, "#42a5f5"),
    ("seco", TagKind.INGREDIENT.value, "#8d6e63"),
    ("refrigerado", TagKind.INGREDIENT.value, "#26a69a"),
    ("importado", TagKind.INGREDIENT.value, "#7e57c2"),
    ("local", TagKind.INGREDIENT.value, "#66bb6a"),
    ("alergeno-gluten", TagKind.INGREDIENT.value, "#ff7043"),
    ("alergeno-lactosa", TagKind.INGREDIENT.value, "#29b6f6"),
    ("alergeno-frutos-secos", TagKind.INGREDIENT.value, "#8d6e63"),
    ("precio-volatil", TagKind.INGREDIENT.value, "#ffa726"),
    ("organico", TagKind.INGREDIENT.value, "#9ccc65"),
    # ── Recipes ──────────────────────────────────────────────
    ("sub-receta", TagKind.RECIPE.value, "#7e57c2"),
    ("temporada", TagKind.RECIPE.value, "#43a047"),
    ("alto-costo", TagKind.RECIPE.value, "#b71c1c"),
]


# ─── CRUD ──────────────────────────────────────────────────────────────────


def ensure_tag(session: Session, name: str, kind: str, color: str = "#757575") -> Tag:
    """Return the Tag row, creating if needed.

    Idempotent: looks up by (name, kind) and reuses.
    """
    tag = session.execute(
        select(Tag).where(Tag.name == name, Tag.kind == kind)
    ).scalar_one_or_none()
    if tag is not None:
        return tag
    tag = Tag(name=name, kind=kind, color=color)
    session.add(tag)
    session.flush()
    return tag


def ensure_starter_tags(session: Session) -> list[Tag]:
    """Insert all STARTER_TAGS if missing. Idempotent — safe to call on every boot."""
    out: list[Tag] = []
    for name, kind, color in STARTER_TAGS:
        out.append(ensure_tag(session, name, kind, color))
    return out


def list_tags_for_kind(session: Session, kind: str) -> list[Tag]:
    """Return all Tag rows for a given kind (product|ingredient|recipe).

    Used by templates that need to render tag pills dynamically. Sort
    order: alphabetical by name.
    """
    return list(
        session.execute(
            select(Tag)
            .where(Tag.kind == kind)
            .order_by(Tag.name)
        ).scalars()
    )


# ─── Tag-link operations ───────────────────────────────────────────────────


def tag_target(
    session: Session, tag: Tag, target_kind: str, target_id: int
) -> TagLink:
    """Add a tag to a target. Idempotent."""
    existing = session.execute(
        select(TagLink).where(
            TagLink.tag_id == tag.id,
            TagLink.target_kind == target_kind,
            TagLink.target_id == target_id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    link = TagLink(tag_id=tag.id, target_kind=target_kind, target_id=target_id)
    session.add(link)
    session.flush()
    return link


def untag_target(
    session: Session, tag: Tag, target_kind: str, target_id: int
) -> bool:
    """Remove a tag from a target. Returns True if a row was deleted."""
    link = session.execute(
        select(TagLink).where(
            TagLink.tag_id == tag.id,
            TagLink.target_kind == target_kind,
            TagLink.target_id == target_id,
        )
    ).scalar_one_or_none()
    if link is None:
        return False
    session.delete(link)
    session.flush()
    return True


def tags_for_target(
    session: Session, target_kind: str, target_id: int
) -> list[Tag]:
    """Return all Tag rows attached to a given target (alphabetical)."""
    return list(
        session.execute(
            select(Tag)
            .join(TagLink, TagLink.tag_id == Tag.id)
            .where(
                TagLink.target_kind == target_kind,
                TagLink.target_id == target_id,
            )
            .order_by(Tag.name)
        ).scalars()
    )


def targets_with_tag(session: Session, tag: Tag) -> list[int]:
    """Return all target_ids that have this tag."""
    return list(
        session.execute(
            select(TagLink.target_id).where(
                TagLink.tag_id == tag.id,
                TagLink.target_kind == tag.kind,
            )
        ).scalars()
    )


__all__ = [
    "STARTER_TAGS",
    "ensure_starter_tags",
    "ensure_tag",
    "list_tags_for_kind",
    "tag_target",
    "tags_for_target",
    "targets_with_tag",
    "untag_target",
]