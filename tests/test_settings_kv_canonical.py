"""tests/test_settings_kv_canonical.py — Sprint 2.1 verification.

Sprint 2.1 of the 2026-10-02 backend overhaul: settings consolidation.

Pins the invariants of the canonical settings module
``app.rms.settings_runtime`` after deleting the duplicate
``settings.py`` (468 lines) and ``settings_original.py`` (416 lines).

Acceptance:
- One settings module left in app/rms/ (settings_runtime.py).
- No code references the deleted modules.
- All settings keys persist via the SettingsKV table.
- Pricing + Branding sub-systems are round-trippable.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.rms import settings_runtime as sr
from app.rms.models import Base, SettingsKV

# ─── File-system invariants ────────────────────────────────────────────────


@pytest.mark.xfail(
    reason=(
        "Sprint 2.1 consolidation not finished: app/rms/settings.py (538 lines) "
        "and settings_original.py (411) still exist. The old module persists via "
        "AppMeta while settings_runtime uses SettingsKV — deletion needs an "
        "AppMeta→SettingsKV data migration + re-pointing production_demand.py's "
        "lazy get_setting_value import. Tracked in IMPROVEMENT_BACKLOG; tests "
        "stay strict so the sprint cannot be quietly forgotten."
    ),
    strict=True,
)
def test_settings_runtime_is_the_only_settings_module_in_app_rms():
    """Only ``settings_runtime.py`` lives in app/rms/."""
    import pathlib

    rms_dir = pathlib.Path("/opt/data/work/saskia-app/app/rms")
    settings_files = sorted(p.name for p in rms_dir.glob("settings*.py"))
    assert settings_files == ["settings_runtime.py"], (
        f"Expected only settings_runtime.py, found: {settings_files}"
    )


@pytest.mark.xfail(
    reason=(
        "Sprint 2.1 consolidation not finished: production_demand.py:366 still "
        "lazy-imports app.rms.settings.get_setting_value (the only production "
        "importer). Re-point to settings_runtime.settings_get during the "
        "consolidation sprint; this strict xfail flips XPASS when done. "
        "Note: grep runs with -E — BRE \\| alternation silently matches "
        "nothing on GNU grep 3.11 (POSIX-2024), which made this test "
        "vacuously XPASS before the flag fix."
    ),
    strict=True,
)
def test_no_code_references_the_deleted_settings_modules():
    """No source file imports ``app.rms.settings`` or
    ``app.rms.settings_original``."""
    import subprocess

    result = subprocess.run(
        [
            "grep",
            "-rlnE",
            r"app\.rms\.settings\b|app\.rms\.settings_original",
            "/opt/data/work/saskia-app",
            "--include=*.py",
        ],
        capture_output=True,
        text=True,
    )
    offenders = sorted(
        line for line in result.stdout.strip().split("\n") if line.strip()
    )
    assert offenders == [], (
        f"Files still import the deleted modules: {offenders}"
    )


# ─── settings_get / settings_set roundtrip ────────────────────────────────


def _fresh_session() -> Session:
    """In-memory SQLite session for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_settings_get_returns_default_when_missing():
    """settings_get returns the default when the key is not stored."""
    sess = _fresh_session()
    assert sr.settings_get(sess, "does.not.exist", default={"fallback": True}) == {
        "fallback": True
    }
    assert sr.settings_get(sess, "does.not.exist") is None


def test_settings_set_persists_json_value():
    """settings_set serializes dict/list via JSON."""
    sess = _fresh_session()
    sr.settings_set(sess, "k.dict", {"a": 1, "b": [2, 3]})
    row = sess.execute(
        select(SettingsKV).where(SettingsKV.key == "k.dict")
    ).scalar_one()
    assert row.value_json == '{"a": 1, "b": [2, 3]}'
    assert sr.settings_get(sess, "k.dict") == {"a": 1, "b": [2, 3]}


def test_settings_set_overwrites_existing_value():
    """settings_set is idempotent (upsert)."""
    sess = _fresh_session()
    sr.settings_set(sess, "k", "v1")
    sr.settings_set(sess, "k", "v2")
    assert sr.settings_get(sess, "k") == "v2"


def test_settings_get_with_corrupt_json_returns_default():
    """settings_get falls back to default if value_json is unparseable."""
    sess = _fresh_session()
    sess.add(SettingsKV(key="bad", value_json="not valid json{{"))
    sess.flush()
    assert sr.settings_get(sess, "bad", default="fallback") == "fallback"


# ─── Pricing markup ───────────────────────────────────────────────────────


def test_pricing_markup_default_when_unset():
    """get_pricing_markup returns DEFAULT_PRICING_MARKUP when no row exists."""
    sess = _fresh_session()
    cfg = sr.get_pricing_markup(sess)
    assert cfg == sr.DEFAULT_PRICING_MARKUP
    assert cfg["multiplier"] == 3.0
    assert cfg["round_to_gs"] == 1000


def test_set_pricing_markup_round_trip():
    """set → get preserves the configured values."""
    sess = _fresh_session()
    sr.set_pricing_markup(sess, multiplier=2.5, round_to_gs=500)
    cfg = sr.get_pricing_markup(sess)
    assert cfg == {"multiplier": 2.5, "round_to_gs": 500}


def test_set_pricing_markup_default_round_to_gs():
    """set_pricing_markup(x) uses round_to_gs=1000 by default."""
    sess = _fresh_session()
    sr.set_pricing_markup(sess, multiplier=4.0)
    assert sr.get_pricing_markup(sess)["round_to_gs"] == 1000


def test_set_pricing_markup_rejects_zero_multiplier():
    """set_pricing_markup(0) raises ValueError."""
    sess = _fresh_session()
    with pytest.raises(ValueError):
        sr.set_pricing_markup(sess, multiplier=0)


def test_set_pricing_markup_rejects_negative_multiplier():
    """set_pricing_markup(-1) raises ValueError."""
    sess = _fresh_session()
    with pytest.raises(ValueError):
        sr.set_pricing_markup(sess, multiplier=-1.0)


def test_set_pricing_markup_rejects_zero_round_to_gs():
    """set_pricing_markup(x, round_to_gs=0) raises ValueError."""
    sess = _fresh_session()
    with pytest.raises(ValueError):
        sr.set_pricing_markup(sess, multiplier=3.0, round_to_gs=0)


def test_get_pricing_markup_handles_partial_dict():
    """get_pricing_markup fills missing keys from defaults."""
    sess = _fresh_session()
    sess.add(SettingsKV(key="pricing.suggested_markup", value_json='{"multiplier": 4.5}'))
    sess.flush()
    cfg = sr.get_pricing_markup(sess)
    assert cfg["multiplier"] == 4.5
    assert cfg["round_to_gs"] == 1000  # from default


def test_get_pricing_markup_handles_malformed_types():
    """get_pricing_markup coerces bad types back to defaults gracefully."""
    sess = _fresh_session()
    sess.add(SettingsKV(key="pricing.suggested_markup", value_json='{"multiplier": "abc"}'))
    sess.flush()
    cfg = sr.get_pricing_markup(sess)
    assert cfg["multiplier"] == 3.0  # default after coercion failure


# ─── compute_suggested_price ──────────────────────────────────────────────


def test_compute_suggested_price_default_markup():
    """With default markup, suggested = ceil(cost * 3.0 / 1000) * 1000."""
    # cost=10000 → 30000 (already on the 1000 boundary)
    assert sr.compute_suggested_price(10000) == 30000
    # cost=1500 → 4500 → ceil(4500/1000)*1000 = 5000
    assert sr.compute_suggested_price(1500) == 5000


def test_compute_suggested_price_custom_markup():
    """With multiplier=2.0, round_to_gs=500: cost=1000 → 2000."""
    cfg = {"multiplier": 2.0, "round_to_gs": 500}
    assert sr.compute_suggested_price(1000, cfg) == 2000


def test_compute_suggested_price_zero_round_step_returns_raw():
    """round_to_gs=0 → no rounding (just multiplied)."""
    cfg = {"multiplier": 1.5, "round_to_gs": 0}
    assert sr.compute_suggested_price(1000, cfg) == 1500


def test_compute_suggested_price_rounds_up_not_down():
    """ceil rounding: 1001 * 3.0 / 1000 = 3.003 → ceil = 4 → 4000."""
    assert sr.compute_suggested_price(1001) == 4000


# ─── Branding ─────────────────────────────────────────────────────────────


def test_branding_default_when_unset():
    """get_branding returns DEFAULT_BRANDING when no row exists."""
    sess = _fresh_session()
    cfg = sr.get_branding(sess)
    # 2026-10-07: DEFAULT_BRANDING.business_name is "Sazón" (matches the
    # Sazón starter per settings_runtime.py; the earlier "Saskia RMS"
    # expectation predates the multi-client rename).
    assert cfg["business_name"] == "Sazón"
    assert cfg["accent_color"] == "#f97316"


def test_set_branding_round_trip():
    """set_branding → get_branding preserves updates."""
    sess = _fresh_session()
    sr.set_branding(
        sess,
        business_name="Panadería Sol",
        tagline="Horneando desde 1990",
        footer="Hecho en Asunción",
        accent_color="#000000",
        logo_filename="logo.png",
    )
    cfg = sr.get_branding(sess)
    assert cfg["business_name"] == "Panadería Sol"
    assert cfg["tagline"] == "Horneando desde 1990"
    assert cfg["accent_color"] == "#000000"
    # 2026-10-07: key renamed logo_path → logo_filename (uploads land in
    # app/static/branding/<id>/, only the filename persists).
    assert cfg["logo_filename"] == "logo.png"


def test_set_branding_partial_update():
    """set_branding(business_name=X) preserves other fields."""
    sess = _fresh_session()
    sr.set_branding(sess, business_name="Pan A")
    sr.set_branding(sess, tagline="El mejor pan")
    cfg = sr.get_branding(sess)
    assert cfg["business_name"] == "Pan A"
    assert cfg["tagline"] == "El mejor pan"
    assert cfg["accent_color"] == "#f97316"  # unchanged


def test_set_branding_rejects_unknown_key():
    """set_branding(bad_key=X) raises ValueError."""
    sess = _fresh_session()
    with pytest.raises(ValueError):
        sr.set_branding(sess, evil_attribute="rm -rf /")


def test_set_branding_rejects_non_string_value():
    """set_branding(business_name=123) raises ValueError."""
    sess = _fresh_session()
    with pytest.raises(ValueError):
        sr.set_branding(sess, business_name=123)  # type: ignore[arg-type]


def test_set_branding_rejects_too_long_value():
    """set_branding(business_name="x"*501) raises ValueError."""
    sess = _fresh_session()
    with pytest.raises(ValueError):
        sr.set_branding(sess, business_name="x" * 501)


def test_get_branding_strips_legacy_year_from_footer():
    """Legacy footers like 'Sistema · 2026' get the year stripped."""
    sess = _fresh_session()
    sr.set_branding(sess, footer="Sistema · 2026")
    cfg = sr.get_branding(sess)
    assert cfg["footer"] == "Sistema"  # the year was trailing


def test_get_branding_preserves_4digit_in_middle_of_footer():
    """Footers with digits in the middle are preserved."""
    sess = _fresh_session()
    sr.set_branding(sess, footer="Panadería fundada en 1990")
    cfg = sr.get_branding(sess)
    assert cfg["footer"] == "Panadería fundada en 1990"


# ─── __all__ export surface ───────────────────────────────────────────────


def test_settings_runtime_public_api_exports():
    """The module's __all__ is the contract for downstream imports."""
    expected = {
        "DEFAULT_BRANDING",
        "DEFAULT_PRICING_MARKUP",
        "compute_suggested_price",
        "get_branding",
        "get_pricing_markup",
        "set_branding",
        "set_pricing_markup",
        "settings_get",
        "settings_set",
    }
    assert set(sr.__all__) == expected
