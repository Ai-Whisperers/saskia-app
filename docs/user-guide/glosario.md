# Glosario — Términos de la panadería

> **Referencia rápida.** Definiciones de los términos técnicos y del
> dominio que vas a encontrar en esta app y en el día a día de la
> panadería. Si un término te suena raro, mirá acá primero.

## Términos de producción y panadería

### Escandallo
Cálculo del **costo real** de un producto terminado. Lista cada
ingrediente que lleva la receta, multiplica por su precio unitario, y
suma todo. Te permite saber cuánto te sale producir un producto y,
por lo tanto, qué margen te queda al venderlo. La app lo calcula
automáticamente desde la receta.

### Merma
**Desperdicio**: producto que se elaboró pero no se vendió (se quemó,
se pasó de fecha, se rompió, sobró del día). Cada evento de merma se
registra con su origen: producción (se quemó en horno), venta
(cliente devolvió), o inventario (se venció en góndola). El semáforo
de food cost usa la merma para avisarte si está alta.

### Food cost (costo de comida)
Porcentaje del precio de venta que se va en ingredientes. **Fórmula:**
`(costo_real / precio_venta) × 100`. Si el food cost de un producto es
40%, significa que 40.000 Gs de cada 100.000 Gs vendidos se van en
materia prima. **Semáforo:** verde ≤35%, amarillo 35-50%, rojo >50%.

### Receta técnica
La fórmula estandarizada de un producto: lista de ingredientes con
cantidades (en gramos, unidades, litros). En la app cada receta
está asociada a un producto, y cuando vendés el producto se
descuenta automáticamente de inventario. Las sub-recetas son
recetas que se usan dentro de otras recetas (ej: pasta frola usada
en tartas).

### Stock
Cantidad disponible de un ingrediente (harina, azúcar, manteca...) o de
un producto terminado. **Stock actual** = última cantidad contada o
comprada menos lo que se usó en producción/ventas. **Stock bajo** =
por debajo del mínimo configurado (aparece en la lista de reponer).

### Cierre diario (EOD)
"End of Day". Rutina que se hace al final de la jornada para
concliar ventas, contar caja, revisar mermas, y dejar todo listo para
el día siguiente. La app tiene un formulario con 9 checks
(`recuento_caja`, `ventas_conciliadas`, `stock_bajo_revisado`,
`ingredientes_reordenados`, `merma_registrada`, `prep_mañana`,
`depósito_caja`, `equipo_limpio`, `comprobantes_archivados`). Una
vez completado, el día queda **bloqueado**: no se puede borrar ni
anular ventas de esa fecha.

### Arqueo de caja
Conteo físico del efectivo en caja al cierre. Comparás lo que dice el
sistema (ventas en efectivo − cambios − retiros) con lo que realmente
hay. La diferencia es la **merma de caja** (sobrante o faltante).
Aparece como un check en el cierre diario.

### Producción
Plan de qué cocinar y cuánto, basado en el **pronóstico de ventas**.
La app usa el histórico de los últimos 30+ días, agrupado por día
de la semana, para estimar cuánto vas a vender mañana (más los
eventos especiales: cumpleaños, pedidos). Te sugiere una lista de
producción: "15 kg de pan, 20 medialunas".

### Pedido
Encargo anticipado de un cliente con fecha prometida de entrega.
**Diferencia con venta:** la venta es inmediata (entrega ahora);
el pedido se prepara después. Cada pedido tiene un link público
(`/p/{token}`) que se le manda al cliente por WhatsApp para que
suba el comprobante de transferencia.

### Comprobante
Foto o PDF del recibo de transferencia bancaria. El cliente lo sube
vía el link público `/p/{token}` después de pagar. La app lo
guarda en `/data/payment_receipts/{pedido_id}/` y marca el pedido
como "esperando confirmación".

## Términos técnicos / app

### SKU
"Stock Keeping Unit" — código único que identifica un producto. En
esta app, el SKU lo generás vos (ej: "MAIZ-001" para el producto
"Medialuna de maiz"). Sirve para escanear con código de barras y
para vincular productos con recetas.

### Migración
Cambio al esquema de la base de datos (agregar columna, crear tabla,
borrar índice). Cada migración tiene un número (`migration 092`,
`migration 098`). La app las aplica al arrancar; si la base está
"atrasada" corre las que faltan. **No borrar migraciones ya
aplicadas** — eso rompe el historial.

### Backup
Copia de seguridad de la base de datos y los archivos subidos
(comprobantes). Se dispara automáticamente al hacer el cierre diario,
o vía el endpoint `/admin/backup` (requiere login). El
`/healthz/backup` muestra cuándo fue el último y si está viejo
(más de 24h aparece como `stale: true`).

### CSRF
"Cross-Site Request Forgery" — ataque donde un sitio malicioso te
hace enviar un formulario sin tu consentimiento. La app lo previene
con un **token CSRF** invisible en cada formulario: el navegador lo
manda junto con los datos y el servidor lo valida. Si el token no
coincide, la app rechaza la acción. No tenés que hacer nada — es
automático.

### Auditoría
Log de **cada acción importante**: crear/editar/borrar producto,
anular venta, hacer cierre, cambiar configuración. Cada entrada
guarda quién (usuario o "anon" si fue por link público), cuándo,
qué cambió (antes/después), y desde qué IP. Visible en
`/auditoria`. Sirve para entender qué pasó cuando algo se borró.

### Health check
Endpoint `/healthz` que devuelve `{"status": "ok"}` si la app está
viva. El puntito verde/rojo de la barra superior lee este endpoint.
`/healthz/summary` da una vista más detallada (DB, errores, backup,
disco). Si la app está "dormida", tarda medio segundo en
despertar.

### Schema version
Número que indica qué tan actualizada está la base de datos. La
app tiene `CURRENT_SCHEMA_VERSION = 98` (en `app/rms/config.py`).
Si la base real está en 97, al arrancar se aplica la migración
098 automáticamente.

### Prefijo de auditoría
Cadena que identifica el tipo de acción en el log de auditoría.
Los más usados: `write.product.create`, `write.sale.void`,
`write.customer.merge`, `write.bank.categorize`, `write.eod.complete`.
Lista completa en `/auditoria` (columna "Acción").

### Token público
Cadena aleatoria de 8 caracteres (ej: `LuptjSew`) que identifica
un pedido en su URL pública (`/p/{token}`). Es el único "auth" de
los endpoints públicos — quien tenga el link puede ver el pedido
y subir comprobante. Por eso **no lo pongas en redes sociales**;
compartilo solo por WhatsApp al cliente.

### Toggle dark/light mode
Botón 🌙/☀️ arriba a la derecha. Cambia entre tema claro y oscuro.
La preferencia se guarda en localStorage. **Atajo de teclado:**
`Ctrl+K` (o `Cmd+K` en Mac) abre el buscador global.