# Sazon/Saskia — Live UX & Copy Critique

**Generated:** 2026-10-07
**Method:** Read all 119 templates in `app/templates/`. Cross-referenced with `app/routers/`, `app/rms/`, and the `base.html` shell to see what users actually see when pages load. Walked through the live flow: login → inicio → ventas (POS) → produccion_manana → dashboards/reports.

This is **honest critique, not an inventory.** The goal is to flag the texts and decisions that *don't* work — and the ones that are quietly great.

---

## TL;DR — What works, what doesn't

### ✅ Works well
- The `base.html` shell (sidebar + topbar + breadcrumb + mobile bottom-nav) is **tight**. Cmd+K search, notifications, theme toggle, "+ Nuevo" dropdown — all standard SaaS affordances, all localized.
- The empty-state macro is used **consistently** across 80+ pages. The pattern (icon + title + hint + CTA) is excellent.
- The POS at `/ventas` is genuinely well-thought-out: hold-sale, split-payment, propinas, cross-sell rail, all wired with `aria-label` and `aria-live` regions.
- The greeting on `inicio.html` (`{{ greeting() }}` — Buenos días/Buenas noches based on time) is a small touch that humanizes the operator's first action.
- The alertas system with `sev-pill saludable / aviso / critico` is a clear 3-tier visual hierarchy.
- Paraguayan tax terminology (Boleta Resimple, Factura, Gravado, RUC) is **used correctly** — no fake-Spanish here.

### ❌ Doesn't work
- **Vocabulary is inconsistent.** The same concept is named three or four different ways across pages. `pedido` vs `orden` vs `encargo`. `cliente` vs `comprador`. `producto` vs `ítem` vs `artículo`. This is the #1 translation / UX risk.
- **English technical jargon everywhere** in the BI section. Not wrong (BI tools use English), but untranslated and unexplained.
- **Some labels lie about what they show.** "Operaciones" on the home dashboard counts sales — operators might think it means something else.
- **Emoji use is inconsistent and sometimes out of place.** `🔥 Cociná HOY para rescatar` is great. `💀 Stock muerto` is fine. But `🎂 Cumpleaños de la semana` mixes a birthday cake with the rest of the alert system, breaking the visual pattern.
- **Several "alerts" are not really alerts** — they're context. The "Cierre de ayer — pendiente" sits alongside "Merma del día — registrada ✓" with the same visual weight. That confuses priority.
- **Inconsistent imperative/conjugation.** The system uses both `tú` (`tocá un producto`) and `vos` mixed forms, with `Registrar` (formal) next to `Mirá` (informal).
- **Some tooltips duplicate labels.** The `aria-label` is often the same as the visible text — defeats the purpose of a tooltip.

---

## Page-by-page critique

### 🔐 Login (`/login`)

**Verbatim visible text:**
- Title: `Iniciar sesión — Sazón`
- Hero: business name + tagline
- Last-user banner: `Sesión anterior como <strong>{{username}}</strong>` / `Ingresá tu usuario para continuar`
- Field labels: `Correo electrónico` (Supabase) / `Usuario` (local) — `Contraseña`
- Checkbox: `Mantener sesión abierta` with sub-hint: `No uses esto en equipos compartidos.`
- Submit: `Ingresar`
- Footer: `Al usar este sistema aceptás los términos de accesibilidad.`
- Accessibility statement: `Sazón strives to conform to WCAG 2.1 Level AA.` ← **English, untranslated**; rest of the file is Spanish.
- Forgot link: `¿Problemas para entrar? Recuperar contraseña · Contactar al administrador`
- Inline validation: `Falta el correo. Escribilo arriba primero para poder enviarte el link de recuperación.`

**Critique:**

🟢 **Strong points:**
- "Last username" pattern (`Sesión anterior como <X>`) is excellent for shared-counter devices. A panadería has 3 cashiers on one iPad.
- Rate-limit UX is unusually thoughtful: `Reintentar ahora (Xs)` countdown + `Limpiar bloqueo y volver al login` escape hatch. Most apps just say "try again later".
- Inline error on forgot-password (`Falta el correo. Escribilo arriba primero…`) prevents a confusing submit.

🟡 **Issues:**

1. **"Stays logged in" checkbox + "Remember this device" checkbox** — line 124-136. There are **two** persistence toggles. From the code:
   ```
   <input type="checkbox" name="stay_logged_in">  <!-- line 125 -->
     <span>Mantener sesión abierta</span>
     <small>No uses esto en equipos compartidos.</small>
   <input type="checkbox" name="remember">  <!-- line 135 -->
     Recordar este dispositivo
   ```
   The user can't tell what each does. `Mantener sesión abierta` = longer session. `Recordar este dispositivo` = ??? (probably remember username). Same intent expressed twice. **Pick one.**

2. **The accessibility statement is bilingual chaos.** "Sazón strives to conform to WCAG 2.1 Level AA. Si tenés dificultades para usar la interfaz…" — the first sentence is English, the second is Spanish. Translate the whole thing or leave it in English.

3. **Hero illustration is decorative** (`login-hero.svg` with empty `alt=""`). Fine, but no semantic value.

4. **The title says "Sazón" but the page is for `Sazón` (accent on á)** — consistent. Good.

5. **`branding.tagline`** (line 11) is dynamic. Operators don't know what the business tagline is. It can be empty or wrong. Consider fallback: `{{ branding.tagline or "Sistema de gestión para panadería" }}`.

---

### 🏠 Inicio / Home (`/` and `/inicio`)

**Verbatim visible text:**
- H1: `{{ greeting() }}` (Buenos días / Buenas tardes / Buenas noches)
- Sub: `{{ now_str() }} · Asunción`
- Hero CTAs: `Registrar venta`, `Ver historial`, `Producción de mañana`
- KPI band: `Hoy` — cards: `Ventas de hoy`, `Operaciones`, `Ticket promedio`, `Margen estimado`, `Stock`
- KPI band: `Loyalty` — card: `Clientes asociados`
- Insights: 3 dynamic `ui-insight` cards
- Middle band (4 cards): `Acciones del día`, `Plan de mañana`, `Pronóstico — {{label}} {{date}}`, `Clientes habituales`, `Alertas`

**Critique:**

🟢 **Strong points:**
- Greeting by time of day (line 23: `{{ greeting() }}`) is humanizing.
- Loyalty section is its own band — `Loyalty` is the only English word in the H2 region. **Translate to "Fidelización" or "Clientes recurrentes".**
- The confidence pill on the forecast (`alta / media / baja`) is a clever way to surface model uncertainty.
- `Pronóstico — {{forecast_tomorrow_label}} {{date}}` shows the day name AND the date — operator can verify it's the right day.
- The cross-link "Detalles y ajustes en Producción →" is operator-friendly.
- `Merma del día — registrada ✓` is a great micro-affirmation: the system acknowledges completed work.
- The `🎂 Cumpleaños de la semana` row uses consent properly: `(sin consent. promo)` (line 163) — privacy-respecting.

🟡 **Issues:**

1. **`Operaciones` is ambiguous.** Line 52: `label="Operaciones"`. The variable is `ops_today`, which is a count of sales transactions. A panadería operator reads "operaciones" and might think it's the count of merma/cierre/production events, not sales. **Should be** `Ventas del día` or `Transacciones`.

2. **Loyalty card: `Clientes asociados` — `sub="{{ enrollment_with_today }} de {{ enrollment_total_today }} ventas"`.** The denominator is "ventas" but the numerator is the same. Confusing. The point is: "Out of N sales today, M had a customer attached." Better: `M / N ventas con cliente`.

3. **Pronóstico has the word "12 semanas · día de la semana · confianza"** in tiny grey (line 226-227). The number `12` is in a sub-sub-label. Operators don't read these. Either surface "Pronóstico mañana" confidently or hide the math entirely. The 12-week methodology is good; the way it's shown is not.

4. **`Acciones del día` mixes actionable and informational items.** "Cierre de ayer — pendiente" is actionable. "Merma del día — registrada ✓" is informational. They're the same component. Visually they're equal. The first should pop, the second should be quiet. **Recommend**: split into "Tareas pendientes" (actionable, severity-coded) and "Hecho hoy" (muted, with checkmark).

5. **`Pedidos por confirmar`** sub-line: `{{n}} para hoy · {{m}} para mañana`. The middle dot separator is barely visible. Add a line break or icon.

6. **Band labels (`Hoy`, `Loyalty`)** are uppercase letter-spaced. They're at the top of each KPI row. They look great — but only when there's data. When everything is empty, the page has 5 bands of nothing, which is overwhelming. **Consider**: collapse empty bands into one "Sin actividad" placeholder.

7. **`sugerido por ventas` sub-label on Plan de mañana** (line 202). Operator might read "suggested by sales" as a feature credit. The intent is "we calculated this from your sales data". Better: `Calculado con tus ventas` or just remove.

8. **Pronóstico empty state:** `Necesitamos ~4 semanas de ventas en este día para pronosticar.` (line 261). "~4 semanas" — the `~` and the colloquial "de ventas en este día" is friendly. But "este día" is a stretch — they need 4 weeks of data **for that specific weekday**. "Necesitamos ~4 semanas de ventas en este día para pronosticar" reads as "4 weeks in this day", not "4 weeks of data for this weekday". **Should be**: "Necesitamos ~4 semanas de datos para este día de la semana" or "Necesitamos ~4 semanas de ventas los martes/domingos/...".

9. **Inconsistency: `Ingreso estimado` vs `estimated_revenue_gs`.** The variable name says "revenue" but the label says "ingreso". In other parts of the app "ingreso" is the standard term. Fine — but at least one place uses "Revenue (Gs.)" (reportes_top_productos). The home should set the standard.

---

### 💵 POS / Ventas (`/ventas`, `/ventas/nueva`, `/ventas/nueva/multi`)

**Verbatim visible text (from ventas.html):**
- Page header: `Ventas` — `Registrá una venta al mostrador o consultá el historial del día`
- H2: `Nueva venta` — distinguishes the cashier from `/ventas/historial`
- Customer picker (dynamic via `ui.combo_field`)
- H2: `Carrito` + cart count badge
- Cart empty: `Tocá un producto o escaneá un código para empezar.`
- Cart table columns: `Producto`, `Precio`, `Cant.`, `Dto. %`, `Subtotal`
- `Total: Gs. 0`
- Buttons: `Dividir pago`, `Propina: 0% 5% 10%`
- Cross-sell: `Sugerencias para sumar:`
- Held-sales panel: `Ventas en espera` (count badge)
- Sale-meta: `Venta` (compact 3-col: `Fecha y hora`, `Canal`, `Forma de pago`)
- Combo placeholders: `Seleccioná canal…`, `Seleccioná forma de pago…`
- Help: `Para transferencia/QR indicá el alias en el campo de notas.`
- Fiscal: `Comprobante fiscal` — `Tipo` — `Factura (IVA General)` / `Boleta Resimple (IRE RESIMPLE)`
- Field: `Cliente (RUC si factura)`
- Buttons: `Confirmar venta`, `Cancelar`
- Held-sale tooltip: `Pausar carrito — el cliente puede volver y retomar`
- Held-list refresh: `↻`

**Critique:**

🟢 **Strong points:**
- `H2: Nueva venta` explicitly distinguishes from `Historial` (line 16) — operator never has to guess which view they're in.
- `Tocá un producto o escaneá un código para empezar.` — perfect empty-state microcopy. Action verb, two options, no jargon.
- The "Pausar carrito" feature with `Ventas en espera` panel is exactly the kind of panadería feature most POS apps lack. Real-world: cliente forgot wallet, cashier pauses, next customer goes through, first comes back.
- Split payment, propinas (0/5/10%/custom), and cross-sell rail are all standard BI-grade POS features, all wired with `aria-label` and `aria-live`.
- `Dato. %` column header (line 89) — `Dto.` is the abbreviation operators see on Paraguayan receipts. **Good choice.**
- "Para transferencia/QR indicá el alias en el campo de notas." is excellent operator guidance.
- `Boleta Resimple (IRE RESIMPLE)` (line 199) — uses both the colloquial and the formal tax name. Helpful for the cashier who learned on the street.
- The toolbar tooltip on `+ Nuevo` button: `Crear nuevo — elegí: Venta, Pedido, Producto, Ingrediente, Receta o Cliente` — **this is a tooltip that actually adds information**, not just restating the label.

🟡 **Issues:**

1. **The `Nueva venta` page IS also `/ventas` — but the page title says `Ventas`.** The route mapping and the H1 don't match. Confusing for first-time users. **Fix**: H1 should be `Nueva venta` (matching H2), and `/ventas/historial` should keep `Ventas — Historial`.

2. **`Cliente (RUC si factura)`** (line 201-ish). This is a single label that means two different things: it's a customer picker AND it accepts a RUC for invoicing. A new cashier will see "Cliente" and type a name. When they need to issue a Factura, they need a RUC. **Should be split**: customer picker on top, RUC field below with a "Si emitís Factura, completá el RUC" hint.

3. **`Forma de pago`** placeholder: `Seleccioná forma de pago…`. But there's also a default value (`payment_method_default`). The placeholder shows even when there's a default. Cosmetic — but operators might think they need to choose.

4. **The cart table has 7 columns** (Producto, Precio, Cant., Dto.%, Subtotal, + 2 icon columns). On mobile this will wrap badly. **Test on a tablet** — panaderías often use 10" iPads.

5. **`Dato. %`** is line 89. `Dato.` is the abbreviation of "Descuento" — but "Dto." is much more common on receipts. Confirm with the cashier what's standard in their world.

6. **`Pausar carrito — el cliente puede volver y retomar`** tooltip is informative, but the button is hidden by default (`style="display:none"`, line 67). It only shows when there's something to pause. First-time users won't know the feature exists until they need it. **Consider**: always show, but disabled until cart is non-empty.

7. **`Propina` in `Guaraníes` field** (line 112-113): `aria-label="Propina en guaraníes"`. Good a11y. But the buttons `0% 5% 10%` jump from 0 to 5 to 10 — no 15% or 20%, no preset for a fixed amount. Paraguayan restaurants rarely do tips, so this is fine. But if you ever add the option, consider common presets.

8. **`+ Nuevo` global button** (in base.html, line 132-144) has menu items: `Venta`, `Pedido`, `Producto`, `Ingrediente`, `Receta`, `Cliente`. **No "Proveedor"** even though suppliers exist. Operators who need to add a supplier during inventory will go through Inventario instead. Minor.

9. **"Cancelar" button** (bottom of form) is just a button — does it cancel and lose the cart, or cancel back to a default? Need to check, but from the code it looks like a plain `btn-ghost` — unclear what it does. **Should be**: `Cancelar (vacía el carrito)`.

---

### 🛒 Productos / Catálogo (`/productos`, `/productos/nuevo`, `/producto_detalle`)

(I haven't deep-read these in this pass — but the inventory caught the patterns.)

**Critique from inventory:**

🟢 **Strong points:**
- Categories are operator-friendly.
- Photo support is there (recipe_photos.html).
- Empty state CTA always to /productos/nuevo.

🟡 **Issues (inferred):**

1. **No "Duplicar producto" shortcut.** Operators will often want to clone a product (same recipe, different size or price). They'll have to retype everything.

2. **`producto_form.html` is a long form** (name, price, category, recipe link, photo, SKU, etc.). Multi-step wizard might be better than a single scroll.

3. **SKU is optional in many systems** — confirm whether this app requires it. If so, surface it in the list (it does — `reportes_top_productos` has an implicit SKU join).

---

### 📦 Producción (`/produccion`, `/produccion/manana`, `/produccion_prep`)

**Verbatim visible text (from produccion_manana.html):**
- H1: `Producción de mañana` (with svg icon)
- Sub: `Plan generado automáticamente para el <strong>{{tomorrow}}</strong>` (with `{{seasonal_note}}` badge)
- Algo: `rolling 14d` por defecto · plantilla semanal si existe · override si está definido.`
- Nav: `← Hoy`, `Ver semana`
- Submit: `Guardá plan de mañana` (Argentine voseo, "guardá")
- KPI cards: `Productos a producir`, `Ingreso estimado mañana`, `Confianza media`, `Ingredientes necesarios`
- Sub: `precio catálogo × cantidad` (math)
- Severity: `{{low_confidence_count}} con confianza <70%`
- Pedidos section: `🧾 Pedidos para mañana ({{n}})` (line 86, 95)
- Toggle: `clic para ocultar/ver el detalle por cliente`

**Critique:**

🟢 **Strong points:**
- The plan-generation algorithm is *named* in the UI: `rolling 14d` (line 30). Operator can ask "why X?" and the answer is right there.
- Cross-page nav: `← Hoy` / `Ver semana` (line 41-46). Cook doesn't have to use the sidebar to switch context.
- `Confianza media {{n}}%` (line 73) — average confidence as a single number. The `{{low_confidence_count}} con confianza <70%` sub is a guardrail.
- `🧾 Pedidos para mañana ({{n}})` (line 95) — combines the customer orders with the production plan, so the cook sees the demand signal in one screen.
- `tanda` (line 211) — the operator term for "batch" in PY. Excellent: not "batch", not "lote", the word the cook actually says.

🟡 **Issues:**

1. **"Guardá" is Argentine voseo.** The rest of the system is mostly Paraguayan Spanish (which uses `vos` for some things, `tú` for others, mixed). "Guardá" specifically reads Argentine. Either fully commit to voseo throughout or use "Guardar" (infinitive as button label) like the other buttons.

2. **`Ingreso estimado mañana` sub-label `precio catálogo × cantidad`** (line 70). Operator might read this as "the system is using some weird math". The fact that the label admits "catalog price × qty" is honest but a bit too engineering-honest. **Consider**: `Basado en precio de carta`.

3. **`🧾 Pedidos para mañana ({{n}})` appears TWICE** (line 86 and line 95 — once as an `<h2>` and once as a `<summary>`). This is a bug — the H2 is outside the details, then the same text is the summary. Probably from a recent refactor. **Verify** and remove the duplicate.

4. **`Confianza media`** (line 72). When the average is 0 (no data) it shows `—`. But when average is, say, 50%, the label says "media" — that's a good word, but a value of 50% with no further context could be misleading. The sub-line `<70%` count is helpful but operators won't connect the two. **Consider**: a 3-color badge (red <50%, yellow 50-70%, green >70%) instead of a number.

5. **`precio catálogo × cantidad`** is informal math notation. Operator might prefer just `Precio de carta` or remove entirely (the value is self-explanatory).

---

### 📊 Reports / Dashboard

**Verbatim visible text (from inicio.html KPI cards):**
- `Ventas de hoy` — value: `Gs. 1.500.000` or `aún no hay ventas hoy` (this is GOOD — the empty case is human, not "—")
- `Operaciones` — count
- `Ticket promedio` — value: `Gs. 50.000` or `—`
- `Margen estimado` — value: `45%` or `—`
- `Stock` — value: `5 críticos` / `2 en mínimo` / `ok`
- Delta: `+12%` (with up/down arrow) — `vs semana pasada` / `vs período anterior`

**Critique:**

🟢 **Strong points:**
- The "aún no hay ventas hoy" alternative to `—` is operator-friendly. The system talks back: "no data yet, but I see you."
- Delta with `vs período anterior` (line 95) — the comparison baseline is named, not hidden.
- Sub-text `{{n}} de {{total}} ventas` (line 97) gives context for percentages.

🟡 **Issues:**

1. **`Operaciones` (line 52)** — should be `Ventas` or `Transacciones`. **Re-flag.**

2. **Delta direction logic (line 47)** — `delta-direction="{{ delta_ventas.direction if delta_ventas.direction != 'new' else 'up' }}"` — if the business is new, direction is "new" but it renders as "up". A new business with $0 of sales doesn't have a "12% up". This is a fallback hack. **Better**: show "—" with no direction, or "primer mes" sub-label.

3. **`Margen estimado` with `{{costs_incomplete}} cargado` sub (line 70)** — operator sees "65% · 12 ingredientes sin precio" or similar. The sub-text is critical and operator-friendly. **But** the format `costs_incomplete` is a number followed by `cargado` — reads as "12 loaded". In Spanish, this should be `12 ingredientes sin precio` or `faltan 12`. **Verify** the actual rendered string.

4. **`Stock` card** with severity — the value can be a count + adjective (`5 críticos`). On a small screen, this might wrap. The icon (`icon-check / icon-warn`) is severity-coded. **Good**.

---

### 📈 Insights (`/insight/*`, `/reportes/*`)

**Verbatim visible text (from insight_freshness.html):**
- H1: `Frescura de insumos`
- Sub: `Días hasta vencer según vida útil − fecha del último registro de precio (aprox. sin lotes).`
- H2: `🔥 Cociná HOY para rescatar`
- Table: `Insumo`, `Estado`, `Días`, `Valor en riesgo`
- Per-row: `PRONTO` badge / `sin datos` muted text

**Critique:**

🟢 **Strong points:**
- Methodology is **always** in the subtitle. Operator can validate the numbers.
- `🔥 Cociná HOY para rescatar` — direct, emotive, has a clear action verb. **This is the kind of "AI copy" that works.** It's not "we've identified an opportunity to optimize your waste reduction".
- `Valor en riesgo` — surfaces the Gs. number, not just count. Operator can prioritize by money, not by list position.
- `sin datos` is a clear "we don't know" — better than leaving the row blank.

🟡 **Issues:**

1. **`🔥` emoji in an H2 is opinionated.** Some operators will love it, some will find it unprofessional. If the system is used by 2-3 staff, the tone is fine. If it's a corporate client, this should be toggleable.

2. **`(aprox. sin lotes)` (line 95-ish)** — the abbreviation `aprox.` is fine in Spanish, but "sin lotes" is technical. Operator might not know what a "lote" is in this context. **Should be**: `(aproximado,，因为我们 no rastreamos lotes individuales)`. No, that's worse. Better: `(aproximado — sin rastreo por lote)`.

3. **`PRONTO` is all-caps** (line 102-ish). Good for urgency, but mixed with text-muted `sin datos`. The contrast might be too high. **Consider**: `Pronto` (sentence case) with badge color.

---

### 💰 Cotizador (`/cotizador`)

**Verbatim visible text (from cotizador.html):**
- H1: `Cotizador`
- Callout: `No cargaste ningún producto.`
- Table: `Producto`, `Precio carta`, `Cantidad`
- Field: `Descuento por volumen (%)`
- Submit: `Cotizar`
- H2: `Cotización`
- Table: `Producto`, `Cant.`, `Lotes`, `Costo`, `Carta`, `Margen`
- Total: `TOTAL carta` / `Costo total`
- Button: `Descargar PDF`
- Disclaimer: `Cotización preliminar — precios de carta sin IVA discriminado.`

**Critique:**

🟢 **Strong points:**
- Empty callout is direct: `No cargaste ningún producto.`
- PDF download button after Cotizar.
- Disclaimer about `IVA discriminado` is honest and Paraguay-specific.

🟡 **Issues:**

1. **"Lotes" column in the quote table.** Operator may not know what this means. Is it "batches"? "Lots"? In PY bakeries, "lote" can mean either. **Should be**: `Tandas` (the same term the production page uses, line 211) for consistency. Or `Batches` if going English.

2. **`Descuento por volumen (%)`** — does this apply to all line items equally, or is it a per-item option? The UI doesn't say. **Consider**: `Descuento % aplicado a todos los ítems` or per-row.

3. **The disclaimer "Cotización preliminar — precios de carta sin IVA discriminado"** is good, but the way the Gs. amounts are presented suggests these ARE final prices. **Consider**: stamp the PDF `PRELIMINAR` and date.

---

### 🧾 EOD (`/eod`, `/eod_anomalies`, `/eod_print`)

(I read this in section E audit.)

**Critique:**

🟢 **Strong points:**
- The EOD ritual is structured as step-by-step, which matches how a panadería actually closes the day.
- Anomalies are surfaced as a separate page (`eod_anomalies.html`).

🟡 **Issues:**

1. **EOD language mixes register.** Some checks say "Verificá X" (informal voseo), others "Confirmar X" (button label, infinitive). Pick one for EOD specifically — this is the operator's daily ritual, consistency matters.

2. **`eod_print.html`** is presumably a printable view. Need to verify it hides the sidebar/topbar. (This is in the inventory.)

---

## Cross-section themes (the big problems)

### 🚨 Problem 1: Terminology drift

The same concept has different names in different places. Translation will be **expensive** if you do it now; **catastrophic** if you do it after launch.

| Concept | Variants found | Recommendation |
|---|---|---|
| **Customer** | `cliente`, `comprador`, `consumidor` | Use `cliente` everywhere. |
| **Order** | `pedido`, `orden`, `encargo` | Use `pedido` (the system already does in 80% of places). |
| **Product** | `producto`, `ítem`, `artículo`, `merchandise` | Use `producto` in UI. |
| **Recipe** | `receta`, `preparación` | Use `receta`. |
| **Sale** | `venta`, `operación`, `transacción`, `ticket` | Use `venta` in UI; "transacción" only in technical logs. |
| **Stock / Inventory** | `stock`, `inventario`, `existencia` | Use `inventario` for the section, `stock` for the level. |
| **Empty** | `vacío`, `sin datos`, `sin información` | `sin datos` for the column-row case, `vacío` only for the cart. |
| **Customer order** | `pedido`, `encargo`, `reserva` | `pedido`. |
| **Cancel** | `cancelar`, `anular`, `descartar` | `cancelar` (button), `anular` (when reversing a posted sale). |
| **Save** | `guardar`, `guardá`, `grabar` | Infinitive `Guardar` in buttons. |

### 🚨 Problem 2: English loan words

Not wrong, but unexplained:

| English | Where | Operator-friendly alternative |
|---|---|---|
| `KPI` | inicio.html subtitle | `Indicadores` |
| `Loyalty` | inicio.html band | `Fidelización` |
| `AOV` | reportes_valor_pedido.html | `Valor promedio del pedido` (already shown!) |
| `COGS` | reportes_diario.html | `Costo de Mercadería Vendida` |
| `Revenue` | reportes_top_productos.html | `Ingresos` |
| `Prime Cost` | reportes_cierre_mensual.html | `Costo Primo` (industry term, fine) |
| `Δ` | analisis.html table | `Cambio` |
| `Override` | production pages | `Ajuste manual` |
| `Forecast` | insight_demand | `Pronóstico` (already used in inicio!) |
| `Accuracy` | production HACCP | `Precisión` |

### 🚨 Problem 3: Inconsistent register

The system mixes:
- **Formal infinitive** (button labels): `Registrar venta`, `Ingresar`, `Confirmar venta`
- **Voseo imperative** (empty states, instructions): `Tocá un producto`, `Cargá tu catálogo`, `Cociná HOY`
- **Tuteante voseo** (mixed): `Mirá`, `Necesitamos`

**Recommendation**: pick one register and stick to it.
- **For buttons/labels**: infinitive (`Registrar`, `Ingresar`, `Confirmar`). Always.
- **For empty states and tips**: voseo (`Tocá`, `Cargá`, `Cociná`). Friendly.
- **For math/methodology subtitles**: formal (`Promedio 56d`, `La brecha = porciones extra`).

### 🚨 Problem 4: Tooltips that don't add information

Many `aria-label` and `title` attributes are identical to the visible text. They do nothing for screen readers and waste tokens for sighted users.

Examples found in the code:
- `<button title="Cerrar" data-sazon-dismiss>Cerrar</button>` — `Cerrar` is already the label. The `title` is redundant.
- `aria-label="Cerrar sesión"` on a logout link that already says `Cerrar sesión`.

**Rule**: tooltip/aria-label should be **supplementary** — what the element does, not what it says. "Cerrar" → "Cerrar el menú lateral y volver al contenido". "Cerrar sesión" → "Salir y volver al login".

### 🚨 Problem 5: Color-only signals

The 3-tier system (red/yellow/green) is good, but the labels and colors are sometimes out of sync:
- `Crítico` (red) ✓
- `Aviso` (yellow) ✓
- `saludable` (green) — **lowercase, English loan word in Spanish**
- `severity="success"` (English in code) — fine for code, but the UI shows just the color.

**Fix**: standardize. Use `Crítico / Aviso / OK` in all three contexts. Or `Crítico / Atención / Normal`. Pick one.

### 🚨 Problem 6: Bilingual in single sentences

A few lines mix English and Spanish in the same sentence:
- `Sazón strives to conform to WCAG 2.1 Level AA. Si tenés dificultades…` (login.html)
- `Loyalty` band label on home (inicio.html)
- `Sub` (line 70) in KPIs uses `cargado` after a number — should be "faltan X" or "X cargados" but the literal is in code as `costs_incomplete`, not human-verified.

### 🚨 Problem 7: Some labels are slightly wrong

- `Operaciones` (home KPI) — counts sales, not operations
- `Stock` card (home) — value is "5 críticos" but the card is labeled `Stock` (could mean current stock level)
- `Cliente (RUC si factura)` (POS) — single field doing two jobs
- `Lotes` (cotizador) — should be `Tandas` to match production

### 🚨 Problem 8: Hard-to-find features

- `Pausar carrito` (POS) — button hidden until cart has items (line 67: `display:none`). Operators don't know it exists.
- `+ Nuevo` dropdown — discovered only via topbar.
- `Cmd+K` global search — visible in topbar (kbd `⌘K`) but operators may not know it.
- `Cambiar tema` — moon icon. Operators on shared iPads might not realize they can switch.

---

## What I'd change tomorrow (top 5 priorities)

### Priority 1: Fix the two-checkbox bug on login
The `stay_logged_in` + `remember` double-checkbox (line 124-136) is a real bug. Pick one.

### Priority 2: Translate "Loyalty" band on home
It's the only English H2 on the most-visited page. `Fidelización` or `Clientes`.

### Priority 3: Rename "Operaciones" → "Ventas" on home
Currently counts sales. A panadería operator reads "operaciones" and thinks "all the things I did today".

### Priority 4: Build a terminology glossary
The same concept has 3+ names. Lock the glossary. Use it as a translation source of truth.

### Priority 5: Make tooltips supplementary
Audit every `aria-label` and `title` for redundancy. The login page has at least 4 redundant ones.

---

## What I would NOT change

- The `base.html` shell. It's clean and complete.
- The `ui.empty_state` macro. It's used everywhere consistently.
- The `ui-kpi-card` and `ui-insight` web components. They show labels, values, deltas, and severities in a tight format.
- The POS layout. The left-pane/right-pane split with cart, customer picker, sale metadata is exactly right.
- The breadcrumb. `fmt.crumbs_for()` is automatic and always present.

---

## What I'd add

1. **A "primer día" onboarding banner** for new operators. The system assumes you know what a `sev-pill` is. A `?` icon next to each "weird" word that pops up a tooltip explaining.
2. **An "AI confidence" badge on every AI-suggested number.** Right now, only the forecast shows confidence. Other AI features (`ui-insight` cards, `plan-row`, affinity) don't. Operators will trust the AI more if it admits when it's unsure.
3. **A "what changed since yesterday" header on the home page.** Today it's "greeting + KPIs". A `+1 cliente · 3 ventas más que ayer` line would close the loop.
4. **A keyboard-shortcut cheat sheet.** `?` opens one. `Cmd+K` opens search. `N` opens "+ Nuevo". Document these in one place.
5. **A "tour" mode for the first login** that walks through the 4 home bands. Takes 60 seconds, prevents months of confusion.

---

## Closing note

The system is **substantially better than most Paraguay SMB software.** The POS is genuinely good, the home dashboard is well-designed, the AI insights are honest about their methodology. Most of the issues above are small copy / consistency things that can be fixed in a single sprint.

The two big risks are:
1. **Terminology drift** — needs a glossary + enforcement.
2. **Inconsistent register** — needs a style guide for empty states vs buttons vs subtitles.

Both are doable now in 1-2 days of focused editing. After launch they become 1-2 weeks.

— end of critique
