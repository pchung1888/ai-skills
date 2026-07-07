"""Render the ```demo-brief``` custom block. See spec §3.2.4.

Schema (YAML):
  n: <integer>                   # required — section number (eyebrow)
  title: "<string>"              # required — section title
  tier: "<string>"               # optional — right-floated meta-pill
  tags: [<string>, ...]          # optional — pill row below title
  body: |                        # required — body prose (multi-line literal OK)
    <text>
  meta:                          # optional — key/value table with small-caps keys
    KEY: value
    ...

Renders to:
  <section class="demo-brief">
    <header>
      <span class="demo-n">N.</span>
      <span class="demo-title">TITLE</span>
      [<span class="pill pill-meta">TIER</span>]   <!-- if tier set -->
    </header>
    [<div class="demo-tags">                         <!-- if tags set and non-empty -->
      <span class="pill">TAG1</span>
      ...
    </div>]
    <div class="demo-body">
      <p>paragraph 1</p>
      [<p>paragraph 2</p>]   <!-- split on blank lines -->
    </div>
    [<dl class="demo-meta">                          <!-- if meta set and non-empty -->
      <dt>KEY1</dt><dd>VALUE1</dd>
      ...
    </dl>]
  </section>

On YAML parse failure, emits an HTML comment instead of raising.
"""
from __future__ import annotations
from html import escape

try:
    import yaml  # PyYAML
except ImportError:
    yaml = None


def _body_to_paragraphs(body: str) -> str:
    """Split body on blank lines into <p> tags, html-escape each paragraph."""
    if not body:
        return ""
    # Normalize CRLF / CR line endings before splitting (Windows author with
    # git autocrlf would otherwise produce single paragraph with embedded \r — critic Phase 5 H-1).
    body = body.replace("\r\n", "\n").replace("\r", "\n")
    paras = [p.strip() for p in body.split("\n\n") if p.strip()]
    return "\n".join(f"<p>{escape(p)}</p>" for p in paras)


def render(source_text: str) -> str:
    if yaml is None:
        return "<!-- md-to-html: PyYAML not installed; demo-brief block skipped -->"
    try:
        data = yaml.safe_load(source_text)
    except yaml.YAMLError as e:
        return f"<!-- md-to-html: malformed YAML in 'demo-brief' block: {escape(str(e)[:120])} -->"
    if not isinstance(data, dict):
        return "<!-- md-to-html: 'demo-brief' block expects a mapping -->"

    # Required fields
    n = data.get("n")
    title = data.get("title")
    body = data.get("body")
    if n is None or not title or not body:
        return (
            f"<!-- md-to-html: 'demo-brief' missing required field"
            f" (n={n!r}, title={bool(title)}, body={bool(body)}) -->"
        )
    if not isinstance(n, int) or isinstance(n, bool):  # bool is a subclass of int — exclude
        return f"<!-- md-to-html: 'demo-brief' field 'n' must be int (got {type(n).__name__}: {n!r}) -->"

    # Optional
    tier = data.get("tier")
    tags = data.get("tags") or []
    meta = data.get("meta") or {}

    # --- header ---
    n_span = f'<span class="demo-n">{escape(str(n))}.</span>'
    title_span = f'<span class="demo-title">{escape(str(title))}</span>'
    tier_span = (
        f'<span class="pill pill-meta">{escape(str(tier))}</span>'
        if tier
        else ""
    )
    header = f"<header>{n_span}{title_span}{tier_span}</header>"

    # --- tags row (only when tags list is non-empty) ---
    tags_html = ""
    if tags:
        pills = "".join(
            f'<span class="pill">{escape(str(t))}</span>' for t in tags
        )
        tags_html = f'<div class="demo-tags">{pills}</div>'

    # --- body paragraphs ---
    body_inner = _body_to_paragraphs(str(body))
    body_html = f'<div class="demo-body">{body_inner}</div>'

    # --- meta dl (only when meta dict is non-empty) ---
    meta_html = ""
    if meta:
        rows = "".join(
            f"<dt>{escape(str(k))}</dt><dd>{escape(str(v))}</dd>"
            for k, v in meta.items()
        )
        meta_html = f'<dl class="demo-meta">{rows}</dl>'

    return (
        '<section class="demo-brief">'
        + header
        + tags_html
        + body_html
        + meta_html
        + "</section>"
    )
