# Sazón — Complete Test Plan

> Single source of truth for backend / frontend / integration coverage of the
> Ai-Whisperers/sazon-app FastAPI restaurant management system.
> Generated 2026-09-22 against commit working tree at
> `/opt/data/profiles/ivan/scratch/sazon-app-work`.

---

## Section 1 — Inventory

### 1.1 Code volume

| Area | Count | Notes |
|---|---|---|
| Routers (`app/routers/*.py`) | 24 files | 23 non-empty + `__init__.py` |
| Routes (registered `@router.METHOD` decorators) | **113** | Across all routers |
| HTML templates (`app/templates/*.html`) | **50** | 4 in `_components/`, 2 in `errors/` |
| DB model classes (`app/rms/models.py`) | **22** | `Base` + 21 `__tablename__` entities |
| Service modules (`app/services/*.py`) | 8 | incl. `template_render.py` |
| Existing test files (`tests/test_*.py`) | **132** | ~22,486 LOC; ~1,500 test fns |
| Test fixtures (`tests/fixtures/`) | 8+ | herbus xlsx, drive, real-drive, etc. |

### 1.2 Models (DB tables)

`AppMeta`, `Ingredient`, `Recipe`, `RecipeLine`, `Product`, `Sale`,
`SaleStockMove`, `ImportBatch`, `User`, `AuditLog`, `IngredientPriceEvent`,
`Customer`, `Tag`, `TagLink`, `ProductionCompletion`, `Supplier`, `WasteLog`,
`Pedido`, `PedidoLine`, `Tenant`, `StockMovement`.

Schema version: **`CURRENT_SCHEMA_VERSION` = 26** (per
`app/rms/db.py`; matches live DB v26/26 per parent session note).

### 1.3 Routers (113 endpoints, grouped by domain)

```
auditoria.py        2  /auditoria,  /auditoria/prune
auth.py             5  /login (GET+POST), /logout (GET+POST), /forgot-password
customers.py        7  /clientes, /clientes/api/search, /clientes/api/create,
                       /clientes/{id}, /clientes/{id}/editar,
                       /clientes/bulk-eliminar
dashboard.py        1  /
eod.py              2  /eod,  /eod/completar
excel_io.py         6  /excel, /excel/mode-guidance, /excel/validar,
                       /excel/importar, /excel/exportar, /excel/plantilla
health.py           5  /healthz, /healthz/errors, /healthz/deps,
                       /healthz/db, /healthz/schema
help.py             2  /guia, /guia/{section}
inventory.py       10  /inventario, /inventario/nuevo, /inventario/{id},
                       /inventario/{id}/editar, /inventario/{id}/eliminar,
                       /inventario/{id}/ajustar, /inventario/{id}/movimientos,
                       /inventario/export.csv
merma.py            3  /merma, /merma/registrar, /merma/receta
ops.py              2  /ops/status, /ops/reset-demo-data
pedidos.py         12  /pedidos, /pedidos/board, /pedidos/nuevo,
                       /pedidos/{id}, /pedidos/{id}/status,
                       /pedidos/{id}/fulfill, /pedidos/{id}/stock-preview,
                       /pedidos/{id}/duplicate, /pedidos/export-csv,
                       /pedidos/bulk-fulfill, /pedidos/bulk-cancel
produccion.py       2  /produccion, /produccion/override
products.py         8  /productos, /productos/nuevo,
                       /productos/{id}/editar, /productos/{id}/eliminar,
                       /productos/bulk-eliminar, /productos/export.csv
recipes.py          6  /recetas, /recetas/nueva,
                       /recetas/{id}, /recetas/{id}/editar
reorder.py          3  /reorder, /reorder/registrar, /reorder/generate-po
reportes.py        15  /reportes, /reportes/iva, /reportes/libro-ventas,
                       /reportes/libro-ventas/set-pdf, /reportes/diario,
                       /reportes/comparacion, /reportes/top-productos,
                       /reportes/retencion, /reportes/valor-pedido,
                       /reportes/ventas-hora, /reportes/metodos-pago,
                       /reportes/precios, /reportes/precios/csv,
                       /reportes/diario/pdf, /reportes/iva/pdf
sales.py            6  /ventas, /ventas/nueva, /ventas/buscar,
                       /ventas/{id}/recibo, /ventas/{id}/anular,
                       /ventas/export.csv
search.py           1  /api/search
settings.py         4  /settings, /settings/business, /settings/fiscal,
                       /settings/theme
suppliers.py        7  /suppliers, /suppliers/nuevo,
                       /suppliers/{id}/editar, /suppliers/{id}/eliminar,
                       /suppliers/{id}/ordenes
users.py            4  /users, /users/crear,
                       /users/{id}/editar, /users/{id}/eliminar
```

### 1.4 Templates (50)

```
Component partials (4):  _components/{calendar,confirm_modal,macros,
                         _customer_picker}.html
Error pages (2):        errors/{404,500}.html
Base / chrome (1):      base.html
Business pages (43):    See matrix in §3.2 (one per route group)
```

### 1.5 Existing test inventory

132 test files, grouped by depth (top files by line count): `test_ingredient_intel.py` (44), `test_visual_revolution.py` (40), `test_ui_smoke.py` (38), `test_recipe_intel.py` (31), `test_routes.py` (28), `test_reports.py` (22), `test_customer_picker.py` (22), `test_real_drive_shape_fixture.py` (21), `test_r2_backup.py` (20), `test_product_similarity.py` (19), `test_inventory_intel.py` (19), `test_excel_patch.py` (19), `test_costing.py` (19), `test_workflow.py` (17), `test_tags.py` (17), `test_dashboard_deltas.py` (17), `test_sales_intel.py` (16), `test_price_history.py` (16), `test_pedidos.py` (16), `test_p1_route_coverage.py` (16), `test_barcode.py` (16), `test_a11y_navigation.py` (16), `test_seed.py` (15), `test_hotfix_regressions.py` (15), `test_units.py` (14), `test_settings.py` (14), `test_production_scheduler.py` (14), `test_dashboard_visual.py` (14), `test_customers.py` (14), `test_waste.py` (13), …

---

## Section 2 — Known issues & live-site verification

### 2.1 Live-site probe (2026-09-22, 09:22 UTC)

Probing `https://sazon-rms.paragu-ai.com` from outside the tunnel returned
**HTTP 429 with `cf-mitigated: challenge`** on every URL (Cloudflare bot
challenge — the operator must click through once). Cannot directly verify
authenticated 200s from this environment.

Per parent-session note, prior manual verification established:

| Path | Status (parent session) | Action |
|---|---|---|
| `/login` | 200 (auth form) | OK |
| `/` (dashboard) | 200 after schema v26 migrate | OK |
| `/productos`, `/inventario`, `/clientes`, `/auditoria` | 200 | OK |
| `/ventas` | **TemplateRuntimeError** | BLOCKER |
| `/reportes/*` | 200 (most), TBD for `/reportes/*/pdf` | OK |
| DB schema | v26 / v26 (drift=0) | OK |

### 2.2 Known issue backlog (must-have regression coverage)

These are the high-priority gaps that have produced outages or surfaced as
PR-blocking issues:

| # | Issue | Source | New test |
|---|---|---|---|
| K1 | `ventas.html` raises `TemplateRuntimeError` | parent session | `test_ventas_page_renders_no_template_error` |
| K2 | Migration 026 added `is_available`/`image_url`/`category`/`tags` to `Product` without shipping migration | `test_p0_outage_prevention.py` covers | existing — keep green |
| K3 | DB-version drift (v19 < code v25) was invisible to `ready=True` | same | existing |
| K4 | Missing Supabase env vars crashed `/login` | same | existing |
| K5 | `get_session` returned raw `Connection` on fallback | same | existing |
| K6 | `/p/{token}` public-pickup route looked up by Integer PK | CHANGELOG 2026-09-21 | add `test_public_pedido_resolves_by_public_token` |
| K7 | `test_p1_route_coverage.py::test_users_page_loads` is `pytest.skip` — admin gate too strict for fake user | tracked; out of scope | add `test_users_admin_gate_returns_403_for_non_admin` (expected behaviour, not a 500) |
| K8 | Static-asset cache busting landed 2026-09-21 | CHANGELOG | add `test_static_links_have_versioned_query` |
| K9 | Nav dropdown (round-1 visual) added ARIA wiring | CHANGELOG | add `test_nav_menu_has_aria_haspopup` |
| K10 | CSRF middleware tightened | `test_csrf_local_dev.py` covers | existing |
| K11 | Rate-limit middleware on write endpoints | `test_rate_limit_write_endpoints.py` covers | existing |
| K12 | Hotfix regressions (5 fail-closed tests) | `test_hotfix_regressions.py` | existing |
| K13 | `/auditoria` IP & user-agent filters | `test_auditoria_ip_user_filter.py` | existing |

---

## Section 3 — Complete route × test_type matrix

Legend: **S** = smoke (page returns 200), **C** = CRUD round-trip,
**P** = permission/auth gate, **API** = JSON contract, **PDF** = binary
download, **CSV** = export shape, **WS** = websocket/HTMX,
**PERF** = query-count budget. Numbers are priority 1 (P1) → 5 (P5).

### 3.1 Auth & system

| Route | M | Tmpl | C | API | P | Perf | Priority |
|---|---|---|---|---|---|---|---|
| GET `/login` | G | login.html | — | — | unauth → 200; authed → 303 | — | P1 |
| POST `/login` | P | — | — | — | valid creds → 303; bad → 200 w/ error; rate-limited → 429 | — | P1 |
| POST `/logout` | P | — | — | — | 303 + cookie cleared | — | P2 |
| GET `/logout` | G | — | — | — | 303 | — | P3 |
| POST `/forgot-password` | P | — | — | JSON ok | invalid email → 200 ok | — | P3 |
| GET `/healthz` | G | — | — | JSON `{status,schema_version,ready}` | always 200 (UptimeRobot) | <5 ms | P1 |
| GET `/healthz/errors` | G | — | — | JSON list | always 200 | — | P3 |
| GET `/healthz/deps` | G | — | — | JSON fingerprint (NO secrets) | always 200 | — | P3 |
| GET `/healthz/db` | G | — | — | JSON `{db,journal_mode}` | 200 | — | P1 |
| GET `/healthz/schema` | G | — | — | JSON `{drift,migrations_applied}` | 200 / 503 | — | P1 |
| GET `/ops/status` | G | ops_status.html | — | — | 200 | — | P2 |
| POST `/ops/reset-demo-data` | P | — | — | — | admin-only 200, others 403 | — | P3 |
| GET `/api/search?q=` | G | — | — | JSON `{type,label,url}[]` | 200 | — | P2 |
| GET `/guia` | G | guia.html | — | — | 200 | — | P3 |
| GET `/guia/{section}` | G | guia.html | — | — | known section 200, unknown 404 | — | P3 |

### 3.2 Business — Ventas / Pedidos / Clientes

| Route | M | Tmpl | C | API | P | Perf | Priority |
|---|---|---|---|---|---|---|---|
| GET `/` | G | inicio.html | — | — | 200, no 500 with empty DB | <90 queries | P1 |
| GET `/ventas` | G | ventas.html | — | — | 200, **NO TemplateRuntimeError** | — | **P0 — K1 blocker** |
| POST `/ventas/nueva` | P | — | recipe OK + StockMove + audit | — | 303; missing fields → 422 | — | P1 |
| GET `/ventas/buscar?sku=` | G | — | — | JSON `{id,name,sale_price_gs}` | 200 | — | P1 |
| GET `/ventas/{id}/recibo` | G | recibo.html | — | — | 200, html printable | — | P2 |
| POST `/ventas/{id}/anular` | P | — | voids Sale + recovers stock | — | 303; double-void → 4xx | — | P1 |
| GET `/ventas/export.csv` | G | — | — | CSV | 200, correct money int format | — | P3 |
| GET `/pedidos` | G | pedidos.html | — | — | 200, includes filters | — | P2 |
| GET `/pedidos/board` | G | pedido_board.html | — | — | 200 | — | P2 |
| GET `/pedidos/nuevo` | G | pedidos_nuevo.html | — | — | 200 | — | P2 |
| POST `/pedidos/nuevo` | P | — | create Pedido + lines | — | 303 | — | P2 |
| GET `/pedidos/{id}` | G | pedido_detalle.html | — | — | 200 | — | P2 |
| POST `/pedidos/{id}/status` | P | — | update status + audit | — | 303; invalid → 422 | — | P2 |
| POST `/pedidos/{id}/fulfill` | P | — | decrement stock + sales | — | 303 | — | P1 |
| GET `/pedidos/{id}/stock-preview` | G | pedido_stock_preview.html | — | — | 200 | — | P3 |
| GET `/pedidos/{id}/duplicate` | G | — | — | — | 303 → nuevo | — | P3 |
| GET `/pedidos/export-csv` | G | — | — | CSV | 200 | — | P3 |
| POST `/pedidos/bulk-fulfill` | P | — | atomic bulk | — | 303 | — | P3 |
| POST `/pedidos/bulk-cancel` | P | — | atomic bulk | — | 303 | — | P3 |
| GET `/p/{public_token}` | G | pedido_publico.html | — | — | **resolves by token, not PK** | — | **P0 — K6 regression** |
| GET `/clientes` | G | clientes.html | — | — | 200, filter param works | — | P2 |
| GET `/clientes/api/search?q=` | G | — | — | JSON list | 200 | — | P3 |
| POST `/clientes/api/create` | P | — | create Customer | JSON `{ok,id}` | 200 | — | P3 |
| GET `/clientes/{id}` | G | cliente_detalle.html | — | — | 200 | — | P2 |
| GET `/clientes/{id}/editar` | G | cliente_editar.html | — | — | 200 | — | P2 |
| POST `/clientes/{id}/editar` | P | — | save edit | — | 303 | — | P2 |
| POST `/clientes/bulk-eliminar` | P | — | atomic delete | — | 303 | — | P3 |

### 3.3 Catálogo — Productos / Recetas / Inventario / Reposición / Merma

| Route | M | Tmpl | C | API | P | Perf | Priority |
|---|---|---|---|---|---|---|---|
| GET `/productos` | G | productos.html | — | — | 200 | — | P1 |
| GET `/productos/nuevo` | G | producto_form.html | — | — | 200 | — | P1 |
| POST `/productos/nuevo` | P | — | create + audit | — | 303; dup SKU → 422 | — | P1 |
| GET `/productos/{id}/editar` | G | producto_form.html | — | — | 200 | — | P2 |
| POST `/productos/{id}/editar` | P | — | save + audit | — | 303 | — | P2 |
| POST `/productos/{id}/eliminar` | P | — | soft delete + audit | — | 303 | — | P2 |
| POST `/productos/bulk-eliminar` | P | — | atomic | — | 303 | — | P3 |
| GET `/productos/export.csv` | G | — | — | CSV | 200 | — | P3 |
| GET `/recetas` | G | recetas.html | — | — | 200 | — | P2 |
| GET `/recetas/nueva` | G | receta_form.html | — | — | 200 | — | P2 |
| POST `/recetas/nueva` | P | — | create + polymorphic lines | — | 303 | — | P2 |
| GET `/recetas/{id}` | G | receta_detalle.html | — | — | 200; shows batch + unit cost | — | P2 |
| GET `/recetas/{id}/editar` | G | receta_form.html | — | — | 200 | — | P3 |
| POST `/recetas/{id}/editar` | P | — | save | — | 303 | — | P3 |
| GET `/inventario` | G | inventario.html | — | — | 200 | — | P1 |
| GET `/inventario/nuevo` | G | inventario_form.html | — | — | 200 | — | P2 |
| POST `/inventario/nuevo` | P | — | create + audit | — | 303 | — | P2 |
| GET `/inventario/{id}` | G | ingrediente_detalle.html | — | — | 200, price strip visible | — | P2 |
| GET `/inventario/{id}/editar` | G | inventario_form.html | — | — | 200 | — | P3 |
| POST `/inventario/{id}/editar` | P | — | save | — | 303 | — | P3 |
| POST `/inventario/{id}/eliminar` | P | — | delete + audit | — | 303 | — | P3 |
| POST `/inventario/{id}/ajustar` | P | — | adjust stock + StockMovement + audit | — | 303 | — | P1 |
| GET `/inventario/{id}/movimientos` | G | inventario_movimientos.html | — | — | 200 | — | P2 |
| GET `/inventario/export.csv` | G | — | — | CSV | 200 | — | P3 |
| GET `/reorder` | G | reorder.html | — | — | 200, suggestions render | — | P2 |
| POST `/reorder/registrar` | P | — | record restock + audit | — | 303 | — | P2 |
| POST `/reorder/generate-po` | P | — | create PO + links supplier | — | 303 | — | P3 |
| GET `/merma` | G | merma.html | — | — | 200 | — | P2 |
| POST `/merma/registrar` | P | — | record WasteLog + audit | — | 303 | — | P2 |
| POST `/merma/receta` | P | — | waste against a recipe (production) | — | 303 | — | P3 |
| GET `/produccion` | G | produccion.html | — | — | 200 | — | P2 |
| POST `/produccion/override` | P | — | override scheduler | — | 303 | — | P3 |

### 3.4 Reportes

| Route | M | Tmpl | C | API | P | Perf | Priority |
|---|---|---|---|---|---|---|---|
| GET `/reportes` | G | reportes.html | — | — | 200, all 12 cards render | — | P2 |
| GET `/reportes/iva` | G | reportes_iva.html | — | — | 200 | — | P3 |
| GET `/reportes/iva/pdf` | G | — | — | application/pdf | 200, valid PDF magic | — | P3 |
| GET `/reportes/libro-ventas` | G | reportes_libro_ventas.html | — | — | 200 | — | P3 |
| GET `/reportes/libro-ventas/set-pdf` | G | — | — | JSON `{url}` | 200 | — | P3 |
| GET `/reportes/diario` | G | reportes_diario.html | — | — | 200 | — | P2 |
| GET `/reportes/diario/pdf` | G | — | — | application/pdf | 200 | — | P3 |
| GET `/reportes/comparacion` | G | reportes_comparacion.html | — | — | 200 | — | P3 |
| GET `/reportes/top-productos` | G | reportes_top_productos.html | — | — | 200 | — | P3 |
| GET `/reportes/retencion` | G | reportes_retencion.html | — | — | 200 | — | P3 |
| GET `/reportes/valor-pedido` | G | reportes_valor_pedido.html | — | — | 200 | — | P3 |
| GET `/reportes/ventas-hora` | G | reportes_ventas_hora.html | — | — | 200 | — | P3 |
| GET `/reportes/metodos-pago` | G | reportes_metodos_pago.html | — | — | 200 | — | P3 |
| GET `/reportes/precios` | G | reportes_precios.html | — | — | 200, filters work | — | P2 |
| GET `/reportes/precios/csv` | G | — | — | CSV | 200 | — | P3 |

### 3.5 Sistema — Excel / Auditoría / Config / Users / Suppliers / EOD

| Route | M | Tmpl | C | API | P | Perf | Priority |
|---|---|---|---|---|---|---|---|
| GET `/excel` | G | excel.html | — | — | 200, shows history | — | P2 |
| GET `/excel/mode-guidance` | G | excel_mode_guidance.html | — | — | 200 | — | P3 |
| POST `/excel/validar` | P | excel_validate.html | validate xlsx → report | — | 200 + report dict | — | P2 |
| POST `/excel/importar` | P | — | transactional import | — | 303; bad file → 422 | — | P1 |
| GET `/excel/exportar` | G | — | — | xlsx | 200, valid zip | — | P3 |
| GET `/excel/plantilla` | G | — | — | xlsx | 200, valid zip | — | P3 |
| GET `/auditoria` | G | auditoria.html | — | — | 200, paginated | — | P2 |
| POST `/auditoria/prune` | P | — | prune old audit rows | — | 303 | — | P3 |
| GET `/settings` | G | settings.html | — | — | 200 | — | P2 |
| POST `/settings/business` | P | — | save | — | 303 | — | P3 |
| POST `/settings/fiscal` | P | — | save | — | 303 | — | P3 |
| POST `/settings/theme` | P | — | save | — | 303 | — | P3 |
| GET `/users` | G | users.html | — | — | admin 200, others 403 (NOT 500/401) | — | P2 |
| POST `/users/crear` | P | — | create + audit | — | 303 | — | P3 |
| POST `/users/{id}/editar` | P | — | save | — | 303 | — | P3 |
| POST `/users/{id}/eliminar` | P | — | delete | — | 303 | — | P3 |
| GET `/suppliers` | G | suppliers.html | — | — | 200 | — | P2 |
| GET `/suppliers/nuevo` | G | supplier_form.html | — | — | 200 | — | P2 |
| POST `/suppliers/nuevo` | P | — | create + audit | — | 303 | — | P2 |
| GET `/suppliers/{id}/editar` | G | supplier_form.html | — | — | 200 | — | P3 |
| POST `/suppliers/{id}/editar` | P | — | save | — | 303 | — | P3 |
| POST `/suppliers/{id}/eliminar` | P | — | delete + audit | — | 303 | — | P3 |
| GET `/suppliers/{id}/ordenes` | G | supplier_orders.html | — | — | 200 | — | P3 |
| GET `/eod` | G | eod.html | — | — | 200 | — | P1 |
| POST `/eod/completar` | P | — | atomic DailySummary + audit | — | 303 | — | P1 |

### 3.6 Summary counts

| Method | Count |
|---|---|
| GET | 85 |
| POST | 28 |
| PUT | 0 |
| DELETE | 0 (FastAPI uses POST for delete here) |
| PATCH | 0 |
| **Total** | **113** |

Smoke-required (every GET HTML page must return 200): **~62 endpoints**
(REST JSON endpoints that don't render HTML are smoke-tested via JSON shape).

---

## Section 4 — Feature coverage gaps

Routes with no direct `client.get/post` coverage in the current test suite
(50 of 113, all need new tests):

```
/auditoria/prune
/clientes/bulk-eliminar
/clientes/{customer_id}
/clientes/{customer_id}/editar
/excel/mode-guidance
/guia/{section}
/inventario/export.csv
/inventario/{ing_id}
/inventario/{ing_id}/ajustar
/inventario/{ing_id}/editar
/inventario/{ing_id}/eliminar
/inventario/{ing_id}/movimientos
/merma/receta
/pedidos/board
/pedidos/bulk-cancel
/pedidos/bulk-fulfill
/pedidos/export-csv
/pedidos/{pedido_id}
/pedidos/{pedido_id}/duplicate
/pedidos/{pedido_id}/fulfill
/pedidos/{pedido_id}/status
/pedidos/{pedido_id}/stock-preview
/p/{public_token}                    ← K6 regression target
/productos/bulk-eliminar
/productos/export.csv
/productos/{p_id}/editar
/productos/{p_id}/eliminar
/recetas/{r_id}
/recetas/{r_id}/editar
/reorder/generate-po
/reportes/comparacion
/reportes/diario/pdf
/reportes/iva/pdf
/reportes/libro-ventas/set-pdf
/reportes/metodos-pago
/reportes/retencion
/reportes/top-productos
/reportes/valor-pedido
/reportes/ventas-hora
/settings/business
/settings/fiscal
/settings/theme
/suppliers/{s_id}/editar
/suppliers/{s_id}/eliminar
/suppliers/{s_id}/ordenes
/users/crear
/users/{user_id}/editar
/users/{user_id}/eliminar
/ventas/{sale_id}/anular
/ventas/{sale_id}/recibo
```

### Feature gaps (cross-cutting)

| Area | Gap |
|---|---|
| **K1 Ventas 500** | `/ventas` page-level TemplateRuntimeError — needs targeted Jinja trace |
| **K6 Public token** | `/p/{token}` lookup bug (already fixed per CHANGELOG 2026-09-21, no test exists yet) |
| **K7 Users admin gate** | skipped test leaves admin-only enforcement unverified at HTTP level |
| **PDF endpoints** | No test asserts `Content-Type: application/pdf` or magic bytes for `/reportes/diario/pdf`, `/reportes/iva/pdf`, `/reportes/libro-ventas/set-pdf` |
| **CSV exports** | No test asserts column ordering / money-as-int invariant for `/inventario/export.csv`, `/productos/export.csv`, `/pedidos/export-csv`, `/ventas/export.csv`, `/reportes/precios/csv` |
| **Bulk endpoints** | `/pedidos/bulk-*`, `/productos/bulk-eliminar`, `/clientes/bulk-eliminar`, `/auditoria/prune` — no atomicity test |
| **Adjustment atomicity** | `/inventario/{id}/ajustar` should write `StockMovement` + `AuditLog` + update `stock_qty` in one txn |
| **Fulfilment atomicity** | `/pedidos/{id}/fulfill` should write `Sale` + `SaleStockMove` + decrement inventory in one txn |
| **EOD atomicity** | `/eod/completar` partial coverage only — add idempotency test (re-POST same date = 422) |
| **Supabase fallback** | Local auth path under missing Supabase env not exercised end-to-end (only unit-level) |
| **Schema drift visible** | `schema_version_mismatch > 0` should make `/healthz/schema` return 503, not 200 (only `db` unit test exists) |
| **Rate-limit write** | `/pedidos/nuevo`, `/ventas/nueva`, `/inventario/{id}/ajustar`, `/merma/registrar` should trip 429 after N writes |
| **CSRF** | Existing coverage good — add integration: GET form → POST without token = 403, with token = 303 |
| **Settings round-trip** | `/settings/business|fiscal|theme` — POST then GET, assert value persisted to `AppMeta` |
| **Override endpoint** | `/produccion/override` has no test for what "override" actually overrides |
| **Demo reset** | `/ops/reset-demo-data` — destructive; needs gated test (admin only, snapshot before) |

---

## Section 5 — Recommended test file structure

Conventions:
- File name: `test_<router>_<feature>.py` (existing style) or
  `test_<NNN>_<feature>.py` for gap-fillers.
- Each file uses shared `client`, `authed_client`, `session_factory`,
  `tmp_db_path` fixtures from `tests/conftest.py`.
- Group into `tests/p0/`, `tests/p1/` … later, but keep all in `tests/` for now
  to match the existing flat layout.

| # | File | Target tests | Covers |
|---|---|---:|---|
| **P0 — Blockers / K-regressions** | | | |
| 1 | `tests/test_k1_ventas_no_template_error.py` | 3 | K1 — load `/ventas` with empty/full DB, assert 200 + key Jinja blocks render |
| 2 | `tests/test_k6_public_pedido_token_lookup.py` | 4 | K6 — create pedido, mint public token, GET `/p/{token}` returns 200; tampered token 404; bad PK-style integer 404 |
| 3 | `tests/test_k7_users_admin_enforcement.py` | 3 | K7 — replace `pytest.skip`; non-admin 403 (not 401/500); admin 200; POST `/users/{id}/eliminar` as non-admin 403 |
| 4 | `tests/test_p0_outage_prevention.py` *(existing)* | 4 | keep green — already catches K2/K3/K4/K5 |
| 5 | `tests/test_hotfix_regressions.py` *(existing)* | 15 | keep green — fail-closed for locked hotfixes |
| **P1 — Core CRUD / auth / health** | | | |
| 6 | `tests/test_smoke_all_html_pages.py` | 62 | One `test_<route>_page_loads` per GET-HTML endpoint (uses `_seed` helper for empty-DB-safe routes) |
| 7 | `tests/test_smoke_all_json_endpoints.py` | 30 | One `test_<route>_json_shape` per JSON-returning endpoint (`/healthz/*`, `/api/search`, `/ventas/buscar`, `/excel/validar`, `/clientes/api/*`) |
| 8 | `tests/test_smoke_all_csv_exports.py` | 5 | Assert `Content-Type: text/csv`, money-as-int column, expected header row for `/inventario`, `/productos`, `/pedidos`, `/ventas`, `/reportes/precios` |
| 9 | `tests/test_smoke_all_pdf_endpoints.py` | 3 | Assert `%PDF-` magic + Content-Type for `/reportes/diario/pdf`, `/reportes/iva/pdf`, `/reportes/libro-ventas/set-pdf` |
| 10 | `tests/test_auth_login_logout.py` | 8 | GET `/login` 200; POST valid → 303; bad pw → 200+error; rate-limit on 5 fails; GET `/logout` → 303; POST `/logout` clears cookie; POST `/forgot-password` returns ok JSON; SSO-disabled flow when env missing |
| 11 | `tests/test_inventory_adjust_atomicity.py` | 4 | POST `/inventario/{id}/ajustar` — single txn writes `StockMovement` + `AuditLog` + updates `stock_qty`; bad qty → 422; concurrent → no double-write |
| 12 | `tests/test_pedidos_fulfill_atomicity.py` | 4 | POST `/pedidos/{id}/fulfill` — single txn creates `Sale` + `SaleStockMove` + decrements stock; double-fulfill → 4xx |
| 13 | `tests/test_eod_idempotency.py` | 3 | POST `/eod/completar` — first call 303; same date second call → 422; future date → 422 |
| 14 | `tests/test_clientes_crud_roundtrip.py` | 6 | create via API + form; detail 200; bulk delete 303; missing customer_id → 404 |
| 15 | `tests/test_suppliers_crud_roundtrip.py` | 5 | create/edit/delete/list + `/suppliers/{id}/ordenes` returns 200 |
| 16 | `tests/test_products_crud_roundtrip.py` | 6 | create/edit/delete/bulk-delete/export; is_available default value |
| 17 | `tests/test_recipes_polymorphic_roundtrip.py` | 5 | create recipe with `line_kind=ingredient` + `line_kind=recipe`; `/recetas/{id}` shows batch_cost + unit_cost |
| **P2 — Workflows / reports** | | | |
| 18 | `tests/test_dashboard_kpis_end_to_end.py` | 5 | seed → sales → dashboard shows correct totals, top products, margin erosion alerts; <90 queries (perf gate) |
| 19 | `tests/test_reportes_pages_load.py` | 13 | smoke each `/reportes/*` HTML page; verify required blocks render |
| 20 | `tests/test_pedidos_bulk_endpoints.py` | 4 | `/pedidos/bulk-fulfill` + `/pedidos/bulk-cancel` — atomic; partial failure roll-back |
| 21 | `tests/test_excel_import_full_flow.py` | 6 | upload herbus_drive_sample.xlsx → validar → importar → row_counts; bad file → 422; mode-guidance 200; export→import round-trip (already in `test_excel_patch.py` — keep) |
| 22 | `tests/test_settings_roundtrip.py` | 4 | POST `/settings/business|fiscal|theme` → GET `/settings` shows persisted values in `AppMeta` |
| 23 | `tests/test_auditoria_filters_and_prune.py` | 4 | filter by IP, user, date range; POST `/auditoria/prune` reduces row count; unauthorized POST is 403 |
| 24 | `tests/test_merma_receta_and_registrar.py` | 4 | both POSTs work; WasteLog rows correct; audit created |
| 25 | `tests/test_produccion_override.py` | 3 | GET 200; POST override updates `ProductionCompletion`; non-admin → 403 |
| **P3 — Cross-cutting / hardening** | | | |
| 26 | `tests/test_csrf_on_forms.py` | 6 | each form endpoint: GET → 200 with token; POST without token → 403; POST with token → 303 |
| 27 | `tests/test_rate_limit_writes.py` | 5 | `/ventas/nueva`, `/pedidos/nuevo`, `/inventario/{id}/ajustar`, `/merma/registrar`, `/excel/importar` — after N writes return 429 |
| 28 | `tests/test_session_lifecycle.py` | 4 | unauthenticated GET `/productos` → 303 → `/login`; expired cookie → same; static assets skipped (existing covered) |
| 29 | `tests/test_supabase_env_fallback.py` | 4 | with env → supabase path used (mock); without → local path used; missing `SUPABASE_URL` does not 500 |
| 30 | `tests/test_schema_drift_blocks_healthz.py` | 3 | when DB schema = code - 1, `/healthz/schema` returns 503; `/healthz` returns 200 with `ready=false` |
| 31 | `tests/test_static_versioned_assets.py` | 3 | HTML contains `?v=` on `app.css`, `calendar.css`; `Cache-Control` header set |
| 32 | `tests/test_nav_dropdown_aria.py` | 4 | `aria-haspopup`, `aria-expanded`, `role=menu`, Esc-to-close markup present in base.html |
| 33 | `tests/test_a11y_forms_and_modals.py` | 8 | every form has `<label>` or `aria-label`; `confirm_modal` macro has `role=dialog`, focus trap, Esc |
| 34 | `tests/test_security_headers.py` | 4 | CSP, X-Content-Type-Options, Referrer-Policy, Permissions-Policy on every HTML response |
| 35 | `tests/test_observability_logs.py` | 3 | `/healthz/errors` surfaces recent errors; structured logging enabled; request_id propagates |
| 36 | `tests/test_backup_pre_mutate.py` | 4 | auto-backup runs before `/ventas/nueva`, `/pedidos/{id}/fulfill`, `/excel/importar`, `/ops/reset-demo-data` |
| 37 | `tests/test_demo_reset_safety.py` | 3 | `/ops/reset-demo-data` admin-only; restores known seed state; audit logs the reset |
| **P4 — Performance / load** | | | |
| 38 | `tests/test_perf_route_query_budgets.py` | 8 | each major page <N queries: inicio<90, /productos<40, /inventario<40, /recetas<40, /reportes/diario<60, /reportes/iva<60, /pedidos<40, /clientes<40 |
| 39 | `tests/test_perf_excel_roundtrip.py` | 3 | export of 1000-row xlsx <3s; import <5s; round-trip preserves ints |
| **P5 — Smoke for ops endpoints** | | | |
| 40 | `tests/test_ops_status_visibility.py` | 3 | `/ops/status` shows schema drift, last backup age, env fingerprint (no secrets), error count |

---

## Section 6 — Estimated totals

| Tier | New test files | New tests | Estimated runtime |
|---|---:|---:|---:|
| P0 (blockers / K-regressions) | 3 new + 2 keep | 14 + 19 = **33** | 12 s |
| P1 (CRUD / auth / health) | 12 | 12 × ~5 avg = **60** | 90 s |
| P2 (workflows / reports) | 8 | 8 × ~4 avg = **32** | 60 s |
| P3 (cross-cutting) | 12 | 12 × ~4 avg = **48** | 110 s |
| P4 (perf) | 2 | **11** | 180 s (perf tests are slow by design) |
| P5 (ops) | 1 | **3** | 5 s |
| **Totals** | **38 new** | **~187 new** | **~8 min** |

Add to existing ~1,500 tests → **~1,687 tests** in suite. Coverage target
stays at **80%** per AGENTS.md; expected post-implementation coverage of
`app/routers/` and `app/services/`: **>85%** (currently estimated 70-75%
based on uncovered-route count).

---

## Section 7 — Priority order for implementation

**Sprint 1 — Unblock production (must ship before any other PR merges)**

1. `test_k1_ventas_no_template_error.py` — fix the live 500 on `/ventas`.
2. `test_k6_public_pedido_token_lookup.py` — protect the WhatsApp pickup link
   regression.
3. `test_k7_users_admin_enforcement.py` — replace the skipped test; gate
   `/users` and `/ops/reset-demo-data`.
4. `test_smoke_all_html_pages.py` — 62 page-load tests. Every template that
   renders must 200; if any regresses to 500 we catch it on PR.
5. `test_smoke_all_json_endpoints.py` — 30 JSON shape tests.

**Sprint 2 — Atomicity guarantees (financial blast radius)**

6. `test_inventory_adjust_atomicity.py`
7. `test_pedidos_fulfill_atomicity.py`
8. `test_eod_idempotency.py`
9. `test_backup_pre_mutate.py`
10. `test_clientes_crud_roundtrip.py`, `test_suppliers_crud_roundtrip.py`,
    `test_products_crud_roundtrip.py`

**Sprint 3 — Cross-cutting hardening**

11. `test_csrf_on_forms.py`
12. `test_rate_limit_writes.py`
13. `test_session_lifecycle.py`
14. `test_supabase_env_fallback.py`
15. `test_schema_drift_blocks_healthz.py`
16. `test_security_headers.py`
17. `test_static_versioned_assets.py`
18. `test_nav_dropdown_aria.py`

**Sprint 4 — Reports & workflow coverage**

19. `test_reportes_pages_load.py`
20. `test_dashboard_kpis_end_to_end.py`
21. `test_pedidos_bulk_endpoints.py`
22. `test_excel_import_full_flow.py`
23. `test_settings_roundtrip.py`
25. `test_auditoria_filters_and_prune.py`
26. `test_merma_receta_and_registrar.py`
27. `test_produccion_override.py`

**Sprint 5 — Performance gates (last; slow tests)**

28. `test_perf_route_query_budgets.py`
29. `test_perf_excel_roundtrip.py`
30. `test_smoke_all_csv_exports.py`, `test_smoke_all_pdf_endpoints.py`
31. `test_a11y_forms_and_modals.py`
32. `test_observability_logs.py`
33. `test_ops_status_visibility.py`
34. `test_recipes_polymorphic_roundtrip.py`
35. `test_demo_reset_safety.py`

---

## Appendix A — Test execution conventions

```bash
# Local
uv run pytest                          # full suite
uv run pytest -x --tb=short            # fast fail
uv run pytest -k "smoke" -q            # only smoke tests
uv run pytest tests/test_p0_outage_prevention.py -v
uv run pytest --cov=app --cov-report=term-missing

# Postgres variant (CI)
uv run pytest -m postgres --db-url=postgresql://... -v
```

Test fixtures to know:

| Fixture | Source | Purpose |
|---|---|---|
| `tmp_db_path` | `conftest.py` (autouse) | forces temp SQLite, never production path |
| `app_engine` | conftest | SQLAlchemy engine on tmp DB |
| `session_factory` | conftest | `sessionmaker(bind=engine)` |
| `client` | conftest | FastAPI `TestClient` with auth-bypass |
| `authed_client` | conftest | alias of `client` (auth already bypassed) |
| `monkeypatch` | pytest | env-var isolation for Supabase keys etc. |
| `mini_xlsx_path` | conftest | tiny xlsx fixture for import tests |

## Appendix B — Mapping existing tests to router coverage

| Router | Existing coverage | Gap |
|---|---|---|
| auditoria | `test_auditoria_filters.py`, `test_audit_prune.py`, `test_auditoria_ip_user_filter.py` | prune happy path |
| auth | `test_auth.py`, `test_auth_gate.py`, `test_auth_integration.py`, `test_auth_supabase.py`, `test_login_a11y_regression.py` | none material |
| customers | `test_clientes_filter.py`, `test_clientes_routes.py`, `test_customers.py`, `test_customer_picker.py` | bulk-eliminar |
| dashboard | `test_dashboard_*.py` (5) | none |
| eod | `test_eod_completion.py`, `test_p1_route_coverage.py` | idempotency |
| excel_io | `test_excel_patch.py`, `test_import_roundtrip.py`, `test_real_drive_shape_fixture.py`, `test_xlsx_fixtures.py`, `test_lazy_openpyxl.py` | mode-guidance, exportar |
| health | `test_healthz.py`, `test_health_cache.py`, `test_healthz_errors.py`, `test_healthz_schema.py`, `test_readiness.py` | none material |
| help | `test_help_route.py` | `{section}` 404 |
| merma | `test_waste.py`, `test_p1_route_coverage.py` | `/merma/receta` |
| ops | `test_ops_status.py`, `test_demo_reset.py` | reset happy path with state diff |
| pedidos | `test_pedidos.py`, `test_p1_route_coverage.py` | board, bulk-*, {id}/fulfill, /p/{token} |
| produccion | `test_produccion_route.py`, `test_produccion_calendar.py` | override |
| products | `test_productos_filter.py` | bulk-eliminar, export, delete |
| recipes | `test_recipe_polymorphic.py`, `test_recipe_intel.py`, `test_costing.py` | `{id}/editar` |
| reorder | `test_reorder_restock.py`, `test_reorder_suggestions.py` | generate-po |
| reportes | `test_reportes_precios.py`, `test_reports.py` | most `/reportes/*` pages and all PDFs |
| sales | `test_sale_via_sku.py`, `test_sales_export.py`, `test_sales_overhaul.py`, `test_void_sale.py`, `test_void_semantics.py` | `/ventas/{id}/recibo`, `/ventas/{id}/anular`, **page 500** |
| search | (none) | full |
| settings | `test_settings.py`, `test_settings_ui.py` | round-trip POST → GET |
| suppliers | `test_p1_route_coverage.py` | `{id}/editar`, `/ordenes` |
| users | `test_p1_route_coverage.py` (1 skipped) | happy path |