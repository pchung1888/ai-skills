#!/usr/bin/env python3
"""fence.py -- decide whether a proposed action must PAUSE for operator approval.

Exit codes:
  0  ALLOW           no fence match
  2  PAUSE-ALWAYS    destructive / irreversible
  3  PAUSE-ACK-ONCE  routine-but-sensitive (app-pool restart); conductor asks once per run

Covers ONLY the regex-able subset of the fence: destructive commands + sensitive paths.
The CONTEXTUAL hard rules (no-PII-in-commit, branch-policy, etc.) are applied by the
conductor as JUDGMENT, NOT here.

PORTABILITY (FIX-4): this pattern set is the PROJECT-AGNOSTIC baseline that mirrors the
ping-personal `personal-critic-gate` Stay-Paused List -- force-push, schema-destructive DDL,
.gitignore / .claude/settings*.json mutations, .env* writes, lockfile rewrites, release/deploy
dirs -- plus the obvious-destructive default set. It deliberately ships NO host-specific paths
(no registry keys, no per-project release folders beyond the generic dist/build/out/Releases).
A host project extends this via its own CLAUDE.md / rule files; the fence and the critic gate
agree by construction.
"""
import re
import sys

PAUSE_ALWAYS = [
    # --- schema-destructive DDL ---
    r"\bDROP\s+(TABLE|DATABASE|PROCEDURE|VIEW|INDEX|FUNCTION|SCHEMA)\b",
    r"\bTRUNCATE\s+TABLE\b",
    r"\bALTER\s+TABLE\b.*\bDROP\s+COLUMN\b",
    r"\bDELETE\s+FROM\b(?![^;\n]*\bWHERE\b)",        # DELETE without a SAME-STATEMENT WHERE
    r"\bUPDATE\b\s+[\w.\[\]@#]+\s+SET\b(?![^;\n]*\bWHERE\b)",  # UPDATE (any target shape) without WHERE
    # NOTE: the no-WHERE lookahead is bounded to one statement (stops at ; or newline) so a WHERE in a
    # LATER batch/line cannot smuggle a bare DELETE/UPDATE past the fence (gate finding, codex). It
    # over-pauses a safe statement that puts WHERE on the next line -- intentional: over-pause, never
    # under-pause. The SQL subset is best-effort; the conductor's VERIFY/judgment backs it.
    # --- irreversible git ---
    r"\bgit\s+push\b",                               # any push pauses (over-pause, never under)
    r"\bgit\s+reset\s+--hard\b",
    r"\bgit\s+branch\s+-D\b",
    r"\bgit\s+clean\b[^\n]*(--force|-[a-z]*f)",      # -f / -fd / -xf AND long-form --force (gate finding)
    r"\bgit\s+rebase\b",                             # shared-ness is not regex-detectable -> over-pause
    r"\bgit\s+filter-branch\b",
    # --- generic destructive filesystem (RESTORED from the host-repo corpus; gate finding H1) ---
    r"\brm\s+-[rf]",                                 # rm -r / -f / -rf
    r"Remove-Item[^\n]*-(Recurse|Force)\b",          # recursive / forced delete
    # --- generic Windows-destructive (host-conditional; never matches on non-Windows hosts) ---
    r"\biisreset\b",
    r"Remove-Item[^\n]*HK(LM|CU):",                  # registry destroy
]
SENSITIVE_PATHS = [
    r"\.gitignore\b",
    r"\.claude[/\\]settings(\.local)?\.json\b",
    r"\.env(\.[\w.-]+)?\b",                          # .env, .env.production, .env.local, ...
    r"\b(package-lock\.json|yarn\.lock|pnpm-lock\.yaml|Cargo\.lock)\b",
    r"\b(Releases|dist|build|out)[/\\]",             # release/deploy dirs
]
PAUSE_ACK_ONCE = [
    r"\bRestart-WebAppPool\b",
]

def classify(action):
    for pat in PAUSE_ALWAYS + SENSITIVE_PATHS:
        if re.search(pat, action, re.IGNORECASE):
            return 2, pat
    for pat in PAUSE_ACK_ONCE:
        if re.search(pat, action, re.IGNORECASE):
            return 3, pat
    return 0, None

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--action", required=True)
    a = ap.parse_args()
    code, pat = classify(a.action)
    label = {0: "ALLOW", 2: "PAUSE-ALWAYS", 3: "PAUSE-ACK-ONCE"}[code]
    sys.stdout.buffer.write(f"{label}\t{pat or ''}\n".encode("utf-8"))
    sys.exit(code)
