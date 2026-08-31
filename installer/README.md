# Saskia RMS — install-session checklist

> **For Kiki (or whoever runs the install).** Per `docs/plans/2026-08-31-rms-fase-1-dev-plan.md §9 Task 9` and the comprehensive improvements review.
>
> **Total time:** ~45-90 minutes depending on how many troubleshooting items arise.

---

## Pre-install (operator-side, before session)

- [ ] Quote signed, first cuota credited (per §0 pre-build gate)
- [ ] Saskia has confirmed **OS: Windows / Mac** (single message on WhatsApp)
- [ ] Saskia has confirmed admin rights to install Python/uv
- [ ] Drive folder identified (Google Drive with the 5 xlsx files)
- [ ] V1 product list received (per intake answers-from-meetings)
- [ ] Empty backup folder created in her Documents / Drive-synced location
- [ ] GitHub PAT for any post-install fixes loaded

## Equipment check (5 min)

- [ ] Computer boots, OS matches what she told us
- [ ] Internet connection works (for `uv` install + dep download)
- [ ] Drive folder URL works in her browser (verified by opening once)
- [ ] We have admin password or PIN for software installs

## Step 1 — Install Python via `uv` (if not present) (10 min)

```cmd
# Windows PowerShell
irm https://astral.sh/uv/install.ps1 | iex
```

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Verify: `uv --version` returns 0.5.x or newer.

If `uv` install fails (corporate proxy / etc.), fall back to official Python 3.13 from python.org and continue with `pip` (we lose the lockfile benefit but the app still runs).

## Step 2 — Get the code (5 min)

```cmd
cd %USERPROFILE%\Documents
git clone https://github.com/Ai-Whisperers/saskia.git
cd saskia
```

(or for Mac: `cd ~/Documents && git clone ... && cd saskia`)

If she doesn't have `git`, install it from git-scm.com first. (Most modern macOS has it; Windows usually doesn't.)

## Step 3 — Install dependencies + verify (5 min)

```bash
uv sync --all-extras
```

This installs FastAPI, uvicorn[standard], SQLAlchemy, openpyxl, jinja2, pydantic, loguru, pytest, hypothesis, ruff. **Expected time:** ~30 seconds (uv is fast).

Verify:

```bash
uv run pytest tests/test_money.py tests/test_units.py -v
```

Should show **88 tests passed**. If any fail, **STOP** and investigate before continuing.

## Step 4 — Initialize the database (5 min)

```bash
uv run python -c "from app.rms.db import init_db; init_db(); print('DB initialized')"
```

(Will fail until `db.py` is implemented. Defer to when Kiki implements Task 1.)

## Step 5 — Configure backup folder (5 min)

The app's auto-backup lands at `~/Documents/AIW-Saskia/backups/` by default. Create that folder:

```bash
mkdir -p ~/Documents/AIW-Saskia/backups
```

If she wants a different location (e.g., a Drive-synced folder like `~/Library/CloudStorage/GoogleDrive-.../My Drive/AIW-Saskia/backups/`), set it in `~/.config/aiw-saskia/backup.toml` later.

## Step 6 — Create the desktop shortcut (5 min)

**Windows:** Create `C:\Users\<saskia>\Desktop\Gestión Saskia.lnk` pointing to:
- Target: `C:\Users\<saskia>\Documents\saskia\installer\run.bat`
- Start in: `C:\Users\<saskia>\Documents\saskia\`
- Icon: optional (folder icon)

**Mac:** Create `/Users/saskia/Desktop/Gestión Saskia.command` (AppleScript-able):
```bash
#!/bin/bash
cd /Users/saskia/Documents/saskia
uv run uvicorn app.rms.main:app --host 127.0.0.1 --port 8765
open http://127.0.0.1:8765
```
Make executable: `chmod +x ~/Desktop/Gestión\ Saskia.command`

## Step 7 — First run + smoke test (10 min)

Double-click the shortcut. Expected sequence:
1. Terminal / cmd window opens (uvicorn starts)
2. Browser opens to http://127.0.0.1:8765
3. Spanish landing page appears: "Sistema de gestión — local"
4. /healthz returns `{"status": "ok", "service": "aiw-saskia-rms"}`
5. /healthz/db returns `{"db": "ok", "journal_mode": "wal"}`

If anything fails, see [Troubleshooting](#troubleshooting) below.

## Step 8 — Teach her the daily flow (15 min)

Walk her through:
1. **Add an ingredient:** Inventario → Agregar ingrediente. Use a real one (e.g., "Harina de trigo"). Set unit = `g`, purchase price = whatever she paid.
2. **Add a recipe:** Recetas → Nueva receta. Pick an existing one (e.g., Muffin de chocolate). Add 3-5 ingredients with quantities.
3. **Check the dashboard:** Inicio should now show a "Stock bajo" alert (if any min_stock is below current) and the recipe cost calculated from your ingredient prices.
4. **Register a sale:** Ventas → Nueva venta → pick the product, qty 1, guardar.
5. **See the inventory drop:** Inventario → the ingredient you used should have a new stock_qty.

## Step 9 — Online/offline test (5 min)

- Disconnect Wi-Fi.
- App should still work (everything is local).
- Reconnect.
- Auto-backup should fire on next app start if last backup > 24h.

## Step 10 — Hand-off

Tell her:
- The shortcut is on her desktop. Double-click to start.
- The data lives in `%LOCALAPPDATA%\AIW-Saskia\` (Windows) or `~/Library/Application Support/AIW-Saskia/` (Mac). Don't delete.
- Auto-backup is set up. Files land in `~/Documents/AIW-Saskia/backups/`.
- For support: WhatsApp Ivan.

## <a id="troubleshooting"></a>Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| "Python is not recognized" | PATH not set | Re-install Python with "Add to PATH" checked, or use `uv` (manages its own) |
| `uv sync` fails with "permission denied" | AV blocks the operation | Add the project folder to AV exclusions |
| Browser shows blank page | uvicorn didn't start | Check terminal window for traceback; usually a missing dependency |
| `127.0.0.1:8765` refused | uvicorn bound to 0.0.0.0 by mistake | We hardcode 127.0.0.1 in main.py; should never happen |
| `/healthz/db` returns 503 | SQLite file is locked by another process | Close other instances of the app; check no backup tool is locking the .sqlite file |
| Stock not dropping on sale | Recipe has no lines (qty 0) or ingredient missing | Verify recipe has at least one line; verify the ingredient exists |

## Done criteria

- [ ] `uv run pytest` shows all tests passing
- [ ] App launches from desktop shortcut
- [ ] Browser shows Spanish landing page
- [ ] /healthz/db returns 200 with `"journal_mode": "wal"`
- [ ] She can add an ingredient + recipe + sale end-to-end
- [ ] Auto-backup file appears in `~/Documents/AIW-Saskia/backups/`
- [ ] She can find the shortcut, the data folder, and the backup folder

Once all are checked, the install session is complete. Schedule Round 1 review for 3-5 days later.
