"""tests/test_backup_cfg_override.py — Batch B4 (2026-10-07).

Verifies the operator-tunable backup thresholds. The three
helpers in app/services/auto_backup.py (needs_auto_backup,
needs_warning, prune_old_backups) accept an optional backup_cfg
dict kwarg. Tests cover:
- Default behavior (no kwarg) matches the historical 24h/7d/30 values.
- Override raises/lowers thresholds.
- Partial cfg merges with defaults (same pattern as B1+B2+B3).
- DEFAULT_BACKUP_CONFIG matches the SettingsKV registry defaults.
- Backward-compat module-level constants still equal defaults.

NOTE: app/services/auto_backup.py is currently a helper-only module
used by tests + small scripts. The production backup scheduler
(app/services/backup_scheduler.py) reads from the
AIW_RMS_BACKUP_HOURS env var. Wiring the SettingsKV values into the
scheduler is a separate decision — see the Batch B4 CHANGELOG entry.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from app.rms.config import ASUNCION_TZ
from app.services.auto_backup import (
    AUTO_BACKUP_THRESHOLD_HOURS,
    DEFAULT_BACKUP_CONFIG,
    DEFAULT_KEEP_LAST_N,
    WARN_THRESHOLD_DAYS,
    backup_filename,
    last_backup_at,
    needs_auto_backup,
    needs_warning,
    prune_old_backups,
)


def test_default_constants_match_legacy_values():
    """Backward-compat: module constants still equal 24/7/30."""
    assert AUTO_BACKUP_THRESHOLD_HOURS == 24
    assert WARN_THRESHOLD_DAYS == 7
    assert DEFAULT_KEEP_LAST_N == 30


def test_default_backup_config_dict_has_three_keys():
    assert set(DEFAULT_BACKUP_CONFIG.keys()) == {
        "auto_threshold_hours",
        "warn_threshold_days",
        "keep_last_n",
    }


def test_needs_auto_backup_default_kwarg_uses_24h():
    """No kwarg → uses AUTO_BACKUP_THRESHOLD_HOURS = 24h."""
    recent = datetime.now(ASUNCION_TZ) - timedelta(hours=1)
    ancient = datetime.now(ASUNCION_TZ) - timedelta(hours=48)
    assert needs_auto_backup(recent) is False
    assert needs_auto_backup(ancient) is True
    assert needs_auto_backup(None) is True


def test_needs_auto_backup_explicit_threshold_overrides():
    """Explicit threshold_hours=1 → 2-hour-old backup needs a new one."""
    two_hours_ago = datetime.now(ASUNCION_TZ) - timedelta(hours=2)
    assert needs_auto_backup(two_hours_ago, threshold_hours=1) is True


def test_needs_auto_backup_cfg_override_lowers_threshold():
    """backup_cfg={"auto_threshold_hours": 1} → 2-hour-old backup fires."""
    two_hours_ago = datetime.now(ASUNCION_TZ) - timedelta(hours=2)
    assert needs_auto_backup(two_hours_ago, backup_cfg={"auto_threshold_hours": 1}) is True


def test_needs_auto_backup_cfg_override_raises_threshold():
    """backup_cfg={"auto_threshold_hours": 100} → 48h backup doesn't fire."""
    ancient = datetime.now(ASUNCION_TZ) - timedelta(hours=48)
    assert needs_auto_backup(ancient, backup_cfg={"auto_threshold_hours": 100}) is False


def test_needs_warning_default_uses_7d():
    """Default 7-day warn threshold."""
    three_days = datetime.now(ASUNCION_TZ) - timedelta(days=3)
    ten_days = datetime.now(ASUNCION_TZ) - timedelta(days=10)
    assert needs_warning(three_days) is False
    assert needs_warning(ten_days) is True
    assert needs_warning(None) is True


def test_needs_warning_cfg_override_raises_threshold():
    """backup_cfg={"warn_threshold_days": 30} → 10d backup doesn't fire."""
    ten_days = datetime.now(ASUNCION_TZ) - timedelta(days=10)
    assert needs_warning(ten_days, backup_cfg={"warn_threshold_days": 30}) is False


def test_prune_old_backups_default_keeps_30(tmp_path):
    """Default keep_last_n=30 → 35 files pruned to 30."""
    # Create 35 fake backup files with incrementing mtimes.
    files = []
    base = datetime.now()
    for i in range(35):
        f = tmp_path / f"rms-backup-{i:04d}.xlsx"
        f.write_text("x")
        # Newer files have higher index → newer mtime
        import os as _os

        mtime = (base + timedelta(seconds=i)).timestamp()
        _os.utime(f, (mtime, mtime))
        files.append(f)

    deleted = prune_old_backups(tmp_path)
    assert deleted == 5
    remaining = sorted(tmp_path.glob("rms-backup-*.xlsx"))
    assert len(remaining) == 30


def test_prune_old_backups_cfg_override_keeps_5(tmp_path):
    """backup_cfg={"keep_last_n": 5} → 10 files pruned to 5."""
    import os as _os

    base = datetime.now()
    for i in range(10):
        f = tmp_path / f"rms-backup-{i:04d}.xlsx"
        f.write_text("x")
        mtime = (base + timedelta(seconds=i)).timestamp()
        _os.utime(f, (mtime, mtime))

    deleted = prune_old_backups(tmp_path, backup_cfg={"keep_last_n": 5})
    assert deleted == 5
    assert len(list(tmp_path.glob("rms-backup-*.xlsx"))) == 5


def test_prune_old_backups_explicit_arg_overrides_cfg(tmp_path):
    """Explicit keep_last_n=2 wins over backup_cfg={"keep_last_n": 100}."""
    import os as _os

    base = datetime.now()
    for i in range(10):
        f = tmp_path / f"rms-backup-{i:04d}.xlsx"
        f.write_text("x")
        mtime = (base + timedelta(seconds=i)).timestamp()
        _os.utime(f, (mtime, mtime))

    deleted = prune_old_backups(tmp_path, keep_last_n=2, backup_cfg={"keep_last_n": 100})
    assert deleted == 8
    assert len(list(tmp_path.glob("rms-backup-*.xlsx"))) == 2


def test_get_backup_config_returns_full_defaults():
    """get_backup_config(session) → dict == DEFAULT_BACKUP_CONFIG."""
    from app.rms.settings_runtime import (
        DEFAULT_BACKUP_CONFIG,
        get_backup_config,
    )

    import app.rms.settings_registry as settings_mod

    orig = settings_mod.get_setting_value
    settings_mod.get_setting_value = lambda session, key: None
    try:
        out = get_backup_config(session=None)
    finally:
        settings_mod.get_setting_value = orig

    assert out == DEFAULT_BACKUP_CONFIG


def test_get_backup_config_coerces_stored_value():
    """Stored '48' for auto_threshold_hours is coerced to int 48."""
    from app.rms.settings_runtime import get_backup_config

    import app.rms.settings_registry as settings_mod

    def fake(session, key):
        if key == "backup.auto_threshold_hours":
            return "48"
        return None

    orig = settings_mod.get_setting_value
    settings_mod.get_setting_value = fake
    try:
        out = get_backup_config(session=None)
    finally:
        settings_mod.get_setting_value = orig

    assert out["auto_threshold_hours"] == 48
    assert isinstance(out["auto_threshold_hours"], int)


def test_partial_cfg_merges_with_defaults():
    """A cfg with only one key overrides that key; rest fall back."""
    from app.services.auto_backup import needs_auto_backup

    ancient = datetime.now(ASUNCION_TZ) - timedelta(hours=48)
    cfg = {"auto_threshold_hours": 100}

    # 48h < 100h threshold → no backup needed.
    assert needs_auto_backup(ancient, backup_cfg=cfg) is False
