import argparse
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from plan_parser import parse_phases, phase_rows as build_phase_rows

TEMPLATE_PATH = Path(__file__).parent.parent / "audit-tracker-template.md"

# An escape hatch with no floor becomes the default.  A reason this short is not a
# reason, it is a keystroke -- same guard shape the acceptance gate already applies.
MIN_NO_REQUIREMENT_REASON = 12


def _as_blockquote(text):
    """Render the owner's words as a markdown blockquote, verbatim.

    Deliberately NOT stored in YAML frontmatter: a real requirement runs to several
    lines or paragraphs, which frontmatter cannot hold without block-scalar syntax,
    and personal-workflow/lib/discover.py already strips block-scalar indicators.
    A body section holds multi-line text safely and reads better besides.
    """
    if not text:
        return "> (none recorded)"
    lines = str(text).replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return "\n".join(("> " + ln).rstrip() for ln in lines)

def render(slug, owner, branch, accept_cmd, accept_shell, accept_match,
           accept_regex, accept_status, accept_reason, spec_path, plan_path,
           phase_rows, phase_1_mode=None, phase_2plus_mode=None,
           auto_mode_triggers=None, max_retries=None, token_budget=None,
           vision_path=None, requirement_verbatim=None,
           requirement_status=None, text_review_status=None):
    tpl = TEMPLATE_PATH.read_text(encoding="utf-8")
    _now = datetime.datetime.now().astimezone()
    _off_h = _now.utcoffset().total_seconds() / 3600
    _tz_label = "EDT" if _off_h == -4 else "EST" if _off_h == -5 else f"UTC{int(_off_h):+d}"
    subst = {
        "{{slug}}": slug,
        "{{owner}}": owner or "owner",
        "{{timestamp_est}}": _now.strftime("%Y-%m-%d %H:%M:%S") + " " + _tz_label,
        "{{branch}}": branch,
        "{{spec_path}}": spec_path or "",
        "{{plan_path}}": plan_path or "",
        "{{accept_cmd}}": accept_cmd or "",
        "{{accept_shell}}": accept_shell or "pwsh",
        "{{accept_match}}": accept_match or "",
        "{{accept_regex}}": accept_regex or "",
        "{{accept_status}}": accept_status or "verifiable",
        "{{accept_reason}}": accept_reason or "",
        "{{purpose_or_placeholder}}": "(fill in 2-3 sentences describing this goal)",
        "{{phase_rows}}": phase_rows or "| 1 | -- | (no phases declared yet) | Pending | -- | -- |",
        "{{phase_1_mode}}": phase_1_mode or "interactive",
        "{{phase_2plus_mode}}": phase_2plus_mode or "autonomous",
        "{{auto_mode_triggers}}": auto_mode_triggers or "[T3]",
        "{{max_retries}}": str(max_retries) if max_retries is not None else "2",
        "{{token_budget_total}}": str(token_budget) if token_budget is not None else "0",
        "{{vision_path}}": vision_path or "",
        "{{requirement_status}}": requirement_status or "provided",
        "{{requirement_verbatim}}": _as_blockquote(requirement_verbatim),
        "{{text_review_status}}": text_review_status or "n/a",
    }
    for k, v in subst.items():
        tpl = tpl.replace(k, v)
    return tpl

def _resolve_requirement(args):
    """Return (requirement_text, status) or (None, None) when the goal must not arm.

    Exactly one of --requirement / --requirement-file / --no-requirement is expected.
    Errors go to stderr and yield a None status so main() can exit non-zero.
    """
    given = [bool(args.requirement), bool(args.requirement_file), bool(args.no_requirement)]
    if sum(given) > 1:
        print("beacon_writer: pass only one of --requirement, --requirement-file, "
              "--no-requirement", file=sys.stderr)
        return None, None

    if args.requirement_file:
        path = Path(args.requirement_file)
        if not path.is_file():
            print(f"beacon_writer: --requirement-file not found: {path}", file=sys.stderr)
            return None, None
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            print(f"beacon_writer: --requirement-file is empty: {path}", file=sys.stderr)
            return None, None
        return text, "provided"

    if args.requirement:
        text = args.requirement.strip()
        if not text:
            print("beacon_writer: --requirement is blank", file=sys.stderr)
            return None, None
        return text, "provided"

    if args.no_requirement:
        reason = args.no_requirement.strip()
        if len(reason) < MIN_NO_REQUIREMENT_REASON:
            print(f"beacon_writer: --no-requirement needs a real reason "
                  f"({MIN_NO_REQUIREMENT_REASON}+ chars); got {len(reason)}",
                  file=sys.stderr)
            return None, None
        return None, f"none -- {reason}"

    print("beacon_writer: refusing to arm without the owner's requirement.\n"
          "  Pass --requirement \"<their words>\", or --requirement-file <path> for a\n"
          "  multi-line ask, or --no-requirement \"<why there isn't one>\".\n"
          "  A goal with no recorded ask gives every later phase nothing to be checked\n"
          "  against, which is how the aim drifts across sessions.", file=sys.stderr)
    return None, None


def _resolve_review(args):
    """Return the text-review status, or None when the write must not happen.

    The requirement is the owner's unedited words and it lands in a git-committed
    file.  In some host repos `docs/` is tracked in git, so a real ask --
    which routinely quotes client names, account identifiers and ticket text -- would
    enter permanent company-repo history with nothing having looked at it.

    No scanner here: a regex sees shape, and the thing at risk has no shape.  A
    pattern list that cannot recognise a client name but claims to check for one is
    worse than nothing, because it licenses skipping the read-back.  So this is an
    acknowledgement, not a detection -- a refusal the caller must answer, recorded in
    the beacon so a later session can see whether anyone actually looked.
    """
    if args.text_reviewed and args.text_unreviewed:
        print("beacon_writer: pass only one of --text-reviewed / --text-unreviewed",
              file=sys.stderr)
        return None
    if args.text_reviewed:
        val = args.text_reviewed.strip()
        if len(val) < MIN_NO_REQUIREMENT_REASON:
            print(f"beacon_writer: --text-reviewed needs who confirmed and when "
                  f"({MIN_NO_REQUIREMENT_REASON}+ chars); got {len(val)}", file=sys.stderr)
            return None
        return f"reviewed -- {val}"
    if args.text_unreviewed:
        val = args.text_unreviewed.strip()
        if len(val) < MIN_NO_REQUIREMENT_REASON:
            print(f"beacon_writer: --text-unreviewed needs a real reason "
                  f"({MIN_NO_REQUIREMENT_REASON}+ chars); got {len(val)}", file=sys.stderr)
            return None
        return f"unreviewed -- {val}"
    print("beacon_writer: refusing to commit the owner's verbatim words unseen.\n"
          "  Show the captured requirement to the owner, then pass\n"
          "    --text-reviewed \"<who confirmed it, when>\"\n"
          "  or --text-unreviewed \"<why no review was possible>\".\n"
          "  This text is about to enter git history. In a company repo where docs/ is\n"
          "  tracked, removing it later means rewriting history, not editing a file.",
          file=sys.stderr)
    return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--slug", required=True)
    p.add_argument("--area", required=True)
    p.add_argument("--owner")
    p.add_argument("--branch", required=True)
    p.add_argument("--spec-path", dest="spec_path", default="")
    p.add_argument("--plan-path", dest="plan_path", default="")
    p.add_argument("--accept-cmd", dest="accept_cmd")
    p.add_argument("--accept-shell", dest="accept_shell", default="pwsh")
    p.add_argument("--accept-match", dest="accept_match")
    p.add_argument("--accept-regex", dest="accept_regex")
    p.add_argument("--unverifiable", dest="unverifiable")
    p.add_argument("--phase-1-mode", dest="phase_1_mode", default=None,
                   choices=["interactive", "autonomous"],
                   help="Operating mode for Phase 1 (default: interactive)")
    p.add_argument("--phase-2plus-mode", dest="phase_2plus_mode", default=None,
                   choices=["interactive", "autonomous"],
                   help="Operating mode for Phase 2+ (default: autonomous)")
    p.add_argument("--auto-mode-triggers", dest="auto_mode_triggers", default=None,
                   help="Comma-separated trigger list (default: [T3]; T5 struck 2026-09-18)")
    p.add_argument("--max-retries", dest="max_retries", type=int, default=2,
                   help="Per-phase FAIL retry cap (default: 2); rendered as frontmatter max_retries")
    p.add_argument("--token-budget", dest="token_budget", type=int, default=0,
                   help="Total token budget for this goal (default: 0 = unlimited); rendered as frontmatter token_budget_total")
    p.add_argument("--vision-path", dest="vision_path", default=None,
                   help="Path to the vision/why doc for this goal (optional); rendered as frontmatter vision_path")
    p.add_argument("--requirement", dest="requirement", default=None,
                   help="The owner's own words, verbatim. Never paraphrase. For a "
                        "multi-line ask use --requirement-file instead.")
    p.add_argument("--requirement-file", dest="requirement_file", default=None,
                   help="Path to a file holding the owner's verbatim ask (multi-line safe).")
    p.add_argument("--no-requirement", dest="no_requirement", default=None,
                   metavar="REASON",
                   help="Arm without a verbatim requirement. Requires a real reason "
                        f"({MIN_NO_REQUIREMENT_REASON}+ chars); it is recorded in the beacon "
                        "and the critic gate reads it.")
    p.add_argument("--text-reviewed", dest="text_reviewed", default=None, metavar="WHO_WHEN",
                   help="Confirms the captured requirement was shown to the owner before "
                        "being committed. Recorded in the beacon as text_review_status.")
    p.add_argument("--text-unreviewed", dest="text_unreviewed", default=None, metavar="REASON",
                   help="Commit the requirement without a read-back, for the recorded "
                        f"reason ({MIN_NO_REQUIREMENT_REASON}+ chars). Visible to every later "
                        "session and to the critic gate.")
    p.add_argument("--out", required=True)
    args = p.parse_args()

    # Fail closed on the requirement.  This is the whole point: a goal armed with no
    # record of what was asked for has nothing for later phases to be checked against,
    # and every session after the first inherits the plan instead of the ask.
    requirement, requirement_status = _resolve_requirement(args)
    if requirement_status is None:
        # 9, not 3: exit 3 is already finalize.py's acceptance failure and
        # personal-workflow/lib/fence.py's PAUSE-ACK-ONCE. A shared caller could not
        # tell a missing requirement from either of those.
        return 9

    # Only gate a requirement that actually exists; --no-requirement wrote nothing to
    # review.  Exit 8 keeps it distinguishable from the missing-requirement refusal.
    if requirement:
        text_review_status = _resolve_review(args)
        if text_review_status is None:
            return 8
    else:
        text_review_status = "n/a -- no requirement captured"

    if args.unverifiable:
        status, reason = "UNVERIFIED", args.unverifiable
    else:
        status, reason = "verifiable", ""
    if args.plan_path:
        phases = parse_phases(args.plan_path)
        rows = build_phase_rows(phases)
    else:
        rows = None
    content = render(args.slug, args.owner, args.branch, args.accept_cmd,
                     args.accept_shell, args.accept_match, args.accept_regex,
                     status, reason, args.spec_path, args.plan_path,
                     phase_rows=rows,
                     phase_1_mode=args.phase_1_mode,
                     phase_2plus_mode=args.phase_2plus_mode,
                     auto_mode_triggers=args.auto_mode_triggers,
                     max_retries=args.max_retries,
                     token_budget=args.token_budget,
                     vision_path=args.vision_path,
                     requirement_verbatim=requirement,
                     requirement_status=requirement_status,
                     text_review_status=text_review_status)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(content, encoding="utf-8")
    print(args.out)
    return 0

if __name__ == "__main__":
    sys.exit(main())
