#!/usr/bin/env bash
# docs-prose: run Vale on the prose docs corpus (deterministic file list).
#
# Why find + explicit args instead of --glob: Vale's multi-glob exclusion
# proved inconsistent (archive/binary files leaked through when several
# --glob flags were combined; single-glob runs excluded correctly).
# An explicit list is boring and always right.
#
# Output: line-format findings. Exit code = vale's (non-zero if findings).
set -euo pipefail
cd "$(dirname "$0")/.."

FILES=$(find docs README.md CHANGELOG.md \
  -type f \( -name '*.md' -o -name '*.txt' \) 2>/dev/null \
  -not -path 'docs/archive/*' \
  -not -path 'docs/dora-snapshots/*' \
  -not -path 'docs/roadmap/historical-plans/*' \
  -not -path 'docs/reports/redesign-2026-09-27/subagent-outputs/*' \
  -not -path 'docs/user-guide/screenshots/*' \
  | sort)

# shellcheck disable=SC2086
uvx --from=vale vale --output=line $FILES
