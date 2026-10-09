#!/usr/bin/env bash
# deploy.sh — one-command deploy of local main to the sazon-vps prod swarm.
# Usage: ./scripts/deploy.sh [--dry-run] [--repo=PATH]
#
# Flags:
#   --dry-run     Print each step without making any network calls or
#                 running remote commands. Exits 0 on success.
#   --repo=PATH   Override the source repo (default: /opt/data/work/sazon-app).
#                 In --dry-run mode this MUST be set so tests can point
#                 at a fixture repo.
#
# Requires: ssh access to root@38.9.96.179 via /opt/data/.ssh/id_ed25519
set -euo pipefail

REPO=/opt/data/work/sazon-app
KEY=/opt/data/.ssh/id_ed25519
VPS=root@38.9.96.179
REMOTE_DIR=/opt/build-apps/sazon-rms
DRY_RUN=0

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --repo=*)  REPO="${arg#*=}" ;;
    -h|--help)
      sed -n '2,/^set -euo/p' "$0" | sed '$d'
      exit 0
      ;;
    *) echo "ERROR: unknown flag '$arg'"; exit 2 ;;
  esac
done

# Helper: run a shell command locally OR print it (dry-run).
# In dry-run mode every step is printed but NOT executed. SSH/scp/remote
# calls print their full arg list so tests can assert on what would
# happen without touching the network.
run() {
  if [ "$DRY_RUN" = "1" ]; then
    echo "DRY: $*"
  else
    "$@"
  fi
}

cd "$REPO"

# Branch + uncommitted-change checks run AFTER arg parsing so --help
# works from any worktree. The actual deploy still hard-requires main
# (you can't deploy from a feature branch by accident).
BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$BRANCH" != "main" ]; then echo "ERROR: not on main (on $BRANCH)"; exit 1; fi
if [ -n "$(git status --porcelain -- app app/static 2>/dev/null)" ]; then
  echo "ERROR: uncommitted changes in app/ — commit first:"; git status --porcelain | head -5; exit 1
fi
echo "==> HEAD: $(git log --oneline -1)"

# 1. sync source
TAR_FILE=/tmp/sazon-src.tar.gz
if [ "$DRY_RUN" = "1" ]; then
  echo "DRY: tar --exclude=... -czf $TAR_FILE ."
else
  tar --exclude='./.git' --exclude='./.venv' --exclude='__pycache__' --exclude='*.pyc' \
      --exclude='./.pytest_cache' --exclude='./.ruff_cache' --exclude='*.db' --exclude='*.sqlite*' \
      --exclude='./tests' --exclude='./herbus_drive' --exclude='./tmp' --exclude='./.env' \
      -czf "$TAR_FILE" .
fi
run scp -q -i "$KEY" -o StrictHostKeyChecking=no "$TAR_FILE" "$VPS:/tmp/"

# 2. extract + sanity: the tree must contain what we think we shipped
run ssh -i "$KEY" -o StrictHostKeyChecking=no "$VPS" \
    "rm -rf $REMOTE_DIR && mkdir -p $REMOTE_DIR && tar xzf /tmp/sazon-src.tar.gz -C $REMOTE_DIR/ && rm /tmp/sazon-src.tar.gz"

# bash parameter expansion, not `cut`: the dry-run test sandboxes PATH to a
# minimal coreutils set that deliberately lacks cut/awk.
LOCAL_MD5="$(md5sum app/rms/main.py)"; LOCAL_MD5="${LOCAL_MD5%% *}"
if [ "$DRY_RUN" = "1" ]; then
  echo "DRY: would compare remote md5 (skipping network)"
  REMOTE_MD5="$LOCAL_MD5"
else
  REMOTE_MD5=$(ssh -i "$KEY" -o StrictHostKeyChecking=no "$VPS" "md5sum $REMOTE_DIR/app/rms/main.py | cut -d' ' -f1")
fi
if [ "$LOCAL_MD5" != "$REMOTE_MD5" ]; then echo "ERROR: sync mismatch (main.py md5 differs)"; exit 1; fi
echo "==> sync verified (main.py md5 match)"

# 3. build (DOCKER_BUILDKIT=0: buildkit caches COPY app even with --no-cache) + swap
# 2026-10-06: this script historically tagged the build as sazon-rms:prod
# but the service in the swarm was originally started with a different
# tag (legacy name from before the rename) and later with date-based
# phase tags. Updating the service to 'sazon-rms:prod' silently no-ops
# because that tag doesn't exist on the remote after the rename, so
# the orchestrator resolves to the current image and reports
# 'converged' without actually swapping.
# Fix: tag the new build as sazon-rms:prod (kept for the script
# contract) AND with a unique date-based name. Use the date tag in
# the service update so the new build actually gets rolled in.
DEPLOY_TAG="deploy-$(date -u +%Y%m%d-%H%M%S)"
run ssh -i "$KEY" -o StrictHostKeyChecking=no "$VPS" \
    "cd $REMOTE_DIR && DOCKER_BUILDKIT=0 docker build --no-cache -t sazon-rms:prod -t $DEPLOY_TAG -f Dockerfile . 2>&1 | tail -2 && docker service update --image $DEPLOY_TAG saskia-vps_web --force 2>&1 | tail -1"

# 4. verify
if [ "$DRY_RUN" = "1" ]; then
  echo "DRY: would curl https://sazon-vps.paragu-ai.com/healthz (skipping network)"
  echo "DRY-RESULT: deploy would have been initiated successfully"
  exit 0
fi
sleep 8
HEALTH=$(curl -s --max-time 15 https://sazon-vps.paragu-ai.com/healthz || true)
echo "==> healthz: $HEALTH"
case "$HEALTH" in
  *'"ok"'*)
    echo "DEPLOY OK: $(git log --oneline -1)"
    # 5. B.8 — install/refresh the daily backup cron.
    # The cron is idempotent (it's just a file in /etc/cron.d/) and
    # only runs once per day at 03:00 UTC, so re-installing on every
    # deploy keeps it in sync with any changes to the wrapper script.
    # The cron token lives in /etc/sazon/backup-cron.token (mode 0400,
    # root-only) and is created on first run; on subsequent deploys
    # we leave it alone.
    run ssh -i "$KEY" -o StrictHostKeyChecking=no "$VPS" '
      set -e
      if [ ! -f /etc/sazon/backup-cron.token ]; then
        echo "==> first deploy: generating SASKIA_CRON_BACKUP_TOKEN"
        mkdir -p /etc/sazon && chmod 0700 /etc/sazon
        python3 -c "import secrets; print(secrets.token_hex(32))" \
          > /etc/sazon/backup-cron.token
        chmod 0400 /etc/sazon/backup-cron.token
        # Append to the env file the swarm service reads (deploy.sh
        # uses .env.sazon; adjust the path if your stack uses a
        # different env file).
        ENV_FILE=/opt/sazon/.env.sazon
        if [ -f "$ENV_FILE" ] && ! grep -q SASKIA_CRON_BACKUP_TOKEN "$ENV_FILE"; then
          echo "SASKIA_CRON_BACKUP_TOKEN=$(cat /etc/sazon/backup-cron.token)" >> "$ENV_FILE"
          echo "==> appended SASKIA_CRON_BACKUP_TOKEN to $ENV_FILE (restart needed to pick up)"
        fi
      fi
      cat > /etc/cron.d/sazon-backup <<EOF
# /etc/cron.d/sazon-backup — daily 03:00 UTC. See docs/operations/backup-cron.md
SASKIA_BACKUP_URL=http://localhost:8000
SASKIA_CRON_BACKUP_TOKEN_FILE=/etc/sazon/backup-cron.token
0 3 * * * root $REMOTE_DIR/.venv/bin/python $REMOTE_DIR/scripts/backup_cron.py >> /var/log/sazon-cron.log 2>&1
EOF
      chmod 0644 /etc/cron.d/sazon-backup
      echo "==> cron installed: $(ls -l /etc/cron.d/sazon-backup)"
      # Smoke test the wrapper — --dry-run exits 0 with no HTTP call.
      SASKIA_BACKUP_URL=http://localhost:8000 \\
      SASKIA_CRON_BACKUP_TOKEN_FILE=/etc/sazon/backup-cron.token \\
        $REMOTE_DIR/.venv/bin/python $REMOTE_DIR/scripts/backup_cron.py --dry-run
    '
    ;;
  *) echo "DEPLOY WARNING: health check did not return ok — inspect: ssh $VPS 'docker service ps saskia-vps_web'"; exit 1;;
esac