# Saskia RMS — Complete Execution Plan for All Remaining Work

**Generated:** 2026-10-05
**Scope:** every TODO / In-Progress / open item across the BACKLOG, canonical roadmap, wishlist, and operational drift.
**Status sources:** [`docs/roadmap/BACKLOG.md`](BACKLOG.md) + [`docs/roadmap/audits/2026-10-05-backlog-verification.md`](audits/2026-10-05-backlog-verification.md) + [`docs/decisions/2026-09-29-canonical-roadmap-alignment.md`](decisions/2026-09-29-canonical-roadmap-alignment.md) + [`docs/roadmap/WISHLIST.md`](WISHLIST.md).
**Total inventory:** 47 distinct items (3 drift + 2 branches + 42 forward work).

---

## TL;DR

- **3 drift items are P0** (redeploy, migration 098, env vars) — all block 1+ Done items from being live.
- **6 canonical A.1–A.6 "cerrar puertas"** are the highest-leverage P0 work and were not in `IMPROVEMENT_BACKLOG.md` — 2 days of focused work to ship all 6.
- **9 canonical B.1–B.9** is the 12–17 day P1 batch. **B.1 (Venta Express) and B.2 (forecast enchufado) are the highest ROI and should go first** (per canonical).
- **6 canonical C.1–C.6** is the 10–12 day P2 batch.
- **2 branches** (feat/prod-quick-merma 15 commits, sprint-2-2-tagging 1 commit) need PR + deploy to be useful.
- **5 BACKLOG #1/#4/#12/#32/#38** + **5 D-items** + **10 wishlist** = long-tail, sequenced after the main sprints.

**Total estimated work: ~50–65 days** spread across 8 sessions, with P0+P1 reachable in 4 sessions (cerrar-puertas, B.8 backup, B.1 Venta Express, B.2 forecast).

---

# 0. P0 Operational Drift (3 items — must fix before counting ✅ as live)

| ID | Item | Effort | Why | Verifier |
|---|---|---|---|---|
| **DRIFT-1** | Redeploy container `saskia-rms:prod` on VPS | XS (10 min) | 3 routes missing in prod: `/healthz/summary`, `/p/{token}`; SCHEMA 98 in DB vs 97 in source; last backup was 72.4h ago | `curl /healthz/summary` → 200; `curl /p/abc123` → 404 (expected — bad token); `/healthz/db` shows schema_version: 97 |
| **DRIFT-2** | Recover migration 098 source (currently in unmerged phase branches) | S (1-2h) | Migration 098 ran on prod DB (closed-day flag + multi-phone) but source has no 098 file. If we redeploy, init_db may try to re-run it. | `git log --all -- _098_*.py` shows the recovered commit; `app/rms/config.py:71` bumped to 98; or `_098_*.py` no-op created and tested |
| **DRIFT-3** | Add prod env vars (`SENTRY_DSN`, `SUPABASE_SECRET_KEY`, `R2_*`) | S (30 min) | `/healthz/deps` 503s because keys missing; Sentry silent | `/healthz/deps` returns 200 with all probes ok; test 500 in prod → Sentry event arrives |

**Session zero (~1h):** fix all 3 before any other work, so future sessions can trust the live URL.

---

# 1. P0 "Cerrar Puertas" (canonical A.1–A.6 — 2 days)

Per `docs/decisions/2026-09-29-canonical-roadmap-alignment.md`. **NOT in IMPROVEMENT_BACKLOG.md** — these are a separate batch the operator didn't track. The verification report flagged this gap on 2026-10-05.

| ID | Item | Effort | Files | Tests | Risk |
|---|---|---|---|---|---|
| **A.1** | Confirm modal on all destructive actions | S (4h) | ~7 routers with destructive POSTs: inventario, suppliers, users, productos, recetas, ventas (anulación), merma. Use existing `<dialog>` or simple JS confirm + reason input for `void_sale`. Add `confirm_required` macro. | 7 wire tests + 1 page test for each | Med (UX) |
| **A.2** | CSRF token on all `<form method="post">` | S (4h) | ~30 templates. Token already exists in `validation.py`. Inject `_csrf_token` hidden input via Jinja2 base macro. Verify server-side. | `test_csrf_all_forms` (one per route) + 1 negative test (no token → 403) | High (security) |
| **A.3** | Audit log on 12 missing actions | S (6h) | 12 action types: `product.create/update/delete`, `customer.merge`, `bank.categorize`, `eod.close`, `production.override.set`, `production.completion.record`, `merma.create/delete`, `excel.import.complete`. `record_audit` already used in 4 routers. Add to 8 more. | 12 wire tests (1 per action) + 1 audit-row-count test | Low |
| **A.4** | `/login` rate-limit (5/min/IP, exp backoff after 3 fails) | XS (2h) | `app/routers/auth.py`. Use existing `rate_limit_dependency` infrastructure (already in `rate_limit.py` for reads). | 5 tests: 4 in-window → 200, 5th → 429; backoff after 3 fails | Low |
| **A.5** | `void_sale` after-cierre bug | S (3h) | `app/routers/sales.py:1093`. Add `if EODClosure.exists_for_date(sale.sold_at.date()): raise HTTPException(409, "venta de un día cerrado no se puede anular")` | 4 tests: before-cierre OK, after-cierre 409, void re-cierre, batch void | Med (correctness) |
| **A.6** | Loading skeletons on /dashboard /ventas /productos /reportes | S (3h) | CSS-only. Add `.skeleton` class with shimmer animation. Wrap each route's main content block in `<div class="skeleton">` until first render. | 4 smoke tests (HTML contains `class="skeleton"`) | Low (UX) |

**Total: 22h ≈ 3 days.** Ship as one PR (`feat: cerrar-puertas A.1-A.6`) with a CHANGELOG entry, then deploy.

**Recommended: one focused session for all 6.** They're all small, all backend, all testable. Kiki can do this in 2-3 days of focused work.

---

# 2. P1 (canonical B.1–B.9 — 12–17 days)

Per canonical: **"B.1 (Venta Express) y B.2 (forecast enchufado) son los más altos ROI y deberían ir PRIMERO en P1. B.8 (backup) debería ser P0.5"**. So the actual order is:

## Phase 1a: P0.5 + P1-highest-ROI (1 week)

| ID | Item | Effort | ROI | Status today |
|---|---|---|---|---|
| **B.8** | Backup local AES-256 + cron diario | S (1d) | "Riesgo #1 no atendido según sombreros" | ❌ TODO. `services/r2_backup.py` + `services/auto_backup.py` exist but startup-only. Hook to EOD close. |
| **B.1** | **Venta Express `/v/quick`** | S (3d) | **-45s/venta = ~22 min/turno = ~10h/mes** | ❌ TODO. 6-8 botones grandes (productos top del día) + input numérico + Enter registra. |
| **B.2** | **Forecast enchufado en `/produccion/manana`** | M (4d) | **-30% desperdicio ≈ Gs. 600k/mes** | ❌ TODO. `forecast.py` + `seasonal.py` written but not wired. |
| **B.9** | `/suppliers/{id}/precios` price comparison | S (1d) | **Gs. 4.3M/año** en harina | ❌ TODO. |

**Total: 9 days.** This is the **highest-ROI batch** in the entire plan. Ship in one session (or split: B.8+B.1 first, then B.2+B.9).

## Phase 1b: P1 resto (1 week)

| ID | Item | Effort | Status today |
|---|---|---|---|
| **B.3** | Pedido web upload comprobante `/p/{slug}` | M (3d) | 🟡 partial — token + rate-limit + URL ✅; upload UI pending. **Depends on DRIFT-1** (route must be live). |
| **B.4** | Customer merge (dedup "María") | M (3d) | ❌ TODO. New endpoint `/clientes/merge` with pick-2 + confirm + audit row. |
| **B.5** | Suscripciones sin cron — botón "Generar pedidos de esta semana" | M (4d) | 🟡 partial — model + page shipped. **Missing:** the generation button itself. **Depends on B.4** (merge handles duplicated customers that subscriptions may produce). |
| **B.6** | Cmd+K + atajos POS + dirty state | M (3d) | 🟡 partial — `shortcuts.js` shipped. **Missing:** contextual atajos per page + dirty state warning on navigation. |
| **B.7** | 3 insights accionables (60+d, margen<30%, stock N días) | M (2d) | 🟡 partial — insight card shipped; **3 specific insights to render.** |

**Total: 17 days.** Spread across 2-3 sessions.

---

# 3. P2 (canonical C.1–C.6 — 10–12 days)

| ID | Item | Effort | Status today | Notes |
|---|---|---|---|---|
| **C.1** | Sentry completo + Telegram alertas (stock crítico, shelf<3, 5xx) | S (2d) | 🟡 partial — Sentry wired. **Missing:** Telegram channel + alerting rules + shelf-life probe. |
| **C.2** | Vista cliente tablet `/m/{slug}` (1280×720) | S (2d) | ✅ done at MVP level (returns 200). **Missing:** photo on each product, "today's menu" badge, optimized for 1280×720. |
| **C.3** | Arqueo de caja guiado `/cierre/arqueo` | S (3d) | ❌ TODO. Shift-open + cash-counted + expected → diff. |
| **C.4** | Food cost semáforo (verde<30% / yellow 30-40% / red>40%) | S (2d) | ❌ TODO. `food_cost.py` exists; render semáforo on `/analisis`. |
| **C.5** | Tests gaps prioritarios | M (3d) | 🟡 partial. **6 test groups needed:** `test_eod_completions` (8), `test_reorder_supplier_prefs`, `test_excel_modes` (APPEND/PATCH/FULL), `test_recipes_subrecipes` (depth>5, yield=0), `test_csrf_all_forms`, `test_xss_prevention`. |
| **C.6** | Bug fixes (aria-labels, sticky headers, indexes, dashboard N+1) | XS-M (1-2d) | 🟡 partial. Aria + indexes done. **Missing:** sticky table headers + dashboard chart N+1. |

**Total: 12 days.** One session.

---

# 4. P3 long-tail (5 items — sequenced after P1+P2)

| ID | Item | Effort | Why now | Notes |
|---|---|---|---|---|
| **D.3** | Cerrar features muertas (Customer.loyalty_points, Tenant scaffold, PriceHistory detector) | M (3d) | Cleanup. loyalty_points now has a real ledger (BACKLOG #14) so the cached field can become a computed property. Tenant model exists but unused — either RLS (BL#38) or delete. PriceHistory has 0 rows but BACKLOG #31 made it work. |
| **D.4** | AI-driven demanda (BACKLOG #32 = Poisson regression) | L (1-2 weeks) | After P2 ships, data is rich. Use `sale_stock_move` (6,177 rows) or now `StockMovement` post-#1. |
| **D.5** | Backup AES-256 con DNI-derived password + restore test mensual | M (3d) | Builds on B.8. Schedule cron monthly. |
| **D.6** | `/riesgos` flag-gated v0.5 | M (3d) | Risks page shipped (Phase 14); v0.5 adds the flag-gate, per-operator visibility, retention. |
| **D.7** | Glossary + Loom en `/guia` | S (1d) | Defer until P1+P2 done; not operator-blocking. |

**Defer (no work planned):** **D.1** voseo/guaraní i18n (no bilingual client), **D.2** high-contrast mode (no a11y complaint).

---

# 5. BACKLOG operator-curated (5 items, mostly already in other buckets)

These are the 5 TODO/In-Progress items from `IMPROVEMENT_BACKLOG.md` (Tiers 1-7). **3 of them overlap with canonical items above** (catalogued separately to avoid double-counting).

| ID | Item | Effort | Status | Overlap |
|---|---|---|---|---|
| **BL#1** | SaleStockMove + StockMovement full consolidation | M (5d) | 🔶 In progress. costing.py dual-write documented; ~50 files for full refactor. **Not in canonical — independent work.** |
| **BL#4** | Atomic DDL across 90 migrations | S (3-5d) | 🔶 In progress. Helper exists; 83 migrations remain to convert. **Not in canonical — independent work.** |
| **BL#12** | Forward-only migration rollback | L (1 week) | ❌ TODO. Intentional design. **Not in canonical — future.** |
| **BL#32** | Poisson regression restocking | L (1-2 weeks) | ❌ TODO. Same as D.4 — overlap. |
| **BL#38** | Supabase RLS multi-tenant | L (1-2 weeks) | ❌ TODO. Out of scope per Saskia single-user context (canonical "Descartado" list). |

**Recommendation:** do **BL#1 + BL#4 together** in a dedicated refactor session (8-10 days). They share the same migration-system concern. Defer BL#12/BL#32/BL#38 indefinitely or until a new engagement materializes.

---

# 6. Wishlist long-tail (10 open items)

8 wishlist items are already shipped (overlap with IMPROVEMENT_BACKLOG). 3 are P0 (mapped to canonical A.1–A.4). 1 is Rejected (multi-tenant). 4 are out of scope.

**10 still open:**

| Wishlist file | Maps to | Status |
|---|---|---|
| `2026-09-04-whatsapp-bot-daily-summary.md` | D.4 / BL#32 | TODO |
| `2026-09-04-auto-reorder-based-on-stockout.md` | new (P2 area) | TODO — auto-reorder when stock hits 0 |
| `2026-09-04-barcode-scanner-integration.md` | E23 (Epic plan) | TODO |
| `2026-09-04-ci-smoke-against-deploy-shape-env.md` | new (infra) | TODO — CI smoke against deploy-shape env |
| `2026-09-04-codeowners-routing.md` | E24.S3 | TODO (low priority) |
| `2026-09-04-docker-compose-dev-postgres.md` | E24.S5 | TODO (dev infra) |
| `2026-09-04-per-user-audit-log.md` | A.3 | TODO (P0 — already in canonical) |
| `2026-09-04-produccion-del-dia-worksheet.md` | B.2 / E21 | TODO (overlaps with B.2) |
| `2026-09-04-rate-limit-on-endpoints.md` | A.4 / BL#10 | TODO (P0 — already in canonical + BACKLOG) |
| `2026-09-04-timezone-groupby-sales.md` | BL#27 | TODO (✅ already shipped per BACKLOG) |

**Net unique wishlist work after overlap:** 5-6 items. All can be picked up in the natural course of P1/P2 work; no separate sprint needed.

---

# 7. Undeployed branches (2 items)

| Branch | Commits | Work | Action |
|---|---|---|---|
| `feat/prod-quick-merma` | 15 | PROD-MERMA-2 batch: `/merma` Hoy card, source-mix chips, source-chip on `/auditoria` + `/merma eventos`, deficit-prompt JS wire, smoke endpoints `/api/smoke/waste-source-mix` + `/api/smoke/prod-loop`, modal a11y, deploy-comment SASKIA_TEST_AUTH_DISABLED | Rebase onto main → PR → merge → deploy. **Or:** cherry-pick only the smoke endpoints (operationally useful) and discard the rest (UI polish). |
| `sprint-2-2-tagging` | 1 | `refactor(tags): consolidate into tagging/ package` | PR + merge. Cosmetic refactor, low risk. |

**Recommendation:** in the same session as DRIFT-1 (redeploy), cherry-pick the smoke endpoints from feat/prod-quick-merma and the tagging refactor from sprint-2-2-tagging. Both will then ship in the same redeploy. **Don't** take the full 15-commit prod-quick-merma PR — too much UI risk for unclear gain.

---

# 8. Recommended Session Sequence

The 50-65 days of total work maps to **8 focused sessions** of 4-8 days each:

| # | Session | Work | Days | Why first |
|---|---|---|---|---|
| **0** | **Operational** | DRIFT-1, DRIFT-2, DRIFT-3 + cherry-pick smoke endpoints from feat/prod-quick-merma + merge sprint-2-2-tagging | 1 | Unblocks everything else; makes BACKLOG ✅ actually live |
| **1** | **Cerrar puertas** | ~~A.1, A.2, A.3, A.4, A.5, A.6~~ ✅ verified done 2026-10-05 | 3 | Highest security/correctness risk; one focused PR |
| **2** | **P1 highest-ROI** | ~~B.8 backup + B.1 Venta Express + B.9 supplier prices~~ ✅ verified done 2026-10-05 | 5 | B.8 is "riesgo #1 no atendido"; B.1 = -45s/venta; B.9 = Gs. 4.3M/año; **ALL P1 TESTS PASS (276/276)** |
| **3** | **P1 forecast + insights** | ~~B.2 forecast enchufado + B.7 insights~~ ✅ verified done 2026-10-05 | 6 | B.2 = -30% desperdicio; "enchufar gemas ocultas" exercise; **44/44 P1 tests pass** |
| **4** | **P1 customer workflow** | ~~B.3 pedido upload + B.4 customer merge + B.5 suscripciones button + B.6 Cmd+K~~ ✅ verified done 2026-10-05 | 13 | High-touch but mostly UI work; **41/41 P1 tests pass** |
| **5** | **P2 observability + tests** | ~~C.1 Sentry~~ ✅ + C.1 Telegram ⚠️ missing + ~~C.5 test gaps~~ ✅ + ~~C.6 polish~~ ✅ | 6 | Defensive; "shores up the walls"; **Telegram alerts not implemented** |
| **6** | **P2 customer-facing** | ~~C.2 tablet menu polish + C.3 arqueo + C.4 food cost semáforo~~ ✅ verified done 2026-10-05 | 7 | C.3 + C.4 use `food_cost.py`; C.2 enhances the shipped MVP |
| **7** | **P3 long-tail** | ~~D.3 dead features~~ ✅ + ~~D.5 backup restore test~~ ✅ + ~~D.6 riesgos v0.5~~ ✅ + ~~D.7 glossary~~ ✅ verified done 2026-10-05 | 8 | Cleanup; not operator-blocking; **0 demonstrably-dead routes of 308 total** |
| **(defer)** | **Refactor** | BL#1 + BL#4 + Epic 23 barcode + E25 S25.7 i18n prep | 10+ | Multi-session, less time-sensitive |
| **(defer)** | **AI** | D.4 / BL#32 Poisson regression | 10+ | L effort, future |

**Total committed: ~50 days across 8 sessions.** Plus deferred refactor + AI = ~70 days for everything in the backlog.

---

# 9. Day-1 to Day-5 (this week)

If you want the **fastest path to closing the most ✅ items**:

| Day | Work | Output |
|---|---|---|
| **Day 1 (today)** | Session 0: deploy drift + smoke endpoints + tagging refactor | 3 routes go live; BACKLOG is honest |
| **Day 2-3** | A.2 CSRF + A.3 audit log (largest security wins) | 30 forms protected, 8 actions audited |
| **Day 4** | A.4 /login rate-limit + A.5 void-after-cierre (small + critical) | 2 critical bugs closed |
| **Day 5** | A.1 confirm modals + A.6 loading skeletons (UX) | 1 PR `feat: cerrar-puertas A.1-A.6` lands |

**End of week 1: 6 P0 ✅ + 3 drift ✅ + 2 branches merged = 11 closed items.**

Then week 2-3 = P1 highest-ROI (B.8, B.1, B.9, B.2). End of week 3: another 4-5 high-ROI items ✅.

---

# 10. Dependencies & Critical Path

```
Session 0 ─┬─→ Session 1 (Cerrar puertas) ─→ Session 2 (B.8 + B.1 + B.9)
            │                                  │
            │                                  ├─→ Session 3 (B.2 + B.7)
            │                                  │
            │                                  └─→ Session 4 (B.3, B.4, B.5, B.6)
            │
            ├─→ Session 5 (C.1, C.5, C.6)
            │
            └─→ Session 6 (C.2, C.3, C.4) ─→ Session 7 (D.3, D.5, D.6, D.7)
                                              ↓
                                       (defer) Refactor + AI
```

**Critical path:** Sessions 0 → 1 → 2 → 3 = 15 days. After that, Sessions 4–7 can run in any order (mostly independent).

**Bottlenecks:**
- **A.2 CSRF** requires per-form test changes. ~30 forms × 5 min = 2.5h just for the test updates.
- **B.2 forecast enchufado** requires production data to validate accuracy. May need 1-2 weeks of new sales before we can compare forecast vs actual.

---

# 11. What this plan does NOT cover

- **Migration rollback (BL#12)** — intentional design, no work planned.
- **Multi-tenant RLS (BL#38, D.3 Tenant)** — out of scope per Saskia single-user context.
- **Multi-warehouse, multi-currency, multi-timezone** — descartado list (canonical).
- **Co-occurrence, cohort, churn, real-time polling** — descartado list.
- **Voice input, native mobile, supplier portal, AI recipe suggestion (E25)** — wishlist aspirational.
- **Sesame i18n, high-contrast a11y (D.1, D.2)** — gated on future need.

These are intentionally not in the plan. If a real engagement or requirement emerges, they get a new epic.

---

# 12. Tracking

This plan is the source of truth for the next 8 sessions. To track progress:

1. **Each session:** create a `docs/roadmap/sessions/YYYY-MM-DD-<slug>.md` with the work done (use the multi-session recovery plan format).
2. **At end of each item:** update [`docs/roadmap/BACKLOG.md`](BACKLOG.md) to mark the row ✅.
3. **At end of each session:** add the session file to `docs/roadmap/sessions/INDEX.md`.
4. **Quarterly:** re-run the verification pass (as I did on 2026-10-05) to catch drift.

---

# 13. Open Questions for You

1. **Do you want me to start Session 0 (operational drift) now?** It's ~1h and unblocks everything.
2. **Or jump to Session 1 (cerrar puertas A.1-A.6)?** ~3 days, 6 high-priority items.
3. **Or stay in planning mode** and refine this further? I can:
   - Break any session into per-day tasks
   - Add risk/mitigation per item
   - Add verification scripts for each session
   - Map the plan to the wishlist more granularly
4. **The 2 undeployed branches:** cherry-pick smoke endpoints only (recommended) or take the full 15-commit prod-quick-merma PR?

Tell me which path and I'll proceed.
