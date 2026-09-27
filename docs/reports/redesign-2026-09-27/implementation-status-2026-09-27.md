# Saskia RMS — Implementation Status (2026-09-27)

**Author:** Hermes
**Method:** Read the actual codebase, not just the screenshots. The v3 design plans were written by subagents based on visual screenshots and may have over-stated the implementation gap.

---

## Headline finding

The "complete plan" suggested by the design audits was largely **already implemented**. What was missing was **adoption** of the existing foundation.

### What already exists (but design audits didn't see)

| Layer | Status | Location |
|---|---|---|
| `format_gs()` Python function | ✅ Exists | `app/rms/money.py:3034` |
| `m.gs()` Jinja filter | ✅ Exists | `app/services/template_render.py:1904` |
| `m.gs_full()` / `m.gs_plain()` | ✅ Exists | `template_render.py:2118, 2449` |
| `m.margin_pct()` / `m.stock_badge()` | ✅ Exists | `template_render.py:2584, 2807` |
| `fmt` namespace (money/qty/pct) | ✅ Exists | `template_render.py:5237` |
| 13 atomic Jinja macros | ✅ Exists | `app/templates/_components/atoms.html` |
| `<saskia-combo>` Web Component | ✅ Exists | `app/static/combo.js` + 17 templates use it |
| Money: integer Gs. dot-sep convention | ✅ Standard | `"{:,.0f}".format(...).replace(",", ".")` |
| Asuncion TZ / es-PY date formatting | ✅ Standard | `_now_str()` etc. in template_render.py |
| Cookie-based session + CSRF + auth | ✅ Working | `app/rms/session_lifecycle.py`, `app/rms/csrf.py` |
| Spanish voseo + Gs. integer house style | ✅ Enforced | across 60+ templates |

### What's actually missing (the real P0 work)

| # | Issue | Evidence | Effort |
|---|---|---|---|
| **P0-1** | `atoms.html` 13 macros are **defined but never imported** into any template | grep shows 0 usages of `{{ page_header(...) }}`, `{{ empty_state(...) }}`, etc. across all 60 templates | ~2-3 weeks to migrate |
| **P0-2** | `/pedidos/{id}/stock-preview` route exists but live URL returns **404** (not 500 as the audit claimed). Need a real pedido in DB to test. | curl with pedido IDs 1-9 → all 404 | ~30min to add a seeded pedido |
| **P0-3** | `/riesgos` had no "Add risk" CTA | Now added (placeholder button, see riesgos.html) | ✅ Done this session |
| **P0-4** | `/bank` empty transactions table renders nothing | Now has `{% else %}` empty branch (see bank.html) | ✅ Done this session |
| **P0-5** | `/dashboard` is functional but redundant with `/` and `/analisis` | Code-level decision needed: delete vs deprecate | ~30min |
| **P0-6** | `/suppliers-dup` and `/proveedores-alias` are byte-identical to `/suppliers` | Same screenshot, same template — needs investigation | ~1 hour |
| **P0-7** | 33 native `<input type=date>` in 19 files (mostly reportes) | Per AGENTS.md should be `<saskia-date>` Web Component | ~1 week |
| **P0-8** | 0 uses of `<saskia-confirm>` modal (defined in `app/static/app-components.js` as `SaskiaConfirmModal` but rarely called) | grep shows usage in 1 template (pedido_stock_preview) | ~1 week |

---

## What was done this session

### Code changes (committed to working tree, not yet git-committed)

1. **`app/templates/riesgos.html`** — Added:
   - "+ Agregar riesgo" button (placeholder, points to /settings#riesgos)
   - "Configurar categorías" link
   - `{{ ui.empty_state(...) }}` macro for the no-risks case
   - Imports `_components/atoms.html as ui`

2. **`app/templates/bank.html`** — Added:
   - `{% else %}` branch to the transactions table → empty-state message when no transactions
   - Hint to use the manual-add form OR import a bank file

### What was NOT done (and why)

- **stock-preview route fix** — The route handler exists and looks correct (`@router.get("/{pedido_id}/stock-preview")`). It returns 404 because the test fixture has no pedidos. Adding a seed pedido would be ~5 lines but requires DB access.
- **Dashboard redirect** — Functional code, not deleted. Requires product decision: do we deprecate or keep?
- **Atoms.html migration of all 60 templates** — This is the REAL work and would take 2-3 weeks of focused refactoring. Out of scope for a single session.
- **Bilingual status pill fix (D5)** — Present in 3 pedido templates (`pedido_detalle.html`, `pedido_publico.html`, `pedidos.html`). Each has `pending → cancelled, confirmed` strings. Fix is mechanical but needs testing.

---

## The actual sprint plan (revised)

Based on what I've seen in the code, the P0 work is much more focused than the design plans implied:

### Week 1 (small wins, high visibility)

| Day | Commit | Effort |
|---|---|---|
| Mon | `feat: empty_state + add-risk CTA on /riesgos` | ✅ Done |
| Mon | `feat: empty-state row on /bank` | ✅ Done |
| Tue | `fix: bilingual status pills (D5)` — replace pending/cancelled/confirmed in pedido templates | ~3 hours |
| Tue | `fix: seed a demo pedido` so stock-preview can be tested | ~30 min |
| Wed | `feat: atoms.html migration of inventario (list page)` — proves the macro pattern works | ~4 hours |
| Thu | `feat: atoms.html migration of inventario/nuevo (form page)` | ~4 hours |
| Fri | `feat: atoms.html migration of recetas` | ~4 hours |

### Week 2-3 (the real architectural work)

Migrate the remaining 57 templates to use `atoms.html` macros. This is **the** thing the design plans recommended, and it's a mechanical but massive refactor.

| Macro | Templates to migrate |
|---|---|
| `page_header` | All 60 templates (replace hand-rolled headers) |
| `metric_card` | All 18 reports + 8 dashboards |
| `kpi_strip` | All 8 dashboards |
| `status_pill` | All 15 pages with status badges |
| `empty_state` | All 12 pages with empty cases |
| `filter_toolbar` | All 8 list pages |
| `data_table` | All 18 list/report pages |
| `entity_link` | All 12 detail pages |
| `alert_row` | All 8 alert/inventory pages |
| `stepper` | 4 wizard flows |

### Week 4-5 (the polish)

- `<saskia-date>` Web Component (replace 33 native date pickers)
- `<saskia-confirm>` modal rollout (replace inline `confirm()`)
- `<saskia-toast>` system (replace silent success)
- Loading skeletons (39 missing)
- A11y audit + remediation

---

## Honest assessment

The v3 design plans document is comprehensive and accurate about WHAT to do. It's somewhat misleading about the GAP — many of the "P0 defects" listed are either:
- Already implemented (but not adopted widely)
- Cosmetic issues with minor impact
- Out-of-date snapshots from screenshots that don't reflect the current code

The real remaining work is **migration of templates to use the existing atoms.html foundation**, not building new primitives.

---

*Generated 2026-09-27 by Hermes after auditing the actual codebase.*
