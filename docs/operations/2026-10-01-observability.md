# Tier 8 — Observability & alerting (2026-10-01)

Saskia RMS paged the operator (you) when something went wrong. Two
channels, both opt-in via env vars:

- **Sentry** — error tracking + performance (free tier 5K events/mo)
- **Resend** — transactional email for backup / EOD / migration
  anomalies (free tier 100/day, 3K/month)

Both are gated: leave the env var blank and the feature is off. No
runtime crash, no surprise bills.

## What gets paged

| Trigger | Severity | Where it fires |
|---|---|---|
| Migration apply failed on startup | error | `app/rms/main.py` lifespan |
| Backup scheduler exception | critical | `app/rms/main.py` lifespan |
| EOD anomaly: cash zero with active sales | info | `POST /eod/anomalies/run` |
| EOD anomaly: high voided rate (>10%) | warn | same |
| EOD anomaly: factura without number | error | same |
| EOD anomaly: negative grand total | critical | same |

EOD anomalies are detected by `app/services/eod_anomaly.py`. To
trigger them manually, POST `/eod/anomalies/run` (also reachable via
the EOD checklist page once the operator wires the button — see
BACKLOG #29).

The mutation in `app/observability/alerts.py` is a single chokepoint
with `MAX_ALERTS_PER_DAY=50` to prevent a runaway loop from flooding
the inbox.

## One-time setup

1. **Resend** (5 min):
   - Sign up at https://resend.com with `ivan@aiwhisperers.dev`
   - Verify the `aiwhisperers.dev` domain (Resend asks for a DNS TXT)
   - Create an API key (Settings → API Keys)
   - Store in BWS as `resend-api-key`
   - Export at deploy time: `RESEND_API_KEY=...`

2. **Sentry** (10 min):
   - Sign up at https://sentry.io (free tier)
   - Create a FastAPI project, copy the DSN
   - Store in BWS as `sentry-dsn`
   - Export at deploy time: `SENTRY_DSN=...`

3. **Wire to deploy**:
   - In `docker-compose.yml` (or Swarm service spec), add:
     ```yaml
     environment:
       SENTRY_DSN: ${SENTRY_DSN}
       SENTRY_ENVIRONMENT: production
       RESEND_API_KEY: ${RESEND_API_KEY}
       ALERT_EMAIL_TO: ivan@aiwhisperers.dev
     ```
   - Restart the service: `docker service update --env-add RESEND_API_KEY=... saskia-vps_web`

## Verifying the wiring

After deploy, you should see these in the startup logs:

```
Sentry: initialized (env=production)
MIGRATIONS: applied (schema_version=97, code=97)
backup scheduler: ...
```

Then trigger a test by:
1. Backing up a sale without an `invoice_number` (or breaking R2
   creds so the backup fails) — the next restart should email you
   a `[saskia-error]` / `[saskia-critical]` subject.
2. The test endpoint is `POST /eod/anomalies/run` — no auth bypass
   needed if the SASKIA_TEST_AUTH_DISABLED path is wired.

## Cost

- Sentry free tier: $0 (5K events/mo, 1 project)
- Resend free tier: $0 (100 emails/day, 3K/month)
- One bakery producing ~30 sales/day = ~30 EOD checks per month
  = well within free tier.

## Failure modes

- **Resend down**: `send_alert` returns False, logs a warning.
  Sentry captures the same call site as a breadcrumb so you still
  see the alert attempt in the Sentry UI.
- **Sentry down**: errors still land in `loguru` (stderr/journald).
  Sentry is the "polished" view, loguru is the source of truth.
- **Both down**: app keeps running. The lifespan exception handlers
  swallow alert failures; nothing about the alert path can crash
  the app.

## What's NOT in Tier 8 (deferred to Tier 9+)

- Daily EOD check cron (currently manual via `/eod/anomalies/run`)
- Telegram / Slack notifications (Saskia only uses email + WhatsApp)
- Alert dedup / rate limiting per anomaly-key
- Operator runbook for handling each alert type (the email body
  contains the next-step hint; the runbook would be the longer
  version)
