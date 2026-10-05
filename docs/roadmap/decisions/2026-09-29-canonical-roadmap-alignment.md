# Saskia RMS — Consolidated Decisions & Roadmap Alignment

**Generated:** 2026-09-29 (this turn)
**Author:** Session A retrospective after Ivan's "what to do next" prompt
**Purpose:** Reconcile Session A's 40-hats decisions (made in isolation) with
the **canonical Saskia-only-roadmap.md** that Ivan wrote on 2026-09-29
(answering the scoping questions in session
`@session:ivan/20260929_171036_409944`). The canonical roadmap wins.

---

## TL;DR — what's different vs Session A's 18 decisions

| # | Session A's decision (made in isolation) | Canonical Ivan's answer | Action |
|---|---|---|---|
| 1 | Rescope `/dashboard` → `/mostrador` role-aware | Saskia = single user, no cashier/manager | **Drop /mostrador — not needed**. Rescope kept for "show pending at counter" via unified `/inicio`. |
| 4 | Chips everywhere | Same — `filter_chips` macro | ✅ Aligned |
| 5 | Ship `/riesgos` flag-gated | **Lower priority** than cerrar-puertas P0 | **Defer to P3** |
| 6 | Delete `produccion_calendario.html` | Same | ✅ Aligned (5 min) |
| 7 | CI gate for `format_gs` | Same | ✅ Shipped Session A |
| 8 | Dark-only, no light mode | Same | ✅ Aligned |
| 9 | Defer PWA | Same | ✅ Aligned |
| 10 | Build 4 web components | **Pivot**: `/v/quick`, forecast enchufado, pedido-web-upload > new components | **Reframe**: 4 web components (kpi-card done) + 2 wired-up services (forecast, food_cost) |
| 11 | Complete 3 macros | **Pivot**: customer merge endpoint, suscripciones modelo, CSRF audit > new macros | **Reframe**: macros still useful BUT **`data_table` is NOT blocking** because the 6 list pages aren't critical P0/P1 |
| 13 | Keep `/wishlist` fix | Same | ✅ Aligned |
| 14 | Don't refactor `receta_form.html` | Same | ✅ Aligned |
| 16 | `/suppliers/{id}/precios` price comparison | **HIGHEST value** missed feature per sombrero #36 (procurement) | ✅ Move to **P1** (Session E) |
| 17 | Glossary + Loom | Same | ✅ Aligned but defer to P3 |
| — | **NEW from canonical**: confirm modal, CSRF audit, audit log, rate limit, `combo.js` bug, void-after-cierre bug | **P0 #1 priority — "cerrar puertas"** | **Add to next session** |
| — | **NEW from canonical**: customer merge, suscripciones, 3 insights, backup local, **Venta Express `/v/quick`**, **forecast enchufado** | **P1 priority** | **Add to roadmap** |
| — | **NEW from canonical**: 8 gemas ocultas (forecast/food_cost/sales_intel/seasonal/recipe_intel/insights/price_history/auto_backup) | Modules written but unconnected | **Plug in, don't rebuild** |

---

## The canonical priority order (Ivan's `saskia-only-roadmap.md`)

### P0 — esta semana (~2 días, ship BEFORE anything else)

These are "cerrar puertas" — prevent the next disaster. Saskia can lose a day's data with one wrong click today.

| # | Item | Effort | Why P0 |
|---|---|---|---|
| A.1 | Confirm modal en TODAS las acciones destructivas (`/inventario/{id}/eliminar`, `/suppliers/{id}/eliminar`, `/users/{id}/eliminar`, `/productos/{id}/eliminar`, `/recetas/{id}/eliminar`, venta anulación con razón obligatoria, merma eliminación) | S | Hoy un click equivocado borra una receta entera |
| A.2 | CSRF token en todos los `<form method="post">` (~30 forms lo olvidan) | S | El token ya existe, falta inyectarlo |
| A.3 | Audit log comprehensivo (12 acciones hoy no loggean: `product.create/update/delete`, `customer.merge`, `bank.categorize`, `eod.close`, `production.override.set`, `production.completion.record`, `merma.create/delete`, `excel.import.complete`) | S | Sin audit = no forensics cuando algo se rompe |
| A.4 | Rate limit en `/login` (5/min por IP, exponential backoff después de 3 fallos) | XS | Defensa básica |
| A.5 | Bug: `void_sale` no respeta cierre del día — Saskia puede anular una venta del lunes DESPUÉS del cierre del lunes | S | Violación contable; mencion explícito en roadmap |
| A.6 | Loading skeletons en `/dashboard`, `/ventas`, `/productos`, `/reportes` | S | UX base |

> **Status Session A:** Confirmé el bug del void-after-cierre (`app/routers/sales.py:1093`) — `void_sale()` no consulta si la venta pertenece a un día con EOD cerrado. Confirmé que solo 4 routers usan `record_audit` (eod/users/health/auditoria) — falta en los 12 módulos críticos. Confirmé que el bug `combo.js` preload NO existe — base.html:304 carga `saskia-combo.js` que sí existe.

### P1 — este mes (~12-17 días, los más valiosos)

| # | Item | Effort | ROI |
|---|---|---|---|
| B.1 | **Venta Express `/v/quick`** — 6-8 botones grandes (productos top del día) + input numérico + Enter registra | S (3d) | **-45s/venta = ~22 min/turno = ~10h/mes** |
| B.2 | **Forecast diario enchufado** — `forecast.py` + `seasonal.py` ya escritos; faltan en `/produccion/manana` UI | M (4d) | **-30% desperdicio ≈ Gs. 600k/mes** |
| B.3 | **Pedido web con upload de comprobante** — `/p/{slug}` está "broken per audit"; Paraguay 80% transferencia sin upload el flujo no cierra | M (3d) | Cierra el flujo de catering |
| B.4 | Customer merge (combinación de duplicados "María") | M (3d) | Reportes distorsionados hoy |
| B.5 | Suscripciones SIN cron — modelo + página `/pedidos/suscripciones` + botón "Generar pedidos de esta semana" | M (4d) | "Todos los lunes 2 chipás" sin re-crear a mano |
| B.6 | Cmd+K mejorado + atajos contextuales POS + dirty state | M (3d) | "Sensación de app moderna" |
| B.7 | 3 insights accionables (solo 3, los más útiles): clientes 60+d sin volver / margen<30% / stock se acaba en N días | M (2d) | Reduce decisiones a ojo |
| B.8 | Backup local con cifrado AES-256 + cron diario (no al startup) | S (1d) | **Riesgo #1 no atendido** según sombreros |
| B.9 | `/suppliers/{id}/precios` price comparison | S (1d) | **Gs. 4.3M/año** ahorrados en harina |

> **Status:** Items B.1 (Venta Express) y B.2 (forecast enchufado) son los más altos ROI y deberían ir PRIMERO en P1. B.8 (backup) debería ser P0.5 — está entre A y B en criticidad.

### P2 — próximo mes (~10-12 días)

| # | Item | Effort |
|---|---|---|
| C.1 | Sentry completo + alertas Telegram (stock crítico + shelf_life<3 + 5xx) | S |
| C.2 | Vista cliente tablet `/m/{slug}` — pública, 1280×720, lista de precios con foto | S |
| C.3 | Arqueo de caja guiado `/cierre/arqueo` | S |
| C.4 | Reporte food cost con semáforo (verde<30% / amarillo 30-40% / rojo>40%) enchufando `food_cost.py` | S |
| C.5 | Tests gaps prioritarios: `test_eod_completions` (8 nuevos), `test_reorder_supplier_prefs` (MOQ+lead time+preferred price), `test_excel_modes` (APPEND/PATCH/FULL), `test_recipes_subrecipes` (depth>5, yield=0), `test_csrf_all_forms`, `test_xss_prevention` | M |
| C.6 | Bug fixes aria-labels en icon-only buttons, sticky table headers, DB indexes faltantes, N+1 fix en dashboard | XS-M |

### P3 — backlog

| # | Item |
|---|---|
| D.1 | Voseo/guaraní i18n (solo si llega cliente bilingüe) |
| D.2 | Modo alto contraste (si llega queja a11y) |
| D.3 | **Cerrar features muertas**: eliminar `Customer.loyalty_points`, scaffolding multi-tenant (`Tenant` table), decidir sobre `PriceHistory` (¿implementar detector sobreprecio o eliminar?) |
| D.4 | AI-driven (backlog #26): demanda por hora/producto usando `sale_stock_move` 6,177 rows |
| D.5 | Backup AES-256 con DNI-derived password + restore test mensual |
| D.6 | `/riesgos` flag-gated v0.5 |
| D.7 | Glossary + Loom videos en `/guia` |

---

## DESCARTADO DEFINITIVAMENTE (el contexto Saskia-single-user-single-location)

Verificado contra sombreros y contra `saskia-only-roadmap.md`. **No perder tiempo en estas features:**

- ❌ RBAC real (admin/manager/cashier) — Saskia es la única usuaria
- ❌ Multi-warehouse / multi-location — 1 ubicación
- ❌ Multi-moneda (USD/EUR/BRL/ARS) — solo Gs; USD/EUR se cambian al tipo de cambio
- ❌ Multi-idioma (en/pt) — 100% hispanohablante (guaraní solo si aparece cliente)
- ❌ Multi-timezone — Asunción
- ❌ Cotizaciones formales — WhatsApp informal funciona
- ❌ Devoluciones parciales — anulación total + merma alcanza
- ❌ PWA offline — internet razonablemente estable
- ❌ WhatsApp Business API / NLP bot — tipear 30 pedidos/día no es cuello de botella
- ❌ Suscripciones automáticas (cron) — modelo sin cron; Saskia abre y click manual
- ❌ Impresión térmica ESC/POS — `window.print()` alcanza para el volumen
- ❌ Co-occurrence matrix, cohort retention, churn prediction, real-time polling
- ❌ Catálogo de 9 insights — reducir a 3 (los descritos en P1)
- ❌ Background jobs / cola — 30 ventas/día, threading no aporta
- ❌ Cursor pagination, cache, virtualización — <1000 rows en auditoría
- ❌ Visual regression, load testing, property-based tests — 1,890 tests es suficiente
- ❌ WCAG audit formal con axe-core — arreglar issues conocidos
- ❌ CI/CD con coverage gate — pre-commit + ruff + mypy sí; coverage no
- ❌ Componentes visuales nuevos (wizard, lightbox, sparklines, status pills animados)
- ❌ Empty states ilustrados, drag-to-reorder, inline editable cells, barcode widget
- ❌ Rotación GitHub App tokens, dependabot
- ❌ Multi-tenant, OpenTelemetry, mobile app nativa, integración delivery apps (PedidosYa/Hugo)
- ❌ Cohort/churn/elasticidad — 30 ventas/día no tiene suficiente data para ML
- ❌ Email semanal — Saskia no lee email; comunicación = WhatsApp
- ❌ Referral program — clientela de barrio
- ❌ Trazabilidad bidireccional harina→pan terminado (sombrero HACCP) — auditoría 1 vez/año, no justifica
- ❌ Sensor Bluetooth temperatura heladera (sombrero HACCP) — overkill
- ❌ Comparativa precios competencia — Saskia los mira en persona
- ❌ Reporte huella de carbono
- ❌ Carta de cierre / migración BD si cierra panadería — planificación de salida

---

## Las 8 gemas ocultas (módulos escritos, no enchufados)

Estos archivos existen pero no se usan en UI. La mayoría son enchufables (no requieren código nuevo):

| Módulo | Estado | Acción | Esfuerzo | ROI |
|---|---|---|---|---|
| `forecast.py` | Calcula `days_of_stock` pero NO sugiere cuánto **producir** mañana | Enchufar en `/produccion/manana` con confianza del forecast | M (4d) | -30% desperdicio ≈ Gs. 600k/mes |
| `food_cost.py` | Fórmula coste/precio existe, no se muestra | Enchufar semáforo verde/amarillo/rojo en `/analisis` | S (2d) | Gs. 500k/mes recuperados con 1 ajuste de precio |
| `sales_intel.py` | Intelligence sobre ventas, no enchufado | Revisar outputs, enchufar relevantes | S | TBD |
| `seasonal.py` | `SEASONAL_CALENDAR_2026` existe, no se aplica al forecast | Llamar desde `forecast.py` | XS (1d) | Mejora precisión del forecast |
| `recipe_intel.py` | Sub-receta cost breakdown, no se muestra | Mostrar en `receta_detalle.html` | S | Decisión "qué producir" más informada |
| `insights.py` | Insights definidos, no se renderizan | Renderizar los 3 priorizados en `/inicio` y `/analisis` | S (2d) | B.7 de P1 |
| `price_history.py` + `IngredientPriceEvent` | 0 rows en BD | Detector de sobreprecio silencioso | S | Gs. 4.3M/año (B.9 de P1) |
| `services/r2_backup.py` | Existe pero sin snapshot automático | Decidir: R2 vs local. Saskia descarga mensual → **local + cron diario** | S (1d) | B.8 de P1 |
| `services/auto_backup.py` | Corre al startup, **no diario** | Cambiar a cron o hook en EOD close | XS | B.8 de P1 |
| `sale_stock_move` | **6,177 rows** en BD | **Oro para entrenar modelo de demanda** (BACKLOG #26) | XL | AI-driven P3 |

---

## Updated Session roadmap (re-aligned)

**Sesión A** ✅ DONE: KPI card + 3 page adoptions + D3 lint gate + bank v056 + uniform tile height
**Sesión B** 🔴 REVISED: **cerrar puertas P0** (confirm modal + CSRF audit + audit log + void-after-cierre) — 5h
**Sesión C** 🟢 P1 #1: **Venta Express `/v/quick`** — 5h
**Sesión D** 🟢 P1 #2: **Forecast diario enchufado** + **seasonal** integration — 5h
**Sesión E** 🟢 P1 resto: backup local + customer merge + 3 insights + price comparison `/suppliers/{id}/precios` — 5h×2
**Sesión F** 🟢 P1 final: suscripciones + Cmd+K + atajos POS — 5h
**Sesión G** 🟡 P2: Sentry + vista tablet + arqueo + food_cost semáforo — 5h
**Sesión H** 🟡 P2: test gaps (eod_completions, reorder, excel_modes, recipes, csrf, xss) — 5h

> **Más realista que las 4 sesiones originales** — refleja el canon Ivan-aprobado en `saskia-only-roadmap.md`.

---

## Source documents

- `@session:ivan/20260929_171036_409944` — Ivan answered 5 scoping questions → produced `saskia-only-roadmap.md`
- `@session:ivan/20260927_182227_f40eb1` — 9 commits, 165 files, 7/18 P0 defects closed, 377 bank tests passing
- `/opt/data/profiles/ivan/cache/scratch/saskia-only-roadmap.md` — 268 lines, Ivan-approved canonical
- `/opt/data/profiles/ivan/cache/scratch/saskia_sombreros_analysis.md` — 369 lines, 120 ideas concretas de 40 sombreros
- `/opt/data/profiles/ivan/cache/scratch/saskia-master-menu.md` — menú completo con checkboxes
- `/opt/data/profiles/ivan/cache/scratch/audit-batch2-prod.md` (78 KB) + `audit-batch3-reports.md` (69 KB)
- `/opt/data/profiles/ivan/cache/scratch/cross-page-wishlist-consolidation.md` — top 30 patterns + top 10 macros
- `/opt/data/profiles/ivan/cache/scratch/macro-contracts-2026-09-27.md` (126 KB) — 10 atomic contracts
- `/opt/data/profiles/ivan/cache/scratch/qol-touches-catalog.md` (41 KB) — 219 QoL items
- `/opt/data/profiles/ivan/cache/scratch/role-wireframes-2026-09-27.md` (85 KB) — 5 personas
- `/opt/data/profiles/ivan/cache/scratch/state-machines-2026-09-27.md` (54 KB) — 4 state machines
- `docs/decisions/v1/40-hats-pre-canonical.md` — Session A original (pre-canonical-reconciliation, archived)
- `docs/upgrades/2026-09-29-UX-UPGRADE-PLAN.md` — UX/UI upgrade plan (catalog reference)
