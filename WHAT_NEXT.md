# the operator · What Next? (refresh 2026-10-13, post S1–S4 sweep)

> **2026-10-13 S1–S4 sweep reconciliation.** Since the 2026-10-12
> docs-verification pass, the S1 (test parametrization), S2 (robustness),
> S3 (cyclomatic complexity), and S4 (scripts/verify_catalog_on_vps
> helpers) campaign batches all landed on `main`. The branch
> `hermes/levelup-s5-batch1` is now at `origin/main` HEAD
> `921d05c6` (rebased -X theirs, no conflicts). This refresh is a docs
> sync, not a behavior change. The 2026-10-12 correction-layer block
> stays as-is (the underlying numbers still hold); the 10-10 narrative
> section is replaced with a 10-13 "shipped since 10-10" roll-up and
> the ranked next-up list is rebuilt against the post-sweep backlog.
>
> Open follow-ups carried into this refresh (driven by the S-prefixed
> work that landed in the window): see the SASKIA-211-row in the "🎯
> What's next?" section below. The big one is **SASKIA-211 persist-DB
> idempotency test** flagged in
> `tests/test_d_grade_helpers_batch14.py:903` — kept in the in-memory
> SQLite fixture for this sweep, the persistent-DB follow-up is the
> next thing on the lane after this docs PR.

## 📊 Current State (2026-10-13 ~post S1–S4 sweep)

| Knob | Value | Source |
|------|-------|--------|
| Schema | v121 | `app/rms/config.py:92` |
| Migrations on disk | 40 | `app/rms/migrations/_*.py` |
| Tests collected | ~8,030 (16-file hardcoded-dates sweep lifts parametrize row count) | `pytest --collect-only` post-#197 |
| Open ruff findings | 0 (lint passes; 11 informational "Invalid `# noqa` directive" warnings on `arch-rule` lines) | `ruff check` |
| Open PRs | 0 (merged: s1-batches 5-14 → #181-199; s2-pr4..pr7 → #177/#180/#187/#200; s3-batches redux → #172/#176/#182/#183/#201; s4-batch1 → #202) | `gh pr list --state open` |
| Open issues | 0 | `gh issue list --state open` |
| Branch | `hermes/levelup-s5-batch1` (this batch) | — |
| Last commit on `main` | `921d05c6 refactor(s4-batch1): extract helpers in scripts/verify_catalog_on_vps` (PR #202) | `git log origin/main -1` |

## ✅ Ships since the 2026-10-10 → 10-12 docs pass

Grouped by lane, full PR chain (every PR closed; all reached `main`):

### S1 — test parametrization (drive D-grade helpers from CC ≤ 10)

- **#178 / #181 / #186 / #189 / #191 / #192 / #193 / #195 / #199** —
  parametrized 9 D-grade helper clusters:
  `bank_list` + `shopping_list_index` (#178),
  `pedido resolve` + `address-book` (#181),
  `_step_5_build_recipe_row` + `_restock_for_target` (#184),
  `plan_production` + `forecast_restock` (#186),
  `compute_plan_accuracy` + `libro_ventas` (#189),
  `batch_compute_prime_cost` + `import_benchmarks` (#191),
  `_validate_workbook` + `_import_patch_ingredientes` (#192),
  `fix_file` + `evidencia_importar` (#193),
  `produccion_print` + `reclassify` (#195),
  `seed_packs_gen` + `_seed_sales_90_days` (#199).
- **#197** — test-hygiene sweep: `# allow-hardcoded-dates: <reason>`
  markers on 16 frozen-time/fixture tests (unblocks the
  `test_no_hardcoded_dates.py` regression gate that was blocking CI).

### S2 — robustness sweep (silent-except → AppError → retry)

- **#177** (PR4) — routers silent-except sweep (54-test gate).
- **#180** (PR5) — `AppError → Sentry level` mapping + `app/rms/sentry.py`.
- **#187** (PR6) — wire `retry_transient` in `scrapers` + `backup_crypto`.
- **#200** (PR7) — wire `retry_transient` in `r2_backup` + `email_outbound`
  (the S2 closure); 12 new test cases in
  `tests/test_retry_wiring_2.py`.

### S3 — cyclomatic complexity (orchestrator pattern, multi-letter epic)

- **#188** (SASKIA-211z) — `_resolve_target` CC 21→4 (orchestrator + 3 helpers).
- **#185** (SASKIA-211y) — `sentry_before_send` CC 22→5 (orchestrator + 3 helpers).
- **#190** (SASKIA-211aa) — `apply_sale` CC 25→10 (5 helpers).
- **#194** — `batch_recipes_cost` CC 18→7 (3 helpers).
- **#176** (#182/#183 redux) — `produccion_worksheet` CC 166→4 (3 views + 15 step helpers) in #176; `_produccion_day_view` CC 28→19 in #182; `margin_drift_all` CC 22→6 (6 helpers) in #183.
- **#201** (S3-batch10) — `produccion_shift_execute` CC 22→3 (D→A).

### S4 — scripts/verify_catalog_on_vps refactor

- **#202** — extract 6 helpers from the vps catalog check
  (`resolve_code_schema_version`, `check_schema_match`,
  `collect_catalog_failures`, `print_report`, `open_db_or_exit`,
  `read_db_or_exit`); 31 new test cases in
  `tests/test_d_grade_helpers_batch15.py`. CC reduction + module exit
  codes made ergonomic.

### Adjacent (not s-prefixed but shipped in-window)

- **#196** — Compact operating lists behind `Más / Filtros / Ver detalles`
  on Proveedores / Caja / Banco / Fiado / Movimientos / Ventas /
  Historial. (HTML polish + keep-in-flow disclosures.)
- **#199** — also covers S1-batch14 (see above).

## 🎯 What's next? (ranked)

### #1 — SASKIA-211 persist-DB idempotency test (open follow-up)

The S1 sweep parametrized `_seed_sales_90_days` with a 4-case
idempotency scenario but kept it on the in-memory SQLite fixture
because adding `rng_np` to the seed helper needs a real persistence
target (the in-memory engine loses state across `session_factory()`
calls). See
`tests/test_d_grade_helpers_batch14.py:903` — the comment in the
pytest.skip case documents:

> Follow-up in SASKIA-211 will add a proper idempotency test with
> persistent DB.

This is the **carry-over item from S1-batch14** that closes the
S3/SASKIA-211 multi-letter complexity epic. Effort: S (one
parameterized file + one fixture + wiring `pysqlite_binary`/`make
test` against `data/test-seed.sqlite3` instead of `:memory:`).
Owner: s1 lane (next batch) or pick up here if s1 lane is idle.

### #2 — VPS secrets rotation — 30 min (deferred to Ivan)

`deploy-dev` / `deploy-test` still need a working `BWS_ACCESS_TOKEN`
+ VPS SSH key. Until then, deploys land via VPS-side pulls (Ivan does
this manually). The transient `bws secret list 429` failures on the
`deploy-test` job are BWS rate-limiting when both jobs request
secrets at the same time — proper fix is "BWS_ACCESS_TOKEN
populated" so the GitHub App rotation path can take over. Once BWS
is populated, both deploys should light up green and the `4095.0`
bws call rate becomes moot.

### #3 — Coverage gap analysis — 2-3h (deferred until a Sprint 2.2)

Test coverage is at 26.12% (gate is 35%, per `pyproject.toml`). Per
AGENTS.md, the 35% gate is a Phase 1 milestone; the 4-phase plan in
`docs/plans/2026-08-31-rms-fase-1-dev-plan.md` bumps it in stages.
The biggest gap is `app/services/template_render.py` at 21% (an
entire module that's not covered). Other modules under 25%:
`app/services/import_xlsx.py`, `app/rms/reports/*`, and
`app/rms/production/*`. The Sprint 2.2 "ship Saskia a usable
product" milestone is the next coverage push.

### #4 — Backlog items (no rush)

- **SASKIA-210** — Supabase RLS + Storage; explicitly deferred per
  the per-client-instances decision
  (`docs/plans/SASKIA-210-supabase-rls-multitenant-onepager.md`).
- **ZAP promotion to high-only** — needs 2 consecutive clean weekly
  scans (calendar check, not work).
- **feature/station-shell** — sibling session (puesto cards UI) in
  flight; carries a stale `app/CHANGELOG.md` that will conflict on
  merge — sibling should drop it before merging.
- **Ruff noqa warnings on `arch-rule` lines (noise)** — 11
  informational warnings ("expected a comma-separated list of
  codes") on `# noqa: arch-rule — <reason>` lines. The lint check
  itself passes; the warnings are stderr noise. Two ways to silence
  would both break the test contract in
  `tests/test_check_imports_rules.py` (which parses the string
  literally). **Left as-is.**

## ⏸️ Parked / waiting on a condition

- **PR #101 refactor** (closed) — the 48-file complexity refactor
  is still valuable but needs re-authoring on the post-#117 base
  with annotations from the start. If anyone wants to do this,
  file a new SASKIA ticket.
- **`feat/station-shell` (feature branch)** — sibling session in
  flight; awaits the CHANGELOG drop + rebase onto main.

## ❌ Explicitly deferred — do not pick up

- **Sentry→Telegram** — Iván: not until 30 customers ask.
- **Supabase RLS + Storage** — SASKIA-210 decision: per-client
  instances, all deferred until Saskia is happy with the product.
- **Tier 3 tools** — Semgrep CE, umbra-scan, prek (Vale was adopted
  locally as documented in PR #102).

## 🛠 Tooling & Plumbing notes

- WHAT_NEXT pattern: regenerate dated, archive previous. Don't
  in-place edit history. Six archived versions now exist in
  `docs/operations/`:
  - `2026-10-09-evening-WHAT_NEXT-archived.md`
  - `2026-10-10-early-WHAT_NEXT-archived.md` (from #121)
  - `2026-10-10-midday-WHAT_NEXT-archived.md` (lost in #125 force-push; kept as reference)
  - `2026-10-10-late-WHAT_NEXT-archived.md` (the 07:30 refresh)
  - `2026-10-10-evening-WHAT_NEXT-archived.md` (the 19:00 refresh)
  - `2026-10-12-WHAT_NEXT-archived.md` (the docs verification pass; the prior refresh before this one)
- Backup discipline (AGENTS.md rule 17) enforced at `init_db()`;
  `sazon rollback --to N` is the recovery net (shipped in #209).
- `app/CHANGELOG.md` was removed in the docs reorg (commit
  `e9b80533`); CI gates now on root `CHANGELOG.md` (commit
  `f7ab4b24`).
- The 11 informational "Invalid `# noqa` directive" warnings from
  ruff are the cost of using `arch-rule` as a project-internal
  code; `tests/test_check_imports_rules.py` parses the string
  literally so we can't rename it without also updating the test.
  Left as-is (warnings don't fail checks).
- **CI test wall-time** dropped from ~12min to ~1.5min after #126.
  The full test suite now runs in the same time window that the
  `sazon migrate` smoke test alone used to take.

---

**Generated:** 2026-10-13 post-S1–S4-sweep; refreshed after rebase
of `hermes/levelup-s5-batch1` onto `origin/main` HEAD `921d05c6`.
