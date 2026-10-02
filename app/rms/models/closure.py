"""MonthlyClosure model — monthly accounting closures (Sprint 3.1)."""

import json
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.rms.models_legacy import Base


class MonthlyClosure(Base):
    """Monthly financial closure record."""
    
    __tablename__ = "monthly_closure"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    month: Mapped[date] = mapped_column(Date, nullable=False, unique=True, index=True)
    total_expenses_gs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None)
    closed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    closed_by_user_id: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, default=None
    )
    reopened_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    reopened_by_user_id: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, default=None
    )
    reopen_reason: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, default=None
    )

    @property
    def period_yyyymm(self) -> str:
        """Return the period in YYYY-MM format."""
        return self.month.strftime("%Y-%m")

    @property
    def snapshot_json(self) -> str:
        """Return a JSON snapshot of the closure."""
        return json.dumps({
            "period_yyyymm": self.period_yyyymm,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "total_expenses_gs": self.total_expenses_gs,
            "reopened_at": self.reopened_at.isoformat() if self.reopened_at else None,
            "reopen_reason": self.reopen_reason,
        })

    @property
    def is_closed(self) -> bool:
        return self.closed_at is not None and self.reopened_at is None

    @property 
    def is_open(self) -> bool:
        return self.closed_at is None


__all__ = ["MonthlyClosure"]