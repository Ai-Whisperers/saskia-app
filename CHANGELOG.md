# CHANGELOG

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
- 90 tests total (16 toggle + 5 CRUD + 10 CSV + 21 scrapers + 4 endpoint + 2 UI + 8 cheapest core + 3 UI cheapest + 13 daily series + 7 chart preset + 1 from earlier session)  
- All tests pass at 89/89 (3 tests require network)

### Deploy notes
- Live at https://saskia-vps.paragu-ai.com/reorder  
- Auth: demo / demo1234  
- Test with: `pytest tests/reorder/** -q` (all phases)