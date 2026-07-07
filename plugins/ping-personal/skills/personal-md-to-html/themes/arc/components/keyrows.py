"""Render the ```keyrows``` custom block. See spec §6.5."""
from __future__ import annotations
from html import escape

DELIM = " : "


def render(source_text: str) -> str:
    rows = []
    for raw_line in source_text.strip("\n").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if DELIM not in line:
            rows.append(
                f"<!-- md-to-html: skipped malformed row '{escape(line[:60])}' in keyrows -->"
            )
            continue
        left, _, right = line.partition(DELIM)
        rows.append(
            f"<dt>{escape(left.strip().lower())}</dt><dd>{escape(right.strip())}</dd>"
        )
    return '<dl class="keyrows">' + "".join(rows) + "</dl>"
