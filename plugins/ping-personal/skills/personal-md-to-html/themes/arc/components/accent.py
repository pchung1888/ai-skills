"""H1 accent_word transform. See spec §6.7 / §7.2.1.

Spec divergence (intentional): spec §7.2.1's pseudo-Python uses list-of-list
Token.attrs (markdown-it-py 2.x). In v3.0+/v4.x (this skill's pin) Token.attrs
is Dict[str,str] and must be set via Token.attrSet(name, value).
"""
from __future__ import annotations
import re

_ACCENT_WORD_RE_CACHE: dict[str, re.Pattern] = {}


def _accent_word_pattern(accent_word: str):
    cached = _ACCENT_WORD_RE_CACHE.get(accent_word)
    if cached is None:
        cached = re.compile(
            r"(?<![A-Za-z0-9_])" + re.escape(accent_word) + r"(?![A-Za-z0-9_])",
            re.IGNORECASE,
        )
        _ACCENT_WORD_RE_CACHE[accent_word] = cached
    return cached


def apply_h1_accent_word(inline_token, accent_word: str) -> None:
    if not accent_word or not inline_token.children:
        return
    pattern = _accent_word_pattern(accent_word)
    out = []
    applied = False
    from markdown_it.token import Token
    for child in inline_token.children:
        if applied or child.type != "text":
            out.append(child)
            continue
        match = pattern.search(child.content)
        if not match:
            out.append(child)
            continue
        before = child.content[:match.start()]
        hit = match.group(0)
        after = child.content[match.end():]
        if before:
            t = Token("text", "", 0)
            t.content = before
            out.append(t)
        open_em = Token("em_open", "em", 1)
        open_em.attrSet("class", "accent")
        hit_token = Token("text", "", 0)
        hit_token.content = hit
        close_em = Token("em_close", "em", -1)
        out.extend([open_em, hit_token, close_em])
        if after:
            t = Token("text", "", 0)
            t.content = after
            out.append(t)
        applied = True
    inline_token.children = out
