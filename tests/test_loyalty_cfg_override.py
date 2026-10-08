"""tests/test_loyalty_cfg_override.py — Batch B1 (2026-10-07).

Verifies that suggest_for_customer honors an operator-provided
loyalty_cfg dict, not just the module-level constants.

Each test customizes one knob and checks the resulting
Suggestion reflects the override. Defaults are tested separately
in tests/test_loyalty_suggestions.py (the original suite).
"""

from __future__ import annotations

import datetime as _dt


class _FakeCustomer:
    def __init__(
        self,
        *,
        birthday: str | None = None,
        loyalty_points: int = 0,
        dietary_restrictions: str | None = None,
    ) -> None:
        self.birthday = birthday
        self.loyalty_points = loyalty_points
        self.dietary_restrictions = dietary_restrictions


def _today() -> _dt.date:
    return _dt.date(2026, 10, 1)


def _base_cfg(**overrides):
    """Build a copy of DEFAULT_LOYALTY_CONFIG with overrides applied."""
    from app.rms.loyalty.suggestions import DEFAULT_LOYALTY_CONFIG

    cfg = dict(DEFAULT_LOYALTY_CONFIG)
    cfg.update(overrides)
    return cfg


def test_lapsed_threshold_override_changes_pct():
    """A gold customer 50 days out fires with cfg=lapsed_days_gold=14."""
    from app.rms.loyalty.suggestions import (
        KIND_VUELVE_PRONTO,
        suggest_for_customer,
    )

    today = _today()
    last = today - _dt.timedelta(days=50)
    cfg = _base_cfg(lapsed_days_gold=14, lapsed_discount_pct_gold=3)

    out = suggest_for_customer(
        _FakeCustomer(),
        last_sale_at=last,
        n_sales=20,
        tier="GOLD",
        redeemed_on_last_visit=True,
        today=today,
        loyalty_cfg=cfg,
    )
    lapsed = [s for s in out if s.kind == KIND_VUELVE_PRONTO]
    assert len(lapsed) == 1
    assert lapsed[0].discount_pct == 3


def test_lapsed_threshold_override_disables_for_short_absence():
    """If lapsed_days_silver=999, a 60-day absence won't fire LAPSED."""
    from app.rms.loyalty.suggestions import (
        KIND_VUELVE_PRONTO,
        suggest_for_customer,
    )

    today = _today()
    last = today - _dt.timedelta(days=60)
    cfg = _base_cfg(lapsed_days_silver=999)

    out = suggest_for_customer(
        _FakeCustomer(),
        last_sale_at=last,
        n_sales=10,
        tier="SILVER",
        redeemed_on_last_visit=True,
        today=today,
        loyalty_cfg=cfg,
    )
    assert KIND_VUELVE_PRONTO not in {s.kind for s in out}


def test_birthday_window_override_extends():
    """birthday_window_days=30 fires 20 days out (default would not)."""
    from app.rms.loyalty.suggestions import (
        KIND_CUMPLE_CERCA,
        suggest_for_customer,
    )

    today = _today()
    bday = today + _dt.timedelta(days=20)
    cfg = _base_cfg(birthday_window_days=30, birthday_discount_pct=5)

    out = suggest_for_customer(
        _FakeCustomer(birthday=bday.strftime("%Y-%m-%d")),
        last_sale_at=today - _dt.timedelta(days=2),
        n_sales=5,
        tier="BRONZE",
        redeemed_on_last_visit=False,
        today=today,
        loyalty_cfg=cfg,
    )
    cumple = [s for s in out if s.kind == KIND_CUMPLE_CERCA]
    assert len(cumple) == 1
    assert cumple[0].discount_pct == 5


def test_points_dormant_threshold_override():
    """points_dormant_threshold=200 with 100 points doesn't fire."""
    from app.rms.loyalty.suggestions import (
        KIND_PUNTOS_DORMIDOS,
        suggest_for_customer,
    )

    today = _today()
    cfg = _base_cfg(points_dormant_threshold=200)

    out = suggest_for_customer(
        _FakeCustomer(loyalty_points=100),
        last_sale_at=today - _dt.timedelta(days=2),
        n_sales=5,
        tier="BRONZE",
        redeemed_on_last_visit=False,
        today=today,
        loyalty_cfg=cfg,
    )
    assert KIND_PUNTOS_DORMIDOS not in {s.kind for s in out}


def test_max_suggestions_override_caps_output():
    """max_suggestions=1 with three firing rules returns only the top."""
    from app.rms.loyalty.suggestions import suggest_for_customer

    today = _today()
    bday = today + _dt.timedelta(days=3)
    last = today - _dt.timedelta(days=60)

    # Default would return up to 3 — LAPSED + POINTS-DORMANT + VIP.
    cfg = _base_cfg(max_suggestions=1)

    out = suggest_for_customer(
        _FakeCustomer(
            birthday=bday.strftime("%Y-%m-%d"),
            loyalty_points=100,
        ),
        last_sale_at=last,
        n_sales=20,
        tier="GOLD",
        redeemed_on_last_visit=False,
        today=today,
        loyalty_cfg=cfg,
    )
    assert len(out) == 1
    # BIRTHDAY has priority=10 (lowest wins), so it wins.
    assert out[0].kind == "cumple_cerca"


def test_default_cfg_when_none_uses_module_constants():
    """When loyalty_cfg=None, DEFAULT_LOYALTY_CONFIG is used implicitly."""
    from app.rms.loyalty.suggestions import (
        DEFAULT_LOYALTY_CONFIG,
        KIND_CUMPLE_CERCA,
        suggest_for_customer,
    )

    today = _today()
    bday = today + _dt.timedelta(days=3)

    out = suggest_for_customer(
        _FakeCustomer(birthday=bday.strftime("%Y-%m-%d")),
        last_sale_at=today - _dt.timedelta(days=2),
        n_sales=5,
        tier="BRONZE",
        redeemed_on_last_visit=False,
        today=today,
        loyalty_cfg=None,
    )
    cumple = [s for s in out if s.kind == KIND_CUMPLE_CERCA]
    assert len(cumple) == 1
    assert cumple[0].discount_pct == DEFAULT_LOYALTY_CONFIG["birthday_discount_pct"]
    assert len(out) <= DEFAULT_LOYALTY_CONFIG["max_suggestions"]


def test_partial_cfg_uses_overrides_plus_defaults():
    """A cfg with only one key set falls back to defaults for the rest."""
    from app.rms.loyalty.suggestions import (
        DEFAULT_LOYALTY_CONFIG,
        KIND_VUELVE_PRONTO,
        suggest_for_customer,
    )

    today = _today()
    last = today - _dt.timedelta(days=22)
    # Only override the bronze pct; everything else uses defaults.
    cfg = {"lapsed_discount_pct_bronze": 25}

    out = suggest_for_customer(
        _FakeCustomer(),
        last_sale_at=last,
        n_sales=5,
        tier="BRONZE",
        redeemed_on_last_visit=True,
        today=today,
        loyalty_cfg=cfg,
    )
    lapsed = [s for s in out if s.kind == KIND_VUELVE_PRONTO]
    assert len(lapsed) == 1
    assert lapsed[0].discount_pct == 25
    # And default lapsed_days_bronze=21 still applies (22 > 21 → yes fire).
    assert lapsed[0].discount_pct != DEFAULT_LOYALTY_CONFIG["lapsed_discount_pct_bronze"]


def test_get_loyalty_config_returns_dict_with_all_keys():
    """get_loyalty_config(session) returns a complete dict."""
    # Fake session — get_loyalty_config only calls get_setting_value
    # which calls session.execute(). For the pure-Python test of the
    # default-coercion path, monkeypatch get_setting_value.
    import app.rms.settings_registry as settings_mod
    from app.rms.settings_runtime import (
        DEFAULT_LOYALTY_CONFIG,
        get_loyalty_config,
    )

    def fake_get_setting_value(session, key):
        # Return None for all keys → caller falls back to defaults.
        return None

    orig = settings_mod.get_setting_value
    settings_mod.get_setting_value = fake_get_setting_value
    try:
        out = get_loyalty_config(session=None)
    finally:
        settings_mod.get_setting_value = orig

    assert out == DEFAULT_LOYALTY_CONFIG


def test_get_loyalty_config_coerces_stored_value():
    """Stored value '5' is coerced to int 5."""
    import app.rms.settings_registry as settings_mod
    from app.rms.settings_runtime import get_loyalty_config

    def fake_get_setting_value(session, key):
        if key == "loyalty.birthday_discount_pct":
            return "5"
        return None

    orig = settings_mod.get_setting_value
    settings_mod.get_setting_value = fake_get_setting_value
    try:
        out = get_loyalty_config(session=None)
    finally:
        settings_mod.get_setting_value = orig

    assert out["birthday_discount_pct"] == 5
    assert isinstance(out["birthday_discount_pct"], int)
