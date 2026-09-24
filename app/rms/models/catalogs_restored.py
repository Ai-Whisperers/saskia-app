"""Restored catalog/config models (static-content audit Phases 1-11).

These were dropped in the Phase-2B package refactor; restored verbatim
from the pre-refactor models.py (b9b5288) — every router still imports
them and migrations 039-049 create their tables.
"""
from __future__ import annotations

from datetime import datetime
from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index,
    Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.rms.models.core import Base


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
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    __table_args__ = (
        UniqueConstraint("scope", "name", name="uq_category_scope_name"),
        Index("ix_category_scope_active", "scope", "is_active", "sort_order"),
    )


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
    "ComplianceInfo",
    # Static-content-audit fix — migration 039
    "Category",
    # Static-content-audit Phase 4 — migrations 041, 042
    "Channel",
    "PaymentMethod",
    # Static-content-audit Phase 6 — migration 044
    "MessageTemplate",
    # Static-content-audit Phase 7 — migrations 045, 046
    "MarginTier",
    "StockStatusConfig",
    # Static-content-audit Phase 8 — migration 047
    "StorageType",
    # Static-content-audit Phase 9 — migration 048
    "DateRangePreset",
    # Static-content-audit Phase 11 — migration 049
    "StorageKeyword",
]


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
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    __table_args__ = (
        Index("ix_date_range_preset_active_sort", "is_active", "sort_order"),
    )


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
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    __table_args__ = (
        Index("ix_margin_tier_active_sort", "is_active", "sort_order"),
    )


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
        DateTime, nullable=False,
        default=datetime.utcnow, onupdate=datetime.utcnow,
    )

    __table_args__ = (
        UniqueConstraint("channel", "key", "locale", name="uq_message_template_chan_key_locale"),
        Index("ix_message_template_chan_active", "channel", "is_active"),
    )


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
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    __table_args__ = (
        Index("ix_payment_method_active_sort", "is_active", "sort_order"),
    )


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
        DateTime, nullable=False,
        default=datetime.utcnow, onupdate=datetime.utcnow,
    )

    __table_args__ = (
        Index("ix_stock_status_config_active", "is_active", "sort_order"),
    )


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
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    __table_args__ = (
        Index("ix_storage_keyword_active_sort", "storage_code", "is_active", "sort_order"),
    )


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
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    __table_args__ = (
        Index("ix_storage_type_active_sort", "is_active", "sort_order"),
    )
