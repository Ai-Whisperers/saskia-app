# Static-Content Audit Phase 7 — Magic Numbers, Tax Constants, and Status Thresholds

**Author:** Hermes Agent (MiniMax-M3)
**Date:** 2026-09-24
**Audience:** Kiki, future agents
**Scope:** Find and DB-drive remaining magic numbers, business-rule constants,
and threshold values that are currently hardcoded in Python logic.
**Continues:** docs/operations/2026-09-24-static-content-audit.md

---

## TL;DR

Phases 1-6 extracted 8 catalog/settings types to the DB. This Phase 7 audit
finds 6 more categories of hardcoded business logic that operators should
control without code deploy:

| # | What's hardcoded | Where | Severity | Effort |
|---|---|---|---|---|
| 1 | **Margin tier thresholds** (10000/5000/1000 Gs) | `app/rms/tags.py:378-382` | **High** — filters recipes incorrectly if economy changes | Small |
| 2 | **Stock status thresholds** (ratio 0.5/5.0, age 30d) | `app/rms/tags.py:325-331` | **High** — "bajo_min/critico/sobrestock/muerto" mis-categorize | Small |
| 3 | **IVA default rate "10" + tax regime "resimple"** | 6+ files | **Medium** — Paraguay tax law changes require code deploy | Small |
| 4 | **Invoice type set `{boleta_resimple, factura, none}`** | `app/routers/sales.py:499` | **Medium** — adding a new invoice type requires code | Small |
| 5 | **Labor cost 25000 Gs/h + overhead 15%** | 4 files | **Medium** — operators set these in /settings, but defaults are hardcoded | Trivial (already in ComplianceInfo) |
| 6 | **Date range presets** (last 7/30/90 days) | `app/routers/dashboard.py`, `reportes.py` | **Low** — UX consistency | Small |

Plus: **business rules that should be extracted into a single config module**
for consistency (not strictly DB-driven, but consolidated).

---

## Detailed findings

### 1. Margin tier thresholds (HIGH severity)

**Location:** `app/rms/tags.py:378-382`

```python
if f.margin_tier == "top_10" and cost > 10000:
    continue
if f.margin_tier == "top_25" and cost > 5000:
    continue
if f.margin_tier == "bottom_25" and cost < 1000:
    continue
```

**Problem:**
- These thresholds are **magic numbers** baked into filtering logic.
- If Paraguay's economy shifts (inflation, costs rise), the "top 10% of recipes"
  tier silently stops making sense — operators can't adjust.
- The tier names ("top_10", "top_25", "bottom_25") imply **percentile-based
  filtering** but actually use **fixed cost thresholds**. Misleading.

**Fix:**
- New `margin_tier` table (`id, code, label, min_cost_gs, max_cost_gs,
  percentile_min, percentile_max, sort_order, is_active`)
- Seed with the current 3 tiers + add proper percentile-based ones
- `filter_recipes()` reads from table instead of if-chain
- API: `GET /api/margin-tiers`, `POST /api/margin-tiers`

### 2. Stock status thresholds (HIGH severity)

**Location:** `app/rms/tags.py:325-331`

```python
if f.stock_status == "bajo_min" and ing.stock_qty >= ing.min_stock_qty:
    continue
if f.stock_status == "critico" and ratio >= 0.5:
    continue
if f.stock_status == "sobrestock" and ratio < 5:
    continue
if f.stock_status == "muerto":
    if ing.last_consumed_at is not None:
        age = (datetime.now(timezone.utc) - ing.last_consumed_at.replace(...)).days
        if age < 30:
            continue
```

**Problem:**
- Hardcoded magic numbers: `0.5` ratio for "critico", `5.0` for "sobrestock",
  `30` days for "muerto".
- Operator has no way to say "I want critico at 0.3 ratio" (more aggressive)
  or "extend muerto to 90 days".
- These are **business policy decisions**, not technical constants.

**Fix:**
- New `stock_status_threshold` table (one row per status code, with operator-
  tunable thresholds) OR SettingsKV JSON with the thresholds
- `filter_inventory()` reads from config
- Per `app/rms/AGENTS.md`: stock moves are atomic — but the **categorization**
  of stock levels is operator policy.

### 3. IVA rate + tax regime (MEDIUM severity)

**Location:** 6+ files
- `app/rms/models.py:224` — `Product.iva_rate` default `"10"`
- `app/rms/models.py:289` — `Sale.iva_rate` default `"10"`
- `app/rms/db.py:1259` — `compliance_info.iva_default_rate` default `"10"`
- `app/routers/settings.py:91` — `tax_regime` form default `"resimple"`
- `app/routers/sales.py:72-76` — `_get_tax_regime()` default `"resimple"`
- `app/routers/dashboard.py:246` — `if ci.tax_regime == "resimple" ...`

**Problem:**
- Paraguay's IVA general rate is 10% (per Ley 125/91 Art. 91 inc. e), but
  certain products are exempt (medicines, books) at 0% or reduced to 5%.
- Today the 10% / resimple / boleta_resimple trio is hardcoded across 6+ files.
- Changing tax law = 6+ code deploys.
- The ComplianceInfo table already exists (migration 035) — but the
  *fallback defaults* are still hardcoded.

**Fix (mostly already done — just consolidate):**
- ComplianceInfo table is the right home. Add a `get_iva_default_rate()`
  helper that reads from ComplianceInfo with `DEFAULT_IVA_RATE = "10"` as
  the documented fallback. Same for `get_tax_regime()`.
- The `invoice_type` set `{boleta_resimple, factura, none}` — extract to a
  constant module: `app/rms/constants.py` with `INVOICE_TYPES` frozenset.
- Optionally expose via SettingsKV for future-proofing.

### 4. Invoice types (MEDIUM severity)

**Location:** `app/routers/sales.py:499`

```python
if invoice_type_clean not in {"boleta_resimple", "factura", "none"}:
    invoice_type_clean = "boleta_resimple"
```

**Problem:**
- Hardcoded set of valid invoice types. Adding a new type (e.g., "nota_credito")
  requires editing this line + the model + migration 037.
- No single source of truth.

**Fix:**
- New `InvoiceType` enum or DB table (`code, label, requires_timbrado,
  requires_ruc, sort_order`)
- Validation against this source
- Used by `app/rms/models.py:281` default, `sales.py:499` validation

### 5. Labor cost + overhead (LOW — already in DB)

**Location:** `app/rms/prime_cost.py:112`, `db.py:1233`

The `labor_cost_per_hour_gs = 25000` and `overhead_multiplier_pct = 15`
defaults are already persisted in the `compliance_info` table (migration 035).
The "hardcoded" 25000/15 are just **fallback defaults** when ComplianceInfo
doesn't have a row yet.

**Fix (minor):**
- Centralize the fallback in a single module: `app/rms/constants.py` with
  `DEFAULT_LABOR_COST_PER_HOUR_GS = 25_000` and `DEFAULT_OVERHEAD_MULTIPLIER_PCT = 15`
- All callers import from there instead of duplicating the literal

### 6. Date range presets (LOW severity)

**Location:** `app/routers/dashboard.py:87,386,393,396`, `reportes.py:220,259`,
`inventory.py:157`, etc.

```python
start = end - timedelta(days=7)  # weekly
start = end - timedelta(days=30)  # monthly
day_of_week_heatmap(session, days=90)  # quarterly
price_history(session, ing.id, days=90)  # quarterly
```

**Problem:**
- Multiple `timedelta(days=N)` calls scattered through the codebase.
- Operator can't add "last 14 days" as a saved preset without code changes.

**Fix:**
- New `date_range_preset` table OR SettingsKV JSON with named presets:
  - `today` (days=1)
  - `week` (days=7)
  - `month` (days=30)
  - `quarter` (days=90)
  - `year` (days=365)
- Refactor callers to use the preset helper

### 7. Timezone — partially handled

**Location:** 6+ files reference `America/Asuncion`

This is already centralized in `app/rms/config.py:ASUNCION_TZ`. Most callers
correctly use it. The few outliers should be fixed but aren't blocking.

### 8. Stock dead-stock threshold (HIGH severity)

The 30-day threshold for "muerto" (dead stock) is in the same block as the
stock_status thresholds — fix together with #2.

---

## Refactoring recommendations (not DB-driven, but consolidation)

Beyond DB extraction, the following refactors improve code health:

### R1. Extract `app/rms/constants.py`

Move all the small "business constants" into one module:
```python
# app/rms/constants.py
"""Business constants for Sazón.

Values that operators might want to tweak but don't need a UI for. Larger
or more dynamic configs live in SettingsKV; tabular configs (channels,
payment methods) live in their own tables; these are the simple defaults.
"""

from decimal import Decimal

# ─── Money ────────────────────────────────────────────────────────
CURRENCY_CODE = "PYG"
CURRENCY_SYMBOL = "Gs."
THOUSANDS_SEPARATOR = "."

# ─── Tax (Paraguay) ────────────────────────────────────────────────
DEFAULT_IVA_RATE = "10"  # Ley 125/91 Art. 91 inc. e — general rate
DEFAULT_TAX_REGIME = "resimple"  # most small businesses
INVOICE_TYPES = frozenset({"boleta_resimple", "factura", "none"})
DEFAULT_INVOICE_TYPE = "boleta_resimple"

# ─── Stock status thresholds (overridable per operator) ──────────
# These are DEFAULTS — operators can override via /settings/inventory.
DEFAULT_STOCK_RATIO_CRITICO = Decimal("0.5")  # stock_qty / min_stock_qty
DEFAULT_STOCK_RATIO_SOBRESTOCK = Decimal("5.0")  # stock_qty / min_stock_qty
DEFAULT_DEAD_STOCK_DAYS = 30  # no consumption in N days

# ─── Costing (overridable via ComplianceInfo) ─────────────────────
DEFAULT_LABOR_COST_PER_HOUR_GS = 25_000
DEFAULT_OVERHEAD_MULTIPLIER_PCT = 15
DEFAULT_YIELD_PERCENTAGE = Decimal("0.85")  # 15% moisture loss for breads

# ─── Pagination ────────────────────────────────────────────────────
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 500

# ─── Margin tier filtering ────────────────────────────────────────
MARGIN_TIER_DEFAULTS = {
    # Legacy hardcoded tiers (will move to DB in this phase)
    "top_10": {"max_cost_gs": 10_000, "label": "Top 10%"},
    "top_25": {"max_cost_gs": 5_000, "label": "Top 25%"},
    "bottom_25": {"min_cost_gs": 1_000, "label": "Bottom 25%"},
}

# ─── Date range presets ───────────────────────────────────────────
DATE_RANGE_PRESETS = {
    "today": 1,
    "week": 7,
    "month": 30,
    "quarter": 90,
    "year": 365,
}
```

### R2. Refactor `app/rms/tags.py` to use the new helpers

Replace the if-chain on `f.margin_tier` and `f.stock_status` with lookups
against the new DB tables (or constants as fallback).

### R3. Centralize `_get_tax_regime()` and `get_iva_default_rate()`

Move these into ComplianceInfo helpers in `app/rms/models.py` or
`app/rms/constants.py` so all callers use the same fallback chain.

---

## Implementation plan (this session — Phase 7)

### Step 1: Create `app/rms/constants.py`
- Single source of truth for business constants
- All callers updated to import from here

### Step 2: Migration 045 — `margin_tier` table
- `id, code, label, min_cost_gs, max_cost_gs, sort_order, is_active`
- Seed with 3 legacy tiers (preserve current behavior exactly)
- API: `GET /api/margin-tiers`

### Step 3: Migration 046 — `stock_status_config` table
- One row per status code with operator-tunable thresholds
- Seed: `bajo_min` (qty < min), `critico` (ratio < 0.5), `sobrestock` (ratio > 5), `muerto` (days > 30)
- API: `GET/POST /api/stock-status-config`

### Step 4: Update `filter_inventory` and `filter_recipes`
- Read thresholds from DB instead of hardcoded if-chain
- Cache the config per request (avoid 1000s of small queries)

### Step 5: API endpoints for tax + invoice
- `GET/POST /api/iva-rates` (default + override)
- `GET/POST /api/invoice-types` (DB-driven)

### Step 6: Update ComplianceInfo to be the canonical source
- Refactor `_get_tax_regime()` callers to use one helper
- Document the fallback chain

### Step 7: Tests + deploy
- Property tests for the tier math (already exist in test_costing.py)
- Verify on VPS

---

## Estimated impact

| Change | Operator benefit |
|---|---|
| Margin tier table | Operators can adjust tier thresholds when economy shifts |
| Stock status config | "Critico at 0.3" / "Muerto at 90 days" via UI |
| Tax/invoice constants | Future tax law changes don't require code deploy |
| `app/rms/constants.py` | One source of truth for business constants |

Total estimated effort: 4 hours (already spent: 0.5h on this audit doc).

---

## What's already good (no work needed)

- ✅ `Unit` enum — single source for unit coercion (`app/rms/units.py`)
- ✅ Currency formatting — `app/rms/money.py:format_gs()` is the canonical helper
- ✅ Timezone — `app/rms/config.py:ASUNCION_TZ` central reference
- ✅ HACCP storage column — already a VARCHAR on `ingredient` (free-text
  but no magic numbers behind it)
- ✅ Difficulty scale — already a 1-5 integer on `recipe`
- ✅ IVA rate column — already on `product` (per-product override)
- ✅ ComplianceInfo — has the right shape, just needs to be the canonical
  read path

---

## Cross-references

- `docs/operations/2026-09-24-static-content-audit.md` — Phases 1-6 done
- `app/rms/AGENTS.md` — money/unit/time/recipe/stock hard rules
- `app/rms/constants.py` (NEW) — business constants module
- `app/rms/tags.py:325-385` — current hardcoded tier + stock_status logic
- `app/routers/sales.py:72-76,499` — tax regime + invoice type references
- `app/rms/prime_cost.py:112` — labor cost fallback
