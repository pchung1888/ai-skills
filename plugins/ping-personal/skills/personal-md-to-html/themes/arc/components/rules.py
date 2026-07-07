"""Render the ```rules``` custom block. See spec §3.2.3.

Schema (YAML):
  columns: [<header-string>, ...]            # required
  items:
    - data: [<col1-value>, <col2-value>, ...]   # positional, matches columns length
      note: <optional pilcrow rationale>
    ...

Items whose data list length != columns length are skipped with an HTML comment
using the 1-based source position (for author debugging).

Renders to:
  <ol class="rules">
    <li class="rule-card">
      <div class="rule-n">1</div>
      <div class="rule-grid" style="--rule-cols: N;">
        <div class="rule-col-header">COLUMN A</div>
        <div class="rule-col-header">COLUMN B</div>
        ...
        <div class="rule-col-cell">value A</div>
        <div class="rule-col-cell">value B</div>
        ...
      </div>
      <p class="rule-note">¶ note text</p>   <!-- if note present and non-empty -->
    </li>
    ...
  </ol>

On YAML parse failure, emits an HTML comment instead of raising.
"""
from __future__ import annotations
from html import escape

try:
    import yaml  # PyYAML
except ImportError:
    yaml = None


def render(source_text: str) -> str:
    if yaml is None:
        return "<!-- md-to-html: PyYAML not installed; rules block skipped -->"
    try:
        data = yaml.safe_load(source_text)
    except yaml.YAMLError as e:
        return f"<!-- md-to-html: malformed YAML in 'rules' block: {escape(str(e)[:120])} -->"
    if not isinstance(data, dict):
        return "<!-- md-to-html: 'rules' block expects a mapping with 'columns' and 'items' -->"
    columns = data.get("columns")
    items = data.get("items")
    if not isinstance(columns, list) or not isinstance(items, list):
        return "<!-- md-to-html: 'rules' block missing 'columns' (list) or 'items' (list) -->"

    n_cols = len(columns)
    cards = []
    rendered_count = 0  # counts only successfully rendered items (for circle-N)

    for src_pos, item in enumerate(items, start=1):
        # src_pos is 1-based source position — used in skip comments for author debugging.
        if not isinstance(item, dict):
            cards.append(
                f"<!-- md-to-html: skipped rule {src_pos} — item is not a mapping -->"
            )
            continue
        item_data = item.get("data")
        if not isinstance(item_data, list):
            cards.append(
                f"<!-- md-to-html: skipped rule {src_pos} — 'data' is missing or not a list -->"
            )
            continue
        if len(item_data) != n_cols:
            cards.append(
                f"<!-- md-to-html: skipped rule {src_pos} — data length mismatch -->"
            )
            continue

        rendered_count += 1
        n = rendered_count  # 1-based display number for circle-N marker

        # Header row (all column headers).
        header_cells = "".join(
            f'<div class="rule-col-header">{escape(str(col))}</div>'
            for col in columns
        )
        # Data row (all cell values, positional).
        data_cells = "".join(
            f'<div class="rule-col-cell">{escape(str(val))}</div>'
            for val in item_data
        )

        grid = (
            f'<div class="rule-grid" style="--rule-cols: {n_cols};">'
            + header_cells
            + data_cells
            + "</div>"
        )

        # Optional pilcrow note — only emit if note is present and non-empty.
        note_raw = item.get("note", "")
        note_html = ""
        if note_raw and str(note_raw).strip():
            note_html = f'<p class="rule-note">¶ {escape(str(note_raw).strip())}</p>'

        cards.append(
            f'<li class="rule-card">'
            f'<div class="rule-n">{n}</div>'
            f"{grid}"
            f"{note_html}"
            f"</li>"
        )

    return '<ol class="rules">' + "".join(cards) + "</ol>"
