import argparse
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from plan_parser import parse_phases, phase_rows as build_phase_rows

TEMPLATE_PATH = Path(__file__).parent.parent / "audit-tracker-template.md"

def render(slug, owner, branch, accept_cmd, accept_shell, accept_match,
           accept_regex, accept_status, accept_reason, spec_path, plan_path,
           phase_rows, phase_1_mode=None, phase_2plus_mode=None,
           auto_mode_triggers=None, max_retries=None, token_budget=None,
           vision_path=None):
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
        "{{auto_mode_triggers}}": auto_mode_triggers or "[T3, T5]",
        "{{max_retries}}": str(max_retries) if max_retries is not None else "2",
        "{{token_budget_total}}": str(token_budget) if token_budget is not None else "0",
        "{{vision_path}}": vision_path or "",
    }
    for k, v in subst.items():
        tpl = tpl.replace(k, v)
    return tpl

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
                   help="Comma-separated trigger list (default: [T3, T5])")
    p.add_argument("--max-retries", dest="max_retries", type=int, default=2,
                   help="Per-phase FAIL retry cap (default: 2); rendered as frontmatter max_retries")
    p.add_argument("--token-budget", dest="token_budget", type=int, default=0,
                   help="Total token budget for this goal (default: 0 = unlimited); rendered as frontmatter token_budget_total")
    p.add_argument("--vision-path", dest="vision_path", default=None,
                   help="Path to the vision/why doc for this goal (optional); rendered as frontmatter vision_path")
    p.add_argument("--out", required=True)
    args = p.parse_args()
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
                     vision_path=args.vision_path)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(content, encoding="utf-8")
    print(args.out)
    return 0

if __name__ == "__main__":
    sys.exit(main())
