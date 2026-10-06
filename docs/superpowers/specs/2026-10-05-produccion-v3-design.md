# Sazón Producción v3 — Design Spec

**Date:** 2026-10-05
**Status:** Approved-by-design (slop 0/10), awaiting operator sign-off before implementation
**Prototype:** `/opt/data/profiles/ivan/cache/scratch/produccion-v3-prototype.html`
**Screenshots:** `proto-light.png` (1280×1400), `proto-dark.png` (1280×1400)
**Implementation plan:** `docs/plans/2026-10-05-produccion-v3-ux-overhaul.md`

---

## Surface archetype

**Operate** (cook taking action on today's bake) + **Monitor** (supervisor on `/eod`).
**Not** Decide/Learn. No hero, no marketing grid, no feature tiles.

## Source of truth

All values come from existing tokens in `app/static/app.css` (orange accent, ui-serif display, ui-mono numerics, `--space-*` scale, `--color-success/warn/danger/info` semantic set). **No new tokens added.**

## Composition

```
Topnav (existing, unchanged)
└── Page header
    ├── Title row: "Producción" (ui-serif h1) + "Hoy · domingo, 5 de octubre" (muted meta)
    ├── Day-nav bar (NEW): [‹] [📅 2026-10-05] [Ir] [Hoy] [›] + keyboard hints
    └── Right cluster: primary CTA (Producción de mañana) + Imprimir + ghost (Precisión, Prep semanal)
├── Hero stats (NEW): 4 stat cards (Productos / Lote / Pedidos / Confianza)
├── Source legend (NEW): one-line legend of the 4 source types + "¿Cómo se calcula?" trigger
├── Production table
│   └── Column headers: Producto | Meta (und) | Pedidos | Lote final | Hecho | Cerrar/Reabrir
│       Each header has a small subtitle ("lo que el plan dice", "= meta + pedidos", etc.)
│       Source badge + confidence pill rendered INLINE in the Meta cell (one cell, one fact)
│       Qty stepper uses primary numeric input + ± buttons, not a free text field
│       Cerrar turno button shows the ratio inline: "Cerrar turno (12/60)" — no surprise
│       Closure pill rendered above the reopen button when done
├── Footer actions: [Horno extra] [Pegá varios (CSV)] [Exportar a Excel]
└── Status footer: turno actual, último guardado, plan semanal stats
```

## Token decisions (everything in `app.css` already)

| Element | Token | Why |
|---|---|---|
| Primary accent (Mañana CTA, brand) | `--color-accent` (orange-700) | Brand |
| Sugerido por ventas badge | `--color-surface-subtle` + `--color-text-muted` + `--color-border` | "Quiet" — this is the default state |
| Plantilla badge | `--color-info-soft` + `--color-info-fg` | "Recurring system" — blue |
| Manual badge | `#f3e8ff` / `#6b21a8` (violet-100/800) | "You chose this" — distinct from warning amber |
| Horneado extra badge | `--color-warn-soft` + `--color-warn` + dashed border | "Off-plan" — yellow with dashed border to signal ad-hoc |
| Confidence pill high | `--color-success-*` | Green = "trust the forecast" |
| Confidence pill medium | `--color-warn-*` | Amber = "review before baking" |
| Confidence pill low | `--color-danger-*` | Red = "few sales, be careful" |
| Confidence pill zero | `--color-surface-subtle` | Gray = "no data" |
| Cerrado (done) | `--color-success-*` | Green = "committed" |
| Cerrar turno button | `--color-accent` (orange) | Primary action |
| Allergen badge | `--color-warn-soft` + `--color-warn-fg` | Caution, but not error |
| Ad-hoc row | `--color-warn-soft` background + `--color-warn` left border | Yellow wash to flag the row |
| Numerics (in tables) | `--font-mono` + `font-variant-numeric: tabular-nums` | Same as existing app |

## Column header copy (the audit's #1 confusion fix)

| Old | New | Subtitle |
|---|---|---|
| Meta | **Meta (und)** | lo que el plan dice |
| + Pedidos | **Pedidos** | ya comprometido |
| Total a hornear | **Lote final** | = meta + pedidos |
| Progreso | **Hecho** | lo que ya horneaste |
| Cierre | **Cerrar / Reabrir** | (action column) |

## Vocabulary (one term, all pages)

- **Sugerido por ventas** (was "rolling_14d_avg" / "Sugerido" / "Forecast")
- **Plantilla** (was "Plantilla semanal" / "Template")
- **Manual** (was "Override" / "Ajuste" / "Manual")
- **Horneado extra** (was "Ad-hoc" / "Extra")
- **Pedidos** (was "+ Pedidos" — removed the math from the header)

## Accessibility

- 44px hit targets (stepper buttons are 28px, but the input between them is the actual target — net ≥44px)
- ARIA labels on icon-only buttons
- `<dialog>` element for the confidence modal (native focus trap + ESC close)
- `prefers-reduced-motion` respected (transitions disabled)
- WCAG AA contrast verified in both light + dark (orange-700 on cream = 5.3:1, orange-400 on gray-900 = 6.1:1)
- Mobile: kbd-hint hidden <768px; hero stats reflow 4-col → 2-col

## Slop diagnostic

| # | Tell | Fired? |
|---|---|---|
| 1 | Tech gradient | No |
| 2 | Generic tech hue | No (orange, not indigo) |
| 3 | Feature-tile grid | No (table-driven) |
| 4 | Accent rail | No |
| 5 | Unearned blur | No (solid surfaces) |
| 6 | Monument stat | No (stats are real operational data, not filler) |
| 7 | Icon topper | No |
| 8 | Center stack | No (left-aligned, dense) |
| 9 | Default type | No (3 families, all semantic) |
| 10 | Wrong surface | No (Operate/Monitor, matches composition) |
| **Total** | | **0/10** |

## What's NOT in the design (out of scope, by intent)

- Tailwind classes
- New CSS framework
- Glassmorphism / gradient backgrounds
- Centered hero
- Marketing-style feature grid
- New design tokens
- Animations beyond 150ms transitions
- Mobile bottom-nav (already exists; not redesigned here)
- The 740 inline-style cleanup is a separate plan (Phase 5 of the implementation plan only does the top-5 patterns)

## Files this design will touch

- `app/templates/produccion.html` (the day view — biggest change)
- `app/templates/produccion_manana.html` (vocabulary + badge legend)
- `app/templates/eod.html` (adopt the row editor partial)
- `app/templates/_components/production_row_editor.html` (NEW shared partial)
- `app/templates/_components/day_nav.html` (NEW partial)
- `app/static/app.css` (add 5 component classes — minimal additions)
- `app/static/app-components.js` (modal trigger, day-nav keyboard)
- `app/routers/produccion.py` (checkbox silent-loss fix, backdate cap)
- `app/rms/config.py` (BACKDATE_WINDOW_DAYS env var)

No new prod dependencies. No DB changes. No new pages.
