# 2026-10-07 — saskia-app reuse/abstraction audit

**Scale:** 1–2 users, internal RMS, SQLite, server-rendered. 286 py files / 25.4k router LOC / 127 templates.
**Verdict:** stack choices are correct — no rewrites. But 6 concrete reuse/abstraction wins exist; 3 shipped today.

## Findings (measured, grep-backed)

| # | Finding | Evidence | Verdict |
|---|---|---|---|
| 1 | **No central `apply_stock_delta()`** — 22 `StockMovement(...)` constructions; 10 sites bump `ing.stock_qty` AND write the movement row by hand (~8 lines each) | `grep -rn 'StockMovement('` across routers+rms | **Ship** — `app/rms/stock_ledger.py` |
| 2 | **Unit-conversion block copy-pasted 3× with DIVERGED behavior**: shopping.py lands raw qty silently on mismatch; reorder.py + waste.py raise 400. Same input, different outcome per route | `Unit.coerce` in 3 files | **Ship** — same helper module |
| 3 | **`clock.py` helpers exist but 302 call sites bypass them** (119 `datetime.now(ASUNCION_TZ)`, 183 `datetime.now(timezone.utc)`); 2 clock-discipline tests FAIL on main right now (seed/packs.py generator template + pedidos.py) | `pytest tests/test_clock_discipline.py` = 2 failed | **Ship** — fix the 2 failing; broad migration is mechanical, not urgent |
| 4 | **44 model classes defined twice** (models_legacy.py + models/ domain package); `models/__init__` re-exports 100% from legacy; `models/procurement.py`, `models/herbus_drive.py`, `models/catalogs_restored.py` have **0 importers** — pure dead mirrors. This exact trap caused today's SASKIA-206 bug (field added to dead copy → `invalid keyword argument` 500) | `comm -12` class lists; runtime `inspect.getfile` | **Ship** — deprecation markers on the 3 dead modules; full delete = separate ticket (L) |
| 5 | `current_user_id(request) or "operator"` repeated **47×** | grep | Ship later — mechanical, low risk |
| 6 | Flash-by-querystring pattern ×43 with **inconsistent param names** (`flash` 66, `error` 4, `msg` 2) | grep | Ship later — also a UX consistency fix |
| 7 | `PAGE_SIZE` defined 3× (auditoria 50, customers 50, sales 20) | grep | Ignore — 3 sites, distinct values, fine |
| 8 | **89 direct `purchase_price_gs` reads** bypass `current_variant_price()` — the variant-price 3-consumer contract (skill-documented) is only partially enforced | grep | Decide — some reads are legitimately parent-price; audit per-consumer before touching |

## Shipped today (this commit)

1. **`app/rms/stock_ledger.py`** — `apply_stock_delta()` (bump + movement row + audit field, one call) and `qty_to_stock_unit()` (convert or fall back per explicit policy). Refactored the two flows I wrote today (shopping mark-purchased, wishlist equipment) + waste.py to use them. New tests lock the contract.
2. **Clock fixes** — `scripts/seed_packs_gen.py` template now emits `clock.now()`; `pedidos.py` routes use `clock` helpers. `test_clock_discipline` green.
3. **Deprecation headers** on `models/procurement.py`, `models/herbus_drive.py`, `models/catalogs_restored.py`: "runtime class lives in models_legacy.py — add new columns THERE" (the pitfall, now visible at the top of the file that invites it).

## Do NOT change (defended)

- Server-rendered Jinja + vanilla CSS — correct at this scale (2026-09-02 audit verdict stands).
- models_legacy as runtime SSOT — the 44-dup situation is ugly but **working**; a domain-package migration is L-effort with migration-file risk. Deprecation markers first, delete later.
- The `models/__init__` re-export shim — it's what keeps the dual definition harmless today.

## Follow-ups queued (not shipped)

- `current_operator()` dependency (47 sites) — 30 min, purely mechanical.
- `redirect_flash()` helper + unify `flash`/`error`/`msg` param — 1 h, touches many routes, do on a quiet day.
- Variant-price consumer audit (89 reads) — needs per-site judgment, half a day.
- Dead model-module deletion — after 2 clean weeks with deprecation headers.
