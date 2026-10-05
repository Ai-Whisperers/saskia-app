# E2E Suite — Gap Analysis & Expansion Plan

**Date:** 2026-09-25 · **Baseline:** 73 E2E test functions (~90+ cases) / 15 files · 2,296 total tests green · 215 routes · 8 prod bugs caught so far

Method: route-by-route diff (registered routes vs E2E mentions), then thin-area grep across the whole suite, then risk-ranking of what's untested end-to-end.

## Measured gaps

### 1. Routes with NO test ANYWHERE (true dark routes — highest risk)

| Route | Risk | Why it matters |
|---|---|---|
| `POST /produccion-planner/compute` | HIGH | Production planning is a core the operator workflow; 0 tests of any kind |
| `POST /vs-mercado/{bench_id}/save` | MED | Competitive benchmarking save |
| `POST /wishlist/{item_id}/send-to-shopping-list` | MED | Cross-module handoff (wishlist → shopping) |
| `POST /productos/upload-image` | MED | File upload on prod — size/type-bomb guards untested |
| `POST /recetas/{r_id}/set-photo` | MED | Same upload class |

### 2. Multi-step journeys only unit-tested (no HTTP journey)

- **Pedido board bulk ops** (`bulk-fulfill`, `bulk-cancel`) — unit-tested but the board UI flow isn't
- **Bank reconciliation journey** (add tx → categorize → report) — 1 file
- **Reorder → purchase order journey** — partial (3 files, no full path)
- **Users admin** (create → edit → eliminate) — enforcement tested, journey not
- **forgot-password** — auth tests exist; the email/token path on prod untested
- **Settings business/fiscal roundtrip** — fiscal data (RUC, timbrado) correctness at journey level

### 3. Cross-cutting scenarios nobody tests

- **Two-user concurrent sessions** (needs 2nd real user — known block)
- **Offline → reconnect** (VPS restart mid-shift; the migration+recovery path exists but no drill simulates a kill -9 + restart with open sessions)
- **Data-scale behavior** — every test uses <10 rows; no test loads 10k sales to verify reportes/cierre don't OOM/timeout (perf smoke at 100× scale)
- **Excel FULL mode** — journey tests cover PATCH only; FULL (replace-all) untested E2E including its destructive-confirmation guard
- **Excel multi-sheet** (Recetas + Lineas + Productos + Ventas in one file) — import contract only tested on Ingredientes
- **Public pedido page (`/p/{token}`)** — enumeration tested; content/rendering not
- **Receipt (`/ventas/{id}/recibo`)** — never rendered in any test
- **Export matrix** — productos/export.csv, ventas/export.csv, pedidos/export-csv untested at content level

### 4. Observability/ops gaps

- **healthz/db, /healthz/deps, /healthz/schema** — only smoke; no "degraded state" test (e.g. corrupt DB → 503 not 500 loop)
- **Log output assertions** — no test asserts ERROR logs are NOT emitted during happy paths (log-based alerts would catch regressions earlier)
- **Post-deploy smoke script** — the manual curl ritual after each deploy (identified before, still manual; J4)

### 5. Test-quality improvements to the E2E layer itself

- **`test_negative_path_matrix`** covers 5 forms × 8 mutations; extend to export/setting routes
- **Timezone matrix** — add DST-transition dates (Paraguay abolished DST 2024, but UTC−3/−4 boundary logic should still be pinned)
- **Migration archaeology** — upgrade path only; no *downgrade-attempt* test (boot at v54 with code at v50 → must refuse cleanly, not corrupt)
- **Property tests** (P1-P3) run at 25 examples; CI profile could afford 100+ for the stock-reconciliation property specifically
- **Snapshot-immutable property** — extend to ingredient prices in recipe snapshots (recipe cost at sale time vs current)

## Prioritized expansion (est. 18-22 h)

| P | Item | Effort | Catches |
|---|---|---|---|
| 1 | True dark routes: planner-compute, vs-mercado save, wishlist→shopping, upload-image + set-photo (incl. 10 MB bomb, wrong type, SVG-with-JS) | 3 h | 500s on prod workflows, upload attacks |
| 2 | Pedido board journey: bulk-fulfill/cancel via board UI + stock reconciliation after bulk | 2 h | Bulk-op partial failures |
| 3 | Excel FULL mode + multi-sheet journey (with destructive-confirm + auto-backup assertions) | 3 h | Data-loss class |
| 4 | Exports content matrix (4 CSV/PDF exports, seeded-data assertions) | 2 h | Empty/garbage exports |
| 5 | Receipt + public-pedido rendering (Spanish copy, amounts, token in URL only) | 1.5 h | Client-facing artifacts |
| 6 | Kill-and-restart drill (SIGKILL app mid-day → restart → data intact, sessions survive-or-clean) | 2 h | Crash corruption |
| 7 | Scale smoke: 10k sales seed → cierre/reportes/demand under time budget | 2 h | OOM/timeout on real data |
| 8 | Log-silence assertions on happy paths (caplog ERROR == 0) | 1 h | Silent regressions |
| 9 | Downgrade-refusal migration test | 1 h | Corruption class |
| 10 | Bank + reorder full journeys | 2.5 h | Money-path workflows |

## Additional considerations (beyond tests)

1. **`/healthz/migrate` is intentionally unauthenticated** (operator escape hatch) — documented, but on a public VPS this is a DoS vector (repeated migration calls). Consider requiring a header secret, or rate-limiting.
2. **seed-demo on prod** — POST is login-gated (verified) but `overwrite` Form flag deserves an E2E guard test: with real data + overwrite=1, what happens? (Currently untested.)
3. **Session-secret rotation drill** — SESSION_SECRET change on prod invalidates sessions; no test/docs cover operator runbook for rotation.
4. **Two-user E2E** — the moment a 2nd user exists: role matrix, per-user audit attribution, concurrent session isolation all become testable (G3).
5. **Backup cadence check** — cron drills restore correctness; nothing asserts a fresh backup exists <25 h old (ops alert, could be a healthz/backup-age endpoint + monitor).
