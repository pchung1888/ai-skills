"""Code-block server-side regex highlighter. See spec §6.9.

Two regexes applied per line AFTER HTML-escaping:
- `code-path` wraps path-like tokens
- `code-comment` wraps trailing line comments (#, --) including leading whitespace

NOTE: `#` inside a quoted string may be mis-classified as a comment; accepted
for v1 (spec §6.9 last sentence).

Phase 7 extension: fence info string may include `path=<value>` (quoted or unquoted)
to emit a `<p class="eyebrow code-eyebrow">` file-path label above the code block.
"""
from __future__ import annotations
import re
from html import escape

_PATH_RE = re.compile(
    r"""(?<![\w./-])(?:[A-Za-z]:[\\/]|/|\./|\.\./|\.claude/|[\w.-]+/)[^\s"'`<>]*"""
)
_COMMENT_RE = re.compile(r"""(^|\s)(#|--)\s.*$""")
_PATH_ATTR_RE = re.compile(r'path=(?:"([^"]*)"|(\S+))')


def highlight_line(line: str) -> str:
    """Apply path + comment regex wrappers to an already-html-escaped line."""
    cm = _COMMENT_RE.search(line)
    if cm:
        head = line[:cm.start()] + cm.group(1)
        tail = line[cm.start() + len(cm.group(1)):]
        head = _PATH_RE.sub(lambda m: f'<span class="code-path">{m.group(0)}</span>', head)
        return head + f'<span class="code-comment">{tail}</span>'
    return _PATH_RE.sub(lambda m: f'<span class="code-path">{m.group(0)}</span>', line)


def _parse_info_string(info: str) -> tuple[str, str | None]:
    """Return (lang, path_or_None). Supports path=value and path="quoted value"."""
    info = info.strip()
    if not info:
        return "", None
    parts = info.split(maxsplit=1)
    lang = parts[0]
    attrs = parts[1] if len(parts) > 1 else ""
    path_match = _PATH_ATTR_RE.search(attrs)
    if path_match:
        path = path_match.group(1) if path_match.group(1) is not None else path_match.group(2)
    else:
        path = None
    return lang, path


def render_fence(self, tokens, idx, options, env):
    # `self` is the bound renderer when registered via md.add_render_rule.
    token = tokens[idx]
    info = (token.info or "").strip()
    lang, path = _parse_info_string(info)
    escaped = escape(token.content)
    # The trailing newline of token.content produces a trailing empty line after
    # split; keep but don't highlight it.
    highlighted = "\n".join(highlight_line(ln) for ln in escaped.split("\n"))
    cls = f' class="language-{escape(lang)}"' if lang else ""
    code_html = f"<pre><code{cls}>{highlighted}</code></pre>\n"
    if path:
        eyebrow_html = f'<p class="eyebrow code-eyebrow">{escape(path)}</p>\n'
        return eyebrow_html + code_html
    return code_html


def render_accent(tokens, idx, options, env):
    """Adds accent class to em_open from rendering side via attrSet semantics.

    Not currently used; placeholder for future hook.
    """
    return ""
