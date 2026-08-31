# Saskia RMS — build plan, phases, verification, and upgrade paths

> **For Ivan, Kiki, and any future agent.** A single document that captures:
> (1) what to build in order, with hours and acceptance
> (2) how to verify completion at every step
> (3) how to visualize progress (a single dashboard)
> (4) where the long-term upgrade paths sit
>
> **Source:** all v2 plan tasks (§9), all SHOULD-FIX items from
> 2026-09-comprehensive-improvements-review.md, all Tier matrix rows from
> 2026-09-tech-stack-review.md.
>
> **Date:** 2026-09 (post-data-layer commit `154484d`).

---

## 1. Where we are right now (state-of-the-repo, post-`154484d`)

| Layer | Status | Files |
|---|---|---|
| **Project config** | ✅ Live | pyproject.toml, LICENSE, .gitignore, .pre-commit-config.yaml, AGENTS.md, README.md |
| **CI / pre-commit** | ✅ Live | .github/workflows/ci.yml, .pre-commit-config.yaml |
| **Money helpers** | ✅ Live + tested (43 tests) | app/rms/money.py |
| **Unit enum** | ✅ Live + tested (45 tests) | app/rms/units.py |
| **DB engine + WAL + migrations** | ✅ Live (smoke-tested) | app/rms/db.py |
| **Models (8 tables)** | ✅ Live (smoke-tested) | app/rms/models.py |
| **Costing engine** (recipe cost, margin, apply_sale, void, cycle detect, polymorphic tree walk) | ✅ Live (smoke-tested 5 scenarios) | app/rms/costing.py |
| **Main app entry** | ✅ Live (bind assertion, lifespan) | app/rms/main.py |
| **Health router** | ✅ Live | app/routers/health.py |
| **Auto-backup helper** | ✅ Live (helpers only; no scheduler yet) | app/services/auto_backup.py |
| **5 base templates** | ✅ Live | base.html, inicio.html, productos.html, producto_form.html, _components/macros.html |
| **App-level docs** | ✅ Live | app/docs/{copy-vos, threat-model, architecture, upgrade-tiers}.md, app/CHANGELOG.md, app/rms/AGENTS.md |
| **Installer docs** | ✅ Live | installer/README.md, installer/run.bat, installer/r2-setup.md |
| **Lockdown + verification protocol** | ⏳ Live as plan; not yet enforced | (this document + the checklist below) |
| **Routers (5 missing)** | ❌ Missing | products, recipes, inventory, sales, dashboard, excel_io |
| **Services (5 missing)** | ❌ Missing | import_xlsx, export_xlsx, r2_backup, reports, backup_scheduler |
| **Templates (4 missing)** | ❌ Missing | recetas, inventario, ventas, excel + 2 components + app.css |
| **Tests (8 missing)** | ❌ Missing | costing, stock_drop, void_sale, healthz, import_roundtrip, recipe_polymorphic, r2_backup, backup_scheduler + mini.xlsx fixture |
| **App boots end-to-end** | ❌ No | Routers not wired |
| **Install on her PC** | ❌ No | Waiting on Saskia |

---

## 2. Build plan: batches with hours, deliverables, acceptance

Each batch ends with a **commit + push + dashboard update**. Each has explicit acceptance.

### Batch 2 — Routers (UI flow) | **~12 hours**

**Files to create (6):**

| File | Purpose | Hours |
|---|---|---|
| `app/static/app.css` | Minimal CSS, no Tailwind, no Bootstrap | 1.5 |
| `app/templates/_components/alerts.html` | Red-flash alert banner for negative stock | 0.5 |
| `app/templates/_components/money_input.html` | Reusable Gs. formatted input | 0.5 |
| `app/templates/inventario.html` | Inventory list + form | 1.5 |
| `app/templates/recetas.html` | Recipes list + form with polymorphic lines | 2 |
| `app/templates/ventas.html` | Sales list + form + void button | 1.5 |
| `app/templates/excel.html` | Import / export UI | 1 |
| `app/routers/inventory.py` | CRUD endpoints | 1 |
| `app/routers/recipes.py` | CRUD with polymorphic line add/edit | 2 |
| `app/routers/products.py` | CRUD with computed margin column | 0.5 |
| `app/routers/sales.py` | Sale entry + void + history | 1 |
| `app/routers/dashboard.py` | Today/week/month + ranking + alerts | 0.5 |

**Wire into `app/rms/main.py`**:
```python
app.include_router(inventory.router)
app.include_router(recipes.router)
app.include_router(products.router)
app.include_router(sales.router)
app.include_router(dashboard.router)
```

**Acceptance for Batch 2:**
- `uv run uvicorn app.rms.main:app --host 127.0.0.1 --port 8765` starts cleanly.
- Browser hits `http://127.0.0.1:8765/` and sees the dashboard (Inicio) with navigation.
- All 6 routers are mounted and respond to GET / POST.
- `ruff check` + `ruff format --check` clean.
- pytest: 88 (existing) still pass.
- **Manual smoke**: take a screenshot of each page in a headless browser; visually check vos copy, money format, no broken Jinja tags.

### Batch 3 — Formal tests for the data layer | **~3 hours**

**Files to create (8):**

| File | Tests | Hours |
|---|---|---|
| `tests/test_costing.py` | recipe_batch_cost (simple, sub-recipe, cycle, missing price), recipe_unit_cost, product_unit_cost, product_margin | 1 |
| `tests/test_stock_drop.py` | apply_sale (simple, sub-recipe, no recipe, NULL yield), stock decrement | 0.5 |
| `tests/test_void_sale.py` | void_sale (simple, sub-recipe, double-void error) | 0.5 |
| `tests/test_healthz.py` | /healthz, /healthz/db with in-memory DB | 0.3 |
| `tests/test_recipe_polymorphic.py` | Polymorphic line kinds, resolve_line_target, cycle prevention | 0.5 |
| `tests/test_void_semantics.py` | Void on already-voided raises; void restores correct qty | 0.2 |

**Acceptance:**
- pytest 6 new files ≥ 60 new tests, all passing.
- Total tests: 88 + ~60 = ~148.
- Coverage gate 80% passes.
- `uv run pytest --cov=app --cov-report=term-missing` shows ≥ 80% line coverage.

### Batch 4 — Excel import/export service | **~6 hours**

**Files to create (2) + 1 fixture:**

| File | Purpose | Hours |
|---|---|---|
| `tests/fixtures/mini.xlsx` | Synthetic: 3 ingredients, 1 recipe, 2 products (generated via Python + openpyxl) | 0.5 |
| `app/services/import_xlsx.py` | Drive Excel → SQLite (polymorphic recipe_lines, money coercion via to_int_gs, sub-recipe name matching) | 3 |
| `app/services/export_xlsx.py` | SQLite → Excel (6 sheets: Ingredientes, Recetas, Lineas, Productos, Ventas, StockMoves) | 1 |
| `app/routers/excel_io.py` | UI endpoints: GET /excel, POST /excel/import (file picker), GET /excel/export | 1 |
| `tests/test_import_roundtrip.py` | Import → export → import = same costing | 0.5 |

**Acceptance:**
- `uv run python -c "from app.services.import_xlsx import from_file; from_file('tests/fixtures/mini.xlsx')"` returns success.
- Roundtrip test passes.
- `uv run python -c "from app.services.export_xlsx import to_file; to_file('/tmp/test.xlsx')"` creates a valid xlsx.
- Money coercion via `to_int_gs()` is the only path; verified by ruff import.
- All existing tests still pass.

### Batch 5 — Backup scheduler + R2 encryption | **~4 hours**

**Files to create (3):**

| File | Purpose | Hours |
|---|---|---|
| `app/services/r2_backup.py` | age-encrypt SQLite + upload to R2 via boto3 | 2 |
| `app/services/backup_scheduler.py` | On startup: local xlsx export + R2 encrypted snapshot, gated on threshold | 1 |
| Wire into `app/rms/main.py` lifespan | Run backup_scheduler on startup | 0.5 |
| `tests/test_r2_backup.py` | Encrypt + decrypt roundtrip with moto (S3 mock) | 0.5 |

**Acceptance:**
- `uv run python -c "from app.services.r2_backup import encrypt_and_upload, download_and_decrypt; ..."` works with a mock R2 endpoint.
- No plaintext on the wire (verified by encrypt-then-upload-then-read-from-mock and checking it's ciphertext).
- On startup, if `r2.toml` exists, R2 upload is attempted; if it doesn't, no error.
- All existing tests still pass.

### Batch 6 — Reports + monthly close | **~2 hours**

**Files to create (1):**

| File | Purpose | Hours |
|---|---|---|
| `app/services/reports.py` | monthly_stockout_report, monthly_close_summary | 2 |

**Acceptance:**
- Reports queryable via Python API.
- Unit-tested with synthetic data.

### Batch 7 — UI smoke test + headless screenshots | **~2 hours**

**Approach:** add a Playwright headless test that screenshots every page. Or: use `curl` against the running server and verify HTML structure.

**Lightweight approach (recommended):**
- Spin up uvicorn in background
- `curl -s localhost:8765/ | grep "Sistema de gestión"` (sanity check)
- `curl -s localhost:8765/inventario | grep "Stock bajo"` (check Spanish copy)
- `curl -s localhost:8765/ventas | grep "Anular"` (check void button)

**Files:**
- `tests/test_ui_smoke.py` — boots TestClient, hits each route, checks Spanish copy

**Acceptance:**
- All 6 routes return 200.
- Spanish copy present in HTML output.
- Money formatting renders correctly.

### Batch 8 — Install session on her PC | **~3 hours** (operator time, not clock-billed)

**Steps:**
1. Pre-install: confirm Python + uv available, AV exclusions added, R2 account created
2. `uv sync --all-extras` on her PC
3. Run `run.bat`, browser opens
4. Walk through: create ingredient, recipe, product, sale, void
5. Verify R2 encrypted snapshot uploaded
6. Verify local backup folder populated
7. Test restore: delete `rms.sqlite`, restart app, restore from R2
8. Verify offline mode (disconnect Wi-Fi)
9. Train her on the basics
10. Document in installer/README.md as the "first session" template

**Acceptance:**
- Saskia can run the app from a desktop shortcut.
- All 7 acceptance items from dev plan §1 pass.
- Restore from R2 works.
- Offline mode works.

### Batch 9 — Round 1 + Round 2 review | **~6 hours**

- Round 1 (3 days): she uses it, sends WhatsApp list of bugs
- Bug fixes from Round 1 (~3 hours of clock time)
- Round 2 (3 days): cosmetic round
- Final fixes from Round 2 (~3 hours)
- Sign-off via WhatsApp written OK

**Acceptance:**
- Saskia signs off via WhatsApp.
- All Phase-1 scope delivered.
- Final commit tagged `fase-1-accepted`.

### Total hours breakdown

| Batch | Hours | Cumulative |
|---|---:|---:|
| 1 (data layer) | 4.0 | 4.0 |
| 2 (routers + UI) | 12 | 16 |
| 3 (formal tests) | 3 | 19 |
| 4 (Excel service) | 6 | 25 |
| 5 (backup + R2) | 4 | 29 |
| 6 (reports) | 2 | 31 |
| 7 (UI smoke) | 2 | 33 |
| 8 (install) | 3 | 36 |
| 9 (review rounds) | 6 | 42 |
| **Already done in `154484d`** | 4 | **4 (already)** |
| **TOTAL** | 46 | 50 |
| **Buffer** | 20 | 70 |

That's 50 hours of build +20 hours of buffer (rework, install issues, Round 1 bugs) = **70h, within the quote**.

---

## 3. Verification protocol — how to check each batch

Every batch ends with this checklist (operator-runnable):

```bash
# Run from project root with the venv active

# 1. Lint clean
uv run ruff check .                # rc=0
uv run ruff format --check .        # rc=0

# 2. Tests pass
uv run pytest tests/ -v             # all green
uv run pytest --cov=app             # ≥ 80% coverage

# 3. Smoke (the 5-scenario data layer check)
# (the script lives at tests/smoke_test.py after Batch 3)

# 4. App boots
uv run uvicorn app.rms.main:app --host 127.0.0.1 --port 8765 &
sleep 3
curl -s http://127.0.0.1:8765/healthz | grep '"status":"ok"'
curl -s http://127.0.0.1:8765/healthz/db | grep 'journal_mode'
kill %1

# 5. Import-export roundtrip (after Batch 4)
uv run python -c "
from app.services.import_xlsx import from_file
from app.services.export_xlsx import to_file
from_file('tests/fixtures/mini.xlsx')
to_file('/tmp/test_export.xlsx')
from_file('/tmp/test_export.xlsx')
print('OK')
"

# 6. R2 roundtrip (after Batch 5)
# Mock R2 with moto; verify encrypt → upload → download → decrypt = original
```

For each batch, the `app/CHANGELOG.md` gets an entry:

```markdown
## [2026-09-XX] Batch N — <name>

**Time:** X.X / 70 h
**Files:** <list>
**Tests added:** <count>
**Coverage:** X%
**Smoke:** <pass/fail per scenario>
**Operator review:** <yes/no>
```

---

## 4. Progress dashboard

This is the visualization you asked for. After every batch, run:

```bash
cd /opt/data/profiles/ivan/scratch/saskia-build-status
./refresh.sh
```

It produces two artifacts:

### 4a. `STATUS.md` (text, machine-readable)

```yaml
---
generated_at: 2026-09-XX
commit: <SHA>
hours_used: 4.0 / 70
hours_budget: 70
budget_pct: 5.7%
batches_complete: [1]
batches_remaining: [2, 3, 4, 5, 6, 7, 8, 9]
tasks_complete: [0, 1, 2]
tasks_remaining: [3, 4, 5, 6, 7, 8, 9, 10]
tests_total: 88
tests_passing: 88
tests_failing: 0
coverage_pct: 80.0
coverage_target: 80.0
lint_errors: 0
lint_warnings: 0
ruff_format_errors: 0
files_total: 44
files_missing: 28
files_planned: 72
ruff:
  check: pass
  format: pass
pytest:
  count: 88
  failing: 0
smoke:
  recipe_batch_cost: pass
  sub_recipe_cost: pass
  cycle_detection: pass
  missing_price: pass
  apply_sale: pass
  void_sale: pass
features:
  data_layer: complete
  ui_layer: missing
  excel_io: missing
  backup_scheduler: missing
  r2_backup: missing
  reports: missing
  install: not_started
  review: not_started
```

### 4b. `STATUS.html` (visual, single file)

A self-contained HTML page with:

- **Header**: commit SHA, hours used / 70, % complete
- **Phase bars**: visual progress per dev-plan Task (1-10)
- **Test counts**: total tests, passing, failing, coverage % (gauge-style)
- **Lint status**: green/red badges
- **Smoke matrix**: 5-scenario × pass/fail
- **Feature matrix**: 7 features × status
- **Files-in-repo**: total / planned
- **Time budget**: hours per batch as a horizontal bar chart

The dashboard reads from `STATUS.md` and renders. No external dependencies. Generated locally; opens in any browser.

### 4c. How to use the dashboard

- **Before each batch**: open `STATUS.html` to see current state
- **After each batch**: re-run `refresh.sh`, verify new state
- **Before operator review**: open `STATUS.html`, check that all green badges are green, no red badges

---

## 5. Long-term upgrade paths (post-fase-1)

These are **NOT** in the current 70h quote. They're tracked here for future reference.

### Fase 1.5 — Minor enhancements (1-3 months after go-live)

| Upgrade | Hours | Quote (Gs.) | Notes |
|---|---:|---:|---|
| Recipe versioning (per-month, per-quarter cost layers) | 6 | 1,500,000 | Cook cost variance for accurate margins |
| Sub-recipe self-reference prevention UI (cycle detection) | 1 | 250,000 | Already in dev plan, but UI to display cycle warnings |
| Monthly close button (auto-generate end-of-month snapshot) | 3 | 750,000 | Single-click close + audit log |
| Supplier automation (when `purchases < threshold`, suggest buy) | 4 | 1,000,000 | "comprá 2kg de harina" |
| New-product onboarding UI (template-driven) | 3 | 750,000 | Wizard for first 10 products |
| Print-friendly dashboard (PDF export) | 2 | 500,000 | "Imprimir informe mensual" |
| **Subtotal** | **19** | **4,750,000** | |

### Fase 2 — Major modules (3-12 months after go-live)

| Module | Hours | Quote (Gs.) | Notes |
|---|---:|---:|---|
| **Planning assistant** (producción + compras + calendario) | 38 | 9,500,000 | Already parked internally per audio 20-aug |
| Merma / waste tracking | 8 | 2,000,000 | Already in product spec |
| Customer CRM | 8 | 2,000,000 | "Compradores recurrentes" |
| WA Business API integration (paid, with bot) | 14 | 3,500,000 | Replaces manual WA |
| **Subtotal** | **68** | **17,000,000** | |

### Fase 3 — Cloud sync (12+ months, only if scale demands)

| Upgrade | Hours | Quote (Gs.) | Recurring | Notes |
|---|---:|---:|---:|---|
| Supabase Postgres (cloud DB) | 25 | 6,250,000 | $25/mo | Quote renegotiation required |
| Customer-facing order app | 30 | 7,500,000 | $25/mo | Multi-tenant, public |
| Multi-location sync | 20 | 5,000,000 | $25/mo | Branch offices |
| **Subtotal** | **75** | **18,750,000** | +$75/mo | |

### Tier-based decision framework

For every future upgrade ask:

1. **Does it cost money recurring?** → Renegotiate the quote
2. **Does it move PII to a third party?** → Saskia's consent
3. **Does it add latency to daily use?** → Measure before committing
4. **Does it violate locked scope?** → Check the quote
5. **Does it help her specifically?** → Yes: Tier 1 or 8 candidate. No: skip.

---

## 6. Decision rules

- **At 60 hours cumulative**: explicit Ivan check-in. If behind, renegotiate scope with Saskia before continuing. If on-track, continue.
- **At 70 hours**: stop. Do not silently overflow. Tier-8 backup fits in the buffer; anything beyond is a renegotiation.
- **Every PR**: include `Time: X.X / 70 h` footer.
- **Every batch**: smoke-tested + dashboard updated.
- **Operator review points**: end of each batch. Ivan confirms before next batch starts (gives you a chance to redirect).
- **Round 1 + Round 2**: Saskia's review, your sign-off.

---

## 7. Failure modes + mitigations

| Failure | Mitigation |
|---|
| Saskia's Drive URL never arrives | Build with synthetic `mini.xlsx` + `stress.xlsx`; test the importer logic locally; document that the import run happens at install session |
| She has admin rights issues on her PC | Have her pre-install admin password; AV exclusion step before `uv sync` |
| Time overruns | 20h buffer in budget; can absorb a full day's worth of issues |
| Round 1 reveals big bugs | Round 2 fix-budget is 3h; bigger fixes are fase 1.5 |
| Saskia wants Cloud (Tier 4) | Quote renegotiation; see upgrade-tiers.md |
| She cancels before go-live | She's already paid first cuota; sunk cost |
| Saskia has unstable internet | Tier 1.1 / Tier 8 are local-first; doesn't depend on internet |

---

## 8. What I'm NOT going to do (operator confirmation needed for)

- ❌ Move to cloud (Tier 3+) without quote renegotiation
- ❌ Add Anthropic API or any LLM
- ❌ Build Fase 1.5 / 2 / 3 features inside the 70h budget
- ❌ Ship without Round 1 + Round 2 sign-off

---

## 9. Tooling for you (Ivan) to check progress

Three artifacts to keep open:

1. **`STATUS.md`** (text) — single source of truth, machine-readable
2. **`STATUS.html`** (visual) — opens in any browser, single file
3. **`docs/operations/2026-09-fase-1-specs.md`** — the build spec Kiki reads

Plus the **commit log** on `Ai-Whisperers/saskia-app` — every batch ends with a commit. The PR footer (`Time: X.X / 70 h`) lets you track budget consumption from the commit log alone.

---

*Drafted 2026-09 by Hermes. Operator review pending. Cost checkpoints at 30h, 50h, 60h.*