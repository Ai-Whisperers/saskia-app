from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.rms.models.core import Base

"""
app/rms/models/inventory.py — Inventory + recipe + product catalog: Ingredient, Recipe, RecipeLine, Product, IngredientPriceEvent, PriceHistory.

Extracted from app/rms/models.py on 2026-09-23 (Phase 3.1 refactor).
All models here share the same declarative Base as the rest of the
project — see app/rms/models/core.py.
"""


class Ingredient(Base):
    """An inventory item. Stock and prices are stored as Decimal (float64).

    purchase_price_gs is integer Gs. (no cents). NULL means "no price set yet"
    (dashboard alerts on this).
    """

    __tablename__ = "ingredient"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    unit: Mapped[str] = mapped_column(String(16), nullable=False)
    stock_qty: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    purchase_price_gs: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    purchase_price_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_consumed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    min_stock_qty: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # Phase 7 reorder: target stock to refill to. Defaults to 2x min_stock_qty
    # if not set (computed in app/rms/reorder.py).
    max_stock_qty: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    shelf_life_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Wave 2 — HACCP storage zone. Inferred from ingredient name on POST
    # /inventario/nuevo; operator can override. ∈ {ambient, refrigerated, frozen, dry}.
    storage: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # E26 ingredient intelligence
    category: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    subcategory: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    role: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    allergens: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    dietary_tags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Migration 061: pre-computed validation issues (e.g. "declares 'vegano'
    # but allergens include dairy"). Newline-separated. Populated by
    # app.rms.tagging.audit.backfill_validation_issues().
    tag_validation_issues: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    lead_time_days: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    supplier_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("supplier.id"), nullable=True, index=True
    )
    # Phase 1.C — HACCP cold-chain + dry-storage fields (Res S.G. N° 213/2019).
    # NULL means "unknown / not set"; operator fills via /inventario/{id}/editar.
    temp_min_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    temp_max_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    humidity_max_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Water activity (a_w). < 0.85 = shelf-stable; > 0.95 = perishable.
    water_activity_aw: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Whether this ingredient requires lot tracking (FIFO per batch).
    # True for dairy, eggs, meat, seafood, fresh produce. False for dry/sugar/salt.
    lot_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    # SINACLA cross-contamination flag: produced in facility with wheat.
    # Blocks "sin tacc" derivation even when tagged sin_gluten (migration 054).
    may_contain_gluten: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    # Audit items 109, 110: opening stock with date + reorder point override
    opening_stock_qty: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    opening_stock_date: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )  # ISO date string
    reorder_point: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )  # overrides min_stock_qty for reorder

    # Relationships
    # NOTE: `recipe_lines` (the reverse of RecipeLine.ingredient) is NOT defined here
    # because RecipeLine.line_ref_id is polymorphic (FK to ingredient OR recipe).
    # Use RecipeLine.ingredient relationship (viewonly=True, primaryjoin with line_kind check)
    # or query RecipeLine directly: SELECT FROM recipe_line WHERE line_kind='ingredient'
    # AND line_ref_id = :id. Helper functions live in costing.py.
    stock_moves: Mapped[list["SaleStockMove"]] = relationship(  # noqa: F821 — SQLAlchemy 2.0 forward ref
        back_populates="ingredient"
    )
    supplier: Mapped[Optional["Supplier"]] = relationship(  # noqa: F821 — SQLAlchemy 2.0 forward ref
        back_populates="ingredients"
    )

    __table_args__ = (
        CheckConstraint("unit IN ('g', 'kg', 'ml', 'l', 'und')", name="ck_ingredient_unit"),
        CheckConstraint("stock_qty IS NOT NULL", name="ck_ingredient_stock_notnull"),
        CheckConstraint("min_stock_qty >= 0", name="ck_ingredient_min_nonneg"),
        CheckConstraint(
            "purchase_price_gs IS NULL OR purchase_price_gs >= 0",
            name="ck_ingredient_price_nonneg",
        ),
        Index("ix_ingredient_name", "name", unique=True),
    )


class Recipe(Base):
    """A recipe. yield_qty + yield_unit describe the batch (e.g., 12 muffins, 1 torta)."""

    __tablename__ = "recipe"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    yield_qty: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    yield_unit: Mapped[str] = mapped_column(String(16), nullable=False, default="und")
    prep_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cook_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    difficulty: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 1-5 scale
    family: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True
    )  # category (legacy, read-only)
    # UI-V2 (migration 068): multi-select "Etiquetas de Menú" — a recipe can
    # belong to several commercial contexts ("Pastelería", "Especial de
    # Temporada"). Comma-separated, like dietary_tags. Replaces the
    # single-limit family for filtering/display.
    menu_tags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    dietary_tags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # comma-separated
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Phase 1.D — moisture loss / yield correction. 1.0 = no loss; 0.85 = 15% loss.
    yield_percentage: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Phase 1.D — informal labor time tracking per batch (in minutes).
    direct_labor_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # HEREBUS integration: image_url (book page or process photo)
    image_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # Tag algebra (migration 054): cached union allergens + intersection tags.
    allergens: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    derived_dietary_tags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    lines: Mapped[list["RecipeLine"]] = relationship(
        back_populates="recipe",
        foreign_keys="RecipeLine.recipe_id",
        cascade="all, delete-orphan",
    )
    products: Mapped[list["Product"]] = relationship(back_populates="recipe")
    stock_moves: Mapped[list["SaleStockMove"]] = relationship(  # noqa: F821 — SQLAlchemy 2.0 forward ref
        back_populates="affected_recipe",
        foreign_keys="SaleStockMove.affected_recipe_id",
    )

    __table_args__ = (
        CheckConstraint("yield_unit IN ('g', 'kg', 'ml', 'l', 'und')", name="ck_recipe_unit"),
        CheckConstraint("yield_qty IS NULL OR yield_qty > 0", name="ck_recipe_yield_positive"),
        Index("ix_recipe_name", "name", unique=True),
    )


class RecipeLine(Base):
    """A line in a recipe. Polymorphic: line_kind ∈ {ingredient, sub_recipe}.

    line_ref_id points to either ingredient.id (if line_kind='ingredient') or
    recipe.id (if line_kind='sub_recipe'). Use the corresponding view (lines_via_ingredient,
    lines_via_sub_recipe) or the helper functions in costing.py to walk the tree.
    """

    __tablename__ = "recipe_line"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recipe_id: Mapped[int] = mapped_column(
        ForeignKey("recipe.id", ondelete="CASCADE"), nullable=False, index=True
    )
    line_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    line_ref_id: Mapped[int] = mapped_column(Integer, nullable=False)
    qty: Mapped[float] = mapped_column(Float, nullable=False)
    # Phase B — T1: per-line unit. Lets Saskia type "250 g" while the linked
    # ingredient is in "kg". Default "" for backward compat (legacy rows assume
    # the ingredient's unit at costing time). Allowed: g, kg, ml, l, und.
    line_unit: Mapped[str] = mapped_column(String(8), nullable=False, default="")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    recipe: Mapped["Recipe"] = relationship(back_populates="lines", foreign_keys=[recipe_id])
    # NOTE: ingredient and sub_recipe relationships are NOT defined here because
    # line_ref_id is polymorphic. Use `resolve_line_target(session, line)` in
    # costing.py to get the right object.

    __table_args__ = (
        CheckConstraint("line_kind IN ('ingredient', 'sub_recipe')", name="ck_line_kind"),
        CheckConstraint("qty > 0", name="ck_line_qty_positive"),
        Index("ix_recipe_line_recipe", "recipe_id"),
        Index("ix_recipe_line_ref", "line_kind", "line_ref_id"),
    )


class Product(Base):
    """A sellable product. Has a sale_price_gs (int) and an optional recipe."""

    __tablename__ = "product"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    portion_label: Mapped[str] = mapped_column(String(60), nullable=False, default="1 unidad")
    sale_price_gs: Mapped[int] = mapped_column(Integer, nullable=False)
    recipe_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("recipe.id"), nullable=True, index=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sku: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True, unique=True, index=True
    )  # E23.S1 barcode
    is_available: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )  # Toggle to hide from POS
    image_url: Mapped[Optional[str]] = mapped_column(
        String(256), nullable=True
    )  # Product image URL
    category: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # Product category
    tags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Comma-separated tags
    # Migration 069: quick-sale "Favoritos" filter persistence (kept in sync
    # with models_legacy.Product).
    is_favorite: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Phase 1.A — IVA rate ∈ {5, 10, 'exento'}. Defaults from ComplianceInfo.iva_default_rate.
    # Stored as string so 'exento' is a valid value alongside 5/10.
    iva_rate: Mapped[str] = mapped_column(
        String(8), nullable=False, default="10", server_default="10"
    )

    # Phase 1.A — INAN R.S.P.A. (Registro Sanitario de Producto Alimenticio). Required when
    # product is packaged + labeled for retail sale. NULL = no R.S.P.A. (e.g. mostrador
    # or encargo sales where R.S.P.A. is not required).
    requires_rspa: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    rspa_number: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    rspa_expiry: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # ISO

    # Phase 1.C — HACCP + costing (lazy fields; detailed cost fields added in Phase 1.D)
    yield_percentage: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Tag algebra: cached inherited tags from linked recipe (migration 054).
    inherited_tags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # 0.85 default = 15% moisture loss for breads (matches industry standard).
    # Operators can override per recipe.

    # Relationships
    recipe: Mapped[Optional["Recipe"]] = relationship(back_populates="products")
    sales: Mapped[list["Sale"]] = relationship(back_populates="product")  # noqa: F821 — SQLAlchemy 2.0 forward ref

    __table_args__ = (
        CheckConstraint("sale_price_gs >= 0", name="ck_product_price_nonneg"),
        Index("ix_product_name", "name", unique=True),
    )


class IngredientVariant(Base):
    """A specific package of an Ingredient (Sprint 7 — Decision A1).

    E.g. for Ingredient "harina", variants are "harina 1kg @ Proveedor A",
    "harina 250g @ Proveedor B", "harina 5kg @ Proveedor C". Each variant
    has its own purchase price + supplier, and price history can be
    tracked per variant (future: IngredientPriceEvent will get a
    variant_id column).

    Rollups: "how much harina total?" = sum over variants of
    (variant.stock_qty * package_size, converted to the Ingredient's base
    unit). Helper in app/rms/inventory.py: rollup_ingredient_stock().

    Preferred: exactly one variant per ingredient should be marked
    preferred — that variant is the "current price" the dashboard reads
    when reporting current purchase_price_gs. Enforced by a partial unique
    index in Postgres / a trigger in SQLite (see migration 040).
    """

    __tablename__ = "ingredient_variant"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ingredient_id: Mapped[int] = mapped_column(
        ForeignKey("ingredient.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Human-readable label of the package (e.g. "Bolsa 1kg", "Saco 25kg").
    # Optional — operators can leave it empty if the size + unit is clear.
    package_size: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    package_unit: Mapped[str] = mapped_column(String(8), nullable=False, default="und")
    purchase_price_gs: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Stock for THIS variant only (e.g. 3 bags of 1kg harina). The
    # ingredient.stock_qty column on the parent is kept for backwards
    # compatibility but new code should read variant-level stock.
    stock_qty: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default="0")
    supplier_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("supplier.id"), nullable=True, index=True
    )
    preferred: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # Relationships
    ingredient: Mapped["Ingredient"] = relationship(back_populates="variants")
    supplier: Mapped[Optional["Supplier"]] = relationship()  # noqa: F821 — SQLAlchemy 2.0 forward ref

    __table_args__ = (
        CheckConstraint("package_size > 0", name="ck_variant_size_positive"),
        CheckConstraint(
            "package_unit IN ('g', 'kg', 'ml', 'l', 'und')",
            name="ck_variant_unit_allowed",
        ),
        CheckConstraint(
            "purchase_price_gs IS NULL OR purchase_price_gs >= 0",
            name="ck_variant_price_nonneg",
        ),
    )


class IngredientPriceEvent(Base):
    """A purchase-price update for an ingredient (Phase B — Q1 core).

    Append-only. Every time Ingredient.purchase_price_gs changes, a row is
    written here so price-history queries (90-day sparkline, current/min/
    max strip on /inventario, fluctuation insight on the dashboard) have a
    real time series instead of just "the current price".

    Fields:
      id             — PK
      ingredient_id  — FK to ingredient.id; cascade-deleted with the ingredient
      price_gs       — int Gs. snapshot at the time of the event
      recorded_at    — UTC datetime; default now()
      source         — how the price changed:
                         * 'restock'      — written by an inventory restock flow
                         * 'manual'       — operator typed/changed it in /inventario
                         * 'excel_import' — set during an Excel import run
    """

    __tablename__ = "ingredient_price_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ingredient_id: Mapped[int] = mapped_column(
        ForeignKey("ingredient.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    price_gs: Mapped[int] = mapped_column(Integer, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="restock")

    __table_args__ = (
        Index(
            "ix_ingredient_price_event_ingredient_time",
            "ingredient_id",
            "recorded_at",
        ),
    )


class PriceHistory(Base):
    """One row per actual ingredient purchase (HEREBUS Price_History sheet).

    Auto-created when a PurchaseOrder is recorded. The avg is computed
    on read (or in a periodic job) — we keep this table append-only.
    """

    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    supplier_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("supplier.id"), nullable=True, index=True
    )
    ingredient_id: Mapped[int] = mapped_column(
        ForeignKey("ingredient.id"), nullable=False, index=True
    )
    qty_purchased: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(16), nullable=False)
    total_gs: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_gs: Mapped[int] = mapped_column(Integer, nullable=False)
    purchase_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recorded_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    ingredient: Mapped["Ingredient"] = relationship("Ingredient")
    supplier: Mapped[Optional["Supplier"]] = relationship("Supplier")  # noqa: F821 — SQLAlchemy 2.0 forward ref

    __table_args__ = (
        CheckConstraint("qty_purchased > 0", name="ck_pricehistory_qty_positive"),
        CheckConstraint("total_gs >= 0", name="ck_pricehistory_total_nonneg"),
        CheckConstraint("unit_price_gs >= 0", name="ck_pricehistory_up_nonneg"),
        Index("ix_pricehistory_ing_date", "ingredient_id", "purchase_date"),
    )
