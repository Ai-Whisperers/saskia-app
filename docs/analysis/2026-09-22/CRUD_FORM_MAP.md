# Sazón — CRUD Form Field Map (gap analysis)

**Generated:** 2026-09-22 — exhaustive field-by-field map of every CRUD form vs the model layer, with validation, hidden fields, missing surface, and gap catalogue.

**Codebase size reviewed:**
- 18 routers, 49 templates, 12 model files (1 model module).
- 180+ test files (regression coverage noted per resource).

**Notation:**
- **R** = required (server rejects 400 if missing OR `Form(...)`/`required` on input)
- **O** = optional (empty string → NULL via `.strip() or None`)
- **C** = computed / derived (UI-only, never POSTed)
- **H** = hidden (CSRF, IDs, redirect)
- **D** = derived on submit (model default or server-side computation)
- **gap** = section "Gaps" at the end of each resource summarises the deltas

---

## Global conventions

- **Auth:** Every router (except `/login`, `/healthz*`, `/api/docs*`, `/static/*`, `/p/{token}`) is gated by `require_login`. All mutating endpoints carry the standard dependency.
- **CSRF strategy (per `app/rms/csrf.py`):** Signed `csrf_token` cookie is set on any GET that returns HTML. POST/PUT/DELETE/PATCH checks the cookie is **present + signature valid**. The cookie itself is the token; **forms do NOT carry a hidden `csrf_token` input**. The cookie check + `SameSite=lax` is the actual defense. Tests (`test_csrf_on_forms.py`) verify POST without cookie → 403.
- **CSRF bug found:** `app/templates/_components/confirm_modal.html` lines 80–84 look for `input[name="_csrf_token"]` to graft into dynamically-created forms, but `_CSRF_FORM_FIELD` in csrf.py is `"csrf_token"` (no underscore) and no template ever renders that field. **Net effect:** the modal-spawned form posts only the `extraInputs` — it still passes CSRF because the cookie check fires regardless, but the `csrf_token` field on the spawned form is the wrong name AND never present. **Dead code.**
- **Money:** integer Gs. (`{sale_price_gs, purchase_price_gs, discount_gs, total_gs}` are all `Mapped[int]`). Parsed via `app.rms.money.parse_gs` which strips dots/commas and returns int.
- **Units:** enum `{g, kg, ml, l, und}` enforced by DB CHECK on `ingredient.unit` + `recipe.yield_unit`. `app/rms/units.Unit.coerce` is the canonical parser; bad values raise `HTTPException(400, "Unidad inválida")`.
- **TZ:** `America/Asuncion` (`app/rms/config.ASUNCION_TZ`). `Sale.sold_at`, `Sale.tz`, and all sale timestamps are Asuncion-aware.
- **Rate-limit:** writes to `/ventas/nueva`, `/merma/registrar`, `/merma/receta`, `/eod/completar`, `/reorder/registrar`, `/produccion/override`, `/produccion/template` all use `is_write_rate_limited(max_per_minute=10)` → 429 on burst.

---

## 1. Producto — `/productos`

### Routes
| Method | Path | Form / API | Notes |
|---|---|---|---|
| GET | `/productos` | HTML list, sort+filter+paginate (50/page) | q, has_recipe, sort, dir, page |
| GET | `/productos/export.csv` | CSV | no filter |
| GET | `/productos/nuevo` | HTML form (new) | `producto_form.html` mode=new |
| POST | `/productos/nuevo` | create | form-encoded |
| GET | `/productos/{id}/editar` | HTML form (edit) | `producto_form.html` mode=edit |
| POST | `/productos/{id}/editar` | update | |
| POST | `/productos/{id}/eliminar` | delete (blocked if sales exist) | 409 if used |
| POST | `/productos/bulk-eliminar` | bulk delete | `ids` comma-separated |
| GET | `/productos/api/...` | **does not exist** — task spec is wrong | (only `/clientes/api/*` exists) |

### Fields (`producto_form.html` + `routers/products.py`)
| Field | Type | R/O | HTML attr | Server validation | Model column |
|---|---|---|---|---|---|
| `name` | text | **R** | `required` | non-empty after `.strip()` (unique constraint) | `product.name String(120) unique` |
| `portion_label` | text | O | (no required) | empty → `"1 unidad"` | `product.portion_label String(60) default="1 unidad"` |
| `sale_price_gs` | number | **R** | `required step=1 min=0` | `parse_gs()` int; rejects negative (DB CHECK) | `product.sale_price_gs Integer ≥ 0` |
| `recipe_id` | select | O | (default blank → NULL) | `int(recipe_id) if recipe_id else None` — **no FK validation; nonexistent IDs cause IntegrityError → 500** | `product.recipe_id FK(recipe.id)` |
| `notes` | textarea | O | no maxlength | empty → None | `product.notes Text` |
| `sku` | text | O | no maxlength, no `pattern` | empty → None; **no uniqueness check on POST** (model has `unique=True` → IntegrityError → 500) | `product.sku String(32) unique` |
| `is_available` | checkbox | O | default `checked` | `is_available == "on"` (string compare) | `product.is_available Boolean default True` |
| `image_url` | url | O | `type=url` | empty → None; **no URL reachability check** | `product.image_url String(256)` |
| `category` | text | O | no maxlength | empty → None | `product.category String(32)` |
| `tags` | text | **MISSING** | — | — | `product.tags Text` — **model has column, form has no input** |
| `id` (hidden) | — | — | — | server uses URL `{id}` | |
| `csrf_token` | hidden | — | — | **NOT rendered in form** | |

### Gaps (Producto)
- ❌ `tags` column on the model (`app/rms/models.py:201`) has NO form input — drift.
- ❌ `/productos/{id}/eliminar` has no confirm-modal wired up in `productos.html` — only bulk-delete goes through `SaskiaConfirmModal`.
- ❌ `sku` lacks server-side `select Product where sku=?` uniqueness pre-check (race window — duplicate SKUs → 500).
- ❌ `recipe_id` accepts any int; nonexistent IDs → IntegrityError 500 instead of friendly 400.
- ❌ `notes` textarea: no `maxlength` (model column is `Text`, unbounded).
- ❌ `image_url`: `type=url` only checks syntax; no fetch/HEAD validation → broken links go to DB silently.
- ❌ No CSRF hidden input in any product form; rely solely on cookie (works, but `confirm_modal.html` looks for the wrong name).
- ❌ `csrf_token` field never written to POSTed forms (acceptable per middleware, but the template's data-entry path silently relies on cookie check).

### Regression coverage
- `tests/test_products_crud_roundtrip.py` — full create→list→update→delete flow.
- `tests/test_productos_filter.py` — q/has_recipe/sort/paginate.
- `tests/test_smoke_all_html_pages.py` — `/productos` returns 200.
- `tests/test_p1_route_coverage.py`, `tests/test_routes.py` — route discovery.

---

## 2. Ingrediente — `/inventario`

### Routes
| Method | Path | Form / API |
|---|---|---|
| GET | `/inventario` | HTML list, sort+paginate |
| GET | `/inventario/export.csv` | CSV |
| GET | `/inventario/nuevo` | HTML form |
| POST | `/inventario/nuevo` | create |
| GET | `/inventario/{id}` | HTML detail (read-only) |
| GET | `/inventario/{id}/editar` | HTML form |
| POST | `/inventario/{id}/editar` | update |
| POST | `/inventario/{id}/eliminar` | delete (blocked if in any recipe) |
| POST | `/inventario/{id}/ajustar` | adjust stock (modal) |
| GET | `/inventario/{id}/movimientos` | HTML history |

### Fields (`inventario_form.html` + `inventory.py`)
| Field | Type | R/O | HTML attr | Server validation | Model column |
|---|---|---|---|---|---|
| `name` | text | **R** | `required` | non-empty after `.strip()` (unique) | `ingredient.name String(120) unique` |
| `category` | text | O | no maxlength | empty → None | `ingredient.category String(32)` |
| `unit` | select | **R** | `required` enum | `Unit.coerce()`; bad → 400 Spanish | `ingredient.unit String(16)` CHECK in {g,kg,ml,l,und} |
| `stock_qty` | number | **R** | `required step=0.01 min=0` | ≥ 0 else 400 | `ingredient.stock_qty Float default 0` |
| `opening_stock_qty` | number | O | `step=0.01 min=0` | parses if non-empty, else None | `ingredient.opening_stock_qty Float` |
| `opening_stock_date` | date | O | no `pattern` (date type) | empty → None | `ingredient.opening_stock_date Text (ISO)` — **stored as Text not Date** |
| `min_stock_qty` | number | **R** | `required step=0.01 min=0` | ≥ 0 | `ingredient.min_stock_qty Float default 0` |
| `reorder_point` | number | O | `step=0.01 min=0` | empty → None | `ingredient.reorder_point Float` |
| `purchase_price_gs` | number | O | `step=1 min=0` | `_parse_price()` → int or None | `ingredient.purchase_price_gs Integer` |
| `notes` | textarea | O | no maxlength | empty → None | `ingredient.notes Text` |
| `supplier_id` | hidden/select | **MISSING** | — | — | `ingredient.supplier_id FK(supplier.id)` exists in model, no form input |
| `subcategory` | text | **MISSING** | — | — | `ingredient.subcategory String(32)` — no form |
| `role` | text | **MISSING** | — | — | `ingredient.role String(32)` — no form |
| `allergens` | text | **MISSING** | — | — | `ingredient.allergens Text` — no form |
| `dietary_tags` | text | **MISSING** | — | — | `ingredient.dietary_tags Text` — no form |
| `shelf_life_days` | number | **MISSING** | — | — | `ingredient.shelf_life_days Integer` — no form |
| `max_stock_qty` | number | **MISSING** | — | — | `ingredient.max_stock_qty Float` — no form (reorder compute uses 2x min as fallback) |
| `lead_time_days` | number | **MISSING** | — | — | `ingredient.lead_time_days Integer default 3` — no form |
| `last_consumed_at` | datetime | C | — | derived | computed via sale/usage |

### Stock-adjust modal (`inventario.html` modal)
| Field | Type | R/O | HTML attr | Server validation |
|---|---|---|---|---|
| `adjustment` | number | **R** | `step=0.01` (no `min=0` so negative allowed) | 0 → redirect (no-op); negatives with `confirm_negative != "yes"` → redirect with "no_confirm:" flash |
| `reason` | text | O | `maxlength=200` | empty → None; truncated to 200 chars in browser |
| `confirm_negative` | hidden | O | empty string default | must be `"yes"` to allow negative result |
| `ing_id` | hidden | **R** | set via JS `openAdjustModal()` | — |

### Gaps (Ingredient)
- ❌ `supplier_id` not on the form (Phase 7 reorder linked it; only `app/services/ingredient_intel.py` reads it).
- ❌ `subcategory`, `role`, `allergens`, `dietary_tags`, `shelf_life_days`, `max_stock_qty`, `lead_time_days` all in model, **none editable from UI**.
- ❌ `opening_stock_date` stored as `Text` in DB (not Date) — sortability depends on ISO format being preserved; no enforcement.
- ❌ Stock-adjust modal `adjustment` input has no `max` cap — operator can type 999999.
- ❌ No upper bound on `purchase_price_gs` (could overflow nothing today but no quick check).
- ❌ `purchase_price_gs` form has `step="1"` but `parse_gs` accepts decimals — inconsistent UX (browser will reject 8000.50 but server would accept it if pasted).
- ❌ Negative stock allowed via `confirm_negative=yes`; warning is shown, no audit log entry (silent in audit log — only StockMovement row is created).
- ❌ `category` is free-text — typos create phantom categories (`"Lacteos"` vs `"Lácteos"` vs `"Lácteos,"`).
- ❌ No bulk-edit / bulk-import surface for ingredients beyond `/excel/importar` (PATCH/FULL/APPEND).
- ❌ `opening_stock_qty` accepts decimals but the stock_movement written is `movement_type='initial'` with no recorded_by audit detail about who set opening stock (only default `current_user_id`).

### Regression coverage
- `tests/test_inventory_adjust_atomicity.py` — adjust is atomic with stock_movement row.
- `tests/test_inventario_price_strip.py` — price history sparkline.
- `tests/test_costing.py` — recipe cost math.
- `tests/test_smoke_all_html_pages.py` — list/detail pages.
- `tests/test_phase4_routes.py` — new endpoints covered.

---

## 3. Inventario movements (StockMovement) — `/inventario/{id}/movimientos`, `/inventario/{id}/ajustar`

### StockMovement model (`models.py:783`)
- `id`, `ingredient_id` (FK CASCADE), `movement_type ∈ {sale, adjustment, merma, reorder, initial}`, `qty` (signed), `reason` (text), `reference_id` (FK polymorphic), `reference_type` (string), `recorded_at`, `created_by`.

### Fields — `inventory_adjust` POST `/inventario/{id}/ajustar`
Same as the modal above; **server-side stamps `created_by`** from `current_user_id(request) or "operator"`.

### Fields — `movimientos` GET (read-only page)
| Field | Source | Notes |
|---|---|---|
| `movement_type` | DB | shown as badge |
| `qty` (signed) | DB | colour-coded |
| `reason` | DB | shown truncated |
| `reference_type` | DB | link to source |
| `reference_id` | DB | link to source |
| `recorded_at` | DB | displayed local |
| `created_by` | DB | shown |
| `balance_before`/`balance_after` | **C** | computed in router by walking history backwards from current_stock |

### Gaps
- ❌ No UI to **manually create** a `movement_type='adjustment'` outside the modal — but `/inventario/{id}/ajustar` is exactly that endpoint (single-purpose modal flow).
- ❌ `reference_id` is polymorphic (sale/waste_log/adjustment/reorder/None) but UI shows raw integer — no link to source for `adjustment` type.
- ❌ No CSV export of movements; only `/inventario/export.csv` exists for ingredient rows, not movement rows.
- ❌ Movements page is **read-only**; cannot edit or delete entries (intentional, but no way to correct a wrong merma/initial stock other than another adjust).

### Regression coverage
- `tests/test_inventory_adjust_atomicity.py` — atomicity of adjust + stock_movement.
- `tests/test_waste.py` — waste → movement integration.

---

## 4. Receta — `/recetas`

### Routes
| Method | Path | Form / API |
|---|---|---|
| GET | `/recetas` | HTML list with q, ingredient filter, sort |
| GET | `/recetas/nueva` | HTML form |
| POST | `/recetas/nueva` | create |
| GET | `/recetas/{id}` | HTML detail (read-only) |
| GET | `/recetas/{id}/editar` | HTML form + scale param |
| POST | `/recetas/{id}/editar` | update (replaces all lines) |
| GET | `/recetas/{r_id}` | detail (also used by production page) |
| (no /eliminar GET/POST) | — | **no delete endpoint** — task spec mentions `/recetas/{id}/eliminar` but it doesn't exist |

### Fields (`receta_form.html` + `recipes.py`)
| Field | Type | R/O | HTML attr | Server validation | Model column |
|---|---|---|---|---|---|
| `name` | text | **R** | `required` | non-empty after `.strip()` (unique) | `recipe.name String(120) unique` |
| `yield_qty` | number | O | `step=0.01 min=0` (no `max`) | empty → None; CHECK `> 0` if not null | `recipe.yield_qty Float` |
| `yield_unit` | select | **R** | `required` | `Unit.coerce()` | `recipe.yield_unit String(16)` CHECK in {g,kg,ml,l,und} |
| `prep_minutes` | number | O | `min=0` (no max, no step) | empty → None | `recipe.prep_minutes Integer` |
| `cook_minutes` | number | O | `min=0` (no max, no step) | empty → None | `recipe.cook_minutes Integer` |
| `difficulty` | number | **MISSING** | — | — | `recipe.difficulty Integer` (1-5) — model has it, no form input |
| `family` | text | O | no maxlength | empty → None | `recipe.family String(32)` |
| `dietary_tags` | text | O | placeholder only, no `pattern` for comma-sep | empty → None | `recipe.dietary_tags Text` |
| `notes` | textarea | O | no maxlength | empty → None | `recipe.notes Text` |
| `line_kind[]` | select | **R per line** | `required` | in {'ingredient','sub_recipe'} via DB CHECK | `recipe_line.line_kind` |
| `line_target_id[]` | select | **R per line** | (no required attr) | parses if non-empty + qty > 0 | `recipe_line.line_ref_id` |
| `line_qty[]` | number | **R per line** | `required step=0.01 min=0` | > 0 (DB CHECK); **no upper bound** | `recipe_line.qty Float > 0` |
| `line_unit[]` | select | O per line | (no required) | `Unit.coerce()` else "" (silent fall-through) | `recipe_line.line_unit String(8) default ""` |
| `line_notes[]` | text | O per line | no maxlength | empty → None | `recipe_line.notes Text` |
| `scale_factor` (GET only) | select | O | — | clamped to [0.25, 10] | — |

### Gaps (Recipe)
- ❌ **No DELETE endpoint** — task spec mentions `/recetas/{id}/eliminar` but router only has GET/POST new+edit. Templates don't link to delete.
- ❌ `difficulty` (1-5 scale) has no form input.
- ❌ No `max` on `prep_minutes` / `cook_minutes` — operator can type 999999.
- ❌ `dietary_tags` free-text with no parsing; comma-separated, but model also has it on `Ingredient` — inconsistent.
- ❌ `line_qty` lacks `max` bound — could overflow costing math.
- ❌ `line_unit` silently falls back to "" on bad value — no Spanish 400; user sees "0 kg flour" with no unit and no error.
- ❌ `line_target_id` for `sub_recipe` kind: in edit mode, dropdown is filtered by `Recipe.id != r_id` — correct. But in **new** mode, `other_recipes` includes ALL recipes including those that may reference this one — risk of circular reference (costing walks would infinite loop).
- ❌ **No CSRF hidden input** on the recipe form.
- ❌ On update, **all old lines are deleted then re-inserted** (`for old in list(r.lines): session.delete(old)`) — if the form has a bug, ingredient FK references in `recipe_line.line_ref_id` are orphaned in the audit trail (no record of what changed).
- ❌ `yield_qty` defaults to `12` in the template — magic number.

### Regression coverage
- `tests/test_recipes_polymorphic_roundtrip.py` — ingredient + sub_recipe lines.
- `tests/test_recipe_polymorphic.py` — polymorphic walk.
- `tests/test_recipe_intel.py` — recipe intelligence.
- `tests/test_p2_audit_validations.py`, `tests/test_p3_operational_gates.py` — operational checks.

---

## 5. Receta lines (polymorphic: ingredient or sub-recipe)

The RecipeLine form is fully integrated into `receta_form.html` (no separate page). Each row in `#lines` div has 6 controls: kind / target / qty / unit / notes / delete-row button.

### Fields (per row, repeated)
Already covered above (`line_kind[]`, `line_target_id[]`, `line_qty[]`, `line_unit[]`, `line_notes[]`).

### Hidden
- `ing_id` (current ingredient, in URL) — used to scope the form.

### Derived on read
- `target_name` (resolved via `resolve_line_target(session, line)` in `costing.py`).
- `line_total_gs` (computed server-side for display).

### Gaps
- ❌ When changing a line's `line_kind` from `ingredient` → `sub_recipe` on edit, the existing `line_target_id` is silently retained (in the JS-added rows). On save, the bad combo silently inserts or skips.
- ❌ No client-side validation that `line_qty > 0` matches the model CHECK (`qty > 0`); template `min=0` allows 0.
- ❌ No max-number-of-lines limit (server trusts whatever client posts).
- ❌ Empty rows are silently skipped — UX does not warn "row 3 has missing data".

---

## 6. Cliente — `/clientes`

### Routes
| Method | Path | Form / API |
|---|---|---|
| GET | `/clientes` | HTML list, search/tier/sort/paginate |
| GET | `/clientes/api/search` | JSON (used by picker modal) |
| POST | `/clientes/api/create` | JSON-or-form (used by picker) |
| GET | `/clientes/{id}` | HTML detail |
| GET | `/clientes/{id}/editar` | HTML form |
| POST | `/clientes/{id}/editar` | update |
| POST | `/clientes/bulk-eliminar` | bulk delete |
| (no `/clientes/nuevo` GET) | — | **new customers created via picker modal** |

### Fields (`cliente_editar.html` + `customers.py`)
| Field | Type | R/O | HTML attr | Server validation | Model column |
|---|---|---|---|---|---|
| `name` | text | **R** | `required maxlength=120` | empty → `"(sin nombre)"` (not rejected!) | `customer.name String(120)` (NOT nullable in model) |
| `phone` | tel | O | `maxlength=32` | empty → None | `customer.phone String(32) indexed` |
| `email` | email | O | `type=email maxlength=120` | empty → None; no RFC validation beyond HTML5 | `customer.email String(120)` |
| `cedula` | text | O | `maxlength=32` | empty → None | `customer.cedula String(32) indexed` |
| `notes` | textarea | O | `rows=3 maxlength=2000` | empty → None | `customer.notes Text` |
| `loyalty_points` | number | **MISSING** | — | — | `customer.loyalty_points Integer default 0` (only mutated via sales flow) |
| `created_at` / `updated_at` | datetime | C | — | server-stamped | both default `datetime.utcnow` |

### API create (`POST /clientes/api/create`)
Accepts JSON or form-encoded. Required: `name`. Optional: phone, email, cedula, notes. Phone match → idempotent update via `ensure_customer`.

### Gaps (Cliente)
- ❌ No GET `/clientes/nuevo` standalone — creation via picker modal only. If picker JS fails, there is no fallback form.
- ❌ `name` is `required` on the form but server silently substitutes `"(sin nombre)"` if blank — mismatch between UI (HTML5 required) and server (lenient).
- ❌ No `email` format validation server-side (only `type=email` browser check, bypassed by curl).
- ❌ No `phone` format validation — anything 32 chars accepted. No Paraguay-specific format check.
- ❌ `loyalty_points` not editable from UI (correct — derived from sales), but no surface to view history of point changes.
- ❌ CSV export on `/clientes?format=csv` doesn't include `email` or `cedula` (privacy maybe intentional, but inconsistent with phone).
- ❌ Bulk-delete silently skips customers with sales — no UI feedback ("3 skipped" only shown if 0 succeed, otherwise just one flash).
- ❌ `/clientes/{id}/editar` POST silently redirects with `flash=Cliente+actualizado` even when name was made empty (server substitutes `"(sin nombre)"`).

### Regression coverage
- `tests/test_clientes_crud_roundtrip.py`, `tests/test_customers.py` — full CRUD.
- `tests/test_clientes_filter.py`, `tests/test_clientes_routes.py`.
- `tests/test_customer_picker.py`.
- `tests/test_auditoria_ip_user_filter.py` — verifies `customer.updated` audit event.

---

## 7. Pedido — `/pedidos`

### Routes
| Method | Path | Form / API |
|---|---|---|
| GET | `/pedidos` | HTML list grouped by urgency (default scope: pendientes) |
| GET | `/pedidos/board` | HTML kitchen display |
| GET | `/pedidos/nuevo` | HTML form |
| POST | `/pedidos/nuevo` | create pedido + lines |
| GET | `/pedidos/{id}` | HTML detail |
| POST | `/pedidos/{id}/status` | state-machine transition |
| POST | `/pedidos/{id}/fulfill` | create sales + decrement stock |
| GET | `/pedidos/{id}/stock-preview` | HTML preview (dry-run) |
| GET | `/pedidos/{id}/duplicate` | redirect → new pedido (GET!) |
| GET | `/pedidos/export-csv` | CSV |
| POST | `/pedidos/bulk-fulfill` | bulk |
| POST | `/pedidos/bulk-cancel` | bulk |
| GET | `/p/{token}` | **public, NO auth** — pickup share |
| (no `/pedidos/{id}/cambiar-estado` separate route) | — | consolidated into `/status` |
| (no `/pedidos/{id}/cancelar` POST as standalone) | — | `/status` with `new_status=cancelled` |

### Fields (`pedidos_nuevo.html` + `pedidos.py`)
| Field | Type | R/O | HTML attr | Server validation | Model column |
|---|---|---|---|---|---|
| `customer_id` | select | O | (optional) | must exist if set → 422 | `pedido.customer_id FK(customer.id)` |
| `customer_name` | text | O | autocomplete via datalist (clients api/search) | empty → empty string stored | `pedido.customer_name String(120) default ""` |
| `customer_phone` | text | O | no `type=tel`, no maxlength | empty → None | `pedido.customer_phone String(32) indexed` |
| `promised_date` | date | **R** | `required` | `date.fromisoformat()` else 422 | `pedido.promised_date Date indexed` |
| `promised_time` | time | O | (no required) | empty → None | `pedido.promised_time String(8)` |
| `channel` | select | O | default whatsapp | `normalize_channel()` raw; mapped to canonical display name | `pedido.channel String(32) default "whatsapp"` (raw, not normalized DB value — *drift*) |
| `payment_intent` | select | O | default efectivo | lowercased; not validated against `ALLOWED_PAYMENT_METHODS` | `pedido.payment_intent String(32) default "efectivo"` |
| `notes` | textarea | O | no maxlength | empty → None | `pedido.notes Text` |
| `line_product_id[]` | select | **R per line** | `required` | must exist; else line silently dropped | `pedido_line.product_id FK` |
| `line_qty[]` | number | **R per line** | `required min=0.01 step=0.01` | > 0 (DB CHECK) | `pedido_line.qty Float > 0` |
| `line_unit_price_gs[]` | number | O | `min=0 step=100` | 0 → snapshot from product | `pedido_line.unit_price_gs Integer ≥ 0` |
| `new_status` (status POST) | text | **R** | hidden | in `PEDIDO_STATUSES` + in `PEDIDO_TRANSITIONS[current]` else 422/409 | `pedido.status String(16) default "pending" indexed` |
| `cancel_reason` | text | O | only used if `new_status=cancelled` | empty → None | `pedido.cancel_reason Text` |

### Derived (read-only)
- `customer_name` if Customer FK exists.
- `total_gs`, `qty_total`, `n_lines`, `age_days`, `spend_30d_gs`, `channel_raw`, `public_url`.

### Hidden
- `public_token` (generated server-side, 8 chars from `secrets.token_urlsafe`).
- `fulfilled_at`, `fulfilled_sale_id` (server-stamped on fulfill).

### Gaps (Pedido)
- ❌ `pedido.channel` stored as RAW string ("whatsapp", "WhatsApp", "wsp" all valid input → normalize to display name but store raw) — `/pedidos/export-csv` uses raw, the UI uses normalized. Inconsistent.
- ❌ `payment_intent` not validated against `ALLOWED_PAYMENT_METHODS` on POST — only `pedidos_fulfill` validates when calling `apply_sale`.
- ❌ `customer_phone` has no `type=tel`, no maxlength, no format check.
- ❌ `/pedidos/{id}/duplicate` is **GET** (state-mutating GET is a known antipattern; should be POST).
- ❌ `/pedidos/{id}/fulfill` doesn't ask for confirmation before posting (template uses `SaskiaConfirmModal.show` but the `extraInputs` mechanism is the broken CSRF code).
- ❌ Bulk-cancel/bulk-fulfill accept any `id` (no scope check; e.g., a manager who shouldn't cancel could in theory via UI bypass).
- ❌ Lines with invalid product_id are **silently dropped** — no error message ("3 líneas no se pudieron guardar").
- ❌ `promised_date` in the past: allowed (intentional — back-dating old WhatsApp orders), but no warning UI.
- ❌ No `prep_minutes` or `cost_gs` snapshot at order time (could be useful for margin reporting).
- ❌ Public `/p/{token}` page shows customer phone + name in HTML — fine for pickup confirmation but no rate limit (someone could enumerate 8-char tokens, though 62^8 = 218T is impractical).

### Regression coverage
- `tests/test_pedidos.py`, `tests/test_pedidos_fulfill_atomicity.py`.
- `tests/test_pedidos_bulk_endpoints.py`.
- `tests/test_k6_public_pedido_token_lookup.py` — public pickup.
- `tests/test_smoke_all_html_pages.py` — list/detail/board.

---

## 8. ProdTemplate (PRO-01 weekly plan) — `/produccion/template` POST

### Route
`POST /produccion/template` — `produccion.py:319`. Router exists, but **no template form**. The endpoint is callable only via direct POST (no UI surface).

### Fields
| Field | Type | R/O | Server validation |
|---|---|---|---|
| `weekday` | int | **R** | 0-6 else 400 |
| `product_id` | int | **R** | must exist else 404 |
| `qty` | float | **R** | ≥ 0 else 400 |
| `notes` | text | O | empty → None |

### Gaps
- ❌ **Endpoint exists, no UI.** Anyone hitting this needs to construct the POST manually.
- ❌ No CSRF input (cookie-only defense).
- ❌ No max qty bound.

---

## 9. ProdOverride (PRO-01 per-date) — `/produccion/override` POST

### Route
`POST /produccion/override` — wired in `produccion.html:42`.

### Fields (per row in `produccion.html`)
| Field | Type | R/O | HTML attr | Server validation |
|---|---|---|---|---|
| `for_date` | date (hidden) | **R** | injected from query | `date.fromisoformat()` implicit via FastAPI |
| `product_id` | int (hidden) | **R** | injected from row | must exist else 404 |
| `qty` | number | **R** | `step=0.5 min=0` (no max) | ≥ 0 else 400; 0 → deletes override row |

### Hidden
- The `for_date` and `product_id` are hidden inputs in the row form.

### Derived (UI)
- `forecast_source` (one of `rolling_14d_avg, seasonal_event, manual, template, override`) — server-only.
- `qty_to_produce` — server-only.

### Gaps
- ❌ `qty` has no `max`; same for `line_qty` on recipe form.
- ❌ `for_date` hidden input could be tampered (cookie-CSRF defense only).
- ❌ `qty=0` deletes the override silently — no "remove override?" confirm.

---

## 10. EOD completion — `/eod/completar` POST, `/eod/check` POST (broken), `/eod` GET

### Routes
| Method | Path | Notes |
|---|---|---|
| GET | `/eod` | HTML checklist + today plan |
| POST | `/eod/completar` | production completion upsert |
| POST | `/eod/check` | **TEMPLATE POSTS HERE, ROUTER HAS NO SUCH ROUTE — 405/404 on submit** |

### Fields (`eod.html` lines 22, 138)
| Form | Field | Type | R/O | HTML attr | Server validation |
|---|---|---|---|---|---|
| `/eod/check` (checklist save) | `<item.key>` per checkbox | checkbox | O | `aria-label` set | **router doesn't exist** |
| `/eod/completar` (production) | `product_id` | int (hidden) | **R** | injected | must exist |
| | `for_date` | date (hidden) | **R** | injected | parsed as date |
| | `completed_qty` | number | **R** | `step=0.5 min=0` (no max) | ≥ 0 (DB CHECK) |
| | `notes` | text | O | no maxlength | empty → None |

### Hidden
- `for_date`, `product_id` on each row form.

### Derived
- `progress` (done/total/pct) — server-computed.
- `completions` dict — server-completed map of product_id → qty.
- `reorder_items` — computed via `compute_reorder_list()`.

### Gaps (EOD)
- ❌ **Dead form**: `eod.html:22` posts to `/eod/check`, but no such route exists. The "Guardar cierre" button silently returns 404/405. The checklist UI is non-functional.
- ❌ `completed_qty` accepts floats with `step=0.5` but is stored as Float — no rounding/precision enforcement.
- ❌ `completed_qty` allows 0 — DB CHECK `completed_qty >= 0` permits zero, semantically odd.
- ❌ No multi-product batch completion (one POST per row).

---

## 11. Waste / Merma — `/merma`, `/merma/registrar`, `/merma/receta`

### Routes
| Method | Path | Form / API |
|---|---|---|
| GET | `/merma` | HTML list + summary + both forms on same page |
| POST | `/merma/registrar` | record single-ingredient waste |
| POST | `/merma/receta` | record whole-batch waste |

### Fields — `/merma/registrar`
| Field | Type | R/O | HTML attr | Server validation |
|---|---|---|---|---|
| `ingredient_id` | select | **R** | `required` | must exist (FK) |
| `qty` | number | **R** | `required step=0.01 min=0.01` | > 0 (DB CHECK) |
| `qty_unit` | select | O | (no required) — JS auto-defaults finer unit | empty → None (uses stock unit) |
| `reason` | select | **R** | `required` | in `WasteReason` enum else 400 Spanish |
| `notes` | textarea | O | no maxlength | empty → None |

### Fields — `/merma/receta`
| Field | Type | R/O | HTML attr | Server validation |
|---|---|---|---|---|
| `recipe_id` | select | **R** | `required` | must exist + have yield_qty |
| `batch_qty` | number | **R** | `required step=0.01 min=0.01` | > 0 (router check) |
| `reason` | select | **R** | `required` | in `WasteReason` |
| `notes` | textarea | O | no maxlength | empty → None |

### Hidden
- None (everything on page).

### Derived
- `cost_gs` — denormalized at insert time using current `purchase_price_gs`.

### Gaps (Merma)
- ❌ `qty` form has no `max`; same for `batch_qty`.
- ❌ `qty_unit` allows any unit regardless of ingredient's stock unit (e.g., "g" on an "und" ingredient — `record_waste` handles it but silently).
- ❌ `reason` enum is exposed as raw enum values (`vencida`, `rotura`, `error_produccion`, `otro`) in the dropdown — should have human-friendly Spanish labels (e.g., "Vencida" instead of "vencida").
- ❌ `notes` textarea has no maxlength.
- ❌ No photo upload (audit item asked for it; not implemented).
- ❌ No edit/delete of existing waste rows (append-only by design, but no UI to add a corrective entry).
- ❌ `qty_unit` form uses `data-default-for-unit='{"kg":"g","l":"ml"}'` — JS-only, no server enforcement.
- ❌ Page renders BOTH forms on the same GET response; clicking "Cancelar" returns to `/merma` — confusing UX.

### Regression coverage
- `tests/test_merma_receta_and_registrar.py`, `tests/test_waste.py`.

---

## 12. Reposición / Restock — `/reorder`, `/reorder/registrar`, `/reorder/generate-po`

### Routes
| Method | Path | Notes |
|---|---|---|
| GET | `/reorder` | HTML list (per-ingredient restock forms) |
| GET | `/reorder?format=json` | JSON |
| POST | `/reorder/registrar` | record restock (task spec said `/restock` — actual is `/registrar`) |
| POST | `/reorder/generate-po` | bulk WhatsApp link |

### Fields — `restock` row form (`reorder.html:95`)
| Field | Type | R/O | HTML attr | Server validation |
|---|---|---|---|---|
| `ingredient_id` | int (hidden) | **R** | injected | must exist else 404 |
| `qty` | number | **R** | `step=0.5 min=0` | > 0 else 400 |
| `price_gs` | number | **R** | `step=100 min=0` (no max) | ≥ 0 else 400 |
| `notes` | text (hidden) | O | empty | empty → None |

### Fields — `generate-po` bulk form
| Field | Type | R/O | Server validation |
|---|---|---|---|
| `selected` | text (hidden, JS-populated) | O | comma-separated int ids |

### Gaps (Reorder)
- ❌ `qty` allows 0 (`min=0`) — but server requires > 0 → 400 if operator types 0; UX would benefit from `min=0.01`.
- ❌ `price_gs` `min=0` allows free — server allows it; warning only at dashboard.
- ❌ Per-row form lacks a confirm-modal (typo = bad data).
- ❌ `generate-po` does **not** include `price_gs` in the WhatsApp text — supplier sees no prices.
- ❌ No undo / no "edit last restock" surface.
- ❌ `restock` event records `IngredientPriceEvent.source='restock'` but no audit log on ingredient.purchase_price_gs change (only the StockMovement row is logged).

---

## 13. Supplier — `/suppliers`

### Routes
| Method | Path | Form / API |
|---|---|---|
| GET | `/suppliers` | HTML list |
| GET | `/suppliers/nuevo` | HTML form |
| POST | `/suppliers/nuevo` | create |
| GET | `/suppliers/{id}/editar` | HTML form |
| POST | `/suppliers/{id}/editar` | update |
| POST | `/suppliers/{id}/eliminar` | delete (blocked if ingredients linked) |
| GET | `/suppliers/{id}/ordenes` | HTML WhatsApp-ready order text |

### Fields (`supplier_form.html`)
| Field | Type | R/O | HTML attr | Server validation |
|---|---|---|---|---|
| `name` | text | **R** | `required` (no maxlength) | non-empty after `.strip()` |
| `contact_name` | text | O | no maxlength | empty → None |
| `phone` | text | O | no `type=tel`, no `pattern` | empty → None |
| `email` | email | O | `type=email` (browser only) | empty → None; no server format check |
| `address` | textarea | O | no maxlength | empty → None |
| `notes` | textarea | O | no maxlength | empty → None |
| `is_active` | checkbox | **MISSING** | — | `supplier.is_active Boolean default True` — model has it, no form input |
| `created_at` | datetime | C | — | server-stamped |

### Gaps (Supplier)
- ❌ `is_active` (Boolean, default True) not editable from UI — once you stop working with a supplier, you can't deactivate them without deleting and losing the link to historical ingredients.
- ❌ No `maxlength` on any field; model column limits not enforced client-side.
- ❌ `phone` no format validation.
- ❌ `email` no server-side regex check.
- ❌ `/suppliers/{id}/eliminar` returns 400 with Spanish if ingredients linked — but the user might want to **deactivate** instead of delete.
- ❌ No unique constraint on `Supplier.name` — two suppliers with the same name allowed.

### Regression coverage
- `tests/test_suppliers_crud_roundtrip.py`.

---

## 14. User — `/users`

### Routes
| Method | Path | Form / API |
|---|---|---|
| GET | `/users` | HTML list (admin only) |
| POST | `/users/crear` | create (admin only) |
| POST | `/users/{id}/editar` | update (admin only) |
| POST | `/users/{id}/eliminar` | delete (admin only, not self) |
| (no `/users/{id}/role` route) | — | **task spec mentions `/role` — not implemented** |

### Fields (modal forms in `users.html`)
| Field | Type | R/O | HTML attr | Server validation |
|---|---|---|---|---|
| `username` | text | **R** | `required minlength=2 maxlength=120` | unique else flash+redirect |
| `password` | password | **R** | `required minlength=6` (create only) | ≥ 6 chars; bcrypt-12 hashed |
| `role` | select | **R** | `required` | in `VALID_ROLES = ("admin","cashier","manager")` |
| `is_active` | checkbox | O | (only on edit form) | sent as `value=true` if checked |
| `new_password` | password | O | `minlength=6` (edit only) | ≥ 6 chars if provided |
| `user_id` (hidden) | int | R on edit/delete | injected | must exist |

### Gaps (User)
- ❌ `/users/{id}/role` (task spec) does not exist. Role is updated via `/users/{id}/editar`.
- ❌ `is_active` checkbox on edit form has `value="true"` but server reads `is_active: bool = Form(False)` — **boolean coercion of "true"/"false" string is form-handler-dependent; FastAPI will pass `"true"` as a truthy string**; the `bool` type coerces `"true"` to True only because FastAPI's Form does so. Subtle and undocumented.
- ❌ No "reset password" flow (admin can't force a password reset for an admin-locked-out user other than via the edit form).
- ❌ No email field on User model — username IS the identifier (no password-recovery by email).
- ❌ No "last login at" display (column exists, hidden in list).
- ❌ `users_create` audit detail includes `username` (PII) — minor.

### Regression coverage
- `tests/test_k7_users_admin_enforcement.py` — admin-only.
- `tests/test_auth.py`, `tests/test_auth_login_logout.py`, `tests/test_auth_integration.py`, `tests/test_auth_supabase.py`.

---

## 15. Settings — `/settings`

### Routes
| Method | Path | Notes |
|---|---|---|
| GET | `/settings` | HTML page with 3 tabs |
| POST | `/settings/business` | save business info |
| POST | `/settings/fiscal` | save fiscal info |
| POST | `/settings/theme` | save theme pref |
| (no `/settings/{key}` generic route) | — | **task spec mentions `/settings/{key}` — not implemented** |

### Fields
| Field | Type | R/O | HTML attr | Server validation |
|---|---|---|---|---|
| `business_name` | text | **R** | `required` | stored in `app_meta` (no validation beyond exists) |
| `business_ruc` | text | O | `pattern=[0-9-]+` (browser only) | empty → empty string in DB |
| `business_address` | textarea | O | no maxlength | empty → empty |
| `business_phone` | tel | O | `type=tel` (browser only) | empty → empty |
| `timbrado` | text | **R** | `required` | no format check |
| `punto_expedicion` | text | **R** | `required` | no format check |
| `invoice_sequence` | number | **R** | `required min=1` | must be int ≥ 1 |
| `theme` | radio | **R** | `light`/`dark`/`system` | in `["light","dark","system"]` else 422; **Spanish error message says "Invalid theme value" in English** |

### Stored where
- `app_meta` table — key/value pairs.

### Gaps (Settings)
- ❌ `/settings/{key}` generic route missing.
- ❌ `theme` 422 error message is in **English**: "Invalid theme value" (rest of the app is Spanish).
- ❌ `business_ruc` `pattern` only allows digits and hyphens — but real RUCs in Paraguay have varied formats ("123-456789-1", "80012345-6", etc.). Server-side no validation.
- ❌ `timbrado` format "001-123456789-001" — no server regex.
- ❌ `invoice_sequence` allowed to be set to any number (no monotonic enforcement — could regress to a duplicate invoice number).
- ❌ No "current value" preview of the saved state in success flash.
- ❌ No write to `app_meta.updated_at` is actually a real timestamp (it's `"now"` literal string in some code paths — see `settings.py:94`, `:129`, `:165` — should be `datetime.utcnow().isoformat()`).
- ❌ Setting persistence is silent (no error if DB write fails).

### Regression coverage
- `tests/test_settings.py`, `tests/test_settings_roundtrip.py`, `tests/test_settings_ui.py`.

---

## 16. Audit — `/auditoria`, `/auditoria/prune`

### Routes
| Method | Path | Notes |
|---|---|---|
| GET | `/auditoria` | HTML list, paginated (50/page), with many filters |
| POST | `/auditoria/prune` | delete entries older than N days |
| (no `/auditoria/{id}`) | — | task spec mentioned `/auditoria/{id}` — not implemented (and shouldn't be, audit is append-only) |

### Fields — `/auditoria/prune`
| Field | Type | R/O | Server validation |
|---|---|---|---|
| `older_than_days` | int (query) | O (default 365) | 1 ≤ N ≤ 3650 |

### Filters — `/auditoria` GET (read-only, query params)
- `page`, `limit`, `action_filter`, `start_date`, `end_date`, `ip_filter`, `user_filter`, `target_type`, `target_id`.

### Gaps (Audit)
- ❌ `/auditoria/{id}` route missing (intentional? — append-only).
- ❌ `/auditoria/prune` form's `older_than_days` is a Query param (not Form) — but template uses POST. Works because of FastAPI, but semantically odd.
- ❌ No "export CSV" for audit log (would be huge but still useful for compliance).
- ❌ IP filter does substring match (`ip_filter in r.ip`) — too lax for IPv6.

---

## 17. Sale — `/ventas`

### Routes
| Method | Path | Form / API |
|---|---|---|
| GET | `/ventas` | HTML list + form |
| GET | `/ventas/export.csv` | CSV |
| GET | `/ventas/buscar?sku=...` | JSON SKU lookup |
| POST | `/ventas/nueva` | create sale + apply_sale() |
| GET | `/ventas/{id}/recibo` | HTML printable receipt |
| POST | `/ventas/{id}/anular` | void |
| (no `/ventas/{id}` standalone) | — | receipt is the only per-sale HTML view |

### Fields — `POST /ventas/nueva`
| Field | Type | R/O | HTML attr | Server validation |
|---|---|---|---|---|
| `product_id` | int (hidden on quick-sell; select on main form) | **R** if no SKU | (no required attr on select; default `Form(None, gt=0)`) | must exist; resolved via SKU if SKU given |
| `sku` | text | O | `pattern=[A-Za-z0-9\-_]+` (browser) | empty → None; resolved via `get_product_by_sku` |
| `qty` | number | **R** | `required step=0.01 min=0.01` | > 0; ≤ MAX_QTY=1_000_000 else 422 |
| `sold_at` | datetime-local | O | no `required` | empty → now in Asuncion TZ; else `datetime.fromisoformat()` |
| `customer_id` | int (hidden, picker) | O | `Form(None, gt=0)` | must exist else 422 |
| `channel` | select | O | default `mostrador` | in `ALLOWED_CHANNELS` else 400 Spanish |
| `payment_method` | select | O | empty default | in `ALLOWED_PAYMENT_METHODS` else 400 Spanish |
| `discount_gs` | number | O | `min=0 value=0 step=100` | 0-100_000_000 else 422 |
| `notes` | textarea | O | no maxlength | empty → None |

### Quick-sell (one-tap)
| Field | R/O | Server validation |
|---|---|---|
| `product_id` (hidden) | **R** | same as main form |
| `qty` (hidden, default=1) | **R** | same |

### Hidden
- `discount_gs` default 0 (form).

### Derived
- `unit_price_gs` — snapshot from product at insert time (NOT form-submitted).
- `total_gs` — `qty * unit_price_gs - discount_gs`.
- `tz` — server default `"America/Asuncion"`.
- `voided_at` — set by `/anular` POST.

### Gaps (Sale)
- ❌ `notes` textarea has no maxlength.
- ❌ `discount_gs` max is server-side 100M Gs. (browser `min=0`, no `max`).
- ❌ `sold_at` accepts ISO-local datetime but no `max` (future dates allowed — could be a sale registered for tomorrow).
- ❌ `customer_id` is a hidden input — if picker JS doesn't update it, the value is `None` silently (no required).
- ❌ `channel` and `payment_method` allow empty (good — defaults to `mostrador`/`None`).
- ❌ `/ventas/{id}/anular` POST has no required reason — operator can void without explanation.
- ❌ Rate-limited (10/min) but no UI feedback when 429 hits (flash not handled).
- ❌ Quick-sell button uses inline `onsubmit="this.querySelector('button').disabled=true"` — bypassable by removing JS attribute.
- ❌ No idempotency token on POST — double-click could create duplicate sales (browsers can be fast).
- ❌ Sale printer (`_fire_printer_for_sale`) silently fails (best-effort) — no UI indicator.
- ❌ CSV export includes `telefono_cliente` (PII) without warning.

### Regression coverage
- `tests/test_sales_overhaul.py`, `tests/test_sale_timezone_field.py`, `tests/test_sale_via_sku.py`.
- `tests/test_sale_channel.py`, `tests/test_void_sale.py`, `tests/test_void_semantics.py`.
- `tests/test_payment_methods.py`, `tests/test_k1_ventas_no_template_error.py`.

---

## 18. Excel import / export — `/excel/...`

### Routes
| Method | Path | Form / API |
|---|---|---|
| GET | `/excel` | HTML import/export page |
| GET | `/excel/mode-guidance` | HTML help |
| POST | `/excel/validar` | dry-run |
| POST | `/excel/importar` | actual import |
| GET | `/excel/exportar` | xlsx download |
| GET | `/excel/plantilla` | xlsx plantilla download |

### Fields — `POST /excel/importar` and `POST /excel/validar`
| Field | Type | R/O | HTML attr | Server validation |
|---|---|---|---|---|
| `file` | file | **R** | `accept=.xlsx required` | must end `.xlsx`; non-empty; else 400 Spanish |
| `mode` | radio | **R** | `PATCH` (default) / `APPEND` / `FULL` | in `VALID_MODES` else 422 |

### Gaps (Excel)
- ❌ No max file size check on upload — large `.xlsx` could OOM the server.
- ❌ `mode` `FULL` is documented as "Reemplazar todo" but code says "Añade filas del archivo SIN pisar las anteriores" — UI text vs docstring disagreement.
- ❌ Dry-run `/validar` opens in a new tab (`target="_blank"`) but uses `id="validate-form"` with hidden file input — clicking "Vista previa" doesn't actually submit the **visible** form's file (it submits a hidden empty form).
- ❌ No progress bar for large imports.
- ❌ No record of which rows failed (only counts).
- ❌ No "undo last import" surface.
- ❌ `mode=FULL` actually behaves like `APPEND` per the guidance HTML — terminology drift.

### Regression coverage
- `tests/test_excel_import_full_flow.py`, `tests/test_excel_patch.py`, `tests/test_import_roundtrip.py`.
- `tests/test_xlsx_fixtures.py`, `tests/test_lazy_openpyxl.py`.

---

## 19. Backup — `/backup/...`

### **NO HTTP ROUTES.** The task spec lists `/backup`, `/backup/{filename}/restore`, `/backup/{filename}/delete` — none of these exist.

- `app/rms/backup.py` is a service module (CLI helpers).
- `app/services/backup_scheduler.py` runs backups on app startup (writes `.xlsx` to `~/Documents/aiw-restaurant/backups/`).
- `app/scripts/backup.py` is a CLI tool.
- `tests/test_backup.py`, `tests/test_r2_backup.py`, `tests/test_backup_pre_mutate.py`, `tests/test_backup_cron.py` exist but test the service layer.

### Gaps (Backup)
- ❌ **NO UI for backups at all.** Operators can't trigger a manual backup or restore from the UI.
- ❌ No way to upload a backup file to restore from within the app.
- ❌ No "backup status" / "last backup time" widget on `/ops/status`.

---

## Summary — Priority Gaps (ordered by impact)

### 🔴 Critical (operational risk)
1. **`eod.html:22` posts to `/eod/check` — route does not exist.** The "Guardar cierre" button silently 404s. The EOD checklist UI is fully non-functional.
2. **CSRF hidden-input mismatch in `_components/confirm_modal.html`.** Looks for `input[name="_csrf_token"]` but `csrf.py` uses `csrf_token`. Modal-spawned forms don't carry the field that the modal tries to copy — broken defense in depth (the cookie check still passes, but the code is dead and future regressions would slip).
3. **`/backup/...` HTTP routes missing entirely.** Task spec lists them; only CLI / scheduler exists. No UI to restore from a user-uploaded backup.
4. **`/recetas/{id}/eliminar` doesn't exist** — no way to delete a recipe from the UI. Task spec lists it.
5. **`/pedidos/{id}/cancelar` and `/pedidos/{id}/cambiar-estado` not separate routes** — only `/status` works. UI uses correct path; task spec is wrong but worth flagging.
6. **`/users/{id}/role` doesn't exist** — task spec lists it; only `/users/{id}/editar` covers it.
7. **`/settings/{key}` doesn't exist** — task spec lists it; only `/business`, `/fiscal`, `/theme` exist.
8. **Silent FK validation gaps** — `recipe_id` (in `producto_form`), `customer_id` (in `pedido`), etc. accept any int → IntegrityError → 500 instead of friendly 400.

### 🟠 High (data integrity)
9. **Model ↔ form drift on `Product`**: `tags` column never editable.
10. **Model ↔ form drift on `Ingredient`**: `supplier_id`, `subcategory`, `role`, `allergens`, `dietary_tags`, `shelf_life_days`, `max_stock_qty`, `lead_time_days` all in model, no UI.
11. **Model ↔ form drift on `Supplier`**: `is_active` column never editable.
12. **Model ↔ form drift on `Recipe`**: `difficulty` column never editable.
13. **Sale form has no idempotency token** — double-click can create duplicate sales.
14. **`sale/anular` accepts no reason** — no audit trail of why a sale was voided (only the void timestamp on Sale).
15. **Server stores `pedido.channel` as raw string** ("wsp", "WhatsApp") — UI normalizes but CSV/DB see mixed casing.
16. **Inventory adjust modal allows unbounded `adjustment`** — no `max` cap, only client-side warning.

### 🟡 Medium (validation/UX gaps)
17. **No `maxlength` on `notes` textareas** across products, recipes, ingredients, sales, merma, customers.
18. **No `max` on `qty` / `batch_qty` / `discount_gs` / `qty_to_produce`** — operator can type 1B.
19. **`purchase_price_gs` form `step=1` but server accepts decimals** — UX mismatch.
20. **No phone/email format validation server-side** for Customer, Supplier — only browser `type=email`/`type=tel` (bypassable via curl).
21. **`timbrado` / `business_ruc` no server regex** — only browser `pattern`.
22. **`invoice_sequence` no monotonic check** — could regress to duplicate invoice numbers.
23. **`opening_stock_date` stored as Text** — DB column type doesn't match semantic (Date).
24. **`pedido_line_unit_price_gs` accepts 0 silently** → server snapshots product price — UX would benefit from "0 = use current price" label.
25. **Merma `qty_unit` server accepts any unit** regardless of ingredient's stock unit.
26. **Recipe `line_unit` silently falls back to ""** on bad value — no Spanish error.
27. **Recipe form on update replaces ALL lines** — silent line deletion; no "delete recipe" capability (no DELETE route).
28. **Settings 422 error message in English** ("Invalid theme value").
29. **`app_meta.updated_at` literal "now" string** in 3 places instead of ISO timestamp.
30. **`Pedido.duplicate` is a GET** — state-mutating GET antipattern.
31. **No file size limit on `/excel/importar` upload** — OOM risk.

### 🟢 Low (polish)
32. **`/ventas/{id}` standalone HTML view missing** — only `/recibo` exists.
33. **No `/auditoria/{id}` view** — acceptable since append-only.
34. **No `/auditoria` CSV export** for compliance.
35. **No undo / edit for waste, initial stock, or restock** — append-only by design but no corrective surface.
36. **Sale's `discount_gs` browser has no `max`** — server enforces 100M but UX doesn't.
37. **`/ventas/{id}/anular` POST is not idempotent** — double-click could double-void (server-side likely safe due to state machine, but UI doesn't prevent).
38. **Merma page renders BOTH forms on GET** — `/merma` returns HTML with the create forms inline; not RESTful.
39. **Supplier `name` no uniqueness** — duplicate supplier names allowed.
40. **`customer.name` server substitutes `"(sin nombre)"` on empty** despite form `required` — inconsistent.

### Notable hidden-field inventory (form has no CSRF input anywhere)
Every form relies on the cookie check. The middleware verifies cookie presence + signature only — same-origin defense via `SameSite=lax`. **No form in the codebase renders `<input name="csrf_token">`.** This is intentional per the design, but the confirm-modal code path (`_components/confirm_modal.html`) tries to find a non-existent field. Either:
- (a) Remove the dead CSRF-input copy code from confirm_modal.html, OR
- (b) Add `csrf_token` hidden inputs to all forms (would require coordinated change to csrf.py middleware to compare form field to cookie).

---

## Quick regression-coverage matrix

| Resource | Round-trip test | Filter/list test | Validation test | A11y test |
|---|---|---|---|---|
| Producto | ✅ `test_products_crud_roundtrip.py` | ✅ `test_productos_filter.py` | partial (csrf_on_forms) | partial |
| Ingredient | ✅ via `test_p1_route_coverage.py` | ❌ | partial | partial |
| StockMovement | ✅ `test_inventory_adjust_atomicity.py` | n/a | n/a | n/a |
| Recipe | ✅ `test_recipes_polymorphic_roundtrip.py` | ❌ (q/ingredient filter exists) | partial | partial |
| RecipeLine | ✅ covered in recipe tests | n/a | n/a | n/a |
| Cliente | ✅ `test_clientes_crud_roundtrip.py` | ✅ `test_clientes_filter.py` | partial | partial |
| Pedido | ✅ `test_pedidos.py` | ❌ | ✅ `test_pedidos_fulfill_atomicity.py` | partial |
| ProdTemplate | ✅ `test_pro_01_weekly_plan.py` | n/a | partial | partial |
| ProdOverride | ✅ `test_produccion_override.py` | n/a | partial | partial |
| EOD completion | ✅ `test_eod_completion.py` | n/a | ✅ `test_eod_idempotency.py` | partial |
| Merma | ✅ `test_merma_receta_and_registrar.py` | partial | partial | partial |
| Reorder | ✅ `test_reorder_suggestions.py`, `test_reorder_restock.py` | partial | partial | partial |
| Supplier | ✅ `test_suppliers_crud_roundtrip.py` | ❌ | partial | partial |
| User | partial (admin enforcement `test_k7_users_admin_enforcement.py`) | n/a | partial | partial |
| Settings | ✅ `test_settings_roundtrip.py` | n/a | partial | partial |
| Audit | ✅ `test_audit_log.py`, `test_audit_prune.py` | ✅ `test_auditoria_filters.py` | partial | partial |
| Sale | ✅ `test_sales_overhaul.py` | partial | ✅ `test_sale_via_sku.py`, `test_void_*` | partial |
| Excel | ✅ `test_excel_import_full_flow.py` | n/a | partial | partial |
| Backup | ✅ service-layer only (no HTTP routes) | n/a | ✅ `test_backup_pre_mutate.py` | n/a |

---

## File inventory of "form-field" findings (highlights)

- `app/templates/producto_form.html` — missing `tags`, no CSRF, no `notes` maxlength.
- `app/templates/inventario_form.html` — 7 model columns missing from UI, `opening_stock_date` stored as Text.
- `app/templates/receta_form.html` — `difficulty` missing, no `max` on prep/cook minutes, no DELETE route.
- `app/templates/cliente_editar.html` — `loyalty_points` not editable, server-substitutes empty name silently.
- `app/templates/pedidos_nuevo.html` — `payment_intent` not validated server-side, `customer_phone` no format check.
- `app/templates/ventas.html` — no idempotency, no max on `qty`/`discount_gs`, no reason for void.
- `app/templates/merma.html` — no max on qty, raw enum values shown to user.
- `app/templates/reorder.html` — `qty` allows 0 client-side (server rejects), `price_gs` no max.
- `app/templates/supplier_form.html` — `is_active` missing.
- `app/templates/users.html` — `/role` route missing.
- `app/templates/settings.html` — English 422 error, `app_meta.updated_at` literal "now".
- `app/templates/auditoria.html` — `/prune` works, no CSV export.
- `app/templates/eod.html` — **`/eod/check` route missing** (dead form).
- `app/templates/_components/confirm_modal.html` — **CSRF input name mismatch** (`_csrf_token` vs `csrf_token`).
- `app/templates/excel.html` — `validate-form` uses hidden empty file input.

End of report.
