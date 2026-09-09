# 03 — Inventario

> **Qué es:** la lista de todos tus ingredientes (harina, huevos, azúcar, etc.)
> con su stock actual y precios.

## Cómo llegar

**Inventario** en la barra superior.

![Pantalla de inventario — placeholder screenshot]

## Qué muestra la tabla

Cada fila es un ingrediente. Las columnas son:

| Columna | Qué significa |
|---|---|
| **Nombre** | El ingrediente (ej. "harina 0000"). |
| **Unidad** | Cómo se mide (kg, litros, unidades). |
| **Stock actual** | Cuánto tenés ahora mismo. |
| **Stock mínimo** | Cuando el stock baja de esto, salta el aviso en Inicio. |
| **Precio compra** | Cuánto te costó (en Gs., por unidad). |
| **Estado** | OK / Stock bajo / Negativo. |

## Crear un nuevo ingrediente

Tocá **+ Nuevo ingrediente** arriba a la derecha.

![Formulario de ingrediente nuevo — placeholder screenshot]

Llená los campos:

| Campo | Ejemplo |
|---|---|
| **Nombre** | "harina 0000" |
| **Unidad** | kg |
| **Stock actual** | 25.0 |
| **Stock mínimo** | 5.0 (cuando baje de 5, te avisa) |
| **Precio de compra** (Gs.) | 5500 (lo que pagaste por kg) |
| **Notas** | "Proveedor: Supermercado X" |

Tocá **Guardar**.

> **Tip:** el precio de compra es fundamental. Si no lo ponés, no
> podés calcular el margen real de cada producto.

## Editar un ingrediente

Tocá **Editar** al final de la fila. Te deja cambiar cualquier campo.

**Cuándo editar:**
- Cuando comprás más (actualizá el stock).
- Cuando cambia el precio.
- Cuando ajustás el stock mínimo (porque ahora comprás más o menos seguido).

## Eliminar un ingrediente

Tocá **Editar → Eliminar**. La app te pide confirmación.

> **Cuidado:** si eliminas un ingrediente que ya está en alguna receta,
> las recetas van a quedar rotas. Es mejor **dejar el ingrediente en 0
> de stock** que eliminarlo.

## Cómo se actualiza el stock

El stock baja automáticamente cuando:
- Vendés un producto que usa ese ingrediente.
- Registrás merma (desperdicio) en [07-merma.md](07-merma.md).

El stock sube cuando:
- Comprás mercadería y actualizás manualmente el campo.
- (Próximamente: integración con planillas de compras.)

Por ahora, **actualizar el stock manualmente** cada vez que comprás
algo es la forma más confiable.

## Productos vs. Ingredientes

**No confundas estas dos cosas:**

- **Productos** son lo que **vendés** (medialunas, tortas). Tienen precio
  de venta, margen, y pueden tener una receta.
- **Ingredientes** son lo que **usás para hacer** los productos (harina,
  huevos). Tienen precio de compra y stock.

La pantalla **Inventario** es para ingredientes. Para productos,
andá a [04-productos.md](04-productos.md).

## Tu flujo de trabajo

**Cada vez que comprás mercadería:**

1. Andá a Inventario.
2. Buscá el ingrediente.
3. Toca Editar.
4. Cambiá el stock al nuevo total (no sumes — reemplazá).
5. Si cambió el precio, actualizalo.
6. Guardar.

**Una vez por mes:** revisá todos los precios. Si te subieron la harina,
actualizá el precio de compra. Esto hace que el cálculo de margen siga
siendo correcto.

## Siguiente paso

→ [04-productos.md](04-productos.md) — qué vendés y a qué precio.
