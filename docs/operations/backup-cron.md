# Daily backup cron — operator runbook (B.8)

This runbook covers the host-level daily backup cron. It complements
the in-process backup that's already wired into the app's lifespan
and EOD save paths.

## Two backup layers, one operator mental model

| Layer | Trigger | Where | What it does |
|---|---|---|---|
| **In-process** (always on) | App startup + every `/eod/save` | `app/services/backup_scheduler.py` (called from `app/rms/main.py:379-382`) | If the last backup is > 24h old, run a backup. Throttled by `last_backup.json`. |
| **Host cron** (new in B.8) | Daily 03:00 UTC | `scripts/backup_cron.py` (called by `/etc/cron.d/sazon-backup`) | POSTs `/admin/backup/cron` on the live app. The endpoint is the same scheduler as the in-process layer. |

Both layers call **the same code** (`run_backup()` in
`app/services/backup_scheduler.py`) and both are **idempotent** —
if the last backup was < 24h ago, the call returns `skipped: true`
and the cron wrapper exits 0.

This is intentional: even with the in-process lifespan path, a
container that's been up for 3 days running steady traffic but never
restarting may not have a recent backup if no EOD save fires. The
host cron is the **backstop** for that case.

## Install on the VPS

```bash
# 1. Generate a strong token (only the app needs to know it; cron
#    presents it on each request). 32 random bytes → 64 hex chars.
python3 -c "import secrets; print(secrets.token_hex(32))"
# → e.g. 4a8d2f...  (treat as a password; never commit it)

# 2. Write the token to a root-only file the cron will read.
sudo install -m 0600 -o root -g root /dev/null /etc/sazon/backup-cron.token
sudo python3 -c "open('/etc/sazon/backup-cron.token','w').write('<token>')"
sudo chmod 0400 /etc/sazon/backup-cron.token

# 3. Add the token to the app's env so the endpoint accepts the
#    wrapper's request. docker-stack.yml uses an env_file, so
#    append to /opt/sazon/.env.sazon:
echo "SASKIA_CRON_BACKUP_TOKEN=<token>" | sudo tee -a /opt/sazon/.env.sazon
sudo systemctl restart sazon-app   # picks up the new env

# 4. Install the crontab. deploy.sh does this automatically; this
#    is the manual equivalent.
sudo tee /etc/cron.d/sazon-backup <<'EOF'
# /etc/cron.d/sazon-backup — daily 03:00 UTC. Exit codes 0=ok,
# 2=config, 3=backup raised, 4=app down (cron retries on 1+2+4).
SASKIA_BACKUP_URL=http://localhost:8000
SASKIA_CRON_BACKUP_TOKEN_FILE=/etc/sazon/backup-cron.token
0 3 * * * root /opt/sazon-app/.venv/bin/python /opt/sazon-app/scripts/backup_cron.py >> /var/log/sazon-cron.log 2>&1
EOF
sudo chmod 0644 /etc/cron.d/sazon-backup

# 5. Verify the install (run as root, --dry-run makes no HTTP call).
SASKIA_BACKUP_URL=http://localhost:8000 \
SASKIA_CRON_BACKUP_TOKEN_FILE=/etc/sazon/backup-cron.token \
sudo -u root /opt/sazon-app/.venv/bin/python \
    /opt/sazon-app/scripts/backup_cron.py --dry-run
```

## Verify a real run

```bash
# Force a backup (skip the 24h throttle) and watch the log:
tail -f /var/log/sazon-cron.log &
SASKIA_BACKUP_URL=http://localhost:8000 \
SASKIA_CRON_BACKUP_TOKEN_FILE=/etc/sazon/backup-cron.token \
sudo /opt/sazon-app/.venv/bin/python \
    /opt/sazon-app/scripts/backup_cron.py
```

You should see a single line of the form:

```
backup_cron: status=backup_complete skipped=false r2_uploaded=true r2_key=rms-snapshots/20261008-030000.sqlite.enc elapsed=42.3s
```

## Exit code reference

The wrapper returns a distinct exit code for each failure mode so
cron monitoring can fire the right kind of alert:

| Exit | Meaning | Cron should | On-call action |
|---|---|---|---|
| 0 | Backup ran, **or** was skipped (last < 24h) | Silent | — |
| 2 | Config error: missing env, missing token file, or endpoint returned 401/503 | Keep running, but **fix the config** | Read the log; usually a missing or rotated token |
| 3 | Backup raised (500 from endpoint) | Alert immediately | Read the log, check `/healthz/backup`, check R2 credentials |
| 4 | App unreachable (connection refused, DNS) | Retry on next tick | Confirm the app is up; if down for hours, page |

Cron itself doesn't alert on exit codes by default. To get
notifications, point the crontab `MAILTO=` at a delivery address
that routes to the on-call channel (e.g. an email-to-Telegram
gateway), or layer a separate watcher that checks the log for
non-zero exit codes every minute.

## When to call a backup manually

```bash
# Run from any host that can reach the app on the same network.
SASKIA_BACKUP_URL=https://sazon.example.com \
SASKIA_CRON_BACKUP_TOKEN=$(cat /etc/sazon/backup-cron.token) \
./scripts/backup_cron.py --json   # one JSON line for log ingestion
```

The endpoint is **idempotent** (returns `skipped: true` if the last
backup is < 24h old) so it's always safe to call. If you need a
"force" flag (e.g. right before a risky migration), use
`/admin/backup` from a logged-in browser session — that bypasses
the 24h throttle.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Exit 2, log says `cannot read SASKIA_CRON_BACKUP_TOKEN_FILE` | Token file missing or wrong perms | Re-install with mode 0400 owned by root |
| Exit 2, log says `invalid_cron_token` | Token in crontab file ≠ token in app env | Regenerate, update both, restart app |
| Exit 3, log says `backup_failed` | R2 outage or DB read error | Check `/healthz/db` and R2 console; alert if recurring |
| Exit 4, log says `Connection refused` | App is down | `docker service ps sazon_app` and restart if needed |
| Exit 0 but `skipped: true` for > 24h | The in-process path is throttling, but cron should NOT be — check that the endpoint is reachable | Likely the cron is hitting the wrong URL; verify with `--dry-run` |

## Related files

- `app/routers/health.py` — `/admin/backup/cron` endpoint
- `app/services/backup_scheduler.py` — `run_backup()` shared by both layers
- `app/rms/main.py:379-382` — lifespan-time backup trigger
- `tests/test_admin_backup_cron.py` — endpoint tests
- `tests/test_backup_cron_wrapper.py` — wrapper tests
- `scripts/deploy.sh` — installs the crontab (called by `deploy-to-vps.sh`)
