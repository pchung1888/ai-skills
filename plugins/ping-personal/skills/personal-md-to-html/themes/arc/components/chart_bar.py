"""Render the ```chart-bar``` custom block. See spec §6.4."""
from __future__ import annotations
from html import escape
from . import chart_line


def render(source_text: str) -> str:
    data = chart_line._parse(source_text)
    if not data:
        return (
            '<svg class="chart-bar" width="100%" viewBox="0 0 320 16" role="img" '
            'aria-label="empty chart"></svg>'
        )
    row_h = 28
    H = row_h * len(data) + 16
    # Dynamic label column based on longest label
    longest_label = max((len(lbl) for lbl, _ in data), default=0)
    label_col = max(80, longest_label * 7 + 16)
    value_col = 40
    bar_x = label_col + 8
    bar_w_max = 240  # fixed bar room
    W = bar_x + bar_w_max + value_col + 8
    vmax = max(v for _, v in data) or 1.0
    out = []
    for i, (lbl, v) in enumerate(data):
        y = 8 + i * row_h
        bw = (v / vmax) * bar_w_max
        out.append(
            f'<text x="{label_col}" y="{y+row_h/2+4:.0f}" font-size="10" font-family="Georgia,serif"'
            f'text-anchor="end" fill="var(--arc-ink)">{escape(lbl)}</text>'
        )
        out.append(
            f'<rect x="{bar_x}" y="{y+4}" width="{bw:.1f}" height="{row_h-12}" '
            f'fill="var(--arc-accent)"/>'
        )
        out.append(
            f'<text x="{bar_x + bw + 6:.1f}" y="{y+row_h/2+4:.0f}" '
            f'font-size="10" font-family="Georgia,serif"fill="var(--arc-accent)">{v:g}</text>'
        )
    return (
        f'<svg class="chart-bar" width="100%" viewBox="0 0 {W} {H}" role="img" '
        f'aria-label="bar chart">' + "".join(out) + "</svg>"
    )
