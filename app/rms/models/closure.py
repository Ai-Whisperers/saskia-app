"""MonthlyClosure model — monthly accounting closures (Sprint 3.1)."""

from datetime import date, datetime
from datetime import timezone

from sqlalchemy import Date, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.rms.models.common import AuditColumns, SoftDeletable


class MonthlyClosure(SoftDeletable, AuditColumns):
    """Monthly financial closure record."""
    
    __tablename__ = "monthly_closure"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    month: Mapped[date] = mapped_column(Date, nullable=False, unique=True, index=True)
    total_expenses_gs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    closed_by_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True, default=None)
    reopened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    reopened_by_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True, default=None)

    @property
    def is_closed(self) -> bool:
        return self.closed_at is not None and self.reopened_at is None

    @property 
    def is_open(self) -> bool:
        return self.closed_at is None


__all__ = ["MonthlyClosure"]