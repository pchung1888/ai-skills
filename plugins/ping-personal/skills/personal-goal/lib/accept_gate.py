import argparse
import re
import sys

DESTRUCTIVE_PREFIXES = [
    "rm ", "del ", "rmdir ", "Remove-Item ", "ri ", "erase ", "sdelete ",
    "git push", "git reset --hard", "git clean -f", "git checkout --",
    "git branch -D", "git rebase", "git filter-branch",
    "truncate ", "Clear-Content ", "Set-Content ",
    "DROP ", "DELETE FROM", "TRUNCATE TABLE",
    "shutdown ", "Restart-Computer", "Stop-Computer",
]
DESTRUCTIVE_CONTAINS = [
    "--no-verify", " rm -rf ", " del /q ", " Remove-Item -Recurse -Force ",
    " > ", " >> ",
]

def is_destructive(cmd):
    s = cmd
    for pre in ("&& ", "& ", "; ", "! "):
        while s.startswith(pre):
            s = s[len(pre):]
    sl = s.lower()
    for p in DESTRUCTIVE_PREFIXES:
        if sl.startswith(p.lower()):
            return p.strip()
    for c in DESTRUCTIVE_CONTAINS:
        if c.lower() in sl:
            return c.strip()
    return None

def validate(args):
    if args.unverifiable is not None:
        if len(args.unverifiable.strip()) < 10:
            print("ERROR: --unverifiable reason must be at least 10 characters", file=sys.stderr)
            return 2
        return 0
    if args.accept_cmd is None and args.no_interactive:
        print("ERROR: acceptance criterion required or pass --unverifiable", file=sys.stderr)
        return 2
    if args.accept_cmd is not None:
        if args.accept_match is not None and args.accept_regex is not None:
            print("ERROR: exactly one of --accept-match or --accept-regex", file=sys.stderr)
            return 2
        if args.accept_match is None and args.accept_regex is None:
            print("ERROR: --accept-cmd requires either --accept-match or --accept-regex", file=sys.stderr)
            return 2
        if args.accept_match is not None and not args.accept_match.strip():
            print("ERROR: --accept-match cannot be empty", file=sys.stderr)
            return 2
        if args.accept_regex is not None and not args.accept_regex.strip():
            print("ERROR: --accept-regex cannot be empty", file=sys.stderr)
            return 2
        if args.accept_regex is not None:
            try:
                re.compile(args.accept_regex)
            except re.error as e:
                print(f"ERROR: --accept-regex did not compile: {e}", file=sys.stderr)
                return 2
        d = is_destructive(args.accept_cmd)
        if d:
            print(f"ERROR: --accept-cmd looks destructive (matched pattern: {d})", file=sys.stderr)
            return 2
    return 0

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--validate", action="store_true", required=True)
    p.add_argument("--accept-cmd", dest="accept_cmd")
    p.add_argument("--accept-match", dest="accept_match")
    p.add_argument("--accept-regex", dest="accept_regex")
    p.add_argument("--unverifiable", dest="unverifiable")
    p.add_argument("--no-interactive", action="store_true")
    args = p.parse_args()
    return validate(args)

if __name__ == "__main__":
    sys.exit(main())
