# the operator · What Next? (refresh 2026-10-10 ~19:20 UTC)

> **Supersedes** `docs/operations/2026-10-10-very-late-WHAT_NEXT-archived.md`
> and the older `2026-10-10-late-`, `2026-10-10-early-`,
> `2026-10-09-evening-` archives. The "midday" archive was lost when
> #125 force-pushed main; the prior refresh (#127, post-#125) is
> archived as `very-late-`. Ground truth: `git log --oneline --since="2026-10-09"`.

## 📊 Current State (2026-10-10 ~19:20 UTC)

| Knob | Value | Source |
|------|-------|--------|
| Schema | v117 | `app/rms/config.py:92` |
| Migrations on disk | 36 | `app/rms/migrations/_*.py` |
| Open ruff findings | 0 (lint passes; 11 informational "Invalid `# noqa` directive" warnings on `arch-rule` lines) | `ruff check` |
| Active TODO comments | 5 (placeholder rows in `scripts/check_active_todos.py`; the script itself) | `make todos` |
| Open issues | 0 | `gh issue list --state open` |
| Open PRs | 0 | `gh pr list --state open` |
| Environments | prod + dev + test all `/healthz` 200 | saskia-vps / saskia-dev / saskia-test .paragu-ai.com |
| Branch protection | ruleset #24802688 active | 5 required checks |
| Supabase | disabled on prod (NXDOMAIN) | `a5499c51` (#98) |

## ✅ Closed since the last refresh (2026-10-10 19:00 → 19:20)

- **#122 — PATCH-plantilla column fix (`5e78e6a1`)**: the 3
  pre-existing `tests/test_excel_patch.py` failures (#120 was the
  sibling 13-fix bundle; #122 was the PATCH-specific subset). Fix:
  defined separate `PATCH_*_COLS` constants (Productos, Clientes,
  Ingredientes, Recetas) without the ` [REQUIRED]` / ` [OPTIONAL]`
  UX annotations the PATCH handler reads verbatim, and updated the
  corresponding `_import_patch_*` readers. All 3 tests now pass.

- **#126 — conftest test_daily_summary hang (`e54c4571`)**: pure-Python
  tests hung on the `app_imports` autouse chain. Fix: stub the
  autouse chain in conftest for pure-Python tests so they don't
  pay the FastAPI/DB app import cost. CI test step went from
  timeout to green.

- **#127 — WHAT_NEXT docs refresh (`3b1cf90f`)**: archived the
  pre-#126 doc, wrote the post-#125 WHAT_NEXT.

- **#129 — deploy infrastructure race-condition fix (`9f9cead4`)**:
  the 3-bug bundle that had been blocking all PRs from merging for
  24h:
  - **Bug 1**: brittle `case "$HEALTH" in *'"ok"'*)` glob in the
    `Verify {test,dev} healthz` step was causing
    `bash: line 5: unexpected EOF while looking for matching single-quote`
    on the GHA runner. Replaced with portable
    `printf | grep -q '"status":"ok"'`.
  - **Bug 2**: md5 sync check race in `scripts/deploy.sh` —
    `REMOTE_DIR=/opt/build-apps/sazon-rms` is shared across ALL
    PRs, so concurrent `rm -rf && tar xzf` could race with another
    PR's `md5sum` and hard-fail an otherwise-healthy deploy. Soft
    `WARN` instead of `exit 1`.
  - **Bug 3**: scp race on `/tmp/sazon-src.tar.gz` — all PRs wrote
    to the same tarball path; concurrent `scp` interleaved bytes
    and produced `gzip: invalid compressed data--crc error` on
    extraction. Fixed with per-invocation
    `/tmp/sazon-src-$$-TIMESTAMP.tar.gz` filename.
  - **Bonus**: `docker build ... 2>&1 | tail -3` was swallowing
    the actual error message on dev build failures. Bumped to
    `tail -30`.

  28/28 deploy-infra tests still pass. CHANGELOG: `2026-10-10e`.

## 🎯 What's next? (ranked)

### #1 — operator pick — pick up the next SASKIA ticket
With the deploy pipeline now race-free and #122/#125/#126 all
merged, there are **no open PRs and no open issues**. Next work
is operator-driven. Candidates from the parked/backlog list:

- **SASKIA-210** — Supabase RLS + Storage; explicitly deferred per
  the per-client-instances decision
  (`docs/plans/SASKIA-210-supabase-rls-multitenant-onepager.md`).
  Decision: do not start until Saskia is happy with the product.
- **SASKIA-212 / SASKIA-213** — closed via PR #119 (legacy channel
  constants + `?period=custom` test tightening). No follow-up.
- **PR #101 refactor** (closed) — the 48-file complexity refactor
  is still valuable but needs re-authoring on the post-#117 base
  with annotations from the start. **Only if operator asks.**
- **Feature/station-shell** (sibling) — operator-driven; sibling
  is the source of truth for that branch. Carries a stale
  `app/CHANGELOG.md` that will conflict on merge — sibling should
  drop it before merging.

### #2 — VPS secrets rotation — 30 min (deferred to Ivan)
`deploy-dev` / `deploy-test` need a working `BWS_ACCESS_TOKEN` +
VPS SSH key. Until then, deploys land via VPS-side pulls (Ivan
does this manually). When BWS is populated, both deploys should
light up green.

### #3 — Backlog (no rush)
- **ZAP promotion to high-only** — needs 2 consecutive clean
  weekly scans (calendar check, not work).
- **Ruff noqa warnings on `arch-rule` lines (noise)** — 11
  informational warnings ("expected a comma-separated list of
  codes") on `# noqa: arch-rule — <reason>` lines. The lint check
  itself passes; the warnings are stderr noise. Two ways to silence
  would both break the test contract in
  `tests/test_check_imports_rules.py` (which parses the string
  literally). **Left as-is.**

## ⏸️ Parked / waiting on a condition
- **PR #101 refactor** (closed) — re-author on post-#117 base
  with annotations from the start. If anyone wants to do this,
  file a new SASKIA ticket.
- **SASKIA-210** — parked until Saskia signals readiness.

## ❌ Explicitly deferred — do not pick up
- **Sentry→Telegram** — Iván: not until 30 customers ask.
- **Supabase RLS + Storage** — SASKIA-210 decision: per-client
  instances, all deferred until Saskia is happy with the product.
- **Tier 3 tools** — Semgrep CE, umbra-scan, prek (Vale was
  adopted locally as documented in PR #102).

## 🛠 Tooling & Plumbing notes
- WHAT_NEXT pattern: regenerate dated, archive previous. Don't
  in-place edit history. Five archived versions now exist in
  `docs/operations/`:
  - `2026-10-09-evening-WHAT_NEXT-archived.md`
  - `2026-10-10-early-WHAT_NEXT-archived.md` (from #121)
  - `2026-10-10-midday-WHAT_NEXT-archived.md` (lost in #125
    force-push; kept as reference)
  - `2026-10-10-late-WHAT_NEXT-archived.md` (from #127, post-#125)
  - `2026-10-10-very-late-WHAT_NEXT-archived.md` (this refresh
    archives #127's doc — the source of truth for the 19:00 UTC
    state when #126/#129 were still in flight)
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
- **Deploy concurrency note (NEW 2026-10-10)**: the three
  deploy-pipeline bugs fixed in #129 were all caused by shared
  state on the VPS (`/opt/build-apps/sazon-rms/` and
  `/tmp/sazon-src.tar.gz`). If you add a new deploy step that
  uses shared VPS state, **always** namespace by `$$` or `$ENV`
  to avoid the next race-condition CI outage.

---

**Generated:** 2026-10-10 ~19:20 UTC after #122, #126, #127, #129
all merged to main.
