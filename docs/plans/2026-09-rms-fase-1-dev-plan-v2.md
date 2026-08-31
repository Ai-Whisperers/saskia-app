# RMS fase 1 — development plan (Saskia) — v2

> **For the delivery team:** this is the canonical build plan for the signed quote.
> **Supersedes** `2026-08-31-rms-fase-1-dev-plan.md` (which it preserves in spirit while filling
> gaps surfaced during the 2026-09 comprehensive review, the tech-stack review, and 7-hats critique).
>
> Do not implement the planning assistant, website, WhatsApp bot, or dedicated Hermes
> from this document.

**Goal:** Ship a **Spanish (vos), single-user restaurant management system that runs on Saskia's
PC**: products, prices, recipes, inventory, sales, low-stock alerts, a numbers dashboard —
loaded from her Drive Excels, with Excel export as backup, **and an encrypted offsite
backup to Cloudflare R2** for disaster recovery.

**Architecture:** Local app on her machine. SQLite file on disk with WAL + secure_delete.
UI in the browser at `http://127.0.0.1:8765` (not public, not hosted). Python services
import/export `.xlsx`. **No cloud account, no monthly server, no third-party SaaS.** Encrypted
backups to Cloudflare R2 free tier (10 GB-month) for offsite redundancy. Theoretical stock
drop on each saved sale. Money in **integer Gs.** (no cents).

**Tech stack (locked for this plan):** Python 3.13 (pinned `>=3.13,<3.14`) · FastAPI 0.115 ·
SQLite 3 · SQLAlchemy 2.0 sync · openpyxl 3.1 · Jinja2 · loguru · `uv` for install ·
pytest + hypothesis for tests · ruff for lint · pre-commit hooks · GitHub Actions CI.
Windows first (Mac supported; `run.sh` deferred to Task 9 when OS is confirmed).
Start via `run.bat` + desktop shortcut. **No HTMX, no React, no Vue, no Tailwind, no Docker,
no Alembic, no async.**

**Calendar:** **6–8 weeks** after first cuota + Drive + PC (quote). Budget: **70 h** at
Gs. 250.000/h. **The clock starts when the four gate conditions are met** (signed quote +
first cuota credited + Drive read access + work PC named); see §13.

---

## 0. Global constraints (hard rules)

These are non-negotiable. Any PR that violates them is auto-blocked by code review.

1. **Product is local RMS**, not a website, not table POS/KDS/card terminal, not SET,
   not WhatsApp bot.
2. **Dedicated Hermes / own VPS is John's SKU.** Do not build or estimate it here.
3. **Planning assistant (producción + compras + calendario, 38 h / Gs. 9.500.000) is
   parked.** Do not sneak it into fase 1 screens.
4. **UI copy: Spanish, vos.** Every user-facing string comes from
   `app/docs/copy-vos.md` (filled by Kiki or Saskia before Task 3).
5. **OPSEC: do not commit workbooks, IDs, banks, or PII** from `saskia-personal-context`.
   Map columns from `04_foodbiz-management-system/tabs/*.md` locally; import from a
   **copy** of Drive files she provides. **Incident response:** if any PII appears in
   a PR, the reviewer MUST block and rotate the relevant tokens (see §14).
6. **Money is integer Gs.** Every money column in DB is `INTEGER`. Every money
   calculation uses `Decimal` for intermediate values. The ONLY allowed persistence
   path for money is `app/rms/money.py:to_int_gs()` (round half-up). Any other
   integer-cast path requires explicit comment + reviewer approval.
7. **Money display uses Paraguayan convention:** `Gs. 1.234.567` (period as thousands
   sep, no decimals). Use `format_gs()` and `parse_gs()` only.
8. **No float money.** Use `Decimal`. See `app/rms/money.py` for the discipline.
9. **Timezone is Asunción (UTC-4, no DST).** All "today / week / month" boundaries
   use Asunción local time. See §11.
10. **Recipes and selling prices: no silent overwrite.** Import is a first load + explicit
    re-import she confirms. The re-import UI must (a) show what will be overwritten,
    (b) require explicit user OK, (c) auto-backup before applying.
11. **Quote includes 2 review rounds + onboarding on that machine.** No additional
    features during review rounds. Cosmetic changes only if hours remain.
12. **Production does not start until first cuota is in + Drive read access + work PC
    named + V1 product list received.** §13 defines pre-flight exceptions.
13. **Free tier is free tier.** No vendor moves PII off her laptop unless explicitly
    approved (Tier 8: encrypted Cloudflare R2 backup, $0, is the only approved cloud
    dependency).

---

## 1. What "done" means (acceptance)

She can sit at **her** PC, open the app, and without us:

1. See **today / week / month** sales, cost of goods from recipes, **margin**, and a
   **ranking** of what leaves more money.
2. See **red alerts:** stock below her minimum, recipes missing an ingredient price,
   sales with no recipe.
3. Edit **products** (name, portion, sale price Gs.), see **cost from recipe** and
   margin Gs. + %.
4. Create/edit **recipes** (ingredients, quantities, yield/portions). **Sub-recipes
   (e.g., Masa choux used in a pastry) are imported via the polymorphic recipe_line
   mechanism** (see §5).
5. Edit **inventory** (stock, purchase price Gs., **min stock** she defines).
6. **Register a sale** (what, how many, when). Saving **drops theoretical ingredient
   stock** when a recipe and stock exist. **Void a sale** to reverse stock moves.
7. **Import** her Drive Excel (v1 and later if she kept annotating). **Export** Excel
   anytime (that file is her primary backup).
8. **App is a shortcut on that PC.** No public URL. No monthly hosting.
9. **Encrypted backup to Cloudflare R2** every time she opens the app (automatic,
   no user action). She can restore from R2 if her laptop dies.

If any of those fail, fase 1 is not delivered.

---

## 2. Explicitly do not build

| Item | Why |
|---|---|
| Public website / carta | Quote: after the local is running |
| Mesas, salón, KDS, datáfono | Out of scope |
| Login/SaaS, hosting, phone app | Local PC only |
| SET invoices, multi-sucursal | Deferred |
| WhatsApp bot / auto orders | Out; sales are typed in the RMS |
| Production-of-the-day planner, shopping list, peak calendar | Parked 38 h module |
| Merma, proveedores as a module, client CRM | Later à la carte |
| Reuse archived `IvanWeissVanDerPol/Saskia` Flask bakery as the product | Wrong era; use as **reference only** if useful |
| **Supabase, Firebase, Postgres cloud, any cloud DB** | Quote: no hosting |
| **Anthropic API, OpenAI, any LLM** | Not signed for; Fase 1.5+ candidate |
| **Alembic, Flask, Django, async frameworks** | Stack is locked |
| **Tailwind, Bootstrap, React, Vue, HTMX** | Stack is locked (server-rendered HTML only) |
| **Docker, Kubernetes, containerization** | Stack is locked (single-machine install) |
| **Third-party Sentry, Datadog, log aggregators** | OPSEC; no PII leaves her PC except encrypted R2 backup |

---

## 3. Architecture (chosen)

Three options were on the table. The locked choice is B with refinements:

| Option | Fit | Verdict |
|---|---|---|
| A. Keep Excel as the database + thin UI | Fast, but formulas already painful; quote is a **panel**, not another workbook | No |
| B. **FastAPI + SQLite + local browser** | Matches existing Python workbook builders; Excel in/out; install = `uv` + shortcut; still "on her PC" | **Yes (chosen)** |
| C. Electron / native desktop | Heavier than 70 h; no extra user value vs localhost | No for fase 1 |

**Runtime**

```
[Saskia PC]
  shortcut → run.bat (Windows) or run.sh (Mac)
    → uv sync (idempotent; only re-installs if pyproject.lock changed)
    → uv run uvicorn 127.0.0.1:8765
    → opens browser to http://127.0.0.1:8765
  data:    %LOCALAPPDATA%\AIW-Saskia\rms.sqlite  (Windows)
           ~/Library/Application Support/AIW-Saskia/rms.sqlite  (Mac)
  backups: ~/Documents/AIW-Saskia/backups/rms-backup-YYYYMMDD-HHMMSS.xlsx
           (auto-exported on every startup, kept for last 30 days)
  cloud:   Cloudflare R2 encrypted snapshots (free tier, 10 GB-month)
           Encrypted with `age` on her laptop; only ciphertext in cloud
  logs:    ~/AppData/Local/AIW-Saskia/logs/app.log  (loguru, 7-day rotation)
```

No port-forward, no ngrok, no "just host it." `app/rms/main.py` has an assertion that
**refuses to start if `bind_host != "127.0.0.1"`**.

**Install story:** `uv` (NOT official Python installer). Reasoning: 10-100× faster than
`pip`, reproducible lockfile via `uv.lock`, single-binary install from
`https://astral.sh/uv`. If `uv` install fails (corporate proxy), fall back to
official Python 3.13.x installer.

**Code home:** `Ai-Whisperers/saskia-app` repo, `app/` directory at the root.

---

## 4. File map (create in `app/`)

```
app/
  README.md                    # how to run locally / on her PC
  CHANGELOG.md                 # app-level changelog (separate from repo-level)
  pyproject.toml               # Python 3.13, FastAPI 0.115, uvicorn[standard], ...
                               # dev: pytest, pytest-cov, hypothesis, ruff
  uv.lock                      # generated by `uv sync`; pinned deps
  .python-version              # "3.13" (used by uv)
  .env.example                 # template for DB_PATH, BIND_HOST, PORT, R2_* vars
  rms/
    __init__.py                # package docstring; safe to import (no side effects)
    config.py                  # paths, ports, env vars, R2 config (with defaults)
    db.py                      # engine, session, WAL+secure_delete pragmas, versioned migrations
    models.py                  # 7 tables per §5
    money.py                   # Decimal helpers + Gs. formatting (already written, 88 tests)
    units.py                   # Unit enum + alias coercion + conversions (already written, 45 tests)
    costing.py                 # recipe_batch_cost, product_unit_cost, margin, apply_sale, void_sale
    main.py                    # FastAPI app, lifespan, router mounts; asserts bind=127.0.0.1
    routers/
      __init__.py
      health.py                # /healthz + /healthz/db (already written)
      dashboard.py             # Inicio: ventas/COGS/margen/ranking/avisos
      products.py              # Productos y precios CRUD
      recipes.py               # Recetas CRUD + polymorphic recipe_line
      inventory.py             # Inventario CRUD
      sales.py                 # Ventas CRUD + void
      excel_io.py              # Import/export xlsx + re-import confirmation
    services/
      __init__.py
      auto_backup.py           # local xlsx export (already written)
      r2_backup.py             # encrypted R2 backup (Tier 8, new in v2)
      import_xlsx.py           # Drive-Excel → SQLite
      export_xlsx.py           # SQLite → Excel (the backup)
      reports.py               # monthly stock-out report, monthly close
    templates/
      base.html                # layout; child templates extend
      inicio.html
      productos.html
      recetas.html
      inventario.html
      ventas.html
      excel.html
      _components/
        alerts.html            # reusable red-flash stock-out banner
        money_input.html       # Gs.-formatted input
        vos_form.html          # standard form with vos copy
    static/
      app.css                  # minimal CSS; no Tailwind, no Bootstrap
  docs/
    copy-vos.md                # Paraguayan Spanish UI copy bank (filled before Task 3)
    architecture.md            # data flow, sources of truth, update paths
    threat-model.md            # single-user, single-PC, single trust boundary
    upgrade-tiers.md           # reference: what's in/out, cost of each Tier
  installer/
    README.md                  # install-session checklist (already written)
    run.bat                    # Windows launcher (already written)
    run.sh                     # Mac launcher (deferred to Task 9 if OS = Mac)
    shortcut-template.bat       # desktop shortcut generator
    r2-setup.md                # how to set up Cloudflare R2 credentials (one-time)

tests/
  __init__.py
  conftest.py                  # shared fixtures (in-memory SQLite, temp dir)
  test_money.py                # 43 tests (already written, passes)
  test_units.py                # 45 tests (already written, passes)
  test_costing.py              # recipe_batch_cost, product_unit_cost, margin (TDD-start in Task 2)
  test_stock_drop.py           # apply_sale, void_sale, allow_negative_stock
  test_import_roundtrip.py     # import → export → import = same costing
  test_void_sale.py            # void semantics (per improvements §6.2)
  test_healthz.py              # /healthz, /healthz/db with WAL confirmation
  test_r2_backup.py            # encrypt + upload + restore (uses moto for S3 mock)
  test_recipe_polymorphic.py   # sub-recipes as ingredients in other recipes
  fixtures/
    mini.xlsx                  # synthetic, 3 ingredients, 1 recipe, 2 products (Task 6 minimum)
    stress.xlsx                # synthetic, 25 tabs, 63 ingredients, 20 recipes, 3 sub-recipes
                               # (matches real HEREBUS_FoodBiz scale; NEVER her real file)
    r2-encrypted-blob          # test fixture for R2 roundtrip

installer/
  README.md                    # install-session checklist (~45-90 min, 10 steps)
  run.bat                      # Windows launcher (uses `uv run uvicorn ...`)
  shortcut-template.bat

.github/
  workflows/
    ci.yml                     # ruff + pytest + coverage gate (80%)

.pre-commit-config.yaml        # ruff + smoke tests on every commit

.gitignore                     # blocks __pycache__, .venv/, *.sqlite, backups/, *.log, .env
```

---

## 5. Data model

All money columns: **integer Gs.** `NULL` purchase price means "missing" (feeds the
dashboard alert).

| Table | Fields | Notes |
|---|---|---|
| `ingredient` | id, name, unit (Unit enum), stock_qty (Decimal, nullable), purchase_price_gs (int, nullable), min_stock_qty (Decimal, default 0), notes | Inventory + low-stock |
| `recipe` | id, name, yield_qty (Decimal), yield_unit (Unit enum), notes | Yield = porciones / rendimiento |
| `recipe_line` | id, recipe_id, **line_kind** (ENUM: 'ingredient' or 'sub_recipe'), **line_ref_id** (FK to ingredient OR recipe, polymorphic), qty (Decimal) | **New in v2: polymorphic to support sub-recipes** |
| `product` | id, name, portion_label, sale_price_gs (int), recipe_id (FK to recipe, nullable) | Sale without recipe → alert |
| `sale` | id, sold_at (datetime, Asunción local), product_id, qty (Decimal), unit_price_gs (int, snapshot), notes | Snapshot price so history survives catalog edits |
| `sale_stock_move` | id, sale_id, **affected_recipe_id** (for tracking sub-recipe expansions), ingredient_id, qty_delta (Decimal, negative) | Audit of theoretical drop; skip if no recipe or no lines |
| `import_batch` | id, imported_at, source_filename, note, row_counts_json | Re-import is explicit; row_counts = audit |
| `app_meta` | key, value (text) | Schema version, last_backup_at, etc. (replaces ad-hoc schema tracking) |

**Polymorphic recipe_line:** `line_kind` ∈ {"ingredient", "sub_recipe"}. `line_ref_id`
points to `ingredient.id` if `line_kind = 'ingredient'`, or `recipe.id` if
`line_kind = 'sub_recipe'`. **Sub-recipes are flattened at costing time**, not at import
time — we keep the recipe tree intact, but the costing engine walks it.

**Why polymorphic, not flattened at import:** if we flatten Masa choux into the parent
recipe, we lose the ability to cost Masa choux as a standalone product (which she might
sell separately). Polymorphic preserves the tree.

**Derived (never stored as source of truth):**

- Recipe batch cost Gs. = Σ over all lines (recursively for sub-recipes), where each
  line cost = `line.qty × line_ref_price`, and `line_ref_price` is either
  `ingredient.purchase_price_gs` (if line_kind = ingredient) or
  `sub_recipe.batch_cost_gs() / sub_recipe.yield_qty` (if line_kind = sub_recipe).
  Walk terminates on cycle detection (raises `CycleInRecipeTree` exception).
- Recipe unit cost Gs. = `recipe.batch_cost_gs() / recipe.yield_qty`.
- Product unit cost Gs. = `recipe.unit_cost_gs()` (if recipe_id set), else `None`.
- Product margin Gs. = `sale_price_gs − unit_cost_gs`; % = `margin / sale_price`
  when sale_price > 0.
- Sale COGS = `product.unit_cost_gs × sale.qty` at **current** recipe (fase 1: current,
  not historical cost). Document this limitation in `app/README.md`.
- Dashboard ranking = `total_margin_gs_in_period` per product, sorted desc.

**Stock drop (on sale save, one transaction, atomic):**

1. Resolve `product.recipe_id`. If missing → save sale, **no** stock moves, flag
   "venta sin receta" in UI.
2. Walk recipe tree (depth-first). For each `recipe_line`:
   - If `line_kind = 'ingredient'`: `need = line.qty / recipe.yield_qty × sale.qty`
     (same unit as ingredient). Insert `sale_stock_move` (−need) and decrement
     `ingredient.stock_qty`.
   - If `line_kind = 'sub_recipe'`: recurse into the sub-recipe.
3. **Allow negative stock** (show it; don't block sale). Dashboard alerts when
   `stock_qty < min_stock_qty` (red flash if `stock_qty < 0`).
4. **`NULL` yield_qty** → refuse to apply sale with explicit error "Receta sin
   rendimiento. Cargá el rendimiento antes de vender."

**Delete/void sale:** reverse all `sale_stock_move` records for that sale.
**Multi-level void** handles sub-recipes correctly. Fase 1 MUST support void; a typo
otherwise wrecks stock.

**Money safety:** all `purchase_price_gs`, `sale_price_gs`, etc. are `int` (SQLAlchemy
`Integer`). All intermediate computations use `Decimal`. The only path from `Decimal`
to `int` is `app/rms/money.py:to_int_gs()`. Any other rounding is a bug.

---

## 6. Excel: source of truth for v1 load

**Do not invent a new catalog.** First import maps her foodbiz workbooks.

**Canonical files (roles only — copy from Drive, never commit):**

| Workbook (personal-context / Drive) | Maps into |
|---|---|
| `HEREBUS_FoodBiz.xlsx` | ingredients, recipes, recipe lines, stock, prices if present |
| `RECETARIO_EN_BLANCO.xlsx` | recipe create template — UI should feel like this form |
| `HEREBUS_Suppliers.xlsx` | **Do not** build a suppliers module. If a sheet has purchase prices, use them as `ingredient.purchase_price_gs` only |
| `HEREBUS_Analisis.xlsx` | Reference for KPIs; dashboard is **computed**, not a dump of that file |

**Import mechanics (refined from v1 plan):**

1. **Subsetting:** the importer reads a `tab_allowlist.toml` config. Default behavior:
   import ALL `Recipe_*`, `Inventory`/`Stock`, and (if present) `*_SubRecipe` tabs.
   Saskia can override during kickoff to import only a V1 subset.
2. **V1 product list cross-check:** after import, the importer reports which imported
   recipes match the V1 product list (from intake) and which don't. Mismatches surface
   in the UI for her to resolve.
3. **Empty ingredient prices stay `NULL`** → dashboard "receta sin precio de
   ingrediente" alert.
4. **Empty yields:** recipe still imports; costing shows "sin rendimiento" until she
   fills it. Sales blocked if yield_qty is NULL.
5. **Money coercion:** all `*Price*` cells (which may be Decimal or string) coerced
   via `money.parse_gs()` → `money.to_int_gs()` before persistence. **This is the
   ONLY allowed path** (per Rule 6).
6. **Re-import:** the UI shows a diff ("esto puede pisar recetas e inventario") and
   requires explicit OK. **Auto-backup is taken before any re-import mutation.**
7. **Sub-recipes:** if `Recipe_Masa_choux` exists AND `Recipe_Pastel_choux` has a
   line referencing Masa choux (e.g., 200g of Masa choux for one Pastel), the importer
   creates a `recipe_line` with `line_kind = 'sub_recipe'` and `line_ref_id` pointing
   to `recipe.id` of Masa choux. **Match by name (case-insensitive, accent-stripped)**
   with an unmatched-names report.
8. **Export:** one `.xlsx` with sheets `Ingredientes`, `Recetas`, `Lineas`, `Productos`,
   `Ventas`, `StockMoves`. That file is her primary backup; SQLite is the working
   state. **Cloudflare R2 encrypted snapshot is the disaster-recovery backup.**

**Hours in the quote for this block:** inside the 54 h "registro + Excel" (see §7).

**Fixture strategy:**

- `tests/fixtures/mini.xlsx` — 3 ingredients, 1 recipe, 2 products. Minimum for
  import/export roundtrip test.
- `tests/fixtures/stress.xlsx` — 25 tabs, 63 ingredients, 20 recipes, 3 sub-recipes.
  Mirrors real HEREBUS scale. **NEVER** includes real Drive data. Used for:
  - Sub-recipe BOM walking
  - Polymorphic recipe_line import
  - Export roundtrip at scale
  - Performance smoke (import time < 5s)

---

## 7. Hour budget (do not exceed without written OK)

From product catalog — **70 h** total. Extra is Gs. 250.000/h after written OK.

| Block | h | Owner-facing slice |
|---|---:|---|
| Skeleton + DB + config + loguru + healthz + money/units + auto-backup | 8 | Task 1 |
| Costing engine (recipe_batch_cost, product_unit_cost, margin, apply_sale, void_sale) | 6 | Task 2 |
| Inventario + Recetas CRUD (Spanish UI) | 12 | Task 3 |
| Productos y precios + margin display | 4 | Task 4 |
| Ventas + stock drop + void + history | 6 | Task 5 |
| Excel import/export + roundtrip + Drive copy workflow | 14 | Task 6 |
| Tablero (ventas, COGS, ranking, avisos, period toggle) | 8 | Task 7 |
| QA de cifras (hand-check 3 real recipes vs Excel) | 2 | Task 8 |
| Install on her PC + onboarding + auto-backup + R2 setup + Windows Defender dance | 6 | Task 9 |
| 2 review rounds + sign-off coordination | 4 | Task 10 |
| **Total** | **70** | |

The clock-pause rule (§13) means any blocked time is logged but not counted. No
filler-work, no fake-data UI polish while waiting.

**If blocked** (no Drive, no PC, no prices): clock pauses per §13. Log idle; do not
burn hours on fake-data UI chrome.

**Hour tracking discipline:**

- Every PR includes a footer with cumulative hours: `Time: 14.0 / 70 h`.
- Daily standup (WhatsApp to Ivan) reports hours-spent.
- At 60 h cumulative: explicit Ivan check-in. At 70 h: stop. No silent overflow.

**"Written OK" definition (per Quote line: "Extra Gs. 250.000/h after written OK"):**
- A WhatsApp message from Ivan to Saskia (and ideally her acknowledgement) constitutes
  written OK.
- Email works equivalently.
- A signed change-order doc is **not** required for fase 1's small extras; only for
  the parked Gs. 9.500.000 planning module and beyond.

---

## 8. Calendar (quote milestones)

Clock starts when: first cuota **and** Drive read access **and** work PC available **and** V1 product list received.

```
Day 0–5   Kickoff: confirm OS, share Drive folder, share V1 list, confirm R2 setup window
Week 1–2  Skeleton + DB + money/units + costing + first import of her Excel
Week 2–4  Inventario + recetas + productos + ventas CRUD with stock drop
Week 4–6  Tablero, export, auto-backup (local + R2), restore test, run.bat + shortcut
Week 6–8  Install on her PC, onboarding, offline test, Round 1 of review
Round 2   Cosmetic only if hours remain; otherwise declined with explicit reason
```

---

## 9. Tasks (build order, refined)

Each task has a **demo** the next person can run. Do not start Task N+1 if N's demo
fails. Each task lists the time-box, the deliverables, and the PR scope.

### Task 0 — Kickoff (commercial + machine + V1 list)

**Owner:** K.W. + whoever installs. **Not billed as extra features.**

- [ ] Quote signed, first cuota in (production may start).
- [ ] Named PC (quote field) + Windows vs Mac.
- [ ] Drive folder identified; **local copy** of foodbiz xlsx on the build machine (not committed).
- [ ] V1 product/recipe list written in `docs/intake/v1-catalog.md` (names only, no customer PII).
- [ ] R2 bucket name + access key ID + secret access key exchanged (or: defer to Task 9).
- [ ] Confirm: no login; bind 127.0.0.1; port 8765.
- [ ] Copy-vos.md filled by Saskia or Kiki (Spanish copy bank).

**Done when:** `docs/intake/v1-catalog.md` exists (names) + a laptop/PC is the install target + V1 list received + Spanish copy available.

### Task 1 — Skeleton app + SQLite + reliability layer (8 h)

**Files:** `app/pyproject.toml`, `app/.python-version`, `app/.env.example`,
`app/rms/__init__.py`, `app/rms/config.py`, `app/rms/db.py`, `app/rms/models.py`,
`app/rms/main.py`, `app/routers/health.py` (already written).

**Produces:**

- `GET /healthz` returns `{"status": "ok", "service": "aiw-saskia-rms"}`.
- `GET /healthz/db` returns `{"db": "ok", "journal_mode": "wal"}` if SQLite is reachable
  and WAL is enabled; 503 otherwise.
- `app/rms/db.py:init_db()` creates 7 tables per §5 + `app_meta` row with
  `schema_version=1`.
- `app/rms/config.py` reads `DB_PATH`, `BIND_HOST`, `PORT` from env, with defaults:
  `DB_PATH=%LOCALAPPDATA%\AIW-Saskia\rms.sqlite`,
  `BIND_HOST=127.0.0.1`, `PORT=8765`.
- `app/rms/main.py` **refuses to start if `BIND_HOST != "127.0.0.1"`** (defensive
  assertion that catches misconfigured env vars).
- `app/rms/db.py` enables WAL mode + `secure_delete = ON` + `foreign_keys = ON` on
  every connection via SQLAlchemy `event.listens_for(Engine, "connect")` listener.
- **Versioned schema migrations** in `app/rms/db.py`:
  `CURRENT_SCHEMA_VERSION = 1`, `MIGRATIONS = {1: "initial schema"}`. `init_db()` runs
  pending migrations in order. Each migration is a Python function that takes a
  SQLAlchemy connection and applies the schema change.
- `app/services/auto_backup.py` exports SQLite → xlsx in
  `~/Documents/AIW-Saskia/backups/` with timestamped filename, kept for last 30 days.
- `tests/test_healthz.py` + `tests/test_money.py` (already passing) + `tests/test_units.py`
  (already passing) all green. **Coverage gate: 80%.**
- `app/docs/threat-model.md` documents: single-user, single-PC, single trust boundary.
  "Anyone with physical access to the laptop has full access."

**Demo:** `uv sync --all-extras` + `uv run pytest` → ≥ 88 tests pass, coverage ≥ 80%. `uv
run uvicorn app.rms.main:app --host 127.0.0.1 --port 8765` → browser shows Spanish
landing page. `/healthz/db` returns 200 with `journal_mode=wal`. Set `BIND_HOST=0.0.0.0`
in env → app refuses to start.

### Task 2 — Costing engine (no UI) (6 h)

**Files:** `app/rms/costing.py`, `tests/test_costing.py`, `tests/test_stock_drop.py`,
`tests/test_void_sale.py`.

**Produces:**

- `recipe_batch_cost_gs(recipe_id, session) -> int | None` (None if any line lacks
  purchase price; walks sub-recipe tree recursively).
- `product_unit_cost_gs(product_id, session) -> int | None`.
- `product_margin(product_id, session) -> tuple[int | None, float | None]`.
- `apply_sale(session, product_id, qty, sold_at) -> Sale` (atomic transaction;
  snapshots `unit_price_gs`; creates `sale_stock_move` rows; walks sub-recipes).
- `void_sale(session, sale_id) -> None` (reverses all stock moves atomically; works
  with sub-recipes).
- `CycleInRecipeTree` exception for circular recipe references.

**Rules:** integer Gs. via `money.to_int_gs()` (half-up). Document rounding in
`app/README.md`.

**Tests (5+ per behavior, TDD-first):**

- muffin batch 12, cost 24_000 Gs. → unit cost 2_000.
- Sale of 2 muffins drops flour by `2 × (flour_per_batch/12)`.
- Sale without recipe creates sale, zero stock moves (UI flag).
- Void restores stock fully.
- Sub-recipe: Pastel_choux uses Masa_choux; cost of Pastel_choux includes Masa_choux cost.
- Cycle: A uses B uses A → raises `CycleInRecipeTree`.
- `NULL` yield_qty → sale raises "Receta sin rendimiento" error.
- Decimal precision: 0.1+0.2=0.3 in cost calculations (no float drift).
- Half-up rounding: 2.5 Gs. → 3 (not banker's 2).

**Demo:** pytest green, all tests pass. Coverage of `costing.py` ≥ 90% (it's pure logic).

### Task 3 — Inventario + Recetas CRUD (Spanish) (12 h)

**Files:** `app/routers/inventory.py`, `app/routers/recipes.py`,
`app/templates/inventario.html`, `app/templates/recetas.html`,
`app/templates/_components/vos_form.html`.

**Produces:**

- Inventory list / add / edit / delete:
  - Name (required)
  - Unit (Unit enum, dropdown)
  - Stock_qty (Decimal, default 0)
  - Purchase_price_gs (int, nullable)
  - Min_stock_qty (Decimal, default 0)
- Recipe list / add / edit:
  - Name
  - Yield_qty + yield_unit
  - Recipe lines (ingredient picker + qty, OR sub-recipe picker + qty)
  - Cannot delete ingredient that's on a recipe → block with Spanish error
- All UI strings from `app/docs/copy-vos.md`.
- Vos copy throughout: "Guardá", "Cancelar", "Stock bajo", "Sin precio", etc.

**Demo:** create flour + muffin recipe + sub-recipe Masa_choux via UI. Verify Polymorphic
recipe_line in DB.

### Task 4 — Productos y precios (4 h)

**Files:** `app/routers/products.py`, `app/templates/productos.html`.

**Produces:**

- Product: name, portion_label, sale_price_gs (int), linked recipe.
- Display shows computed `unit_cost_gs`, `margin_gs`, `margin_%` (or "falta precio /
  rendimiento" if N/A).
- Cannot delete recipe that's on a product → block with Spanish error.

**Demo:** product "Muffin" sale 8_000, cost 2_000, margin 6_000 / 75%.

### Task 5 — Ventas + stock drop + void (6 h)

**Files:** `app/routers/sales.py`, `app/templates/ventas.html`,
`app/templates/_components/alerts.html`.

**Produces:**

- Sale form: product (dropdown), qty (Decimal), datetime (default = Asunción local
  now), notes (optional).
- Save calls `apply_sale()`.
- History table (last 30 days by default, sortable).
- Void button on each sale row calls `void_sale()` after confirmation modal.
- After save: redirect to history with success message.
- Inventory page reflects new stock (no auto-refresh needed; user navigates).
- **Allow negative stock** with red-flash alert component if stock < 0.

**Backdating:** yes, allowed. Default = now; user can override to any past datetime.
Justification: a typo ("sold yesterday") shouldn't force a void-and-redo cycle. Limit
to past 30 days (UI date picker max=Today).

**Demo:** sell 2 muffins → flour decreases → void → flour restores.

### Task 6 — Excel import / export (14 h)

**Files:** `app/services/import_xlsx.py`, `app/services/export_xlsx.py`,
`app/routers/excel_io.py`, `app/templates/excel.html`,
`tests/test_import_roundtrip.py`, `tests/test_recipe_polymorphic.py`,
`tests/fixtures/mini.xlsx`, `tests/fixtures/stress.xlsx`.

**Produces:**

- `import_xlsx.from_file(path) -> ImportBatchResult` with row_counts, unmatched_names,
  warnings.
- `export_xlsx.to_file(path) -> None` writes the 6-sheet workbook.
- Importer respects `tab_allowlist.toml` (default: import all Recipe_*, Inventory/Stock,
  SubRecipe tabs).
- Re-import UI: shows diff ("esto puede pisar X recetas, Y ingredientes, Z productos.
  ¿Continuar?"), requires explicit OK, takes auto-backup first.
- Polymorphic recipe_line: sub-recipes detected by name match (case-insensitive,
  accent-stripped), created with `line_kind = 'sub_recipe'`.
- Money coercion: every price cell routed through `money.parse_gs()` →
  `money.to_int_gs()`.
- Roundtrip test: import `mini.xlsx` → export → re-import → same costing.
- Stress test: import `stress.xlsx` (25 tabs, 63 ingredients, 20 recipes, 3 sub-recipes)
  in < 5 seconds; export roundtrip in < 5 seconds.

**Demo:** import `mini.xlsx`; see V1 cross-check report; export; re-import is idempotent.

### Task 7 — Tablero Inicio (8 h)

**Files:** `app/routers/dashboard.py`, `app/templates/inicio.html`.

**Period toggle: hoy / semana / mes** (calendar boundaries in Asunción local time UTC-4).

**Widgets (all required by quote):**

- **Ventas Gs.** = SUM(qty × unit_price_gs) over period.
- **Costo de lo vendido Gs.** = SUM(unit_cost_gs × qty) over period; flag recipes with
  None cost.
- **Margen Gs.** = Ventas − Costo. **%** = Margen / Ventas when Ventas > 0.
- **Ranking:** products by `total_margin_gs_in_period` (desc). Show top 5 + bottom 5.
  "Worst" = lowest margin Gs. (could be negative if she's losing money on a product).
- **Avisos (red alerts):**
  - Stock below min (`stock_qty < min_stock_qty AND min_stock_qty > 0`)
  - Stock negative (`stock_qty < 0`) — red flash
  - Recipes with `batch_cost IS NULL` (any line lacks price)
  - Sales in period with no recipe

**Timezone:** all queries use `datetime.now(ASUNCION_TZ)` for "now". "Today" =
00:00 to 23:59:59.999999 in Asunción local. Document this in `app/docs/architecture.md`.

**Demo:** after stress.xlsx + 3 sales, ranking and alerts match hand-spreadsheet verification.

### Task 8 — QA de cifras (2 h) + freeze

- [ ] Walk 3 real recipes from V1 list: cost vs Excel/calculator. Fix rounding bugs only.
- [ ] Test void → restore → re-void edge case.
- [ ] Test negative-stock sales + dashboard red flash.
- [ ] Note known limits in `app/README.md`: current recipe cost (not FIFO), polymorphic
  recipe_line (sub-recipes flatten on import validation only, not stock movement),
  single-user (no auth).

### Task 9 — Install on her PC + onboarding + R2 setup (6 h)

**Files:** `installer/README.md`, `installer/run.bat`, `installer/run.sh`,
`installer/r2-setup.md`, `installer/shortcut-template.bat`.

**Steps:**

1. `uv` setup (PowerShell install from astral.sh; 30s).
2. Clone `Ai-Whisperers/saskia-app` to `~/Documents/saskia-app`.
3. `uv sync --all-extras` (~30s).
4. **R2 credentials setup** (one-time):
   - Saskia (or Ivan, on her behalf) creates a Cloudflare account + R2 bucket.
   - Generates an R2 API token (read+write to that bucket only).
   - Stores in `~/.config/aiw-saskia/r2.toml` (gitignored, mode 0600).
   - First `r2_backup.upload()` encrypts+stores a test snapshot; verify by listing
     the bucket in Cloudflare dashboard.
5. Create desktop shortcut `Gestión Saskia` (Windows) or `.command` file (Mac).
6. **Offline test**: disconnect Wi-Fi, restart app, verify it still works.
7. **Restore test**: delete local `rms.sqlite`, run app, auto-restore-from-R2 brings it
   back. Verify data integrity.
8. Teach: daily sales, export to Drive, don't delete `rms.sqlite` or
   `~/.config/aiw-saskia/r2.toml`.
9. **Windows Defender / AV handling:** add `Documents/saskia-app`, `AppData\Local\AIW-Saskia`
   to AV exclusions BEFORE first run.

**Done criteria:** app launches from desktop shortcut; `/healthz/db` returns WAL;
auto-backup fires; R2 encrypted snapshot appears in bucket; restore test passes; she
can add an ingredient + recipe + sale end-to-end.

### Task 10 — Review rounds (quote) (4 h)

- [ ] Round 1: she uses it 3–5 days; WhatsApp list of fixes in scope.
- [ ] Round 2: same. Cosmetic only if hours remain.
- [ ] Written OK (WhatsApp) = fase 1 accepted.
- [ ] Scope creep (planning, web, bot) → "otro presupuesto", do not start.

---

## 10. Team split (suggested)

| Role | Focus | Tasks |
|---|---|---|
| Backend | SQLite, costing, import/export, R2 backup | 1, 2, 6 |
| UI | Spanish screens, dashboard, void flow | 3, 4, 5, 7 |
| Delivery | Kickoff, her PC, R2 setup, QA with real recipes | 0, 8, 9, 10 |
| K.W. | Scope police, cuota, no planning in the build | all gates |

**Reality check:** this engagement has been bootstrapped by Ivan + Hermes solo. Kiki
has not been assigned. The "team split" is **suggested**; in practice one person may
do all of this. **70 h is one stream.** Two people: backend and UI in parallel after
Task 2, merge daily.

**Escalation path:** when a task's demo fails, the executor fixes it within the same
task's hour budget. If fix would exceed budget: STOP, ping Ivan, get explicit OK before
continuing. No silent overflow.

---

## 11. Timezone & date handling

**Asunción timezone: UTC-4, no DST.**

```python
# app/rms/config.py
from zoneinfo import ZoneInfo
ASUNCION_TZ = ZoneInfo("America/Asuncion")
```

- All `datetime.now()` calls in app code use `datetime.now(ASUNCION_TZ)`.
- All "today / week / month" period boundaries are computed in Asunción local time.
- DB stores UTC datetime (Python datetime without tz); conversion happens at the edge.
- Reason: store UTC for portability; display/period in Asunción local for human
  relevance.

**Period boundaries:**
- Today: `[00:00:00, 23:59:59.999999]` in Asunción local.
- Week: ISO calendar week (Mon–Sun), current week containing today.
- Month: calendar month (1st–last day), current month containing today.

**Documented in:** `app/docs/architecture.md` §3 (timezone).

---

## 12. Backup architecture (NEW in v2)

**Three-tier backup strategy:**

| Tier | Where | What | When | Cost |
|---|---|---|---|---|
| **Working copy** | `~/AppData/...\rms.sqlite` | live DB | continuous | $0 |
| **Local export** | `~/Documents/AIW-Saskia/backups/rms-backup-*.xlsx` | xlsx export of all tables | on every app startup (if last backup > 24h), kept for 30 days | $0 |
| **Cloud encrypted** | Cloudflare R2 bucket | age-encrypted SQLite snapshot | on every app startup (if last R2 backup > 24h) | **$0** (free tier covers her) |

**R2 encryption details:**
- Library: `age` (https://github.com/FiloSottile/age). Modern, simple, audited.
- Key: `~/.config/aiw-saskia/age.key` (mode 0600). Generated on first install.
- Workflow:
  1. Encrypt SQLite file with `age -e -r age1... < rms.sqlite > rms.sqlite.age`
  2. Upload to R2 with `boto3` (S3-compatible API): `boto3.client('s3', endpoint_url='https://<account>.r2.cloudflarestorage.com').put_object(...)`
  3. Restore: download, decrypt, replace.
- **No plaintext on R2.** Even Cloudflare breach = useless ciphertext.

**Restore test (Task 9 mandatory):** delete local SQLite, run app, restore from latest R2
snapshot. Verify data integrity by checking a known ingredient + a known sale.

**Credential rotation:** R2 API token rotated annually. Key rotation story: `age`
supports multiple recipients; new key can decrypt old files.

---

## 13. Clock-pause rule (Task 0.0 pre-flight)

The dev plan §0 says clock pauses until: first cuota is in + Drive read access + work PC
named + V1 product list received.

**Pre-flight exceptions** (work that happens BEFORE clock starts, NOT billed):

- Building the app skeleton (already done in pre-signoff commit `f82dfb3` of the
  engagement repo, which migrated to `saskia-app`).
- Writing specs, tests, fixture generation.
- Saskia kickoff message + reply (WhatsApp).
- `copy-vos.md` fill (Kiki or Saskia).

**Work that REQUIRES the gate cleared:**

- Any code that touches her data (importers that read her Drive files).
- Installing on her PC (Task 9).
- Any clock-billed hour.

**Operator override:** explicit operator call to start work before gate clears. Document
the override in the PR commit message.

**Current status (as of v2 publication):** gate NOT cleared. Pre-signoff skeleton
landed via operator override. Future tasks require the gate.

---

## 14. OPSEC and incident response (NEW in v2)

**Standard OPSEC posture (extends AGENTS.md rule #6):**

- No PII in PRs. No bank statements. No workbooks. No identity docs.
- No logs to third-party services.
- No analytics or telemetry.
- No LLM API calls (Anthropic, OpenAI, etc.).
- One approved cloud dependency: Cloudflare R2 (free tier, encrypted).

**Incident response — if PII accidentally committed:**

1. Reviewer MUST block the PR.
2. Stop the merge. Notify operator.
3. **Rotate** any token in the leaked file (R2 access key, etc.).
4. Operator decides: amend commit, force-push with `git push --force` (rewriting
   history is acceptable for PII containment).
5. If PII was a private repo: lower exposure risk, but still rotate.
6. If PII was a public repo: GH Archive, Software Heritage already cached. Focus
   becomes damage control, not containment.
7. Add a post-mortem to `docs/sessions/` (no PII in the post-mortem itself).

**Pre-commit hooks block common cases:**
- Secret files (`.env`, `credentials.json`, `id_rsa`) → blocked.
- Files > 1 MB without explicit justification → warning.
- YAML files must parse → enforced.

---

## 15. CI / testing pipeline (NEW in v2)

**GitHub Actions** runs on every PR to main:
1. `uv sync --all-extras`
2. `uv run ruff check .` (lint)
3. `uv run ruff format --check .` (format)
4. `uv run pytest --cov=app --cov-report=term-missing` (tests + coverage)
5. Coverage gate: fail if < 80% line coverage.
6. `uv run mypy app/` (informational, not blocking yet)

**Pre-commit hooks** run on every commit locally:
1. `ruff --fix --exit-non-zero-on-fix`
2. `ruff format`
3. `pytest tests/test_money.py tests/test_units.py` (smoke)
4. Secret-file detection
5. Large-file detection
6. YAML validation

**Coverage targets:**
- `app/rms/money.py` ≥ 95% (pure logic, easy)
- `app/rms/units.py` ≥ 95%
- `app/rms/costing.py` ≥ 90%
- `app/services/import_xlsx.py` ≥ 70% (Excel parsing has many edge cases)
- `app/routers/*.py` ≥ 70% (UI tested via roundtrip, not unit tests in fase 1)
- **Overall: ≥ 80%**

---

## 16. Money & units discipline (formal)

**Money invariants (enforced by tests):**

1. `app/rms/money.py:to_int_gs()` is the ONLY path to round money to integer. Any
   other `int(float)`)` or)` `Decimal.quantize(Decimal("1"))` in app code is a bug.
2. All DB money columns are `INTEGER` (SQLAlchemy `Integer`). Adding a `Numeric` or
   `Float` column for money requires PR review + explicit operator OK.
3. All `Decimal` money calculations use `Decimal(str(value))` to avoid float
   representation errors. `Decimal(0.1)` is exact; `Decimal(float('0.1'))` is not.
5. Money parsing (`parse_gs`) is strict: rejects negatives, decimals, mixed
   separators. See tests in `tests/test_money.py`.

**Unit invariants (enforced by tests):**

1. `app/rms/units.py:Unit.coerce()` is the ONLY path to convert free-text unit input
   to `Unit`. Direct enum value matching is allowed for already-validated input.
2. Cross-family unit conversion (`g → L`, `kg → und`) is forbidden in fase 1
   (would require ingredient-specific density). Raises `ValueError`.
3. New units added to the enum require operator OK + alias-map update.

**Where these rules live:** `app/rms/AGENTS.md` (a new file at app-root level with
engineering conventions, separate from the repo-level AGENTS.md).

---

## 17. Risks (updated from v1)

| Risk | Mitigation |
|---|---|
| Workbooks are 25 tabs of inconsistent names | V1 subset via tab_allowlist.toml; mapping doc; do not wait for perfect warehouse model |
| Sub-recipes are recipe rows used as ingredients | Polymorphic recipe_line (line_kind ∈ {ingredient, sub_recipe}); import matches by name |
| Yields / prices empty | Ship with alerts; sales blocked if yield_qty is NULL |
| She keeps editing Drive Excel after import | Re-import is explicit; sales never wiped; auto-backup before re-import |
| "Can I open it on my phone?" | No. Quote. Parking: another design |
| Agent/Hermes overwrites recipes | App is source of truth on PC; Excel export is local backup; R2 encrypted snapshot is disaster backup |
| Windows Defender / no Python / no uv | Installer session; portable venv if needed; AV exclusions pre-added |
| Planning sneak-in | Reject PRs that add "producción del día" / shopping list / Navidad calendar |
| Time zone confusion (server local ≠ Asunción) | All datetime math uses Asunción TZ; documented in architecture.md |
| Sub-recipe cycle (A uses B uses A) | Cycle detection raises `CycleInRecipeTree`; importer reports and refuses |
| Money rounding errors | `to_int_gs()` is the only path; property-based tests in test_money.py |
| Float money creeps in | Pre-commit hook + ruff lint rule `flake8-bugbear` (B904); reject any float→int conversion of money |
| CloudFlare R2 outage | Restore falls back to local backup (`~/Documents/AIW-Saskia/backups/`); manual export to USB |
| Saskia loses her `age` key | Recovery story: re-install creates new key; restores from latest R2 snapshot; old snapshots become unreadable |
| Hour overflow | Time-tracking footer on every PR; daily standup; 60h check-in; 70h stop |
| Kiki not assigned | Plan is solo-executable; team split is optimization, not requirement |
| Operator override drift | Document override in PR commit message; pre-signoff skeleton was last override (justified) |

---

## 18. Definition of ready / done (process)

**Ready to sprint:** Task 0 complete (signed quote + first cuota + Drive + PC + V1 list + Spanish copy).

**Done for a task:** demo in §9 + tests if the task lists them + Spanish UI if the task
has UI + no new out-of-scope screen + PR footer shows hours + coverage gate passes.

**Done for the project:** §1 acceptance on **her** PC + written OK after round 2 + restore-from-R2 test passes + offline test passes.

**Handoff artifacts:**

- This plan (v2)
- `app/README.md` (run, backup, restore, rounding)
- `app/CHANGELOG.md` (app-level)
- `app/docs/architecture.md` (data flow, timezone, sources of truth)
- `app/docs/threat-model.md` (single-user, single-PC, single trust boundary)
- `app/docs/copy-vos.md` (Paraguayan Spanish UI strings)
- `app/docs/upgrade-tiers.md` (reference: what's in/out, cost of each Tier)
- `installer/README.md` (install checklist)
- `installer/r2-setup.md` (R2 setup guide)
- `docs/intake/v1-catalog.md` (V1 product list)
- Hub quote remains commercial source of truth (`Company-Information/docs/clients/2026-08-18-saskia-weiss-vander.md`)

---

## 19. Definition of "v2 supersedes v1"

This v2 preserves every requirement from v1 (`2026-08-31-rms-fase-1-dev-plan.md`) and
adds:

- Polymorphic `recipe_line` (sub-recipes as ingredients in other recipes).
- Timezone handling (Asunción UTC-4).
- WAL + secure_delete + foreign_keys pragmas.
- `/healthz` + `/healthz/db` endpoints.
- Auto-backup on startup with 30-day retention.
- **Tier 8 cloud backup**: encrypted Cloudflare R2 snapshots, free tier, no monthly cost.
- Versioned schema migrations.
- Backdating sales (up to 30 days past).
- Allow-negative-stock with red-flash alert.
- Hour-tracking discipline.
- 80% coverage gate in CI.
- Pre-commit hooks (ruff, smoke tests, secret detection).
- Incident response plan (PII leak protocol).
- Stress fixture (`stress.xlsx`, 25 tabs, 63 ingredients, 20 recipes, 3 sub-recipes).
- Money/unit discipline rules in §16.
- `app/docs/threat-model.md`, `app/docs/architecture.md`, `app/docs/upgrade-tiers.md`.
- 88 tests already passing as the pre-signoff baseline.

**Hours:** 70 h (unchanged). Most new content is documentation + spec, not new code.
The Tier 8 R2 backup is ~3 h of build time, absorbed by reducing QA buffer in Task 8
from 1h to 2h.

**Quote:** unchanged. All new features are within the locked scope ("Excel import/export
from Drive" = "R2 is just another export destination, with encryption").

---

*AI Whisperers · internal · 2026-09 v2 (replaces 2026-08-31 v1) · aligns with quote
v4 / CURRENT-CONTEXT. Not for Saskia as-is. Changes from v1: see §19.*