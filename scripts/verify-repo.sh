#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

required_files=(
  README.md GOAL.md STATUS.md ARCHITECTURE.md AGENTS.md SECURITY.md
  WORKER_TASK.md ARCHITECT_TASK.md REVIEWER_TASK.md
  SECURITY_REVIEWER_TASK.md RESEARCH_TASK.md
  .engineering-manifest
  scripts/verify-repo.sh scripts/security-check.sh scripts/run-hook.sh
)

failed=0
open_braces='{'
open_braces="${open_braces}{"
project_token="${open_braces}PROJECT_NAME}}"
year_token="${open_braces}YEAR}}"

for path in "${required_files[@]}"; do
  if [[ ! -f "$path" ]]; then
    printf 'missing required file: %s\n' "$path" >&2
    failed=1
  fi
done

while IFS= read -r -d '' path; do
  if grep -Fq -e "$project_token" -e "$year_token" "$path" 2>/dev/null; then
    printf 'unreplaced template token found: %s\n' "$path" >&2
    failed=1
  fi
done < <(find . -type f ! -path './.git/*' ! -name '.engineering-manifest' -print0)

if [[ -f scripts/security-check.sh ]]; then
  if ! bash scripts/security-check.sh >/dev/null; then
    failed=1
  fi
fi

if [[ "$failed" -ne 0 ]]; then
  exit 1
fi

printf 'repository contract: PASS\n'
