# Guía de Saskia RMS

> **Para Saskia.** Esta guía explica, página por página, todo lo que
> tiene la app y cómo usarlo en el día a día de la panadería.

**URL activa:** `https://saskia-vps.paragu-ai.com`  *(si ves "service suspended", contactá al equipo — esa URL no es la correcta)*
**URL alternativa (suspendida):** `https://saskia-rms.paragu-ai.com` — Render, NO usar
**Versión del manual:** 2026-10-01 · schema 75 · commit `5e81760` · 16 secciones
**Manual versión:** v1.0 (ver "Cómo verificar la versión" abajo)

## Índice rápido

| # | Sección | Cuándo leerla |
|---|---|---|
| [0](00-quickstart.md) | Primer inicio de sesión | Antes de usar la app por primera vez |
| [1](01-dashboard.md) | Pantalla principal (Inicio) | Todos los días al abrir |
| [2](02-ventas.md) | Ventas (lo más usado) | Cada venta del día |
| [3](03-inventario.md) | Inventario / ingredientes | Al reordenar, al hacer compras |
| [4](04-productos.md) | Productos y precios | Al cambiar precios, agregar productos |
| [5](05-recetas.md) | Recetas | Al crear o modificar recetas |
| [6](06-clientes.md) | Clientes | Al registrar clientes nuevos |
| [7](07-merma.md) | Merma (desperdicio) | Cada vez que algo se tira |
| [8](08-produccion.md) | Plan de producción | Al planificar el día |
| [9](09-reportes.md) | Reportes (IVA, libro de ventas, diario) | Mensual, antes de declarar |
| [10](10-auditoria.md) | Auditoría / log | Cuando algo se borró y querés saber quién |
| [11](11-configuracion.md) | Configuración | Cambios poco frecuentes |
| [12](12-ops.md) | Estado operativo (diagnóstico) | Cuando algo no carga |
| [13](13-reponer.md) | Reponer stock (lista de compras) | Antes de ir al super o proveedor |
| [14](14-cierre.md) | Cierre diario (EOD) | Al final del día |
| [15](15-excel.md) | Excel (importar/exportar) | Para copias de seguridad o cargas masivas |

## Conceptos generales

### Idioma y zona horaria

- Toda la app está en **español rioplatense** (usamos "vos": "guardá", "vendé").
- La moneda es **guaraní (Gs.)** y se muestra sin decimales (`1.234.567`).
- El horario que importa es **Asunción (UTC-4)**. El sistema
  convierte automáticamente — no necesitás pensar en zonas horarias.

### Cómo se ve la app

Todas las pantallas tienen el mismo esqueleto:

- **Barra superior** con el logo `🍰 Saskia RMS` y enlaces a cada sección.
- **Indicador de salud** (puntito verde) en la esquina — si está rojo, hay
  problema técnico.
- **Botón 🌙 / ☀️** — cambia entre tema claro y oscuro.
- **Botón ⎋ (cerrar sesión)** arriba a la derecha.

### Tres reglas de oro

1. **Si algo no carga:** esperá 5 segundos y refrescá (`F5`). El sitio se
   "duerme" después de 5 minutos sin uso y tarda medio segundo en
   despertar.
2. **Si la pantalla está vacía:** probablemente sea porque todavía no
   cargaste datos. Andá a **Inventario** o **Productos** para empezar.
3. **Si ves un error:** anotá qué estabas haciendo y avisá a Iván. No
   te frustres — los errores se pueden reproducir y arreglar.

## Mapa visual de la app

```
Inicio            → resumen del día + avisos
Productos         → qué vendés + precios
Recetas           → cómo se hace cada producto
Inventario        → qué tenés en la panadería
Ventas            → registrar una venta
Clientes          → quién te compró
Producción        → cuánto hornear mañana
Cierre (EOD)      → marcar tareas del final del día
Merma             → desperdicio
Reportes          → IVA + libro de ventas + resumen diario
Auditoría         → log de todo lo que pasó
Configuración     → preferencias
Reponer           → lista de compras para hacer
Cierre (EOD)      → checklist del final del día
Excel             → importar/exportar planilla
Ops               → diagnóstico (solo Iván)
```

---

## Lo que podés hacer — y lo que todavía no

**Versión:** schema 75 · commit `36639ae` · 2026-10-01

### ✅ Funcionalidades activas (lista cerrada)

| # | Flujo | Página | Captura |
|---|---|---|---|
| 1 | Registrar una venta (POS, scan, multi-item) | [`02-ventas`](02-ventas.md) | `01-ventas-pos.png` |
| 2 | Anular una venta del día | [`02-ventas`](02-ventas.md) → Historial | (en `01-ventas-pos.png`) |
| 3 | Crear pedido anticipado (recetas, orden) | [`03-pedidos`](03-pedidos.md) | `04-pedidos-nuevo.png` |
| 4 | Ver el board de pedidos pendientes | [`03-pedidos`](03-pedidos.md) | `03-pedidos-board.png` |
| 5 | Plan de producción del día (manual) | [`05-produccion`](05-produccion.md) | `05-produccion.png` |
| 6 | Plan de producción de mañana (auto) | [`05-produccion`](05-produccion.md) | `06-produccion-manana.png` |
| 7 | Cierre diario (EOD checklist) | [`14-cierre`](14-cierre.md) | `07-eod-checklist.png` |
| 8 | Crear / editar producto | [`04-productos`](04-productos.md) | `08-productos.png`, `09-productos-nuevo.png` |
| 9 | Crear / editar receta con foto | [`05-recetas`](05-recetas.md) | `10-recetas.png`, `11-recetas-nueva.png` |
| 10 | Crear / ajustar ingrediente (stock, precio) | [`03-inventario`](03-inventario.md) | `12-inventario.png`, `13-inventario-nuevo.png` |
| 11 | Registrar merma / desperdicio | [`07-merma`](07-merma.md) | `14-merma.png` |
| 12 | Reponer stock (con precios scrapeados) | [`13-reponer`](13-reponer.md) | `15-reorder.png` |
| 13 | Reporte diario de ventas | [`09-reportes`](09-reportes.md) | `16-reportes-diario.png` |
| 14 | Registrar cliente y sumar puntos | [`06-clientes`](06-clientes.md) | `17-clientes.png` |
| 15 | Canjear puntos del cliente (POS) | [`02-ventas`](02-ventas.md) → "Usar puntos" | (en POS) |
| 16 | Lista de compras (sincroniza con stock bajo) | [`06-lista-compras`](06-clientes.md#lista-de-compras) | `18-shopping-list.png` |

### ⏳ Lo que **todavía no** podés hacer (wishlist)

| # | Lo que falta | Por qué | Cuándo (planificado) |
|---|---|---|---|
| A | Sincronizar planillas de Drive en vivo | Sólo importa Excel manualmente | Q4 2026 |
| B | Notificación WhatsApp al cliente cuando su pedido está listo | Evolution API no configurada | Sin fecha |
| C | Pagos con tarjeta (POS integrado con Bancard) | Requiere uno con extensiones | Sin fecha |
| D | Imprimir tickets en la impresora fiscal | Requiere driver específico | Sin fecha |
| E | Multi-usuario (roles: cajero / administrador / panadero) | Sólo hay un usuario (`demo`) | Q4 2026 |
| F | App móvil nativa (iOS / Android) | Hoy sólo funciona en navegador | Sin fecha |
| G | Funcionar sin internet (modo offline) | La app requiere conexión constante | Sin fecha |
| H | Códigos QR para clientes (auto-checkin) | No implementado | Sin fecha |

Si necesitás alguna de estas, anotalo en `installer/ROUND-2-NOTES.md` o avisá a Iván.

### ⚠️ Funciones que tienen riesgo de rotura conocida

- **`/ventas` carga lenta con >200 ventas en pantalla.** Si la página se cuelga, refrescá con `F5` o navegá a otra sección y volvé.
- **`/reorder` usa scraping externo** (Superseis, Stock.com.py). Si la página no carga precios, los scrapers pueden estar caídos — usá el botón "📤 Cargar CSV" para no quedar bloqueada.
- **El navegador "duerme" a los 5 minutos** y tarda medio segundo en despertar. Es normal.

---

## Cómo verificar que tenés la versión correcta

Tres formas:

| Cómo | Dónde mirar | Cómo se ve OK |
|---|---|---|
| En el navegador | Pie de página de cualquier pantalla | "Saskia RMS v1.0 · Sistema local · 2026" |
| Al iniciar sesión | Header `X-Agent` en respuesta `/login` | `SaskiaRMS/1.0` |
| En este manual | El número "v1.0" arriba | Dice `2026-10-01 · schema 75` |

Si los tres no coinciden, **el manual está desactualizado** — avisá a Iván para que lo actualice.

---

**Próximo paso:** [00-quickstart.md](00-quickstart.md) →
