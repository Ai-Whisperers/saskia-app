# Upgrade tiers — what's in / what's out / what costs what

> **For operator (Ivan) and any future agent.** Reference doc listing the realistic
> upgrade paths for the Saskia engagement, with their costs and trade-offs.

## TL;DR

**Fase 1 is local-first with encrypted Cloudflare R2 backup (Tier 1 + Tier 8).**
**$0/month, forever.** All other upgrades either cost money, change the quote, or
add complexity that's not needed for Saskia's scale.

## Tier matrix

| Tier | What | Cost/month | Solves | Quote violation? |
|---|---|---|---|---|
| 1. Local-first + free upgrades | current + Drive sync + restore tests | $0 | A: laptop death | No |
| 8. Cloudflare R2 encrypted backups | local DB + encrypted blob in R2 | $0 (free tier) | A, E (partial) | No (storage ≠ hosting) |
| 2. Supabase Storage backups | local DB + encrypted blob in Supabase Storage | $25 | A, E (partial) | No |
| 3. Supabase Free DB | move DB to Supabase Postgres | $0 | A, C | **Yes** (hosting) |
| 4. Supabase Pro DB | full cloud migration | $25 | A, B, C, D, E | **Yes** |
| 5. Turso Free DB | move DB to hosted libSQL | $0 | A, C | **Yes** |
| 6. Turso Developer DB | hosted libSQL, more headroom | $5 | A, C, B/D partial | **Yes** |
| 7. Claude API for LLM | smart features (planning, recipes) | ~$1-5 | F: LLM features | **Yes** (new vendor) |

## Definitions

- **A:** Laptop death safety (data survives physical laptop loss)
- **B:** Phone access (view from mobile)
- **C:** Multi-device sync (2+ devices, same data)
- **D:** Multi-user (employees entering sales)
- **E:** Cloud-managed security (trust SOC2 vendor)
- **F:** LLM features (smart suggestions, planning)
- **G:** Production observability (logs, metrics)

## Tier 1: free local-first upgrades (already specced, some implemented)

- Tier 1.1: Encrypted local backup to second folder (USB stick or second drive)
- Tier 1.2: Scheduled cloud-backup to her existing Google Drive (every hour)
- Tier 1.3: Restoration test script (`make test-restore`)
- Tier 1.4: GitHub Actions CI (already done in saskia-app)
- Tier 1.5: Pre-commit hooks (already done in saskia-app)
- Tier 1.6: loguru + structured JSON logs (already done)

**Total: 6 free upgrades; 3 already implemented; 3 to add (~3.5h of build time).**

## Tier 8: Cloudflare R2 encrypted backups (CHOSEN for fase 1)

- Local DB stays on her laptop.
- On startup (if last R2 backup > 24h): encrypt SQLite with `age`, upload to R2.
- Free tier: 10 GB-month storage, 1M Class A ops, 10M Class B ops.
- Saskia's usage: ~30 backups/month × 10MB = 300 MB. Well inside free tier.
- **Total: $0/month, forever.**

## Tier 2: Supabase Storage backups (alternative to Tier 8)

- Same architecture as Tier 8, but using Supabase Storage instead of Cloudflare R2.
- $25/month (Pro plan minimum).
- Slightly less generous free tier than R2.
- Worse trade-off for Saskia (more expensive, same OPSEC outcome).

**Verdict: skip. Tier 8 is better.**

## Tier 3-6: Cloud DB migration (NOT CHOSEN for fase 1)

- All four (Supabase Free, Supabase Pro, Turso Free, Turso Developer) require
  moving the DB off her laptop.
- All four violate the quote's "Hosting / ops monthly: Gs. 0. Not this product."
- All four require Saskia's informed consent (her data moves to third-party servers).
- All four introduce internet dependency (every sale entry requires HTTPS).
- All four increase the OPSEC surface (third-party custody).

**Verdict: not without renegotiating the quote with Saskia.**

## Tier 7: Claude API for LLM features (DEFER to Fase 1.5+)

- Adds recipe scaling, menu planning, ingredient substitution, sales language translation.
- Costs ~$1-5/month at her scale (depending on usage).
- Adds latency (1-3 seconds per Claude call).
- Adds new vendor (Anthropic).
- Adds OPSEC surface (Anthropic sees her data; not used for training by default, but on their servers).

**Verdict: defer. The planning assistant is parked at Gs. 9.500.000; that's where Claude belongs if at all.**

## What I will not do without explicit operator override + quote renegotiation

- ❌ Swap SQLite for any cloud DB (Tier 3-6)
- ❌ Add Claude API calls (Tier 7)
- ❌ Add any monthly hosting of any kind
- ❌ Move PII to third-party services without Saskia's consent

## What I CAN do without renegotiation

- ✅ Tier 1: any free local upgrade
- ✅ Tier 8: encrypted Cloudflare R2 backup
- ✅ Fase 1.5 enhancements that don't change the quote (e.g., more reports, better UX)

## Decision framework for future upgrades

When the operator considers adding a Tier:
1. Does it cost money recurring? If yes → renegotiate the quote.
2. Does it move PII to a third party? If yes → get Saskia's consent.
3. Does it add latency to daily use? If yes → measure impact.
4. Does it violate the locked scope? If yes → check the quote.
5. Does it make the app better for HER specifically? If no → skip.

If all five pass, it's a Tier 1 or Tier 8 candidate.
