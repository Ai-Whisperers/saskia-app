# 18 — Suscripciones (entregas recurrentes)

> **Qué es:** la lista de clientes que tienen entregas periódicas
> (diarias, semanales, etc.) — por ejemplo, el café de la esquina que
> recibe 20 medialunas todos los lunes y miércoles. La app los agrupa
> y te ayuda a no olvidarte de ninguna entrega.

## Cómo llegar

**Ventas y clientes → Suscripciones** en la barra lateral.

> **Captura pendiente:** cuando se vuelva a correr el script de
> screenshots, esta sección va a tener una imagen acá
> (`screenshots/23-suscripciones.png` — todavía no generada).
> Por ahora seguí leyendo — la pantalla es bastante intuitiva.

## Qué muestra

Cada fila es una suscripción activa:

| Columna | Qué significa |
|---|---|
| **Cliente** | Nombre del cliente. |
| **Productos** | Qué productos lleva y en qué cantidad. |
| **Frecuencia** | Cada cuánto: diaria, semanal, quincenal, mensual. |
| **Próxima entrega** | Fecha del próximo envío. |
| **Estado** | Activa / Pausada / Cancelada. |

## Crear una nueva suscripción

1. **+ Nueva suscripción** arriba a la derecha
2. Elegí el cliente (o creá uno nuevo desde Clientes)
3. Tildá los productos que va a llevar
4. Para cada producto, poné la cantidad
5. Definí la frecuencia (diaria, semanal, etc.) y la fecha de inicio
6. **Guardar**

> **Tip:** si la frecuencia es semanal, elegí los **días de la semana**
> específicos (por ejemplo, "lunes y miércoles"). Si decís "semanal"
> sin días, la app asume "todos los lunes".

## Ver entregas pendientes del día

Arriba de la tabla hay un panel **"Entregas de hoy"** con la lista de
suscripciones que tienen que entregarse HOY. Cada fila tiene:

- El nombre del cliente y un botón para llamarlo (si tiene teléfono cargado)
- Los productos y cantidades
- Un botón **✓ Entregada** para marcarla cuando se entregó

Cuando marcás una entrega como entregada:

- Se genera automáticamente una **venta** en el sistema con esos productos
- Se descuenta del stock (si hay recetas cargadas, también de los ingredientes)
- Queda registrada en el historial del cliente

## Pausar una suscripción

Si el cliente se va de vacaciones o no necesita entregas por un tiempo:

1. Tocá **Pausar** en la fila de la suscripción
2. Elegí hasta qué fecha queda pausada
3. La suscripción no genera entregas durante ese período
4. Vuelve a activarse automáticamente al día siguiente de la fecha de pausa

## Cancelar definitivamente

Si el cliente se dio de baja:

1. Tocá **Cancelar** en la fila
2. Confirmá la cancelación
3. La suscripción pasa a "histórico" — no genera más entregas
4. Queda visible en el historial del cliente por si necesitás reactivarla

## Diferencia con Pedidos

- **Pedido** = un encargo puntual para una fecha específica (cumpleaños,
  torta para el sábado). Una sola entrega.
- **Suscripción** = entregas periódicas automáticas. Se renueva sola.

Si un cliente te pide "20 medialunas todos los lunes hasta fin de mes",
es una suscripción. Si te pide "30 medialunas para el sábado", es un
pedido.

## Notificaciones

Por defecto, la app te muestra las entregas de hoy en el panel
**"Entregas de hoy"** al iniciar sesión. Si querés también un aviso
por mail o por WhatsApp, pedile a Iván que active la integración
correspondiente en Configuración.

## Siguiente paso

→ [07-clientes.md](07-clientes.md) — cómo cargar clientes nuevos.
