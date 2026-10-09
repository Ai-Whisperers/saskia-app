#!/usr/bin/env bash
# install_bws_token.sh — install the BWS access token on the VPS.
#
# Run ONCE per VPS, not per deploy. The token is the long-lived Bitwarden
# Secrets access token; it lives in /etc/sazon/bws-token (mode 0400).
# After this script runs, deploy.sh and write_env_file.py read the token
# from there.
#
# The token value is NOT in this script (and not in git). The operator
# pastes it from ~/.hermes/inbox/bws-token.secret (which is the same
# file BWS itself writes). The script prompts for the value, or accepts
# it via env var BWS_TOKEN.
#
# Usage (on the VPS as root):
#   BWS_TOKEN="0.14fe0cd6-..." bash scripts/install_bws_token.sh
#
# Or interactive:
#   bash scripts/install_bws_token.sh
#   # prompts: "Enter BWS access token: "

set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: must run as root (or sudo)"
  exit 1
fi

# Token source: env var > interactive prompt
if [ -z "${BWS_TOKEN:-}" ]; then
  echo -n "Enter BWS access token: "
  read -rs BWS_TOKEN
  echo
fi

if [ -z "$BWS_TOKEN" ]; then
  echo "ERROR: BWS_TOKEN is empty"
  exit 1
fi

mkdir -p /etc/sazon
chmod 0700 /etc/sazon

# If bws isn't installed, install it. Idempotent.
if ! command -v bws >/dev/null 2>&1; then
  echo "==> installing bws CLI"
  BWS_VERSION="2.1.0"
  curl -fsSL "https://github.com/bitwarden/sdk/releases/download/bws-v${BWS_VERSION}/bws-x86_64-unknown-linux-gnu-${BWS_VERSION}.zip" \
    -o /tmp/bws.zip
  (cd /tmp && unzip -o bws.zip && mv bws /usr/local/bin/ && chmod +x /usr/local/bin/bws)
  rm /tmp/bws.zip
fi
echo "==> bws version: $(bws --version)"

# Write the token, mode 0400, root-only
echo "$BWS_TOKEN" > /etc/sazon/bws-token
chmod 0400 /etc/sazon/bws-token

# Smoke test: list one secret to confirm the token works
echo "==> smoke test: bws secret list"
BWS_ACCESS_TOKEN="$BWS_TOKEN" bws secret list --output json 2>&1 | head -3
echo "==> ok"
echo
echo "Token installed at /etc/sazon/bws-token (mode 0400, root-only)."
echo "Run: bash scripts/deploy.sh --env=prod   to deploy to production."
