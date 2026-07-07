"""Render the ```chart-line``` custom block. See spec §6.3."""
from __future__ import annotations
import csv
import io
from html import escape


def _parse(source_text: str):
    rows = list(csv.reader(io.StringIO(source_text)))
    rows = [r for r in rows if r and any(c.strip() for c in r)]
    if not rows:
        return []
    first = rows[0]
    try:
        float(first[1].strip())
        data = rows
    except (ValueError, IndexError):
        data = rows[1:]
    out = []
    for r in data:
        if len(r) < 2:
            continue
        try:
            out.append((r[0].strip(), float(r[1].strip())))
        except ValueError:
            continue
    return out


def render(source_text: str) -> str:
    data = _parse(source_text)
    if not data:
        return (
            '<svg class="chart-line" viewBox="0 0 320 80" role="img" '
            'aria-label="empty chart"></svg>'
        )
    W, H = 320, 80
    pad_x, pad_y = 24, 8
    plot_w, plot_h = W - 2 * pad_x, H - 2 * pad_y
    vals = [v for _, v in data]
    vmin, vmax = min(vals), max(vals)
    span = (vmax - vmin) or 1.0
    span_padded = span * 1.10
    base = vmin - (span_padded - span) / 2
    pts = []
    dots = []
    for i, (_, v) in enumerate(data):
        x = pad_x + (plot_w * i / max(1, len(data) - 1))
        y = pad_y + plot_h - ((v - base) / span_padded * plot_h)
        pts.append(f"{x:.1f},{y:.1f}")
        dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.5" fill="var(--arc-accent)"/>')
    labels = "".join(
        f'<text x="{pad_x + (plot_w * i / max(1, len(data)-1)):.1f}" y="{H-2}" '
        f'font-size="10" fill="var(--arc-ink)" text-anchor="middle">{escape(lbl)}</text>'
        for i, (lbl, _) in enumerate(data)
    )
    return (
        f'<svg class="chart-line" viewBox="0 0 {W} {H}" role="img" '
        f'aria-label="line chart">'
        f'<polyline fill="none" stroke="var(--arc-accent)" stroke-width="1.5" '
        f'points="{" ".join(pts)}"/>'
        + "".join(dots) + labels + "</svg>"
    )
