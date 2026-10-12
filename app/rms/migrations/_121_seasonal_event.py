"""Migration 121 — SASKIA-216: create `seasonal_event` table.

Per OOB-2026-10-12 ("the website of sazon should load all of the thigns")
and the 2026-10-08 questionnaire §16.1 (Semana Santa = si), §16.5
(Menú estacional verano/invierno = si), §16.6 (Aviso 30 días antes = si,
already wired as `seasonal.notif_lead_days` setting from SASKIA-215).

The `seasonal_event` table stores date-anchored demand drivers for
production planning. Multi-tenant: shared across all tenants, filtered
per-vertical via the `relevance_tags` CSV column. Schema migration 121
creates the table; the seeder (SASKIA-216) populates ~132 tier-1 rows
for PY + a few NL heritage rows for 2026-2028. Tier 2/3/4 expansion is
SASKIA-220.

Idempotent: CREATE TABLE IF NOT EXISTS + CREATE INDEX IF NOT EXISTS
(works on both SQLite and Postgres). Re-running the migration on the
same DB is safe.

The 30-day lead time from `seasonal.notif_lead_days` (SASKIA-215) is
applied at READ time by the Sazon UI, not stored here.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text


def _migration_121_seasonal_event(conn: Any) -> None:
    """Create seasonal_event table + indexes + unique constraint.

    Schema (per app/rms/models_legacy.py:SeasonalEvent):

    - id (INTEGER PK)
    - slug (VARCHAR(80), indexed) — event identifier across years
    - name_es (VARCHAR(120), NOT NULL) — Spanish label
    - name_nl (VARCHAR(120), nullable) — Dutch label (NL heritage events)
    - name_en (VARCHAR(120), nullable) — English label (exports)
    - description (TEXT, nullable)
    - event_date (DATE, NOT NULL, indexed) — the actual date
    - end_date (DATE, nullable) — for multi-day events (e.g. Carnaval)
    - country (VARCHAR(2), NOT NULL, default 'PY', indexed) — ISO-3166-1 alpha-2
    - category (VARCHAR(20), NOT NULL, indexed) — legal/commercial/religious/school/folk/sectoral/heritage
    - impact_score (FLOAT, NOT NULL, default 0.5) — 0.0-1.0 demand multiplier
    - impact_tag (VARCHAR(20), NOT NULL, default 'medium') — critical/high/medium/low/info
    - relevance_tags (VARCHAR(200), NOT NULL, default '') — CSV of pack slugs
    - is_annual (BOOLEAN, NOT NULL, default 0) — True for fixed dates
    - recurrence (VARCHAR(80), nullable) — 'fixed' / 'easter-3' / 'third-sunday-june' / 'movable-by-decree'
    - created_at (DATETIME, NOT NULL)
    - updated_at (DATETIME, NOT NULL)

    Indexes:
    - ix_seasonal_event_country_slug_date (UNIQUE on country, slug, event_date)
    - ix_seasonal_event_country_date (composite for date-range queries)
    - ix_seasonal_event_category_date (composite for category filter)
    """
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS seasonal_event (
                id INTEGER PRIMARY KEY,
                slug VARCHAR(80) NOT NULL,
                name_es VARCHAR(120) NOT NULL,
                name_nl VARCHAR(120),
                name_en VARCHAR(120),
                description TEXT,
                event_date DATE NOT NULL,
                end_date DATE,
                country VARCHAR(2) NOT NULL DEFAULT 'PY',
                category VARCHAR(20) NOT NULL,
                impact_score FLOAT NOT NULL DEFAULT 0.5,
                impact_tag VARCHAR(20) NOT NULL DEFAULT 'medium',
                relevance_tags VARCHAR(200) NOT NULL DEFAULT '',
                is_annual BOOLEAN NOT NULL DEFAULT 0,
                recurrence VARCHAR(80),
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
            """
        )
    )

    # Idempotent indexes
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_seasonal_event_slug ON seasonal_event (slug)"
        )
    )
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_seasonal_event_event_date ON seasonal_event (event_date)"
        )
    )
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_seasonal_event_country ON seasonal_event (country)"
        )
    )
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_seasonal_event_category ON seasonal_event (category)"
        )
    )
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_seasonal_event_country_date ON seasonal_event (country, event_date)"
        )
    )
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_seasonal_event_category_date ON seasonal_event (category, event_date)"
        )
    )

    # Unique constraint on (country, slug, event_date) — the natural key
    # Note: SQLite needs this to be a unique index, not a table constraint,
    # because CREATE TABLE IF NOT EXISTS doesn't alter existing tables.
    conn.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_seasonal_event_country_slug_date "
            "ON seasonal_event (country, slug, event_date)"
        )
    )

    # Bump schema version
    from app.rms.db import _bump_schema_version

    _bump_schema_version(conn, 121)
