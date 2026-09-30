#!/usr/bin/env bash
# deploy.sh — one-command deploy of local main to the saskia-vps prod swarm.
# Usage: ./scripts/deploy.sh
# Requires: ssh access to root@38.9.96.179 via /opt/data/.ssh/id_ed25519
set -euo pipefail

REPO=/opt/data/work/saskia-app
KEY=/opt/data/.ssh/id_ed25519
VPS=root@38.9.96.179
REMOTE_DIR=/opt/build-apps/saskia-rms

cd "$REPO"

BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$BRANCH" != "main" ]; then echo "ERROR: not on main (on $BRANCH)"; exit 1; fi
if [ -n "$(git status --porcelain -- app app/static 2>/dev/null)" ]; then
  echo "ERROR: uncommitted changes in app/ — commit first:"; git status --porcelain | head -5; exit 1
fi
echo "==> HEAD: $(git log --oneline -1)"

# 1. sync source
tar --exclude='./.git' --exclude='./.venv' --exclude='__pycache__' --exclude='*.pyc' \
    --exclude='./.pytest_cache' --exclude='./.ruff_cache' --exclude='*.db' --exclude='*.sqlite*' \
    --exclude='./tests' --exclude='./herbus_drive' --exclude='./tmp' --exclude='./.env' \
    -czf /tmp/saskia-src.tar.gz .
scp -q -i "$KEY" -o StrictHostKeyChecking=no /tmp/saskia-src.tar.gz "$VPS:/tmp/"

# 2. extract + sanity: the tree must contain what we think we shipped
ssh -i "$KEY" -o StrictHostKeyChecking=no "$VPS" \
  "rm -rf $REMOTE_DIR && mkdir -p $REMOTE_DIR && tar xzf /tmp/saskia-src.tar.gz -C $REMOTE_DIR/ && rm /tmp/saskia-src.tar.gz"
LOCAL_MD5=$(md5sum app/rms/main.py | cut -d' ' -f1)
REMOTE_MD5=$(ssh -i "$KEY" -o StrictHostKeyChecking=no "$VPS" "md5sum $REMOTE_DIR/app/rms/main.py | cut -d' ' -f1")
if [ "$LOCAL_MD5" != "$REMOTE_MD5" ]; then echo "ERROR: sync mismatch (main.py md5 differs)"; exit 1; fi
echo "==> sync verified (main.py md5 match)"

# 3. build (DOCKER_BUILDKIT=0: buildkit caches COPY app even with --no-cache) + swap
ssh -i "$KEY" -o StrictHostKeyChecking=no "$VPS" \
  "cd $REMOTE_DIR && DOCKER_BUILDKIT=0 docker build --no-cache -t saskia-rms:prod -f Dockerfile . 2>&1 | tail -2 && docker service update --image saskia-rms:prod saskia-vps_web --force 2>&1 | tail -1"

# 4. verify
sleep 8
HEALTH=$(curl -s --max-time 15 https://saskia-vps.paragu-ai.com/healthz || true)
echo "==> healthz: $HEALTH"
case "$HEALTH" in
  *'"ok"'*) echo "DEPLOY OK: $(git log --oneline -1)";;
  *) echo "DEPLOY WARNING: health check did not return ok — inspect: ssh $VPS 'docker service ps saskia-vps_web'"; exit 1;;
esac
