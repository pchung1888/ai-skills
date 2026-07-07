"""Render the ```timeline``` custom block. See spec §6.1."""
from __future__ import annotations

import re
from html import escape

EM_DASH = "—"


def render(source_text: str) -> str:
    beats = []
    chunks = [c.strip("\n") for c in re.split(r"\n\s*\n", source_text.strip("\n")) if c.strip()]
    for chunk in chunks:
        lines = chunk.splitlines()
        first = lines[0] if lines else ""
        quote = lines[1] if len(lines) > 1 else ""
        if EM_DASH in first:
            # First em-dash splits timestamp from title; subsequent em-dashes
            # remain part of the title text.
            ts, _, title = first.partition(EM_DASH)
            ts = ts.strip()
            title = title.strip()
        else:
            ts = ""
            title = first.strip()
        if not title:
            beats.append(
                f"<!-- md-to-html: skipped malformed row '{escape(chunk[:60])}' in timeline -->"
            )
            continue
        item = ['<li>']
        if ts:
            item.append(f'<span class="t">{escape(ts)}</span>')
        item.append('<span class="dot" aria-hidden="true">○</span>')
        item.append(f'<h3 class="beat">{escape(title)}</h3>')
        if quote:
            item.append(f'<p class="quote"><em>{escape(quote)}</em></p>')
        item.append('</li>')
        beats.append("".join(item))
    return '<ol class="arc timeline">' + "".join(beats) + "</ol>"
