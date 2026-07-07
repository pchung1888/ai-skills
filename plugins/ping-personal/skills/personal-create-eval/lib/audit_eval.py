#!/usr/bin/env python3
"""audit_eval.py -- eval-health auditor for ping-personal skills (ENHANCE scan mode).

For each skill directory, assess the health of its evals/ and emit findings tagged
HIGH / MED / LOW. Exit 1 if any HIGH finding exists, else exit 0.

CLI:
    python audit_eval.py [--skills-dir <dir>] [--skill <dir>] [--json]

Default --skills-dir is the parent of THIS skill (i.e. all sibling skills): the
script lives in <skills>/personal-create-eval/lib/, so the skills dir is two
parents up from the file.

Stdlib only. ASCII only in source (Windows PowerShell cp1252 pitfall). Cross-platform
paths via pathlib. Forces UTF-8 stdout so it is safe on a Windows console.
"""

import argparse
import json
import re
import sys
from pathlib import Path

# Force UTF-8 stdout/stderr so a cp1252 Windows console cannot mangle output.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        # Older Python or a non-reconfigurable stream: PYTHONIOENCODING covers it.
        pass

# Severity ordering for sorting / totals.
SEVERITIES = ("HIGH", "MED", "LOW")

# Template residue markers. We deliberately do NOT match any generic <word>:
# calibration over the real corpus showed that legitimate, filled-in files use
# pattern-placeholders like <name>.md, <SEVERITY>, <artifact>, <mode> inside
# code-spans and judge-prompt scaffolding. Matching those would fire the
# placeholder MED on ~9 healthy skills -- a dead metric (the exact anti-pattern
# this skill exists to kill). Instead we anchor on the literal sentinel tokens
# the templates ship with, which appear in NO filled-in file. See `notes`.
PLACEHOLDER_PATTERNS = (
    re.compile(r"<\.\.\.>"),            # the "Fill every <...>" template marker
    re.compile(r"<skill-name>"),        # canonical scaffold-substituted token
    re.compile(r"<behavior>"),          # grader-template slot
    re.compile(r"<grader_name>"),       # eval-plan-template slot
    re.compile(r"<judge_name>"),        # eval-plan-template slot
    re.compile(r"<judge-name>"),
    re.compile(r"<artifact type>"),     # judge-rubric-template slot
    re.compile(r"<F0\?>"),              # failure-mode id placeholder
    re.compile(r"<## Required Heading>"),
    re.compile(r"<expected token>"),
    re.compile(r"\bTODO:"),             # template residue: throw 'TODO: replace...'
)

# Files we scan for placeholder residue (only the ones that exist).
PLACEHOLDER_FILES = ("eval-plan.md", "eval.ps1", "judge-rubric.md")

# Extensions that count as a "lib script path" for the unwired check. The spec
# scopes this to script references (Join-Path ... 'something' that is a script);
# .md references (e.g. an agent file) are out of scope and stay clean.
SCRIPT_EXTS = (".py", ".ps1")

# Anchor on Join-Path so we only scan PATH literals, not arbitrary quoted
# strings. A Join-Path takes a base token (a $variable, or a parenthesized
# sub-expression) followed by a quoted child literal -- e.g.
#   Join-Path $Lib 'advance.py'
#   Join-Path $SkillDir 'tests/smoke.py'
# We capture that trailing quoted literal. This deliberately does NOT match a
# command-argument string buried in an array such as @('--accept-cmd','pwsh x.ps1')
# (calibration showed that over-greedy "any quoted .ps1" leaked a false LOW).
JOINPATH_LITERAL_RE = re.compile(
    r"""Join-Path\s+(?:\$\w+|\([^)]*\))\s+['"]([^'"]+)['"]""")


class Finding:
    """One eval-health finding for a single skill."""

    def __init__(self, severity, code, message):
        self.severity = severity
        self.code = code
        self.message = message

    def to_dict(self, skill_name):
        return {
            "skill": skill_name,
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
        }


def _read_text(path):
    """Read a file as UTF-8, tolerating odd bytes. Returns '' if unreadable."""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _find_placeholders(text):
    """Return the sorted set of distinct placeholder tokens present in text."""
    hits = set()
    for pat in PLACEHOLDER_PATTERNS:
        for m in pat.finditer(text):
            hits.add(m.group(0))
    return sorted(hits)


def _joinpath_script_refs(ps1_text):
    """Extract Join-Path child literals from eval.ps1 that name a script (.py/.ps1).

    We do NOT try to resolve the PowerShell variable base of each Join-Path
    (that way lies a mini-interpreter). We collect the quoted child literal of
    every Join-Path whose basename ends in a script extension, then let the
    caller check existence by basename anywhere under the skill tree. Directory
    tokens ('lib', '..'), SKILL.md, and .md agent references are naturally
    skipped by the extension filter; non-path command-argument strings are
    skipped because they are not Join-Path children.
    """
    refs = []
    for m in JOINPATH_LITERAL_RE.finditer(ps1_text):
        literal = m.group(1)
        # Normalize both separator styles, take the basename.
        base = re.split(r"[\\/]", literal)[-1]
        low = base.lower()
        if low.endswith(SCRIPT_EXTS):
            refs.append((literal, base))
    return refs


def audit_skill(skill_dir):
    """Audit a single skill directory; return (skill_name, [Finding, ...])."""
    findings = []
    skill_name = skill_dir.name
    evals_dir = skill_dir / "evals"
    eval_ps1 = evals_dir / "eval.ps1"

    # HIGH: no evals/ dir, OR no evals/eval.ps1 (missing eval entirely).
    if not evals_dir.is_dir():
        findings.append(Finding("HIGH", "no_evals_dir",
                                 "no evals/ directory -- skill has no eval at all"))
        return skill_name, findings  # nothing else to check without an evals/ dir
    if not eval_ps1.is_file():
        findings.append(Finding("HIGH", "no_eval_ps1",
                                 "evals/ exists but no eval.ps1 -- no runnable grader"))
        # Continue: we can still flag plan/placeholder/fixture issues below.

    # MED: evals/ exists but no eval-plan.md.
    eval_plan = evals_dir / "eval-plan.md"
    if not eval_plan.is_file():
        findings.append(Finding("MED", "no_eval_plan",
                                 "evals/ exists but no eval-plan.md -- the failure map is missing"))

    # MED: eval.ps1 contains ZERO 'throw' tokens (a grader that can never fail).
    if eval_ps1.is_file():
        ps1_text = _read_text(eval_ps1)
        if "throw" not in ps1_text:
            findings.append(Finding("MED", "no_throw",
                                     "eval.ps1 has no 'throw' -- the grader can never fail "
                                     "(measures nothing)"))
    else:
        ps1_text = ""

    # MED: leftover placeholder token (<...>-style residue or 'TODO:') in any of
    # eval-plan.md / eval.ps1 / judge-rubric.md.
    for fname in PLACEHOLDER_FILES:
        fpath = evals_dir / fname
        if not fpath.is_file():
            continue
        hits = _find_placeholders(_read_text(fpath))
        if hits:
            findings.append(Finding(
                "MED", "placeholder",
                "leftover template placeholder(s) in {0}: {1}".format(
                    fname, ", ".join(hits))))

    # LOW: fixtures/ with good-* files but NO bad-* files (uncalibrated grader).
    fixtures_dir = evals_dir / "fixtures"
    if fixtures_dir.is_dir():
        names = [p.name for p in fixtures_dir.iterdir() if p.is_file()]
        has_good = any(n.startswith("good-") for n in names)
        has_bad = any(n.startswith("bad-") for n in names)
        if has_good and not has_bad:
            findings.append(Finding(
                "LOW", "uncalibrated_fixtures",
                "fixtures/ has good-* but no bad-* -- grader is uncalibrated "
                "(may accept everything)"))

    # LOW: eval.ps1 references a script path (.py/.ps1 literal) that does not
    # exist anywhere under the skill dir (the unwired-registry trap).
    if ps1_text:
        for literal, base in _joinpath_script_refs(ps1_text):
            found = any(p.name == base for p in skill_dir.rglob(base))
            if not found:
                findings.append(Finding(
                    "LOW", "unwired_script",
                    "eval.ps1 references script '{0}' but no '{1}' exists under "
                    "the skill dir (unwired)".format(literal, base)))

    return skill_name, findings


def discover_skill_dirs(args):
    """Resolve the list of skill directories to audit from CLI args."""
    if args.skill:
        return [Path(args.skill).resolve()]
    if args.skills_dir:
        base = Path(args.skills_dir).resolve()
    else:
        # Default: the parent of THIS skill. lib/ -> personal-create-eval -> skills.
        base = Path(__file__).resolve().parents[2]
    if not base.is_dir():
        return []
    return sorted(p for p in base.iterdir() if p.is_dir())


def print_report(results):
    """Print a readable per-skill report and severity totals. Returns total HIGH count."""
    totals = {s: 0 for s in SEVERITIES}
    high_count = 0
    print("=" * 64)
    print("EVAL HEALTH AUDIT")
    print("=" * 64)
    for skill_name, findings in results:
        if not findings:
            print("[OK]   {0}: healthy".format(skill_name))
            continue
        print("[!!]   {0}: {1} finding(s)".format(skill_name, len(findings)))
        # Show findings worst-first.
        ordered = sorted(findings, key=lambda f: SEVERITIES.index(f.severity))
        for f in ordered:
            totals[f.severity] += 1
            if f.severity == "HIGH":
                high_count += 1
            print("         [{0:<4}] {1}: {2}".format(f.severity, f.code, f.message))
    print("-" * 64)
    print("TOTALS: HIGH={0}  MED={1}  LOW={2}  (skills audited: {3})".format(
        totals["HIGH"], totals["MED"], totals["LOW"], len(results)))
    if high_count:
        print("RESULT: FAIL -- {0} high-severity finding(s); exit 1".format(high_count))
    else:
        print("RESULT: PASS -- no high-severity findings; exit 0")
    print("=" * 64)
    return high_count


def emit_json(results):
    """Emit findings as a flat JSON array. Returns total HIGH count."""
    out = []
    high_count = 0
    for skill_name, findings in results:
        for f in findings:
            out.append(f.to_dict(skill_name))
            if f.severity == "HIGH":
                high_count += 1
    print(json.dumps(out, indent=2))
    return high_count


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Audit eval health across ping-personal skills.")
    parser.add_argument("--skills-dir",
                        help="directory whose subdirectories are skills to audit "
                             "(default: the parent of this skill)")
    parser.add_argument("--skill",
                        help="audit a single skill directory instead of a whole tree")
    parser.add_argument("--json", action="store_true",
                        help="emit a JSON array of findings instead of a report")
    args = parser.parse_args(argv)

    skill_dirs = discover_skill_dirs(args)
    if not skill_dirs:
        target = args.skill or args.skills_dir or "(default skills dir)"
        sys.stderr.write("audit_eval: no skill directories found at: {0}\n".format(target))
        return 2

    results = [audit_skill(d) for d in skill_dirs]

    if args.json:
        high_count = emit_json(results)
    else:
        high_count = print_report(results)

    return 1 if high_count else 0


if __name__ == "__main__":
    sys.exit(main())
