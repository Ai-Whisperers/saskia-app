# /healthz/db operator runbook (E4.S4)

When the dashboard looks wrong or sales stop coming in, `/healthz/db` is the
first thing to check. It reports the live state of the database from inside
the running container — not a synthetic ping.

## Quick health check

```bash
curl -s https://saskia-vps.paragu-ai.com/healthz/db | jq
```

A 200 means the DB is reachable and the schema is consistent. A 503 means
something is wrong — read the JSON for the reason.

## What the endpoint returns

```json
{
  "db": "ok",                     // "ok" or "unreachable"
  "journal_mode": "wal",          // SQLite only — must be "wal"
  "server_version": "15.x",       // Postgres only
  "schema_version": 74,           // Current schema version (Bump in config.py on migrations)
  "schema_target": 74,            // What the code expects after migrations
  "migrations_pending": false,    // true = drift detected, run migrate
  "last_audit_at": "2026-09-30T22:11:03",  // Most recent audit row timestamp
  "elapsed_ms": 4
}
```

## Failure modes

### `{"db": "unreachable", "detail": "SELECT 1 failed"}`

The DB engine couldn't answer a trivial query. This is almost always:

1. **Disk full** — VPS disk at 100%. `df -h /` on the host. Free space or extend.
2. **Container can't reach the DB volume** — Swarm bind mount gone.
   `docker service inspect saskia-vps_web | jq '.[0].Spec.TaskTemplate.Mounts'`.
3. **Postgres connection refused** (hosted) — Supabase project paused or
   network ACL change. Check Supabase dashboard.

### `migrations_pending: true`

The DB schema version is older than the code expects. This happens when
a new image rolled out but the migration step failed silently or was
skipped. Fix:

```bash
# SSH into the VPS
ssh root@38.9.96.179
# Force a one-shot migration run inside the container:
docker exec $(docker ps -q -f name=saskia-vps_web) aiw-saskia migrate
# Verify:
curl -s https://saskia-vps.paragu-ai.com/healthz/db | jq '.migrations_pending'
```

If migrate keeps failing, the migration SQL is incompatible with the
existing schema — read the migration log, possibly restore a backup.

### `journal_mode: "delete"` (SQLite)

Concurrent writes are unsafe. Restart triggers the post-Migration
`PRAGMA journal_mode=WAL` step. If it stays "delete" after restart, the
post-migration script didn't execute — check the container startup log:

```bash
docker logs $(docker ps -q -f name=saskia-vps_web) --tail=200 | grep -i wal
```

### `last_audit_at` is hours/days old

The audit table isn't being written. Either:

1. No user activity — healthy during quiet hours.
2. The audit middleware crashed — check `/healthz/errors`.
4. The DB is in read-only state — confirm via `journal_mode` above.

## UptimeRobot probe

We use UptimeRobot to alert when `/healthz/db` returns anything other
than 200. Recommended config:

| Setting          | Value                                  |
|------------------|----------------------------------------|
| Monitor type     | HTTPS                                  |
| URL              | `https://saskia-vps.paragu-ai.com/healthz/db` |
| Monitoring interval | 5 minutes                           |
| Timeout         | 10 seconds                              |
| Alert contacts   | Telegram bot + email                   |
| Keyword check   | (none — rely on status code)           |

A 5-minute interval catches DB outages before customers notice. Don't go
below 2 minutes — UptimeRobot's free tier allows 50 monitors and we're
already using 4.

## Alert routing

Alerts come in via the AIW Telegram bot. When you see one:

1. Open the runbook above.
2. Run `curl -s https://saskia-vps.paragu-ai.com/healthz/db | jq`.
3. Follow the matching failure-mode section.
4. After fixing, watch for one more 5-minute cycle to confirm recovery.

If the alert persists > 30 min, escalate per the
`docs/operations/2026-09-08-incident-response.md` playbooks.