# Sazón — Complete UX/UI Upgrade Plan v2 (Full Catalog)

**Generated:** 2026-09-29 (rev 3 — full catalog sweep, ops triad blueprint integrated)
**Author:** UX/UI Principal review (multi-hat analysis + Gemini QA on operational triad)
**Repo:** `/opt/data/profiles/ivan/scratch/sazon-app-work`
**Live:** `https://sazon-vps.paragu-ai.com` (Docker Swarm, image `sazon-rms:prod`, schema v60)

---

## Source audits (complete — 14 files in `/tmp/designer-drop/`)

| File | Size | Lines | Contents |
|---|---:|---:|---|
| `design-plans-2026-09-27.md` | 340 KB | 9,463 | **17 pages × 5-hat analysis + wishlist + QoL + defects** |
| `macro-contracts-2026-09-27.md` | 68 KB | 2,363 | **10 atomic macro contracts** (Purpose/Arguments/HTML/Behavior/A11y/Locale/Used-by/Anti-patterns) |
| `audit-batch2-prod.md` | 78 KB | 948 | 14 pages (Inventario/Producción/Pedidos/Receta) |
| `audit-batch3-reports.md` | 69 KB | 950 | 14 pages (Compras/Reportes/Admin/Bank/Riesgos/Auditoría) |
| `role-wireframes-2026-09-27.md` | 44 KB | 932 | **5 personas** × ASCII wireframes + keyboard maps + cognitive-load targets |
| `cross-page-wishlist-consolidation.md` | 37 KB | 602 | top 30 patterns + top 10 macros + top 10 defects |
| `cross-cutting-consistency-audit.md` | 38 KB | 544 | **12 naming/consistency dimensions** |
| `ux-audit-2026-09-27.md` | 34 KB | 587 | **18 P0 defects categorized** + 5 universal defects |
| `state-machines-2026-09-27.md` | 32 KB | 769 | **4 state machines** (Pedido / Stock Ledger / Cierre Caja / Bake-loss math) |
| `qol-touches-catalog.md` | 40 KB | 358 | **219 QoL items in 16 categories** with effort estimates |
| `REPORT.md` | 52 KB | 1,402 | route → router → template → context-keys reference |
| `implementation-status-2026-09-27.md` + `-evening.md` | 18 KB | 279 | what got shipped 2026-09-27 |
| `README.md` | — | 66 | overview |
| `sazon-ux-audit-drop-2026-09-27.zip` | 9.5 MB | — | full bundle + 82 screenshots |

**Grand total:** 30 patterns · 10 macros · 219 QoL items · 18 P0 defects · 12 naming dimensions · 17 pages × 5-hat · 28 per-page audits · 4 state machines · 5 personas · 6 universal defects · 10 cross-page defects.

---

## What's already shipped (from session 20260927_182227 — 9 commits, ~165 files)

**Web Components built (5):** `ui-date` (12.9 KB · D1 fix) · `ui-combo` (18.6 KB · D17 refactor in progress) · `ui-month` (9.4 KB) · `ui-skeleton` (6.0 KB) · `ui-toast` (7.5 KB · D14 in progress)
**CSS layers:** `app.css` 48 KB · `app-shell.css` 13.7 KB · `app-components.css` 28.3 KB · `app-improvements.css` 15.8 KB
**Macros defined in atoms.html (18):** page_header · metric_card · kpi_strip · status_pill · status_pill_for · empty_state · report_source_footer · loading_state · skeleton_section · entity_link · filter_toolbar · data_table · row_actions · alert_row · stepper · tooltip · flash_toast · combo_field
**Adoption (this session):** skeleton_section 41 templates · empty_state 26 · status_pill 19 · page_header 19 · combo_field 18 · report_source_footer 14 · metric_card 9 · alert_row 3 · entity_link 2 · **stub-only:** kpi_strip 1, filter_toolbar 1, data_table 1, row_actions 1, stepper 1, tooltip 1, loading_state 1 (these need `{% call %}` block refactor)
**P0 defects fixed:** D1 native date → `<ui-date>` ✅ · D4 slug names → `fmt.entity_name()` (65 refs) ✅ · D5 bilingual pedido status ✅ · D6 stock-preview 500 ✅ · D8 /riesgos CTA ✅ · D10 /bank empty state ✅ · D12 audit confirm modal ✅ · D16 date format drift ✅ (8/18)
**P0 defects remaining:** D2 loading skeletons (39 pages) · D3 currency drift (mostly fixed) · D7 /dashboard decision · D9 /vs-mercado data layer · D13 empty-state counts · D14 toast feedback · D15 0 vs — · D17 native selects · D18 orphan text

---

## Architectural blueprint (NEW — operational triad)

**Source:** Gemini UX/UI QA Review (paste received 2026-09-29) — covers `pedidos_nuevo.html`, `produccion.html`, `eod.html` with strict DOM ordering.

### `pedidos_nuevo.html` — 60/40 Split-Pane POS

**Layout:** `display: grid; grid-template-columns: 2fr 1fr` (`.detail-grid-layout`)

```
┌─────────────────────────────────────────────────────────┐
│ h1 "Nuevo Pedido"   [Guardar] [Cancelar]                │  ← page roof
├──────────────────────────────┬──────────────────────────┤
│ Card 1: Cliente picker       │ Card 4: Productos (cart) │
│ Card 2: Entrega (date,time,  │ Running ticket — builds  │
│           delivery zone)     │ vertically as items add  │
│ Card 3: Origen (canal, pago) │                          │
│ Card 5: Notas + toggles      │ Total (Gs.) pinned bottom│
└──────────────────────────────┴──────────────────────────┘
```

**QA invariants:**
- Stock-low warning `"Stock bajo: {qty} {unit}"` renders INSIDE the right pane cart, not at top of page
- Price inputs default to `sale_price_gs` when left at 0
- All cards: `import "_components/atoms.html" as ui`

### `produccion.html` — 3-tier horizontal cascade

```
┌─────────────────────────────────────────────────────────┐
│ ⚠ "Pedidos pendientes para hoy" (full width, urgent)   │  ← Layer 1
├──────────────────────────┬──────────────────────────────┤
│ Card: 🧁 Plan manual     │ Table: Productos a producir  │  ← Layer 2
│ (collapsible details)    │ Source badges (Ventas14d,    │
│                          │ Plantilla, Override input)  │
├──────────────────────────┴──────────────────────────────┤
│ Table: Ingredientes necesarios                          │  ← Layer 3
│ Rows with stock<required → bg-danger-soft + ¡Falta!     │
│ [Guardar overrides] docked below Productos table        │
└─────────────────────────────────────────────────────────┘
```

### `eod.html` — 2-column ritual/data isolation

```
┌─────────────────────────────────────────────────────────┐
│ h1 "🔒 Cierre diario"  [Progreso: 5/9] [Listo badge]     │  ← page roof
├──────────────────────────┬──────────────────────────────┤
│ Left: The Ritual         │ Right: The Hard Data         │
│  - 9-item checklist      │ Card 1: Producción del día  │
│  - Textarea "Notas..."   │   Producto | Plan | Hecho   │
│  - ⚠ "Cerrar el día no  │   Delta: green+/red- (CSS   │
│    cambia el stock"      │   vars --color-success/     │
│    (bold uppercase)      │   --color-danger)           │
│  - [Guardar cierre]      │ Card 2: Reposición (top 5   │
│                          │   low-stock + cost footer + │
│                          │   "Abrir Reponer" link)     │
└──────────────────────────┴──────────────────────────────┘
```

---

## The 30 reusable UX patterns (complete)

**Legend:** ✅ already a reusable component in `_components/` · ⚠ partially implemented · ❌ missing everywhere · 📊 # of pages needing it

| # | Pattern | Pages | Effort | Priority | Status |
|---|---|---|---|---|---|
| 1 | **KPI delta strip** (vs prior period) | 9 | M | P1 | ❌ |
| 2 | **Filter chip rail** | 6 | M | **P0** (defect: chips non-clickable) | ⚠ |
| 3 | **Severity color bar** (left-edge stripe) | 7 | S | P1 | ❌ |
| 4 | **Empty state with onboarding CTA** | 8 | S | **P0** (Riesgos worst) | ⚠ (26 uses) |
| 5 | **In-page "derived tags" block** | 6 | M | P1 | ⚠ |
| 6 | **Side-rail live preview panel** | 5 | M | P1 | ⚠ |
| 7 | **Source attribution at table footer** | 5 | S | P2 | ⚠ (14 uses) |
| 8 | **Sticky top action cluster** | 8 | S | P1 | ❌ |
| 9 | **Tab nav with active underline** | 5 | S | P1 | ⚠ |
| 10 | **Collapsible "ejemplo" callout** | 5 | S | P2 | ❌ |
| 11 | **Inline derived pill cluster** | 6 | S | P2 | ⚠ |
| 12 | **Aggregated KPI strip** (real cards) | 9 | S | **P0** (Wishlist broken) | ⚠ |
| 13 | **Inline warnings** (margin<30%, etc.) | 5+ | S | P1 | ⚠ |
| 14 | **Bulk action bar** | 6 | S | P1 | ❌ |
| 15 | **Inline row actions** | 7 | S | P2 | ⚠ |
| 16 | **Date range presets** | 8 | S | **P0** | ❌ |
| 17 | **Bar chart visualization** | 7 | M | P1 | ⚠ |
| 18 | **Period comparison overlay** | 4 | M | P2 | ❌ |
| 19 | **Drill-down (click row → detail)** | 9 | S | P2 | ✅ |
| 20 | **Print preview** | 5 | S | P2 | ⚠ |
| 21 | **Source attribution footer** (= #7) | — | — | — | — |
| 22 | **Search bar** (page-local) | 8 | S | **P0** | ⚠ |
| 23 | **Saved filters per user** | 6 | M | P2 | ❌ |
| 24 | **Sortable column headers** | 7 | S | P2 | ⚠ |
| 25 | **Sticky header** | 9 | S | P1 | ❌ |
| 26 | **Pagination + jump-to-page** | 6 | S | **P0** | ⚠ |
| 27 | **Tooltip glossary (?) on jargon** | all | S | P2 | ❌ |
| 28 | **Photo placeholder** (initials) | 5 | S | P2 | ❌ |
| 29 | **Drag-drop reorder** | 3 | L | P2 | ❌ |
| 30 | **Required-field markers (*) + save feedback (toast/inline)** | all | S | **P0** | ⚠ |

---

## The 10 architectural macros (complete contracts)

**From `macro-contracts-2026-09-27.md` — 2,363 lines, full spec for each:**

| # | Macro | Signature | Status |
|---|---|---|---|
| 1 | `kpi_tile` | `(label, value, delta=None, delta_direction=None, severity='neutral', icon=None, href=None, tooltip=None, count=None, sublabel=None)` | ⚠ stub (1 use) |
| 2 | `status_pill` | `(label, tone='neutral', icon=None, tooltip=None, href=None, size='md', dot=False)` | ✅ 19 uses |
| 3 | `data_table` | `(columns, rows, row_actions=None, bulk_actions=None, pagination=None, selectable=False, sticky_header=True, empty_state=None, source_attribution=None, sort=None, on_row_click=None)` | ⚠ stub (1 use, needs `{% call %}`) |
| 4 | `filter_chips` | `(chips, active_key=None, date_presets=None, search_input=False, saved_views=None, sync_with_url=True, target_url=None)` | ⚠ stub |
| 5 | `empty_state` | `(icon=None, title, description=None, primary_cta=None, secondary_cta=None, tip=None, illustration=None, size='md')` | ✅ 26 uses |
| 6 | `bulk_action_bar` | `(selected_count, actions, on_clear=None, label_fmt=None)` | ❌ missing |
| 7 | `date_range_presets` | `(presets, target_input_from='#date_from', target_input_to='#date_to', custom_enabled=True, custom_label='Personalizado', on_apply=None, active_key=None)` | ❌ missing |
| 8 | `severity_left_stripe` | `(severity, thickness='4px')` | ❌ missing |
| 9 | `inline_warning` | `(tone, title=None, message=None, action=None, dismissible=False, tooltip=None, icon=None, expand=None)` | ⚠ stub |
| 10 | `confirm_destructive` | `(trigger_label, title, body, confirm_label, cancel_label='Cancelar', confirm_action=None, confirm_method='POST', require_typed_confirmation=False, typed_phrase='ELIMINAR', icon='alert-triangle', trigger_tone='danger', trigger_icon='trash', trigger_variant='button', size='md', secondary_action=None)` | ❌ missing (close to `<ui-confirm-modal>`) |

**Per-macro work estimate (for the 6 stub/missing ones):**
- **kpi_tile** — 1 day: define HTML/CSS, adopt in `inicio.html`, `analisis.html`, `bank.html` (3-4 templates)
- **data_table** — 2 days: refactor as `{% call %}` block macro, migrate `inventario.html` (the gold standard) as reference, then 9 other list pages
- **filter_chips** — 1.5 days: define HTML/CSS, add URL-state sync, migrate to `inventario.html`, `pedidos.html`, `reportes/index`
- **bulk_action_bar** — 1 day: JS for selection state, sync with `data_table` selectable=True, migrate to `inventario`, `proveedores`, `auditoria`
- **date_range_presets** — 1.5 days: chips + custom date range, sync with `<ui-date>` components, 8 pages
- **severity_left_stripe** — 0.5 day: pure CSS wrapper, 7 pages
- **inline_warning** — 1 day: tone variants + action CTA + dismissible, 5+ pages
- **confirm_destructive** — 0.5 day: thin wrapper over `<ui-confirm-modal>`, 1 page (auditoria already uses confirm modal)

**Total macro rollout: 8 days for all 10 to be production-ready across all pages.**

---

## The 219 QoL items (complete — 16 categories)

**From `qol-touches-catalog.md` — 358 lines.** Effort legend: XS (<1h) · S (1–4h) · M (4–8h) · L (1–2 days) · XL (3+ days).

### 1. Micro-interactions (12 items · XS–S)
1.1 Hover lift on cards · 1.2 Button press feedback · 1.3 Skeleton loaders · 1.4 Success checkmark draw · 1.5 Error shake · 1.6 Count-up animation on KPI tiles · 1.7 Empty-state fade-in · 1.8 Focus ring 2px brand-orange · 1.9 Ripple on click · 1.10 Smooth route transitions · 1.11 Pulse on live indicator · 1.12 Subtle row hover highlight

### 2. Keyboard shortcuts (16 items · XS–L)
2.1 ⌘K Command palette (L) · 2.2 / Focus global search · 2.3 ? Show shortcuts modal · 2.4–2.5 g+i / g+v nav · 2.6 ⌘N New (context-aware) · 2.7 ⌘S Save · 2.8 ⌘P Print · 2.9 Esc Close · 2.10 j/k row nav · 2.11 e Edit row · 2.12 Enter submit · 2.13 Tab cycle · 2.14 n/P paging · 2.15 Space toggle · 2.16 ⌘/ Help

### 3. Sound & haptic (12 items · XS–S)
3.1 New-order chime · 3.2 Success chime · 3.3 Error buzz · 3.4 Click sound · 3.5 Stock-low alert · 3.6 Timer alarm (15min) · 3.7 Haptic on mobile · 3.8 Sound toggle · 3.9 Volume slider · 3.10 Per-sound mute · 3.11 Respect prefers-reduced-motion/sound · 3.12 Audio cues for keyboard nav

### 4. Dark mode & theming (10 items · S)
4.1 Light mode toggle · 4.2 System theme auto-detect · 4.3 Custom accent color · 4.4 High-contrast mode · 4.5 Font size scaling · 4.6 Print stylesheet · 4.7 Density toggle (Compact/Comfortable/Spacious) · 4.8 Colorblind-friendly palette · 4.9 Save theme to localStorage · 4.10 Theme picker UI

### 5. A11Y enhancements (14 items · XS–S)
5.1 Skip-to-content link · 5.2 aria-live announcer · 5.3 aria-label on icon buttons · 5.4 Color contrast ≥4.5:1 · 5.5 Keyboard nav for kanban · 5.6 Alt text for photos · 5.7 prefers-reduced-motion · 5.8 `<th scope="col">` · 5.9 Form labels associated · 5.10 Focus trap on modal · 5.11 Status pills text+icon · 5.12 Error summary at form top · 5.13 Required-field aria · 5.14 High-contrast focus ring

### 6. i18n / localization (12 items · S)
6.1 dd/mm/aaaa (Paraguayan) · 6.2 Currency `Gs. 20.000` (period thousands, no decimals) · 6.3 Number formatting `1.234,56` · 6.4 Timezone (Asunción UTC-4) · 6.5 Plural forms · 6.6 Spanish-first copy (kill English leaks) · 6.7 Vos vs infinitive consistency · 6.8 Country code +595 · 6.9 RTL-safe layout · 6.10 Locale weekday/month names · 6.11 Currency placement unified · 6.12 i18n keys extracted

### 7. Performance feedback (12 items · XS–M)
7.1 Skeleton loaders · 7.2 Progress bar for long ops · 7.3 Optimistic UI · 7.4 Lazy-load images · 7.5 Virtualized lists (Inventario, Auditoría, Bank) · 7.6 Infinite scroll on kanban · 7.7 Debounced search 300ms · 7.8 Loading state on Save button · 7.9 Toast with progress · 7.10 Prefetch on link hover · 7.11 Cache static data · 7.12 Service worker offline

### 8. Errors & recovery (14 items · XS–S)
8.1 Toast for transient · 8.2 Banner for persistent · 8.3 Modal for blocking · 8.4 Retry button (exp backoff) · 8.5 Undo for destructive · 8.6 Draft restoration · 8.7 Browser-back warning · 8.8 Breadcrumb · 8.9 Empty-state recovery · 8.10 Error reference code · 8.11 Offline queue · 8.12 "Something went wrong" with action · 8.13 Validation inline + summary · 8.14 Confirmation for destructive

### 9. Onboarding & help (14 items · XS–L)
9.1 First-run modal · 9.2 Empty state with CTA + tip (template pattern) · 9.3 Contextual tooltip on jargon (TACC, HACCP, Escandallo) · 9.4 ? Keyboard shortcuts overlay · 9.5 Video tutorials (60-90s Loom) · 9.6 Sample data generator · 9.7 Glossary page `/glossary` · 9.8 Tooltips on table headers · 9.9 Tour mode · 9.10 "¿Cómo funciona?" expandable · 9.11 First-action success toast · 9.12 Help icon (?) in header · 9.13 "¿No sé qué elegir?" guided Q&A · 9.14 Contextual inline help

### 10. Data freshness (12 items · XS–S)
10.1 "Actualizado hace X min" timestamp · 10.2 Auto-refresh indicator (green pulsing dot) · 10.3 Stale data warning · 10.4 Manual refresh button · 10.5 Cache status badge · 10.6 Last sync timestamp · 10.7 "Ver histórico" link · 10.8 Real-time new-order badge · 10.9 "Datos actualizándose..." subtle indicator · 10.10 Connection status · 10.11 Timestamp tooltip · 10.12 Background polling 60s

### 11. Print & export (14 items · S)
11.1 Print stylesheet · 11.2 PDF export · 11.3 CSV export · 11.4 XLSX export · 11.5 Share via WhatsApp · 11.6 Share via email · 11.7 Copy to clipboard + toast · 11.8 Thermal printer receipt (80mm) · 11.9 Export with date range filter · 11.10 QR code generation · 11.11 Export progress toast · 11.12 Scheduled email reports · 11.13 Print preview · 11.14 Filename convention

### 12. Search & filter (14 items · XS–S)
12.1 Search debounce 300ms · 12.2 Fuzzy match · 12.3 Search highlighting · 12.4 Saved searches · 12.5 Recent searches · 12.6 Advanced filter disclosure · 12.7 Multi-select stay-open · 12.8 Clear all filters · 12.9 Active filter chips · 12.10 URL-state persistence · 12.11 Empty-search-results state · 12.12 Search scope selector · 12.13 Search keyboard nav · 12.14 ⌘K global search

### 13. Table enhancements (15 items · XS–S)
13.1 Column resize · 13.2 Column visibility toggle · 13.3 Density toggle · 13.4 Row striping · 13.5 Sticky header · 13.6 Sticky first column · 13.7 Pagination + jump-to-page · 13.8 Page size selector · 13.9 Sort indicators · 13.10 Hover preview row · 13.11 Bulk select checkboxes · 13.12 Right-click context menu · 13.13 Total row · 13.14 Empty rows · 13.15 Frozen footer

### 14. Forms enhancements (18 items · XS–S)
14.1 Auto-save draft every 5s · 14.2 Browser-back warning · 14.3 Dirty-state indicator · 14.4 Char counters · 14.5 Validation inline + summary · 14.6 Required-field indicators · 14.7 Field-level help tooltips · 14.8 Smart defaults · 14.9 Auto-focus first field · 14.10 Tab order verification · 14.11 Sticky save bar at bottom · 14.12 "Save & add another" · 14.13 Save & duplicate · 14.14 Cancel with confirm · 14.15 Conditional field reveal · 14.16 Number input with stepper · 14.17 Phone auto-format · 14.18 Currency input with thousands separator

### 15. Mobile / touch (15 items · XS–S)
15.1 Touch targets ≥44×44px · 15.2 Swipe-to-delete · 15.3 Swipe-to-advance-status (KDS) · 15.4 Long-press menu · 15.5 Pull-to-refresh · 15.6 Numeric keypad (`inputmode="decimal"`) · 15.7 Camera capture for photos · 15.8 Location-aware fields · 15.9 Bottom-sheet action menu · 15.10 Sticky FAB · 15.11 Tap-to-call / tap-to-WhatsApp · 15.12 Offline mode indicator · 15.13 Safe-area-inset padding · 15.14 Mobile-optimized forms · 15.15 QR scan for ingredient lookup

### 16. Notifications (15 items · XS–S)
16.1 Toast types (success/error/warning/info) · 16.2 Action in toast (Undo/Reintentar) · 16.3 Persistent notification · 16.4 Notification center (last 50) · 16.5 Mute by route · 16.6 Unread count badge · 16.7 Browser notifications (Web Notifications API) · 16.8 Email digest · 16.9 Priority levels (3s/6s/manual) · 16.10 Group rapid-fire toasts · 16.11 Sticky toast with progress · 16.12 Toast positioning · 16.13 Toast a11y · 16.14 "Mark all as read" · 16.15 Filter notification center

**Total effort estimate for QoL:**
- XS items (<1h each): ~80 items × 0.5h = 40h
- S items (1–4h each): ~110 items × 2h = 220h
- M items (4–8h each): ~20 items × 6h = 120h
- L items (1–2 days): ~7 items × 12h = 84h
- XL items (3+ days): ~2 items × 24h = 48h
- **Grand total: ~512h = 64 working days** for ALL 219 items

**Tier-1 priority subset (P0 = ship in next sprint, ~25 items):**
1.1 Hover lift · 1.5 Error shake · 1.8 Focus ring · 1.11 Live pulse · 2.6 ⌘N · 2.7 ⌘S · 2.9 Esc · 4.6 Print stylesheet · 5.4 Contrast ≥4.5:1 · 5.13 Required-field aria · 6.1 dd/mm/aaaa · 6.2 Currency placement · 6.6 Spanish-first · 7.1 Skeleton loaders (39 pages!) · 7.7 Debounced search · 8.1 Toast · 8.13 Validation inline · 9.2 Empty state with CTA · 9.3 Tooltip on jargon · 11.1 Print stylesheet · 12.1 Debounced search · 12.9 Active filter chips · 13.5 Sticky header · 14.6 Required-field indicators · 16.1 Toast types · 16.9 Priority levels

**Tier-1 effort: ~50h = 6 days**

---

## 18 P0 defects (full list)

**From `ux-audit-2026-09-27.md` — 587 lines.**

| # | Defect | Status | Effort |
|---|---|---|---|
| D1 | Native `<input type="date">` — white triangle, English "mm/dd/yyyy" | ✅ FIXED (`<ui-date>` × 24 inputs) | done |
| D2 | No loading skeletons across slow routes | ❌ 39 pages need `.skeleton` adoption | 1 week |
| D3 | Currency drift (`Gs. 75` / `75` / `Gs. 75,00`) | ⚠ Mostly fixed; needs CI lint | 0.5d |
| D4 | Slug display names ("Producto cfaf4b47") | ✅ FIXED (`fmt.entity_name()` × 65) | done |
| D5 | Bilingual status pills (Transiciones in English) | ✅ FIXED | done |
| D6 | pedido_stock_preview 500 error | ✅ FIXED (demo pedido seeded) | done |
| D7 | /dashboard redundant with / and /analisis | ❌ Decision: rescope vs delete | 0.25d |
| D8 | /riesgos no CTA | ✅ FIXED (Agregar riesgo button) | done |
| D9 | /vs-mercado shows 1 row not 17 | ❌ Data-layer SQL fix | 4h |
| D10 | /bank empty state | ✅ FIXED | done |
| D11 | Suppliers duplicate routes | ❌ N/A (URLs 404) | 0 |
| D12 | Audit confirm modal (native confirm) | ✅ FIXED (`<ui-confirm-modal>`) | done |
| D13 | Empty-state counts (no totals) | ❌ Design decision needed | 4h |
| D14 | No toast feedback after save | ❌ Need `<ui-toast>` adoption across saves | 1d |
| D15 | "0" vs "—" ambiguity | ❌ Partial — formatter needed in atoms | 1d |
| D16 | Date format drift | ✅ FIXED (`<ui-date>`) | done |
| D17 | Native select dropdowns | ❌ Refactor to `<ui-combo>` | 1 week |
| D18 | Orphaned text | ✅ N/A | done |

**Fixed: 8/18 (44%) · Remaining: 7 P0 (5 days) + 3 P1**

---

## 12 naming consistency dimensions (canonical)

**From `cross-cutting-consistency-audit.md` — 544 lines.**

| # | Current drift | Canonical choice | Pages affected |
|---|---|---|---|
| 1 | Guardá/Salvar/Guardar | **Guardá** (voseo imperative per AGENTS.md) | all forms |
| 2 | Cliente/Comprador/Customer | **Cliente** | clientes, ventas |
| 3 | Producto/Receta | **Receta** = production, **Producto** = commercial. Don't conflate | recetas, productos |
| 4 | Mostrador/Pickup/Counter | **Mostrador** | ventas, pedidos |
| 5 | Cerrar día/Cierre/EOD | **Cerrar día** | eod, cierre |
| 6 | Comprobante fiscal/Boleta/Factura/Recibo | **Comprobante** | ventas, recibo |
| 7 | ingrediente/Insumo | **Ingrediente** | inventario, recetas |
| 8 | Ver/Abrir/Ver detalle/Detalle | **Ver** | row actions |
| 9 | Categoría/Familia/Etiqueta/Tag | **Categoría** (ingredient), **Etiqueta** (dietary/allergen) | inventario, recetas |
| 10 | Voseo drift (Vos/Tú/Usted) | **Infinitive** (safer per system prompt) | all |
| 11 | English leaks (stock/pending/link/preview) | **Spanish equivalents** | all |
| 12 | Currency placement (`Gs. 20.000` vs `20.000 Gs`) | **`Gs. 20.000`** always | all |

---

## 4 state machines (complete — 769 lines)

**From `state-machines-2026-09-27.md`.**

### §1 Pedido (states + transitions + field requirements + edge cases + anti-states)
- States: BORRADOR · PENDIENTE · CONFIRMADO · EN_PREPARACION · LISTO · ENTREGADO · CANCELADO
- Anti-states: explicit forbids
- Visual: Mermaid state diagram included

### §2 Stock Movement Ledger (7 ledger types)
1. COMPRA · 2. VENTA · 3. PRODUCCION_CONSUMO · 4. PRODUCCION_SOBRANTE · 5. AJUSTE_MANUAL · 6. MERMA · 7. TRANSFERENCIA
- Immutable, append-only
- "Current stock" always derived
- `stock_reservation` companion table
- PRODUCCION_CONSUMO ↔ PRODUCCION_SOBRANTE pairing contract

### §3 Cierre de Caja (5 phases)
- Phase 1: Conteo físico · Phase 2: Reconciliación ventas · Phase 3: Validación arqueo · Phase 4: Sign-off · Phase 5: Generación de libros
- Anti-states: forbid skipping phases

### §4 Bake-loss math
- Core formula + worked example (chipa bag of 30)
- Cost recalculation under bake loss
- Where the bake-loss field lives
- How bake loss flows through the system

---

## 5 personas × ASCII wireframes (932 lines)

**From `role-wireframes-2026-09-27.md`.**

1. **Counter staff** (`/pos`) — environment/login/primary/sub-screens/keyboard map/cognitive-load/anti-patterns
2. **Production-baker** (`/produccion-kitchen`) — environment/login/primary/sub-screens/keyboard map/cognitive-load/anti-patterns
3. **Owner-finance** (`/owner-cockpit`) — KPI dashboard
4. **New user** — onboarding tour
5. **Auditor** — traceability screen

Each persona has: ASCII wireframe (primary + sub-screens), keyboard map, cognitive-load targets, anti-patterns to avoid, anti-patterns audit (lifted from corpus).

---

## Web components to BUILD (vs already shipped)

| Status | Component | Size | Used in |
|---|---|---|---|
| ✅ Shipped | `ui-date` | 12.9 KB | 24 inputs across 13 templates |
| ✅ Shipped | `ui-combo` | 18.6 KB | (partially) |
| ✅ Shipped | `ui-month` | 9.4 KB | inventario_movimientos, reportes |
| ✅ Shipped | `ui-skeleton` | 6.0 KB | (just shipped, adoption pending) |
| ✅ Shipped | `ui-toast` | 7.5 KB | (partial adoption) |
| ✅ Shipped | `ui-confirm-modal` | — | auditoria |
| ❌ To build | `ui-pill-cluster` | ~3 KB | derived tags, status |
| ❌ To build | `ui-kpi-card` | ~4 KB | KPI tiles with delta |
| ❌ To build | `ui-stripe-severity` | ~1 KB | left-edge color bar |
| ❌ To build | `ui-bulk-action-bar` | ~3 KB | bulk select toolbar |
| ❌ To build | `ui-date-range-presets` | ~5 KB | preset chips + custom range |
| ❌ To build | `ui-empty-state` | ~2 KB | icon + CTA + tip |
| ❌ To build | `ui-warning` | ~2 KB | inline_warning tone variants |
| ❌ To build | `ui-stepper` | ~2 KB | wizard steps |
| ❌ To build | `ui-tooltip` | ~1 KB | glossary ? |
| ❌ To build | `ui-fab` | ~2 KB | floating "+ Nuevo" |
| ❌ To build | `ui-bar-chart` | ~6 KB | SVG bar charts (7 pages) |
| ❌ To build | `ui-sparkline` | ~3 KB | KPI delta trend |
| ❌ To build | `ui-photo-placeholder` | ~1 KB | initials in colored box |
| ❌ To build | `ui-status-pill` | ~2 KB | (already exists as macro; consolidate) |

**Total new components to build: ~13 components × ~3 KB avg = ~40 KB new JS, ~10 days effort**

---

## Per-page upgrade worklist (77 pages, complete)

### 6.1 OPERATIONAL (counter, day-to-day)

#### `/` → `inicio.html` (333 LOC, 1 test)
- **5-hat:** Counter needs "Hoy en el mostrador" card · Owner needs KPI delta strip · Baker needs mini-batch-plan · New user needs tour · Auditor needs session chip
- **Top wishlist (5):** Pinned "Hoy en el mostrador" card · Quick-action FAB · Bottom-of-day-close countdown · Recent customer strip · Active-session chip
- **Defects:** no delta arrows on KPIs (P1)
- **Patterns:** #1 (KPI delta) · #12 (KPI strip) · #30 (required-field markers)
- **Code estimate:** 1 day refactor · template 200 LOC change · 1 test file 100 LOC
- **Web components:** `<ui-kpi-card>`, `<ui-fab>`, `<ui-sparkline>`

#### `/ventas` → `ventas.html` (656 LOC, 3 tests — POS, the most-used page)
- **5-hat:** Counter needs category labels on chips · repeat customer indicator · refund/void flow · receipt email/SMS
- **Top wishlist (5):** Category labels on chips · Customer repeat indicator · Discount/coupon · Refund/void flow with audit trail · Receipt email/SMS
- **Defects:** category labels missing (P1)
- **Patterns:** #13 (inline warnings) · #16 (date presets) · #20 (print receipt)
- **Code estimate:** 3 days · template 150 LOC change · 2 test files × 200 LOC
- **Web components:** `<ui-toast>`, `<ui-confirm-modal>`

#### `/pedidos` → `pedidos.html` (297 LOC, 3 tests)
- **5-hat:** Status filter chips · bulk actions · calendar view · channel color-coding · KPI strip
- **Top wishlist (5):** Status filter chips · Bulk actions · Calendar view · Channel color-coding · KPI strip
- **Defects:** no filter chip rail (P0)
- **Patterns:** #2 (filter chips) · #3 (severity stripe) · #14 (bulk action bar) · #26 (pagination)
- **Code estimate:** 2 days · 1 test file × 150 LOC
- **Web components:** `<ui-filter-chips>`, `<ui-bulk-action-bar>`, `<ui-pagination>`

#### `/pedidos/nuevo` → `pedidos_nuevo.html` (213 LOC, 1 test) — **OPS TRIAD**
- **5-hat:** Counter needs fast order intake · Owner needs margin tracking · Baker needs production impact · Auditor needs source attribution
- **Blueprint (60/40 split-pane POS):**
  - Left pane (2fr): Cliente · Entrega · Origen · Notas
  - Right pane (1fr): Live cart with Total pinned bottom
- **Top wishlist (5):** Sticky total bar · Customer balance warning · Recurring orders · Quick-add presets · Production impact preview
- **Defects:** no live total preview (P1) · ⚠ long vertical form fatigue (P0)
- **Patterns:** #6 (live preview panel — RIGHT PANE) · #8 (sticky action cluster) · #30 (required-field)
- **Code estimate:** 4 days · 1 test file × 300 LOC (full e2e)
- **Web components:** `<ui-combo>`, `<ui-warning>`, `<ui-toast>`

#### `/pedidos/{id}` → `pedido_detalle.html` (196 LOC, 0 tests)
- **5-hat:** Need payment recording · status transitions · WhatsApp deep-link · print receipt · production impact
- **Top wishlist (5):** Payment recording · Status transition buttons · WhatsApp deep-link · Print receipt · Production impact mini-card
- **Defects:** "Ver stock antes de cumplir" was 500 (now FIXED)
- **Patterns:** #7 (source attribution) · #13 (inline warnings)
- **Code estimate:** 2 days · 1 test file × 200 LOC (0 currently — test gap)
- **Web components:** `<ui-confirm-modal>`, `<ui-pill-cluster>`

#### `/pedidos/board` → `pedido_board.html` (335 LOC, 66 KB, 0 tests) — kanban — **TEST GAP**
- **5-hat:** Counter needs 5 columns · drag-drop · live timer · channel color · KPI strip
- **Top wishlist (5):** 5 columns · Drag-drop · Live timer · Color by channel · KPI strip
- **Defects:** no drag-drop (P1) · 0 tests
- **Patterns:** #29 (drag-drop) · #12 (KPI strip) · #13 (inline warnings)
- **Code estimate:** 5 days · 1 test file × 400 LOC (test gap)
- **Web components:** `<ui-bar-chart>` (timer viz)

#### `/pedidos/{id}/stock-preview` → `pedido_stock_preview.html` (91 LOC, 1 test) — **WAS 500, now FIXED**
- **Defects:** ✅ FIXED (demo pedido seeded, recipe/ingredient class-import fix)
- **Code estimate:** 0.5 day hardening tests

#### `/eod` → `eod.html` (184 LOC, 1 test) — **OPS TRIAD**
- **Blueprint (2-col ritual/data isolation):**
  - Left: 9-item checklist · "Notas para el turno siguiente" · ⚠ "Cerrar el día no cambia el stock" (bold uppercase) · [Guardar cierre]
  - Right: Producción del día table (Plan · Hecho · Delta CSS var) · Reposición top 5 low-stock + cost footer
- **Top wishlist (5):** Progress bar · Celebration when all checked · Mini-waste widget · Sign-off history · Undo last close
- **Defects:** no progress bar (P1)
- **Patterns:** #13 (inline warnings — disclaimers!) · state-machine-§3 (5 phases)
- **Code estimate:** 3 days · 1 test file × 250 LOC
- **Web components:** `<ui-stepper>`, `<ui-warning>`

#### `/dashboard` → `dashboard.html` (152 LOC, 1 test) — **REDUNDANT**
- **Defect:** duplicates `/` and `/analisis` (P0)
- **Code estimate:** 0.25 day — decide: delete + redirect OR rescope to "Producción KPIs"

### 6.2 CATALOG

#### `/inventario` → `inventario.html` (292 LOC, 4 tests) — **GOLD STANDARD**
- **Patterns:** this IS the reference — extract macros from here
- **Defects:** "Ingredientes 415de24c" slug (P1) · inconsistent icon family (P2)
- **Code estimate:** 2 days to extract macros + add filter chips + bulk action bar

#### `/inventario/nuevo` and `/inventario/{id}/editar` → `inventario_form.html` (144 LOC, 2 tests) — **GOLD STANDARD**
- **Patterns:** #1 (KPI) · #6 (live preview) · #7 (source attribution)
- **Defects:** native date picker (FIXED) · no live cost preview (P1)
- **Code estimate:** 2 days

#### `/inventario/{id}` → `ingrediente_detalle.html` (387 LOC, 0 tests) — 4-quadrant
- **Defects:** Pronóstico `(sin consumo reciente)` no CTA (P0) · `—` for días restantes (P0)
- **Patterns:** #5 (derived tags — already good)
- **Code estimate:** 2 days · 1 test file × 150 LOC

#### `/inventario/{id}/movimientos` → `inventario_movimientos.html` (82 LOC, 0 tests)
- **Defects:** empty state CTA missing entries
- **Patterns:** #1 (KPI delta) · #2 (chips) · #16 (date presets)
- **Code estimate:** 1.5 days

#### `/productos` → `productos.html` (579 LOC, 0 tests)
- **Defects:** D3 currency drift (mostly FIXED) · prime cost > 100% amber not red (P1) · D2 action button (FIXED)
- **Patterns:** #2 (filter chips) · #11 (pill cluster) · #12 (KPI)
- **Code estimate:** 2 days · 1 test file × 200 LOC

#### `/productos/nuevo` and `/productos/{id}/editar` → `producto_form.html` (508 LOC, 0 tests)
- **Defects:** no live margin preview (P1)
- **Patterns:** #6 (live preview) · #5 (derived tags)
- **Code estimate:** 2 days · 1 test file × 250 LOC

#### `/recetas` → `recetas.html` (270 LOC, 6 tests, 53 tests passing) — **JUST SHIPPED Foto + Dificultad**
- **Patterns:** #2 · #24 (sortable) · #11 (Sin-TACC pill)
- **Code estimate:** 1.5 days for filter chips + sort

#### `/recetas/nueva` and `/recetas/{id}/editar` → `receta_form.html` (1,149 LOC, 0 tests) — **MOST COMPLEX FORM**
- **Defects:** Escandallo total = Gs. 0 (server-side fix) · CSRF token missing
- **Patterns:** #6 (live preview — already implemented)
- **Code estimate:** 5 days (the hardest template) · 1 test file × 400 LOC

#### `/recetas/{id}` → `receta_detalle.html` (329 LOC, 0 tests)
- **Patterns:** #5 (pill cluster) · #20 (print prep sheet)
- **Code estimate:** 2 days

### 6.3 PRODUCTION

#### `/produccion` → `produccion.html` (452 LOC, 1 test) — **OPS TRIAD**
- **Blueprint (3-tier cascade):**
  - Layer 1 (full-width urgent banner): "Pedidos pendientes para hoy"
  - Layer 2 (2-col grid): Plan manual (collapsible) | Productos a producir (with Source badges)
  - Layer 3 (full-width): Ingredientes necesarios (rows with stock<required → bg-danger-soft + ¡Falta! badge)
- **Defects:** day cards show one recipe by default (P1)
- **Patterns:** #29 (drag-drop) · #12 (KPI strip) · state-machine-§2 (stock ledger)
- **Code estimate:** 4 days · 1 test file × 300 LOC

#### `/produccion-planner` → `planner.html` (115 LOC, 1 test)
- **Patterns:** #6 (preview panel) · #20 (print)
- **Code estimate:** 1.5 days

#### `/reorder` → `reorder.html` (184 LOC, 2 tests)
- **Defects:** "sin proveedor" should be red not italic (P1)
- **Patterns:** #3 (severity) · #7 (source attribution) · #14 (bulk)
- **Code estimate:** 1.5 days

### 6.4 ORDERS (additional)

#### `/pedidos/publico/{token}` → `pedido_publico.html` (128 LOC, 0 tests)
- **Code estimate:** 0.5 day (minimal read-only view)

#### `/wishlist` → `wishlist.html` (71 LOC, 1 test)
- **Defects:** "Gs. 50,000,000" plain text broken (P0)
- **Patterns:** #4 (empty state) · #12 (KPI)
- **Code estimate:** 0.5 day

#### `/shopping-list` → `shopping_list.html` (124 LOC, 1 test)
- **Patterns:** #1 · #7 · #16
- **Code estimate:** 0.5 day

### 6.5 BANK / FINANZAS

#### `/bank` → `bank.html` (274 LOC, 4 test files, 61 tests) — **HARDENED**
- **Code estimate:** 1 day for KPI delta strip + bulk reconciliation

#### `/reportes` → `reportes.html` (30 LOC, 0 tests) — index
- **Defects:** 14 cards in flat grid (P1)
- **Patterns:** #9 (tabs) · #22 (search) · #7 (source)
- **Code estimate:** 1 day

#### All 12 `/reportes/*` sub-routes (12 templates, ~1.1K LOC total)
- **All need:** D3 format_gs audit · #16 date presets · #7 source attribution · #22 search
- **Code estimate:** 3 days · 1 test file × 250 LOC (covers all 12)
- **Per-page effort:** S each

#### `/analisis` → `analisis.html` (250 LOC, 2 tests)
- **Defects:** rotation block empty state no CTA (P0)
- **Patterns:** #4 · #17 (bar chart) · #3 (severity)
- **Code estimate:** 1.5 days

#### `/riesgos` → `riesgos.html` (63 LOC, 0 tests) — **WORST EMPTY STATE**
- **Defects:** renders only summary strip (P0)
- **Patterns:** #4 · #2 · #14
- **Code estimate:** 1 day

#### `/auditoria` → `auditoria.html` (167 LOC, 2 tests)
- **Defects:** chips non-clickable (P0) · no export (P1)
- **Patterns:** #2 (fix defect) · #3 · #7 · #20
- **Code estimate:** 1.5 days

### 6.6 CUSTOMERS / SUPPLIERS

#### `/clientes` → `clientes.html` (199 LOC, 1 test)
- **Defects:** D2 (P2), D5 (P1)
- **Patterns:** #2 · #5 (0 vs —) · #24
- **Code estimate:** 1 day

#### `/clientes/{id}` → `cliente_detalle.html` (137 LOC, 0 tests)
- **Defects:** no action buttons (P1)
- **Patterns:** #5 (4-quadrant) · #8 (sticky)
- **Code estimate:** 1 day

#### `/clientes/{id}/editar` → `cliente_editar.html` (54 LOC, 0 tests)
- **Patterns:** #8 · #30
- **Code estimate:** 0.5 day

#### `/suppliers` → `suppliers.html` (77 LOC, 1 test)
- **Patterns:** #2 · #12 · #14
- **Code estimate:** 1 day

#### `/supplier/nuevo` → `supplier_form.html` (48 LOC, 0 tests)
- **Patterns:** #8 · #10 (ejemplo)
- **Code estimate:** 0.5 day

#### `/supplier/{id}/orders` → `supplier_orders.html` (85 LOC, 0 tests)
- **Patterns:** #22 · #16
- **Code estimate:** 0.5 day

### 6.7 PRICING / BENCHMARKS

#### `/pricing` → `pricing.html` (54 LOC, 0 tests)
- **Patterns:** #4 · #12 · #2
- **Code estimate:** 0.5 day

#### `/vs-mercado` → `benchmarks.html` (108 LOC, 0 tests) — **DATA BUG**
- **Defect:** shows 1 row not 17 (P0)
- **Patterns:** #3 · #4
- **Code estimate:** 0.5 day (data layer)

#### `/vs-mercado/{id}/editar` → `benchmark_edit.html` (97 LOC, 0 tests)
- **Patterns:** #8 · #30
- **Code estimate:** 0.5 day

### 6.8 INSIGHTS (8 pages × ~40 LOC each)

All 8 insight pages are minimal placeholders:
- `insight_stock.html` · `insight_margenes.html` · `insight_margenes_detalle.html` · `insight_afinidades.html` · `insight_demand.html` · `insight_food_cost.html` · `insight_freshness.html` · `insight_price_impact.html`
- **Patterns:** #12 (KPI) · #17 (bar chart) · #18 (period comparison)
- **Code estimate:** 4 days (8 pages × 0.5 day) · 1 test file × 200 LOC

### 6.9 WASTE / SETTINGS / USERS / MISC

#### `/merma` → `merma.html` (264 LOC, 1 test) — exemplary ejemplo
- **Patterns:** #9 (tabs) · #1 · #3
- **Code estimate:** 1 day

#### `/settings` → `settings.html` (747 LOC, 1 test) — 4 tabs — **LONGEST PAGE**
- **Defects:** P0 first 3 tabs make page 3125px tall · Save at bottom · no tooltips
- **Patterns:** #8 (sticky actions) · #27 (tooltips)
- **Code estimate:** 2 days (sticky TOC)

#### `/settings/catalog` → `settings_catalog.html` (956 LOC, 1 test) — biggest by bytes
- **Code estimate:** 2 days

#### `/users` → `users.html` (211 LOC, 0 tests)
- **Patterns:** #2 · #8
- **Code estimate:** 1 day

#### `/login` → `login.html` (163 LOC, 1 test)
- **Patterns:** minimal — just a11y
- **Code estimate:** 0.5 day

#### `/excel` → `excel.html` (140 LOC, 3 tests)
- **Patterns:** #16 · #22
- **Code estimate:** 0.5 day

#### `/guia` → `guia.html` (13 LOC) — VERY MINIMAL
- **Defects:** no search (P1)
- **Patterns:** #22
- **Code estimate:** 1 day

#### `/recibo` → `recibo.html` (144 LOC, 0 tests)
- **Patterns:** #20
- **Code estimate:** 0.5 day

#### `/ventas/historial` → `ventas_historial.html` (180 LOC, 1 test)
- **Patterns:** #2 · #5
- **Code estimate:** 1 day

#### `/creditos` → `creditos.html` (35 LOC, 0 tests)
- **Patterns:** #12 · #16
- **Code estimate:** 0.5 day

#### `/combo-smoke` → `dev_combo_smoke.html` (73 LOC, 0 tests) — dev
- **Code estimate:** skip

#### `/ops/status` → `ops_status.html` (48 LOC, 0 tests)
- **Code estimate:** 0.5 day

### 6.10 ORPHAN / DEAD TEMPLATES

- `base.html` (309 LOC) — parent template, NOT orphan
- `delivery_zones.html` (38 LOC) — redirects to `/settings`
- `produccion_calendario.html` (25 LOC) — orphan, investigate

---

## Estimated totals (the complete picture)

| Category | Count | Effort |
|---|---:|---:|
| Pages upgraded (all 77) | 77 | ~75 days |
| Macros completed (6 stub/missing) | 6 | ~8 days |
| Web components built (13 new) | 13 | ~10 days |
| QoL Tier-1 shipped (25 items) | 25 | ~6 days |
| P0 defects fixed (7 remaining) | 7 | ~5 days |
| New tests written | ~6,500 LOC | ~6 days |
| Total (all-in) | | ~110 days |

**Realistic 2-week sprint (top priorities, ~12 days):**
1. Complete `data_table`, `filter_chips`, `bulk_action_bar` macros (3 days)
2. Build `<ui-kpi-card>`, `<ui-pill-cluster>`, `<ui-stripe-severity>`, `<ui-bar-chart>` (4 days)
3. Roll out macros to 6 P0 pages: inventario, productos, recetas, pedidos, clientes, auditoria (3 days)
4. Fix 7 remaining P0 defects (2 days)
5. Tests for new components + e2e for operacional triad (3 days × parallel)
6. Deploy + verify on VPS (1 day, with `--no-cache` build)

---

## Open questions (need Ivan's call before next sprint)

1. **Should `/dashboard` be deleted?** Redundant with `/` and `/analisis`.
2. **Where should "today" KPIs live?** `/` actionable vs `/analisis` strategic?
3. **Should recetas be primary entity?** Currently productos + recetas are siblings.
4. **Canonical filter rail pattern?** Currently 2 different patterns.
5. **Should `/riesgos` ship before production?** Currently renders nothing.
6. **`/delivery-zones` and `/produccion-calendario`** — dead routes or active but unlinked?
7. **CI gate for format_gs?** Add lint step that fails if `Gs\. {{` appears without filter?
8. **Theme preference?** Stick with dark-only or add light mode (10-item QoL category 4)?
9. **Light-mode toggle complexity** — affects 13 web components' CSS
10. **Service worker / PWA** (QoL 7.12) — invest in offline mode?

---

## Lessons / pitfalls

1. **Docker build cache gotcha** — `app/` changes may be served from cached COPY layer. Always `docker build --no-cache` + verify by exec'ing. (Saved to `sazon-rms-deploy-flow` skill.)
2. **SQLite rejects `ADD COLUMN IF NOT EXISTS`** — use inspector-based try/except.
3. **Tag algebra EN→ES** — normalize at read boundary + migration v60.
4. **Migration data steps need fresh code** — re-run manually if data is stale.
5. **`receta_form.html` is 1,149 LOC** — any change needs e2e `test_e2e_un_dia_en_la_panaderia.py`.
6. **Test investment correlates with audit depth** — `pedido_board` has 0 tests despite being 66 KB.
7. **Format drift invisible in unit tests** — D3 only catches in screenshot review. Add CI lint rule.
8. **Web components use CSS Custom Properties** — never hardcode colors, always `var(--color-*)`.
9. **Jinja `{% call %}` blocks** — needed for `data_table`, `filter_chips`, `bulk_action_bar` (skip-these-stub-only macros).
10. **`<ui-date>` adoption worked** — 24 inputs in 13 templates converted without regressions.

---

## Appendix A — File locations

- **This document:** `/opt/data/profiles/ivan/scratch/sazon-app-work/docs/upgrades/2026-09-29-UX-UPGRADE-PLAN.md`
- **Source audits:** `/tmp/designer-drop/*.md` (14 files, 19,260 lines total)
- **Bundle with screenshots:** `/tmp/sazon-ux-audit-drop-2026-09-27.zip` (9.5 MB)
- **Existing atoms.html:** `app/templates/_components/atoms.html` (18 macros)
- **Web components:** `app/static/ui-{date,combo,month,skeleton,toast,confirm-modal}.js`

## Appendix B — Test coverage gaps (top 10)

| Page | LOC | Tests | Gap |
|---|---:|---:|---:|
| `pedido_board.html` | 335 | **0** | HIGHEST — kanban with no tests |
| `receta_form.html` | 1,149 | **0** | HIGHEST — most complex form |
| `receta_detalle.html` | 329 | **0** | high |
| `settings_catalog.html` | 956 | 1 (low LOC) | high |
| All 8 `insight_*` pages | ~340 | **0** | high |
| `pedido_detalle.html` | 196 | **0** | high |
| `pedido_publico.html` | 128 | **0** | medium |
| `inventario_movimientos.html` | 82 | **0** | medium |
| `users.html` | 211 | **0** | medium |
| `recibo.html` | 144 | **0** | medium |

**Heaviest tested pages:**
- `bank.html` — 4 test files, 61 tests
- `recetas.html` — 6 test files, 53 tests (just shipped)
- `inventario.html` — 4 test files, ~620 LOC
- `pedidos.html` — 3 test files, ~340 LOC

---

*End of plan. 77 pages × 30 patterns × 10 macros × 219 QoL items × 18 P0 defects × 12 naming dimensions × 4 state machines × 5 personas × ops triad blueprint. ~110 days all-in, ~12 days for 2-week priority sprint.*