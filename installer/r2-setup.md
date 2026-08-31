# Cloudflare R2 setup — encrypted backup destination

> **For Saskia (or Ivan, on her behalf) during Task 9 install.** One-time setup.
> Total time: 15-30 minutes.

## What this does

The app backs up her SQLite database to Cloudflare R2 (S3-compatible object storage)
encrypted with `age`. Free tier covers her scale by 30×. This is the **only** cloud
dependency the app has.

## Prerequisites

- Her laptop (the one with the app).
- A browser open to her Cloudflare account (or she'll create one — see step 1).
- A credit card on the Cloudflare account (R2 requires it for verification, but
  won't charge anything if usage stays in the free tier).

## Step 1 — Create a Cloudflare account (if she doesn't have one)

1. Open https://dash.cloudflare.com/sign-up
2. Email + password. Verify email.
3. Skip the "add a domain" wizard.
4. Done.

## Step 2 — Create an R2 bucket

1. In the Cloudflare dashboard, click **R2** in the left sidebar.
2. Click **Create bucket**.
3. Name it: `aiw-saskia-backups` (or any name she prefers).
4. Location: **Automatic** (cheapest, default).
5. Click **Create bucket**.
6. **Copy the bucket name and the account ID** — she'll need both.

## Step 3 — Generate an R2 API token

1. In R2 settings, click **Manage R2 API Tokens**.
2. Click **Create API token**.
3. Token name: `aiw-saskia-app` (or anything).
4. Permissions: **Object Read & Write**.
5. Bucket scope: **Apply to specific buckets** → select `aiw-saskia-backups`.
6. TTL: leave default.
7. Click **Create API Token**.
8. **Copy the Access Key ID and Secret Access Key** — these are shown ONCE. Save them.

## Step 4 — Generate the `age` encryption key on her laptop

The `age` key is what encrypts the SQLite database before upload. Without it, even
a Cloudflare breach gets ciphertext only.

**In a terminal on her laptop:**

```bash
# Install age (one-time, ~30 seconds)
# Windows PowerShell:
irm https://filippo.io/install-age | iex

# Mac:
brew install age

# Generate a key pair
age-keygen -o ~/.config/aiw-saskia/age.key

# The public key is printed to stdout. Note it.
# The private key is in ~/.config/aiw-saskia/age.key (mode 0600).
```

**Save the private key somewhere safe** (password manager, printed on paper in a
drawer, etc.). If she loses the laptop AND the key, encrypted backups are unrecoverable.

## Step 5 — Configure the app

Create `~/.config/aiw-saskia/r2.toml`:

```toml
# ~/.config/aiw-saskia/r2.toml
# Cloudflare R2 credentials (encrypted at rest by the age key, not by the OS).
# NEVER commit this file. Add to .gitignore.

[backup]
enabled = true
endpoint_url = "https://<account_id>.r2.cloudflarestorage.com"
bucket_name = "aiw-saskia-backups"
access_key_id = "<from step 3>"
secret_access_key = "<from step 3>"
age_public_key = "age1<...from step 4>"

[behavior]
min_interval_hours = 24  # don't backup more than once every 24h
keep_local_backups_days = 30  # keep last 30 days of local xlsx exports
```

Make sure permissions are restrictive:

```bash
chmod 600 ~/.config/aiw-saskia/r2.toml
chmod 600 ~/.config/aiw-saskia/age.key
```

## Step 6 — Verify with the app

1. Start the app (`run.bat` on Windows, `run.sh` on Mac).
2. Wait for the startup backup to fire.
3. Check the logs (`~/AppData/Local/AIW-Saskia/logs/app.log` on Windows,
   `~/Library/Logs/AIW-Saskia/app.log` on Mac) for: "Backup uploaded to R2: rms-backup-2026-09-XX.age"
4. Open Cloudflare dashboard → R2 → `aiw-saskia-backups` → verify a file with today's date exists.

## Restoring from R2

If her laptop dies and she wants to restore:

1. Install the app on the new laptop (clone repo, `uv sync`).
2. Get the `age` private key (from her password manager or printed copy).
3. Get the latest ciphertext from R2 (download via dashboard or `aws s3 cp`).
4. Decrypt: `age -d -i ~/.config/aiw-saskia/age.key < backup.age > rms.sqlite`
5. Place `rms.sqlite` in the data dir.
6. Restart the app. Done.

## Cost

- Free tier: 10 GB-month storage, 1M Class A ops, 10M Class B ops, **no egress fees**.
- Saskia's expected usage: ~300 MB/month.
- **Cost: $0/month, forever.**

## What if Cloudflare R2 is unavailable?

If R2 has an outage, the app falls back to local-only backups (`~/Documents/AIW-Saskia/backups/`).
She can manually copy that folder to a USB stick or external drive for offsite safety.

## What if she wants to disable cloud backup?

Set `enabled = false` in `r2.toml`. The app will skip the R2 upload and only use local backup.
She can re-enable anytime by flipping the flag.
