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
| Backup runs but log says `D.5 backup encryption DISABLED` | The DNI file `/etc/sazon/backup-dni` is missing or wrong perms (D.5) | See the D.5 section below |

## Related files

- `app/routers/health.py` — `/admin/backup/cron` endpoint
- `app/services/backup_scheduler.py` — `run_backup()` shared by both layers
- `app/rms/main.py:379-382` — lifespan-time backup trigger
- `tests/test_admin_backup_cron.py` — endpoint tests
- `tests/test_backup_cron_wrapper.py` — wrapper tests
- `scripts/deploy.sh` — installs the crontab (called by `deploy-to-vps.sh`)

---

# D.5 — DNI-derived backup encryption

D.5 layers AES-256-GCM encryption on top of the daily backup
pipeline. The encryption key is derived from the operator's
national ID number (DNI), not stored on disk. This means a
VPS-only breach or a VPS+R2 simultaneous breach yields
**ciphertext-without-key** — to decrypt, the attacker also
needs the DNI, which lives on a USB stick (or wherever the
operator keeps their identity).

## How it works

1. Operator writes their DNI to a single-line file on a USB
   stick (or any storage that is NOT the VPS):
   `echo "1234567" > /media/usb/sazon-dni`
2. The app reads the DNI at backup time (via the
   `AIW_RMS_BACKUP_DNI_FILE` env var, default
   `/etc/sazon/backup-dni`).
3. The DNI + a per-backup random salt are passed to
   `PBKDF2-HMAC-SHA256` with 600,000 iterations (OWASP 2023
   minimum) to derive a 32-byte AES key.
4. The SQLite snapshot is encrypted with AES-256-GCM (12-byte
   random nonce, 16-byte GCM tag). The cleartext snapshot is
   immediately deleted.
5. The R2 upload is encrypted with a fresh AES-256-GCM call
   (different salt + nonce pair — never reuse nonces).
6. The legacy `r2-encryption.key` file (Fernet, on disk) is
   deleted on the first run with DNI.

## Provisioning the DNI file

```bash
# 1. Decide where the file lives. Strong recommendation:
#    on a USB stick, NOT the VPS filesystem. The whole
#    point of D.5 is that the key is NOT on the VPS.
USB=/media/usb

# 2. On the OPERATOR's machine (not the VPS), write the DNI.
#    The DNI is the operator's national ID number. If multiple
#    operators, pick the one whose identity rotates least
#    often (rotating the DNI rotates the keyspace for old
#    backups; see "DNI rotation" below).
echo "1234567" > /tmp/sazon-dni

# 3. Copy it to the USB stick. The USB stick is the secure
#    store; the VPS file is a copy that's pinned to the stick.
cp /tmp/sazon-dni "$USB/sazon-dni"
chmod 0400 "$USB/sazon-dni"

# 4. On the VPS, create the file and chmod it. The operator
#    pastes the DNI from the USB stick to the VPS in person
#    (e.g. via SSH from a laptop that's mounted the stick).
sudo mkdir -p /etc/sazon
sudo install -m 0400 -o root -g root /dev/null /etc/sazon/backup-dni
sudo nano /etc/sazon/backup-dni   # paste the DNI, save, exit

# 5. Verify: the cron should now show "D.5 backup encryption
#    enabled" in logs instead of "DISABLED". The next backup
#    run will produce a .sqlite.enc file (encrypted) instead
#    of a .sqlite file (cleartext).
ls -l /etc/sazon/backup-dni        # should be -r-------- root root
cat /etc/sazon/backup-dni          # should print the DNI
```

## Threat model recap

| Scenario | Before D.5 | After D.5 (DNI file on USB) |
|---|---|---|
| VPS only (attacker reads `/opt/sazon/backups/`) | ❌ All sales history exposed | ✅ Snapshots are AES-256-GCM, key not on disk |
| R2 only (attacker reads R2 bucket) | ✅ Fernet-encrypted | ✅ AES-256-GCM (better cipher) |
| VPS + R2 (attacker has both) | ❌ Fernet key was on VPS, decrypts R2 | ✅ Key is on USB, not VPS — still need DNI |
| VPS + USB (attacker has the operator's machine) | ❌ Full access | ❌ Full access (key was with the data) |
| Insider (operator goes rogue) | ❌ Full access | ❌ Full access (operator knows the DNI) |

D.5 reduces the blast radius of remote-exploit scenarios. It
does NOT protect against physical access or insider threats —
that's what physical security + multi-party approval are for.

## DNI rotation (when the operator's DNI changes)

Rotating the DNI **invalidates the keyspace for every backup
made under the old DNI**. Old backups cannot be restored with
the new DNI.

**When does the DNI rotate?**

- Operator gets a new national ID (rare; mostly on citizenship
  change).
- Operator leaves the business and a new operator takes over.
- The operator suspects the DNI was leaked.

**Migration procedure:**

1. **Before** rotating, run a restore test to confirm you can
   read the latest backup with the **current** DNI. If you
   can't, don't rotate — figure out the auth problem first.
2. Download the latest R2 backup manually. Verify you can
   decrypt it on a separate machine with the current DNI:
   ```python
   from app.services.backup_crypto import decrypt_backup
   from pathlib import Path

   blob = Path("rms-snapshot-20261007-030000.sqlite.enc").read_bytes()
   plaintext = decrypt_backup(blob, "1234567")  # current DNI
   assert plaintext.startswith(b"SQLite format 3")
   ```
3. Archive all old backups to cold storage (e.g. a
   write-once optical disc, or a separate S3 bucket with
   bucket-level immutability). The DNI file + the archive
   must move together — one without the other is useless.
4. Update `/etc/sazon/backup-dni` (or the USB stick) to the
   new DNI. chmod 0400.
5. The next backup run will use the new DNI automatically.
   Old backups (under the old DNI) are now considered
   archived and are NOT touched by the regular prune.

**If you lose the old DNI before archiving:** every backup
ever made under that DNI is unrecoverable. This is the
trade-off for "key never on disk". Treat the DNI file with
the same care as the master encryption key of any other
production system.

## File location and permissions

| File | Perms | Owner | Where | Why |
|---|---|---|---|---|
| `/etc/sazon/backup-dni` | 0400 | root | VPS | App reads it at backup time |
| `/etc/sazon/backup-cron.token` | 0400 | root | VPS | Cron auth (different from DNI) |
| USB stick copy of DNI | 0400 | operator | USB | The real source of truth |

The app REFUSES to read the DNI file if it is world- or
group-readable. This is a hard check in
`app/services/backup_crypto.py:derive_key_from_dni_file`.
You'll see a `BackupCryptoError` in logs and the backup will
run unencrypted (with a loud warning) if the perms are wrong.

## What's NOT encrypted (and why)

- **`.xlsx` files** — these are the operator's monthly
  report. Encrypting them would defeat the purpose (the
  operator can't open them in Excel). The xlsx is fine in
  cleartext on the local disk; the threat is exfiltration of
  the full sales history, which the xlsx is a human summary
  of (not the source of truth).
- **`.csv` files** — same reasoning. The CSVs are the
  importable record; cleartext is a feature.
- **`.sqlite.enc` snapshots** — the source of truth. ENCRYPTED.
- **R2 `.sqlite.enc` uploads** — encrypted with a fresh
  AES-256-GCM call per upload.

## When the DNI file goes missing

The scheduler logs `D.5 backup encryption DISABLED` and runs
the backup unencrypted. The cron returns 200 (success) but
the operator should see the warning in logs and provision
the file. This is a "loud but not fatal" mode — we don't
want a missing DNI file to silently break the daily backup.

To make the warning louder, add a watch on the log line:
```bash
# In /etc/cron.d/sazon-cron-watch (separate cron, runs every 5 min):
*/5 * * * * root grep -q "D.5 backup encryption DISABLED" /var/log/sazon-cron.log && /usr/local/bin/alert-via-telegram.sh "Backups running unencrypted"
```
