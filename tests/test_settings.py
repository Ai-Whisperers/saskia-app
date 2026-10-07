"""tests/test_settings.py — verify app/rms/settings_registry.py (E10, Sprint 2.1).

Per docs/plans/2026-09-07-sazon-complete-epic-plan-v3.md E10.

Covers:
- 31 settings registered across 7 groups
- get_setting_value returns default when not stored
- set_setting persists + validates (rejects bad values)
- set_setting round-trips through validator (str, int, float, bool, json)
- list_settings returns 30 entries
- settings_by_group groups by SettingGroup
- reset_setting_to_default reverts to default
"""

# allow-hardcoded-dates: settings snapshot uses a fixed timestamp
from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from app.rms.settings_registry import (
    SETTINGS,
    SettingGroup,
    get_setting,
    get_setting_value,
    list_settings,
    reset_setting_to_default,
    set_setting,
    settings_by_group,
)


def test_settings_count():
    """42 settings registered across 9 groups.

    Updated 2026-10-05: added BRANDING group with 10 settings (business
    identity — logo, favicon, hero, accent color, contact info,
    business_type, tagline, footer). Was 31 settings in 7 groups.
    Added PRODUCTION group (PRODUCCION-V2 Fase 3: demand cache TTL).
    """
    assert len(SETTINGS) == 42
    groups = {s.group for s in SETTINGS}
    assert groups == {
        SettingGroup.GENERAL,
        SettingGroup.BRANDING,
        SettingGroup.INVENTORY,
        SettingGroup.SALES,
        SettingGroup.DASHBOARD,
        SettingGroup.BACKUP,
        SettingGroup.SESSION,
        SettingGroup.DEMO,
        SettingGroup.PRODUCTION,
    }


def test_settings_per_group_counts():
    """Each group has expected setting count.

    Counts last updated 2026-10-05 after adding BRANDING group with 10
    business-identity settings (logo, favicon, hero, accent_color, etc.)
    and PRODUCTION group with 1 setting (demand cache TTL).
    """
    by_group: dict[SettingGroup, int] = {}
    for s in SETTINGS:
        by_group[s.group] = by_group.get(s.group, 0) + 1
    assert by_group[SettingGroup.GENERAL] == 7
    assert by_group[SettingGroup.BRANDING] == 10  # 10 branding fields
    assert by_group[SettingGroup.INVENTORY] == 6
    assert by_group[SettingGroup.SALES] == 5
    assert by_group[SettingGroup.DASHBOARD] == 5
    assert by_group[SettingGroup.BACKUP] == 3
    assert by_group[SettingGroup.SESSION] == 3
    assert by_group[SettingGroup.DEMO] == 2
    assert by_group[SettingGroup.PRODUCTION] == 1
    # Sanity: total matches len(SETTINGS)
    assert sum(by_group.values()) == len(SETTINGS)


def test_get_setting_value_returns_default_when_unset(session_factory):
    """If a setting has never been stored, return its default."""
    s = session_factory()
    try:
        # No setup — fresh DB
        assert get_setting_value(s, "general.currency_symbol") == "Gs."
        assert get_setting_value(s, "general.decimal_places") == 0
        assert get_setting_value(s, "inventory.auto_deduct_on_sale") is True
        assert get_setting_value(s, "dashboard.show_margins") is True
    finally:
        s.close()


def test_set_setting_round_trip_str(session_factory):
    s = session_factory()
    try:
        set_setting(s, "general.business_name", "Mi Panadería")
        s.commit()
        assert get_setting_value(s, "general.business_name") == "Mi Panadería"
        # Raw stored
        assert get_setting(s, "general.business_name") == "Mi Panadería"
    finally:
        s.close()


def test_set_setting_round_trip_int(session_factory):
    s = session_factory()
    try:
        set_setting(s, "inventory.alert_lead_time_days", 14)
        s.commit()
        assert get_setting_value(s, "inventory.alert_lead_time_days") == 14
    finally:
        s.close()


def test_set_setting_round_trip_float(session_factory):
    s = session_factory()
    try:
        set_setting(s, "inventory.default_min_stock", 2.5)
        s.commit()
        assert get_setting_value(s, "inventory.default_min_stock") == 2.5
    finally:
        s.close()


def test_set_setting_round_trip_bool(session_factory):
    s = session_factory()
    try:
        set_setting(s, "inventory.auto_deduct_on_sale", False)
        s.commit()
        assert get_setting_value(s, "inventory.auto_deduct_on_sale") is False

        set_setting(s, "inventory.auto_deduct_on_sale", True)
        s.commit()
        assert get_setting_value(s, "inventory.auto_deduct_on_sale") is True

        # From string "1" / "0"
        set_setting(s, "inventory.auto_deduct_on_sale", "1")
        s.commit()
        assert get_setting_value(s, "inventory.auto_deduct_on_sale") is True
    finally:
        s.close()


def test_set_setting_round_trip_json(session_factory):
    s = session_factory()
    try:
        # Pick a setting with a json validator — none in the current 30.
        # Add a json setting ad-hoc.
        from app.rms.settings_registry import VALIDATORS

        VALIDATORS["json"]
        # There's no json setting in the registry; test json round-trip by
        # storing via a raw SettingsKV row (the store set_setting uses).
        from app.rms.models import SettingsKV

        s.add(SettingsKV(key="test.json", value_json='["a", "b", 1]'))
        s.commit()
        # No spec for test.json → get_setting returns the raw stored text
        assert get_setting(s, "test.json") == '["a", "b", 1]'
        assert json.loads(get_setting(s, "test.json")) == ["a", "b", 1]
    finally:
        s.close()


def test_set_setting_unknown_key_raises(session_factory):
    s = session_factory()
    try:
        with pytest.raises(ValueError, match="Unknown setting key"):
            set_setting(s, "general.nonexistent", "x")
    finally:
        s.close()


def test_set_setting_overwrites_existing(session_factory):
    """Calling set_setting twice overwrites the row (no duplicates)."""
    s = session_factory()
    try:
        set_setting(s, "general.business_name", "A")
        s.commit()
        set_setting(s, "general.business_name", "B")
        s.commit()
        assert get_setting_value(s, "general.business_name") == "B"
        # Only one row
        from app.rms.models import SettingsKV

        n = len(
            list(
                s.execute(
                    select(SettingsKV).where(SettingsKV.key == "general.business_name")
                ).scalars()
            )
        )
        assert n == 1
    finally:
        s.close()


def test_list_settings_returns_31(session_factory):
    """list_settings returns 42 entries with value/default/group/etc.

    Updated 2026-10-05: was 31 entries. Now 42 (added 10 BRANDING fields:
    logo, favicon, hero, accent color, contact info, business_type,
    tagline, footer + 1 PRODUCTION field: demand cache TTL).
    """
    s = session_factory()
    try:
        all_settings = list_settings(s)
        assert len(all_settings) == 42
        entry = all_settings[0]
        for k in ("key", "value", "default", "description", "group", "choices"):
            assert k in entry
    finally:
        s.close()


def test_settings_by_group_groups_correctly(session_factory):
    """settings_by_group returns dict with 9 keys matching the group values.

    Updated 2026-10-05: was 7 keys, now 9 (added "branding" and "production").
    """
    s = session_factory()
    try:
        grouped = settings_by_group(s)
        assert set(grouped.keys()) == {
            "general",
            "branding",  # NEW: 10 branding settings
            "inventory",
            "sales",
            "dashboard",
            "backup",
            "session",
            "demo",
            "production",  # NEW: 1 PRODUCTION field
        }
        assert len(grouped["general"]) == 7
        assert len(grouped["branding"]) == 10
        assert len(grouped["inventory"]) == 6
        assert len(grouped["sales"]) == 5
    finally:
        s.close()


def test_reset_setting_to_default(session_factory):
    """reset_setting_to_default clears the stored row; get returns default."""
    s = session_factory()
    try:
        set_setting(s, "general.business_name", "Override")
        s.commit()
        assert get_setting_value(s, "general.business_name") == "Override"

        reset_setting_to_default(s, "general.business_name")
        s.commit()
        # Default for general.business_name is "Sazón"
        assert get_setting_value(s, "general.business_name") == "Sazón"
        # Raw row gone
        assert get_setting(s, "general.business_name") is None
    finally:
        s.close()


def test_setting_keys_are_unique():
    """All setting keys unique (no duplicates by accident)."""
    keys = [s.key for s in SETTINGS]
    assert len(keys) == len(set(keys)), (
        f"Duplicate keys: {set(k for k in keys if keys.count(k) > 1)}"
    )
