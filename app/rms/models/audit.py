from __future__ import annotations

from sqlalchemy import (
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.rms.models.core import Base

"""
app/rms/models/audit.py — Audit + system-state tables: AppMeta, AuditLog, SettingsKV, User, Tenant.

Extracted from app/rms/models.py on 2026-09-23 (Phase 3.1 refactor).
All models here share the same declarative Base as the rest of the
project — see app/rms/models/core.py.
"""

class AppMeta(Base):
    """Key-value store for app metadata (schema version, last_backup_at, etc.)."""

    __tablename__ = "app_meta"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)
