"""SASKIA-215: Verify the 4 La Vaquita questionnaire answers land in
the settings_kv table when seed_sazon() runs.

This test guards against the registry-vs-seeder drift where the
questionnaire answers (location.barrio = 'San Lorenzo', etc.) are
known but neither the seeder nor the registry hard-codes them.

The 4 expected values come from the 2026-10-08 onboarding
questionnaire (sections 8.1, 16.6, 22.1, 22.2). Update both this
test AND seed/sazon.py's _seed_settingskv_branding (or a new
_seed_settingskv_vaquita helper) when the questionnaire is updated.
"""

from __future__ import annotations

import json
import os

import pytest
from sqlalchemy import select


def _make_empty_db(tmp_path):
    """Build a fresh SQLite DB with the full schema, no data."""
    db_path = tmp_path / "saskia-215.sqlite"
    os.environ["AIW_SASKIA_DB_PATH"] = str(db_path)
    os.environ["AIW_RMS_DB_PATH"] = str(db_path)

    from app.rms.db import init_db, make_engine, make_session_factory

    engine = make_engine(f"sqlite:///{db_path}")
    init_db(engine)
    SessionLocal = make_session_factory(engine)
    return db_path, SessionLocal


def test_seed_sazon_populates_vaquita_answers(tmp_path):
    """After seed_sazon() the 4 §8.1/§16.6/§22.1/§22.2 answers
    must be persisted in settings_kv with the questionnaire values.

    The seeder currently populates branding.* (post-SASKIA-213) but does
    NOT yet populate location.*, seasonal.*, or sales.shop_whatsapp.
    When the seeder is extended (this ticket's TODO), this test will
    flip from xfail to pass.
    """
    pytest.importorskip("app.rms.seed")
    _, SessionLocal = _make_empty_db(tmp_path)

    from app.rms.models_legacy import SettingsKV
    from app.rms.seed import seed_sazon

    s = SessionLocal()
    try:
        seed_sazon(s, overwrite=False)
        s.commit()
    finally:
        s.close()

    s = SessionLocal()
    try:
        rows = (
            s.execute(
                select(SettingsKV).where(
                    SettingsKV.key.in_(
                        [
                            "sales.shop_whatsapp",
                            "location.barrio",
                            "location.zona",
                            "seasonal.notif_lead_days",
                        ]
                    )
                )
            )
            .scalars()
            .all()
        )
        # The seeder stores settings as raw strings (not JSON-encoded);
        # that's the pre-existing convention from _seed_settingskv_branding.
        # Strip surrounding quotes only if the value happens to be a JSON
        # string. Otherwise keep the raw text.
        kv = {}
        for r in rows:
            v = r.value_json
            try:
                kv[r.key] = json.loads(v)
            except (json.JSONDecodeError, TypeError):
                kv[r.key] = v
    finally:
        s.close()

    # §8.1: WhatsApp del local para tomar pedidos
    assert kv.get("sales.shop_whatsapp") == "+595 991 683805"
    # §22.1: Barrio del local
    assert kv.get("location.barrio") == "San Lorenzo"
    # §22.2: Tipo de zona
    assert kv.get("location.zona") == "residencial"
    # §16.6: Días de anticipación para notificar picos
    assert kv.get("seasonal.notif_lead_days") == 30


def test_seed_sazon_registry_recipe_labor_defaults(tmp_path):
    """Recipe labor cost settings (SASKIA-215) come from the registry
    defaults (0 = disabled, 25000 Gs/h). Saskia §7.4 said sí; the
    seeder does NOT enforce a specific value (25000 Gs/h is the
    registry default — Saskia can change it via the admin UI).

    We use list_settings() (not raw KV lookup) because the registry
    default is returned when the row is absent. The seeder only writes
    keys for the answered questionnaire fields; the rest fall back to
    the registry defaults at read time.
    """
    pytest.importorskip("app.rms.seed")
    _, SessionLocal = _make_empty_db(tmp_path)

    from app.rms.seed import seed_sazon
    from app.rms.settings_registry import list_settings

    s = SessionLocal()
    try:
        seed_sazon(s, overwrite=False)
        s.commit()
    finally:
        s.close()

    s = SessionLocal()
    try:
        all_settings = list_settings(s)
        by_key = {entry["key"]: entry for entry in all_settings}
        # The keys MUST be present in the admin UI listing
        # (registry default fallback). Saskia §7.4 said yes to labor
        # cost but the seeder doesn't force a value — she sets it
        # in the UI.
        assert "recipe.labor_cost_enabled" in by_key
        assert by_key["recipe.labor_cost_enabled"]["value"] == 0
        assert "recipe.labor_cost_per_hour_gs" in by_key
        assert by_key["recipe.labor_cost_per_hour_gs"]["value"] == 25000
    finally:
        s.close()


def test_settings_registry_has_la_vaquita_keys():
    """The 6 new settings must be in the registry, with the right
    group, type, and default. This guards against the registry
    regressing (e.g. an accidental deletion in a future refactor).
    """
    from app.rms.settings_registry import SETTINGS, SettingGroup

    by_key = {s.key: s for s in SETTINGS}
    # LOCATION
    assert "location.barrio" in by_key
    assert by_key["location.barrio"].group == SettingGroup.LOCATION
    assert by_key["location.barrio"].default == ""
    assert "location.zona" in by_key
    assert by_key["location.zona"].group == SettingGroup.LOCATION
    assert by_key["location.zona"].default == "residencial"
    # SEASONAL
    assert "seasonal.notif_lead_days" in by_key
    assert by_key["seasonal.notif_lead_days"].group == SettingGroup.SEASONAL
    assert by_key["seasonal.notif_lead_days"].default == "30"
    # RECIPE
    assert "recipe.labor_cost_enabled" in by_key
    assert by_key["recipe.labor_cost_enabled"].group == SettingGroup.RECIPE
    assert by_key["recipe.labor_cost_enabled"].default == "0"
    assert "recipe.labor_cost_per_hour_gs" in by_key
    assert by_key["recipe.labor_cost_per_hour_gs"].group == SettingGroup.RECIPE
    assert by_key["recipe.labor_cost_per_hour_gs"].default == "25000"
    # SALES (new)
    assert "sales.shop_whatsapp" in by_key
    assert by_key["sales.shop_whatsapp"].group == SettingGroup.SALES
    assert by_key["sales.shop_whatsapp"].default == ""
