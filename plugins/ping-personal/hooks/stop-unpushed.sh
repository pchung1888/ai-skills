#!/usr/bin/env bash
# Stop hook: warn the user when the current branch has commits that are not on its upstream.
# Never blocks and never fetches. Silent outside a repo, without an upstream, on a detached HEAD,
# or when git is missing.
. "$(dirname "$0")/hook-lib.sh"

input=$(cat)
cwd=$(json_get "$input" cwd)
[ -n "$cwd" ] && cd "$(to_posix_path "$cwd")" 2>/dev/null

command -v git >/dev/null 2>&1 || exit 0
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0
git symbolic-ref -q HEAD >/dev/null 2>&1 || exit 0
upstream=$(git rev-parse --abbrev-ref '@{u}' 2>/dev/null) || exit 0
ahead=$(git log '@{u}..HEAD' --oneline 2>/dev/null)
[ -z "$ahead" ] && exit 0

branch=$(git rev-parse --abbrev-ref HEAD)
msg="NOT PUSHED: $branch has commits that are not on $upstream:
$ahead"
printf '{"systemMessage": "%s"}\n' "$(json_escape "$msg")"
exit 0
