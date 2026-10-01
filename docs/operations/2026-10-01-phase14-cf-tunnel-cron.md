# CF-Tunnel liveness cron — Phase 14 (2026-10-01)

## What this is

`scripts/cf_tunnel_liveness.py` runs three probes (public URL, DNS,
local container healthz/db) and exits with one of:

| Exit | Class | Action |
|---:|---|---|
| 0 | all healthy | none |
| 1 | CF-Tunnel flap (local ok, public bad) | **Do NOT redeploy.** Fix cloudflared / Traefik / DNS. |
| 2 | DNS drift (CNAME no longer points to CF-tunnel) | Check NS + CNAME records |
| 3 | Local app unhealthy | Redeploy is appropriate |
| 4 | script error / config missing | Debug the script |
| 5 | catastrophic (all 3 fail) | Check VPS + cloudflared daemon + CF account |

The script is intentionally **read-only** — it doesn't redeploy, restart,
or modify any state. It only reports. The cron that fires it should
decide what to do with each exit class.

## Cron registration

The AIW cron fleet already manages `aiw-*-monitor-30min` jobs (see
`cron-fleet-governance` skill). To wire this:

1. File the line — pick the 30-min cadence cron already running on the
   VPS host:
   ```yaml
   # /etc/cron.d/aiw-cron-fleet — add this entry
   */30 * * * * root cd /opt/build-apps/saskia-rms && \
     /opt/build-apps/saskia-rms/.venv/bin/python \
     scripts/cf_tunnel_liveness.py --quiet >> \
     /var/log/aiw/saskia-cf-tunnel.log 2>&1
   ```

2. Wire alert — exit-1/2/5 should page Ivan via the existing
   `aiw-ops-monitor` alert pipeline. Exit-3 should fire the existing
   `aiw-engineering-monitor` (app class). Edit
   `/etc/cron.d/aiw-cron-fleet-alerts`:
   ```yaml
   * * * * * root /opt/aiw/bin/alert-classify.sh \
     --source=saskia-cf-tunnel \
     --exit-from-log=/var/log/aiw/saskia-cf-tunnel.log
   ```

3. Test the alert path — run `scripts/cf_tunnel_liveness.py` with a
   bogus `SASKIA_PUBLIC_URL` to force exit 1, confirm the alert fires,
   then revert.

## Why --quiet + log file (not stdout)

The fleet's log aggregator tails `/var/log/aiw/*.log` and parses
one-line records. `--quiet` outputs exactly one line with the
exit-code-relevant status bits, so log parsing is trivial.

## Why not in the LMS app's own /healthz?

`/healthz` and `/healthz/db` are already in the app — they prove
*container* health. CF-Tunnel health is a *different* layer; it
needs to be checked from outside (or via `dig`) so it can detect
edge failures that the container cannot see.

## Known limitations

- No `dig` on the cron host → DNS probe is skipped (returns `ok`).
  If a DNS flap is the suspected cause, run the script manually on
  the operator's machine which has `dig` installed.
- Local probe uses `127.0.0.1:LOCAL_PROBE_PORT`. The default 8080
  matches the Dockerfile `EXPOSE`. If the deploy changes the
  internal port, set `SASKIA_LOCAL_HEALTH_PORT` env var.
- No rate limiting — the script makes 1 HTTPS request + 1 DNS query
  per run. Safe at 30-min cadence.

## Verification

After deploying the cron, wait 30 minutes for the first run. Confirm:

```bash
tail -f /var/log/aiw/saskia-cf-tunnel.log
```

You should see one line per run with `[OK]` for a healthy state. If
any run shows `[FAIL]` with `public=FAIL local=OK`, the CF-Tunnel
flap class was caught — proceed per the diagnosis message.