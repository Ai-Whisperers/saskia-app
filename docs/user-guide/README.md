# Guía de Saskia RMS

> **Para Saskia.** Esta guía explica, página por página, todo lo que
> tiene la app y cómo usarlo en el día a día de la panadería.

**URL:** `https://saskia-rms.paragu-ai.com`

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

**Próximo paso:** [00-quickstart.md](00-quickstart.md) →
