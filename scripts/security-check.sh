#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$root"

git_root="$(git -C "$root" rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "$git_root" ]]; then
  printf 'tracked secret-file policy: SKIP (project Git metadata unavailable)\n'
  exit 0
fi

resolved_git_root="$(cd "$git_root" 2>/dev/null && pwd -P || true)"
if [[ -z "$resolved_git_root" ]]; then
  printf 'tracked secret-file policy: FAIL (cannot resolve Git root: %s)\n' "$git_root" >&2
  exit 1
fi

if [[ "$resolved_git_root" != "$root" ]]; then
  printf 'tracked secret-file policy: SKIP (project is not the Git root)\n'
  exit 0
fi

failed=0

while IFS= read -r -d '' path; do
  name="${path##*/}"

  case "$name" in
    .env.example|example.env|*.env.example|*.example.env)
      continue
      ;;
  esac

  case "$name" in
    .env|.env.*|*.env|*.pem|*.key|*.p12|*.pfx|id_rsa|id_ed25519)
      printf 'potential secret file must not be tracked: %s\n' "$path" >&2
      failed=1
      ;;
  esac
done < <(git ls-files -z)

if [[ "$failed" -ne 0 ]]; then
  exit 1
fi

printf 'tracked secret-file policy: PASS\n'
