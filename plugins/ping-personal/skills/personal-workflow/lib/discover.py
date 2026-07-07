#!/usr/bin/env python3
"""discover.py -- emit the PROJECT half of the personal-workflow capability map as JSON.

Reads the FILESYSTEM only. A subprocess cannot see the model's skill registry, so this
script never emits plugin/built-in skills (ping-personal:*, superpowers:*, gstack, ...).
The MODEL folds those in at runtime (see SKILL.md "Discovery").

Defaults point at the HOST project's .claude/skills and .claude/agents (the cwd where the
operator runs /personal-workflow) -- NOT the plugin dir. So the conductor discovers whatever
project it is dropped into. See port-design doc sections 4-5.
"""
import json
import re
import sys
from pathlib import Path

FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

def _frontmatter(text):
    m = FM_RE.match(text)
    return m.group(1) if m else ""

def _field(fm, key):
    m = re.search(rf"^{key}:\s*(.*?)(?=\n\S+:|\Z)", fm, re.DOTALL | re.MULTILINE)
    return m.group(1).strip() if m else ""

def _clean(desc):
    # strip a leading YAML block-scalar indicator (> or |, optional +/- chomp) and fold whitespace
    desc = re.sub(r"^[>|][+-]?", "", desc.strip())
    return re.sub(r"\s+", " ", desc).strip()

def _is_empty_desc(desc):
    # strip whitespace and any run of dashes (the registry-render artifact is literal "---")
    return desc.strip().strip("-").strip() == ""

def _body_fallback(text):
    body = FM_RE.sub("", text, count=1)
    lines = [l.strip() for l in body.splitlines()]
    head = next((l for l in lines if l.startswith("#")), "")
    para = next((l for l in lines if l and not l.startswith("#")), "")
    return (head.lstrip("# ").strip() + " " + para).strip()

def _row(text, name, kind):
    fm = _frontmatter(text)
    nm = _field(fm, "name") or name
    desc = _clean(_field(fm, "description"))
    confidence = "high"
    if _is_empty_desc(desc):
        desc = _clean(_body_fallback(text))
        confidence = "low"
    row = {"name": nm, "kind": kind, "description": desc, "confidence": confidence}
    if kind == "skill":
        row["invoke"] = "Skill"
    else:
        row["invoke"] = "Agent"
        row["subagent_type"] = nm
    return row

def discover(skills_dir, agents_dir):
    rows = []
    for p in sorted(Path(skills_dir).glob("*/SKILL.md")):
        rows.append(_row(p.read_text(encoding="utf-8"), p.parent.name, "skill"))
    for p in sorted(Path(agents_dir).glob("*.md")):
        rows.append(_row(p.read_text(encoding="utf-8"), p.stem, "agent"))
    return {"source": "filesystem", "rows": rows}

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--skills-dir", default=".claude/skills")
    ap.add_argument("--agents-dir", default=".claude/agents")
    ap.add_argument("--out", default="-")
    a = ap.parse_args()
    payload = json.dumps(discover(a.skills_dir, a.agents_dir), indent=2, ensure_ascii=False)
    if a.out == "-":
        sys.stdout.buffer.write(payload.encode("utf-8"))  # bypass cp1252 console
        sys.stdout.buffer.write(b"\n")
    else:
        Path(a.out).write_text(payload, encoding="utf-8")
