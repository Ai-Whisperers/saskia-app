# 02 — Ventas

> **Qué es:** el registro de cada venta del día. **La pantalla que más vas a usar.**

## Cómo llegar

**Ventas** en la barra superior. Verás tres secciones: **Quick-sell**,
**Nueva venta**, e **Historial**.

![Pantalla de ventas — placeholder screenshot]

## Sección 1: Quick-sell (botones grandes arriba)

Son los **5 productos más vendidos en los últimos 14 días**. Cada uno
es un botón grande con el nombre + precio.

**Uso:** tocá el botón cuando vendés uno de esos productos. Se registra
una venta de **1 unidad** automáticamente. Si vendés 2 unidades, tocá el
botón dos veces.

> **Truco:** los botones son grandes para que un cliente pueda cobrar
> en menos de 5 segundos.

## Sección 2: Nueva venta (formulario completo)

Para ventas que **no son los top 5** o que requieren más detalle:

![Formulario de nueva venta — placeholder screenshot]

El formulario tiene estos campos:

| Campo | Qué poner |
|---|---|
| **Escanear SKU (opcional)** | Si tenés un lector de código de barras, escanealo acá. Si no, dejalo vacío. |
| **Producto** | Elegí el producto desde el menú. |
| **Cantidad** | Cuántas unidades (por defecto: 1). |
| **Forma de pago** | efectivo / transferencia / tarjeta / otro. |
| **Descuento (Gs.)** | Si le hiciste descuento al cliente, escribilo acá en guaraníes. |
| **Cliente (teléfono)** | Si querés registrar quién compró, escribí el teléfono. |
| **Notas** | Algo que quieras anotar ("cliente pidió extra queso"). |
| **Fecha y hora** | Por defecto: ahora. Tocá para cambiarla si necesitás registrar una venta anterior. |

Después de completar, hacé clic en **Registrar venta**.

### Opción A: Escaneo de SKU (si tenés lector de código de barras)

Si tu panadería usa lectores de código de barras USB (los que parecen
un control remoto), esto es para vos:

1. Tocá el campo **"Escanear SKU"**.
2. Escaneá el producto. La app busca el producto en la base de datos
   y llena el formulario automáticamente.
3. Revisá que sea el producto correcto, completá la cantidad, y
   confirmá.

**Si el SKU no existe:** la app muestra "SKU no encontrado". Tendrás que
cargar ese producto primero en
[Productos](04-productos.md) → Asignar SKU.

### Opción B: Selección manual

Si no usás lector:

1. Toca el campo **Producto** — se abre una lista.
2. Buscá por nombre o scrolleá.
3. Toca el producto.
4. Completá el resto del formulario.
5. Confirmá.

## Sección 3: Historial (tabla abajo)

Muestra todas las ventas registradas. Podés filtrar:

| Filtro | Para qué sirve |
|---|---|
| **Buscar** | Escribí parte del nombre del producto o teléfono del cliente. |
| **Todos los productos** | Filtrá por un producto específico. |
| **Todo el historial** | Filtrá por últimos 7 / 30 / 90 días. |
| **Limpiar** | Borra todos los filtros. |

## Anular una venta

Si te equivocás (vendiste algo dos veces, o cobraste mal):

1. Buscá la venta en el **Historial**.
2. Tocá **Anular** al final de la fila.
3. Confirmá.

**La venta se marca como anulada** (no se borra) y el stock de los
ingredientes se devuelve automáticamente. Es importante no borrar — el
log de auditoría necesita el registro para que sepamos qué pasó.

## Cómo funciona el stock al vender

Cuando registrás una venta, la app **descuenta automáticamente** los
ingredientes del inventario según la receta del producto. Si vendés
una docena de medialunas, se descuenta la harina, los huevos, la
manteca, etc., en las proporciones correctas.

> **Si la receta no está bien cargada**, las proporciones se calculan
> mal y tu stock queda incorrecto. Es importante mantener las recetas
> actualizadas — ver [05-recetas.md](05-recetas.md).

## Errores comunes

| Error | Qué significa | Qué hacer |
|---|---|---|
| **"Producto sin receta"** | Estás vendiendo algo sin ingredientes cargados | Crear la receta primero |
| **"Stock insuficiente"** | No te queda suficiente ingrediente | Anotar para reponer, pero la venta igual se registra (no se bloquea) |
| **"Stock bajo"** | Te queda poco del ingrediente | Ir a Reponer después |

## Tu día a día con esta pantalla

**Cuando entra un cliente:**

1. Si es uno de los 5 productos top → tocá el botón de Quick-sell.
2. Si no → usá el formulario, elegí el producto, completá.
3. Con código de barras → escaneá directo.

**Al final del día:**

1. Mirá el **Historial** para confirmar que todas las ventas están.
2. Si falta alguna, registrala manualmente con la fecha y hora real.

## Siguiente paso

→ [03-inventario.md](03-inventario.md) — cómo gestionar ingredientes y stock.
