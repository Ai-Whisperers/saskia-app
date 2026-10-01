# Saskia RMS — Operator Cheat Sheet: Loyalty & POS

**Version:** 1.0 (2026-10-01)
**Para:** Saskia, y quien esté en caja.
**Cuando imprimir:** Primer día de uso. Después a la pared al lado del POS.

---

## ⚡ Cómo cobrar con puntos (lo importante)

1. **Identificar al cliente** — Tocá el buscador "Cliente" en `/ventas/nueva`.
   Buscá por nombre, teléfono, o RUC. Si no existe, crealo (botón "+ Nuevo").
2. **Cargá los productos** de la venta como siempre.
3. **Mirar el bloque "⭐ Canjear N puntos"**:
   - Si el cliente tiene **≥ 100 puntos**: aparece un botón grande. **UN TAP** =
     pre-rellena todos los puntos disponibles y el descuento en Gs.
   - Si tiene **< 100 puntos**: usá el input chico. Tipeá cuántos puntos
     querés canjear (se previsualiza el descuento en vivo).
4. **Confirmar**: Revisá el descuento y el total nuevo. Apretá **Confirmar venta**.
5. **Decirle al cliente** "¡Ganaste X puntos!". Aparece en el recibo.

> **Nunca** se canjea sin apretar "Confirmar venta". No es un auto-cobro.

---

## 🎁 Sugerencias automáticas (la "tarjeta 🎁 Ofertas")

Después de elegir un cliente, abajo del bloque de puntos aparecen hasta 3
tarjetas con sugerencias. **Un tap = aplicar** ese descuento.

Tipos de sugerencia:

| Nombre | Cuándo aparece | Qué hace |
|---|---|---|
| 🎂 **Cumple cerca** | 7 días antes/después del cumpleaños | 15% de descuento, sin canje de puntos |
| 🔁 **Volvé pronto** | Cliente con ≥ 21 días sin venir (BRONZE/SILVER/GOLD) | 10% / 7% / 5% de descuento (tier BRONZE/SILVER/GOLD) |
| 😴 **Puntos dormidos** | Cliente con ≥ 50 puntos que no viene hace 14+ días | Canjeá tus puntos antes de que se duerman |
| 💎 **Cliente fiel** | Cliente con ≥ 5 visitas | Sin descuento automático — solo reconocimiento |

Si la sugerencia **no se aplica** (no aparece el descuento en el campo
descuento): mirá si ya seleccionaste un producto. La sugerencia necesita
un precio actual para calcular el monto.

---

## ❌ Errores comunes

| Mensaje | Causa | Solución |
|---|---|---|
| "Para canjear puntos necesitás seleccionar un cliente" | El input quedó con un valor pero no hay cliente | Buscá y elegí un cliente. El input vuelve a 0. |
| "Puntos insuficientes: el cliente tiene X, intentás canjear Y" | El número tipeado es mayor al saldo | Tipeá un número más chico (o menos del botón grande). |
| "Descuento demasiado alto" | Puntos + descuento manual > Gs. 5.000.000 | Bajá el descuento manual o los puntos. |
| "Falta el campo de descuento" | Estás en una página sin el campo descuento (ej. dashboard) | Volvé a `/ventas/nueva`. |

---

## 🧾 Anular una venta

1. En `/ventas`, encontrá la venta. Clickeá "Anular".
2. Confirmá. **Todos** los puntos ganados en esa venta se revierten
   (el cliente vuelve a su saldo previo).
3. Si el cliente había canjeado puntos, esa fila se queda en el ledger
   (no se le "devuelven" — ya usó el descuento).

**No hay devoluciones parciales todavía.** Si el cliente devuelve 1
producto de 3, hay que anular todo y volver a cargar la venta de los
2 productos que se lleva. (Funcionalidad parcial-refund planeada.)

---

## 🏷️ Categorías de cliente (tiers)

| Tier | Cuándo | Descuento por volver |
|---|---|---|
| **🥉 BRONCE** | Primera compra | 10% después de 21+ días sin venir |
| **🥈 SILVER** | Cliente recurrente | 7% después de 30+ días sin venir |
| **🥇 GOLD** | Cliente muy leal | 5% después de 45+ días sin venir |

(Los descuentos son sobre la sugerencia "Volvé pronto". El cliente
puede además canjear puntos, lo que se acumula con el descuento.)

---

## 📞 Soporte técnico

- **App lenta o error 500:** refrescá la página. Si sigue: avisá a Iván con la
  hora y la pantalla que estabas mirando.
- **"Saldo no cuadra":** el ledger no puede estar mal (es append-only).
  Lo más común: una venta anulada. Pedile al cliente su última fecha
  de visita y verificá en su perfil.
- **Tarjeta 🎁 no aparece:** necesitás que el cliente tenga AL MENOS
  una venta registrada. Si es nuevo, no hay datos para sugerir.

---

**Imprimible A4 / Letter. Una cara. Pegar al lado del POS.**
