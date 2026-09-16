#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

required=0
if [[ "${1:-}" == "--required" ]]; then
  required=1
  shift
fi

name="${1:-}"
if [[ -z "$name" ]]; then
  printf 'usage: %s [--required] <check|test|eval|build|deploy> [args...]\n' "$0" >&2
  exit 64
fi
shift

case "$name" in
  check|test|eval|build|deploy) ;;
  *)
    printf 'unknown project hook: %s\n' "$name" >&2
    exit 64
    ;;
esac

hook="scripts/project/$name"
if [[ ! -f "$hook" ]]; then
  if [[ "$required" -eq 1 ]]; then
    printf 'required project hook is not configured: %s\n' "$hook" >&2
    exit 78
  fi
  printf 'project hook not configured; skipping: %s\n' "$hook"
  exit 0
fi

if [[ ! -x "$hook" ]]; then
  printf 'project hook exists but is not executable: %s\n' "$hook" >&2
  exit 126
fi

exec "$hook" "$@"
