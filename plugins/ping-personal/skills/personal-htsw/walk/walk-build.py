#!/usr/bin/env python3
"""Build a personal-htsw walk-through page from a walk spec (JSON).

Usage:
  python walk-build.py <spec.json> --out <page.html>

The spec holds only content (title, steps, questions, glossary). This script owns the
structure the build brief requires: opening, clickable flow chart as the table of
contents, one section per step, Back/Previous/Next links, mini-flow menu, answer
sheet, Reference and glossary. walk.css and walk.js next to this file are inlined,
so the page is one self-contained file. Spec format: references/walk-page.md.
"""
import argparse
import html
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = Path(".")  # folder of the spec; svg_file paths resolve against it
ANIME = "https://cdnjs.cloudflare.com/ajax/libs/animejs/4.5.0/anime.umd.min.js"
FONTS = ("https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&"
         "family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Serif:ital,wght@0,500;0,600;0,700;1,500&display=swap")
TAGS = ("suggestion", "recommended", "for expert discussion")
TONES = {"ok": "var(--ok)", "warn": "var(--warn)", "change": "var(--b)", "b": "var(--b)", "a": "var(--a)", "info": "var(--info)"}


def esc(s):
    return html.escape(str(s), quote=True)


class Inline:
    """Turns spec text into safe HTML: [t](#id), **bold**, `code`, proposal tags, glossary terms."""

    TOKEN = re.compile(r"\[([^\]]+)\]\((#[\w-]+)\)|\*\*(.+?)\*\*|`([^`]+)`|\((suggestion|recommended|for expert discussion)\)")

    def __init__(self, glossary):
        self.defs = {}
        for term, meaning in glossary:
            self.defs[term.lower()] = (term, meaning)
        terms = sorted(self.defs, key=len, reverse=True)
        self.term_re = re.compile(r"(?<![\w.+-])(" + "|".join(re.escape(t) for t in terms) + r")(?![\w+])", re.I) if terms else None
        self.used = set()  # terms already wrapped in the current section

    def section(self):
        self.used = set()

    def terms(self, text):
        if not self.term_re:
            return esc(text)
        out, last = [], 0
        for m in self.term_re.finditer(text):
            key = m.group(1).lower()
            if key in self.used:
                continue
            self.used.add(key)
            out.append(esc(text[last:m.start()]))
            out.append('<span class="term" role="button" tabindex="0" data-def="%s">%s</span>' % (esc(self.defs[key][1]), esc(m.group(1))))
            last = m.end()
        out.append(esc(text[last:]))
        return "".join(out)

    def __call__(self, text, terms=True):
        text = str(text)
        out, last = [], 0
        plain = self.terms if terms else esc
        for m in self.TOKEN.finditer(text):
            out.append(plain(text[last:m.start()]))
            if m.group(1):
                out.append('<a href="%s">%s</a>' % (esc(m.group(2)), esc(m.group(1))))
            elif m.group(3):
                out.append("<b>%s</b>" % plain(m.group(3)))
            elif m.group(4):
                out.append("<code>%s</code>" % esc(m.group(4)))
            else:
                out.append('<span class="tag">(%s)</span>' % esc(m.group(5)))
            last = m.end()
        out.append(plain(text[last:]))
        return "".join(out)


def strip_marks(text):
    text = re.sub(r"\[([^\]]+)\]\(#[\w-]+\)", r"\1", str(text))
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\s*\((?:%s)\)" % "|".join(TAGS), "", text)
    return text.strip()


# Refused in svg and html blocks. Checked on the text after HTML entities are decoded, so java&#115;cript: is caught.
# (?!\s*["']?#) lets a same-page "#id" reference through and refuses anything else.
UNSAFE = re.compile("|".join([
    r"<\s*script", r"[\s/\"']on\w+\s*=", r"(?:java|vb)script\s*:", r"data:\s*text/html",
    r"<\s*foreignObject", r"<\s*iframe", r"<\s*object", r"<\s*embed",
    r"<\s*(?:use|image|a)\b[^>]*?\b(?:xlink:)?href\s*=\s*[\"']?(?!\s*[\"']?#)",
    r"<\s*(?:animate|set)\b[^>]*?\battributeName\s*=\s*[\"']?\s*(?:xlink:)?href",
    r"@import", r"url\(\s*[\"']?(?!\s*[\"']?#)",
]), re.I)
ID_RE = re.compile(r"[a-z][a-z0-9-]*")
RESERVED = re.compile(r"intro|flow|answers|ref-words|top|main|q\d+|box-.*|pbox-.*|wb-.*")
CATS = {"a": "a", "b": "b", "c": "c", "d": "ok"}  # category id -> color token (--X, --X-soft)


def unsafe(text, what):
    text = str(text)
    for _ in range(3):  # decode entities until stable, so &#115; tricks cannot hide a match
        nxt = html.unescape(text)
        if nxt == text:
            break
        text = nxt
    m = UNSAFE.search(text)
    if m:
        raise SystemExit("walk-build: %s contains %r (script, event handler, external link or url, foreignObject, iframe, object and embed are refused)" % (what, m.group(0).strip()[:60]))


def check_svg(svg, what):
    """Same checks for svg_file and inline svg: nothing unsafe, exactly one <svg> element."""
    svg = svg.strip()
    unsafe(svg, what)
    low = svg.lower()
    if not (low.startswith("<svg") and low.endswith("</svg>")) or low.count("<svg") != 1:
        raise SystemExit("walk-build: %s must hold exactly one <svg>...</svg> element and nothing else" % what)
    return svg


def validate(spec):
    seen = {}
    fields = [("steps[%d].id" % i, s.get("id")) for i, s in enumerate(spec["steps"])]
    fields += [("reference[%d].id" % i, r.get("id")) for i, r in enumerate(spec.get("reference", []))]
    fields += [("answers.questions[%d].id" % i, q["id"]) for i, q in enumerate(spec["answers"].get("questions", [])) if "id" in q]
    for name, v in fields:
        if not isinstance(v, str) or not ID_RE.fullmatch(v):
            raise SystemExit("walk-build: %s = %r must match ^[a-z][a-z0-9-]*$" % (name, v))
        if RESERVED.fullmatch(v):
            raise SystemExit("walk-build: %s = %r is a reserved id" % (name, v))
        if v in seen:
            raise SystemExit("walk-build: %s = %r duplicates %s" % (name, v, seen[v]))
        seen[v] = name
    for i, s in enumerate(spec["steps"]):
        a = s.get("alongside")
        if a is not None:
            if not isinstance(a, str) or not 1 <= len(a.split()) <= 4 or len(a) > 24:
                raise SystemExit("walk-build: steps[%d].alongside = %r must be a string of 1 to 4 words and at most 24 characters, for example \"while others go on\"" % (i, a))
            if s.get("outcomes"):
                raise SystemExit("walk-build: steps[%d].alongside cannot be set on the decision step" % i)
            unsafe(a, "steps[%d].alongside" % i)
            flow = spec["steps"][:-1] if spec["steps"][-1].get("outcomes") else spec["steps"]
            half = (len(flow) + 1) // 2
            if i in (0, half - 1, half, len(flow) - 1):
                raise SystemExit("walk-build: steps[%d].alongside needs a step before and after it in the same chart column (not first or last in a column, not right before the decision)" % i)
            if i > 0 and spec["steps"][i - 1].get("alongside"):
                raise SystemExit("walk-build: steps[%d].alongside cannot follow another alongside step" % i)


def block_html(b, il):
    if not isinstance(b, dict) or len(b) != 1:
        raise SystemExit("walk-build: each block must be an object with one key, got %r" % (b,))
    kind, v = next(iter(b.items()))
    if kind == "bullets":
        return '<ul class="pts">' + "".join("<li>%s</li>" % il(x) for x in v) + "</ul>"
    if kind == "numbered":
        return '<ol class="steps-list">' + "".join("<li>%s</li>" % il(x) for x in v) + "</ol>"
    if kind == "h3":
        return "<h3>%s</h3>" % il(v, terms=False)
    if kind == "table":
        head = "".join("<th>%s</th>" % il(h, terms=False) for h in v["head"])
        rows = "".join("<tr>" + "".join("<td>%s</td>" % il(c) for c in r) + "</tr>" for r in v["rows"])
        return '<div class="tbl"><table><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>' % (head, rows)
    if kind == "chips":
        return '<ol class="chips">' + "".join("<li>%s</li>" % il(x) for x in v) + "</ol>"
    if kind == "note":
        tone = v.get("tone", "info")
        title = '<b>%s</b>' % esc(v["title"]) if v.get("title") else ""
        return '<div class="note %s">%s%s</div>' % (esc(tone), title, il(v["text"]))
    if kind == "analogy":
        return analogy_html(v, il)
    if kind == "svg_file":
        path = (BASE / v["file"]).resolve()
        if BASE.resolve() != path and BASE.resolve() not in path.parents:
            raise SystemExit("walk-build: svg_file %r is outside the spec folder" % v["file"])
        v = dict(v, svg=path.read_text(encoding="ascii"))
        what = "svg_file %s" % v["file"]
        kind = "svg"
    if kind == "svg":
        v = dict(v, svg=check_svg(v["svg"], locals().get("what", "inline svg block")))
        cap = "<figcaption>%s</figcaption>" % il(v["caption"]) if v.get("caption") else ""
        return '<figure><div class="fig">%s</div>%s</figure>' % (v["svg"], cap)
    if kind == "done":
        return '<ul class="done">' + "".join("<li><span>%s</span></li>" % il(x) for x in v) + "</ul>"
    if kind == "ba":
        def side(cls, title, items):
            return '<div class="side %s"><h4>%s</h4><ul>%s</ul></div>' % (cls, esc(title), "".join("<li>%s</li>" % il(x) for x in items))
        if v.get("kind") == "options":  # two alternatives: an "or" divider, no arrow, neither side is "after"
            return '<div class="ba opts">%s<div class="or" aria-hidden="true">or</div>%s</div>' % (
                side("opt", v.get("before_title", "Option 1"), v["before"]), side("opt", v.get("after_title", "Option 2"), v["after"]))
        return '<div class="ba">%s<div class="arrow" aria-hidden="true">-&gt;</div>%s</div>' % (
            side("before", v.get("before_title", "Today"), v["before"]), side("after", v.get("after_title", "After"), v["after"]))
    if kind == "stats":
        cells = []
        for s in v:
            val = str(s["value"])
            cells.append('<div class="stat"><div class="v">%s</div><div class="l">%s</div></div>' % (esc(val), il(s["label"])))
        return '<div class="stats">' + "".join(cells) + "</div>"
    if kind == "html":
        unsafe(v, "html block")
        return v
    raise SystemExit("walk-build: unknown block type %r" % kind)


def icon(*paths):
    """A 24x24 line icon that takes the text color. paths are the inner SVG elements."""
    return ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
            'stroke-linejoin="round" focusable="false">%s</svg>' % "".join(paths))


ICON_BULB = icon('<path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/>',
                 '<path d="M9 18h6"/>', '<path d="M10 22h4"/>')
ICON_MARK = icon('<path d="m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16z"/>')
ICON_ASK = icon('<circle cx="12" cy="12" r="10"/>', '<path d="M9.1 9a3 3 0 0 1 5.8 1c0 2-3 3-3 3"/>', '<path d="M12 17h.01"/>')
ICON_DONE = icon('<circle cx="12" cy="12" r="10"/>', '<path d="m8 12 3 3 5-6"/>')


def analogy_html(text, il):
    return ('<div class="analogy"><div class="ic" aria-hidden="true">' + ICON_BULB + '</div><div><div class="k">Think of it like this</div>'
            '<p class="say">%s</p></div></div>' % il(text))


def wrap_lines(text, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > width:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return lines


def ALE(s):
    """Extra class for the arrow that leaves an alongside box."""
    return " al-edge" if s.get("alongside") else ""


def chart_svg(spec):
    """Desktop chart: a 2-column snake (left column down, connector, right column down),
    then the decision diamond and its outcome boxes centered below both columns."""
    steps = spec["steps"]
    W, bw, gut, mar, gap = 680, 300, 40, 20, 20
    decision = steps[-1] if steps[-1].get("outcomes") else None
    flow = steps[:-1] if decision else steps
    half = (len(flow) + 1) // 2
    cols = [flow[:half], flow[half:]]
    colx = [mar, mar + bw + gut]
    cx = W // 2
    y0 = 34 if cols[1] else 12
    parts, edges, labels, ends = [], [], [], []
    for c, col in enumerate(cols):
        x0, ccx, y = colx[c], colx[c] + bw // 2, y0
        boxes = []
        for k, s in enumerate(col):
            n = c * half + k + 1
            cat = s.get("cat", "a")
            tl = wrap_lines(s["name"], 24)
            sl = wrap_lines(s["sub"], 34) if s.get("sub") else []
            sl += [s["alongside"]] if s.get("alongside") else []
            h = 33 + 19 * len(tl) + 15 * (len(sl) - 1) if sl else max(44, 24 + 19 * len(tl))
            parts.append(
                '<a class="st cat-%s%s" id="box-%s" href="#%s"><title>Open step %d: %s</title>'
                '<rect class="bx" x="%d" y="%d" width="%d" height="%d" rx="10"/>'
                '<circle class="num" cx="%d" cy="%d" r="15"/><text class="numt" x="%d" y="%d" text-anchor="middle">%d</text>' % (
                    esc(cat), " al" if s.get("alongside") else "", esc(s["id"]), esc(s["id"]), n, esc(s["name"]), x0, y, bw, h,
                    x0 + 28, y + h // 2, x0 + 28, y + h // 2 + 4, n))
            for j, ln in enumerate(tl):
                parts.append('<text class="t" x="%d" y="%d">%s</text>' % (x0 + 54, y + 24 + 19 * j, esc(ln)))
            for j, ln in enumerate(sl):
                parts.append('<text class="s%s" x="%d" y="%d">%s</text>' % (" altag" if s.get("alongside") and j == len(sl) - 1 else "", x0 + 54, y + 22 + 19 * len(tl) + 15 * j, esc(ln)))
            parts.append('<path class="tick" d="M%d,%d l5,5 l9,-10" stroke="var(--ok)" stroke-width="2.5" fill="none"/></a>' % (x0 + bw - 30, y + h // 2))
            boxes.append((y, h))
            y += h
            if k < len(col) - 1 and s.get("alongside") and 0 < k:
                # Alongside step with a neighbour on both sides: a short dashed stub ending in an open circle
                # ("feeds in later"); the solid bypass edge below goes from the step before to the step after.
                edges.append('<line class="flow-edge al-edge" data-from="%d" x1="%d" y1="%d" x2="%d" y2="%d"/>' % (n - 1, ccx, y, ccx, y + 11))
                edges.append('<circle class="al-dot" cx="%d" cy="%d" r="5"/>' % (ccx, y + 16))
                if s.get("edge_note"):
                    labels.append('<text class="flow-lbl" x="%d" y="%d">%s</text>' % (ccx + 10, y + 12, esc(s["edge_note"])))
                bx = x0 - 16
                (ya, ha), (yb2, hb) = boxes[k - 1], (y + gap + 10, 0)
                edges.append('<path class="flow-edge al-bypass" data-from="%d" data-to="%d" d="M%d,%d H%d V%d H%d" marker-end="url(#wb-ah)"/>' % (n - 2, n + 1, x0, ya + ha // 2, bx, yb2 + 22, x0 - 2))
                y += gap + 10
            elif k < len(col) - 1:
                edges.append('<line class="flow-edge%s" data-from="%d" x1="%d" y1="%d" x2="%d" y2="%d" marker-end="url(#wb-ah)"/>' % (ALE(s), n - 1, ccx, y, ccx, y + gap - 2))
                if s.get("edge_note"):
                    labels.append('<text class="flow-lbl" x="%d" y="%d">%s</text>' % (ccx + 10, y + gap // 2 + 4, esc(s["edge_note"])))
                y += gap
        ends.append(y if col else y0)
    lcx, rcx = colx[0] + bw // 2, colx[1] + bw // 2
    bot = max(ends)
    if cols[1]:
        # Connector: bottom of the left column, along the gutter, into the top of the right column.
        yb, gx, ytop = ends[0] + 12, W // 2, y0 - 24
        edges.append('<path class="flow-edge%s" data-from="%d" d="M%d,%d V%d H%d V%d H%d V%d" marker-end="url(#wb-ah)"/>' % (ALE(cols[0][-1]), half - 1, lcx, ends[0], yb, gx, ytop, rcx, y0 - 2))
        if cols[0][-1].get("edge_note"):
            labels.append('<text class="flow-lbl" x="%d" y="%d">%s</text>' % (lcx + 12, yb + 15, esc(cols[0][-1]["edge_note"])))
    y = bot
    if decision:
        last = cols[1][-1] if cols[1] else cols[0][-1]
        lx = rcx if cols[1] else lcx
        hw, hh = 140, 44
        top = bot + (38 if cols[1] else gap)
        if cols[1]:
            # Feed enters the diamond's right tip so it never shares the x=W/2 line with the snake connector.
            edges.append('<path class="flow-edge%s" data-from="%d" data-to="d" d="M%d,%d V%d H%d" marker-end="url(#wb-ah)"/>' % (ALE(last), len(flow) - 1, lx, ends[1], top + hh, cx + hw + 2))
        else:
            edges.append('<line class="flow-edge%s" data-from="%d" data-to="d" x1="%d" y1="%d" x2="%d" y2="%d" marker-end="url(#wb-ah)"/>' % (ALE(last), len(flow) - 1, lx, ends[0], cx, top - 2))
        if last.get("edge_note"):
            labels.append('<text class="flow-lbl" x="%d" y="%d">%s</text>' % (lx + 10, ends[1 if cols[1] else 0] + 16, esc(last["edge_note"])))
        n = len(steps)
        mid = top + hh
        parts.append(
            '<a class="st cat-%s" id="box-%s" href="#%s"><title>Open step %d: %s</title>'
            '<polygon class="bx" points="%d,%d %d,%d %d,%d %d,%d"/>' % (
                esc(decision.get("cat", "a")), esc(decision["id"]), esc(decision["id"]), n, esc(decision["name"]),
                cx, top, cx + hw, mid, cx, top + 2 * hh, cx - hw, mid))
        lines = wrap_lines("%d. %s" % (n, decision["name"]), 20)
        ly = mid - (len(lines) - 1) * 9 + 5
        for k, ln in enumerate(lines):
            parts.append('<text class="t" x="%d" y="%d" text-anchor="middle">%s</text>' % (cx, ly + k * 18, esc(ln)))
        parts.append('<path class="tick" d="M%d,%d l5,5 l9,-10" stroke="var(--ok)" stroke-width="2.5" fill="none"/>' % (cx - 7, top + 2 * hh - 26))
        parts.append("</a>")
        y = top + 2 * hh
        outs = decision["outcomes"]
        m = len(outs)
        ow = min(190, (W - 2 * mar - (m - 1) * 14) // m)
        ox0 = (W - (m * ow + (m - 1) * 14)) // 2
        ols = [wrap_lines(o["label"], 20) for o in outs]
        onl = [wrap_lines(o.get("note", ""), 26) for o in outs]
        ll, nl = max(len(x) for x in ols), max(len(x) for x in onl)
        # Label baselines are 19px apart, the first note baseline 18px below the last label, note lines 16px apart.
        oh = (26 + 19 * (ll - 1) + (18 + 16 * (nl - 1) if nl else 0)) + 14
        bus = y + 16
        otop = bus + 18
        for k, o in enumerate(outs):
            ocx = ox0 + k * (ow + 14) + ow // 2
            edges.append('<path class="flow-edge" data-from="d" d="M%d,%d V%d H%d V%d" marker-end="url(#wb-ah)"/>' % (cx, y, bus, ocx, otop - 2))
            col = TONES.get(o.get("tone", "a"), "var(--a)")
            parts.append('<g class="oc"><rect x="%d" y="%d" width="%d" height="%d" rx="10" style="stroke:%s"/>' % (ocx - ow // 2, otop, ow, oh, col))
            for j, ln in enumerate(ols[k]):
                parts.append('<text x="%d" y="%d" text-anchor="middle" style="fill:%s">%s</text>' % (ocx, otop + 26 + 19 * j, col, esc(ln)))
            for j, ln in enumerate(onl[k]):
                parts.append('<text class="flow-lbl" x="%d" y="%d" text-anchor="middle">%s</text>' % (ocx, otop + 26 + 19 * (ll - 1) + 18 + 16 * j, esc(ln)))
            parts.append("</g>")
        y = otop + oh
    H = y + 12
    return ('<svg viewBox="0 0 %d %d" role="img" aria-label="%s">'
            '<defs><marker id="wb-ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">'
            '<path d="M0,0 L10,5 L0,10 z" fill="var(--muted)"/></marker></defs>'
            '<g font-family="IBM Plex Sans, sans-serif">%s%s%s</g></svg>') % (
        W, H, esc(spec.get("chart_label", "The %d steps. Click a step to open it." % len(steps))), "".join(edges), "".join(parts), "".join(labels))


def phone_chart(spec):
    """Narrow chart for phones: full-width boxes in an ordered list, down arrows, stacked outcomes."""
    steps = spec["steps"]
    decision = steps[-1] if steps[-1].get("outcomes") else None
    out = []
    for i, s in enumerate(steps):
        sub = "<small>%s</small>" % esc(s["sub"]) if s.get("sub") else ""
        sub += '<small class="altag">%s</small>' % esc(s["alongside"]) if s.get("alongside") else ""
        if i > 1 and steps[i - 1].get("alongside"):
            sub += '<small class="afternote">starts after step %d</small>' % (i - 1)
        dec = s is decision
        out.append('<li><a class="st pst cat-%s%s%s" id="pbox-%s" href="#%s"><span class="pn">%d</span><span class="pt">%s<b>%s</b>%s</span>'
                   '<span class="ptick" aria-hidden="true"></span></a></li>' % (
                       esc(s.get("cat", "a")), " pdec" if dec else "", " al" if s.get("alongside") else "", esc(s["id"]), esc(s["id"]), i + 1,
                       "<em>Decision</em>" if dec else "", esc(s["name"]), sub))
        if i < len(steps) - 1 or dec:
            note = "<span>%s</span>" % esc(s["edge_note"]) if s.get("edge_note") else ""
            out.append('<li class="parr%s" aria-hidden="true"><i></i>%s</li>' % (" al" if s.get("alongside") else "", note))
    if decision:
        items = []
        for o in decision["outcomes"]:
            col = TONES.get(o.get("tone", "a"), "var(--a)")
            note = "<span>%s</span>" % esc(o["note"]) if o.get("note") else ""
            items.append('<li class="po" style="--tone:%s"><b>%s</b>%s</li>' % (col, esc(o["label"]), note))
        out.append('<li><ul class="pouts">%s</ul></li>' % "".join(items))
    return '<ol class="pchart" aria-label="The %d steps. Tap a step to open it.">%s</ol>' % (len(steps), "".join(out))


def hero_map(spec):
    """Mini flow chart for the hero: numbered dots in the same snake order as the chart, the decision
    diamond, outcome dots and one dashed path from step 1 to the diamond. Decorative (aria-hidden)."""
    steps = spec["steps"]
    decision = steps[-1] if steps[-1].get("outcomes") else None
    flow = steps[:-1] if decision else steps
    half = (len(flow) + 1) // 2
    cols = [flow[:half], flow[half:]]
    W, y0, pitch, r = 300, 54, 44, 13
    xs = [82, 218] if cols[1] else [W // 2]
    dots, edges, ends = [], [], []
    for c, col in enumerate(cols[:len(xs)]):
        for k, s in enumerate(col):
            n = c * half + k + 1
            y = y0 + k * pitch
            if k:
                edges.append('<line class="hm-edge" x1="%d" y1="%d" x2="%d" y2="%d"/>' % (xs[c], y - pitch + r, xs[c], y - r))
            dots.append('<g class="hm-n cat-%s"><circle cx="%d" cy="%d" r="%d"/><text x="%d" y="%d" text-anchor="middle">%d</text></g>' % (
                esc(s.get("cat", "a")), xs[c], y, r, xs[c], y + 4, n))
        ends.append(y0 + (len(col) - 1) * pitch)
    bot = max(ends)
    mid = W // 2
    path = ["M%d,%d V%d" % (xs[0], y0, ends[0])]
    if cols[1]:
        yb, ytop = ends[0] + 24, y0 - 24
        path.append("V%d H%d V%d H%d V%d" % (yb, mid, ytop, xs[1], ends[1]))
        edges.append('<path class="hm-edge" d="M%d,%d V%d H%d V%d H%d V%d"/>' % (xs[0], ends[0] + r, yb, mid, ytop, xs[1], y0 - r))
    top = bot + 56
    tail = ""
    if decision:
        hw, hh = 38, 26
        if cols[1]:
            path.append("V%d H%d" % (top, mid + hw))
            edges.append('<path class="hm-edge" d="M%d,%d V%d H%d"/>' % (xs[-1], ends[-1] + r, top, mid + hw + 2))
        else:
            path.append("V%d" % (top - hh))
            edges.append('<line class="hm-edge" x1="%d" y1="%d" x2="%d" y2="%d"/>' % (mid, ends[0] + r, mid, top - hh))
        tail = ('<g class="hm-dec"><polygon points="%d,%d %d,%d %d,%d %d,%d"/><text x="%d" y="%d" text-anchor="middle">%d</text></g>' % (
            mid, top - hh, mid + hw, top, mid, top + hh, mid - hw, top, mid, top + 4, len(steps)))
        outs = decision["outcomes"]
        oy = top + hh + 36
        gap = min(90, (W - 20) // max(len(outs), 1))
        nlines = 1
        for k, o in enumerate(outs):
            ox = mid + (k - (len(outs) - 1) / 2.0) * gap
            col = TONES.get(o.get("tone", "a"), "var(--a)")
            edges.append('<path class="hm-edge" d="M%d,%d V%d H%d V%d"/>' % (mid, top + hh, top + hh + 14, ox, oy - 9))
            lines = wrap_lines(o["label"], max(8, gap // 7))[:2]
            nlines = max(nlines, len(lines))
            tspans = "".join('<tspan x="%d" dy="%d">%s</tspan>' % (ox, 0 if j == 0 else 15, esc(ln)) for j, ln in enumerate(lines))
            tail += ('<g class="hm-out" style="--tone:%s"><circle cx="%d" cy="%d" r="9"/>'
                     '<text class="hm-lbl" x="%d" y="%d" text-anchor="middle">%s</text></g>') % (col, ox, oy, ox, oy + 25, tspans)
        H = oy + 32 + 15 * (nlines - 1)
    else:
        H = bot + 30
    d = " ".join(path)
    # The caption counts every step, so it agrees with the page ("12 steps, ends in 1 decision").
    cap = '<text class="hm-cap" x="%d" y="16" text-anchor="middle">%d steps%s</text>' % (mid, len(steps), ", ends in 1 decision" if decision else "")
    return ('<aside class="hero-map" aria-hidden="true"><svg viewBox="0 0 %d %d" focusable="false">'
            '<defs><mask id="wb-hm-mask" maskUnits="userSpaceOnUse" x="0" y="0" width="%d" height="%d">'
            '<path class="hm-reveal" d="%s" fill="none" stroke="#fff" stroke-width="8"/></mask></defs>'
            '%s%s<path class="hm-path" d="%s" mask="url(#wb-hm-mask)"/>%s%s</svg></aside>') % (
        W, H, W, H, d, cap, "".join(edges), d, "".join(dots), tail)


def hero_visual(spec):
    """The hero picture of the idea: the spec's hero_visual svg_file in the glass card with a caption.
    Without hero_visual the mini flow chart is used. The svg keeps its own role and aria-label."""
    hv = spec.get("hero_visual")
    if not hv:
        return hero_map(spec)
    name = hv.get("svg_file") if isinstance(hv, dict) else None
    if not isinstance(name, str) or not name:
        raise SystemExit("walk-build: hero_visual needs an svg_file key naming an svg in the spec folder")
    path = (BASE / name).resolve()
    if BASE.resolve() != path and BASE.resolve() not in path.parents:
        raise SystemExit("walk-build: hero_visual svg_file %r is outside the spec folder" % name)
    if not path.is_file():
        raise SystemExit("walk-build: hero_visual svg_file %s does not exist in the spec folder" % name)
    try:
        raw = path.read_text(encoding="ascii")
    except UnicodeDecodeError:
        raise SystemExit("walk-build: hero_visual svg_file %s must be ASCII only" % name)
    svg = check_svg(raw, "hero_visual svg_file %s" % name)
    root = re.match(r"<svg\b[^>]*>", svg, re.I).group(0)
    lab = re.search(r"\baria-label\s*=\s*(?:\"([^\"]*)\"|'([^']*)')", root, re.I)
    if not re.search(r"\brole\s*=\s*[\"']img[\"']", root, re.I) or not lab or len((lab.group(1) or lab.group(2) or "").strip()) < 8:
        raise SystemExit("walk-build: hero_visual svg_file %s needs role=\"img\" and an aria-label of at least 8 characters on the <svg>" % name)
    if not re.search(r"\bviewBox\s*=", root, re.I):
        raise SystemExit("walk-build: hero_visual svg_file %s needs a viewBox on the <svg> so it scales" % name)
    cap = '<p class="hv-cap">%s</p>' % esc(hv["caption"]) if hv.get("caption") else ""
    links = spec.get("hero_links")
    hint = ""
    if links:
        svg = hero_links(svg, links, spec["steps"])
        svg = re.sub(r'role\s*=\s*"img"', 'role="group"', svg, count=1, flags=re.I)
        hint = '<p class="hv-hint">Click or tap a part of the picture to jump to its step.</p>'
    return '<aside class="hero-map hero-vis">%s<small class="hv-eye">The idea in one picture</small>%s%s</aside>' % (svg, cap, hint)


def hero_links(svg, links, steps):
    """Make parts of the hero svg jump to a step. links maps an element id in the svg to a step id (max 5).
    Adds class hv-link, tabindex, role, aria-label and data-go to the element; walk.js does the jump."""
    if not isinstance(links, dict) or not links or len(links) > 5:
        raise SystemExit("walk-build: hero_links must be an object of 1 to 5 entries mapping an svg element id to a step id")
    for eid, sid in links.items():
        idx = [i for i, s in enumerate(steps) if s["id"] == sid]
        if not idx:
            raise SystemExit("walk-build: hero_links %s points at step id %r, which is not a step" % (eid, sid))
        pat = re.compile(r"<[A-Za-z][^<>]*?\sid\s*=\s*\"%s\"[^<>]*>" % re.escape(eid))
        if len(pat.findall(svg)) != 1:
            raise SystemExit("walk-build: hero_links element id %r must appear exactly once in the hero svg" % eid)
        tag0 = pat.search(svg).group(0)
        if tag0.lower().startswith("<svg"):
            raise SystemExit("walk-build: hero_links element id %r cannot be the root svg" % eid)
        for attr in ("tabindex", "role", "aria-label", "data-go"):
            if re.search(r"\s%s\s*=" % attr, tag0, re.I):
                raise SystemExit("walk-build: hero_links element id %r already has %s" % (eid, attr))
        i = idx[0]
        extra = ' tabindex="0" role="link" aria-label="%s" data-go="#%s"' % (esc("Go to step %d: %s" % (i + 1, steps[i]["name"])), esc(sid))

        def add(m):
            tag = m.group(0)
            if re.search(r"\sclass\s*=\s*\"", tag):
                tag = re.sub(r'(\sclass\s*=\s*")', r'\g<1>hv-link ', tag, count=1)
            else:
                tag = tag.replace(">", ' class="hv-link">', 1) if not tag.endswith("/>") else tag[:-2] + ' class="hv-link"/>'
            return tag[:-2] + extra + "/>" if tag.endswith("/>") else tag[:-1] + extra + ">"
        svg = pat.sub(add, svg, count=1)
    return svg


def walk_links(items):
    out = []
    for kind, href, label, back in items:
        cls = ' class="next"' if kind == "next" else ""
        data = ' data-back="%s"' % esc(back) if back else ""
        out.append('<a%s href="%s"%s>%s</a>' % (cls, esc(href), data, label))
    return '<div class="walk">%s</div>' % "".join(out)


def build(spec):
    for key in ("title", "steps", "glossary", "answers", "opening"):
        if key not in spec:
            raise SystemExit("walk-build: spec is missing %r" % key)
    validate(spec)
    il = Inline(spec["glossary"])
    steps = spec["steps"]
    for s in steps:  # an unknown category id falls back to a
        if s.get("cat", "a") not in CATS:
            print("walk-build: warning: step %s has unknown cat %r, using a (known: %s)" % (s["id"], s["cat"], ", ".join(CATS)), file=sys.stderr)
            s["cat"] = "a"
    cats = {c["id"]: c["label"] for c in spec.get("categories", [])}
    for k in cats:
        if k not in CATS:
            print("walk-build: warning: categories entry %r is not one of %s, legend swatch uses a" % (k, ", ".join(CATS)), file=sys.stderr)
    ans = spec["answers"]
    ans_title = ans.get("title", "Answer sheet")
    lbl = lambda i: "%d %s" % (i + 1, steps[i]["name"])
    sec = []

    has_decision = bool(str(spec.get("decision") or "").strip())  # no decision: no strip text box, no "Decision needed" note

    # Opening.
    il.section()
    sec.append('<section class="sec" id="intro" aria-labelledby="h-intro"><h2 id="h-intro" data-name="%s">%s</h2>%s%s%s</section>' % (
        esc(spec.get("opening_title", "Why we are here")), esc(spec.get("opening_title", "Why we are here")),
        '<div class="note idea"><b>Decision needed</b>%s</div>' % il(spec["decision"]) if has_decision else "",
        '<ul class="pts">%s</ul>' % "".join("<li>%s</li>" % il(x) for x in spec["opening"]),
        walk_links([("next", "#flow", "Next: %s -&gt;" % esc(spec.get("flow_title", "The flow")), None)])))

    # Flow chart = table of contents.
    il.section()
    legend = "".join('<span><i style="background:var(--%s-soft);border:1px solid var(--%s)"></i>%s</span>' % (CATS.get(k, "a"), CATS.get(k, "a"), esc(v)) for k, v in cats.items())
    cap = spec.get("flow_caption", [])
    cap = cap if isinstance(cap, list) else [cap]
    has_al = any(s.get("alongside") for s in steps if not s.get("outcomes"))
    if has_al:
        legend += '<span><i class="dash"></i>runs alongside</span>'
    arrows = '<figcaption class="arrows">Arrows show reading order.%s</figcaption>' % (" A dashed step ends in an open circle. The next step does not wait." if has_al else "")
    sec.append(
        '<section class="sec" id="flow"><h2 data-name="%s">%s</h2><p class="lead">%s</p>'
        '<figure>%s<div class="fig flowfig">%s</div><div class="pflow">%s</div><div class="legend">%s<span><i style="background:var(--ok)"></i>opened</span>'
        '<span><i style="background:var(--hi)"></i>you are here</span></div>%s%s</figure>%s</section>' % (
            esc(spec.get("flow_title", "The flow")), esc(spec.get("flow_title", "The flow")),
            il(spec.get("flow_lead", "Click a step to open it. Each step ends with Back, Previous and Next.")),
            arrows if has_al else "", chart_svg(spec), phone_chart(spec), legend, "<figcaption>%s</figcaption>" % "<br>".join(il(c) for c in cap) if cap else "",
            "" if has_al else arrows,
            walk_links([("next", "#" + steps[0]["id"], "Start: %s -&gt;" % esc(lbl(0)), None)])))

    # One section per step.
    for i, s in enumerate(steps):
        il.section()
        cat = s.get("cat", "a")
        body = [block_html(b, il) for b in s.get("blocks", [])]
        links = [("back", "#box-" + s["id"], "&lt;- Back to the flow", s["id"])]
        if i > 0:
            links.append(("prev", "#" + steps[i - 1]["id"], "&lt;- Previous: %s" % esc(lbl(i - 1)), None))
        if i < len(steps) - 1:
            links.append(("next", "#" + steps[i + 1]["id"], "Next: %s -&gt;" % esc(lbl(i + 1)), None))
        else:
            links.append(("next", "#answers", "Next: %s -&gt;" % esc(ans_title), None))
        check = ""
        if s.get("check"):
            check = '<details class="check"><summary><span class="ic" aria-hidden="true">' + ICON_ASK + ICON_DONE + '</span>Check yourself: %s</summary><p class="ans">%s</p></details>' % (
                il(s["check"]["q"], terms=False), il(s["check"]["a"], terms=False))
        sec.append(
            '<section class="sec cat-%s" id="%s"><span class="big-n" aria-hidden="true">%02d</span>'
            '<p class="kind">%s</p><h2 data-name="%s"><span class="step-no">Step %d</span> %s</h2>'
            '<p class="lead">%s</p>%s%s%s%s%s</section>' % (
                esc(cat), esc(s["id"]), i + 1, esc(cats.get(cat, "")), esc(lbl(i)), i + 1, il(s["name"], terms=False),
                il(s["lead"]), analogy_html(s["analogy"], il) if s.get("analogy") else "", "".join(body),
                check,
                '<div class="remember"><div class="ic" aria-hidden="true">' + ICON_MARK + '</div><div><div class="k">Remember</div><p class="say">%s</p></div></div>' % il(s["takeaway"], terms=False) if s.get("takeaway") else "",
                walk_links(links)))

    # Answer sheet: the walk ends here.
    il.section()
    qhtml = []
    for qi, q in enumerate(ans.get("questions", [])):
        n = qi + 1
        h = ['<fieldset class="q" id="q%d" data-title="%s" data-ask="%s"><legend>%d. %s</legend><p class="ctx">%s</p>' % (
            n, esc(q["title"]), esc(q["ask"]), n, esc(q["title"]), il(q["ask"], terms=False))]
        h.append('<p class="why2">Why it matters: %s%s</p>' % (il(q.get("why", ""), terms=False), "<br>%s" % il(q["when"], terms=False) if q.get("when") else ""))
        if q.get("choices"):
            for j, c in enumerate(q["choices"]):
                tag = ' <span class="tag">(%s)</span>' % esc(c["tag"]) if c.get("tag") else ""
                eff = '<span class="why">%s</span>' % il(c["effect"], terms=False) if c.get("effect") else ""
                h.append('<label class="ch"><input type="radio" name="q%d" value="%d" data-text="%s"> %s%s%s</label>' % (
                    n, j, esc(strip_marks(c["text"])), il(c["text"], terms=False), tag, eff))
            h.append('<label class="ch"><input type="radio" name="q%d" value="other"> Other</label>' % n)
            h.append('<input type="text" class="other-in" aria-label="Other answer for question %d" placeholder="Other: type the answer" hidden>' % n)
        else:
            h.append('<input type="text" class="free" aria-label="Answer for question %d" placeholder="Type the answer">' % n)
        h.append('<input type="text" class="note" aria-label="Note for question %d" placeholder="Note (optional)">' % n)
        h.append("</fieldset>")
        qhtml.append("".join(h))
    recap = "".join("<li><b>%s</b> - %s</li>" % (esc(lbl(i)), il(s["takeaway"], terms=False)) for i, s in enumerate(steps) if s.get("takeaway"))
    sec.append(
        '<section class="sec" id="answers"><h2 data-name="%s">%s</h2><p class="lead">%s</p>%s%s'
        '<form id="qform" onsubmit="return false">%s</form>'
        '<div class="btns"><button type="button" id="respond">Respond</button><button type="button" class="sec" id="clear">Clear</button><span class="qcount"></span></div>'
        '<div id="status" role="status" aria-live="polite"></div><textarea id="out" readonly aria-label="Answer summary"></textarea>%s</section>' % (
            esc(ans_title), esc(ans_title), il(ans.get("lead", "Each answer becomes a decision record."), terms=False),
            '<ul class="pts">%s</ul>' % "".join("<li>%s</li>" % il(x, terms=False) for x in ans.get("bullets", [])),
            '<details class="recap"><summary>Before you answer: the %d ideas in one list</summary><ol>%s</ol></details>' % (len(steps), recap) if recap else "",
            "".join(qhtml),
            walk_links([("back", "#flow", "&lt;- Back to the flow", None),
                        ("prev", "#" + steps[-1]["id"], "&lt;- Previous: %s" % esc(lbl(len(steps) - 1)), None)])))

    # Reference.
    refs = list(spec.get("reference", []))
    sec.append('<div class="divider">Reference</div>')
    for r in refs:
        il.section()
        sec.append('<section class="sec ref-sec" id="%s"><h2 data-name="%s">%s</h2>%s%s%s</section>' % (
            esc(r["id"]), esc(r["title"]), esc(r["title"]), '<p class="lead">%s</p>' % il(r["lead"]) if r.get("lead") else "",
            "".join(block_html(b, il) for b in r.get("blocks", [])), walk_links([("back", "#flow", "&lt;- Back to the flow", None)])))
    gl_title = spec.get("glossary_title", "Words used here")
    rows = "".join('<tr><td class="nw">%s</td><td>%s</td></tr>' % (esc(t), esc(m)) for t, m in spec["glossary"])
    sec.append('<section class="sec ref-sec" id="ref-words"><h2 data-name="%s">%s</h2><p class="lead">%s</p>'
               '<div class="tbl"><table><thead><tr><th>Word</th><th>Meaning</th></tr></thead><tbody>%s</tbody></table></div>%s</section>' % (
                   esc(gl_title), esc(gl_title), "Dotted words on this page show their meaning on hover or tap.", rows,
                   walk_links([("back", "#flow", "&lt;- Back to the flow", None)])))

    # Mini-flow menu.
    mi = ['<li><a class="plain" href="#intro">%s</a></li>' % esc(spec.get("opening_title", "Why we are here")),
          '<li><a class="plain" href="#flow">%s</a></li>' % esc(spec.get("flow_title", "The flow"))]
    for i, s in enumerate(steps):
        ends = ""
        if s.get("outcomes"):
            ends = '<div class="ends">%s</div>' % "".join('<span style="color:%s">%s</span>' % (TONES.get(o.get("tone", "a"), "var(--a)"), esc(o["label"])) for o in s["outcomes"])
        tog = '<button type="button" class="seen-tog" data-step="%s" aria-pressed="false" aria-label="Mark step %d as read"></button>' % (esc(s["id"]), i + 1)
        mi.append('<li><a class="cat-%s%s" href="#%s"><span class="n">%d</span>%s</a>%s%s</li>' % (esc(s.get("cat", "a")), " al" if s.get("alongside") else "", esc(s["id"]), i + 1, esc(s["name"]), tog, ends))
    mi.append('<li><a class="plain" href="#answers">%s</a></li>' % esc(ans_title))
    ref_links = "".join('<li><a href="#%s">%s</a></li>' % (esc(r["id"]), esc(r["title"])) for r in refs)
    ref_links += '<li><a href="#ref-words">%s</a></li>' % esc(gl_title)
    nav = ('<nav class="mf" aria-label="Walk-through"><p class="lbl">Walk-through</p><ol class="mini">%s</ol>'
           '<button type="button" class="reset-prog" id="reset-prog">Reset progress</button>'
           '<div class="ref"><p class="lbl">Reference</p><ol>%s</ol></div></nav>') % ("".join(mi), ref_links)

    cfg = {"steps": [[s["id"], lbl(i)] for i, s in enumerate(steps)], "key": spec.get("key") or re.sub(r"\W+", "-", spec["title"].lower()).strip("-"),
           "respondTitle": ans.get("respond_title", spec["title"] + " - answers")}
    dec_step = steps[-1] if steps[-1].get("outcomes") else None
    pills = "".join('<a class="opill" style="--tone:%s" href="#%s">%s</a>' % (
        TONES.get(o.get("tone", "a"), "var(--a)"), esc(dec_step["id"]), esc(o["label"])) for o in dec_step["outcomes"]) if dec_step else ""
    sheet_link = '<a class="cta alt" href="#answers">Open the answer sheet</a>'
    if has_decision:
        strip = ('<div class="dstrip rv"><span class="dk">Decision needed</span><p class="dt">%s</p><div class="dpills">%s</div>%s<p class="dnote">You answer at the end, on the answer sheet.</p></div>') % (
            il(spec["decision"], terms=False), pills, sheet_link)
    elif pills:  # outcomes without a decision text: pills only, under a small label
        strip = '<div class="dstrip rv"><span class="dk">Possible outcomes</span><div class="dpills">%s</div>%s</div>' % (pills, sheet_link)
    else:
        strip = ""
    hero = ('<header class="hero" id="top"><div class="hero-in"><div class="hero-main"><div class="eyebrow rv">%s</div><h1>%s</h1><p class="sub rv">%s</p>%s%s'
            '<a class="cta rv" href="#intro">Start the walk -&gt;</a></div>%s</div></header>') % (
        esc(spec.get("eyebrow", "Walk-through")), esc(spec["title"]), esc(spec.get("subtitle", "")),
        '<p class="big-idea rv"><small>The idea in one sentence</small>%s</p>' % il(spec["idea"], terms=False) if spec.get("idea") else "", strip, hero_visual(spec))
    bar = ('<div class="bar"><div class="bar-in"><a class="brand" href="#top">%s</a><span class="where" aria-live="polite"></span>'
           '<div class="tools"><button type="button" class="btn-ghost" id="present" aria-pressed="false" title="Present: one section at a time, arrow keys move">Present</button>'
           '<div class="pill" role="group" aria-label="Theme"><button type="button" data-t="auto">Auto</button><button type="button" data-t="light">Light</button><button type="button" data-t="dark">Dark</button></div>'
           '<a class="fab" href="#answers"><span class="full">%s</span><span class="short">Answers</span></a></div></div>'
           '<div class="prog" aria-hidden="true"><i></i></div></div>') % (esc(spec["title"]), esc(ans_title))
    css = (HERE / "walk.css").read_text(encoding="ascii")
    js = (HERE / "walk.js").read_text(encoding="ascii")
    page = (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<title>%s</title>\n<meta name="description" content="%s">\n<link rel="preconnect" href="https://fonts.googleapis.com">\n<link rel="stylesheet" href="%s">\n'
        '<style>\n%s</style>\n</head>\n<body>\n<a class="skip" href="#intro">Skip to the walk-through</a>\n%s\n%s\n<div class="wrap">\n%s\n<main id="main">\n%s\n</main>\n</div>\n'
        '<div class="pdots" aria-label="Present mode sections"></div>\n'
        '<script>window.WALK=%s;</script>\n<script src="%s"></script>\n<script>\n%s</script>\n</body>\n</html>\n') % (
        esc(spec["title"]), esc(strip_marks(spec.get("idea", spec.get("subtitle", "")))), FONTS, css, bar, hero, nav, "\n".join(sec),
        json.dumps(cfg).replace("<", "\\u003c"), ANIME, js)
    return page


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("spec")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    raw = Path(a.spec).read_text(encoding="utf-8")
    bad = [(i, ch) for i, ch in enumerate(raw) if ord(ch) > 126 or (ord(ch) < 32 and ch not in "\n\r\t")]
    if bad:
        i, ch = bad[0]
        line = raw.count("\n", 0, i) + 1
        sys.exit("walk-build: spec is not ASCII: %d bad character(s), first U+%04X on line %d" % (len(bad), ord(ch), line))
    global BASE
    BASE = Path(a.spec).resolve().parent
    page = build(json.loads(raw))
    page.encode("ascii")  # fails loudly if anything non-ASCII slipped in
    Path(a.out).write_text(page, encoding="ascii", newline="\n")
    print("walk-build: wrote %s (%d bytes, %d steps)" % (a.out, len(page), len(json.loads(raw)["steps"])))


if __name__ == "__main__":
    main()
