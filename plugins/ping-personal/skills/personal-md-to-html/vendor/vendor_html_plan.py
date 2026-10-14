"""Copy the html-plan runtime into vendor/html-plan/ as pure ASCII.

Usage: python vendor/vendor_html_plan.py <html-plan runtime folder>
Example: python vendor/vendor_html_plan.py C:/Users/<you>/.claude/plugins/cache/claude-community/html-plan/1.0.0/skills/html-plan/runtime

Every non-ASCII character becomes an escape the browser reads as the same character:
\\uXXXX in htmlplan.js (surrogate pairs above U+FFFF), \\XXXXXX in htmlplan.css.
"""
import sys
from pathlib import Path

src = Path(sys.argv[1])
out = Path(__file__).resolve().parent / "html-plan"


def js_escape(text):
    def one(c):
        o = ord(c)
        if o < 128:
            return c
        if o <= 0xFFFF:
            return "\\u%04x" % o
        o -= 0x10000
        return "\\u%04x\\u%04x" % (0xD800 + (o >> 10), 0xDC00 + (o & 0x3FF))
    return "".join(one(c) for c in text)


def css_escape(text):
    return "".join(c if ord(c) < 128 else "\\%06x" % ord(c) for c in text)


for name, fn in (("htmlplan.js", js_escape), ("htmlplan.css", css_escape)):
    text = (src / name).read_text(encoding="utf-8")
    (out / name).write_text(fn(text), encoding="ascii", newline="\n")
    print(f"{name}: {len(text)} chars -> {out / name}")
