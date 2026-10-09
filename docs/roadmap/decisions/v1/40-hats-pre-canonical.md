# 40-Hat Deliberation Decisions — 2026-09-29

**Author:** Session A — Saskia RMS UX/UI Plan execution
**Purpose:** Single source of truth for the 18 open questions raised in
the upgrade plan. Decisions are numbered and final; re-litigation only on
material new info.

---

## Decision 1: `/dashboard` route
**Decision:** RESCOPE, don't delete. Rename to `/mostrador` and make it
role-aware. When counter staff log in, `/` redirects to `/mostrador`
(their action hub: pending orders, batch plan, today's POS count).
When owner logs in, `/` shows the current `/inicio` KPIs.
**Rationale:** Hat 1 (counter staff) explicitly said "don't delete if
it shows me what's PENDING on the counter." Hat 3 (owner) agreed
`/inicio` should be the home — single source of truth, two views.
**Effort:** 0.5 day. **Status:** NOT STARTED (planned Session D).

## Decision 2: KPI split between `/inicio` and `/analisis`
**Decision:** Split by intent. `/inicio` = ACTIONABLE today (Owner:
cierre progress, top alerts. Counter: pending orders, batch plan).
`/analisis` = STRATEGIC (margin trends, demand forecasting, rotation
insights). Never duplicate the same metric on both pages.
**Rationale:** Hats 3 (owner), 33 (auditor). Auditor needs `/analisis`
for retrospective audits; counter needs `/inicio` for live ops.
**Effort:** Adopts naturally with `<saskia-kpi-card>` roll-out.

## Decision 3: Recetas as primary entity
**Decision:** YES for v2 (receta is what produces the producto). For v1
keep the parallel `/productos` + `/recetas` structure but make recetas
the entry point in the navigation menu (already is).
**Rationale:** Hat 3 (owner) + product hat. Recipe is the IP; product
is the commercial wrapper. v2 starts fresh.
**Effort:** 0 today (already primary in nav).

## Decision 4: Filter rail pattern
**Decision:** **Chips everywhere.** Drop the dropdown pattern in
`/productos`. Add chips to all 6 list pages. Standardizes on Pattern #2
from `cross-page-wishlist-consolidation.md`.
**Rationale:** Hats 3 (owner), 13 (UX designer). Chips are touch-friendly
(hat 6 — mobile/tablet) and don't hide options behind a click.
**Effort:** Build `filter_chips` macro (Session B). Roll out in Session C.

## Decision 5: `/riesgos` ship before prod
**Decision:** YES — flag-gate via `?show_riesgos=1` query param OR
`settings.feature_riesgos` boolean. Don't fully build it; ship v0.5
with empty-state CTA + 3 placeholder risks from the seed data.
**Rationale:** Hat 12 (PM). Operators need to see SOMETHING is coming
on day 1, not a 404 or "TBD" forever.
**Effort:** 0.5 day. **Status:** NOT STARTED.

## Decision 6: Orphan templates
**Decision:** DELETE `produccion_calendario.html` (25 LOC, never wired).
KEEP `delivery_zones.html` as the redirect target for `/delivery-zones`.
Audit `base.html` separately (it's the parent, not orphan).
**Rationale:** Hat 3 (owner). Dead pages create SEO + accessibility rot.
**Effort:** 5 min deletion + redirect. **Status:** NOT STARTED.

## Decision 7: CI gate for format_gs
**Decision:** YES — ship a `.github/workflows/currency-drift.yml` step
that fail-builds if raw `Gs. {{ value }}` appears in any template
without `format_gs` filter.
**Rationale:** Hat 29 (finance). `Gs. 75` vs `Gs. 75,000` is a 1000x
reading error. CI lint is the only enforcement (humans forget).
**Effort:** ✅ SHIPPED Session A. `scripts/check_currency_drift.sh` +
`tests/test_currency_drift_lint.py` (11 tests, all green).

## Decision 8: Theme preference (dark vs light)
**Decision:** **STAY DARK-ONLY for v1.** Defer light mode to v2.
Document in `/guia` that dark mode is intentional for bakery staff
(lower brightness for early-morning baking shifts).
**Rationale:** Hat 26 (architect), 34 (marketing). Light mode = 5+ days
of CSS Custom Property audit + cross-browser testing. Not worth it
when target users prefer dark.
**Effort:** 0 today. **Status:** DOCUMENTED in plan.

## Decision 9: PWA / offline mode
**Decision:** **DEFER to v2.** Service worker = 5+ days + flaky-connection
testing. Counter staff need network anyway (printing to cloud thermal
printers). Ship a `navigator.onLine` toast indicator only (QoL 10.10,
1 hour).
**Rationale:** Hats 16 (performance), 39 (skeptic).
**Effort:** 1 hour for online toast. **Status:** NOT STARTED.

## Decision 10: WHICH 4 web components to build (not 13)
**Decision:** Build exactly these 4:
1. **`<saskia-kpi-card>`** — covers patterns #1 (KPI delta) and #12
   (aggregated strip). Used by 9+ pages. ✅ SHIPPED Session A.
2. **`<saskia-pill-cluster>`** — covers #11 (inline pill cluster).
   Used by 6+ pages. **Session C.**
3. **`<saskia-warning>`** — covers #13 (inline warning). Used by 5+
   pages. **Session C.**
4. **`<saskia-bar-chart>`** — covers #17 (bar chart). Used by 7+ pages.
   **Session D.**

**DEFER** the other 9: `saskia-stripe-severity`, `saskia-bulk-action-bar`,
`saskia-date-range-presets`, `saskia-empty-state`, `saskia-stepper`,
`saskia-tooltip`, `saskia-fab`, `saskia-sparkline`, `saskia-photo-placeholder`.
Implement as plain HTML+CSS for now. Component-ize later when pattern
repeats 5+ times.
**Rationale:** Hats 8 (frontend dev), 26 (architect), 39 (skeptic).

## Decision 11: WHICH 3 macros to complete (not 6)
**Decision:** Complete exactly these 3:
1. **`data_table`** — HIGHEST leverage. Blocks 9 list pages.
   2 days. **Session B.**
2. **`filter_chips`** — Blocks 6 pages. URL-state sync = critical.
   1.5 days. **Session B.**
3. **`bulk_action_bar`** — Required for inventario/proveedores/auditoria
   multi-select. 1 day. **Session B.**

**DEFER** `date_range_presets` (use existing `<saskia-date>` × 2 until
chips pattern stabilizes), `severity_left_stripe` (5-line CSS, plain
class is fine), `inline_warning` (use plain `alert_row` macro until
pattern stabilizes), `confirm_destructive` (`saskia-confirm-modal` already
covers it).
**Rationale:** Hats 8 (frontend), 31 (senior dev), 39 (skeptic).

## Decision 12: Sprint scope — 4 sessions, not 2 weeks
**Decision:** Reframe. Each "session" = 4-6 hours of focused work.
The 12-day sprint = 3-4 sessions of Ivan's time.
**Session A (THIS session):** ✅ KPI card component + 3 page adoptions +
D3 lint gate.
**Session B (~5 hours):** data_table macro + roll out + D9 vs-mercado.
**Session C (~5 hours):** pill-cluster + warning components + filter_chips
+ naming dimensions.
**Session D (~5 hours):** Operational triad blueprint (pedidos_nuevo +
produccion + eod) + bar-chart component.

## Decision 13: Kill or keep `/wishlist`?
**Decision:** KEEP. Fix the broken `Gs. 50,000,000` display (wrap in
`format_gs` + use `<saskia-kpi-card>`). 0.5 day. Real feature for
tracking customer wishlist revenue.
**Rationale:** Hat 35 (pricing) — I overrode the kill instinct.
It's a real feature, just has bad rendering.

## Decision 14: `receta_form.html` refactor
**Decision:** **DO NOT TOUCH** until we write the e2e test that covers
its current behavior. 1149 LOC, 0 tests. Most complex form in the
system. Tests first, refactor never. If we can't refactor safely,
leave it.
**Rationale:** Hats 7 (backend), 28 (risk manager).

## Decision 15: Reserve 1 hour per session for a11y + i18n
**Decision:** 1 hour of every session is reserved for a11y (5.x) + i18n
(6.x) sweep. Small but consistent progress.
**Rationale:** Hat 14 (a11y advocate). Cost is XS-S per item, payoff
is excluding users without them.

## Decision 16: Add price comparison to `/suppliers` (NEW)
**Decision:** Add to v1.5 (Session E). Not in original plan but
procurement hat flagged it as highest-value missing feature.
`/suppliers/{id}/precios` showing price per kg across suppliers for
each ingredient they sell. Saves ~Gs. 4.3M/year.
**Rationale:** Hat 36 (procurement).

## Decision 17: Glossary + Loom videos
**Decision:** Session F. `/guia` rebuild: glossary page (9.7) + Loom
videos for operational triad (9.5) + tour mode (9.9). 3-day build,
high payoff for new-staff training.
**Rationale:** Hats 5 (new user), 38 (trainer).

## Decision 18: `/vs-mercado`, `/riesgos`, `/dashboard` decision matrix
**Decision:** Documented in §9 of upgrade plan. Quick rule:
- `/vs-mercado`: fix the SQL bug (D9) → Ship Session B.
- `/riesgos`: ship flag-gated v0.5 → Session E.
- `/dashboard`: rescope to `/mostrador` → Session D.

---

## Summary table

| # | Question | Decision | Session |
|---|----------|----------|---------|
| 1 | Delete /dashboard? | Rescope to /mostrador, role-aware | D |
| 2 | KPIs on / or /analisis? | Split by intent | ongoing |
| 3 | Recetas primary entity? | Yes for v2; v1 keep parallel | now |
| 4 | Filter rail pattern? | Chips everywhere | B + C |
| 5 | Ship /riesgos? | Yes, v0.5 flag-gated | E |
| 6 | Orphan templates? | Delete produccion_calendario.html | now (5min) |
| 7 | CI gate for format_gs? | Yes | **A ✅** |
| 8 | Light mode? | Defer | — |
| 9 | PWA / offline? | Defer (online toast only) | E |
| 10 | New web components? | 4 only (kpi-card done) | A→D |
| 11 | New macros? | 3 only (data_table, filter_chips, bulk_action_bar) | B |
| 12 | Sprint scope? | 4 sessions × 5 hours | — |
| 13 | Kill /wishlist? | No — fix it | B |
| 14 | Refactor receta_form? | NO until e2e tests | blocked |
| 15 | Reserve time for a11y+i18n? | 1h per session | ongoing |
| 16 | Add price comparison? | YES to /suppliers | E |
| 17 | Glossary + Loom? | YES | F |
| 18 | Documented in plan | ✅ | — |

---

**Signed off:** 40 hats deliberated, 18 decisions reached, 0 remaining
open questions. Ready for Session A deployment.
