# 06 — Clientes

> **Qué es:** la lista de clientes que compran en tu panadería. La app
> les asigna puntos automáticamente por cada compra, y muestra un
> ranking de los mejores clientes.

## Cómo llegar

**Clientes** en la barra superior.

![Listado de Clientes.](screenshots/17-clientes.png)

## Tu rutina diaria con clientes

**No necesitás cargar clientes manualmente.** La app los crea sola:

1. Cuando registrás una venta en
   [Ventas](02-ventas.md), escribís el teléfono del cliente en el campo
   "Cliente (teléfono)".
2. La app crea automáticamente el cliente con ese teléfono.
3. A partir de la segunda compra, empieza a sumar puntos.

> **Tip:** en la panadería, basta con pedir el teléfono al cliente y
> escribirlo en la venta. No necesitás nombre completo.

### Crear un cliente desde la app (opcional)

Si querés cargar un cliente **antes** de la primera venta — por ejemplo,
para abrir un pedido anticipado o para anotar dirección y nombre de
antemano — andá a **Clientes → Nuevo cliente** (botón "+" arriba a la
derecha). Te deja completar:

- Nombre y apellido
- Teléfono (formato Paraguay: `+5959XX XXXXXX`)
- Dirección y notas

Si el teléfono ya existe, la app **actualiza** al cliente en lugar de
crear uno duplicado — útil si cambia de dirección o nombre.

### Ver zonas horarias del cliente

Cuando entrás al perfil de un cliente (pestaña "Historial"), abajo del
listado de compras vas a ver un desglose por **zona horaria** (tz). Por
ejemplo:

```
🇵🇾 Asunción       47 compras · 1.234.000 Gs.
🇦🇷 Buenos Aires    3 compras ·   45.000 Gs.
```

Sirve para dos cosas:

1. **Multi-sucursal:** saber en qué zona compra más cada cliente antes de
   abrir un local nuevo.
2. **Fraud-spotting:** si un cliente de repente compra desde una tz que
   nunca usó (y se queja de puntos faltantes), es señal de que alguien
   usó su teléfono. Anotalo y avisá a Iván.

## Programa de puntos

La regla es: **1 punto por cada 1.000 Gs. gastados**, y **cada punto vale
1.000 Gs. de descuento**.

Ejemplo:

| Compra | Gastado | Puntos ganados |
|---|---|---|
| Docena medialunas (25.000 Gs.) | 25.000 | 25 puntos |
| Torta mediana (60.000 Gs.) | 60.000 | 60 puntos |
| 5 medialunas + 1 café (30.000 Gs.) | 30.000 | 30 puntos |

Después de 100 puntos acumulados (100.000 Gs. gastados), el cliente
puede canjear 100.000 Gs. de descuento en su próxima compra.

**Cómo aplicar el descuento:**

Cuando registrás una venta para ese cliente, escribí el descuento en
guaraníes. La app valida que el cliente tenga suficientes puntos. Si
no los tiene, no te deja aplicar el descuento.

## Niveles (tiers)

Los clientes suben de nivel según lo que gastaron en total:

| Nivel | Acumulado | Color en la app |
|---|---|---|
| **Bronce** | < 100.000 Gs. | Sin badge |
| **Plata** | 100.000 - 500.000 Gs. | Plateado |
| **Oro** | 500.000 - 1.500.000 Gs. | Dorado |
| **Platino** | > 1.500.000 Gs. | Platino |

Los niveles son solo informativos — no dan descuentos automáticos.

## Ver un cliente

Toca el nombre del cliente en la tabla. Te lleva a su perfil, donde
ves:

- Total gastado en la panadería.
- Cuántas compras hizo.
- Fecha de la última compra.
- Lista completa de todas sus compras.
- Sus puntos acumulados.

## Buscar un cliente

Arriba de la tabla hay una barra de búsqueda. Escribí parte del nombre
o el teléfono. También podés filtrar por nivel.

## Tu día a día con clientes

**Al cobrar a un cliente conocido:**

1. Pedíle su teléfono.
2. Buscá el teléfono en la venta.
3. Si quiere gastar puntos, calculá: "tiene X puntos, puede descontar X
   mil Gs." y aplicá el descuento manualmente.

**Al final del día:**

No hay una rutina diaria específica para clientes. La app registra
todo automáticamente cuando cargás ventas con teléfono.

## Siguiente paso

→ [08-merma.md](08-merma.md) — cómo registrar desperdicio.
