"""app/rms/tagging/filters.py — Filter dataclasses + query helpers.

Per docs/plans/2026-09-07-sazon-complete-epic-plan-v3.md E9.

Lifted from ``app/rms/tags.py``. Owns the listings-filter concern:
- SalesFilter / InventoryFilter / RecipeFilter / ProductFilter dataclasses
- filter_sales / filter_inventory / filter_recipes / filter_products

Public API contract unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rms.models import (
    Ingredient,
    Product as MProductModel,
    Recipe,
    Sale,
    Tag,
    TagLink,
)
from app.rms.money import to_int_gs
from app.rms.tagging.model import TagKind


class TagKind(str, Enum):
    """Tag targets."""

    PRODUCT = "product"
    INGREDIENT = "ingredient"
    RECIPE = "recipe"


# --- Starter tags (data, not schema) ---

STARTER_TAGS: list[tuple[str, str, str]] = [
    # (name, kind, color)
    # Products
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
    # Ingredients
    ("perecedero", TagKind.INGREDIENT.value, "#f44336"),
    ("congelable", TagKind.INGREDIENT.value, "#0288d1"),
    ("seco", TagKind.INGREDIENT.value, "#bf8f30"),
    ("refrigerado", TagKind.INGREDIENT.value, "#1976d2"),
    ("importado", TagKind.INGREDIENT.value, "#6a1b9a"),
    ("local", TagKind.INGREDIENT.value, "#2e7d32"),
    ("alergeno-gluten", TagKind.INGREDIENT.value, "#ff6f00"),
    ("alergeno-lactosa", TagKind.INGREDIENT.value, "#ff6f00"),
    ("alergeno-frutos-secos", TagKind.INGREDIENT.value, "#ff6f00"),
    ("precio-volatil", TagKind.INGREDIENT.value, "#d84315"),
    ("organico", TagKind.INGREDIENT.value, "#33691e"),
    # Recipes
    ("sub-receta", TagKind.RECIPE.value, "#7e57c2"),
    ("temporada", TagKind.RECIPE.value, "#43a047"),
    ("alto-costo", TagKind.RECIPE.value, "#b71c1c"),
]


# --- CRUD ---


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
    """Insert all STARTER_TAGS if missing. Idempotent."""
    out: list[Tag] = []
    for name, kind, color in STARTER_TAGS:
        out.append(ensure_tag(session, name, kind, color))
    return out


def list_tags_for_kind(session: Session, kind: str) -> list[Tag]:
    """Return all Tag rows for a given kind (product|ingredient|recipe).

    Used by templates that need to render tag pills dynamically — the
    static lists previously hardcoded in app/templates/_components/tags.html
    are gone. Sort order: alphabetical by name.
    """
    return list(session.execute(select(Tag).where(Tag.kind == kind).order_by(Tag.name)).scalars())


def tag_target(session: Session, tag: Tag, target_kind: str, target_id: int) -> TagLink:
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


def untag_target(session: Session, tag: Tag, target_kind: str, target_id: int) -> bool:
    """Remove a tag from a target. Returns True if removed."""
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


def tags_for_target(session: Session, target_kind: str, target_id: int) -> list[Tag]:
    """Return all Tag rows attached to a given target."""
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


# --- Filter dataclasses (pure data, no SQL) ---


@dataclass
class SalesFilter:
    """Filter criteria for /ventas listing (E9.S2)."""

    start_date: datetime | None = None
    end_date: datetime | None = None
    product_ids: list[int] = field(default_factory=list)
    product_tag_names: list[str] = field(default_factory=list)
    min_amount_gs: int | None = None
    max_amount_gs: int | None = None
    only_voided: bool = False
    search_text: str | None = None  # matches notes (case-insensitive)


@dataclass
class InventoryFilter:
    """Filter criteria for /inventario listing."""

    stock_status: str | None = None  # bajo_min, critico, sobrestock, muerto
    ingredient_tag_names: list[str] = field(default_factory=list)
    search_text: str | None = None
    min_cost_gs: int | None = None
    max_cost_gs: int | None = None


@dataclass
class RecipeFilter:
    """Filter criteria for /recetas listing."""

    margin_tier: str | None = None  # top_10, top_25, bottom_25
    recipe_tag_names: list[str] = field(default_factory=list)
    search_text: str | None = None
    min_yield: float | None = None
    max_yield: float | None = None


@dataclass
class ProductFilter:
    """Filter criteria for /productos listing."""

    category: str | None = None
    product_tag_names: list[str] = field(default_factory=list)
    has_recipe: bool | None = None
    search_text: str | None = None
    is_active: bool | None = None


# ─── Filter query helpers ──────────────────────────────────────────────────


def _to_naive_utc(dt: datetime) -> datetime:
    """Convert a tz-aware datetime to naive UTC; pass naive through."""
    if dt.tzinfo:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def filter_sales(session: Session, f: SalesFilter) -> list[Sale]:
    """Apply SalesFilter and return matching sales (newest first)."""
    q = select(Sale)
    if f.start_date:
        start = (
            f.start_date.astimezone(timezone.utc).replace(tzinfo=None)
            if f.start_date.tzinfo
            else f.start_date
        )
        q = q.where(Sale.sold_at >= start)
    if f.end_date:
        end = (
            f.end_date.astimezone(timezone.utc).replace(tzinfo=None)
            if f.end_date.tzinfo
            else f.end_date
        )
        q = q.where(Sale.sold_at <= end)
    if f.product_ids:
        q = q.where(Sale.product_id.in_(f.product_ids))
    if f.only_voided:
        q = q.where(Sale.voided_at.is_not(None))
    if f.search_text:
        q = q.where(Sale.notes.ilike(f"%{f.search_text}%"))
    # Tag filter: subquery on product ids with the tags
    if f.product_tag_names:
        tag_subq = (
            select(TagLink.target_id)
            .join(Tag, Tag.id == TagLink.tag_id)
            .where(
                TagLink.target_kind == TagKind.PRODUCT.value,
                Tag.name.in_(f.product_tag_names),
            )
        )
        q = q.where(Sale.product_id.in_(tag_subq))
    # Amount filter (post-query; SQLAlchemy doesn't have a clean way to express
    # `qty * unit_price_gs BETWEEN X AND Y` against computed columns without
    # denormalizing). We filter client-side below for simplicity.
    sales = list(session.execute(q.order_by(Sale.sold_at.desc())).scalars())
    if f.min_amount_gs is not None or f.max_amount_gs is not None:
        sales = [
            s
            for s in sales
            if (
                f.min_amount_gs is None
                or to_int_gs(Decimal(str(s.qty)) * Decimal(str(s.unit_price_gs))) >= f.min_amount_gs
            )
            and (
                f.max_amount_gs is None
                or to_int_gs(Decimal(str(s.qty)) * Decimal(str(s.unit_price_gs))) <= f.max_amount_gs
            )
        ]
    return sales


def filter_inventory(session: Session, f: InventoryFilter) -> list[Ingredient]:
    """Apply InventoryFilter and return matching ingredients."""
    q = select(Ingredient)
    if f.search_text:
        q = q.where(Ingredient.name.ilike(f"%{f.search_text}%"))
    if f.min_cost_gs is not None:
        q = q.where(Ingredient.purchase_price_gs >= f.min_cost_gs)
    if f.max_cost_gs is not None:
        q = q.where(Ingredient.purchase_price_gs <= f.max_cost_gs)
    if f.ingredient_tag_names:
        tag_subq = (
            select(TagLink.target_id)
            .join(Tag, Tag.id == TagLink.tag_id)
            .where(
                TagLink.target_kind == TagKind.INGREDIENT.value,
                Tag.name.in_(f.ingredient_tag_names),
            )
        )
        q = q.where(Ingredient.id.in_(tag_subq))

    ingredients = list(session.execute(q.order_by(Ingredient.name)).scalars())

    if f.stock_status:
        # Phase 7 — thresholds come from stock_status_config table (with
        # DEFAULT_* constants fallback). See app/rms/stock_status.py.
        from app.rms.stock_status import categorize, get_thresholds

        thresholds = get_thresholds(session)
        out: list[Ingredient] = []
        for ing in ingredients:
            status = categorize(
                ing.stock_qty,
                ing.min_stock_qty,
                ing.last_consumed_at,
                thresholds,
            )
            if status == f.stock_status:
                out.append(ing)
        return out
    return ingredients


def filter_recipes(session: Session, f: RecipeFilter) -> list[Recipe]:
    """Apply RecipeFilter and return matching recipes."""
    q = select(Recipe)
    if f.search_text:
        q = q.where(Recipe.name.ilike(f"%{f.search_text}%"))
    if f.min_yield is not None:
        q = q.where(Recipe.yield_qty >= f.min_yield)
    if f.max_yield is not None:
        q = q.where(Recipe.yield_qty <= f.max_yield)
    if f.recipe_tag_names:
        tag_subq = (
            select(TagLink.target_id)
            .join(Tag, Tag.id == TagLink.tag_id)
            .where(
                TagLink.target_kind == TagKind.RECIPE.value,
                Tag.name.in_(f.recipe_tag_names),
            )
        )
        q = q.where(Recipe.id.in_(tag_subq))
    recipes = list(session.execute(q.order_by(Recipe.name)).scalars())
    if f.margin_tier:
        # Phase 7 — thresholds come from the margin_tier table. Operators
        # adjust via /api/margin-tiers. See app/rms/margin_tier.py.
        from app.rms.costing import recipe_batch_cost_gs
        from app.rms.margin_tier import filter_recipes_by_tier

        recipes_with_cost: list[tuple[Recipe, int | None]] = []
        for r in recipes:
            cost = recipe_batch_cost_gs(session, r.id).batch_cost_gs
            recipes_with_cost.append((r, cost))
        # filter_recipes_by_tier handles missing tier code (returns all)
        return filter_recipes_by_tier(session, recipes_with_cost, f.margin_tier)
    return recipes


def filter_products(session: Session, f: ProductFilter) -> list[MProductModel]:
    """Apply ProductFilter and return matching products."""
    q = select(MProductModel)
    if f.search_text:
        q = q.where(MProductModel.name.ilike(f"%{f.search_text}%"))
    if f.has_recipe is True:
        q = q.where(MProductModel.recipe_id.is_not(None))
    elif f.has_recipe is False:
        q = q.where(MProductModel.recipe_id.is_(None))
    if f.product_tag_names:
        tag_subq = (
            select(TagLink.target_id)
            .join(Tag, Tag.id == TagLink.tag_id)
            .where(
                TagLink.target_kind == TagKind.PRODUCT.value,
                Tag.name.in_(f.product_tag_names),
            )
        )
        q = q.where(MProductModel.id.in_(tag_subq))
    return list(session.execute(q.order_by(MProductModel.name)).scalars())


__all__ = [
    "InventoryFilter",
    "ProductFilter",
    "RecipeFilter",
    "SalesFilter",
    "filter_inventory",
    "filter_products",
    "filter_recipes",
    "filter_sales",
]