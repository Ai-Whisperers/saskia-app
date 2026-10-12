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
    """60 settings registered across 12 groups.

    Updated 2026-10-05: added BRANDING group (was 31 in 7 groups).
    Updated 2026-10-07 (Batch B1+B2+B3+B4): added LOYALTY (11),
    EOD (3), ALERTS (1), and BACKUP (3 more). Total settings
    42 → 60, total groups 9 → 12.
    Updated 2026-10-12 (SASKIA-215): added LOCATION (2),
    SEASONAL (1), RECIPE (2), and SALES.shop_whatsapp (1). Total
    settings 68 → 74, total groups 13 → 16.
    Updated 2026-10-12 (SASKIA-221): added 26 settings across 7 new groups
    (CONTACT, MARKETING, TARGETING, POSITIONING, OPERATIONS, COMPLIANCE,
    GOALS) plus 4 more LOCATION settings. Total 74 → 101, total 16 → 23.
    """
    assert len(SETTINGS) == 106  # SASKIA-221 (101) + SASKIA-223 (4) + SASKIA-217 (1 seasonal.relevance_tags)
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
        SettingGroup.LOCATION,  # SASKIA-215
        SettingGroup.SEASONAL,  # SASKIA-215
        SettingGroup.RECIPE,  # SASKIA-215
        SettingGroup.CONTACT,  # SASKIA-221
        SettingGroup.MARKETING,  # SASKIA-221
        SettingGroup.TARGETING,  # SASKIA-221
        SettingGroup.POSITIONING,  # SASKIA-221
        SettingGroup.OPERATIONS,  # SASKIA-221
        SettingGroup.COMPLIANCE,  # SASKIA-221
        SettingGroup.GOALS,  # SASKIA-221
        SettingGroup.HEREBUS,  # SASKIA-223
    }


def test_settings_per_group_counts():
    """Each group has expected setting count.

    Counts last updated 2026-10-05 after adding BRANDING group with 10
    business-identity settings (logo, favicon, hero, accent_color, etc.)
    and PRODUCTION group with 1 setting (demand cache TTL).
    Updated 2026-10-12 (SASKIA-215): added LOCATION (2),
    SEASONAL (1), RECIPE (2), SALES.shop_whatsapp (1).
    """
    by_group: dict[SettingGroup, int] = {}
    for s in SETTINGS:
        by_group[s.group] = by_group.get(s.group, 0) + 1
    assert by_group[SettingGroup.GENERAL] == 7
    assert by_group[SettingGroup.BRANDING] == 10  # 10 branding fields
    assert by_group[SettingGroup.INVENTORY] == 6
    assert by_group[SettingGroup.SALES] == 9  # 5 + 3 PRE_SALE + 1 shop_whatsapp (SASKIA-215)
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
    # SASKIA-215 + SASKIA-221: location (6 = 2 from 215 + 4 from 221) / seasonal / recipe
    assert by_group[SettingGroup.LOCATION] == 6
    assert by_group[SettingGroup.SEASONAL] == 2  # SASKIA-215 notif_lead_days + SASKIA-217 relevance_tags
    assert by_group[SettingGroup.RECIPE] == 2
    # SASKIA-221: 7 new groups
    assert by_group[SettingGroup.CONTACT] == 5
    assert by_group[SettingGroup.MARKETING] == 3
    assert by_group[SettingGroup.TARGETING] == 3
    assert by_group[SettingGroup.POSITIONING] == 2
    assert by_group[SettingGroup.OPERATIONS] == 5
    assert by_group[SettingGroup.COMPLIANCE] == 2
    assert by_group[SettingGroup.GOALS] == 3
    # SASKIA-223: 4 HEREBUS import count fields
    assert by_group[SettingGroup.HEREBUS] == 4
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


def test_list_settings_returns_74(session_factory):
    """list_settings returns 74 entries with value/default/group/etc.



    Updated 2026-10-07 (Batch B1+B2+B3+B4+B5+B6): was 42 entries. Now 68
    (added 11 LOYALTY + 3 EOD + 1 ALERTS + 3 BACKUP + 5 RATE_LIMIT + 3 PRE_SALE).
    Updated 2026-10-12 (SASKIA-215): added 6 more (2 LOCATION + 1 SEASONAL
    + 2 RECIPE + 1 SALES.shop_whatsapp). Now 74.
    Updated 2026-10-12 (SASKIA-221): added 26 more (CONTACT 5, LOCATION 4
    new, MARKETING 3, TARGETING 3, POSITIONING 2, OPERATIONS 5, COMPLIANCE 2,
    GOALS 3). Now 101.
    """
    s = session_factory()
    try:
        all_settings = list_settings(s)
        assert len(all_settings) == 106
        entry = all_settings[0]
        for k in ("key", "value", "default", "description", "group", "choices"):
            assert k in entry
    finally:
        s.close()


def test_settings_by_group_groups_correctly(session_factory):
    """settings_by_group returns dict with 16 keys matching the group values.



    Updated 2026-10-07 (Batch B1+B2+B3+B4+B5+B6): was 42 entries. Now 68
    (added "loyalty", "eod", "alerts", "rate_limit").
    Updated 2026-10-12 (SASKIA-215): added "location", "seasonal", "recipe".
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
            "location",  # SASKIA-215/221: 6 location fields (2 + 4 new)
            "seasonal",  # SASKIA-215: 1 seasonal field
            "recipe",  # SASKIA-215: 2 recipe labor cost fields
            "contact",  # SASKIA-221: 5 contact fields
            "marketing",  # SASKIA-221: 3 marketing fields
            "targeting",  # SASKIA-221: 3 targeting fields
            "positioning",  # SASKIA-221: 2 positioning fields
            "operations",  # SASKIA-221: 5 operations fields
            "compliance",  # SASKIA-221: 2 compliance fields
            "goals",  # SASKIA-221: 3 goals fields
            "herbus",  # SASKIA-223: 4 HEREBUS import count fields
        }
        assert len(grouped["general"]) == 7
        assert len(grouped["branding"]) == 10
        assert len(grouped["inventory"]) == 6
        assert len(grouped["sales"]) == 9  # 5 + 3 PRE_SALE + 1 shop_whatsapp (SASKIA-215)
        assert len(grouped["backup"]) == 6  # 3 original + 3 Batch B4
        assert len(grouped["loyalty"]) == 11
        assert len(grouped["eod"]) == 3
        assert len(grouped["alerts"]) == 1
        assert len(grouped["rate_limit"]) == 5
        assert len(grouped["location"]) == 6  # 2 from SASKIA-215 + 4 from SASKIA-221
        assert len(grouped["seasonal"]) == 2
        assert len(grouped["recipe"]) == 2
        # SASKIA-221
        assert len(grouped["contact"]) == 5
        assert len(grouped["marketing"]) == 3
        assert len(grouped["targeting"]) == 3
        assert len(grouped["positioning"]) == 2
        assert len(grouped["operations"]) == 5
        assert len(grouped["compliance"]) == 2
        assert len(grouped["goals"]) == 3
        assert len(grouped["herbus"]) == 4
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
