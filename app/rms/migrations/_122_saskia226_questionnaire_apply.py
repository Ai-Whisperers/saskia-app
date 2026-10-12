"""Migration 122 — SASKIA-226: apply Saskia's 2026-10-08 questionnaire answers
to the live settings_kv rows that still hold the seed-default placeholders.

Why: the live saskia-vps DB was seeded with the original placeholder values
("Av. España 1234, casi Brasil, Asunción", "+595 21 555-1000", "hola@lavaquita.example")
before the 2026-10-08 onboarding questionnaire was completed. The seeder
now carries the operator's real answers in BUSINESS_INFO (see
app/rms/seed/sazon.py), but the seeder's settings_kv branch is
skip-on-existing (KV-wins) and so re-running it does NOT update
already-seeded rows. This migration overwrites the three branding
contact rows with the operator's answers (Saskia confirmed §2.1, §2.3,
§2.4 of the onboarding questionnaire).

Idempotent: the UPDATE statement is a no-op if the value_json already
matches. Safe to re-run. Does NOT touch any other settings_kv row.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import text

# Operator's answers from the 2026-10-08 onboarding questionnaire (Saskia
# Weiss Vander, La Vaquita Holandesa). These match the BUSINESS_INFO
# constants in app/rms/seed/sazon.py — keep both in sync.
UPDATES: list[tuple[str, str, str]] = [
    # (key, new_value_json, source_section)
    # SASKIA-225 (2026-10-12) — these 5 keys existed on the live DB
    # with the OLD seed placeholders. The seeder's settings_kv branch
    # is skip-on-existing (KV-wins), so re-running the seeder does NOT
    # update them. This migration overwrites them with the operator's
    # answers (Saskia confirmed §2.1, §2.3, §2.4 of the 2026-10-08
    # onboarding questionnaire).
    (
        "branding.address",
        "Laguán Grande, Arquitectos, Calle 17, Asunción",
        "§2.1 — dirección completa del local",
    ),
    (
        "branding.contact_phone",
        "+595 991 683805",
        "§2.3 — teléfono / WhatsApp",
    ),
    (
        "branding.contact_email",
        "La.vaquitaholandesa@gmail.com",
        "§2.4 — email de contacto",
    ),
    # §8.1 — same number (Saskia uses WhatsApp for orders)
    (
        "sales.shop_whatsapp",
        "+595 991 683805",
        "§8.1 — WhatsApp para tomar pedidos",
    ),
    # §8.7 — manual change (operator override of the seed default)
    (
        "ops.pickup_instructions",
        "Tocar timbre. Si está cerrado, llamar al +595 991 683805.",
        "§8.7 — manual change (auto-update from new phone)",
    ),
]

# SASKIA-221 (2026-10-12) added 6 new settings to the registry (CONTACT
# + LOCATION group). These did NOT exist on the live DB before this
# deploy, so the migration also needs to INSERT them (not just UPDATE
# the existing ones above).
INSERTS: list[tuple[str, str, str]] = [
    # CONTACT (3) — SASKIA-221 settings, all sourced from the operator's
    # questionnaire answers in BUSINESS_INFO.
    (
        "contact.phone",
        "+595 991 683805",
        "Saskia §2.3",
    ),
    (
        "contact.email",
        "La.vaquitaholandesa@gmail.com",
        "Saskia §2.4",
    ),
    (
        "contact.whatsapp",
        "+595 991 683805",
        "Saskia §8.1 (alias of sales.shop_whatsapp)",
    ),
    # LOCATION (3) — SASKIA-221 settings, sourced from the operator's
    # questionnaire answers in BUSINESS_INFO.
    (
        "location.address_full",
        "Laguán Grande, Arquitectos, Calle 17, Asunción",
        "Saskia §2.1",
    ),
    (
        "location.city",
        "Asunción",
        "Saskia §2.1",
    ),
    (
        "location.department",
        "Central",
        "Saskia §2.1 — Central/San Lorenzo area",
    ),
]


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _migration_122_saskia226_questionnaire_apply(conn: Any) -> None:
    """Apply the 5 settings_kv updates + 6 new inserts from the operator's
    questionnaire.

    Each update is a no-op if the current value_json already matches
    (so re-running the migration is safe). Each insert is a no-op if
    the key already exists (KV-wins).
    """
    for key, new_value, _source in UPDATES:
        existing = conn.execute(
            text("SELECT value_json FROM settings_kv WHERE key = :k"),
            {"k": key},
        ).fetchone()
        if existing is None:
            # The key doesn't exist yet — insert it. The seeder would
            # have created it on a fresh DB; on a re-seeded DB the
            # legacy importer may not have run.
            conn.execute(
                text(
                    "INSERT INTO settings_kv (key, value_json, updated_at) "
                    "VALUES (:k, :v, :ts)"
                ),
                {"k": key, "v": new_value, "ts": _now_iso()},
            )
        elif existing[0] != new_value:
            # Update the value (KV-wins override of the seed placeholder).
            conn.execute(
                text(
                    "UPDATE settings_kv SET value_json = :v, updated_at = :ts "
                    "WHERE key = :k"
                ),
                {"k": key, "v": new_value, "ts": _now_iso()},
            )

    # SASKIA-221 INSERTs — only insert if the key doesn't exist (these
    # were added in a recent registry update and won't be on the live
    # DB until either the seeder runs or this migration lands).
    for key, new_value, _source in INSERTS:
        existing = conn.execute(
            text("SELECT value_json FROM settings_kv WHERE key = :k"),
            {"k": key},
        ).fetchone()
        if existing is None:
            conn.execute(
                text(
                    "INSERT INTO settings_kv (key, value_json, updated_at) "
                    "VALUES (:k, :v, :ts)"
                ),
                {"k": key, "v": new_value, "ts": _now_iso()},
            )
        # If the key exists with a different value, do NOT overwrite —
        # these are new settings and the operator may have already
        # configured them. The 5 keys above (UPDATES) are the only ones
        # the operator answered before they were seeded, so they are
        # the only ones we override.

    # Bump INSIDE this function — each migration owns its own bump.
    from app.rms.db import _bump_schema_version

    _bump_schema_version(conn, 122)
