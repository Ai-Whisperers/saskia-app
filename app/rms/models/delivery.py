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
app/rms/models/delivery.py — Geo-specific tables: DeliveryZone.

Extracted from app/rms/models.py on 2026-09-23 (Phase 3.1 refactor).
All models here share the same declarative Base as the rest of the
project — see app/rms/models/core.py.
"""

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
