# Saskia RMS — COMPLETE Test-Code Improvement Catalog

**Date:** 2026-09-25
**Supersedes:** the 10-item list in 2026-09-25-test-code-refactor-analysis.md
(kept for its sequencing; this is the full inventory).
**Method:** regex/metric sweeps over all 240 test files, CI config, app code,
and pyproject — every number below is measured.

## Master metric snapshot

| # | Metric | Value |
|---|---|---|
| M1 | test files (root + e2e) | 233 + 7 |
| M2 | test functions | 2,018 (+ parametrize expansion → 2,231 collected) |
| M3 | raw `session_factory()` sites | 998 |
| M4 | factory `make_*` calls | 126 |
| M5 | inline `Ingredient(name=` | 161 |
| M6 | inline `Product(name=` | 170 |
| M7 | local `_seed*`/`_make*` helpers | 49 |
| M8 | direct `client.post(` sites | 299 |
| M9 | direct `client.get(` sites | 469 |
| M10 | flows.py route paths | 6 of 191 |
| M11 | content-blind `assert status==200` | 379 |
| M12 | literal-ID (`== 1`) assumptions | ~210 |
| M13 | models with factories | 7 of 45 |
| M14 | parametrize uses | 30 |
| M15 | test docstrings | 1,450 of 2,018 |
| M16 | naive `datetime.now()` in tests | 26 |
| M17 | `date.today()` in tests | 56 |
| M18 | `sleep()` in tests | 7 |
| M19 | hardcoded URL literals | 543 |
| M20 | `except Exception` in tests | 10 |
| M21 | monkeypatch.setattr sites | 39 |
| M22 | markers used | 74 across 2,231 tests |
| M23 | conftest fixtures | 34 (509 lines) |
| M24 | skips | 11; xfail 0 |
| M25 | CI status | budget-gated, effectively manual |

---

## THE COMPLETE CATALOG

### Category A — Factories & data builders

**A1. Complete factory coverage: 38 unbuilt models.** Highest-value:
IngredientVariant (+preferred), IngredientPriceEvent, WasteLog, DeliveryZone,
User(role=), ProductionPlan/Override/Completion, Tag/TagLink, ImportBatch,
RecipePricing, PriceHistory, SaleStockMove (for hand-crafted ledger states).
*A35 tests hand-roll variants today.*

**A2. Builder composition sugar.** `make_recipe(lines=[...])` exists; add
named scenarios: `make_catalog(s)` (ingredient+recipe+product wired),
`make_sellable(s, price=...)` returning the product with stock-backed
recipe — collapses the 3-step preamble in dozens of tests.

**A3. Timestamped variants.** `make_sale(at=...)` exists; ensure EVERY
factory accepts explicit temporal kwargs (bought_at, recorded_at,
promised_date) so tests never depend on wall-clock for data shape.

**A4. Value-object builders for money.** All money in tests should go
through a `gs(n)` helper (Decimal-safe, documents intent) per AGENTS.md
money rules — currently raw ints everywhere.

**A5. Factory traits/mixins.** `make_ingredient(s, traits={"low_stock": True})`
style presets for recurring states (low stock, near-expiry, allergen-heavy,
packaging) — kills the multi-kwarg repetition at call sites.

**A6. quick_seed scenarios rebuilt on factories** (API frozen, internals
delegated) — planned in R1 but not yet done; still hand-rolls 6 helpers.

### Category B — HTTP flows

**B1. flows.py: 6 → ~30 paths.** products CRUD, customers CRUD, suppliers
CRUD, reorder/restock, EOD run, excel upload, exports, users admin.

**B2. Generic `api_crud()` for the /api/ settings cluster.** One helper
loops create/read/update/delete across the 37 JSON routes (already
prototyped inside test_settings_runtime_crud as `_crud_roundtrip` —
promote it to flows.py).

**B3. `assert_see(client, path, *needles)` helper** for the 379
content-blind asserts; standardizes content verification + gives better
failure output than `assert "x" in r.text`.

**B4. Response-object assertions.** FlowResult should carry parsed
`.json()` and `.flash` (extracted from Location query params) so tests
assert on structured outcomes, not strings.

**B5. Authenticated-vs-anonymous pairs.** A flow helper
`as_anonymous(fn)` wrapper to test the 401/redirect gate per route class
(currently only strict_auth tests it once).

**B6. Idempotency probes.** `flows.sell(idempotency_key=...)` — the
idempotency system has unit tests; no flow-level double-click simulation
(same POST twice).

### Category C — Structural / organizational

**C1. conftest split.** 509 lines/34 fixtures → extract `_lib/supabase_fake.py`,
`_lib/warnings_silencer.py`; conftest keeps only fixture declarations.

**C2. e2e/conftest.py** with the `e2e` marker registration + shared e2e
fixtures (strict_client variant for role tests later).

**C3. Test-file taxonomy.** 233 flat files with inconsistent naming
(`test_k1_`, `test_k6_`, `test_k7_`, `test_p0_`, `test_p1_`, `test_p3_`,
`test_r2_`, `test_saskia_r2_`, `test_nav_02_`). Group into subdirs or
rename with a consistent scheme when touched (not a big-bang rename —
breaks git blame).

**C4. Dead/duplicate test inventory.** Some files test the same route
twice via different eras (test_routes vs test_p1_route_coverage vs
test_smoke_all_routes). One deliberate pass to mark-or-merge duplicates.

**C5. `pytest.ini`/pyproject marker registry completeness.** `e2e` marker
not registered; add to pyproject markers list to avoid warnings.

**C6. Register a `migration` marker** for the archaeology tests so the
weekly full-sweep (all 54 versions) is selectable separately from the
sampled set.

### Category D — Assertions & verification quality

**D1. Content-blind assert sweep** (M11: 379) — fold into factory adoption.

**D2. Negative-path matrix as data.** One parametrized test per route
family: (missing required field, garbage money string, negative qty,
nonexistent FK id, oversized input). Currently ad-hoc per file.

**D3. Invariant assertions library.** Formalize what e2e asserts inline:
`invariants.stock_never_negative(s)`, `invariants.money_is_int(session)`,
`invariants.audit_covers(s, actions)`, `invariants.snapshots_immutable(...)`.
One import, reused by every scenario.

**D4. Schema-level invariants.** After flows, query sqlite_master and
assert money columns are INTEGER type (AGENTS.md rule) — catches model
drift at test time.

**D5. UI-copy invariants.** Flash messages assert Spanish-vos copy from
copy-vos.md; a fixture of approved strings prevents silent anglicization.

**D6. Error-path templates.** 404/500 pages must render branded Spanish
pages (there's a regression class here — the `branding is undefined` crash
of 2026-09). Add render-asserts for the main error codes.

### Category E — Determinism & time

**E1. Naive `datetime.now()` sweep** (M16: 26 — top: test_void_semantics 6,
test_stock_drop 6, test_r2_backup 4) → UTC-aware.

**E2. `date.today()` sweep** (M17: 56 — top: test_pedidos 14,
test_dashboard_compliance 8, test_eod_completion 7) → `freeze_asuncion`
or explicit dates. This is the midnight-flake class.

**E3. `sleep()` elimination** (M18: 7 — test_price_history 4) → explicit
timestamps; sleeps are the top CI-time waster and flake source.

**E4. Time-travel harness.** Generalize freeze_asuncion to a context
manager `frozen(date)` usable inside tests (not just fixture-time).

**E5. Timezone-matrix test for /produccion.** Parametrize across UTC
boundaries (23:30, 00:15 Asunción) — the exact window that flaked.

### Category F — Concurrency & performance

**F1. Concurrent-write scenarios per mutation family.** The 2-thread sales
test exists; add pedidos-fulfill and stock-adjust races (both mutate stock).

**F2. Connection-pool exhaustion probe.** 50 sequential requests assert no
pool growth (regression for the get_session leak class).

**F3. Per-route perf budget as data.** A parametrized slow-route detector
(route X must respond < N ms on seeded data) instead of ad-hoc perf tests.

**F4. xdist-default workflow** (`-n 4` green now; make it the documented
fast loop, serial = release gate).

### Category G — Security & auth testing

**G1. CSRF negative matrix.** Missing cookie, tampered cookie, cross-user
token — unit tests exist; drive through flows for the top-10 mutation routes.

**G2. Rate-limit flow test.** Burst 12 POSTs → assert 429s AND no partial
DB state (writes either fully applied or not at all).

**G3. Role matrix (blocked on 2nd user)** — make_user(role=) factory now,
tests when users exist.

**G4. Session-expiry mid-flow.** Expired/invalid session cookie → POST must
303 to /login, never 500 (SessionMiddleware edge).

**G5. Security-header asserts on every HTML flow** (CSP, X-Frame-Options —
middleware exists, only spot-checked today).

**G6. Public-token exposure.** pedido.public_token pages must not leak
other pedidos' data (enumeration probe: token+1, token−1).

### Category H — Data integrity & migrations

**H1. Full migration sweep marker** (weekly: all 54 versions, not sampled 9).

**H2. Postgres parity (pg-marked tests exist)** — run them in CI when
budget resolves; today they skip locally without Docker.

**H3. FK-integrity sweep.** After a full e2e day: PRAGMA foreign_key_check
on the DB — zero violations expected, one test.

**H4. Backup roundtrip for the CRON format.** The nightly backup is a raw
sqlite dump (rms-*.sqlite.gz), not the JSON archive the drill tests. Add a
restore drill for the sqlite-file format too (the actual artifact ops has).

**H5. Import-batch idempotency.** Re-running an import must not duplicate
(the no-silent-overwrite rule) — flow-level Excel test.

### Category I — Tooling & DX

**I1. `just`/Makefile targets.** `test` (serial), `test-fast` (xdist),
`test-e2e`, `test-migration`, `lint`, `ci-local` — encode the tiers.

**I2. Deterministic herbus fixture.** test_shopping_benchmarks' hard
/tmp dependency → generate from tests/fixtures/build_herbus_drive_fixture.py
on session start (or importorskip with a clear message).

**I3. Coverage per-module report in CI** (and fail_under for money.py/
units.py per AGENTS.md: 95% — currently a single global 80% gate).

**I4. ruff on tests/.** Test code isn't linted today (ruff runs on app/);
cheap hygiene win.

**I5. pytest-randomly as default-off, not default-on.** The suite is
order-sensitive by history; `-p no:randomly` is cargo-culted in every
command. Either fix order-independence or document serial as canonical
(done in R8) — currently the plugin ships enabled and everyone disables it.

**I6. Docstring coverage for the remaining 568 tests** (M15: 1,450/2,018)
— the suite is the documentation of business rules; enforce on new files.

**I7. Test-name convention lint.** Enforce `test_<unit>_<scenario>_<expectation>`
naming via a review checklist; today names mix English/Spanish/scenario styles.

### Category J — CI pipeline

**J1. CI budget resolution** (documented decision pending: public flip,
Pro seat, or self-hosted on the VPS). Until then the effective gate is
manual — the biggest process risk in the whole catalog.

**J2. Tiered CI when unblocked:** PR = smoke+crud+auth+security+e2e (~5 min);
nightly = full serial + xdist + perf + migration full sweep; weekly = manual
+ pg containers.

**J3. CHANGELOG-discipline + coverage gates already in ci.yml — keep, and
mirror as pre-commit hooks for local enforcement.

**J4. Deploy smoke job.** Post-deploy: curl healthz + login + one GET per
top-10 route from the VPS (the manual ritual after `docker service update`,
automated).

### Category K — App-side testability refactors (production code, small)

**K1. Route table export.** Expose `app.rms.main.routes` as data (method,
path, router) — lets a coverage test assert every route is exercised by ≥1
test (kills the dark-router class permanently).

**K2. Settings-runtime validation consistency.** Some endpoints return 400,
others 422, for equivalent bad input (measured during the CRUD sweep).
Standardize → simpler negative-path matrix (D2).

**K3. Test-only code paths in app/** (6 sites: auth-bypass ×3, for_tests ×2,
internal-routes gate ×1): consolidate behind a single `app.rms.testing`
module so the audit surface is one file, not six scattered flags.

**K4. Seed data as a first-class module.** seed.py's demo dataset is the
shared language of tests + dev boots; version it alongside migrations.

### Category L — Knowledge & process

**L1. ADR for the test architecture** (factories/flows/invariants pattern)
so Kiki's future work extends rather than forks it.

**L2. Bug-to-test convention.** Every prod incident gets a regression test
named for the incident date (existing pattern: test_hotfix_regressions) —
write it down as the rule.

**L3. Runbook: "adding a new route" checklist** — flow helper + factory +
negative-path row + invariant row. Makes coverage the default.

---

## Sizing

| Category | Items | Rough total |
|---|---|---|
| A Factories | 6 | 8 h |
| B Flows | 6 | 5 h |
| C Structure | 6 | 6 h |
| D Assertions | 6 | 6 h (much folded into A/B adoption) |
| E Determinism | 5 | 4 h |
| F Concurrency/perf | 4 | 4 h |
| G Security | 6 | 6 h (G3 blocked) |
| H Integrity/migrations | 5 | 4 h |
| I Tooling/DX | 7 | 5 h |
| J CI | 4 | 4 h (J1 is a decision, not work) |
| K App-side testability | 4 | 5 h |
| L Process | 3 | 2 h |
| **TOTAL** | **62 items** | **~59 h** (≈25 h for the high-leverage core A+B+C1-C2+D3+E) |

Priority order for execution: A1→A2→B1→B2→B3 (the factory/flow core, one
batch) → E1-E3 (determinism) → D2-D3 (assertions) → C1-C2 (structure) →
then category-by-category.
