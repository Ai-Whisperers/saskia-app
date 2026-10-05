# 17 — Lista de compras

> **Qué es:** una lista concreta de qué comprar y cuánto, generada
> automáticamente por la app según el stock actual y el plan de producción
> de los próximos días. Pensada para que la lleves al super o al proveedor
> y marques lo que conseguiste.

## Cómo llegar

**Compras → Lista de compras** en la barra lateral.

> **Tip:** la lista se genera desde **Reponer** (ver [14-reponer.md](14-reponer.md)).
> Si nunca entraste a "Reponer", la lista arranca vacía. Empezá por ahí.

![Lista de compras](screenshots/18-shopping-list.png)

## Qué muestra

La lista está **agrupada por proveedor** (casa comercial donde se compra
cada ingrediente). Cada grupo tiene:

- **Nombre del proveedor** (ej. "Casa Rica", "Feria Mayorista", "Importadora")
- **Subtotal en Gs.** — lo que te saldría comprar todo lo de ese proveedor
- Cantidad de productos distintos a reponer

Las columnas de cada fila son:

| Columna | Qué significa |
|---|---|
| **Ingrediente** | El nombre (ej. "Harina de trigo"). |
| **Cant. a comprar** | Cuánto falta para llegar al stock objetivo. |
| **Unidad** | kg / litros / unidades. |
| **Para qué** | A qué producto/receta está destinado (cliente, receta, etc.). |
| **Subtotal Gs.** | Lo que te costaría comprar esa cantidad al precio actual. |
| **Comprar** | Checkbox para tildar cuando ya lo compraste. |

Arriba de la lista hay un **total general en Gs.** — el costo estimado
de toda la lista si comprás todo.

## Tildar lo que ya compraste

A la derecha de cada fila hay un checkbox **Comprar**. Cuando lo tildás:

- La fila se marca como comprada (queda en la lista con el tilde verde)
- El stock en Inventario se actualiza automáticamente con la cantidad comprada
- Si el precio real fue distinto al estimado, te pregunta cuánto pagaste
  (para mantener los precios actualizados)

> **Tip:** si comprás TODO de un proveedor, en vez de tildar uno por
> uno, tocá **"Comprar todo"** arriba a la derecha del grupo. Es más
> rápido y evita olvidos.

## Recalcular

Si cargás nuevas ventas o cambias el plan de producción mientras estás
en la lista, tocá **"Recalcular"** arriba — la app vuelve a mirar el
stock y regenera las cantidades a comprar.

## Agregar algo que no estaba en la lista

A veces te das cuenta de que falta algo que la app no detectó
(porque no estaba en el plan de producción, o es un ingrediente nuevo).
En ese caso:

1. Tocá **"+ Cargar manualmente"** abajo de la lista
2. Buscá el ingrediente (o creá uno nuevo desde Inventario)
3. Poné la cantidad que querés comprar
4. Guardá

La fila aparece mezclada con las generadas automáticamente. Cuando la
marcás como comprada, se descuenta del stock igual que una fila normal.

## Imprimir o compartir

- **Imprimir:** botón **🖨 Imprimir** arriba a la derecha — formato
  optimizado para hoja A4.
- **WhatsApp:** botón **📱 Enviar** — abre WhatsApp Web con un mensaje
  pre-armado para mandarle al proveedor. Podés editarlo antes de enviar.

## Siguiente paso

→ [14-reponer.md](14-reponer.md) — cómo se genera esta lista desde "Reponer".
