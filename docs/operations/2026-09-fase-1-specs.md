# Fase 1 build specs — implementation details

> **For Kiki.** Bundle of implementation specs for the build phase. Each spec is self-contained: file paths, code stubs, test cases, time estimates. Land each spec into its corresponding task in the dev plan.
>
> **Source:** `/opt/data/profiles/ivan/.hermes/plans/2026-08-31_192054-saskia-comprehensive-improvements.md`
>
> **Cross-references:**
> - `docs/plans/2026-08-31-rms-fase-1-dev-plan.md` — the locked build plan, tasks 1-10
> - `docs/operations/import-mapper.md` — v1 catalog column spec
> - `docs/operations/2026-09-fase-1-prep.md` — operator-side docs (this same bundle, the prep file)
> - `docs/operations/copy-vos-request.md` — Paraguayan Spanish UI copy template

---


---

# Auto-backup on app startup

_Source: original at `saskia-preflight/spec-auto-backup.md`_

# App spec — Auto-backup to local folder

> **For Kiki (or whoever picks up Task 9 install).** Implementation spec for the SHOULD-FIX auto-backup feature.
>
> **Source:** improvements review §2.1 (1h build, integrated into Task 9 install session).
>
> **Cost to build:** ~1h. **Pays for itself** the first time Saskia has a power loss.

---

## What this does

Every time the app starts, if the last backup is more than 24 hours old, automatically export the SQLite database to a timestamped `.xlsx` file in a configured local folder. **No user action required.**

If the last backup is more than 7 days old, show a notification toast inside the app: *"Hace más de 7 días que no exportás. ¿Querés exportar ahora?"* with a button that triggers an immediate export.

## Why

The dev plan §3 says "backups: Excel export she copies to Drive." That's a manual step. Manual steps don't happen. Without auto-backup, the first time her laptop crashes mid-write or Windows Update forces a reboot, she loses every sale since the last export.

## Configuration

**File:** `app/config.py` reads backup config from `~/.config/aiw-saskia/backup.toml`:

```toml
# ~/.config/aiw-saskia/backup.toml
[backup]
# Folder where auto-exported .xlsx files land.
# Default if missing: ~/Documents/AIW-Saskia/backups/
folder = "~/Documents/AIW-Saskia/backups/"

# Auto-export runs if last backup is older than this (hours).
auto_threshold_hours = 24

# Show in-app toast if last backup is older than this (days).
warn_threshold_days = 7

# Keep this many recent backups; older ones get deleted.
keep_last_n = 30
```

On Windows, `~` is `%USERPROFILE%`. The folder should be inside her Documents or anywhere inside a Drive-synced folder (Drive File Stream auto-uploads it).

## Implementation

### Module: `app/services/auto_backup.py`

```python
from datetime import datetime, timedelta
from pathlib import Path
import sqlite3
import openpyxl
from app.config import get_backup_config
from app.services.export_xlsx import export_all_to_xlsx

def needs_auto_backup(last_backup_at: datetime | None, threshold_hours: int) -> bool:
    """True if last_backup_at is older than threshold, or no backup yet."""
    if last_backup_at is None:
        return True
    return datetime.now() - last_backup_at > timedelta(hours=threshold_hours)

def needs_warning(last_backup_at: datetime | None, threshold_days: int) -> bool:
    """True if last_backup_at is older than threshold, or no backup yet."""
    if last_backup_at is None:
        return True
    return datetime.now() - last_backup_at > timedelta(days=threshold_days)

def last_backup_at(folder: Path) -> datetime | None:
    """Return the mtime of the most recent .xlsx in folder, or None."""
    if not folder.exists():
        return None
    files = list(folder.glob("rms-backup-*.xlsx"))
    if not files:
        return None
    return datetime.fromtimestamp(max(f.stat().st_mtime for f in files))

def auto_backup(db_path: Path, folder: Path) -> Path:
    """Export SQLite -> timestamped .xlsx in folder. Returns the new file path."""
    folder.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = folder / f"rms-backup-{timestamp}.xlsx"
    export_all_to_xlsx(db_path, out)
    return out

def prune_old_backups(folder: Path, keep_last_n: int) -> int:
    """Delete oldest backups beyond keep_last_n. Returns count deleted."""
    files = sorted(folder.glob("rms-backup-*.xlsx"), key=lambda f: f.stat().st_mtime, reverse=True)
    deleted = 0
    for f in files[keep_last_n:]:
        f.unlink()
        deleted += 1
    return deleted
```

### Call site: `app/rms/main.py` (in startup event)

```python
from contextlib import asynccontextmanager
from app.services.auto_backup import (
    auto_backup, last_backup_at, needs_auto_backup,
    needs_warning, prune_old_backups,
)
from app.config import get_backup_config

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    cfg = get_backup_config()
    db_path = Path(app.state.config["db_path"])
    folder = Path(cfg["folder"]).expanduser()

    last = last_backup_at(folder)
    if needs_auto_backup(last, cfg["auto_threshold_hours"]):
        try:
            new = auto_backup(db_path, folder)
            app.state.last_backup_at = datetime.now()
            app.state.last_backup_path = new
            prune_old_backups(folder, cfg["keep_last_n"])
        except Exception as e:
            # Backup failure must NOT block app startup.
            # Log to file; UI shows "Backup failed" if user navigates to it.
            log_to_audit(f"backup failed: {e}")
    else:
        app.state.last_backup_at = last

    # Warn if too old
    if needs_warning(app.state.last_backup_at, cfg["warn_threshold_days"]):
        app.state.show_backup_warning = True

    yield
    # Shutdown (nothing to do)
```

### UI: `app/templates/inicio.html` (warning toast)

Add a banner at the top of the dashboard when `show_backup_warning == True`:

```html
{% if show_backup_warning %}
<div class="backup-warning">
  <span>Hace más de 7 días que no exportás.</span>
  <a href="/exportar">Exportar ahora</a>
</div>
{% endif %}
```

## Tests

`tests/test_auto_backup.py`:

1. `test_needs_auto_backup_when_never_backed_up` — `last_backup_at is None` → returns `True`
2. `test_needs_auto_backup_when_recent` — `last_backup_at = now - 1 hour`, threshold 24h → returns `False`
3. `test_needs_auto_backup_when_old` — `last_backup_at = now - 25 hours`, threshold 24h → returns `True`
4. `test_prune_old_backups_keeps_n_most_recent` — create 35 backups, prune, verify only 30 remain
5. `test_auto_backup_creates_timestamped_file` — call `auto_backup`, verify filename matches `rms-backup-YYYYMMDD-HHMMSS.xlsx`

## What this does NOT do

- ❌ Does NOT upload to Drive directly. The folder should be inside a Drive-synced location (e.g., `~/Library/CloudStorage/GoogleDrive-.../My Drive/AIW-Saskia/backups/`). Drive uploads happen automatically via Drive File Stream.
- ❌ Does NOT run as a system service. It's a one-time check on app startup. If she never opens the app, no backup.
- ❌ Does NOT alert her externally (no email, no SMS). The in-app toast is the only signal.

## Time spent

- 30 min: write `auto_backup.py` + tests
- 15 min: integrate with `main.py` lifespan
- 15 min: pre-create backup folder at install session + write `backup.toml` with Windows-friendly defaults

**Total: ~1h** as estimated.

---

*End of spec. To be merged into Task 9 of the dev plan when the build starts.*


---

# SQLite WAL + bind-127 + /healthz endpoint

_Source: original at `saskia-preflight/spec-wal-bind-healthz.md`_

# App spec — SQLite WAL + bind-127.0.0.1-only + /healthz

> **For Kiki.** Implementation spec for the reliability + security baselines. Integrated into Task 1 (skeleton app).
>
> **Source:** improvements review §2.2.
>
> **Cost:** ~1h.

---

## A. SQLite WAL mode + pragmas

**File:** `app/rms/db.py`

After `create_engine(...)`, immediately run these pragmas on every new connection:

```python
from sqlalchemy import create_engine, event

engine = create_engine(
    f"sqlite:///{db_path}",
    echo=False,
    connect_args={"check_same_thread": False},
)

@event.listens_for(engine, "connect")
def set_sqlite_pragmas(dbapi_connection, connection_record):
    """Set reliability pragmas on every new SQLite connection."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")        # Concurrent readers + safer writes
    cursor.execute("PRAGMA synchronous=NORMAL")     # Faster, still crash-safe in WAL
    cursor.execute("PRAGMA foreign_keys=ON")        # Enforce FK constraints
    cursor.execute("PRAGMA busy_timeout=5000")      # Wait 5s if DB is locked, fail gracefully
    cursor.close()
```

### Why

- **`journal_mode=WAL`**: Without this, every write locks the entire DB. Concurrent reads stall. Power loss mid-write silently corrupts the file. WAL mode lets readers and writers run simultaneously and survives power loss.
- **`synchronous=NORMAL`**: Combined with WAL, gives crash-safety with better performance than FULL. Trades ~1 in 1000 chance of corruption on power loss for ~10x write speed.
- **`foreign_keys=ON`**: SQLite has FK support but it's disabled by default per-connection. Without this, the schema constraints in `models.py` are decorative.
- **`busy_timeout=5000`**: Instead of immediate "database is locked" error, wait up to 5 seconds. Reduces "I tried to register a sale but my cashier was also adding inventory" failures.

### Documentation

Add to `app/README.md`:

```markdown
## SQLite pragmas

The app sets these pragmas on every connection:
- `journal_mode=WAL` — write-ahead logging for concurrent readers
- `synchronous=NORMAL` — crash-safe in WAL with better perf than FULL
- `foreign_keys=ON` — FK constraints enforced
- `busy_timeout=5000` — 5s wait before failing on lock

Do not change these without operator review. WAL mode is required
for the auto-backup + concurrent sale-entry workflow to work.
```

## B. Bind to 127.0.0.1 only

**File:** `app/rms/main.py` (startup)

```python
import os
import sys

# Refuse to bind to anything other than 127.0.0.1
BIND_HOST = os.environ.get("RMS_BIND_HOST", "127.0.0.1")
if BIND_HOST != "127.0.0.1":
    print(f"FATAL: RMS_BIND_HOST must be 127.0.0.1, got '{BIND_HOST}'.", file=sys.stderr)
    print("       This app is single-PC, single-user. LAN access is not supported.", file=sys.stderr)
    sys.exit(1)
```

### Why

If `run.bat` ever passes `--host 0.0.0.0` (e.g., "let me try from my phone"), every machine on her Wi-Fi can hit the app. No PII, but cost data + sales data + inventory. **This is the easiest OPSEC break in the entire engagement.**

The check at startup makes the constraint unbreakable from the outside; bypassing requires editing source code, which means she'd have to ask us.

### What if she asks for LAN access later?

That's a separate quote. Add to the FAQ: *"If you want to open this from your phone or another laptop, that's fase 2 — different security model, different deployment. Currently the app is local-only by design."*

## C. /healthz endpoint

**File:** `app/routers/health.py`

```python
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

router = APIRouter()

@router.get("/healthz")
def healthz(request: Request):
    """Cheap health check. Returns 200 always; verifies uvicorn is alive."""
    return {"status": "ok", "service": "aiw-saskia-rms"}

@router.get("/healthz/db")
def healthz_db(request: Request):
    """DB health check. Returns 200 if SQLite is reachable and writable; 503 otherwise."""
    try:
        db = request.app.state.db
        result = db.execute(text("SELECT 1")).scalar()
        if result != 1:
            return JSONResponse({"db": "unreachable"}, status_code=503)
        # Also check WAL is enabled
        mode = db.execute(text("PRAGMA journal_mode")).scalar()
        return {
            "db": "ok",
            "journal_mode": mode,
            "version": "x.y.z",  # from app/__init__.py
        }
    except Exception as e:
        return JSONResponse({"db": "error", "detail": str(e)}, status_code=503)
```

**Register in main.py:** `app.include_router(health.router, prefix="")`.

### Why

When her browser shows a blank page, the diagnostic chain is:
1. Is uvicorn running? → `/healthz` returns 200
2. Is the DB reachable? → `/healthz/db` returns 200
3. Is the page route broken? → look at browser devtools console

Without this, debugging takes 10 minutes of "is it Python? is it the browser? is it Windows Defender?"

### Tests

`tests/test_health.py`:

1. `test_healthz_returns_ok`
2. `test_healthz_db_returns_ok_when_db_alive`
3. `test_healthz_db_returns_503_when_db_locked` — open a long-running write transaction, then call `/healthz/db` from another thread

## What this does NOT do

- ❌ Does NOT add `/metrics` (Prometheus-style). Out of scope; this is a single-user app.
- ❌ Does NOT add authentication. Dev plan §3 says no login.
- ❌ Does NOT add request logging. Probably useful; defer to fase 1.5.

## Time spent

- 15 min: pragmas + bind check + tests
- 30 min: /healthz + /healthz/db endpoints + tests
- 15 min: README updates

**Total: ~1h** as estimated.

---

*End of spec. To be merged into Task 1 of the dev plan when the build starts.*


---

# Money rounding (Decimal) + Unit enum

_Source: original at `saskia-preflight/spec-money-units.md`_

# App spec — Money rounding + Unit enum

> **For Kiki.** Implementation spec for the money and unit type-safety helpers. Integrated into Task 2 (costing engine).
>
> **Source:** improvements review §2.6.
>
> **Cost:** ~1h.

---

## A. Money helpers (`app/rms/money.py`)

The Guaraní rules per the dev plan and `04_foodbiz/AGENTS.md`:

- All money columns in the DB are **integer Gs.** (no decimals)
- All money **display** uses Guaraní conventions: "Gs. 729.167" with period-as-thousands-separator
- All money **calculations** should NOT round intermediate values
- All money **persistence** rounds half-up to integer at the last step

### Implementation

```python
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

def to_decimal(value) -> Decimal:
    """Coerce input to Decimal safely. Reject None, empty string, or non-numeric."""
    if value is None or value == "":
        raise ValueError(f"Cannot coerce {value!r} to Decimal")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as e:
        raise ValueError(f"Invalid money value: {value!r}") from e

def to_int_gs(value) -> int:
    """Round to nearest integer Gs., half up. Use at persistence sites only.
    
    NEVER use this in intermediate calculations. The pattern is:
        line_cost = to_decimal(qty) * to_decimal(price)   # Decimal, no rounding
        recipe_cost = sum(...)                            # Decimal, no rounding
        recipe_cost_gs = to_int_gs(recipe_cost)           # round ONCE at the end
    """
    return int(to_decimal(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

def format_gs(value: int) -> str:
    """Format integer Gs. as 'Gs. 1.234.567' (period thousands separator, Paraguayan)."""
    if value is None:
        return "—"
    # Format with thousand separators (period), no decimals
    s = f"{abs(value):,}".replace(",", ".")
    return f"Gs. {s}" if value >= 0 else f"-Gs. {s}"

def parse_gs(s: str) -> int:
    """Parse a user-entered Gs. string (with optional thousands sep) back to int."""
    if s is None:
        raise ValueError("empty string")
    cleaned = s.strip().replace(".", "").replace(",", "").replace("Gs.", "").replace("Gs", "").strip()
    if not cleaned.lstrip("-").isdigit():
        raise ValueError(f"not an integer: {s!r}")
    return int(cleaned)
```

### Why these specific rules

- **`Decimal` not `float`**: float has representation errors. `Decimal("0.1") + Decimal("0.2") == Decimal("0.3")`; floats give `0.30000000000000004`. For money, that's not a bug, that's a class of bugs.
- **No intermediate rounding**: if `line_cost = 832.5 Gs.` and we round to 833 immediately, then sum 20 lines, we might end up at 16,667 when the right answer (sum first, round once) is 16,650. Round at persistence sites only.
- **`quantize(Decimal("1"), ROUND_HALF_UP)`**: Python's `Decimal` rounds half-to-even by default (banker's rounding). For money, half-up is the standard.
- **Paraguayan formatting**: period as thousands separator (Spanish convention), comma as decimal (but we never use decimal). "Gs. 1.234.567" not "Gs. 1,234,567".

### Display in HTML

Server-side format: `{{ product.sale_price_gs | fmt_gs }}` where `fmt_gs` is a Jinja filter that calls `format_gs`. Don't format in JavaScript; the server is the source of truth for money.

```python
# app/main.py
from app.rms.money import format_gs
@app.template_filter("fmt_gs")
def fmt_gs_filter(value):
    return format_gs(value)
```

## B. Unit enum (`app/rms/units.py`)

The dev plan §5 has `unit` field on `ingredient` and `recipe.yield_unit`. Free-text "g" vs "gramos" vs "gram" is a bug factory.

### Implementation

```python
from enum import Enum

class Unit(Enum):
    """Canonical units for HEREBUS ops. Add to this list only with operator review."""
    G = "g"
    KG = "kg"
    ML = "ml"
    L = "l"
    UNIT = "und"      # countable items (eggs, muffins, packages)

    @classmethod
    def coerce(cls, value: str) -> "Unit":
        """Parse free-text input into canonical Unit. Fuzzy on aliases."""
        if value is None:
            raise ValueError("empty unit")
        s = str(value).strip().lower()
        # Map common aliases to canonical
        aliases = {
            "g": cls.G, "gramo": cls.G, "gramos": cls.G, "gram": cls.G,
            "kg": cls.KG, "kilo": cls.KG, "kilos": cls.KG, "kilogramo": cls.KG,
            "ml": cls.ML, "mililitro": cls.ML, "mililitros": cls.ML,
            "l": cls.L, "litro": cls.L, "litros": cls.L,
            "und": cls.UNIT, "unidad": cls.UNIT, "unidades": cls.UNIT, "u": cls.UNIT,
            "porcion": cls.UNIT, "porciones": cls.UNIT, "bandeja": cls.UNIT,
        }
        if s in aliases:
            return aliases[s]
        # Try direct enum match
        for member in cls:
            if member.value == s:
                return member
        raise ValueError(f"unknown unit: {value!r}. Allowed: g, kg, ml, l, und")
```

### Validation

```python
# In Pydantic models:
from pydantic import validator
from app.rms.units import Unit

class IngredientBase(BaseModel):
    name: str
    unit: Unit        # Pydantic auto-coerces via the enum
    stock_qty: Decimal
    purchase_price_gs: int | None = None
    min_stock_qty: Decimal = Decimal("0")
    
    @validator("unit", pre=True)
    def coerce_unit(cls, v):
        return Unit.coerce(v)
```

This means:
- User enters "gramos" → coerced to `Unit.G`
- User enters "u" → coerced to `Unit.UNIT`
- User enters "stones" → 422 Unprocessable Entity with a friendly error

### Conversion at costing time

The costing engine needs to handle unit math:
- `recipe_line.qty` is in `ingredient.unit`
- `recipe.yield_qty` is in `recipe.yield_unit`
- `product.portion_label` is in `recipe.yield_unit` (typically; can differ)

Conversion rules:
- `g ↔ kg`: divide / multiply by 1000
- `ml ↔ l`: divide / multiply by 1000
- `und`: no conversion to g/kg/ml/l
- **Cross-family conversions are forbidden**: `g → ml` (density), `und → kg` (recipe-defined) — these would need explicit conversion factors per ingredient, out of scope

Stock drop calculation must check unit compatibility:

```python
def can_drop_stock(line_unit: Unit, ingredient_unit: Unit) -> bool:
    """True if line_unit and ingredient_unit are directly compatible."""
    if line_unit == ingredient_unit:
        return True
    pair = frozenset([line_unit, ingredient_unit])
    return pair in (frozenset([Unit.G, Unit.KG]), frozenset([Unit.ML, Unit.L]))

def convert_qty(qty: Decimal, from_unit: Unit, to_unit: Unit) -> Decimal:
    if not can_drop_stock(from_unit, to_unit):
        raise ValueError(f"Cannot convert {from_unit} to {to_unit}")
    factor = {
        (Unit.G, Unit.KG): Decimal("0.001"),
        (Unit.KG, Unit.G): Decimal("1000"),
        (Unit.ML, Unit.L): Decimal("0.001"),
        (Unit.L, Unit.ML): Decimal("1000"),
    }.get((from_unit, to_unit))
    return qty * factor if factor else qty
```

### Display

Use the canonical value in the UI:

```python
unit_display = {
    Unit.G: "g",
    Unit.KG: "kg",
    Unit.ML: "ml",
    Unit.L: "l",
    Unit.UNIT: "und",
}
```

## Tests

`tests/test_money.py`:

1. `test_to_int_gs_rounds_half_up` — `to_int_gs(Decimal("0.5"))` → `1`; `to_int_gs(Decimal("1.5"))` → `2`; `to_int_gs(Decimal("2.5"))` → `3` (NOT banker's rounding 2)
2. `test_to_int_gs_no_float_drift` — `to_int_gs(Decimal("0.1") + Decimal("0.2"))` → `0` (NOT `1` like float would give)
3. `test_format_gs_uses_period_thousands_separator` — `format_gs(1234567)` → `"Gs. 1.234.567"` (NOT `"Gs. 1,234,567"`)
4. `test_parse_gs_handles_period_comma_space` — `parse_gs("Gs. 1.234.567")` → `1234567`; `parse_gs("1,234,567")` → `1234567`; `parse_gs("1234567")` → `1234567`
5. `test_to_decimal_rejects_invalid_input` — `to_decimal(None)` raises; `to_decimal("")` raises; `to_decimal("abc")` raises

`tests/test_units.py`:

1. `test_unit_coerce_aliases` — `Unit.coerce("gramos")` → `Unit.G`; `Unit.coerce("kilo")` → `Unit.KG`; `Unit.coerce("porcion")` → `Unit.UNIT`
2. `test_unit_coerce_rejects_unknown` — `Unit.coerce("stones")` raises ValueError
3. `test_convert_g_to_kg` — `convert_qty(Decimal("1500"), Unit.G, Unit.KG)` → `Decimal("1.5")`
4. `test_convert_kg_to_g` — `convert_qty(Decimal("1.5"), Unit.KG, Unit.G)` → `Decimal("1500")`
5. `test_convert_cross_family_forbidden` — `convert_qty(Decimal("100"), Unit.G, Unit.L)` raises ValueError

## Time spent

- 30 min: money.py + tests
- 30 min: units.py + Pydantic integration + tests

**Total: ~1h** as estimated.

---

*End of spec. To be merged into Task 2 of the dev plan when the build starts.*


---

# Self-service import (file picker)

_Source: original at `saskia-preflight/spec-self-service-import.md`_

# App spec — Self-service import (file picker)

> **For Kiki.** Implementation spec for replacing the "she provides a copy" ritual with a native file picker. Integrated into Task 6 (Excel import/export).
>
> **Source:** improvements review §2.3.
>
> **Cost:** ~2h.

---

## What this does

The app has an "Importar" button that opens a native file dialog. Saskia picks her Excel file (anywhere — Desktop, Downloads, Drive-synced folder, USB stick). The app imports. **No copy-of-Drive-files ritual. No USB hand-off. No "give us access."**

## Why

The dev plan §6 says "import from a copy of Drive files she provides." That's a multi-step ritual:
1. Saskia opens Drive
2. Finds the folder
3. Downloads the file
4. Hands it to us (USB? Airdrop? Email?)
5. We import
6. She deletes the copy (per OPSEC)

This won't happen naturally. The "she runs it without us in the room" goal (dev plan §1) requires self-service.

## Implementation

### Backend: `app/routers/excel_io.py`

Add a `POST /import/upload` endpoint accepting multipart form data:

```python
import shutil
import tempfile
from pathlib import Path
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from app.services.import_xlsx import import_workbook
from app.services.auto_backup import auto_backup
from datetime import datetime

router = APIRouter()

@router.post("/import/upload")
async def import_upload(
    request: Request,
    file: UploadFile = File(...),
    confirm_overwrite: bool = Form(False),
):
    """Self-service import. She picks the file; we import.

    confirm_overwrite must be True to overwrite existing recipes/inventory.
    First call returns preview with row counts + ask for confirmation.
    Second call (with confirm=True) does the actual import + auto-backup first.
    """
    if not file.filename.endswith((".xlsx", ".xlsm")):
        raise HTTPException(400, "Only .xlsx and .xlsm files are supported")

    db_path = Path(request.app.state.config["db_path"])

    # Always auto-backup BEFORE import. If import fails, she has a recovery point.
    backup_folder = Path(request.app.state.config["backup_folder"]).expanduser()
    backup = auto_backup(db_path, backup_folder)
    backup_filename = backup.name

    # Save upload to temp
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    try:
        result = import_workbook(
            db_path=db_path,
            xlsx_path=tmp_path,
            confirm_overwrite=confirm_overwrite,
        )
    except Exception as e:
        # Restore from backup if import blew up mid-flight
        result = {
            "status": "error",
            "detail": str(e),
            "backup_before": backup_filename,
            "rollback_command": f"cp {backup} {db_path}",
        }
    finally:
        tmp_path.unlink(missing_ok=True)

    return result
```

### Service: `app/services/import_xlsx.py` (rewrite from existing spec)

The current dev plan §6 says to write `services/import_xlsx.py` that maps sheets to tables. Per the improvements review §6.3 (name-matching rule) and the import-mapper spec at `docs/operations/import-mapper.md`, the service must:

1. **Two-pass**: First call returns a preview (counts of ingredients/recipes to be imported, any unmapped columns, any name conflicts). Second call (with `confirm=True`) does the actual write.
2. **Match by name**: try ING-ID first, fall back to normalized name (lowercase, accent-stripped, whitespace-collapsed). Document in docstring.
3. **Skip + count**: rows that can't be mapped are **skipped, not failed**. The result includes `{"skipped": [{"row": N, "reason": "ING-9999 not found in inventory"}]}`.
4. **Don't wipe sales**: import is additive. Existing sales, stock_moves, etc. are preserved. Re-importing the same file is a no-op (or only updates changed fields).

```python
def import_workbook(db_path: Path, xlsx_path: Path, confirm_overwrite: bool) -> dict:
    """Two-pass import. Returns counts + skip list."""
    # First pass: parse the workbook, compute what would change
    parsed = parse_workbook(xlsx_path)
    changes = diff_against_db(db_path, parsed)

    if not confirm_overwrite and changes.has_conflicts():
        return {
            "status": "preview",
            "would_change": changes.summary(),
            "conflicts": changes.conflict_list(),
            "skipped": parsed.skipped(),
        }

    if not confirm_overwrite:
        # No conflicts; safe to proceed but require confirmation for safety
        return {
            "status": "preview",
            "would_change": changes.summary(),
            "skipped": parsed.skipped(),
        }

    # Second pass: actually write
    return {
        "status": "imported",
        "added": changes.added(),
        "updated": changes.updated(),
        "skipped": parsed.skipped(),
        "backup_before": backup_filename,
    }
```

### Frontend: `app/templates/excel_io.html`

```html
{% extends "base.html" %}
{% block content %}
<h1>Importar planilla</h1>

<form id="import-form" action="/import/upload" method="post" enctype="multipart/form-data">
  <p>
    <label>
      Archivo Excel (.xlsx):
      <input type="file" name="file" accept=".xlsx,.xlsm" required>
    </label>
  </p>
  <p>
    <label>
      <input type="checkbox" name="confirm_overwrite" value="true">
      Confirmo: pisar recetas e inventario si hay cambios
    </label>
  </p>
  <button type="submit">Importar</button>
</form>

<details>
  <summary>¿Qué hace esto?</summary>
  <ol>
    <li>Hace un backup automático del SQLite actual (por si algo sale mal).</li>
    <li>Lee tu archivo de Excel.</li>
    <li>Agrega ingredientes nuevos. Actualiza los que cambiaron.</li>
    <li>Salta filas que no se pueden mapear (te las muestra abajo).</li>
    <li>Nunca borra ventas existentes.</li>
  </ol>
  <p>Si querés volver atrás después de importar, decímelo y restauramos el backup.</p>
</details>

{% if result %}
<section class="result {% if result.status == 'error' %}error{% elif result.status == 'preview' %}preview{% else %}ok{% endif %}">
  <h2>Resultado</h2>
  <pre>{{ result | tojson(indent=2) }}</pre>
</section>
{% endif %}
{% endblock %}
```

### CSRF / size limits

- FastAPI's default `UploadFile` has no size limit. Set one:
  ```python
  app.add_middleware(
      lambda: None,  # placeholder
  )
  ```
  Actually use Starlette's `MaxBodySizeMiddleware` or just check `file.size` in the endpoint:
  ```python
  MAX_SIZE = 50 * 1024 * 1024  # 50 MB
  @router.post("/import/upload")
  async def import_upload(request: Request, file: UploadFile = File(...)):
      # Read into memory to check size; reject early
      contents = await file.read()
      if len(contents) > MAX_SIZE:
          raise HTTPException(413, f"Archivo demasiado grande ({len(contents)} bytes). Máximo: {MAX_SIZE}")
      # ... rest of logic
  ```

- CSRF: since the app has no login, CSRF doesn't apply. But the import endpoint should still validate `confirm_overwrite == True` before destructive ops.

## Tests

`tests/test_import_upload.py`:

1. `test_import_upload_rejects_non_xlsx` — POST with `.txt` file returns 400
2. `test_import_upload_creates_backup_first` — verify a backup file exists in the backup folder after import
3. `test_import_upload_preview_mode_doesnt_modify_db` — first call (no confirm) returns preview; SQLite row count unchanged
4. `test_import_upload_overwrite_mode_modifies_db` — second call (confirm=True) updates rows
5. `test_import_upload_preserves_sales` — even with confirm=True, existing sales are untouched
6. `test_import_upload_skips_unmappable_rows` — workbook with `ING-9999` references returns skipped list
7. `test_import_upload_restores_on_failure` — malformed workbook → response includes rollback command

## What this does NOT do

- ❌ Does NOT sync to Drive. The backup lands in a local folder; Drive upload is via Drive File Stream (not the app's job).
- ❌ Does NOT show a file picker for the workbook system (Google Sheets). Only local Excel files.
- ❌ Does NOT auto-detect changes from Drive. She has to re-import manually when she updates her workbook.

## Time spent

- 30 min: `excel_io.py` route + service integration
- 30 min: `excel_io.html` template + result display
- 30 min: tests
- 30 min: documentation in `app/README.md`

**Total: ~2h** as estimated.

---

*End of spec. To be merged into Task 6 of the dev plan when the build starts.*


---

# Stock-out alert + monthly report

_Source: original at `saskia-preflight/spec-stockout-alert.md`_

# Sto-out alert + monthly report spec

> **For Kiki.** Implementation spec for the dashboard's stock-out signaling and the monthly stock-out report. Integrated into Task 7 (Tablero Inicio).
>
> **Source:** improvements review §2.4.
>
> **Cost:** ~1h.

---

## A. Stock-out alert in the dashboard widget

### Current behavior (dev plan §7)

```
Avisos: low stock (stock_qty < min_stock_qty and min > 0),
       recipes with batch_cost is None,
       sales in period with no recipe
```

### Improved behavior

Three severity levels:

| Severity | Condition | Visual |
|---|---|---|
| **OK** | `stock_qty >= min_stock_qty` (and `min > 0`) | No badge |
| **WARN** | `0 <= stock_qty < min_stock_qty` (and `min > 0`) | Yellow badge: "Stock bajo" |
| **CRITICAL** | `stock_qty < 0` | **Flashing red** badge: "¡Stock negativo!" |

### Implementation

`app/routers/dashboard.py`:

```python
from enum import Enum

class StockSeverity(Enum):
    OK = "ok"
    WARN = "warn"
    CRITICAL = "critical"

def stock_severity(stock_qty: Decimal, min_stock_qty: Decimal) -> StockSeverity:
    """Severity ladder. min_stock_qty = 0 means 'no min set' = OK."""
    if min_stock_qty <= 0:
        return StockSeverity.OK
    if stock_qty < 0:
        return StockSeverity.CRITICAL
    if stock_qty < min_stock_qty:
        return StockSeverity.WARN
    return StockSeverity.OK
```

`app/templates/inicio.html` (Avisos widget):

```html
{% for alert in stock_alerts %}
<section class="alert alert-{{ alert.severity.value }}{% if alert.severity.value == 'critical' %}flash{% endif %}">
  <strong>
    {% if alert.severity.value == 'critical' %}¡Stock negativo!{% else %}Stock bajo{% endif %}:
  </strong>
  {{ alert.ingredient_name }} tiene {{ alert.stock_qty }} {{ alert.unit }},
  mínimo es {{ alert.min_stock_qty }} {{ alert.unit }}.
  {% if alert.severity.value == 'critical' %}
    Hacé un recuento.
  {% else %}
    Reabastecé pronto.
  {% endif %}
</section>
{% endfor %}
```

The `.flash` CSS class makes CRITICAL alerts blink:

```css
.alert-critical.flash {
    animation: blinker 1.5s linear infinite;
    background-color: #fee;
}
@keyframes blinker {
    50% { opacity: 0.3; }
}
```

(Don't make this too aggressive — flashing is annoying. 1.5s interval is gentle.)

## B. Monthly stock-out report

### What it shows

For the prior calendar month:
- Ingredients that were below minimum or negative at any point
- Days-below-zero per ingredient (cumulative count of days where `stock_qty < 0`)
- Suggested reorder quantity (max historical usage × 30 days / actual current stock)

### Implementation

`app/services/reports.py`:

```python
from datetime import date, datetime, timedelta
from sqlalchemy import func, and_

def monthly_stockout_report(session, year: int, month: int) -> list[dict]:
    """Returns rows for the monthly stock-out report."""
    period_start = date(year, month, 1)
    if month == 12:
        period_end = date(year + 1, 1, 1)
    else:
        period_end = date(year, month + 1, 1)
    
    # Find all sale_stock_moves in the period, grouped by ingredient
    moves = (
        session.query(
            SaleStockMove.ingredient_id,
            func.sum(SaleStockMove.qty_delta).label("total_moved")
        )
        .filter(SaleStockMove.created_at >= period_start)
        .filter(SaleStockMove.created_at < period_end)
        .group_by(SaleStockMove.ingredient_id)
        .all()
    )
    
    rows = []
    for ingredient_id, total_moved in moves:
        ingredient = session.query(Ingredient).get(ingredient_id)
        if ingredient.stock_qty < ingredient.min_stock_qty:
            avg_daily_usage = abs(total_moved) / 30  # rough estimate
            suggested_reorder = max(0, int(avg_daily_usage * 30 - ingredient.stock_qty))
            rows.append({
                "ingredient": ingredient.name,
                "unit": ingredient.unit.value,
                "current_stock": ingredient.stock_qty,
                "min_stock": ingredient.min_stock_qty,
                "monthly_usage": abs(total_moved),
                "suggested_reorder": suggested_reorder,
                "severity": "critical" if ingredient.stock_qty < 0 else "warn",
            })
    
    return sorted(rows, key=lambda r: r["severity"] != "critical", reverse=False)
```

### Endpoint: `app/routers/reports.py`

```python
from fastapi import Request, Query
from fastapi.responses import HTMLResponse, StreamingResponse
import io
import csv

@router.get("/reports/stockout/{year}/{month}")
def stockout_report(request: Request, year: int, month: int, format: str = Query("html")):
    """Monthly stock-out report. HTML by default; ?format=csv for export."""
    session = request.app.state.db
    rows = monthly_stockout_report(session, year, month)
    
    if format == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=[
            "ingredient", "unit", "current_stock", "min_stock",
            "monthly_usage", "suggested_reorder", "severity",
        ])
        writer.writeheader()
        writer.writerows(rows)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=stockout-{year}-{month:02d}.csv"},
        )
    
    return templates.TemplateResponse("reports/stockout.html", {
        "request": request,
        "year": year,
        "month": month,
        "rows": rows,
    })
```

### UI: link from dashboard

`app/templates/inicio.html`:

```html
<a href="/reports/stockout/{{ now.year }}/{{ now.month }}" class="btn-secondary">
  Ver reporte mensual de stock
</a>
```

## Tests

`tests/test_stockout_report.py`:

1. `test_stock_severity_ok` — stock >= min → OK
2. `test_stock_severity_warn` — 0 <= stock < min → WARN
3. `test_stock_severity_critical` — stock < 0 → CRITICAL
4. `test_stock_severity_no_min` — min = 0 → OK (regardless of stock)
5. `test_monthly_report_excludes_ok_ingredients` — only ingredients below minimum appear
6. `test_monthly_report_critical_first` — CRITICAL rows sort before WARN
7. `test_monthly_report_csv_export` — `?format=csv` returns valid CSV

## What this does NOT do

- ❌ Does NOT email alerts. In-app only.
- ❌ Does NOT auto-reorder. Saskia manually triggers orders via her supplier workflow.
- ❌ Does NOT track days-below-zero precisely (uses daily snapshot, not real-time). 1-day resolution is fine.

## Time spent

- 30 min: severity enum + dashboard widget
- 30 min: monthly report service + endpoint + template

**Total: ~1h** as estimated.

---

*End of spec. To be merged into Task 7 of the dev plan when the build starts.*


---

# Test suite minimum (pytest coverage)

_Source: original at `saskia-preflight/spec-test-suite.md`_

# Test-suite minimum spec

> **For Kiki.** Implementation spec for the test suite that covers money, costing, and import. Lands across Tasks 1-6 as a continuous practice, not as a single task.
>
> **Source:** improvements review §2.9.
>
> **Cost:** ~2h total, distributed across Tasks 1-6.

---

## Why

The dev plan §4 lists three test files (`test_costing.py`, `test_stock_drop.py`, `test_import_roundtrip.py`). That's **not enough**. Bugs in costing are expensive (every sale uses it). Bugs in import are silent (wrong data, no error).

This spec defines the **minimum** test suite. More is welcome but this is the floor.

## Layout

```
app/
  tests/
    __init__.py
    conftest.py              # shared fixtures
    test_money.py            # 5+ tests
    test_units.py            # 5+ tests
    test_costing.py          # 10+ tests (was 1+ in dev plan)
    test_stock_drop.py       # 5+ tests (was 1+)
    test_import_roundtrip.py # 3+ tests (was 1+)
    test_void_sale.py        # 3+ tests (no coverage in dev plan)
    test_healthz.py          # 2+ tests (new, post §2.2)
    fixtures/
      mini.xlsx              # synthetic workbook (3 ingredients, 1 recipe, 2 products)
```

## `conftest.py`

```python
import pytest
from app.rms.db import init_db
from app.rms.models import (
    Ingredient, Recipe, RecipeLine, Product, Sale, SaleStockMove,
)

@pytest.fixture
def db_session(tmp_path):
    """In-memory SQLite for fast tests."""
    db_path = tmp_path / "test.sqlite"
    session = init_db(db_path)
    yield session
    session.close()

@pytest.fixture
def make_ingredient(db_session):
    """Factory for ingredients."""
    def _make(name, unit="g", purchase_price_gs=1000, stock_qty=1000, min_stock_qty=100):
        ing = Ingredient(
            name=name,
            unit=unit,
            purchase_price_gs=purchase_price_gs,
            stock_qty=stock_qty,
            min_stock_qty=min_stock_qty,
        )
        db_session.add(ing)
        db_session.flush()
        return ing
    return _make

@pytest.fixture
def mini_workbook(tmp_path):
    """Path to the synthetic mini.xlsx used in import tests."""
    return Path(__file__).parent / "fixtures" / "mini.xlsx"
```

## `test_money.py` (5+ tests)

```python
from decimal import Decimal
import pytest
from app.rms.money import to_int_gs, format_gs, parse_gs, to_decimal

def test_to_int_gs_rounds_half_up():
    assert to_int_gs(Decimal("0.5")) == 1
    assert to_int_gs(Decimal("1.5")) == 2
    assert to_int_gs(Decimal("2.5")) == 3   # NOT banker's rounding (2)
    assert to_int_gs(Decimal("3.5")) == 4

def test_to_int_gs_no_float_drift():
    """Classic float bug: 0.1 + 0.2 = 0.30000000000000004"""
    # With Decimal, this should round to 0
    result = to_int_gs(Decimal("0.1") + Decimal("0.2"))
    assert result == 0
    # Not 1 (which is what float would give)

def test_format_gs_uses_period_thousands():
    assert format_gs(0) == "Gs. 0"
    assert format_gs(1234567) == "Gs. 1.234.567"
    assert format_gs(729167) == "Gs. 729.167"
    assert format_gs(17500000) == "Gs. 17.500.000"

def test_parse_gs_handles_various_inputs():
    assert parse_gs("Gs. 729.167") == 729167
    assert parse_gs("1.234.567") == 1234567
    assert parse_gs("1,234,567") == 1234567
    assert parse_gs("1234567") == 1234567
    assert parse_gs("-Gs. 500") == -500

def test_to_decimal_rejects_invalid_input():
    with pytest.raises(ValueError):
        to_decimal(None)
    with pytest.raises(ValueError):
        to_decimal("")
    with pytest.raises(ValueError):
        to_decimal("abc")
```

## `test_units.py` (5+ tests)

```python
import pytest
from decimal import Decimal
from app.rms.units import Unit, convert_qty, can_drop_stock

def test_unit_coerce_aliases():
    assert Unit.coerce("gramos") == Unit.G
    assert Unit.coerce("kilo") == Unit.KG
    assert Unit.coerce("mililitros") == Unit.ML
    assert Unit.coerce("litros") == Unit.L
    assert Unit.coerce("porcion") == Unit.UNIT
    assert Unit.coerce("u") == Unit.UNIT

def test_unit_coerce_rejects_unknown():
    with pytest.raises(ValueError):
        Unit.coerce("stones")
    with pytest.raises(ValueError):
        Unit.coerce(None)

def test_convert_g_to_kg():
    assert convert_qty(Decimal("1500"), Unit.G, Unit.KG) == Decimal("1.5")

def test_convert_kg_to_g():
    assert convert_qty(Decimal("1.5"), Unit.KG, Unit.G) == Decimal("1500")

def test_convert_cross_family_forbidden():
    with pytest.raises(ValueError):
        convert_qty(Decimal("100"), Unit.G, Unit.L)
    with pytest.raises(ValueError):
        convert_qty(Decimal("100"), Unit.UNIT, Unit.G)

def test_can_drop_stock_compatible():
    assert can_drop_stock(Unit.G, Unit.G)
    assert can_drop_stock(Unit.G, Unit.KG)
    assert can_drop_stock(Unit.KG, Unit.G)
    assert can_drop_stock(Unit.ML, Unit.L)
    assert not can_drop_stock(Unit.G, Unit.ML)
    assert not can_drop_stock(Unit.UNIT, Unit.G)
```

## `test_costing.py` (10+ tests)

Per dev plan §9 Task 2: *"muffin batch 12, cost 24_000 Gs. → unit cost 2_000; sale of 2 drops flour by `2 * (flour_per_batch/12)`."*

Expand to:

```python
def test_recipe_batch_cost_with_full_prices(make_ingredient, db_session):
    flour = make_ingredient("Flour", purchase_price_gs=2000)  # 2000 Gs/kg
    recipe = Recipe(name="Muffin", yield_qty=12, yield_unit="und")
    db_session.add(recipe)
    db_session.flush()
    db_session.add(RecipeLine(recipe_id=recipe.id, ingredient_id=flour.id, qty=500))  # 500g = 0.5kg
    db_session.flush()
    
    cost = recipe_batch_cost_gs(db_session, recipe.id)
    assert cost == 1000  # 0.5kg × 2000 Gs/kg = 1000 Gs

def test_recipe_batch_cost_missing_price_returns_none(make_ingredient, db_session):
    """If any line lacks purchase_price_gs, batch cost is None."""
    flour = make_ingredient("Flour", purchase_price_gs=None)
    recipe = Recipe(name="Muffin", yield_qty=12, yield_unit="und")
    db_session.add(recipe)
    db_session.flush()
    db_session.add(RecipeLine(recipe_id=recipe.id, ingredient_id=flour.id, qty=500))
    db_session.flush()
    
    cost = recipe_batch_cost_gs(db_session, recipe.id)
    assert cost is None  # Missing price flagged

def test_product_unit_cost_scales_by_yield(make_ingredient, db_session):
    """Batch of 12 muffins costs 24_000 Gs → unit cost 2_000 Gs."""
    flour = make_ingredient("Flour", purchase_price_gs=48000)  # 48000 Gs/kg
    recipe = Recipe(name="Muffin", yield_qty=12, yield_unit="und")
    db_session.add(recipe)
    db_session.flush()
    db_session.add(RecipeLine(recipe_id=recipe.id, ingredient_id=flour.id, qty=500))  # 500g
    db_session.flush()
    product = Product(name="Muffin", portion_label="1 muffin", sale_price_gs=8000, recipe_id=recipe.id)
    db_session.add(product)
    db_session.flush()
    
    unit_cost = product_unit_cost_gs(db_session, product.id)
    assert unit_cost == 2000  # (500g × 48 Gs/g) / 12 muffins = 2000 Gs

def test_product_margin_with_full_pricing(make_ingredient, db_session):
    product = make_product_with_recipe(...)
    margin_gs, margin_pct = product_margin(db_session, product.id)
    assert margin_gs == 6000  # 8000 - 2000
    assert abs(margin_pct - 0.75) < 0.001  # 6000/8000

def test_product_margin_with_missing_price_returns_none(...):
    """When recipe has missing ingredient price, margin is None."""
    # ...

def test_apply_sale_drops_stock_proportionally(make_ingredient, db_session):
    """Sale of 2 muffins drops flour by 2 * (flour_per_batch/12)."""
    flour = make_ingredient("Flour", stock_qty=1000, purchase_price_gs=2000)
    recipe = make_recipe_with_lines(...)
    product = make_product(...)
    db_session.flush()
    
    initial_stock = flour.stock_qty
    sale = apply_sale(db_session, product.id, qty=2, sold_at=now())
    new_stock = flour.stock_qty
    
    assert new_stock == initial_stock - 2 * (500 / 12)  # 2 muffins × (500g/12 muffins)

def test_apply_sale_without_recipe_does_not_drop_stock(...):
    """Sale without recipe creates sale row but no stock moves."""

def test_apply_sale_with_zero_recipe_yield_does_not_drop_stock(...):
    """Recipe with yield_qty=0 should not crash; skip the move."""

def test_apply_sale_with_multiple_ingredients_drops_all_proportionally(...):
    """Multi-ingredient recipe; check each ingredient drops correctly."""

def test_apply_sale_negative_qty_raises(...):
    """qty must be positive. Negative would create phantom sales."""
```

## `test_stock_drop.py` (5+ tests)

```python
def test_sale_stock_move_recorded_on_sale(...):
    """Verify the sale_stock_move row is created with correct qty_delta."""

def test_void_sale_reverses_stock_drop(...):
    """Void restores ingredient.stock_qty to pre-sale value."""

def test_void_sale_deletes_sale_stock_moves(...):
    """Void doesn't leave orphan moves."""

def test_void_already_voided_sale_is_noop(...):
    """Voiding twice doesn't double-restore stock."""

def test_multiple_sales_accumulate(...):
    """3 sales × 2 muffins = 6 muffins worth of stock dropped."""
```

## `test_import_roundtrip.py` (3+ tests)

```python
def test_import_mini_xlsx_creates_ingredients(db_session, mini_workbook):
    """3 ingredients in mini.xlsx appear in DB after import."""

def test_import_then_export_then_import_same_counts(db_session, mini_workbook):
    """Roundtrip preserves ingredient/recipe counts."""

def test_import_with_unmappable_rows_skips_with_count(db_session, tmp_path):
    """Workbook with ING-9999 reference returns skipped list, doesn't fail."""
```

## `test_void_sale.py` (3+ tests)

```python
def test_void_restores_sale_stock_moves(...):
    """Void reverses the stock moves AND the sale row remains (audit)."""

def test_void_after_restock_handles_correctly(...):
    """If she restocked between sale and void, void shouldn't double-add."""
    # Implementation: void = negative sale OR explicit reversal of last move

def test_void_with_zero_qty_sale(...):
    """Sale of 0 (e.g., testing) voids cleanly."""
```

## `test_healthz.py` (2+ tests)

```python
def test_healthz_returns_ok(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "aiw-saskia-rms"}

def test_healthz_db_returns_journal_mode(client):
    response = client.get("/healthz/db")
    assert response.status_code == 200
    data = response.json()
    assert data["db"] == "ok"
    assert data["journal_mode"] == "wal"
```

## When to run

- **Local pre-commit**: Run pytest before each `git commit`. Local pre-push hook enforces this.
- **Local pre-PR**: Run full pytest before opening a PR.
- **CI**: skip for fase 1 (overkill).

## Pre-push hook

`scripts/pre-push` (or just rely on discipline):

```bash
#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."
echo "Running pytest..."
python -m pytest app/tests/ -v --tb=short
echo "✓ Tests pass. Pushing."
```

## What this does NOT do

- ❌ No CI (GitHub Actions). Local discipline only.
- ❌ No coverage threshold enforcement. Aim for >80%, but don't block on it.
- ❌ No mutation testing. Out of scope.

## Time spent

- 30 min: conftest.py + fixture scaffolding
- 30 min: test_money.py + test_units.py (pure functions, fast)
- 30 min: test_costing.py (recipe scenarios)
- 15 min: test_stock_drop.py + test_void_sale.py
- 15 min: test_import_roundtrip.py + mini.xlsx fixture

**Total: ~2h** as estimated, distributed across Tasks 1-6.

---

*End of spec. To be applied continuously during Tasks 1-6 of the dev plan when the build starts.*


---

# Review-round feedback channel

_Source: original at `saskia-preflight/spec-feedback-channel.md`_

# Feedback channel spec — review round 1

> **For Kiki and Ivan.** Implementation spec for capturing Saskia's review-round-1 feedback as durable artifacts in the engagement repo. Lands at Task 10 (review rounds).
>
> **Source:** improvements review §5.1, §6.5.
>
> **Cost:** ~30 min setup + ongoing use.

---

## What this does

Instead of WhatsApp lists that get lost, the review-round-1 feedback is captured as a markdown file in `saskia/docs/sessions/round-1-feedback.md`. Each feedback item has structure: severity, description, repro steps, screenshot. Items get ticked off as fixed. The file becomes the working agreement between Saskia and the build team.

## Why

WhatsApp is informal. Lists get lost. No version control. No clear "fixed vs not fixed" state. After 50 items in a WhatsApp chat, the team can't tell what's done.

## Template

```markdown
# Round 1 feedback — capture and resolution

**Period:** 2026-09-DD to 2026-09-DD (5 days of testing)
**Tester:** Saskia
**Build version:** v0.1 (commit SHA at start)
**Capture date:** 2026-09-DD

## How to use

1. Saskia adds items below using the template
2. Ivan or Kiki reviews, sets status
3. Items get fixed in PRs
4. Fixed items get ticked + commit SHA noted
5. When round 1 closes, this file becomes the diff against v0.1

## Status legend

- **OPEN** — not yet reviewed
- **ACCEPTED** — in scope, will fix
- **OUT-OF-SCOPE** — fase 2 or separate quote
- **DEFERRED** — fase 1.5 or later
- **FIXED** — implemented; commit SHA noted
- **WONT-FIX** — explicitly rejected with reason

---

## Items

### #001 — <short title>

**Severity:** blocker | major | minor | cosmetic
**Status:** OPEN
**Reported:** 2026-09-DD

**What:** <one-paragraph description>

**Repro:**
1. <step 1>
2. <step 2>
3. <expected vs actual>

**Screenshot:** <attached or linked>

**Saskia says:** <verbatim if useful>

**Build team:** <response>

---
```

## Saskia's instructions (Spanish, for WhatsApp)

```
Para revisar el sistema durante la semana que viene:

1. Usalo como si fuera tu sistema real: vendé, registrá, 
   importá, exportá.
2. Cada vez que algo se comporta raro o falta algo, mandame
   un mensaje con:
   - Qué estabas haciendo (pasos para repetir)
   - Qué esperabas que pase
   - Qué pasó en realidad
   - Si podés, una captura de pantalla
3. Una vez por día te mando el archivo round-1-feedback.md
   en Drive para que pongas tus items ahí. Así no se pierden
   en el chat.
4. Lo revisamos juntos al final de la semana y decidimos
   qué arreglamos en esta fase vs qué va para fase 2.

Si algo es bloqueante (te impide trabajar), avisame YA, 
no esperes al final de la semana.
```

## Kiki's workflow

When a feedback item lands:

1. Triage within 24h: OPEN → ACCEPTED / OUT-OF-SCOPE / DEFERRED / WONT-FIX
2. ACCEPTED items get a "Build team" comment with the planned fix
3. Each fix lands as its own commit, with `Refs #NNN` in the commit message
4. After fix is in production, update the item: status FIXED, commit SHA

## Example lifecycle

```markdown
### #001 — Sale of 0 muffins crashes the form

**Severity:** major
**Status:** FIXED
**Reported:** 2026-09-15
**Fixed:** 2026-09-17, commit `abc1234`

**What:** When you try to register a sale with quantity 0, 
the form freezes and you have to reload.

**Repro:**
1. Productos → Muffin
2. Cantidad → 0
3. Click "Registrar venta"
4. Browser tab freezes

**Screenshot:** see Drive `round-1-feedback/screenshots/001.png`

**Saskia says:** "Puse 0 por error y se quedó colgado"

**Build team:** Added qty > 0 validation in Task 5. 
Fixed in commit abc1234.

---

### #002 — Dashboard "hoy" includes tomorrow's early sales

**Severity:** minor
**Status:** OPEN
**Reported:** 2026-09-15

**What:** When I sell past midnight, the next day's morning
shows the previous night's sales in "hoy."

**Repro:** (not tested, but reported)

**Build team:** Pending review. Likely a UTC-4 timezone
fix in dashboard query.
```

## Storage

- **Source of truth:** `saskia/docs/sessions/round-N-feedback.md` in the engagement repo (committed)
- **Mirror:** copy to her Drive folder for her reading
- **No WhatsApp-only state.** Always persisted.

## Review round 2 (similar but cosmetic)

Round 2 follows the same template but the focus is on **Spanish copy + UX**, not functional bugs. See dev plan §9 Task 10.

## What this does NOT do

- ❌ Does NOT replace the dev plan §10 review rounds. It just adds structure to them.
- ❌ Does NOT track every line of feedback forever. After fase 1 closes, the file becomes historical.

## Time spent

- 15 min: create template file
- 15 min: send Saskia her instructions

**Total: ~30 min** as estimated.

---

*End of spec. To be applied at Task 10 of the dev plan.*


---

# Code-review checklist for fase 1 PRs

_Source: original at `saskia-preflight/code-review-checklist.md`_

# Code-review checklist for fase 1 PRs

> **For Kiki (and any future reviewer).** Use this checklist when reviewing any PR to `saskia/app/`. Each item has a reason; blocking items must be addressed before merge.
>
> **Source:** improvements review §6.

---

## Blocking (must pass)

### Money and costing

- [ ] **No float in money calculations.** `Decimal` only for amounts > 0.
- [ ] **No intermediate rounding.** Round at persistence site, not in the calculation chain.
- [ ] **Rounding mode is HALF_UP, not banker's.** `Decimal.quantize(Decimal("1"), rounding=ROUND_HALF_UP)`.
- [ ] **All money is integer Gs.** in the DB. UI formats with `format_gs()` and period-as-thousands-separator.
- [ ] **Costing engine matches `app/rms/costing.py` tests.** No manual calc in the route that bypasses the engine.

### Data integrity

- [ ] **No silent overwrite of SQLite.** Every write that affects >1 row uses an explicit transaction.
- [ ] **No wipe of `sale` or `sale_stock_move` rows.** Import is additive; void reverses stock_moves but doesn't delete sales.
- [ ] **Foreign keys enforced.** `PRAGMA foreign_keys=ON` confirmed in `app/rms/db.py`.
- [ ] **WAL mode confirmed.** `PRAGMA journal_mode=WAL` on every connection.

### Security

- [ ] **Bind to 127.0.0.1 only.** `app/rms/main.py` has the assertion that refuses other binds.
- [ ] **No secrets in source.** No `.env`, no API keys, no passwords. If a secret is needed, it's in the `~/.config/aiw-saskia/` config dir, not in git.
- [ ] **No PII from `saskia-personal-context/`** in the public repo. OPSEC contract applies.
- [ ] **No live customer PII** (names, phones, addresses of buyers). AGENTS.md rule #4.

### UX correctness

- [ ] **Timezone is Asunción** (`America/Asuncion`), not system-local. `zoneinfo.ZoneInfo("America/Asuncion")` in any `datetime.now()`.
- [ ] **Period toggle uses calendar boundaries.** "month" = 1st to last day of Asunción local month.
- [ ] **Negative stock is allowed but visible.** Red flashing when stock < 0, yellow when 0 ≤ stock < min.
- [ ] **Void semantics documented.** Reverses the last applied stock move OR records as a negative sale (operator-decided, but consistent).

### Spanish copy

- [ ] **All UI strings come from `app/docs/copy-vos.md`.** No inline strings.
- [ ] **No Argentine forms** ("salvá", "tenés" with different idioms, etc.). Paraguayan vos only.
- [ ] **Money format** "Gs. X.YYY.ZZZ" with period thousands sep, no decimals.
- [ ] **Date format** DD/MM/YYYY.
- [ ] **Empty states have copy** (not just blank pages).

### Tests

- [ ] **New logic has pytest coverage.** Test the failure modes, not just the happy path.
- [ ] **Imports tested with synthetic mini.xlsx** (NOT the real Drive file). `tests/fixtures/mini.xlsx`.
- [ ] **Roundtrip test passes:** import mini → export → import again → same counts.

---

## Non-blocking (should fix but can ship)

- [ ] **Test names describe behavior**, not implementation. `test_apply_sale_drops_stock_for_recipe_with_two_ingredients` not `test_apply_sale_case_3`.
- [ ] **Doc strings on public functions.** Even one-liner "what does this return" helps.
- [ ] **No magic numbers.** Constants in `app/rms/config.py`.
- [ ] **SQL queries use SQLAlchemy ORM** for type safety. Raw SQL only for performance-critical paths (and commented).

---

## Out of scope (don't add)

- ❌ **Authentication / login.** Fase 1 is single-user.
- ❌ **Multi-machine sync.** Fase 2.
- ❌ **HTTPS / TLS.** Local-only on 127.0.0.1.
- ❌ **Recipe versioning.** Fase 1.5.
- ❌ **WhatsApp integration.** Fase 2+.
- ❌ **Planning assistant.** Fase 2+ (Gs. 9.5M parked).
- ❌ **Public website.** Fase 2+.

If a PR adds any of these, **automatic rejection** with comment "out of scope, see AGENTS.md rule #1-6."

---

## How to use this

1. Open the PR
2. Walk through blocking items top to bottom
3. Mark ✅ or ❌ per item, with a comment if ❌
4. If any blocking item is ❌, request changes before review
5. If all blocking ✅, optionally walk non-blocking items as suggestions
6. Approve and merge

For larger PRs (>500 lines), split into multiple reviews per logical chunk.

---

*Drafted 2026-09 by Hermes. To be applied during fase 1 build, weeks 1-8.*

