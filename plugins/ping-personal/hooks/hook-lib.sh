# Shared helpers for the ping-personal Claude Code hooks. Source it; bash + sed + awk only.

# Print the string value of a top-level-or-nested JSON key from stdin JSON in $1.
# Example: json_get "$input" cwd -> D:\repo   (JSON escapes \\ and \" are undone)
json_get() {
    printf '%s' "$1" | tr -d '\r\n' \
        | sed -n "s/.*\"$2\"[[:space:]]*:[[:space:]]*\"\(\([^\"\\\\]\|\\\\.\)*\)\".*/\1/p" \
        | sed -e 's/\\\\/\x01/g' -e 's/\\"/"/g' -e 's/\x01/\\/g'
}

# Escape text for a JSON string value; real newlines become \n.
json_escape() {
    printf '%s' "$1" | awk 'BEGIN { ORS = "" }
        { gsub(/\r/, ""); gsub(/\\/, "\\\\"); gsub(/"/, "\\\""); gsub(/\t/, "\\t");
          if (NR > 1) print "\\n"; print }'
}

# Turn a Windows path (C:\x\y) into the form this bash understands (/c/x/y).
to_posix_path() {
    if command -v cygpath >/dev/null 2>&1; then cygpath -u "$1" 2>/dev/null || printf '%s' "$1"
    else printf '%s' "$1"; fi
}
