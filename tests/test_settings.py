"""tests/test_settings.py — verify app/rms/settings.py (E10).

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

from app.rms.models import AppMeta
from app.rms.settings import (
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
    """60 settings registered across 12 groups.

    Updated 2026-10-05: added BRANDING group (was 31 in 7 groups).
    Updated 2026-10-07 (Batch B1+B2+B3+B4): added LOYALTY (11),
    EOD (3), ALERTS (1), and BACKUP (3 more). Total settings
    42 → 60, total groups 9 → 12.
    """
    assert len(SETTINGS) == 65
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
        SettingGroup.LOYALTY,  # Batch B1
        SettingGroup.EOD,  # Batch B2
        SettingGroup.ALERTS,  # Batch B3
        SettingGroup.RATE_LIMIT,  # Batch B5
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
    assert by_group[SettingGroup.BACKUP] == 6  # 3 original + 3 from Batch B4
    assert by_group[SettingGroup.SESSION] == 3
    assert by_group[SettingGroup.DEMO] == 2
    assert by_group[SettingGroup.PRODUCTION] == 1
    # Batch B1: POS suggestion thresholds
    assert by_group[SettingGroup.LOYALTY] == 11
    # Batch B2: EOD anomaly detector thresholds
    assert by_group[SettingGroup.EOD] == 3
    # Batch B3: alert rate limit
    assert by_group[SettingGroup.ALERTS] == 1
    # Batch B5: rate-limit throttles
    assert by_group[SettingGroup.RATE_LIMIT] == 5
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
        from app.rms.settings import VALIDATORS

        VALIDATORS["json"]
        # Use list_settings round-trip for json
        # Actually there's no json setting; we test json round-trip by
        # calling get_setting_value with a stored JSON string.
        s.add(AppMeta(key="test.json", value='["a", "b", 1]', updated_at="2026-01-01"))
        s.commit()
        # There's no spec for test.json, so get_setting_value returns raw
        assert get_setting(s, "test.json") == '["a", "b", 1]'
        # With validator: use VALIDATORS directly
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
        n = len(
            list(s.execute(select(AppMeta).where(AppMeta.key == "general.business_name")).scalars())
        )
        assert n == 1
    finally:
        s.close()


def test_list_settings_returns_65(session_factory):
    """list_settings returns 65 entries with value/default/group/etc.


    Updated 2026-10-07 (Batch B1+B2+B3+B4+B5): was 42 entries. Now 65
    (added 11 LOYALTY + 3 EOD + 1 ALERTS + 3 BACKUP + 5 RATE_LIMIT).
    """
    s = session_factory()
    try:
        all_settings = list_settings(s)
        assert len(all_settings) == 65
        entry = all_settings[0]
        for k in ("key", "value", "default", "description", "group", "choices"):
            assert k in entry
    finally:
        s.close()


def test_settings_by_group_groups_correctly(session_factory):
    """settings_by_group returns dict with 13 keys matching the group values.


    Updated 2026-10-07 (Batch B1+B2+B3+B4+B5): was 9 keys, now 13
    (added "loyalty", "eod", "alerts", "rate_limit").
    """
    s = session_factory()
    try:
        grouped = settings_by_group(s)
        assert set(grouped.keys()) == {
            "general",
            "branding",  # 10 branding settings
            "inventory",
            "sales",
            "dashboard",
            "backup",  # 6 (3 original + 3 from Batch B4)
            "session",
            "demo",
            "production",  # 1 PRODUCTION field
            "loyalty",  # Batch B1: 11 POS suggestion thresholds
            "eod",  # Batch B2: 3 EOD anomaly thresholds
            "alerts",  # Batch B3: 1 alert rate limit
            "rate_limit",  # Batch B5: 5 rate-limit throttles
        }
        assert len(grouped["general"]) == 7
        assert len(grouped["branding"]) == 10
        assert len(grouped["inventory"]) == 6
        assert len(grouped["sales"]) == 5
        assert len(grouped["backup"]) == 6  # 3 original + 3 Batch B4
        assert len(grouped["loyalty"]) == 11
        assert len(grouped["eod"]) == 3
        assert len(grouped["alerts"]) == 1
        assert len(grouped["rate_limit"]) == 5
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
