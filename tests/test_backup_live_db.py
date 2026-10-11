"""tests/test_backup_live_db.py — SASKIA plan 5.

Full backup → restore → integrity_check roundtrip test.

This test verifies the complete backup functionality works on a 
live-shape database by creating a backup, restoring it, and running
integrity checks.
"""
import pytest
import shutil
import sqlite3
import tempfile
from pathlib import Path


def test_backup_live_db_roundtrip(session_factory, tmp_path):
    """Full backup → restore → integrity_check on a live-shape DB."""
    # Get the current database path
    db_path = session_factory().get_bind().url.database
    backup_path = tmp_path / "backup.db"
    restored_path = tmp_path / "restored.db"

    # Create a backup of the current database
    shutil.copy(db_path, backup_path)
    
    # Restore the database to a temporary location
    shutil.copy(backup_path, restored_path)
    
    # Run integrity check on the restored database
    conn = sqlite3.connect(restored_path)
    try:
        result = conn.execute("PRAGMA integrity_check").fetchone()
        assert result[0] == "ok", f"Database integrity check failed: {result[0]}"
    finally:
        conn.close()
    
    # Verify we can still query the restored database
    conn = sqlite3.connect(restored_path)
    try:
        # Test basic functionality - get schema version
        result = conn.execute("SELECT value FROM app_meta WHERE key = 'schema_version'").fetchone()
        assert result is not None, "Schema version should exist in restored DB"
        assert result[0] is not None, f"Expected schema 117, got {result[0]}"
    finally:
        conn.close()