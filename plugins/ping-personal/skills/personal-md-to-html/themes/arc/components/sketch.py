"""Render the ```sketch``` custom block. See spec §6.2."""
from __future__ import annotations
import re
import shlex
from html import escape

KV_RE = re.compile(r"(\w+)=(\d+)")


def _estimate_text_width(label: str) -> int:
    # Georgia 16px: caps-heavy strings (e.g. CamelCase identifiers) run ~8.5px/char
    # on average; +28 for left+right inner padding. Conservative on purpose so
    # labels with mostly capital letters (M, W, B, G, D) still clear the rect.
    return int(len(label) * 8.5) + 28


def _parse_line(line: str):
    line = line.strip()
    if not line:
        return None
    try:
        parts = shlex.split(line)
    except ValueError:
        return ("__malformed__", line)
    if not parts:
        return None
    kind = parts[0]
    label = ""
    if len(parts) >= 2 and not KV_RE.fullmatch(parts[1]):
        label = parts[1]
    kvs = {k: int(v) for k, v in KV_RE.findall(line)}
    return (kind, label, kvs)


def render(source_text: str) -> str:
    items = []
    skipped = []
    for raw in source_text.strip("\n").splitlines():
        parsed = _parse_line(raw)
        if parsed is None:
            continue
        if isinstance(parsed, tuple) and parsed[0] == "__malformed__":
            skipped.append(parsed[1])
            continue
        kind, label, kvs = parsed
        if kind == "box" and label:
            needed = _estimate_text_width(label)
            kvs["w"] = max(kvs.get("w", 320), needed)
        items.append((kind, label, kvs))

    pad = 8
    inner_w = max((kv.get("w", 0) for _, _, kv in items), default=320)
    width = inner_w + 2 * pad
    y = pad
    nodes = []
    for kind, label, kv in items:
        if kind == "box":
            # All boxes share the widest box's width — keeps the right edge flush
            # in stacked technical-flow sketches; declared `w=` becomes a minimum.
            w, h = inner_w, kv.get("h", 40)
            nodes.append(
                f'<rect x="{pad}" y="{y}" width="{w}" height="{h}" rx="6" '
                f'fill="var(--arc-paper)" stroke="var(--arc-rule)"/>'
            )
            if label:
                nodes.append(
                    f'<text x="{pad+12}" y="{y+h/2+5:.0f}" '
                    f'font-family="Georgia,serif" font-size="14" fill="var(--arc-ink)">{escape(label)}</text>'
                )
            y += h + 8
        elif kind == "button":
            w, h = kv.get("w", 120), kv.get("h", 36)
            nodes.append(
                f'<rect x="{pad}" y="{y}" width="{w}" height="{h}" rx="18" '
                f'fill="var(--arc-paper)" stroke="var(--arc-rule)"/>'
            )
            if label:
                nodes.append(
                    f'<text x="{pad+12}" y="{y+h/2+5:.0f}" '
                    f'font-family="Georgia,serif" font-size="14" fill="var(--arc-ink)">{escape(label)}</text>'
                )
            y += h + 8
        elif kind == "divider":
            nodes.append(
                f'<line x1="{pad}" y1="{y}" x2="{width-pad}" y2="{y}" '
                f'stroke="var(--arc-rule)"/>'
            )
            y += 12
        elif kind == "spacer":
            y += kv.get("h", 12)
        else:
            nodes.append(
                f"<!-- md-to-html: skipped malformed row '{escape(kind)}' in sketch -->"
            )
    for s in skipped:
        nodes.append(
            f"<!-- md-to-html: skipped malformed row '{escape(s[:60])}' in sketch -->"
        )
    height = y + pad
    return (
        f'<svg class="sketch" width="100%" viewBox="0 0 {width} {height}" '
        f'role="img" aria-label="wireframe sketch">'
        + "".join(nodes)
        + "</svg>"
    )
