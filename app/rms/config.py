"""app/rms/config.py — paths, ports, env vars, defaults.

Read by `main.py` (FastAPI app), `db.py` (engine init), `services/backup_scheduler.py`,
and `services/r2_backup.py`.

All env vars are optional; defaults are sensible for a single-user local install.
"""

from __future__ import annotations

import os
from pathlib import Path
from zoneinfo import ZoneInfo

# Timezone (Asunción, UTC-4, no DST)
ASUNCION_TZ = ZoneInfo("America/Asuncion")

# Binding (must be 127.0.0.1; main.py asserts this)
BIND_HOST = os.getenv("BIND_HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8765"))


# Data dir (per-OS)
def default_data_dir() -> Path:
    if os.name == "nt":
        # Windows: %LOCALAPPDATA%\AIW-Saskia
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
    elif os.uname().sysname == "Darwin":
        # macOS: ~/Library/Application Support/AIW-Saskia
        base = Path.home() / "Library" / "Application Support"
    else:
        # Linux: ~/.local/share/AIW-Saskia
        base = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share")))
    return base / "AIW-Saskia"


DATA_DIR = Path(os.getenv("AIW_SASKIA_DATA_DIR", str(default_data_dir())))

# DB file path
DB_PATH = Path(os.getenv("AIW_SASKIA_DB_PATH", str(DATA_DIR / "rms.sqlite")))

# Local backup dir
BACKUP_DIR = Path(
    os.getenv(
        "AIW_SASKIA_BACKUP_DIR",
        str(Path.home() / "Documents" / "AIW-Saskia" / "backups"),
    )
)

# Log dir
LOG_DIR = Path(
    os.getenv(
        "AIW_SASKIA_LOG_DIR",
        str(DATA_DIR / "logs"),
    )
)

# R2 (Cloudflare) backup config — read from ~/.config/aiw-saskia/r2.toml if present
R2_CONFIG_PATH = Path(
    os.getenv(
        "AIW_SASKIA_R2_CONFIG",
        str(Path.home() / ".config" / "aiw-saskia" / "r2.toml"),
    )
)

# Behavior knobs
BACKUP_THRESHOLD_HOURS = int(os.getenv("AIW_SASKIA_BACKUP_HOURS", "24"))
KEEP_LOCAL_BACKUPS_DAYS = int(os.getenv("AIW_SASKIA_KEEP_LOCAL_DAYS", "30"))

# Schema version (hand-rolled migrations; see db.py)
CURRENT_SCHEMA_VERSION = 1


def ensure_dirs() -> None:
    """Create data, backup, and log dirs if they don't exist. Idempotent."""
    for d in (DATA_DIR, BACKUP_DIR, LOG_DIR):
        d.mkdir(parents=True, exist_ok=True)


__all__ = [
    "ASUNCION_TZ",
    "BIND_HOST",
    "PORT",
    "DATA_DIR",
    "DB_PATH",
    "BACKUP_DIR",
    "LOG_DIR",
    "R2_CONFIG_PATH",
    "BACKUP_THRESHOLD_HOURS",
    "KEEP_LOCAL_BACKUPS_DAYS",
    "CURRENT_SCHEMA_VERSION",
    "ensure_dirs",
]
