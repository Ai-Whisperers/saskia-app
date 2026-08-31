# Architecture — Saskia RMS

> **For Kiki and any future agent.** Explains the data flow, sources of truth, and
> update paths. Read this before making changes that affect how data moves through
> the system.

## Data flow diagram

```
   ┌─────────────────────┐
   │ HEREBUS_FoodBiz.xlsx │   ← Source of truth (operator-side, in her Drive)
   │ HEREBUS_Suppliers.xlsx│
   │ HEREBUS_Analisis.xlsx │
   └──────────┬──────────┘
              │ (she copies to local path; app imports)
              ▼
   ┌─────────────────────┐
   │   app/rms/models.py │   ← SQLite schema (7 tables + app_meta)
   │   SQLite on her PC  │
   └──────────┬──────────┘
              │ (uvicorn renders via Jinja2)
              ▼
   ┌─────────────────────┐
   │  Spanish UI at      │   ← Single-user, single-PC
   │  http://127.0.0.1:8765
   └─────────────────────┘

   Backups (parallel):
   - On startup → ~/Documents/AIW-Saskia/backups/*.xlsx (auto-export, 30-day)
   - On startup → Cloudflare R2 encrypted snapshot (24h threshold, free tier)
   - Export anytime from UI → ~/Documents/AIW-Saskia/exports/*.xlsx (manual)
```

## Sources of truth (and what is NOT a source of truth)

| Data | Source of truth | NOT a source of truth |
|---|---|---|
| Recipes + ingredients | SQLite (after import) | The Excel xlsx files (they're snapshots) |
| Sale history | SQLite | UI dashboard (it's computed) |
| Stock levels | SQLite (after sale/import) | Real-world kitchen (this is theoretical stock) |
| Ingredient purchase prices | SQLite (after Saskia enters) | Default values in xlsx (could be empty) |
| Dashboard numbers | Computed from SQLite on every render | Cached anywhere |
| Recipe cost | Computed from ingredient prices + lines | Hardcoded anywhere |
| Product margin | Computed from sale price + cost | Cached |

## Read paths (always)

1. UI request → uvicorn → FastAPI router → SQLAlchemy query → SQLite → render Jinja2 → browser.

## Write paths (rare, deliberate)

1. UI form submit → FastAPI form handler → Pydantic validation → SQLAlchemy session → SQLite transaction.
2. Re-import → UI button → file picker → `import_xlsx.from_file()` → confirmation modal → `apply_import()` (with pre-import auto-backup).
3. Sale save → `apply_sale()` atomic transaction → sale + sale_stock_move rows.
4. Sale void → `void_sale()` atomic transaction → reverses all stock moves for that sale.

## Update paths (when source changes)

- **She edits the Drive xlsx** → next time she clicks "Importar" in the UI → confirmation modal → diff displayed → she confirms → SQLite updates (additive by name match, never wiping sales).
- **She edits in the app** → SQLite is updated directly → next "Exportar" creates a new xlsx in `~/Documents/AIW-Saskia/exports/`. That file becomes the new snapshot for the next import round.
- **She fixes a typo in a recipe** → UI form submit → SQLite updated → no other action needed.

## Concurrency model

- **One user at a time.** No concurrent edits. Single `uvicorn` worker. SQLite WAL
  allows one writer + many readers within the same process, but since we have one
  user, this is moot.
- **No transactions span HTTP requests.** Each form submit is one transaction. Auto-commit
  after success. Rollback on exception.

## Timezone handling

- **Source of truth:** Asunción local time (UTC-4, no DST).
- **DB stores:** UTC datetime.
- **UI displays:** Asunción local.
- **Conversion:** `app/rms/config.py:ASUNCION_TZ = ZoneInfo("America/Asuncion")`.

## Money handling

- **DB stores:** integer Gs.
- **In-app:** `Decimal` (never `float`).
- **Persistence:** `app/rms/money.py:to_int_gs()` is the ONLY allowed path.
- **Display:** `app/rms/money.py:format_gs()` (Paraguayan: `Gs. 1.234.567`).
- **Parsing user input:** `app/rms/money.py:parse_gs()` (strict; rejects negatives, decimals).

## Error handling

- All router functions catch exceptions and render Spanish error pages.
- All unhandled exceptions are logged with traceback to `app.log` (local, not cloud).
- Auto-backup runs BEFORE destructive operations (re-import, mass-delete) — never
  after, never without a backup snapshot.
