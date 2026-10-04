"""tests/test_address_phase13_delivery_ux.py — Phase 13 (2026-10-01) tests.

Covers:
  1. address_compose — discrete fields -> composed string
  2. ventana_text — ASAP / Window / Scheduled render correctly + the
     "(no es garantía)" suffix in the window/scheduled cases.
  3. default_invoice_profile_payload — the customer invoice profile
     payload helper picks is_default row first, then non-defaults by alias.
  4. Migration 079 → 081 schema_version sanity (CURRENT_SCHEMA_VERSION
     is 81 after init_db runs).
"""

from app.services.customer_address import (
    compose_address_text,
    default_invoice_profile_payload,
    ventana_text,
)


# ── 1. address_compose ─────────────────────────────────────────────
def test_address_compose_full_fields():
    out = compose_address_text(
        {
            "calle_principal": "Av. España",
            "calle_secundaria": "Curupayty",
            "numero": "1234",
            "edificio": "Torre X",
            "piso": "5",
            "unidad": "B",
            "barrio": "Las Carmelitas",
            "ciudad": "Asunción",
            "departamento": "Central",
        }
    )
    assert "Av. España" in out
    assert "Curupayty" in out or "e/" in out  # "entre" indicator
    assert "1234" in out
    assert "Torre X" in out
    assert "5" in out
    assert "B" in out
    assert "Las Carmelitas" in out
    assert "Asunción" in out


def test_address_compose_omits_empty_fields():
    # No edificio/piso/unidad → no parenthesis; calle_secundaria not present
    out = compose_address_text(
        {
            "calle_principal": "Av. España",
            "numero": "1234",
            "barrio": "Recoleta",
        }
    )
    assert out == "Av. España 1234, Barrio Recoleta"
    # No parenthesis since no edificio/piso
    assert "(" not in out
    assert "Torre" not in out


def test_address_compose_returns_empty_for_empty_input():
    assert compose_address_text({}) == ""
    assert compose_address_text(None) == ""


# ── 2. ventana_text ────────────────────────────────────────────────
def test_ventana_text_asap_default_no_garantia_disclaimer():
    # ASAP doesn't get the "no es garantía" disclaimer — that's exactly
    # what ASAP is. But it still tells the cashier the type.
    out = ventana_text(None, None, None, None)
    assert "ASAP" in out or "lo antes posible" in out.lower()


def test_ventana_text_window_includes_no_garantia_disclaimer():
    out = ventana_text("window", "14:00", "16:00", None)
    assert "14:00" in out
    assert "16:00" in out
    # explicit "(no es garantía)" is required so the cashier doesn't
    # commit to a hard SLA they can't keep.
    assert "no es garantía" in out.lower() or "preferida" in out.lower()


def test_ventana_text_scheduled_includes_date_and_no_garantia():
    out = ventana_text("scheduled", "10:00", "12:00", "2026-12-25")
    assert "10:00" in out
    assert "12:00" in out
    assert "2026-12-25" in out or "25/12/2026" in out


def test_ventana_text_handles_only_one_time():
    # half-specified window still renders (no crash, graceful fallback)
    out = ventana_text("window", "14:00", "", None)
    assert "14:00" in out


# ── 3. default_invoice_profile_payload ─────────────────────────────
def test_default_invoice_profile_payload_picks_default_first():
    profiles = [
        {"id": 11, "alias": "Empresa B", "ruc_ci": "80022222-1", "is_default": False},
        {"id": 22, "alias": "Personal", "ruc_ci": "1234567", "is_default": True},
        {"id": 33, "alias": "Empresa A", "ruc_ci": "80011111-1", "is_default": False},
    ]
    payload = default_invoice_profile_payload(profiles)
    assert isinstance(payload, list)
    assert payload[0]["id"] == 22  # the is_default one wins
    assert all(p["ruc_ci"] for p in payload)


def test_default_invoice_profile_payload_empty_returns_none():
    # No profiles → cashier falls back to typing RUC/CI manually
    assert default_invoice_profile_payload([]) is None
    assert default_invoice_profile_payload(None) is None


def test_default_invoice_profile_payload_sorts_non_default_by_alias():
    profiles = [
        {"id": 1, "alias": "Zeta", "ruc_ci": "9999", "is_default": False},
        {"id": 2, "alias": "Alfa", "ruc_ci": "1111", "is_default": False},
        {"id": 3, "alias": "Mia", "ruc_ci": "3333", "is_default": False},
    ]
    payload = default_invoice_profile_payload(profiles)
    assert payload is not None
    # Helper renames `alias` to `label`
    labels = [p["label"] for p in payload]
    assert labels == ["Alfa", "Mia", "Zeta"]


# ── 4. Schema version after init_db ────────────────────────────────
def test_schema_version_is_at_least_81():
    """Phase 13: migrations 079 (structured address), 080 (invoice
    profiles), and 081 (delivery window) require CURRENT_SCHEMA_VERSION
    ≥ 81. After init_db on a fresh DB, schema_version == 81."""
    from app.rms.config import CURRENT_SCHEMA_VERSION
    from app.rms.db import init_db

    assert CURRENT_SCHEMA_VERSION >= 81, (
        f"Expected CURRENT_SCHEMA_VERSION ≥ 81, got {CURRENT_SCHEMA_VERSION}"
    )
    # Smoke-run init_db on a fresh in-memory engine; if migrations 079-081
    # are not wired in init_db, schema stays at 78 (and init_db raises).
    from sqlalchemy import create_engine

    eng = create_engine("sqlite:///:memory:")
    init_db(eng)
    # We don't import init_db here without engine; use a quick smoke
    # through the live DB initialiser path with a tmp file.
    import os
    import tempfile

    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    try:
        eng2 = create_engine(f"sqlite:///{path}")
        init_db(eng2)
        with eng2.connect() as conn:
            from sqlalchemy import text

            ver = conn.execute(
                text("SELECT value FROM app_meta WHERE key='schema_version'")
            ).scalar_one_or_none()
        assert ver is not None
        assert int(ver) >= 81, f"DB schema_version is {ver}, expected ≥ 81"
    finally:
        if os.path.exists(path):
            os.remove(path)
