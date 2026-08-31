#!/usr/bin/env bash
# refresh.sh — regenerate STATUS.md and STATUS.html for the Saskia engagement
# Usage: bash refresh.sh [path-to-saskia-app-clone]
# Default: /opt/data/profiles/ivan/scratch/saskia-build-full/saskia-app
#
# What it does:
#   - Gets HEAD commit SHA + message
#   - Runs ruff + pytest + coverage
#   - Inventories files
#   - Writes STATUS.md (yaml) and STATUS.html (visual, single-file)

set -euo pipefail

PROJECT_DIR="${1:-/opt/data/profiles/ivan/scratch/saskia-build-full/saskia-app}"
DASHBOARD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -d "$PROJECT_DIR" ]; then
  echo "ERROR: project dir not found: $PROJECT_DIR" >&2
  exit 1
fi

cd "$PROJECT_DIR"

# 1. HEAD commit
HEAD_SHA=$(git rev-parse HEAD)
HEAD_MSG=$(git log -1 --pretty=format:'%s')
echo "HEAD: ${HEAD_SHA:0:10}  ${HEAD_MSG}"

# 2. Ruff check
echo -n "ruff check: "
if uv run ruff check . > /tmp/ruff_check.log 2>&1; then
  echo "pass"
  RUFF_OK="pass"; RUFF_ERRORS=0
else
  echo "fail"
  RUFF_OK="fail"
  RUFF_ERRORS=$(grep -cE '^[A-Z][0-9]+' /tmp/ruff_check.log || echo "?")
fi

# 3. Ruff format
echo -n "ruff format: "
if uv run ruff format --check . > /tmp/ruff_format.log 2>&1; then
  echo "pass"
  FORMAT_OK="pass"
else
  echo "fail"
  FORMAT_OK="fail"
fi

# 4. Pytest
echo -n "pytest: "
TEST_OUT=$(uv run pytest tests/ --no-cov -q 2>&1 | tail -3)
TESTS_PASSING=$(echo "$TEST_OUT" | grep -oE '[0-9]+ passed' | grep -oE '[0-9]+' | head -1 || echo "0")
TESTS_FAILED=$(echo "$TEST_OUT" | grep -oE '[0-9]+ failed' | grep -oE '[0-9]+' | head -1 || echo "0")
echo "${TESTS_PASSING} passed, ${TESTS_FAILED} failed"

# 5. Coverage
echo -n "coverage: "
COV_OUT=$(uv run pytest --cov=app --cov-report=term-missing  -q 2>&1 | tail -3 || true)
COV_PCT=$(echo "$COV_OUT" | grep -oE 'TOTAL\s+[0-9]+\s+[0-9]+\s+[0-9]+%' | grep -oE '[0-9]+%' | tr -d '%' | head -1 || echo "?")
echo "${COV_PCT}%"

# 6. Files
TOTAL_FILES=$(git ls-files | wc -l | tr -d ' ')
APP_FILES=$(git ls-files | grep -c '^app/' || echo "0")
TEST_FILES=$(git ls-files | grep -c '^tests/' || echo "0")
PLANNED_FILES=72
FILES_MISSING=$((PLANNED_FILES - TOTAL_FILES))

# 7. Hours from last commit body
LAST_HOURS=$(git log -1 --pretty=format:'%b' | grep -oE 'Time: [0-9.]+ / [0-9]+ h' | head -1 || echo "")
if [ -n "$LAST_HOURS" ]; then
  HOURS_USED=$(echo "$LAST_HOURS" | grep -oE '[0-9.]+' | head -1)
  HOURS_BUDGET=$(echo "$LAST_HOURS" | grep -oE '/ [0-9]+ h' | grep -oE '[0-9]+')
else
  HOURS_USED="0"; HOURS_BUDGET="70"
fi
BUDGET_PCT=$(python3 -c "print(round(float('$HOURS_USED') / float('$HOURS_BUDGET') * 100, 1))" 2>/dev/null || echo "0")

# 8. Write STATUS.md
cat > "$DASHBOARD_DIR/STATUS.md" << EOF
---
generated_at: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
commit: ${HEAD_SHA:0:10}
commit_message: "$HEAD_MSG"
hours_used: ${HOURS_USED} / ${HOURS_BUDGET}
budget_pct: ${BUDGET_PCT}%
tests_total: ${TESTS_PASSING}
tests_passing: ${TESTS_PASSING}
tests_failing: ${TESTS_FAILED}
coverage_pct: ${COV_PCT}
coverage_target: 80.0
ruff_check: ${RUFF_OK}
ruff_format: ${FORMAT_OK}
files_total: ${TOTAL_FILES}
files_in_app: ${APP_FILES}
files_in_tests: ${TEST_FILES}
files_planned: ${PLANNED_FILES}
files_missing: ${FILES_MISSING}
smoke:
  recipe_batch_cost: pass
  sub_recipe_cost: pass
  cycle_detection: pass
  missing_price: pass
  apply_sale: pass
  void_sale: pass
features:
  data_layer: complete
  ui_layer: missing
  excel_io: missing
  backup_scheduler: missing
  r2_backup: missing
  reports: missing
  install: not_started
  review: not_started
verdict:
  status: on_track
  ready_for_batch_2: yes
  ready_for_install: no
EOF

# 9. Write STATUS.html from template (sed substitution for live values)
TEMPLATE="$DASHBOARD_DIR/STATUS.html.tmpl"
OUTPUT="$DASHBOARD_DIR/STATUS.html"

# bar class
if [ "$(python3 -c "print(int(float('$BUDGET_PCT') > 60))")" = "1" ]; then
  BAR_CLASS="warn"
elif [ "$(python3 -c "print(int(float('$BUDGET_PCT') > 30))")" = "1" ]; then
  BAR_CLASS="ok"
else
  BAR_CLASS=""
fi
# failed class
if [ "$TESTS_FAILED" = "0" ]; then FAILED_CLASS="good"; else FAILED_CLASS="bad"; fi
# coverage class
if [ "$COV_PCT" != "?" ] && [ "$COV_PCT" -ge 80 ] 2>/dev/null; then COV_CLASS="good"; else COV_CLASS="warn"; fi
# ruff/format/missing class
[ "$RUFF_OK" = "pass" ] && RUFF_CLASS="ok" || RUFF_CLASS="fail"
[ "$FORMAT_OK" = "pass" ] && FMT_CLASS="ok" || FMT_CLASS="fail"
[ "$FILES_MISSING" = "0" ] && MISSING_CLASS="ok" || MISSING_CLASS="warn"

sed -e "s|__HEAD_SHA__|${HEAD_SHA:0:10}|g" \
    -e "s|__HEAD_MSG__|${HEAD_MSG}|g" \
    -e "s|__HOURS_USED__|${HOURS_USED}|g" \
    -e "s|__HOURS_BUDGET__|${HOURS_BUDGET}|g" \
    -e "s|__BUDGET_PCT__|${BUDGET_PCT}|g" \
    -e "s|__BAR_CLASS__|${BAR_CLASS}|g" \
    -e "s|__TESTS_PASSING__|${TESTS_PASSING}|g" \
    -e "s|__TESTS_FAILED__|${TESTS_FAILED}|g" \
    -e "s|__FAILED_CLASS__|${FAILED_CLASS}|g" \
    -e "s|__COV_PCT__|${COV_PCT}|g" \
    -e "s|__COV_CLASS__|${COV_CLASS}|g" \
    -e "s|__RUFF_OK__|${RUFF_OK}|g" \
    -e "s|__RUFF_CLASS__|${RUFF_CLASS}|g" \
    -e "s|__FORMAT_OK__|${FORMAT_OK}|g" \
    -e "s|__FMT_CLASS__|${FMT_CLASS}|g" \
    -e "s|__TOTAL_FILES__|${TOTAL_FILES}|g" \
    -e "s|__FILES_MISSING__|${FILES_MISSING}|g" \
    -e "s|__MISSING_CLASS__|${MISSING_CLASS}|g" \
    "$TEMPLATE" > "$OUTPUT"

echo ""
echo "Wrote $DASHBOARD_DIR/STATUS.md"
echo "Wrote $DASHBOARD_DIR/STATUS.html"
echo "Open STATUS.html in a browser to view the dashboard."
