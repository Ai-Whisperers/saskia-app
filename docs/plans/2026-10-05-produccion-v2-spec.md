# Producción v2 — spec (Fase 0)

**Date:** 2026-10-05
**Author:** Iván via Hermes (Fase 0)
**Status:** Aprobado — bloqueando implementación Fase 1
**Predecessor:** `docs/plans/2026-08-31-rms-fase-1-dev-plan.md`, `docs/operations/2026-09-fase-1-specs.md`

## Resumen ejecutivo

Hoy, `/produccion` mezcla 3 conceptos en 1 columna (`qty_to_produce`): lo que el sistema
sugiere, lo que la operadora decide, y el resultado final — sin separación visible. Los
pedidos (`PedidoLine.qty`) son un panel lateral decorativo, **no entran al cálculo del
plan**. La operadora no tiene forma de "cerrar el turno" formalmente: `production_completion`
es editable para siempre, sin justificación de ceros, sin audit del plan.

**Fase 0 → Fase 1** (esta entrega) ataca solo el primer problema:
**separar demanda y plan en columnas distintas, y hacer que la demanda sume pedidos confirmados**.
El botón "cerrar turno" y el audit del plan van a Fase 2.

## Decisiones bloqueadas (de la conversación con Iván)

| # | Decisión | Resolución |
|---|---|---|
| 1 | ¿Fase 0 spec primero, o directo a Fase 1? | **Spec primero (esta entrega)** |
| 2 | `production_scheduler.py` ¿deprecar o portar features? | **Deprecarlo**. Las features que valen la pena (DOW multiplier 12w) **ya están portadas** a `production.py.forecast_sales()` desde oct 01 (B2). El resto del scheduler no se usa fuera de `insights.production_tomorrow` (que es solo `/inicio`). Migrar `/inicio` para usar `production.py` en una fase posterior (Fase 5). Por ahora se deprecó con un `DeprecationWarning` en la cabecera del módulo. |
| 3 | Pedidos `pending` ¿cuentan al plan? | **Sí**, cuentan. Criterio: `Pedido.status IN ('pending', 'confirmed', 'ready')` → suma `PedidoLine.qty` por `product_id`. Justificación: si un cliente pidió algo y no se lo cancelaron, el negocio ya se comprometió. Mostrar `pending` con un badge de "riesgo" (color diferente a `confirmed`/`ready`) para que la cocinera vea que no es compromiso firme. |
| 4 | Cierre de turno ¿por día o por producto? | **Por producto con total del día actualizado**. La cocinera marca cada producto, ve el total del día en tiempo real, y al final un solo botón "Cerrar turno" bloquea las 15+ filas. **Fase 2** — no en esta entrega. |
| 5 | Justificación de ceros ¿obligatoria u opcional? | **Opcional**. El audit log captura quién cerró y cuándo; la justificación se guarda si se tipea, pero no se requiere. **Fase 2**. |
| 6 | UI v2 ¿flag, rol, o cutover? | **`?ui=v2` query param** (default `v1` durante 1 sprint, después default `v2` y `v1` se borra). En esta Fase 1 entregamos **detrás del flag** pero solo el **backend** (servicio + migración + wire en el router). El template nuevo es Fase 2. |
| 7 | Mobile | **Ignorar**. Misma grilla desktop. |

## Alcance de la Fase 1 (esta entrega)

### 1.1 Nueva tabla `production_demand_snapshot`

Una fila por `(for_date, product_id)` que cachea la composición de la demanda.
Se recalcula **on-read** (cada vez que `/produccion?for_date=X` carga) — sin
triggers, sin cache distribuido, sin TTL. La query que la llena es barata
(1 SELECT a `pedido`+`pedido_line` para esa fecha).

```sql
CREATE TABLE production_demand_snapshot (
    for_date DATE NOT NULL,
    product_id INTEGER NOT NULL REFERENCES product(id),
    qty_forecast NUMERIC(12,2) NOT NULL DEFAULT 0,
    qty_pedidos NUMERIC(12,2) NOT NULL DEFAULT 0,
    qty_pedidos_confirmed NUMERIC(12,2) NOT NULL DEFAULT 0,  -- subset of qty_pedidos (status in confirmed|ready)
    qty_evento NUMERIC(12,2) NOT NULL DEFAULT 0,
    qty_total NUMERIC(12,2) NOT NULL DEFAULT 0,
    confidence_pct INTEGER NOT NULL DEFAULT 0,
    source TEXT NOT NULL,  -- 'computed' | 'closed' | 'manual'
    computed_at TIMESTAMP NOT NULL,
    PRIMARY KEY (for_date, product_id)
);
```

**Por qué `qty_pedidos` y `qty_pedidos_confirmed` por separado:** porque la decisión
#3 dice "todos cuentan", pero la UI necesita diferenciar visualmente.
`qty_pedidos` = `pending + confirmed + ready`. `qty_pedidos_confirmed` = `confirmed + ready`.
La diferencia = pedidos que aún no están confirmados = "riesgo".

### 1.2 Nueva tabla `production_plan_audit`

Log append-only de cambios al PLAN (no a la demanda, no al completion).
Cada POST que cambia el plan (`/override`, `/override-bulk`, `/template`,
`/template/fork-week`, `/shift-execute` cuando es un cambio material, `/ad-hoc`,
`/ad-hoc/bulk`) deja una fila.

```sql
CREATE TABLE production_plan_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    for_date DATE NOT NULL,
    product_id INTEGER NOT NULL REFERENCES product(id),
    old_qty NUMERIC(12,2),
    new_qty NUMERIC(12,2) NOT NULL,
    change_source TEXT NOT NULL,  -- 'template' | 'override' | 'manual_form' | 'adhoc' | 'bulk' | 'fork_week' | 'shift_execute'
    changed_by VARCHAR(64),
    changed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);
CREATE INDEX ix_production_plan_audit_date ON production_plan_audit (for_date);
CREATE INDEX ix_production_plan_audit_product ON production_plan_audit (product_id);
```

### 1.3 `production_completion.status`

Agregar columna `status` para la Fase 2 (cierre de turno). La dejamos en la
misma migración 102 para no romper el patrón "un PR = una migración".

```sql
ALTER TABLE production_completion
    ADD COLUMN status TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'done', 'cancelled'));
ALTER TABLE production_completion
    ADD COLUMN closure_notes TEXT;
```

**`status='open'`** es el default. La migración backfillea a `'open'` para
filas existentes (idempotente — el `DEFAULT 'open'` lo hace solo).

### 1.4 Nuevo módulo `app/rms/production_demand.py`

API pública:

```python
@dataclass(frozen=True)
class DemandRow:
    product_id: int
    product_name: str
    qty_forecast: float  # de production.forecast_sales() (existente, sin cambios)
    qty_pedidos: float  # suma PedidoLine.qty, status in (pending, confirmed, ready)
    qty_pedidos_confirmed: float  # suma, status in (confirmed, ready)
    qty_evento: float  # (multiplier - 1.0) * qty_forecast
    qty_total: float  # qty_forecast * seasonal_multiplier + qty_pedidos
    confidence_pct: int  # de production._forecast_confidence() (existente)
    source: str  # 'computed' | 'closed' | 'manual'
    computed_at: datetime


def get_demand(
    session: Session,
    *,
    for_date: date,
    use_dow_forecast: bool = False,  # para /manana
) -> dict[int, DemandRow]:
    """Return {product_id: DemandRow} for for_date.

    On-read cache: writes to production_demand_snapshot, reads back if
    computed_at < 5 min ago AND no pedido changed since. For Fase 1, we
    skip the dirty-check and just always recompute (cheap query).
    """


def persist_plan_audit(
    session: Session,
    *,
    for_date: date,
    product_id: int,
    old_qty: float | None,
    new_qty: float,
    change_source: str,
    changed_by: str | None,
    notes: str | None = None,
) -> None:
    """Append a row to production_plan_audit. Caller commits."""
```

**Por qué dataclass frozen:** consistencia con el resto del módulo
(`ProductionRow` en `production.py` no es frozen, pero los nuevos sí lo son
porque no mutamos después de calcular). Decisión consciente: si te molesta
la inconsistencia, lo cambio en revisión.

### 1.5 Wire en el router `/produccion` (día)

Detrás de `?ui=v2`, la vista día **suma** `get_demand()` al `plan_rows_view` y
agrega estos campos al dict de cada fila:

```python
{
    ...campos existentes (qty_to_produce, completed_qty, pending_pedido_qty, ...)...,
    "qty_demand_total": ...,        # qty_total de DemandRow
    "qty_demand_pedidos": ...,      # qty_pedidos
    "qty_demand_pedidos_pending": ...,  # qty_pedidos - qty_pedidos_confirmed
    "qty_demand_forecast": ...,     # qty_forecast * seasonal_multiplier
    "confidence_pct": ...,          # de DemandRow (override del de ProductionRow si está)
}
```

**El template NO cambia en esta Fase 1.** Solo el router populará los nuevos
campos. La Fase 2 los renderea en la grilla 4-col. Esto nos permite merge el
backend con confianza y verificar que los números cuadran antes de tocar la UI.

### 1.6 Wire de audit

En cada POST existente, agregar 1 línea `persist_plan_audit(...)` antes del
`session.commit()`. **Sin cambiar el comportamiento de los endpoints** — solo
agregar el log.

Endpoints a wirar:
- `POST /produccion/override` (single row)
- `POST /produccion/override-bulk` (N rows en loop)
- `POST /produccion/template` (single row)
- `POST /produccion/template/fork-week` (N rows en loop)
- `POST /produccion/shift-execute` (N rows, en loop)
- `POST /produccion/ad-hoc` (single row)
- `POST /produccion/ad-hoc/bulk` (N rows en loop)

**No wirar:** `POST /produccion/closed` (es sobre `production_closed_day`, no
sobre el plan).

### 1.7 `production_scheduler.py` — deprecation warning

Agregar al inicio del archivo:

```python
import warnings

warnings.warn(
    "app.rms.production_scheduler is deprecated; use app.rms.production "
    "(plan_production) and app.rms.demand_freshness (forecast_demand) instead. "
    "Will be removed in 2026-Q1.",
    DeprecationWarning,
    stacklevel=2,
)
```

**No tocar** las funciones existentes. Solo el warning. La migración a Fase 5
(eliminación) es trabajo separado.

## Out of scope (Fase 2+)

- ❌ Template `produccion.html` con grilla 4-col → **Fase 2**
- ❌ Endpoint `POST /produccion/close-day` y botón "Cerrar turno" → **Fase 2**
- ❌ Migración de `/inicio` para usar `production.py` en vez de `production_scheduler` → **Fase 5**
- ❌ Eliminación de `production_scheduler.py` → **Fase 5**
- ❌ Mobile dedicado → **Fase 6** (o nunca)
- ❌ Vista `/produccion/manana` con columna Pedidos → **Fase 2**
- ❌ `production_demand_snapshot` con TTL de 5 min real (dirty-check) → **Fase 3** si la perf se queja

## Compatibilidad

- Los 46 archivos de test que matchean `produccion|plan|forecast` asumen el
  comportamiento actual de `plan_production()`. **`get_demand()` es ADITIVO**,
  no modifica `plan_production()`. Los tests siguen verdes sin cambios.
- El template `produccion.html` no se toca en Fase 1. El usuario no ve NADA
  nuevo todavía — esto es solo plumbing.
- La columna `production_completion.status` se agrega con `DEFAULT 'open'`,
  así que el código existente que lee `production_completion` (sin filtrar
  por `status`) sigue viendo todas las filas como antes.
- La columna `production_completion.closure_notes` se agrega como `TEXT NULL`
  — código existente no la lee, no se rompe.

## Test plan (Fase 1)

`tests/test_production_demand.py` (~14 tests):

### Unit (sin DB)
1. `DemandRow` es frozen (no se puede mutar).
2. `_compute_demand_qty(forecast=10, pedidos=5, evento=0)` → `qty_total=15`.
3. `_compute_demand_qty(forecast=10, pedidos=5, evento=0.5)` → `qty_total=15` (evento ya está dentro de forecast multiplicado).
4. `_split_pedidos_status(pending_qty=3, confirmed_qty=5, ready_qty=2)` → `(10, 7)`.
5. Property: `qty_pedidos >= qty_pedidos_confirmed` siempre.
6. Property: `qty_total >= qty_forecast` siempre (los pedidos no restan).

### Integration (con DB, fixtures de factories)
7. `get_demand()` para fecha sin ventas ni pedidos → todas las qty en 0.
8. `get_demand()` suma 2 `PedidoLine` del mismo producto → qty_pedidos correcto.
9. `get_demand()` filtra pedidos `cancelled` y `fulfilled` → no entran.
10. `get_demand()` cuenta `pending` aparte de `confirmed`/`ready` → los 2 sub-campos correctos.
11. `persist_plan_audit()` escribe 1 fila y se puede leer back.
12. `persist_plan_audit()` en bulk (N filas) → todas se leen back.

### Wiring (router)
13. `GET /produccion?for_date=X&ui=v2` popular `qty_demand_total` y `qty_demand_pedidos` en `plan_rows_view` (test_assert en HTML no, en el response context vía `client.get` y parse del HTML para encontrar el nuevo campo — O mejor: el campo se mete en el dict pero el template no lo renderea todavía, así que solo verificamos `status < 500` y que la query no rompe).
14. `POST /produccion/override` deja 1 fila en `production_plan_audit` con `change_source='override'`.

## Esfuerzo

| Tarea | h |
|---|---|
| Migration 102 | 1.5 |
| `app/rms/production_demand.py` | 3 |
| `tests/test_production_demand.py` | 3 |
| Wire en router `/produccion` (read + 7 POSTs audit) | 2 |
| Deprecation warning en `production_scheduler.py` | 0.25 |
| CHANGELOG + smoke | 0.5 |
| **Total** | **~10h** |

## Riesgos

| Riesgo | Mitigación |
|---|---|
| `production_completion.closure_notes` choca con un `notes` existente (semántica distinta) | El modelo `ProductionCompletion` ya tiene `notes` (string, usado para tag ad-hoc). `closure_notes` es para Fase 2; el `ADD COLUMN` es aditivo, no rompe nada. Documentar en CHANGELOG. |
| Postgres DDL auto-commitea y `_bump_schema_version` queda detrás | Usar `atomic_ddl_block` para los 2 ALTER; el CREATE TABLE va aparte. Verificar que el bump queda AL FINAL de la función, después de todos los DDL. |
| `get_demand()` agrega 1 query por cada render del día | Query barata (`WHERE promised_date=:d AND status IN (...)` con índice en `promised_date`). Aceptable. Si se queja, Fase 3 agrega cache. |
| El audit en 7 endpoints duplica lógica → fácil olvidar uno en el futuro | Helper `persist_plan_audit()` con kwargs claros; un test por endpoint (no solo del helper) que verifica que se escribió. |
| `production_scheduler.py` deprecation warning se dispara en cada import del módulo, contaminando logs de tests | El warning se dispara 1 vez por proceso Python (warnings.warn no tiene default `once`). En CI los warnings se silencian. En prod se loguea. Aceptable. |
