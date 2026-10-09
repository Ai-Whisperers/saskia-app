# the operator · What Next? (refresh 2026-10-09)

> **Supersedes** `WHAT_NEXT_2026-10-08-archived.md`. Older
> `IMPROVEMENT_BACKLOG.md`, `COMPLETE_*.md`, `PHASE2_*.md` are stale — use
> `git log` as ground truth: `git log --oneline --since="2026-10-08"`.

## 📊 Current State (2026-10-09)

| Knob | Value | Source |
|------|-------|--------|
| Schema | v117 | `app/rms/config.py:92` (CURRENT_SCHEMA_VERSION=117) |
| Prod image | `sazon-rms:prod-20261009-161420` | last prod deploy |
| Test image | `sazon-rms:test-20261009-160431` | last test deploy |
| Prod site | https://sazon-vps.paragu-ai.com | env-real (post 2026-10-09 fix) |
| Test site | https://saskia-test.paragu-ai.com | env-real |
| Ruff | tracked in-memory (subagent fixing now) | `uv run ruff check .` |
| Backup cron | `/etc/cron.d/sazon-backup-prod` installed 2026-10-09 | VPS |

## ✅ Closed in the last 24h (since 2026-10-08)

- **Sales payment-row bug fix** — `56f2b77e`. Bot's complexity refactor
  of `sale_create_multi` lost 3 critical things: (1) single-method sales
  wrote **zero** `SalePayment` rows (entire else branch was missing),
  (2) split payments missing `created_at` → 500 NOT NULL errors,
  (3) `_process_split_payments` missing `_left -= _take` decrement +
  defensive remainder handling. All restored. 18/19 sale tests pass
  (1 pre-existing void test failure documented separately).
- **Ruff cleanup after bot's complexity wave** — `5c140b1f`. ~50
  whitespace/import violations fixed. (The 323 type-annotation errors
  fixed in a follow-up commit; subagent working as of this writing.)
- **CI workflow unblocking** — `5e3f53e2`, `fffe7c7f`, `640c21e5`.
  Pre-existing CI bugs fixed: (1) `uv pip install --system pyyaml`
  → throwaway venv, (2) `SAZKIA_DEPLOY_KEY` secret missing → switched
  to `VPS_KEY`, (3) `BWS_ACCESS_TOKEN` still missing from GH secrets
  (auto-deploy chain remains manual — see Open #1).
- **Prod deploy chain restored** — `d0bf56da`, `5fb3b2ed`, `b9456540`.
  `write_env_file.py` was failing on `SENTRY_DSN` (not in BWS) and
  silently using placeholder env values (`FERNET_KEY=***-replace-me-***`,
  `SUPABASE_***_KEY=***lder`). Three commits: (1) optional_bws_keys
  field, (2) YAML inline comment parsing, (3) actually wire it through
  (first attempt's comment-stripping was masked by YAML). **Prod now
  has real env** — 21 lines, 1659 bytes, real FERNET_KEY, all 4 Supabase
  keys, all CF R2 keys, real NEON_DATABASE_URL, real SASKIA passwords.
  Backup cron installed for the first time.
- **5 critical refactor regressions caught in ruff** — manually fixed
  in this session: `_build_hourly_sales_chart` + `_build_30day_sales_chart`
  were deleted (would 500 every /dashboard request), `forecast.py:ing`
  undefined in comprehension, `reorder.py:csv` import inside function
  with `csv.DictReader` in type hint (F821), 4 `PLANTILLA_*_COLS`
  constants deleted but still referenced (export-xlsx would 500).

## 🎯 What's next? (3 picks, ranked)

### #1 — **Type-annotation subagent + ruff CI gate** — ongoing, ~30 min

The subagent is in the middle of fixing 323 ANN001/ANN202 errors. Once
it lands, CI will pass again. Then the **next** commit should be a
ruff-CI-required check: branch protection rule that fails the merge
when ruff fails. (Currently `ci.yml` already runs `ruff check .` but
the repo is private + budget-gated, so CI isn't actually executing.
Fix: add `dev-ci.yml` to branch protection as a required check, or
flip repo to public.)

### #2 — **Fix the `test_void_removes_payment_rows` pre-existing failure** — 30 min

The `void_sale` function in `app/rms/sales/lifecycle.py` marks
`sale.voided_at` and reverses stock moves, but does NOT delete
`SalePayment` rows. The test expects deletion. Two options:
- (a) Make `void_sale` also soft-delete `SalePayment` rows (mark
  `voided_at` instead of hard delete) — preserves audit trail.
- (b) Make `void_sale` hard-delete `SalePayment` rows.
- (c) Update the test to match current behavior.

Per AGENTS.md, no money mutation without a test. (a) is safest.

### #3 — **Hard Rule 18 conflict resolution** — 30 min, agent-decided

`AGENTS.md` Hard Rule 18 says "`app_meta` table is source of truth
(P1)" but `docs/operations/2026-10-09-schema-version-source.md` (on
main) decided against it with 4 reasons. Per AGENTS.md: hard-rule
conflicts = ESCALATE. Either:
- Implement Tier 3 (P1 work — add `app_meta(schema_version)` as
  runtime source of truth, keep `SCHEMA_VERSION` constant as build-intent)
- Or amend Hard Rule 18 to reflect the new world (drop P1 designation,
  note the doc as the resolution)

## ❌ Deferred — Sentry→Telegram activation

Per WHAT_NEXT_2026-10-08-archived.md: needs ≥30 Sazon customers asking
for Telegram. Iván explicitly deferred 2026-10-07. Code path stays
shipped but dormant. Not in scope.

## 🛠 Tooling & Plumbing

- **Stale docs**: prior `IMPROVEMENT_BACKLOG.md`, `COMPLETE_*.md`,
  `PHASE2_*.md` are superseded. Don't re-edit. Refresh
  `IMPROVEMENT_BACKLOG.md` to add 3 most-recently-shipped items from
  this session (sales payment fix, prod deploy chain, refactor
  regressions caught by ruff).
- **Backup discipline**: AGENTS.md rule 17 (pre-migration backup)
  enforced at `init_db()`. SASKIA-209 added `sazon rollback` recovery.
- **CRITICAL**: the bot's complexity-refactor wave (commits 31a4c766,
  3d0c9f56, cbfd41f9, 816ffba5, 092d5292, 6ca34c08, 123afefa,
  1d2c42a3, cb5c1983, 1c63a5b6, 3e894be5, 3cbe3c48, 27241bea,
  635e49f4, 079cc12f, 26171fb1, e0d0b55c, 12117512, e8e57725) is
  generating ruff-broken code every commit. Either stop the bot or
  enforce ruff via dev-ci.yml as a required check.

## 💼 Business-Operational priorities (operator-visible)

- **Prod is now real** — no more placeholder envs. Sales/payment bug
  fix is live. Operator can resume normal operation.
- **Predictive restocking** (SASKIA-208) was waiting on VPS deploy —
  deploy happened, should be working now. Verify on /produccion.
- **Wishlist purchases → inventory** (SASKIA-205) is live.
- **Forward-only migration rollback** (SASKIA-209) is live.

---

**Generated:** 2026-10-09 after prod deploy (image prod-20261009-161420).
**Update pattern:** when this falls out of date, run
`git log --oneline --since="2026-10-09"` and rewrite the "Closed in
the last 24h" section. Archive the old version as
`WHAT_NEXT_YYYY-MM-DD-archived.md` first. Don't add to this file
in-place — start a new dated file.
