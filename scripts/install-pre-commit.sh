#!/bin/sh
# Install the pre-commit hook for Tier 1 lint.
# Idempotent — overwrites existing hook.
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HOOK="$SCRIPT_DIR/../.git/hooks/pre-commit"

cat > "$HOOK" <<'EOF'
#!/bin/sh
set -e
cd "$(git rev-parse --show-toplevel)"
PY=$(ls -d .venv/bin/python* 2>/dev/null | head -1)
if [ -z "$PY" ]; then
    echo "⚠  .venv not found; skipping lint_tier1.py"
    exit 0
fi
if ! "$PY" scripts/lint_tier1.py; then
    echo ""
    echo "❌ Tier 1 lint failed. Fix violations, or commit with --no-verify."
    exit 1
fi
EOF
chmod +x "$HOOK"
echo "✅ pre-commit hook installed at $HOOK"
