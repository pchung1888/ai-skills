"""Paragraph-level core rule: detect leading U+00B6 (pilcrow) and tag
paragraph_open with class="pilcrow". See spec §3.2.8.

Detection: paragraph's first inline child is a text token whose first
non-whitespace character is the literal pilcrow character. The pilcrow
is preserved in output and styled separately via CSS ::first-letter.

Any paragraph NOT starting with ¶ is left completely unchanged.
"""
from __future__ import annotations

PILCROW = "¶"  # ¶


def _first_text_token(children):
    """Descend through leading em_open / strong_open / s_open wrappers
    and return the first actual `text` token, or None.
    Lets `**¶ bold**` and `*¶ italic*` paragraphs trigger pilcrow tagging
    (critic Phase 7 M1)."""
    for child in children:
        if child.type == "text":
            return child
        if child.type in ("em_open", "strong_open", "s_open"):
            continue  # skip the formatting opener, keep looking
        return None  # any other token type (image, link, code_inline) stops descent
    return None


def apply_pilcrow(tokens) -> None:
    """Walk the top-level token list; tag any paragraph_open that precedes
    an inline whose first text content starts with U+00B6 (possibly inside
    italic/bold/strikethrough wrappers)."""
    for i, tok in enumerate(tokens):
        if tok.type != "paragraph_open":
            continue
        # The inline token immediately follows the paragraph_open.
        if i + 1 >= len(tokens):
            continue
        inline = tokens[i + 1]
        if inline.type != "inline" or not inline.children:
            continue
        first = _first_text_token(inline.children)
        if first is None:
            continue
        if first.content.lstrip().startswith(PILCROW):
            existing = tok.attrGet("class") or ""
            new_class = f"{existing} pilcrow".strip() if existing else "pilcrow"
            tok.attrSet("class", new_class)
