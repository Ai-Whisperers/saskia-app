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
