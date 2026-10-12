"""Tests for migration 124 — SASKIA-226 questionnaire columns.

Saskia's 2026-10-08 onboarding questionnaire included questions that
don't have a place in the current schema:
- §20.1 MIPYME/MIE registration (operator answer: TBD)
- §22.1 Barrio/zona of the local
- §22.2 Estacionamiento for clients

This migration adds:
- compliance_info.is_mipyme_mie (boolean, default false)
- tenant.barrio (varchar 64, nullable)
- tenant.zona (varchar 64, nullable)
- tenant.has_parking (boolean, default false)
"""
from __future__ import annotations

from sqlalchemy import text


def test_migration_124_schema_version_bumped(session_factory):
    """Fresh DB runs init_db through migration 124."""
    with session_factory() as s:
        v = s.execute(text("SELECT value FROM app_meta WHERE key='schema_version'")).scalar()
    assert v is not None
    assert int(v) >= 124


def test_migration_124_adds_is_mipyme_mie_column(session_factory):
    """compliance_info.is_mipyme_mie column exists and defaults to false."""
    with session_factory() as s:
        cols = [r[1] for r in s.execute(text("PRAGMA table_info(compliance_info)")).fetchall()]
    assert "is_mipyme_mie" in cols

    # The default value is false
    with session_factory() as s:
        # Trigger init of the compliance_info row if not present
        s.execute(
            text(
                "INSERT OR IGNORE INTO compliance_info (id, tax_regime, iva_default_rate) "
                "VALUES (1, 'resimple', '10')"
            )
        )
        s.commit()
        mipyme = s.execute(
            text("SELECT is_mipyme_mie FROM compliance_info WHERE id = 1")
        ).fetchone()
    assert mipyme is not None
    # SQLite stores booleans as 0/1
    assert mipyme[0] in (0, False)


def test_migration_124_adds_tenant_location_columns(session_factory):
    """tenant.barrio, tenant.zona, tenant.has_parking columns exist."""
    with session_factory() as s:
        cols = [r[1] for r in s.execute(text("PRAGMA table_info(tenant)")).fetchall()]
    for col in ("barrio", "zona", "has_parking"):
        assert col in cols, f"column '{col}' missing from tenant table"


def test_migration_124_tenant_defaults(session_factory):
    """Insert a fresh tenant row; verify barrio/zona are NULL and
    has_parking defaults to 0."""
    with session_factory() as s:
        s.execute(
            text(
                "INSERT INTO tenant (id, slug, business_name, primary_color, currency) "
                "VALUES (1, 'default', 'Test Tenant', '#7b3f00', 'Gs.')"
            )
        )
        s.commit()
        t = s.execute(
            text("SELECT barrio, zona, has_parking FROM tenant WHERE id = 1")
        ).fetchone()
    assert t is not None
    assert t[0] is None  # barrio
    assert t[1] is None  # zona
    assert t[2] in (0, False)  # has_parking


def test_migration_124_can_set_tenant_location(session_factory):
    """After migration 124, the operator can save §22.1 + §22.2 answers."""
    with session_factory() as s:
        s.execute(
            text(
                "INSERT INTO tenant (id, slug, business_name, primary_color, currency) "
                "VALUES (1, 'default', 'Test Tenant', '#7b3f00', 'Gs.')"
            )
        )
        s.execute(
            text(
                "UPDATE tenant SET barrio = 'San Lorenzo', zona = 'residencial', "
                "has_parking = 1 WHERE id = 1"
            )
        )
        s.commit()
        t = s.execute(
            text("SELECT barrio, zona, has_parking FROM tenant WHERE id = 1")
        ).fetchone()
    assert t[0] == "San Lorenzo"
    assert t[1] == "residencial"
    assert t[2] in (1, True)


def test_migration_124_applies_vaquita_holandesa_answers(session_factory):
    """If the la-vaquita-holandesa tenant row exists with empty
    location fields, the migration applies §22.1 + §22.2 answers.

    The fixture's session_factory goes through init_db, which inserts
    a 'default' tenant. We simulate the live scenario by inserting a
    second tenant with slug='la-vaquita-holandesa' and NULL location
    fields, then running the migration and verifying the migration
    wrote §22.1 + §22.2 values.
    """
    with session_factory() as s:
        s.execute(
            text(
                "INSERT INTO tenant (id, slug, business_name, primary_color, currency) "
                "VALUES (99, 'la-vaquita-holandesa', 'La Vaquita Holandesa', '#7b3f00', 'Gs.')"
            )
        )
        s.commit()

    from app.rms.migrations._124_saskia226_questionnaire_columns import (
        _migration_124_saskia226_questionnaire_columns,
    )

    with session_factory().get_bind().connect() as conn:
        _migration_124_saskia226_questionnaire_columns(conn)
        conn.commit()

    with session_factory() as s:
        t = s.execute(
            text(
                "SELECT barrio, zona, has_parking FROM tenant "
                "WHERE slug = 'la-vaquita-holandesa'"
            )
        ).fetchone()
    assert t[0] == "San Lorenzo", f"expected 'San Lorenzo', got {t[0]!r}"
    assert t[1] == "residencial", f"expected 'residencial', got {t[1]!r}"
    assert t[2] in (1, True)


def test_migration_124_idempotent_for_existing_vaquita_values(session_factory):
    """If the la-vaquita-holandesa tenant row already has §22.1 + §22.2
    values, re-running the migration does not change them."""
    with session_factory() as s:
        s.execute(
            text(
                "INSERT INTO tenant (id, slug, business_name, primary_color, currency, "
                "barrio, zona, has_parking) "
                "VALUES (99, 'la-vaquita-holandesa', 'La Vaquita Holandesa', '#7b3f00', "
                "'Gs.', 'San Lorenzo', 'residencial', 1)"
            )
        )
        s.commit()

    from app.rms.migrations._124_saskia226_questionnaire_columns import (
        _migration_124_saskia226_questionnaire_columns,
    )

    # Run twice — second call should be a no-op
    with session_factory().get_bind().connect() as conn:
        _migration_124_saskia226_questionnaire_columns(conn)
        conn.commit()
        _migration_124_saskia226_questionnaire_columns(conn)
        conn.commit()

    with session_factory() as s:
        t = s.execute(
            text(
                "SELECT barrio, zona, has_parking FROM tenant "
                "WHERE slug = 'la-vaquita-holandesa'"
            )
        ).fetchone()
    assert t[0] == "San Lorenzo"
    assert t[1] == "residencial"
    assert t[2] in (1, True)


def test_migration_124_idempotent_on_rerun(session_factory):
    """Running the migration twice does not error (column already exists)."""
    from app.rms.migrations._124_saskia226_questionnaire_columns import (
        _migration_124_saskia226_questionnaire_columns,
    )

    # Run twice — should be no-ops the second time
    with session_factory().get_bind().connect() as conn:
        _migration_124_saskia226_questionnaire_columns(conn)
        conn.commit()
        _migration_124_saskia226_questionnaire_columns(conn)
        conn.commit()

    with session_factory() as s:
        cols = [r[1] for r in s.execute(text("PRAGMA table_info(tenant)")).fetchall()]
    for col in ("barrio", "zona", "has_parking"):
        assert col in cols
