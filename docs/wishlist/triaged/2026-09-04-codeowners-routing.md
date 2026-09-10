# CODEOWNERS for review routing

**Date:** 2026-09-04
**Author:** operator (Iván)
**Cost guess:** XS
**Phase guess:** 1.5
**Source:** discovered during critical-path plan

## What

Add `/.github/CODEOWNERS`: default reviewer = operator (Iván); route `app/services/r2_backup.py` → Kiki.

## Why now

Trivial file, high signal. Once we enable branch protection, every PR auto-requests the right reviewer.


## Triage

**Moved to triaged:** 2026-09-09
**Status:** SHIPPED — `.github/CODEOWNERS` routes `app/services/r2_backup.py` → Kiki; default reviewer = operator (Iván). Verified by `tests/test_dev_tooling.test_codeowners_exists`. Commit 928f08d.
