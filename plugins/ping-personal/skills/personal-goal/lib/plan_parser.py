import re
import sys
from pathlib import Path

PHASE_RE = re.compile(r"^#{2,3}\s+Phase\s+(\d+)(?:\s*[:\-]\s*(.+?))?\s*$", re.MULTILINE)

def parse_phases(plan_path):
    text = Path(plan_path).read_text(encoding="utf-8")
    phases = []
    for m in PHASE_RE.finditer(text):
        n = int(m.group(1))
        title = (m.group(2) or "").strip()
        phases.append((n, title))
    return phases

def phase_rows(phases):
    rows = []
    for n, title in phases:
        rows.append(f"| {n} | Plan §Phase {n} | {title} | ⬜ Pending | -- | -- |")
    return "\n".join(rows)

if __name__ == "__main__":
    phases = parse_phases(sys.argv[1])
    print(phase_rows(phases))
