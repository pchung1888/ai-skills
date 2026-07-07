"""Render the ```kpi``` custom block. See spec §3.2.2.

Schema (YAML): array of tile objects with keys:
  - label  (string, required)
  - value  (string, required)
  - delta  (string, optional)  — e.g. "+12%" or "-3%"; sign drives color
  - trend  (enum, optional)    — "line" or "bar"; emits inline SVG sparkline
  - data   (string, optional)  — csv values, required if trend set

Delta token mapping:
  starts with "+" → delta--positive  (reuses --arc-good-bg / --arc-good-fg)
  starts with "-" → delta--negative  (reuses --arc-warn-bg / --arc-warn-fg)
  otherwise       → neutral (no extra class)

Sparkline: inline SVG, 80×24, stroke via currentColor (inherits .kpi-tile color).

On YAML parse failure, emits an HTML comment instead of raising.
"""
from __future__ import annotations
from html import escape

try:
    import yaml
except ImportError:
    yaml = None

_SPARK_W = 80
_SPARK_H = 24


def _parse_csv_floats(raw: str) -> list[float]:
    out = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(float(part))
        except ValueError:
            return []
    return out


def _sparkline(kind: str, raw: str) -> str:
    """Emit a minimal inline SVG sparkline.  viewBox is always set (validator check #5)."""
    values = _parse_csv_floats(str(raw))
    if len(values) < 2:
        return "<!-- md-to-html: sparkline needs >=2 numeric values -->"
    vmin, vmax = min(values), max(values)
    span = vmax - vmin or 1.0
    if kind == "line":
        step = _SPARK_W / (len(values) - 1)
        pts = " ".join(
            f"{i * step:.1f},{_SPARK_H - ((v - vmin) / span) * _SPARK_H:.1f}"
            for i, v in enumerate(values)
        )
        return (
            f'<svg class="kpi-spark" viewBox="0 0 {_SPARK_W} {_SPARK_H}" '
            f'width="{_SPARK_W}" height="{_SPARK_H}" aria-hidden="true">'
            f'<polyline fill="none" stroke="var(--arc-accent)" stroke-width="1.2" points="{pts}"/>'
            f"</svg>"
        )
    if kind == "bar":
        n = len(values)
        bar_w = _SPARK_W / n * 0.7
        gap = _SPARK_W / n * 0.3
        bars = []
        for i, v in enumerate(values):
            # Floor at 1.0px so the minimum value still renders a visible sliver
            # instead of an invisible zero-height rect (critic H1).
            h = max(((v - vmin) / span) * _SPARK_H, 1.0)
            x = i * (bar_w + gap)
            y = _SPARK_H - h
            bars.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" '
                f'width="{bar_w:.1f}" height="{h:.1f}" '
                f'fill="var(--arc-accent)"/>'
            )
        return (
            f'<svg class="kpi-spark" viewBox="0 0 {_SPARK_W} {_SPARK_H}" '
            f'width="{_SPARK_W}" height="{_SPARK_H}" aria-hidden="true">'
            + "".join(bars) + "</svg>"
        )
    return f"<!-- md-to-html: unknown trend '{escape(kind)}' — expected line or bar -->"


def _delta_html(delta: str) -> str:
    """Return the delta <span> or empty string if delta is blank."""
    delta_s = str(delta).strip()
    if not delta_s:
        return ""
    if delta_s.startswith("+"):
        cls = "delta delta--positive"
    elif delta_s.startswith(("-", "−")):  # ASCII hyphen-minus OR Unicode U+2212
        cls = "delta delta--negative"
    else:
        cls = "delta"
    return f'<span class="{cls}">{escape(delta_s)}</span>'


def render(source_text: str) -> str:
    if yaml is None:
        return "<!-- md-to-html: PyYAML not installed; kpi block skipped -->"
    try:
        tiles = yaml.safe_load(source_text)
    except yaml.YAMLError as e:
        return f"<!-- md-to-html: malformed YAML in 'kpi' block: {escape(str(e)[:120])} -->"
    if not isinstance(tiles, list):
        return "<!-- md-to-html: 'kpi' block must be a YAML list of tiles -->"
    rendered = []
    for tile in tiles:
        if not isinstance(tile, dict):
            rendered.append("<!-- md-to-html: skipped non-mapping kpi tile -->")
            continue
        label = str(tile.get("label", "")).strip()
        value = str(tile.get("value", "")).strip()
        if not label or not value:
            rendered.append(
                "<!-- md-to-html: skipped kpi tile missing 'label' or 'value' -->"
            )
            continue
        # Delta — sibling of value (not nested inside it).
        delta_raw = str(tile.get("delta", ""))
        delta_html = _delta_html(delta_raw)
        # Sparkline.
        spark = ""
        trend = tile.get("trend")
        data = tile.get("data")
        if trend:
            if not data:
                spark = "<!-- md-to-html: kpi tile has 'trend' but no 'data' -->"
            else:
                spark = _sparkline(str(trend), str(data))
        rendered.append(
            '<article class="kpi-tile">'
            f"<header>{escape(label)}</header>"
            f'<div class="value">{escape(value)}</div>'
            + (delta_html if delta_html else "")
            + spark
            + "</article>"
        )
    return '<div class="kpi-row">' + "".join(rendered) + "</div>"
