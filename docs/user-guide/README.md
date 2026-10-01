# Guía de Saskia RMS

> **Para Saskia.** Esta guía explica, página por página, todo lo que
> tiene la app y cómo usarlo en el día a día de la panadería.

**URL activa:** `https://saskia-vps.paragu-ai.com`  *(si ves "service suspended", contactá al equipo — esa URL no es la correcta)*
**URL alternativa (suspendida):** `https://saskia-rms.paragu-ai.com` — Render, NO usar
**Versión del manual:** 2026-10-01 · schema 83 · commit `<HEAD>` · 17 secciones
**Manual versión:** v1.1 (ver "Cómo verificar la versión" abajo)

## Índice rápido

| # | Sección | Cuándo leerla |
|---|---|---|
| [0](00-quickstart.md) | Primer inicio de sesión | Antes de usar la app por primera vez |
| [1](01-dashboard.md) | Pantalla principal (Inicio) | Todos los días al abrir |
| [2](02-ventas.md) | Ventas (lo más usado) | Cada venta del día |
| [3](03-pedidos.md) | Pedidos anticipados y suscripciones | Para encargos y entregas a domicilio |
| [4](04-inventario.md) | Inventario / ingredientes | Al reordenar, al hacer compras |
| [5](05-productos.md) | Productos y precios | Al cambiar precios, agregar productos |
| [6](06-recetas.md) | Recetas | Al crear o modificar recetas |
| [7](07-clientes.md) | Clientes | Al registrar clientes nuevos |
| [8](08-merma.md) | Merma (desperdicio) | Cada vez que algo se tira |
| [9](09-produccion.md) | Plan de producción | Al planificar el día |
| [10](10-reportes.md) | Reportes (IVA, libro de ventas, diario) | Mensual, antes de declarar |
| [11](11-auditoria.md) | Auditoría / log | Cuando algo se borró y querés saber quién |
| [12](12-configuracion.md) | Configuración | Cambios poco frecuentes |
| [13](13-ops.md) | Estado operativo (diagnóstico) | Cuando algo no carga |
| [14](14-reponer.md) | Reponer stock (lista de compras) | Antes de ir al super o proveedor |
| [15](15-cierre.md) | Cierre diario (EOD) | Al final del día |
| [16](16-excel.md) | Excel (importar/exportar) | Para copias de seguridad o cargas masivas |

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
Ventas            → registrar una venta
Pedidos           → encargos anticipados + suscripciones
Inventario        → qué tenés en la panadería
Productos         → qué vendés + precios
Recetas           → cómo se hace cada producto
Clientes          → quién te compró
Merma             → desperdicio
Producción        → cuánto hornear mañana
Reportes          → IVA + libro de ventas + resumen diario
Auditoría         → log de todo lo que pasó
Configuración     → preferencias
Ops               → diagnóstico (solo Iván)
Reponer           → lista de compras para hacer
Cierre (EOD)      → checklist del final del día
Excel             → importar/exportar planilla
```

---

## Lo que podés hacer — y lo que todavía no

**Versión:** schema 83 · commit `<HEAD>` · 2026-10-01

### ✅ Funcionalidades activas (lista cerrada)

| # | Flujo | Página | Captura |
|---|---|---|---|
| 1 | Registrar una venta (POS, scan, multi-item) | [`02-ventas`](02-ventas.md) | `01-ventas-pos.png` |
| 2 | Anular una venta del día | [`02-ventas`](02-ventas.md) → Historial | (en `01-ventas-pos.png`) |
| 3 | Crear pedido anticipado (recetas, orden) | [`03-pedidos`](03-pedidos.md) | `04-pedidos-nuevo.png` |
| 4 | Ver el board de pedidos pendientes (KDS kanban) | [`03-pedidos`](03-pedidos.md) | `03-pedidos-board.png` |
| 5 | Plan de producción del día (manual) | [`09-produccion`](09-produccion.md) | `05-produccion.png` |
| 6 | Plan de producción de mañana (auto) | [`09-produccion`](09-produccion.md) | `06-produccion-manana.png` |
| 7 | Cierre diario (EOD checklist) | [`15-cierre`](15-cierre.md) | `07-eod-checklist.png` |
| 8 | Crear / editar producto | [`05-productos`](05-productos.md) | `08-productos.png`, `09-productos-nuevo.png` |
| 9 | Crear / editar receta con foto | [`06-recetas`](06-recetas.md) | `10-recetas.png`, `11-recetas-nueva.png` |
| 10 | Crear / ajustar ingrediente (stock, precio) | [`04-inventario`](04-inventario.md) | `12-inventario.png`, `13-inventario-nuevo.png` |
| 11 | Registrar merma / desperdicio | [`08-merma`](08-merma.md) | `14-merma.png` |
| 12 | Reponer stock (con precios scrapeados) | [`14-reponer`](14-reponer.md) | `15-reorder.png` |
| 13 | Reporte diario de ventas | [`10-reportes`](10-reportes.md) | `16-reportes-diario.png` |
| 14 | Registrar cliente y sumar puntos | [`07-clientes`](07-clientes.md) | `17-clientes.png` |
| 15 | Canjear puntos del cliente (POS) | [`02-ventas`](02-ventas.md) → "Usar puntos" | (en POS) |
| 16 | Lista de compras (sincroniza con stock bajo) | [`14-reponer`](14-reponer.md) → Lista de compras | `18-shopping-list.png` |
| 17 | Suscripción semanal de un cliente (pedido recurrente) | [`03-pedidos`](03-pedidos.md) → Suscripciones | (en `03-pedidos-board.png`) |

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
| En este manual | El número "v1.x" arriba | Dice `2026-10-01 · schema 82` |

Si los tres no coinciden, **el manual está desactualizado** — avisá a Iván para que lo actualice.

---

**Próximo paso:** [00-quickstart.md](00-quickstart.md) →
