# 13 — Reponer stock (lista de compras)

> **Qué es:** la lista automática de qué tenés que comprar, basada en
> lo que está bajo del mínimo.

## Cómo llegar

**Reponer** en la barra superior.

![Pantalla de reponer — placeholder screenshot]

## Qué muestra

Una tabla con los ingredientes que están **por debajo del mínimo**,
ordenados por urgencia:

| Columna | Qué significa |
|---|---|
| **Ingrediente** | Cuál tenés que comprar. |
| **Actual** | Cuánto te queda. |
| **Mínimo** | Por debajo de cuánto se dispara el aviso. |
| **Máximo** | Cuánto deberías tener. |
| **Sugerido** | Cuánto comprar (= máximo − actual). |
| **Urgencia** | Crítico (menos de la mitad del mínimo) / Bajo (entre mínimo y la mitad). |
| **Costo est.** | Cuánto te va a salir (precio × cantidad sugerida). |

## Cómo funciona

La app revisa cada ingrediente:

- Si **stock < mínimo**, lo incluye en la lista.
- Calcula cuánto comprar para volver al **máximo** (que es 2× el mínimo
  por default, o un valor que podés editar en Inventario).
- Ordena los más urgentes primero (los que están más cerca de 0).

## Ejemplo

Si tu stock de harina es:
- Mínimo: 5 kg
- Máximo: 20 kg
- Actual: 3 kg

La lista sugiere **comprar 17 kg de harina**, y la marca como "Bajo"
(porque 3 está entre la mitad del mínimo y el mínimo).

Si tu stock de huevos es:
- Mínimo: 12 unidades
- Máximo: 48 unidades
- Actual: 0 unidades

La lista sugiere **comprar 48 huevos**, y la marca como "Crítico"
(porque 0 es menos de la mitad del mínimo).

## Cómo usar esta pantalla

**Cada vez que vayas al super o al proveedor:**

1. Andá a Reponer.
2. Mirá la lista (ordenada por urgencia).
3. Anotá los ingredientes y las cantidades.
4. Comprá.
5. Volvé a la app y actualizá el stock en Inventario.

**Una vez por mes:**

1. Mirá si los "Costo est." se van acumulando mucho.
2. Si es así, considerá subir los precios de venta o ajustar el stock
   mínimo de los ingredientes que más se acaban.

## Tu flujo de trabajo

```
Reponer (qué falta)
   ↓
Comprar al proveedor
   ↓
Inventario → actualizar stock + precio
   ↓
Inventario listo para producción
```

## Siguiente paso

→ [14-cierre.md](14-cierre.md) — el cierre diario (tareas del final del día).
