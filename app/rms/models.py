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

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
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
    purchase_price_updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    last_consumed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    min_stock_qty: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # Phase 7 reorder: target stock to refill to. Defaults to 2x min_stock_qty
    # if not set (computed in app/rms/reorder.py).
    max_stock_qty: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    shelf_life_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # E26 ingredient intelligence
    category: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    subcategory: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    role: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    allergens: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    dietary_tags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    lead_time_days: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    supplier_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("supplier.id"), nullable=True, index=True
    )
    # Audit items 109, 110: opening stock with date + reorder point override
    opening_stock_qty: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    opening_stock_date: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # ISO date string
    reorder_point: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # overrides min_stock_qty for reorder

    # Relationships
    # NOTE: `recipe_lines` (the reverse of RecipeLine.ingredient) is NOT defined here
    # because RecipeLine.line_ref_id is polymorphic (FK to ingredient OR recipe).
    # Use RecipeLine.ingredient relationship (viewonly=True, primaryjoin with line_kind check)
    # or query RecipeLine directly: SELECT FROM recipe_line WHERE line_kind='ingredient'
    # AND line_ref_id = :id. Helper functions live in costing.py.
    stock_moves: Mapped[list["SaleStockMove"]] = relationship(back_populates="ingredient")
    supplier: Mapped[Optional["Supplier"]] = relationship(back_populates="ingredients")

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
    family: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # category
    dietary_tags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # comma-separated
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # HEREBUS integration: image_url (book page or process photo)
    image_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

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
    recipe_id: Mapped[Optional[int]] = mapped_column(ForeignKey("recipe.id"), nullable=True, index=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sku: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, unique=True, index=True)  # E23.S1 barcode
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)  # Toggle to hide from POS
    image_url: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)  # Product image URL
    category: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # Product category
    tags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Comma-separated tags

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
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="admin")  # admin, cashier, manager
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


class AuditLog(Base):
    """Append-only log of security-relevant events.

    Populated by app/rms/audit.record() from sensitive endpoints (login,
    logout, password reset, sales create/void, recipe/product edits,
    inventory movements). Surfaced at GET /audit (admin only).

    Per the 2026-09-04 critical-path plan, E3.S1. Schema-versioned migration
    lives in app/rms/db.py as _migration_002_audit_log; bumping
    CURRENT_SCHEMA_VERSION is required to apply it on existing DBs.

    Fields:
      id           - PK
      occurred_at  - UTC timestamp
      user_id      - Optional[str] (Supabase UUID) or int (local user_id); null if anonymous
      action       - e.g. "login.success", "login.failure", "sale.create"
      target_type  - e.g. "sale", "recipe", "ingredient" (nullable for auth events)
      target_id    - stringified PK of target row (nullable)
      detail       - free-form JSON dict for action-specific context
      ip           - client IP (X-Forwarded-For aware, first hop)
      user_agent   - truncated User-Agent header

    Notes on design:
      - No UPDATE/DELETE permissions enforced at the ORM level (SQLite has no
        row-level perms anyway). Application code is expected to never
        mutate or delete rows.
      - `detail` uses JSON type (dialect-aware: JSONB on PG, TEXT on SQLite)
        to match the row_counts_json pattern from commit 501bcff.
      - For hosted (Supabase) auth, user_id is a UUID string. For local
        bcrypt auth, user_id is an int. Both are stored as TEXT for cross-dialect
        safety (Supabase UUIDs are 36 chars, int fits in any string column).
    """

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    target_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    detail: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)



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
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="restock")

    __table_args__ = (
        Index(
            "ix_ingredient_price_event_ingredient_time",
            "ingredient_id",
            "recorded_at",
        ),
    )


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




class ProductionCompletion(Base):
    """How much of a planned product was actually produced on a given day.

    Saskia review T5: "Al final del dia debe registrarse cuanto de la
    produccion se completo". One row per (product, date) — re-recording
    updates in place via upsert_completion().
    """

    __tablename__ = "production_completion"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("product.id"), nullable=False, index=True
    )
    for_date: Mapped[date] = mapped_column(Date, nullable=False)
    completed_qty: Mapped[float] = mapped_column(Float, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint("completed_qty >= 0", name="ck_completion_qty_nonneg"),
        UniqueConstraint("product_id", "for_date", name="uq_completion_product_date"),
    )

    # Relationships
    product: Mapped["Product"] = relationship("Product")


class ProductionPlanTemplate(Base):
    """PRO-01: Repeating weekly production plan template.

    One row per (weekday 0-6 = Mon-Sun, product). When the operator opens the
    production page on a Thursday, the "Sugerido" plan is loaded from this
    template (auto-forecast only when the template is empty for that weekday).
    A specific date can override this — see ProductionPlanOverride.
    """

    __tablename__ = "production_plan_template"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    weekday: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("product.id"), nullable=False, index=True
    )
    qty: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        CheckConstraint("weekday >= 0 AND weekday <= 6", name="ck_template_weekday_range"),
        CheckConstraint("qty >= 0", name="ck_template_qty_nonneg"),
        UniqueConstraint("weekday", "product_id", name="uq_template_weekday_product"),
    )

    # Relationships
    product: Mapped["Product"] = relationship("Product")


class ProductionPlanOverride(Base):
    """PRO-01: Per-date override of the weekly template.

    Recording an override for one date does NOT change the weekly template —
    other weeks are unaffected. Overrides are date-scoped, not weekday-scoped.
    """

    __tablename__ = "production_plan_override"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("product.id"), nullable=False, index=True
    )
    for_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    qty: Mapped[float] = mapped_column(Float, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        CheckConstraint("qty >= 0", name="ck_override_qty_nonneg"),
        UniqueConstraint("product_id", "for_date", name="uq_override_product_date"),
    )

    # Relationships
    product: Mapped["Product"] = relationship("Product")


class Supplier(Base):
    """A supplier / proveed for ingredients (audit item 284).

    Stores contact info so reorder suggestions can surface the supplier
    and generate WhatsApp pre-fill links for placing orders.
    """

    __tablename__ = "supplier"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    contact_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    ingredients: Mapped[list["Ingredient"]] = relationship(back_populates="supplier")

    __table_args__ = (
        Index("ix_supplier_name", "name"),
    )


class WasteLog(Base):
    """A waste event (E22).

    Append-only. Cost is denormalized at insert time so historical
    reports don't retroactively change when purchase prices change.
    """

    __tablename__ = "waste_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ingredient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ingredient.id"), nullable=False, index=True
    )
    qty: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[str] = mapped_column(String(32), nullable=False)
    cost_gs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    recorded_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint("qty > 0", name="ck_waste_qty_positive"),
        Index("ix_waste_log_reason", "reason"),
    )

    # Relationships
    ingredient: Mapped["Ingredient"] = relationship("Ingredient")


# ──────────────────────────────────────────────────────────────────
# HEREBUS Drive integration — new modules (migration 029)
# ──────────────────────────────────────────────────────────────────


class DeliveryZone(Base):
    """A delivery zone (HEREBUS ZONAS_DELIVERY sheet).

    Each pedido can reference one zone. The zone drives delivery cost
    calculation and minimum-order validation at creation time.
    """

    __tablename__ = "delivery_zone"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    coverage_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    radius_km: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    delivery_cost_gs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    min_order_gs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    delivery_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    pedidos: Mapped[list["Pedido"]] = relationship(back_populates="delivery_zone")

    __table_args__ = (
        Index("ix_delivery_zone_active", "is_active", "position"),
    )


# NOTE: `delivery_zone_id` is added to Pedido class below (forward ref).
# Customer.zone is also added inline (existing model has been extended).


class WishlistItem(Base):
    """Kitchen equipment wishlist (HEREBUS Wishlist sheet).

    Track what equipment HEREBUS needs to buy, with priority and ₲ costs.
    """

    __tablename__ = "wishlist_item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="must_have")
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price_gs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    category: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    buy_location: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    purchased: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    purchased_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    __table_args__ = (
        CheckConstraint(
            "priority IN ('must_have', 'nice_to_have', 'optional')",
            name="ck_wishlist_priority",
        ),
        CheckConstraint("quantity > 0", name="ck_wishlist_qty_positive"),
        CheckConstraint("unit_price_gs >= 0", name="ck_wishlist_price_nonneg"),
    )


class RiskItem(Base):
    """An operational risk on the registry (HEREBUS Risk_Register sheet)."""

    __tablename__ = "risk_item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    probability: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    impact_gs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mitigation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    owner: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    __table_args__ = (
        CheckConstraint(
            "probability BETWEEN 1 AND 5", name="ck_risk_prob_range"
        ),
        CheckConstraint("impact_gs >= 0", name="ck_risk_impact_nonneg"),
        CheckConstraint(
            "status IN ('active', 'activo', 'mitigated', 'closed')",
            name="ck_risk_status",
        ),
    )


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
    supplier: Mapped[Optional["Supplier"]] = relationship("Supplier")

    __table_args__ = (
        CheckConstraint("qty_purchased > 0", name="ck_pricehistory_qty_positive"),
        CheckConstraint("total_gs >= 0", name="ck_pricehistory_total_nonneg"),
        CheckConstraint("unit_price_gs >= 0", name="ck_pricehistory_up_nonneg"),
        Index("ix_pricehistory_ing_date", "ingredient_id", "purchase_date"),
    )


class ProductionPlan(Base):
    """A planned batch — output of the Production Planner.

    User picks recipe + batches-qty. System computes ingredient needs,
    joins with current stock, and surfaces shortages. Auto-generates
    ShoppingListItem rows for the shortage (when "Send to shop" pressed).
    """

    __tablename__ = "production_plan"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recipe_id: Mapped[int] = mapped_column(
        ForeignKey("recipe.id"), nullable=False, index=True
    )
    batches_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    planned_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="planned")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    recipe: Mapped["Recipe"] = relationship("Recipe")
    shopping_items: Mapped[list["ShoppingListItem"]] = relationship(
        back_populates="production_plan", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("batches_qty > 0", name="ck_plan_batches_positive"),
        CheckConstraint(
            "status IN ('planned', 'cooked', 'cancelled')",
            name="ck_plan_status",
        ),
    )


class ShoppingListItem(Base):
    """Items to buy, linked optionally to a ProductionPlan or generic."""

    __tablename__ = "shopping_list_item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ingredient_id: Mapped[int] = mapped_column(
        ForeignKey("ingredient.id"), nullable=False, index=True
    )
    production_plan_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("production_plan.id", ondelete="SET NULL"), nullable=True
    )
    qty_to_buy: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(16), nullable=False)
    purpose_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    purchased: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    purchased_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    ingredient: Mapped["Ingredient"] = relationship("Ingredient")
    production_plan: Mapped[Optional["ProductionPlan"]] = relationship(
        back_populates="shopping_items"
    )

    __table_args__ = (
        CheckConstraint("qty_to_buy > 0", name="ck_shopping_qty_positive"),
        Index("ix_shopping_open", "purchased", "created_at"),
    )


class MarketBenchmark(Base):
    """Per-product pricing-vs-market row (HEREBUS Benchmarks_Market).

    Allows Saskia to position each recipe relative to local competitors.
    """

    __tablename__ = "market_benchmark"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recipe_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("recipe.id"), nullable=True, index=True
    )
    product_label: Mapped[str] = mapped_column(String(120), nullable=False)
    our_wholesale_gs: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    our_retail_gs: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    comp_min_gs: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    comp_avg_gs: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    market_avg_gs: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    position: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    source: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class BankTransaction(Base):
    """A bank transaction (Dutch TAB file or PY savings image import).

    Two currencies supported: PY Guaraní (₲) and EUR.
    The TAB bank is held in EUR by JGHM VAN DER POL (the Dutch owner).
    """

    __tablename__ = "bank_transaction"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    posted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    balance_after: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    counterparty_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    counterparty_iban: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reference: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="tab")
    account_holder: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    __table_args__ = (
        CheckConstraint("currency IN ('EUR', 'PYG', 'USD')", name="ck_bank_currency"),
        Index("ix_bank_date_account", "posted_at", "account_holder"),
        Index("ix_bank_category", "category", "posted_at"),
    )


class SettingsKV(Base):
    """Single-row-per-key config (hours, pickup address, etc).

    Stored as JSON value for flexibility — keeps Django-style "constance"
    without a 30+ single-purpose tables.
    """

    __tablename__ = "settings_kv"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value_json: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )



class Pedido(Base):
    """A pre-order (pedido) — Phase 3 (2026-09-17 prelaunch roadmap).

    Most pedidos come in via WhatsApp the day before or morning-of for pickup.
    A pedido can have multiple PedidoLine items. Status moves through
    pending → confirmed → ready → fulfilled, or is cancelled. A public
    pickup-share token (random base32-ish, 8 chars) is generated at create
    time so the customer can fetch a confirmation page without logging in.

    fields:
      customer_id           — optional FK to Customer (pickup may be a stranger)
      customer_name         — denormalized for WhatsApp pedidos with no Customer row
      customer_phone        — index for fast phone lookup; optional
      promised_date         — when the customer expects pickup (Date)
      promised_time         — "HH:MM" local Asunción; optional
      channel               — whatsapp | pedidosya | mostrador | phone | other
      status                — pending | confirmed | ready | fulfilled | cancelled
      payment_intent        — efectivo | transferencia | qr | tarjeta | otro
      notes                 — free text
      public_token          — 8-char unique URL token for /p/{token}
      fulfilled_at          — set by the /fulfill endpoint
      fulfilled_sale_id     — link to the first Sale created on fulfillment
                              (multi-line pedidos create N sales; only the first
                              is linked here for back-reference)
    """

    __tablename__ = "pedido"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customer.id"), index=True, nullable=True
    )
    customer_name: Mapped[str] = mapped_column(
        String(120), nullable=False, default=""
    )
    customer_phone: Mapped[str | None] = mapped_column(
        String(32), nullable=True, index=True
    )
    promised_date: Mapped[datetime] = mapped_column(Date, nullable=False, index=True)
    promised_time: Mapped[str | None] = mapped_column(String(8), nullable=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False, default="whatsapp")
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", index=True
    )
    payment_intent: Mapped[str] = mapped_column(
        String(32), nullable=False, default="efectivo"
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # HEREBUS integration: link to delivery zone (drives cost + min order)
    delivery_zone_id: Mapped[int | None] = mapped_column(
        ForeignKey("delivery_zone.id"), nullable=True, index=True
    )
    public_token: Mapped[str] = mapped_column(
        String(40), nullable=False, unique=True, index=True, default=""
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    fulfilled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    fulfilled_sale_id: Mapped[int | None] = mapped_column(
        ForeignKey("sale.id"), nullable=True, index=True
    )
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    lines: Mapped[list["PedidoLine"]] = relationship(
        back_populates="pedido", cascade="all, delete-orphan"
    )
    customer: Mapped["Customer | None"] = relationship()
    delivery_zone: Mapped["DeliveryZone | None"] = relationship(back_populates="pedidos")

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','confirmed','ready','fulfilled','cancelled')",
            name="ck_pedido_status",
        ),
    )


class PedidoLine(Base):
    """A line in a pedido. Mirrors the PedidoLine spec in the 2026-09-17 plan.

    qty is float (paraguay bakeries sell by weight too — 0.5 kg of bread, etc.).
    unit_price_gs is SNAPSHOT — even if the product's sale_price_gs changes later.
    fulfilled_qty starts at 0 and is updated when /pedidos/{id}/fulfill runs.
    """

    __tablename__ = "pedido_line"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pedido_id: Mapped[int] = mapped_column(
        ForeignKey("pedido.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("product.id"), nullable=False, index=True
    )
    qty: Mapped[float] = mapped_column(Float, nullable=False)
    unit_price_gs: Mapped[int] = mapped_column(Integer, nullable=False)
    fulfilled_qty: Mapped[float] = mapped_column(Float, nullable=False, default=0)

    pedido: Mapped["Pedido"] = relationship(back_populates="lines")
    product: Mapped["Product"] = relationship()

    __table_args__ = (
        CheckConstraint("qty > 0", name="ck_pedido_line_qty_positive"),
        CheckConstraint("unit_price_gs >= 0", name="ck_pedido_line_price_nonneg"),
    )





class Tenant(Base):
    """A multi-tenant boundary (E15).

    In single-tenant mode (today), exactly one Tenant row exists
    (slug="default") and every model implicitly references it.
    In multi-tenant mode, a future migration would add tenant_id to
    each table and isolate data per slug.
    """

    __tablename__ = "tenant"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    business_name: Mapped[str] = mapped_column(String(160), nullable=False)
    primary_color: Mapped[str] = mapped_column(String(16), nullable=False, default="#7b3f00")
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="Gs.")
    created_at: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)

class StockMovement(Base):
    """Append-only stock movement ledger for auditability.

    Every stock change (sale, adjustment, merma, reorder, initial stock)
    gets a row here so operators can trace exactly why an ingredient's
    stock changed over time.

    Fields:
      id             — PK
      ingredient_id  — FK to ingredient.id
      movement_type  — sale | adjustment | merma | reorder | initial
      qty            — signed: positive=in, negative=out
      reason         — free-text label (e.g. "rotura de envase", "recount")
      reference_id   — FK to the triggering row (sale.id, WasteLog.id, etc.);
                       NULL for initial-stock records
      reference_type — 'sale' | 'waste_log' | 'adjustment' | 'reorder' | None
      recorded_at    — UTC datetime; default now()
      created_by     — operator username or 'operator'; NULL for system records
    """

    __tablename__ = "stock_movement"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ingredient_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("ingredient.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    movement_type: Mapped[str] = mapped_column(String(16), nullable=False)
    qty: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reference_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reference_type: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, index=True
    )
    created_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "movement_type IN ('sale','adjustment','merma','reorder','initial')",
            name="ck_stock_movement_type",
        ),
        Index("ix_stock_movement_ingredient_recorded", "ingredient_id", "recorded_at"),
    )

    # Relationships
    ingredient: Mapped["Ingredient"] = relationship("Ingredient")


__all__ = [
    "Base",
    "AppMeta",
    "AuditLog",
    "Ingredient",
    "IngredientPriceEvent",
    "Recipe",
    "RecipeLine",
    "Product",
    "Sale",
    "SaleStockMove",
    "ImportBatch",
    "User",
    "Tag",
    "TagLink",
    "Tenant",
    "Customer",
    "WasteLog",
    "Pedido",
    "PedidoLine",
    "StockMovement",
    "Supplier",
    "ProductionCompletion",
    "ProductionPlanTemplate",
    "ProductionPlanOverride",
    # HEREBUS Drive integration — migration 029
    "DeliveryZone",
    "WishlistItem",
    "RiskItem",
    "RecipePricing",
    "PriceHistory",
    "ProductionPlan",
    "ShoppingListItem",
    "MarketBenchmark",
    "BankTransaction",
    "SettingsKV",
]
