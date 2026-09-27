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
app/rms/models/procurement.py — Buys, waste, stock ledger, imports: ImportBatch, Supplier, WasteLog, ShoppingListItem, StockMovement.

Extracted from app/rms/models.py on 2026-09-23 (Phase 3.1 refactor).
All models here share the same declarative Base as the rest of the
project — see app/rms/models/core.py.
"""

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
