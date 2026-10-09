# Makefile with setup / test / lint / run

**Date:** 2026-09-04
**Author:** operator (Iván)
**Cost guess:** XS
**Phase guess:** 1.5
**Source:** discovered during critical-path plan

## What

Add a `Makefile` at repo root: `setup`, `test`, `lint`, `run`, `migrate`.

## Why now

Reduces onboarding friction. One `make test` instead of remembering the `uv run pytest --cov=app --cov-report=term` incantation.


## Triage

**Moved to triaged:** 2026-09-09
**Status:** SHIPPED — `Makefile` with 18 targets (install, test, test-verbose, test-coverage, lint, lint-fix, format, check, serve, migrate, seed, seed-reset, backup, fixtures, clean, ci-smoke, pre-commit, stats). Verified by `tests/test_dev_tooling.test_makefile_entry_points`. Commit 928f08d.
