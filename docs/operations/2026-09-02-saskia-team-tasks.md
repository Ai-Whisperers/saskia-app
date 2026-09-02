# Saskia RMS — AIW Team Task List (Operator + Dev)

**Date:** 2026-09-02
**Companion to:** `docs/operations/2026-09-02-saskia-decision-hosted-pivot.md`

Two parallel tracks. **Operator track** = Ivan (you) — needs accounts, creds, and OKs. **Dev track** = me (the agent) — code, tests, deploys. Run them in parallel.

---

## Operator track (Ivan)

### OPR-1 — Provision managed services (~30 min)

| # | Sub-task | Service | Time | Blocked by |
|---|---|---|---|---|
| OPR-1.1 | Create Neon project | neon.tech | 5m | none |
| OPR-1.2 | Copy DATABASE_URL → BWS `SASKIA_NEON_DATABASE_URL` | BWS | 2m | OPR-1.1 |
| OPR-1.3 | Create Supabase project | supabase.com | 5m | none |
| OPR-1.4 | Copy 3 Supabase keys → BWS | BWS | 2m | OPR-1.3 |
| OPR-1.5 | Create user `saskia@paragu-ai.com` in Supabase | Supabase dashboard | 1m | OPR-1.3 |
| OPR-1.6 | Generate initial password → BWS `SASKIA_USER_PASSWORD` | local | 1m | OPR-1.5 |
| OPR-1.7 | Confirm/own `paragu-ai.com` DNS (or pick subdomain) | Cloudflare | 5m | none |
| OPR-1.8 | Create CF tunnel `saskia-rms` | Cloudflare Zero Trust | 10m | OPR-1.7 |
| OPR-1.9 | Copy tunnel token → BWS `SASKIA_CF_TUNNEL_TOKEN` | BWS | 1m | OPR-1.8 |
| OPR-1.10 | Connect Render to saskia-app repo | render.com | 5m | none |
| OPR-1.11 | Paste 11 env vars to Render | Render dashboard | 5m | OPR-1.2/1.4/1.9 |
| OPR-1.12 | Generate `SASKIA_R2_FERNET_KEY` → BWS | local (`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`) | 1m | none |

**Acceptance:** all 11 env vars visible in Render dashboard.

### OPR-2 — Apply schema + smoke test (~25 min)

| # | Sub-task | Tool | Time | Blocked by |
|---|---|---|---|---|
| OPR-2.1 | Apply schema to Neon | `uv run python -c "from app.rms.db_dialect import make_engine, get_metadata; e=make_engine('<DATABASE_URL>'); get_metadata().create_all(e)"` | 2m | OPR-1.11 |
| OPR-2.2 | Wait for Render deploy to go green | Render dashboard | 5-10m | OPR-1.11 |
| OPR-2.3 | `curl https://<URL>/healthz` → 200 | curl | 1m | OPR-2.2 |
| OPR-2.4 | `curl https://<URL>/login` → 200 + HTML form | curl | 1m | OPR-2.3 |
| OPR-2.5 | Log in via browser, verify dashboard renders | browser | 2m | OPR-2.4 |
| OPR-2.6 | Restart service, verify R2 backup fires | Render dashboard + logs | 5m | OPR-2.5 |
| OPR-2.7 | Add UptimeRobot monitor | uptimerobot.com | 2m | OPR-2.5 |

**Acceptance:** all 6 protected routes return 200 with valid session cookie.

### OPR-3 — Send Saskia the WhatsApp messages (~10 min)

| # | Sub-task | Reference | Time |
|---|---|---|---|
| OPR-3.1 | Send Message 1 (initial setup) | `docs/operations/2026-09-02-saskia-agent-messages.md` | 2m |
| OPR-3.2 | Wait for her "I logged in" reply | WhatsApp | varies |
| OPR-3.3 | Send Message 2 (first-login walkthrough) | same file | 2m |
| OPR-3.4 | Wait 24h | — | 24h |
| OPR-3.5 | Send Message 3 (daily use) | same file | 2m |
| OPR-3.6 | Wait 7d | — | 7d |
| OPR-3.7 | Send Message 4 (week 1 check-in) | same file | 2m |

**Acceptance:** Saskia has logged in, registered ≥1 product, registered ≥1 sale.

### OPR-4 — Round 1 review (after 5-7 days of use)

| # | Sub-task | Reference |
|---|---|---|
| OPR-4.1 | Capture Saskia's feedback in `installer/ROUND-1-NOTES.md` | (template to be created — see DEV-7) |
| OPR-4.2 | Triage items: blocker / major / minor / cosmetic | same file |
| OPR-4.3 | Hand off to DEV for fixes | issues/PRs |

**Acceptance:** Round 1 review template filled in, items triaged.

---

## Dev track (the agent — me)

### DEV-1 — Schema migration runner (1h, optional)

**Already mostly done.** `db_dialect.make_engine()` + `db_dialect.get_metadata()` + `lifespan()` in `main.py` handle this. Verify:

- [ ] `init_db(engine)` (Postgres variant) creates all 8 tables
- [ ] Migration runner from `db.py` works with Postgres (if any MIGRATIONS dict exists)
- [ ] PR if any changes needed

**Verification gate:** `uv run pytest tests/ --no-cov` (325 pass) + new test `tests/test_postgres_schema.py` that runs `metadata.create_all` against a fresh Neon dev branch and asserts all 8 tables exist.

### DEV-2 — R2 backup end-to-end verification on Postgres (2h)

Already implemented. Verify:

- [ ] On Render startup, `backup_scheduler.run_backup()` fires
- [ ] R2 upload succeeds (Fernet-encrypted)
- [ ] app_meta row `backup_last_r2_at` is updated
- [ ] Test against the actual Render deploy (not just mocks)

**Verification gate:** new test in `tests/test_r2_integration.py` that round-trips: snapshot Postgres state, download from R2, decrypt, compare.

### DEV-3 — Smoke test the hosted auth flow (3h)

**Largest gap in current test coverage.** Current tests use `SASKIA_TEST_AUTH_DISABLED=1` (test bypass). For hosted we need:

- [ ] Test Supabase JWT verification against a real (test-project) Supabase instance
- [ ] Test refresh-token rotation
- [ ] Test password reset flow
- [ ] Test that expired JWTs are rejected
- [ ] Test that wrong JWKS keys are rejected

**Verification gate:** all auth tests pass without `SASKIA_TEST_AUTH_DISABLED` env var.

### DEV-4 — CF Tunnel health-check (1h)

CF Tunnel needs to verify Render is healthy:

- [ ] Add `/healthz/deep` endpoint that checks DB + R2 reachable
- [ ] Update CF tunnel config to use `/healthz/deep` for origin health
- [ ] Document in `installer/cf-tunnel-setup.md`

**Verification gate:** tunnel stays up after Render service restart (CF retries).

### DEV-5 — Operator runbook (2h)

**The "operator paste these commands" doc** so OPR can execute without thinking:

- [ ] `docs/operations/2026-09-02-saskia-deploy-runbook.md` — step-by-step with exact commands, copy-pasteable, no narrative
- [ ] Each step has: command, expected output, "if it fails, do X"

**Verification gate:** OPR follows it cold and gets to "app live" without asking.

### DEV-6 — Update INSTALLER to recommend hosted (1h)

The current `installer/README.md` is for local-first. Update:

- [ ] Add a "Hosted (recommended)" section at the top
- [ ] Keep local section for users who want it
- [ ] Update `installer/run.bat` to detect if hosted URL is reachable and redirect browser there
- [ ] Update installer docs/screenshots for hosted

**Verification gate:** new operator reading README sees hosted path first.

### DEV-7 — Round 1 review template (30m)

`installer/ROUND-1-NOTES.md` was referenced in the status report but doesn't exist on disk:

- [ ] Create the file with the template (similar to `docs/sessions/round-2-feedback.md`)
- [ ] Include: blocker/major/minor/cosmetic severity ladder, status legend, sign-off section
- [ ] Reference the v1 plan task 10 + Round 2 doc structure

**Verification gate:** file is committed, links work from `installer/README.md`.

### DEV-8 — Saskia-personal-context Drive sync (3h, blocked)

Blocked on Saskia's Drive URL (per `20260831_173309_c84c4e` session bookend).

- [ ] When Saskia provides URL: read 5 xlsx files (Productos, Recetas, Ingredientes, Movimientos, etc.)
- [ ] Map columns to schema (per `docs/operations/import-mapper.md`)
- [ ] Test import_xlsx round-trip against the xlsx
- [ ] Run the importer on hosted Neon (via admin route or one-time script)

**Verification gate:** import succeeds, all 5 files' rows visible in `/inventario`, `/recetas`, `/productos`.

### DEV-9 — Test isolation for Postgres path (1h)

Current tests use SQLite (`conftest.py` sets `DATABASE_URL=sqlite:///:memory:`). For hosted:

- [ ] Add Postgres test path (use a Neon dev branch or testcontainers)
- [ ] Verify all 325 tests pass against both SQLite and Postgres
- [ ] CI matrix: `[sqlite, postgres]`

**Verification gate:** GitHub Actions CI runs both backends, both pass.

### DEV-10 — Pre-commit guard against credential patterns (1h)

**Operator requested** — to prevent future token-in-config-file leaks.

- [ ] Add `scripts/check-no-secrets.py` that scans staged files for token shapes
- [ ] Hook into `.pre-commit-config.yaml` as a local hook
- [ ] Document in `AGENTS.md` rule #11

**Verification gate:** trying to commit a file containing `ghp_*` or `x-access-token:` fails pre-commit.

---

## Dependency graph

```
DEV-5 (runbook) → OPR-2 (smoke test)
DEV-7 (template) → OPR-4 (Round 1 review)
OPR-1.1 (Neon) → OPR-1.2 → OPR-1.11
OPR-1.3 (Supabase) → OPR-1.4 → OPR-1.5 → OPR-1.6 → OPR-1.11
OPR-1.7 (DNS) → OPR-1.8 → OPR-1.9 → OPR-1.11
DEV-1, DEV-2, DEV-3, DEV-4, DEV-9 all feed into the deploy readiness check
DEV-6 makes the installer hosted-aware (cosmetic)
DEV-8 is blocked on Saskia's Drive URL
DEV-10 is independent — security hardening, ship anytime
```

**Critical path:** OPR-1.x → DEV-5 (runbook) → OPR-2 (smoke) → OPR-3 (Saskia messages) → OPR-4 (Round 1)

---

## Hour budget vs. 200h plan

| Item | Original plan hours | Actual | Variance |
|---|---|---|---|
| Milestone 1 (hosted foundation) | 25h | TBD | TBD |
| Milestone 1.5 (auth gate) | 0 (not in original plan) | already done (5h) | +5h (security gap closed early) |
| Milestone 2 (Fase 1 features in hosted) | 50h | TBD | TBD |
| Total toward hosting | 75h | TBD | TBD |

Per the `200h-plan.md`: **43h used / 200h budget = 21.5%** at last STATUS.md check. We have 157h left.

---

## Acceptance for "hosted is live for Saskia"

When ALL of these are true, we can say "she just logs in":

- [ ] Render service is "Live" (green) and has been for 24h with no restarts
- [ ] `/healthz` returns 200 from UptimeRobot continuously
- [ ] Saskia has logged in at least once
- [ ] Saskia has registered ≥1 product and ≥1 sale
- [ ] R2 backup has fired at least once successfully
- [ ] Saskia has confirmed she can see her data after a browser refresh
- [ ] Operator (Ivan) has confirmed no alerts in 48h

---

## Sign-off

When this list is complete:

> *Hosted pivot live. Saskia just logs in.*
> AI Whisperers (operator): ___________________________ date: ___________

---

*Generated 2026-09-02 per `docs/operations/2026-09-02-saskia-decision-hosted-pivot.md`. Companion to Round 1 review template at `installer/ROUND-1-NOTES.md` (DEV-7).*