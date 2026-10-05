#!/bin/bash
# deploy-to-vps.sh — Build + push Sazón to ServaRica VPS in parallel run.
# Run from /opt/data/profiles/ivan/scratch/sazon-app-work/
#
# Strategy:
#   1. rsync source to VPS at /opt/build-apps/sazon-rms/
#   2. docker build on the VPS
#   3. Deploy stack with docker stack deploy
#   4. Wait for healthz to respond

set -euo pipefail

VPS_HOST="${VPS_HOST:-paragu-ai}"
REMOTE_DIR="/opt/build-apps/sazon-rms"
LOCAL_DIR="$(cd "$(dirname "$0")" && pwd)"
STACK_NAME="sazon-vps"
STACK_FILE="docker-stack.yml"

echo "▶ Syncing source to $VPS_HOST:$REMOTE_DIR"
# Use rsync if available, otherwise tar + scp
if command -v rsync >/dev/null 2>&1; then
  rsync -avz --delete \
    --exclude='.git/' \
    --exclude='.venv/' \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    --exclude='.pytest_cache/' \
    --exclude='.ruff_cache/' \
    --exclude='*.db' \
    --exclude='*.sqlite*' \
    --exclude='tests/' \
    --exclude='herbus_drive/' \
    --exclude='tmp/' \
    --exclude='.env' \
    "$LOCAL_DIR/" "$VPS_HOST:$REMOTE_DIR/"
else
  echo "  (rsync not found, using tar + scp)"
  # Create tar excluding noise
  cd "$LOCAL_DIR"
  tar --exclude='.git' \
      --exclude='.venv' \
      --exclude='__pycache__' \
      --exclude='.pytest_cache' \
      --exclude='.ruff_cache' \
      --exclude='*.db' \
      --exclude='*.sqlite*' \
      --exclude='tests' \
      --exclude='herbus_drive' \
      --exclude='tmp' \
      --exclude='.env' \
      -czf /tmp/sazon-src.tar.gz .
  scp /tmp/sazon-src.tar.gz "$VPS_HOST:/tmp/sazon-src.tar.gz"
  ssh "$VPS_HOST" "rm -rf $REMOTE_DIR && mkdir -p $REMOTE_DIR && tar xzf /tmp/sazon-src.tar.gz -C $REMOTE_DIR/ && rm /tmp/sazon-src.tar.gz"
fi

echo "▶ Building Docker image on VPS"
ssh "$VPS_HOST" "cd $REMOTE_DIR && docker build -t sazon-rms:prod ."

echo "▶ Deploying Swarm stack"
ssh "$VPS_HOST" "cd $REMOTE_DIR && docker stack deploy -c $STACK_FILE $STACK_NAME --resolve-image=never"

echo "▶ Waiting for service to start"
sleep 10

echo "▶ Checking service status"
ssh "$VPS_HOST" "docker service ls --filter name=$STACK_NAME --format 'table {{.Name}}\t{{.Replicas}}\t{{.Image}}\t{{.Ports}}'"

echo
echo "▶ Checking health endpoint via Traefik"
for i in 1 2 3 4 5; do
  sleep 5
  if curl -sk -o /dev/null -w "%{http_code}\n" --max-time 10 https://sazon-vps.paragu-ai.com/healthz 2>/dev/null | grep -q '200'; then
    echo "✓ Health check OK at https://sazon-vps.paragu-ai.com/healthz"
    break
  fi
  echo "  attempt $i: waiting..."
done

echo
echo "▶ Container logs (last 50 lines)"
ssh "$VPS_HOST" "docker service logs ${STACK_NAME}_web --tail 50" || true

echo
echo "Done. Try: https://sazon-vps.paragu-ai.com/"
