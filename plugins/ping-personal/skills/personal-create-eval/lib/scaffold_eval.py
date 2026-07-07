#!/usr/bin/env python3
"""Scaffold an evals/ directory for a target skill (CREATE mode helper).

Generates evals/eval-plan.md + evals/eval.ps1 + evals/fixtures/.gitkeep from
the templates under ../references/templates/, with --taste also writing
evals/judge-rubric.md. Every literal '<skill-name>' token in each written file
is replaced with the target skill's frontmatter name (or the dir basename).

Idempotent: existing target files are skipped unless --force. --dry-run prints
the actions it WOULD take and writes nothing.

Python 3 stdlib only. ASCII source only (Windows PowerShell cp1252 pitfall).
Cross-platform paths via pathlib.
"""

import argparse
import sys
from pathlib import Path

# Force UTF-8 stdout so emitting paths/messages is safe on a cp1252 Windows console.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

PLACEHOLDER = "<skill-name>"

# Templates live at ../references/templates/ relative to THIS script file.
SCRIPT_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = SCRIPT_DIR.parent / "references" / "templates"

TEMPLATES = {
    "eval-plan.md": TEMPLATE_DIR / "eval-plan-template.md",
    "eval.ps1": TEMPLATE_DIR / "eval-grader-template.ps1",
}
TASTE_TEMPLATE = {
    "judge-rubric.md": TEMPLATE_DIR / "judge-rubric-template.md",
}


def read_skill_name(skill_dir: Path) -> str:
    """Return the SKILL.md frontmatter 'name:' value, else the dir basename.

    A missing SKILL.md or a missing name line is NOT fatal -- fall back to the
    directory basename. Only a missing target dir is fatal (handled by caller).
    """
    fallback = skill_dir.name
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return fallback
    text = skill_md.read_text(encoding="utf-8")
    lines = text.splitlines()
    # Frontmatter is the block between the first two '---' delimiter lines.
    if not lines or lines[0].strip() != "---":
        return fallback
    for line in lines[1:]:
        stripped = line.strip()
        if stripped == "---":
            break
        if stripped.startswith("name:"):
            value = stripped[len("name:"):].strip()
            # Strip surrounding single or double quotes if present.
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                value = value[1:-1].strip()
            if value:
                return value
    return fallback


def plan_file(target: Path, force: bool) -> str:
    """Decide the verb for one target file: write / overwrite / skip."""
    if target.exists():
        return "overwrite" if force else "skip"
    return "write"


def emit(message: str, dry_run: bool) -> None:
    """Print an action line, prefixed with 'would ' in dry-run mode."""
    if dry_run:
        print("would " + message)
    else:
        print(message)


def render_and_write(src: Path, dest: Path, skill_name: str) -> None:
    content = src.read_text(encoding="utf-8")
    content = content.replace(PLACEHOLDER, skill_name)
    dest.write_text(content, encoding="utf-8", newline="")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Scaffold an evals/ directory for a target skill."
    )
    parser.add_argument("--skill", required=True, help="path to the target skill dir")
    parser.add_argument("--taste", action="store_true",
                        help="also write judge-rubric.md for taste-heavy skills")
    parser.add_argument("--force", action="store_true",
                        help="overwrite existing target files instead of skipping")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the actions that WOULD be taken; write nothing")
    args = parser.parse_args(argv)

    skill_dir = Path(args.skill).resolve()
    if not skill_dir.is_dir():
        print("ERROR: target skill dir not found: " + str(skill_dir), file=sys.stderr)
        return 1

    skill_name = read_skill_name(skill_dir)
    print("skill name: " + skill_name)
    print("target: " + str(skill_dir / "evals"))

    evals_dir = skill_dir / "evals"
    fixtures_dir = evals_dir / "fixtures"

    # Directory creation (idempotent; nothing happens in dry-run).
    if args.dry_run:
        if not evals_dir.exists():
            emit("create dir " + str(evals_dir), True)
        if not fixtures_dir.exists():
            emit("create dir " + str(fixtures_dir), True)
    else:
        evals_dir.mkdir(parents=True, exist_ok=True)
        fixtures_dir.mkdir(parents=True, exist_ok=True)

    # Assemble the full set of files to (maybe) write.
    jobs = []  # (dest_path, source_template_or_None)
    for fname, src in TEMPLATES.items():
        jobs.append((evals_dir / fname, src))
    if args.taste:
        for fname, src in TASTE_TEMPLATE.items():
            jobs.append((evals_dir / fname, src))
    # .gitkeep is a content file too -- same skip/force logic, no substitution.
    gitkeep = fixtures_dir / ".gitkeep"
    jobs.append((gitkeep, None))

    for dest, src in jobs:
        verb = plan_file(dest, args.force)
        label = dest.name if dest.name != ".gitkeep" else "fixtures/.gitkeep"
        if verb == "skip":
            emit("skip (exists) " + label, args.dry_run)
            continue
        # verb is 'write' or 'overwrite'
        if not args.dry_run:
            if src is None:
                dest.write_text("", encoding="utf-8", newline="")
            else:
                render_and_write(src, dest, skill_name)
        emit(verb + " " + label, args.dry_run)

    # Reminder (printed in both modes).
    print("")
    print("reminder:")
    print("  - run-all.ps1 auto-discovers evals/eval.ps1 by glob; there is no registration step.")
    print("  - the <...> placeholders in the written files must be filled in before relying on the eval.")
    print("  - calibrate graders against good-* and bad-* fixtures; a grader that passes everything measures nothing.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
