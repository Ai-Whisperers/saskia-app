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
    prep_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
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

    # Relationships
    lines: Mapped[list["PedidoLine"]] = relationship(
        back_populates="pedido", cascade="all, delete-orphan"
    )
    customer: Mapped["Customer | None"] = relationship()

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
]
