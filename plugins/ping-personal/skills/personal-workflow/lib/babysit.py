#!/usr/bin/env python3
"""
babysit.py -- report-only sweep of "## To Be Tested" GOAL entries.

Usage:
  python babysit.py --todo <path> --docs-root <path>
                    [--max-age-days 14] [--run-acceptance]

Reads .claude/TODO.md "## To Be Tested" section, locates each beacon,
and reports: slug | beacon | gate | staleness | branch state.
Never mutates any file.  Exit 0 always (unless --todo or --docs-root
file/dir is missing, in which case exit 1).
"""

import argparse
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None  # fallback: manual frontmatter parser


# ---------------------------------------------------------------------------
# Frontmatter parser (no PyYAML required)
# ---------------------------------------------------------------------------

def parse_frontmatter(text):
    """Return dict of YAML frontmatter keys from a markdown file string.
    Falls back to a simple line-based parser when PyYAML is absent."""
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return {}
    raw = m.group(1)
    if yaml:
        try:
            return yaml.safe_load(raw) or {}
        except Exception:
            pass
    # Manual line parser: key: value (no nested structures needed)
    result = {}
    for line in raw.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            result[k.strip()] = v.strip()
    return result


# ---------------------------------------------------------------------------
# TODO.md parser
# ---------------------------------------------------------------------------

GOAL_LINE_RE = re.compile(
    r"^-\s+\*\*\[GOAL\s+(\d{4}-\d{2}-\d{2})\s+([\w-]+)\]\*\*"
)
BEACON_FRAGMENT_RE = re.compile(r"Beacon:\s*([^\s.]+(?:\.md)?)")


def parse_to_be_tested(todo_path):
    """Return list of dicts: {date, slug, beacon_hint} from ## To Be Tested."""
    text = Path(todo_path).read_text(encoding="utf-8")
    # Find section
    section_m = re.search(r"^##\s+To Be Tested\s*\n(.*?)(?=^##|\Z)", text,
                          re.MULTILINE | re.DOTALL)
    if not section_m:
        return []
    section = section_m.group(1)
    entries = []
    for line in section.splitlines():
        m = GOAL_LINE_RE.match(line.strip())
        if not m:
            continue
        date_str, slug = m.group(1), m.group(2)
        bm = BEACON_FRAGMENT_RE.search(line)
        beacon_hint = bm.group(1) if bm else None
        entries.append({"date": date_str, "slug": slug,
                        "beacon_hint": beacon_hint})
    return entries


# ---------------------------------------------------------------------------
# Beacon locator
# ---------------------------------------------------------------------------

def locate_beacon(slug, hint, docs_root):
    """Return Path to beacon or None."""
    # 1. Explicit hint from TODO line
    if hint:
        p = Path(hint)
        if p.is_absolute() and p.exists():
            return p
        # Relative to repo root -- try walking up from docs_root
        # hint is e.g. "docs/goal-skill-v2/goal-skill-v2-audit-tracker.md"
        # docs_root is e.g. ".../docs"
        # Try: docs_root.parent / hint  (repo-root relative)
        candidate = Path(docs_root).parent / hint
        if candidate.exists():
            return candidate
        # Try: hint as-is from cwd
        candidate2 = Path(hint)
        if candidate2.exists():
            return candidate2

    # 2. Glob docs-root for *<slug>*-audit-tracker.md
    for p in Path(docs_root).rglob(f"*{slug}*audit-tracker.md"):
        return p
    return None


# ---------------------------------------------------------------------------
# Staleness check
# ---------------------------------------------------------------------------

def is_stale(beacon_path, max_age_days):
    """Return True when beacon file mtime is older than max_age_days."""
    try:
        mtime = beacon_path.stat().st_mtime
        age_days = (time.time() - mtime) / 86400
        return age_days > max_age_days
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Branch state check
# ---------------------------------------------------------------------------

def branch_state(branch):
    """Return string: 'ok', 'UNPUSHED', 'no-upstream', or 'branch-missing'."""
    if not branch:
        return "no-branch-field"
    # Does branch exist locally?
    r = subprocess.run(
        ["git", "rev-parse", "--verify", branch],
        capture_output=True, text=True
    )
    if r.returncode != 0:
        return "branch-missing"
    # Does it have an upstream?
    r2 = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", f"{branch}@{{u}}"],
        capture_output=True, text=True
    )
    if r2.returncode != 0:
        return "no-upstream"
    # Are there unpushed commits?
    r3 = subprocess.run(
        ["git", "log", f"origin/{branch}..{branch}", "--oneline"],
        capture_output=True, text=True
    )
    if r3.returncode != 0:
        # Try @{u} form in case remote name differs
        r3b = subprocess.run(
            ["git", "log", f"{branch}@{{u}}..{branch}", "--oneline"],
            capture_output=True, text=True
        )
        if r3b.stdout.strip():
            return "UNPUSHED"
        return "ok"
    if r3.stdout.strip():
        return "UNPUSHED"
    return "ok"


# ---------------------------------------------------------------------------
# Acceptance gate
# ---------------------------------------------------------------------------

def run_acceptance(fm):
    """Run accept_cmd and return (status_str, detail_str).
    status_str: 'PASS', 'FAIL', 'UNVERIFIABLE'.
    """
    cmd = (fm.get("accept_cmd") or "").strip()
    shell = (fm.get("accept_shell") or "").strip()
    match = (fm.get("accept_match") or "").strip()
    regex = (fm.get("accept_regex") or "").strip()
    status = (fm.get("accept_status") or "").strip()

    if status == "unverifiable" or not cmd:
        return "UNVERIFIABLE", "accept_status=unverifiable or no cmd"

    # Build argv same way finalize.py does: interpreter + cmd string
    if shell:
        argv = [shell, "-NoProfile", "-Command", cmd] if shell.lower() == "pwsh" \
            else [shell, "-c", cmd]
    else:
        try:
            argv = shlex.split(cmd, posix=True)
        except ValueError:
            argv = cmd.split()

    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=120)
        output = r.stdout + r.stderr
    except Exception as e:
        return "UNVERIFIABLE", f"exec error: {e}"

    # Check match / regex
    if match and match in output:
        return "PASS", f"match '{match}' found"
    if regex:
        if re.search(regex, output):
            return "PASS", f"regex matched"
        return "FAIL", f"regex not matched; exit={r.returncode}"
    if match and match not in output:
        return "FAIL", f"match '{match}' not found; exit={r.returncode}"
    # No match/regex -- use exit code
    if r.returncode == 0:
        return "PASS", "exit 0"
    return "FAIL", f"exit {r.returncode}"


# ---------------------------------------------------------------------------
# Table renderer
# ---------------------------------------------------------------------------

def render_table(rows):
    """Return a markdown table string."""
    header = ("| slug | beacon | gate | staleness | branch state |")
    sep    = ("|---|---|---|---|---|")
    lines  = [header, sep]
    for r in rows:
        def cell(v):
            return str(v).replace("|", "\\|")
        lines.append(
            f"| {cell(r['slug'])} "
            f"| {cell(r['beacon'])} "
            f"| {cell(r['gate'])} "
            f"| {cell(r['staleness'])} "
            f"| {cell(r['branch_state'])} |"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Babysit sweep of To Be Tested goals")
    ap.add_argument("--todo", required=True, help="path to .claude/TODO.md")
    ap.add_argument("--docs-root", required=True, help="path to docs/ dir")
    ap.add_argument("--max-age-days", type=float, default=14,
                    help="beacon mtime threshold for STALE flag (default 14)")
    ap.add_argument("--run-acceptance", action="store_true",
                    help="execute accept_cmd; without this flag, gate='not run'")
    args = ap.parse_args()

    todo_path = Path(args.todo)
    docs_root = Path(args.docs_root)

    if not todo_path.exists():
        print(f"ERROR: --todo path not found: {todo_path}", file=sys.stderr)
        sys.exit(1)
    if not docs_root.is_dir():
        print(f"ERROR: --docs-root not a directory: {docs_root}", file=sys.stderr)
        sys.exit(1)

    entries = parse_to_be_tested(todo_path)
    if not entries:
        print("(no GOAL entries found under ## To Be Tested)")
        return

    rows = []
    for e in entries:
        slug = e["slug"]
        beacon_path = locate_beacon(slug, e["beacon_hint"], docs_root)

        # Beacon cell
        if beacon_path:
            beacon_rel = beacon_path.name
        else:
            beacon_rel = "NOT FOUND"

        # Staleness
        if beacon_path and beacon_path.exists():
            stale = is_stale(beacon_path, args.max_age_days)
            staleness = "STALE" if stale else "fresh"
        else:
            staleness = "n/a"

        # Branch state + frontmatter
        fm = {}
        br_state = "n/a"
        if beacon_path and beacon_path.exists():
            fm = parse_frontmatter(beacon_path.read_text(encoding="utf-8"))
            br_state = branch_state(fm.get("branch", ""))

        # Gate
        if not args.run_acceptance:
            gate = "not run"
        elif not beacon_path or not beacon_path.exists():
            gate = "UNVERIFIABLE (no beacon)"
        else:
            gate_status, _detail = run_acceptance(fm)
            gate = gate_status

        rows.append({
            "slug": slug,
            "beacon": beacon_rel,
            "gate": gate,
            "staleness": staleness,
            "branch_state": br_state,
        })

    print(render_table(rows))


if __name__ == "__main__":
    main()
