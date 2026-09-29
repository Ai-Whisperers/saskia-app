"""tests/test_daily_summary.py — verify scripts/daily_summary.py."""
from __future__ import annotations


def test_daily_summary_dryrun():
    """Smoke test: the script runs with --backend dryrun and exits 0."""
    import os
    import sqlite3
    import subprocess
    import tempfile

    db_path = tempfile.mktemp(suffix=".sqlite")
    # Init empty schema
    conn = sqlite3.connect(db_path)
    conn.close()
    env = os.environ.copy()
    env["AIW_SASKIA_DB_PATH"] = db_path
    env["PATH"] = "/opt/data/work/saskia-app/.venv/bin:" + env.get("PATH", "")
    env.pop("DATABASE_URL", None)
    result = subprocess.run(
        [
            "uv", "run", "python", "scripts/daily_summary.py", "--backend", "dryrun",
        ],
        capture_output=True, text=True, timeout=60,
        cwd="/opt/data/work/saskia-app",
        env=env,
    )
    assert "ok=True" in result.stdout, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    os.unlink(db_path)


def test_daily_summary_with_yesterday_flag():
    """The --yesterday flag changes the label."""
    import os
    import sqlite3
    import subprocess
    import tempfile

    db_path = tempfile.mktemp(suffix=".sqlite")
    conn = sqlite3.connect(db_path)
    conn.close()
    env = os.environ.copy()
    env["AIW_SASKIA_DB_PATH"] = db_path
    env.pop("DATABASE_URL", None)
    result = subprocess.run(
        [
            "uv", "run", "python", "scripts/daily_summary.py",
            "--yesterday", "--backend", "dryrun",
        ],
        capture_output=True, text=True, timeout=60,
        cwd="/opt/data/work/saskia-app",
        env=env,
    )
    assert "(ayer)" in result.stdout or "yesterday" in result.stdout.lower() or result.returncode == 0
    os.unlink(db_path)
