"""Generic structural acceptance check for a prototype HTML file.

Enforces the self-containment lessons the personal-prototype skill teaches, so a
finished prototype does not have to re-derive them:

  - file exists and is non-empty
  - self-contained: no external src="http..." / url(http...) / <link href="http...">
    resource loads (icons and CSS must be base64-embedded, not linked)
  - at least one base64 data: URI present (proves icons were embedded)
  - no position:fixed (the footer-overlay-in-full-page-screenshots bug)
  - ASCII-only source (Windows PowerShell cp1252 pitfall)

Optional --marker TOKEN (repeatable) adds required strings the prototype must
contain (e.g. the feature's key labels). Marker matching is case-insensitive.

Prints CHECK-OK on success, or CHECK-FAIL: <semicolon-separated reasons>.
Exit 0 on pass, 1 on fail. Pure stdlib. ASCII source only.

Usage:
  python.exe check_prototype.py <path-to-prototype.html> [--marker TOKEN ...]
"""
import argparse
import re
import sys
from pathlib import Path

# Resource-loading attributes pointing at an absolute http(s) URL. Anchor hrefs
# (navigation) are intentionally NOT flagged - the lesson is about resources that
# must be embedded (images, scripts, stylesheets), not links a demo may carry.
EXTERNAL_PATTERNS = [
    (re.compile(r"""src\s*=\s*["']?\s*https?://""", re.IGNORECASE), 'external src="http..."'),
    (re.compile(r"""url\(\s*["']?\s*https?://""", re.IGNORECASE), 'external url(http...) in CSS'),
    (re.compile(r"""<link\b[^>]*\bhref\s*=\s*["']?\s*https?://""", re.IGNORECASE), 'external <link href="http...">'),
]
DATA_URI = re.compile(r"""data:[^;"')\s]+;base64,""", re.IGNORECASE)
POSITION_FIXED = re.compile(r"""position\s*:\s*fixed""", re.IGNORECASE)


def first_non_ascii(text):
    """Return (line_no, char) of the first non-ASCII char, or None if all ASCII."""
    for i, line in enumerate(text.splitlines(), start=1):
        for ch in line:
            if ord(ch) > 127:
                return (i, ch)
    return None


def check(path, markers):
    """Return a list of violation strings; empty list means the file passes."""
    reasons = []
    p = Path(path)
    if not p.is_file():
        return ["file missing: " + str(p)]
    raw = p.read_bytes()
    if not raw.strip():
        return ["file is empty: " + str(p)]
    text = raw.decode("utf-8", errors="replace")

    # Self-containment: no external resource loads.
    for pattern, label in EXTERNAL_PATTERNS:
        if pattern.search(text):
            reasons.append("not self-contained (" + label + ")")

    # Icons embedded as base64.
    if not DATA_URI.search(text):
        reasons.append("no base64 data: URI found (icons not embedded)")

    # The footer/header overlay bug.
    if POSITION_FIXED.search(text):
        reasons.append("position:fixed present (use static flow in prototypes)")

    # ASCII-only source.
    nonascii = first_non_ascii(text)
    if nonascii is not None:
        line_no, ch = nonascii
        reasons.append("non-ASCII char U+%04X at line %d" % (ord(ch), line_no))

    # Required markers (case-insensitive).
    low = text.lower()
    for m in markers:
        if m.lower() not in low:
            reasons.append("missing required marker: " + m)

    return reasons


def main(argv=None):
    parser = argparse.ArgumentParser(description="Structural acceptance check for a prototype HTML file.")
    parser.add_argument("html", help="path to the prototype HTML file")
    parser.add_argument("--marker", action="append", default=[],
                        help="required string the prototype must contain (repeatable)")
    args = parser.parse_args(argv)

    reasons = check(args.html, args.marker)
    if reasons:
        print("CHECK-FAIL: " + "; ".join(reasons))
        return 1
    print("CHECK-OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
