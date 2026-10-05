"""tests/test_pg_roundtrip.py — real Postgres regression tests via testcontainers.

Closes Phase 0 epic E2.S2. Booted Postgres container (see conftest_pg.py)
provides pg_engine / pg_session_factory / pg_session fixtures.

The 5 production hotfixes on 2026-09-04:
- f1af406 (HEAD /healthz for UptimeRobot)   - covered by test_healthz.py (no PG needed)
- c093a75 (SUPABASE_SECRET_KEY alias)       - covered by test_hotfix_regressions (no PG needed)
- 99b37c6 (supabase SDK in Dockerfile)      - covered by Dockerfile inspection (no PG needed)
- bb21eff (/healthz/deps env fingerprint)   - covered by test_hotfix_regressions (no PG needed)
- 501bcff (row_counts_json matches JSONB)   - **this file**

This file also pins the basic init_db() + AuditLog + ImportBatch behavior
against a real PG roundtrip, so future migrations that work on SQLite but
break on PG get caught in CI.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

# Register the PG fixtures from tests/conftest_pg.py. Pytest only auto-loads
# conftest.py; the _pg suffix would otherwise be ignored. This plugin line
# is the documented pytest way to expose fixtures from a non-conftest module.
pytest_plugins = ["tests.conftest_pg"]


def test_init_db_applies_all_migrations(pg_engine):
    """init_db() should run all migrations and bring schema_version to CURRENT_SCHEMA_VERSION.

    On SQLite this is trivial (CREATE TABLE IF NOT EXISTS). On Postgres,
    migrations include ALTER TABLE / CREATE INDEX statements that may have
    PG-specific syntax (e.g., JSONB defaults, partial indexes). This test
    catches any migration that fails silently on PG.
    """
    from app.rms.db import CURRENT_SCHEMA_VERSION, schema_version

    with pg_engine.connect() as conn:
        actual = schema_version(conn)
    assert actual == CURRENT_SCHEMA_VERSION, (
        f"init_db left DB at schema v{actual}, expected v{CURRENT_SCHEMA_VERSION}. "
        "A migration probably failed silently on Postgres."
    )


def test_audit_log_insert_and_query(pg_session_factory):
    """AuditLog row inserts and reads back via PG. Catches issues like
    NULL detail JSONB default or column-type mismatches.
    """
    from app.rms.models import AuditLog

    with pg_session_factory() as session:
        row = AuditLog(
            occurred_at=datetime.now(timezone.utc),
            user_id="test-user-uuid-1234567890",
            action="test.smoke",
            target_type="test",
            target_id="42",
            detail={"k": "v", "n": 1},
            ip="127.0.0.1",
            user_agent="test/1.0",
        )
        session.add(row)
        session.commit()
        session.refresh(row)

        assert row.id is not None
        assert row.action == "test.smoke"
        # detail may come back as dict (PG JSONB) or str (PG TEXT fallback).
        if isinstance(row.detail, str):
            assert json.loads(row.detail) == {"k": "v", "n": 1}
        else:
            assert row.detail == {"k": "v", "n": 1}


def test_row_counts_json_jsonb_roundtrip_on_postgres(pg_session_factory):
    """Hotfix 501bcff lock-in test, run against real PG JSONB.

    On Postgres, a Text-typed ORM column holding a dict raises
    DatatypeMismatch on insert. With the JSON-typed column, the
    dialect renders JSONB and accepts the dict directly.

    Reverting 501bcff (changing JSON back to Text) would 500 every
    Excel import on hosted. This test catches that regression against
    the real PG engine.
    """
    from app.rms.models import ImportBatch

    counts = {"ingredients": 5, "recipes": 2, "products": 3, "nested": {"a": 1}}
    with pg_session_factory() as session:
        batch = ImportBatch(
            imported_at=datetime.now(timezone.utc),
            source_filename="test_pg.xlsx",
            note="PG JSONB regression test",
            row_counts_json=counts,
        )
        session.add(batch)
        session.commit()
        session.refresh(batch)
        # PG returns JSONB as a Python dict directly (not a string).
        assert batch.row_counts_json == counts, (
            f"PG roundtrip altered the dict: in={counts} out={batch.row_counts_json!r}"
        )


def test_psycopg3_dialect_recognized(pg_engine):
    """The engine must use the psycopg3 driver (postgresql+psycopg://).

    psycopg2 (postgresql+psycopg2://) is deprecated in favor of psycopg3.
    Hotfix 32c5d32 corrected the dialect prefix; this test pins the
    correct driver on real PG.
    """
    assert pg_engine.dialect.name == "postgresql"
    # psycopg3 dialect name surfaces as 'psycopg' in the driver name.
    drivername = pg_engine.dialect.driver  # type: ignore[attr-defined]
    assert drivername == "psycopg", (
        f"Engine uses {drivername!r}, expected 'psycopg'. "
        "Hotfix 32c5d32 corrected this — reverting breaks PG inserts."
    )
