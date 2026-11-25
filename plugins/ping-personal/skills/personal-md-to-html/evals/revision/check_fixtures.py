#!/usr/bin/env python3
"""Checks the made-up revision fixtures. Usage: check_fixtures.py [--scrub-diff <commit>]
Prints one line per failed rule, then FIXTURES PASS/FAIL (and SCRUB PASS/FAIL with the flag)."""
import json, re, subprocess, sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
FX = HERE / "fixtures"
REPO = HERE.parents[5]
FILES = ["old-plain.html", "old-script.html", "interactive.md", "walk.json", "placement.html", "targets.json"]
GATE1 = ["h", "p", "li", "btn", "img", "tbl", "code", "dia"]
bad = []


def fail(msg):
    bad.append(msg)
    print(msg)


texts = {}
for n in FILES:
    p = FX / n
    if not p.is_file():
        fail("missing file: " + n)
        continue
    raw = p.read_bytes()
    try:
        texts[n] = raw.decode("ascii")
    except UnicodeDecodeError:
        fail("not ASCII: " + n)

if "targets.json" in texts:
    try:
        t = json.loads(texts["targets.json"])
        if len(t) != 20:
            fail("targets.json has %d entries, need 20" % len(t))
        c = Counter(x["kind"] for x in t)
        for k in GATE1:
            if c[k] < 2:
                fail("targets.json kind %s has %d, need 2+" % (k, c[k]))
        if "placement.html" in texts:
            html = set(re.findall(r'data-fx="([^"]+)"', texts["placement.html"]))
            js = {x["fx"] for x in t}
            if html != js:
                fail("data-fx mismatch: html-only %s, json-only %s" % (sorted(html - js), sorted(js - html)))
    except Exception as e:
        fail("targets.json parse: %s" % e)

if "old-plain.html" in texts:
    if "data-rev-id" in texts["old-plain.html"]:
        fail("old-plain.html has data-rev-id")
    if "<script" in texts["old-plain.html"]:
        fail("old-plain.html has <script")

if "interactive.md" in texts:
    m = re.match(r"---\n(.*?)\n---\n", texts["interactive.md"], re.S)
    if not m or not re.search(r"^interactive:\s*true\s*$", m.group(1), re.M):
        fail("interactive.md frontmatter missing or no interactive: true")

if "walk.json" in texts:
    try:
        json.loads(texts["walk.json"])
    except Exception as e:
        fail("walk.json parse: %s" % e)

print("FIXTURES FAIL" if bad else "FIXTURES PASS")

if "--scrub-diff" in sys.argv:
    commit = sys.argv[sys.argv.index("--scrub-diff") + 1]
    inp = REPO / "docs/revision-mode/autopilot/inputs.json"
    pats = []
    if inp.is_file():
        pats = [re.compile(x) for x in json.loads(inp.read_text(encoding="utf-8")).get("scrubPatterns", [])]

    git_failed = []

    def git(*a):
        r = subprocess.run(["git", "-C", str(REPO)] + list(a), capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            git_failed.append(" ".join(a))
        return r.stdout

    lines = [l[1:] for l in git("diff", commit).splitlines() if l.startswith("+") and not l.startswith("+++")]
    for f in git("ls-files", "--others", "--exclude-standard", "plugins/").splitlines():
        try:
            lines += (REPO / f).read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            pass
    hits = ["pattern #%d" % i for l in lines for i, p in enumerate(pats) if p.search(l)]
    for h in hits[:20]:
        print("scrub hit: " + h + " (matched text not printed)")
    if not pats:
        print("scrub error: no scrubPatterns loaded from inputs.json")
    for g in git_failed:
        print("scrub error: git " + g + " failed")
    scrub_bad = bool(hits or not pats or git_failed)
    print("SCRUB FAIL" if scrub_bad else "SCRUB PASS")
    bad += hits + (["scrub"] if scrub_bad else [])

sys.exit(1 if bad else 0)
