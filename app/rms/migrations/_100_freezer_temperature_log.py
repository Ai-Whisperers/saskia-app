"""Migration 100: freezer_temperature_log table for HACCP compliance.

T-2026-10-04 (B.6): Paraguay MSPBS HACCP exige registro de temperatura
de heladeras/freezers donde se almacenan productos crudos, semi-elaborados
y elaborados. el operador opera con un freezer de masa y uno de productos
finales. Sin registro continuo, una inspección puede multar al local.

Schema:
  - freezer_temperature_log (id, location, temperature_c, for_date,
    shift AM|PM, recorded_at, recorded_by_user_id, notes)
  - Composite index on (for_date, location) for the daily-view query

Idempotent: try/except on every ALTER/CREATE. The SQLAlchemy model
in app/rms/models_legacy.py creates the same table on fresh DBs.
"""

from typing import Any

from sqlalchemy import text


def _migration_100_freezer_temperature_log(conn: Any) -> None:
    """Create freezer_temperature_log table + indexes."""
    try:
        dialect_name = conn.dialect.name
    except Exception:
        dialect_name = "sqlite"

    # 1) Create the table. SQLite and Postgres both support this DDL.
    try:
        if dialect_name == "sqlite":
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS freezer_temperature_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        location VARCHAR(64) NOT NULL,
                        temperature_c FLOAT NOT NULL,
                        for_date DATE NOT NULL,
                        shift VARCHAR(8) NOT NULL,
                        recorded_at TIMESTAMP NOT NULL,
                        recorded_by_user_id INTEGER,
                        notes TEXT,
                        CHECK (temperature_c BETWEEN -40 AND 30),
                        CHECK (shift IN ('AM', 'PM'))
                    )
                    """
                )
            )
        else:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS freezer_temperature_log (
                        id SERIAL PRIMARY KEY,
                        location VARCHAR(64) NOT NULL,
                        temperature_c DOUBLE PRECISION NOT NULL,
                        for_date DATE NOT NULL,
                        shift VARCHAR(8) NOT NULL,
                        recorded_at TIMESTAMP NOT NULL,
                        recorded_by_user_id INTEGER REFERENCES "user"(id),
                        notes TEXT,
                        CONSTRAINT ck_freezer_temp_range CHECK (temperature_c BETWEEN -40 AND 30),
                        CONSTRAINT ck_freezer_shift CHECK (shift IN ('AM', 'PM'))
                    )
                    """
                )
            )
    except Exception:
        pass

    # 2) Indexes for fast daily-view lookup.
    try:
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_freezer_temperature_log_location ON freezer_temperature_log(location)"
            )
        )
    except Exception:
        pass
    try:
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_freezer_temperature_log_for_date ON freezer_temperature_log(for_date)"
            )
        )
    except Exception:
        pass
    try:
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_freezer_temp_date_location ON freezer_temperature_log(for_date, location)"
            )
        )
    except Exception:
        pass

    # BACKLOG #4 (2026-10-02): always bump schema_version at the end.
    from app.rms.db import _bump_schema_version

    _bump_schema_version(conn, 100)
