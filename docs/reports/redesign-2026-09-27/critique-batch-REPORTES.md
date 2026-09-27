# Saskia RMS — Visual Critique Batch: Reportes

**Auditor:** UX/UI Principal + QA Architect
**Scope:** 8 pages — diario, stock-intel, ventas-hora, precios, price-impact, freshness, demand, metodos-pago
**Method:** 5-hat analysis per page + defect log + wishlist

---

## `/reportes/diario` (reportes-diario.png)

### 5-Hat Analysis

**Counter staff:** Se enfoca en cuántas ventas hubo (`Nº ventas`) y el total de ingresos del día. La métrica de margen bruto les importa solo si necesitan reportar al dueño. No pueden hacer nada con `COGS` o `Gastos` desde el mostrador.

**Owner-finance:** El resumen diario es su pantalla de control financiera por excelencia. Quiere ver ingresos vs yesterday, IVA acumulado, y margen bruto con el delta `%. El campo "Gastos" con valor `expenses_placeholder_gs` es un problema serio — no puede confiar en el margen si los gastos son un placeholder. No tiene cómo comparar este día contra el anterior (sin filtro de rango de fechas).

**Production-baker:** COGS les dice cuánto les costó la producción del día, pero no hay desglose por producto o por receta. No pueden distinguir qué fue lo más caro de producir.

**New user:** La página es clara en su lectura vertical (ingresos → IVA → COGS → Gastos → Ventas → Margen). Pero el color verde en `Margen bruto` cuando es ≥40% no tiene explicación en pantalla — "¿por qué 40%?" no se responde desde la UI.

**Auditor:** Necesita saber qué día específica se está mostrando (título: "Resumen diario — {{ for_date }}"). Pero no hay atribución de fuente de datos ni marca de cuándo se generó el reporte. Si tuviera que presentar esto al contador, no sabe si viene de ventas POS, de ajustes manuales, o de ambos.

### Defects (P0/P1/P2)

- [P0] **"Gastos" es un placeholder en un reporte financiero** — el template pasa `expenses_placeholder_gs` que se renderiza como `Gs. 0`. Owner/auditor no puede confiar en el margen bruto cuando un componente clave es fake data.
- [P1] **Sin filtro de rango de fechas; solo fecha única** — no se puede comparar contra ayer, contra la semana pasada, ni ver un rango.报表 ohne Vergleich ist Blindflug.
- [P1] **El umbral del 40% en `is-up` no tiene explicación** — el usuario ve `56.2% ↑` en verde y no sabe de dónde sale ese threshold ni si es bueno o malo.
- [P1] **`report_source_footer()` falta en esta página** — inconsistente con `precios` y `metodos-pago` que sí lo tienen. Auditoría financiera sin atribución de fuente es incomplete.
- [P2] **Sin KPI delta strip** — todas las otras páginas de reportes carecen de "vs ayer" / "vs semana pasada" en la parte superior. El `metric-delta` solo existe en la tarjeta de Margen bruto.
- [P2] **El botón "Exportar PDF" está al final, antes del form de fecha** — el flujo natural es primero elegir fecha, luego exportar. El botón PDF debería estar junto al form, o al menos después.

### Complete Design Wishlist

1. Reemplazar `expenses_placeholder_gs` con gastos reales del modelo de datos (o mostrar "—" si no hay gastos cargados).
2. Agregar filtro de rango de fechas (Desde / Hasta) con presets: Hoy, Ayer, Esta semana, Mes actual.
3. Agregar KPI delta strip en la parte superior: "Ingresos vs ayer: +Gs. 120.000 ↑, Ventas vs ayer: +3."
4. Tooltip en el `metric-delta` de margen: explicar que `≥40%` es el objetivo y qué factores lo mueven.
5. Agregar `report_source_footer()` con marca de cuándo se generó y de qué tablas источник данных.
6. Agregar breakdown de COGS por producto(receta) debajo del KPI de COGS — un mini-table expandible.
7. El form de fecha debería estar arriba, antes de las métricas, con el botón Exportar PDF al lado del form.
8. Mostrar contexto del día (¿es hoy? ¿es pasado?) con un chip "Hoy" / "Ayer" / "Fecha histórica" junto al título.

---

## `/reportes/stock-intel` (reportes-stock-intel.png)

### 5-Hat Analysis

**Counter staff:** No relevante para el mostrador. Este reporte es de back-office.

**Owner-finance:** Quiere saber cuánto dinero tiene parado en la estantería en forma de insumos sin consumir. **Problema crítico: no se muestra el valor en Guaraníes del stock muerto.** Solo ve días sin consumo y último consumo — sin la plata, no puede priorize.

**Production-baker:** Le dice qué insumos no se están usando (y por lo tanto probablemente están próximos a vencer). Pero la tabla no conecta con el `/reportes/freshness` — el baker tiene que ir a otro reporte para ver si esos insumos muertos están cerca de vencer.

**New user:** "Stock muerto" es un concepto de negocio que necesita explicación. Sin tooltip, un usuario nuevo no sabe si 45 días sin consumo es normal (ej. especias) o un problema.

**Auditor:** Tabla de rotación clara. Pero sin знаения денег en stock muerto, no puede calcular el capital inmovilizado. Y sin filtro de rango de fechas, no puede hacer análisis de tendencia.

### Defects (P0/P1/P2)

- [P0] **Stock muerto sin valor en Gs.** — la columna "Valor en riesgo" existe en `/reportes/freshness` pero NO en stock-intel. El owner no puede saber cuánto capital tiene paralizado sin hacer el cálculo mental.
- [P0] **Variable `days` y `dead_days` usadas en el template pero no pasadas por el router** — el template `insight_stock.html` referencia `{{ days }}` y `{{ dead_days }}` pero el router no define estos valores. En runtime renderiza literalmente `{{ days }}` o queda en blanco.
- [P1] **Sin vínculo a freshness** — un insumo en stock muerto probablemente también está en freshness, pero no hay un link o CTA para "Ver si está por vencer" desde la tabla de stock muerto.
- [P1] **Tabla stock muerto sin columna "Valor (Gs.)"** — la rotación tiene todas las columnas numéricas menos la más importante para la decisión financiera.
- [P2] **Sin filtro de rango de días configurable** — `dead_days = N` está hardcodeado en el backend y no se puede cambiar desde la UI.
- [P2] **Sin fuente de datos ni marca de freshness** — el auditor quiere saber de cuándo es el último consumo registrado.

### Complete Design Wishlist

1. Agregar columna "Valor (Gs.)" a la tabla de stock muerto con `m.gs()` formatting.
2. Corregir el router para pasar `days` y `dead_days` al template; si el default es 30d, mostrarlo explícitamente.
3. Agregar chip "Ver en Frescura →" en cada fila de stock muerto que lleva a `/reportes/freshness?ingredient_id=X`.
4. Hacer configurable el umbral de `dead_days` (30/60/90) con un filtro en la UI.
5. Agregar totales: "Total stock muerto: Gs. X" al final de la tabla.
6. Agregar `report_source_footer()` con fecha del último movimiento de stock registrado.
7. En la sección de Rotación, marcar con color los ingredientes con `días de stock > 30` (sobre-stockado = también es un problema).

---

## `/reportes/ventas-hora` (reportes-ventas-hora.png)

### 5-Hat Analysis

**Counter staff:** Quiere saber a qué hora hay más ventas para planificarse (cuándo ir al baño, cuándo es el tranco). La tabla de 24 filas es legible. La barra visual.inline ayuda a ver el shape del día sin leer números.

**Owner-finance:** Hora pico como número les dice cuándo están los peaks, pero no les dice cuánto facturaron en cada hora (solo cantidad de ventas). No pueden hacer análisis de productividad/hora.

**Production-baker:** La hora pico les dice cuándo empezar a producir más. Pero no ven **qué productos** se venden a cada hora — "a las 9 vendí 12 medialunas" no es útil si no saben que son medialunas.

**New user:** Las barras.inline son una buena pista visual, pero sin explicación de cómo interpretarlas (ancho = proporción del peak). El label "Hora pico: 14:00" en la parte superior es útil pero debería estar **destacado visualmente en la tabla**, no solo como texto arriba.

**Auditor:** No hay filtro de rango de fechas, así que no puede comparar "¿este martes vs el martes pasado?" No puede exportar. Y sin saber qué período se está mostrando, no puede verificar nada.

### Defects (P0/P1/P2)

- [P0] **Sin filtro de rango de fechas en una página de reportes** — el router no pasa `start_date`/`end_date` al template; defaults to all-time. Esto hace el reporte inútil para comparaciones.
- [P0] **`report_source_footer()` no existe en esta página** — el template no llama `ui.report_source_footer()` en el `{% block title %}`. Inconsistente con `precios` y `metodos-pago`.
- [P1] **Hora pico no está resaltada visualmente en la tabla** — el texto "Hora pico: 14:00" arriba se pierde cuando el usuario mira la tabla. La fila correspondiente debería tener un `.is-peak` highlight.
- [P1] **Barras.inline con CSS hardcodeado** (`background:#3b82f6`) — no usa tokens CSS del design system, no es responsive, no tiene hover state.
- [P2] **Sin weekday/day-of-week filter** — un viernes a las 14:00 no es igual a un lunes. No se puede filtrar por día de la semana.
- [P2] **No hay contexto de fecha en el título** — el usuario no sabe si está viendo "todos los días" o "solo esta semana" o "solo septiembre".

### Complete Design Wishlist

1. Agregar filtro de rango de fechas + presets (Hoy, Semana, Mes) como en `metodos-pago`.
2. Agregar filtro day-of-week chips (Lun–Dom) para comparar patrones.
3. Resaltar la fila de hora pico con color de fondo + bold en el label de hora.
4. Reemplazar las barras CSS inline con un componente de barra chart reutilizable que use design tokens.
5. Mostrar hora pico destacada en una KPI card al inicio ("Hora pico: 14:00 — 23 ventas") con el contexto del período filtrado.
6. Agregar `report_source_footer()` al bloque `title` como tienen `metodos-pago` y `precios`.
7. En la KPI card de hora pico, agregar "vs período anterior" delta si se filtra por rango.

---

## `/reportes/precios` (reportes-precios.png)

### 5-Hat Analysis

**Counter staff:** No directamente relevante para el mostrador. Si el precio de la harina sube, el dueño les avisará.

**Owner-finance:** QUIERE esta página. Le permite ver la tendencia de precios de ingredientes para renegociar con proveedores o ajustar precios de venta. La tabla de stats (min/max/avg) es perfecta. La posibilidad de exportar CSV para comparar con facturas es excelente.

**Production-baker:** Le interesa el precio de los insumos que más usa. Pero la página no le dice **qué recetas se ven afectadas** por un aumento de precio. Solo ve el número del insumo.

**New user:** La estructura es clara (tabla → click → detalle con gráfico). El toggle de períodos (7d/30d/90d/365d) es entendible. Pero el empty state podría explicar mejor qué hacer si no hay precios cargados.

**Auditor:** La atribución de fuente está en el footer (`report_source_footer()`) — bien. Pero necesita ver de dónde viene cada precio: ¿del último restock? ¿de edición manual? La columna "Origen" en la tabla de detalle ayuda, pero la lista no tiene origen.

### Defects (P0/P1/P2)

- [P0] **La tabla de lista NO tiene columna "Origen del último precio"** — el detalle sí la tiene ("Reposición", "Manual", "Importación Excel") pero la lista solo tiene "Último cambio" como fecha. Auditor necesita saber si fue cargado a mano o por importación.
- [P1] **Sin breakdown de impacto en recetas** — cuando ves el detalle de un ingrediente cuyo precio subió, la página no te dice "esta alza sube el costo de la medialuna en Gs. 200". Eso está en `price-impact` pero no hay un link desde `precios`.
- [P1] **El gráfico SVG no tiene tooltip on hover** — el `line_chart` de `rms/charts.py` genera SVG estático. No se puede ver el valor exacto de un día sin leer la escala del eje Y.
- [P2] **La tabla de eventos en detalle usa formato de fecha inconsistente** — el template de detalle usa `ev.date.strftime("%d/%m/%Y")` (Paraguay locale) pero la lista usa `strftime("%d/%m/%Y")` — confirmado como correcto. Pero la tabla de la lista usa `dd/mm/YYYY` en el detail view mientras que otros reportes usan `dd-mm-YYYY` en stock-intel. **Formato de fecha inconsistente entre reportes.**
- [P2] **El botón "Exportar CSV" está en la misma línea que los toggles de período** — se mezcla visualmente con los filtros. Debería estar separado, a la derecha.

### Complete Design Wishlist

1. Agregar columna "Origen" a la tabla de lista (igual que en detalle): "Reposición / Manual / Excel".
2. En la fila de ingrediente con precio que cambió significativamente (>15% en 30d), mostrar un chip de alerta visual.
3. Agregar link "Ver impacto en recetas →" en la página de detalle del ingrediente que lleva a `/reportes/price-impact?ingredient_id=X`.
4. Agregar tooltip al SVG chart que muestre el valor exacto al hover (requiere JS interactivo, no solo SVG estático).
5. Mover el botón "Exportar CSV" a la derecha, separado de los toggles de período, con un separador visual.
6. Estandarizar formato de fecha en todos los reportes a `dd/mm/YYYY` (Paraguay standard) — currently inconsistent between pages.
7. En la KPI card "Promedio", agregar el desvío estándar o la tendencia (subiendo ↗ / bajando ↘) para indicar dirección.
8. Agregar un chip "Sin movimiento en N días" para ingredientes whose last price event is old.

---

## `/reportes/price-impact` (reportes-price-impact.png)

### 5-Hat Analysis

**Counter staff:** Esta página no les afecta directamente.

**Owner-finance:** La pregunta "¿subo los precios?" tiene respuesta aquí. La tabla de recetas afectadas con `Δ costo por unidad` es directa y accionable. La sección de "Productos bajo objetivo (33%)" con precio sugerido es exactamente lo que el owner necesita para decidir.

**Production-baker:** Ve qué recetas cambian de costo, pero el Δ costo por unidad en Gs. abstractos no les dice nada. Necesitan saber: "¿cuánto más me cuesta hacer una bandeja de pan de queso?"

**New user:** Sin contexto, no saben qué significa "33%" en el subtítulo de la segunda sección. ¿33% de qué? ¿Del costo? ¿Del precio? ¿Del margen?

**Auditor:** Sin rango de fechas ni fuente de datos, no puede verificar de dónde vienen los números. Los umbrales (33%) no tienen explicación ni referencia a cómo se calcularon.

### Defects (P0/P1/P2)

- [P0] **La sección "Productos bajo objetivo (33%)" no explica qué es el 33%** — umbral de food cost? margen objetivo? Aparece hardcodeado en el template sin tooltip ni ayuda. User ve "33%" y no sabe qué significa.
- [P0] **La tabla de recetas afectadas no tiene contexto de escala** — "+Gs. 150" por unidad no dice nada si no sabés cuántas unidades vendés de esa receta. Falta: unidades vendidas en el período × delta = impacto total.
- [P1] **No hay botón "Volver al ingrediente"** — estás viendo el impacto de CAMBIAR el precio del ingrediente X, pero no hay forma fácil de volver a la vista del ingrediente o de hacer otro análisis de impacto.
- [P1] **El valor delta se muestra en verde/rojo por signo, pero no hay escala** — "+Gs. 150" en rojo es una lectura binaria. Un delta de Gs. 150 en una receta que se vende 500 veces al día es Gs. 75.000 de impacto; en una que se vende 2 veces es irrelevante.
- [P2] **Sin vínculo desde `/reportes/precios`** — el flujo natural es "miro precios → un ingrediente subió → quiero ver el impacto → voy a price-impact". No hay link desde la página de precios al ingrediente específico en price-impact.
- [P2] **Empty state dice "Ninguna receta cambia de forma significativa"** — pero no dice qué umbral usa para "significativamente". El usuario no sabe si el umbral es 1 Gs. o 1.000 Gs.

### Complete Design Wishlist

1. Reemplazar "(33%)" con un tooltip o link a la explicación del umbral: "Productos cuyo food cost supera el 33% del precio de venta — margen < 67%."
2. Agregar columna "Impacto total (Gs.)" a la tabla de recetas: `delta_unit_cost × ventas_en_período`.
3. Agregar columna "Unidades vendidas (período)" para que el owner pueda evaluar la materiality del impacto.
4. Agregar breadcrumb: "Precios → [Nombre del ingrediente] → Impacto" para navegación.
5. Desde `/reportes/precios`, agregar botón/link "Impacto en recetas →" en la columna de acciones de cada ingrediente.
6. En el empty state, explicar qué umbral se usa: "Ningún cambio > Gs. 50/unidad en el período."
7. Agregar `report_source_footer()` con el rango de fechas del análisis.

---

## `/reportes/freshness` (reportes-freshness.png)

### 5-Hat Analysis

**Counter staff:** El callout "Cociná HOY para rescatar" con la lista de insumos en riesgo les habla directamente. Es el contenido más accionable de cualquier página de reportes.

**Owner-finance:** "Valor en riesgo" en Gs. les dice cuánto dinero pueden perder si no actúan. Pero no hay un CTA para convertir "valor en riesgo" en una orden de producción o en una promoción.

**Production-baker:** El bloque "Cociná HOY" les dice exactamente qué recipes can rescue the at-risk stock. Pero el nombre de la receta y los insumos no están vinculados — el baker tiene que ir a cada receta manualmente.

**New user:** "Días hasta vencer según vida útil − fecha del último registro de precio (aprox. sin lotes)" — esta descripción es técnica y confusa. Un usuario nuevo no sabe qué es "fecha del último registro de precio" ni qué significa "aprox. sin lotes".

**Auditor:** Sin registro de cuándo se hizo este análisis ni de la vida útil de cada insumo, no puede auditar la cadena de decisiones. Tampoco hay forma de marcar un insumo como "ya cocinado/rescatado".

### Defects (P0/P1/P2)

- [P0] **Descripción del subtitle técnica y potentially misleading** — "vida útil − fecha del último registro de precio" implies que la vida útil es la distancia al último registro de precio, cuando en realidad life ulife debería ser un atributo del ingrediente. Esto confunde al usuario sobre cómo se calcula la fecha de vencimiento.
- [P0] **La tabla de "Cociná HOY" muestra las recetas que usan los insumos pero no tiene links a esas recetas** — `c.rescues|join(", ")` es solo texto, no clickeable. El baker tiene que buscar la receta a mano.
- [P1] **La columna "Estado" usa 4 tags diferentes que compiten visualmente** — `status_pill("VENCIDO")`, `status_pill("CRÍTICO")`, `<span class="badge">PRONTO</span>`, `<span class="text-muted">sin datos</span>`. Badge colors and styles are inconsistent with each other.
- [P1] **"sin datos" para urgency=unknown no tiene CTA** — el usuario ve "sin datos" y no sabe qué hacer para remediarlo. Debería decir "Registrá la vida útil del insumo en su ficha para activar el seguimiento."
- [P2] **No hay forma de marcar un insumo como "ya utilizado / rescatado"** — después de cocinar, el reporte sigue mostrando el mismo insumo en rojo.
- [P2] **El bloque "Cociná HOY" no dice cuándo fue la última vez que se usó ese insumo** — "usa: medialuna, pan dulce" sin contexto de stock actual o última fecha de uso.

### Complete Design Wishlist

1. Reescribir el subtitle: "Muestra qué insumos necesitan usarse pronto según su vida útil registrada y el stock actual. Sin fechas de vencimiento por lote, usamos la fecha del último movimiento como referencia."
2. Hacer los nombres de recetas en "Cociná HOY" links a `/recetas/{id}`.
3. En la tabla principal, hacer el nombre del insumo link a `/inventario/{id}` (ya está en freshness, pero confirmarlo).
4. Estandarizar los status badges: usar `status_pill` para todos los estados (VENCIDO/CRÍTICO/PRONTO/OK/sin datos).
5. Para "sin datos", agregar inline CTA: "Registrá la vida útil →" que lleva a `/inventario/{id}/editar`.
6. Agregar columna "Stock actual" a la tabla para que el baker sepa cuánto tiene disponible.
7. Agregar un botón "Marcar como rescatado" por fila que actualice el estado del insumo.
8. Agregar `report_source_footer()` con la fecha del análisis.

---

## `/reportes/demand` (reportes-demand.png)

### 5-Hat Analysis

**Counter staff:** No puede usar la página de demanda directamente — necesita que el baker interprete los números y planifique la producción. Lo que sí pueden hacer es ver "para mañana necesito X bandejas de medialuna" y transmitirlo al sector de producción.

**Owner-finance:** La "Lista de compras sugerida" con costo estimado (`m.gs(s.est_cost_gs)`) es gold. Pueden aprobar o rechazar la orden de compra basándose en el costo. PERO: no hay total de la lista de compras, solo fila por fila.

**Production-baker:** La tabla de previst por producto con `Batches` es exactamente lo que necesitan para planificar. Pero la columna `Promedio` no dice de cuántos días — "Promedio: 12" no dice si es 12 por día en promedio de 56 días, o el promedio de los últimos 3 días.

**New user:** La fórmula "Promedio 56d × factor del día × tendencia 14d" es útil pero está solo en el subtitle. Un new user no sabe qué significa "factor del día" ni qué es "tendencia 14d". Necesita un "?" tooltip que lo explique.

**Auditor:** Sin fecha de generación, sin rango de datos fuente, sin capacidad de exportar la lista de compras, la auditoria del forecast es imposible. Necesita saber: ¿con cuánta data se generó este forecast?

### Defects (P0/P1/P2)

- [P0] **No hay total de costo de la lista de compras** — la tabla de shopping tiene `est_cost_gs` por fila pero ningún total. El owner no puede saber cuánto va a gastar en la orden de compra sin sumar mentalmente.
- [P0] **No hay filtro de fecha para el forecast** — el forecast es "para mañana" pero no se puede cambiar la fecha destino. ¿Qué pasa si quiere ver el forecast para el viernes (día de alto consumo)? No hay forma.
- [P1] **Sin export de la lista de compras** — después de aprobar el forecast, el usuario necesita llevar la lista a su proveedor o al sistema de compras. No hay CSV ni PDF de la shopping list.
- [P1] **`forecast.avg_per_day` sin contexto temporal** — "Promedio: 12" — ¿12 de qué? ¿12 unidades? ¿12 por día? El template no lo clarifica. La fórmula dice "56d × factor" pero la columna dice "Promedio" no "Promedio 56d".
- [P2] **Sin atribución de fuente ni fecha de generación del forecast** — el auditor no sabe de cuándo es la base de datos ni cuándo se generó el reporte.
- [P2] **La columna "Tendencia" usa notación "×" sin explicación** — `1.2×` significa ¿+20% vs el baseline? ¿vs yesterday? ¿vs los últimos 14 días? Sin tooltip es ambiguo.

### Complete Design Wishlist

1. Agregar fila de total al final de la lista de compras: "Costo total estimado: Gs. X" con formato grande.
2. Agregar selector de fecha destino del forecast (no solo "mañana por defecto") — que el usuario pueda ver el forecast para cualquier día de la semana que quiera planificar.
3. Agregar botón "Exportar lista de compras" (CSV) desde la tabla de shopping.
4. Renombrar columna "Promedio" a "Promedio 56d" para que sea consistente con la fórmula del subtitle.
5. Agregar tooltip en la columna "Factor día": "Multiplicador basado en el día de la semana (ej. viernes = 1.4× por alto consumo)."
6. Agregar tooltip en la columna "Tendencia": "Comparación del promedio de los últimos 14 días vs el promedio general de 56 días."
7. Agregar `report_source_footer()` con la fecha de generación y el rango de datos fuente.
8. En la shopping list, agregar columna "Receta" o "Usado en" para que el shopper sepa para qué producto es cada insumo.

---

## `/reportes/metodos-pago` (reportes-metodos-pago.png)

### 5-Hat Analysis

**Counter staff:** Quiere saber al empezar el turno cuántos pagos en efectivo vs tarjeta tuvo ayer para cuadrar la caja. La tabla es útil. Pero no puede ver esto desde el mostrador sin ir a Reportes — un widget en el `/inicio` sería más útil.

**Owner-finance:** El desglose por método de pago les ayuda a planificar la logística bancaria (cuántas transferencias, cuántos efectivos). Pero sin series temporales, no pueden ver tendencias: "¿Estamos recibiendo más pagos en transferencia que hace 3 meses?"

**Production-baker:** No directamente relevante para producción.

**New user:** La tabla es fácil de leer. El empty state con `empty_state()` macro es bueno. Pero no entiende por qué ve ciertos métodos de pago (ej. "MIXTO") y qué significa exactamente.

**Auditor:** No tiene forma de exportar la tabla. No tiene cómo saber qué período se está mostrando (sin fecha en el título ni en el subtitle). Y la estructura de `breakdown` como dict significa que no hay forma de saber desde el audit log qué campos existen — si mañana aparece un método nuevo ("QR"), no se detecta.

### Defects (P0/P1/P2)

- [P0] **El período filtrado no se muestra en el título ni en el subtitle** — `start_date` y `end_date` se pasan como `""` (empty string) por default. El usuario no sabe si está viendo "todo el historial" o "solo hoy". Para un reporte financiero esto es unacceptable.
- [P0] **Sin export** — no hay botón CSV/PDF/XLSX para un reporte financiero. Owner/auditor no puede presentar esto al contador.
- [P1] **Redundant `</div>` after `</table>` in template** — `insight_metodos_pago.html` line 41 has an extra closing `</div>` after `</table>` that doesn't match any open tag. The `data-loaded-section` div closes immediately before the table. Creates malformed HTML structure.
- [P1] **Métodos de pago como dict key sin enumeración explícita** — el template hace `{% for method, data in breakdown.items() %}` pero no hay garantía de qué keys existen. Si un método tiene 0 ventas, ¿aparece en la lista? Auditor no puede verificar completitud.
- [P2] **Sin visualización** — una tabla de métodos de pago se beneficiaría enormemente de un gráfico de torta o barras horizontales. Es el tipo de dato que se entiende mejor visualmente que en números.
- [P2] **El filtro de fechas usa `grid grid-2` pero con form-row adentro** — el layout de los campos de fecha en la línea 15–16 usa `grid grid-2` + `form-row`, que es mixto. Debería usar `form-grid` o `form-row` consistentemente.
- [P2] **No hay preset de período rápido** (Hoy, Ayer, Esta semana, Mes) — solo un date picker open que requiere typing/selección manual.

### Complete Design Wishlist

1. Mostrar el rango de fechas activo en el subtitle: "Mostrando del 01/09/2026 al 30/09/2026" o "Todo el historial" si no hay filtro.
2. Agregar presets de período rápido: Hoy | Ayer | Esta semana | Mes | Últimos 30 días — como chips/toggles.
3. Agregar botón "Exportar CSV" en la parte superior, al lado derecho.
4. Agregar gráfico de barras horizontales o torta con los `% del total` como visualización complementaria a la tabla.
5. En la tabla, agregar columna que muestre % del total como barra inline (como en `ventas-hora`) para view at-a-glance.
6. Asegurar que todos los métodos de pago del sistema aparezcan aunque tengan 0 ventas, con "0" y "0.0%" — así el auditor puede verificar que ningún método se está omitiendo silenciosamente.
7. Corregir el `</div>` extra en el template — el `data-loaded-section` div debe envolver tanto el skeleton como la tabla, no cerrar antes de la tabla.
8. Reemplazar el form `grid grid-2` + `form-row` mix con un layout consistente para los campos de fecha.

---

*Critique batch complete. 8 pages analyzed. Next batch: pending.*
