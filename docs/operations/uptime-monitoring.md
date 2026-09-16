# Uptime Monitoring — Saskia RMS

> **For**: Ivan (operator), Kiki (any future build agent)
> **Purpose**: Detect outages before Saskia notices. Single source of truth for `/healthz*` endpoints, UptimeRobot configuration, and alert routing.

## TL;DR

| Endpoint | URL | Returns | Status code on failure |
|---|---|---|---|
| `/healthz` | `https://saskia-rms.paragu-ai.com/healthz` | `{status, service}` | 503 during cold-start (5–30s) |
| `/healthz/db` | `https://saskia-rms.paragu-ai.com/healthz/db` | DB connectivity + schema drift + last audit | 503 if DB unreachable |
| `/healthz/schema` | `https://saskia-rms.paragu-ai.com/healthz/schema` | `code_version` vs `db_version` drift count | 500 if drift > 0 |
| `/healthz/deps` | `https://saskia-rms.paragu-ai.com/healthz/deps` | Env-var fingerprints + package versions | never fails (debug-only) |

**UptimeRobot monitor id**: `803916096` (5-min interval, probes `/healthz`, keeps Render free-tier container warm).
**Alert channel**: WhatsApp Evolution API → Ivan's phone.

---

## Endpoints

### `/healthz` — process liveness

Cheap. Returns:
- **200**: app finished lifespan, ready to serve traffic.
- **503** (`{"status": "warming_up", ...}`): cold-start in progress. This is **expected** for 5–30 seconds after Render spins the container up.

UptimeRobot pings every 5 min so the container stays warm. If you see a 503 storm (more than 1 per minute), something is wrong — see [Cold-start storm](#cold-start-storm).

### `/healthz/db` — database health

Returns:
```json
{
  "db": "ok",
  "dialect": "sqlite",
  "journal_mode": "wal",
  "schema_version": 13,
  "code_schema_version": 13,
  "migrations_pending": 0,
  "last_audit_at": "2026-09-08 05:06:56.193969"
}
```

| Field | Meaning | Operator action when wrong |
|---|---|---|
| `db` | `"ok"` or `"error"` | 503 → DB unreachable. Check Render dashboard logs. |
| `dialect` | `"sqlite"` (local) or `"postgresql"` (hosted) | If hosted reports `sqlite`, env var `DATABASE_URL` is missing. |
| `journal_mode` | SQLite WAL mode | Anything other than `wal` is a bug — fix in `app/rms/db.py`. |
| `schema_version` | Current DB schema | Compare with `code_schema_version`. |
| `code_schema_version` | Latest migration in code | Should match `schema_version`. |
| `migrations_pending` | `code_version - db_version` | `> 0` = drift. Redeploy to auto-apply (init_db runs in lifespan). |
| `last_audit_at` | Most recent audit-log row | If stale (>24h), writes have stopped. Check app. |

### `/healthz/schema` — drift detector

Returns:
```json
{
  "code_version": 13,
  "db_version": 13,
  "drift": 0,
  "status": "in_sync"
}
```

**Returns 500 when `drift > 0`**. This is intentional — UptimeRobot / health-check tools trigger an alert on non-200.

### `/healthz/deps` — env fingerprint (debug-only)

Returns env-var **lengths and SHA-256 first-8-chars only** — never values. Used to debug "did the deploy pick up the new env vars?" without leaking secrets.

---

## UptimeRobot configuration

| Field | Value |
|---|---|
| Monitor ID | `803916096` |
| URL | `https://saskia-rms.paragu-ai.com/healthz` |
| Method | `HEAD` (locked in by commit `f1af406` — see `tests/test_hotfix_regressions.py`) |
| Interval | 5 minutes |
| Timeout | 30 seconds |
| Keyword (success) | (none — accept any 200) |
| Alert contacts | Ivan's email + WhatsApp Evolution |

**Why HEAD, not GET**: Render free tier counts HEAD against the request budget but the response body is empty, so it's cheaper.

**Why 5 min, not 1 min**: Render's free tier sleeps after 5 min of no traffic. 5-min probes = 100% uptime + always warm.

### Scripting it

`scripts/uptimerobot_setup.py` reads the API key from BWS at runtime and is **idempotent**: pause / resume / verify the monitor without re-creating it. Always run before manually editing UptimeRobot via the dashboard — keeps BWS as the source of truth.

```bash
uv run python scripts/uptimerobot_setup.py --verify   # show current state
uv run python scripts/uptimerobot_setup.py --pause    # if doing maintenance
uv run python scripts/uptimerobot_setup.py --resume   # after maintenance
```

---

## Alert routing

When `/healthz` or `/healthz/db` returns non-200 for **3 consecutive probes** (15 minutes), UptimeRobot fires an alert to:

1. **Ivan's email** — primary.
2. **WhatsApp Evolution webhook** → Ivan's phone — secondary.

The Evolution webhook URL is stored in `scripts/daily_summary.py` config (BWS-backed). It posts a JSON message with:
```
🚨 saskia-rms DOWN
endpoint: /healthz
consecutive_failures: 3
last_response_code: 503
last_response_body: {"status": "warming_up", ...}
dashboard: https://dashboard.uptimerobot.com/monitors/803916096
```

If you don't see the WhatsApp alert within 1 minute, check the Evolution log: `https://saskia-rms.paragu-ai.com/ops/status` (operator-only, see `/ops/status` route).

---

## Diagnostic flowchart

When Saskia reports a problem, walk this in order:

```
Saskia: "el sistema no anda"
  │
  ├─→ curl -I https://saskia-rms.paragu-ai.com/healthz
  │     ├─ 200 ──→ app is alive; problem is in the route or her browser
  │     │           check Render logs for stack traces
  │     └─ 503 ──→ cold-start or startup failure
  │
  ├─→ curl https://saskia-rms.paragu-ai.com/healthz/db | jq
  │     ├─ "migrations_pending": 0 ──→ schema is in sync
  │     └─ "migrations_pending": >0 ──→ redeploy (init_db auto-applies)
  │
  ├─→ curl https://saskia-rms.paragu-ai.com/healthz/schema | jq
  │     ├─ "drift": 0 ──→ schema OK
  │     └─ "drift": >0 ──→ same as above
  │
  ├─→ curl https://saskia-rms.paragu-ai.com/healthz/deps | jq
  │     ├─ env vars present ──→ config OK
  │     └─ missing SUPABASE_* ──→ env vars dropped; check Render dashboard
  │
  └─→ Render dashboard → service logs → look for stack trace
        └─→ copy + paste to Kiki for triage
```

For the full incident playbook, see `docs/operations/2026-09-08-incident-response.md`.

---

## Common incidents

### Cold-start storm

**Symptom**: 503 on `/healthz` or `/static/app.css` for 5–30 seconds after a quiet period.
**Why**: Render free tier sleeps after 5 min idle. Spin-up takes 5–30s. UptimeRobot ping + readiness gate = first request after a sleep waits, then everything works.
**Mitigation**: UptimeRobot 5-min probe (already in place). If you see it once and the site now loads, this is expected. If it happens multiple times per hour, upgrade Render to Standard ($7/mo).

### Schema drift (`migrations_pending > 0`)

**Symptom**: `/healthz/db` returns `migrations_pending: N>0`.
**Why**: Code was deployed with new migrations, but the DB hasn't been migrated. Or: `init_db()` failed silently.
**Mitigation**: Redeploy. `init_db()` runs in the lifespan and applies pending migrations. If redeploy doesn't fix it, run `aiw-saskia migrate` from the Render shell.

### Write silence (`last_audit_at` stale)

**Symptom**: `last_audit_at` > 24 hours old in normal operation.
**Why**: Either nothing is being written (real problem if sales are happening) or `record()` in `app/rms/audit.py` is throwing silently.
**Mitigation**: Open `/auditoria` (operator only). If empty, check Render logs for `audit_log` exceptions.

---

## What this runbook does NOT cover

- **Application-level bugs** (sale math wrong, missing ingredient, etc.) → use `/ops/status` + `/auditoria` + Kiki.
- **Performance** (slow queries, timeouts) → see `docs/operations/2026-09-09-performance-analysis.md`.
- **Security incidents** → see `docs/operations/2026-09-08-incident-response.md` and the AIW `aod` workflow.

---

## Maintenance

- **Monthly**: verify UptimeRobot still pings `/healthz` and the alert contact is correct (people change phones).
- **On schema-version bump**: redeploy. `/healthz/db` will show `migrations_pending: 0` once `init_db()` runs.
- **On new endpoint addition**: update the table at the top of this doc.
- **On Render plan change**: re-evaluate probe interval (Standard tier can sleep less aggressively, may not need warming probes).

---

**Doc version:** 2026-09-16 v1 (initial — closes E3.S4)
**Owner:** Ivan (operator), with runbook updates from Kiki (build agent)