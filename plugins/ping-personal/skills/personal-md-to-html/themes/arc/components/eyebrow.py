"""Render the ```eyebrow``` body-level custom block. See spec §3.2.5.

Schema: plain text content, single line, no YAML. Renders to:
    <p class="eyebrow">CONTENT</p>

The .eyebrow CSS class is already defined in tokens.css — this component
reuses it without redefinition.
"""
from __future__ import annotations
from html import escape


def render(source_text: str) -> str:
    content = source_text.strip()
    # Collapse internal whitespace runs to a single space; preserve case.
    content = " ".join(content.split())
    if not content:
        return "<!-- md-to-html: empty 'eyebrow' block -->"
    return f'<p class="eyebrow">{escape(content)}</p>'
