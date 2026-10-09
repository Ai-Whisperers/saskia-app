# Repository deep audit — all 9 competitors vs Sazon (2026-10-08)

A full deep read of every cloned competitor's architecture, pages,
logic, and pages pattern — plus synthesis, takeaways, and a
roadmap of what Sazon should change vs what should stay.

---

## Part 1 — Repository inventory at a glance

| # | Repo | ⭐ | Stack | Production relevant? | Cloned? |
|---|---|---|---|---|---|
| 1 | tastyigniter/TastyIgniter | 3,775 | PHP/Laravel | ⚠️ middleware, no baking plan | partly |
| 2 | enatega/food-delivery-multivendor | 1,387 | TS/Mongo/Mobile | ❌ (multi-vendor delivery) | README only |
| 3 | pizzaql/pizzaql | 715 | Next/GraphQL/Prisma | ⚠️ order-only | ✓ |
| 4 | evan361425/flutter-pos-system | 619 | Flutter/Dart | ✓ inventory + analysis | ✓ |
| 5 | ury-erp/ury | 382 | Frappe+Vue+KDS | ✓ mosaic KDS | ✓ |
| 6 | harismuneer/RMS (DineOut) | 346 | Android/Java | ⚠️ Android teaching project | ✓ |
| 7 | FreeOpenSourcePOS/FloCafe | 129 | Electron+Express+Next | ✓ KDS + offline-first | ✓ |
| 8 | faizaldevs/RestoPOS | 104 | Laravel+Vue+MariaDB | ✓ KOT + recipes | ✓ |
| 9 | karanshukla/openresto | 96 | ASP.NET 10 + Expo + SQLite | ⚠️ booking, not baking | ✓ |
| 10 | olasunkanmi-SE/restaurant (resto-nestjs) | 242 | NestJS+React | ❌ narrow DDD teach | ✓ |

Sazon is the local-first bake-day planner among 10 SaaS/POS-style
competitors. Three "bakery-adjacent" competitors (FloCafe, RestoPOS,
URY) are the relevant ones; four (pizzaql, flutter-pos, harismuneer,
resto-nestjs) have partial patterns; three (tastyigniter, openresto,
enatega) are out of domain.

---

## Part 2 — Per-repo deep architecture read

### 2.1 FloCafe (`/clones/FloCafe`) — Electron + Express + Next + SQLite

**Top-level layout**: `main/` (Express + Electron server) + `frontend/` (Next.js) + `tests/` (vitest) + `docs/` + `shared/`. Electron multi-server: `main/server.ts:3001` (API), `main/kds-server.ts:3002` (KDS-only), `main/server-app.ts:3003` (companion). All share one SQLite file via `main/db.ts`.

**Route surface (from routes barrel, production-relevant subset):**

```
GET  /api/kitchen/orders           kitchen.ts:23     (live KOT)
PATCH /api/kitchen/items/:id/status kitchen.ts        (advance KOT)
GET  /api/kitchen/sse             kds-server.ts       (real-time push)
GET  /api/recipes/product/:id     recipes.ts:23       (BOM read)
PUT  /api/recipes/product/:id     recipes.ts:32       (BOM write)
GET  /api/supplies                supplies.ts         (stock view)
POST /api/supplies/adjust         supplies.ts         (manual delta)
GET  /api/printers                printers.ts         (ESC/POS config)
POST /api/print/kot/:id           print/              (auto-print on KOT)
```

**Page surface (from frontend pages):**
- `kds.tsx` (live board)
- `orders.tsx` (register)
- `menu-products.tsx` (catalog)
- `menu-recipes.tsx` (BOM editor)
- `inventory.tsx`
- `reports.tsx` (sales + usage)
- `printers.tsx`

**The 5 patterns that matter for Sazon** (from existing audit on disk):
1. **KOT advance via PATCH** (`status: pending → preparing → ready → served`). Sazon's `/produccion` writes a single `completed_qty` at end-of-shift; FloCafe lets a cook bump per row in real time — closer to a baking-min-by-min tablet view.
2. **Multiple printers auto-select on KOT** via `kot_printer` field per kitchen station. Sazon has thermal printing but only for production worksheet + receipts (`print_export.py`).
3. **Recipe-to-product 1:1** (`recipes.product_id`) with explicit yield — same model as Sazon. No multi-level BOM by default.
4. **Station routing**: a kitchen user sees only the categories they own (`getUserKdsStationIds`). Sazon has no stations.
5. **Maintenance mode** middleware can drain KDS without losing data (`db.ts:23-35`). Sazon's EOD uses a different model.

**What's missing from FloCafe** (and Sazon has): production planning (no daily forecast), no merma/scraps path, no accuracy feedback loop, no multi-week templates.

---

### 2.2 OpenResto (`/clones/openresto`) — ASP.NET 10 + Expo + SQLite

**Top-level layout**: `OpenRestoApi.Domain` (entities) + `OpenRestoApi.Core` (services) + `OpenRestoApi.Infrastructure` (EF Core + repos) + `OpenRestoApi` (controllers) + `openresto-frontend` (Expo mobile) + `openresto-cli` + multi-arch `nginx-vps/`.

**Architecture** (from prior audit): Clean architecture, JWT in HttpOnly cookies. NOT a POS — it's a booking platform. The relevant patterns are resource allocation, time-bucketed planning.

**Routing surface** (production-relevant):
```
POST /api/bookings              (turn-times computed from party size)
GET  /api/bookings/{id}         (assigns table via TableAutoAssigner)
POST /api/holds/{id}            (creates chronological hold)
GET  /api/coverpacing           (real-time capacity gauge)
GET  /api/turntimes             (per-seats duration rules)
```

**Mobile page surface** (Expo Router):
- `/admin/dashboard` (cover pacing widget)
- `/admin/calendar` (time grid)
- `/admin/settings/restaurant` (turn time + covers per slot)
- `/admin/settings/users`

**The 4 patterns OpenResto is actually good at:**
1. **`TurnTimesHelper`** (TurnTime config: min_seats→minutes) is the cleanest "capacity per time" object in the bunch. Bakable parallel: "1 product → batch_minutes per oven".
2. **`TableAutoAssigner.BuildCandidatesAsync`** sorts candidates by smallest-fitting-first, then by deprioritization tier, then by ID. Sazon's `produce_plan_production()` could borrow this for allocating dough to ovens across shifts, if you ever add multi-oven capacity.
3. **Cover pacing** — time-bucketed live count visible on dashboard (`MaxCoversPerSlot`). Sazon's `/produccion` grilla has DEMANDA per product, but not per hour.
4. **PauseHelper** — operator can close the day at 14:00 to stop new orders; Sazon's EOD does this too (`/eod`).

**What's missing**: production plan, recipes, ingredients, BOM, costing, costs-of-goods, POS. The Domain layer is rich, the entity layer has `Booking`/`Table`/`Hold`, no `Ingredient`/`Recipe`/`Product`/`Production`.

---

### 2.3 URY (`/clones/ury`) — Frappe+Vue+KDS, 45 doctypes

**Top-level**: `ury/` (Frappe app — 45 doctypes in `ury/ury/doctype/`), `mosaic/` (Vue KDS), `pos/` (`ury_pos/` — restaurant POS), `self-order/`, `frontend/`, `packages/`, `scripts/`.

**Production-relevant doctypes** (already inventoried):
```
ury_production_item_groups       (child of ury_production_unit, links to Item Group)
ury_production_unit              (KDS display config: printer, branch, warehouse, 
                                  order-type-wise display, order_type)
ury_kot                          (Kitchen Order Ticket master)
ury_kot_items                    (KOT line items)
ury_kot_error_log                (KOT print failures)
ury_materials                    (raw materials — separate from Items?)
ury_pos_checklist_log            (compliance log)
ury_checklist_item               (checklist definitions)
ury_checklist_log_item           (per-day checklist runs)
ury_daily_p_and_l                (auto daily P&L)
ury_p_and_l_breakup              (P&L breakdown)
ury_p_and_l_materials            (P&L by material)
ury_cost_of_goods               (COGS by item)
ury_notification_recipient       (real-time alert targets)
ury_printer_settings             (ESC/POS)
ury_table                        (restaurant tables)
ury_room                         (room/zone)
ury_order                        (customer order)
ury_order_item                   (line item)
ury_menu                         (menu group)
ury_menu_course                  (course)
ury_menu_item                    (menu item + recipe?)
ury_payment_terminal             (card terminal config)
ury_payment_terminal_transaction (transaction log)
ury_self_ordering_profile        (kiosk config)
ury_ordering_device              (kiosk device)
ury_ordering_session             (kiosk session)
```

**The big surprise from the URY model**: production here means "kitchen display configuration", NOT "bake plan". They have no recipe/BOM doctype, no ingredient deduction model, no daily-batch forecast.

URY's "pre-billing checklist" model is the standout:
```
ury_pos_checklist_log        (one row per shift/day, completed_at)
ury_checklist_item           (item def: name, required, order, type)
ury_checklist_log_item       (run entry: id, log_id, item_id, completed_at,
                              completed_by, value)
```
This is exactly what Sazon's HACCP/well-formed-close lacks. The pattern translates 1:1 to Sazon's operator UX.

**Pages** (Frappe listview/formview auto-generated per doctype, plus custom `ury/ury/page/`):
- `ury_mosaic/` Vue KDS standalone (`mosaic/src/views/Home.vue` — single screen)
- `ury_pos/pos.html` — POS register
- `ury/ury/page/dashboard/` — operations dashboard
- `ury/ury/page/menu_builder/` — menu editor
- `ury/ury/page/chart_of_accounts/` — accounting

**Standout patterns for Sazon**:
1. **POS checklist per shift** — `ury_pos_checklist_log` enforced before submit. Sazon has `eod` but no checklist gating.
2. **KOT error log** = real production observability. Sazon has no printer-error path.
3. **Daily P&L auto-rollup** = purely from movements. Sazon has the data (`stock_movement` + `sale`), just doesn't shape it.
4. **Mosaic (Vue)** as a standalone KDS app — proven separation from POS.

---

### 2.4 RestoPOS (`/clones/RestoPOS`) — Laravel + Vue + MariaDB

**Top-level**: `app/` (Laravel 11.x), `routes/` (117 tenant routes), `database/migrations/`, `docker-compose.yml`, `azure-pipelines.yml`, `nginx.conf`. KOT + recipe consumption + multi-payment + multi-location.

**Models (40+)** include:
```
Account, Consumption_item, Customer, CustomerGroup, Discount, Employee,
EmployeeAttendance, EmployeeCategory, EmployeeSalary, Expense,
ExpenseCategory, Food, FoodBrand, FoodCategory, Kitchen, Location, Modifier,
Point, Product, ProductBrand, ProductCategory, Purchase, PurchaseItem,
PurchasePayment, PurchaseReturn, Register, Sale, SalePayment, SaleItem,
Setting, Stock, StockTransfer, Supplier, Table, Tax, User, Variant, …
```

**Route surface (118 routes on `routes/tenant.php`)** — production-relevant subset:

```
# KOT auto-print
POST /kot/direct/print/{order_id}/{type}    "KOT path: 'new'/'duplicate'"
# Recipe consumption (matches your "recipe-driven stock deduction")
POST /consumption/complete                  "complete consumption"
GET  /consumption/get/{consumption_id}      "view a consumption"
GET  /consumption/product/get/{consumption_id}  "what's in a consumption"
GET  /consumption/material/get/{material_id}    "what a material costs"
GET  /food/ingredient/get/{product_id}      "ingredients of a product"
# Report paths (RestoPOS has reports, not insights)
GET  /report/kitchen/order                  "KOT report"
GET  /report/product/consumption            "auto-deduct usage"
GET  /report/food/category                  "sales by category"
GET  /report/account
GET  /report/gst                            "GST (tax) breakdown"
# POS
GET  /pos/open, /pos/close                  "register open/close"
POST /pos/addsale                           "add sale"
GET  /pos/check/registers                   "which register has cash"
# Purchase
GET  /purchase/filter, /purchase/payment
POST /purchase/product/add
```

**Pages (`frontend/src/views/`, Vue 2 + AdminLTE)** include:
- `pos/checkout.vue` — POS cart screen
- `kitchen/order.vue` — KOT monitor
- `kitchen/management.vue` — KOT management
- `report/kitchen-order.vue`
- `report/product-consumption.vue`
- `inventory/list.vue`
- `recipe/list.vue` + `recipe/edit.vue`

**Standout patterns**:
1. **Recipe Consumption is split from Sale**: `consumption/complete` writes the consumption record independently. Sazon does it inside `apply_sale` (rule 8).
2. **Multi-location pivot** (`food.locations()` is `belongsToMany(Location)` with `withPivot('quantity','supplier_id')`). The pivot carries per-location stock — close to Sazon's `Ingredient.stock_qty` but per location.
3. **KOT type** parameter (`'new'` vs `'duplicate'`) lets you re-fire the same KOT to a backup printer. Sazon's KOT path is invisible (print_export.py).
4. **42 report types** via separate routes vs Sazon's handful of `reportes/*` pages.
5. **Table ordering flow** — every sale has a `table_id`. Sazon doesn't track tables (counter-only).

---

### 2.5 PizzaQL (`/clones/pizzaql`) — Next + GraphQL + Prisma

**Top-level**: `backend/src/index.js` (one file), `frontend/pages/` + `components/`. Older (~2019), uses `graphql-yoga` + Nexus + Prisma 2.

**Backend schema**: ONE `Order` type with `id, status, paid, price, size, dough, type, name, phone, time, city, street`. That's it — no product, no recipe, no stock. It's a tiny proof-of-concept.

**Pages**:
- `index.js` — order form for customers
- `admin.js` — dashboard (CreateOrder + Orders list)
- `order.js` — order lookup by ID
- `authorize.js`, `logout.js`, `privacy.js`, `tos.js`, `_app.js`, `_document.js`

**What it teaches**: GraphQL Subscriptions is on the TODO list ("WIP" in README). Order Placement uses `react-hook-form`. Pizza-size / dough as separate fields on the Order — Sazon variants could be modeled the same way (ProductVariant.pack_size, ProductVariant.dough).

**Not relevant to Sazon's production-path** — wrong domain. Listed for completeness as a comparison to the cut-down variant model and as the only repo using GraphQL Subscriptions for live order updates.

---

### 2.6 Flutter POS (`/clones/flutter-pos-system`) — Flutter 3 + Dart 3 (offline-first)

**Top-level**: `lib/ui/` (15+ screens) + `lib/models/` + `lib/services/` + `lib/routes.dart`. **Offline-first** (Hive box per type), no remote backend at all.

**UI screens** (the model architecture is the punchline — clean offline-first pubsub):
```
ui/
├── menu/                 (product + ingredients UI)
│   ├── menu_page.dart
│   ├── product_page.dart
│   ├── product_ingredient_view.dart    (BOM read view)
│   └── widgets/
│       ├── menu_product_list.dart
│       ├── menu_catalog_list.dart
│       ├── product_ingredient_reorder.dart  (drag-and-drop reorder)
│       ├── product_modal.dart           (edit modal)
│       └── product_reorder.dart
├── stock/                (stock UI)
│   ├── stock_view.dart
│   ├── quantities_page.dart
│   ├── replenishment_page.dart
│   └── widgets/
│       ├── stock_ingredient_list_tile.dart
│       ├── stock_quantity_modal.dart
│       ├── replenishment_modal.dart
│       └── replenishment_apply.dart
├── order_attr/           (variant UI)
│   ├── order_attribute_page.dart
│   └── widgets/...
├── analysis/             (charts + history)
│   ├── analysis_view.dart
│   ├── history_page.dart
│   └── widgets/
│       ├── chart_card_view.dart
│       ├── history_calendar_view.dart
│       ├── history_order_list.dart
│       ├── chart_reorder.dart
│       └── reloadable_card.dart
├── order/checkout/       (cart + checkout)
│   ├── stashed_order_list_view.dart
└── printer/              (ESC/POS thermal)
    ├── printer_page.dart
    ├── printer_settings_modal.dart
    └── widgets/
        ├── printer_view.dart
        ├── receipt_template_modal.dart
        └── receipt_component_modal.dart
```

**Plus extras**: `image_gallery_page.dart`, `settings/`, `l10n/` (i18n).

**The pattern that matters for Sazon**:
1. **One widget per "view" per "feature"** with a `page.dart` + `widgets/`. Sazon's `/produccion` template is monolithic (2366 lines). The Flutter split = `production_demand.py`, `production_completion_form.dart`, `production_table_view.dart`, `production_filters.dart`, etc. That refactor is baked into Sazon's mental model.
2. **`reloadable_card.dart`** — every metric card reloads on demand. Sazon's `/` is a single SSR page; the operator has no "pull to refresh".
3. **drag-and-drop reorder** for both products and chart cards (`product_ingredient_reorder.dart`, `chart_reorder.dart`). Sazon's `produccion.html` grilla has column sort but no row reorder — hard for cook to put "my top 5 today" at the top.

---

### 2.7 DineOut / harismuneer (`/clones/Restaurant-Management-System`) — Android Java + Firebase

**Top-level**: `app/src/main/java/com/dineout/code/{billing,kitchen,hall,order,admin,reporting}`. Standard Android + Firebase.

**Activities** (the user-RBAC split is the only thing to learn):
```
billing/         DishPrice, OrderBill, Feedback, BillAdapter, ConfirmPayment,
                 PendingPayments, DishOrder, OrdersAdapter
kitchen/         MainActivity, CooksListActivity, AttendanceActivity
                 + models/ Order, Chef, ChefQueue, EmployeeDb, OrderDetailsDb
hall/            Tracking, DishAdapter, Adapter
                 + DB/ Inventory, Item, Assignment, Receipt, MenuItems,
                       MenuItem, Order
order/           MainActivity, Inventory, Item, MenuItem, Order, Menu,
                 OrderDetails, cart, cartListView, quantityInvalidPrompt
admin/           AdminPanelActivity, AddEmployeeActivity, AddMenuItemActivity,
                 AddTabletActivity, EndOfWeekActivitiy, Tablet, Item, Menu,
                 MenuItem, IngredientsListAdapter
reporting/       Main_Activity, NestedTable, EndOfDay_EventHandler, GMailSender,
                 order, JSSEProvider
                 + EmailSender/
```

**5 user roles** (from README): Customer, Head Chef/Kitchen Manager, Chef, Admin, Hall Manager. Each has its own Activity tree.

**The pattern to learn**: chef queue as a model — `ChefQueue` + `Order` + `Chef` models. Sazon's `production_demand.py` is shift-aware (AM/PM badge) but doesn't assign to a baker. If you ever go multi-baker, this is a 5-day refactor.

**EndOfWeekActivity + EndOfDay_EventHandler** — they have a true EOW/EOD flow. Sazon's EOD is one page; no EOW.

---

### 2.8 resto-nestjs (`/clones/resto-nestjs`) — NestJS + React

**Top-level**: `backend/src/{addon,audit,cart,category,domain,item,location,menu,order,order_manager,order_notes,order_processing_queue,order_statuses,restaurant,shared,singleclient}` — full DDD layout, and `frontend/src/pages/{Home, About, FoodMenu, Login, OrderSuccess, Store, Landing, SignUp, index}`.

**Backend controllers** (39 routes via @Get/@Post decorators): every controller is a thin wrapper over `*.service.ts`, which is its own aggregate with a `Result<IResponseDTO>` return type. Clean DDD, functional-style.

**Pages**: Customer-facing only (no admin UI). This is barely a system — closer to a teaching demo of NestJS with DDD.

**What's relevant for Sazon**: the **DddStyleAggregate** pattern (one entity = one service = one controller). Sazon's `app/rms/plan_accuracy.py` is already a service-aggregate over three models (`ProductionCompletion`, `ProductionPlan`, `Sale`). The "service owns its domain" idiom is identical.

**Caveat**: this is the lowest-signal clone in the bunch.

---

### 2.9 TastyIgniter (`/clones/TastyIgniter`) — Laravel modular, partial clone

The 4.x branch is `laravel/framework`-only stub (92 files) — features are external extension repos (TastyIgniter has 22 official extension repos on GitHub, all named `tastyigniter-ext-…`).

What's known from public docs (web-only — clone is sparse):
- Architecture: extension loader; each feature (menu, orders, locations, customers, reservations, payments, locales) lives in its own repo
- Models: `Menus`, `MenuItems`, `Categories`, `MenuItemOptions`, `Categories`, `Locations`, `Tables`, `Customers`, `Orders`, `OrderMenuItems`, `Reservations`, `Users`, `UserRoles`, `Extensions`
- API: REST + JSON:API (`/api/v1/...`)
- Template engines: Twig + Laravel Blade
- Frontend: Bootstrap 5 + Alpine.js (no React/Vue)
- Payments: Stripe, PayPal, Mollie, etc. via extensions
- Reservations: a "find a table, hold it" flow with multi-day calendar

**Standout patterns for Sazon**:
1. **Extensions as separate packages** — same boundary as Sazon's `app/rms/` modules but more rigorous. If you ever ship a multi-tenant version, this is the model.
2. **JSON:API for v1** — predictable query syntax for clients.
3. **MenuItemOptions** as a separate table from MenuItems — Sazon already models this with `ProductVariant`; TastyIgniter's separation is cleaner.

---

## Part 3 — Cross-cutting capability matrix

| Capability | Sazon | FloCafe | OpenResto | URY | RestoPOS | PizzaQL | FlutterPOS | DineOut | resto-nestjs | TastyIgniter |
|---|---|---|---|---|---|---|---|---|---|---|
| **Bake-day forecast + auto-suggest** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Append-only plan audit** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Plan completion (real qty baked)** | ✅ upsert | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Plan accuracy back-fills forecast** | ✅ computed, ❌ unwired | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Multi-level BOM (sub-recipes)** | ✅ via walk | ❌ (1:1 only) | ❌ | partial | ❌ | ❌ | ❌ | partial | ❌ | partial (via Options) |
| **Recipe auto-deduct on sale** | ✅ rule 8 | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | partial | ✅ | ✅ via extension |
| **KDS (real-time live order screen)** | ❌ | ✅ standalone `:3002` | ❌ | ✅ `mosaic/` | ✅ KOT path | ❌ (TODO) | ❌ | partial | ❌ | partial via extension |
| **Station routing (multi-baker)** | ❌ | ✅ categories by user | ❌ | ✅ ury_production_unit | ✅ kitchens table | ❌ | ❌ | partial | ❌ | partial |
| **Pre-billing checklist (gate sale)** | ❌ | ✅ "verifications" | ❌ | ✅ `ury_pos_checklist_log` | ❌ | ❌ | ❌ | ❌ | ❌ | partial |
| **Daily P&L auto** | ❌ | ❌ | ❌ | ✅ `ury_daily_p_and_l` | partial via GST | ❌ | ❌ | ✅ EOD/EOW | ❌ | partial |
| **Real-time SSE/WebSocket push** | ❌ | ✅ SSE | ❌ | ✅ | ❌ | TODO Subscriptions | ❌ | partial Firebase | ❌ | ❌ |
| **Drag-and-drop UI for daily ordering** | partial (column sort) | ✅ kanban | ❌ | partial | ❌ | ❌ | ✅ (reorder modals) | ❌ | ❌ | partial |
| **Mobile app** | ❌ | partial (Electron tablet) | ✅ Expo | ✅ self-order | ❌ | ❌ | ✅ Flutter | ✅ | ✅ Expo | partial extension |
| **Multi-tenant** | ❌ (single client decision) | ❌ | ❌ | partial | ✅ Stancl Tenancy | ❌ | ❌ | ❌ | ❌ | ✅ multi-location |
| **Merma/scraps (waste tracking)** | ✅ `app/merma` | ❌ | ❌ | partial | ❌ | ❌ | ❌ | ❌ | ❌ | partial |
| **HACCP / cold-chain logging** | ✅ `/produccion/haccp` | partial | ❌ | partial | ❌ | ❌ | ❌ | partial | ❌ | ❌ |
| **Production worksheet (printable)** | ✅ `/produccion` print mode | ✅ KOT print | partial | ✅ KOT print | ✅ KOT direct | ❌ | partial | ❌ | ❌ | partial |
| **Confidence band per row** | ✅ `_forecast_confidence` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Day-of-week seasonal multiplier** | ✅ `SEASONAL_CALENDAR_2026` | ❌ | partial `TurnTimes` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | partial |
| **Bulk CSV ad-hoc production entry** | ✅ "Horneado extra" | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | partial via import |

**Sazon's unique wins (no competitor has all 4)**:
1. Bake-day forecast with confidence bands
2. Append-only plan audit (`production_plan_audit`)
3. Day/Week/Month views of the same workspace
4. Plan-completion upsert (idempotent)

**Sazon's forced deficiencies (don't try to fix these)**:
- Single-tenant by operator decision (memory SASKIA-210)
- No mobile app (operator is at the laptop)
- Local-first (Cloudflare only on hosted VPS)

---

## Part 4 — Sazon's actual production flow today

How `/produccion` works end-to-end (confirmed from code reading):

1. **GET /produccion?for_date=YYYY-MM-DD&view=day** → `_full.day_view()` →
   - **Compute the snapshot**: `production_demand.snapshot_for_date()` reads 14d avg + seasonal events + pedidos pending/confirmed → TTL cache 300s
   - **Load completions**: `eod_completions.completions_for_date()` upserts from `production_completion` table
   - **Load overrides**: `production_production.get_overrides_for_date()` reads `production_plan_override`
   - **Build the plan**: `plan_production(date, products)` returns `ProductionPlan` (Demand + Meta + Override + Lote final)
   - **Render**: produccion.html grilla with 12 columns × ~80 products
2. **POST /produccion/completion** → `_full.mark_completion()` → upsert `production_completion` row
3. **POST /produccion/override** → `_helpers.upsert_override()` → `production_plan_override`
4. **GET /produccion/manana** → `forecast.py` → DOW-weighted average of past 12 weeks
5. **GET /produccion/haccp** → 3 columns (Frio / Stock / Merma diária)
6. **POST /produccion/print** → `print_export.py` → worksheet.pdf
7. **GET /produccion/accuracy** → `plan_accuracy.compute_plan_accuracy()` → AccuracyReport (this fires, but it's NEVER read by the plan)

The `producci