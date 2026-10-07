from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.rms.models.core import Base

"""
app/rms/models/production.py — Production planning: ProductionCompletion, ProductionPlanTemplate, ProductionPlanOverride, ProductionPlan.

Extracted from app/rms/models.py on 2026-09-23 (Phase 3.1 refactor).
All models here share the same declarative Base as the rest of the
project — see app/rms/models/core.py.
"""


class ProductionCompletion(Base):
    """How much of a planned product was actually produced on a given day.

    the operator review T5: "Al final del dia debe registrarse cuanto de la
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
    # PRODUCCION-V2 Fase 2: end-of-shift closure. 'open' = cook hasn't
    # finished reviewing the day; 'done' = "yes, this is what we
    # baked"; 'cancelled' = "we baked 0 of this; here's why". The
    # closure_notes is the cook's optional free-text justification
    # (NULL when blank). updated_at is the most recent write (set on
    # upsert and on close-day).
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="open", server_default="open"
    )
    closure_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
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

