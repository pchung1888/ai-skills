import argparse
import hashlib
import datetime
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from atomic_write import atomic_write
from log_appender import append_failure_row, open_detours

def _git_add_beacon(bp):
    """Stage the beacon, even when it sits under an ignored directory.

    The beacon is a file this tool creates and owns, and it is the only
    cross-session safety net; it must reach git.  Plain `git add` on a path under
    an ignore rule exits 1 EVEN WHEN THE FILE IS ALREADY TRACKED and even when it
    successfully stages the change -- so a `check=True` call raised on a command
    that had actually worked, and the commit below it never ran.  That is how a
    beacon could be silently left uncommitted for a whole goal.
    """
    subprocess.run(["git", "add", "-f", str(bp)], check=True)




def parse_header(beacon_text):
    m = re.match(r"^---\n(.*?)\n---", beacon_text, re.DOTALL)
    if not m:
        raise RuntimeError("no YAML frontmatter")
    h = {}
    for line in m.group(1).split("\n"):
        if ":" in line:
            k, v = line.split(":", 1)
            h[k.strip()] = v.strip()
    return h


def _is_windows():
    return sys.platform.startswith("win")


def _bash_available():
    return shutil.which("bash") is not None


def _glob_collision(beacon_path, slug):
    """Return list of all *<slug>*-audit-tracker.md under docs/ (excl. canonical)."""
    root = Path(beacon_path).resolve().parent
    for candidate in [root, root.parent, root.parent.parent]:
        docs = candidate / "docs"
        if docs.is_dir():
            matches = list(docs.rglob(f"*{slug}*-audit-tracker.md"))
            return [str(m) for m in matches if m.resolve() != Path(beacon_path).resolve()]
    return []


def _cache_path(beacon_path):
    return Path(str(beacon_path) + ".accept-cache")


def _cache_key(cmd, matched_line):
    raw = (cmd + "|" + matched_line).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _read_cache(cp):
    """Return dict with keys: key, matched_line, ts -- or None if absent/corrupt."""
    if not cp.exists():
        return None
    try:
        lines = cp.read_text(encoding="utf-8").splitlines()
        d = {}
        for l in lines:
            if "=" in l:
                k, v = l.split("=", 1)
                d[k.strip()] = v.strip()
        if "key" in d and "ts" in d:
            return d
    except Exception:
        pass
    return None


def _write_cache(cp, cmd, matched_line):
    ts = datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    key = _cache_key(cmd, matched_line)
    cp.write_text(
        f"key = {key}\nmatched_line = {matched_line}\nts = {ts}\n",
        encoding="utf-8"
    )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--beacon", required=True)
    p.add_argument("--todo", required=True)
    p.add_argument("--slug", required=True)
    p.add_argument("--shell", default=None,
                   help="Override accept_shell from beacon (pwsh or bash).")
    p.add_argument("--skip-if-cached", action="store_true",
                   help="Skip re-running acceptance if cache exists and accept_cmd unchanged.")
    p.add_argument("--allow-open-detours", dest="allow_open_detours", action="store_true",
                   help="Close the goal even with detours still open; the open ids are recorded.")
    p.add_argument("--force", action="store_true",
                   help="Ignore cache and always run acceptance command.")
    args = p.parse_args()

    bp = Path(args.beacon)
    content = bp.read_text(encoding="utf-8")

    # The return path, enforced.  A detour is a side quest opened to unblock the goal;
    # closing the goal while one is still open is how a two-hour fix quietly becomes
    # the project and the original aim is never resumed.
    _open = open_detours(content)
    if _open and args.allow_open_detours:
        # The help text and the design doc both said the open ids are recorded. They
        # were not: the override fell straight through to acceptance and never touched
        # the beacon. A bypass that leaves no trace is worse than no gate, because the
        # terminal tells the operator a record exists.
        content = append_failure_row(
            content, "finalize", "finalize",
            f"closed with detours still open: {', '.join(_open)}",
            "Reopen the goal or justify each open detour", "")
        atomic_write(args.beacon, content)
        try:
            _git_add_beacon(bp)
            subprocess.run(["git", "commit", "-q", "-m",
                            f"chore({bp.stem.replace('-audit-tracker','')}): finalize with "
                            f"open detours {', '.join(_open)}"], check=True)
        except subprocess.CalledProcessError:
            print("WARNING: override recorded in the beacon but the commit failed",
                  file=sys.stderr)
        print(f"NOTE: finalizing with open detours: {', '.join(_open)} (recorded)",
              file=sys.stderr)
    if _open and not args.allow_open_detours:
        print(f"ERROR: cannot finalize -- detours still open: {', '.join(_open)}.\n"
              f"  Close each with: /personal-goal-next --detour-close <id>\n"
              f"  or pass --allow-open-detours to close the goal anyway (recorded).",
              file=sys.stderr)
        return 7

    h = parse_header(content)
    cmd = h.get("accept_cmd", "")
    if not cmd:
        print("ERROR: beacon has no accept_cmd", file=sys.stderr)
        return 2

    slug_key = bp.stem.replace("-audit-tracker", "")
    others = _glob_collision(args.beacon, slug_key)
    if others:
        print(f"WARNING: multiple audit-trackers match slug -- collision candidates: {', '.join(others)}", file=sys.stderr)

    shell = args.shell or h.get("accept_shell", "pwsh")

    # Shell mismatch refuse
    if shell == "bash":
        if _is_windows() and not _bash_available():
            print("ERROR: beacon accept_shell is 'bash' but bash is not available on this Windows machine. "
                  "Install Git-for-Windows/WSL bash or override with --shell pwsh.", file=sys.stderr)
            return 2
    elif shell == "pwsh":
        if not _is_windows() and shutil.which("pwsh") is None:
            print("ERROR: beacon accept_shell is 'pwsh' but pwsh is not available on this system. "
                  "Install PowerShell Core or override with --shell bash.", file=sys.stderr)
            return 2

    match = h.get("accept_match", "")
    regex_pat = h.get("accept_regex", "")

    # Acceptance cache check
    cp = _cache_path(bp)
    cache = _read_cache(cp)
    if cache and not args.force:
        cached_key = _cache_key(cmd, cache.get("matched_line", ""))
        current_key = _cache_key(cmd, cache.get("matched_line", ""))
        # The cache is valid if the stored key matches a re-hash of cmd+matched_line
        if cache.get("key") == current_key:
            ts = cache.get("ts", "unknown time")
            if args.skip_if_cached:
                print(f"acceptance previously PASSED at {ts}; skipping (--skip-if-cached).")
                return 0
            else:
                print(f"acceptance previously PASSED at {ts}; rerunning anyway (use --skip-if-cached to skip).")

    # Run acceptance command.
    # Pass cmd as a single string argument to the shell interpreter (pwsh -Command
    # or bash -c).  The interpreter handles $vars, pipes, quotes -- no Python
    # shell=True needed.  shell=True would expose accept_cmd to OS-shell injection.
    # encoding='utf-8' + errors='replace' guards against Windows cp1252 fallback
    # crashing on UTF-8 box-drawing characters.
    if shell == "pwsh":
        r = subprocess.run(["pwsh", "-NoProfile", "-Command", cmd],
                           capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
    else:
        r = subprocess.run(["bash", "-c", cmd],
                           capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
    out = r.stdout

    passed = False
    matched_line = ""
    if match:
        passed = match in out
        if passed:
            matched_line = next((l for l in out.splitlines() if match in l), match)
    elif regex_pat:
        m2 = re.search(regex_pat, out)
        passed = m2 is not None
        if passed:
            matched_line = m2.group(0)

    if passed:
        # Write acceptance cache
        _write_cache(cp, cmd, matched_line)

        # Move TODO entry to "## To Be Tested"
        tp = Path(args.todo)
        tc = tp.read_text(encoding="utf-8")
        m3 = re.search(rf"^(- \*\*\[GOAL .* {re.escape(args.slug)}\][^\n]*)\n", tc, re.MULTILINE)
        if m3:
            entry = m3.group(1)
            tc = tc.replace(entry + "\n", "")
            if "## To Be Tested" not in tc:
                tc += "\n## To Be Tested\n"
            tc = re.sub(r"(## To Be Tested\n)", r"\1" + entry + "\n", tc, count=1)
            tp.write_text(tc, encoding="utf-8")
        print("FINALIZE PASS: acceptance command matched.")
        return 0
    else:
        content = append_failure_row(content, "finalize", "finalize",
                                     f"acceptance command did not match: cmd={cmd}",
                                     "Investigate failed assertion",
                                     "Acceptance criterion needs refinement")
        atomic_write(args.beacon, content)
        # No cwd= -- use process cwd (repo root) with absolute beacon path.
        _git_add_beacon(bp)
        subprocess.run(["git", "commit", "-q", "-m",
                        f"chore({args.slug}): finalize FAILED -- acceptance not met"], check=True)
        print("FINALIZE FAIL: acceptance command output did not match.", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
