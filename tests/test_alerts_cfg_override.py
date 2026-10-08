"""tests/test_alerts_cfg_override.py — Batch B3 (2026-10-07).

Verifies the operator-tunable alert rate limit. ``dispatch_anomalies``
accepts an optional ``max_per_day`` kwarg that overrides the
DEFAULT_ALERTS_CONFIG default.
"""

from __future__ import annotations

from unittest.mock import patch as umock_patch

from app.observability import alerts
from app.services.eod_anomaly import Anomaly


def _anomaly(idx: int) -> Anomaly:
    return Anomaly(
        key=f"eod.k{idx}",
        severity="warn",
        title=f"t{idx}",
        body=f"b{idx}",
    )


def test_dispatch_anomalies_default_cap_unchanged():
    """When max_per_day is not passed, DEFAULT_ALERTS_CONFIG["max_per_day"] is used."""
    items = [_anomaly(i) for i in range(alerts.DEFAULT_ALERTS_CONFIG["max_per_day"] + 5)]

    with umock_patch("app.observability.alerts.send_alert", return_value=True) as m:
        n = alerts.dispatch_anomalies(items)
    assert n == alerts.DEFAULT_ALERTS_CONFIG["max_per_day"]
    assert m.call_count == alerts.DEFAULT_ALERTS_CONFIG["max_per_day"]


def test_dispatch_anomalies_override_lowers_cap():
    """Override cap of 5 stops dispatching after 5 items."""
    items = [_anomaly(i) for i in range(20)]

    with umock_patch("app.observability.alerts.send_alert", return_value=True) as m:
        n = alerts.dispatch_anomalies(items, max_per_day=5)
    assert n == 5
    assert m.call_count == 5


def test_dispatch_anomalies_override_raises_cap():
    """Override cap of 100 dispatches all 20 items (no cap hit)."""
    items = [_anomaly(i) for i in range(20)]

    with umock_patch("app.observability.alerts.send_alert", return_value=True) as m:
        n = alerts.dispatch_anomalies(items, max_per_day=100)
    assert n == 20
    assert m.call_count == 20


def test_max_alerts_per_day_constant_matches_default():
    """MAX_ALERTS_PER_DAY still equals DEFAULT_ALERTS_CONFIG["max_per_day"]
    (backward-compat for scripts/tests that import the old name).
    """
    assert alerts.MAX_ALERTS_PER_DAY == alerts.DEFAULT_ALERTS_CONFIG["max_per_day"]


def test_get_alerts_config_returns_dict_with_all_keys():
    """get_alerts_config(session) returns a complete dict."""
    import app.rms.settings_registry as settings_mod
    from app.rms.settings_runtime import (
        DEFAULT_ALERTS_CONFIG,
        get_alerts_config,
    )

    orig = settings_mod.get_setting_value
    settings_mod.get_setting_value = lambda session, key: None
    try:
        out = get_alerts_config(session=None)
    finally:
        settings_mod.get_setting_value = orig

    assert out == DEFAULT_ALERTS_CONFIG
    assert isinstance(out["max_per_day"], int)


def test_get_alerts_config_coerces_stored_value():
    """Stored '100' is coerced to int 100."""
    import app.rms.settings_registry as settings_mod
    from app.rms.settings_runtime import get_alerts_config

    def fake(session, key):
        if key == "alerts.max_per_day":
            return "100"
        return None

    orig = settings_mod.get_setting_value
    settings_mod.get_setting_value = fake
    try:
        out = get_alerts_config(session=None)
    finally:
        settings_mod.get_setting_value = orig

    assert out["max_per_day"] == 100
    assert isinstance(out["max_per_day"], int)
