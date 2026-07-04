#!/usr/bin/env bash
set -euo pipefail

message=$1
shift

git config user.name "report-bot"
git config user.email "report-bot@users.noreply.github.com"
git add -- "$@"

if git diff --cached --quiet; then
  exit 0
fi

git commit -m "$message"

for attempt in 1 2 3; do
  if git pull --rebase origin main && git push origin HEAD:main; then
    exit 0
  fi
  git rebase --abort 2>/dev/null || true
  if (( attempt < 3 )); then
    sleep $((attempt * 2))
  fi
done

echo "Failed to persist report state after 3 attempts" >&2
exit 1
