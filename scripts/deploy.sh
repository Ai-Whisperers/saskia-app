#!/usr/bin/env bash
# deploy.sh — one-command deploy to a saskia-* swarm stack.
#
# Usage:
#   ./scripts/deploy.sh --env=prod                      # ships main to saskia-vps.paragu-ai.com
#   ./scripts/deploy.sh --env=test                      # ships current branch to saskia-test
#   ./scripts/deploy.sh --env=dev                       # ships current branch to saskia-dev
#   ./scripts/deploy.sh --env=dev --branch=feat/foo     # checks out feat/foo first (if clean)
#   ./scripts/deploy.sh --env=prod --dry-run            # print every step, run nothing
#   ./scripts/deploy.sh --env=test --repo=/path/to/repo # use a different local checkout
#
# Branches:
#   --env=prod  REQUIRES current branch == main, and the tree must be clean
#                under app/ and app/static/. Build is from whatever main HEAD is.
#   --env=test  Allows any local branch. CI also auto-deploys test on PR open.
#   --env=dev   Allows any local branch. CI auto-deploys dev on push to non-main.
#                (The CI workflow lives in .github/workflows/deploy-dev.yml.)
#
# Stacks on the VPS:
#   saskia      → saskia-vps.paragu-ai.com    (saskia-prod-data volume)
#   saskia-test → saskia-test.paragu-ai.com   (saskia-test-data volume)
#   saskia-dev  → saskia-dev.paragu-ai.com    (saskia-dev-data volume)
#
# Requires:
#   - ssh access to root@38.9.96.179 via /opt/data/.ssh/id_ed25519
#   - bws CLI at /usr/local/bin/bws on the VPS (for write_env_file.py)
#   - the deploy/render_stack.py and deploy/write_env_file.py scripts (synced
#     with this file via the tar at the top of step 1)

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KEY="${SAZKIA_DEPLOY_KEY:-/opt/data/.ssh/id_ed25519}"
VPS="${SAZKIA_VPS:-root@38.9.96.179}"
REMOTE_DIR="/opt/build-apps/sazon-rms"
DRY_RUN=0
ENV=""
BRANCH=""

for arg in "$@"; do
  case "$arg" in
    --env=*)   ENV="${arg#*=}" ;;
    --branch=*) BRANCH="${arg#*=}" ;;
    --dry-run) DRY_RUN=1 ;;
    --repo=*)  REPO="${arg#*=}" ;;
    -h|--help)
      sed -n '2,/^set -euo/p' "$0" | sed '$d'
      exit 0
      ;;
    *) echo "ERROR: unknown flag '$arg'"; exit 2 ;;
  esac
done

if [ -z "$ENV" ]; then
  echo "ERROR: --env is required (prod | test | dev)"
  exit 2
fi
case "$ENV" in
  prod|test|dev) ;;
  *) echo "ERROR: --env must be one of prod|test|dev, got '$ENV'"; exit 2 ;;
esac

# Helper: run a shell command locally OR print it (dry-run).
run() {
  if [ "$DRY_RUN" = "1" ]; then
    echo "DRY: $*"
  else
    "$@"
  fi
}

cd "$REPO"

# Branch + uncommitted-change checks. Prod is the strictest; test/dev allow
# in-flight feature branches.
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ -n "$BRANCH" ] && [ "$BRANCH" != "$CURRENT_BRANCH" ]; then
  if [ -n "$(git status --porcelain)" ]; then
    echo "ERROR: --branch=$BRANCH requested but working tree is dirty; commit or stash first"
    exit 1
  fi
  run git checkout "$BRANCH"
  CURRENT_BRANCH="$BRANCH"
fi

case "$ENV" in
  prod)
    if [ "$CURRENT_BRANCH" != "main" ]; then
      echo "ERROR: --env=prod requires branch=main (currently on $CURRENT_BRANCH)"
      exit 1
    fi
    if [ -n "$(git status --porcelain -- app app/static 2>/dev/null)" ]; then
      echo "ERROR: --env=prod has uncommitted changes in app/ — commit first:"
      git status --porcelain | head -5
      exit 1
    fi
    if [ "$(git rev-parse HEAD)" != "$(git rev-parse origin/main)" ]; then
      echo "ERROR: --env=prod requires HEAD == origin/main (run: git pull --ff-only)"
      exit 1
    fi
    ;;
  test|dev)
    # Allow any local branch; CI will push to test/dev. The local branch is
    # what gets shipped.
    if [ -n "$(git status --porcelain -- app app/static 2>/dev/null)" ]; then
      echo "WARN: --env=$ENV has uncommitted changes in app/ — those will NOT be deployed (tar excludes .git/.venv, but staged-and-uncommitted is in the worktree). Commit first."
    fi
    ;;
esac

echo "==> HEAD: $(git log --oneline -1)"

# 1. sync source. We tar the WHOLE repo (including deploy/) so the VPS gets
#    render_stack.py and write_env_file.py alongside the app code.
TAR_FILE=/tmp/sazon-src.tar.gz
if [ "$DRY_RUN" = "1" ]; then
  echo "DRY: tar ... -czf $TAR_FILE ."
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

# 3. Write the env file (BWS-driven) and render the stack file.
#    These are run on the VPS (not here) so the BWS access token stays put.
#    The stack name and service name are env-specific (saskia, saskia-test, saskia-dev).
ENV_FILE_HOST="/etc/sazon/.env.${ENV}"
STACK_FILE="/tmp/docker-stack.${ENV}.yml"
DEPLOY_TAG="${ENV}-$(date -u +%Y%m%d-%H%M%S)"

# Stack name is env-specific: prod=saskia (keeps the existing live service
# stable), test=saskia-test, dev=saskia-dev. Service = stack_name + "_web".
case "$ENV" in
  prod) STACK_NAME="saskia"; SERVICE_NAME="saskia_web" ;;
  test) STACK_NAME="saskia-test"; SERVICE_NAME="saskia-test_web" ;;
  dev)  STACK_NAME="saskia-dev";  SERVICE_NAME="saskia-dev_web" ;;
esac

# Compute the per-env hostname for the health check.
HOSTNAME=""
case "$ENV" in
  prod) HOSTNAME="saskia-vps.paragu-ai.com" ;;
  test) HOSTNAME="saskia-test.paragu-ai.com" ;;
  dev)  HOSTNAME="saskia-dev.paragu-ai.com" ;;
esac

run ssh -i "$KEY" -o StrictHostKeyChecking=no "$VPS" "
  set -e
  cd $REMOTE_DIR

  # Render the stack file from the template + envs.yaml.
  python3 deploy/render_stack.py --env=$ENV --output=$STACK_FILE

  # Write the env file from BWS. Idempotent — only rewrites if changed.
  python3 deploy/write_env_file.py --env=$ENV

  # Build the image. DOCKER_BUILDKIT=0 because buildkit caches the COPY
  # layer even with --no-cache. Per-env image tag so the running service
  # can be pinned to the just-built image.
  DOCKER_BUILDKIT=0 docker build --no-cache \
    -t sazon-rms:$ENV-latest \
    -t sazon-rms:$DEPLOY_TAG \
    -f Dockerfile . 2>&1 | tail -3

  # Stack deploy. --resolve-image=never so the new image (just-built) is
  # picked up; we use the per-env 'latest' tag, not the date tag, so
  # 'docker stack rm' / 'docker stack deploy' is idempotent.
  docker stack deploy -c $STACK_FILE $STACK_NAME --resolve-image=never 2>&1 | tail -3

  # Force the service to swap to the new image. Per the saskia-rms-deploy-flow
  # skill, Swarm's tag-reconciliation alone won't swap when the tag is the
  # same name with a new digest — --force is mandatory.
  docker service update --image sazon-rms:$DEPLOY_TAG $SERVICE_NAME --force 2>&1 | tail -1
"

# 4. verify
if [ "$DRY_RUN" = "1" ]; then
  echo "DRY: would curl https://$HOSTNAME/healthz (skipping network)"
  echo "DRY-RESULT: deploy to $ENV would have been initiated"
  exit 0
fi
sleep 8
HEALTH=$(curl -s --max-time 15 "https://$HOSTNAME/healthz" || true)
echo "==> $ENV healthz: $HEALTH"
case "$HEALTH" in
  *'"ok"'*)
    echo "DEPLOY OK ($ENV): $(git log --oneline -1)"
    # 5. install/refresh the daily backup cron (prod only — test/dev have
    # their own shorter retention schedules in envs.yaml but they share the
    # same cron wrapper, which we install per-env below).
    run ssh -i "$KEY" -o StrictHostKeyChecking=no "$VPS" "
      set -e
      ENV=$ENV
      # Cron token (per-env). Idempotent — only created on first deploy.
      if [ ! -f /etc/sazon/backup-cron-\$ENV.token ]; then
        echo '==> first deploy for '\$ENV': generating backup cron token'
        mkdir -p /etc/sazon && chmod 0700 /etc/sazon
        python3 -c 'import secrets; print(secrets.token_hex(32))' \
          > /etc/sazon/backup-cron-\$ENV.token
        chmod 0400 /etc/sazon/backup-cron-\$ENV.token
        if [ -f /etc/sazon/.env.\$ENV ] && ! grep -q SASKIA_CRON_BACKUP_TOKEN /etc/sazon/.env.\$ENV; then
          echo \"SASKIA_CRON_BACKUP_TOKEN=\$(cat /etc/sazon/backup-cron-\$ENV.token)\" >> /etc/sazon/.env.\$ENV
        fi
      fi
      # Pick the backup schedule from envs.yaml (parsed inline; we keep the
      # deploy script shell-only). Empty schedule = skip cron install.
      case \$ENV in
        prod) SCHED='0 3 * * *' ;;
        test) SCHED='0 4 * * *' ;;
        dev)  SCHED='' ;;
      esac
      if [ -n \"\$SCHED\" ]; then
        cat > /etc/cron.d/sazon-backup-\$ENV <<EOF
# /etc/cron.d/sazon-backup-\$ENV — daily at \$SCHED. See docs/operations/backup-cron.md
SASKIA_BACKUP_URL=http://localhost:8000
SASKIA_CRON_BACKUP_TOKEN_FILE=/etc/sazon/backup-cron-\$ENV.token
SASKIA_ENV=\$ENV
\$SCHED root $REMOTE_DIR/.venv/bin/python $REMOTE_DIR/scripts/backup_cron.py >> /var/log/sazon-cron-\$ENV.log 2>&1
EOF
        chmod 0644 /etc/cron.d/sazon-backup-\$ENV
        echo \"==> \$ENV cron installed: \$(ls -l /etc/cron.d/sazon-backup-\$ENV)\"
      fi
    "
    ;;
  *) echo "DEPLOY WARNING ($ENV): health check did not return ok — inspect: ssh $VPS 'docker service ps $SERVICE_NAME'"; exit 1;;
esac
