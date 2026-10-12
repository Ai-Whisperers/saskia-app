# Sazón State — read this first (not the repo tree)

> **Purpose**: every "analyze the saskia/sazón app" session starts here (~500 tokens) instead of
> rebuilding ~100k tokens of context. **Update rule**: any PR that changes schema/deploy/CI state
> updates this file in the same PR. Last verified: 2026-10-12.

## Repo & environments

- Repo: `Ai-Whisperers/saskia-app` (main). Worktrees under `/opt/data/work/saskia-app*` — sibling
  Hermes sessions may be mid-work in them; check `git status` before touching.
- Schema: **121** on main (`CURRENT_SCHEMA_VERSION`, app/rms/config.py). Chain: 118 recipe_backfill,
  119 photo_autolink, 120 shop_whatsapp_rename, 121 seasonal_event. NO GAPS allowed in numbering;
  migrations apply pre-migration archives (rule 17), `sazon rollback` undoes the last one.
- Deploys: dev auto on merge (deploy-dev), test/prod manual promote. As of 10-12: **dev healthy**;
  test/prod were at schema 117 → promoting main applies 118–121.
- CI (10 checks): the pre-deploy-dev fast gate requires **root `CHANGELOG.md`** touched whenever
  `app/|scripts/|tests/|.github/` change; ci.yml FAILS if `app/CHANGELOG.md` reappears (single-changelog
  doctrine, #155). deploy-dev's public-healthz step can race the rolling update — rerun before debugging.

## Recent state (2026-10-12)

- Merged: #152 (SASKIA-212 recipes), #154 (SASKIA-215/216 renumbered 120/121), #155 (docs dedupe),
  #157 (SASKIA-217 seasonal calendar), #158 (SASKIA-220 tenant middleware — opt-in, no-op without
  `/etc/sazon/tenants/`), #159/#161 lineage (SASKIA-211a gates + costing cleanup).
- Architecture decision SASKIA-210: per-client instances (one site+DB per client), NOT multi-tenant.
- ONE root CHANGELOG.md; one AGENTS.md (root); Vale styles flattened.

## Known debt / gotchas

- SaleStockMove (app/rms/models/sales.py) is a deprecated stub — table deleted in migration 092;
  use raw SQL/text() for Sale-adjacent new code (relationships don't resolve at mapper-config time).
- `seed_sazon(overwrite=False)` is NOT idempotent on populated DBs (duplicate catalog + synthetic
  sales). Operator script guards with exit 2 + `--force`. Always VACUUM INTO backup before seeding prod.
- Sibling collisions: sessions share checkouts. Rebase off `origin/main`, and VERIFY the branch
  still differs from main before any force-push (a reset-to-main branch rebases "cleanly" to empty
  and kills the PR — happened to #156 on 10-12).
- GH auth: PAT in BWS `GITHUB_PAT_AIW_DEPLOY_2026_09_10`; GH App install token rotates ~1h
  (mint via `skills/github-app-rotation/scripts/get_installation_token.py`).

## Where deeper history lives

- CHANGELOG.md (root) — full ship history, newest first
- docs/operations/, docs/plans/ — dated analyses
- Hermes session corpus: `Ai-Whisperers/hermes-corpus` (snapshot) — only if this doc + CHANGELOG
  don't answer it. Do NOT re-derive repo state by scanning the tree when this file answers it.
