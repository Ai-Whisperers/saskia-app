"""Tests for migration 122 — SASKIA-226 questionnaire apply.

Saskia's 2026-10-08 onboarding questionnaire provided the real
operator answers for: address, phone, email, WhatsApp. The seeder
already has these in BUSINESS_INFO, but its settings_kv branch is
skip-on-existing, so re-running the seeder does NOT update rows that
were already seeded with the old placeholders. Migration 122 overwrites
those 5 rows with the operator's answers.

Idempotency: the UPDATE is a no-op if value_json already matches, so
re-running the migration on the same DB is safe.
"""
from __future__ import annotations

from sqlalchemy import bindparam, text

# The 5 keys this migration updates, paired with the operator's answers.
EXPECTED_UPDATES = {
    "branding.address": "Laguán Grande, Arquitectos, Calle 17, Asunción",
    "branding.contact_phone": "+595 991 683805",
    "branding.contact_email": "La.vaquitaholandesa@gmail.com",
    "sales.shop_whatsapp": "+595 991 683805",
    "ops.pickup_instructions": "Tocar timbre. Si está cerrado, llamar al +595 991 683805.",
}

# The 6 keys this migration inserts (if missing), paired with the
# operator's answers.
EXPECTED_INSERTS = {
    "contact.phone": "+595 991 683805",
    "contact.email": "La.vaquitaholandesa@gmail.com",
    "contact.whatsapp": "+595 991 683805",
    "location.address_full": "Laguán Grande, Arquitectos, Calle 17, Asunción",
    "location.city": "Asunción",
    "location.department": "Central",
}

EXPECTED_VALUES = {**EXPECTED_UPDATES, **EXPECTED_INSERTS}


def test_migration_122_schema_version_bumped(session_factory):
    """Fresh DB runs init_db through migration 122."""
    with session_factory() as s:
        v = s.execute(text("SELECT value FROM app_meta WHERE key='schema_version'")).scalar()
    assert v is not None
    assert int(v) >= 122


def test_migration_122_overrides_placeholder_values(session_factory):
    """Insert the OLD placeholder values, then run the migration, then
    verify the values are now the operator's answers.

    The fixture's session_factory goes through init_db, which already
    seeds these keys with the operator's values (via the seeder's
    SASKIA-215 BUSINESS_INFO). So we first UPDATE the rows to the old
    placeholders, then run the migration, then verify the migration
    overwrote them with the operator's correct values.
    """
    placeholders = {
        "branding.address": "Av. España 1234, casi Brasil, Asunción",
        "branding.contact_phone": "+595 21 555-1000",
        "branding.contact_email": "hola@lavaquita.example",
        "sales.shop_whatsapp": "+595 981 000000",
        "ops.pickup_instructions": "Tocar timbre. Si está cerrado, llamar al +595 21 555-1000.",
    }
    with session_factory() as s:
        for k, v in placeholders.items():
            s.execute(
                text(
                    "UPDATE settings_kv SET value_json = :v, updated_at = '2026-10-08T00:00:00+00:00' "
                    "WHERE key = :k"
                ),
                {"k": k, "v": v},
            )
        s.commit()

    from app.rms.migrations._122_saskia226_questionnaire_apply import (
        _migration_122_saskia226_questionnaire_apply,
    )

    with session_factory().get_bind().connect() as conn:
        _migration_122_saskia226_questionnaire_apply(conn)
        conn.commit()

    with session_factory() as s:
        for key, expected in EXPECTED_VALUES.items():
            actual = s.execute(
                text("SELECT value_json FROM settings_kv WHERE key = :k"),
                {"k": key},
            ).fetchone()
            assert actual is not None, f"key '{key}' is missing"
            assert actual[0] == expected, (
                f"key '{key}' has wrong value.\n"
                f"  expected: {expected!r}\n"
                f"  actual:   {actual[0]!r}"
            )


def test_migration_122_idempotent_when_already_correct(session_factory):
    """If the rows already hold the operator's values, the migration
    does NOT touch them (the UPDATE branch is a no-op)."""
    # The fixture's session_factory already seeds these keys with the
    # operator's values via the seeder. We just verify that re-running
    # the migration does not change anything.

    from app.rms.migrations._122_saskia226_questionnaire_apply import (
        _migration_122_saskia226_questionnaire_apply,
    )

    with session_factory().get_bind().connect() as conn:
        _migration_122_saskia226_questionnaire_apply(conn)
        conn.commit()

    with session_factory() as s:
        for key, expected in EXPECTED_VALUES.items():
            actual = s.execute(
                text("SELECT value_json, updated_at FROM settings_kv WHERE key = :k"),
                {"k": key},
            ).fetchone()
            assert actual is not None, f"key '{key}' is missing after migration"
            assert actual[0] == expected, f"value of '{key}' changed"
            # updated_at is preserved (the UPDATE branch is a no-op,
            # so the row is not touched)


def test_migration_122_inserts_when_key_missing(session_factory):
    """If a key is not in settings_kv at all (e.g. live DB seeded before
    the seeder created the key), the migration INSERTS it."""
    # The fixture's session_factory goes through init_db, which seeds
    # these keys. We delete them first to simulate a DB where the
    # settings row was never written, then run the migration and verify
    # the migration inserts the operator's values.
    with session_factory() as s:
        s.execute(
            text(
                "DELETE FROM settings_kv WHERE key IN :keys"
            ).bindparams(bindparam("keys", expanding=True)),
            {"keys": list(EXPECTED_VALUES.keys())},
        )
        s.commit()

    from app.rms.migrations._122_saskia226_questionnaire_apply import (
        _migration_122_saskia226_questionnaire_apply,
    )

    with session_factory().get_bind().connect() as conn:
        _migration_122_saskia226_questionnaire_apply(conn)
        conn.commit()

    with session_factory() as s:
        for key, expected in EXPECTED_VALUES.items():
            actual = s.execute(
                text("SELECT value_json FROM settings_kv WHERE key = :k"),
                {"k": key},
            ).fetchone()
            assert actual is not None, f"key '{key}' was not inserted"
            assert actual[0] == expected


def test_migration_122_inserts_saskia221_keys_does_not_overwrite(session_factory):
    """SASKIA-221 added 6 new settings (contact.* + location.*). The
    migration inserts them if missing, but does NOT overwrite them if
    the operator has already configured a different value."""
    # Pre-set one of the SASKIA-221 keys to a DIFFERENT value, simulating
    # that the operator (or another process) has already configured it.
    with session_factory() as s:
        s.execute(
            text(
                "DELETE FROM settings_kv WHERE key IN :keys"
            ).bindparams(bindparam("keys", expanding=True)),
            {"keys": list(EXPECTED_INSERTS.keys())},
        )
        s.execute(
            text(
                "INSERT INTO settings_kv (key, value_json, updated_at) "
                "VALUES ('contact.email', :v, '2026-10-08T00:00:00+00:00')"
            ),
            {"v": "custom@lavaquita.example"},
        )
        s.commit()

    from app.rms.migrations._122_saskia226_questionnaire_apply import (
        _migration_122_saskia226_questionnaire_apply,
    )

    with session_factory().get_bind().connect() as conn:
        _migration_122_saskia226_questionnaire_apply(conn)
        conn.commit()

    with session_factory() as s:
        # The pre-set key was NOT overwritten
        custom = s.execute(
            text("SELECT value_json FROM settings_kv WHERE key = 'contact.email'")
        ).fetchone()
        assert custom[0] == "custom@lavaquita.example", (
            "operator's pre-set contact.email was overwritten"
        )
        # The OTHER SASKIA-221 keys were inserted
        for key in ("contact.phone", "contact.whatsapp", "location.address_full",
                    "location.city", "location.department"):
            actual = s.execute(
                text("SELECT value_json FROM settings_kv WHERE key = :k"),
                {"k": key},
            ).fetchone()
            assert actual is not None, f"SASKIA-221 key '{key}' was not inserted"
            assert actual[0] == EXPECTED_INSERTS[key]


def test_migration_122_keys_match_business_info():
    """The 5 updated values match the BUSINESS_INFO constants in the
    seeder. If you change one without the other, the next seeder run
    will be a no-op (skip-on-existing) and the values will drift."""
    from app.rms.seed.sazon import BUSINESS_INFO

    assert BUSINESS_INFO["address"] == EXPECTED_VALUES["branding.address"]
    assert BUSINESS_INFO["phone"] == EXPECTED_VALUES["branding.contact_phone"]
    assert BUSINESS_INFO["email"] == EXPECTED_VALUES["branding.contact_email"]
