# Sazón — Complete QOL Touches Catalog

**Compiled by:** Senior UX/UI Principal
**Date:** 2026-09-27
**Source audits:** `audit-batch2-prod.md` (14 pages · production/recipes), `audit-batch3-reports.md` (14 pages · compras/reportes/admin), `design-plans-2026-09-27.md` (76 pages · consolidated personal review)
**Scope:** 16 categories · 8+ items per category · all vanilla JS / CSS / HTML — no framework lock-in
**Effort legend:** XS = <1h · S = 1–4h · M = 4–8h · L = 1–2 days · XL = 3+ days

---

## 1. MICRO-INTERACTIONS

| # | Item | Where it applies | Implementation hint | Effort |
|---|---|---|---|---|
| 1.1 | **Hover lift on cards** (transform: translateY(-2px) + shadow grow) | All KPI tiles (Inicio, Inventario, Producción, Pedidos, Compras, Reportes) | `transition: all 150ms ease; :hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,.12); }` | XS |
| 1.2 | **Button press feedback** (scale 0.97 + inset shadow) | Every primary CTA (Guardar, Crear pedido, Confirmar, Reponer) | `:active { transform: scale(.97); box-shadow: inset 0 2px 4px rgba(0,0,0,.15); }` | XS |
| 1.3 | **Skeleton loaders** (not spinners) for tables, KPI tiles, kanban cards | Inicio, Inventario list, Pedidos board, Producción | `.skeleton { background: linear-gradient(90deg, #1f2937 0%, #2d3748 50%, #1f2937 100%); background-size: 200% 100%; animation: shimmer 1.5s infinite; }` | S |
| 1.4 | **Success checkmark draw animation** (SVG path stroke-dashoffset) | Toast confirmations on save, on stock adjust, on pedido confirm | Inline SVG + `stroke-dasharray: 100; stroke-dashoffset: 100; animation: draw 400ms ease-out forwards;` | S |
| 1.5 | **Error shake** (translateX ±3px 3x) on validation failure | All forms (ingredient create/edit, order new, recipe edit, supplier new) | `.shake { animation: shake 200ms; } @keyframes shake { 0%,100% { transform: translateX(0); } 25%,75% { transform: translateX(-3px); } 50% { transform: translateX(3px); } }` | XS |
| 1.6 | **Count-up animation on KPI tiles** (number animates 0 → value) | All KPI tile values (Inicio ventas, Inventario valor, Pedidos count) | `requestAnimationFrame` loop with `easeOutCubic` — 800ms total | S |
| 1.7 | **Empty-state fade-in** (opacity 0→1 + slideUp 8px) | Every empty-state card (Proveedores, Riesgos, Wishlist, Bank, Auditoría, Movimientos) | `@keyframes fadeUp { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }` | XS |
| 1.8 | **Focus ring 2px brand-orange + 2px offset** (visible on all interactive elements) | Every button, input, select, link, action icon | `:focus-visible { outline: 2px solid #f97316; outline-offset: 2px; }` — use `focus-visible` not `:focus` to avoid mouse-click rings | XS |
| 1.9 | **Ripple on click** for primary buttons (Material-style) | Guardar, Crear, Confirmar, Reponer | JS to spawn absolutely-positioned span from click coords, animate scale+opacity | S |
| 1.10 | **Smooth route transitions** (fade old content out, new in 200ms) | All page navigations | View Transitions API where supported, fallback `.route-out { opacity: 0 } .route-in { animation: fadeUp 200ms; }` | M |
| 1.11 | **Pulse on live indicator** (green dot pulsing every 2s) | KDS auto-refresh badge, "live" timestamps, websocket connection | `@keyframes pulse { 0%,100% { opacity: 1 } 50% { opacity: .4 } }` | XS |
| 1.12 | **Subtle row hover highlight** on table rows (bg tint, no full-color) | Inventario list, Pedidos board, Auditoría, Reorder, Bank, Wishlist | `tr:hover { background: rgba(255,255,255,.03); transition: background 100ms; }` | XS |

---

## 2. KEYBOARD SHORTCUTS

| # | Item | Where it applies | Implementation hint | Effort |
|---|---|---|---|---|
| 2.1 | **⌘K / Ctrl+K → Command palette** (search anything: pages, ingredients, products, suppliers, orders) | Global — opens overlay from any page | Listen for `(meta\|ctrl)+k`; prevent default; show modal with input + filtered result list | L |
| 2.2 | **/ → Focus global search** (currently the magnifier in header) | All pages with the search trigger | `if (e.key === '/' && !['INPUT','TEXTAREA'].includes(e.target.tagName)) { e.preventDefault(); searchInput.focus(); }` | XS |
| 2.3 | **? → Show shortcuts modal** | Global | `if (e.key === '?' && !e.shiftKey) { e.preventDefault(); showShortcutsModal(); }` | S |
| 2.4 | **g+i → Navigate to Inicio (home)** | Global (vim-style two-key sequence) | `let lastG = 0; if (e.key === 'g') lastG = Date.now(); else if (e.key === 'i' && Date.now()-lastG < 500) navigate('/');` for "i" → "inicio" | XS |
| 2.5 | **g+v → Navigate to Ventas** (and similarly g+p=Producción, g+l=Lista de compras, g+r=Reportes, g+a=Auditoría) | Global | Same `g + letter` two-key pattern — map to nav routes | XS |
| 2.6 | **⌘N / Ctrl+N → New** (context-aware: on inventario list → new ingredient; on pedidos → new pedido) | All index pages | `(meta\|ctrl)+n` listener that resolves context from current route | S |
| 2.7 | **⌘S / Ctrl+S → Save** (works on every form) | All forms | Prevent default, trigger form submit; show "Saved ✓" toast | XS |
| 2.8 | **⌘P / Ctrl+P → Print** (uses native print with custom stylesheet) | Detail pages (pedido, receta, ingrediente) | Don't preventDefault; rely on `@media print` CSS | XS |
| 2.9 | **Esc → Close modal/cancel editing** | All modals, dropdowns open, command palette open | `if (e.key === 'Escape') closeTopmostOverlay();` | XS |
| 2.10 | **j / k → Next / previous row** in tables (vim-style) | All list pages (Inventario, Auditoría, Reorder, Pedidos, Bank) | Track focused row, move with `j`/`k`; add `tabindex="0"` to `<tr>` | S |
| 2.11 | **e → Edit focused row** (when on Inventario/Receta/Supplier list) | All editable entity lists | When row is focused via j/k, `e` opens edit modal/page | XS |
| 2.12 | **Enter → Submit form** + **Shift+Enter → newline in textarea** | All forms | Default form behavior — just verify it works on every form | XS |
| 2.13 | **Tab/Shift+Tab → Cycle focus** (with visible ring, skip invisible elements) | All pages | Native behavior — ensure `tabindex` order is logical | XS |
| 2.14 | **n → Next page** / **P → Previous page** in pagination | All paginated lists (Inventario, Auditoría, Bank, Wishlist) | Listen when not in input | XS |
| 2.15 | **Space → Toggle** (Comprado in shopping list, En preparación in KDS) | Shopping list rows, KDS cards | Toggle current row's checkbox / advance status | XS |
| 2.16 | **⌘/ → Toggle help overlay** (alternative to ?) | Global | Same as 2.7 but bound to ⌘/ | XS |

---

## 3. SOUND & HAPTIC

| # | Item | Where it applies | Implementation hint | Effort |
|---|---|---|---|---|
| 3.1 | **New order chime** (subtle ascending bell) when order arrives on KDS | Pedidos board (KDS view) | `new Audio('/sounds/new-order.mp3').play()` triggered by SSE/poll; user toggleable | S |
| 3.2 | **Success chime** on save / create | All forms after successful submit | 200ms 440Hz sine + envelope; `Tone` lib or pre-rendered MP3 | XS |
| 3.3 | **Error buzz** (low 110Hz square, 300ms) on validation failure | Forms when required field empty or invalid | Same as 3.2 with different frequency/waveform | XS |
| 3.4 | **Click sound** (very short, soft tap) on primary button click | All CTAs | `AudioBufferSourceNode` with cached 50ms sample | XS |
| 3.5 | **Stock-low alert sound** when any ingredient crosses below mínimo | Inventario list, Inicio | Trigger when SSE says stock dropped; quiet by default | S |
| 3.6 | **Timer alarm** (3-beep sequence) when KDS order ages > 15min | Pedidos board | SetTimeout from order received time; loud, distinct | S |
| 3.7 | **Haptic feedback on mobile** (Vibration API) on key actions | Mobile version — submit, save, error | `if (navigator.vibrate) navigator.vibrate(50);` on submit; `[100,30,100]` pattern on error | XS |
| 3.8 | **Sound toggle in header** (🔊 Probar sonido button already exists) | Global header | Persist `localStorage.soundEnabled`; check before every `.play()` | XS |
| 3.9 | **Volume slider** (0–100% with mute) | Settings or sound menu | `<input type="range" min="0" max="100">` that sets `Audio.volume` on every Audio | XS |
| 3.10 | **Per-sound mute** (toggle new-order vs timer-alarm separately) | Sound menu | Checkboxes per sound class in localStorage | S |
| 3.11 | **Respect prefers-reduced-motion / prefers-reduced-sound** | All audio triggers | Check `matchMedia('(prefers-reduced-motion: reduce)').matches` and skip | XS |
| 3.12 | **Audio cues for keyboard nav** (subtle tick on j/k) | Power-user tables | Optional toggle; off by default | S |

---

## 4. DARK MODE & THEMING

| # | Item | Where it applies | Implementation hint | Effort |
|---|---|---|---|---|
| 4.1 | **Light mode toggle** (already dark; add light variant) | Global | `:root[data-theme="light"] { --bg: #fff; --fg: #1a1a1a; ... }`; toggle in header | M |
| 4.2 | **System theme auto-detect** (`prefers-color-scheme`) | Global | `matchMedia('(prefers-color-scheme: dark)')` listener updates `data-theme` attribute | XS |
| 4.3 | **Custom accent color** (user picks from 6–8 swatches) | Settings → Appearance | `--accent: var(--user-accent, #f97316);` with swatches (orange, blue, green, purple, pink, teal) | S |
| 4.4 | **High-contrast mode** for accessibility | Global | `:root[data-contrast="high"]` with pure-black bg, white fg, bold borders | S |
| 4.5 | **Font size scaling** (S/M/L) | Global | `--font-scale: 1;` set on `<html>`; `font-size: calc(16px * var(--font-scale))` on body | S |
| 4.6 | **Print stylesheet** (clean B&W, no nav, big fonts, page breaks) | All printable pages (Pedido detail, Receta, Ingrediente detail, Reports) | `@media print { nav, header, .no-print { display: none; } body { background: white; color: black; font-size: 11pt; } .page-break { page-break-before: always; } }` | M |
| 4.7 | **Compact / Comfortable / Spacious density** | All tables (Inventario, Auditoría, Pedidos, Bank) | `.density-compact td { padding: 4px 8px; }` etc., toggled by body attribute | S |
| 4.8 | **Reduce orange** for colorblind users (alternative to orange-as-action) | Global | Optional alt palette where green replaces orange for primary CTAs | S |
| 4.9 | **Save theme preference** to localStorage and apply before paint | Global | Inline script in `<head>` reads localStorage before CSS loads (avoid FOUC) | XS |
| 4.10 | **Theme picker UI** (3-radio: Dark / Light / Auto) | Settings page or header dropdown | Simple `<input type="radio">` group; updates `data-theme` | S |

---

## 5. A11Y ENHANCEMENTS

| # | Item | Where it applies | Implementation hint | Effort |
|---|---|---|---|---|
| 5.1 | **Skip-to-content link** (visible on Tab) | All pages | `<a href="#main" class="skip-link">Saltar al contenido</a>` styled off-screen until focus | XS |
| 5.2 | **aria-live="polite" announcer** for dynamic content (KDS new orders, save success) | Pedidos board, all forms | `<div aria-live="polite" id="announcer" class="sr-only"></div>`; populate on events | S |
| 5.3 | **aria-label on icon-only buttons** (Ver / Editar / Ajustar / Movimientos / Cancelar) | All action icon buttons | `aria-label="Ver ingrediente"` on every `<button>` with no text | XS |
| 5.4 | **Color contrast ≥ 4.5:1** on all text (audit brand orange #f97316 on dark bg #0f172a) | Global | Compute contrast; replace any failing color with WCAG-AA variant | M |
| 5.5 | **Keyboard nav for kanban board** (arrow keys between cards, Enter to advance status) | Pedidos board (KDS) | Roving tabindex; arrow keys move focus across cards | L |
| 5.6 | **Alt text for product/recipe photos** | Receta edit (future photos), Pedido share link | `alt="Foto de medialunas de queso"` — descriptive, not "image1.jpg" | XS |
| 5.7 | **prefers-reduced-motion support** (disable shimmer, count-up, ripple for users who set it) | All animations | `@media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; } }` | XS |
| 5.8 | **`<th scope="col">`** on every table header | All tables (Inventario, Pedidos, Auditoría, Reorder, Bank) | Add scope attribute to every `<th>` | XS |
| 5.9 | **Form labels always associated** (`<label for>` or wrapping) | All forms | Audit and fix any `<input>` without label | XS |
| 5.10 | **Focus management on modal open** (move focus into modal, trap, return on close) | All modals | On modal open: focus first input; Tab cycles within; Esc closes; on close: focus trigger | M |
| 5.11 | **Status pills with text + icon** (not color-only) | All status pills (Pendiente, Confirmado, Cancelado, Listo, Sin stock) | Always pair color with text/icon so colorblind users can distinguish | XS |
| 5.12 | **Error summary at top of form** (list of all validation errors linked to fields) | All forms | On submit failure: show `<div role="alert">3 errores: Nombre requerido, Stock mínimo requerido…</div>` | S |
| 5.13 | **Required-field markers + announce** (`*` visible + `aria-required="true"`) | All forms | `<input required aria-required="true">` + `<span class="req">*</span>` | XS |
| 5.14 | **High-contrast focus ring** (3px solid black + 3px white offset for double-ring) | All focusable elements | `:focus-visible { outline: 3px solid #000; outline-offset: 3px; box-shadow: 0 0 0 5px #fff; }` | XS |

---

## 6. i18n / LOCALIZATION

| # | Item | Where it applies | Implementation hint | Effort |
|---|---|---|---|---|
| 6.1 | **Date format `dd/mm/aaaa`** (Paraguayan convention; currently some say `mm/dd/yyyy`) | All date inputs, all date displays | Centralize via `Intl.DateTimeFormat('es-PY')`; replace any `mm/dd/yyyy` placeholders | M |
| 6.2 | **Currency formatting** (Gs. 20.000 with period thousands separator, no decimals) | All currency displays (Inventario valor, Pedido total, Reorder total) | `new Intl.NumberFormat('es-PY', { style: 'currency', currency: 'PYG', maximumFractionDigits: 0 }).format(value)` | XS |
| 6.3 | **Number formatting** (1.234,56 with comma decimal, period thousands) | All numeric displays (stock 1.000 kg) | `new Intl.NumberFormat('es-PY').format(1.234)` | XS |
| 6.4 | **Timezone awareness** (Asunción UTC-4, no DST) | All timestamps, "Updated X minutes ago" | Use `Intl.DateTimeFormat('es-PY', { timeZone: 'America/Asuncion' })`; never `new Date().toLocaleString()` raw | S |
| 6.5 | **Plural forms** (1 pedido / 2 pedidos / 1 ingrediente / 2 ingredientes) | All count badges | `new Intl.PluralRules('es').select(n)` then map to `un/unos/unas` correctly | S |
| 6.6 | **Spanish-first copy** (eliminate "stock", "pending", "link", "preview" English leaks) | All pages | Define glossary: `stock → existencias`, `pending → pendiente`, `link → enlace`, `preview → vista previa`; run sweep | M |
| 6.7 | **Vos vs infinitive consistency** (pick one — recommend infinitive for safety) | All CTAs (Guardar not Guardá; Editar not Editá) | Standardize on infinitive: "Guardar / Editar / Cancelar / Crear" | XS |
| 6.8 | **Country code formatting** (+595 9XX XXXXX always shown, never 0981112222 bare) | All phone numbers (Cliente, Proveedor, Pedido detail) | Auto-prepend +595 if 9-digit number starting with 9 | S |
| 6.9 | **Right-to-left safe layout** (in case Arabic/Hebrew added later) | Global | Use logical CSS properties: `margin-inline-start` not `margin-left` | L |
| 6.10 | **Locale-aware weekday/month names** (Lunes 27 Sep, not Monday 27 Sep) | All date displays | `Intl.DateTimeFormat('es-PY', { weekday: 'long', day: 'numeric', month: 'short' })` | XS |
| 6.11 | **Currency placement unified** (always "Gs. 20.000", never "20.000 Gs" or "Gs 20.000") | All currency | Set one formatter and use everywhere | XS |
| 6.12 | **Translation strings extracted** (i18n keys for every UI string, even if only ES supported now) | All strings | Move all `<button>Guardar</button>` to `<button>{t('action.save')}</button>` for future-proofing | L |

---

## 7. PERFORMANCE FEEDBACK

| # | Item | Where it applies | Implementation hint | Effort |
|---|---|---|---|---|
| 7.1 | **Skeleton loaders for tables** (instead of "Cargando…" spinners) | Inventario, Pedidos, Auditoría, Bank, Reorder | Render row-shaped gray blocks matching real column widths | S |
| 7.2 | **Progress bar for long ops** (bulk export, PDF generation, CSV download) | Export buttons, plan calculator, batch submit | `fetch()` with stream + `Content-Length` to update progress bar | S |
| 7.3 | **Optimistic UI updates** (mark as Comprado instantly, sync in background, rollback on error) | Shopping list Comprado toggle, KDS status advance, ingredient stock change | Update DOM immediately; on server error revert + toast | M |
| 7.4 | **Lazy-load images** (below-fold photos with `loading="lazy"`) | Receta photos, Ingrediente photos (future) | Add `loading="lazy"` and `decoding="async"` to all `<img>` | XS |
| 7.5 | **Virtualized lists** for >100 rows (Inventario, Auditoría, Bank transactions) | Tables with potential for many rows | Use `IntersectionObserver` to render only visible rows + buffer | L |
| 7.6 | **Infinite scroll on kanban** (load more pending orders as user scrolls) | Pedidos board | IntersectionObserver on sentinel; append next batch | S |
| 7.7 | **Debounced search** (300ms after last keystroke, not on every keystroke) | All search inputs (Inventario, Proveedores, Auditoría) | `let timer; input.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(search, 300); });` | XS |
| 7.8 | **Loading state on Save button** (spinner + "Guardando…" + disabled) | All forms | `<button disabled><span class="spinner"></span> Guardando…</button>` while fetch pending | XS |
| 7.9 | **Toast with progress** (toast shows "Exportando 47/100…" for long ops) | CSV export, PDF export | Stream progress to a persistent toast | M |
| 7.10 | **Prefetch on link hover** (instant navigation) | All `<a>` to other routes | `<link rel="prefetch" href="...">` injected on mouseenter | M |
| 7.11 | **Cache static data** (categories, units, allergens) in memory | Ingredient form, Order form | Fetch once on app boot; reuse from JS object | S |
| 7.12 | **Service worker for offline read-only** (cached last-viewed Inventario, Pedidos) | Global | Register SW; cache API responses with stale-while-revalidate | L |

---

## 8. ERRORS & RECOVERY

| # | Item | Where it applies | Implementation hint | Effort |
|---|---|---|---|---|
| 8.1 | **Toast for transient success/error** (auto-dismiss 4s) | All save actions, validation errors | `<div class="toast">Saved ✓</div>` positioned bottom-right, `aria-live="polite"` | S |
| 8.2 | **Banner for persistent errors** (e.g., "Sin conexión — los cambios se guardarán al reconectar") | Global header | Sticky banner when `navigator.onLine === false` | S |
| 8.3 | **Modal for blocking errors** (confirmation, destructive actions) | Delete ingredient, cancel order, eliminate audit entries | Standard `<dialog>` element with focus trap | S |
| 8.4 | **Retry button on all failed fetches** (exponential backoff: 1s, 2s, 4s) | Every API call | `try { await fetch() } catch { await retry(3) }`; show "Reintentar" button after final fail | S |
| 8.5 | **Undo for destructive actions** (delete ingredient, cancel order, remove shopping list item) | All delete/cancel buttons | After action: toast with "Deshacer (5s)" button; on click, reverse the action | M |
| 8.6 | **Draft restoration** (save form to localStorage every 5s; restore on next visit) | All long forms (New order, Recipe edit, Supplier new, Report config) | On input: serialize to `localStorage.draft.<route>`; on load: check + offer restore | M |
| 8.7 | **Browser back warning** (`beforeunload`) on dirty forms | All forms with unsaved changes | `if (formIsDirty()) { e.preventDefault(); e.returnValue = ''; }` | XS |
| 8.8 | **"Where am I?" breadcrumb** (Inicio › Inventario › Harina 0000 › Movimientos) | All nested pages | Already exists in some pages; standardize + add chevron icons | XS |
| 8.9 | **Empty-state recovery** (when API returns empty: "No tenés proveedores todavía — Agregá el primero") | All list endpoints | Render empty state with primary CTA pointing to /new | XS |
| 8.10 | **Error reference code + copy** (already on 500 page) | All error toasts and pages | Generate `err-<random8>`; show in toast; click to copy | S |
| 8.11 | **Offline queue** (queue failed writes; replay when back online) | All write operations | IndexedDB-backed queue; replay on `online` event | L |
| 8.12 | **"Something went wrong" with action** ("Reintentar · Volver al inicio · Reportar") | All error pages | Always provide 3 actions, never dead-end | S |
| 8.13 | **Validation inline + summary** (red border on field + summary at top) | All forms | On submit: mark invalid fields; show summary card with anchor links | S |
| 8.14 | **Confirmation for destructive actions** (Delete, Cancel, Reset) | All destructive buttons | Native `<dialog>` confirm or custom modal with typed-name confirmation for high-stakes | S |

---

## 9. ONBOARDING & HELP

| # | Item | Where it applies | Implementation hint | Effort |
|---|---|---|---|---|
| 9.1 | **First-run modal** (1–2 screen explainer on first ever visit) | Inicio, or each page once | Detect via `localStorage.onboarded.<route>`; show carousel | M |
| 9.2 | **Empty state with CTA + tip** (template pattern across system) | All empty states (Proveedores, Riesgos, Wishlist, Bank, Auditoría, Movimientos) | Standard `<EmptyState>` component with slots for icon, title, description, primaryCTA, secondaryCTA, tip | S |
| 9.3 | **Contextual tooltip on jargon** (TACC, HACCP, Escandallo, Lote obligatorio, Punto de reorder) | All forms | `<span class="tooltip-trigger">?</span>` with hover/focus popover | S |
| 9.4 | **? → Keyboard shortcuts overlay** | Global (bound to ?) | Modal showing all shortcuts grouped by category | S |
| 9.5 | **Video tutorials** (60-90s Loom/YouTube embeds for top workflows) | Onboarding modal, Help page | `<iframe>` in modal; respect `prefers-reduced-motion` | M |
| 9.6 | **Sample data generator** ("Llená con datos de ejemplo" button on empty pages) | Empty Proveedores, Recetas, Productos | Triggers API to seed 5 sample rows; undoable | M |
| 9.7 | **Glossary page** (`/glossary` with all jargon terms explained) | Help/nav | Single static page with anchor links | S |
| 9.8 | **Tooltips on table column headers** (hover shows definition + example) | Inventario, Pedidos, Auditoría | `title="..."` + custom popover for richer content | XS |
| 9.9 | **Tour mode** (highlighted walkthrough overlay with next/back/skip) | New user onboarding | Spotlight div + popover positioned; 5–7 steps | L |
| 9.10 | **"¿Cómo funciona?" expandable** on each page header | All pages with non-obvious flows (Reorder, Plan producción, Riesgos) | Disclosure pattern: `▶ ¿Cómo funciona?` toggles body | S |
| 9.11 | **Inline success toast on first action** ("🎉 ¡Listo! Ya creaste tu primer proveedor") | First-time actions | Detect via count in localStorage; show celebratory toast | S |
| 9.12 | **Help icon (?) in header** with quick links to Glossary, Shortcuts, Contact | Global header | Persistent `?` icon → opens menu | XS |
| 9.13 | **"No sé qué elegir" guided Q&A** for Reports index | Reportes | Modal with 3-question tree that suggests a report | L |
| 9.14 | **Contextual inline help** ("¿Por qué importa este campo?") | All forms | Subtle info icon next to fields; popover on click | S |

---

## 10. DATA FRESHNESS

| # | Item | Where it applies | Implementation hint | Effort |
|---|---|---|---|---|
| 10.1 | **"Actualizado hace X min"** timestamp on data panels | Inventario, Pedidos board, KDS, Bank | Relative time formatter; update every 30s | S |
| 10.2 | **Auto-refresh indicator** (green pulsing dot, "Live · auto-refresh 30s") | KDS, Bank, Inicio | Already exists on KDS; reuse pattern | XS |
| 10.3 | **Stale data warning** ("⚠ Datos de hace 15min — refrescar") | When fetch older than threshold | Compare `Date.now() - lastFetch`; show banner if > 5min | S |
| 10.4 | **Manual refresh button** (next to auto-refresh indicator) | All auto-refreshing pages | `<button>↻ Refrescar</button>` next to timestamp | XS |
| 10.5 | **Cache status badge** ("Caché local · actualizado 14:30") | Offline-aware pages | Show `localStorage.lastUpdated`; provide "Forzar recarga" | S |
| 10.6 | **Last sync timestamp** for sync operations (Proveedores imported from CSV, Bank transactions imported) | All import endpoints | Display "Última sincronización: 27/09 14:30 — 247 registros" | XS |
| 10.7 | **"Ver histórico" link** on every data panel | Inventario, Proveedores, Recetas | Link to /audit?entity=ingredient&id=X | XS |
| 10.8 | **Real-time new-order badge** (red dot + count) in nav | Global sidebar Pedidos item | SSE/poll Pedidos count; show badge if > 0 | S |
| 10.9 | **"Datos actualizándose..." subtle indicator** | All pages on background refetch | Top-right progress dot while refetching | XS |
| 10.10 | **Connection status indicator** ("🟢 Conectado / 🟠 Reintentando / 🔴 Sin conexión") | Global header | Listen to `online`/`offline` events + fetch retries | S |
| 10.11 | **Timestamp tooltip** (hover "Actualizado hace 3 min" → "27/09/2026 14:30:42") | All relative timestamps | `<time datetime="..." title="...">hace 3 min</time>` | XS |
| 10.12 | **Background polling** (silent refresh every 60s while page is visible) | Inicio, Inventario, Pedidos | `setInterval` + `document.visibilityState` check | S |

---

## 11. PRINT & EXPORT

| # | Item | Where it applies | Implementation hint | Effort |
|---|---|---|---|---|
| 11.1 | **Print stylesheet** (clean B&W, hide nav, big fonts, page breaks) | All printable pages | `@media print { ... }` rules | M |
| 11.2 | **PDF export** (browser print-to-PDF or jsPDF) | Reports, Pedido detail, Receta, Inventario list | `<button onclick="window.print()">Imprimir / PDF</button>` | XS |
| 11.3 | **CSV export** (respecting current filters) | Inventario, Auditoría, Bank, Proveedores, Recetas | Build CSV from current table data; trigger download via Blob + URL.createObjectURL | S |
| 11.4 | **XLSX export** (Excel-compatible, with formatting) | Same as CSV | Use SheetJS (`xlsx` lib) to write workbook with column widths, headers | M |
| 11.5 | **Share via WhatsApp** (deep-link to wa.me with prefilled text) | Pedido detail, Receta, Lista de compras, Reporte | `https://wa.me/?text=${encodeURIComponent(msg)}` opens WhatsApp web/app | XS |
| 11.6 | **Share via email** (mailto: with subject + body) | Pedido detail, Reporte, Lista de compras | `mailto:?subject=...&body=...` | XS |
| 11.7 | **Copy to clipboard** with toast confirmation | Any copyable value (link, ID, hash) | `navigator.clipboard.writeText()`; toast "Copiado ✓" | XS |
| 11.8 | **Print receipt / ticket** (thermal printer friendly, 80mm width) | Pedido detail (for KDS) | `@media print { @page { size: 80mm auto; } }` — narrow format | S |
| 11.9 | **Export with date range filter** (don't dump everything) | All exports | Honor current filter state when generating export | S |
| 11.10 | **QR code generation** (for share links, ingredient labels) | Pedido share link, Inventario detail | Use `qrcode.js` to render to canvas/SVG | S |
| 11.11 | **Export progress toast** ("Generando PDF… 47%") | Long-running exports | Stream progress to a persistent toast | S |
| 11.12 | **Scheduled email reports** (weekly Resumen diario to owner's email) | Reportes | Cron-like setting per report card | L |
| 11.13 | **Print preview before print** | All print actions | `window.print()` already triggers native preview | XS |
| 11.14 | **Export filename convention** (e.g., `sazon-inventario-2026-09-27.csv`) | All exports | `<a download="saskia-<entity>-<date>.<ext>">` | XS |

---

## 12. SEARCH & FILTER

| # | Item | Where it applies | Implementation hint | Effort |
|---|---|---|---|---|
| 12.1 | **Search debounce 300ms** (not every keystroke) | All search inputs | `setTimeout` pattern | XS |
| 12.2 | **Fuzzy match** (typo-tolerant: "harians" finds "Harina") | All search inputs | Fuse.js or custom Levenshtein score | M |
| 12.3 | **Search highlighting** (mark matched substring in result) | Search results | Wrap matched span with `<mark>` | S |
| 12.4 | **Saved searches** (named filters stored per user) | Inventario, Auditoría, Proveedores | Save current filter set as named search; show in dropdown | M |
| 12.5 | **Recent searches** (last 10, persisted) | All search inputs | `localStorage.recentSearches` array | S |
| 12.6 | **Advanced filter disclosure** (collapsible panel with more options) | Inventario, Auditoría, Bank, Proveedores | `▶ Filtros avanzados` toggle | S |
| 12.7 | **Multi-select dropdowns that stay open** for picking multiple values | Inventario (Categoría, Estado, Alérgenos) | Custom dropdown with checkboxes; click-outside closes | S |
| 12.8 | **Clear all filters button** (with active count badge) | All filtered lists | "Limpiar filtros (3)" button when any active | XS |
| 12.9 | **Active filter chips** ("Categoría: Harinas ×") above table | All filtered lists | Show each active filter as removable chip | S |
| 12.10 | **URL-state persistence** (filters in query string for shareable links) | All filterable lists | Read/write `?filter=...` to URL | S |
| 12.11 | **Empty-search-results state** ("No hay coincidencias para 'xyz' — ¿Quisiste decir 'abc'?") | All search results | When 0 results: offer fuzzy suggestion | S |
| 12.12 | **Search scope selector** (Buscar en: Nombre / SKU / Notas / Todos) | Inventario, Proveedores, Clientes | Radio or dropdown above search input | S |
| 12.13 | **Search keyboard nav** (↑↓ to navigate results, Enter to select) | Global command palette, search dropdown | Standard combobox ARIA pattern | M |
| 12.14 | **"Search across all" global** (⌘K) | Global | Already covered in 2.1; reinforce here | L |

---

## 13. TABLE ENHANCEMENTS

| # | Item | Where it applies | Implementation hint | Effort |
|---|---|---|---|---|
| 13.1 | **Column resize** (drag right edge to resize) | Inventario, Auditoría, Bank, Reorder | `<th>` with `resizable` CSS + JS drag handler | M |
| 13.2 | **Column visibility toggle** (hamburger menu → checkboxes per column) | Inventario, Pedidos board, Auditoría | Menu icon in table header; persists per user | M |
| 13.3 | **Density toggle** (compact / comfortable / spacious) | All tables | `.density-compact td { padding: 4px 8px; font-size: 13px; }` etc. | S |
| 13.4 | **Row striping** (zebra: every other row slightly tinted) | All tables | `tr:nth-child(even) { background: rgba(255,255,255,.02); }` | XS |
| 13.5 | **Sticky header** (`position: sticky; top: 0;` on `<thead>`) | All scrolling tables | CSS-only; ensure parent has overflow | XS |
| 13.6 | **Sticky first column** (when table scrolls horizontally) | Pricing matrix, wide reports | `th:first-child, td:first-child { position: sticky; left: 0; background: var(--bg); }` | S |
| 13.7 | **Pagination + jump-to-page** (input "Ir a página N") | All paginated lists | `« ‹ 1 2 [3] 4 5 › »` with input | S |
| 13.8 | **Page size selector** (10 / 25 / 50 / 100 per page) | All paginated lists | `<select>` that triggers re-fetch | XS |
| 13.9 | **Sort indicators** (▲▼ on clickable column headers) | All sortable tables | Add `<span class="sort-arrow">` toggling on click | XS |
| 13.10 | **Hover preview row** (expanded detail in a popover below) | Inventario (last movements), Pedidos (recipe impact) | `<tr class="preview">` injected on row hover | M |
| 13.11 | **Bulk select checkboxes** + toolbar (Ajustar / Archivar / Exportar / Eliminar) | Inventario, Auditoría, Proveedores | Checkbox column + floating action toolbar | M |
| 13.12 | **Right-click context menu** (Editar / Ajustar / Ver historial / Duplicar) | Inventario, Proveedores, Recetas, Pedidos | `contextmenu` event listener → custom menu | M |
| 13.13 | **Total row** at bottom of numeric columns (sum visible) | Reorder (total estimado), Bank (running balance), Auditoría (count) | Compute sums client-side from current page | XS |
| 13.14 | **Empty rows** when filter has no matches ("Sin resultados — ajustar filtros") | All filtered tables | Standard empty row with message | XS |
| 13.15 | **Frozen footer** (totals visible while scrolling) | Tables with totals | Sticky `<tfoot>` like sticky header | S |

---

## 14. FORMS ENHANCEMENTS

| # | Item | Where it applies | Implementation hint | Effort |
|---|---|---|---|---|
| 14.1 | **Auto-save draft every 5s** to localStorage | New pedido, Receta edit, New proveedor, Report config | Serialize form to `localStorage.draft.<route>` | M |
| 14.2 | **Browser back warning** on dirty forms | All forms | `beforeunload` listener | XS |
| 14.3 | **Dirty-state indicator** ("Tienes cambios sin guardar") | All forms | Compare form values to original on input | S |
| 14.4 | **Char counters** next to text fields with limits | Notas, Descripción, Razón social | `<span class="char-count">12/500</span>` updated on input | XS |
| 14.5 | **Validation inline + summary** | All forms | On blur: validate field; on submit: aggregate errors to summary card | S |
| 14.6 | **Required-field indicators** (`*` + asterisk legend) | All forms | `<span class="req">*</span>` after label; footer "Campos requeridos: *" | XS |
| 14.7 | **Field-level help tooltips** ("¿Por qué importa este campo?") | All forms | Info icon → popover with explanation | S |
| 14.8 | **Smart defaults** (Fecha prometida = tomorrow, Hora = 17:00 default) | New pedido | Pre-fill on form open | XS |
| 14.9 | **Auto-focus first field** on form open | All forms | `autofocus` attribute or `input[0].focus()` | XS |
| 14.10 | **Tab order verification** (logical, not random) | All forms | Audit and fix DOM order; use `tabindex` only when needed | XS |
| 14.11 | **Sticky save bar at bottom** (always visible Save/Cancel) | Long forms (New pedido, Receta edit, Inventario) | `position: sticky; bottom: 0;` on footer | S |
| 14.12 | **"Save & add another"** button (common when seeding multiple) | New ingrediente, New proveedor, New producto | Dual-submit: save + reset form vs save + redirect | S |
| 14.13 | **Save & duplicate** for variants | Edit ingrediente → save as new variant | Same form, redirect to new id, show toast | S |
| 14.14 | **Cancel with confirm** if form is dirty | All forms | If `formIsDirty()`, show "Tienes cambios sin guardar. ¿Salir?" | S |
| 14.15 | **Field-level conditional reveal** (e.g., show "Lote" only if "Lote obligatorio" checked) | Forms with dependent fields | `if (cb.checked) { field.style.display = 'block'; }` | XS |
| 14.16 | **Number input with stepper** (+/− buttons) | Cantidad, Tandas, Stock actual | `<input type="number">` with adjacent buttons | XS |
| 14.17 | **Phone auto-format** as user types (`+595 21 123 456`) | Cliente, Proveedor | `input` event → format string | S |
| 14.18 | **Currency input with thousands separator** (1.000,50 → 1000.50) | Precio, Stock value | Format on blur, parse on submit | S |

---

## 15. MOBILE / TOUCH

| # | Item | Where it applies | Implementation hint | Effort |
|---|---|---|---|---|
| 15.1 | **Touch targets ≥ 44×44px** (Apple HIG / Material) | All buttons, links, table actions on mobile | `min-height: 44px; min-width: 44px;` via `@media (pointer: coarse)` | XS |
| 15.2 | **Swipe-to-delete** on list rows (with undo) | Inventario, Proveedores, Shopping list | Touch event handlers; visual feedback (red bg) | M |
| 15.3 | **Swipe-to-advance-status** on KDS cards (right = next status) | Pedidos board | Swipe gesture → optimistic update | M |
| 15.4 | **Long-press menu** (alternative to right-click on mobile) | All entity lists | `touchstart`/`touchend` timer | S |
| 15.5 | **Pull-to-refresh** on scrollable lists | Pedidos board, Inventario | Custom touch handler with threshold | M |
| 15.6 | **Numeric keypad for number fields** (`inputmode="decimal"`) | Cantidad, Tandas, Stock, Precio | `<input inputmode="decimal" pattern="[0-9.,]*">` | XS |
| 15.7 | **Camera capture for ingredient photos** | Inventario edit (future) | `<input type="file" accept="image/*" capture="environment">` | S |
| 15.8 | **Location-aware fields** ("Ubicación: usar mi ubicación actual") | Inventario (estantería), Proveedores (dirección) | `navigator.geolocation.getCurrentPosition()` | S |
| 15.9 | **Bottom-sheet action menu** (alternative to dropdown on mobile) | KDS cards, list row actions | `<dialog>` styled as bottom sheet | M |
| 15.10 | **Sticky FAB** (floating "+ Nuevo" button bottom-right) | Inventario, Proveedores, Pedidos | `position: fixed; bottom: 16px; right: 16px;` with safe-area-inset | XS |
| 15.11 | **Tap-to-call / tap-to-WhatsApp** on phone numbers | Cliente detail, Proveedor detail, Pedido | `<a href="tel:+595...` and `<a href="https://wa.me/595...` | XS |
| 15.12 | **Offline mode indicator** (persistent when offline) | Global header | `navigator.onLine` + service worker | S |
| 15.13 | **Safe-area-inset padding** (notch-aware) | All pages | `padding-bottom: env(safe-area-inset-bottom);` | XS |
| 15.14 | **Mobile-optimized forms** (single column, big inputs, sticky submit) | All forms | `@media (max-width: 640px) { grid-template-columns: 1fr; input { font-size: 16px; } .save-bar { position: sticky; bottom: 0; } }` | S |
| 15.15 | **QR scan for ingredient lookup** | Inventario list, Reorder | `BarcodeDetector` API where available; manual entry fallback | L |

---

## 16. NOTIFICATIONS

| # | Item | Where it applies | Implementation hint | Effort |
|---|---|---|---|---|
| 16.1 | **Toast types** (success / error / warning / info) with distinct color + icon | Global | 4 variants; auto-dismiss 4s; stack top-right | S |
| 16.2 | **Action button in toast** ("Saved ✓ · Deshacer" / "Error · Reintentar") | All action toasts | Render `<button>` inside toast container | S |
| 16.3 | **Persistent notification** (no auto-dismiss, requires click to close) | Critical errors, blocking warnings | Toast with `data-persistent="true"`; user must click ✕ | XS |
| 16.4 | **Notification center** (sidebar with history of last 50 toasts) | Global | Off-canvas panel opened from header bell icon | M |
| 16.5 | **Mute by route** (don't show toasts on KDS during service hours) | Pedidos board, Cocina view | `localStorage.mutedRoutes = ['/pedidos/board']`; check before render | S |
| 16.6 | **Unread count badge** on notification bell | Global header | `<span class="badge">3</span>` updated as toasts appear | XS |
| 16.7 | **Browser notifications** (Web Notifications API for order alerts) | Global | `Notification.requestPermission()` on opt-in; `new Notification('Nuevo pedido')` | S |
| 16.8 | **Email digest** (daily summary to owner's email) | Owner persona | Scheduled job; opt-in | L |
| 16.9 | **Priority levels** (info dismisses in 3s, warning in 6s, error manual) | All toasts | Map type → timeout | XS |
| 16.10 | **Group rapid-fire toasts** ("3 ingredientes actualizados" instead of 3 separate) | Bulk operations | Coalesce identical toasts within 500ms window | S |
| 16.11 | **Sticky toast with progress** ("Sincronizando 47/100…") | Long sync operations | Toast with `<progress>` bar; auto-close on 100% | S |
| 16.12 | **Toast positioning** (top-right by default, configurable) | Global | `localStorage.toastPosition = 'top-right'/'bottom-right'/'top-center'` | S |
| 16.13 | **Toast accessibility** (`role="status"` for info, `role="alert"` for error) | All toasts | Set aria-live based on urgency | XS |
| 16.14 | **"Mark all as read"** in notification center | Notification panel | Clears badge + marks history read | XS |
| 16.15 | **Filter notification center by type** (errors / warnings / success / info) | Notification panel | Tab group at top of panel | S |

---

## Cross-cutting summary

These 16 categories touch every page in the system. Priority implementation order (by impact-per-effort):

1. **Required-field markers + form validation summary** (defect P1 across 14 forms) — addresses many audit defects
2. **Toast notification system** (replaces missing save feedback on 6+ pages)
3. **Skeleton loaders** (replaces static "—" silent failures)
4. **Slug-as-display-name fix** (affects 9 pages — data issue, not QOL, but should ride with this work)
5. **⌘K command palette** (high impact for power users, complements j/k row nav)
6. **Date/currency formatting via Intl** (addresses locale defects)
7. **Skeleton + loading states on Save buttons** (universal pattern)
8. **Auto-save drafts** (prevents data loss — addresses brittle flow on New pedido, Receta edit)
9. **Keyboard shortcut ? overlay** (documents everything once implemented)
10. **Bulk-select toolbar** (Inventario, Auditoría, Proveedores)

A single shared design-system pass implementing items 1–10 would lift the entire system from "functional but friction-heavy" to "delightful daily driver" — directly closing the top persona frustrations: counter speed (optimistic + auto-save), owner visibility (KPIs + freshness), baker clarity (jargon tooltips + skeleton), new-user onboarding (first-run + glossary), auditor traceability (audit panel + drafts).

*End of catalog. ~165 items across 16 categories. All implementable in vanilla JS/CSS/HTML.*