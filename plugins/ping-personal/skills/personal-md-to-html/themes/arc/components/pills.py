"""Inline pill transform: split text tokens on [[…]]. See spec §3.2.6, §3.2.9.

Supports:
  [[TAG]]            → <span class="pill">TAG</span>        (default outlined)
  [[TAG|good]]       → <span class="pill pill--good">TAG</span>
  [[TAG|warn]]       → <span class="pill pill--warn">TAG</span>
  [[TAG|muted]]      → <span class="pill pill--muted">TAG</span>
  [[TAG|ANYTHING]]   → <span class="pill">TAG</span>  (unknown variant stripped)

Decision for v1: unknown variant suffix is stripped from display content and
the pill falls back to the default outlined style. So [[X|GOOD]] renders
identically to [[X]] — the pipe+suffix are consumed but discarded.

The pill-meta upgrade (float right) applies when the pill is the LAST
non-whitespace child of a paragraph_open OR heading_open parent block.
Phase 8 extends the original paragraph-only scope to also cover headings
(spec §3.2.9).
"""
from __future__ import annotations
import re
from html import escape

# Permissive: capture everything after | as the variant candidate.
# Group 1 = label content (no brackets or pipe).
# Group 2 = variant string or None (everything after | if present).
PILL_RE = re.compile(r"\[\[([^\[\]|]+)(?:\|([^\[\]]*))?\]\]")
ALLOWED_VARIANTS = {"good", "warn", "muted"}

# Matches any pill open-tag regardless of whether a variant class is present.
# Group 1 = the variant suffix (e.g. " pill--warn") or empty string if none.
_PILL_OPEN_RE = re.compile(r'^<span class="pill( pill--(?:good|warn|muted))?">')


def _pill_html(label: str, variant: str | None) -> str:
    """Emit a pill span. Unknown or absent variant → default outlined class."""
    if variant is not None and variant in ALLOWED_VARIANTS:
        cls = f"pill pill--{variant}"
    else:
        cls = "pill"
    return f'<span class="{cls}">{escape(label)}</span>'


def transform_pills(children, parent_block_type: str):
    from markdown_it.token import Token
    out = []
    for child in children:
        if child.type != "text" or "[[" not in child.content:
            out.append(child)
            continue
        text = child.content
        pos = 0
        for m in PILL_RE.finditer(text):
            if m.start() > pos:
                t = Token("text", "", 0)
                t.content = text[pos:m.start()]
                out.append(t)
            pill = Token("html_inline", "", 0)
            pill.content = _pill_html(m.group(1), m.group(2))
            out.append(pill)
            pos = m.end()
        if pos < len(text):
            t = Token("text", "", 0)
            t.content = text[pos:]
            out.append(t)
    if parent_block_type in ("paragraph_open", "heading_open"):
        return _mark_last_pill_as_meta(out)
    return out


def _mark_last_pill_as_meta(tokens):
    """Walk in reverse; skip whitespace-only text tokens; upgrade the last
    pill html_inline to pill-meta (inserting 'pill-meta' between 'pill' and
    any variant class, for both plain and filled-variant pills)."""
    for tok in reversed(tokens):
        if tok.type == "text" and tok.content.strip() == "":
            continue
        if tok.type == "html_inline":
            m = _PILL_OPEN_RE.match(tok.content)
            if m:
                variant_suffix = m.group(1) or ""
                # Replace the opening class: "pill" → "pill pill-meta", then
                # re-append the variant suffix (e.g. " pill--warn") if any.
                tok.content = _PILL_OPEN_RE.sub(
                    f'<span class="pill pill-meta{variant_suffix}">',
                    tok.content,
                    count=1,
                )
        break
    return tokens
