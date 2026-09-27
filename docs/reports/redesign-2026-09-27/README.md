# Saskia RMS — Redesign Analysis (2026-09-27)

**Generated:** 2026-09-27 19:30 UTC by UX/UI principal review
**Coverage:** 60 pages analyzed (32 directly + 28 via subagents)
**Method:** 5-hat UX/UI principal analysis per page (counter, owner-finance, production-baker, new user, auditor)

---

## 📋 Files

| File | Size | What it is |
|---|---|---|
| **design-plans-2026-09-27.md** | 224 KB · 3432 lines · 8 sections | **MAIN DELIVERABLE** — Full per-page design plans + cross-cutting audits + architecture + sprint plan |
| REPORT.md | 52 KB | Per-page route → router → template → context keys reference |
| ux-audit-2026-09-27.md | 34 KB | Cross-cutting pattern audit (12 patterns, 6 defects) |
| audit-batch2-prod.md | 78 KB | Inventario, producción, pedidos, recetas family (14 pages, 5-hat each) |
| audit-batch3-reports.md | 69 KB | Compras, reportes, admin, bank, riesgos, auditoría (14 pages, 5-hat each) |
| subagent-outputs/cross-page-wishlist-consolidation.md | 37 KB | Top 30 reusable UX patterns + Top 10 architectural macros |
| subagent-outputs/qol-touches-catalog.md | 41 KB | Quality-of-life touches catalog (16 categories × 8+ items = 219 items) |
| subagent-outputs/cross-cutting-consistency-audit.md | 38 KB | App-wide consistency audit (12 dimensions, 46 pages) |

---

## 🎯 Top 3 recommendations (3-week sprint)

1. **Extract 10 atomic macros** from `/inventario` and `/inventario/nuevo` (the gold-standard pages) into `app/components/atoms.html`. Use them as canonical templates for every other list/form/report page. **Impact:** Closes ~70% of P0+P1 issues in one move.

2. **Fix the 5 broken/empty pages** (`/dashboard` → redirect, `/pedido/{id}/stock-preview` → fix 500, `/riesgos` → add CTA, `/vs-mercado` → fix data, `/bank` → add import CTA). **Effort:** ~1 week.

3. **Fix currency format drift (D3)** with a `format_gs` Jinja filter mandate + CI lint rule. **Why:** The recurring defect that violates system prompt §2 Prime Directive #5.

---

## 📚 Where to start reading

- **5 minutes:** §1 of design-plans-2026-09-27.md "Bottom line" lines
- **30 minutes:** subagent-outputs/cross-page-wishlist-consolidation.md
- **1 hour:** design-plans-2026-09-27.md end-to-end
- **2 hours:** All 4 cross-cutting files

---

## 🚀 Sprint plan (week-by-week)

See §8 of design-plans-2026-09-27.md for the day-by-day commit plan.

- **Week 1 (P0 quick wins):** Fix stock-preview 500, fix seeder Spanish names, add 3 empty-state CTAs, delete /dashboard, build saskia-date
- **Week 2 (P0 currency + confirmation):** Build format_gs filter + CI lint, server-side None vs 0, build saskia-confirm modal
- **Week 3 (P0 macros + a11y):** Build kpi_tile, status_pill, empty_state, confirm_destructive macros + a11y quick wins
