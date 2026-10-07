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
        # Windows: %LOCALAPPDATA%\aiw-restaurant
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
    elif os.uname().sysname == "Darwin":
        # macOS: ~/Library/Application Support/aiw-restaurant
        base = Path.home() / "Library" / "Application Support"
    else:
        # Linux: ~/.local/share/aiw-restaurant
        base = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share")))
    return base / "aiw-restaurant"


DATA_DIR = Path(os.getenv("AIW_RMS_DATA_DIR", str(default_data_dir())))

# DB file path
# Read AIW_RMS_DB_PATH first (the canonical name), then fall back to
# AIW_SASKIA_DB_PATH (the legacy name still set by the saskia-vps
# production stack — see app/rms/main.py comments). Without this
# fallback, prod would read the default DATA_DIR/rms.sqlite (empty)
# instead of the seeded /data/rms.sqlite.
DB_PATH = Path(
    os.getenv("AIW_RMS_DB_PATH")
    or os.getenv("AIW_SASKIA_DB_PATH")
    or str(DATA_DIR / "rms.sqlite")
)

# Local backup dir
BACKUP_DIR = Path(
    os.getenv(
        "AIW_RMS_BACKUP_DIR",
        str(Path.home() / "Documents" / "aiw-restaurant" / "backups"),
    )
)

# Log dir
LOG_DIR = Path(
    os.getenv(
        "AIW_RMS_LOG_DIR",
        str(DATA_DIR / "logs"),
    )
)

# R2 (Cloudflare) backup config — read from ~/.config/sazon/r2.toml if present
R2_CONFIG_PATH = Path(
    os.getenv(
        "AIW_RMS_R2_CONFIG",
        str(Path.home() / ".config" / "sazon" / "r2.toml"),
    )
)

# Behavior knobs
BACKUP_THRESHOLD_HOURS = int(os.getenv("AIW_RMS_BACKUP_HOURS", "24"))
KEEP_LOCAL_BACKUPS_DAYS = int(os.getenv("AIW_RMS_KEEP_LOCAL_DAYS", "30"))

# D.5 — DNI-derived backup encryption. The DNI file is operator-managed
# (typically on a USB stick, NOT on the VPS). The path is REQUIRED for
# scheduled backups to run; if the file is missing, the cron fails
# closed with exit code 2. The file must be mode 0600 or 0400 — see
# app/services/backup_crypto.py for the perms check.
BACKUP_DNI_FILE = os.getenv("AIW_RMS_BACKUP_DNI_FILE", "/etc/sazon/backup-dni")

# PRODUCCION-V3 Phase 0: cap how far back shift-execute can write a
# ProductionCompletion row. The 14-day rolling forecast uses the last
# 14 days of completions; a stray 2020-01-01 backfill would corrupt
# the moving window. Cap is configurable per-deploy (default 7 days
# covers "I forgot to log yesterday and the day before").
BACKDATE_WINDOW_DAYS = int(os.getenv("AIW_RMS_BACKDATE_DAYS", "7"))

# Schema version (hand-rolled migrations; see db.py)
CURRENT_SCHEMA_VERSION = 112  # 111 = sale.channel + pedido.channel CHECK constraint (P41); 112 = extended channel set with HEREBUS retail/wholesale/distributor/eventual (SASKIA-204)
# 086 = monthly_closure table (Sprint 3.1 BACKLOG #15)
# 087 = soft_delete_columns on owned tables (Sprint 3.2)
# 088 = audit_columns on owned tables (Sprint 3.2)


def ensure_dirs() -> None:
    """Create data, backup, and log dirs if they don't exist. Idempotent."""
    for d in (DATA_DIR, BACKUP_DIR, LOG_DIR):
        d.mkdir(parents=True, exist_ok=True)


__all__ = [
    "ASUNCION_TZ",
    "BACKDATE_WINDOW_DAYS",
    "BACKUP_DIR",
    "BACKUP_THRESHOLD_HOURS",
    "BIND_HOST",
    "CURRENT_SCHEMA_VERSION",
    "DATA_DIR",
    "DB_PATH",
    "KEEP_LOCAL_BACKUPS_DAYS",
    "LOG_DIR",
    "PORT",
    "R2_CONFIG_PATH",
    "ensure_dirs",
]


# ---------------------------------------------------------------------------
# Pre-billing checklist thresholds (M-BIZ-002, URY pattern)
# ---------------------------------------------------------------------------
# All operator-tunable. Defaults are conservative for a single-user PY
# shop; tighten or loosen via env vars. Reading happens at module-import
# time, so changes require a process restart (or a reload of
# app.rms.sales.pre_sale_check and app.rms.sales.pre_sale_check_cart).
#
# Used by:
#   - app/rms/sales/pre_sale_check.py (single-line)
#   - app/rms/sales/pre_sale_check_cart.py (multi-line)

# Per-line qty ceiling: sales above this fire QTY_TOO_LARGE as a
# warning (single-line) or @N in multi-line. Default 999 (a single sale
# of more than 999 kg or units of one product is almost certainly wrong).
SAZON_PREFLIGHT_MAX_QTY_PER_SALE = int(os.getenv("SAZON_PREFLIGHT_MAX_QTY_PER_SALE", "999"))

# Cap on active held_sale rows (POS hold/sale pause). When the cap is
# hit, the oldest active row is auto-evicted (status=auto_evicted,
# audit row preserved). Default 50 — generous for a single-cashier
# counter but bounded to prevent runaway growth.
SAZON_MAX_HELD_SALES = int(os.getenv("SAZON_MAX_HELD_SALES", "50"))

# Discount ceiling: sales with discount > this % of the line total
# (without an explicit operator override) fire DISCOUNT_REQUIRES_OVERRIDE
# as a blocker. Default 20% — anything above is suspicious in a small shop.
SAZON_PREFLIGHT_MAX_DISCOUNT_PCT = int(os.getenv("SAZON_PREFLIGHT_MAX_DISCOUNT_PCT", "20"))

# M-FLO-001 (FloCafe port): below this many makeable units of stock,
# the POS quick-sell button shows a "Quedan N" low-stock badge. Default
# 5 units. Operators can override via SAZON_MENU_LOW_STOCK_UNITS.
SAZON_MENU_LOW_STOCK_UNITS = int(os.getenv("SAZON_MENU_LOW_STOCK_UNITS", "5"))
