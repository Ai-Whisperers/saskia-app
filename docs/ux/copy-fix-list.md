# Sazon/Saskia — Comprehensive Copy & UX Fix List

**Generated:** 2026-10-07
**Source:** 110 templates in `app/templates/`, cross-referenced with `app/docs/copy-vos.md` (canonical style guide)
**Format:** Page-by-page actionable fixes, with priority tags

**Priority levels used throughout:**
- 🔴 **P0 — Wrong/lies to the user** (e.g. label says X, data shows Y)
- 🟠 **P1 — Misleading or confusing** (ambiguous, lies by omission, jargon without explanation)
- 🟡 **P2 — Inconsistent with style guide** (uses different terminology than the rest of the app, wrong register, English loan word)
- 🟢 **P3 — Polish** (would be nicer, not blocking)

**Numbering convention:** `PAGE_NAME.SECTION.PRIORITY` — e.g. `VENTAS.6.1` = ventas.html, section 6 (UX/copy flags), priority P1.

**Style guide reference:** `app/docs/copy-vos.md` says:
- Paraguayan voseo Spanish: "guardá", "tenés", "querés" (NOT Argentine voseo)
- Money: `Gs. 729.167` (period thousands sep, no decimals)
- Date: `DD/MM/YYYY`
- Buttons: infinitive verbs (`Registrar`, no `Guardá`)
- Empty states: friendly voseo (`Tocá`, `Cargá`)

---

## GLOBAL FIXES (apply everywhere first)

These should be fixed in a single pass before per-page work, because they affect every page.

### G.1 🟠 Currency symbol drift

**Issue:** `Gs.` is the standard (per `copy-vos.md`), but `₲` (Unicode guaraní) appears in some places.

**Where:**
- `reportes_mermas_cost.html`: `Costo total ₲`, `Costo promedio / evento ₲`
- `ops_status.html`: `Total ₲`
- `suppliers_volatility.html`: `Mín ₲`, `Máx ₲`, `Promedio ₲`
- `riesgos.html`: `Impact Gs.`, `Sev Gs.` (uses "Gs" without dot, also wrong)

**Fix:** Replace all `₲` and bare `Gs` with `Gs.`. Add `.` everywhere.

**Files to edit:**
- `reportes_mermas_cost.html`
- `ops_status.html`
- `suppliers_volatility.html`
- `riesgos.html`

### G.2 🟠 English band labels

**Issue:** English words in H2/H3 on most-visited pages.

**Where:**
- `inicio.html`: `Loyalty` band label (the only English H2 on home)
- `caja.html`: should check, but the title "Caja" is fine; the H2 "Sesiones recientes" is fine

**Fix:** Rename `Loyalty` → `Fidelización` or `Clientes`.

**File:** `inicio.html` line 87.

### G.3 🟠 English loan words in BI section (acceptable but inconsistent)

**Issue:** Mixed English/Spanish in the BI section.

| English | Where | Spanish equivalent |
|---|---|---|
| `KPI` | `inicio.html` subtitle (`KPIs en vivo`) | `Indicadores` |
| `AOV` | `reportes_valor_pedido.html` | (Already explained inline — OK) |
| `COGS` | `reportes_diario.html` (`COGS` label) | `Costo de Mercadería Vendida` or `CMV` |
| `Revenue` | `reportes_top_productos.html` (`Revenue (Gs.)`) | `Ingresos` |
| `Prime Cost` | `reportes_cierre_mensual.html` (column) | (Industry standard — keep) |
| `Override` | `produccion_manana.html` (sub: "override si está definido") | `Ajuste manual` |
| `Forecast` | `insight_demand.html`, `produccion_manana.html` (column) | `Pronóstico` (already used in inicio) |
| `Accuracy` | `produccion_accuracy.html` | `Precisión` (acceptable) |
| `Batches` | `insight_demand.html` (column) | `Tandas` (matches producción pages) |
| `Lotes` | `cotizador.html` (column), `planner.html` (label) | `Tandas` |
| `Δ` | `analisis.html`, `insight_margenes.html` (column headers) | `Cambio` |
| `Override` | `produccion_manana.html` | `Ajuste manual` |

**Fix:** Standardize per the table. Industry terms (`Prime Cost`, `AOV`, `Override`) can stay with inline explanation.

### G.4 🟡 Inconsistent register (voseo vs infinitive)

**Issue:** Mix of imperative voseo (`Guardá`, `Tocá`), infinitive (`Registrar`, `Ingresar`), and Argentine voseo.

**Per `copy-vos.md`:**
- **Buttons:** infinitive (`Registrar`, `Ingresar`, `Cancelar`)
- **Empty states / hints:** Paraguayan voseo (`Tocá`, `Cargá`, `Cociná`)
- **Argentine voseo (`Guardá`)** is **wrong** — must be Paraguayan.

**Where to fix:**
- `produccion_manana.html` line 56: `Guardá plan de mañana` → `Guardar plan de mañana` (button)
- `produccion_manana.html` line 54: `aria-label="Guardá los ajustes..."` → `Guardar los ajustes...`
- `reorder.html`: `Marcar comprado rapido` → `Marcar comprado rápido` (typo) or `Marcar como comprado`
- `receta_form.html` button check

**Search for `Guardá` in all templates and replace with `Guardar` (for buttons) or `Guardá` (for empty states).**

### G.5 🟠 Redundant tooltips / aria-labels

**Issue:** Many `aria-label` and `title` attributes are identical to the visible text. Tooltips should add information, not repeat it.

**Examples found:**
- `dashboard.html`: `<button type="button" aria-label="Cerrar" data-sazon-dismiss>Cerrar</button>` — both are "Cerrar"
- `users.html`: many `aria-label="Cerrar"` on close buttons that already say "Cerrar"
- `recetas.html`, `inventario.html`, `productos.html`: many `aria-label="Cerrar"`
- `riesgos.html`: `tt: ¿Eliminar usuario?` — fine
- `reorder.html`: `tt: Asigná un proveedor antes de reponer` — adds info (good)

**Rule:** `aria-label` should be supplementary. Replace `"Cerrar"` with `"Cerrar el diálogo y volver a {{where}}"` where the context is clear. Or just remove the redundant `aria-label` since the visible text already serves.

### G.6 🟡 Empty state naming inconsistency

**Issue:** Different ways to say "no data".

| Pattern | Used in |
|---|---|
| `Sin datos` | many |
| `No hay ventas registradas` | reports |
| `Todavía no hay...` | many |
| `No hay...` | some |
| `Sin...` | some |

**Per `copy-vos.md`:** use `Todavía no cargaste X` for the "first time" case, `No hay X` for the "filtered out" case.

**Fix:** Standardize. Audit each empty state.

### G.7 🟠 Severity pill naming inconsistency

**Issue:** Three-tier system but labels are inconsistent.

| Tier | Used in |
|---|---|
| `Crítico` (red) | `inicio.html` |
| `Aviso` (yellow) | `inicio.html` |
| `saludable` (green, **lowercase English loan**) | `inicio.html` |
| `severity="success"` (English in code, fine for code) | `inicio.html` |

**Fix:** Use `Crítico / Aviso / OK` in UI. Or `Crítico / Atención / Normal`. Pick one, apply everywhere.

**File:** `inicio.html` line 228.

### G.8 🟠 Column header abbreviations

**Issue:** Inconsistent abbreviation patterns.

| Used | Where |
|---|---|
| `Gs.` | most reports |
| `₲` | `reportes_mermas_cost.html`, `ops_status.html` |
| `Gs` (no dot) | `riesgos.html` (`Impact Gs.`, `Sev Gs.`) |
| `Gs.{{amount}}` | many (correct) |
| `Precio carta` | `cotizador.html` (no unit shown — implicit Gs.) |
| `Costo (Gs.)` | `merma.html` (good) |
| `Costo (Gs.)` vs `Costo/porción (Gs.)` | `analisis.html` |

**Fix:** Use `Gs.` with period everywhere, and `(Gs.)` in column headers that don't show the unit inline. Use `Gs. 729.167` format with period thousands separator per `copy-vos.md`.

---

## PER-PAGE FIXES

---

### LOGIN — `login.html`

**Issues found:**

| # | Pri | Issue | Current | Fix |
|---|---|---|---|---|
| LOGIN.1 | 🔴 | Two persistence checkboxes (bug) | Lines 124-136: `stay_logged_in` (label `Mantener sesión abierta`) AND `remember` (label `Recordar este dispositivo`) | Pick one. `Recordar este dispositivo` is the standard pattern. Remove `stay_logged_in` checkbox and the helper text. |
| LOGIN.2 | 🟠 | English sentence in Spanish UI | Line 156: `Sazón strives to conform to WCAG 2.1 Level AA.` | Translate: `Sazón apunta a cumplir con WCAG 2.1 Nivel AA.` |
| LOGIN.3 | 🟠 | Empty alt on hero | Line 16: `<img src="/static/login-hero.svg" alt="">` | OK for decorative, but add `aria-hidden="true"` for clarity. |
| LOGIN.4 | 🟡 | Tagline can be empty | Line 11: `{{ branding.tagline }}` | Add fallback: `{{ branding.tagline or "Sistema de gestión para panadería" }}` |
| LOGIN.5 | 🟡 | Hints duplicate intent | Line 128-130: `No uses esto en equipos compartidos.` below `Mantener sesión abierta` | If LOGIN.1 is fixed (remove this checkbox), the hint goes away. |
| LOGIN.6 | 🟡 | Punctuation inconsistency | Line 165: `¿Problemas para entrar?` (with `?`); line 206: `¿Olvidaste tu contraseña?` (with `?`). Both correct. | OK |
| LOGIN.7 | 🟠 | Redundant aria-label | Line 20: `aria-label` not set on the alert; relies on `role="alert"`. OK. | OK |
| LOGIN.8 | 🟢 | Forgot password inline error is good | Line 191: `Falta el correo. Escribilo arriba primero...` | Keep, no change. |
| LOGIN.9 | 🟢 | Rate-limit UX is excellent | Lines 28-44 (countdown + escape hatch) | Keep, no change. |

**To add:**
- A "Don't have an account? Contact Iván" hint for new staff (currently only `Contactar al administrador`)
- A "Last login: 2 days ago from this device" sub-text under "Sesión anterior" — would help detect stolen sessions

---

### INICIO — `inicio.html`

This is the most-visited page. Critical.

| # | Pri | Issue | Current | Fix |
|---|---|---|---|---|
| INICIO.1 | 🟠 | `Operaciones` KPI label lies | Line 52: counts sales, not operations | Rename to `Ventas` or `Transacciones` |
| INICIO.2 | 🟠 | English band label | Line 87: `Loyalty` | Rename to `Fidelización` or `Clientes` |
| INICIO.3 | 🟠 | "saludable" is English loan word, lowercase | Line 228: `<span class="sev-pill saludable">alta</span>` (and aviso, critico for the others) | Use `Crítico / Aviso / OK` consistently. Or rename the green pill to `OK` (3 letters, universal). |
| INICIO.4 | 🟠 | Forecast methodology in tiny grey | Line 226-227: `12 semanas · día de la semana · confianza [pill]` | Surface the "Confianza: alta" prominently, drop the "12 semanas" jargon. Operators don't read 12px text. |
| INICIO.5 | 🟡 | "Acciones del día" mixes actionable + informational | Line 122: includes both "Cierre pendiente" (actionable) and "Merma registrada ✓" (informational) | Split: `Tareas pendientes` (actionable, severity-coded) and `Hecho hoy` (muted, with checkmark). |
| INICIO.6 | 🟡 | Pronóstico empty state confusing | Line 261: `Necesitamos ~4 semanas de ventas en este día para pronosticar.` | "en este día" reads as "in this day" not "for this weekday". Rewrite: `Necesitamos ~4 semanas de ventas de este día de la semana para pronosticar.` |
| INICIO.7 | 🟡 | "sugerido por ventas" sub-label | Line 202 | The intent is "calculated from your sales data". Rewrite: `Calculado con tus ventas` or remove. |
| INICIO.8 | 🟡 | Pedidos sub-line uses mid-dot | Line 130: `{{n}} para hoy · {{m}} para mañana` | Mid-dot is barely visible. Add line break or icon. |
| INICIO.9 | 🟡 | Pronóstico band has too much info | Lines 222-263: includes label + 2 metric cards + table + link | Consider collapsing the 2 metric cards into a single sentence. |
| INICIO.10 | 🟡 | "Clientes habituales" sub-label | Line 269: `últimos 30 días · 2+ visitas` | OK, but `2+` is informal. Try `con 2 o más visitas`. |
| INICIO.11 | 🟡 | "AÚN no hay ventas hoy" / "aún no hay ventas hoy" | Line 44: `{% if ventas_gs %}{{ m.gs_full(ventas_gs) }}{% else %}aún no hay ventas hoy{% endif %}` | Inconsistent capitalization (aún vs Aún). Pick one. |
| INICIO.12 | 🟠 | "Merma del día — registrada ✓" | Line 185 | OK, but the ✓ emoji is non-standard. Use a checkmark icon or text `[OK]`. |
| INICIO.13 | 🟢 | Birthday row uses 🎂 | Line 162: `🎂 Cumpleaños de la semana` | Emoji OK in this context. |
| INICIO.14 | 🟢 | "Regulars" terminology | Line 268: `Clientes habituales` | OK, but inconsistent with `regulars` in code. Use `Clientes habituales` in UI. |
| INICIO.15 | 🟠 | KPI deltas show wrong direction for new business | Line 47: `delta-direction="up" if direction == "new"` | New business shouldn't show "up". Show "—" or "primer mes" sub. |
| INICIO.16 | 🟡 | "12 semanas · día de la semana · confianza" | Line 226 | This is technical methodology, not operator language. Replace with `Confianza del pronóstico: [alta]`. |
| INICIO.17 | 🟠 | Loyalty sub "X de Y ventas" | Line 97: `{{enrollment_with_today}} de {{enrollment_total_today}} ventas` | "X de Y ventas" reads as "X of Y sales" — confusing. Try `{{enrollment_total_today}} ventas · {{enrollment_with_today}} con cliente`. |
| INICIO.18 | 🟢 | "Todo en orden por hoy." | Line 193 | Good. Keep. |

**To add:**
- A `+1 cliente nuevo vs. ayer` line in the "Hoy" band
- A "What changed since yesterday" header showing day-over-day deltas inline
- An AI confidence badge on every `ui-insight` card
- An onboarding banner for new operators (visible only on first login)

---

### VENTAS (POS) — `ventas.html`, `ventas_detalle.html`, `ventas_historial.html`, `ventas_qa.html`

| # | Pri | Issue | Current | Fix |
|---|---|---|---|---|
| VENTAS.1 | 🟠 | Page H1 doesn't match H2 | Line 5 H1: `Ventas`; Line 16 H2: `Nueva venta` | Confusing for first-time. Change H1 to `Nueva venta` (matches H2); `/ventas/historial` keeps `Ventas — Historial`. |
| VENTAS.2 | 🟠 | `Cliente (RUC si factura)` is one field doing two jobs | Line 201-ish | Split: customer picker on top, RUC field below with `Si emitís Factura, completá el RUC` hint. |
| VENTAS.3 | 🟠 | "Lotes" in cotizador → "Tandas" globally | `cotizador.html` line `Lotes` | Rename to `Tandas` to match `produccion_manana.html` (line 211: `{{p.batch_count}} tanda{{'s' if p.batch_count > 1}}`). |
| VENTAS.4 | 🟡 | Cart "Pausar" button hidden until cart has items | Line 67: `style="display:none"` | Always show, disabled until cart is non-empty. First-time users won't discover the feature otherwise. |
| VENTAS.5 | 🟡 | `Cancelar` button (bottom) unclear | Line ~1450: `Cancelar` | Specify: `Cancelar (vacía el carrito)`. |
| VENTAS.6 | 🟡 | Held-sale panel copy unclear | Line 137: `Ventas en espera` | OK, but add a sub-hint: `Pausaste la venta de un cliente. Retomá cuando vuelva.` |
| VENTAS.7 | 🟡 | "Forma de pago" placeholder vs default | Line 183: `placeholder='Seleccioná forma de pago…'` but value is `payment_method_default` | Cosmetic. Either show default with "(default)" tag or hide placeholder when default is set. |
| VENTAS.8 | 🟡 | 7-column cart table on mobile | Lines 84-92: 7 columns | Test on tablet. Will wrap badly on 10" iPad. |
| VENTAS.9 | 🟢 | "Dto." abbreviation | Line 89: `Dto. %` | Paraguayan receipts use `Dto.` — confirm with Saskia. |
| VENTAS.10 | 🟢 | "Tocá un producto" empty state | Line 78 | Perfect. Keep. |
| VENTAS.11 | 🟢 | "Para transferencia/QR indicá el alias..." | Line 186 | Excellent. Keep. |
| VENTAS.12 | 🟢 | Held-sale tooltip is informative | Line 68: `Pausar carrito — el cliente puede volver y retomar` | Good. Keep. |
| VENTAS.13 | 🟢 | "Nuevo" dropdown in topbar | base.html line 132: `Crear nuevo — elegí: Venta, Pedido, Producto, Ingrediente, Receta o Cliente` | Excellent. **Missing: Proveedor** (suppliers exist). Add to dropdown. |
| VENTAS.14 | 🟠 | "Boleta Resimple (IRE RESIMPLE)" | Line 199 | OK but the dual-name might confuse. Consider just `Boleta Resimple` (the colloquial form). |
| VENTAS.15 | 🟢 | Propina 0/5/10% buttons | Lines 109-112 | OK. Paraguay rarely tips, so this is generous. |
| VENTAS.16 | 🟠 | Propina field has `min="0" step="1000"` | Line 112 | Reasonable. But operator might type `5000` and have to convert. Consider adding a "Propina sugerida: Gs. 5.000" smart suggestion based on total. |
| VENTAS.17 | 🟠 | History page: `Historial de ventas` filters `Rango de días` | `ventas_historial.html` line 73 | `Rango de días` is ambiguous. Try `Últimos N días` (consistent with other reports). |
| VENTAS.18 | 🟠 | History page: `Ver anuladas` | `ventas_historial.html` line 76 | "Ver anuladas" is good, but consider `Incluir anuladas` toggle. |
| VENTAS.19 | 🟠 | History table 10 columns | `ventas_historial.html` lines 96-105 | Wide table. Consider a printable view. |
| VENTAS.20 | 🟢 | Anular venta tooltip | `ventas_historial.html` line ~150: `¿Anular venta #X?` | Good. |
| VENTAS.21 | 🟢 | `Re-petir este pedido` tooltip | `cliente_detalle.html` line ~250 | OK. |
| VENTAS.22 | 🟠 | `Atendido por` column header | `ventas_historial.html` line 105 | Should be `Operador` to match home page (`ventas_qa` uses `Operador`). |

**To add:**
- A "Quick repeat" button on each history row to re-do the same sale in 1 click
- A "Last sale" pre-fill on the POS (most common: same customer, same products)
- An "Offline mode" indicator if the network is down (the app works locally-first per AGENTS.md)

---

### CLIENTES — `clientes.html`, `cliente_detalle.html`, `cliente_editar.html`, `clientes_nuevo.html`, `clientes_duplicados.html`

| # | Pri | Issue | Current | Fix |
|---|---|---|---|---|
| CLIENTES.1 | 🟡 | `Cliente seleccionado` (label) is awkward | `pedidos_nuevo.html` line ~75 | Try `Cliente` with a small "selected" badge. |
| CLIENTES.2 | 🟡 | `Sub · Ped` table header | `clientes.html` line ~250 | Cryptic. Should be `Pedidos abiertos` or `Suscripciones`. |
| CLIENTES.3 | 🟠 | "Tooltip: Click to copy ID" | `clientes.html` line ~150 | Useful for support. Keep. |
| CLIENTES.4 | 🟠 | `clientes_duplicados.html` H1 | Line ~50: `Grupo · canónico {{name}} (id={{id}})` | The `(id=X)` is internal noise. Drop it. |
| CLIENTES.5 | 🟠 | `cliente_editar.html`: `Tipo de operación` and `Tipo de documento` are separate labels but they refer to the same RUC/CI field | Lines 80-90 | One field for `RUC / CI` with a `Tipo` selector. |
| CLIENTES.6 | 🟡 | `Acepta recibir promos (WhatsApp)` label | `cliente_editar.html` line 70 | The parenthetical "(WhatsApp)" is info, not a label modifier. Move to a hint below the checkbox. |
| CLIENTES.7 | 🟡 | `Cumpleaños` placeholder | `cliente_editar.html` line 75: `DD-MM o DD-MM-AAAA` | Per `copy-vos.md`, date format is `DD/MM/YYYY`. Update placeholder to `DD/MM/AAAA` (PY uses AAAA for year, not YYYY). |
| CLIENTES.8 | 🟡 | `DD-MM o DD-MM-AAAA` | Same | Confusing. Pick one format. Per `copy-vos.md`: `DD/MM/AAAA`. |
| CLIENTES.9 | 🟠 | `Restricciones ({{n}})` and `Preferencias ({{n}})` | `cliente_editar.html` line 95-100 | `Restricciones` and `Preferencias` are different concepts. Make the sub-headers clearer: `Restricciones alimentarias` and `Preferencias de orden`. |
| CLIENTES.10 | 🟡 | `Cliente seleccionado` placeholder | `pedidos_nuevo.html` line ~80 | OK. |
| CLIENTES.11 | 🟢 | `Sin compras hace más de 90 días` | `cliente_detalle.html` line ~150 (tooltip) | Useful churn signal. Keep. |
| CLIENTES.12 | 🟢 | `Recontactar` tooltip | Same | OK. |
| CLIENTES.13 | 🟢 | `Compró en los últimos N días` tooltip | Same | OK. |
| CLIENTES.14 | 🟠 | `Calle principal`, `Calle secundaria / entrecalles`, `Número`, `Edificio`, `Piso`, `Unidad / Puerta`, `Barrio` — 7 address fields | `pedidos_nuevo.html` lines ~150-180 | Excessive. Paraguayan addresses usually: Calle + Número + Barrio. Consider: 1 textarea `Dirección completa` + structured fallback. |
| CLIENTES.15 | 🟡 | `Departamento` and `Ciudad` | Same | PY uses `Departamento` (like Estado in Brazil). OK. |
| CLIENTES.16 | 🟠 | `Lo antes posible` vs `En una franja horaria (preferida, no es garantía)` radio buttons | `pedidos_nuevo.html` line ~200 | The second is a long parenthetical. Try: `Franja horaria preferida (no es garantía)`. |
| CLIENTES.17 | 🟢 | `Canjear puntos` | `cliente_detalle.html` line ~190 | Good, clear action. |
| CLIENTES.18 | 🟡 | "Puntos a canjear" placeholder `ej. 10` | `cliente_detalle.html` | OK, but mention "100 puntos = Gs. 5.000" or whatever the conversion is. |
| CLIENTES.19 | 🟠 | `Compras últimos 30 días` | `pedido_detalle.html`, `pedidos.html` | Inconsistent capitalization. Should be `Compras últimos 30 días` (lowercase 30). |
| CLIENTES.20 | 🟢 | `Compró en los últimos N días` tooltip pattern | Used 3+ times | Standardize. |

**To add:**
- A "Customer since" date on `cliente_detalle.html` (currently missing)
- A "Last contacted" date
- A "Lifetime value (Gs.)" KPI card

---

### PRODUCTOS — `productos.html`, `producto_detalle.html`, `producto_form.html`, `productos_importar.html`

| # | Pri | Issue | Current | Fix |
|---|---|---|---|---|
| PRODUCTOS.1 | 🟠 | "Margen bajo: menos del 40%" tooltip | `productos.html` | OK. Add "objetivo: 50%" for context. |
| PRODUCTOS.2 | 🟠 | "Vendés por debajo del costo" tooltip | Same | OK. |
| PRODUCTOS.3 | 🟡 | "Sin precios de ingredientes cargados" tooltip | Same | The word "cargados" is past participle, but used as adj. Try `Sin precio de ingredientes cargado` (singular) or rephrase. |
| PRODUCTOS.4 | 🟠 | `Costo base con más de 90 días — revisá precios` | Same | OK. |
| PRODUCTOS.5 | 🟠 | `Costo base de hace N días` vs `Costo actualizado hace N día(s)` | Same | Two tooltips for similar concept. Unify. |
| PRODUCTOS.6 | 🟡 | "Edición masiva" H2 | `productos.html` line 33 | OK. |
| PRODUCTOS.7 | 🟠 | `Porción` column header | `productos.html` line ~200 | What's a "Porción"? Try `Tamaño` or `Porción/Envase`. |
| PRODUCTOS.8 | 🟠 | `Mayorista` column | Same | Should be `Precio mayorista (Gs.)` for clarity. |
| PRODUCTOS.9 | 🟠 | `Prime Cost` column | Same | Per G.3, this is industry standard, but operators may not know it. Add a tooltip explaining. |
| PRODUCTOS.10 | 🟠 | `% Costo` column | Same | Should be `Costo %` (noun) or `Costo/Venta %`. |
| PRODUCTOS.11 | 🟡 | `Costo act.` | Same | Truncated. Try `Costo actual` or `Costo hoy`. |
| PRODUCTOS.12 | 🟠 | `Disp.` column | Same | Truncated. Try `Disponible` or `Activo`. |
| PRODUCTOS.13 | 🟠 | `Producido` column | Same | Inconsistent. Could be `Producido 30d` (with time period). |
| PRODUCTOS.14 | 🟢 | `Todavía no cargaste productos` empty state | Same | Per `copy-vos.md`, this is the correct pattern. |
| PRODUCTOS.15 | 🟠 | `SKU / Código de barras` label | `producto_form.html` line ~50 | The `/` is informal. Try `SKU o código de barras`. |
| PRODUCTOS.16 | 🟠 | `Etiqueta de porción` | `producto_form.html` line ~55 | Unclear. Try `Tamaño de la porción` (e.g., "100g", "1 unidad"). |
| PRODUCTOS.17 | 🟡 | `Precio mayorista (Gs.)` label | `producto_form.html` line 60 | OK. |
| PRODUCTOS.18 | 🟠 | `IVA%` label | `producto_form.html` line 65 | Should be `IVA (%)` or `IVA` (since the field is a percentage). |
| PRODUCTOS.19 | 🟠 | `Requiere RSPA` label | `producto_form.html` line 80 | RSPA is Paraguayan health registration. Add tooltip: `Registro Sanitario de Producto Alimenticio (INAN)`. |
| PRODUCTOS.20 | 🟠 | `Nº Registro RSPA` | Same | Inconsistent `Nº` vs `Número`. Pick one. |
| PRODUCTOS.21 | 🟠 | `Vencimiento RSPA` | Same | OK. |
| PRODUCTOS.22 | 🟡 | `Slug URL (opcional, se genera del nombre)` | `producto_form.html` line 95 | "se genera del nombre" is informal. Try `se genera automáticamente del nombre`. |
| PRODUCTOS.23 | 🟢 | `Disponibilidad` section header | `producto_form.html` | OK. |
| PRODUCTOS.24 | 🟢 | `Visible en el menú público (tablet)` | Same | OK. |
| PRODUCTOS.25 | 🟠 | CSV import format help | `productos_importar.html` | OK. |
| PRODUCTOS.26 | 🟠 | `Formato del CSV` H2 | `productos_importar.html` line 11 | OK. |
| PRODUCTOS.27 | 🟠 | "Stock insuficiente" tooltip | `productos.html` | Inconsistent with `Stock bajo` elsewhere. |

**To add:**
- A "Duplicate product" button
- A "Print price tags" button (common panadería workflow)
- A "Recently sold" indicator
- A "Best/worst seller" badge

---

### RECETAS — `recetas.html`, `receta_detalle.html`, `receta_form.html`, `recipe_photos.html`

| # | Pri | Issue | Current | Fix |
|---|---|---|---|---|
| RECETAS.1 | 🟠 | `Foto` column header in recetas | `recetas.html` | Should be `Imagen`. |
| RECETAS.2 | 🟠 | `Costo total (Gs.)` | `recetas.html` | OK. |
| RECETAS.3 | 🟠 | `Dificultad` aria-label | `recetas.html` line ~70: `Dificultad {{r.difficulty}}` | Incomplete. Try `Dificultad {{r.difficulty}} de 5`. |
| RECETAS.4 | 🟠 | "Sin foto" aria-label | Same | OK. |
| RECETAS.5 | 🟠 | `Sin foto` aria-label in receta_detalle | `receta_detalle.html` | OK. |
| RECETAS.6 | 🟠 | `Etiqueta de porción` | (re-used) | See PRODUCTOS.16. |
| RECETAS.7 | 🟠 | `Rinde` label | `receta_form.html` | Per `copy-vos.md`, full form is `Rinde (porciones)`. Update. |
| RECETAS.8 | 🟠 | `Escalar rendimiento` | `receta_form.html` | OK. |
| RECETAS.9 | 🟠 | `Tiempos` legend | `receta_form.html` | OK. |
| RECETAS.10 | 🟠 | `Prep.`, `Cocción` labels | `receta_form.html` | Abbreviated. Try `Tiempo de prep.` and `Tiempo de cocción`. |
| RECETAS.11 | 🟠 | `Dificultad` aria-label | `receta_form.html` | Add `(1-5)`. |
| RECETAS.12 | 🟠 | `Después de guardar, crear producto` | `receta_form.html` line ~150 | "Después de guardar" is the action sequence. The full text is `Genera un Producto vinculado a esta receta, con precio sugerido (costo × 3).` The `× 3` is internal jargon. Try `costo + 200% de margen` or `costo × 3 (margen 200%)`. |
| RECETAS.13 | 🟠 | "1=fácil, 5=experto" tooltip | `receta_detalle.html` | OK. |
| RECETAS.14 | 🟠 | "Margen estimado" tooltip | `receta_detalle.html` | OK. |
| RECETAS.15 | 🟠 | `Secuencia Completa de Preparación (Incluye Sub-recetas)` | `receta_detalle.html` | H2 appears twice (line ~50 and ~60). Probably a duplicate. Verify. |
| RECETAS.16 | 🟠 | `1. Preparación de Sub-receta` | `receta_detalle.html` | Numbered headings. OK. |
| RECETAS.17 | 🟠 | `2. Mezcla de la Base (X min)` | Same | OK. |
| RECETAS.18 | 🟠 | `3. Ensamblaje y Decoración` | Same | OK. |
| RECETAS.19 | 🟠 | `Desglose de costo` H2 | Same | OK. |
| RECETAS.20 | 🟠 | `Etiquetas dietarias` legend | `receta_form.html` | OK. |
| RECETAS.21 | 🟠 | `Etiquetas de Menú` legend | Same | OK. |
| RECETAS.22 | 🟡 | `Ingredientes y sub-recetas` H2 | `receta_form.html` | OK. |
| RECETAS.23 | 🟡 | `Ingredientes efectivos` H2 | Same | OK. |
| RECETAS.24 | 🟠 | `Notas de receta` H2 | Same | Could be just `Notas`. |
| RECETAS.25 | 🟠 | `Producción` H2 | Same | OK. |
| RECETAS.26 | 🟠 | `Escandallo` H2 | Same | "Escandallo" is industry standard. OK. |
| RECETAS.27 | 🟠 | `Elegir foto` H2 | Same | OK. |
| RECETAS.28 | 🟠 | `0.000` placeholder | `receta_form.html` | Should be `0.0` or `0` for clarity. |
| RECETAS.29 | 🟠 | "opcional" placeholder | Same | In Spanish, the label says "Rinde" but placeholder says "opcional". Confusing. |
| RECETAS.30 | 🟠 | Long notes placeholder | `receta_form.html` line ~200 | The placeholder has line breaks and examples. Excellent for guidance. |
| RECETAS.31 | 🟢 | "Cantidad total" column | `receta_detalle.html` | OK. |
| RECETAS.32 | 🟢 | "Origen" column | Same | OK. |
| RECETAS.33 | 🟢 | "Tipo" column | Same | OK. |

**To add:**
- A "Print recipe" button (kitchen workflow)
- A "Scale" calculator (1x / 2x / 0.5x buttons)
- A "Recently cooked" indicator
- A "Cost change log" (when ingredient prices change)

---

### INVENTARIO — `inventario.html`, `inventario_form.html`, `inventario_movimientos.html`, `inventario_auditoria_etiquetas.html`, `carga_inicial.html`

| # | Pri | Issue | Current | Fix |
|---|---|---|---|---|
| INV.1 | 🟠 | `Recibir` column | `inventario.html` | OK. |
| INV.2 | 🟠 | `Variantes` column | Same | OK. |
| INV.3 | 🟠 | `Estado` column | Same | OK. |
| INV.4 | 🟠 | `Mostrar agotados` label | `ingrediente_detalle.html` line ~80 | OK. |
| INV.5 | 🟠 | `Tamaño del paquete` label | `ingrediente_detalle.html` line ~85 | OK. |
| INV.6 | 🟠 | `Precio (Gs.)` label | Same | OK. |
| INV.7 | 🟠 | `Stock inicial (en und. del paquete)` | Same | "und." is abbreviation. Try `unidades del paquete`. |
| INV.8 | 🟠 | `Stock de apertura` label | `inventario_form.html` | OK. |
| INV.9 | 🟠 | `Fecha de apertura` | Same | "Apertura" in this context = "first time using this ingredient". Could be `Fecha de inicio` or `Fecha de primera compra`. |
| INV.10 | 🟠 | `Stock mínimo (para alertas)` label | `inventario_form.html` | OK. |
| INV.11 | 🟠 | `Punto de reorden (override)` | Same | "override" is English. Per G.3, rename to `Punto de reorden (ajuste manual)`. |
| INV.12 | 🟠 | `Precio de compra (Gs., por unidad)` | Same | OK. |
| INV.13 | 🟠 | `Vida útil (días)` | Same | OK. |
| INV.14 | 🟠 | `Posible contaminación cruzada con trigo (bloquea "sin TACC")` | Same | Long label. Could be `Contaminación cruzada con trigo`. Hint: `Marca esta opción si el ingrediente puede tener contacto con trigo; bloquea recetas "sin TACC"`. |
| INV.15 | 🟠 | `Lead time proveedor (días)` | `inventario_form.html` | "Lead time" is English. Per `copy-vos.md`, this should be `Tiempo de reposición (días)` or `Plazo de entrega del proveedor (días)`. |
| INV.16 | 🟠 | `Clasificación y conservación` legend | `inventario_form.html` | OK. |
| INV.17 | 🟠 | `Conservación (HACCP)` | `ingrediente_detalle.html` | OK. |
| INV.18 | 🟠 | `Alérgenos (INAN)` | `inventario.html` | INAN is the regulator. Operator tooltip would help. |
| INV.19 | 🟠 | `Historial de precios (N registros)` | `ingrediente_detalle.html` | OK. |
| INV.20 | 🟠 | `Pronóstico — ¿cuándo me quedo corto?` | Same | Good. |
| INV.21 | 🟠 | `Horizonte (días)` label | `ingrediente_detalle.html` | Operator may not know what "horizonte" means in this context. Try `Cuántos días adelante querés ver` or `Pronóstico para los próximos N días`. |
| INV.22 | 🟠 | `¿Llenar todos los ingredientes a 2× el mínimo?` | `inventario.html` | The "2×" is informal. Try `¿Llenar todos los ingredientes al doble del mínimo?`. |
| INV.23 | 🟠 | `Auditoría de etiquetas` H2 | `inventario_auditoria_etiquetas.html` | OK. |
| INV.24 | 🟡 | `Detectado por migración 061 pero no en este run` | Same | Internal jargon. Operator shouldn't see this. Hide or rewrite. |
| INV.25 | 🟠 | `Carga inicial de inventario` H2 | `carga_inicial.html` | OK. |
| INV.26 | 🟠 | `Stock real hoy` column | Same | OK. |
| INV.27 | 🟠 | `Precio ref.` column | Same | "ref." abbreviation. Try `Precio referencia` or `Precio de ref.`. |
| INV.28 | 🟠 | `vs. mercado: Gs. X Gs/Y — notes` tooltip | `inventario.html` | Excellent — surfaces market comparison. Keep. |
| INV.29 | 🟠 | `Movimientos de stock` H2 | `inventario_movimientos.html` | OK. |
| INV.30 | 🟠 | `Tipo` column | Same | OK. |
| INV.31 | 🟠 | `Cantidad` column | Same | OK. |
| INV.32 | 🟠 | `Balance antes / después` | Same | Spanish "balance" is ambiguous (could mean balance sheet). Try `Stock antes` / `Stock después`. |
| INV.33 | 🟠 | `Motivo` column | Same | OK. |
| INV.34 | 🟠 | `Referencia` column | Same | OK. |
| INV.35 | 🟠 | `Operador` column | Same | OK. |
| INV.36 | 🟠 | `Sin movimientos registrados` tooltip | Same | OK. |
| INV.37 | 🟢 | `Empezá cargando tus ingredientes` tooltip | `inventario.html` | Excellent voseo. Keep. |
| INV.38 | 🟢 | `¡Stock negativo!` tooltip | `inventario.html` | Per `copy-vos.md`: `¡Stock negativo! <ingredient> está en <qty> <unit>. Hacé un recuento.` Could be expanded. |

**To add:**
- A "Bulk price update" (all flour went up 10%)
- A "Stock take" mode (print a list, scan to mark)
- A "Last counted" date

---

### PRODUCCIÓN — `produccion.html`, `produccion_manana.html`, `produccion_prep.html`, `produccion_prep_recipes.html`, `produccion_accuracy.html`, `produccion_haccp.html`, `produccion_print.html`, `planner.html`

| # | Pri | Issue | Current | Fix |
|---|---|---|---|---|
| PROD.1 | 🟠 | `Guardá plan de mañana` button (Argentine voseo) | `produccion_manana.html` line 56 | Per G.4, change to `Guardar plan de mañana`. |
| PROD.2 | 🟠 | `aria-label="Guardá los ajustes..."` | `produccion_manana.html` line 54 | Same. Change to `Guardar`. |
| PROD.3 | 🟠 | `Ingreso estimado mañana` sub: `precio catálogo × cantidad` | `produccion_manana.html` line 70 | "catálogo × cantidad" is engineering-honest. Try `Basado en precio de carta`. |
| PROD.4 | 🔴 | `🧾 Pedidos para mañana (N)` appears TWICE | `produccion_manana.html` line 86 and 95 | Bug — H2 then `<summary>`. Remove the H2. |
| PROD.5 | 🟠 | `Confianza media` label is misleading | `produccion_manana.html` line 72 | "Confianza media" sounds like a fixed value. The value is the actual % (e.g., 65%). Rename to `Confianza promedio (%)`. |
| PROD.6 | 🟠 | `{{n}} con confianza <70%` sub | Same | OK as a guardrail. |
| PROD.7 | 🟠 | `🟧 Horneado extra N hoy` | `produccion.html` | Emoji in H2. Inconsistent with other pages. |
| PROD.8 | 🟠 | `🔥 Merma — producto` | `produccion.html` | Same. |
| PROD.9 | 🟠 | `📋 Pegá varios horneados extra (CSV)` | `produccion.html` | OK — operator workflow. |
| PROD.10 | 🟠 | `Aún no hay ventas registradas` | `produccion.html` | "Aún" capitalized inconsistently. Per `copy-vos.md`, use `Todavía no hay ventas registradas`. |
| PROD.11 | 🟠 | `Sin plantilla semanal` | Same | OK. |
| PROD.12 | 🟠 | `Plan frío (datos insuficientes)` | Same | "Frío" is jargon. Try `Sin suficientes datos` or `Plan estimado (datos insuficientes)`. |
| PROD.13 | 🟠 | `Plan vacío (cantidades en cero)` | Same | OK. |
| PROD.14 | 🟠 | `Ingredientes necesarios` | Same | OK. |
| PROD.15 | 🟠 | `Producción por día` | Same | OK. |
| PROD.16 | 🟠 | `Ingredientes de la semana` | Same | OK. |
| PROD.17 | 🟠 | `Cerrar turno: —` | `produccion.html` | The em-dash is placeholder. Should be `Cerrar turno` with the actual count or `Cerrar turno: ninguno pendiente`. |
| PROD.18 | 🟠 | `¿Qué significa el porcentaje de confianza?` | Same | H2 question. OK. |
| PROD.19 | 🟠 | `CSV` label | Same | OK. |
| PROD.20 | 🟠 | `Lotes perdidos` label | Same | "Lotes perdidos" should be `Tandas perdidas` (per VENTAS.3). |
| PROD.21 | 🟠 | `Justificación (opcional — útil para "no se vendió" o "cerrado por feriado")` | Same | Excellent helper text. |
| PROD.22 | 🟠 | `Cerrar turno` button | Same | OK. |
| PROD.23 | 🟠 | `Hicimos lo planeado (o más)` | Same | Voseo. OK. |
| PROD.24 | 🟠 | `No horneado: Cero unidades. Decí por qué abajo.` | Same | The "Decí por qué" is Argentine voseo. Per G.4, fix to Paraguayan. Try `Indicá por qué abajo`. |
| PROD.25 | 🟠 | `Confianza del cálculo: N%. Bajo = se queda cerca de la meta; Medio = puede variar ±10%; Alto = conviene revisar` | `produccion.html` line ~300 | Excellent. Keep. |
| PROD.26 | 🟠 | `Alta confianza` / `Confianza media` / `Confianza baja` tooltips | `produccion_manana.html` | The labels `alta/media/baja` are fine but the visual presentation (sev-pill) should match inicio.html (Crítico/Aviso/OK). |
| PROD.27 | 🟠 | `Forecast del algoritmo (rolling 14d / plantilla / ajuste)` | `produccion_manana.html` | OK, internal label. |
| PROD.28 | 🟠 | `Unidades ya comprometidas vía pedidos` | Same | OK. |
| PROD.29 | 🟠 | `Plan final (forecast + pedidos, editable)` | Same | OK. |
| PROD.30 | 🟠 | `Editá este número; es lo que vamos a producir` | Same | Voseo. OK per `copy-vos.md`. |
| PROD.31 | 🟠 | `Qué producir mañana` H2 | `produccion_manana.html` | OK. |
| PROD.32 | 🟠 | `Plan de preparación semanal` H2 | `produccion_prep.html` | OK. |
| PROD.33 | 🟠 | `Volver a la vista semana` tooltip | Same | OK. |
| PROD.34 | 🟠 | `Falta = no alcanza; Justo = alcanza justo; Suficiente = sobra` | Same | Excellent legend. Keep. |
| PROD.35 | 🟠 | `Recetas para preparar hoy` H2 | `produccion_prep_recipes.html` | OK. |
| PROD.36 | 🟠 | `Totales cruzados (suma de todas las recetas — debería coincidir con /shopping-list)` | Same | OK. |
| PROD.37 | 🟠 | `Volver al plan del día` tooltip | Same | OK. |
| PROD.38 | 🟠 | `Ver totales agregados de la semana` tooltip | Same | OK. |
| PROD.39 | 🟠 | `Lista de compras (lo que falta por comprar)` | Same | OK. |
| PROD.40 | 🟠 | `Sin stock registrado` | Same | OK. |
| PROD.41 | 🟠 | `Stock suficiente` | Same | OK. |
| PROD.42 | 🟠 | `Stock bajo` | Same | OK. |
| PROD.43 | 🟠 | `Aparece en` column | Same | OK. |
| PROD.44 | 🟠 | `Precisión del plan vs. producción real` H2 | `produccion_accuracy.html` | OK. |
| PROD.45 | 🟠 | `Días con mayor desvío` | Same | OK. |
| PROD.46 | 🟠 | `Días mejor calibrados` | Same | OK. |
| PROD.47 | 🟠 | `Accuracy` column | Same | "Accuracy" is English. Per G.3, change to `Precisión` or `Ajuste %`. |
| PROD.48 | 🟠 | `Sobró hornear` | Same | OK. |
| PROD.49 | 🟠 | `Faltó hornear` | Same | OK. |
| PROD.50 | 🟠 | `No hay datos de producción en este período` | Same | OK. |
| PROD.51 | 🟠 | `Registro HACCP — Temperatura de freezers` H2 | `produccion_haccp.html` | OK. |
| PROD.52 | 🟠 | `📝 Registrar lectura` | Same | Emoji H2. |
| PROD.53 | 🟠 | `⏰ Pendientes hoy` | Same | Same. |
| PROD.54 | 🟠 | `📊 Lecturas del {{ for_date }}` | Same | Same. |
| PROD.55 | 🟠 | `📅 Últimos 7 días` | Same | Same. |
| PROD.56 | 🟠 | `Turno` label with `AM (apertura)` / `PM (cierre)` | `produccion_haccp.html` | OK, but explain `AM/PM` is the only field — operator might expect more. |
| PROD.57 | 🟠 | `Temperatura (°C)` label | Same | OK. |
| PROD.58 | 🟠 | `Ubicación` label | Same | OK. |
| PROD.59 | 🟠 | `Producción — Plan del día` H2 | `produccion_print.html` | OK. |
| PROD.60 | 🟠 | `Productos a hornear el {{day.date}}` aria | Same | OK. |
| PROD.61 | 🟠 | `Plan manual de producción` H2 | `planner.html` | OK. |
| PROD.62 | 🟠 | `Receta` label | Same | OK. |
| PROD.63 | 🟠 | `Tandas` label | Same | OK. |
| PROD.64 | 🟠 | `Stock negativo — revisar ventas sin reposición` tooltip | Same | OK. |
| PROD.65 | 🟠 | `Faltante` column | Same | OK. |
| PROD.66 | 🟠 | `Unit Gs.` column | Same | "Unit" is English. Per G.3, `Precio unit. (Gs.)` or `Unitario (Gs.)`. |
| PROD.67 | 🟠 | `Costo faltante` column | Same | OK. |
| PROD.68 | 🟠 | `Status` column | Same | English. Try `Estado`. |
| PROD.69 | 🟡 | Tooltip: `¿Cargar plan desde plantilla?` | `produccion.html` | OK. |
| PROD.70 | 🟡 | `UI v2 (DEMANDA, META, REAL, Pedidos)` | Same | Internal label. Hide. |
| PROD.71 | 🟡 | `Origen (mouseover para detalle)` | Same | OK. |
| PROD.72 | 🟡 | `Set every row's qty to its target and check 'done'` | Same | English in tooltip. Translate. |
| PROD.73 | 🟡 | `Las estrellas indican la dificultad de la receta (1 = muy fácil, 5 = muy difícil). Útil para elegir qué hornear cuando estás cansado/a.` | Same | Excellent. Keep. |
| PROD.74 | 🟠 | `Elegí un producto y la cantidad a producir hoy` tooltip (5 times) | Same | Repetitive tooltip. Either inline it as a placeholder or show once. |
| PROD.75 | 🟠 | `Elegí un producto y la cantidad a producir hoy` | Same | OK. |
| PROD.76 | 🟠 | `Mostrar N filas` | Same | OK. |
| PROD.77 | 🟠 | `Origen ?` column | Same | `?` after column name. Add a real tooltip. |

**To add:**
- A "Yesterday vs. plan" comparison
- A "Most over/under produced" leaderboard
- A "Print HACCP" button
- A "Last 7 days summary" on the production page header

---

### PEDIDOS — `pedidos.html`, `pedidos_nuevo.html`, `pedido_board.html`, `pedido_detalle.html`, `pedido_stock_preview.html`, `pedido_publico.html`

| # | Pri | Issue | Current | Fix |
|---|---|---|---|---|
| PED.1 | 🟠 | `Cocina — pedidos del día` H2 | `pedido_board.html` | "Cocina" is good. |
| PED.2 | 🟠 | `Activar sonido de nuevos pedidos` aria | Same | OK. |
| PED.3 | 🟠 | `Desactivar audio` tooltip | Same | OK. |
| PED.4 | 🟠 | `Filtrar pedidos` aria | Same | OK. |
| PED.5 | 🟠 | `Pedidos por estado` aria | Same | OK. |
| PED.6 | 🟠 | `Pedido asociado` H2 | `pedido_detalle.html` | OK. |
| PED.7 | 🟠 | `Prometido` H2 | Same | "Prometido" = promised delivery date. OK. |
| PED.8 | 🟠 | `Impacto en puntos` H2 | Same | OK. |
| PED.9 | 🟠 | `Ventas generadas (N)` H2 | Same | OK. |
| PED.10 | 🟠 | `Entrega` H2 | Same | OK. |
| PED.11 | 🟠 | `Ítems` H2 | Same | OK. |
| PED.12 | 🟠 | `Link para el cliente` H2 | Same | OK. |
| PED.13 | 🟠 | `Historial` H2 | Same | OK. |
| PED.14 | 🟠 | `Otros pedidos de este cliente` H2 | Same | OK. |
| PED.15 | 🟠 | `Acciones` H2 | Same | OK. |
| PED.16 | 🟠 | `Cancelar pedido` H2 | Same | OK. |
| PED.17 | 🟠 | `Cliente` H2 | Same | OK. |
| PED.18 | 🟠 | `Compras últimos 30 días` tooltip | `pedido_detalle.html`, `pedidos.html` | OK. |
| PED.19 | 🟠 | `Ver ficha del cliente` tooltip | Same | OK. |
| PED.20 | 🟠 | `Re-petir este pedido` tooltip | `cliente_detalle.html` | "Re-petir" hyphen is unusual. Try `Repetir este pedido`. |
| PED.21 | 🟠 | `Forma de pago esperada` label | `pedidos_nuevo.html` | OK. |
| PED.22 | 🟠 | `Zona de delivery` | Same | OK. |
| PED.23 | 🟠 | `Dirección de envío (si es delivery)` | Same | OK. |
| PED.24 | 🟠 | `Entregar a` | Same | OK. |
| PED.25 | 🟠 | `Tipo de dirección` | Same | OK. |
| PED.26 | 🟠 | `Instrucciones para el cadete` | Same | OK. |
| PED.27 | 🟠 | `Lo antes posible` | Same | OK. |
| PED.28 | 🟠 | `En una franja horaria (preferida, no es garantía)` | Same | "no es garantía" is parenthetical. Try `Franja horaria preferida (no es garantía)`. |
| PED.29 | 🟠 | `Programar para otro día` | Same | OK. |
| PED.30 | 🟠 | `Fecha programada` | Same | OK. |
| PED.31 | 🟠 | `Perfil de facturación` | Same | OK. |
| PED.32 | 🟠 | `Guardar dirección en la ficha del cliente` | Same | OK. |
| PED.33 | 🟠 | `Notas internas (alergias, preferencias...)` | Same | OK. |
| PED.34 | 🟠 | `Ventana de entrega` legend | Same | OK. |
| PED.35 | 🟠 | `Ítems del pedido` H2 | Same | OK. |
| PED.36 | 🟠 | `Cliente seleccionado` label | Same | Awkward. Try `Cliente` with sub: `Click para cambiar`. |
| PED.37 | 🟠 | `Buscar por nombre o teléfono` placeholder | `pedidos.html` | OK. |
| PED.38 | 🟠 | `Limpiar búsqueda` aria | Same | OK. |
| PED.39 | 🟠 | `Filtrar por estado` aria | Same | OK. |
| PED.40 | 🟠 | `Filtrar por período` aria | Same | OK. |
| PED.41 | 🟠 | `Exportar pedidos a CSV` aria | Same | OK. |
| PED.42 | 🟠 | `¿Cancelar pedidos?` tooltip | Same | OK. |
| PED.43 | 🟠 | `atrasado` tooltip | Same | OK. |
| PED.44 | 🟠 | `Ventana preferida` tooltip | Same | OK. |
| PED.45 | 🟠 | `¿Cumplir pedido?` tooltip | Same | OK. |
| PED.46 | 🟠 | `¿Cancelar pedido?` tooltip | Same | OK. |
| PED.47 | 🟠 | `Compartir enlace público` tooltip | Same | OK. |
| PED.48 | 🟠 | `No hay pedidos pendientes` tooltip | Same | OK. |
| PED.49 | 🟠 | `Todos los pedidos` H2 | `pedidos.html` | OK. |
| PED.50 | 🟠 | `Preview de stock — Pedido #N` H2 | `pedido_stock_preview.html` | OK. |
| PED.51 | 🟠 | `Ingredientes a consumir` H2 | Same | OK. |
| PED.52 | 🟠 | `Forzar cumplimiento a pesar del faltante` label | Same | Long label. Try `Forzar cumplimiento aunque falte stock`. |
| PED.53 | 🟠 | `Sin productos con receta` tooltip | Same | OK. |
| PED.54 | 🟠 | `Cumplido` column | `pedido_detalle.html` | OK. |
| PED.55 | 🟠 | `Cumplido`, `Prometido`, `Estado`, `Ítems`, `Total` columns | Same | OK. |
| PED.56 | 🟢 | `Ventas generadas` H2 | Same | OK. |

**To add:**
- A "Bulk fulfill" button for kitchen
- A "Print picking list" button
- A "Order ready" notification (push to customer's WhatsApp)

---

### REPORTES (BI section) — `reportes*.html`, `insight_*.html`, `analisis.html`, `dashboard.html`, `evidencia_mercado.html`, `benchmarks.html`, `benchmark_edit.html`, `cotizador.html`, `food-cost-variance.html`, `fiscal.html`, `board.html`

Already covered in section D of the audit. Top issues:

| # | Pri | Issue | Where | Fix |
|---|---|---|---|---|
| REP.1 | 🟠 | `KPI` loan word | `inicio.html`, `dashboard.html` | Replace with `Indicadores`. |
| REP.2 | 🟠 | `Revenue` loan word | `reportes_top_productos.html` | Replace with `Ingresos`. |
| REP.3 | 🟠 | `COGS` loan word | `reportes_diario.html` | Replace with `Costo de Mercadería Vendida`. |
| REP.4 | 🟠 | `Batches` loan word | `insight_demand.html` | Replace with `Tandas`. |
| REP.5 | 🟠 | `Lotes` loan word | `cotizador.html` | Replace with `Tandas`. |
| REP.6 | 🟠 | `Override` loan word | `produccion_manana.html` | Replace with `Ajuste manual`. |
| REP.7 | 🟠 | `Accuracy` loan word | `produccion_accuracy.html` | Keep, but add tooltip explaining. |
| REP.8 | 🟠 | `Δ` symbol in column headers | `analisis.html`, `insight_margenes.html` | Add tooltip: `Cambio`. |
| REP.9 | 🟠 | `Δ Margen Gs.` | `insight_margenes.html` | OK if Δ is understood. Otherwise `Cambio (Gs.)`. |
| REP.10 | 🟠 | `Prom/día` | `insight_demand.html` | OK but explain. Try `Promedio diario`. |
| REP.11 | 🟠 | `Prime Cost` (column) | `reportes_cierre_mensual.html`, `productos.html` | Industry standard, OK with tooltip. |
| REP.12 | 🟠 | `AOV` (in title only) | `reportes_valor_pedido.html` | Explained inline. OK. |
| REP.13 | 🟠 | `Forecast` (column) | `insight_demand.html`, `produccion_manana.html` | Replace with `Pronóstico`. |
| REP.14 | 🟠 | `Previsto` (column) | `insight_demand.html` | OK. |
| REP.15 | 🟠 | `🔥 Cociná HOY para rescatar` | `insight_freshness.html` | Emoji + voseo. Good. |
| REP.16 | 🟠 | `💀 Stock muerto` | `insight_stock.html` | Emoji. Acceptable but corporate clients may want it removed. |
| REP.17 | 🟠 | `🔄 Rotación (más lento primero)` | Same | OK. |
| REP.18 | 🟠 | `Food cost %` column | `insight_price_impact.html` | English. Try `Costo de alimento %` or `Costo / venta %`. |
| REP.19 | 🟠 | `Productos bajo objetivo (33%)` | Same | Hard-coded threshold. Allow per-product override. |
| REP.20 | 🟠 | `Stock cubre la producción prevista. 🎉` | `insight_demand.html` | OK. |
| REP.21 | 🟠 | `Ningún producto cruza el objetivo. ✅` | `insight_price_impact.html` | OK. |
| REP.22 | 🟠 | `Mercado avg Gs.` | `benchmarks.html` | Mixed English/Spanish. Try `Mercado promedio (Gs.)`. |
| REP.23 | 🟠 | `Mercado real (evidencia)` | Same | OK. |
| REP.24 | 🟠 | `Posición` column | Same | OK. |
| REP.25 | 🟠 | `Δ Gs.` column | Same | Per REP.8. |
| REP.26 | 🟠 | `Sin datos de mercado cargados` tooltip | Same | OK. |
| REP.27 | 🟠 | `📥 CSV` button | `evidencia_mercado.html` | OK. |
| REP.28 | 🟠 | `🔍 Evidencia de mercado` link | `benchmarks.html` | OK. |
| REP.29 | 🟠 | `💰 Nuestro precio` H3 | `benchmark_edit.html` | OK. |
| REP.30 | 🟠 | `🏪 Mercado` H3 | Same | OK. |
| REP.31 | 🟠 | `📦 Receta vinculada: {{name}}` H2 | Same | OK. |
| REP.32 | 🟠 | `Cotizador de pedidos grandes` H1 | `cotizador.html` | OK. |
| REP.33 | 🟠 | `Cotización` H2 | Same | OK. |
| REP.34 | 🟠 | `Lotes` column | Same | Per VENTAS.3 — change to `Tandas`. |
| REP.35 | 🟠 | `Carta` column | Same | "Carta" = menu price. OK in context. |
| REP.36 | 🟠 | `Margen` column | Same | OK. |
| REP.37 | 🟠 | `TOTAL carta` | Same | OK. |
| REP.38 | 🟠 | `Costo total` | Same | OK. |
| REP.39 | 🟠 | `Cotización preliminar — precios de carta sin IVA discriminado.` | Same | OK. |
| REP.40 | 🟠 | `No cargaste ningún producto.` | Same | Direct. Good. |
| REP.41 | 🟠 | `Comparación de períodos` H1 | `reportes_comparacion.html` | OK. |
| REP.42 | 🟠 | `Período 1 (más reciente)` legend | Same | OK. |
| REP.43 | 🟠 | `Período 2 (anterior)` legend | Same | OK. |
| REP.44 | 🟠 | `Métrica` column | Same | OK. |
| REP.45 | 🟠 | `Cambio %` column | Same | OK. |
| REP.46 | 🟠 | `Comparación de precios` H1 | `supplier_precios.html` | OK. |
| REP.47 | 🟠 | `Precios por ingrediente` H2 | Same | OK. |
| REP.48 | 🟠 | `¿Cómo está posicionado {{supplier}}?` H2 | Same | OK. |
| REP.49 | 🟠 | `Ahorro potencial si comprás al más barato` column | Same | Voseo. OK. |
| REP.50 | 🟠 | `Sin datos de comparación todavía` tooltip | Same | OK. |
| REP.51 | 🟠 | `Volatilidad de precios por proveedor` H1 | `suppliers_volatility.html` | OK. |
| REP.52 | 🟠 | `Proveedor` column | Same | OK. |
| REP.53 | 🟠 | `Mín ₲` / `Máx ₲` / `Promedio ₲` | Same | Per G.1, change to `Mín (Gs.)` / `Máx (Gs.)` / `Promedio (Gs.)`. |
| REP.54 | 🟠 | `Volatilidad` column | Same | OK (industry term). |
| REP.55 | 🟠 | `Tendencia` column | Same | OK. |
| REP.56 | 🟠 | `Último hace` column | Same | Awkward. Try `Último cambio` or `Hace cuánto`. |
| REP.57 | 🟠 | `Acción` column | Same | OK. |
| REP.58 | 🟠 | `Sin datos de precios por proveedor` tooltip | Same | OK. |
| REP.59 | 🟠 | `Sin notificaciones` empty state | `base.html` notif | OK. |
| REP.60 | 🟠 | `Limpiar` button | Same | OK. |

**To add:**
- A "Save view" button (save filter state for later)
- A "Subscribe" button (email me this report weekly)
- A "Compare to last month" inline toggle

---

### MERMA — `merma.html`

| # | Pri | Issue | Current | Fix |
|---|---|---|---|---|
| MER.1 | 🟠 | `Hoy` H2 | `merma.html` line 11 | OK. |
| MER.2 | 🟠 | `Registrar merma de ingrediente` H2 | Same | OK. |
| MER.3 | 🟠 | `Resumen últimos N días` H2 | Same | OK. |
| MER.4 | 🟠 | `Gráfico de merma` H2 | Same | OK. |
| MER.5 | 🟠 | `Por motivo` H2 | Same | OK. |
| MER.6 | 🟠 | `Eventos` H2 | Same | OK. |
| MER.7 | 🟠 | `Motivo:` label | Same | OK. |
| MER.8 | 🟠 | `Cantidad` label | Same | OK. |
| MER.9 | 🟠 | `Motivo` column | Same | OK. |
| MER.10 | 🟠 | `Costo (Gs.)` column | Same | OK. |
| MER.11 | 🟠 | `Origen` column | Same | OK. |
| MER.12 | 🟠 | `Registrado desde /producción` tooltip | Same | OK. |
| MER.13 | 🟠 | `Registrado manualmente desde /merma` tooltip | Same | OK. |
| MER.14 | 🟠 | `🔥 Merma — producto` H2 | `produccion.html` | (See PROD.8) |

**To add:**
- A "Bulk waste" entry mode (for a day of many small waste events)

---

### CAJA — `caja.html`, `caja_z.html`

| # | Pri | Issue | Current | Fix |
|---|---|---|---|---|
| CAJA.1 | 🟠 | `Caja` H1 | `caja.html` | OK. |
| CAJA.2 | 🟠 | `Caja abierta` H2 | Same | OK. |
| CAJA.3 | 🟠 | `Abrir caja` H2 | Same | OK. |
| CAJA.4 | 🟠 | `Sesiones recientes` H2 | Same | OK. |
| CAJA.5 | 🟠 | `Conteo físico al cerrar (Gs.)` label | Same | OK. |
| CAJA.6 | 🟠 | `Monto inicial (Gs.)` label | Same | OK. |
| CAJA.7 | 🟠 | `Canal (opcional)` label | Same | OK. |
| CAJA.8 | 🟠 | `salón / delivery` placeholder | Same | "salón" — verify with Saskia. May be "mostrador" instead. |
| CAJA.9 | 🟠 | `¿Cerrar caja?` tooltip | Same | OK. |
| CAJA.10 | 🟠 | `Apertura` / `Cierre` / `Esperado` / `Contado` / `Diff` columns | Same | "Diff" English. Try `Diferencia`. |
| CAJA.11 | 🟠 | `Caja {% if open_sess %}...{% endif %}` H1 | `caja_z.html` | Dynamic. OK. |
| CAJA.12 | 🟠 | `Caja abierta` H2 (in z report) | Same | OK. |
| CAJA.13 | 🟠 | `Abrir caja` H2 | Same | OK. |

**To add:**
- A "Cash variance reason" field when closing (why is the count off?)
- A "Print Z report" button

---

### SUSCRIPCIONES — `suscripciones.html`, `suscripcion_form.html`

| # | Pri | Issue | Current | Fix |
|---|---|---|---|---|
| SUSC.1 | 🟠 | `Suscripciones` H1 | `suscripciones.html` | OK. |
| SUSC.2 | 🟠 | `Cliente *` label | `suscripcion_form.html` | OK. |
| SUSC.3 | 🟠 | `Descripción del pedido *` | Same | OK. |
| SUSC.4 | 🟠 | `Cadencia *` | Same | OK. |
| SUSC.5 | 🟠 | `Día preferido` | Same | OK. |
| SUSC.6 | 🟠 | `Hora preferida` | Same | OK. |
| SUSC.7 | 🟠 | `Fecha de inicio *` | Same | OK. |
| SUSC.8 | 🟠 | `Fecha de fin (opcional)` | Same | OK. |
| SUSC.9 | 🟠 | `Precio estimado (Gs.)` | Same | OK. |
| SUSC.10 | 🟠 | `Notas` | Same | OK. |
| SUSC.11 | 🟠 | `Ej: 1 kg de chipa + 2 facturas` placeholder | Same | Excellent. |
| SUSC.12 | 🟠 | `Ej: 09:00` placeholder | Same | OK. |
| SUSC.13 | 🟠 | `Ej: pasa los sábados a retirar antes del cierre` placeholder | Same | OK. |
| SUSC.14 | 🟠 | `¿Cancelar suscripción?` tooltip | `suscripciones.html` | OK. |
| SUSC.15 | 🟠 | `¿Eliminar suscripción?` tooltip | Same | OK. |
| SUSC.16 | 🟠 | `Sin suscripciones todavía` tooltip | Same | OK. |
| SUSC.17 | 🟠 | `Día / hora` column | Same | OK. |
| SUSC.18 | 🟠 | `Precio Gs.` column | Same | OK. |
| SUSC.19 | 🟠 | `Vigencia` column | Same | OK. |

---

### FIADO — `fiado.html`, `fiado_cliente.html`

| # | Pri | Issue | Current | Fix |
|---|---|---|---|---|
| FIADO.1 | 🟠 | `Fiado · Cuentas por cobrar` H1 | `fiado.html` | Excellent. |
| FIADO.2 | 🟠 | `Cliente`, `Saldo`, `Límite`, `Estado` columns | Same | OK. |
| FIADO.3 | 🟠 | `Historial` H2 | `fiado_cliente.html` | OK. |
| FIADO.4 | 🟠 | `Monto Gs.` placeholder | Same | OK. |
| FIADO.5 | 🟠 | `Nota (opcional)` placeholder | Same | OK. |
| FIADO.6 | 🟠 | `Fecha`, `Tipo`, `Monto`, `Nota` columns | Same | OK. |

**To add:**
- A "Send reminder" button (WhatsApp)

---

### PROVEEDORES / SHOPPING — `suppliers.html`, `supplier_form.html`, `supplier_orders.html`, `supplier_precios.html`, `suppliers_volatility.html`, `shopping_list.html`, `reorder.html`, `wishlist.html`

| # | Pri | Issue | Current | Fix |
|---|---|---|---|---|
| PROV.1 | 🟠 | `Proveedores` H1 | `suppliers.html` | OK. |
| PROV.2 | 🟠 | `¿Desactivar proveedor?` tooltip | Same | OK. |
| PROV.3 | 🟠 | `No hay proveedores todavía` tooltip | Same | OK. |
| PROV.4 | 🟠 | `Nombre del proveedor *` label | `supplier_form.html` | OK. |
| PROV.5 | 🟠 | `Persona de contacto` | Same | OK. |
| PROV.6 | 🟠 | `RUC / Cédula` | Same | OK. |
| PROV.7 | 🟠 | `Pedido a {{supplier}}` H1 | `supplier_orders.html` | OK. |
| PROV.8 | 🟠 | `Datos de contacto` H2 | Same | OK. |
| PROV.9 | 🟠 | `Enviar pedido por WhatsApp` H2 | Same | Excellent. |
| PROV.10 | 🟠 | `Ingredientes bajo mínimo` H2 | Same | OK. |
| PROV.11 | 🟠 | `Ingredientes para reponer` H2 | Same | OK. |
| PROV.12 | 🟠 | `Marcar comprado rapido` aria | `reorder.html` | Typo: `rapido` → `rápido`. |
| PROV.13 | 🟠 | `Marcá ingredientes arriba para generar el pedido` tooltip | Same | Voseo. OK. |
| PROV.14 | 🟠 | `Marca ingredientes arriba para marcarlos como comprados en 1 click` | Same | Long. Split into tooltip + visible hint. |
| PROV.15 | 🟠 | `Proveedor fijo (manual). Hacé click en 🔓 para liberar.` | Same | OK. |
| PROV.16 | 🟠 | `Desbloquear — liberar el dropdown` | Same | OK. |
| PROV.17 | 🟠 | `Necesita un proveedor seleccionado antes de fijar` | Same | OK. |
| PROV.18 | 🟠 | `Fijar este proveedor — el dropdown siempre elegirá este` | Same | OK. |
| PROV.19 | 🟠 | `Basado en N compra(s) en los últimos 90 días` | Same | OK. |
| PROV.20 | 🟠 | `Asigná un proveedor antes de reponer` | Same | OK. |
| PROV.21 | 🟠 | `Llena a 2x min con un click (usa el proveedor fijado y el ultimo precio)` | Same | Informal. Try `Llená al doble del mínimo con 1 click (usa el proveedor fijado y el último precio)`. |
| PROV.22 | 🟠 | `Actual` column | `reorder.html` | OK. |
| PROV.23 | 🟠 | `Urgencia` column | Same | OK. |
| PROV.24 | 🟠 | `Costo est.` column | Same | OK. |
| PROV.25 | 🟠 | `Cant a comprar` column | `shopping_list.html` | "Cant" abbreviation. Try `Cantidad`. |
| PROV.26 | 🟠 | `Para qué` column | Same | OK. |
| PROV.27 | 🟠 | `Subtotal Gs.` column | Same | OK. |
| PROV.28 | 🟠 | `🏪 {{supplier}} N pendientes` H2 | Same | Emoji H2. Acceptable. |
| PROV.29 | 🟠 | `Sin proveedor asignado` | Same | OK. |
| PROV.30 | 🟠 | `¿Sincronizar faltantes?` tooltip | Same | OK. |
| PROV.31 | 🟠 | `Importar todos los ingredientes con stock < mínimo` | Same | OK. |
| PROV.32 | 🟠 | `Marcar como comprado` | Same | OK. |
| PROV.33 | 🟠 | `¿Eliminar ítem?` | Same | OK. |
| PROV.34 | 🟠 | `Enviar a la lista de compras` tooltip | `wishlist.html` | OK. |
| PROV.35 | 🟠 | `Item`, `Qty`, `Unit Gs.`, `Total Gs.`, `Categoría`, `Dónde comprar`, `Status` columns | Same | `Qty` English → `Cant.`. `Unit Gs.` English → `Unitario (Gs.)`. `Status` → `Estado`. |

**To add:**
- A "Best price" indicator on each ingredient
- A "Last purchase date" column

---

### DELIVERY — `delivery_zones.html`

| # | Pri | Issue | Current | Fix |
|---|---|---|---|---|
| DEL.1 | 🟠 | `Zona` column | `delivery_zones.html` | OK. |
| DEL.2 | 🟠 | `Cobertura` column | Same | OK. |
| DEL.3 | 🟠 | `Radio` column | Same | OK. |
| DEL.4 | 🟠 | `Costo Gs.` column | Same | OK. |
| DEL.5 | 🟠 | `Pedido mín Gs.` column | Same | OK. |
| DEL.6 | 🟠 | `Tiempo` column | Same | OK. |
| DEL.7 | 🟠 | `Notas` column | Same | OK. |

---

### MENUS — `menus.html`, `menu_import_ocr.html`, `menu_publico.html`, `menu_tablet.html`

| # | Pri | Issue | Current | Fix |
|---|---|---|---|---|
| MENU.1 | 🟠 | `Menús ejecutivos` H1 | `menus.html` | OK. |
| MENU.2 | 🟠 | `Nuevo menú` H2 | Same | OK. |
| MENU.3 | 🟠 | `Activos (N)` H2 | Same | OK. |
| MENU.4 | 🟠 | `Nombre` label | Same | OK. |
| MENU.5 | 🟠 | `Precio (Gs.)` label | Same | OK. |
| MENU.6 | 🟠 | `Menú ejecutivo lunes` placeholder | Same | OK. |
| MENU.7 | 🟠 | `25000` placeholder | Same | Should be `25.000` per `copy-vos.md` (period thousands). |
| MENU.8 | 🟠 | `Cantidad de {{name}}` aria | Same | OK. |
| MENU.9 | 🟠 | `¿Desactivar menú?` tooltip | Same | OK. |
| MENU.10 | 🟠 | `Productos incluidos` legend | Same | OK. |
| MENU.11 | 🟠 | `Menú`, `Precio`, `Incluye` columns | Same | OK. |
| MENU.12 | 🟠 | `Importar carta por foto` H1 | `menu_import_ocr.html` | OK. |
| MENU.13 | 🟠 | `Revisá antes de confirmar` H2 | Same | OK. |
| MENU.14 | 🟠 | `Foto de la carta (JPG/PNG/WebP, máx 8MB)` label | Same | OK. |
| MENU.15 | 🟠 | `Nombre`, `Precio (Gs)`, `Categoría`, `Estado` columns | Same | `Precio (Gs)` should be `Precio (Gs.)` (with period). |
| MENU.16 | 🟠 | `Categorías` aria | `menu_publico.html` | OK. |
| MENU.17 | 🟠 | `Sin foto` aria | `menu_tablet.html` | OK. |
| MENU.18 | 🟠 | `Precio` aria | Same | OK. |
| MENU.19 | 🟠 | `Etiquetas` aria | Same | OK. |

**To add:**
- A "Featured" badge for menu items
- A "Sold out" indicator

---

### SETTINGS / USERS — `settings.html`, `settings_catalog.html`, `users.html`, `branding.html`

| # | Pri | Issue | Current | Fix |
|---|---|---|---|---|
| SET.1 | 🟠 | `Configuración` H1 | `settings.html` | OK. |
| SET.2 | 🟠 | `Información de Negocio` H2 | Same | OK. |
| SET.3 | 🟠 | `Régimen tributario (DNIT / SET)` H2 | Same | OK. |
| SET.4 | 🟠 | `Timbrado (RESIMPLE)` H2 | Same | OK. |
| SET.5 | 🟠 | `INAN — Registro de Establecimiento (R.E.)` H2 | Same | OK. |
| SET.6 | 🟠 | `Habilitación Municipal` H2 | Same | OK. |
| SET.7 | 🟠 | `Costeo (Fase 1.D)` H2 | Same | "Fase 1.D" is internal dev phase — should not be visible to operator. |
| SET.8 | 🟠 | `Pagos y Delivery` H2 | Same | OK. |
| SET.9 | 🟠 | `Formas de pago` H2 | Same | OK. |
| SET.10 | 🟠 | `Zonas de delivery` H2 | Same | OK. |
| SET.11 | 🟠 | `Notificaciones` H2 | Same | OK. |
| SET.12 | 🟠 | `Configuración Fiscal` H2 | Same | OK. |
| SET.13 | 🟠 | `Tema y apariencia` H2 | Same | OK. |
| SET.14 | 🟠 | `Vista previa` H2 | Same | OK. |
| SET.15 | 🟠 | `Vista clara` / `Vista oscura` H2 | Same | OK. |
| SET.16 | 🟠 | `Información del sistema` H2 | Same | OK. |
| SET.17 | 🟠 | `Datos de ejemplo` H2 | Same | OK. |
| SET.18 | 🟠 | `Nombre legal del negocio` label | Same | OK. |
| SET.19 | 🟠 | `RUC` label | Same | OK. |
| SET.20 | 🟠 | `Razón social` label | Same | OK. |
| SET.21 | 🟠 | `Nombre de fantasía` label | Same | OK. |
| SET.22 | 🟠 | `Régimen` label | Same | OK. |
| SET.23 | 🟠 | `IVA por defecto para productos nuevos` label | Same | OK. |
| SET.24 | 🟠 | `Número de timbrado` label | Same | OK. |
| SET.25 | 🟠 | `Vencimiento del timbrado` label | Same | OK. |
| SET.26 | 🟠 | `R.E. N°` label | Same | OK. |
| SET.27 | 🟠 | `Vencimiento R.E.` label | Same | OK. |
| SET.28 | 🟠 | `Director Técnico (Regente)` label | Same | OK. |
| SET.29 | 🟠 | `Registro del Director Técnico` label | Same | OK. |
| SET.30 | 🟠 | `N° habilitación comercial` label | Same | OK. |
| SET.31 | 🟠 | `Vencimiento habilitación` label | Same | OK. |
| SET.32 | 🟠 | `Costo mano de obra (Gs./hora)` label | Same | OK. |
| SET.33 | 🟠 | `Overhead (% sobre materiales)` label | Same | OK. |
| SET.34 | 🟠 | `Punto de expedición` label | Same | OK. |
| SET.35 | 🟠 | `Secuencia de facturas` label | Same | OK. |
| SET.36 | 🟠 | `Tema preferido` label | Same | OK. |
| SET.37 | 🟠 | `Claro` / `Oscuro` / `Del sistema` labels | Same | OK. |
| SET.38 | 🟠 | `Usa la configuración de su sistema operativo` (hint) | Same | "su" should be "tu". |
| SET.39 | 🟠 | `¿Cargar datos de ejemplo?` tooltip | Same | OK. |
| SET.40 | 🟠 | `⚠️ ATENCIÓN — Resetear y recargar` | Same | OK. |
| SET.41 | 🟠 | `Nueva categoría de producto` H2 | `settings_catalog.html` | OK. |
| SET.42 | 🟠 | `Nueva familia de receta` H2 | Same | OK. |
| SET.43 | 🟠 | `Nuevo canal de venta` H2 | Same | OK. |
| SET.44 | 🟠 | `Nueva forma de pago` H2 | Same | OK. |
| SET.45 | 🟠 | `Nuevo código de almacenamiento HACCP` H2 | Same | OK. |
| SET.46 | 🟠 | `Nuevo período de fecha` H2 | Same | OK. |
| SET.47 | 🟠 | `Configuración de impuestos (IVA, régimen)` H2 | Same | OK. |
| SET.48 | 🟠 | `Branding` H2 | Same | OK. |
| SET.49 | 🟠 | `Proveedores` H2 | Same | OK. |
| SET.50 | 🟠 | `Predeterminado` column | Same | OK. |
| SET.51 | 🟠 | `Nombre del negocio` label | Same | OK. |
| SET.52 | 🟠 | `Lema` label | Same | OK. |
| SET.53 | 🟠 | `Pie de página` label | Same | OK. |
| SET.54 | 🟠 | `Color de acento (hex)` label | Same | OK. |
| SET.55 | 🟠 | `Ruta del logo (opcional)` label | Same | OK. |
| SET.56 | 🟠 | `Gestión de Usuarios` H1 | `users.html` | OK. |
| SET.57 | 🟠 | `Nuevo Usuario` H2 | Same | OK. |
| SET.58 | 🟠 | `Editar Usuario` H2 | Same | OK. |
| SET.59 | 🟠 | `¿Eliminar usuario?` H2 | Same | OK. |
| SET.60 | 🟠 | `Nombre de usuario` label | Same | OK. |
| SET.61 | 🟠 | `Contraseña` label | Same | OK. |
| SET.62 | 🟠 | `Rol` label | Same | OK. |
| SET.63 | 🟠 | `Nueva contraseña` label | Same | OK. |
| SET.64 | 🟠 | `Usuario activo` label | Same | OK. |
| SET.65 | 🟠 | `Mínimo 6 caracteres` placeholder | Same | OK. |
| SET.66 | 🟠 | `Dejar en blanco para no cambiar` placeholder | Same | OK. |
| SET.67 | 🟠 | `No hay usuarios creados` tooltip | Same | OK. |
| SET.68 | 🟠 | `Último acceso` column | Same | OK. |
| SET.69 | 🟠 | `Creado` column | Same | OK. |
| SET.70 | 🟠 | `Acciones` column | Same | OK. |

**To add:**
- A "Test email/SMS" button
- A "Backup now" button
- A "Restore from backup" button

---

### EOD / AUDITORIA / OPS — `eod.html`, `eod_anomalies.html`, `eod_print.html`, `auditoria.html`, `auditoria_analytics.html`, `ops_status.html`, `riesgos.html`, `bank.html`, `healthz_summary.html`

| # | Pri | Issue | Current | Fix |
|---|---|---|---|---|
| EOD.1 | 🟠 | `Resumen del rango` H2 | `eod.html` | OK. |
| EOD.2 | 🟠 | `Progreso del cierre` H2 | Same | OK. |
| EOD.3 | 🟠 | `Reposición` H2 | Same | OK. |
| EOD.4 | 🟠 | `Producción del día` H2 | Same | OK. |
| EOD.5 | 🟠 | `Notas para el turno siguiente` label | Same | OK. |
| EOD.6 | 🟠 | `Ej: mañana llega pedido de harina; cliente X retira a las 10` placeholder | Same | Excellent. |
| EOD.7 | 🟠 | `Hecho: {{product}}` aria | Same | OK. |
| EOD.8 | 🟠 | `Guardar {{product}}` aria | Same | OK. |
| EOD.9 | 🟠 | `Imprimí el resumen de hoy en 1 página para archivar en la carpeta` tooltip | Same | Excellent. |
| EOD.10 | 🟠 | `Día`, `Plan (filas)`, `Completado` columns | Same | OK. |
| EOD.11 | 🟠 | `Item`, `Ingrediente`, `Sugerido`, `Costo est.`, `Total estimado` columns | Same | OK. |
| EOD.12 | 🟠 | `Producto`, `Plan`, `Hecho` columns | Same | OK. |
| EOD.13 | 🟠 | `Anomalías del cierre` H1 | `eod_anomalies.html` | OK. |
| EOD.14 | 🟠 | `Severidad`, `ID`, `Título`, `Detalle` columns | Same | OK. |
| EOD.15 | 🟠 | `Cierre del día — {{today.strftime("%A %d de %B de %Y")}}` H1 | `eod_print.html` | OK. |
| EOD.16 | 🟠 | `1. Checklist de cierre` H2 | Same | OK. |
| EOD.17 | 🟠 | `2. Plan de producción del día` H2 | Same | OK. |
| EOD.18 | 🟠 | `3. Reposición necesaria` H2 | Same | OK. |
| EOD.19 | 🟠 | `Progreso del checklist` aria | Same | OK. |
| EOD.20 | 🟠 | `Auditoría` H1 | `auditoria.html` | OK. |
| EOD.21 | 🟠 | `Filtros` H2 | Same | OK. |
| EOD.22 | 🟠 | `Retención de datos` H2 | Same | OK. |
| EOD.23 | 🟠 | `Acción` label | Same | OK. |
| EOD.24 | 🟠 | `Origen (merma)` label | Same | OK. |
| EOD.25 | 🟠 | `Tipo de registro` label | Same | OK. |
| EOD.26 | 🟠 | `ID del registro` label | Same | OK. |
| EOD.27 | 🟠 | `login.success, sale.create, ...` placeholder | Same | OK. |
| EOD.28 | 🟠 | `192.168.1.1` placeholder | Same | OK. |
| EOD.29 | 🟠 | `Ver analítica agregada del audit log` tooltip | Same | OK. |
| EOD.30 | 🟠 | `Origen del registro` tooltip | Same | OK. |
| EOD.31 | 🟠 | `No hay entradas de auditoría` tooltip | Same | OK. |
| EOD.32 | 🟠 | `Fecha`, `Usuario`, `Acción`, `Target`, `IP`, `User Agent`, `Detalle` columns | Same | OK. |
| EOD.33 | 🟠 | `Analítica de auditoría` H1 | `auditoria_analytics.html` | OK. |
| EOD.34 | 🟠 | `Top IPs` H2 | Same | "IPs" English. Try `Direcciones IP`. |
| EOD.35 | 🟠 | `Acciones más frecuentes` H2 | Same | OK. |
| EOD.36 | 🟠 | `Actividad por operador` H2 | Same | OK. |
| EOD.37 | 🟠 | `Login OK` / `Login FAIL` columns | Same | English. Try `Login exitoso` / `Login fallido`. |
| EOD.38 | 🟠 | `Acciones distintas` column | Same | OK. |
| EOD.39 | 🟠 | `Última actividad` column | Same | OK. |
| EOD.40 | 🟠 | `Estado operativo` H1 | `ops_status.html` | OK. |
| EOD.41 | 🟠 | `Operaciones comunes` H2 | Same | OK. |
| EOD.42 | 🟠 | `Reorder rate (últimos 90 días)` H2 | Same | "Reorder rate" English. Try `Tasa de reposición (últimos 90 días)`. |
| EOD.43 | 🟠 | `Endpoint`, `Propósito`, `Acción` columns | Same | "Endpoint" English. Try `Ruta`. |
| EOD.44 | 🟠 | `Cliente`, `Pedidos`, `Total ₲` columns | Same | `Total ₲` per G.1 → `Total (Gs.)`. |
| EOD.45 | 🟠 | `⚠️ Registro de riesgos` H1 | `riesgos.html` | OK. |
| EOD.46 | 🟠 | `Descripción` label | Same | OK. |
| EOD.47 | 🟠 | `Categoría` label | Same | OK. |
| EOD.48 | 🟠 | `Probabilidad (1-5)` label | Same | OK. |
| EOD.49 | 🟠 | `Impacto Gs.` label | Same | Should be `Impacto (Gs.)`. |
| EOD.50 | 🟠 | `Mitigación propuesta` label | Same | OK. |
| EOD.51 | 🟠 | `Responsable` label | Same | OK. |
| EOD.52 | 🟠 | `Notas` label | Same | OK. |
| EOD.53 | 🟠 | `Ej: Corte de luz durante turno mañana` placeholder | Same | OK. |
| EOD.54 | 🟠 | `Sin riesgos registrados` tooltip | Same | OK. |
| EOD.55 | 🟠 | `ID`, `Riesgo`, `Prob.`, `Impact Gs.`, `Sev Gs.`, `Mitigación`, `Status`, `Owner` columns | Same | `Prob.` abbreviation. Try `Probabilidad`. `Impact Gs.` per EOD.49. `Sev Gs.` per G.1. `Status` English → `Estado`. `Owner` English → `Responsable`. |
| EOD.56 | 🟠 | `Base de datos` H2 | `healthz_summary.html` | OK. |
| EOD.57 | 🟠 | `Errores 500` H2 | Same | OK. |
| EOD.58 | 🟠 | `Backup` H2 | Same | OK. |
| EOD.59 | 🟠 | `Dependencias externas` H2 | Same | OK. |
| EOD.60 | 🟠 | `Disco` H2 | Same | OK. |
| EOD.61 | 🟠 | `Atajos del operador` H2 | Same | OK. |
| EOD.62 | 🟠 | `Currency` label | `bank.html` | English. Try `Moneda`. |
| EOD.63 | 🟠 | `Importe (+/-)` label | Same | OK. |
| EOD.64 | 🟠 | `Counterparty` label | Same | English. Try `Contraparte` or `Beneficiario`. |
| EOD.65 | 🟠 | `Categoría` label | Same | OK. |
| EOD.66 | 🟠 | `Descripción` label | Same | OK. |
| EOD.67 | 🟠 | `Conciliado con {{type}} #{{id}}` tooltip | Same | OK. |
| EOD.68 | 🟠 | `¿Descuadrar transacción?` tooltip | Same | OK. |
| EOD.69 | 🟠 | `Desconciliar` tooltip | Same | OK. |
| EOD.70 | 🟠 | `Sin movimientos bancarios cargados` tooltip | Same | OK. |
| EOD.71 | 🟠 | `Fecha`, `Cuenta`, `Importe`, `Categoría`, `Counterparty`, `Descripción`, `Conciliación` columns | Same | `Counterparty` English per EOD.64. |

---

### AUTH / ERRORS / HELP — `login.html` (covered), `errors/404.html`, `errors/4xx.html`, `errors/500.html`, `guia.html`, `dev_combo_smoke.html`, `copiloto.html`

| # | Pri | Issue | Current | Fix |
|---|---|---|---|---|
| HELP.1 | 🟠 | `Copiloto IA` H1 | `copiloto.html` | OK. |
| HELP.2 | 🟠 | `Preguntale algo al copiloto...` placeholder | Same | Excellent. |
| HELP.3 | 🟠 | `Tabla de contenidos` aria | `guia.html` | OK. |
| HELP.4 | 🟠 | `Sazón UI components smoke test` H1 | `dev_combo_smoke.html` | Internal dev page. Should not be linked from operator UI. |
| HELP.5 | 🟠 | `Form submitted ✓` | Same | OK. |
| HELP.6 | 🟠 | `Cómo se usa mañana` H2 | Same | OK. |
| HELP.7 | 🟠 | (errors/) — to be checked separately | | |
| HELP.8 | 🟠 | `Resumen del rango` already covered in EOD | | |

---

### COVERED ABOVE (also exists in audit)
- `dashboard.html`, `inicio.html`, `analisis.html`, `reportes.html` (index)
- `carga_inicial.html`
- `boards.html`, `pedido_publico.html` (minimal templates)
- `food-cost-variance.html`, `fiscal.html` (minimal)

---

## SUMMARY OF CHANGES BY PRIORITY

| Priority | Count | Examples |
|---|---|---|
| 🔴 P0 | ~10 | Login double-checkbox, INICIO.1, PROD.4 (duplicate H2) |
| 🟠 P1 | ~150 | All English loan words, register drift, currency symbol, $Gs.$ vs $₲$, KPI/Loyalty/Cost/etc. |
| 🟡 P2 | ~100 | Abbreviations, formatting, hints, placeholders |
| 🟢 P3 | ~30 | Polish — emojis, opinionated copy, hierarchy |

## TOP 5 THINGS TO FIX FIRST

1. **G.1** — Replace `₲` and bare `Gs` with `Gs.` everywhere (5 templates)
2. **G.2** — Rename `Loyalty` → `Fidelización` on `inicio.html`
3. **G.3** — Standardize English loan words per the table
4. **G.4** — Replace `Guardá` with `Guardar` in buttons
5. **LOGIN.1** — Remove the duplicate `stay_logged_in` checkbox

## ESTIMATED EFFORT

- **Global fixes (G.1–G.8):** ~4 hours (find/replace + verification)
- **Per-page P0/P1 fixes:** ~2 days of focused editing
- **P2/P3 polish:** ~3 days
- **Total:** ~1 week for the full list

After this pass, run a 1-day re-audit to verify the changes landed correctly.
