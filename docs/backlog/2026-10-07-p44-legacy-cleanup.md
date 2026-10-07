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

## Action
Move all 10 files to `app/_archive/2026-10-07-p44-legacy-cleanup/`.
Create `app/_archive/README.md` pointing operators to the archive if
they need to recover anything. **Don't delete** in case there's a
recovery scenario; archive instead.

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
polish/saskia-p0 (continues from P43).