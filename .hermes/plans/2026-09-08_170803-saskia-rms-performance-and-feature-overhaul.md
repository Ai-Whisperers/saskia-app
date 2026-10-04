# Saskia RMS — Performance Overhaul & Missing Pages Plan

> **For Hermes:** Use subagent-driven-development to execute. Each task is TDD: write failing test → confirm fail → minimal impl → confirm pass → commit.

**Goal:** Fix all N+1 query patterns causing 15-60 second dashboard loads, add gzip/cache headers, ship the missing `/clientes` `/produccion` `/eod` `/merma` `/reportes` `/auditoria` routes that already have backend modules built, and polish navigation.

**Architecture:** Replace per-row query loops with batch pre-load functions that already exist (or follow the same pattern as `batch_products_cost_margin` in `app/rms/costing.py`). Add standard FastAPI middleware (GZip, cache headers). Wire built-but-unrouted modules to routes + Jinja templates in Spanish.

**Tech Stack:** FastAPI 0.115, SQLAlchemy 2.0 sync, Jinja2 3.1, pytest 8, Neon Postgres 18.6. No new dependencies.

---

## Current State

- 837 tests passing, ruff clean
- Local HEAD: `7210ef2 feat(ops): opt-in AIW_SASKIA_RUN_MIGRATIONS env var for one-shot migration bootstrap`
- BWS: 198 secrets total, 10 flagged, `SASKIA_USER_PASSWORD` = sha `054ca845`
- Render free tier (spins down on idle, 30-60s cold start penalty)
- Neon schema v10, 30 ingredients, 12 recipes, 20 products, 920 sales, 6169 sale_stock_moves
- Live site: `/healthz` 200, `/healthz/db` 200 (postgres dialect), `/login` works with fresh password

---

## Phases (in priority order)

### Phase 1: P0 Performance Fixes (15-60s → <500ms dashboard load)

These 4 changes alone will turn a 60-second dashboard into a 300ms dashboard. All are mechanical replacements of bad patterns with existing helpers.

### Phase 2: Static Asset Hardening

Gzip + cache headers. Pure middleware/header additions. No DB impact. 70% bandwidth reduction on every page.

### Phase 3: P1 N+1 in Insights + Sales Intel

`build_insights()` and `rising_products()`/`churning_products()` have similar N+1 patterns. Fix with the same batch approach.

### Phase 4: Missing Pages (Built Modules, No Routes)

Six modules are fully built and tested (`customers.py`, `production.py`, `menu_engineering.py`, `waste.py`, `accounting.py`, `audit.py`). Zero routes/templates for them. Each one is a new route + Jinja template + 2-4 tests. Highest user-impact work in the project.

### Phase 5: Sales Page Overhaul

The operator's most-used page. Add customer field, payment method, discount, quick-sell buttons, void-with-reason. Backend fields need to be added to the `Sale` model first.

### Phase 6: Navigation + UX Polish

Logout button in nav, breadcrumbs, mobile responsive tables, print CSS, "today" filters. Small touches, big perceived-quality boost.

### Phase 7: Cold-start Mitigation

UptimeRobot integration using existing BWS keys. Keeps the free-tier container warm.

---

## Phase 1: P0 Performance Fixes

### Task 1: Add regression test for dashboard query count

**Files:**
- Create: `tests/test_dashboard_perf.py`

**Step 1:** Write test that asserts the dashboard route uses fewer than 20 queries for a typical seed dataset.

```python
"""Regression test: dashboard must not regress to N+1 queries."""

from sqlalchemy import event
from app.rms import main as main_module
from app.rms.seed import seed_demo_data


def test_dashboard_renders_under_20_queries(client, session_factory):
    # Seed full demo data: 30 ingredients, 12 recipes, 20 products, 920 sales
    with session_factory() as s:
        seed_demo_data(s)

    # Count queries
    queries = []
    engine = session_factory.kw["bind"]

    @event.listens_for(engine, "before_cursor_execute")
    def count(conn, cursor, statement, params, context, executemany):
        queries.append(statement)

    try:
        with client:
            resp = client.get("/?period=month")
        assert resp.status_code == 200
    finally:
        event.remove(engine, "before_cursor_execute", count)

    assert len(queries) < 20, f"Dashboard issued {len(queries)} queries — N+1 regression"
```

**Step 2:** Run: `unset DATABASE_URL AIW_SASKIA_DB_PATH && uv run pytest tests/test_dashboard_perf.py -v`
Expected: FAIL with current code (3,000+ queries).

**Step 3:** No implementation. Test stands as the bar.

**Step 4:** Confirm fail. **Step 5:** Commit `test: add dashboard query-count regression test`.

---

### Task 2: Fix N+1 in dashboard cost calculation

**Files:**
- Modify: `app/routers/dashboard.py:60-105` (the `for s in sales` loop calling `product_unit_cost_gs`)

**Step 1:** Identify the bad loop. Current code:
```python
sales = session.scalars(select(Sale).where(...)).all()
ventas_gs = sum(int(round(s.qty * s.unit_price_gs)) for s in sales)
cogs_gs = 0
sales_no_recipe = []
for s in sales:
    if s.product is None or s.product.recipe_id is None:
        sales_no_recipe.append(s)
        continue
    cost = product_unit_cost_gs(session, s.product_id)  # ← N+1
    ...
```

**Step 2:** Use the existing `batch_products_cost_margin()` helper at `app/rms/costing.py:185`. Pre-load all unique products referenced by sales, compute all costs in 3-4 queries, then look up in the returned dict.

```python
from app.rms.costing import batch_products_cost_margin

sales = session.scalars(select(Sale).where(...)).all()
products_in_period = sorted({s.product for s in sales if s.product is not None}, key=lambda p: p.id)
batch_costs = batch_products_cost_margin(session, products_in_period)

ventas_gs = sum(int(round(s.qty * s.unit_price_gs)) for s in sales)
cogs_gs = 0
sales_no_recipe = []
for s in sales:
    if s.product is None or s.product.recipe_id is None:
        sales_no_recipe.append(s)
        continue
    cost, _margin = batch_costs.get(s.product_id, (None, (None, None)))
    if cost is None or cost.batch_cost_gs is None:
        sales_no_recipe.append(s)
        continue
    cogs_gs += int(round(s.qty * cost.batch_cost_gs))
```

**Step 3:** Run the new perf test: `uv run pytest tests/test_dashboard_perf.py -v`
Expected: PASS (queries drop from 3,000+ to ~10).

**Step 4:** Run full suite: `unset DATABASE_URL AIW_SASKIA_DB_PATH && uv run pytest -q`
Expected: 838 passed.

**Step 5:** Commit `perf(dashboard): batch-load product costs via batch_products_cost_margin` (~200× speedup on dashboard).

---

### Task 3: Fix N+1 in dashboard ranking loop

**Files:**
- Modify: `app/routers/dashboard.py:107-130` (the ranking aggregation loop)

**Step 1:** Identify second N+1:
```python
ranking_dict: dict[int, dict] = {}
for s in sales:
    ...
    if s.product.recipe_id is not None:
        cost = product_unit_cost_gs(session, rid)  # ← N+1 again
```

**Step 2:** Reuse the `batch_costs` dict from Task 2. The product_id → CostResult lookup is already loaded.

```python
for s in sales:
    ...
    if s.product.recipe_id is not None:
        cost, _margin = batch_costs.get(rid, (None, (None, None)))
        if cost is not None and cost.batch_cost_gs is not None:
            line_margin = int(round(s.qty * (s.unit_price_gs - cost.batch_cost_gs)))
            ranking_dict[rid]["margen_gs"] += line_margin
```

**Step 3:** Run perf test + full suite. Expected: 838 passed.

**Step 4:** Commit `perf(dashboard): reuse batch costs in ranking loop` (removes 2nd N+1).

---

### Task 4: Fix N+1 in recipes_no_cost check

**Files:**
- Modify: `app/routers/dashboard.py:141-146`

**Step 1:** Current:
```python
for r in session.scalars(select(Recipe)).all():
    from app.rms.costing import recipe_batch_cost_gs

    if recipe_batch_cost_gs(session, r.id).batch_cost_gs is None and len(r.lines) > 0:
        recipes_no_cost.append(r)
```

**Step 2:** Add a batch helper to `app/rms/costing.py` (if not exists) that loads all recipes + their lines + ingredients in one pass:

```python
def batch_recipe_costs(session: Session, recipe_ids: list[int]) -> dict[int, CostResult]:
    """Batch-compute recipe costs. Pre-loads lines + ingredients to avoid N+1."""
    if not recipe_ids:
        return {}
    recipes = session.scalars(select(Recipe).where(Recipe.id.in_(recipe_ids))).all()
    all_lines = session.scalars(
        select(RecipeLine).where(RecipeLine.recipe_id.in_(recipe_ids))
    ).all()
    ingredient_ids = {ln.line_ref_id for ln in all_lines if ln.line_kind == "ingredient"}
    if ingredient_ids:
        session.scalars(select(Ingredient).where(Ingredient.id.in_(ingredient_ids))).all()
    return {r.id: recipe_batch_cost_gs(session, r.id) for r in recipes}
```

Then in dashboard.py:
```python
from app.rms.costing import batch_recipe_costs

all_recipes = session.scalars(select(Recipe)).all()
batch_recipe_results = batch_recipe_costs(session, [r.id for r in all_recipes])
recipes_no_cost = [
    r
    for r in all_recipes
    if batch_recipe_results.get(r.id, CostResult(batch_cost_gs=None)).batch_cost_gs is None
    and len(r.lines) > 0
]
```

**Step 3:** Tests: add to `tests/test_dashboard_perf.py` a check that recipe_no_cost still produces correct results. Run perf test + full suite.

**Step 4:** Commit `perf(dashboard): batch-load recipe costs for no-cost check`.

---

## Phase 2: Static Asset Hardening

### Task 5: Add GZipMiddleware

**Files:**
- Modify: `app/rms/main.py:147` (the middleware registration section)

**Step 1:** Find current middleware stack:
```python
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(SessionMiddleware, ...)
```

**Step 2:** Add `GZipMiddleware` from `starlette.middleware.gzip`. Register BEFORE other response-shaping middleware (reverse-order execution):
```python
from starlette.middleware.gzip import GZipMiddleware

...
app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(SessionMiddleware, ...)
```

**Step 3:** Test manually: `curl -sS -H "Accept-Encoding: gzip" -I https://saskia-rms.paragu-ai.com/login`
Expected: `content-encoding: gzip` header present.

**Step 4:** Add regression test in `tests/test_a11y_navigation.py` or new `tests/test_middleware.py`:
```python
def test_gzip_compression_active(client):
    resp = client.get("/login", headers={"Accept-Encoding": "gzip"})
    assert resp.headers.get("content-encoding") == "gzip"
```

**Step 5:** Run full suite. Commit `perf: add GZipMiddleware for ~70% bandwidth reduction`.

---

### Task 6: Add Cache-Control headers to static files

**Files:**
- Modify: `app/rms/main.py:163` (the `app.mount("/static", ...)` line)

**Step 1:** Wrap the `StaticFiles` mount in a small middleware that adds `Cache-Control: max-age=3600, public`:

```python
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class StaticCacheHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        if request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "max-age=3600, public"
        return response


_static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if os.path.isdir(_static_dir):
    app.add_middleware(StaticCacheHeadersMiddleware)
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")
```

**Step 2:** Test: `curl -sS -I https://saskia-rms.paragu-ai.com/static/app.css`
Expected: `cache-control: max-age=3600, public` header present.

**Step 3:** Run full suite. Commit `perf: cache static assets for 1 hour`.

---

## Phase 3: P1 N+1 in Insights + Sales Intel

### Task 7: Fix N+1 in classify_products

**Files:**
- Modify: `app/rms/menu_engineering.py` (`classify_products` function)
- Add test: `tests/test_menu_engineering.py::test_classify_products_batch_load`

**Step 1:** Current code (line ~50 of `menu_engineering.py`):
```python
def classify_products(session: Session) -> list[ProductClassification]:
    products = list(session.scalars(select(Product)).all())
    for p in products:
        vol = _product_volume(session, p.id)  # ← 1 query
        margin_gs, cost_gs, margin_ratio = _product_margin(session, p)  # ← 2+ queries
        ...
```

**Step 2:** Pre-load all needed data, then compute in-memory:
```python
def classify_products(session: Session) -> list[ProductClassification]:
    products = list(session.scalars(select(Product)).all())
    if not products:
        return []

    # Pre-load all ingredient stock movements once
    sales_in_window = session.scalars(
        select(Sale).where(
            Sale.sold_at >= datetime.now(timezone.utc) - timedelta(days=_VOLUME_WINDOW_DAYS)
        )
    ).all()
    volume_by_product: dict[int, float] = {}
    for s in sales_in_window:
        if s.product_id and not s.voided_at:
            volume_by_product[s.product_id] = volume_by_product.get(s.product_id, 0) + s.qty

    # Pre-load batch costs (uses existing batch_products_cost_margin)
    batch_costs = batch_products_cost_margin(session, products)

    classifications = []
    for p in products:
        vol = int(volume_by_product.get(p.id, 0))
        cost, (margin_gs, margin_ratio) = batch_costs.get(
            p.id, (CostResult(batch_cost_gs=None), (None, None))
        )
        classifications.append(ProductClassification(...))
    ...
```

**Step 3:** Tests: existing `test_menu_engineering.py` should still pass; add a new test that asserts `classify_products` issues ≤3 queries for 20 products.

**Step 4:** Run + commit `perf(menu_engineering): batch-load sales volume + costs`.

---

### Task 8: Fix N+1 in production_plan_for_day calls in build_insights

**Files:**
- Modify: `app/rms/insights.py:81` (the `for p in products` loop)

**Step 1:** Current:
```python
tomorrow_plans = []
for p in session.query(Product).all():
    try:
        tomorrow_plans.append(production_plan_for_day(session, p))
    except Exception:
        pass
```

**Step 2:** Add a batch function to `app/rms/production_scheduler.py`:
```python
def batch_production_plans(
    session: Session, products: list[Product], target_date: date | None = None
) -> list[ProductionPlan]:
    """Compute production plans for many products, batch-loading forecast + stock."""
    if not products:
        return []
    product_ids = [p.id for p in products]
    forecasts = {fid: expected_daily_sales(session, fid, days_history=14) for fid in product_ids}
    all_ingredients = session.scalars(select(Ingredient)).all()
    stock_by_ingredient = {i.id: i.stock_qty for i in all_ingredients}

    plans = []
    for p in products:
        forecast = forecasts.get(p.id, 0)
        plan = _plan_for_product_with_forecast(
            session, p, forecast, target_date, stock_by_ingredient
        )
        plans.append(plan)
    return plans
```

Then in insights.py:
```python
from app.rms.production_scheduler import batch_production_plans

tomorrow_plans = batch_production_plans(session, list(session.scalars(select(Product)).all()))
```

**Step 3:** Tests: add a query-count test in `tests/test_insights.py`. Run full suite.

**Step 4:** Commit `perf(insights): batch production plans via batch_production_plans`.

---

### Task 9: Fix N+1 in rising_products and churning_products

**Files:**
- Modify: `app/rms/sales_intel.py` (`rising_products` and `churning_products`)

**Step 1:** Current:
```python
def rising_products(session, threshold_pct=0.3, window_days=14):
    out = []
    for p in session.scalars(select(Product)).all():  # ← already 1 query
        trend = _trend_for_product(
            session, p.id, threshold_pct, window_days
        )  # ← +3 queries per product
        if trend.direction == "rising":
            out.append(trend)
```

**Step 2:** Refactor `_trend_for_product` into a batch that takes a list of product_ids. Pre-load all sales in window + window-prior:

```python
def batch_product_trends(
    session: Session, product_ids: list[int], threshold_pct: float, window_days: int
) -> list[TrendResult]:
    """Compute trend for many products in 2 queries (current + prior window)."""
    if not product_ids:
        return []
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=window_days)
    prior_start = now - timedelta(days=window_days * 2)

    current_sales = session.scalars(
        select(Sale).where(
            Sale.product_id.in_(product_ids),
            Sale.sold_at >= window_start,
            Sale.voided_at.is_(None),
        )
    ).all()
    prior_sales = session.scalars(
        select(Sale).where(
            Sale.product_id.in_(product_ids),
            Sale.sold_at >= prior_start,
            Sale.sold_at < window_start,
            Sale.voided_at.is_(None),
        )
    ).all()

    current_by_p: dict[int, float] = {}
    prior_by_p: dict[int, float] = {}
    for s in current_sales:
        current_by_p[s.product_id] = current_by_p.get(s.product_id, 0) + s.qty
    for s in prior_sales:
        prior_by_p[s.product_id] = prior_by_p.get(s.product_id, 0) + s.qty

    out = []
    for pid in product_ids:
        cur = current_by_p.get(pid, 0)
        pri = prior_by_p.get(pid, 0)
        change = (cur - pri) / pri if pri > 0 else None
        direction = ...
        if direction == "rising" and (change or 0) >= threshold_pct:
            out.append(TrendResult(...))
    return out
```

**Step 3:** Tests: existing `test_sales_intel.py` should still pass; add a query-count test.

**Step 4:** Commit `perf(sales_intel): batch trend computation across products`.

---

## Phase 4: Missing Pages (Built Modules, No Routes)

These modules are fully implemented and tested in the codebase. They just have no routes or templates yet. Highest user-impact work.

### Task 10: /clientes route + template (Customers)

**Files:**
- Create: `app/routers/customers.py`
- Modify: `app/rms/main.py` (register new router)
- Create: `app/templates/clientes.html`
- Create: `app/templates/cliente_detalle.html`
- Create: `tests/test_clientes_routes.py`

**Step 1:** Write failing tests for `/clientes` (list) and `/clientes/{id}` (detail):
```python
def test_clientes_list_shows_tiers(client):
    resp = client.get("/clientes")
    assert resp.status_code == 200
    body = resp.text
    assert "Clientes" in body
    # Bronze/Silver/Gold/Platinum tiers shown
    for tier in ["Bronze", "Silver", "Gold", "Platinum"]:
        assert tier in body or tier.lower() in body


def test_cliente_detalle_shows_purchase_history(client):
    resp = client.get("/clientes/1")
    assert resp.status_code == 200
    assert "Historial" in resp.text or "historial" in resp.text
```

**Step 2:** Run: expect FAIL (404). **Step 3:** Implement router + templates using `app/rms/customers.py` (already built). Use `customer_stats()` and `customer_purchase_history()`.

**Step 4:** Add nav link in `base.html` (Clientes).

**Step 5:** Tests pass. Commit `feat(routes): add /clientes list + detail pages`.

---

### Task 11: /produccion route + template (Production worksheet)

**Files:**
- Create: `app/routers/production.py`
- Modify: `app/rms/main.py`
- Create: `app/templates/produccion.html`
- Create: `tests/test_produccion_route.py`

**Step 1:** Write failing test:
```python
def test_produccion_shows_tomorrow_plan(client):
    resp = client.get("/produccion")
    assert resp.status_code == 200
    assert "Producción" in resp.text or "produccion" in resp.text
    # Should show ingredients + quantities
    assert "cantidad" in resp.text.lower() or "qty" in resp.text.lower()
```

**Step 2:** Run: FAIL (404). **Step 3:** Implement using `app/rms/production.py`'s `plan_production()`. Show tomorrow's plan grouped by recipe, with ingredients and quantities.

**Step 4:** Nav link "Producción". **Step 5:** Tests + commit.

---

### Task 12: /eod route + template (End-of-day checklist)

**Files:**
- Create: `app/routers/eod.py`
- Modify: `app/rms/main.py`
- Create: `app/templates/eod.html`
- Create: `tests/test_eod_route.py`

**Step 1:** Failing test:
```python
def test_eod_checklist_renders(client):
    resp = client.get("/eod")
    assert resp.status_code == 200
    assert "checklist" in resp.text.lower() or "Cierre" in resp.text
```

**Step 2:** FAIL. **Step 3:** Implement using `EOD_CHECKLIST_TEMPLATE` from `app/rms/workflow.py`. Show 10 standard items with DONE/PENDING/SKIPPED state.

**Step 4:** Nav link "Cierre diario". **Step 5:** Tests + commit.

---

### Task 13: /merma route + template (Waste log)

**Files:**
- Create: `app/routers/merma.py`
- Modify: `app/rms/main.py`
- Create: `app/templates/merma.html`
- Create: `tests/test_merma_route.py`

**Step 1:** Failing test for list + create form.

**Step 2:** FAIL. **Step 3:** Implement using `WasteReason` enum + `record_waste()` from `app/rms/waste.py`. Form to record waste, table to view.

**Step 4:** Nav link. **Step 5:** Tests + commit.

---

### Task 14: /reportes route + template (Reports — IVA etc.)

**Files:**
- Create: `app/routers/reportes.py`
- Modify: `app/rms/main.py`
- Create: `app/templates/reportes.html`, `app/templates/reportes_iva.html`, `app/templates/reportes_libro_ventas.html`
- Create: `tests/test_reportes_route.py`

**Step 1:** Failing tests for each subpage.

**Step 2:** FAIL. **Step 3:** Implement using `monthly_iva_breakdown()`, `libro_ventas()`, `daily_summary()` from `app/rms/accounting.py`.

**Step 4:** Nav link. **Step 5:** Tests + commit.

---

### Task 15: /auditoria route + template (Audit log viewer)

**Files:**
- Create: `app/routers/auditoria.py`
- Modify: `app/rms/main.py`
- Create: `app/templates/auditoria.html`
- Create: `tests/test_auditoria_route.py`

**Step 1:** Failing test:
```python
def test_auditoria_shows_paginated_log(client):
    resp = client.get("/auditoria")
    assert resp.status_code == 200
    # Should show user, action, occurred_at columns
    for col in ["Usuario", "Acción", "Fecha"]:
        assert col in resp.text
```

**Step 2:** FAIL. **Step 3:** Implement using `audit_log` table + `app/rms/audit.py`. Paginate, filter by user/action/date.

**Step 4:** Nav link. **Step 5:** Tests + commit.

---

## Phase 5: Sales Page Overhaul

### Task 16: Add customer/payment/discount fields to Sale model

**Files:**
- Modify: `app/rms/models.py` (Sale model)
- Modify: `app/rms/db.py` (add migration 011)
- Modify: `app/rms/config.py` (`CURRENT_SCHEMA_VERSION = 11`)
- Create: `tests/test_sale_new_fields.py`

**Step 1:** Failing test:
```python
def test_sale_has_payment_method_field():
    from app.rms.models import Sale

    sale = Sale(product_id=1, qty=1, unit_price_gs=10000, payment_method="cash")
    assert sale.payment_method == "cash"


def test_sale_has_discount_field():
    sale = Sale(product_id=1, qty=1, unit_price_gs=10000, discount_gs=1000)
    assert sale.discount_gs == 1000
```

**Step 2:** Run: FAIL (no fields). **Step 3:** Add `payment_method: str | None`, `discount_gs: int = 0`, `customer_id: int | None` to Sale. Migration 011 adds columns via dialect-aware helpers.

**Step 4:** Tests pass. Commit `feat(sales): add customer/payment/discount fields to Sale`.

---

### Task 17: Sales form overhaul (new fields + quick-sell)

**Files:**
- Modify: `app/routers/sales.py` (POST handler to accept new fields)
- Modify: `app/templates/ventas.html` (add customer lookup, payment select, discount input, quick-sell buttons)

**Step 1:** Failing test:
```python
def test_sale_create_with_customer_and_discount(client):
    # POST /ventas/nueva with new fields
    resp = client.post(
        "/ventas/nueva",
        data={
            "product_id": 1,
            "qty": 1,
            "discount_gs": 500,
            "customer_phone": "0981234567",
            "payment_method": "cash",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
```

**Step 2:** FAIL. **Step 3:** Update `sale_create` handler to call `ensure_customer()` by phone, store `discount_gs` + `payment_method` + `customer_id`. Update template to add fields.

**Step 4:** Tests pass. Commit `feat(sales): support customer/payment/discount on sale form`.

---

### Task 18: Add quick-sell buttons

**Files:**
- Modify: `app/templates/ventas.html` (top-of-page button bar)

**Step 1:** Test (visual regression): top of ventas.html should contain 5 large buttons for top-5 selling products.

**Step 2:** FAIL. **Step 3:** Compute top-5 selling products (last 14 days) in router, pass to template, render as 5 large `<button>` elements that POST a pre-filled sale.

**Step 4:** Tests pass. Commit `feat(sales): quick-sell buttons for top products`.

---

## Phase 6: Navigation + UX Polish

### Task 19: Logout button in nav

**Files:**
- Modify: `app/templates/base.html`

**Step 1:** Test: nav should contain a link to `/logout`.

**Step 2:** Add `<a href="/logout" class="nav-link">Cerrar sesión</a>` to nav-right.

**Step 3:** Test + commit `feat(nav): add logout link`.

---

### Task 20: Breadcrumbs on edit pages

**Files:**
- Modify: `app/templates/producto_form.html`, `receta_form.html`, `inventario_form.html`

**Step 1:** Tests: each edit template should contain a breadcrumb like "Productos > Nombre".

**Step 2:** FAIL. **Step 3:** Add `<nav class="breadcrumbs">` block at top of each form.

**Step 4:** Tests + commit `feat(ui): add breadcrumbs to edit forms`.

---

### Task 21: Mobile-responsive tables

**Files:**
- Modify: `app/static/app.css`

**Step 1:** Visual regression: load any table page at 375px viewport width, table should horizontally scroll instead of overflowing.

**Step 2:** Add to CSS:
```css
@media (max-width: 768px) {
    table.data { display: block; overflow-x: auto; white-space: nowrap; }
    .form-row { flex-direction: column; }
    .nav-links { order: 3; width: 100%; }
}
```

**Step 3:** Verify via curl that the CSS is shipped. Commit `feat(css): mobile-responsive tables + nav`.

---

### Task 22: Print-friendly CSS

**Files:**
- Modify: `app/static/app.css`

**Step 1:** Add `@media print` block that hides nav/footer, shows report cleanly.

**Step 2:** Commit `feat(css): print-friendly styles for end-of-day reports`.

---

## Phase 7: Cold-start Mitigation

### Task 23: UptimeRobot integration

**Files:**
- Create: `scripts/uptimerobot_setup.py`
- Modify: `app/CHANGELOG.md`

**Step 1:** Use `UPTIMEROBOT_ACCOUNT_API_KEY` and `UPTIMEROBOT_MONITOR_KEY` from BWS to create a monitor that pings `https://saskia-rms.paragu-ai.com/healthz` every 5 minutes.

**Step 2:** Write script that:
1. Fetches keys from BWS (in subprocess)
2. Creates the monitor via UptimeRobot API
3. Saves the monitor ID + key to a config file for future updates

**Step 3:** Run, verify the monitor exists via GET /v2/getMonitors.

**Step 4:** Commit `ops: UptimeRobot monitor for saskia-rms healthz endpoint`.

---

## Validation / Acceptance Criteria

After all phases complete:

1. **Performance**: dashboard `/` loads in <500ms (down from 15-60s)
2. **Query count**: any single page issues ≤20 DB queries
3. **Bandwidth**: gzipped responses for all HTML/CSS/JS > 500 bytes
4. **Cache**: `/static/*` returns `Cache-Control: max-age=3600`
5. **Coverage**: 6 new routes (`/clientes`, `/produccion`, `/eod`, `/merma`, `/reportes`, `/auditoria`) reachable + functional
6. **UX**: nav has 8 items including logout
7. **Sales**: `/ventas/nueva` accepts customer phone, payment method, discount
8. **Cold-start**: UptimeRobot monitor active
9. **Tests**: 850+ pytest passing, ruff clean
10. **Live**: `/healthz/db` returns postgres dialect, full login flow works

---

## Risks & Tradeoffs

- **Task 7-9 (Phase 3)**: Refactoring `classify_products` could subtly change behavior. Existing tests must continue to pass — they're the safety net.
- **Task 16 (Sale model changes)**: Adding `payment_method` + `discount_gs` is backward-compatible (default to NULL/0). No data migration needed for old sales.
- **Task 23 (UptimeRobot)**: Free-tier UptimeRobot allows 50 monitors; this would use 1.
- **Tasks 10-15 (missing pages)**: Each is a new ~150-300 line module (route + template + 2-4 tests). Bite-sized as listed.

---

## Estimated Effort

| Phase | Tasks | Lines added | Time |
|---|---|---|---|
| 1 | 4 | ~50 | 30 min |
| 2 | 2 | ~40 | 15 min |
| 3 | 3 | ~120 | 1 hr |
| 4 | 6 | ~1500 | 4 hr |
| 5 | 3 | ~300 | 1.5 hr |
| 6 | 4 | ~150 | 45 min |
| 7 | 1 | ~80 | 20 min |
| **Total** | **23** | **~2240** | **~9 hr** |

---

## Execution Order (Recommended)

1. Phase 1 + 2 first (one epic, dramatic speedup) → verify on live → 1 commit
2. Phase 3 next (insights/sales_intel N+1) → verify → 1 commit
3. Phase 4 (6 missing pages) → 6 commits, one per page
4. Phase 5 (sales overhaul) → 3 commits
5. Phase 6 (UX polish) → 4 commits
6. Phase 7 (UptimeRobot) → 1 commit, then enable in dashboard

**Total: ~16 commits across the next session or two.**

---

## Open Questions

1. **Sale model changes (Task 16)**: do we want `payment_method` as free-text or enum? Suggest enum: `cash | transfer | card | other`. Easy to add new values.
2. **Quick-sell buttons (Task 18)**: should they appear only on mobile, or always? Suggest always (operator on tablet benefits too).
3. **Missing pages prioritization (Phase 4)**: `/clientes` and `/produccion` are highest impact (loyalty finally works, daily chore automated). Do those two first, then the rest.
4. **UptimeRobot free-tier limit**: 50 monitors. Plenty of headroom but worth noting.
