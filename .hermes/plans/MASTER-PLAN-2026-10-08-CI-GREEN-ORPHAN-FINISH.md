# MASTER PLAN — saskia-app: CI green + finish orphan shipping (2026-10-08)

**Author:** Hermes (autonomous) · **Decides:** all decisions pre-made, no user input needed
**Repo:** Ai-Whisperers/saskia-app · **main tip at plan time:** `acbdef31` (schema v114)
**Worktree:** `/opt/data/profiles/ivan/scratch/saskia-app-saskia-204` (branches for all work)
**Untouchable:** worktree of active session `hermes/20261005_211356_c7aa80`, `saskia-app-work` (dirty)

---

## 0. Current state (verified 2026-10-08 ~04:00 UTC)

### 0.1 Landed this effort (all MERGED — do not redo)
| PR | Content | Note |
|---|---|---|
| #55 | back-to-top + live-time/date-format/money-format/cache | wave 1 |
| #56 | ruff 265→0 (SASKIA-204), `rm -rf .venv` CI fix, migration 112 | Ivan's #63 superseded parts |
| #58 | ruff format sweep (237 files) | |
| #60 | post-merge format cleanup | |
| #62 | B.1 Venta Express (port from polish/saskia-p0) | |
| #63 (Ivan) | ruff 253→0 round 2 + latent-crash fixes | |
| #66 | seed_sazon: ASUNCION_TZ import + Channel enum unshadow (25/25 seed tests) | |
| #67 | wave 2a input-safety: autosave.js + undo.js + form-dirty.js (+74 tests) | |
| #68 | /ventas/buscar route-order 400 fix + produccion highlight tests → CSS_BODY | |
| 6568f6b3 (sib) | "6 lost UI features" night triage | introduced merma.py format break |

### 0.2 Why main CI is red right now (3 independent causes, verified)
1. **`app/routers/merma.py` unformatted** (L219-224) — landed via sibling `6568f6b3`.
   `ruff check` passes; `ruff format --check` fails → CI `Lint (ruff)` step red.
2. **`tests/test_no_hardcoded_dates.py` → 59 failures across ~60 test files** on clean main
   (verified locally on pristine checkout). Cause: sibling commits put date literals
   (`"2026-10-07"`, `datetime(2026, ...)`) in **comments/docstrings** of new/edited test files
   (e.g. `test_P35_sidebar_visibility_breakpoint.py:89` docstring "2026-10-07 Ivan: …").
   The test greps all test files for `20[2-9]\d-[01]\d-[0-3]\d` etc.
3. **Baseline-red, pre-existing, NOT ours:**
   - `smoke` job: Postgres password auth, 15+ consecutive failures on main (infra, needs creds
     we don't have — treat as known-red, never block on it).
   - OWASP ZAP: baseline-red on every branch incl. main (rules/tuning issue, advisory).

### 0.3 Remaining orphan assets (all source commits verified locally reachable)
| File | Source commit | Tests to port | Wave |
|---|---|---|---|
| state-preservation.js | `5b2b3c9c` | test_cross_page_state, test_cross_page_state_implementation | 2b |
| sortable-table.js | `28cdd2b8` | test_sortable_tables | 2b |
| search-highlight.js | `9fab2fd4` | test_search_highlight | 2b |
| stepper.js (+css) | `4987add0` | test_stepper | 2c |
| lazy-load.js | `59565ed8` | test_lazy_load, test_image_lazy_loading | 2c |
| perf-monitor.js | `4eb6b721` | test_perf_monitor (+form_help split) | 2c |
| clipboard.js | `b6b4b557` | test_clipboard | 2c |
| print-area.js | `859422e9` | test_print_area | 2d |
| form-validator.js | `50a50cc4` | test_form_validator | 2d |
| saskia-tooltip.js/.css + touch-targets.css | `c6143a12` | test_touch_and_tooltip | 2d (rebrand to `ui-*`) |

Already in main: autosave, undo, form-dirty (wave 2a, #67); ui-toast.js (sibling);
ui-skeleton.js; back-to-top + 4 format utils (#55).

### 0.4 Standing constraints (from AGENTS.md + session history)
- Hard rule 35: every PR touching app/scripts/tests/.github updates `app/CHANGELOG.md`.
- Hard rule 37: PR references a ticket. **Next free ticket numbers: SASKIA-311+** (310 taken).
- No new dependencies. ruff 0.16.10 pinned by CI resolution.
- Tests: no wall-clock dependence, no network, no real Sazon DB (`SASKIA_TEST_AUTH_DISABLED=1`).
- Git identity: `Hermes (autonomous) <hermes@ai-whisperers.dev>`; pushes via feature branches.
- Local pytest invocations must stay < ~4.5 min per call (kernel stability); full suite only on CI.

---

## 1. Workstream A — Restore main CI green (P0, do first, one PR)

**Ticket: SASKIA-311 · Branch: `fix/saskia-311-main-ci-red` · Est: 1-2h · Blocks everything else**

### A1. Format merma.py (2 min)
```
ruff format app/routers/merma.py
```
Verify `ruff format --check .` → clean, `ruff check .` → 0.

### A2. Kill the 59 `test_no_hardcoded_dates` failures (the real work)
The test allowlists: `tests/benchmarks/`, `tests/e2e/`, and any file with
`# allow-hardcoded-dates: <reason>` in its **first 2000 chars**.

**Decision (pre-made):** two-tier fix, judged per file:
- **Tier 1 — strip:** the date appears only in a comment/docstring as provenance
  ("2026-10-07 Ivan: …"). Rewrite the prose without the literal
  (e.g. "2026-10-07" → "early Oct 2026"). This is the majority (~40 files, incl. all
  `test_SASKIA-30x*`, `test_P35_sidebar_visibility_breakpoint`).
- **Tier 2 — allow-marker:** the date is load-bearing (fixture arithmetic: production_close_day
  (23), production_demand (17), tier8_eod_anomaly (13), public_recibo (11),
  produccion_copy_last_week (12), produccion_haccp (10), produccion_helpers (6),
  preflight_route (6), produccion_concurrent_edit (6), settings_audit (3) etc.).
  Add to file header (within first 2000 chars):
  `# allow-hardcoded-dates: fixtures intentionally pin dates; asserted relative to frozen now`
- Build the file list programmatically from the failing test's own output
  (`--tb=line` grep `has N hardcoded`), never by hand.
- After the bulk edit: run the test file locally (it takes ~3.5 min — single call, patience),
  expect 0 failed. Then `ruff check` + `ruff format --check`.

**Do NOT** touch `tests/benchmarks/` or `tests/e2e/` (already allowed). Do NOT edit the
`test_no_hardcoded_dates.py` scanner itself (it is the guard; relaxing it hides future rot).

### A3. smoke job (Postgres auth) — document, don't chase
Keep as known-red. Optional (only if >30 min spare): read `.github/workflows/*smoke*` +
the Postgres service block; if it's a missing secret (`POSTGRES_PASSWORD` style), open a
**question-Issue** for Ivan (only he can add repo secrets) — do not attempt workarounds.

### A4. ZAP — leave advisory-red
Confirmed baseline-red on every branch including main. Not a merge blocker. No action.

### A5. Ship
- CHANGELOG entry (Fixed: merma.py format; Fixed: 60 test files' hardcoded-date literals).
- Commit style: 2 commits (1: format merma.py; 2: date-literal sweep) — atomic revert units.
- PR → wait full CI (this is the PR that must go fully green except smoke/ZAP).
- **Merge order: this PR before any wave-2 PR.**

---

## 2. Workstream B — Ship remaining 10 orphan JS modules (waves 2b/2c/2d)

**Generic protocol per wave (learned from 2a):**
1. `git checkout -B feat/<wave-branch> origin/main` (fresh base, right before pushing).
2. Cherry-pick source commits; resolve base.html conflicts by keeping HEAD's script block and
   inserting only this wave's tags **with `?v={{ asset_version() }}`** suffix (current convention).
3. If a ported test predates the CSS extraction or format sweep: run ruff format+check --fix
   on just the new files; adapt assertions that reference inline `<style>` to the CSS_BODY
   pattern (see #68's produccion highlight fix).
4. Run the wave's test files locally (keep each pytest call under ~4 min; split if needed).
5. CHANGELOG entry per wave. One commit per feature (squash-merge preserves granularity).
6. Rebase onto latest origin/main immediately before push (main moves every ~15 min);
   `--force-with-lease` only.
7. If CI shows `Lint (ruff)` failure on files I didn't touch → they came from main's newer
   commits into the merge preview → format exactly those files, push again.
8. Test-job cancelled (no failed step) → `gh run rerun <id> --failed`, do NOT rebase for it.
9. Never merge with `test` FAILURE unless the failing tests are proven-failing on clean main
   (verify in `saskia-app-clean` worktree first) AND are outside my diff's scope.

### Wave 2b — reading/state UX (SASKIA-312, est 2-3h, 3 commits)
Branch: `feat/phase3m1-wave2b-reading-state`
- `state-preservation.js` ← 5b2b3c9c. **Conflict-known:** also touches
  `app/templates/_components/macros.html`, `insight_food_cost.html`, `base.html` — resolve to
  current main's macro structure; port only the state-preservation bits.
- `sortable-table.js` ← 28cdd2b8 (+ sortable-table.css if the commit has it — check `git show
  28c2dd2b8 --stat`; there is also `shortcut-badge.css` in the orphan list, skip unless in commit).
- `search-highlight.js` (+ css if present) ← 9fab2fd4.
- Tests: test_cross_page_state (145), test_cross_page_state_implementation (143),
  test_sortable_tables, test_search_highlight.
- Note: `test_state_preservation.py` and `test_touch_and_tooltip.py` ABSENT from main — port
  them from the same commits.

### Wave 2c — input/perf utilities (SASKIA-313, est 2h, 4 commits)
Branch: `feat/phase3m1-wave2c-input-perf`
- `stepper.js` (+stepper.css) ← 4987add0
- `lazy-load.js` ← 59565ed8 (IntersectionObserver + fallback)
- `perf-monitor.js` ← 4eb6b721 (commit also carries form-help text — take ONLY perf-monitor
  file + its tests; form_help pieces stay orphan unless tests demand them)
- `clipboard.js` ← b6b4b557 (data-copy + data-copy-from)
- Tests: test_stepper, test_lazy_load, test_image_lazy_loading, test_perf_monitor, test_clipboard.

### Wave 2d — print/validate/tooltip + rebrand port (SASKIA-314, est 3h, 3 commits)
Branch: `feat/phase3m1-wave2d-print-validate-tooltip`
- `print-area.js` ← 859422e9 (data-print targets)
- `form-validator.js` ← 50a50cc4 (HTML5 constraint API inline validation)
- **Rebrand port (decision B from user):** `saskia-tooltip.js` + `saskia-tooltip.css` +
  `touch-targets.css` ← c6143a12, renamed **ui-tooltip.js / ui-tooltip.css / ui-touch-targets.css**
  with all internal `saskia-tooltip` identifiers → `ui-tooltip` (class prefix, custom element
  name if any, localStorage keys). Template find/replace for any `saskia-tooltip` references
  (grep before/after; zero occurrences of the old name may remain). toast part already done by
  sibling (ui-toast.js in main).
- Tests: test_print_area, test_form_validator, test_touch_and_tooltip (port, rename refs).

### Wave 2 closeout (same PR as 2d or follow-up SASKIA-315)
- grep `-r "saskia-tooltip\|toast-helper"` → 0 hits outside CHANGELOG history.
- Check `/tmp/phase3m1-only.txt` remainder (non-JS orphans: .env.example, seed/catalog.py,
  customer_contacts/timeline services, misc CSS like empty-states/pagination/filter-bar-advanced,
  dark-mode, a11y-sweep tests) → **defer**: separate decision PR later, they are not blocking
  and several conflict with sibling UI work (6568f6b3 touched inicio/analisis templates).

---

## 3. Workstream C — Post-wave hygiene (SASKIA-316, only after A+B)

1. **Branch census re-run:** `git branch -r` — delete every merged/absorbed feature branch
   (keep `main`, `hermes/20261005_*`).
2. **Full-suite CI watch on main:** after last wave merges, confirm one fully-green CI run
   (excluding smoke/ZAP baseline) — that is the definition of done for the whole effort.
3. **Session log + state files:** append to `session_logs/2026-10-08.md` in the migration
   workspace; note wave statuses in the wave-1 report's "Next steps" section.
4. **Skill update:** `saskia-rms-development` — add the "orphan wave protocol" lessons:
   merge-preview lint failures come from siblings' unformatted main commits (fix = format those
   files in my PR); CI ruff == local 0.16.10 (same version, no skew); `--force-with-lease`
   after every rebase; base.html script tags need `?v={{ asset_version() }}`.

---

## 4. Execution protocol (applies to every work item)

**Order of operations (strict):**
```
work item → implement → local tests (targeted files only) → ruff check --fix → ruff format →
CHANGELOG → commit(s) → fetch+rebase origin/main → ruff format the merge result → push
--force-with-lease → open PR → poll (gh run view, 4-5 min cycles) →
  ├ lint fail on foreign files → format them, push
  ├ test fail on foreign failing-on-main tests → verify on clean main, comment on PR, merge OK
  ├ cancelled (no failed step) → gh run rerun --failed
  └ green (except smoke/ZAP) → merge
```

**Polling discipline:** bounded `time.sleep(280-295)` + single gh check per kernel call;
never sleep >300s in one call (kernel death risk); never run full pytest locally in one call.

**Conflict resolution defaults:**
- base.html script block: HEAD + add only my lines (with `?v=`).
- CHANGELOG: keep both sides, mine under the newest section.
- Tests asserting inline CSS: switch to CSS_BODY pattern.
- fixtures/_quick_seed-style long lines: wrap args one-per-line (CI ruff preference).

**Merge order:** A (#311) → 2b (#312) → 2c (#313) → 2d (#314) → hygiene (#316).
Each PR rebased on main at push time; waves NEVER parallel (base.html conflicts).

---

## 5. Risks & rollbacks

| Risk | Likelihood | Mitigation / Rollback |
|---|---|---|
| Sibling pushes break main mid-wave (again) | HIGH (every ~15 min) | Rebase-before-push; foreign failures verified against clean main before merge; my commits are atomic per feature |
| test_no_hardcoded_dates sweep touches 60 files → merge conflicts with siblings | MEDIUM | Do A before waves; keep sweep mechanical (regex-driven), rebase late |
| Cherry-picked JS assumes pre-format-sweep/DOM differences | MEDIUM | Local test run per wave; adapt assertions like #68 did |
| Kernel death on long pytest | MEDIUM | <4.5 min pytest calls; write output to /tmp file + grep; state survives in worktree not kernel |
| smoke/ZAP misread as regression | LOW | Both documented baseline-red; check main's own runs first, always |
| state-preservation macros.html conflict | HIGH (known) | Port only its bits onto current macro structure; run its 288 test lines locally |
| Rebrand rename misses a reference | LOW | post-wave grep must be 0 for old names; tests renamed too |

**Global rollback:** every wave = separate PR + separate commits → `git revert <merge-commit>`
reverts one feature cleanly; waves independent (no cross-wave code deps).

---

## 6. Definition of done (whole effort)

1. main CI run fully green except smoke + ZAP (both documented baseline).
2. `ruff check .` = 0 · `ruff format --check .` = clean on main.
3. `tests/test_no_hardcoded_dates.py` = 0 failed.
4. All 13 orphan JS modules in `app/static/` (13 = 3 from 2a + 10 from 2b/2c/2d), all wired
   in base.html with `?v={{ asset_version() }}`, zero `saskia-tooltip`/`toast-helper` refs.
5. All wave test suites green locally before push, green on CI after merge.
6. Branch census: only `main` + active-session branch remain.
7. CHANGELOG documents every wave; tickets SASKIA-311…316 filed in `docs/intake/` per rule 37
   (one ticket file per workstream, status: shipped).

## 7. Time budget
A: 1.5-2h · 2b: 2-3h · 2c: 2h · 2d: 3h · hygiene: 1h → **~10-11h total**, CI wait included.
Execute strictly in order; if session time runs out mid-wave, the plan file + this state make
the next session resumable without re-analysis.
