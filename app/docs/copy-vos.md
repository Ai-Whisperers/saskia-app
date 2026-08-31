# UI copy bank — Paraguayan Spanish (vos)

> **For Kiki or Saskia to fill.** This is the canonical Spanish (vos) UI string table. Every user-facing string in the app should reference this bank.
>
> **Why this matters:** the dev plan says "Spanish (vos)" but doesn't define which vos. Paraguayan Spanish ≠ Argentine Spanish ≠ Mexican Spanish. Without a copy bank approved by Saskia, every UI screen becomes a debate.
>
> **How to fill:** for each string, replace `<...>` with the actual Spanish (vos) copy Saskia would naturally read. Use Paraguayan conventions ("guardá", "tenés", "querés", period as thousands separator). Money format: "Gs. 729.167" (period thousands sep, no decimals). Date format: "31/08/2026" (DD/MM/YYYY).

---

## Buttons / actions

| English placeholder | Spanish (vos) copy | Notes |
|---|---|---|
| Save | Guardá | |
| Cancel | Cancelar | Standard |
| Delete | Eliminar | |
| Edit | Editar | Standard |
| Add new | Agregar nuevo | |
| Confirm | Confirmar | Standard |
| Back | Volver | Standard |
| Search | Buscar | Standard |
| Export | Exportar | Standard |
| Import | Importar | Standard |
| Print | Imprimir | Standard |
| Refresh | Actualizar | |
| Filter | Filtrar | Standard |
| Close | Cerrar | Standard |
| New sale | Nueva venta | |
| New ingredient | Nuevo ingrediente | |
| New recipe | Nueva receta | |
| New product | Nuevo producto | |

## Form labels

| English placeholder | Spanish (vos) copy | Notes |
|---|---|---|
| Name | Nombre | Standard |
| Description | Descripción | Standard |
| Quantity | Cantidad | Standard |
| Unit | Unidad | Standard |
| Price (Gs.) | Precio (Gs.) | Always "(Gs.)" suffix |
| Sale price | Precio de venta | |
| Purchase price | Precio de compra | |
| Date | Fecha | DD/MM/YYYY |
| Notes | Notas | Standard |
| Category | Categoría | Standard |
| Yield | Rinde | "Rinde (porciones)" explicit form |
| Yield unit | Unidad de rinde | |
| Min stock | Stock mínimo | Standard |
| Current stock | Stock actual | Standard |

## Empty states / messages

| Context | Spanish (vos) copy | Notes |
|---|---|---|
| No ingredients yet | "Todavía no cargaste ingredientes. Hacé clic en Agregar." | |
| No sales today | "Hoy todavía no registraste ventas." | |
| No recipes match | "No hay recetas que coincidan con tu búsqueda." | |
| Sale saved | "Venta registrada: 12 muffins a Gs. 86.000." | |
| Stock below minimum | "Stock bajo: <ingredient> tiene <qty> <unit>, mínimo es <min>" | |
| Stock negative | "¡Stock negativo! <ingredient> está en <qty> <unit>. Hacé un recuento." | |
| Recipe without price | "Receta sin precio de ingrediente: <recipe>. Carga los precios para ver el costo." | |
| Sale without recipe | "Venta sin receta: <product>. Asignale una receta para ver el margen." | |
| Import preview | "Vas a importar 63 ingredientes, 20 recetas, 0 líneas con errores. ¿Continuar?" | |
| Import success | "Listo. Importaste 63 ingredientes y 20 recetas. Tu backup está en <path>." | |
| Import error | "No pude importar. Tu backup anterior está en <path>. Avisame y lo restauro." | |
| Delete confirm | "¿Eliminar <thing>? Esta acción no se puede deshacer." | |
| Void sale confirm | "¿Anular esta venta? Se devuelve el stock." | |

## Errors / validation

| Context | Spanish (vos) copy | Notes |
|---|---|---|
| Required field | "Este campo es obligatorio" | Standard |
| Invalid number | "Ingresá un número válido (ej: 1234)" | |
| Invalid money | "Ingresá un monto en Gs. (ej: 729167)" | Note: no decimals, no thousands sep in input |
| Invalid unit | "Unidad no reconocida. Usá: g, kg, ml, l, und" | List canonical units |
| Insufficient permission | "Esta acción no está disponible" | (No permission system in v1; placeholder) |
| Network error | "No pude conectar. Revisá tu internet." | (App is local; rarely seen) |
| Generic error | "Algo salió mal. Avisame y lo reviso." | Operator handles |

## Status badges

| English placeholder | Spanish (vos) copy | Notes |
|---|---|---|
| Active | Activo | Standard |
| Inactive | Inactivo | Standard |
| Pending | Pendiente | Standard |
| Done | Listo | Standard |
| Draft | Borrador | Standard |
| Archived | Archivado | Standard |
| Low stock | Stock bajo | Red color |
| Out of stock | Sin stock | Red color |
| Negative stock | ¡Stock negativo! | Red color, flashing |

## Numbers in copy

| Number | Spanish (vos) copy | Notes |
|---|---|---|
| 1 unit | "1 unidad" or "1 und" | Convention: short form |
| 12 units | "12 unidades" or "12 und" | |
| 0 units | "0 unidades" or "sin stock" | Prefer "sin stock" |
| 729167 Gs. | "Gs. 729.167" | Period thousands sep |
| 17.500.000 Gs. | "Gs. 17.500.000" | Same |

## Dashboard widget titles

- "Ventas de hoy" (Today sales)
- "Ventas de la semana" (This week's sales)
- "Ventas del mes" (This month's sales)
- "Costo de lo vendido" (Cost of goods sold)
- "Margen" (Margin)
- "Ranking de productos" (Product ranking — by margin)
- "Avisos" (Alerts)

## Sale form (longer)

```
Nueva venta
Fecha: [2026-08-31 14:30] (default = ahora)
Producto: [Muffin ▾]
Cantidad: [12]
Notas: [opcional]

Vista previa:
  Stock actual de harina de trigo: 1000 g
  Después de esta venta: 970 g (stock mínimo: 500 g) ✓
  Costo estimado: Gs. 24.000
  Margen estimado: Gs. 78.000 (75%)

[Cancelar]  [Registrar venta]
```

## Empty sale preview (when product has no recipe)

```
Vista previa:
  Este producto no tiene receta asignada.
  No se puede calcular el costo ni descontar stock.

  [Asignar receta]  [Continuar de todos modos]
```

---

## When to fill this

**Before Task 3 of the dev plan starts.** That's the "Inventario + recetas CRUD (Spanish)" task, which is the first task with significant UI copy.

## How to commit

1. Save filled version at `app/docs/copy-vos.md` (or this same path in the engagement repo).
2. Saskia reviews and ticks each line: ✅ or "change to X".
3. Kiki implements per the copy bank.
4. Round 2 of dev plan review = copy review.

---

*Filled by: _____________________ (Saskia or Kiki, Paraguayan Spanish speaker)*
*Date: _____________________*
