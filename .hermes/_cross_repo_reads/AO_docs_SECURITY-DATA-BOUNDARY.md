# Data Boundary & Local-Processing Policy (GLD-16)

> Codifies which workloads may touch cloud plans, which require local processing, and what may never leave the boundary. Companion to `docs/GLD14-15-16-VENDOR-DIVERSITY-SPECS.md` (probe data rules).

## Tier rules

| Tier | Workload class | Allowed surfaces |
|---|---|---|
| **T1 LOCAL-ONLY** | Patient-identifiable data, clinical records, anything covered by a client NDA naming data residency | Jan / local weights / client-on-prem deployments only. Concrete tooling (verified 2026-09-25): [openmed](https://github.com/maziyarpanahi/openmed) (Apache-2.0, clinical NER + de-id on-device), [VoiceStudio](https://github.com/debpalash/VoiceStudio) (AGPL-3.0 — internal use only, never embed in a hosted product) |
| **T2 CLOUD-PLAN** | Operational + content work: SEO drafts, marketing copy, research digests, code | Paid flat plans (zai coding endpoint today; MiniMax when provisioned) |
| **T3 NEVER-ANYWHERE-FREE** | Credentials, auth material, client-identifying datasets | Paid surfaces only; free tiers/gateways have the weakest data guarantees |

## Rules

1. **Default when in doubt**: T1 — if a client would recognize the content as theirs, it stays local.
2. **Free-tier routing** (GLD-14 probe): dual-run sidecars may carry only synthetic/public fixtures, never live org or client content.
3. **Bench fixtures** (`eval/bench/`): synthetic only by construction — safe on any plan.
4. **Prompts are a data surface**: job prompts referencing client names/PII make that job T1. Check the PROMPT.md, not just the code.
5. **Vendor terms gate**: NOASSERTION-license or unaudited-terms surfaces (see GLD-15 memo) are T3 regardless of content until reviewed.

## Current compliance snapshot (2026-09-25)

- Canary jobs (research briefs, tracker): T2 ✓ — prompts reference org-internal state, no client PII.
- Ometz voice stack (parked, GLD-17): will be **T1 by rule 1** when revived — design for local/on-prem inference.
- Outreach scripts (GLD-18): Kiki sends from her account; scripts contain personalization slots, no client data → T2 for drafting, human-channel for sending.
