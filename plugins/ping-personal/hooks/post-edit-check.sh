#!/usr/bin/env bash
# PostToolUse hook for Edit|Write. Warns (never blocks) when:
#  (a) a tracked file's line endings changed versus what git checks out for HEAD (CRLF/LF/mixed);
#  (b) a SKILL.md has a broken frontmatter: no opening/closing ---, name not equal to its folder,
#      empty description, tabs, or non-ASCII bytes.
# The warning goes to the user (systemMessage) and to Claude (additionalContext).
. "$(dirname "$0")/hook-lib.sh"

input=$(cat)
raw=$(json_get "$input" file_path)
[ -z "$raw" ] && exit 0
file=$(to_posix_path "$raw")
[ -f "$file" ] || exit 0
warnings=""
warn() { warnings="${warnings}$1
"; }

# Prints none, LF, CRLF or mixed for the file in $1.
eol_style() {
    local lf crlf
    lf=$(tr -cd '\n' < "$1" | wc -c)
    # Count CR bytes with tr: Git Bash grep can strip CR before matching.
    crlf=$(tr -cd '\r' < "$1" | wc -c)
    if [ "$lf" -eq 0 ]; then echo none
    elif [ "$crlf" -eq 0 ]; then echo LF
    elif [ "$crlf" -ge "$lf" ]; then echo CRLF
    else echo mixed; fi
}

# (a) line-ending drift on tracked files
if command -v git >/dev/null 2>&1; then
    dir=$(dirname "$file"); base=$(basename "$file")
    if prefix=$(git -C "$dir" rev-parse --show-prefix 2>/dev/null) \
        && git -C "$dir" cat-file -e "HEAD:$prefix$base" 2>/dev/null; then
        tmp=$(mktemp)
        # --filters writes the bytes a checkout of HEAD would produce (autocrlf/eol applied).
        git -C "$dir" cat-file --filters "HEAD:$prefix$base" > "$tmp" 2>/dev/null
        before=$(eol_style "$tmp"); after=$(eol_style "$file")
        rm -f "$tmp"
        if [ "$before" != none ] && [ "$after" != none ] && [ "$before" != "$after" ]; then
            warn "Line endings changed in $base: $before in HEAD, $after now."
        fi
    fi
fi

# (b) SKILL.md frontmatter lint
if [ "$(basename "$file")" = "SKILL.md" ]; then
    folder=$(basename "$(dirname "$file")")
    first=$(head -n 1 "$file" | tr -d '\r')
    closing=$(awk 'NR > 1 && /^---\r?$/ { print "yes"; exit }' "$file")
    if [ "$first" != "---" ]; then
        warn "SKILL.md: the first line must be ---."
    elif [ "$closing" != "yes" ]; then
        warn "SKILL.md: the frontmatter has no closing ---."
    else
        front=$(awk 'NR == 1 { next } /^---\r?$/ { exit } { print }' "$file" | tr -d '\r')
        name=$(printf '%s\n' "$front" | sed -n 's/^name:[[:space:]]*//p' | head -n 1)
        [ "$name" != "$folder" ] && warn "SKILL.md: name '$name' does not match the folder '$folder'."
        desc=$(printf '%s\n' "$front" | sed -n 's/^description:[[:space:]]*//p' | head -n 1)
        case "$desc" in
            ''|'>'|'|'|'>-'|'|-')
                # Empty, or a block scalar: needs an indented non-empty line right after it.
                if ! printf '%s\n' "$front" | awk '/^description:/ { f = 1; next }
                        f && /^[ \t]+[^ \t]/ { ok = 1; exit } f { exit } END { exit !ok }'; then
                    warn "SKILL.md: the description is missing or empty."
                fi ;;
        esac
        printf '%s' "$front" | grep -q "$(printf '\t')" && warn "SKILL.md: the frontmatter contains a tab; YAML needs spaces."
        printf '%s' "$front" | LC_ALL=C grep -q "$(printf '[\200-\377]')" && warn "SKILL.md: the frontmatter has non-ASCII characters; use plain ASCII."
    fi
fi

[ -z "$warnings" ] && exit 0
msg=$(json_escape "${warnings%
}")
printf '{"systemMessage": "%s", "hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": "%s"}}\n' "$msg" "$msg"
exit 0
