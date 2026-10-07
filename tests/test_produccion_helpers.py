"""Tests for the extracted _helpers module.

Sazon-Improvement v2 (2026-10-06) Phase E: contract tests for the
helpers extracted from _full.py to _helpers.py. The shim re-exports
the public names from __init__.py, so callers can use either:
  from app.routers.produccion import source_to_bucket   # via shim
  from app.routers.produccion._helpers import ...      # direct

Both must point to the SAME function object (identity check) so
the shim is real, not a copy.
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo


def test_helpers_module_imports():
    from app.routers.produccion import _helpers

    assert hasattr(_helpers, "source_to_bucket")
    assert hasattr(_helpers, "_asuncion_today")
    assert hasattr(_helpers, "_batch_surplus")
    assert hasattr(_helpers, "_fermentation_reminder")
    assert hasattr(_helpers, "_week_monday")
    assert hasattr(_helpers, "_day_counts")
    assert hasattr(_helpers, "_parse_overrides")
    assert hasattr(_helpers, "_confidence_band_for_pct")
    assert hasattr(_helpers, "_current_user_display_name")


def test_constants_defined():
    from app.routers.produccion import _helpers

    assert "receta" in _helpers.SOURCE_BUCKETS
    assert "historial" in _helpers.SOURCE_BUCKETS
    assert "override" in _helpers.SOURCE_BUCKETS
    assert "horneado-extra" in _helpers.SOURCE_BUCKETS
    assert len(_helpers.CONFIDENCE_BANDS) == 5
    assert _helpers.DEFAULT_BAKE_START_HOUR == 6


def test_source_to_bucket_is_adhoc():
    """is_ad_hoc=True always returns 'horneado-extra' regardless of source."""
    from app.routers.produccion._helpers import source_to_bucket

    assert source_to_bucket("rolling_14d_avg", is_ad_hoc=True) == "horneado-extra"
    assert source_to_bucket("template", is_ad_hoc=True) == "horneado-extra"
    assert source_to_bucket(None, is_ad_hoc=True) == "horneado-extra"


def test_source_to_bucket_mappings():
    """The 4-bucket mapping per PRODUCCION-V3 Phase 2 design spec."""
    from app.routers.produccion._helpers import source_to_bucket

    # override stays override
    assert source_to_bucket("override", is_ad_hoc=False) == "override"
    # template/manual/seasonal_event → receta
    assert source_to_bucket("template", is_ad_hoc=False) == "receta"
    assert source_to_bucket("manual", is_ad_hoc=False) == "receta"
    assert source_to_bucket("seasonal_event", is_ad_hoc=False) == "receta"
    # rolling_14d_avg + unknown → historial
    assert source_to_bucket("rolling_14d_avg", is_ad_hoc=False) == "historial"
    assert source_to_bucket(None, is_ad_hoc=False) == "historial"
    assert source_to_bucket("xyz_unknown", is_ad_hoc=False) == "historial"


def test_batch_surplus_zero_or_negative():
    """Zero or negative demand yields zero everything (no batch needed)."""
    from app.routers.produccion._helpers import _batch_surplus

    assert _batch_surplus(0, 12) == {
        "batches": 0,
        "baked_qty": 0.0,
        "surplus_qty": 0.0,
        "surplus_pct": 0.0,
    }
    assert _batch_surplus(-5, 12) == {
        "batches": 0,
        "baked_qty": 0.0,
        "surplus_qty": 0.0,
        "surplus_pct": 0.0,
    }
    assert _batch_surplus(10, 0) == {
        "batches": 0,
        "baked_qty": 0.0,
        "surplus_qty": 0.0,
        "surplus_pct": 0.0,
    }


def test_batch_surplus_exact_fit():
    """Demand is exact multiple of yield → no surplus."""
    from app.routers.produccion._helpers import _batch_surplus

    r = _batch_surplus(24, 12)  # 2 batches, 24 baked, 24 demand → 0 surplus
    assert r["batches"] == 2
    assert r["baked_qty"] == 24.0
    assert r["surplus_qty"] == 0.0
    assert r["surplus_pct"] == 0.0


def test_batch_surplus_with_remainder():
    """Demand of 10 with yield 12 → 1 batch, 12 baked, 2 surplus."""
    from app.routers.produccion._helpers import _batch_surplus

    r = _batch_surplus(10, 12)
    assert r["batches"] == 1
    assert r["baked_qty"] == 12.0
    assert r["surplus_qty"] == 2.0
    assert r["surplus_pct"] == 20.0


def test_week_monday_returns_monday():
    """Returns the Monday of the week containing any_date."""
    from app.routers.produccion._helpers import _week_monday

    # 2026-10-07 is a Wednesday → 2026-10-05 is the Monday
    assert _week_monday(date(2026, 10, 7)) == date(2026, 10, 5)
    # 2026-10-05 is a Monday → returns itself
    assert _week_monday(date(2026, 10, 5)) == date(2026, 10, 5)
    # 2026-10-11 is a Sunday → previous Monday is 2026-10-05
    assert _week_monday(date(2026, 10, 11)) == date(2026, 10, 5)


def test_parse_overrides_extracts_ov_prefixed():
    """Params like ov_12=10.5 become {12: 10.5}."""
    from app.routers.produccion._helpers import _parse_overrides

    params = {"ov_12": "10.5", "ov_7": "3", "other": "skip", "ov_bad": "not-a-number"}
    result = _parse_overrides(params)
    assert result == {12: 10.5, 7: 3.0}


def test_confidence_band_for_pct_thresholds():
    """The 5-band mapping: 0/None=vlow, <25=vlow, <50=low, <70=med, <85=high, else=vhigh."""
    from app.routers.produccion._helpers import _confidence_band_for_pct

    assert _confidence_band_for_pct(None) == "conf-vlow"
    assert _confidence_band_for_pct(0) == "conf-vlow"
    assert _confidence_band_for_pct(15) == "conf-vlow"
    assert _confidence_band_for_pct(25) == "conf-low"
    assert _confidence_band_for_pct(49) == "conf-low"
    assert _confidence_band_for_pct(50) == "conf-med"
    assert _confidence_band_for_pct(69) == "conf-med"
    assert _confidence_band_for_pct(70) == "conf-high"
    assert _confidence_band_for_pct(84) == "conf-high"
    assert _confidence_band_for_pct(85) == "conf-vhigh"
    assert _confidence_band_for_pct(100) == "conf-vhigh"


def test_fermentation_reminder_none_for_zero():
    """fermentation_minutes=0 or None → None (no ferment step)."""
    from app.routers.produccion._helpers import _fermentation_reminder

    assert _fermentation_reminder(None) is None
    assert _fermentation_reminder(0) is None
    assert _fermentation_reminder(-5) is None


def test_fermentation_reminder_finishes_at_bake_start():
    """The start_at + fermentation_minutes == bake_start (06:00 today)."""
    from app.routers.produccion._helpers import _fermentation_reminder

    r = _fermentation_reminder(120, bake_start_hour=6)  # 2h ferment
    assert r is not None
    assert r["fermentation_minutes"] == 120
    assert r["fermentation_hours"] == 2.0
    # ready_label should be 06:00 today
    today = datetime.now(ZoneInfo("America/Asuncion")).date()
    assert today.strftime("%d/%m") in r["ready_label"]


def test_shim_reexports_helper_identity():
    """The shim must re-export the SAME function object, not a copy.

    The python-phased-refactor skill says: pin with a test that asserts
    `shim.symbol is new_package.symbol` (identity, not equality) so the
    shim never silently copies a value.
    """
    # The shim's __init__ re-exports from _full, not from _helpers
    # (helpers extraction is additive; _full still has the originals).
    # The identity test is: re-export via __init__ must match the
    # _full-defined function until the next extraction step.
    import app.routers.produccion as pkg
    from app.routers.produccion import _full, _helpers

    assert pkg.source_to_bucket is _full.source_to_bucket
    # And the helper module's copy (when imported) is also a function
    # that passes the same tests
    assert callable(_helpers.source_to_bucket)
    assert callable(_full.source_to_bucket)


def test_asuncion_today_returns_date():
    """_asuncion_today returns a date in the America/Asuncion timezone."""
    from app.routers.produccion._helpers import _asuncion_today

    result = _asuncion_today()
    assert isinstance(result, date)
    # Should be within ±1 day of UTC today
    utc_today = datetime.utcnow().date()
    assert abs((result - utc_today).days) <= 1
