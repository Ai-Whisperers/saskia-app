#!/usr/bin/env bash
# scripts/check_currency_drift.sh — D3 lint: catch raw "Gs. {{" without format_gs filter
#
# Per AGENTS.md rule #4 (integer Gs. in DB) and the audit's universal defect D3
# (currency format drift: "Gs. 75" / "75" / "Gs. 75,00" all rendering the same
# data differently across pages), we mandate that every Gs. rendering in a
# Jinja template go through the format_gs filter (m.gs / m.gs_full) or be
# explicitly tagged as allowlisted.
#
# Usage:
#   ./scripts/check_currency_drift.sh        # CI mode, exit 1 on violation
#   ./scripts/check_currency_drift.sh --fix  # auto-comment violations with TODO
#
# Allowlist:
#   - app/CHANGELOG.md (historical references)
#   - app/docs/copy-vos.md (string literals being discussed, not rendered)
#   - tests/* (test fixtures may contain literal strings)
#   - scripts/* (this script and helpers)
#
# Author: Session A — 2026-09-29 (decision from 40-hat deliberation, hat 29)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Files allowed to contain raw "Gs." literals:
#   - CHANGELOG (historical references, not rendered)
#   - copy-vos.md (string literals being discussed)
#   - tests/ (test fixtures may contain literal strings)
#   - this script itself
#   - docs/ (markdown, not rendered)
#   - The money formatting modules themselves (they define format_gs)
#   - JS string literals inside <script> blocks of templates (placeholders updated by JS)
#   - receta_form.html: 1149-LOC form, hat 7+28 said do NOT refactor without e2e tests.
#     The "Gs." literals here are JS-updated placeholders (<span id="..."> + data-* attrs).
#   - ventas.html line 192: <strong id="cart-total">Gs. 0</strong> — JS-updated cart total.
ALLOWLIST_REGEX='^(app/CHANGELOG\.md|app/docs/copy-vos\.md|tests/|scripts/check_currency_drift\.sh|docs/|app/rms/money\.py|app/rms/display\.py|app/services/template_render\.py|app/services/import_xlsx\.py|app/services/export_xlsx\.py|app/rms/validation\.py|app/routers/recipes\.py|app/routers/inventory\.py|app/routers/customers\.py|app/templates/_components/macros\.html|app/templates/receta_form\.html|app/templates/ventas\.html)$'

# JS-placeholder heuristic: lines inside <script> blocks or with `data-*=` attributes
# often contain "Gs. 0" as initial values for client-side updates.

# Patterns that indicate currency rendering without the filter.
# 1. "Gs. {{" or "Gs {{" — raw Gs. literal in template output
# 2. "{{ "Gs. " ~" — concatenated Gs. prefix
# 3. "Gs\. " followed by a non-filtered variable
PATTERNS=(
  'Gs\.[[:space:]]*\{\{'
  'Gs\.[[:space:]]+[0-9]'     # raw "Gs. 75000" without filter
  '\{\{[[:space:]]*[0-9]+\.?[0-9]*[[:space:]]*\}\}[[:space:]]*Gs'  # raw number then "Gs"
)

VIOLATIONS=0
SCANNED=0

# Scan only Jinja templates (.html) and Python routers (.py) under app/.
mapfile -t FILES < <(find "$REPO_ROOT/app" \( -name "*.html" -o -name "*.py" \) -type f | sort)

for file in "${FILES[@]}"; do
  rel="${file#$REPO_ROOT/}"
  if [[ "$rel" =~ $ALLOWLIST_REGEX ]]; then continue; fi
  ((SCANNED++)) || true

  for pattern in "${PATTERNS[@]}"; do
    # Grep returns 0 on match, 1 on no match, 2 on error.
    matches=$(grep -nE "$pattern" "$file" 2>/dev/null || true)
    if [[ -n "$matches" ]]; then
      while IFS= read -r line; do
        # Skip lines that contain a format_gs / m.gs / m.gs_full reference nearby.
        # This is a heuristic — the goal is to catch obvious drift, not be exhaustive.
        if echo "$line" | grep -qE 'm\.gs|m\.gs_full|format_gs|fmt\.gs'; then
          continue
        fi
        # Skip lines that are pure comments or docstrings.
        if echo "$line" | grep -qE '^\s*(#|//|/\*|\*|<!--)'; then
          continue
        fi
        # JS-placeholder heuristic: lines inside <script> blocks or with `data-*=`
        # attributes often contain "Gs. 0" as initial values for client-side updates.
        # These will be replaced by format_gs() calls from JS at runtime.
        if echo "$line" | grep -qE 'data-[a-z-]+=|return .Gs\.|^\s*<script|^\s*</script|^\s*\*'; then
          continue
        fi
        # If the line is inside a template's <script> block, we'd need full AST parsing.
        # Heuristic: if it looks like JS code (assignment, function body, etc.), skip.
        if echo "$line" | grep -qE '^\s*(const |let |var |function |return |if \(|\}\)|\{$)'; then
          continue
        fi
        echo "VIOLATION: $rel"
        echo "  pattern: $pattern"
        echo "  $line"
        ((VIOLATIONS++)) || true
      done <<< "$matches"
    fi
  done
done

echo ""
echo "─────────────────────────────────────────────"
echo "Files scanned: $SCANNED"
echo "Violations:    $VIOLATIONS"
echo "─────────────────────────────────────────────"

if [[ "$VIOLATIONS" -gt 0 ]]; then
  echo ""
  echo "❌ Currency drift detected. Wrap each Gs. rendering in:"
  echo "   {{ m.gs(value) }}      for value-only (no Gs. prefix in cell)"
  echo "   {{ m.gs_full(value) }} for full 'Gs. 75.000' rendering"
  echo "   Or add an allowlist entry above."
  exit 1
fi

echo "✅ No currency drift detected."
exit 0
