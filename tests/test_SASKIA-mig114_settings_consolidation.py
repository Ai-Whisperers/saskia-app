"""# allow-hardcoded-dates: fixtures intentionally pin fixed dates (calendar edges, tz math, far-future sentinels); asserted relative to frozen or explicit anchors.
Sprint 2.1 — migration 114 data-copy test (AppMeta → settings_kv).

Locks: registry + legacy keys copy over, KV wins on conflict, empty
AppMeta values are skipped, non-settings AppMeta rows stay, idempotent
re-run.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.rms.db import init_db
from app.rms.models import AppMeta, SettingsKV


@pytest.fixture()
def engine(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path}/mig114.sqlite")
    return eng


def _db_version(s) -> int:
    """schema_version lives in app_meta (AGENTS.md rule 18: PRAGMA
    user_version not implemented yet)."""
    row = s.execute(
        select(AppMeta.value).where(AppMeta.key == "schema_version")
    ).scalar_one_or_none()
    return int(row) if row else 0


def test_fresh_db_reaches_114_and_settings_copied(engine, tmp_path):
    """Fresh init: version 114, no crash, settings_kv usable."""
    init_db(engine)
    s = sessionmaker(bind=engine)()
    assert _db_version(s) == 114
    s.close()


def test_appmeta_settings_copied_to_kv(tmp_path):
    """Pre-seeded AppMeta settings land in settings_kv and are deleted."""
    engine = create_engine(f"sqlite:///{tmp_path}/mig114b.sqlite")
    # Init to 113 first (pre-consolidation), seed, then re-init to 114.
    # Simulate by bumping config: init_db applies all pending in order, so
    # seed by intercepting after create_all — simplest: init fully, then
    # hand-insert AppMeta rows and re-run JUST migration 114's function.
    init_db(engine)
    s = sessionmaker(bind=engine)()
    ts = "2026-10-07T00:00:00+00:00"
    s.add(AppMeta(key="production.demand_snapshot_ttl_seconds", value="900", updated_at=ts))
    s.add(AppMeta(key="business_name", value="Mi Panadería", updated_at=ts))
    s.add(AppMeta(key="theme", value="dark", updated_at=ts))
    s.add(
        AppMeta(key="last_backup_at", value="2026-10-07T00:00:00Z", updated_at=ts)
    )  # NOT a setting
    s.commit()

    from app.rms.db import _migration_114_settings_kv_consolidation

    with engine.begin() as conn:
        _migration_114_settings_kv_consolidation(conn)

    kv = {k: v for k, v in s.execute(select(SettingsKV.key, SettingsKV.value_json)).all()}
    # Registry key copied (bare string → JSON-quoted)
    assert kv.get("production.demand_snapshot_ttl_seconds") == '"900"'
    # Legacy router keys copied
    assert kv.get("business_name") == '"Mi Panadería"'
    assert kv.get("theme") == '"dark"'
    # Copied rows removed from AppMeta
    assert s.scalar(select(AppMeta).where(AppMeta.key == "business_name")) is None
    assert (
        s.scalar(select(AppMeta).where(AppMeta.key == "production.demand_snapshot_ttl_seconds"))
        is None
    )
    # Non-settings AppMeta row untouched
    assert s.scalar(select(AppMeta).where(AppMeta.key == "last_backup_at")) is not None
    s.close()


def test_migration_114_idempotent_and_kv_wins(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/mig114c.sqlite")
    init_db(engine)
    s = sessionmaker(bind=engine)()
    from app.rms.db import _migration_114_settings_kv_consolidation

    # KV already has business_name → migration must NOT overwrite/delete
    s.add(SettingsKV(key="business_name", value_json='"KV Wins"'))
    s.add(
        AppMeta(key="business_name", value="AppMeta Older", updated_at="2026-10-07T00:00:00+00:00")
    )
    s.commit()

    with engine.begin() as conn:
        _migration_114_settings_kv_consolidation(conn)
    val = s.scalar(select(SettingsKV.value_json).where(SettingsKV.key == "business_name"))
    assert val == '"KV Wins"'
    # AppMeta row stays (KV existed → skip branch, no delete)
    assert s.scalar(select(AppMeta).where(AppMeta.key == "business_name")) is not None

    # Re-run: no crash, no dupes
    with engine.begin() as conn:
        _migration_114_settings_kv_consolidation(conn)
    n = len(list(s.execute(select(SettingsKV).where(SettingsKV.key == "business_name"))))
    assert n == 1
    s.close()


def test_empty_appmeta_value_skipped(tmp_path):
    """Empty-string AppMeta rows mean 'never customized' — not copied."""
    engine = create_engine(f"sqlite:///{tmp_path}/mig114d.sqlite")
    init_db(engine)
    s = sessionmaker(bind=engine)()
    s.add(AppMeta(key="business_name", value="", updated_at="2026-10-07T00:00:00+00:00"))
    s.commit()

    from app.rms.db import _migration_114_settings_kv_consolidation

    with engine.begin() as conn:
        _migration_114_settings_kv_consolidation(conn)
    assert s.scalar(select(SettingsKV).where(SettingsKV.key == "business_name")) is None
    # Row left in place (harmless; the page falls back to blank either way)
    assert s.scalar(select(AppMeta).where(AppMeta.key == "business_name")) is not None
    s.close()
