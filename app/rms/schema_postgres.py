"""app/rms/schema_postgres.py — Postgres-flavored SQLAlchemy schema.

This module exists alongside models.py so the SQLite test path stays
isolated from the production Postgres path. Both models.py and
schema_postgres.py define the same 8 tables, but Postgres uses:
- NUMERIC(12,4) for stock_qty / yield_qty / min_stock_qty / qty / qty_delta
  (avoids Float drift; exact decimal arithmetic)
- BIGINT for money columns (was Integer — same range, no behavior change)
- TIMESTAMP WITH TIME ZONE for sold_at (was DateTime; TZ-aware)
- JSONB for app_meta.value (was Text — but kept Text for app_meta.value
  since the migration scripts already handle string-encoded JSON)
- VARCHAR(n) replaces String(n) — same SQL under the hood

The SQLite path keeps models.py unchanged. Production uses
schema_postgres.py via env var DATABASE_URL.

Strategy:
- Both modules export `Base` (declarative base) and all 8 model classes
- A factory function `get_metadata()` returns the right Base for the
  configured DATABASE_URL
- `init_db(engine)` is dialect-agnostic (works for both)
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import bcrypt
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Postgres-flavored declarative base. All models inherit from this."""

    pass


class AppMeta(Base):
    __tablename__ = "app_meta"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[str] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)


class Ingredient(Base):
    __tablename__ = "ingredient"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    unit: Mapped[str] = mapped_column(String(16), nullable=False)
    stock_qty: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False, default=0)
    purchase_price_gs: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    min_stock_qty: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False, default=0)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

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
    __tablename__ = "recipe"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    yield_qty: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), nullable=True)
    yield_unit: Mapped[str] = mapped_column(String(16), nullable=False, default="und")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

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
    __tablename__ = "recipe_line"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    recipe_id: Mapped[int] = mapped_column(
        ForeignKey("recipe.id", ondelete="CASCADE"), nullable=False
    )
    line_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    line_ref_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    qty: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    recipe: Mapped["Recipe"] = relationship(back_populates="lines", foreign_keys=[recipe_id])

    __table_args__ = (
        CheckConstraint("line_kind IN ('ingredient', 'sub_recipe')", name="ck_line_kind"),
        CheckConstraint("qty > 0", name="ck_line_qty_positive"),
        Index("ix_recipe_line_recipe", "recipe_id"),
        Index("ix_recipe_line_ref", "line_kind", "line_ref_id"),
    )


class Product(Base):
    __tablename__ = "product"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    portion_label: Mapped[str] = mapped_column(String(60), nullable=False, default="1 unidad")
    sale_price_gs: Mapped[int] = mapped_column(BigInteger, nullable=False)
    recipe_id: Mapped[Optional[int]] = mapped_column(ForeignKey("recipe.id"), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    recipe: Mapped[Optional["Recipe"]] = relationship(back_populates="products")
    sales: Mapped[list["Sale"]] = relationship(back_populates="product")

    __table_args__ = (
        CheckConstraint("sale_price_gs >= 0", name="ck_product_price_nonneg"),
        Index("ix_product_name", "name", unique=True),
    )


class Sale(Base):
    __tablename__ = "sale"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    sold_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"), nullable=False, index=True)
    qty: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    unit_price_gs: Mapped[int] = mapped_column(BigInteger, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    voided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    product: Mapped["Product"] = relationship(back_populates="sales")
    stock_moves: Mapped[list["SaleStockMove"]] = relationship(
        back_populates="sale", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("qty > 0", name="ck_sale_qty_positive"),
        CheckConstraint("unit_price_gs >= 0", name="ck_sale_price_nonneg"),
    )


class SaleStockMove(Base):
    __tablename__ = "sale_stock_move"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    sale_id: Mapped[int] = mapped_column(
        ForeignKey("sale.id", ondelete="CASCADE"), nullable=False, index=True
    )
    affected_recipe_id: Mapped[int] = mapped_column(ForeignKey("recipe.id"), nullable=False)
    ingredient_id: Mapped[int] = mapped_column(
        ForeignKey("ingredient.id"), nullable=False, index=True
    )
    qty_delta: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)

    sale: Mapped["Sale"] = relationship(back_populates="stock_moves")
    affected_recipe: Mapped["Recipe"] = relationship(
        foreign_keys=[affected_recipe_id], back_populates="stock_moves"
    )
    ingredient: Mapped["Ingredient"] = relationship(back_populates="stock_moves")


class ImportBatch(Base):
    __tablename__ = "import_batch"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    row_counts_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


# --- User table for single-tenant auth (Milestone 1) ---


class User(Base):
    """Single user per tenant in v1. Multi-tenant (Milestone 7) adds tenant_id."""

    __tablename__ = "user"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now()
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (CheckConstraint("length(username) >= 1", name="ck_user_username_nonempty"),)

    def set_password(self, plain: str) -> None:
        """Hash with bcrypt cost-12 and store."""
        salt = bcrypt.gensalt(rounds=12)
        self.password_hash = bcrypt.hashpw(plain.encode("utf-8"), salt).decode("utf-8")

    def check_password(self, plain: str) -> bool:
        """Verify password against stored bcrypt hash."""
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
