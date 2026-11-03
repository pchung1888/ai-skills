#!/usr/bin/env python3
"""Score a walk-through page against the build brief.

Usage:
  python walk-check.py <page.html> [--spec <spec.json>] [--json]

Each rule is one pass/fail check named after the brief section it guards. Exit code 0 when
every "must" rule passes, 1 otherwise. "Idea" rules measure how well the page helps a
reader catch the idea (lead, takeaway, analogy, check-yourself); they are scored but
do not fail the build. Rule list: references/walk-page.md, "Checks".
"""
import argparse
import html.parser
from html import unescape as html_unescape
import json
import re
import sys
from pathlib import Path

# Idea-rule thresholds. Tunable: raise to warn less often, lower to warn more often.
# Share of a takeaway's content words that also appear in its lead before the takeaway counts as an echo.
TAKEAWAY_ECHO_MAX = 0.5
# Share of a lead's content words that also appear in the step name before the lead counts as a repeat of the name.
LEAD_NAME_REPEAT_MAX = 0.5
# Hard cap for words in one lead or takeaway sentence (the writing target is 20).
LEAD_SENTENCE_MAX_WORDS = 22
STOP_WORDS = set("the a an and or but of to in on at for with by from as is are was were be been it its this that these those "
                 "so if then than not no each every all any one two you your we our they their his her will can may do does".split())


class Tree(html.parser.HTMLParser):
    """Collects the bits the rules need: sections, links, ids, text per tag."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids, self.hrefs, self.sections, self.stack = set(), [], [], []
        self.id_list = []  # every id attribute in page order, to spot duplicates
        self.cur = None
        self.text_by = {}  # (section id, tag) -> list of texts
        self.capture = []
        self.p_count = {}

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("id"):
            self.ids.add(a["id"])
            self.id_list.append(a["id"])
        if tag == "a" and a.get("href", "").startswith("#"):
            self.hrefs.append((a["href"], a.get("class", ""), self.cur["id"] if self.cur else None))
        if tag == "section":
            self.cur = {"id": a.get("id"), "cls": a.get("class", ""), "h2": "", "walk": [], "lead": False, "takeaway": False,
                        "analogy": False, "check": False, "cm_target": True}
            self.sections.append(self.cur)
        if self.cur is not None:
            cls = a.get("class", "")
            if tag == "p" and "lead" in cls.split():
                self.cur["lead"] = True
            if "remember" in cls.split():
                self.cur["takeaway"] = True
            if "analogy" in cls.split():
                self.cur["analogy"] = True
            if tag == "details" and "check" in cls.split():
                self.cur["check"] = True
            if tag == "p" and not ({"lead", "kind", "ctx", "why2", "ans", "say"} & set(cls.split())):
                self.p_count[self.cur["id"]] = self.p_count.get(self.cur["id"], 0) + 1
            if tag == "h2":
                self.cur["h2name"] = a.get("data-name", "")
        if tag in ("li", "td", "h2"):
            self.capture.append([tag, []])

    def handle_endtag(self, tag):
        if self.capture and self.capture[-1][0] == tag:
            t, parts = self.capture.pop()
            text = re.sub(r"\s+", " ", "".join(parts)).strip()
            if self.cur is not None:
                self.text_by.setdefault((self.cur["id"], t), []).append(text)
        if tag == "section":
            self.cur = None

    def handle_data(self, data):
        for c in self.capture:
            c[1].append(data)


def words(s):
    return len(re.findall(r"[A-Za-z0-9][\w'./+-]*", s))


def sentences(s):
    return [x for x in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"(])", s) if x.strip()]


def check(page_path, spec_path=None):
    raw = Path(page_path).read_bytes()
    text = raw.decode("utf-8", "replace")
    t = Tree()
    t.feed(text)
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8")) if spec_path else None
    secs = [s for s in t.sections if s["id"]]
    ids = [s["id"] for s in secs]
    step_secs = [s for s in secs if re.fullmatch(r"s\d+", s["id"]) or (spec and s["id"] in {x["id"] for x in spec["steps"]})]
    step_ids = [s["id"] for s in step_secs]
    R = []

    def rule(rid, group, ok, detail, must=True):
        R.append({"id": rid, "group": group, "ok": bool(ok), "detail": detail, "must": must})

    # Page order.
    rule("order-opening-first", "Page order", ids[:1] == ["intro"], "first section is %s" % (ids[:1],))
    rule("order-chart-second", "Page order", ids[1:2] == ["flow"], "second section is %s" % (ids[1:2],))
    after = ids[2:2 + len(step_ids)]
    rule("order-steps-follow-chart", "Page order", after == step_ids and step_ids, "%d step sections after the chart" % len(step_ids))
    nxt = ids[2 + len(step_ids):3 + len(step_ids)]
    rule("order-answers-after-last-step", "Page order", nxt == ["answers"], "after last step: %s" % (nxt,))
    div = text.find('class="divider"')
    rule("order-reference-after-divider", "Page order", div > text.find('id="answers"') > 0, "divider after answer sheet")
    rule("glossary-present", "Content", "ref-words" in ids, "Words used here section")
    intro_li = " ".join(t.text_by.get(("intro", "li"), []))
    rule("opening-40-110-words", "Content", 40 <= words(intro_li) <= 110, "%d words in the opening points" % words(intro_li))

    # Content rules.
    lis = [x for (sid, tag), v in t.text_by.items() if tag == "li" and sid in step_ids + ["intro"] for x in v]
    long_pts = [x for x in lis if words(x) > 22]
    rule("points-short", "Content", not long_pts, "target 20, fails over 22: %d li points over 22 words: %s" % (len(long_pts), "; ".join(x[:60] for x in long_pts[:3])))
    over20 = [x for x in lis if words(x) > 20]
    rule("points-target-20", "Content", not over20, "%d li points over the 20-word target (hard fail is over 22)" % len(over20), must=False)
    semi = [x for x in lis if ";" in x]
    rule("no-semicolons", "Content", not semi, "%d points with a semicolon" % len(semi))
    paras = {k: v for k, v in t.p_count.items() if k in step_ids}
    rule("no-paragraphs", "Content", not any(paras.values()), "stray <p> per step: %s" % paras)
    rule("lead-per-step", "Content", all(s["lead"] for s in step_secs), "%d of %d steps open with a lead sentence" % (sum(s["lead"] for s in step_secs), len(step_secs)))

    # Chart.
    boxes = re.findall(r'<a class="st[^"]*" id="box-([\w-]+)" href="#([\w-]+)"', text)
    rule("chart-box-per-step", "Chart", [b[1] for b in boxes] == step_ids, "%d boxes link to %d steps" % (len(boxes), len(step_ids)))
    pboxes = re.findall(r'<a class="st pst[^"]*" id="pbox-([\w-]+)" href="#([\w-]+)"', text)
    rule("chart-box-per-step-phone", "Chart", [b[1] for b in pboxes] == step_ids and all(a == b for a, b in pboxes), "%d phone boxes link to %d steps in order" % (len(pboxes), len(step_ids)))
    rule("chart-decision-diamond", "Chart", "<polygon" in text.split('id="flow"')[1].split("</section>")[0] if 'id="flow"' in text else False, "diamond in the chart")
    flow_html = text.split('id="flow"', 1)[1].split("</section>", 1)[0] if 'id="flow"' in text else ""
    groups = re.findall(r'<g class="oc">.*?</g>', flow_html, re.S) + re.findall(r'<a class="st [^"]*" id="box-.*?</a>', flow_html, re.S)
    crowded = []
    for g in groups:
        by_x = {}
        for x, y in re.findall(r'<text[^>]* x="(-?\d+)" y="(-?\d+)"', g):
            by_x.setdefault(x, []).append(int(y))
        for ys in by_x.values():
            ys.sort()
            crowded += [b - a for a, b in zip(ys, ys[1:]) if b - a < 12]
    rule("chart-text-no-overlap", "Chart", groups and not crowded, "%d outcome/step boxes checked, %d text baselines closer than 12px" % (len(groups), len(crowded)))
    rule("chart-legend", "Chart", 'class="legend"' in text, "legend under the chart")
    rule("chart-own-scroll-box", "Chart", re.search(r"\.fig\{overflow-x:auto", text) is not None, "chart scrolls in its own box on a phone")

    # Navigation.
    menu = re.findall(r'<li><a class="cat-[\w]+(?: al)?" href="#([\w-]+)"><span class="n">(\d+)</span>([^<]+)</a>', text)
    rule("menu-mini-flow", "Navigation", [m[0] for m in menu] == step_ids, "%d menu boxes in step order" % len(menu))
    rule("menu-outcomes", "Navigation", 'class="ends"' in text, "decision outcomes under the last menu step")
    rule("yellow-you-are-here", "Navigation", re.search(r"a\.cur\{background:var\(--hi\)", text) and "--hi:#f5b800" in text, "yellow highlight token")
    rule("no-red-highlight", "Navigation", not re.search(r"\.cur\{[^}]*(red|#f00|#e00)", text), "highlight is not red")
    names_ok = True
    detail = []
    for i, s in enumerate(step_secs):
        nm = (s.get("h2name") or "").split(" ", 1)[-1]
        box_t = re.search(r'id="box-%s"[^>]*><title>Open step \d+: ([^<]+)</title>' % re.escape(s["id"]), text)
        menu_t = [m[2] for m in menu if m[0] == s["id"]]
        nexts = re.findall(r'href="#%s">(?:Next|&lt;- Previous|Start): \d+ ([^<]+?)(?: -&gt;)?</a>' % re.escape(s["id"]), text)
        got = {html_unescape(x) if x else x for x in {nm, box_t.group(1) if box_t else None, menu_t[0] if menu_t else None} | set(nexts)}
        if len(got) != 1:
            names_ok = False
            detail.append("%s: %s" % (s["id"], sorted(x or "?" for x in got)))
    rule("names-match-4-places", "Navigation", names_ok, "chart, menu, heading, links agree" if names_ok else "; ".join(detail[:3]))
    walks_ok = []
    for i, sid in enumerate(step_ids):
        sec_html = text.split('id="%s"' % sid, 1)[1].split("</section>", 1)[0]
        has_back = 'data-back="%s"' % sid in sec_html
        has_prev = i == 0 or 'href="#%s">&lt;- Previous' % step_ids[i - 1] in sec_html
        target = step_ids[i + 1] if i < len(step_ids) - 1 else "answers"
        has_next = re.search(r'class="next" href="#%s"' % target, sec_html) is not None
        walks_ok.append(has_back and has_prev and has_next)
    rule("walk-links-every-step", "Navigation", all(walks_ok) and walks_ok, "%d of %d steps have Back, Previous, Next" % (sum(walks_ok), len(walks_ok)))
    ans_html = text.split('id="answers"', 1)[1].split("</section>", 1)[0] if 'id="answers"' in text else ""
    rule("answers-no-next", "Navigation", 'class="next"' not in ans_html and ans_html, "answer sheet ends the walk")
    rule("intro-next-flow", "Navigation", re.search(r'id="intro".*?class="next" href="#flow"', text, re.S) is not None, "opening says Next: the flow")
    bad = sorted({h for h, _, _ in t.hrefs if len(h) > 1 and h[1:] not in t.ids})
    rule("links-resolve", "Navigation", not bad, "missing targets: %s" % bad)
    dup = sorted({i for i in t.id_list if t.id_list.count(i) > 1})
    rule("unique-ids", "Navigation", not dup, "%d ids in the page, duplicates: %s" % (len(t.id_list), dup or "none"))

    # Questions, comments, Respond.
    qs = re.findall(r'<fieldset class="q" id="q\d+".*?</fieldset>', text, re.S)
    q_ok = [("Why it matters:" in q and 'class="note"' in q and ('value="other"' in q or 'class="free"' in q)) for q in qs]
    rule("questions-complete", "Answers", qs and all(q_ok), "%d of %d questions have why, Other or free text, and a note" % (sum(q_ok), len(qs)))
    rule("comments-script", "Answers", "Save comment" in text and "has-c" in text, "Comment, Save, Delete and menu marker")
    rule("respond-fallback", "Answers", "execCommand(\"copy\")" in text and "clipboard.writeText" in text, "clipboard plus select-and-copy fallback")
    rule("respond-unsaved-warning", "Answers", "not saved" in text, "warns about unsaved comments")
    rule("floating-answer-button", "Answers", 'class="fab" href="#answers"' in text, "floating answer sheet button")

    # Look, motion and safety.
    try:
        raw.decode("ascii")
        ascii_ok, ad = True, "ASCII only"
    except UnicodeDecodeError as e:
        ascii_ok, ad = False, "non-ASCII byte at %d" % e.start
    rule("ascii-only", "Look", ascii_ok, ad)
    shown = re.sub(r"(?is)<(script|style|code|pre|svg)\b.*?</\1>", " ", text)
    shown = re.sub(r"<[^>]+>", " ", shown)
    placeholder = sorted({m.group(0).lower() for m in re.finditer(r"(?i)\bto be set\b|\bTBD\b|\bTODO\b", shown)})
    rule("no-placeholder-text", "Content", not placeholder, "reader-facing text outside code has no 'to be set', 'TBD' or 'TODO'%s" % (": found " + ", ".join(placeholder) if placeholder else ""))
    rule("theme-picker", "Look", all(x in text for x in ('data-t="auto"', 'data-t="light"', 'data-t="dark"', ':root[data-theme="dark"]', "prefers-color-scheme:dark")), "Auto, Light, Dark with a dark token set")
    rule("type-scale-tokens", "Look", "--fs-1" in text and "--s3" in text, "type scale and spacing tokens")
    rule("focus-rings", "Look", ":focus-visible" in text, "focus rings")
    rule("plex-fonts", "Look", "IBM+Plex+Sans" in text and "IBM+Plex+Serif" in text, "IBM Plex Sans and Serif")
    rule("reduced-motion", "Motion", "prefers-reduced-motion" in text and "matchMedia" in text, "motion off under reduced motion")
    rule("anime-pinned", "Motion", re.search(r"cdnjs\.cloudflare\.com/ajax/libs/animejs/\d+\.\d+\.\d+/", text) is not None, "anime.js pinned to an exact cdnjs version")
    rule("works-without-script", "Motion", "window.anime&&" in text.replace(" ", "") and ".motion .rv" in text, "hidden-until-animated only when anime loaded")

    # Idea catching (scored, never fails the build).
    n = len(step_secs) or 1
    rule("idea-sentence", "Idea", 'class="big-idea' in text, "one-sentence idea in the hero", must=False)
    hv_m = re.search(r'<aside class="hero-map hero-vis">(<svg\b[^>]*>)(.*?)</svg>', text, re.S)
    hv_root = hv_m.group(1) if hv_m else ""
    hv_lab = re.search(r'aria-label\s*=\s*"([^"]*)"', hv_root)
    hv_links = bool(hv_m) and 'class="hv-link' in hv_m.group(2)
    hv_role = "group" if hv_links else "img"
    hv_why = []
    if not hv_m:
        hv_why.append('no <aside class="hero-map hero-vis"> that starts with an <svg> whose opening tag has no ">" inside an attribute')
    else:
        if 'role="%s"' % hv_role not in hv_root:
            hv_why.append('svg root needs role="%s"%s' % (hv_role, " (it holds hv-link parts)" if hv_links else ""))
        if not hv_lab or len(hv_lab.group(1).strip()) < 8:
            hv_why.append("svg root needs aria-label of 8+ characters")
    rule("idea-hero-visual", "Idea", not hv_why, "hero svg picture of the idea (spec hero_visual)" + (": " + "; ".join(hv_why) if hv_why else " has the right role and an aria-label"), must=False)
    if hv_m:
        vb = re.search(r'viewBox\s*=\s*"\s*[-\d.]+[ ,]+[-\d.]+[ ,]+([\d.]+)', hv_root)
        floor = 22 * (float(vb.group(1)) / 560 if vb else 1)
        small = [float(m.group(1)) for t in re.findall(r"<text\b[^>]*>", hv_m.group(2)) for m in [re.search(r"font-size\s*[:=]\s*\"?([\d.]+)", t)] if m and float(m.group(1)) < floor]
        rule("hero-text-size", "Idea", not small, "hero svg text is at least %.0f units at this viewBox (12px on a 375px phone)%s" % (floor, ": smallest is %g" % min(small) if small else ""), must=False)
    rule("idea-takeaway-per-step", "Idea", all(s["takeaway"] for s in step_secs), "%d of %d steps end with Remember" % (sum(s["takeaway"] for s in step_secs), n), must=False)
    rule("idea-check-yourself", "Idea", sum(s["check"] for s in step_secs) >= n / 2, "%d of %d steps have Check yourself" % (sum(s["check"] for s in step_secs), n), must=False)
    rule("idea-analogy", "Idea", sum(s["analogy"] for s in step_secs) >= 3, "%d steps have an analogy" % sum(s["analogy"] for s in step_secs), must=False)
    rule("idea-glossary-inline", "Idea", text.count('class="term"') >= 10, "%d inline glossary popovers" % text.count('class="term"'), must=False)
    def sec_html(sid):
        return text.split('id="%s"' % sid, 1)[1].split("</section>", 1)[0]
    vis = sum(1 for sid in step_ids if re.search(r'class="(stats|ba|chips|fig|analogy|tbl)[ "]', sec_html(sid)))
    rule("idea-visual-per-step", "Idea", vis >= n * 0.75, "%d of %d steps have a visual (stats, before/after, chips, figure, analogy, table)" % (vis, n), must=False)
    mech = [sid for sid in step_ids if 'class="fig"' in sec_html(sid)]
    rule("idea-mechanism-svg", "Idea", mech, "%d steps have a figure from svg or svg_file" % len(mech), must=False)
    figs = [svg for sid in step_ids for svg in re.findall(r'<div class="fig">(<svg.*?</svg>)', sec_html(sid), re.S)]
    fonts = [(m.group(1) or m.group(2) or m.group(3) or "").strip() for svg in figs
             for m in re.finditer(r'font-family\s*[:=]\s*(?:"([^"]*)"|\'([^\']*)\'|([^;"\'>}]*))', svg)]
    bad_f = [x for x in fonts if x != "var(--sans)"]
    rule("svg-font-tokens", "Idea", not bad_f, "%d figure fonts, %d not var(--sans)%s" % (len(fonts), len(bad_f), ": " + "; ".join(bad_f[:2]) if bad_f else ""), must=False)
    rule("svg-emphasis", "Idea", any("var(--hi)" in svg for svg in figs), "%d of %d step figures use var(--hi) for the one thing to look at" % (sum("var(--hi)" in svg for svg in figs), len(figs)), must=False)
    n_an = sum(sec_html(sid).count('class="analogy"') for sid in step_ids)
    rule("idea-analogy-cap", "Idea", n_an <= 5, "%d analogies in the steps (more than 5 stops being special)" % n_an, must=False)
    verbish = {"is", "are", "has", "have", "gets", "goes", "runs", "sets", "picks", "needs", "keeps", "moves", "ends", "starts", "builds", "makes", "shows", "checks", "tests", "proves"}
    def has_verb(name):
        return any(w in verbish or (len(w) > 3 and w.endswith(("s", "ed", "ing"))) for w in re.findall(r"[a-z']+", name.lower()))
    names = [(s.get("h2name") or "").split(" ", 1)[-1] for s in step_secs]
    no_verb = [x for x in names if not has_verb(x)]
    rule("idea-claim-names", "Idea", len(no_verb) * 3 <= len(names), "%d of %d step names have no verb-like word%s" % (len(no_verb), len(names), ": " + "; ".join(no_verb[:3]) if no_verb else ""), must=False)
    lead_m = re.search(r'<p class="lead">(.*?)</p>', flow_html, re.S)
    lead_t = re.sub(r"<[^>]+>", "", lead_m.group(1)) if lead_m else ""
    rule("idea-flow-lead", "Idea", lead_m and "click" not in lead_t.lower() and words(lead_t) >= 6, "flow lead has %d words%s" % (words(lead_t), ", says click" if "click" in lead_t.lower() else ""), must=False)

    # Lead and takeaway text, read from the page (steps only).
    def plain(h):
        return re.sub(r"\s+", " ", html_unescape(re.sub(r"<[^>]+>", "", h))).strip()

    def content(x):
        return {w for w in re.findall(r"[a-z]+", x.lower()) if len(w) > 2 and w not in STOP_WORDS}
    lead_of, take_of, name_of = {}, {}, {}
    for s_ in step_secs:
        h_ = sec_html(s_["id"])
        lm = re.search(r'<p class="lead">(.*?)</p>', h_, re.S)
        tm = re.search(r'class="remember">.*?<p class="say">(.*?)</p>', h_, re.S)  # the Remember card only; the analogy also uses p.say
        lead_of[s_["id"]] = plain(lm.group(1)) if lm else ""
        take_of[s_["id"]] = plain(tm.group(1)) if tm else ""
        name_of[s_["id"]] = (s_.get("h2name") or "").split(" ", 1)[-1]
    long_s = [(sid, x) for sid in step_ids for x in sentences(lead_of[sid]) + sentences(take_of[sid]) if words(x) > LEAD_SENTENCE_MAX_WORDS]
    rule("lead-takeaway-short", "Content", not long_s, "%d lead or takeaway sentences over %d words (target 20)%s" % (
        len(long_s), LEAD_SENTENCE_MAX_WORDS, ": " + "; ".join("%s: %s" % (a_, b_[:50]) for a_, b_ in long_s[:3]) if long_s else ""))
    topic = [sid for sid in step_ids if re.match(r"^The [\w ]{1,20}? (is|are) (a|an|the) ", lead_of[sid], re.I)]
    # Idea rule, not must: definition leads ("The X is a Y") can be the reader's own content, so a must rule would fail good pages.
    rule("idea-lead-is-claim", "Idea", not topic, "%d leads read 'The X is a/an/the ...' (a definition, not a claim; idea rule because some definitions are the content)%s" % (len(topic), ": " + ", ".join(topic[:6]) if topic else ""), must=False)

    def share(a_, b_):
        ca, cb = content(a_), content(b_)
        return len(ca & cb) / len(ca) if ca else 0
    echo = [sid for sid in step_ids if take_of[sid] and share(take_of[sid], lead_of[sid]) > TAKEAWAY_ECHO_MAX]
    rule("idea-takeaway-not-echo", "Idea", not echo, "%d takeaways share over %d%% of their content words with the lead%s" % (
        len(echo), TAKEAWAY_ECHO_MAX * 100, ": " + ", ".join(echo[:6]) if echo else ""), must=False)
    rep = [sid for sid in step_ids if share(lead_of[sid], name_of[sid]) > LEAD_NAME_REPEAT_MAX]
    rule("idea-lead-not-name", "Idea", not rep, "%d leads mostly repeat the step name (over %d%% of content words)%s" % (
        len(rep), LEAD_NAME_REPEAT_MAX * 100, ": " + ", ".join(rep[:6]) if rep else ""), must=False)

    # Text length (warnings only; read from the spec, skipped without one).
    if spec:
        steps_ = spec["steps"]
        dec = steps_[-1] if steps_ and steps_[-1].get("outcomes") else None
        outs = dec["outcomes"] if dec else []
        limits = [("idea-len-title", "title", 40, [spec.get("title", "")]),
                  ("idea-len-step-name", "step name", 28, [x.get("name", "") for x in steps_]),
                  ("idea-len-step-sub", "step sub", 40, [x.get("sub", "") for x in steps_]),
                  ("idea-len-outcome-label", "outcome label", 16, [o.get("label", "") for o in outs]),
                  ("idea-len-outcome-note", "outcome note", 24, [o.get("note", "") for o in outs])]
        for rid, label, lim, vals in limits:
            bad_ = [v for v in vals if len(v) > lim]
            rule(rid, "Idea", not bad_, "%d of %d %s over %d chars%s" % (len(bad_), len(vals), label, lim, ": " + "; ".join(v[:40] for v in bad_[:3]) if bad_ else ""), must=False)

        par = re.compile(r"while (the )?other(s| steps)|while others go on|in parallel|meanwhile|alongside|at the same time|concurrent(ly)?|in the background", re.I)
        nosvg = lambda v: {k: nosvg(x) for k, x in v.items() if k != "svg"} if isinstance(v, dict) else [nosvg(x) for x in v] if isinstance(v, list) else v
        miss_ = [x.get("id", "?") for x in steps_ if not x.get("alongside") and par.search(x.get("lead", "") + " " + " ".join(b for b in x.get("bullets", []) if isinstance(b, str)) + " " + json.dumps(nosvg(x.get("blocks", []))))]
        rule("alongside-stated", "Idea", not miss_, "%d steps say they run alongside others but have no alongside field%s" % (len(miss_), ": " + ", ".join(miss_[:6]) if miss_ else ""), must=False)

    all_w = [words(x) for x in lis] or [0]
    stats = {"points": len(lis), "max_words_per_point": max(all_w), "mean_words_per_point": round(sum(all_w) / len(all_w), 1),
             "points_over_20": sum(1 for w in all_w if w > 20), "bytes": len(raw)}
    return R, stats


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("page")
    ap.add_argument("--spec")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    R, stats = check(a.page, a.spec)
    must = [r for r in R if r["must"]]
    idea = [r for r in R if not r["must"]]
    score = {"must_pass": sum(r["ok"] for r in must), "must_total": len(must), "idea_pass": sum(r["ok"] for r in idea), "idea_total": len(idea)}
    if a.json:
        print(json.dumps({"score": score, "stats": stats, "rules": R}, indent=1))
    else:
        for r in R:
            print("%s  %-32s %-10s %s" % ("PASS" if r["ok"] else ("FAIL" if r["must"] else "MISS"), r["id"], r["group"], r["detail"]))
        print("SCORE brief %d/%d  idea %d/%d  | points %d, max %d words, mean %.1f, over 20: %d" % (
            score["must_pass"], score["must_total"], score["idea_pass"], score["idea_total"], stats["points"],
            stats["max_words_per_point"], stats["mean_words_per_point"], stats["points_over_20"]))
    sys.exit(0 if score["must_pass"] == score["must_total"] else 1)


if __name__ == "__main__":
    main()
