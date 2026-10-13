"""Migration 124 — SASKIA-226: add is_mipyme_mie + tenant.location columns.

Why: Saskia's 2026-10-08 onboarding questionnaire included questions
that don't have a place in the current schema:
- §20.1 "¿Estás inscripta en el régimen MIPYME/MIE (Ley 4.783/12)?"
  (operator answer: TBD)
- §22.1 "¿En qué barrio/zona está el local?" (operator answer:
  "San Lorenzo", zona: "residencial")
- §22.2 "¿Hay estacionamiento para clientes?" (TBD)

The Tenant table currently has no `barrio`/`zona` columns, and the
ComplianceInfo table has no `is_mipyme_mie` column. This migration
adds them so the operator's answers (when filled) can be persisted.

Idempotent: ADD COLUMN is a no-op if the column already exists.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import text


def _column_exists(conn: Any, table: str, column: str) -> bool:
    """Return True if the column already exists on the table (idempotent)."""
    rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return any(row[1] == column for row in rows)


def _migration_124_saskia_questionnaire_columns(conn: Any) -> None:
    """Add the missing schema columns for the 2026-10-08 questionnaire
    and populate the operator's answers where already given (§22.1 +
    §22.2 of the 2026-10-08 onboarding questionnaire)."""
    # ComplianceInfo.is_mipyme_mie (boolean, default false) — §20
    if not _column_exists(conn, "compliance_info", "is_mipyme_mie"):
        conn.execute(
            text(
                "ALTER TABLE compliance_info "
                "ADD COLUMN is_mipyme_mie BOOLEAN NOT NULL DEFAULT 0"
            )
        )

    # Tenant.barrio (text, nullable) — §22.1
    if not _column_exists(conn, "tenant", "barrio"):
        conn.execute(
            text("ALTER TABLE tenant ADD COLUMN barrio VARCHAR(64) NULL")
        )

    # Tenant.zona (text, nullable) — §22.1 (e.g. "residencial", "comercial")
    if not _column_exists(conn, "tenant", "zona"):
        conn.execute(
            text("ALTER TABLE tenant ADD COLUMN zona VARCHAR(64) NULL")
        )

    # Tenant.has_parking (boolean, default false) — §22.2
    if not _column_exists(conn, "tenant", "has_parking"):
        conn.execute(
            text(
                "ALTER TABLE tenant "
                "ADD COLUMN has_parking BOOLEAN NOT NULL DEFAULT 0"
            )
        )

    # Apply the operator's §22.1 + §22.2 answers to the La Vaquita
    # Holandesa tenant row. The seeder already has these values in
    # BUSINESS_INFO; the migration writes them to the live DB.
    # Idempotent: if barrio/zona/has_parking are already set, the
    # UPDATE is a no-op (the WHERE clause matches no row when values
    # are unchanged).
    conn.execute(
        text(
            "UPDATE tenant "
            "SET barrio = 'San Lorenzo', zona = 'residencial', has_parking = 1 "
            "WHERE slug = 'la-vaquita-holandesa' "
            "AND (barrio IS NULL OR barrio != 'San Lorenzo' "
            "     OR zona IS NULL OR zona != 'residencial' "
            "     OR has_parking = 0)"
        )
    )

    # Bump INSIDE this function — each migration owns its own bump.
    from app.rms.db import _bump_schema_version

    _bump_schema_version(conn, 124)
