# BACKLOG: Unidades de venta y bundles (docenas) — productos

**Creado:** 2026-10-05 · **Prioridad:** después del sprint de producción
**Pedido por:** Ivan — "we shouldn't have products like 'Docena muffins vainilla' — they should be 'Muffins vainilla' with price per muffin and deals for 6/12 etc."

## Estado actual (auditado en prod, 2026-10-05)

29 productos. Conviven TRES modelos de venta inconsistentes:

1. **Unidad suelta:** `Muffin de vainilla` ₲8.000/und · `Muffin de chocolate` ₲8.500 · `Oliebollen (unidad)` ₲5.500 · `Tompoezen` ₲12.000 · `Stroopwafel` ₲7.000
2. **Docena como producto separado:** `Docena muffins vainilla` ₲96.000 (=8.000/und ✓) · `Docena muffins chocolate` ₲108.000 (=9.000/und ✗ no coincide con la unidad) · `Docena tompoezen` ₲130.000 (=10.833/und, vendiendo la unidad a 12.000 — **descuento oculto del 10%**) · `Docena stroopwafels` ₲80.000 (vs 84.000 por unidad) · `Docena oliebollen` ₲70.000 (vs 66.000 — **docena más cara que 12 sueltas**)
3. **Media docena de un solo producto:** `Facturas (media docena)` ₲18.000 / `Facturas (docena)` ₲35.000 (media docena×2=36.000 → bundle correcto con descuento)

**Problemas concretos:**
- Producción: hornear 1 muffin = 1 plan; la "docena" es un producto aparte con receta duplicada → el plan de producción cuenta mal y la precisión del forecast se bifurca entre ambos SKUs.
- Stock/ventas: vender 6 muffins no descuenta nada de la docena ni viceversa.
- Reportes: margen por producto se divide entre dos SKUs del mismo bien.
- Pedidos: el cliente pide "6 muffins" → tiene que existir un SKU exacto o el operador improvisa.

## Diseño propuesto

**Principio:** 1 producto = 1 receta = 1 unidad de horneado. Los packs son **presentaciones de venta** (sale units), no productos.

1. **Producto base único** ("Muffins vainilla"), `portion_label = "1 unidad"`, precio por unidad.
2. **Tabla nueva `product_sale_unit`** (o campo JSON si no queremos migración):
   - `unit_name` ("unidad", "media docena", "docena", "bolsa 60 uds")
   - `qty_units` (1, 6, 12, 60)
   - `price_gs` (8.000 / 45.000 / 90.000 — el pack lleva su propio precio con descuento opcional)
   - `is_default` (qué elige el POS por defecto)
   - `barcode/sku` opcional por presentación
3. **POS/ventas:** selector de presentación por línea (dropdown al lado del producto). La línea guarda `(product_id, sale_unit_id, qty_presentation)`; stock y producción se convierten a unidades base con `qty_units`.
4. **Producción:** planifica SIEMPRE en unidades base → el plan deja de duplicarse y el forecast se concentra en un solo SKU.
5. **Pedidos:** mismo selector; "Docena empanadas" sigue funcionando como texto de búsqueda porque el alias puede indexarse.
6. **Migración de datos (one-shot, idempotente):**
   - `Docena muffins vainilla` → merge ventas+pedidos históricos en `Muffins vainilla` con sale_unit "docena" @ 96.000.
   - Corregir precios inconsistentes tompoezen/stroopwafel/oliebollen explícitamente (decidir el precio de pack).
   - `Facturas (docena/media)` → 1 producto con 2 presentaciones.
   - Casos especiales que probablemente quedan como productos reales: `Pan lactal`, tortas enteras (`Cheesecake entera` = receta distinta a la porción), `Pepernoten (bolsa 60 uds)` (envase real), `Carrot Cake (43x33)` (formato de bandeja).
7. **Reportes:** margen y producidos por producto base; opcional drill "¿cuántas docenas se vendieron?" vía sum de presentaciones.

## Impacto / estimación

- Schema + migración: 2-3h · Selector en POS/ventas: 3h · Pedidos: 2h · Producción (unificar plan a base): 2h · Migración de datos + verificación: 3h · Tests: 2h → **~14-15h, 1 sprint chico.**
- Riesgo medio: doble SKU histórico en ventas/reportes → la migración debe mergear, no dejar huérfanos.
- Pre-requisito limpio: correr primero el close-day bulk para tener datos de "Producido" por producto base.

## Decisión pendiente del operador

1. ¿Precio de docena con descuento fijo (ej. -10%) o precio por pack cargado a mano?
2. ¿"Media docena" solo para facturas o para todos?
3. ¿Mantener SKUs viejos como alias de búsqueda invisibles o borrarlos?
