"""app/rms/categories.py — Category catalog (operator-configurable).

Phase 1 of the static-content audit (docs/operations/2026-09-24-static-content-audit.md).

Replaces the hardcoded lists previously in:
- app/templates/_components/tags.html (product_category_options, recipe_family_options)
- app/templates/receta_form.html (the duplicated family list)

Now operators can add/edit categories from /settings/categories without a code deploy.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rms.models import Category


# Scope constants
SCOPE_PRODUCT = "product"
SCOPE_RECIPE_FAMILY = "recipe_family"


def list_categories(session: Session, scope: str, include_inactive: bool = False) -> list[Category]:
    """Return active categories for `scope`, sorted by sort_order then name.

    Args:
        session: SQLAlchemy session
        scope: one of SCOPE_PRODUCT, SCOPE_RECIPE_FAMILY
        include_inactive: when True, also returns is_active=False rows
    """
    q = select(Category).where(Category.scope == scope)
    if not include_inactive:
        q = q.where(Category.is_active.is_(True))
    q = q.order_by(Category.sort_order.asc(), Category.name.asc())
    return list(session.execute(q).scalars())


def get_or_create_category(
    session: Session, name: str, scope: str, sort_order: int = 1000
) -> Category:
    """Idempotent: return existing Category or insert a new one.

    Used by the inline-create flow on the product/recipe forms. When an
    operator types a category name not in the dropdown, the combo's
    onCreate callback POSTs here to create it on the fly.

    Returns the Category row (existing or freshly inserted).
    """
    name = name.strip()
    if not name:
        raise ValueError("Category name cannot be empty")
    if scope not in (SCOPE_PRODUCT, SCOPE_RECIPE_FAMILY):
        raise ValueError(f"Unknown scope: {scope!r}")

    existing = session.execute(
        select(Category).where(Category.scope == scope, Category.name == name)
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    cat = Category(name=name, scope=scope, sort_order=sort_order, is_active=True)
    session.add(cat)
    session.flush()
    return cat


def update_category(
    session: Session, category_id: int, *, name: str | None = None,
    sort_order: int | None = None, is_active: bool | None = None,
) -> Category | None:
    """Update fields on an existing Category. Returns the updated row or None.

    Only fields explicitly passed are updated (None = don't touch).
    """
    cat = session.get(Category, category_id)
    if cat is None:
        return None
    if name is not None:
        cat.name = name.strip()
    if sort_order is not None:
        cat.sort_order = sort_order
    if is_active is not None:
        cat.is_active = is_active
    session.flush()
    return cat


__all__ = [
    "SCOPE_PRODUCT",
    "SCOPE_RECIPE_FAMILY",
    "list_categories",
    "get_or_create_category",
    "update_category",
]
