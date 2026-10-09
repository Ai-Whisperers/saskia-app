from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.rms.models.core import Base

"""
app/rms/models/auth.py — Auth + system tables: User, AuditLog, SettingsKV, Tenant.

Extracted from app/rms/models.py on 2026-09-23 (Phase 3.1 refactor).
All models here share the same declarative Base as the rest of the
project — see app/rms/models/core.py.
"""


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
