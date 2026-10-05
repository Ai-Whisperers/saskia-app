# Merma / waste tracking

**Date:** 2026-09-04
**Author:** operator (Iván) — moved from ROUND-1-NOTES OUT-OF-SCOPE
**Cost guess:** S
**Phase guess:** 1.5
**Source:** `installer/ROUND-1-NOTES.md` "Out-of-scope for Round 1"

## What

Capture waste/spoilage events: an ingredient was discarded with reason and quantity. Reports: merma per ingredient per week, merma cost per month, top-reason breakdown.

## Why now

Quick to ship: one new `WasteEvent` table, one `/merma` route, one monthly report. Would catch real money leaks the operator doesn't currently measure.

## Repro / context

- Could fold into E5 (Fase 1.5) if the operator agrees it's worth a sprint.
- The audit log (E3.S1) is a good fit for the event record itself.
## Triage

**Moved to triaged:** 2026-09-09
**Status:** SHIPPED — `app/rms/waste.py` (WasteLog + WasteReason enum + cost-denormalized impact) + `app/routers/merma.py` (`/merma` route + monthly report). E22.
