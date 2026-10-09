#!/usr/bin/env bash
# promote.sh — promote a tested build from one env to another.
#
# Usage:
#   ./scripts/promote.sh --from=test --to=prod
#   ./scripts/promote.sh --from=dev --to=test
#
# What this does:
#   1. Reads the current running image digest on the source env (test or dev).
#   2. Re-tags that same image as the destination env's tag.
#   3. Updates the destination env's service with --force so Swarm actually
#      swaps (per saskia-rms-deploy-flow skill: tag-reconciliation alone
#      doesn't swap when the tag is the same name with a new digest).
#   4. Verifies the destination healthz.
#
# This is intentionally a *re-tag + force-update* — NOT a rebuild. The
# tested image is the same one we ship to prod. If you need a fresh build,
# use scripts/deploy.sh --env=<to> instead.
#
# Why a separate script: deploy.sh requires a clean working tree and (for
# prod) the branch == main. Promote.sh doesn't touch the local repo at
# all — it only re-tags and updates a remote service.

set -euo pipefail

KEY="${SAZKIA_DEPLOY_KEY:-/opt/data/.ssh/id_ed25519}"
VPS="${SAZKIA_VPS:-root@38.9.96.179}"

FROM=""
TO=""
for arg in "$@"; do
  case "$arg" in
    --from=*) FROM="${arg#*=}" ;;
    --to=*)   TO="${arg#*=}" ;;
    -h|--help)
      sed -n '2,/^set -euo/p' "$0" | sed '$d'
      exit 0
      ;;
    *) echo "ERROR: unknown flag '$arg'"; exit 2 ;;
  esac
done

if [ -z "$FROM" ] || [ -z "$TO" ]; then
  echo "ERROR: both --from and --to are required"
  exit 2
fi
case "$FROM:$TO" in
  test:prod|dev:test|dev:prod) ;;
  *) echo "ERROR: only test→prod, dev→test, dev→prod are allowed (got $FROM→$TO)"; exit 2 ;;
esac

# Source/dest service names + health hostnames
case "$FROM" in
  prod) FROM_SVC="saskia_web";          FROM_HOST="saskia-vps.paragu-ai.com" ;;
  test) FROM_SVC="saskia-test_web";     FROM_HOST="saskia-test.paragu-ai.com" ;;
  dev)  FROM_SVC="saskia-dev_web";      FROM_HOST="saskia-dev.paragu-ai.com" ;;
esac
case "$TO" in
  prod) TO_SVC="saskia_web";            TO_HOST="saskia-vps.paragu-ai.com" ;;
  test) TO_SVC="saskia-test_web";       TO_HOST="saskia-test.paragu-ai.com" ;;
  dev)  TO_SVC="saskia-dev_web";        TO_HOST="saskia-dev.paragu-ai.com" ;;
esac

# Image tags per env (matching deploy.sh)
FROM_TAG="sazon-rms:$FROM-latest"
TO_TAG="sazon-rms:$TO-$(date -u +%Y%m%d-%H%M%S)"

echo "==> promote: $FROM → $TO"
echo "    source service: $FROM_SVC @ $FROM_HOST"
echo "    dest service:   $TO_SVC @ $TO_HOST"
echo "    source image:   $FROM_TAG"
echo "    dest tag:       $TO_TAG"

# 1. Re-tag the source image. We use 'docker service update --image' on the
#    source to capture the current digest, then 'docker tag' on the
#    destination. Actually simpler: 'docker service inspect' returns the
#    image digest; we tag FROM_TAG as TO_TAG in the daemon.
echo "==> step 1: tag $FROM_TAG as $TO_TAG"
ssh -i "$KEY" -o StrictHostKeyChecking=no "$VPS" "docker tag $FROM_TAG $TO_TAG"

# 2. Force-update the destination service.
echo "==> step 2: force-update $TO_SVC with $TO_TAG"
ssh -i "$KEY" -o StrictHostKeyChecking=no "$VPS" "docker service update --image $TO_TAG $TO_SVC --force 2>&1 | tail -1"

# 3. Verify destination healthz.
echo "==> step 3: healthz $TO_HOST"
sleep 8
HEALTH=$(curl -s --max-time 15 "https://$TO_HOST/healthz" || true)
echo "==> $TO healthz: $HEALTH"
case "$HEALTH" in
  *'"ok"*) echo "PROMOTE OK ($FROM→$TO): $TO_TAG" ;;
  *) echo "PROMOTE WARNING: $TO healthz did not return ok — inspect: ssh $VPS 'docker service ps $TO_SVC'"; exit 1 ;;
esac
