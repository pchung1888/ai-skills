#!/usr/bin/env bash
# pre-push-discipline.sh
#
# Pre-push guard that blocks the three most common "oh no" pushes:
#
#   1. Direct push to a long-lived integration branch (main / master).
#   2. Delete of a long-lived integration branch (feature/*).
#   3. Non-fast-forward (force) push to ANY branch -- including topic/*.
#
# This is the project-agnostic port of the upstream pre-push hook from a
# private codebase. Reasonable defaults for the typical "main + feature/* +
# topic/*" branch convention. Fork the script if your repo uses different
# integration-branch names (e.g. develop, trunk, integration/*).
#
# Usage:
#   1. Drop this file in your repo's .githooks/ directory.
#   2. chmod +x .githooks/pre-push-discipline.sh
#   3. Wire it up:
#        git config core.hooksPath .githooks
#      OR call it from your existing pre-push hook with:
#        bash .githooks/pre-push-discipline.sh "$@" || exit 1
#
# Bypass (use sparingly, document the reason in the commit message):
#   git push --no-verify
#
# Exit codes:
#   0  push is allowed
#   1  push is blocked (one of the three guards fired)

set -u

ZERO_SHA="0000000000000000000000000000000000000000"

while read local_ref local_sha remote_ref remote_sha; do

  # Guard 1: Block direct push to main / master.
  # (Also covers deleting main / master: keyed off remote_ref.)
  if echo "$remote_ref" | grep -qE "refs/heads/(main|master)$"; then
    echo "BLOCKED: Direct push to $(echo "$remote_ref" | sed 's|refs/heads/||') is not allowed."
    echo "Push to a topic branch and open a PR/MR."
    echo "Bypass with documented reason: git push --no-verify"
    exit 1
  fi

  # Guard 2: Block deletes of feature/* (long-lived integration branches).
  # Allow deletes of topic/* and other short-lived branches.
  if [ "$local_sha" = "$ZERO_SHA" ]; then
    if echo "$remote_ref" | grep -q "refs/heads/feature/"; then
      echo "BLOCKED: Deleting feature/* branches is not allowed."
      echo "Feature branches are long-lived integration branches; only delete topic/* branches."
      echo "Bypass with documented reason: git push --no-verify"
      exit 1
    fi
    # Delete of a non-protected branch (topic/*, etc.) -- skip non-FF check.
    continue
  fi

  # Guard 3: Block non-fast-forward (force) pushes to any branch.
  # Only fires when remote_sha is known locally (avoids false-positive when
  # remote has unfetched commits we genuinely don't know about).
  if [ "$remote_sha" != "$ZERO_SHA" ]; then
    if git cat-file -e "$remote_sha" 2>/dev/null; then
      if ! git merge-base --is-ancestor "$remote_sha" "$local_sha" 2>/dev/null; then
        echo "BLOCKED: Non-fast-forward push to $remote_ref -- would rewrite shared history."
        echo "Create a new commit instead of amending/rebasing published branches."
        echo "Bypass with documented reason: git push --no-verify"
        exit 1
      fi
    fi
  fi

done

exit 0
