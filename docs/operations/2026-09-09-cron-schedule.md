# 2026-09-09 Cron schedule for saskia-rms

Operational cron jobs that the operator should install on the Render
shell (or equivalent server-side scheduler). Each job calls a
script under `scripts/` and logs to `/var/log/saskia-*.log`.

## Backup (weekly, Sunday 03:00 UTC)

```cron
# Edit crontab: crontab -e
0 3 * * 0 cd /opt/data/profiles/ivan/scratch/saskia-app-work && /usr/bin/env python3 scripts/backup_cron.py >> /var/log/saskia-backup.log 2>&1
```

**Notes:**
- The script writes to `/tmp/aiw-saskia-backups/` by default. R2 sync
  is a separate concern (handled by `app/services/backup_scheduler.py`
  on app startup).
- `--retention-days 30` is the default. Override with `--retention-days N`.
- For free-tier Render: this job runs on a separate cron container, not
  inside the app container (Render's free tier doesn't include cron).
  Alternative: run via `cron-job.org` calling the backup endpoint, or
  via the Render dashboard's "Cron Jobs" feature (paid tier).

## Audit log prune (daily, 02:00 UTC)

```cron
0 2 * * * cd /opt/data/profiles/ivan/scratch/saskia-app-work && /usr/bin/env python3 scripts/audit_prune.py --days 30 >> /var/log/saskia-audit-prune.log 2>&1
```

## UptimeRobot (already configured)

The monitor id `803916096` pings `https://saskia-rms.paragu-ai.com/healthz`
every 5 minutes. No action needed.

## Monitoring + alerting

After 1 week of operation, set up alerts on:

| Endpoint | Threshold | Meaning |
|---|---|---|
| `/healthz` | 503 for >2 min | Cold-start taking too long, or container died |
| `/healthz/db` | 503 for >30s | Neon paused; first query needs resume time |
| `/healthz/schema` | drift > 0 | Migration didn't run; deploy re-trigger |
| `/healthz/errors` | last_1h > 5 | Many recent 500s; check /auditoria |

## One-shot scripts (operator, not cron)

These are run manually:

- `scripts/set_render_env.py` — push BWS-backed vars to Render
- `scripts/uptimerobot_setup.py create-all` — ensure 3 monitors exist
- `scripts/audit_prune.py --dry-run` — preview what would be deleted
- `scripts/audit_prune.py` — apply retention
- `scripts/backup.py` — full local backup with options
- `scripts/backup_cron.py` — same as above but cron-friendly (no argparse UI)
- `scripts/redact_key.py` — rotate a leaked credential
- `scripts/check_no_secrets.py` — pre-commit hook for credential leaks
- `scripts/check_render_env.py` — verify env-var parity between BWS and Render
