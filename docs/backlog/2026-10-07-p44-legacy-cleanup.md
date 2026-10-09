# P44 — Legacy code cleanup pass (2026-10-07)

## Goal
Remove or archive legacy/dead code identified during the channel
cleanup pass. The codebase has accumulated ~10 files that are no
longer imported anywhere — leftover from a half-finished Phase-2B
domain-package refactor (commit fb57f00 broke models; everything
fell back to `models_legacy.py`).

## Findings (10 dead files, ~1,200 lines)

**A. Migration files duplicated in `db.py` (7 files, ~250 lines).**
db.py defines ALL 111 migration functions inline AND has a MIGRATIONS
dict that references them. The standalone migration files below are
NOT imported by db.py or anything else — they are pure dead code:

| File | Migration # | Why dead |
|------|---|---|
| `_005_customer.py` | 5 | inline in db.py:3204 |
| `_006_simple_test.py` | 6 | inline in db.py (registered as `_006_waste_log`) |
| `_043_branding_setting.py` | 43 | inline in db.py:1962 |
| `_044_message_templates.py` | 44 | inline in db.py |
| `_057_recipe_instructions.py` | 57 | inline in db.py:2571 |
| `_061_tag_validation.py` | 61 | inline in db.py:3147 |
| `_062_audit_repair.py` | 62 | inline in db.py:2840 |

Note: `_056_bank_reconciliation.py` LOOKS dead but `db.py:2563` does a
lazy `from app.rms.migrations._056_bank_reconciliation import` inside a
function. Keep.

**B. Phase-2B model submodules never adopted (3 files, ~770 lines).**
A Phase-2B refactor (fb57f00) split `models.py` into `app/rms/models/`
submodules but broke things; the system reverted to `models_legacy.py`
re-exported from `models/__init__.py`. The submodules never had their
imports wired up. All three are dead:

| File | Lines | Description |
|------|---|---|
| `app/rms/models/catalogs_restored.py` | 307 | Catalog/config models (Phase 2B) |
| `app/rms/models/herbus_drive.py` | 273 | HEREBUS drive sync models |
| `app/rms/models/procurement.py` | 188 | Procurement models |

**C. Service module never wired (1 file, ~113 lines).**
`app/services/auto_backup.py` is only referenced in
`docs/archive/2026-09/operations/2026-09-fase-1-specs.md` (an archived
spec). No code imports it.

## Action (revised 2026-10-08)

1. **Already done in PR #54** (commit `a93a699b`): copies of 10 files
   saved to `app/_archive/2026-10-07-p44-legacy-cleanup/` plus
   `app/_archive/README.md`.

2. **This commit (2026-10-08)**: `git rm` the 9 actually-dead files
   from their original locations:
   - 7 dead migration files (replaced by inline functions in `db.py`)
   - 3 dead model submodules (Phase 2B refactor leftovers)

3. **Skip** `app/services/auto_backup.py` — it IS used by 39 tests
   in `tests/test_auto_backup.py` + `tests/test_backup_cfg_override.py`.
   Also remove the duplicate copy from the archive directory
   (operators don't need to recover what's still in active code).

## Verification (2026-10-08)

- `git grep` for any reference to the 9 removed files in `app/`/`tests/`:
  - Only CHANGELOG.md mentions exist (history pointers, not imports).
- `app/rms.migrations` package still auto-discovers the same 41
  migrations (none of the dead files had a function in the same
  version slot as an inline replacement... wait, `_006_simple_test`
  is in slot 6; the inline `_migration_006_waste_log` is in `db.py`'s
  local MIGRATIONS dict. Confirmed via `app/rms/db.py:4661` that the
  runner uses the db.py dict, not the pkgutil one).
- `ruff check` clean (re-running the auto_backup test file imports
  is fine — the function is still importable from `app/services/`).

## Out of scope (deferred)
- The inline migrations themselves in `db.py` (lines 1-3100) — moving
  them to per-file form is Phase 2B redo territory. Not this commit.
- Pre-existing ruff findings in `db.py` / `models_legacy.py` — many
  (B904, BLE001, I001, F401, F811, F821, ANN001, S110, DTZ005, E501).
  Some are real bugs; this commit doesn't address them. Mechanical
  refactor sweep is its own task.
- `models_legacy.py` (2,914 lines) and `db.py` (4,844 lines) split —
  Phase 2B redo territory.

## Acceptance
- All 10 files moved to archive
- `git grep` for any reference (at any pointer, including docs) shows
  nothing unexpected
- All existing tests pass (100/100 P4x + held_sale + etc)
- `ruff check` clean on the archive (the moved files retain their
  original state but don't add new findings to the active codebase)

## Branch
polish/saskia-p0 (continues from P43).## Correction (2026-10-08)

`app/services/auto_backup.py` is **NOT** dead — it is imported by:
- `tests/test_auto_backup.py` (9 tests)
- `tests/test_backup_cfg_override.py` (3 tests)

Keep it in app/. This P44 commit moves only the 9 actually-dead files
and leaves `auto_backup.py` where it is.
