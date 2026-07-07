#!/usr/bin/env python3
"""preflight.py -- loop-worthiness pre-flight + judgment-call exclusion +
gate-scope check + untrusted-input validation.

Jobs:
  1. check_readiness     -- is this loop-worthy (gate + budget + stop declared)?
  2. flag_excluded       -- does the intent touch a judgment-call / destructive
                            domain? (word-boundary matched)
  3. scope_warnings      -- THE GATE LAW: does the gate cover a multi-artifact goal?
  4. validate_beacon_cell / validate_skill_ref -- untrusted-input guards for the
                            unattended path (the loop re-reads its own state files).

scope_warnings is the check that would have caught the reported stutter: a goal
that says "all/every/N" with a one-file accept_cmd and no campaign is a
gate-scope mismatch -- attended WARN, unattended REFUSE (see SKILL.md).
"""
import argparse, json, re, sys

EXCLUSION_KEYWORDS = {
    # judgment-call domains (don't loop unattended without a human)
    "auth", "payment", "billing", "migration", "schema",
    "architecture", "encryption", "secret", "credential",
    # destructive / production verbs (unattended shell-exec is a SECURITY gate;
    # over-blocking here is acceptable, under-blocking is not)
    "deploy", "production", "prod", "sudo", "truncate", "drop",
    "delete", "rm", "grant", "revoke", "chmod", "chown", "wipe",
    "force push", "force-push", "push --force",
}
GATE_STOP_TOKENS = {"accept_cmd-green", "all-goals-done"}
FUZZY_STOP_TOKENS = {"fuzzy-judge", "fuzzy"}
# STOP tokens that, when declared, mean the goal already names a multi-artifact
# gate -- so the scope check should NOT warn (only accept_cmd-only goals can be
# gate-scope-narrow).
_SCOPE_OK_STOP = ("all-goals-done", "fuzzy-judge", "fuzzy")

# A goal that names MANY deliverables. "both" dropped (usually exactly 2 named
# things); numeric arm requires >1 followed by a plural noun, so "fix 1 bug" and
# "fix 3 failing tests" do not false-positive.
_MULTIPLICITY = re.compile(
    r"\b(all|every|each|several|multiple|various)\b"
    r"|\b(?:[2-9]|\d{2,})\s+[a-z]+s\b", re.IGNORECASE)
# cadence phrasing ("every 30 minutes") is not a multi-artifact goal.
_CADENCE = re.compile(
    r"\bevery\s+\d+\s*(?:s|sec|secs|second|seconds|m|min|mins|minute|minutes|"
    r"h|hr|hrs|hour|hours|d|day|days)\b", re.IGNORECASE)

# An accept_cmd that already checks MANY artifacts (so it is NOT single-file).
_AGG_TOKENS = (
    "where-object", "foreach", "for-each", "measure-object",
    "select-object", "group-object", "get-childitem",
    "| measure", "grep -c", "grep -l", "-count", ".count",
    " in @(", "\nfor ",
)
# Whole-suite gates: a test/build runner is co-extensive with an "all tests"
# goal, so it must NOT be flagged single-artifact (the green-list FP).
_TEST_RUNNER = re.compile(
    r"\b(?:npm|yarn|pnpm)\s+test\b|\bpytest\b|\bpy\.test\b|\bdotnet\s+test\b"
    r"|\bgradle\w*\s+test\b|\bmvn\s+test\b|\bgo\s+test\b|\bcargo\s+test\b"
    r"|\bjest\b|\bvitest\b|\brspec\b|\bctest\b|\bmake\s+test\b|run-?all", re.IGNORECASE)
# A real file artifact (a single named output file), by known extension.
_PATH_EXT = re.compile(
    r"[\w./\\-]+\.(?:md|txt|json|csv|ps1|py|sql|asp|vb|vbs|js|jsx|ts|tsx|html?"
    r"|xml|log|cs|yml|yaml|toml|ini|cfg)\b", re.IGNORECASE)

_BEACON_CELL_BAD = re.compile(r"\.\.[\\/]|[;&|`$<>]")
_SKILL_REF_OK = re.compile(r"^[a-z0-9][a-z0-9:_-]*$")


def _word_match(kw: str, text: str) -> bool:
    if " " in kw:  # multi-word phrase: substring is the right match
        return kw in text
    return re.search(r"(?<![a-z0-9])" + re.escape(kw) + r"(?![a-z0-9])", text) is not None


def check_readiness(contract: dict, beacon: dict) -> list[str]:
    failures = []
    budget = contract.get("BUDGET", "")
    stop = contract.get("STOP", "")
    has_crisp = bool(beacon.get("accept_cmd")) or any(t in stop for t in GATE_STOP_TOKENS)
    has_fuzzy = any(t in stop for t in FUZZY_STOP_TOKENS)
    if not (has_crisp or has_fuzzy):
        failures.append("condition-2-no-gate")
    if not ("max_iters=" in budget or "token_ceiling=" in budget):
        failures.append("condition-3-no-budget")
    if not stop:
        failures.append("condition-4-no-stop")
    return failures


def flag_excluded(intent: str) -> list[str]:
    lower = intent.lower()
    return [kw for kw in sorted(EXCLUSION_KEYWORDS) if _word_match(kw, lower)]


_PHYSICAL_ACTION = re.compile(
    r"(?<![a-z])(?:click|press|paste|screenshot|reboot|restart|unplug|"
    r"plug in|toggle|power on|power off)\b", re.IGNORECASE)
_START_STOP_TARGET = re.compile(
    r"(?<![a-z])(?:start|stop|launch|relaunch)\b[^.]{0,40}?\b"
    r"(?:service|sim|simulator|app|application|exe|server|acceptor|daemon|process)\b",
    re.IGNORECASE)
_OBSERVE_REQUEST = re.compile(
    r"\b(?:tell me|let me know|paste (?:back|the|it)|report back|"
    r"show me the (?:result|output|console|log|screen))\b", re.IGNORECASE)


# Generic OS-level deploy roots. Add your own org's deploy root(s) via the
# deploy_roots param below (e.g. a company-name Program Files subfolder) --
# this default set alone won't catch an org-specific install path.
_DEPLOY_MARKERS = ("program files", "programdata")


def is_deployed_config_path(path, deploy_roots=None):
    """True if path is a DEPLOYED (live, outside-repo) config -> must fence.
    A generic marker set alone can miss an org-specific deployed-app config
    edit; pass deploy_roots to close that gap for your own environment."""
    p = (path or "").replace("\\", "/").lower()
    if any(m in p for m in _DEPLOY_MARKERS):
        return True
    for root in (deploy_roots or []):
        if p.startswith(root.replace("\\", "/").lower()):
            return True
    return False


def detect_external_actions(text: str) -> list[str]:
    """Scan goal/phase text for external-world action language -> the driver
    auto-selects goal-phase (fence per phase) and announces why. Scoped to
    physical/UI imperatives + observation requests so descriptive prose
    ('refactor the service layer', 'run the tests') does NOT false-trigger.
    Over-detection only ever ADDS an announced fence; it never silently skips
    one (same risk posture as flag_excluded)."""
    t = text or ""
    hits = []
    if _PHYSICAL_ACTION.search(t) or _START_STOP_TARGET.search(t):
        hits.append("external-action")
    if _OBSERVE_REQUEST.search(t):
        hits.append("human-observation")
    return hits


def _is_multi(intent: str) -> bool:
    intent = intent or ""
    return bool(_MULTIPLICITY.search(intent)) and not bool(_CADENCE.search(intent))


def gate_is_single_artifact(accept_cmd: str) -> bool:
    """True if accept_cmd checks exactly one named file with no aggregation.
    A test/build runner is a whole-suite gate -> NOT single-artifact."""
    if not accept_cmd:
        return False
    low = accept_cmd.lower()
    if _TEST_RUNNER.search(low):
        return False
    if any(tok in low for tok in _AGG_TOKENS):
        return False
    paths = set(_PATH_EXT.findall(low))
    return len(paths) <= 1


def scope_warnings(intent: str, beacon: dict, campaign: bool = False, stop: str = "") -> list[str]:
    """THE GATE LAW: warn when the gate cannot cover a multi-artifact goal."""
    if campaign or any(t in (stop or "") for t in _SCOPE_OK_STOP):
        return []
    if not _is_multi(intent):
        return []
    accept_cmd = beacon.get("accept_cmd", "")
    if not accept_cmd:
        return ["gate-scope-undeclared"]
    if gate_is_single_artifact(accept_cmd):
        return ["gate-scope-narrow"]
    return []


def validate_beacon_cell(value: str) -> list[str]:
    """Untrusted-input guard: a beacon table cell (a file path) must not contain
    path traversal or shell metacharacters."""
    return ["unsafe-beacon-cell"] if _BEACON_CELL_BAD.search(value or "") else []


def validate_skill_ref(name: str) -> list[str]:
    """Untrusted-input guard: a skill:<name> ACTION must match an allowlisted
    name shape (no shell injection)."""
    return [] if _SKILL_REF_OK.match(name or "") else ["unsafe-skill-ref"]


_EXTERNAL_SOURCES = {"jira", "atlassian", "email", "m365", "slack"}


def is_external_read_allowed(source, unattended, allowlist):
    """External-service reads (jira/email/slack) are free ATTENDED; UNATTENDED
    they require the source in the declared allowlist (fail-closed). Local
    sources are always allowed."""
    if source not in _EXTERNAL_SOURCES:
        return []
    if not unattended:
        return []
    return [] if source in (allowlist or set()) else ["external-read-refused"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--intent", default="")
    ap.add_argument("--contract", default="{}")
    ap.add_argument("--beacon", default="{}")
    ap.add_argument("--stop", default="")
    ap.add_argument("--campaign", action="store_true")
    a = ap.parse_args()
    beacon = json.loads(a.beacon)
    result = {
        "failures": check_readiness(json.loads(a.contract), beacon),
        "excluded_keywords": flag_excluded(a.intent),
        "scope_warnings": scope_warnings(a.intent, beacon, a.campaign, a.stop),
    }
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
