#!/usr/bin/env bash
# PostToolUse hook for Edit|Write (Claude: tool_input.file_path; Codex: apply_patch text in tool_input.command).
# Warns (never blocks) when:
#  (a) a tracked file's line endings changed versus what git checks out for HEAD (CRLF/LF/mixed);
#  (b) a SKILL.md has a broken frontmatter: no opening/closing ---, name not equal to its folder,
#      empty description, tabs, or non-ASCII bytes.
# The warning goes to the user (systemMessage) and to Claude (additionalContext).
. "$(dirname "$0")/hook-lib.sh"

input=$(cat)
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

# Runs both checks on one file; a path that is not a file is skipped.
check_file() {
local file=$1
[ -f "$file" ] || return 0

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

}

# Claude sends one file_path. Codex sends the apply_patch text: one "*** Update File: <path>" or
# "*** Add File: <path>" line per file, paths relative to cwd, newlines still escaped as \n.
raw=$(json_get "$input" file_path)
if [ -n "$raw" ]; then
    check_file "$(to_posix_path "$raw")"
else
    patch=$(json_get "$input" command)
    cwd=$(to_posix_path "$(json_get "$input" cwd)")
    while IFS= read -r rel; do
        [ -z "$rel" ] && continue
        case "$rel" in /*|[A-Za-z]:*) check_file "$(to_posix_path "$rel")" ;; *) check_file "${cwd:-.}/$rel" ;; esac
    done <<EOF
$(printf '%s' "$patch" | sed 's/\\n/\n/g' | sed -n 's/^\*\*\* \(Update\|Add\) File: //p' | tr -d '\r')
EOF
fi

[ -z "$warnings" ] && exit 0
msg=$(json_escape "${warnings%
}")
printf '{"systemMessage": "%s", "hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": "%s"}}\n' "$msg" "$msg"
exit 0
