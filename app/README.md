# app/ — Saskia RMS Fase 1

> **Local restaurant-management app** for Saskia Weiss Vander — installed on her PC, running at `127.0.0.1:8765`, no hosting, no monthly fee.
>
> **Repo:** `Ai-Whisperers/saskia`
> **Engagement:** Fase 1, Gs. 17.500.000 / 24 cuotas (per `docs/CURRENT-CONTEXT.md`)
> **Plan:** `docs/plans/2026-08-31-rms-fase-1-dev-plan.md`
> **Specs:** `docs/operations/2026-09-fase-1-specs.md`

## What's in here (after build complete)

```
app/
  README.md                 # this file
  CHANGELOG.md              # app-level changelog (separate from repo-level)
  pyproject.toml            # at repo root, not here
  rms/
    __init__.py
    config.py               # paths, ports, env vars
    db.py                   # engine, session, pragmas, versioned migrations
    models.py               # SQLAlchemy ORM (ingredient, recipe, product, sale, ...)
    money.py                # Decimal helpers + Gs. formatting (Paraguayan convention)
    units.py                # Unit enum (g/kg/ml/l/und) with aliases
    costing.py              # recipe_batch_cost_gs, product_unit_cost_gs, etc.
    main.py                 # FastAPI app, lifespan, router mounts
  routers/
    health.py               # /healthz and /healthz/db
    dashboard.py            # Inicio (today/week/month sales, ranking, alerts)
    products.py             # Productos y precios (CRUD)
    recipes.py              # Recetas (CRUD)
    inventory.py            # Inventario (CRUD)
    sales.py                # Ventas (entry + void)
    excel_io.py             # Import/export
  services/
    auto_backup.py          # On-startup backup to ~/Documents/AIW-Saskia/backups/
    import_xlsx.py          # Drive-Excel -> SQLite
    export_xlsx.py          # SQLite -> Excel
    reports.py              # Monthly stock-out, monthly close
  templates/
    base.html               # layout; child templates extend it
    inicio.html
    productos.html
    recetas.html
    inventario.html
    ventas.html
    excel.html
    reports/
      stockout.html
  static/
    app.css
  docs/
    copy-vos.md             # Paraguayan Spanish UI copy bank (filled by Saskia/Kiki)
    architecture.md         # data flow, sources of truth, update paths
    auto-backup-spec.md     # mirrors docs/operations/2026-09-fase-1-specs.md
  installer/
    README.md               # install-session checklist (Task 9)
    run.bat                 # Windows: venv + uvicorn + start browser
    shortcut-template.bat   # desktop shortcut generator
tests/
  conftest.py
  test_money.py             # Decimal + format + parse
  test_units.py             # Unit enum + aliases + conversions
  test_costing.py           # recipe_batch_cost, product_unit_cost, margin
  test_stock_drop.py        # apply_sale, void_sale, stock moves
  test_import_roundtrip.py  # import -> export -> import (with synthetic mini.xlsx)
  test_void_sale.py         # void semantics (per improvements §6.2)
  test_healthz.py           # /healthz and /healthz/db
  fixtures/
    mini.xlsx               # synthetic, never her real Drive file
```

## What's here NOW (this commit)

The empty skeleton with:
- `rms/money.py` — Decimal helpers (per spec §A)
- `rms/units.py` — Unit enum (per spec §B)
- `rms/__init__.py`
- `routers/health.py` — /healthz + /healthz/db (per spec §C)
- `services/auto_backup.py` — auto-backup on startup (per spec §1)
- `tests/conftest.py`, `tests/test_money.py`, `tests/test_units.py` — per spec §9
- `docs/copy-vos.md` — UI copy bank template (needs Kiki or Saskia to fill)
- `installer/README.md` — install-session checklist
- `installer/run.bat` — Windows launcher

Other modules are placeholders / will be added by Kiki per the dev plan tasks.

## How to run (after build complete)

**Windows:**
```cmd
cd %USERPROFILE%\path\to\saskia
run.bat
```

**Mac/Linux:**
```bash
cd /path/to/saskia
uv sync
uv run uvicorn app.rms.main:app --host 127.0.0.1 --port 8765 --reload
```

Browser opens to http://127.0.0.1:8765 automatically.

## How to test

```bash
uv sync --all-extras
uv run pytest --cov=app
```

Coverage target: >80% (CI fails below).

## Operator note (recorded in this commit)

This `app/` skeleton was committed to the engagement repo before the four
clock-pause conditions in `docs/plans/2026-08-31-rms-fase-1-dev-plan.md §0`
were satisfied (signed quote + first cuota + Drive + PC named). This was
done at explicit operator override. The 70h build clock is NOT yet running.
Any further work on `app/` after the operator override is still subject to
the §0 gate.

See `docs/operations/2026-09-tech-stack-review.md` for the rationale of
the chosen stack (uv, FastAPI, SQLite, openpyxl, etc.).
