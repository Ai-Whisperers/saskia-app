# Inicio v2 — Deep Critique & Fix Log (2026-09-25)

Source: user-provided deep critique of `/` after the P0-fix deploy, with real
data loaded. Full critique text preserved below. This file tracks what was
fixed in response.

## Fixes applied (commit pending)

| Critique item | Fix | Where |
|---|---|---|
| 3.1 KPI "↓100% abajo" divide-by-zero | current=0 now renders neutral "sin ventas en el período" — never a -100% alarm | `dashboard.py:_delta_pct` |
| 3.1 KPI hero "Gs. 0" first thing every morning | empty window shows "aún no hay ventas en este período" instead of Gs. 0 | `inicio.html` KPI trio |
| 2.2 / 3.3 two time windows presented as one | every module now labeled with its window (hoy/semana/mes/período · últimos 30 días) | `inicio.html` section headers |
| 3.6 "Costo MP 2184.5%" impossible headline | sanity clamp: revenue=0 → "sin ventas para comparar"; ratio>100 → "revisar datos de costo" | `inicio.html` Inteligencia KPI |
| 3.6 "hora pico 10.0.0" float rendering | `|int` + `%02d` format ("10:00") | `inicio.html` |
| 3.5 Avisos wall unbounded | capped at 5 per type + "… y N más — ver todos" overflow links; every line now actionable (reponer →, editar receta →, ver productos →) | `inicio.html` Avisos |
| 3.12 "Produção de mañana" Portuguese | → "Producción de mañana" | `inicio.html` |
| G-11 debug formula as "Motivo" | "velocity=0.9/day + 20% safety → target 1 units (1 batch)" → "Vendés ~0.9/día; con 20% de colchón → hacer 1 u. (1 tanda)" | `production_scheduler.py` (both call sites) |
| Footer "2026 · 2026" | already fixed in P0 batch (branding normalization) | `settings_runtime.py` |

## Not yet done (P1/P2 from the critique — tracked backlog)

- "Acciones del día" checklist block (pedidos por confirmar / producción vs
  hecho / cierre de ayer / reposiciones urgentes)
- Extract Inteligencia→Recetas-complejas (L–T) into a separate "Análisis"
  page with tabs; summary line + link on home
- Classification 2×2 quadrant chart (currently stacked bars)
- Recommendation rows deep-linkable + benefit formula + discard
- Rotation table: filter zero-consumption rows
- Freshness ("por vencer") block on home
- Quick-actions bar (Registrar venta · Nuevo pedido · Reponer)
- Collapse persistence + section anchors
- Same-weekday comparison for the KPI hero (currently vs prior day/week/month)

## Original critique (preserved verbatim, abridged headers)

Verdict: the page evolved from "unfinished" to "overstuffed" — real data and
genuinely smart modules (recomendaciones, clasificación, día-pico
consistency), but 18 undifferentiated sections, three self-contradictions
("Sin datos todavía" vs populated 30-day rankings), an impossible 2184.5%
headline, and the two things a baker needs at 5 AM (what's urgent today,
what to do next) buried.

Rule proposed: **home = estado + acciones; análisis = destino separado.**
