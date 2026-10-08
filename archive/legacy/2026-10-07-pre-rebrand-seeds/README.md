# Pre-rebrand seeds (2026-10-07 audit)

**Status as of 2026-10-07:** NO files in this directory are kept as
load-bearing. This directory is a **placeholder** for any future
pre-rebrand seeds that get archived.

## The decision

The `scripts/seed_vaquita_holandesa_for_saskia.py` script + its regression
test `tests/test_seed_vaquita_holandesa_for_saskia.py` were initially
flagged for archival in the 2026-10-07 audit (because both files contain
the pre-rebrand "Saskia" name). After multi-hat analysis they were
**kept as load-bearing**:

- The script is the **operator-facing re-seed workflow** for the
  "Vaquita Holandesa" catalog (the Dutch-PY bakery catalog the
  Sazón business runs). Removing it would orphan the production
  re-seed flow documented in `docs/operations/`.
- The test asserts the script **refuses to corrupt user data** by
  exiting with code 2 if the DB is already populated — a real safety
  guard against operator accidents.
- The "Vaquita" name is the **catalog name**, not the operator
  brand. The post-rebrand operator brand is "Sazón RMS" (the
  "Saskia" mention in the script and test was updated to "Sazón"
  in commit A3.1).

## What changed in commit A3.1

- `scripts/seed_vaquita_holandesa_for_saskia.py` — narrative brand
  mentions updated from "Saskia" → "Sazón RMS". The script name
  itself is unchanged ("Vaquita" is the catalog, not the brand).
- `tests/test_seed_vaquita_holandesa_for_saskia.py` — narrative
  brand mentions + the `"Saskia" in text` assertion updated to
  expect "Sazón" instead.
- This directory remains empty except for `.keep` and this README.
  The 2 files initially placed here by the A3 subagent (an
  accidental duplicate) were removed in A3.1.
