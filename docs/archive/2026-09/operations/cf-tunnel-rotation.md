# Cloudflare Tunnel Token Rotation Runbook

> **Audience:** the operator (Iván) running the VPS / Render side.
> **Cadence:** every **90 days** (next due: 2026-12-04, 2027-03-04, …).
> **Source of truth for the current token:** BWS secret `cloudflared_token`.

## Why rotate?

Cloudflare Tunnel tokens are long-lived bearer tokens. If one leaks
(checking out a copy of `cloudflared` to a public repo, screenshotting
a config dump, accidentally printing it in CI logs), an attacker can
stand up their own tunnel pointing at your hostname and serve phishing
pages on your domain. Rotating caps the blast radius.

The hosted deploy (Render) reads the token from BWS at container
startup; if you rotate without restarting, the running container
keeps the old token in memory.

## Pre-flight

- VPS accessible (operator + working SSH)
- Render dashboard open
- Cloudflare dashboard open for the `paragu-ai.com` zone
- BWS CLI available (`bws secret list` works)
- `scripts/save_saskia_cf_token.py` works (verifies with the existing
  one before writing the new one)

## Step-by-step

### 1. Generate a fresh token in Cloudflare

1. Open the Cloudflare Zero Trust dashboard → `Networks` → `Tunnels`.
2. Find the `sazon-tunnel` tunnel.
3. Click `...` → `Configure` → `Token` tab.
4. Click `Generate new token` (this invalidates the old one immediately).
5. **Copy the new token** — it's only shown once. Paste to a scratch
   file (`/tmp/cf-token-new.txt`). Do NOT commit it anywhere.

### 2. Stash the OLD token for rollback

The old token is now invalid, but you can recover from the old
token if you can re-generate via Cloudflare UI. Document the rotation:

```bash
# Date: 2026-09-XX
# OLD: aaa...aaa (rotated out)
# NEW: bbb...bbb (in step 3)
echo "CF token rotated 2026-09-XX (90d cadence)" \
    >> /opt/data/agents/docs/secret-rotation.log
```

### 3. Save the new token to BWS

```bash
python3 scripts/save_saskia_cf_token.py --token-file /tmp/cf-token-new.txt
# Expected output:
#   validating token against tunnel UUID ...
#   token validates (200 OK from CF API)
#   writing to BWS secret 'cloudflared_token' ...
#   done.
```

The script will:

1. Read the token from the file
2. Hit Cloudflare's tunnel metadata API to confirm the token is valid
3. Push to BWS via `secrets().update("cloudflared_token", value=..., project_ids=[...])`
4. Print success

If step 2 fails (token rejected), the script aborts before writing to
BWS. Do not bypass this — a bad token in BWS will break Render startup.

### 4. Restart the cloudflared container on VPS

```bash
# On the VPS
docker restart sazon-cloudflared
docker logs --tail 20 sazon-cloudflared
# Look for: "Registered tunnel connection" + "https://sazon-rms.paragu-ai.com"
```

If using `cloudflared` as a systemd service instead of Docker:

```bash
sudo systemctl restart cloudflared
sudo journalctl -u cloudflared --since "5 minutes ago"
```

### 5. Restart the Render service

Render's container reads `CLOUDFLARED_TOKEN` (or `AIW_SASKIA_CLOUDFLARED_TOKEN`)
from the environment, which Render populates from the linked BWS
project. After BWS update, Render's next deploy picks up the new value.

To force a redeploy without code changes:

1. Render dashboard → `sazon-rms` service
2. `Manual Deploy` → `Deploy latest commit`
3. Wait for `Live` (about 90 seconds)

### 6. Verify end-to-end

```bash
# From anywhere on the public internet
curl -fsS https://sazon-rms.paragu-ai.com/healthz
# Expected: {"status":"ok","service":"sazon-rms"}

# UptimeRobot monitor 803916096 should go back to "up" within 60s
```

Also check the audit log for any `login.failure` spikes during the
restart window — that's a sign someone's tunnel is still using the
old token. If you see spikes, immediately generate a new token and
restart.

### 7. Document the rotation

```bash
echo "$(date -u +%Y-%m-%d) CF token rotated by Iván; cadence=90d; next=2026-12-XX" \
    >> installer/SECRET-ROTATION.log
git add installer/SECRET-ROTATION.log
git commit -m "chore(ops): log CF tunnel token rotation $(date -u +%Y-%m-%d)"
```

## Rollback (if new token breaks production)

If you generate a new token and Render won't start (container exits
in 30s loop):

1. Revert the BWS update: `bws secret edit cloudflared_token --value "$(cat /tmp/cf-token-old.txt)"`
2. Render `Manual Deploy` to pick up the old token
3. Investigate: was the new token truncated in transit? Was the wrong
   tunnel ID used?

If the new token itself is corrupted, generate yet another — the
old one is already invalid in Cloudflare's view.

## Cadence reminder

Set a calendar reminder every 90 days. The next 4 rotations:

- 2026-12-04
- 2027-03-04
- 2027-06-02
- 2027-09-01

## Related

- `scripts/save_saskia_cf_token.py` — BWS writer
- `installer/ROUND-1-NOTES.md #001` — original token hygiene problem
- `docs/operations/2026-09-02-cloudflared-audit.md` — full audit trail
