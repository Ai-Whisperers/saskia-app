# Time-zone field on Sale + groupby timezone

**Date:** 2026-09-04
**Author:** operator (Iván) — discovered during E4.S2 design
**Cost guess:** S
**Phase guess:** 1.5
**Source:** `app/services/reports.py` uses server time; no `tz` field on Sale

## What

Add a `tz: str` column to `Sale`. Today everything groups by server time, which is fine while Render stays UTC, but breaks the day boundary when future instances live in different timezones.

## Why now

While we're touching Sale for the daily-trend chart. Single-column addition; no migration backfill needed.
