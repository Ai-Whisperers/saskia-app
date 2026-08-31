# Saskia RMS — Fase 1 app

> **The RMS app source code** for Saskia Weiss Vander — built per `docs/plans/2026-08-31-rms-fase-1-dev-plan.md`. Installs on her PC, runs at `127.0.0.1:8765`, no hosting.
>
> **Companion repo:** `Ai-Whisperers/saskia-context` (engagement + personal data, private)

## What this repo is

Just the code. No PII. No bank statements. No family context. Just the
build brief, the source tree, the tests, and the installer.

The "who is Saskia and what does she need" context is in
`Ai-Whisperers/saskia-context`. Kiki (or whoever builds) does NOT need
that repo. She reads this one.

## What's in here

```
pyproject.toml           # Python 3.13, FastAPI 0.115, uvicorn[standard], etc.
LICENSE                  # MIT
.gitignore
.pre-commit-config.yaml
.github/workflows/ci.yml # GitHub Actions: ruff + pytest + coverage gate

app/
  README.md              # app-level orientation
  rms/                   # core: db, models, money, units, costing, main
  routers/               # health, dashboard, products, recipes, inventory, sales, excel_io
  services/              # auto_backup, import_xlsx, export_xlsx, reports
  templates/             # server-rendered HTML (Spanish)
  static/
  docs/                  # app-level docs (architecture, copy-vos.md, etc.)
  installer/             # run.bat + run.sh + install checklist

tests/
  conftest.py
  test_money.py          # Decimal helpers
  test_units.py          # Unit enum
  test_costing.py        # recipe_batch_cost, product_unit_cost, margin
  test_stock_drop.py
  test_import_roundtrip.py
  test_void_sale.py
  test_healthz.py
  fixtures/mini.xlsx

docs/
  plans/                 # dev plan
  operations/            # build specs, import-mapper, discovery prompt
  sessions/              # round-2 review template

installer/
  README.md              # install-session checklist
  run.bat                # Windows launcher (run.sh when Mac confirmed)
```

## How to install

See `installer/README.md`. Quick start:

```bash
git clone https://github.com/Ai-Whisperers/saskia-app.git
cd saskia-app
uv sync --all-extras
uv run pytest tests/    # should pass
uv run uvicorn app.rms.main:app --host 127.0.0.1 --port 8765
```

## Status

- **Pre-signoff skeleton landed** (commit `f82dfb3` in the original engagement repo, before the split).
- **Build clock:** does not start until quote signed + first cuota + Drive + PC named.

See the build specs in `docs/operations/` for what Task 1-10 of the dev plan each produces.

## Cross-references

- Build plan: `docs/plans/2026-08-31-rms-fase-1-dev-plan.md`
- Build specs: `docs/operations/2026-09-fase-1-specs.md`
- Tech-stack alternatives: `docs/operations/2026-09-tech-stack-review.md` (also in `saskia-context`)
- Comprehensive improvements: `docs/operations/2026-09-comprehensive-improvements-review.md` (also in `saskia-context`)
- Operator pre-signoff checklist: `docs/operations/2026-09-fase-1-prep.md` (also in `saskia-context`)
- Round 2 review template: `docs/sessions/round-2-feedback.md`

---

_Maintained by Ivan / Kiki. Visibility: **PUBLIC** on GitHub (no PII; build-only)._
_Last update: 2026-09 (post-split from Ai-Whisperers/saskia)._
