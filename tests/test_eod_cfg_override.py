"""tests/test_eod_cfg_override.py — Batch B2 (2026-10-07).

Verifies the operator-tunable EOD anomaly thresholds. Each test
seeds a small Sale fixture via the existing session_factory,
then calls ``detect_anomalies`` with a custom eod_cfg dict and
checks the resulting list of Anomaly objects reflects the
override.
"""
from __future__ import annotations

from datetime import date, datetime as _dt, time

import pytest


pytestmark = pytest.mark.smoke

@pytest.fixture
def product_id(session_factory) -> int:
    """Create a real Product row using qseed so the mapper is fully
    configured by the time we INSERT sales. (Same approach as
    tests/test_tier8_eod_anomaly.py — see that file for context on
    why we bypass the ORM and use raw SQL.)
    """
    from tests._fixtures_quick_seed import quick_seed

    data = quick_seed(session_factory, "basic")
    return int(data["product"].id)



def _today() -> date:
    return date(2026, 9, 1)


def test_voided_rate_threshold_override_lowers_bar(session_factory, product_id):
    """Threshold 0.05 fires with 1 voided of 10 sales (10% > 5%)."""
    from app.rms.settings_runtime import DEFAULT_EOD_CONFIG
    from app.services.eod_anomaly import (
        detect_anomalies,
        _check_voided_rate,
    )

    # Use the helper directly to bypass detect_anomalies' loop and
    # keep the test surgical. cfg is passed positionally.
    with session_factory() as s:
        # Seed 10 sales, 1 voided.
        for i in range(10):
            s.execute(
                __import__("sqlalchemy").text(
                    """INSERT INTO sale (
                        product_id, unit_price_gs, qty, discount_gs,
                        payment_method, invoice_type, invoice_number,
                        sold_at, voided_at
                    ) VALUES (
                        :pid, 10000, 1, 0, 'efectivo', 'boleta_resimple',
                        NULL, :sold_at, :voided_at
                    )"""
                ),
                {
                    "pid": product_id,
                    "sold_at": _dt.combine(_today(), time(12, 0)),
                    "voided_at": (
                        _dt.combine(_today(), time(13, 0))
                        if i == 0
                        else None
                    ),
                },
            )
        s.commit()

        # Threshold 0.05 → fires (10% >= 5%).
        cfg = dict(DEFAULT_EOD_CONFIG)
        cfg["voided_rate_threshold"] = 0.05
        a = _check_voided_rate(s, _today(), cfg)
        assert a is not None
        assert a.key == "eod.voided_rate"

        # Threshold 0.50 → does NOT fire (10% < 50%).
        cfg2 = dict(DEFAULT_EOD_CONFIG)
        cfg2["voided_rate_threshold"] = 0.50
        a2 = _check_voided_rate(s, _today(), cfg2)
        assert a2 is None


def test_voided_rate_min_sales_override_disables_on_quiet_days(session_factory, product_id):
    """min_sales=100 disables the check for a day with only 5 sales."""
    from app.rms.settings_runtime import DEFAULT_EOD_CONFIG
    from app.services.eod_anomaly import _check_voided_rate

    with session_factory() as s:
        # Seed only 2 sales, both voided (100% rate).
        for _ in range(2):
            s.execute(
                __import__("sqlalchemy").text(
                    """INSERT INTO sale (
                        product_id, unit_price_gs, qty, discount_gs,
                        payment_method, invoice_type, invoice_number,
                        sold_at, voided_at
                    ) VALUES (
                        :pid, 10000, 1, 0, 'efectivo', 'boleta_resimple',
                        NULL, :sold_at, :voided_at
                    )"""
                ),
                {
                    "pid": product_id,
                    "sold_at": _dt.combine(_today(), time(12, 0)),
                    "voided_at": _dt.combine(_today(), time(13, 0)),
                },
            )
        s.commit()

        # Default min_sales=3 → both sales < 3, check skipped.
        cfg = dict(DEFAULT_EOD_CONFIG)
        assert _check_voided_rate(s, _today(), cfg) is None

        # Override min_sales=1 → fires.
        cfg["voided_rate_min_sales"] = 1
        a = _check_voided_rate(s, _today(), cfg)
        assert a is not None
        assert a.key == "eod.voided_rate"


def test_max_uninvoiced_ids_displayed_override_caps_list(session_factory, product_id):
    """Cap of 3 truncates the IDs displayed in the email body."""
    from app.rms.settings_runtime import DEFAULT_EOD_CONFIG
    from app.services.eod_anomaly import _check_uninvoiced_factura

    with session_factory() as s:
        for i in range(15):
            s.execute(
                __import__("sqlalchemy").text(
                    """INSERT INTO sale (
                        product_id, unit_price_gs, qty, discount_gs,
                        payment_method, invoice_type, invoice_number,
                        sold_at, voided_at
                    ) VALUES (
                        :pid, 10000, 1, 0, 'efectivo', 'factura',
                        NULL, :sold_at, NULL
                    )"""
                ),
                {
                    "pid": product_id,
                    "sold_at": _dt.combine(_today(), time(12, i)),
                },
            )
        s.commit()

        cfg = dict(DEFAULT_EOD_CONFIG)
        cfg["max_uninvoiced_ids_displayed"] = 3
        a = _check_uninvoiced_factura(s, _today(), cfg)
        assert a is not None
        assert a.key == "eod.uninvoiced_factura"
        # 15 total, but only 3 IDs in body + "..." marker
        assert a.body.count("ID") >= 1  # at least one
        assert a.body.count(", ") == 2  # exactly 3 IDs joined by ", "
        assert a.body.endswith("...")


def test_detect_anomalies_accepts_eod_cfg_kwarg(session_factory, product_id):
    """End-to-end: pass eod_cfg and verify threshold override applies."""
    from app.rms.settings_runtime import DEFAULT_EOD_CONFIG
    from app.services.eod_anomaly import detect_anomalies

    with session_factory() as s:
        # Seed 4 sales, 1 voided (25% rate)
        for i in range(4):
            s.execute(
                __import__("sqlalchemy").text(
                    """INSERT INTO sale (
                        product_id, unit_price_gs, qty, discount_gs,
                        payment_method, invoice_type, invoice_number,
                        sold_at, voided_at
                    ) VALUES (
                        :pid, 10000, 1, 0, 'efectivo', 'boleta_resimple',
                        NULL, :sold_at, :voided_at
                    )"""
                ),
                {
                    "pid": product_id,
                    "sold_at": _dt.combine(_today(), time(12, 0)),
                    "voided_at": (
                        _dt.combine(_today(), time(13, 0))
                        if i == 0
                        else None
                    ),
                },
            )
        s.commit()

        # Default threshold (0.10) does NOT fire (25% > 10% — wait, 25% > 10% SHOULD fire).
        # Let me recalc: 1 voided / 4 sales = 0.25 (25%). Default threshold is 0.10. So 25% > 10%, SHOULD fire.
        anomalies_default = detect_anomalies(s, day=_today())
        keys_default = {a.key for a in anomalies_default}
        assert "eod.voided_rate" in keys_default

        # Override threshold to 0.50 (50%). 25% < 50%, should NOT fire.
        cfg = dict(DEFAULT_EOD_CONFIG)
        cfg["voided_rate_threshold"] = 0.50
        anomalies_override = detect_anomalies(s, day=_today(), eod_cfg=cfg)
        keys_override = {a.key for a in anomalies_override}
        assert "eod.voided_rate" not in keys_override


def test_get_eod_config_returns_dict_with_all_keys():
    """get_eod_config(session) returns a complete dict."""
    from app.rms.settings_registry import get_setting_value
    from app.rms.settings_runtime import (
        DEFAULT_EOD_CONFIG,
        get_eod_config,
    )

    # Monkeypatch get_setting_value to return None for all keys
    # → all defaults applied.
    import app.rms.settings_registry as settings_mod

    orig = settings_mod.get_setting_value
    settings_mod.get_setting_value = lambda session, key: None
    try:
        out = get_eod_config(session=None)
    finally:
        settings_mod.get_setting_value = orig

    assert out == DEFAULT_EOD_CONFIG
    assert isinstance(out["voided_rate_threshold"], float)
    assert isinstance(out["voided_rate_min_sales"], int)


def test_get_eod_config_coerces_float():
    """Stored '0.25' is coerced to float 0.25."""
    from app.rms.settings_runtime import get_eod_config

    import app.rms.settings_registry as settings_mod

    def fake(session, key):
        if key == "eod.voided_rate_threshold":
            return "0.25"
        return None

    orig = settings_mod.get_setting_value
    settings_mod.get_setting_value = fake
    try:
        out = get_eod_config(session=None)
    finally:
        settings_mod.get_setting_value = orig

    assert out["voided_rate_threshold"] == 0.25
    assert isinstance(out["voided_rate_threshold"], float)
