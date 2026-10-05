<!-- ROADMAP-REDIRECT -->
# ⚠️ Moved / Superseded

**This file has been moved or superseded.** The canonical location is:

> **`docs/roadmap/STATUS.md`**

WHAT_NEXT has been replaced by `docs/roadmap/STATUS.md` (current state) and `docs/roadmap/BACKLOG.md` (forward-looking work).

See [`docs/roadmap/README.md`](docs/roadmap/README.md) for the full index.

---

<!-- ORIGINAL CONTENT BELOW -->

# Saskia · What Next? (Oct 2026)

## 📊 Current State — Where We Are

| Table | Rows | Status |
|-------|------|--------|
| supplier | 7 | ✅ HEREBUS seeds |
| delivery_zone | 6 | ✅ Asunción zones |
| ingredient | 77 | ✅ 44 HEREBUS + 33 default |
| recipe | 20 | ✅ 7 HEREBUS + 13 default |
| recipe_line | 189 | ✅ |
| recipe_pricing | 7 | ✅ Channels margins |
| product | 28 | ✅ |
| customer | 8 | ✅ |
| sale | 355 | ✅ |
| waste_log | 2 | ✅ |
| wishlist_item | 27 | ✅ 6 purchased |
| risk_item | 12 | ✅ |
| bank_transaction | 302 | ✅ Dutch EUR |
| settings_kv | 7 | ✅ Business hours + margins |

**Schema: v31** · **Tests: 50/50 passing** · **Routes: 26**

---

## 🚨 Gaps + Hidden Risks (what's broken or unfinished)

### 1. Sales channel mismatch — **HIGH RISK**
- 346 sales have `channel='mostrador'`, but 6 say 'retail' and 3 'wholesale'
- New HEREBUS-specific channels (Retail/Wholesale/Distributor/Eventual) aren't on the enum
- **Fix**: extend `Sale.channel` enum, add `/sales` filter by channel, auto-classify from VENTAS sheet's `Canal de Venta` column

### 2. Wishlist purchases don't trigger Inventory — **HIGH**
- When user clicks "Marcar comprado" on a Horno ₲1.5M, we flip a bit but:
  - No inventory entry created (₲1.5M should go to Fixed Assets or Equipment ledger)
  - No supplier order created
  - No depreciation start date set
- **Fix**: hook into `mark_purchased` to auto-create a Supplier order + Equipment entry

### 3. Production Planner doesn't actually generate shopping list — **KILLER FEATURE MISSING**
- We compute ingredient shortfalls but the "Generate shopping list" button is a no-op
- The `ShoppingListItem` table exists but is empty
- **Fix**: POST `/produccion-planner/compute/save-as-shopping-list/{plan_id}` to materialize

### 4. Sales SKU tracking + reorder alerts — **MEDIUM**
- 346 sales but only 28 products (most sales have `product_id=NULL`)
- Can't reconcile stock movement vs ingredient usage
- **Fix**: add `SaleStockMove` auto-creation in recipes router

### 5. Benchmarks = 0 rows imported — **MEDIUM**
- `Benchmarks_Market` has competitor prices but the import script didn't parse them
- User can manually enter competitor prices via `/benchmarks/{id}/edit`
- Currently no "Posición" scoring works

### 6. Bank statement: PY savings account not imported — **MEDIUM**
- WhatsApp bank statement image (June 2026) needs OCR/manual entry
- 302 EUR transactions imported, 0 PYG transactions
- **Fix**: add `/bank/upload-image` endpoint + manual entry form

### 7. Recipe photo manual link UI — **LOW**
- All 7 HEREBUS recipes have cookbook photos via hash distribution
- But user can't say "this photo IS this recipe" (just pure hash)
- **Fix**: add `/recetas/{id}/set-photo` endpoint

### 8. Delivery zones need a /delivery-zones/{id}/edit — **LOW**
- Zones seeded but no CRUD UI
- Currently requires SQL to update

### 9. NAV menu doesn't show new modules — **UX GAP**
- /wishlist, /riesgos, /pricing, /bank, /dashboard, /planner, /benchmarks, /delivery-zones — **none in nav menu**
- User has to remember URLs or browse via /guia

### 10. No audit trail for HEREBUS data — **COMPLIANCE**
- The 302 bank transactions have category auto-set but no review/edit UI
- `AuditLog` should record who imported which records

---

## 🎯 What's the BIGGEST bang-for-buck?

### 🏆 Top 5 next moves (ranked by ROI)

#### #1 — **Production Planner → Shopping List** (3 hr) — *Killer feature*
Just adds one POST route that materializes shortfalls into `ShoppingListItem`. Saskia has ALL data already; this single endpoint unlocks the end-to-end "ingredient need → buy list" loop that the spreadsheets are trying to do manually. Plus add `/shopping-list` view.

#### #2 — **Sale channel mismatch fix** (2 hr)
6 small things: extend enum, fix 3 'wholesale' rows marked wrong, add filter to `/ventas`, render channel breakdown on dashboard. Also easy to notice/break.

#### #3 — **Nav menu update** (1 hr) — 8 new modules visible
Add the 8 new sections to `_components/macros.html` or the topnav. Pure UX.

#### #4 — **Photo manual-link UI** (1.5 hr)
Show all 14 jpgs in a picker, let user attach each to a recipe. Forward-looking.

#### #5 — **Benchmarks manual edit form** (2 hr)
Form to set competitor prices, compute "Posición" automatically (vs Market avg).

### 🎁 Bonus polish (low risk, high satisfaction)

- **Currency formatting helper** (15 min): `₲ 1.500.000` instead of `1500000.0` — already used in some places but not all
- **Wishlist "supplier offer" link**: When mark-purchased, auto-generate WhatsApp link to prefill a vendor message
- **Benchmarks heatmap** (CSS): visualize +20% vs market in red
- **Bank statement manual entry form**: 30 lines of HTML

---

## 🛠️ Tooling & Plumbing

- **`scripts/import_herebus_data.py`** is idempotent and ready to re-run on every deploy
- **50 tests passing** — needs new test coverage as features land
- **2 commits** ready to push on last session (one was pushed: `2efc4c5`, one earlier `988d838`)

---

## 💼 Business-Operational priorities (vs Tech)

If you're running HEREBUS right now, the questions to ask Saskia are:
1. *"What's my food cost % this month?"* — partly works (Dashboard v1, but `Waste.cost_gs` is 0 for many rows because cost calc was fraction-only)
2. *"What do I need to buy tomorrow to bake 10 muffins?"* — **doesn't work** (Planner exists but doesn't push to shopping list)
3. *"Is Saskia paying more for flour than the other bakery down the street?"* — doesn't work (Benchmarks empty)
4. *"What kitchen equipment am I missing that would speed production?"* — works (Wishlist @ ₲60M)

**Top operational gap is #1 + #3 above.**

---

## 🧭 Recommended Plan (pick 1)

| Plan | What | Time | Impact |
|------|------|------|--------|
| **A** | Shipping pipeline (#1) + nav menu (#3) | 4hr | Big UX unlock |
| **B** | Benchmarks full loop (#5) + photo linker (#4) | 4hr | New strategic tool |
| **C** | Bank statement upload + PY savings | 4hr | Complete bank story |
| **D** | Channel mismatch fix + dashboard upgrade | 4hr | Pre-launch polish |
| **E** | Full security/audit hardening for prod | 1 day | Deploy-ready |
| **F** | Build the mobile-PWA version of the dashboard | 2-3 days | Deployment-ready UI |

Saskia is now feature-rich for v1.0 launch; the gaps above are mostly polish.
The two genuinely missing pieces that BLOCK actual HEREBUS work:
- **Shopping list from planner** (#1, plan A)
- **Production data → dashboard refresh** (so /dashboard shows LIVE data)
