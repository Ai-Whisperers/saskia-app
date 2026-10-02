"""MonthlyClosure model — monthly accounting closures (Sprint 3.1)."""

from datetime import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.rms.models_legacy import Base


class MonthlyClosure(Base):
    """Monthly financial closure record."""
    
    __tablename__ = "monthly_closure"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    period_yyyymm: Mapped[str] = mapped_column(String(7), nullable=False, unique=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    closed_by_user_id: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, default=None
    )
    total_iva_gs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_revenue_gs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_cogs_gs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_expenses_gs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    net_gs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    snapshot_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None)
    reopened_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    reopened_by_user_id: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, default=None
    )
    reopen_reason: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, default=None
    )

    __table_args__ = (
        CheckConstraint(
            "length(period_yyyymm) = 7",
            name="ck_monthly_closure_period_format",
        ),
        UniqueConstraint("period_yyyymm", name="uq_monthly_closure_period"),
    )

    @property
    def is_closed(self) -> bool:
        return self.closed_at is not None and self.reopened_at is None

    @property 
    def is_open(self) -> bool:
        return self.closed_at is None


__all__ = ["MonthlyClosure"]