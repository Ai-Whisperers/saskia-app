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
