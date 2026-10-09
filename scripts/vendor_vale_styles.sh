#!/usr/bin/env bash
# Re-vendor Vale style packages into styles/ (pinned by URL; refresh = rerun + review diff).
# Provenance recorded in styles/PROVENANCE.txt.
set -euo pipefail
cd "$(dirname "$0")/.."

PACKS=(
  "Microsoft:https://github.com/vale-cli/Microsoft/releases/latest/download/Microsoft.zip"
  "write-good:https://github.com/vale-cli/write-good/releases/latest/download/write-good.zip"
)

for entry in "${PACKS[@]}"; do
  name="${entry%%:*}"
  url="${entry#*:}"
  tmp="$(mktemp -d)"
  echo "==> fetching $name"
  curl -fsSL "$url" -o "$tmp/pack.zip"
  rm -rf "styles/$name"
  mkdir -p "styles"
  unzip -qo "$tmp/pack.zip" -d "styles/$name"
  rm -rf "$tmp"
done

echo "Done. Review: git diff --stat styles/"
echo "Then update styles/PROVENANCE.txt with today's date."
