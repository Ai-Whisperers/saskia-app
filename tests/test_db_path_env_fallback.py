"""TDD: DB_PATH must accept the legacy AIW_SASKIA_DB_PATH env var.

Why this test exists:
- 2026-10-06 the user could not log in to the saskia-vps production
  stack even with `demo / demo1234`. The container had
  AIW_SASKIA_DB_PATH=/data/rms.sqlite set (legacy env name), but
  app/rms/config.py only read AIW_RMS_DB_PATH. The app fell back
  to the default DATA_DIR/rms.sqlite, which was an EMPTY database
  (0 users, 0 products). Every login attempt returned
  "credenciales inválidas" because the user query returned None.

The fix: DB_PATH reads AIW_RMS_DB_PATH first, then falls back to
AIW_SASKIA_DB_PATH, then to the default. This matches the rest of
the codebase (app/rms/main.py:1118, 1215 already do this fallback).

This test must:
1. Set AIW_SASKIA_DB_PATH to a custom path and verify DB_PATH uses it.
2. Set AIW_RMS_DB_PATH to override AIW_SASKIA_DB_PATH (canonical wins).
3. With neither set, fall back to DATA_DIR/rms.sqlite.
"""



def _reload_config(monkeypatch, env: dict[str, str | None]):
    """Set env vars and re-import config to pick them up.

    AIW_RMS_DATA_DIR and AIW_RMS_DB_PATH are read at module import
    time, so we have to drop the cached module from sys.modules
    before re-importing. We also clear the lru_caches that depend
    on these (using_supabase, etc.) — but DB_PATH itself is a
    module-level constant.
    """
    for k, v in env.items():
        if v is None:
            monkeypatch.delenv(k, raising=False)
        else:
            monkeypatch.setenv(k, v)

    # Drop config + any module that imported DB_PATH
    import sys
    for mod_name in list(sys.modules.keys()):
        if mod_name == "app.rms.config" or mod_name.startswith("app."):
            del sys.modules[mod_name]

    from app.rms import config
    return config


def test_db_path_accepts_legacy_aiw_saskia_db_path(monkeypatch, tmp_path):
    """When only AIW_SASKIA_DB_PATH is set (legacy prod env name),
    DB_PATH must use it. Without the fix, DB_PATH falls back to
    DATA_DIR/rms.sqlite which is empty in prod."""
    target = tmp_path / "saskia.sqlite"
    target.touch()
    config = _reload_config(monkeypatch, {
        "AIW_SASKIA_DB_PATH": str(target),
        "AIW_RMS_DB_PATH": None,
        "AIW_RMS_DATA_DIR": None,
    })
    assert config.DB_PATH == target, (
        f"DB_PATH should be {target} (from AIW_SASKIA_DB_PATH), got {config.DB_PATH}"
    )


def test_db_path_prefers_aiw_rms_db_path_over_legacy(monkeypatch, tmp_path):
    """When both env vars are set, AIW_RMS_DB_PATH (canonical) wins.
    This preserves the documented precedence."""
    canonical = tmp_path / "canonical.sqlite"
    legacy = tmp_path / "legacy.sqlite"
    canonical.touch()
    legacy.touch()
    config = _reload_config(monkeypatch, {
        "AIW_RMS_DB_PATH": str(canonical),
        "AIW_SASKIA_DB_PATH": str(legacy),
    })
    assert config.DB_PATH == canonical, (
        f"AIW_RMS_DB_PATH should win over AIW_SASKIA_DB_PATH. "
        f"Got {config.DB_PATH}, expected {canonical}"
    )


def test_db_path_defaults_to_data_dir_when_neither_set(monkeypatch, tmp_path):
    """With both env vars unset, DB_PATH falls back to DATA_DIR/rms.sqlite."""
    config = _reload_config(monkeypatch, {
        "AIW_RMS_DB_PATH": None,
        "AIW_SASKIA_DB_PATH": None,
        "AIW_RMS_DATA_DIR": str(tmp_path / "data"),
    })
    expected = tmp_path / "data" / "rms.sqlite"
    assert config.DB_PATH == expected, (
        f"DB_PATH should default to {expected}, got {config.DB_PATH}"
    )
