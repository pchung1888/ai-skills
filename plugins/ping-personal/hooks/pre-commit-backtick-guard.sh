#!/usr/bin/env bash
# pre-commit-backtick-guard.sh
#
# Pre-commit guard that detects fabricated code references in long markdown
# specs. For each staged .md file longer than 200 lines, this strips fenced
# code blocks, then extracts inline backtick-quoted tokens that look like
# code symbols (file paths, function names, env vars, ALL_CAPS constants).
# For each such token, the script greps the rest of the repo (excluding the
# .md file itself); zero hits means the token is likely fabricated.
#
# This is the project-agnostic port of the "Backtick Discipline" pre-commit
# guard from a private codebase. The original ran on a hand-rolled SP-format
# linter chain; this version is standalone -- drop it into any repo's
# .githooks/ directory and wire it via `git config core.hooksPath .githooks`,
# or call it from another hook runner (husky, lefthook, pre-commit, etc.).
#
# Carve-outs (legitimate prose, not spec citations):
#   - .claude/TODO.md
#   - docs/progress/**
#   - .claude/skills/**/SKILL.md
#
# Token-filter carve-outs (prose patterns that look code-like but rarely
# resolve to real repo strings, and would force unnecessary unwrap edits):
#   - slash-commands (e.g. "/personal-critic-gate")
#   - glob patterns (anything containing * or ?)
#   - pure-uppercase tokens with no underscore (e.g. "ABSTAIN", "BLOCKED")
#
# Usage:
#   1. Drop this file in your repo's .githooks/ (or hooks/) directory.
#   2. chmod +x .githooks/pre-commit-backtick-guard.sh
#   3. Wire it up:
#        git config core.hooksPath .githooks
#      OR call it from your existing pre-commit hook with:
#        bash .githooks/pre-commit-backtick-guard.sh || exit 1
#
# Bypass (use sparingly): git commit --no-verify
#
# Exit codes:
#   0  no violations OR no long .md files staged
#   1  one or more long .md files reference fabricated tokens

set -u

LONG_MDS=$(git diff --cached --name-only --diff-filter=ACM | grep -E "\.md$" || true)
[ -z "$LONG_MDS" ] && exit 0

SPEC_GUARD_FAILED=0

while IFS= read -r f; do
  [ -z "$f" ] && continue
  [ ! -f "$f" ] && continue

  # Carve-out: skip prose-heavy files where backtick tokens are legitimately
  # documentation references rather than spec citations.
  case "$f" in
    .claude/TODO.md) continue ;;
    docs/progress/*) continue ;;
    .claude/skills/*/SKILL.md) continue ;;
  esac

  LINE_COUNT=$(wc -l < "$f")
  if [ "$LINE_COUNT" -le 200 ]; then continue; fi

  # Strip fenced code blocks, then extract inline `tokens`. Filter to plausible
  # code symbols: contains a dot, slash, or underscore, OR starts with p/fn/sp_
  # (common SP/UDF naming), OR looks env-var-ish (ALL_CAPS with underscores).
  TOKENS=$(awk '/^[ \t]*```/{f=!f;next} !f' "$f" \
    | grep -oE '`[^`]+`' \
    | sed 's/^`//;s/`$//' \
    | grep -E '(\.|/|_|^p[A-Z]|^fn[A-Z]|^sp_|^[A-Z_]{4,}$)' \
    | sort -u)

  [ -z "$TOKENS" ] && continue

  while IFS= read -r tok; do
    [ -z "$tok" ] && continue

    # Skip tokens that aren't useful to grep:
    case "$tok" in
      *' '*) continue ;;     # contains space, not a symbol
      '') continue ;;
      /[a-z]*) continue ;;   # slash-command prose mention
      *'*'*) continue ;;     # glob wildcard
      *'?'*) continue ;;     # glob wildcard
    esac

    # Pure-uppercase tokens with NO underscore are almost always prose
    # enums/acronyms; real ALL_CAPS constants have underscores (MAX_RETRIES,
    # ERR_INVALID). Skip pure-uppercase-no-underscore tokens.
    case "$tok" in
      *_*) ;;             # has an underscore: likely a real constant, keep
      *[!A-Z]*) ;;        # has any non-uppercase char: likely a symbol, keep
      *) continue ;;      # pure-uppercase, no underscore: prose enum, skip
    esac

    # Repo grep, excluding the .md file being inspected.
    HITS=$(git grep -l --fixed-strings -- "$tok" 2>/dev/null | grep -v -F "$f" | head -1 || true)
    if [ -z "$HITS" ]; then
      echo "SPEC-GUARD: '$f' references unknown token \`$tok\` (no other repo file mentions it)."
      SPEC_GUARD_FAILED=1
    fi
  done <<< "$TOKENS"
done <<< "$LONG_MDS"

if [ "$SPEC_GUARD_FAILED" = "1" ]; then
  echo ""
  echo "BLOCKED: Long-spec fabrication guard found tokens in staged .md files that"
  echo "do not appear anywhere else in the repo. Either remove the fabricated"
  echo "references or add the referenced files. Bypass: git commit --no-verify"
  exit 1
fi

exit 0
