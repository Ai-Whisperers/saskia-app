# Customer directory / loyalty

**Date:** 2026-09-04
**Author:** operator (Iván) — moved from ROUND-1-NOTES OUT-OF-SCOPE
**Cost guess:** L
**Phase guess:** 3
**Source:** `installer/ROUND-1-NOTES.md` "Out-of-scope for Round 1"

## What

Add a `Customer` table and a "register sale to customer" UI. Customers accumulate purchase history; reportable as "top customers by spend", "customers who haven't come back in 30 days". Future: loyalty points.

## Why not now

Herbus is B2C but Saskia's current customers are walk-in repeat; she doesn't have a loyalty program. No customer table today.
## Triage

**Moved to triaged:** 2026-09-09
**Status:** SHIPPED — `app/rms/customers.py` (Customer model + loyalty points 1pt/1000 Gs + tier system) + `app/routers/customers.py` (`/clientes` route). E13.
