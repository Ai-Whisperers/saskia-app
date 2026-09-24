from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Boolean, CheckConstraint, Date, DateTime, Float, JSON,
    ForeignKey, Index, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.rms.models.core import Base


"""
app/rms/models/sales.py — Sales + customer + tags + channel pricing: Sale, SaleStockMove, Customer, Tag, TagLink, RecipePricing.

Extracted from app/rms/models.py on 2026-09-23 (Phase 3.1 refactor).
All models here share the same declarative Base as the rest of the
project — see app/rms/models/core.py.
"""

class Sale(Base):
    """A recorded sale. unit_price_gs is SNAPSHOT — even if product catalog changes."""

    __tablename__ = "sale"
    customer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("customer.id"), nullable=True, index=True)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sold_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"), nullable=False, index=True)
    qty: Mapped[float] = mapped_column(Float, nullable=False)
    unit_price_gs: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    voided_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # Phase 5: payment + discount
    payment_method: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    discount_gs: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    # Phase 6: timezone of the cash register that recorded the sale.
    # Defaults to America/Asuncion since single-tenant Asunción bakery.
    tz: Mapped[str] = mapped_column(
        String(64), nullable=False, default="America/Asuncion", server_default="America/Asuncion"
    )
    # Stream A prelaunch: which sales channel produced this sale.
    # Allowed values: mostrador, whatsapp, pedidosya, monchis, mostrador-encargo.
    # Defaults to 'mostrador' so existing rows have a sensible value
    # and a brand-new sale (form default) lands on mostrador too.
    channel: Mapped[str] = mapped_column(
        String(32), nullable=False, default="mostrador", server_default="mostrador"
    )

    # Phase 1.B — Fiscal invoice fields (Paraguay DNIT compliance).
    # invoice_type ∈ {'boleta_resimple', 'factura', 'none'}.
    # 'none' = no fiscal document emitted (e.g. internal sample, regalo).
    invoice_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="boleta_resimple", server_default="boleta_resimple"
    )
    # Sequential invoice number (per type). NULL when invoice_type='none'.
    invoice_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Customer RUC for Factura (required when invoice_type='factura').
    invoice_customer_ruc: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    invoice_customer_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    # IVA breakdown at sale time (snapshot — does not change if Product.iva_rate changes).
    iva_rate: Mapped[str] = mapped_column(String(8), nullable=False, default="10", server_default="10")
    iva_base_gs: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    iva_amount_gs: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    # Relationships
    product: Mapped["Product"] = relationship(back_populates="sales")
    customer: Mapped[Optional["Customer"]] = relationship(back_populates="sales")
    stock_moves: Mapped[list["SaleStockMove"]] = relationship(
        back_populates="sale", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("qty > 0", name="ck_sale_qty_positive"),
        CheckConstraint("unit_price_gs >= 0", name="ck_sale_price_nonneg"),
        # Covers: sales list by date range, dashboard charts, daily/weekly summaries,
        # libro_ventas, IVA reports, customer stats — every query that filters
        # sold_at AND ignores voided sales in the same pass.
        Index("ix_sale_sold_at_voided", "sold_at", "voided_at"),
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
    affected_recipe_id: Mapped[int] = mapped_column(ForeignKey("recipe.id"), nullable=False, index=True)
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

class Customer(Base):
    """A customer record (E13).

    Phone is the de-facto unique identifier (matches how Saskia
    identifies customers at the counter). Loyalty points are tracked
    in-app; lifetime spend is computed from sales at query time.
    """

    __tablename__ = "customer"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    cedula: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    loyalty_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # HEREBUS integration: free-text zone label (no FK — early stage)
    zone: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_customer_name", "name"),
    )

    # Relationships
    sales: Mapped[list["Sale"]] = relationship(back_populates="customer")

class Tag(Base):
    """Tag row (E9.S1).

    A tag belongs to a single kind (product | ingredient | recipe).
    Polymorphic M:N is handled by TagLink.
    """

    __tablename__ = "tag"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    color: Mapped[str] = mapped_column(String(16), nullable=False, default="#757575")

    __table_args__ = (
        UniqueConstraint("name", "kind", name="uq_tag_name_kind"),
        Index("ix_tag_kind", "kind"),
    )

    # Relationships
    links: Mapped[list["TagLink"]] = relationship(
        "TagLink", back_populates="tag", cascade="all, delete-orphan"
    )

class TagLink(Base):
    """Polymorphic M:N link between a Tag and a target (E9.S1).

    target_kind in ("product", "ingredient", "recipe"); target_id is the FK
    to the corresponding table.
    """

    __tablename__ = "tag_link"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tag_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tag.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    target_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    __table_args__ = (
        UniqueConstraint("tag_id", "target_kind", "target_id", name="uq_tag_link"),
        Index("ix_tag_link_target", "target_kind", "target_id"),
    )

    # Relationships
    tag: Mapped["Tag"] = relationship("Tag", back_populates="links")

class RecipePricing(Base):
    """Per-channel pricing for a recipe (HEREBUS COSTOS + Pricing_Por_Producto).

    Channel margins (from MAESTRA):
      - wholesale: +40%
      - private_label: +25%
      - distributor: +22%
      - retail: +50%
      - broker_commission: +5%
    """

    __tablename__ = "recipe_pricing"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recipe_id: Mapped[int] = mapped_column(
        ForeignKey("recipe.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    cost_total_gs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    labor_gs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    packaging_gs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_per_unit_gs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    wholesale_gs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    private_label_gs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    distributor_gs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retail_gs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    broker_commission_gs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    recipe: Mapped["Recipe"] = relationship("Recipe")

    __table_args__ = (
        CheckConstraint("cost_per_unit_gs >= 0", name="ck_pricing_per_unit_nonneg"),
        CheckConstraint("retail_gs >= 0", name="ck_pricing_retail_nonneg"),
    )
