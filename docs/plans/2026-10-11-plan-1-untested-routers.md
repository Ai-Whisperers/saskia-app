# Plan 1 — Cover the 12 untested routers (8h, P0)

> **Master plan:** `docs/plans/2026-10-11-round-5-6-master-plan.md`
>
> **Goal:** Add direct route tests for every router that has 0
> of them. ~69 tests across 12-15 new files. Smoke-level
> coverage that catches future regressions in route wiring.

---

## Why this is P0

The 12 untested routers include:

- `settings_runtime` (41 routes) — admin configuration of pricing,
  templates, taxes. **A typo in any route path = silent
  misconfiguration** that won't be caught until prod breaks.
- `customers` (20 routes) — PII, soft-delete, credit limits.
  Missing route tests = missing coverage of audit-gated actions.
- `products` (17 routes) — catalog CRUD with variants, allergens.
  Same risk.
- `suscripciones` (8 routes) — recurring customer orders.
  Misses here = recurring revenue tracking silently broken.

Smoke tests are cheap (15-20 min each), they catch wiring bugs,
and they can be deepened later.

---

## Method (copy-paste template)

For each router, follow this pattern:

1. Read `app/routers/<router>.py` and count routes
   (`grep -E '^@router\.(get|post|put|delete|patch)'`).
2. Read each route's signature to learn:
   - HTTP method + path
   - Query parameters (e.g. `?new_price=N`, `?product_id=X`)
   - Path parameters (e.g. `{ingredient_id}`)
   - Required auth (most use `Depends(get_session)` or `Depends(require_admin)`)
3. Create `tests/test_<router>_routes.py` with one test per route.
4. Use the `authed_client` fixture (admin session) and
   `session_factory` (real DB session) from `tests/conftest.py`.
5. For each route:
   - GET: assert 200 + non-empty body
   - POST/PUT/DELETE: assert 303 redirect or 200 with a follow-up
     GET that confirms the state changed

### Pattern (copy-paste for each file)

```python
"""tests/test_<router>_routes.py — SASKIA audit (round 6).

The <router> router (app/routers/<router>.py) had 0 direct route
tests. These are smoke-level: each route returns 200 with the
expected shape. They catch future regressions in route wiring
(typo in path, missing import, template rename).
"""

from __future__ import annotations

import pytest


# ── /<path>/one ─────────────────────────────────────────────────
def test_<router>_one_returns_200(authed_client):
    """GET <path>/one → 200 (route wiring)."""
    r = authed_client.get("<path>/one")
    assert r.status_code == 200
    # The page should reference its topic (use Spanish from the
    # template, e.g. "Clientes" for customers).
    body = r.text
    assert "<expected topic>" in body or "sin datos" in body.lower()


# ── /<path>/api/one ─────────────────────────────────────────────
def test_<router>_api_one_returns_json(authed_client):
    """GET <path>/api/one → JSON (route wiring)."""
    r = authed_client.get("<path>/api/one")
    assert r.status_code == 200
    import json
    data = json.loads(r.text)
    assert isinstance(data, (list, dict))
```

### Common gotchas (from round 5 work)

1. **Query params are REQUIRED for some routes.** If the route
   signature is `new_price: int = Query(..., ge=0)`, you must
   pass `?new_price=5000` or you get 422. Use the
   `params={...}` arg on `client.get()`.
2. **Admin-only routes may return 403 with the wrong user.**
   `authed_client` is the admin; `client` (no fixture) is anon.
   Use `authed_client` for admin routes.
3. **Some routes redirect (303) on success.** Check the route
   code first — if it returns `RedirectResponse`, assert 303
   and check `Location` header.
4. **Form-POST routes expect form data, not JSON.** Use
   `data={...}` not `json={...}`.
5. **Routes that touch external systems (Herebus, Supabase)
   may need monkeypatching.** Check for `import herebus` or
   `import supabase` in the route — if found, mark the test
   as `@pytest.mark.skip(reason="external system")` until
   plan 1.5 (testcontainers) ships.

---

## The 12+3 work items

### 1.1 — settings_runtime (2h, 41 routes → 20 tests)

Largest gap. The 41 routes break into:
- 8 GETs (read config)
- 12 POSTs (write config)
- 15 GETs that return JSON (preview, validate)
- 6 admin-only

**Top 20 to test (by risk):**

1. `GET /api/settings/pricing-markup/preview` (used in dashboard)
2. `GET /api/settings/pricing-mode` (high-traffic read)
3. `POST /api/settings/pricing-mode` (write)
4. `GET /api/settings/loyalty-config` (operator-facing)
5. `POST /api/settings/loyalty-config` (write)
6. `GET /api/settings/cost-display` (POS display)
7. `POST /api/settings/cost-display` (write)
8. `GET /api/templates/{key}` (operator template editor)
9. `POST /api/templates/{key}` (write)
10. `GET /api/settings/tax-config` (financial)
11. `POST /api/settings/tax-config` (write)
12. `GET /api/settings/sms-templates` (operator)
13. `POST /api/settings/sms-templates` (write)
14. `GET /api/settings/refund-policy` (financial)
15. `POST /api/settings/refund-policy` (write)
16. `GET /api/settings/opening-hours` (UI)
17. `POST /api/settings/opening-hours` (write)
18. `GET /api/settings/print-receipt-header` (POS)
19. `POST /api/settings/print-receipt-header` (write)
20. `GET /api/settings/feature-flags` (used by every page)

Each test: ~5min. Total: 1.5-2h.

### 1.2 — customers (1h, 20 routes → 8 tests)

Top 8:
1. `GET /clientes` (list, no-arg)
2. `GET /clientes/new` (form)
3. `POST /clientes/new` (create)
4. `GET /clientes/{id}` (detail)
5. `GET /clientes/{id}/edit` (form)
6. `POST /clientes/{id}/edit` (update)
7. `POST /clientes/{id}/delete` (soft-delete)
8. `GET /clientes/{id}/fiado` (credit account view)

### 1.3 — products (1h, 17 routes → 8 tests)

Top 8:
1. `GET /productos` (list)
2. `GET /productos/new` (form)
3. `POST /productos/new` (create)
4. `GET /productos/{id}` (detail)
5. `GET /productos/{id}/edit` (form)
6. `POST /productos/{id}/edit` (update)
7. `POST /productos/{id}/delete` (soft-delete)
8. `GET /productos/{id}/allergens` (allergen list)

### 1.4 — suscripciones (1h, 8 routes → 5 tests)

All 8 (smaller):
1. `GET /suscripciones`
2. `GET /suscripciones/new`
3. `POST /suscripciones/new`
4. `GET /suscripciones/{id}`
5. `GET /suscripciones/{id}/pause`

### 1.5 — caja (DONE, round 5)

### 1.6 — insights_stock (30min, 4 routes → 4 tests)

All 4:
1. `GET /insights/stock`
2. `GET /insights/stock/api/{ingredient_id}`
3. `GET /insights/stock/recetas` (recipes view)
4. `GET /insights/stock/api/substitutes/{ingredient_id}`

### 1.7 — excel_io (30min, 6 routes → 4 tests)

Top 4 (skip the 2 that need real file uploads):
1. `GET /excel/template/{kind}` (download template)
2. `GET /excel/export/{kind}` (download data)
3. `GET /excel/import` (upload form)
4. `GET /excel/export.csv` (CSV variant)

### 1.8 — analisis (30min, ? routes → 3 tests)

Top 3:
1. `GET /analisis`
2. `GET /analisis/ventas`
3. `GET /analisis/margenes`

### 1.9 — copiloto (30min, ? routes → 3 tests)

Top 3 (operator assist):
1. `GET /copiloto`
2. `GET /copiloto/sugerencias`
3. `POST /copiloto/feedback`

### 1.10 — gerencia (15min, 19 lines → 2 tests)

Only 19 lines. Likely 1-2 routes. Both:
1. `GET /gerencia`
2. `GET /gerencia/kpis`

### 1.11 — menus (30min, ? routes → 3 tests)

Top 3 (planning):
1. `GET /menus`
2. `GET /menus/{id}/edit`
3. `POST /menus/{id}/edit`

### 1.12 — herebus (30min, ? routes → 2 tests)

Read `app/routers/herebus.py` first. Likely 1-3 routes for
the Here Maps integration. If any hit the real API, mark as
`@pytest.mark.skip(reason="external system")`.

### 1.13 — photo_credits (5min, 1 route → 1 test)

Trivial. Just `GET /photo-credits`.

### 1.14 — users (1h, ? routes → 5 tests)

Auth and user management. Top 5:
1. `GET /usuarios` (list)
2. `GET /usuarios/new` (form)
3. `POST /usuarios/new` (create)
4. `GET /usuarios/{id}/edit` (form)
5. `POST /usuarios/{id}/edit` (update)

### 1.15 — cotizador (30min, ? routes → 3 tests)

Price quote tool. Top 3:
1. `GET /cotizador`
2. `POST /cotizador/calcular`
3. `GET /cotizador/historial`

---

## Acceptance criteria

1. **15 new test files** (12 routers + 3 utility).
2. **~69 new tests** total.
3. All new tests pass in isolation **and** in the full suite.
4. **0 new test pollution** (no test depends on state from
   another test in a non-obvious way).
5. **No regression** in existing 7,997 tests.

## How to verify

```bash
# Run the new files
uv run pytest tests/test_settings_runtime_routes.py tests/test_customers_routes.py \
  tests/test_products_routes.py tests/test_suscripciones_routes.py \
  tests/test_insights_stock_routes.py tests/test_excel_io_routes.py \
  tests/test_analisis_routes.py tests/test_copiloto_routes.py \
  tests/test_gerencia_routes.py tests/test_menus_routes.py \
  tests/test_herebus_routes.py tests/test_photo_credits_routes.py \
  tests/test_users_routes.py tests/test_cotizador_routes.py \
  --no-cov -p no:cacheprovider

# Then full suite
uv run pytest tests/ --no-cov -p no:cacheprovider -m "not (browser or e2e or pg or manual)"
```

## Ship-blocked-by
Plan 0 (commit uncommitted work first).

## Risk
Low. Smoke tests can't break anything; they only catch regressions.

## Owner / next action
**Ship settings_runtime first** (largest gap, highest risk). Use
the same `authed_client` + `session_factory` pattern that the
round-5 work used.
