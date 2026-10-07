# Saskia RMS — Canonical Backlog (Merged Source of Truth)

> **Last updated:** 2026-10-05
> **Sources merged:**
> 1. `/IMPROVEMENT_BACKLOG.md` (operator-curated, 40 items in 7 Tiers, last touched 2026-10-01)
> 2. `docs/decisions/2026-09-29-canonical-roadmap-alignment.md` (Iván's P0/P1/P2/P3, 18+ items)
> 3. `docs/p1-p2-wishlist-2026-09-27.md` (wishlist categories — merged into individual items)
> 4. `docs/roadmap/WISHLIST.md` (raw ideas from Saskia/operator)
>
> **Convention:** every item has an **ID** (A.# from canonical, or BACKLOG-# from
> operator list, or E#.S# from epic plan, or WISHLIST-#), a **Status** (✅ Done /
> 🔶 In Progress / ❌ TODO), a **Source** (which doc it came from), an **Effort**
> estimate, and a short description.

## Backlog summary (40 operator items + 18 canonical + 21 wishlist = 79 tracked)

| Tier / phase | Total | ✅ Done | 🔶 In Progress | ❌ TODO |
|---|---:|---:|---:|---:|
| **P0 Critical correctness** (canonical A + Tier 1) | 12 | 4 | 2 | 6 |
| **P0 Security / data integrity** (Tier 2) | 6 | 5 | 0 | 1 |
| **P1 Quality / refactoring** (Tier 3) | 8 | 8 | 0 | 0 |
| **P1 Performance** (Tier 4) | 5 | 5 | 0 | 0 |
| **P2 Analytics** (Tier 5) | 6 | 6 | 0 | 0 |
| **P2 Predictive / ML** (Tier 6 + canonical B) | 14 | 3 | 0 | 11 |
| **P3 Infra & future** (Tier 7 + canonical D) | 11 | 4 | 0 | 7 |
| **Wishlist (raw ideas)** | 21 | 8 | 0 | 13 |

---

# P0 — Critical (this week, "cerrar puertas")

## P0.1 — Correctness (canonical A.1–A.6 + Tier 1 #1–#6)

| ID | Title | Status | Source | Effort | Notes |
|---|---|---|---|---|---|
| **A.1** | Confirm modal on all destructive actions | 🔴 In Progress polish/saskia-p0 | canonical | S | audited 2026-10-07: real gap = 11 forms (caja/cerrar x2, eod/completar, clientes merge, pedido duplicate, menus off, excel importar, bank unreconcile, auditoria/prune, override-bulk, shift-execute) |
| **A.2** | CSRF token on all `<form method="post">` | ✅ Done verified 2026-10-07 | canonical + WISHLIST | S | middleware signed-cookie on all POSTs + field present in ALL 50 templates (15 `_csrf_token` + 35 `csrf_token`, both accepted) + guard test test_p0_confirm_modal_csrf.py green |
| **A.3** | Audit log on 12 missing actions | ✅ Done verified 2026-10-07 | canonical + WISHLIST | S | verified in code: write.product.* / write.customer.merge / write.bank.categorize / write.eod.complete / write.production.override.set / write.merma.* / write.excel.import all present (81 audited actions) |
| **A.4** | Rate-limit on /login (5/min, backoff after 3 fails) | ✅ Done verified 2026-10-07 | canonical | XS | is_rate_limited enforced in login_submit (auth.py:114) with styled retry-countdown page |
| **A.5** | `void_sale` after-cierre bug | ✅ Done verified 2026-10-07 | canonical | S | guard void_after_eod_close in app/rms/sales/lifecycle.py:305 + costing.py:633 |
| **A.6** | Loading skeletons on `/dashboard /ventas /productos /reportes` | ✅ Done verified 2026-10-07 | canonical | S | ui.loading_state + ui-skeleton.js: dashboard(4) + productos + reportes index + 13 reportes pages covered. /ventas intentionally excluded: POS renders synchronously, skeleton flash would slow the cashier |
| **BACKLOG #1** | Consolidate `sale_stock_move` + `stock_movement` | 🔶 In Progress | operator | M | costing.py dual-write documented; ~50 files for full refactor |
| **BACKLOG #2** | `pedido_sale_stock_move` link | ✅ Done | operator | — | mig 076; `Sale.linked_pedido_id`; chain pedido→sales→stock_moves |
| **BACKLOG #3** | DB-level `stock_qty >= 0` (INV-03) | ✅ Done | operator | — | mig 084 SQLite triggers + PG CheckConstraint; 6/6 tests pass |
| **BACKLOG #4** | Migrations truly atomic | 🔶 In Progress | operator | S | `atomic_ddl_block` SAVEPOINT helper at `db.py:4073`; mig 085-089 converted; **83 migrations remain** to convert |
| **BACKLOG #5** | DB CHECK on `recipe.yield_qty > 0` | ✅ Done | operator | — | mig 028 update + mig 083 insert triggers; tests pass |
| **BACKLOG #6** | `ON DELETE` policy on `RecipeLine.recipe_id` | ✅ Done | operator | — | audit: CASCADE on RecipeLine, RESTRICT on Product.recipe_id |

## P0.2 — Security / data integrity (Tier 2 #7–#12)

| ID | Title | Status | Source | Effort | Notes |
|---|---|---|---|---|---|
| **BACKLOG #7** | `void_sale` Decimal sweep (12 sites) | ✅ Done 5ce2885 | operator | — | |
| **BACKLOG #8** | `pedidos_fulfill` idempotency | ✅ Done 5ce2885 | operator | — | |
| **BACKLOG #9** | `/eod/check` idempotency | ✅ Done 2026-09-29 | operator | — | F3 race + AppMeta unique-key reserve |
| **BACKLOG #10** | Read rate-limit (60/min search, 30/min reportes) | ✅ Done 2026-10-01 | operator | — | cea8111; also covers canonical A.4 partially |
| **BACKLOG #11** | Sentry error tracking | ✅ Done 2026-10-01 | operator | — | test_sentry_init.py; main.py:206-229, 917-928 |
| **BACKLOG #12** | Forward-only migration rollback path | ❌ TODO | operator | L | Intentional design; manual write required if 027 breaks |

---

# P1 — Quality & Performance (this month)

## P1.1 — Quality / refactoring (Tier 3 #13–#20)

| ID | Title | Status | Source | Effort | Notes |
|---|---|---|---|---|---|
| **BACKLOG #13** | `Ingredient.avg_cost_gs` moving-average | ✅ Done | operator | — | mig 089; `waste.py:record_waste` recomputes; 6 tests |
| **BACKLOG #14** | `LoyaltyTransaction` ledger | ✅ Done | operator | — | mig 074; `award_points` / `redeem_points`; ledger UI on `/clientes/{id}` |
| **BACKLOG #4-alt** | Atomic DDL block (also Tier 1) | ✅ Done | operator | — | (Sprint 4.5 2026-10-02; mig 085-089 converted) |
| **BACKLOG #16** | `GET /ventas/{sale_id:int}` standalone | ✅ Done | operator | — | Sprint 4.1 commit 272128b; `ventas_detalle.html` |
| **BACKLOG #17** | Public recibo `/p/{token}` | ✅ Done | operator | — | audit was stale; 25 tests pass (token + rate-limit + expiry) |
| **BACKLOG #18** | `parse_money_gs` / `parse_gs` consolidation | ✅ Done | operator | — | already a thin wrapper |
| **BACKLOG #19** | `RecipeLine.qty` Float → Numeric(12,4) | ✅ Done | operator | — | Sprint 4.2 commit f454757 |
| **BACKLOG #20** | Discount math overflow guard | ✅ Done | operator | — | Decimal-safe; 10 tests |

## P1.2 — Performance (Tier 4 #21–#25)

| ID | Title | Status | Source | Effort | Notes |
|---|---|---|---|---|---|
| **BACKLOG #21** | `compute_reorder_list` N+1 (false alarm) | ✅ Done | operator | — | single bulk SELECT already |
| **BACKLOG #22** | Dashboard 24h aggregation + discount fix | ✅ Done | operator | — | Python kept (TZ-aware); 9 tests in `test_dashboard_aggregation_discount_fix.py` |
| **BACKLOG #23** | `/productos` `batch_compute_prime_cost` | ✅ Done | operator | — | selects eager-loaded recipe; 8 tests |
| **BACKLOG #24** | `/recetas` pagination | ✅ Done | operator | — | `page` + `page_size` (default 50, max 200) |
| **BACKLOG #25** | Hot-path indexes | ✅ Done | operator | — | Sale.sold_at, StockMovement.ingredient_id, Pedido.customer_phone |

---

# P2 — Analytics & ML (next month, canonical B + C)

## P2.1 — Analytics value (Tier 5 #26–#31 + canonical C.4–C.5)

| ID | Title | Status | Source | Effort | Notes |
|---|---|---|---|---|---|
| **BACKLOG #26** | `/reportes/consumo` consumption analytics | ✅ Done | operator | — | 7/30/90/365 toggle; reads `StockMovement` post-#1 |
| **BACKLOG #27** | `Sale.tz` timezone breakdown | ✅ Done | operator | — | `/clientes/{id}`; 7 tests pass |
| **BACKLOG #28 / #34** | Waste ROI per ingredient | ✅ Done | operator | — | `/reportes/mermas-cost?days=90`; 11 tests |
| **BACKLOG #29 / #33** | Plan accuracy dashboard | ✅ Done | operator | — | `/produccion/accuracy`; Hypothesis property tests |
| **BACKLOG #30** | Audit log analytics | ✅ Done | operator | — | `/auditoria/analytics`; top IPs/actions/operators |
| **BACKLOG #31** | `/suppliers/volatility` leaderboard | ✅ Done | operator | — | Sprint 4.11; 12 tests |
| **C.4** | Food cost semáforo on `/analisis` | ✅ Done verified 2026-10-07 | canonical | S | semaforo_color live in analisis.html:12-19 (gray/danger/warning) |
| **C.5** | Test gaps (eod_completions, reorder, excel_modes, recipes, csrf, xss) | 🟡 partial | canonical | M | 10+ test files shipped (P17/P18/P32/P33/P36/P39 reorder+prep, csrf); xss/eod_completions still open |

## P2.2 — Predictive / ML (Tier 6 #32–#36 + canonical B.1–B.2)

| ID | Title | Status | Source | Effort | Notes |
|---|---|---|---|---|---|
| **B.1** | **Venta Express `/v/quick`** | ❌ TODO | canonical | S (3d) | 6-8 big buttons + numeric input + Enter; -45s/venta |
| **B.2** | **Forecast enchufado in `/produccion/manana`** | ✅ Done | canonical | M (4d) | /produccion/manana route (forecast.py:67) + plan_production + confidence_pct + _forecast_confidence + seasonal integration + override-bulk POST; 18/18 tests pass in test_p1_b2_forecast_enchufado.py |
| **B.3** | Pedido web upload comprobante `/p/{slug}` | ✅ Done | canonical | M (3d) | pedido_publico.html:148-158 (P1-B3: comprobante upload, visible when payment_intent != efectivo) |
| **B.4** | Customer merge (dedup "María" duplicates) | ✅ Done verified 2026-10-07 | canonical | M (3d) | POST /clientes/{id}/merge (customers.py:1550) + dupes UI + audit write.customer.merge |
| **B.5** | Suscripciones sin cron | 🟡 partial | canonical | M (4d) | `PedidoSubscription` model + page shipped (B5 6d38bc1); cron-gen button pending |
| **B.6** | Cmd+K + atajos POS + dirty state | ✅ Done | canonical | M (3d) | app/static/shortcuts.js shipped (Phase 4 polish); shortcuts help modal |
| **B.7** | 3 insights accionables (60+d, margen<30%, stock N días) | ✅ Done | canonical | M (2d) | insights.py:176-186 emits 60+d stock + margen<30% + days_of_stock alerts; rendered in /analisis (23 insight refs) |
| **BACKLOG #32** | Poisson regression restocking | ❌ TODO | operator | L | "expected consumption next 3 days" |
| **C.1** | Sentry + Telegram alerts (stock crítico, shelf<3, 5xx) | ✅ Done 2026-10-07 | canonical | S | app/rms/notify.py (91b44f94) + 1-line before_send hook in main.py (aa0eb6cf) + 3 wiring tests; silent no-op without TG_BOT_TOKEN/TG_CHAT_ID; VPS env pending (operator lane) |
| **C.2** | Vista cliente tablet `/m/{slug}` (1280×720) | ✅ partial | canonical | S | 2d30172 + 6d38bc1; further polish |
| **C.3** | Arqueo de caja guiado `/cierre/arqueo` | ✅ Done 2026-10-07 | canonical | S | 18e75696: conteo por denominaciones (100k..50) en caja.html, autollena counted_gs + diff en vivo; sin backend nuevo |
| **C.6** | Bug fixes (aria-labels, sticky headers, missing indexes, dashboard N+1) | ✅ done | canonical | XS-M | all shipped: dashboard N+1 (caf1cf19, 25+ → 0 per-product sale queries), sticky headers wrapped in 5 templates (cotizador, eod, bank, caja, creditos), aria+indexes already done. Also fixed pre-existing /inicio 500 from tz-naive datetime compare. |

---

# P3 — Infra & future (Tier 7 #37–#40 + canonical D)

| ID | Title | Status | Source | Effort | Notes |
|---|---|---|---|---|---|
| **BACKLOG #37** | Supabase Storage for product images | ✅ Done | operator | — | HEAD `4214cc0` 2026-10-02 |
| **BACKLOG #38** | Supabase RLS multi-tenant | ❌ TODO | operator | L | Tenant model exists; RLS not implemented |
| **BACKLOG #39** | `/healthz/backup` + `/admin/backup` | ✅ Done | operator | — | Sprint 4.7; UptimeRobot 503s on stale backups |
| **BACKLOG #40** | `/healthz/deps` Supabase + R2 + disk probes | ✅ Done | operator | — | Sprint 4.6; 90% alarm threshold |
| **B.8** | Backup local AES-256 + cron diario | ❌ TODO | canonical | S (1d) | `auto_backup.py` exists; hook to EOD close needed |
| **B.9** | `/suppliers/{id}/precios` price comparison | ✅ Done | canonical | S (1d) | app/routers/suppliers.py:246 (supplier_precios) + get_price_comparison wired |
| **D.1** | Voseo/guaraní i18n | ➖ Deferred | canonical | — | only if bilingual client |
| **D.2** | Modo alto contraste | ➖ Deferred | canonical | — | only if a11y complaint |
| **D.3** | Cerrar features muertas (Customer.loyalty_points, Tenant scaffold, PriceHistory) | 🟡 partial | canonical | M | loyalty_points now real (BACKLOG #14); Tenant still scaffold; PriceHistory now writes (BACKLOG #31) |
| **D.4** | AI-driven demanda por hora/producto | ❌ TODO | canonical | XL | 6,177 sale_stock_move rows are training data |
| **D.5** | Backup AES-256 con DNI-derived password + restore test mensual | 🟡 partial | canonical | M | R2 retention shipped; password derivation + monthly test pending |
| **D.6** | `/riesgos` flag-gated v0.5 | ✅ Done | canonical | M | app/routers/herebus.py:222 (risks_router) + riesgos.html template (12 risks seeded) |
| **D.7** | Glossary + Loom en `/guia` | ➖ Deferred | canonical | — | low priority |

---

# Wishlist (raw ideas, 21 items)

> Source: `docs/wishlist/`. See [`WISHLIST.md`](WISHLIST.md) for the full index.
> Key insight: **3 wishlist items are P0 (canonical "cerrar puertas")** —
> `2026-09-04-csrf-tokens-on-state-changing-forms.md` (A.2),
> `2026-09-04-per-user-audit-log.md` (A.3), and
> `2026-09-04-rate-limit-on-endpoints.md` (BACKLOG #10 + /login gap).

---

# Descartado definitivamente (per Saskia single-user context)

> Source: `docs/decisions/2026-09-29-canonical-roadmap-alignment.md`.

**Do not pursue these features** — verified against sombreros and `saskia-only-roadmap.md`:

- ❌ RBAC real (admin/manager/cashier) — Saskia is the only user
- ❌ Multi-warehouse / multi-location — 1 ubicación
- ❌ Multi-moneda (USD/EUR/BRL/ARS) — solo Gs; USD/EUR tipo de cambio
- ❌ Multi-idioma (en/pt) — 100% hispanohablante
- ❌ Multi-timezone — Asunción
- ❌ Cotizaciones formales — WhatsApp informal
- ❌ Devoluciones parciales — anulación + merma
- ❌ PWA offline — internet razonablemente estable
- ❌ WhatsApp Business API / NLP bot
- ❌ Suscripciones automáticas (cron) — modelo + manual
- ❌ Impresión térmica ESC/POS — `window.print()`
- ❌ Co-occurrence matrix, cohort retention, churn prediction, real-time polling
- ❌ Catálogo de 9 insights → reducir a 3
- ❌ Background jobs / cola
- ❌ Cursor pagination, cache, virtualización
- ❌ Visual regression, load testing, property-based tests
- ❌ WCAG audit formal con axe-core
- ❌ CI/CD con coverage gate (gate al 35% es suficiente)
- ❌ Componentes visuales nuevos (wizard, lightbox, sparklines, status pills)
- ❌ Empty states ilustrados, drag-to-reorder, inline editable cells, barcode widget
- ❌ Rotación GitHub App tokens, dependabot (already done)
- ❌ Multi-tenant, OpenTelemetry, mobile app nativa, integración delivery apps
- ❌ Cohort/churn/elasticidad
- ❌ Email semanal — Saskia no lee email
- ❌ Referral program
- ❌ Trazabilidad bidireccional harina→pan terminado
- ❌ Sensor Bluetooth temperatura heladera
- ❌ Comparativa precios competencia
- ❌ Reporte huella de carbono
- ❌ Carta de cierre / migración BD si cierra panadería

---

# The 8 gemas ocultas (módulos escritos, no enchufados)

> Source: `docs/decisions/2026-09-29-canonical-roadmap-alignment.md`.
> These files exist but are not wired into the UI. Most are enchufables (no new code).

| Módulo | Estado | Acción | Esfuerzo | ROI |
|---|---|---|---|---|
| `forecast.py` | Calcula `days_of_stock` pero no sugiere cuánto producir | Enchufar en `/produccion/manana` | M (4d) | -30% desperdicio ≈ Gs. 600k/mes |
| `food_cost.py` | Fórmula coste/precio existe | Enchufar semáforo en `/analisis` | S (2d) | Gs. 500k/mes |
| `sales_intel.py` | Intelligence sobre ventas | Enchufar 3-4 outputs relevantes | S | TBD |
| `seasonal.py` | `SEASONAL_CALENDAR_2026` existe | Llamar desde `forecast.py` | XS (1d) | Mejora precisión |
| `recipe_intel.py` | Sub-receta cost breakdown | Mostrar en `receta_detalle.html` | S | Decisión informada |
| `insights.py` | Definidos, no se renderizan | Renderizar 3 priorizados | S (2d) | B.7 de P1 |
| `price_history.py` + `IngredientPriceEvent` | 0 rows en BD | Detector de sobreprecio silencioso | S | Gs. 4.3M/año (B.9) |
| `services/r2_backup.py` | Existe sin snapshot automático | Decidir R2 vs local → local + cron | S (1d) | B.8 |
| `services/auto_backup.py` | Corre al startup, no diario | Cambiar a cron o hook en EOD close | XS | B.8 |
| `sale_stock_move` | 6,177 rows en BD | Oro para entrenar modelo de demanda | XL | AI-driven P3 |
