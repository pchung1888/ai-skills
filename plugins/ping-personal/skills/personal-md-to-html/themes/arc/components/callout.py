"""Render the ```callout``` custom block. See spec §3.2.1.

Schema (YAML): array of objects with keys:
  - label  (string, required)  — small-caps eyebrow
  - quote  (string, optional)  — italic-serif body line
  - body   (string, optional)  — plain body explanation

Renders to:
  <div class="callout-grid">
    <article class="callout">
      <header>LABEL</header>
      <p class="quote"><em>QUOTE</em></p>
      <p>BODY</p>
    </article>
    ...
  </div>

On YAML parse failure, emits an HTML comment instead of raising.
"""
from __future__ import annotations
from html import escape

try:
    import yaml
except ImportError:
    yaml = None


def render(source_text: str) -> str:
    if yaml is None:
        return "<!-- md-to-html: PyYAML not installed; callout block skipped -->"
    try:
        items = yaml.safe_load(source_text)
    except yaml.YAMLError as e:
        return f"<!-- md-to-html: callout parse error: {escape(str(e)[:120])} -->"
    if not isinstance(items, list):
        return "<!-- md-to-html: 'callout' block must be a YAML list of objects -->"
    cards = []
    for item in items:
        if not isinstance(item, dict):
            cards.append("<!-- md-to-html: skipped non-mapping callout item -->")
            continue
        label = str(item.get("label", "")).strip()
        if not label:
            cards.append("<!-- md-to-html: skipped callout missing 'label' -->")
            continue
        parts = [f"<header>{escape(label)}</header>"]
        if "quote" in item and item["quote"]:
            parts.append(f'<p class="quote"><em>{escape(str(item["quote"]))}</em></p>')
        if "body" in item and item["body"]:
            parts.append(f"<p>{escape(str(item['body']))}</p>")
        cards.append(f'<article class="callout">{"".join(parts)}</article>')
    return '<div class="callout-grid">' + "".join(cards) + "</div>"
