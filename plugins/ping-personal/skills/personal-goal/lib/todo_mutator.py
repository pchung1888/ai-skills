import argparse
import datetime
import re
import sys
from pathlib import Path

MINIMAL_TODO = "# TODO\n\n## In Progress\n\n## Backlog\n"

def add_in_progress(todo_path, slug, beacon_path, acceptance):
    p = Path(todo_path)
    if not p.exists():
        p.write_text(MINIMAL_TODO, encoding="utf-8")
    content = p.read_text(encoding="utf-8")
    if content.count("## In Progress") > 1:
        print("ERROR: multiple '## In Progress' headings", file=sys.stderr)
        return 2
    if "## In Progress" not in content:
        # Insert before "## Backlog" or at top
        if "## Backlog" in content:
            content = content.replace("## Backlog", "## In Progress\n\n## Backlog", 1)
        else:
            content += "\n## In Progress\n"
    today = datetime.date.today().isoformat()
    line = f"- **[GOAL {today} {slug}]** /personal-goal harness initialized. Beacon: {beacon_path}. Acceptance: {acceptance}.\n"
    # Insert line after '## In Progress' heading
    # Use lambda to avoid re.sub interpreting backslashes in replacement string (Windows paths)
    content = re.sub(r"(## In Progress\r?\n)", lambda m: m.group(1) + "\n" + line, content, count=1)
    p.write_text(content, encoding="utf-8")
    return 0

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--add", action="store_true", required=True)
    p.add_argument("--slug", required=True)
    p.add_argument("--beacon", required=True)
    p.add_argument("--acceptance", required=True)
    p.add_argument("--todo", required=True)
    args = p.parse_args()
    return add_in_progress(args.todo, args.slug, args.beacon, args.acceptance)

if __name__ == "__main__":
    sys.exit(main())
