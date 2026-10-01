# CHANGELOG

## 2026-10-01
- **Schema 75** (`app/rms/config.py`): adds `suggestion_applied` to `loyalty_transaction.reason` ENUM (Tier 3.2).
- **Logging** (`app/rms/main.py`): rotating file sink (BACKLOG #45) — 50 MB / 7-day retention; env-tunable path.
- **Spool prune** (`app/rms/notifications.py`): bound `notifications_spool/dryrun-*` at 7 days; prevents local-disk bloat.
- **Migrations 60-62** (`app/rms/db.py`): wrap ORM-touching steps in try/except so fresh DBs don't fail when 072's columns don't exist yet.
- **JS init fix** (`app/static/pedido-combos.js`): initialise `window.customerPickHandlers` before assignment.
- **Tests** (`tests/test_daily_sales_series.py`, `tests/_fixtures_quick_seed.py`): anchor seed "today" sale to noon UTC so daily bucketing is TZ-stable; add `_asuncion_today()` helper. - User Guide v1.0 (screenshots + version drift check)

### New
- **24 real PNG screenshots** of every daily-use page captured via Playwright + cookie auth against the live Swarm URL. Replaces 22 "placeholder screenshot" references across 16 sections of `docs/user-guide/`.
- **`check_manual_version.py`** — verifies README's `schema NN · commit XXXX` header against `app/rms/config.py` and `git HEAD`. Exits non-zero on drift so CI can catch stale docs.
- **"Lo que podés hacer" matrix** in README — 16 confirmed-active daily workflows linked to their screenshots, 8 wishlist items bucketed by quarter, 3 known-fragility callouts.
- **Version pinning header** in README: three-form verification (browser footer, login response header, this manual) so Saskia can detect drift herself.
- **`tests/test_user_guide_version.py`** — 7 tests pin the contract: header present, drift check passes, every section embeds a screenshot, no placeholder strings remain, README documents both active and not-yet-active features.

### Fixes
- README pointed at **suspended** Render URL `saskia-rms.paragu-ai.com` (returns 503 / `x-render-routing: suspend-by-user`). Now points at the live Swarm URL `saskia-vps.paragu-ai.com` and warns about the suspended one.

### Stats
- 24 screenshots (5.5 MB total), 4 helper scripts (capture + replace + version-check), 17 doc files updated.
- `152 + 7 = 159` tests, `152/152` pass + 6 PG skip + 3 net skip.

### Deploy notes
- Manual lives in repo at `docs/user-guide/README.md`. No live deploy needed (markdown only).
- When schema or routes change: re-run `python3 docs/user-guide/capture_saskia_screenshots.py` and update the version header in README.md. Run `python3 docs/user-guide/check_manual_version.py` to confirm no drift.

## 2026-09-30 - reorder supplier redesign + scraper completion

### New
- **Manual supplier toggle** (Phase 1):  
  - 🔒 lock/unlock supplier on /reorder page (replaces automatic streak blocking)
  - Audit trail for lock/unlock events (action: "ingredient.supplier.lock/unlock")
  - 16 new tests covering: lock/unlock buttons, audit rows, error handling

- **Supplier CRUD** (Phase 2):  
  - Soft delete suppliers (preserves history, sets "inactive" status)
  - "Proveedores" tab on /settings/catalog links to /suppliers
  - 5 new tests: CRUD operations, soft delete, tab navigation

- **CSV price upload** (Phase 3):  
  - POST /reorder/upload-prices endpoint (CSV: ingredient_name,supplier_name,price_gs,date)
  - Auto-migration: adds supplier_id to IngredientPriceEvent (migration 073)
  - 10 new tests: CSV parsing, duplicate handling, audit trails, rollback safety

- **Superseis scraper** (Phase 4):  
  - HTTP + BeautifulSoup scraper for superseis.com.py
  - Handles ₲ 3.600 format and complex OpenCart layout
  - Graceful degradation for Stock.com.py (JS site, CSV-only fallback)
  - 13 new tests: parsing robustness, format extraction, graceful error messages

- **Scrape endpoint** (bonus):  
  - POST /reorder/scrape?q=<query> returns scraped prices per source
  - Writes audit row (action: "read.scraper.run")
  - 4 new tests: empty query, aggregation, audit tracing, audit failure handling

### Fixes
- - Fix depth counter in Superseis scraper: void HTML elements (img, input, br, etc.) don't emit closing tags, causing under-decremented depths and missed card completions. Now tracks only tag types that actually close via `</tag>`. 

- - Register 'network' pytest marker in pyproject.toml to silence test warnings.

### Stats
- 152 tests total (16 toggle + 5 CRUD + 10 CSV + 21 scrapers + 4 endpoint + 2 UI + 8 cheapest core + 3 UI cheapest + 13 daily series + 7 chart preset + 11 export period + 5 healthz docs + 22 reports + 6 PG regression + 8 mobile UX + 10 status dashboard)
- All tests pass at 145/145 (3 tests require network; 6 PG tests skip without Docker)

### Deploy notes
- Live at https://saskia-vps.paragu-ai.com/reorder  
- Auth: demo / demo1234  
- Test with: `pytest tests/reorder/** -q` (all phases)