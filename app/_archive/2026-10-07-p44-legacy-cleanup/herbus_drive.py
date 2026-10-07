from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
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
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.rms.models.core import Base

"""
app/rms/models/herbus_drive.py — Operational / HEREBUS-imported tables: WishlistItem, RiskItem, MarketBenchmark, BankTransaction, ComplianceInfo, MarketPriceReference.

Extracted from app/rms/models.py on 2026-09-23 (Phase 3.1 refactor).
All models here share the same declarative Base as the rest of the
project — see app/rms/models/core.py.
"""


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


class MarketBenchmark(Base):
    """Per-product pricing-vs-market row (HEREBUS Benchmarks_Market).

    Allows the operator to position each recipe relative to local competitors.
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


__all__ = [
    "BankTransaction",
    "ComplianceInfo",
    # HEREBUS Drive integration — migration 029
    "MarketBenchmark",
    "MarketPriceReference",
    "RiskItem",
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

    ingredient: Mapped["Ingredient"] = relationship("Ingredient")  # noqa: F821 — SQLAlchemy 2.0 forward ref
