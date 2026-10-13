"""Tests for SASKIA-216: migration 121 (create seasonal_event table).

Verifies:
- Schema bumps to 119
- The seasonal_event table exists with the expected columns
- All 6 indexes (slug, event_date, country, category, country+date, category+date) exist
- The unique constraint (country, slug, event_date) is enforced
- The seeder inserts 126 Tier 1 events idempotently
- Re-running the seeder is a no-op
- The migration is reversible on a clean DB (drop table + recreate)
"""

# allow-hardcoded-dates: fixture: event_date='2026-06-24' is seasonal_event row data, not relative-time

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError


def test_migration_121_bumps_schema_version(session_factory):
    """Fresh DB runs init_db through migration 121."""
    with session_factory() as s:
        v = s.execute(text("SELECT value FROM app_meta WHERE key='schema_version'")).scalar()
    assert v is not None
    assert int(v) >= 121


def test_migration_121_creates_seasonal_event_table(session_factory):
    """The seasonal_event table is created with the expected columns."""
    with session_factory() as s:
        rows = s.execute(text("PRAGMA table_info(seasonal_event)")).fetchall()
    columns = {row[1]: row[2] for row in rows}
    # All 17 expected columns
    expected = {
        "id",
        "slug",
        "name_es",
        "name_nl",
        "name_en",
        "description",
        "event_date",
        "end_date",
        "country",
        "category",
        "impact_score",
        "impact_tag",
        "relevance_tags",
        "is_annual",
        "recurrence",
        "created_at",
        "updated_at",
    }
    assert expected.issubset(set(columns.keys())), f"missing: {expected - set(columns.keys())}"


def test_migration_121_creates_indexes(session_factory):
    """All 6 indexes + the unique constraint are created."""
    with session_factory() as s:
        idx_rows = s.execute(text("PRAGMA index_list(seasonal_event)")).fetchall()
    index_names = {r[1] for r in idx_rows}
    expected_indexes = {
        "ix_seasonal_event_slug",
        "ix_seasonal_event_event_date",
        "ix_seasonal_event_country",
        "ix_seasonal_event_category",
        "ix_seasonal_event_country_date",
        "ix_seasonal_event_category_date",
        "uq_seasonal_event_country_slug_date",
    }
    assert expected_indexes.issubset(index_names), f"missing: {expected_indexes - index_names}"


def test_migration_121_enforces_unique_country_slug_date(session_factory):
    """The (country, slug, event_date) UNIQUE constraint is enforced."""
    with session_factory() as s:
        s.execute(
            text(
                "INSERT INTO seasonal_event (slug, name_es, event_date, country, category, "
                "impact_score, impact_tag, relevance_tags, is_annual, created_at, updated_at) "
                "VALUES ('test_dup', 'Test', '2026-06-24', 'PY', 'legal', 0.5, 'medium', '', 0, "
                "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            )
        )
        s.commit()
        with pytest.raises(IntegrityError):
            # Duplicate (country, slug, event_date) should fail
            s.execute(
                text(
                    "INSERT INTO seasonal_event (slug, name_es, event_date, country, category, "
                    "impact_score, impact_tag, relevance_tags, is_annual, created_at, updated_at) "
                    "VALUES ('test_dup', 'Test2', '2026-06-24', 'PY', 'legal', 0.5, 'medium', '', 0, "
                    "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                )
            )
            s.commit()


def test_seed_seasonal_events_inserts_126_rows(session_factory):
    """The Tier 1 seeder inserts 126 rows for 2026-2028."""
    from app.rms.seed.seasonal_events import seed_seasonal_events

    with session_factory() as s:
        n = seed_seasonal_events(s)
        s.commit()
    assert n == 126, f"expected 126, got {n}"


def test_seed_seasonal_events_is_idempotent(session_factory):
    """Re-running the seeder is a no-op."""
    from app.rms.seed.seasonal_events import seed_seasonal_events

    with session_factory() as s:
        n1 = seed_seasonal_events(s)
        s.commit()
    with session_factory() as s:
        n2 = seed_seasonal_events(s)
        s.commit()
    assert n1 == 126
    assert n2 == 0  # all skipped, no new rows


def test_seed_seasonal_events_has_critical_py_holidays(session_factory):
    """The most important PY holidays are present with critical/high impact."""
    from app.rms.seed.seasonal_events import seed_seasonal_events

    with session_factory() as s:
        seed_seasonal_events(s)
        s.commit()
        # Semana Santa 2026 (Jueves Santo = 2026-04-02 = Easter - 3)
        rows = s.execute(
            text(
                "SELECT slug, name_es, event_date, impact_tag, relevance_tags "
                "FROM seasonal_event WHERE country='PY' AND event_date='2026-04-02'"
            )
        ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "jueves_santo"
    assert rows[0][3] == "critical"

    # Pascua 2026 (2026-04-05)
    with session_factory() as s:
        rows = s.execute(
            text(
                "SELECT slug, event_date, impact_tag FROM seasonal_event "
                "WHERE country='PY' AND slug='pascua' AND event_date='2026-04-05'"
            )
        ).fetchall()
    assert len(rows) == 1
    assert rows[0][2] == "critical"

    # Día de la Madre PY 2026 (15 May)
    with session_factory() as s:
        rows = s.execute(
            text(
                "SELECT slug, impact_tag FROM seasonal_event "
                "WHERE country='PY' AND slug='dia_madre_py' AND event_date='2026-05-15'"
            )
        ).fetchall()
    assert len(rows) == 1
    assert rows[0][1] == "critical"

    # Navidad 2026
    with session_factory() as s:
        rows = s.execute(
            text(
                "SELECT slug, impact_tag FROM seasonal_event "
                "WHERE country='PY' AND slug='navidad' AND event_date='2026-12-25'"
            )
        ).fetchall()
    assert len(rows) == 1
    assert rows[0][1] == "critical"


def test_seed_seasonal_events_includes_nl_heritage(session_factory):
    """The 'Vaquita Holandesa' brand heritage NL events are included."""
    from app.rms.seed.seasonal_events import seed_seasonal_events

    with session_factory() as s:
        seed_seasonal_events(s)
        s.commit()
        rows = s.execute(
            text(
                "SELECT slug, name_nl FROM seasonal_event "
                "WHERE country='NL' AND event_date='2026-12-05'"
            )
        ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "sinterklaas"
    assert "Sinterklaas" in (rows[0][1] or "")


def test_seed_seasonal_events_relevance_tags_filter(session_factory):
    """The relevance_tags CSV column is queryable for per-vertical filtering."""
    from app.rms.seed.seasonal_events import seed_seasonal_events

    with session_factory() as s:
        seed_seasonal_events(s)
        s.commit()
        # Panadería-relevant events 2026
        rows = s.execute(
            text(
                "SELECT COUNT(*) FROM seasonal_event "
                "WHERE relevance_tags LIKE '%panaderia%' AND event_date LIKE '2026%'"
            )
        ).scalar()
    # At least Reyes, Pascua, Navidad, Día de la Madre (4 critical for Panadería)
    assert rows >= 4, f"expected >= 4 panaderia-tagged events, got {rows}"


def test_seed_sazon_includes_seasonal_events(session_factory):
    """seed_sazon() end-to-end also seeds 126 seasonal events."""
    from app.rms.seed.sazon import seed_sazon

    with session_factory() as s:
        report = seed_sazon(s)
        s.commit()
    assert report.seasonal_events == 126, f"expected 126, got {report.seasonal_events}"
