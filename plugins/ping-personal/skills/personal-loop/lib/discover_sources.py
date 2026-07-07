#!/usr/bin/env python3
"""discover_sources.py -- the repo-local half of the evidence map + the merge
contract + the locations-not-secrets enforcer.

Discovery is hybrid (spec S3.1): this lib does the deterministic, READ-ONLY
repo probes; the model supplies the self-observation half (which MCP servers /
skills / agents are live) into typed slots. merge_evidence() owns the merged
schema so neither half can silently corrupt the map. assert_no_secret_value()
makes "locations, not secrets" enforceable rather than aspirational.
"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
import secrets_scan

_TICKET = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")
_REQUIRED_SLOTS = {"jira", "codebase", "logs", "graph", "db"}
_OBSERVED_SLOTS = _REQUIRED_SLOTS | {"email", "slack"}
_RUNNER_MARKERS = (
    ("package.json", "npm test"), ("pyproject.toml", "pytest"),
    ("pytest.ini", "pytest"), ("Cargo.toml", "cargo test"),
    ("go.mod", "go test"), ("pom.xml", "mvn test"),
)
_GRAPH_DIRS = (("understand-anything", ".understand"), ("graphify", "graphify-output"))


def _detect_runner(root):
    for marker, label in _RUNNER_MARKERS:
        if os.path.exists(os.path.join(root, marker)):
            return label
    return None


def _detect_graph(root):
    for tool, d in _GRAPH_DIRS:
        if os.path.isdir(os.path.join(root, d)):
            return {"tool": tool, "path": d}
    return {"tool": None, "path": None}


def _detect_db_keys(root):
    # record KEY NAMES only, never values
    env = os.path.join(root, ".claude", ".env")
    keys = []
    if os.path.isfile(env):
        for line in open(env, encoding="utf-8", errors="replace"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k = line.split("=", 1)[0].strip()
                if any(t in k.upper() for t in ("CONN", "DB", "SQL", "DATABASE")):
                    keys.append(f".env:{k}")
    return {"creds_at": keys}


def probe_repo(root, goal_text="", branch=""):
    """Read-only filesystem/repo probe -> the repo-local half of the map.
    Records LOCATIONS only (e.g. a .env key NAME), never a secret value."""
    tickets = _TICKET.findall(goal_text or "") + _TICKET.findall(branch or "")
    logs = [d for d in ("logs", "log", os.path.join(".claude", "tmp"))
            if os.path.isdir(os.path.join(root, d))]
    return {
        "jira": {"ticket": tickets[0] if tickets else None, "mode": "read"},
        "codebase": {"root": root,
                     "vcs": "git" if os.path.isdir(os.path.join(root, ".git")) else None,
                     "test_runner": _detect_runner(root)},
        "logs": {"paths": logs, "screen_only": False},
        "graph": _detect_graph(root),
        "db": _detect_db_keys(root),
    }


def merge_evidence(script_part, observed_part):
    """Own the merged-map schema. script_part = probe_repo output; observed_part
    = model self-observation into typed slots. Raises ValueError on an unknown
    slot, a non-object slot, or a missing required slot, so a bad self-
    observation cannot silently corrupt the map."""
    merged = dict(script_part or {})
    for k, v in (observed_part or {}).items():
        if k not in _OBSERVED_SLOTS:
            raise ValueError(f"unknown evidence slot: {k}")
        if not isinstance(v, dict):
            raise ValueError(f"evidence slot {k} must be an object")
        merged.setdefault(k, {}).update(v)
    missing = _REQUIRED_SLOTS - set(merged)
    if missing:
        raise ValueError(f"map missing required slots: {sorted(missing)}")
    return merged


def assert_no_secret_value(evidence_map):
    """Enforce 'locations, not secrets': the assembled map must not contain a
    secret VALUE. Run the project scanner over the serialized map; any hit
    raises (refuse to write the map)."""
    hits = secrets_scan.scan(json.dumps(evidence_map, default=str))
    if hits:
        raise ValueError(f"evidence map contains secret value(s): {hits}")
