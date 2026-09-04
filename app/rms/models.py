"""app/rms/models.py — SQLAlchemy ORM models.

Per dev plan §9 Task 1 + v2 §5 (data model).

Tables:
- ingredient: name, unit, stock_qty, purchase_price_gs (int), min_stock_qty, notes
- recipe: name, yield_qty, yield_unit, notes
- recipe_line: polymorphic via line_kind + line_ref_id (FK to ingredient OR recipe)
- product: name, portion_label, sale_price_gs (int), recipe_id (nullable)
- sale: sold_at, product_id, qty, unit_price_gs (snapshot int), notes
- sale_stock_move: sale_id, affected_recipe_id, ingredient_id, qty_delta
- import_batch: imported_at, source_filename, note, row_counts_json
- app_meta: key, value, updated_at (schema version, last_backup_at, etc.)
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """SQLAlchemy declarative base. All models inherit from this."""

    pass


class AppMeta(Base):
    """Key-value store for app metadata (schema version, last_backup_at, etc.)."""

    __tablename__ = "app_meta"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)


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
    min_stock_qty: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    # NOTE: `recipe_lines` (the reverse of RecipeLine.ingredient) is NOT defined here
    # because RecipeLine.line_ref_id is polymorphic (FK to ingredient OR recipe).
    # Use RecipeLine.ingredient relationship (viewonly=True, primaryjoin with line_kind check)
    # or query RecipeLine directly: SELECT FROM recipe_line WHERE line_kind='ingredient'
    # AND line_ref_id = :id. Helper functions live in costing.py.
    stock_moves: Mapped[list["SaleStockMove"]] = relationship(back_populates="ingredient")

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
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    lines: Mapped[list["RecipeLine"]] = relationship(
        back_populates="recipe",
        foreign_keys="RecipeLine.recipe_id",
        cascade="all, delete-orphan",
    )
    products: Mapped[list["Product"]] = relationship(back_populates="recipe")
    stock_moves: Mapped[list["SaleStockMove"]] = relationship(
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
        ForeignKey("recipe.id", ondelete="CASCADE"), nullable=False
    )
    line_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    line_ref_id: Mapped[int] = mapped_column(Integer, nullable=False)
    qty: Mapped[float] = mapped_column(Float, nullable=False)
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
    recipe_id: Mapped[Optional[int]] = mapped_column(ForeignKey("recipe.id"), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    recipe: Mapped[Optional["Recipe"]] = relationship(back_populates="products")
    sales: Mapped[list["Sale"]] = relationship(back_populates="product")

    __table_args__ = (
        CheckConstraint("sale_price_gs >= 0", name="ck_product_price_nonneg"),
        Index("ix_product_name", "name", unique=True),
    )


class Sale(Base):
    """A recorded sale. unit_price_gs is SNAPSHOT — even if product catalog changes."""

    __tablename__ = "sale"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sold_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"), nullable=False, index=True)
    qty: Mapped[float] = mapped_column(Float, nullable=False)
    unit_price_gs: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    voided_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    product: Mapped["Product"] = relationship(back_populates="sales")
    stock_moves: Mapped[list["SaleStockMove"]] = relationship(
        back_populates="sale", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("qty > 0", name="ck_sale_qty_positive"),
        CheckConstraint("unit_price_gs >= 0", name="ck_sale_price_nonneg"),
    )


class SaleStockMove(Base):
    """Audit of stock moves caused by a sale (or its void).

    qty_delta is negative for normal sales (stock decreases). For voids, the
    same row is updated to positive (stock restored).
    """

    __tablename__ = "sale_stock_move"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sale_id: Mapped[int] = mapped_column(
        ForeignKey("sale.id", ondelete="CASCADE"), nullable=False, index=True
    )
    affected_recipe_id: Mapped[int] = mapped_column(ForeignKey("recipe.id"), nullable=False)
    ingredient_id: Mapped[int] = mapped_column(
        ForeignKey("ingredient.id"), nullable=False, index=True
    )
    qty_delta: Mapped[float] = mapped_column(Float, nullable=False)

    # Relationships
    sale: Mapped["Sale"] = relationship(back_populates="stock_moves")
    affected_recipe: Mapped["Recipe"] = relationship(
        foreign_keys=[affected_recipe_id], back_populates="stock_moves"
    )
    ingredient: Mapped["Ingredient"] = relationship(back_populates="stock_moves")


class ImportBatch(Base):
    """Audit of a Drive-Excel import run."""

    __tablename__ = "import_batch"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    source_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    row_counts_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


# --- User table for single-tenant auth (Milestone 1) ---
#
# We import bcrypt inside the methods (not at module top) because bcrypt
# 5.x changed its API and the lazy import lets tests monkeypatch easily.
# This mirrors the bcrypt helpers in app.auth.


class User(Base):
    """Single user per tenant in v1. Multi-tenant (Milestone 7) adds tenant_id."""

    __tablename__ = "user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    last_login_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (CheckConstraint("length(username) >= 1", name="ck_user_username_nonempty"),)

    def set_password(self, plain: str) -> None:
        """Hash with bcrypt cost-12 and store."""
        import bcrypt

        salt = bcrypt.gensalt(rounds=12)
        self.password_hash = bcrypt.hashpw(plain.encode("utf-8"), salt).decode("utf-8")

    def check_password(self, plain: str) -> bool:
        """Verify password against stored bcrypt hash."""
        import bcrypt

        if not self.password_hash:
            return False
        return bcrypt.checkpw(plain.encode("utf-8"), self.password_hash.encode("utf-8"))


__all__ = [
    "Base",
    "AppMeta",
    "Ingredient",
    "Recipe",
    "RecipeLine",
    "Product",
    "Sale",
    "SaleStockMove",
    "ImportBatch",
    "User",
]
