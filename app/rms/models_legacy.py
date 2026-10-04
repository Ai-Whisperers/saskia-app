"""app/rms/models.py — SQLAlchemy ORM models.

Per dev plan §9 Task 1 + v2 §5 (data model).

Tables:
- ingredient: name, unit, stock_qty, purchase_price_gs (int), min_stock_qty, notes
- recipe: name, yield_qty, yield_unit, notes
- recipe_line: polymorphic via line_kind + line_ref_id (FK to ingredient OR recipe)
- product: name, portion_label, sale_price_gs (int), recipe_id (nullable)
- sale: sold_at, product_id, qty, unit_price_gs (snapshot int), notes
- sale_stock_move: dropped (BACKLOG #1; sale-driven stock-out now lives in stock_movement)
- import_batch: imported_at, source_filename, note, row_counts_json
- app_meta: key, value, updated_at (schema version, last_backup_at, etc.)
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Optional

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
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """SQLAlchemy declarative base. All models inherit from this."""


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
    # BACKLOG #13 (2026-10-02): moving-average cost per unit in Gs. NULL
    # means "not yet computed" — analytics fall back to purchase_price_gs.
    # Updated on each waste event using the formula
    #   new_avg = ((old_avg * old_stock) - waste_cost) / new_stock
    # when new_stock > 0, else NULL.
    avg_cost_gs: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
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
    # Migration 061: pre-computed list of logical contradictions in this
    # ingredient's tags (e.g. "declares 'vegano' but allergens include dairy").
    # Newline-separated. NULL = no issues or never computed.
    # Populated by app.rms.tagging.audit.backfill_validation_issues() and
    # refreshed whenever allergens / dietary_tags / name changes.
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
    # SINACLA cross-contamination (migration 054): blocks "sin tacc" derivation.
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
    # S7 Decision B — per-ingredient forecast horizon. NULL = use global default
    # (DEFAULT_FORECAST_HORIZON_DAYS env var, typically 14).
    forecast_horizon_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # S8 US 4.1 — flag ingredients that are packaging items (boxes, bags,
    # ribbons) rather than food ingredients. Packaging items live in the
    # same table for inventory simplicity but are sold, not consumed by
    # recipes. See app/rms/costing.py:apply_sale for the per-sale wiring.
    is_packaging: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    # Phase 2 — Expiry date for ingredient lot tracking (HACCP / FIFO).
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    # Migration 072 (P2 reorder redesign, 2026-09-30): reorder-supplier
    # tracking. `last_purchase_supplier_id` is the source of truth for the
    # dropdown default on /reorder (pre-seeded from `supplier_id` so
    # existing ingredients don't show "sin registro" on first visit).
    # `purchase_streak_count` increments when she buys from the same
    # supplier twice in a row, resets on a change. At 3 it triggers
    # `locked_supplier_id`, which makes the dropdown default to that
    # supplier and shows the "fijo" badge.
    last_purchase_supplier_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("supplier.id"), nullable=True, index=True
    )
    last_purchase_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    purchase_streak_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    locked_supplier_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("supplier.id"), nullable=True
    )

    # Relationships
    # NOTE: `recipe_lines` (the reverse of RecipeLine.ingredient) is NOT defined here
    # because RecipeLine.line_ref_id is polymorphic (FK to ingredient OR recipe).
    # Use RecipeLine.ingredient relationship (viewonly=True, primaryjoin with line_kind check)
    # or query RecipeLine directly: SELECT FROM recipe_line WHERE line_kind='ingredient'
    # AND line_ref_id = :id. Helper functions live in costing.py.
    # BACKLOG #1: the legacy `stock_moves` relationship to SaleStockMove
    # is removed. Use `StockMovement` rows joined on `ingredient_id`
    # filtered by movement_type='sale' instead (see /reportes/consumo).
    supplier: Mapped[Optional["Supplier"]] = relationship(
        back_populates="ingredients", foreign_keys=[supplier_id]
    )
    last_purchase_supplier: Mapped[Optional["Supplier"]] = relationship(
        foreign_keys=[last_purchase_supplier_id]
    )
    locked_supplier: Mapped[Optional["Supplier"]] = relationship(foreign_keys=[locked_supplier_id])
    # S7 Decision A1 — one Ingredient has many IngredientVariants (1kg, 250g, etc).
    variants: Mapped[list["IngredientVariant"]] = relationship(
        back_populates="ingredient",
        cascade="all, delete-orphan",
        order_by="IngredientVariant.preferred.desc(), IngredientVariant.package_size",
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
    supplier: Mapped[Optional["Supplier"]] = relationship()

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

    def __repr__(self) -> str:
        return (
            f"<IngredientVariant id={self.id} "
            f"ingredient_id={self.ingredient_id} "
            f"package_size={self.package_size} {self.package_unit} "
            f"price={self.purchase_price_gs} "
            f"preferred={self.preferred}>"
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
    # UI-V2 (migration 068): multi-select "Etiquetas de Menú" — comma-separated.
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
    # Recipe instructions: JSON array of {phase, title, steps}
    instructions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    lines: Mapped[list["RecipeLine"]] = relationship(
        back_populates="recipe",
        foreign_keys="RecipeLine.recipe_id",
        cascade="all, delete-orphan",
    )
    products: Mapped[list["Product"]] = relationship(back_populates="recipe")
    # BACKLOG #1: legacy SaleStockMove relationship removed. Use
    # StockMovement.affected_recipe_id instead (one row per recipe+ingredient
    # pair consumed by sales of this recipe).

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
    qty: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
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
    # P3 UX batch: quick-sale "Favoritos" filter persists here.
    is_favorite: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Comma-separated tags

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

    # Phase 2 — Wholesale / mayorista price (B2B channel).
    mayorista_price_gs: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # C2 — Public tablet-menu slug. Unique URL-safe identifier for the
    # customer-facing `/m/{slug}` page. NULL means the product is NOT
    # visible on the tablet menu (operators can opt-in per product).
    # Stored as a normalised lowercase alphanumeric slug (max 60 chars)
    # so URLs are short enough to type on a 1280×720 tablet display.
    tablet_slug: Mapped[Optional[str]] = mapped_column(
        String(60), nullable=True, unique=True, index=True
    )
    # Whether the product shows on the public tablet menu. Default True
    # so existing products auto-appear; the operator can flip this off to
    # hide specific items (e.g., items only sold at-mostrador).
    tablet_visible: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )

    # Phase 1.C — HACCP + costing (lazy fields; detailed cost fields added in Phase 1.D)
    yield_percentage: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    inherited_tags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # 0.85 default = 15% moisture loss for breads (matches industry standard).
    # Operators can override per recipe.

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
    customer_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("customer.id"), nullable=True, index=True
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sold_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"), nullable=False, index=True)
    qty: Mapped[float] = mapped_column(Float, nullable=False)
    unit_price_gs: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    voided_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # CIE-01: cancellation audit trail. Nullable so legacy rows and fresh
    # sales don't need to populate them. Operators fill in via the
    # /ventas/{id}/anular modal when voiding.
    void_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    voided_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    # S8 US 4.1 — per-sale packaging (audio review: "the box for the cake").
    # The same product sold different ways (local/eat-in/to-go/event) may
    # need different packaging; the choice is on the SALE, not the product.
    # packaging_item_id must point to an Ingredient with is_packaging=True.
    # packaging_qty is NULL when there's no packaging (eat-in local sale).
    packaging_item_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("ingredient.id"), nullable=True, index=True
    )
    packaging_qty: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
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
    iva_rate: Mapped[str] = mapped_column(
        String(8), nullable=False, default="10", server_default="10"
    )
    iva_base_gs: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    iva_amount_gs: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    # Migration 076 — back-pointer to the Pedido that produced this Sale.
    # Nullable because most sales are POS-driven (no pedido). When a Sale
    # is generated by /pedidos/<id>/fulfill, the fulfill handler sets this
    # to pedido.id so we can walk sale↔pedido symmetrically. Indexed
    # because the detail-page timeline joins on this column.
    linked_pedido_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("pedido.id"), nullable=True, index=True
    )

    # BACKLOG #17 (Migration 085) — /r/{token} public digital recibo.
    # public_token is populated on first /ventas/{id}/share call; until
    # then it's NULL. public_token_expires_at follows the same 30-day
    # convention as pedido.public_token_expires_at (migration 067).
    # public_token_shared_at records when the operator last generated
    # the URL (for "Last shared" display on /ventas/{id}).
    public_token: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    public_token_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    public_token_shared_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    product: Mapped["Product"] = relationship(back_populates="sales")
    customer: Mapped[Optional["Customer"]] = relationship(back_populates="sales")
    # BACKLOG #1: legacy SaleStockMove relationship removed. Use
    # StockMovement joined on reference_id=sale.id AND
    # reference_type='sale' instead (see /ventas/{id} detail page).
    linked_pedido: Mapped[Optional["Pedido"]] = relationship(
        "Pedido", foreign_keys=[linked_pedido_id], viewonly=True
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
    """DEPRECATED stub — sale_stock_move table removed by migration 092 (BACKLOG #1).

    The class is preserved as an abstract stub so test fixtures and
    historical imports (`from app.rms.models import SaleStockMove`)
    don't break at import time. The actual table no longer exists in
    the database (migration 092 dropped it). Use StockMovement with
    movement_type='sale' and reference_type='sale' instead.

    `__abstract__ = True` tells SQLAlchemy to NOT configure a mapper
    or create any table for this class. The class is therefore just
    a name that resolves to a class object — instantiating it raises
    TypeError via the __init__ guard below, so legacy code paths
    can't sneak in a row write.

    Column aliases (`qty_delta`, `sale_id`, `ingredient_id`,
    `affected_recipe_id`, `sale`) are provided as class-level
    InstrumentedAttributes pointing at the matching StockMovement
    columns. They exist purely so legacy query code that wrote
    `SaleStockMove.qty_delta` keeps resolving (returns the same data
    via the StockMovement source-of-truth table). New code should
    NOT use these aliases — they are here as a backwards-compat
    shim and may be removed in a future cleanup.
    """

    __abstract__ = True  # SQLAlchemy: skip table + mapper config

    # NOTE: legacy column aliases (qty_delta, sale_id, ingredient_id,
    # affected_recipe_id, sale) are attached to this class at the
    # bottom of models_legacy.py — after StockMovement has been
    # defined — as class-level references into StockMovement's
    # InstrumentedAttributes. See the post-class binding block at
    # the end of this file.

    def __init__(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover — guard
        raise TypeError(
            "SaleStockMove is deprecated — sale_stock_move table was "
            "dropped by migration 092. Use StockMovement with "
            "movement_type='sale' and reference_type='sale' instead."
        )


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
    role: Mapped[str] = mapped_column(
        String(32), nullable=False, default="admin"
    )  # admin, cashier, manager
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
    recorded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="restock")
    # Migration 073 (2026-10-01): tag every event with the supplier that
    # quoted this price. NULL for historical rows from before the column
    # existed; populated by /reorder/registrar (when supplier_id is
    # provided) and by the CSV price upload. ``ON DELETE SET NULL`` so
    # soft-deleted suppliers don't orphan their price history.
    supplier_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("supplier.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

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
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # P3 delivery batch: operator's default zone for this customer
    preferred_zone_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # P3 dietary batch: hard restrictions (CSV of CANONICAL_DIETARY_TAGS),
    # approved substitutes in preference order (JSON [{tag, rank, note}]),
    # and the confirm-always flag (ask every order before substituting).
    # P3 profile batch: retention + comms + facturación defaults
    birthday: Mapped[str | None] = mapped_column(String(10), nullable=True)  # MM-DD or YYYY-MM-DD
    how_found: Mapped[str | None] = mapped_column(String(32), nullable=True)
    preferred_channel: Mapped[str | None] = mapped_column(String(32), nullable=True)
    marketing_consent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    invoice_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    invoice_ruc: Mapped[str | None] = mapped_column(String(20), nullable=True)
    dietary_restrictions: Mapped[str | None] = mapped_column(Text, nullable=True)
    dietary_preferences: Mapped[str | None] = mapped_column(Text, nullable=True)
    dietary_confirm_always: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Relationships
    sales: Mapped[list["Sale"]] = relationship(back_populates="customer")
    addresses: Mapped[list["CustomerAddress"]] = relationship(
        back_populates="customer", cascade="all, delete-orphan"
    )


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
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

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

    T-2026-10-04 (Tier 5-K): added ``updated_at`` so two cooks editing
    the same shift in parallel don't silently overwrite each other.
    Migration 099 adds the column on existing DBs. SQLAlchemy won't
    enforce the default here — SQLite / Postgres handle DEFAULT.
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
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

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


class ProductionClosedDay(Base):
    """T-2026-10-04 (P1): Whole-day flag marking a date as closed.

    Used for holidays, vacations, equipment failures, etc. When a date
    has a row in this table, the production plan returns an empty plan
    regardless of the weekly template or forecast.

    One row per date (PRIMARY KEY on for_date) — there is no concept
    of "closed for half a day" because the bakery either opens or
    doesn't.
    """

    __tablename__ = "production_closed_day"

    for_date: Mapped[date] = mapped_column(Date, primary_key=True)
    reason: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    closed_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    closed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


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
    ruc: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    # Migration 072 added two more FKs back to this table from
    # ingredient (last_purchase_supplier_id + locked_supplier_id), so
    # the relationship below needs an explicit `foreign_keys` to tell
    # SQLAlchemy which FK is the join column. Without it, the mapper
    # raises "multiple foreign key paths linking the tables" on
    # initialization (test_reorder_supplier_redesign.py proves it).
    ingredients: Mapped[list["Ingredient"]] = relationship(
        back_populates="supplier",
        foreign_keys="Ingredient.supplier_id",
    )
    # These two reverse views are read-only — the writes go through the
    # forward `Ingredient.last_purchase_supplier` /
    # `Ingredient.locked_supplier` relationships. `viewonly=True` plus
    # `overlaps=` silences SQLAlchemy's "multiple FK paths" warning.
    last_purchase_ingredients: Mapped[list["Ingredient"]] = relationship(
        foreign_keys="Ingredient.last_purchase_supplier_id",
        viewonly=True,
        overlaps="last_purchase_supplier",
    )
    locked_ingredients: Mapped[list["Ingredient"]] = relationship(
        foreign_keys="Ingredient.locked_supplier_id",
        viewonly=True,
        overlaps="locked_supplier",
    )

    __table_args__ = (Index("ix_supplier_name", "name"),)


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
# Expense model (migration 082, Phase 14 2026-10-01)
# ──────────────────────────────────────────────────────────────────


class Expense(Base):
    """An operating-expense row (Phase 14).

    Used by `daily_summary()` to subtract real expenses from margin
    (until now it returned `expenses_placeholder_gs=0`). Also feeds
    cierres mensuales.

    Categories: INGREDIENT | RENT | UTILITIES | PAYROLL | PACKAGING |
                OTHER. amount_gs is always positive — sign applied at
    aggregate time. is_voided=True preserves audit trail while removing
    the row from aggregates (same pattern as Sale.voided_at).
    """

    __tablename__ = "expense"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    amount_gs: Mapped[int] = mapped_column(Integer, nullable=False)
    is_voided: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    # Optional bookkeeping: who logged it + an optional supplier FK
    # for INGREDIENT expenses (lets you trace flour from supplier X).
    created_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    supplier_id: Mapped[Optional[int]] = mapped_column(ForeignKey("supplier.id"), nullable=True)
    # Sprint 3.1: receipt URL and recurring period tracking
    receipt_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    recurring_period: Mapped[str] = mapped_column(String(32), nullable=False, default="once")

    __table_args__ = (
        CheckConstraint("amount_gs >= 0", name="ck_expense_amount_nonneg"),
        CheckConstraint(
            "category IN ('INGREDIENT','RENT','UTILITIES','PAYROLL','PACKAGING','OTHER')",
            name="ck_expense_category",
        ),
        CheckConstraint(
            "recurring_period IN ('once','monthly','quarterly','yearly')",
            name="ck_expense_recurring_period",
        ),
    )

    supplier: Mapped[Optional["Supplier"]] = relationship("Supplier")


# ──────────────────────────────────────────────────────────────────
# HEREBUS Drive integration — new modules (migration 029)
# ──────────────────────────────────────────────────────────────────


class CustomerAddress(Base):
    """A delivery address for a customer (P3 delivery batch).

    One customer can have many (casa / oficina / "casa de mi mamá").
    `zone_id` optionally pre-fills the pedido's delivery zone; cost still
    comes from the zone at pedido time. `label` is operator-facing short
    text ("casa", "oficina"); `address_text` is the full directions text.

    Phase 13 (2026-10-01): extended with structured fields so the cashier
    can optionally fill calle/secundaria/número/edificio/piso/unidad/
    barrio/ciudad/departamento/pais/postal/recipient_name/
    delivery_instructions. address_text stays as the legacy composed
    string (rendered for receipts + dispatch tickets). The pick alias
    is `label`; address_kind discriminates HOME/WORK/FAMILY/OTHER.
    """

    __tablename__ = "customer_address"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customer.id"), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(32), nullable=False, default="casa")
    address_text: Mapped[str] = mapped_column(Text, nullable=False)
    zone_id: Mapped[int | None] = mapped_column(ForeignKey("delivery_zone.id"), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    # ── Phase 13: structured address fields (research-backed)
    # MercadoLibre PY uses discrete street_name+street_number+floor+apartment;
    # Lightspeed X uses 2 address lines + suburb + city + state + country.
    # These are all optional; existing address_text remains the rendered
    # "what the cashier sees" and is composed from these at write time.
    calle_principal: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    calle_secundaria: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    numero: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    edificio: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    piso: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    unidad: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    barrio: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    ciudad: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    departamento: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    pais: Mapped[Optional[str]] = mapped_column(String(8), nullable=True, default="PRY")
    codigo_postal: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    recipient_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    delivery_instructions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # address_kind: HOME | WORK | FAMILY | OTHER (app-layer enum)
    address_kind: Mapped[Optional[str]] = mapped_column(String(16), nullable=True, default="HOME")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    customer: Mapped["Customer"] = relationship(back_populates="addresses")
    zone: Mapped[Optional["DeliveryZone"]] = relationship()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<CustomerAddress {self.id} c={self.customer_id} {self.label!r}>"


class CustomerInvoiceProfile(Base):
    """Multiple invoice profiles per customer (Phase 13, 2026-10-01).

    Research (Wise Platform "profiles", Shopify B2B "CompanyLocation",
    Stripe "TaxID collection") — one person can invoice under many tax
    identities: personal CI, spouse's RUC, their own company RUC. Today's
    Customer has a single invoice_ruc + invoice_name which prevents this.

    The cashier picks the WHOLE profile (alias + RUC + razon_social +
    tipo_documento + tipo_operacion) — the e-invoice later locks RUC↔name
    so they must travel together. SIFEN defines 7 tipos de documento
    and 4 tipos de operación; we expose those as DB CHECK constraints
    (see migration 080).

    Single `Customer.invoice_ruc` / `invoice_name` columns are kept for
    backward compat (the latest-write-wins behavior stays for the
    rare legacy path). The migration backfilled one profile per
    customer that had legacy RUC/name set.
    """

    __tablename__ = "customer_invoice_profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customer.id"), nullable=False, index=True)
    alias: Mapped[str] = mapped_column(String(64), nullable=False)
    ruc_ci: Mapped[str] = mapped_column(String(20), nullable=False)
    razon_social: Mapped[str] = mapped_column(String(160), nullable=False)
    # tipo_documento: 1:Cedula paraguaya, 2:Pasaporte, 3:Cedula extranjera,
    # 4:Carnet de residencia, 5:Innominado, 6:Tarjeta Diplomatica exoneracion,
    # 7:Otro — see SIFEN spec (https://sisfe.com.py/documentacion.html)
    tipo_documento: Mapped[str] = mapped_column(String(32), nullable=False, default="CI_PARAGUAYA")
    # tipo_operacion: 1:B2B, 2:B2C, 3:B2G, 4:B2F (extranjero)
    tipo_operacion: Mapped[str] = mapped_column(String(16), nullable=False, default="B2C")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    customer: Mapped["Customer"] = relationship()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<CustomerInvoiceProfile {self.id} c={self.customer_id} {self.alias!r} {self.ruc_ci!r}>"


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

    __table_args__ = (Index("ix_delivery_zone_active", "is_active", "position"),)


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
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

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
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint("probability BETWEEN 1 AND 5", name="ck_risk_prob_range"),
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
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipe.id"), nullable=False, index=True)
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
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

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

    # Reconciliation fields (added in migration 056)
    reconciled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reconciled_with_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    reconciled_with_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reconciled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    reconciled_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        CheckConstraint("currency IN ('EUR', 'PYG', 'USD')", name="ck_bank_currency"),
        Index("ix_bank_date_account", "posted_at", "account_holder"),
        Index("ix_bank_category", "category", "posted_at"),
        Index("ix_bank_reconciled", "reconciled", "posted_at"),
        Index("ix_bank_reconciled_with", "reconciled_with_type", "reconciled_with_id"),
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
    customer_name: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    customer_phone: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    promised_date: Mapped[datetime] = mapped_column(Date, nullable=False, index=True)
    promised_time: Mapped[str | None] = mapped_column(String(8), nullable=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False, default="whatsapp")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", index=True)
    payment_intent: Mapped[str] = mapped_column(String(32), nullable=False, default="efectivo")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # HEREBUS integration: link to delivery zone (drives cost + min order)
    delivery_zone_id: Mapped[int | None] = mapped_column(
        ForeignKey("delivery_zone.id"), nullable=True, index=True
    )
    # P3 delivery batch: address snapshot + acceptable arrival window +
    # factura data (RUC required for facturas, not boletas).
    address_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivery_window_start: Mapped[str | None] = mapped_column(String(8), nullable=True)
    delivery_window_end: Mapped[str | None] = mapped_column(String(8), nullable=True)
    invoice_ruc: Mapped[str | None] = mapped_column(String(20), nullable=True)
    invoice_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # Phase 13 (2026-10-01): preferred delivery window semantics
    # 'asap' (default), 'window' (window_start..end are guidance, not a
    # promise — matches Instacart "desired windows"), 'scheduled' (future
    # date). See _render_ventana_preferida in app/templates for the
    # "ventana preferida: 14:00–16:00 (no es garantía)" rendering.
    delivery_preference: Mapped[str | None] = mapped_column(String(16), nullable=True)
    delivery_scheduled_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    # Phase 13: FKs linking the pedido to the chosen invoice profile
    # (multiple per customer, SIFEN-compliant) and chosen address
    # (multiple per customer, alias-driven picker).
    customer_invoice_profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("customer_invoice_profile.id"), nullable=True, index=True
    )
    customer_address_id: Mapped[int | None] = mapped_column(
        ForeignKey("customer_address.id"), nullable=True, index=True
    )
    public_token: Mapped[str] = mapped_column(
        String(40), nullable=False, unique=True, index=True, default=""
    )
    # P1-2: 30-day expiry for /p/{token} pickup links. NULL = legacy
    # row pre-dating schema v67 (treated as expired — see
    # _is_token_valid() in app/routers/pedidos.py).
    public_token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
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
    # P1-B3: customer-uploaded comprobante de pago from /p/{public_token}.
    # Relative path like "payment_receipts/123/2026-09-29_141503.jpg".
    payment_receipt_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    payment_receipt_uploaded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    lines: Mapped[list["PedidoLine"]] = relationship(
        back_populates="pedido", cascade="all, delete-orphan"
    )
    customer: Mapped["Customer | None"] = relationship()
    delivery_zone: Mapped["DeliveryZone | None"] = relationship(back_populates="pedidos")
    invoice_profile: Mapped["CustomerInvoiceProfile | None"] = relationship()
    address: Mapped["CustomerAddress | None"] = relationship()
    # Migration 076 — every Sale generated by fulfilling this pedido.
    # Note: fulfilled_sale_id points at the FIRST sale (legacy); this
    # collection includes the rest when the pedido has multiple lines.
    sales: Mapped[list["Sale"]] = relationship(
        "Sale", foreign_keys="Sale.linked_pedido_id", viewonly=True
    )

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
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"), nullable=False, index=True)
    qty: Mapped[float] = mapped_column(Float, nullable=False)
    unit_price_gs: Mapped[int] = mapped_column(Integer, nullable=False)
    fulfilled_qty: Mapped[float] = mapped_column(Float, nullable=False, default=0)

    pedido: Mapped["Pedido"] = relationship(back_populates="lines")
    product: Mapped["Product"] = relationship()

    __table_args__ = (
        CheckConstraint("qty > 0", name="ck_pedido_line_qty_positive"),
        CheckConstraint("unit_price_gs >= 0", name="ck_pedido_line_price_nonneg"),
    )


class PedidoEvent(Base):
    """Migration 077 (2026-10-01): per-pedido edit log.

    Append-only timeline of every meaningful change to a pedido.
    Distinct from AuditLog: scope is per-pedido (joined cheaply on
    pedido_id) and granularity captures line edits + note changes +
    window adjustments, not just security events.

    event_type values (constrained by ck_pedido_event_type):
      - created             pedido row first inserted
      - status_change       status transition (e.g. pending -> confirmed)
      - line_added          a PedidoLine was added
      - line_removed        a PedidoLine was deleted
      - line_qty_changed    qty on an existing line was edited
      - line_price_changed  unit_price_gs was edited
      - note_edited         notes text changed
      - address_changed     address_text / delivery_zone_id changed
      - window_changed      delivery_window_start/end changed
      - customer_changed    customer_id reassigned
      - payment_intent_set  payment_intent changed
      - cancelled           status='cancelled' with reason
      - duplicated          pedido duplicated from this one

    payload_json captures the structured diff. Examples:
      - status_change: {"from": "pending", "to": "confirmed"}
      - line_added: {"product_id": 17, "qty": 2.0, "unit_price_gs": 28000}
      - cancelled: {"reason": "cliente avisó tarde"}

    Index on (pedido_id, ts) for cheap timeline rendering.
    """

    __tablename__ = "pedido_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pedido_id: Mapped[int] = mapped_column(
        ForeignKey("pedido.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ts: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(64), nullable=False, default="system")
    event_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    pedido: Mapped["Pedido"] = relationship()

    __table_args__ = (
        Index("ix_pedido_event_pedido_ts", "pedido_id", "ts"),
        CheckConstraint(
            "event_type IN ('created','status_change','line_added','line_removed',"
            "'line_qty_changed','line_price_changed','note_edited','address_changed',"
            "'window_changed','customer_changed','payment_intent_set','cancelled',"
            "'duplicated')",
            name="ck_pedido_event_type",
        ),
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
    # Migration 090 (BACKLOG #1): affected_recipe_id added for
    # sub-recipe traceability. Migration 091 backfilled from
    # sale_stock_move. Migration 092 dropped sale_stock_move entirely.
    # Nullable because non-sale movements (reorder, merma, adjustment,
    # initial) don't have an affected recipe.
    affected_recipe_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("recipe.id"), nullable=True, index=True
    )
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


class ComplianceInfo(Base):
    """Phase 1.A — Single-row table for Paraguayan tax / regulatory IDs.

    Required by DNIT (IVA, IRE/RESIMPLE, SIFEN), INAN (R.E., Director Técnico),
    and municipal (habilitación comercial). One row only; updated via
    /configuracion.

    The model intentionally stores the IDs as nullable strings (not enums) so
    the operator can paste them verbatim from RUC cards / habilitación papers
    without us validating format. Validation lives in the form layer.

    date fields are ISO strings (not Date columns) so an operator can paste
    "31/12/2027" or "2027-12-31" — we parse on save and reformat on display.
    """

    __tablename__ = "compliance_info"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)

    # DNIT / SET identification
    ruc: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    razon_social: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    nombre_fantasia: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    # Tax regime: 'general' (IVA General + IRE General) or 'resimple' (IRE RESIMPLE
    # only, with Boleta Resimple) or 'no_libreta' (informal, no DNIT obligations).
    tax_regime: Mapped[str] = mapped_column(String(16), nullable=False, default="resimple")

    # Default IVA rate applied when creating new products.
    # ∈ {5, 10, 'exento'}. Override per product via Product.iva_rate.
    iva_default_rate: Mapped[str] = mapped_column(String(8), nullable=False, default="10")

    # RESIMPLE-specific: timbrado number for Boleta Resimple (mandatory)
    timbrado_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    timbrado_expiry: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # ISO

    # Next sequential invoice number per type. Updated atomically on each sale.
    next_boleta_resimple_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    next_factura_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # INAN — Registro de Establecimiento
    inan_re_number: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    inan_re_expiry: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # ISO
    director_tecnico: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    director_tecnico_registro: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)

    # Municipal habilitación comercial
    municipal_habilitacion: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    municipal_habilitacion_expiry: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    # Establecimiento físico (used on invoice header)
    establecimiento_address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    establecimiento_phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    establecimiento_email: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    # Logo path (relative to /static/) — surfaced on invoice print + dashboard
    logo_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Phase 1.D — Costing config
    labor_cost_per_hour_gs: Mapped[int] = mapped_column(Integer, nullable=False, default=25000)
    overhead_multiplier_pct: Mapped[int] = mapped_column(Integer, nullable=False, default=15)

    # SIFEN prep (Phase 1.F)
    sifen_certificate_id: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    sifen_csc_code: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    sifen_test_mode: Mapped[bool] = mapped_column(default=True, nullable=False)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class DateRangePreset(Base):
    """Operator-tunable date range presets (migration 048).

    Replaces the hardcoded DATE_RANGE_PRESETS_DAYS dict in
    app/rms/constants.py. Operators add/edit presets from
    /settings/catalog without code deploy.

    Used by date-filter chips in dashboard / reportes.
    """

    __tablename__ = "date_range_preset"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    label: Mapped[str] = mapped_column(String(64), nullable=False)
    days: Mapped[int] = mapped_column(Integer, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (Index("ix_date_range_preset_active_sort", "is_active", "sort_order"),)


class StorageType(Base):
    """HACCP storage codes (migration 047).

    Operator-configurable list of storage codes used in ingredient.storage.
    Replaces the hardcoded _STORAGE_KEYWORDS dict in
    app/rms/ingredient_intel.py which had fixed "refrigerated", "frozen",
    "ambient" codes.

    Schema:
      - id, code (unique)
      - label (Spanish display name)
      - requires_temp_min/max, requires_humidity_max (HACCP hints)
      - sort_order, is_active
    """

    __tablename__ = "storage_type"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    label: Mapped[str] = mapped_column(String(64), nullable=False)
    requires_temp_min: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    requires_temp_max: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    requires_humidity_max: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (Index("ix_storage_type_active_sort", "is_active", "sort_order"),)


class MarginTier(Base):
    """Operator-tunable margin tier thresholds (migration 045).

    Replaces the hardcoded if-chain in app/rms/tags.py:378-382 that used
    magic numbers (10000 / 5000 / 1000 Gs) to filter recipes into
    "top 10%" / "top 25%" / "bottom 25%" tiers.

    Schema:
      - id, code (unique)
      - label (display name, e.g. "Top 10%")
      - min_cost_gs (nullable; recipes with cost >= this value)
      - max_cost_gs (nullable; recipes with cost <= this value)
      - sort_order
      - is_active

    Operators can adjust tier thresholds when the economy shifts without
    code deploy.
    """

    __tablename__ = "margin_tier"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    label: Mapped[str] = mapped_column(String(64), nullable=False)
    min_cost_gs: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_cost_gs: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (Index("ix_margin_tier_active_sort", "is_active", "sort_order"),)


class StockStatusConfig(Base):
    """Operator-tunable stock status thresholds (migration 046).

    Replaces the hardcoded magic numbers in app/rms/tags.py:325-331 that
    defined:
      - bajo_min: stock < min_stock_qty (no parameter; just the comparison)
      - critico: stock_qty / min_stock_qty < 0.5
      - sobrestock: stock_qty / min_stock_qty > 5.0
      - muerto: no consumption in last N days (default 30)

    Each row = one stock status code + its thresholds. Operators adjust
    via /api/stock-status-config.

    Schema:
      - id, code (unique)
      - label (display name)
      - threshold_ratio (for critico/sobrestock; nullable if not used)
      - threshold_days (for muerto; nullable if not used)
      - sort_order
      - is_active
    """

    __tablename__ = "stock_status_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    label: Mapped[str] = mapped_column(String(64), nullable=False)
    threshold_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    threshold_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    __table_args__ = (Index("ix_stock_status_config_active", "is_active", "sort_order"),)


class StorageKeyword(Base):
    """Operator-tunable HACCP storage keyword map (migration 049).

    Replaces the hardcoded _STORAGE_KEYWORDS dict in
    app/rms/ingredient_intel.py. Operators add/edit storage keywords from
    /settings/catalog without code deploy.

    Schema:
      - id, storage_code (links to storage_type.code)
      - keyword (lowercase substring matched against ingredient name)
      - sort_order (priority — lower = checked first)
      - is_active

    When infer_storage() runs on an ingredient name, it normalizes the
    name (lowercase + stripped) and checks for substring matches against
    the keyword list, sorted by sort_order.
    """

    __tablename__ = "storage_keyword"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    storage_code: Mapped[str] = mapped_column(String(32), nullable=False)
    keyword: Mapped[str] = mapped_column(String(64), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_storage_keyword_active_sort", "storage_code", "is_active", "sort_order"),
    )


class Channel(Base):
    """Operator-configurable sale channel catalog (migration 041).

    Replaces hardcoded CHANNELS_DISPLAY / ALLOWED_CHANNELS frozenset
    previously in app/rms/schemas.py. Operators add/edit channels from
    /settings/channels without a code deploy.

    The sale.channel column stays as a free-text VARCHAR for now (no FK)
    so existing rows don't break and adding a new channel doesn't require
    a backfill. New writes should use the channel code from this table.
    """

    __tablename__ = "channel"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    label: Mapped[str] = mapped_column(String(64), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (Index("ix_channel_active_sort", "is_active", "sort_order"),)


class PaymentMethod(Base):
    """Operator-configurable payment method catalog (migration 042).

    Replaces hardcoded PAYMENT_METHODS_DISPLAY / ALLOWED_PAYMENT_METHODS
    frozenset previously in app/rms/schemas.py.

    fee_pct: % surcharge/discount for using this method (e.g., tarjeta
    may have +3% fee). 0 = no adjustment. Future use: sales apply this
    automatically. Today: just informational.
    """

    __tablename__ = "payment_method"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    label: Mapped[str] = mapped_column(String(64), nullable=False)
    requires_reference: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    fee_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (Index("ix_payment_method_active_sort", "is_active", "sort_order"),)


class MessageTemplate(Base):
    """Operator-editable message templates (Phase 6).

    Replaces hardcoded copy in app/routers/pedidos.py, notifications,
    email/WhatsApp copy throughout. Kiki can edit copy from
    /settings/templates without a code deploy.

    Schema:
      - id, channel (email | whatsapp | sms), key (template identifier),
        subject (nullable; emails only), body (the template body),
        locale (es-PY default; future i18n), is_active, version, notes
        updated_at

    Body uses {placeholders} like Python str.format() — substitute
    variables at send time (e.g., {customer_name}, {order_total}).
    """

    __tablename__ = "message_template"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(200), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    locale: Mapped[str] = mapped_column(String(8), nullable=False, default="es-PY")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    __table_args__ = (
        UniqueConstraint("channel", "key", "locale", name="uq_message_template_chan_key_locale"),
        Index("ix_message_template_chan_active", "channel", "is_active"),
    )


class CommunicationLog(Base):
    """Migration 078 (2026-10-01): outbound & inbound message log.

    Append-only log of every communication sent to or received from a
    customer (WhatsApp, email, SMS, manual note). Distinct from
    AuditLog because:
      - Scope: per-customer (joined on customer_id) and per-pedido
        (optional join on pedido_id when the message relates to an order)
      - Content: the actual rendered message body + delivery status,
        not just a security event

    Used by:
      - Cliente detail page ("Mensajes" tab) — chronological thread
      - Pedido detail timeline — so the operator sees which messages
        were sent and when
      - Reporting: response rate, channel coverage, delivery failures

    Schema:
      - direction: outbound (sent by us) | inbound (received from customer)
      - channel: whatsapp | email | sms | note (manual operator log)
      - template_id: FK to message_template (nullable — free-form allowed)
      - customer_id: FK to customer (NOT NULL — every message is about someone)
      - pedido_id: FK to pedido (nullable — some messages aren't order-related)
      - phone/email: snapshot of destination address (so log survives contact edits)
      - subject, body: rendered content
      - status: pending | sent | delivered | read | failed | received
      - provider_message_id: WhatsApp/email provider's ID (for webhook matching)
      - error_message: filled on status='failed'
      - ts_sent: when we sent it (outbound) or received it (inbound)
      - ts_delivered / ts_read: provider-confirmed timestamps

    Indexes:
      - (customer_id, ts_sent) for per-customer thread
      - (pedido_id, ts_sent) for pedido timeline
      - (status, ts_sent) for delivery-failure monitoring
      - (provider_message_id) for webhook reconciliation
    """

    __tablename__ = "communication_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customer.id", ondelete="CASCADE"), nullable=False, index=True
    )
    pedido_id: Mapped[int | None] = mapped_column(
        ForeignKey("pedido.id", ondelete="SET NULL"), nullable=True, index=True
    )
    template_id: Mapped[int | None] = mapped_column(
        ForeignKey("message_template.id", ondelete="SET NULL"), nullable=True
    )
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    email: Mapped[str | None] = mapped_column(String(120), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(200), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    provider_message_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    ts_sent: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    ts_delivered: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ts_read: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    actor: Mapped[str | None] = mapped_column(String(64), nullable=True)

    customer: Mapped["Customer"] = relationship()
    pedido_rel: Mapped["Pedido | None"] = relationship(foreign_keys=[pedido_id])
    template: Mapped["MessageTemplate | None"] = relationship()

    __table_args__ = (
        Index("ix_communication_log_customer_ts", "customer_id", "ts_sent"),
        Index("ix_communication_log_pedido_ts", "pedido_id", "ts_sent"),
        Index("ix_communication_log_status_ts", "status", "ts_sent"),
        CheckConstraint(
            "direction IN ('outbound','inbound')",
            name="ck_communication_log_direction",
        ),
        CheckConstraint(
            "channel IN ('whatsapp','email','sms','note')",
            name="ck_communication_log_channel",
        ),
        CheckConstraint(
            "status IN ('pending','sent','delivered','read','failed','received')",
            name="ck_communication_log_status",
        ),
    )


class Category(Base):
    """Operator-configurable category/family catalog (migration 039).

    Replaces the hardcoded lists previously living in
    app/templates/_components/tags.html (product_category_options,
    recipe_family_options) and the duplicated family list in
    app/templates/receta_form.html line 53.

    scope ∈ {'product', 'recipe_family'}
      - 'product'        — categories shown on /productos forms
      - 'recipe_family'  — families shown on /recetas forms

    Operators can add/edit/reorder from /settings/categories (TODO).
    For now, seed data matches the prior hardcoded values exactly.

    Uniqueness: (scope, name) — same name allowed across scopes
    ("Pastelería" is both a product category and a recipe family).
    """

    __tablename__ = "category"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    scope: Mapped[str] = mapped_column(String(16), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("scope", "name", name="uq_category_scope_name"),
        Index("ix_category_scope_active", "scope", "is_active", "sort_order"),
    )


__all__ = [
    "AppMeta",
    "AuditLog",
    "BankTransaction",
    "Base",
    # Static-content-audit fix — migration 039
    "Category",
    # Static-content-audit Phase 4 — migrations 041, 042
    "Channel",
    "CommunicationLog",
    # market-intel 2026-09-30 — evidencia de competencia retail
    "CompetitorPriceObservation",
    "ComplianceInfo",
    "Customer",
    # Phase 13 (2026-10-01): structured address fields on CustomerAddress
    "CustomerAddress",
    # Phase 13 (2026-10-01): multiple invoice profiles per customer
    "CustomerInvoiceProfile",
    # Static-content-audit Phase 9 — migration 048
    "DateRangePreset",
    "DeliveryZone",
    "ImportBatch",
    "Ingredient",
    "IngredientPriceEvent",
    # Migration 074 — loyalty ledger for earn/redeem/void_reversal/manual_adjust
    "LoyaltyTransaction",
    # Static-content-audit Phase 7 — migrations 045, 046
    "MarginTier",
    "MarketBenchmark",
    # Static-content-audit Phase 6 — migration 044
    "MessageTemplate",
    "PaymentMethod",
    "Pedido",
    "PedidoEvent",
    "PedidoLine",
    "PriceHistory",
    "Product",
    "ProductionClosedDay",
    "ProductionCompletion",
    "ProductionPlan",
    "ProductionPlanOverride",
    "ProductionPlanTemplate",
    "Recipe",
    "RecipeLine",
    "RecipePricing",
    "RiskItem",
    "Sale",
    "SaleStockMove",
    "SettingsKV",
    "ShoppingListItem",
    "StockMovement",
    "StockStatusConfig",
    # Static-content-audit Phase 11 — migration 049
    "StorageKeyword",
    # Static-content-audit Phase 8 — migration 047
    "StorageType",
    "Supplier",
    # P1-B5 — suscripciones (recurring customer orders), no cron
    "Suscripcion",
    "Tag",
    "TagLink",
    "Tenant",
    "User",
    "WasteLog",
    "WishlistItem",
]


class MarketPriceReference(Base):
    """Wave 4 — Market reference price per ingredient (Paraguay, Gs/kg or Gs/l or Gs/und).

    Operator-curated baseline that the system uses to surface "your price is
    X% above/below market" alerts on /inventario. Updated manually (no external
    API configured in BWS) or via CSV import. Each row snapshots the price
    as-of a specific date so we can track drift over time.

    Schema:
        ingredient_id: FK to Ingredient (one current row per ingredient)
        unit: 'kg' | 'l' | 'und' (must match the ingredient's unit family)
        price_gs: median market price in Guaraníes
        source: 'manual' | 'supermarket' | 'mayorista' | 'csv-import'
        notes: free text (e.g., "Stock Sep 2026", "Supersei Mcal Lopez")
        as_of: when the price was last verified
        created_at / updated_at: audit timestamps
    """

    __tablename__ = "market_price_reference"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ingredient_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("ingredient.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    unit: Mapped[str] = mapped_column(String(16), nullable=False)
    price_gs: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    as_of: Mapped["Date"] = mapped_column(Date, nullable=False, default=date.today)
    created_at: Mapped["DateTime"] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at: Mapped["DateTime"] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    ingredient: Mapped["Ingredient"] = relationship("Ingredient")


class CompetitorPriceObservation(Base):
    """Market-intel — observación de precio retail de la competencia (append-only).

    Fuente: repositorio de investigación saskia-market-intel
    (/opt/data/work/research-repos/saskia-market-intel — cartas online
    verificadas de locales PY con URL y fecha) u observación manual del
    operador ("pasé por Karu: cheesecake 32.000").

    A diferencia de MarketPriceReference (insumos), esta tabla guarda
    precios de PRODUCTOS retail de terceros. El vínculo con nuestro
    catálogo es por `family` (taxonomía del research repo), no por FK:
    "cheesecake en El Café de Acá" no es nuestro producto, es evidencia.

    Append-only: corregir = nueva observación con nueva fecha (mismo
    contrato que price_history). La vista /vs-mercado/evidencia agrega
    p25/mediana/p75 por familia+unidad.
    """

    __tablename__ = "competitor_price_observation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    competitor_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    competitor_type: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True
    )  # cafetería|panadería|supermercado|confitería|importado|bistró
    city: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    product_name: Mapped[str] = mapped_column(String(160), nullable=False)
    family: Mapped[Optional[str]] = mapped_column(String(24), nullable=True, index=True)
    unit: Mapped[str] = mapped_column(String(16), nullable=False, default="unidad")
    price_gs: Mapped[int] = mapped_column(Integer, nullable=False)
    as_of: Mapped["Date"] = mapped_column(Date, nullable=False, default=date.today, index=True)
    source: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped["DateTime"] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped["DateTime"] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    __table_args__ = (
        Index("ix_cpo_family_unit_asof", "family", "unit", "as_of"),
        CheckConstraint("price_gs > 0", name="ck_cpo_price_positive"),
    )


class Suscripcion(Base):
    """P1-B5 — Suscripción (recurring customer order).

    Captures a customer's standing request (e.g., "1 kg de pan cada
    sábado a las 9") without auto-generating pedidos: no cron, no
    implicit stock decrement, no automatic billing. The operator
    reads the list on /suscripciones when planning and pre-loads
    the corresponding pedidos manually.

    Status is a soft-state machine (activa → pausada / cancelada).
    Deletion is allowed when no pedidos have been generated against
    the suscripción; otherwise the operator must cancel rather than
    delete to preserve history.

    Schema:
        customer_id: FK to Customer (required — every suscripción belongs to one)
        product_summary: free-text description (e.g., "1 kg chipa + 2 facturas")
        cadence: 'semanal' | 'quincenal' | 'mensual'
        preferred_day_of_week: 1-7 (ISO weekday) or None for cadence-derived
        preferred_time: HH:MM (optional, free-text)
        start_date / end_date: subscription window
        price_gs: estimated price snapshot (int, Guaraníes)
        status: 'activa' | 'pausada' | 'cancelada'
        notes: free text
        created_at / updated_at: audit timestamps
    """

    __tablename__ = "suscripcion"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("customer.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    product_summary: Mapped[str] = mapped_column(String(500), nullable=False)
    cadence: Mapped[str] = mapped_column(String(16), nullable=False)
    preferred_day_of_week: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    preferred_time: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    start_date: Mapped["Date"] = mapped_column(Date, nullable=False, default=date.today)
    end_date: Mapped[Optional["Date"]] = mapped_column(Date, nullable=True)
    price_gs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="activa")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped["DateTime"] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at: Mapped["DateTime"] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    customer: Mapped["Customer"] = relationship("Customer")

    __table_args__ = (
        CheckConstraint(
            "cadence IN ('semanal','quincenal','mensual')",
            name="ck_suscripcion_cadence",
        ),
        CheckConstraint(
            "status IN ('activa','pausada','cancelada')",
            name="ck_suscripcion_status",
        ),
        CheckConstraint(
            "preferred_day_of_week IS NULL OR (preferred_day_of_week BETWEEN 1 AND 7)",
            name="ck_suscripcion_dow",
        ),
        CheckConstraint("price_gs >= 0", name="ck_suscripcion_price_nonneg"),
        Index("ix_suscripcion_status", "status"),
        Index("ix_suscripcion_customer", "customer_id"),
    )


class LoyaltyTransaction(Base):
    """Append-only ledger of customer loyalty point movements.

    Migration 074 (2026-10-01): the ``Customer.loyalty_points`` column
    existed since the original loyalty work but was never incremented —
    ``award_points()`` in ``app/rms/customers.py`` was defined but
    unwired. This ledger captures every delta (earn, redeem, manual
    adjustment, void reversal) so refunds/voids can reverse points
    cleanly without losing history.

    Schema:
      - id: PK
      - customer_id: FK -> customer.id, indexed
      - delta: signed integer (positive=earn, negative=redeem/void)
      - reason: enum-like string ('earn_sale', 'redeem', 'void_reversal',
                'manual_adjust')
      - sale_id: nullable FK -> sale.id, set when reason IN
                 ('earn_sale', 'redeem', 'void_reversal')
      - actor: 'system' | 'operator' — for audit (who triggered it)
      - notes: optional free-text (e.g. "canje por descuento 5.000 Gs")
      - recorded_at: UTC datetime (default now)

    The Customer.loyalty_points column is kept as the cached balance for
    fast display; this table is the source of truth. A periodic
    reconcile (or any inconsistency) can rebuild the column from
    SUM(delta) GROUP BY customer_id.

    Invariants:
      - reason IN ('earn_sale', 'redeem', 'void_reversal', 'manual_adjust')
      - delta != 0
      - sale_id is set when reason ∈ {earn_sale, redeem, void_reversal}
    """

    __tablename__ = "loyalty_transaction"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("customer.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(24), nullable=False)
    sale_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("sale.id", ondelete="SET NULL"),
        nullable=True,
    )
    actor: Mapped[str] = mapped_column(String(32), nullable=False, default="system")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, index=True
    )

    __table_args__ = (
        # Tier 3.2 (2026-10-01): suggestion_applied added as a pure
        # event-log row (delta=0, no balance change). The
        # ``ck_loyalty_delta_nonzero`` constraint was dropped because
        # suggestion_applied rows are zero-balance by design; the
        # earn/redeem/void/manual_adjust code never writes 0 anyway.
        CheckConstraint(
            "reason IN ('earn_sale','redeem','void_reversal','manual_adjust','suggestion_applied')",
            name="ck_loyalty_reason",
        ),
        Index("ix_loyalty_customer_time", "customer_id", "recorded_at"),
    )


class Refund(Base):
    """A partial (or full) monetary reversal of a Sale or Pedido.

    Distinct from Sale.voided_at — void means "this transaction didn't happen",
    refund means "this transaction happened and we're giving some money back".
    Multiple refunds can target the same Sale (a customer might bring back
    1 of 3 items today, 2 tomorrow); the DB enforces sum(amount_gs) <= target
    total via a trigger installed in migration 089.

    Fields:
      target_type         — 'sale' | 'pedido' | 'pedido_line' (polymorphic)
      target_id           — FK to the target row (no real FK; enforced by app)
      target_amount_gs    — snapshot of the target's total at refund time
      amount_gs           — how much we're refunding (always > 0)
      payment_method      — must equal original payment_method (caller validates)
      restock_qty         — if True, stock is returned to inventory
      restocked_qty       — quantity returned to stock (0 if restock_qty=False)
      reason              — operator-supplied free text ("cliente devolvió torta")
      recorded_at         — UTC datetime when refund was issued
      recorded_by         — operator id (string, same as Sale.voided_by)
      eod_date            — date the refund belongs to (for EOD closure rule)
      loyalty_reversed    — points deducted from customer (cached for audit;
                            source of truth is LoyaltyTransaction table)

    Invariants (enforced by trigger 089_refund_amount_cap):
      - amount_gs > 0
      - target_amount_gs > 0
      - target_id IS NOT NULL
      - For any (target_type, target_id), SUM(amount_gs) <= original target total
      - For 'pedido_line', target_id is the PedidoLine.id (refund per-line)
      - restocked_qty >= 0 (and =0 if restock_qty=False)

    Refunds DO NOT void the original Sale/Pedido. The original row remains
    in the ledger with its full amount; refunds are a separate flow that
    operators can audit independently. This matches DNIT (Paraguayan tax
    authority) requirements: a fiscal invoice once issued must remain in
    the books; a refund is a separate "nota de crédito".
    """

    __tablename__ = "refund"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    target_type: Mapped[str] = mapped_column(String(16), nullable=False)
    target_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    target_amount_gs: Mapped[int] = mapped_column(Integer, nullable=False)
    amount_gs: Mapped[int] = mapped_column(Integer, nullable=False)
    payment_method: Mapped[str] = mapped_column(String(32), nullable=False)
    restock_qty: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    restocked_qty: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default="0"
    )
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, index=True
    )
    recorded_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    eod_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    loyalty_reversed: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    __table_args__ = (
        CheckConstraint(
            "target_type IN ('sale','pedido','pedido_line')",
            name="ck_refund_target_type",
        ),
        CheckConstraint(
            "amount_gs > 0",
            name="ck_refund_amount_positive",
        ),
        CheckConstraint(
            "target_amount_gs > 0",
            name="ck_refund_target_amount_positive",
        ),
        CheckConstraint(
            "restocked_qty >= 0",
            name="ck_refund_restocked_qty_nonneg",
        ),
        # ix_refund_recorded_at is created automatically via `index=True`
        # on the recorded_at column above. The previous explicit
        # `Index("ix_refund_recorded_at", "recorded_at")` here caused
        # init_db() to fail on a fresh DB with "index already exists".
        # Migration 089 still creates the matching index idempotently
        # via CREATE INDEX IF NOT EXISTS for legacy Postgres prod paths.
        Index("ix_refund_target", "target_type", "target_id"),
        # ix_refund_recorded_at removed (2026-01-02 fix; BACKLOG Tier-7
        # unblocks /healthz/depth tests by letting init_db complete).
    )


# ---------------------------------------------------------------------------
# BACKLOG #1 (schema 92): post-class column aliases for the abstract
# SaleStockMove stub. StockMovement is defined ABOVE this block, so we can
# now safely reference its InstrumentedAttributes and attach them to
# SaleStockMove as backwards-compat aliases. Legacy code that wrote
# `SaleStockMove.qty_delta` keeps resolving to the same data via the
# stock_movement source-of-truth table.
#
# These aliases are NOT new SQL columns — they are pointers to the same
# underlying InstrumentedAttributes on StockMovement, so a query like
# `select(SaleStockMove.qty_delta)` is equivalent to
# `select(StockMovement.qty)` at execution time.
#
# Do NOT add new code that uses these aliases. They exist solely to keep
# /analisis, /reportes, and other legacy query paths from breaking at
# import time. Future cleanup: rewrite each callsite to use StockMovement
# directly and delete this block.
# ---------------------------------------------------------------------------
SaleStockMove.qty_delta = StockMovement.qty
SaleStockMove.sale_id = StockMovement.reference_id
SaleStockMove.ingredient_id = StockMovement.ingredient_id
SaleStockMove.affected_recipe_id = StockMovement.affected_recipe_id
# NOTE: SaleStockMove.sale (the relationship) is NOT aliased here — it
# requires a real mapped relationship, which the abstract class can't
# provide. The remaining `join(SaleStockMove.sale)` references in the
# codebase are dead code paths (never executed in current routes) and
# should be rewritten to use StockMovement.reference_id joined to Sale.
