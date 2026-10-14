"""Render the html-plan blocks: flow, calls, machine, terminal, note, ask, code-pins.

Each block becomes an html-plan element (doc-flow, doc-calls, ...). The browser draws it with the
vendored runtime (vendor/html-plan/), which md-to-html inlines on any page that uses one of these
blocks. Block syntax: SKILL.md "html-plan blocks"; html-plan's own reference is its blocks.md.
"""
from __future__ import annotations

import re
from html import escape
from pathlib import Path

import yaml

NAMES = ("flow", "calls", "machine", "terminal", "note", "ask", "code-pins")
TONES = ("info", "warn", "risk", "ok", "idea")
# code-pins reads a file from the folder md-to-html runs in; these names never go into a page.
SECRET_RE = re.compile(r"(^|[\\/])(\.env[^\\/]*|id_rsa[^\\/]*|[^\\/]*\.(pem|key|pfx|p12)|[^\\/]*secret[^\\/]*)$", re.I)
MAX_CODE_LINES = 60


def _problem(block: str, why: str) -> str:
    # A visible note, so a broken block shows on the page instead of vanishing.
    return f'<doc-note tone="risk"><strong>{escape(block)} block skipped</strong> {escape(why)}</doc-note>\n'


def _script_safe(text: str) -> str:
    # Text inside <script type="text/plain"> must not end the tag early ("</script" in any case)
    # or open a script-data comment ("<!--"). The backslash shows in the drawn block; that is the cost.
    return re.sub(r"</(script)", r"<\\/\1", text, flags=re.I).replace("<!--", "<\\!--")


def _plain(tag: str, body: str, attrs: str = "") -> str:
    # html-plan reads the source from a text/plain script.
    body = _script_safe(body)
    return f'<{tag}{attrs}>\n<script type="text/plain">\n{body}</script>\n</{tag}>\n'


def _yaml(block: str, body: str):
    try:
        y = yaml.safe_load(body)
    except yaml.YAMLError as e:
        return None, _problem(block, f"the YAML did not parse ({str(e).splitlines()[0]})")
    if not isinstance(y, dict):
        return None, _problem(block, "expected YAML keys, see SKILL.md")
    return y, None


FLOW_SYNTAX_RE = re.compile(r"(?m)^\s*[\w-]+\s*=|->|^\s*\|")
LIST_MARK_RE = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+")
NOTE_TITLES = {"info": "Note", "warn": "Watch out", "risk": "Risk", "ok": "Good", "idea": "Idea"}
_asks = [0]


def flow(body: str, info: str = "") -> str:
    """html-plan flow syntax, or a plain list of steps, drawn top to bottom in that order."""
    if FLOW_SYNTAX_RE.search(body):
        return _plain("doc-flow", body)
    steps = [LIST_MARK_RE.sub("", l).strip() for l in body.splitlines() if l.strip()]
    if not steps:
        return _problem("flow", "no steps")
    # "=" and "->" would read as flow syntax inside a label, so they become plain words.
    steps = [s.replace("->", "to").replace("=", ":") for s in steps]
    lines = [f"s{i} = {s}" for i, s in enumerate(steps, 1)]
    lines += [f"| s{i} |" for i in range(1, len(steps) + 1)]
    lines += [f"s{i} -> s{i + 1}" for i in range(1, len(steps))]
    return _plain("doc-flow", "\n".join(lines) + "\n")


def calls(body: str, info: str = "") -> str:
    return _plain("doc-calls", body)


def machine(body: str, info: str = "") -> str:
    m = re.search(r"(?m)^\s*machine\s+([\w-]+)", body)
    return _plain("doc-machine", body, f' name="{escape(m.group(1))}"' if m else "")


def terminal(body: str, info: str = "") -> str:
    # {g}..{/g} green, {r}..{/r} red, {y}..{/y} amber, {dim}..{/dim} grey, {b}..{/b} bold; the rest is text.
    t = escape(body.rstrip("\n"))
    for k in ("g", "r", "y", "dim"):
        t = t.replace("{" + k + "}", f'<span class="{k}">').replace("{/" + k + "}", "</span>")
    t = t.replace("{b}", "<b>").replace("{/b}", "</b>")
    return f'<doc-mock frame="terminal" w="480"><template>{t}</template></doc-mock>\n'


def _yaml_or_none(body: str):
    try:
        y = yaml.safe_load(body)
    except yaml.YAMLError:
        return None
    return y if isinstance(y, dict) else None


def note(body: str, info: str = "") -> str:
    """YAML (tone, title, body), or ```note <tone> followed by plain text."""
    y = _yaml_or_none(body)
    if not y or "body" not in y:
        words = info.split()
        y = {"tone": words[0] if words else "info", "body": " ".join(body.split())}
    tone = str(y.get("tone", "info"))
    if tone not in TONES:
        tone = "info"
    title = escape(str(y.get("title") or NOTE_TITLES[tone]))
    return f'<doc-note tone="{tone}"><strong>{title}</strong> {escape(str(y.get("body", "")))}</doc-note>\n'


def _ask_from_list(body: str) -> dict:
    """A question line, then options as "- [x] text" (picked) or "- [ ] text"."""
    question, opts = "", []
    for line in body.splitlines():
        m = re.match(r"^\s*[-*]\s+(?:\[([ xX])\]\s*)?(.+)$", line)
        if m:
            opts.append({"label": m.group(2).strip(), "checked": (m.group(1) or " ").lower() == "x"})
        elif line.strip() and not opts:
            question = (question + " " + line.strip()).strip()
    _asks[0] += 1
    for i, o in enumerate(opts, 1):
        o["value"] = f"o{i}"
    return {"id": f"choice-{_asks[0]}", "question": question, "options": opts,
            "multi": sum(o["checked"] for o in opts) > 1}


def ask(body: str, info: str = "") -> str:
    """YAML (id, question, multi, options), or a question line then "- [x]" / "- [ ]" options."""
    y = _yaml_or_none(body)
    if not y or "options" not in y:
        y = _ask_from_list(body)
    opts = y.get("options") or []
    if not y.get("id") or not y.get("question") or not isinstance(opts, list) or len(opts) < 2:
        return _problem("ask", "needs a question and at least two options")
    kind, name = ("checkbox" if y.get("multi") else "radio"), escape(str(y["id"]))
    rows = []
    for o in opts:
        if not isinstance(o, dict) or "label" not in o:
            return _problem("ask", "every option needs a label")
        value = escape(str(o.get("value", o["label"])))
        note_ = f' <small>{escape(str(o["note"]))}</small>' if o.get("note") else ""
        rows.append(f'<label><input type="{kind}" name="{name}" value="{value}"'
                    f'{" checked" if o.get("checked") else ""}> {escape(str(o["label"]))}{note_}</label>')
    return f'<doc-ask id="{name}"><p>{escape(str(y["question"]))}</p>{"".join(rows)}</doc-ask>\n'


def code_pins(body: str, info: str = "") -> str:
    """YAML: path + lines (a-b) read from the current folder, or code + start; pins: {line: note}."""
    y, bad = _yaml("code-pins", body)
    if bad:
        return bad
    pins = y.get("pins") or {}
    if not isinstance(pins, dict):
        return _problem("code-pins", "pins must be line: note pairs")
    title = str(y.get("title") or y.get("path") or "code")
    if y.get("path"):
        root = Path.cwd().resolve()
        f = (root / str(y["path"])).resolve()
        if root not in f.parents or SECRET_RE.search(str(f)) or not f.is_file():
            return _problem("code-pins", f"cannot read {y['path']} (outside this folder, a secrets file, or missing)")
        m = re.fullmatch(r"(\d+)-(\d+)", str(y.get("lines", "")).strip())
        if not m:
            return _problem("code-pins", "lines must look like 120-140")
        a, b = int(m.group(1)), int(m.group(2))
        if not 1 <= a <= b or b - a >= MAX_CODE_LINES:
            return _problem("code-pins", f"lines must be a range of at most {MAX_CODE_LINES}")
        code = "\n".join(f.read_text(encoding="utf-8", errors="replace").splitlines()[a - 1:b]) + "\n"
    elif y.get("code"):
        a, code = int(y.get("start", 1)), str(y["code"])
    else:
        return _problem("code-pins", "needs path + lines, or code")
    lang = escape(str(y.get("lang") or Path(title).suffix.lstrip(".") or "plain"))
    hl = ",".join(str(int(n)) for n in pins)
    pin_html = "".join(f'<doc-pin line="{int(n)}" tone="info" title="{escape(str(t))}"></doc-pin>' for n, t in pins.items())
    code = _script_safe(code)
    return (f'<doc-code title="{escape(title)}" lang="{lang}" start="{a}" hl="{hl}" wrap>\n'
            f'<script type="text/plain">\n{code}</script>\n{pin_html}</doc-code>\n')


RENDERERS = {"flow": flow, "calls": calls, "machine": machine, "terminal": terminal,
             "note": note, "ask": ask, "code-pins": code_pins}
