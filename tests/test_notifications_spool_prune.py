"""Verify _prune_spool removes only files older than retention."""
import os, time, datetime
from pathlib import Path
from app.rms.notifications import _prune_spool, SPOOL_DIR, _SPOOL_RETENTION_DAYS

def test_prune_drops_only_old_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # Two files: one fresh, one 10 days old
    SPOOL_DIR.mkdir(parents=True, exist_ok=True)
    fresh = SPOOL_DIR / "dryrun-fresh.txt"
    fresh.write_text("x")
    old = SPOOL_DIR / "dryrun-old.txt"
    old.write_text("x")
    # Backdate old by 10 days
    old_time = (datetime.datetime.now() - datetime.timedelta(days=10)).timestamp()
    os.utime(old, (old_time, old_time))

    removed = _prune_spool()
    assert removed == 1
    assert fresh.exists()
    assert not old.exists()
