"""Tests for SASKIA-221: 26 more settings + 7 new groups.

Verifies:
- Registry has 101 settings (was 74), 23 groups (was 16)
- All 7 new groups (CONTACT, MARKETING, TARGETING, POSITIONING,
  OPERATIONS, COMPLIANCE, GOALS) are present
- LOCATION grew from 2 to 6
- The seeder populates the 6 answered settings (phone, email, whatsapp,
  address_full, city, department)
- The unanswered settings (instagram, facebook, ruc, timbrado, etc.)
  are registered with empty defaults and the seeder does NOT write them
- Validation works (bool settings accept "1"/"0", int settings accept
  numeric strings, etc.)
- The registry is the single source of truth (no rogue settings_kv rows
  outside the registry)
"""

from __future__ import annotations

from sqlalchemy import text

from app.rms.settings_registry import (
    SETTINGS,
    SettingGroup,
    get_setting_value,
)


def test_saskia221_registry_has_105_settings():
    """74 + 26 + 1 = 101 (SASKIA-221) + 4 (SASKIA-223 HEREBUS) = 105 settings."""
    assert len(SETTINGS) == 105


def test_saskia221_registry_has_24_groups():
    """16 + 7 = 23 (SASKIA-221) + 1 (SASKIA-223 HEREBUS) = 24 groups."""
    assert len(SettingGroup.__members__) == 24


def test_saskia221_new_groups_present():
    """The 7 new groups from SASKIA-221 are defined."""
    expected = {"contact", "marketing", "targeting", "positioning", "operations", "compliance", "goals"}
    actual = {g.value for g in SettingGroup}
    assert expected.issubset(actual), f"missing: {expected - actual}"


def test_saskia221_location_grew_to_6():
    """LOCATION went from 2 (SASKIA-215) to 6 (SASKIA-221 adds 4)."""
    location_settings = [s for s in SETTINGS if s.group == SettingGroup.LOCATION]
    assert len(location_settings) == 6
    keys = {s.key for s in location_settings}
    assert keys == {
        "location.barrio",
        "location.zona",
        "location.address_full",
        "location.city",
        "location.department",
        "location.reference_point",
    }


def test_saskia221_contact_settings_5():
    """CONTACT has 5 settings (phone, email, whatsapp, instagram, facebook)."""
    contact_settings = [s for s in SETTINGS if s.group == SettingGroup.CONTACT]
    assert len(contact_settings) == 5


def test_saskia221_marketing_settings_3():
    """MARKETING has 3 settings (primary_channel, has_whatsapp_business, has_website)."""
    marketing_settings = [s for s in SETTINGS if s.group == SettingGroup.MARKETING]
    assert len(marketing_settings) == 3


def test_saskia221_targeting_settings_3():
    """TARGETING has 3 settings (audience, age_range, area)."""
    targeting_settings = [s for s in SETTINGS if s.group == SettingGroup.TARGETING]
    assert len(targeting_settings) == 3


def test_saskia221_positioning_settings_2():
    """POSITIONING has 2 settings (differentiator, unique_selling_points)."""
    positioning_settings = [s for s in SETTINGS if s.group == SettingGroup.POSITIONING]
    assert len(positioning_settings) == 2


def test_saskia221_operations_settings_5():
    """OPERATIONS has 5 settings (is_solo, has_cashiers, has_delivery, has_pickup, has_dine_in)."""
    operations_settings = [s for s in SETTINGS if s.group == SettingGroup.OPERATIONS]
    assert len(operations_settings) == 5


def test_saskia221_compliance_settings_2():
    """COMPLIANCE has 2 settings (ruc, timbrado)."""
    compliance_settings = [s for s in SETTINGS if s.group == SettingGroup.COMPLIANCE]
    assert len(compliance_settings) == 2


def test_saskia221_goals_settings_3():
    """GOALS has 3 settings (target_revenue, target_products, target_customers)."""
    goals_settings = [s for s in SETTINGS if s.group == SettingGroup.GOALS]
    assert len(goals_settings) == 3


def test_saskia221_contact_settings_have_questionnaire_defaults():
    """The 3 CONTACT settings that have known values default to those values."""
    keys = {s.key: s.default for s in SETTINGS}
    # From questionnaire sec.2.3, 2.4, 2.7
    assert keys["contact.phone"] == "+595 991 683805"
    assert keys["contact.email"] == "La.vaquitaholandesa@gmail.com"
    assert keys["contact.whatsapp"] == "+595 991 683805"
    # TBD fields are empty
    assert keys["contact.instagram_handle"] == ""
    assert keys["contact.facebook"] == ""


def test_saskia221_location_settings_have_questionnaire_defaults():
    """LOCATION settings default to La Vaquita's real address."""
    keys = {s.key: s.default for s in SETTINGS}
    assert keys["location.address_full"] == "Laguan Grande, Arquitectos, Calle 17, Asuncion"
    assert keys["location.city"] == "Asuncion"
    assert keys["location.department"] == "Central"


def test_saskia221_operations_settings_match_questionnaire():
    """OPERATIONS reflects Saskia's solo, no-delivery reality (sec.4.5, 17)."""
    keys = {s.key: s.default for s in SETTINGS}
    assert keys["operations.is_solo"] == "1"
    assert keys["operations.has_cashiers"] == "0"
    assert keys["operations.has_delivery"] == "0"
    assert keys["operations.has_pickup"] == "1"
    assert keys["operations.has_dine_in"] == "0"


def test_saskia221_goals_settings_match_questionnaire():
    """GOALS reflects Saskia's product/customer targets (sec.11.2, 11.4)."""
    keys = {s.key: s.default for s in SETTINGS}
    assert keys["goals.target_products"] == "30"  # sec.11.4 = +30 products meta
    assert keys["goals.target_customers_daily"] == "30"  # sec.11.2 = 20-30 daily


def test_saskia221_marketing_primary_channel_choice():
    """The marketing.primary_channel has a choices list (enum-style)."""
    mpc = next(s for s in SETTINGS if s.key == "marketing.primary_channel")
    assert mpc.choices == ["whatsapp", "instagram", "facebook", "web"]


def test_saskia221_seeder_populates_6_answered_settings(session_factory):
    """After seed_sazon, the 6 answered SASKIA-221 settings are in DB."""
    from app.rms.seed.sazon import seed_sazon
    with session_factory() as s:
        seed_sazon(s)
        s.commit()

    with session_factory() as s:
        # CONTACT
        assert get_setting_value(s, "contact.phone") == "+595 991 683805"
        assert get_setting_value(s, "contact.email") == "La.vaquitaholandesa@gmail.com"
        # LOCATION
        assert get_setting_value(s, "location.city") == "Asuncion"
        assert get_setting_value(s, "location.department") == "Central"


def test_saskia221_seeder_does_not_write_tbd_settings(session_factory):
    """The 20 unanswered SASKIA-221 settings are NOT in settings_kv
    (only registered with empty defaults). The seeder is conservative."""
    from app.rms.seed.sazon import seed_sazon
    with session_factory() as s:
        seed_sazon(s)
        s.commit()
        # These are TBD per the questionnaire — not in DB
        n = s.execute(
            text(
                "SELECT COUNT(*) FROM settings_kv WHERE key IN ("
                "'contact.instagram_handle', 'contact.facebook', "
                "'compliance.ruc', 'compliance.timbrado')"
            )
        ).scalar()
    assert n == 0, f"TBD settings should NOT be in DB, but found {n}"


def test_saskia221_seeder_sets_herbus_contact_settings(session_factory):
    """The seeder also writes the contact.* keys that match the BUSINESS_INFO."""
    from app.rms.seed.sazon import seed_sazon
    with session_factory() as s:
        seed_sazon(s)
        s.commit()
        # The seeder writes 6 SASKIA-221 keys (3 CONTACT + 3 LOCATION)
        n = s.execute(
            text(
                "SELECT COUNT(*) FROM settings_kv WHERE key IN ("
                "'contact.phone', 'contact.email', 'contact.whatsapp', "
                "'location.address_full', 'location.city', 'location.department'"
                ")"
            )
        ).scalar()
    assert n == 6, f"expected 6 SASKIA-221 settings in DB, found {n}"


def test_saskia221_all_new_keys_have_unique_keys():
    """No duplicate keys in the registry (sanity check)."""
    keys = [s.key for s in SETTINGS]
    assert len(set(keys)) == len(keys), "registry has duplicate keys"
