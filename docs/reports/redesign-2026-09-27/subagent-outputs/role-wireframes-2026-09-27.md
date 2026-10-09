# Sazón — Role-Based Wireframes (v1, 2026-09-27)

**Purpose:** Concrete ASCII wireframes for the three canonical operator roles, derived from the audit corpus (`audit-batch2-prod.md`, `audit-batch3-reports.md`, `cross-cutting-consistency-audit.md`) and the role archetypes the founder articulated:

- **Counter Cashier** — speed, touch/barcode, zero menus
- **Production Baker** — wall-mounted tablet, glancable, flour & wet hands
- **Owner / Manager** — laptop, analytical, deep data

**Audience for this doc:** design lead, lead engineer, QA architect. Each role gets: (1) the environment, (2) the canonical `/first-screen` on login, (3) sub-screens, (4) primary-screen ASCII wireframe, (5) cognitive-load targets, (6) anti-patterns.

**Cross-cutting:** All three roles share the same global left rail (`Operación · Catálogo · Compras · Ventas y Clientes · Finanzas · Configuración`) and the same command-bar (`⌘K`), but **the first screen after login, the touch density, the keyboard map, and the default zoom are role-specific**. This doc fixes those.

**Convention for ASCII:**
- Outer frames `╔═╗ ║ ╚═╝`; inner subdivisions `┌─┐ │ └─┘ ├─┤`; `▓` filled tappable; `░` ambient/disabled; `[ 48px ]` = minimum touch target; `(k: …)` = keyboard binding.
- Currency default: `Gs. 20.000` (dot thousand sep, period after `Gs.`, no decimals — matches the dominant canonical pattern from `cross-cutting-consistency-audit.md §1.6`).

---

## Index

1. [Role 1 — Counter Cashier (`/pos`)](#role-1--counter-cashier-pos)
   - 1.1 Environment & devices
   - 1.2 Login → first screen
   - 1.3 Sub-screens
   - 1.4 Primary screen ASCII wireframe
   - 1.5 Sub-screen wireframes (recibo, buscar, historial)
   - 1.6 Keyboard map
   - 1.7 Cognitive-load targets
   - 1.8 Anti-patterns (must not)
   - 1.9 Anti-patterns audit (lifted from corpus)
2. [Role 2 — Production Baker (`/produccion-kitchen`)](#role-2--production-baker-produccion-kitchen)
   - 2.1 Environment & devices
   - 2.2 Login → first screen
   - 2.3 Sub-screens
   - 2.4 Primary screen ASCII wireframe (today's batches)
   - 2.5 Sub-screen wireframes (planner, recipe card, ingredient detail)
   - 2.6 Cognitive-load targets
   - 2.7 Anti-patterns (must not)
3. [Role 3 — Owner / Manager (`/owner-cockpit`)](#role-3--owner--manager-owner-cockpit)
   - 3.1 Environment & devices
   - 3.2 Login → first screen
   - 3.3 Sub-screens
   - 3.4 Primary screen ASCII wireframe (cockpit)
   - 3.5 Sub-screen wireframes (analisis, reportes, pricing, bank, riesgos, auditoria)
   - 3.6 Cognitive-load targets
   - 3.7 Anti-patterns (must not)
4. [Cross-cutting: shared global nav, role resolution, login routing](#cross-cutting)
5. [Acceptance checklist](#acceptance-checklist)
6. [Open questions](#open-questions)

---

# Role 1 — Counter Cashier (`/pos`)

## 1.1 Environment & devices

| Dimension | Target |
|---|---|
| **Device** | 10–13" capacitive touchscreen at the counter (Android tablet or iPad). Wall-mounted or stand. |
| **Secondary I/O** | USB barcode-gun (HID, Enter-terminated); 80mm thermal receipt printer (USB/LAN); payment-terminal bridge (PinPad). |
| **Acoustic** | Loud (customers + kitchen extractor). Visual cues only, no audio. |
| **Touch target** | **Minimum 48×48 px** (primary CTAs 96×96). |
| **Hands** | Wet / sticky / flour-dusted between counter and bakery; gloves possible. |
| **Session** | Continuous 4–9 h shifts; no logout mid-shift. |
| **Failure tolerance** | Offline-queue sales; receipt printer must keep working; payment terminal falls back to standalone. |

## 1.2 Login → first screen

Counter users authenticate with a **4–6 digit PIN** on a numpad. No usernames are typed at the counter — the PIN identifies the operator for the audit log. Three failed attempts require a manager unlock from `/owner-cockpit`.

**Post-login destination:** `/pos` (the sale-entry screen). Always. No role picker — the system knows the role, and for counter users the only sensible first screen is the live sale-entry. After a 1-minute idle, the cashier returns to `/pos`, not the dashboard.

**Bootstrap < 800 ms** from cold cache (PWA service worker pre-warms the most recent product catalog snapshot). The cashier's last 20 sales are pre-loaded in memory for `/ventas/buscar` autocomplete.

## Sub-screens

| Path | Title | Notes |
|---|---|---|
| `/pos` | **Punto de Venta** (default) | Full screen; this is the login destination. No modals. |
| `/pos/pago` | Confirmar pago | Slide-up sheet (≤40% screen height), not a centered modal |
| `/pos/cliente` | Asignar cliente | Slide-in right panel; only when total > `Gs. 100.000` or via `F4` |
| `/ventas/{id}/recibo` | Recibo (printable) | Auto-opens after sale; bottom sheet, auto-dismiss after 6 s |
| `/ventas/buscar` | Buscar venta | Full-screen replace of `/pos`; cart kept in memory |
| `/ventas/historial` | Ventas de hoy | Full-screen replace; read-only |
| `/caja` | Caja (drawer) | Z-close requires manager PIN |
| `/cerrar-turno` | Cerrar turno | Auto-prompt after 9 h idle; manual via `F10→C`; 3-step wizard |
| `/config/impresora` | Configurar impresora | Manager only |

**Why no modals at all:** The cashier never wants their flow interrupted by a centered card with a backdrop. Every dialog is a slide-up sheet or a full-screen replacement. (Source: `audit-batch1` — counter persona, all sections — "anti-pattern: confirmation modals slow line down".)

## 1.4 Primary screen ASCII wireframe — `/pos` (sale entry)

This is the screen the cashier sees for 95% of their shift. One screen, three zones: status (top), search-and-cart (middle, two columns), payment (bottom).

```
╔══════════════════════════════════════════════════════════════════════════════════════════╗
║ STATUS (56px)   ● CONECTADO  ◉ 09:43  ▣ Impresora OK  ⬛ ₲ 4.250.000  ⌘K Buscar  María (caja 1)  [F10] [F9] ║
╠══════════════════════════════════════════════════════════════════════════════════════════╣
║                                                                                            ║
║  SEARCH & SCAN  (left 60%)                     CART  (right 40%)                          ║
║  ┌────────────────────────────────────────┐  ┌────────────────────────────────────────┐  ║
║  │  🔍  Escanear o buscar producto…       │  │  Venta #1432        3 ítems   - ⌫      │  ║
║  │       (cursor blinks here)             │  ├────────────────────────────────────────┤  ║
║  │                                        │  │  Chipa          [−] 1 [+]   Gs. 4.000   │  ║
║  │  ─────────────────────────────         │  │  Pan baguette   [−] 2 [+]   Gs. 12.000  │  ║
║  │  Recently sold (last 60 min)           │  │  Alfajor maic.  [−] 3 [+]   Gs. 10.500  │  ║
║  │  ▓ Chipa                Gs. 4.000      │  ├────────────────────────────────────────┤  ║
║  │  ▓ Pan francés (kg)     Gs. 9.000      │  │  Subtotal                   24.091     │  ║
║  │  ▓ Bizcocho de laranja  Gs. 18.500     │  │  IVA 10% incluido             2.409     │  ║
║  │  ▓ Empanada (un)        Gs. 5.500      │  │  TOTAL                      26.500     │  ║
║  │                                        │  │                              (28 pt)    │  ║
║  │  ─────────────────────────────         │  └────────────────────────────────────────┘  ║
║  │  Categorías (chips, horizontal)        │                                                ║
║  │  ▓ Panificados ▓ Dulces ▓ Salados      │                                                ║
║  │  ▓ Bebidas ░ Sin gluten                │                                                ║
║  └────────────────────────────────────────┘                                                ║
║                                                                                            ║
╠══════════════════════════════════════════════════════════════════════════════════════════╣
║ PAYMENT (96px)                                                                             ║
║  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐                         ║
║  │ COBRAR  ⏎ Enter   │  │ CRÉDITO  F4      │  │ SEPARAR  F5       │                         ║
║  │ (efectivo / mix)  │  │ (cuenta cliente) │  │ (reservar pedido) │                         ║
║  │     [ 96px ]      │  │     [ 96px ]     │  │     [ 96px ]      │                         ║
║  └──────────────────┘  └──────────────────┘  └──────────────────┘                         ║
║  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐                         ║
║  │ DESCUENTO  F6     │  │ DEVOLVER  F7     │  │ CANCELAR  Esc     │                         ║
║  │ (con clave mgr)   │  │ (requiere mgr)   │  │ (carrito actual)  │                         ║
║  │     [ 96px ]      │  │     [ 96px ]     │  │     [ 96px ]      │                         ║
║  └──────────────────┘  └──────────────────┘  └──────────────────┘                         ║
╚══════════════════════════════════════════════════════════════════════════════════════════╝
```

**Zone anatomy:**

- **Status strip (top, 56 px):** always visible. Three colored dots indicate subsystem health: `● CONECTADO` (server), `◉` clock, `▣` printer. Cash-drawer balance shown so cashiers answer "¿cuánto hay en caja?" without leaving `/pos`. Right side: `⌘K` hint, user pill, `F10` (Caja), `F9` (Historial).
- **Search & Scan (left 60%):** search input is the **autofocus** target on screen load. Below: "Recently sold" (last 60 min) — top 4 items almost certainly needed. Below that: horizontal category chips. Tapping a chip filters the recent list + search results. **No dropdowns anywhere** — search is `search-as-you-type` with 80 ms debounce.
- **Cart (right 40%):** vertical scroll. Each row: name, qty, line total, `[ − ] [ qty ] [ + ]`. `[ + ]` and `[ − ]` are equal width (48×48). Trash icon per row (hold 1 s, or `Shift+Del` on the optional keyboard).
- **Payment buttons (bottom, 96 px tall):** six buttons in a 3×2 grid. Each ≥ 96×96 px on tablet, 96 px tall in CSS regardless of width. Primary (`COBRAR`) is orange and shows `⏎ Enter` on the button face. Other five gray with shortcut chip on bottom-right.

**Color semantics:** background white; cart totals 28 pt bold (vs 18 pt body); `● CONECTADO` green (`#10B981`), flips to amber `#F59E0B` when offline-mode (sales queue locally); printer dot green; flips red `#EF4444` when unreachable.

**What you do NOT see on `/pos`:**
- No left navigation rail — only reachable via back-arrow top-left with 3 items: `Caja (F10)`, `Buscar venta (F2)`, `Cerrar turno (F10→C)`. The full six-section nav is **not** visible.
- No settings, no profile menu, no logout button. Logout: long-press user pill 2 s → confirmation sheet.
- No notifications panel. Alerts (stock crítico) are owner's and baker's concern, not the cashier's.

## 1.5 Sub-screen wireframes

### 1.5.1 `/pos/pago` — Confirmar pago (slide-up sheet, bottom 40%)

Triggered by tapping `COBRAR` (or `⏎ Enter`). Slides up over `/pos`. Does **not** replace the cart.

```
                    ╔════════════════════════════════════════════════════════════╗
                    ║                                                            ║
                    ║  Cobrar venta #1432                          [ ✕  Esc ]    ║
                    ║  ─────────────────────────────────────────────────────────  ║
                    ║                                                            ║
                    ║  TOTAL                                   Gs. 26.500        ║
                    ║                                                            ║
                    ║  Recibido:                                                  ║
                    ║  ┌────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────┐    ║
                    ║  │ 5  │ 10 │ 20 │ 50 │ 100│ 200│ 500│1k │2k │5k │Borr│    ║
                    ║  │.000│.000│.000│.000│.000│.000│.000│.000│.000│.000│←  │    ║
                    ║  └────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┘    ║
                    ║                                                            ║
                    ║  ┌──────────────────────────────────────────────┐           ║
                    ║  │     Gs. 30.000                               │           ║
                    ║  │     (teclado numérico)                       │           ║
                    ║  └──────────────────────────────────────────────┘           ║
                    ║                                                            ║
                    ║  Vuelto                                  Gs.  3.500        ║
                    ║                                                            ║
                    ║  ┌────────────────────┐  ┌────────────────────┐             ║
                    ║  │  EFECTIVO    F1    │  │  TARJETA     F2    │             ║
                    ║  │  ⏎ confirmar      │  │  (llama POS)       │             ║
                    ║  │     [ 72px ]       │  │     [ 72px ]       │             ║
                    ║  └────────────────────┘  └────────────────────┘             ║
                    ║  ┌────────────────────┐  ┌────────────────────┐             ║
                    ║  │  TRANSFERENCIA F3  │  │  MIXTO       F4    │             ║
                    ║  │  (comprobante)     │  │  (parte y parte)   │             ║
                    ║  │     [ 72px ]       │  │     [ 72px ]       │             ║
                    ║  └────────────────────┘  └────────────────────┘             ║
                    ║                                                            ║
                    ╚════════════════════════════════════════════════════════════╝
```

- The quick-pick grid (`5.000 … 5.000`) is **denomination chips**, one tap = add to "Recibido". Bills are the most common in Paraguay (₲ 2.000, ₲ 5.000, ₲ 10.000, ₲ 20.000, ₲ 50.000, ₲ 100.000).
- The numeric input shows the live "Recibido" value, not the cambio.
- Cambio (vuelto) appears only after Recibido ≥ Total, in **bold green**.
- `⏎` confirms whichever payment method is highlighted. Default highlight = `EFECTIVO`.
- No "completado" modal: after `⏎`, the sheet auto-dismisses, prints the receipt, and `/pos` is back with an empty cart.

### 1.5.2 `/ventas/{id}/recibo` — Recibo (printable, modal-light bottom sheet)

```
╔══════════════════════════════════════════════════════════════════╗
║  Venta #1432            domingo 27 sep 2026 · 09:43             ║
║  ───────────────────────────────────────────────────────────    ║
║    1 × Chipa                       Gs.   4.000                  ║
║    2 × Pan baguette                Gs.  12.000                  ║
║    3 × Alfajor de maicena          Gs.  10.500                  ║
║  ───────────────────────────────────────────────────────────    ║
║    Subtotal                        Gs.  24.091                  ║
║    IVA 10%                         Gs.   2.409                  ║
║    TOTAL                           Gs.  26.500                  ║
║    Recibido Gs. 30.000   Vuelto    Gs.   3.500                  ║
║    Caja 1 · María G.                                             ║
║  ╔════════════════════════════════════════════════════════╗      ║
║  ║  ¡Gracias por su compra!                              ║      ║
║  ║  Panadería San Roque · RUC 80012345-6                 ║      ║
║  ║  Av. España 1234, Asunción                            ║      ║
║  ║  Tiket: 0001-001432                                    ║      ║
║  ╚════════════════════════════════════════════════════════╝      ║
║                                                                 ║
║  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           ║
║  │ IMPRIMIR │ │REENVIAR  │ │  EMAIL   │ │  CERRAR  │           ║
║  │   F8     │ │ WhatsApp │ │  recibo  │ │   Esc    │           ║
║  └──────────┘ └──────────┘ └──────────┘ └──────────┘           ║
╚══════════════════════════════════════════════════════════════════╝
```

**Why modal-light (bottom sheet, not a centered modal):** the cashier may need to walk away with the printed receipt immediately while the customer waits; the bottom-sheet shape lets them see the next cart start coming in behind it. Auto-dismiss after 6 s.

The `REENVIAR` button opens WhatsApp Web with a pre-filled text containing the receipt link (deep-link to `/ventas/{id}/recibo`).

### 1.5.3 `/ventas/buscar` — Buscar venta (full-screen replace)

```
╔════════════════════════════════════════════════════════════════════════════════════════╗
║  ← Volver a /pos (Esc)                                                                  ║
║  Buscar venta                                                                            ║
║  ┌───────────────────────────────────────────────────────────────────────────────┐    ║
║  │  🔍  ticket, nombre de cliente, o re-escanear código de barras…                │    ║
║  └───────────────────────────────────────────────────────────────────────────────┘    ║
║                                                                                         ║
║  Resultados (8)                                                                         ║
║  ┌─────┬──────────────┬─────────────────┬──────────┬────────────┬────────────────┐    ║
║  │ #   │ Ticket       │ Fecha / hora    │ Cliente  │ Total      │ Acción         │    ║
║  ├─────┼──────────────┼─────────────────┼──────────┼────────────┼────────────────┤    ║
║  │ 1432│ 0001-001432  │ 27/09 09:43     │ (consum) │ Gs. 26.500 │ [Recibo] [↶] │    ║
║  │ 1431│ 0001-001431  │ 27/09 09:38     │ Carlos R.│ Gs. 18.000 │ [Recibo] [↶] │    ║
║  │ 1430│ 0001-001430  │ 27/09 09:35     │ (consum) │ Gs.  4.000 │ [Recibo] [↶] │    ║
║  │ 1429│ 0001-001429  │ 27/09 09:31     │ Ana P.   │ Gs. 12.500 │ [Recibo] [↶] │    ║
║  │ 1428│ 0001-001428  │ 27/09 09:22     │ (consum) │ Gs.  9.000 │ [Recibo] [↶] │    ║
║  └─────┴──────────────┴─────────────────┴──────────┴────────────┴────────────────┘    ║
║  ↶ = revertir venta (requiere PIN de mgr)                                                ║
╚════════════════════════════════════════════════════════════════════════════════════════╝
```

- Search results show 8 rows per page. Default sort: most recent first.
- Re-scan a barcode: the system looks up the most-recent sale that contains that SKU and jumps directly to its detail page.

The cashier uses this to spot voids and recount sales at end-of-shift.

### 1.5.4 `/ventas/historial` — Ventas de hoy (full-screen replace)

```
╔════════════════════════════════════════════════════════════════════════════════════════╗
║  ← Volver a /pos (Esc)                                                                  ║
║  Ventas de hoy · domingo 27 sep 2026                                          [F9]      ║
║                                                                                         ║
║  ┌──────────┬──────────┬──────────┬──────────┬──────────┐                              ║
║  │ Ventas   │ Ticket   │ Promedio │ Efectivo │ Anuladas │                              ║
║  │   82     │ ₲ 1.45M  │ ₲ 17.700 │   56     │    0     │                              ║
║  └──────────┴──────────┴──────────┴──────────┴──────────┘                              ║
║                                                                                         ║
║  Línea de tiempo (cada venta = un punto):                                              ║
║  ┌─────────────────────────────────────────────────────────────────────────────────┐   ║
║  │ 08 ─── 09 ─── 10 ─── 11 ─── 12 ─── 13 ─── 14 ─── 15 ─── 16 ─── 17 ─── 18 ──  │   ║
║  │      ▓ ▓       ▓▓▓    ▓▓▓▓    ▓▓▓▓▓▓▓▓    ▓▓▓▓▓▓▓▓▓▓    ▓▓▓▓▓   ▓▓          │   ║
║  │ ●9:43  ●9:31  ●9:38 ●9:22  ●10:01 ●10:14 ●10:25 ●10:39 ●10:55 ●11:02 ●11:14  │   ║
║  └─────────────────────────────────────────────────────────────────────────────────┘   ║
║  Tabla compacta: Hora · Total · Cliente · Items · Forma de pago · Caja · Recibo         ║
╚════════════════════════════════════════════════════════════════════════════════════════╝
```

- The cashier uses this to spot voids and to recount sales at end-of-shift. Read-only. Owner has richer analytics on `/owner-cockpit`.

### 1.5.5 `/caja` — Caja (drawer balance & Z-close)

```
╔════════════════════════════════════════════════════════════════════════════╗
║  Caja · María G. · caja 1 · turno abierto 09:00                            ║
║  ┌──────────────────────────────────────────────────────────────────────┐  ║
║  │ Apertura     Gs.   500.000  (efectivo inicial, F10 → A)              │  ║
║  │ Ventas hoy   Gs. 1.450.000  (82 ventas)                              │  ║
║  │ - Anuladas   Gs.         0  (0 ventas)                               │  ║
║  │ - Retiradas  Gs.  -200.000  (2 retiros: mgr)                         │  ║
║  │ + Ingresos   Gs.   150.000  (cambio pedido Proveedores)             │  ║
║  │ Esperado     Gs. 1.900.000                                           │  ║
║  │ Contado      Gs.         _  (declarado por cajero)                   │  ║
║  │ Diferencia   Gs.         _                                           │  ║
║  └──────────────────────────────────────────────────────────────────────┘  ║
║  [ Declarar contado ] [ Retiro ] [ Ingreso extra ] [ Cerrar Z (turno) ]    ║
╚════════════════════════════════════════════════════════════════════════════╝
```

- Z-close requires the manager PIN. Closing a shift generates an immutable audit-log entry: `cashier.session.closed` with `{opener, closer, expected, counted, diff}`.

## 1.6 Keyboard map (POS)

| Key | Action |
|---|---|
| `⌘K` / `Ctrl+K` | Global command bar (product search + actions) |
| `⏎ Enter` | Add highlighted product to cart **or** confirm payment on `/pos/pago` |
| `Esc` | Cancel current flow, dismiss slide-up sheet |
| `F1`–`F4` | Pay: cash · card · transfer · mixed (or open `/pos/cliente`) |
| `F5`–`F7` | Hold · Discount (mgr) · Refund (mgr) |
| `F8`–`F10` | Reprint · Today's sales (`/ventas/historial`) · Cash drawer (`/caja`) |
| `Shift+Del` | Delete cart line |
| `Tab` / `←` `→` | Move between cart line qty inputs / categories |
| `*` (numpad) | Multiply qty (e.g., `5*` then enter = 5 of the scanned item) |

## 1.7 Cognitive-load targets

- **0–3 s** to start a sale after a barcode scan (autofocus + Enter adds line).
- **1 tap per action.** Adding to cart = 1 tap (or 1 scan). Changing qty = `[+]` or `[-]` tap. Pay = 1 tap on `COBRAR` + 1 tap on `EFECTIVO`.
- **Zero menus.** All actions direct (button or keyboard). No hamburger, drawer, or overflow `⋮`.
- **Single screen:** `/pos` covers ~95% of the cashier's shift. The other four screens are 1 keypress away.
- **Visible state:** clock, drawer balance, printer status always on screen — no surprises at end of shift.
- **No decisions while the line is moving:** `Recently sold` surfaces the most likely items so the cashier rarely types a search query.

## 1.8 Anti-patterns (must NOT)

- **No modals** — slide-up sheets (≤40%) or full-screen replacements only.
- **No multi-level navigation** — single-path on `/pos`.
- **No text < 18 pt** — body 18 pt; line name 20 pt; totals 28 pt.
- **No dropdowns** — search-as-you-type + chip filters.
- **No hover-only affordances** — touch + keyboard only.
- **No emoji-only indicators** — color + shape + label (color-blind safe).
- **No accidental cancels** — `Esc` requires 2 s hold or confirmation sheet.
- **No "loading…" spinners blocking input** — skeletons or in-place progress.
- **No centered "Are you sure?" popups** — bottom-sheet confirmations; destructive option on the right.

## 1.9 Anti-patterns audit (lifted from corpus)

| # | Source | Defect | How `/pos` fixes it |
|---|---|---|---|
| 1 | `audit-batch3 §3` (P0) | "Guardá" voseo button label | All buttons infinitive: "Cobrar", "Confirmar", "Reimprimir" |
| 2 | `audit-batch2 §4` | Tooltip-heavy precision clicks | Primary actions ≥ 96×96 px; tooltips optional |
| 3 | `cross-cutting §1.1` | Date format drift | Single canonical `dd/mm/yyyy` on cashier-facing screens |
| 4 | `cross-cutting §1.5` | Silent form submissions | Sale = receipt bottom-sheet auto-open + printer sound |
| 5 | `cross-cutting §1.6` | Currency placement drift | All amounts `Gs. 20.000` (dot sep, no decimals) |
| 6 | `audit-batch2 §1` | Tiny green/red bars without axis | Cart-row totals are full text, not visual bars |
| 7 | `cross-cutting §1.7` | Slug-as-display-name | All products MUST have `display_name` set at creation; auto-block on `/pos` |
| 8 | `audit-batch2 §5` | Action-icon inconsistency | Closed icon set: `[ + ] [ − ] [ ✕ ] [ ↶ ] [ ◯ ]` |

---

# Role 2 — Production Baker (`/produccion-kitchen`)

## 2.1 Environment & devices

| Dimension | Target |
|---|---|
| **Primary device** | 10" Android tablet, wall-mounted above the prep table. **Portrait only.** |
| **Backup device** | Printed clipboard (A4); `/recetas/{id}?print=1` produces a print-friendly recipe card. |
| **Touch** | Capacitive; works through flour-covered fingers, struggles with water droplets. Anti-glare matte protector + raised bezel. |
| **Distance** | Baker stands 0.5–2.0 m. Glances, not constant reading. |
| **Hands** | Wet, sticky (dough), oily (butter), flour-covered. |
| **Light** | Warm 3000K kitchen + window daylight above. |
| **Failure tolerance** | Tablet freezes → printed clipboard is canonical. Tablet is an accelerator, not a single point of failure. |

## 2.2 Login → first screen

Baker uses the same **PIN** scheme. On login, system routes to `/produccion-kitchen` — never to a dashboard. Login before 04:00 shows yesterday's leftover batches plus a "Plan de hoy" CTA; after 04:00, only today's. **Bootstrap < 1.2 s** — PWA pre-fetches `/produccion-kitchen` data every 60 s, so the screen is populated before login.

## 2.3 Sub-screens

| Path | Title | When |
|---|---|---|
| `/produccion-kitchen` | Lotes de hoy (default, the first screen) | Always |
| `/produccion` | Tablero de producción (planning board) | "Later" view (vs. `kitchen` which is "now") |
| `/produccion-planner` | Planner semanal | Head baker Sunday-night planning session |
| `/recetas/{id}` | Ficha de receta (print-friendly) | Print target; also reachable from `/produccion-kitchen` |
| `/inventario/{id}` | Detalle de ingrediente (print-friendly) | When batch is Pendiente but ingredient is short |
| `/produccion-kitchen/horno` | Estado del horno | Per-oven state (temp, time remaining, next batch) |

All are full-screen, vertical-recipe-card layouts. The baker **never** sees a modal — dismissing one with flour-covered hands is awkward.

## 2.4 Primary screen ASCII wireframe — `/produccion-kitchen` (today's batches)

```
╔═══════════════════════════════════════════════════════════╗
║  Producción · domingo 27 sep 2026 · 04:18                 ║
║  ───────────────────────────────────────────────────      ║
║                                                            ║
║  ┌────────────────────────────────────────────────────┐    ║
║  │  ▓▓▓▓ PAN FRANCÉS                                │    ║
║  │  Estado: ▰ PENDIENTE    Lote #214                 │    ║
║  │  ─── Ingredientes (descendente por peso) ───       │    ║
║  │   Harina 0000       ████░░░░░  4.5 / 5   kg       │    ║
║  │   Agua             ████████░  2.7 / 3.0 L         │    ║
║  │   Levadura seca    █████░░░░░   80 / 100 g        │    ║
║  │   Sal              ██████░░░░   80 / 100 g        │    ║
║  │  ─── Tiempo ───                                    │    ║
║  │   Amasado    12 min   ✓ listo                      │    ║
║  │   Leudado    90 min   ● en curso                   │    ║
║  │   Horneado   35 min   ░ pendiente                  │    ║
║  │  ╔══════════════════════════════════════════╗      │    ║
║  │  ║  [   EMPEZAR AMASADO   ⏎  ]    [88px]  ║      │    ║
║  │  ╚══════════════════════════════════════════╝      │    ║
║  └────────────────────────────────────────────────────┘    ║
║                                                            ║
║  ┌────────────────────────────────────────────────────┐    ║
║  │  ▓▓▓▓ CHIPAS                                      │    ║
║  │  Estado: ● EN HORNO     Lote #215                  │    ║
║  │  ┌──────────────────────────────────────────┐      │    ║
║  │  │     12 : 34                             │      │    ║
║  │  │     restantes                           │      │    ║
║  │  └──────────────────────────────────────────┘      │    ║
║  │  Horno 2 · 230 °C                                   │    ║
║  │  ╔══════════════════════════════════════════╗      │    ║
║  │  ║   [   SACAR DEL HORNO   ⏎   ]   [88px]  ║      │    ║
║  │  ╚══════════════════════════════════════════╝      │    ║
║  └────────────────────────────────────────────────────┘    ║
║                                                            ║
║  ┌────────────────────────────────────────────────────┐    ║
║  │  ▓▓▓▓ ALFAJOR DE MAICENA                          │    ║
║  │  Estado: ░ PENDIENTE    Lote #216                  │    ║
║  │  Hora planificada: 10:00                            │    ║
║  └────────────────────────────────────────────────────┘    ║
║                                                            ║
║  … (desplazá para más lotes)                              ║
╚═══════════════════════════════════════════════════════════╝
```

**Recipe-card anatomy:**
- **One card per batch.** Cards stacked vertically, time-of-day order (earliest top). Baker scrolls, never paginates.
- **Recipe name** (top, 32 pt, all-caps) — readable from 2 m.
- **Status pill** (`▰ PENDIENTE` / `● EN HORNO` / `✓ LISTO`) with **text + icon + color** (never color alone).
- **Ingredients list** in **descending weight order** — `Harina 4.5 kg`, `Agua 2.7 L`, `Levadura 80 g`, `Sal 80 g`. Each row has a progress bar showing **consumed vs. required**.
- **Time section:** phases (`Amasado`, `Leudado`, `Horneado`), each with duration and current status. Active phase shows circular countdown.
- **Primary CTA** at bottom: `[ EMPEZAR {phase} ⏎ ]` or `[ SACAR DEL HORNO ⏎ ]`. Always 88 px tall.

**Glancability rule:** from 2 m, the baker must see (1) what's next, (2) how long until done, (3) what's at risk. Nothing else matters.

**Color semantics (color-blind safe):**
- Pending: `░` outline only, gray text.
- In progress: `●` filled dot, blue text + animated ring around active phase.
- Done: `✓` check, green text + slight desaturation (card "sinks" visually).
- At-risk (running late): `▲` triangle icon in red + text "Demorado" — never red alone.

## 2.5 Sub-screen wireframes

### 2.5.1 `/produccion-planner` — Planner semanal

This is for the head baker on Sunday night. Larger data density is acceptable because they're sitting at a desk for the planning session (or they printed `/produccion-kitchen/print-week`).

```
╔════════════════════════════════════════════════════════════════════════════╗
║  Planner semanal · semana 39 (22 sep – 28 sep 2026)                       ║
║        LUN     MAR     MIÉ     JUE     VIE     SÁB     DOM                ║
║  04 ── ░░░     ░░░     ░░░     ░░░     ░░░     ░░░     ░░░  ← panes       ║
║  06 ── ▓▓▓     ▓▓▓     ▓▓▓     ▓▓▓     ▓▓▓     ▓▓▓     ▓▓▓  ← chipas       ║
║  08 ── ░░░     ░░░     ░░░     ░░░     ░░░     ░░░     ░░░  ← facturas     ║
║  10 ── ▓▓▓     ▓▓▓     ░░░     ░░░     ▓▓▓     ▓▓▓     ▓▓▓  ← tortas       ║
║  14 ── ░░░     ░░░     ░░░     ░░░     ░░░     ░░░     ░░░  ← repostería    ║
║                                                                             ║
║  Stock proyectado al sábado:                                                ║
║   Harina 0000   ██████░░░░  18 / 25 kg     ⚠ bajo para fin de semana       ║
║   Azúcar        ██████████  10 / 10 kg     ✓ suficiente                    ║
║   Levadura      ████░░░░░░  400 / 1000 g   ⚠ bajo                          ║
║  [ Imprimir semana ]  [ Generar pedido ]  [ Sincronizar con POS ]          ║
╚════════════════════════════════════════════════════════════════════════════╝
```

The planner is **read-mostly** on a wall tablet (the head baker uses a laptop for editing); the tablet shows it as a glanceable grid. Tapping a cell drills into `/produccion-kitchen?date=2026-09-29&recipe=chipa`.

### 2.5.2 `/recetas/{id}` — Ficha de receta (print-friendly)

```
╔═══════════════════════════════════════════════════════════╗
║  PAN FRANCÉS                                  Lote #214   ║
║  ───────────────────────────────────────────────────      ║
║  Rendimiento: 12 panes (650 g c/u)                        ║
║  Tiempo total: 2 h 17 min                                 ║
║  ─── Ingredientes ─── (ordenados por peso, descendente)  ║
║    5.0 kg   Harina 0000                                    ║
║    3.0 L    Agua tibia (28 °C)                             ║
║  100 g      Levadura seca                                  ║
║  100 g      Sal                                            ║
║   30 g      Mejorador                                      ║
║  ─── Pasos ───                                             ║
║   1. Amasar 12 min a velocidad lenta                      ║
║   2. Reposo 15 min en bol grande                           ║
║   3. Dividir en 12 porciones (650 g c/u)                   ║
║   4. Formar bollos, reposo 30 min                          ║
║   5. Hornear a 230 °C por 35 min                           ║
║  ─── Notas ───                                             ║
║   Si la harina está fría, llevar a 18 °C antes.            ║
║   Si el horno es a gas, precalentar 20 min extra.          ║
║  ─── Costo ─── (solo en pantalla, no en print)             ║
║   Costo total: Gs. 18.000  ·  Costo / pan: Gs. 1.500      ║
║   Precio venta sugerido: Gs. 4.500 / pan                   ║
║  [ Imprimir ]  [ Ver en cocina ]  [ Editar receta ]        ║
╚═══════════════════════════════════════════════════════════╝
```

**Print-friendly:** when `?print=1` is set, the page is reformatted as a single A4 sheet — no nav, no `Costo` section, no `Editar` button. Black-on-white, 12 pt body, 24 pt title. The printout is the canonical clipboard backup.

### 2.5.3 `/inventario/{id}` — Detalle de ingrediente (print-friendly, vertical)

Same orientation as the recipe card. Vertical, big numbers, single ingredient per card.

```
╔═══════════════════════════════════════════════════════════╗
║  HARINA 0000                                               ║
║  Categoría: Harinas · Alérgenos: gluten                   ║
║  ───────────────────────────────────────────────────      ║
║  Stock actual  ████████░░░░░░░░  18 / 25 kg              ║
║  Días restantes (consumo promedio 7d): 5 días             ║
║  Precio compra:     Gs. 6.500 / kg                        ║
║  Última compra:     2026-09-24 · 5 kg                    ║
║  Proveedor:         Molino San Lorenzo                    ║
║  ─── Usado en ───                                         ║
║   • Pan francés (4.5 kg/lote)                             ║
║   • Chipa (2.0 kg/lote)                                   ║
║   • Facturas (1.2 kg/lote)                                ║
║  [ + Reposición rápida ]  [ Ver movimientos ]             ║
╚═══════════════════════════════════════════════════════════╝
```

The `+ Reposición rápida` button at the bottom logs a quick top-up (e.g., "5 kg flour delivered") without navigating to the full inventory module. Opens a single-field sheet.

## 2.6 Cognitive-load targets

- **0 navigation.** The first screen is the only screen for 95% of the bake. One recipe per card; one card on screen at a time.
- **1 glance to see "what's next."** Status pill + countdown are visible at 2 m.
- **Time visible without touching.** Countdown runs in real-time; screen never sleeps (auto-brightness ≥ 60%).
- **No decisions.** When the timer says "Sacar del horno," the baker taps the button. No "¿Estás seguro?" — it just marks the batch done and auto-advances to the next phase.
- **One CTA per card.** No `[ Cancelar ]` next to `[ Empezar ]` — there's nothing to cancel from the baker's perspective.

## 2.7 Anti-patterns (must NOT)

- **No small text** — min 18 pt body, 24 pt ingredient names, 32 pt recipe title.
- **No modals** — cannot be dismissed with flour-covered hands; full-screen replacements only.
- **No color-only indicators** — color-blindness + flour-covered glasses. Always pair color with shape and label.
- **No hover** — touch only. Long-press for context tooltips, never required to use the screen.
- **No dropdowns or selects** — tap-to-pick chips with the value displayed.
- **No decorative animation** — only the active-phase ring may animate.
- **No emoji-only badges** — status is `▰` / `●` / `✓` / `▲` + text, never 🎉 / ⏰ / ❗.
- **No "Edit recipe" on the wall tablet** — recipes are edited on a laptop, not at the oven.
- **No auto-logout** — baker shift is 4–14 h. Logout is explicit, on long-press of the user pill.

---

# Role 3 — Owner / Manager (`/owner-cockpit`)

## 3.1 Environment & devices

| Dimension | Target |
|---|---|
| **Primary device** | Laptop (13–15") or desktop monitor (24"+). Real keyboard + mouse/trackpad. |
| **Browser** | Modern Chromium, Firefox, Safari. **NOT a tablet.** |
| **Environment** | Office or backroom. Multi-tasking: chat, email, paperwork. |
| **Cognitive load** | High. Analytical. Wants to compare weeks, drill into anomalies, export for the accountant. |
| **Time per session** | 2–10 s peeks + 30–60 s daily review + 10–30 min weekly review. |
| **Density** | High. Every important number visible without scrolling. |
| **Auth** | Email + password + TOTP. Owner is the only role with email login. |

## 3.2 Login → first screen

Owner authenticates with **email + password + TOTP**. System routes to `/owner-cockpit` — never to a "home" page.

**Daily review cadence:** the cockpit is the screen the owner opens first thing in the morning — designed for 30–60 s of KPI scanning + 1–2 alert drills, then leave. The cockpit is **not** a deep-work dashboard; that lives on `/analisis` and `/reportes/*`.

**First-screen design principle:** "If a number is bad, it should be impossible to miss." Red bars + red text + triangle icon for any KPI below threshold; healthy numbers use neutral gray. The owner should be able to do their daily review with audio muted — purely visually.

## 3.3 Sub-screens

| Path | Title | When |
|---|---|---|
| `/owner-cockpit` | Cockpit (default) | First screen on login |
| `/analisis` | Análisis (KPIs, top productos, promedios) | Deep dive |
| `/reportes` + `/reportes/*` | Ventas · Caja · IVA · Top · Mermas · Compras | Pick from index, filter, export CSV/PDF |
| `/pricing` | Precios por receta | Inline edit; reflows margin |
| `/vs-mercado` | Vs. mercado | Competitive positioning (manual or scraped) |
| `/bank` | Flujo de caja (banco) | Daily; reconcile vs. CSV import |
| `/riesgos` | Registro de riesgos | Quarterly review |
| `/auditoria` | Bitácora de auditoría | Append-only, immutable, filterable |
| `/eod` | Cierre EOD (end of day) | Daily, manual; sticky until done |

These sub-screens are full pages with their own density; the cockpit surfaces them via `[ Ver detalle ]` links on each tile.

## 3.4 Primary screen ASCII wireframe — `/owner-cockpit`

```
╔════════════════════════════════════════════════════════════════════════════════════════════════════════════╗
║  Sazón · Cockpit              domingo 27 sep 2026 · 09:18          admin@panaderia.com  [⌘K] [⌘N]   ║
╠════════════════════════════════════════════════════════════════════════════════════════════════════════════╣
║ KPI STRIP (96px, 7 tiles — each clickable)                                                          ║
║ ┌───────────┬───────────┬───────────┬───────────┬───────────┬───────────┬───────────┐                ║
║ │ CAPITAL   │ VENTAS HOY│ VENTAS 7D │ MARGEN BR.│ MARGEN NET│ MERMA 7D  │ OCUPACIÓN │                ║
║ │ Gs. 12.4M │ Gs. 1.45M │ Gs.  9.8M │    62.3%  │ ▲ 14.2% ▼ │    3.1%   │    78%    │                ║
║ │ ▲ +2.1%   │ ▲ +12% OK │ = vs sem 3│ ▲ +1.4pp  │ vs sem ant│ ▼ -0.3pp⚠ │ ▲ +4pp    │                ║
║ └───────────┴───────────┴───────────┴───────────┴───────────┴───────────┴───────────┘                ║
╠════════════════════════════════════════════════════════════════════════════════════════════════════════════╣
║ ┌──────────────────────────────┬─────────────────────────────────┬──────────────────────────────────┐   ║
║ │ 4-CHART GRID (2×2)           │ ALERTAS (sorted by severity)    │ ACCIONES RÁPIDAS                 │   ║
║ │ ┌──────────────────────────┐ │ ┌─────────────────────────────┐ │ ┌──────────────────────────────┐ │   ║
║ │ │ Ventas – semana (line 7d)│ │ │ ▲ Levadura seca +18% en 7d  │ │ │ CERRAR DÍA (EOD)             │ │   ║
║ │ │ ▁▂▃▄▅▆█                  │ │ │   Gs. 12.000 → 14.200/kg    │ │ │ hace 6h — pendiente           │ │   ║
║ │ └──────────────────────────┘ │ │   [Actualizar precio]       │ │ │ [ Abrir EOD ]                │ │   ║
║ │ ┌──────────────────────────┐ │ ├─────────────────────────────┤ │ └──────────────────────────────┘ │   ║
║ │ │ Ventas – mes (bar by wk) │ │ │ ▲ Pan francés margen 64→51% │ │ ┌──────────────────────────────┐ │   ║
║ │ │ ███▆▅▃▃▅▆                │ │ │   (subió harina 0000)       │ │ │ NÓMINA  (próximo 30/09)      │ │   ║
║ │ └──────────────────────────┘ │ │   [Ver receta]              │ │ │ [ Revisar ]                  │ │   ║
║ │ ┌──────────────────────────┐ │ ├─────────────────────────────┤ │ └──────────────────────────────┘ │   ║
║ │ │ Top productos (mes)      │ │ │ ⚠ Merma facturas 5.2%       │ │ ┌──────────────────────────────┐ │   ║
║ │ │ Chipa ███████████        │ │ │   (objetivo ≤ 2.5%)         │ │ │ AUDITORÍA  12 eventos / 24h  │ │   ║
║ │ │ Pan fra. ████████        │ │ │   [Ver detalle]             │ │ │ [ Revisar bitácora ]         │ │   ║
║ │ │ Bizcocho █████           │ │ ├─────────────────────────────┤ │ └──────────────────────────────┘ │   ║
║ │ └──────────────────────────┘ │ │ ● Stock crítico: 3 SKU       │ │ ┌──────────────────────────────┐ │   ║
║ │ ┌──────────────────────────┐ │ │   Harina 0000 (5d rest.)     │ │ │ REPORTES                     │ │   ║
║ │ │ Comparación trimestral   │ │ │   Levadura (2d) Azúcar (1d)  │ │ │ [Ventas][Caja][IVA][Top]     │ │   ║
║ │ │ Q1 vs Q2 vs Q3 (line)    │ │ │   [Generar pedido compra]    │ │ │ [Mermas][Compras]            │ │   ║
║ │ └──────────────────────────┘ │ ├─────────────────────────────┤ │ └──────────────────────────────┘ │   ║
║ │                              │ │ 2 alertas más… [Ver todas]   │ │ ┌──────────────────────────────┐ │   ║
║ │                              │ └─────────────────────────────┘ │ │ REORDENAR STOCK               │ │   ║
║ │                              │                                 │ │ (auto-prellena desde crítico) │ │   ║
║ │                              │                                 │ │ [Abrir lista de compras]      │ │   ║
║ │                              │                                 │ └──────────────────────────────┘ │   ║
║ └──────────────────────────────┴─────────────────────────────────┴──────────────────────────────────┘   ║
╠════════════════════════════════════════════════════════════════════════════════════════════════════════════╣
║ FOOTER: Sazón v1.0 · última sync 09:18 · 1 dispositivo activo · soporte: hola@saskia.com.py           ║
╚════════════════════════════════════════════════════════════════════════════════════════════════════════════╝
```

**KPI strip anatomy (96 px tall, 7 tiles):**
- Each tile ~14% width (7 across).
- Top: big number (28 pt), label (12 pt uppercase).
- Below: delta vs reference period (`▲ +12% vs ayer`; ▲ green / ▼ red / = gray).
- Tile color: white default; **amber** if in warning band; **red border + red text** if below threshold.
- Tiles clickable → drill into corresponding report.

**Chart grid (2×2):** top-left Ventas semana (line, 7d); top-right Ventas mes (bar, by week); bottom-left Top productos mes (horizontal bar); bottom-right Comparación trimestral (Q1 vs Q2 vs Q3 line). Every point/bar is tappable.

**Alerts panel:** sorted by severity (price drift first, then margin, then merma, then stock). Each alert: icon (color + shape), title, one-sentence description, primary action button (`[ Actualizar precio ]`, `[ Ver receta ]`, etc.). "N alertas más… [Ver todas]" → `/analisis?view=alerts`.

**Quick actions (right column):**
- Each card: title + one-line status + primary CTA.
- `CERRAR DÍA (EOD)` is sticky — until EOD is closed, shows "pendiente" and red dot.
- `NÓMINA` shows next payroll date.
- `AUDITORÍA` shows count of audit-log entries in last 24 h.
- `REPORTES` is a 2×3 chip grid linking to each report.
- `REORDENAR STOCK` pre-fills shopping list from stock-critical list.

**Footer:** last sync status, active devices, support contact. Owners want to know the system is healthy.

## 3.5 Sub-screen wireframes

### 3.5.1 `/analisis` — Análisis

```
╔══════════════════════════════════════════════════════════════════════════════════════════╗
║  Análisis                                                                                ║
║  Período: [ Última semana ▾ ]   Comparar con: [ Semana anterior ▾ ]   [ Exportar CSV ] ║
║  ┌─────────────────────────────────────────────────────────────────────────────────┐    ║
║  │ RESUMEN                                                                          │    ║
║  │   Ventas:       Gs. 9.840.000  (▲ +6.2% vs sem ant.)                            │    ║
║  │   Costos:       Gs. 3.720.000  (▲ +4.8%)                                          │    ║
║  │   Margen bruto: 62.2%         (▲ +1.1pp)                                          │    ║
║  │   Margen neto:  14.2%         (▼ -0.4pp ⚠)                                       │    ║
║  │   Merma:        3.1%          (▼ -0.3pp ✓)                                        │    ║
║  └─────────────────────────────────────────────────────────────────────────────────┘    ║
║  ┌──────────────────────────────┐  ┌──────────────────────────────────────────────────┐║
║  │ Ventas por día (line, 7d)    │  │ Top 10 productos (rentabilidad)                   │║
║  └──────────────────────────────┘  │ 1. Chipa           Gs. 4.000  margen 71%  ROI ★★★ │║
║  ┌──────────────────────────────┐  │ 2. Pan francés     Gs. 4.500  margen 64%  ROI ★★★ │║
║  │ Ventas por categoría (donut) │  │ 3. Bizcocho        Gs. 18.500 margen 68%  ROI ★★  │║
║  └──────────────────────────────┘  │ 4. Empanada        Gs. 5.500  margen 55%  ROI ★★  │║
║                                     │ …                                                  │║
║                                     └──────────────────────────────────────────────────┘║
║  ┌──────────────────────────────┐  ┌──────────────────────────────────────────────────┐║
║  │ (cuarto chart)               │  │ Alertas activas (8)                                │║
║  │                              │  │ ▲ Levadura seca +18%   ▲ Pan francés margen -13pp │║
║  └──────────────────────────────┘  │ ⚠ Merma facturas 5.2%   ● Stock crítico 3 SKU     │║
║                                     └───────────────────────────────────────────��───────┘║
╚══════════════════════════════════════════════════════════════════════════════════════════╝
```

Density is higher than the cockpit. Two columns of charts plus a summary card. The owner compares periods via the top-bar dropdowns.

### 3.5.2 `/reportes/*` (representative: `/reportes/ventas`)

```
╔══════════════════════════════════════════════════════════════════════════════════════════╗
║  Reportes › Ventas                                                                         ║
║  Período: [ Este mes ▾ ]   Forma de pago: [ Todas ▾ ]   Categoría: [ Todas ▾ ]            ║
║  Cliente: [_______________]   Caja: [ Todas ▾ ]   [ Aplicar filtros ]  [ Exportar PDF ]   ║
║  ┌─────────────────────────────────────────────────────────────────────────────────────┐  ║
║  │ Resumen del período                                                                  │  ║
║  │   Ventas brutas: Gs. 28.450.000    Devoluciones: Gs. 180.000 (4 ops)                 │  ║
║  │   Ventas netas:   Gs. 28.270.000    Ticket prom:  Gs. 17.320   # ventas: 1.642       │  ║
║  └─────────────────────────────────────────────────────────────────────────────────────┘  ║
║  Tabla:                                                                                    ║
║   #      Fecha    Caja   Cajero     Cliente      Items  Subtotal   IVA    Total   Forma    ║
║   1432   27/09    1      María G.   (consum.)    3      24.091    2.409  26.500  efvo.    ║
║   1431   27/09    1      María G.   Carlos R.    2      16.364    1.636  18.000  tarjeta  ║
║   …                                                                                        ║
║  Paginación: « 1 2 3 … 28 »  Tamaño de página: [ 50 ▾ ]                                   ║
╚══════════════════════════════════════════════════════════════════════════════════════════╝
```

Every column is filterable. CSV/PDF export respects current filters. Drill from a row → `/ventas/{id}/recibo` (read-only).

### 3.5.3 `/pricing` — Precios por receta

```
╔══════════════════════════════════════════════════════════════════════════════════════════╗
║  Precios por receta                                                                        ║
║  Margen objetivo: [ 60 % ▾ ]    Markup sugerido: [ × 2.5 ▾ ]    [ Aplicar a todas ]      ║
║  ┌──────┬──────────────────┬──────────┬──────────┬──────────┬──────────┬──────────┬───────┐ ║
║  │ #    │ Receta           │ Costo    │ Precio   │ Margen   │ Vs mer.  │ Estado   │ Acc.  │ ║
║  ├──────┼──────────────────┼──────────┼──────────┼──────────┼──────────┼──────────┼───────┤ ║
║  │ 001  │ Pan francés      │ 1.500    │ 4.500    │ 67 %     │ = 4.500  │ ✓ OK     │ Edit. │ ║
║  │ 002  │ Chipa            │ 1.100    │ 4.000    │ 73 %     │ ▲ +5%    │ ✓ OK     │ Edit. │ ║
║  │ 003  │ Bizcocho laranja │ 5.800    │ 18.500   │ 69 %     │ ▼ -8% ⚠ │ ⚠ debajo │ Edit. │ ║
║  │ 004  │ Empanada         │ 2.100    │ 5.500    │ 62 %     │ = 5.500  │ ✓ OK     │ Edit. │ ║
║  │ 005  │ Pan baguette     │ 2.400    │ 6.000    │ 60 %     │ ▲ +2%    │ ✓ OK     │ Edit. │ ║
║  └──────┴──────────────────┴──────────┴──────────┴──────────┴──────────┴──────────┴───────┘ ║
║  Bulk: [ Seleccionar todo ] [ Aplicar margen objetivo ] [ Exportar lista de precios ]      ║
╚══════════════════════════════════════════════════════════════════════════════════════════╝
```

Inline editing of price (single click on the cell → numeric input → `⏎` saves). The `Vs mer.` column pulls from `/vs-mercado` (manual or scraped competitor prices).

### 3.5.4 `/bank` — Flujo de caja (banco)

```
╔══════════════════════════════════════════════════════════════════════════════════════════╗
║  Flujo de caja                                                                              ║
║  Período: [ Últimos 30 días ▾ ]                                                            ║
║  ┌─────────────────────────────────────────────────────────────────────────────────────┐  ║
║  │ Saldo inicial          Gs.  8.200.000                                                │  ║
║  │ + Ingresos (ventas)    Gs. 28.270.000                                                │  ║
║  │ - Costos (compras)     Gs. 11.430.000                                                │  ║
║  │ - Nómina               Gs.  6.800.000                                                │  ║
║  │ - Impuestos (IVA)      Gs.  2.572.000                                                │  ║
║  │ - Servicios            Gs.    920.000                                                │  ║
║  │ - Retiros mgr          Gs.    400.000                                                │  ║
║  │ Saldo final (esperado) Gs. 14.348.000                                                │  ║
║  │ Saldo real (banco)     Gs. 14.201.000                                                │  ║
║  │ Diferencia             Gs.   -147.000  ⚠ (investigar)                                │  ║
║  └─────────────────────────────────────────────────────────────────────────────────────┘  ║
║  Línea de tiempo diaria:                                                                   ║
║   día 1 ─── 7 ─── 14 ─── 21 ─── 28 ─── 30                                                   ║
║         ▁▂▃▂▃▄▃▅▄▅▆▅▆▇▆▇█                                                                     ║
║  Tabla de movimientos:                                                                      ║
║   Fecha       Concepto            Categoría       Ingreso       Egreso       Saldo        ║
║   2026-09-27  Venta mostrador      ventas            1.450.000      -        14.201.000     ║
║   2026-09-26  Compra harina 0000   compras              -        320.000    12.751.000     ║
║   …                                                                                        ║
╚══════════════════════════════════════════════════════════════════════════════════════════╝
```

The owner uses this to reconcile against the bank statement (manual import of CSV from the bank).

### 3.5.5 `/riesgos` — Registro de riesgos

```
╔══════════════════════════════════════════════════════════════════════════════════════════╗
║  Registro de riesgos                                                                        ║
║  ┌────┬───────────────────────────┬─────────┬──────────┬──────────┬────────────┬─────────┐ ║
║  │ #  │ Riesgo                    │ Prob.   │ Impacto  │ Score    │ Mitigación │ Estado  │ ║
║  ├────┼───────────────────────────┼─────────┼──────────┼──────────┼────────────┼─────────┤ ║
║  │ R1 │ Suba de harina 0000       │ Media   │ Alto     │  12 / 25 │ Buscar prov.│ Abierto │ ║
║  │ R2 │ Falla de horno #2         │ Baja    │ Crítico  │   9 / 25 │ Mantenim.  │ Vigilar │ ║
║  │ R3 │ Rotación de cajero        │ Alta    │ Medio    │  12 / 25 │ Capacitar  │ Abierto │ ║
║  │ R4 │ Costo de energía          │ Media   │ Medio    │   9 / 25 │ Cotizar    │ Cerrado │ ║
║  └────┴───────────────────────────┴─────────┴──────────┴──────────┴────────────┴─────────┘ ║
║  Score = Probabilidad × Impacto (matriz 5×5, escala 1-25)                                  ║
╚══════════════════════════════════════════════════════════════════════════════════════════╝
```

### 3.5.6 `/auditoria` — Bitácora de auditoría

```
╔══════════════════════════════════════════════════════════════════════════════════════════╗
║  Bitácora de auditoría                                                                      ║
║  Filtros: Tipo [ todos ▾ ]   Usuario [ todos ▾ ]   Fecha [ últimos 7d ▾ ]                 ║
║   Hora        Tipo                     Usuario        Detalle                              ║
║   09:18:42    session.login            admin          Cockpit loaded                      ║
║   09:18:43    price.update             admin          Pan francés 4.200 → 4.500           ║
║   09:15:11    cashier.session.open     María G.       caja 1, apertura Gs. 500.000        ║
║   09:14:50    supplier.merge           admin          "Molinos SA" + "Molinos S.A." → …   ║
║   09:02:00    stock.adjust             Carlos B.      Harina 0000 -0.5 kg (motivo: merma) ║
║   08:55:33    inventory.transfer       Carlos B.      Azúcar 10kg → producción           ║
║   08:30:00    daily.eod.closed         admin          EOD 2026-09-26 cerrado              ║
║   …                                                                                        ║
║  [ Exportar CSV ]  [ Exportar PDF firmado ]                                                 ║
╚══════════════════════════════════════════════════════════════════════════════════════════╝
```

Every row is **append-only and immutable** (append-only at the DB level). Filterable by user, type, date.

## 3.6 Cognitive-load targets

- **30–60 s for daily review.** KPIs across the top, charts middle, alerts right.
- **Drill-down on any number.** Every KPI tile clickable; every chart point clickable; every alert has a primary action button.
- **Compare any metric to any period.** Top-bar dropdowns on `/analisis` and `/reportes/*` accept arbitrary periods (day / week / month / quarter / year / custom) and arbitrary comparison periods.
- **One-click EOD.** `CERRAR DÍA` is the most important button in the system for the owner. One click → wizard → done.
- **Empty state = "this is what good looks like," not "go sell something."** On a brand-new install, the cockpit shows greyed-out tiles with sample numbers and a `[ Cargar datos demo ]` CTA, so the owner sees the intended density immediately.

## 3.7 Anti-patterns (must NOT)

- **No "go sell something" empty states.** Show sample numbers (greyed-out tiles) or first-run onboarding CTA.
- **No emoji-only alerts.** Every alert uses icon + color + text. `⚠ Levadura subió 18%` is OK; `🚨` alone is not.
- **No "Create" buttons on the cockpit.** Owner does not create products, recipes, sales, or purchases. Owner reviews, prices, configures, reconciles.
- **No login-style forms on the cockpit.** KPIs ARE the content.
- **No color-only signaling.** Color paired with shape (▲/▼/⚠/●) and text.
- **No pop-up modals for alerts.** Alerts live in the right panel; click opens a side drawer.
- **No infinite scroll.** Reports paginate.
- **No silent destructive actions.** Every price change, supplier merge, EOD close shows a confirmation sheet summarizing the diff.
- **No settings menu on the cockpit.** Settings live at `/configuración/*`; cockpit exposes only `[ Configurar umbrales de alerta ]` and `[ Configurar roles ]`.

---

# Cross-cutting

## Shared global nav (left rail)

All three roles see the same six-section nav (`Operación · Catálogo · Compras · Ventas y Clientes · Finanzas · Configuración`). The nav is **collapsed by default** on the cashier's `/pos` (only `Caja`, `Buscar venta`, `Cerrar turno` reachable from the user pill) and **expanded by default** on the owner's cockpit. The baker's nav shows only `Producción`, `Recetas`, `Inventario`, `Cerrar turno`.

## Role resolution at login

The user record carries a `primary_role` (`cashier` | `baker` | `owner`). A user may have multiple roles (e.g., the owner may also serve as a cashier on a busy day). On login:

1. If `primary_role` is set, route to that role's first-screen.
2. If multiple roles, show a one-tap role picker (3 large buttons, not a dropdown).

## Login routing table

| Role | First screen | Default font |
|---|---|---|
| Counter Cashier | `/pos` | 18 pt body |
| Production Baker | `/produccion-kitchen` | 24 pt body |
| Owner / Manager | `/owner-cockpit` | 14 pt body |

## Per-role keyboard map (consolidated)

| Key | Cashier | Baker | Owner |
|---|---|---|---|
| `⌘K` / `Ctrl+K` | Global command bar | Global command bar | Global command bar |
| `⌘N` | New sale (reset cart) | New batch (rare) | New risk entry |
| `⏎` | Confirm / add to cart | Confirm / advance phase | Form submit |
| `Esc` | Cancel sheet | Cancel sheet | Close drawer |
| `F1`–`F4` | Pay: cash · card · transfer · mixed | (n/a) | (n/a) |
| `F5`–`F7` | Hold · Discount (mgr) · Refund (mgr) | (n/a) | (n/a) |
| `F8`–`F10` | Reprint · Today's sales · Cash drawer | (n/a) | (n/a) |
| `⌘S` | (sales save on `⏎`) | (n/a) | Save settings |
| `⌘E` | (n/a) | Edit recipe (only on `/recetas/{id}`) | Export current view |
| `⌘⇧P` | (n/a) | (n/a) | Owner command palette |

## Per-role visual density

| Dimension | Cashier | Baker | Owner |
|---|---|---|---|
| Touch target min | 48×48 (primary 96×96) | 88×88 | 28 px (mouse) |
| Body font | 18 pt | 24 pt | 14 pt |
| Color use | Functional only (status) | Status + phase ring | Rich (KPIs, alerts, deltas) |
| Whitespace | Tight (cart density) | Loose (glanceability) | Compact (analytical) |
| Animations | Skeleton only | Active-phase ring only | Number count-up, chart transitions |
| Audio | None | None | Optional (muted by default) |
| Auto-logout | Never (until explicit) | Never (until explicit) | 30 min idle |

---

# Acceptance checklist

### Counter Cashier
- [ ] `/pos` is the default screen after cashier PIN login.
- [ ] No modal appears anywhere in the cashier flow.
- [ ] All buttons ≥ 48×48 px; primary CTAs ≥ 96×96 px.
- [ ] Status strip (clock, drawer balance, printer health) always visible.
- [ ] Search-as-you-type replaces every dropdown.
- [ ] Cart qty edit works with `[ + ]` / `[ − ]` only.
- [ ] Payment sheet = slide-up, ≤ 40% screen height.
- [ ] Receipt bottom-sheet auto-prints + auto-dismisses after 6 s.
- [ ] Currency uses `Gs. 20.000` (dot sep, no decimals).
- [ ] `F1`–`F10` keyboard map works as documented.

### Production Baker
- [ ] `/produccion-kitchen` is the default screen after baker PIN login.
- [ ] One recipe per card, stacked vertically, time-of-day order.
- [ ] Recipe title ≥ 32 pt, ingredients ≥ 18 pt.
- [ ] Ingredients listed in descending weight order.
- [ ] Status uses icon + color + text (never color-only).
- [ ] Active phase countdown visible without touch.
- [ ] `/recetas/{id}?print=1` produces print-friendly A4 (no nav, no cost section).
- [ ] No edit affordance on the wall tablet (recipes edited on laptop).
- [ ] Auto-logout disabled for baker shifts.

### Owner / Manager
- [ ] `/owner-cockpit` is the default screen after owner email+TOTP login.
- [ ] KPI strip has 7 tiles, each clickable to drill down.
- [ ] 4-chart grid shows week / month / quarter / year comparisons.
- [ ] Alerts panel sorted by severity, each with a primary action button.
- [ ] Quick actions include `CERRAR DÍA (EOD)` with pending indicator until closed.
- [ ] All deltas show comparison vs reference period (▲ green / ▼ red / = neutral).
- [ ] No "Create" buttons on the cockpit (only on sub-screens).
- [ ] Empty state shows sample numbers (not "go sell something").
- [ ] Every report is filterable + exportable to CSV and PDF.

### Cross-cutting
- [ ] All three roles share the same six-section nav; first-screen and visible items differ.
- [ ] Global command bar (`⌘K`) is reachable from any role with role-scoped suggestions.
- [ ] Currency canonical (`Gs. 20.000`) across all roles.
- [ ] Date format canonical (`dd/mm/yyyy`) across all roles.
- [ ] All buttons use infinitive ("Guardar", "Cobrar", "Editar") — no voseo.
- [ ] No slug-as-display-name leaks ("Ingrediente 415de24c") on cashier/baker screens.
- [ ] Every form submission shows a confirmation (receipt print, toast, or auto-advance).

---

# Open questions

1. **Multi-role users** — should the role picker appear at every login for users with ≥2 roles, or only on first login?
2. **Offline mode for baker** — read-only lock, or show last-known state with red "offline" dot? (Bakery ovens don't wait for connectivity.)
3. **Touch-friendly cockpit** — should `/owner-cockpit` ship a `?density=touch` variant for weekend tablet peeks? (Out of scope for v1.)
4. **PinPad fallback** — if the payment-terminal bridge isn't ready, does the `TARJETA` button auto-fall-back to manual masked entry + audit note, or hide the button entirely?
5. **Tablet vs. clipboard primacy** — design assumes wall-tablet primary + printed clipboard backup; confirm with bakery if this matches the historical workflow.
6. **Cockpit vs. análisis split** — 4 charts on cockpit + 4 on análisis; or 8 on cockpit + análisis as deep-dive-only?
7. **Audit retention** — 1 year / 5 years / forever? Compliance question for the Paraguayan tax authority (SET).
8. **Multi-store** — v1 assumes single-store; flag `regional_manager` as a potential 4th role for v2.
9. **Auto-close vs. explicit shift close** — cashier auto-closes at 22:00; baker shift = 04:00–18:00, currently implicit. Should baker shift auto-close at midnight?
10. **Shift overlap** — what happens when a baker starts their shift before the cashier's? Should `/produccion-kitchen` show yesterday's final-state or last-night's pull-list summary?

---

**End of v1 wireframe doc — 2026-09-27**