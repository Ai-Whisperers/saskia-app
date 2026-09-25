# Saskia RMS — E2E Test Analysis: Full-Catalog Gap Review

**Date:** 2026-09-25
**Baseline:** 191 routes across 24 routers; 2,215+ tests; E2E suite = 4 files / 29 tests
(`un_dia_en_la_panaderia`, `strict_auth`, `suppliers_shopping_flows`,
`migration_archaeology`). Suite green serial AND `-n 4`.

## 1. What the E2E layer already proves

| Dimension | Covered by |
|---|---|
| Full business day (stock→recipe→product→pedido→sell→void→merma) with invariants | un_dia #1 |
| Allergen guard 409 + snapshot price immutability | un_dia #2/#3 |
| Pedido lifecycle through real forms (repeated-field encoding) | un_dia #4 |
| Recipe line contract (the line_qty regression class) | un_dia #5 |
| Negative-stock guard, tag cascade through edit route | un_dia #6/#7 |
| Real bcrypt auth path (login/reject/anonymous/session) | strict_auth |
| All 7 shopping routes + sync rule + idempotency; supplier CRUD | suppliers_shopping |
| Populated-DB upgrade replay v1→54 + registry contiguity | migration_archaeology |

Track record: 3 shipped-to-prod bugs found in the first 2 days of this
suite (allergen sort crash, `_product_inherit_sync` NameError,
`get_session` connection leak on 184 routes).

## 2. Gaps by measured route coverage

### 2.1 Untouched route clusters (19 routes with zero test references)
- **customers detail/edit** (`GET/POST /clientes/{id}`, `/{id}/editar`) — the
  allergen guard READS `Customer.notes`; nothing tests editing that note
  through the UI, then re-triggering a POS sale.
- **insights price-impact** (`/reportes/price-impact/{id}`) — built, live,
  zero tests.
- **recipes GET detail + crear-producto** — the recipe→product spawn flow.
- **products upload-image** — file-upload surface, untested.
- **reportes/cierre-mensual** — month-close, money-relevant, untested.
- **users admin edit/delete** (`/usuarios/{id}/editar|eliminar`) —
  privilege surface, untested.
- **settings_runtime: 37 routes, effectively untested** (only static-content
  audit touches it). This is the single biggest cluster: branding, tax
  config, margin tiers, pricing markup, categories/channels/payment
  methods/storage types/date presets — all operator-editable runtime config
  that downstream costing/reports read.

### 2.2 Flow dimensions no E2E covers yet
1. **Excel import → operations → re-import** roundtrip through HTTP (unit
   tests exist for the patch engine; the full user journey incl. preview +
   confirm + no-silent-overwrite rule is only partially covered).
2. **Backup → restore drill**: backups are tested as artifacts; no test
   boots the app against a restored DB file and asserts the day continues.
   (The cron pulls backups off-box; nobody has ever proven a restore.)
3. **Role/permission matrix**: only `admin` exists in tests. If Kiki/others
   get non-admin accounts, every mutation route needs an authz E2E.
4. **CSRF + rate-limit interplay inside a real flow**: both have unit
   tests; no scenario does a burst day (12 rapid POSTs) asserting 429s
   don't corrupt partial state.
5. **Multi-day continuity**: demand forecast uses observed sales span;
   freshness uses receipt dates. One flow spanning 3 frozen days
   (freeze_asuncion) would lock in the date math end-to-end.
6. **Concurrent writes**: `database is locked` class. Two interleaved
   clients selling from the same finite stock — final stock must reconcile
   exactly. (The leak fix removed the main trigger; the invariant deserves
   a test of its own.)
7. **Export correctness**: CSV/XLSX/printer endpoints render data that
   must match the DB rows (money formatting, voided exclusion).
8. **Audit-trail completeness for the whole day**: after the un-dia flow,
   assert every mutation wrote an audit row with the right action name —
   one test, huge forensic value.
9. **Session expiry mid-flow**: session cookie expires → in-flight POST
   must redirect, not 500.
10. **Static/copy integrity inside flows** (Spanish vos strings, no
    English leakage) — partially covered by static audit; not asserted on
    post-error flash messages, which are the most common breakage.

### 2.3 Structural risks in the suite itself
- **flows.py covers only 10 routes** of 191 — extend before writing more
  scenarios, or scenarios become half-HTTP/half-DB again.
- **No `pytest.ini` e2e marker** — the `e2e/` dir isn't marked, so
  `pytest -m smoke` selection is inconsistent with the dir layout.
- **Coverage gate is 80% global** — nothing enforces per-route coverage;
  settings_runtime proves the gate can pass with an entire router dark.

## 3. Priority plan (ranked by risk × cost)

| # | Item | Est | Why |
|---|---|---|---|
| 1 | **Settings-runtime E2E**: one parametrized "config CRUD sweep" over the 37 routes (create→read→update→delete for each entity type) + one flow asserting a margin-tier change alters product pricing on the next render | 3 h | Biggest dark cluster; feeds costing |
| 2 | **Customers E2E**: edit customer allergen note via UI → POS sale blocked/unblocked | 1.5 h | Health-safety feature with zero UI-path test |
| 3 | **Restore drill E2E**: backup → new engine on the file → run one sale | 1.5 h | The only unproven half of the backup story |
| 4 | **Audit-completeness assertion** appended to the un-dia flow | 1 h | Forensics; cheap |
| 5 | **Concurrent-sales invariant** (2 threads × N sales, exact stock reconcile) | 2 h | Lock-class regressions |
| 6 | **3-day frozen flow** for demand/freshness date math | 2 h | Date bugs are the top flake/bug class here |
| 7 | **Excel import journey** (upload → preview → confirm → verify) | 3 h | Data-loss surface |
| 8 | **users admin + role matrix** (once 2nd user exists) | 2 h | Blocked on real users |
| 9 | **cierre-mensual + exports content assertions** | 2 h | Money reports |
| 10 | Extend `flows.py` to ~30 routes + `e2e` pytest marker | 2 h | Multiplier for everything above |

Total ≈ 20 h. Items 1-6 are the "do next" batch (~10 h) — they cover the
only dark router, the safety feature, and the three unproven invariants
(restore, concurrency, dates).
