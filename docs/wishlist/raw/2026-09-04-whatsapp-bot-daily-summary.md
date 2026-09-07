# WhatsApp bot for daily sales summary

**Date:** 2026-09-04
**Author:** operator (Iván) — moved from ROUND-1-NOTES OUT-OF-SCOPE section
**Cost guess:** M
**Phase guess:** 2
**Source:** `installer/ROUND-1-NOTES.md` "Out-of-scope for Round 1"

## What

At end-of-day, send Saskia a WhatsApp message: "Hoy vendiste Gs. X.XXX.XXX en N ventas. Top producto: X (N unidades)." Twilio/Baileys integration.

## Why now

Saskia is the only user and she's physically at the shop every day — she can already see her sales in the app. The bot is for the days she doesn't open the laptop. Defer until she asks for it.

## Repro / context

- Needs a `daily-summary` endpoint that returns the message payload.
- WhatsApp integration is a separate cost line. Evolution API (already wired for AIW team) could be reused if Saskia agrees to use it.
