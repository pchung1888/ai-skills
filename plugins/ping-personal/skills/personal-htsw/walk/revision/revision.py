#!/usr/bin/env python3
"""Revision mode page tool (Python 3 standard library only).

Usage:
  python revision.py inject <in.html> --out <out.html> [--default on|off] [--source <name>] [--carry-ids-from <v1.html>]
  python revision.py textcheck <a.html> <b.html>
  python revision.py extract <saved.html> --out <pins.json>
  python revision.py report <pins.json> <v2.html>

inject stamps data-rev-id on meaningful elements and adds the css, snap and js blocks.
It never changes a text node and never overwrites its input file.
textcheck prints TEXT SAME or TEXT DIFF: <offset> for the content text of two pages.
extract validates the rev-annotations block of a saved page and writes one ledger row per pin.
report checks a ledger against the v2 page and prints a last line REVISE REPORT OK or REVISE REPORT FAIL.
It never rewrites the ledger; verdicts it changes to orphaned go to <ledger>.reported.json.
"""
import argparse
import hashlib
import json
import re
import sys
from collections import namedtuple
from difflib import SequenceMatcher
from html.parser import HTMLParser
from pathlib import Path

REVISION_DIR = Path(__file__).resolve().parent
MAX_SLUG_LENGTH = 32
FALLBACK_SECTION = "s1"
SMALL_SVG_PIXELS = 48

VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr",
}
INLINE_TAGS = {
    "span", "a", "em", "strong", "b", "i", "u", "code", "small", "sub", "sup", "mark", "kbd", "abbr", "label", "time", "br",
}
NON_TEXT_BLOCK_TAGS = {
    "html", "head", "body", "title", "meta", "link", "base", "noscript", "caption", "thead", "tbody", "tfoot", "tr", "td",
    "th", "colgroup", "col", "ul", "ol", "dl", "select", "option", "optgroup", "textarea", "summary", "script", "style",
    "template", "section", "article", "main",
}
CLOSED_SUBTREE_TAGS = {
    "script", "style", "template", "nav", "head", "svg", "canvas", "noscript", "select", "textarea", "picture",
}
CLOSED_SUBTREE_KINDS = {"h", "btn", "code", "img", "dia"}
UI_CLASS_NAMES = {"bar", "nw-bar"}
UI_CLASS_PREFIXES = ("sc-", "nw-")
CONTENT_TEXT_SKIPPED_TAGS = {"script", "style", "template", "head"}
IMPLIED_END_TAGS = {"p", "li", "dt", "dd", "tr", "td", "th"}
# A replaced element keeps its v1 id only when the two texts are at least this similar (difflib ratio, 0 to 1).
# Fixture cases: an edited sentence scores 0.69, an unrelated sentence scores 0.35 to 0.38.
CARRY_MIN_TEXT_SIMILARITY = 0.5
ANNOTATION_CONTEXT = "http://www.w3.org/ns/anno.jsonld"
ANNOTATIONS_SCRIPT_ID = "rev-annotations"
REPORTED_SUFFIX = ".reported.json"  # report writes changed verdicts here, never over the input ledger
PINS_IN_SUFFIX = ".count"  # sidecar next to the ledger: how many pins extract found
VERDICTS = ("done", "kept", "orphaned")
CSS_SELECTOR_ID_PATTERN = re.compile(r'^\[data-rev-id="([^"]+)"\]$')
IdRecord = namedtuple("IdRecord", "rev_id section kind text")
Candidate = namedtuple("Candidate", "element_index section kind")

# One kind table, tag rules only. Order matters: the first matching row wins.
# Keys: tags, classes, tag_classes (tag with class), tags_without_class (tag lacking class),
# parent_class_tags (tag whose parent has class), roles, input_types, not_under (skip under these tags).
KIND_TABLE = [
    ("fig", {"tags": {"figure"}, "classes": {"fig"}}),
    ("tbl", {"tags": {"table"}}),
    ("row", {"tags": {"tr"}, "not_under": {"thead", "tfoot"}}),
    ("code", {"tags": {"pre"}}),
    ("dia", {"tags": {"canvas", "doc-flow", "svg"}, "classes": {"mermaid"}}),
    ("img", {"tags": {"img", "picture"}}),
    ("btn", {"tags": {"button"}, "tag_classes": {("a", "btn")}, "roles": {"button"}, "input_types": {"button", "submit"}}),
    (
        "box",
        {
            "tags": {"aside", "doc-note", "doc-ask", "doc-claim", "doc-pin"},
            "classes": {"callout", "say", "why", "why2"},
            "tag_classes": {("div", "note"), ("div", "analogy")},
            "tags_without_class": {("details", "lvl")},
        },
    ),
    ("h", {"tags": {"h1", "h2", "h3", "h4", "h5", "h6"}, "parent_class_tags": {("summary", "lvl")}}),
    ("li", {"tags": {"li"}}),
    ("def", {"tags": {"dt", "dd"}}),
    ("p", {"tags": {"p", "blockquote"}}),
]
KIND_SPEC_BY_NAME = dict(KIND_TABLE)
FIGURE_SUPPRESSED_KINDS = {"img", "dia"}

DEFAULT_CSS_PLACEHOLDER = "/* revision.css not found next to revision.py; placeholder injected */"
DEFAULT_JS_PLACEHOLDER = "/* revision.js not found next to revision.py; placeholder injected */"
ID_PATTERN = re.compile(r"^(.+)-([a-z]+)-(\d+)$")
BLOCK_REMOVAL_PATTERNS = [
    re.compile(r'<style data-rev="css">.*?</style>\n?', re.S),
    re.compile(r'<script data-rev="snap">.*?</script>\n?', re.S),
    re.compile(r'<script data-rev="js">.*?</script>\n?', re.S),
]
TRAILING_SCRIPT_PATTERN = re.compile(r"<script\b[^>]*>(?:(?!</script>).)*</script>\s*\Z", re.S | re.I)
SNAP_SCRIPT = '<script data-rev="snap">window.__revSnap=document.documentElement.outerHTML;</script>'


class ElementRecord:
    def __init__(self, tag, attrs, parent_index, insert_offset):
        self.tag = tag
        self.attrs = attrs
        self.parent_index = parent_index
        self.insert_offset = insert_offset
        self.has_own_text = False
        self.heading_parts = []

    def class_names(self):
        return set((self.attrs.get("class") or "").split())


class PageScan(HTMLParser):
    """Walks the page once and records every element, its parent and where a new attribute can go."""

    def __init__(self, page_text):
        super().__init__(convert_charrefs=True)
        self.page_text = page_text
        self.line_start_offsets = [0] + [m.end() for m in re.finditer("\n", page_text)]
        self.element_list = []
        self.open_stack = []
        self.text_chunk_list = []
        self.feed(page_text)
        self.close()

    def absolute_offset(self):
        line_number, column = self.getpos()
        return self.line_start_offsets[line_number - 1] + column

    def handle_starttag(self, tag, attrs):
        start_tag_text = self.get_starttag_text()
        tag_end_offset = self.absolute_offset() + len(start_tag_text)
        insert_offset = tag_end_offset - (2 if start_tag_text.endswith("/>") else 1)
        if tag in IMPLIED_END_TAGS:
            self.close_implied(tag)
        parent_index = self.open_stack[-1] if self.open_stack else None
        self.element_list.append(ElementRecord(tag, dict(attrs), parent_index, insert_offset))
        if tag not in VOID_TAGS:
            self.open_stack.append(len(self.element_list) - 1)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID_TAGS:
            self.open_stack.pop()

    def handle_endtag(self, tag):
        if tag in VOID_TAGS:
            return
        for stack_position in range(len(self.open_stack) - 1, -1, -1):
            if self.element_list[self.open_stack[stack_position]].tag == tag:
                del self.open_stack[stack_position:]
                return

    def close_implied(self, tag):
        # ponytail: closes only an open sibling of the same tag under inline tags; full HTML implied-end rules not modelled.
        stack = self.open_stack
        while stack and self.element_list[stack[-1]].tag in INLINE_TAGS:
            stack.pop()
        if tag in ("td", "th"):
            if stack and self.element_list[stack[-1]].tag in ("td", "th"):
                stack.pop()
        elif stack and self.element_list[stack[-1]].tag == tag:
            stack.pop()
        elif tag == "tr" and len(stack) > 1 and self.element_list[stack[-1]].tag in ("td", "th"):
            del stack[-2:]

    def handle_data(self, data):
        current_index = self.open_stack[-1] if self.open_stack else None
        self.text_chunk_list.append((current_index, data))
        if not data.strip():
            return
        owner_index = current_index
        while owner_index is not None and self.element_list[owner_index].tag in INLINE_TAGS:
            owner_index = self.element_list[owner_index].parent_index
        if owner_index is not None:
            self.element_list[owner_index].has_own_text = True
        ancestor_index = current_index
        while ancestor_index is not None:
            if self.element_list[ancestor_index].tag in ("h1", "h2", "h3"):
                self.element_list[ancestor_index].heading_parts.append(data)
            ancestor_index = self.element_list[ancestor_index].parent_index


def ancestor_indexes(scan, element_index):
    parent_index = scan.element_list[element_index].parent_index
    while parent_index is not None:
        yield parent_index
        parent_index = scan.element_list[parent_index].parent_index


def content_text(scan):
    """Body text with script, style, template, head and data-rev-ui nodes removed, whitespace collapsed."""
    kept_parts = []
    for owner_index, data in scan.text_chunk_list:
        if owner_index is not None:
            chain = [owner_index, *ancestor_indexes(scan, owner_index)]
            if any(
                scan.element_list[i].tag in CONTENT_TEXT_SKIPPED_TAGS or "data-rev-ui" in scan.element_list[i].attrs
                for i in chain
            ):
                continue
        kept_parts.append(data)
    return " ".join("".join(kept_parts).split())


def first_difference_offset(text_a, text_b):
    shared_length = min(len(text_a), len(text_b))
    for offset in range(shared_length):
        if text_a[offset] != text_b[offset]:
            return offset
    return None if len(text_a) == len(text_b) else shared_length


def read_page(path):
    with open(path, encoding="utf-8", newline="") as page_file:
        return page_file.read()


def matches_rule(element, parent, spec):
    tag = element.tag
    class_names = element.class_names()
    if tag in spec.get("tags", ()) or class_names & spec.get("classes", set()):
        return True
    if any(tag == rule_tag and rule_class in class_names for rule_tag, rule_class in spec.get("tag_classes", ())):
        return True
    if any(tag == rule_tag and rule_class not in class_names for rule_tag, rule_class in spec.get("tags_without_class", ())):
        return True
    if parent is not None and any(
        tag == rule_tag and rule_class in parent.class_names() for rule_tag, rule_class in spec.get("parent_class_tags", ())
    ):
        return True
    if (element.attrs.get("role") or "") in spec.get("roles", ()):
        return True
    return tag == "input" and (element.attrs.get("type") or "") in spec.get("input_types", ())


def is_small_svg(element):
    width_text = (element.attrs.get("width") or "").strip()
    return element.tag == "svg" and width_text.isdigit() and int(width_text) < SMALL_SVG_PIXELS


def is_ui_or_hidden(element):
    class_names = element.class_names()
    return (
        "data-rev-ui" in element.attrs
        or "hidden" in element.attrs
        or "display:none" in (element.attrs.get("style") or "").replace(" ", "").lower()
        or bool(class_names & UI_CLASS_NAMES)
        or any(name.startswith(UI_CLASS_PREFIXES) for name in class_names)
    )


def kind_of(scan, element_index):
    element = scan.element_list[element_index]
    parent = scan.element_list[element.parent_index] if element.parent_index is not None else None
    if is_ui_or_hidden(element) or element.tag in CLOSED_SUBTREE_TAGS - {"svg", "canvas", "picture"}:
        return None
    if element.tag in INLINE_TAGS and not matches_rule(element, parent, KIND_SPEC_BY_NAME["btn"]):
        return None
    under_tags = {scan.element_list[i].tag for i in ancestor_indexes(scan, element_index)}
    for kind, spec in KIND_TABLE:
        if not matches_rule(element, parent, spec):
            continue
        if under_tags & spec.get("not_under", set()):
            return None
        if kind == "dia" and is_small_svg(element):
            return None
        return kind
    if element.has_own_text and element.tag not in NON_TEXT_BLOCK_TAGS and "-" not in element.tag:
        return "p"
    return None


def slugify(heading_text):
    slug = re.sub(r"[^a-z0-9]+", "-", heading_text.lower()).strip("-")[:MAX_SLUG_LENGTH].strip("-")
    return slug


def plan_ids(scan, carry_records=()):
    """Returns ({element_index: new data-rev-id}, retired v1 ids) for each meaningful element that has none yet."""
    taken_ids = {e.attrs["data-rev-id"] for e in scan.element_list if e.attrs.get("data-rev-id")}
    taken_ids.update(record.rev_id for record in carry_records)
    highest_number = {}
    for taken_id in taken_ids:
        id_match = ID_PATTERN.match(taken_id)
        if id_match:
            key = (id_match.group(1), id_match.group(2))
            highest_number[key] = max(highest_number.get(key, 0), int(id_match.group(3)))
    closed_indexes = set()
    heading_slug_counts = {}
    current_heading_slug = None
    candidate_list = []
    for element_index, element in enumerate(scan.element_list):
        if element.parent_index in closed_indexes:
            closed_indexes.add(element_index)
            continue
        if element.tag in ("h1", "h2", "h3"):
            base_slug = slugify(" ".join("".join(element.heading_parts).split()))
            if base_slug:
                repeat_count = heading_slug_counts.get(base_slug, 0) + 1
                heading_slug_counts[base_slug] = repeat_count
                current_heading_slug = base_slug if repeat_count == 1 else "%s-%d" % (base_slug, repeat_count)
        kind = kind_of(scan, element_index)
        if element.tag in CLOSED_SUBTREE_TAGS or "-" in element.tag or kind in CLOSED_SUBTREE_KINDS or is_ui_or_hidden(element):
            closed_indexes.add(element_index)
        if kind in FIGURE_SUPPRESSED_KINDS and any(
            matches_rule(scan.element_list[i], None, KIND_SPEC_BY_NAME["fig"]) for i in ancestor_indexes(scan, element_index)
        ):
            kind = None
        if kind is None or element.attrs.get("data-rev-id"):
            continue
        section = section_of(scan, element_index) or current_heading_slug or FALLBACK_SECTION
        candidate_list.append(Candidate(element_index, section, kind))
    new_id_by_index, retired_ids = carry_ids(scan, candidate_list, carry_records)
    for candidate in candidate_list:
        if candidate.element_index in new_id_by_index:
            continue
        key = (candidate.section, candidate.kind)
        next_number = highest_number.get(key, 0) + 1
        highest_number[key] = next_number
        new_id_by_index[candidate.element_index] = "%s-%s-%d" % (candidate.section, candidate.kind, next_number)
    return new_id_by_index, retired_ids


def element_text_map(scan):
    """Returns {element_index: normalized content text} using the same exclusions as content_text."""
    part_lists = {}
    for owner_index, data in scan.text_chunk_list:
        if owner_index is None:
            continue
        chain = [owner_index, *ancestor_indexes(scan, owner_index)]
        if any(
            scan.element_list[i].tag in CONTENT_TEXT_SKIPPED_TAGS or "data-rev-ui" in scan.element_list[i].attrs
            for i in chain
        ):
            continue
        for chain_index in chain:
            part_lists.setdefault(chain_index, []).append(data)
    return {index: " ".join("".join(parts).split()) for index, parts in part_lists.items()}


def id_records_of(scan):
    """Returns an IdRecord for each element that already carries a well-formed data-rev-id, in document order."""
    text_by_index = element_text_map(scan)
    record_list = []
    for element_index, element in enumerate(scan.element_list):
        rev_id = element.attrs.get("data-rev-id") or ""
        id_match = ID_PATTERN.match(rev_id)
        if id_match:
            record_list.append(IdRecord(rev_id, id_match.group(1), id_match.group(2), text_by_index.get(element_index, "")))
    return record_list


def carry_ids(scan, candidate_list, carry_records):
    """Pairs v2 candidates with v1 records per section (design D6). Returns ({index: v1 id}, retired v1 ids)."""
    if not carry_records:
        return {}, []
    text_by_index = element_text_map(scan)
    carried_id_by_index = {}
    paired_ids = set()
    for section in dict.fromkeys(record.section for record in carry_records):
        old_list = [record for record in carry_records if record.section == section]
        new_list = [candidate for candidate in candidate_list if candidate.section == section]
        old_keys = [(record.kind, record.text) for record in old_list]
        new_keys = [(candidate.kind, text_by_index.get(candidate.element_index, "")) for candidate in new_list]
        opcode_list = SequenceMatcher(None, old_keys, new_keys, autojunk=False).get_opcodes()
        for opcode, old_start, old_end, new_start, new_end in opcode_list:
            if opcode not in ("equal", "replace"):
                continue
            old_block = old_list[old_start:old_end]
            new_block = new_list[new_start:new_end]
            for old_record, new_candidate, new_key in zip(old_block, new_block, new_keys[new_start:new_end]):
                same_kind = old_record.kind == new_candidate.kind
                similarity = SequenceMatcher(None, old_record.text, new_key[1]).ratio()
                if opcode == "equal" or (same_kind and similarity >= CARRY_MIN_TEXT_SIMILARITY):
                    carried_id_by_index[new_candidate.element_index] = old_record.rev_id
                    paired_ids.add(old_record.rev_id)
    retired_ids = [record.rev_id for record in carry_records if record.rev_id not in paired_ids]
    return carried_id_by_index, retired_ids


def section_of(scan, element_index):
    for ancestor_index in ancestor_indexes(scan, element_index):
        ancestor = scan.element_list[ancestor_index]
        class_names = ancestor.class_names()
        is_section = (
            (ancestor.tag == "section" and ancestor.attrs.get("id"))
            or (ancestor.tag == "details" and "lvl" in class_names and ancestor.attrs.get("id"))
            or "data-sec" in ancestor.attrs
            or "sec" in class_names
        )
        if is_section:
            section_name = slugify(ancestor.attrs.get("id") or ancestor.attrs.get("data-sec") or "")
            if section_name:
                return section_name
    return None


def set_html_attribute(page_text, name, value, overwrite):
    html_tag_match = re.search(r"<html\b[^>]*>", page_text, re.I)
    if not html_tag_match:
        return page_text
    html_tag = html_tag_match.group(0)
    attribute_match = re.search(r'\s%s="[^"]*"' % re.escape(name), html_tag)
    if attribute_match and not overwrite:
        return page_text
    if attribute_match:
        new_tag = html_tag[: attribute_match.start()] + ' %s="%s"' % (name, value) + html_tag[attribute_match.end():]
    else:
        new_tag = html_tag[:-1] + ' %s="%s">' % (name, value)
    return page_text[: html_tag_match.start()] + new_tag + page_text[html_tag_match.end():]


def runtime_blocks():
    notes = []
    css_file = REVISION_DIR / "revision.css"
    js_file = REVISION_DIR / "revision.js"
    css_text = css_file.read_text(encoding="utf-8") if css_file.exists() else DEFAULT_CSS_PLACEHOLDER
    js_text = js_file.read_text(encoding="utf-8") if js_file.exists() else DEFAULT_JS_PLACEHOLDER
    if not css_file.exists():
        notes.append("note: revision.css not found, placeholder injected")
    if not js_file.exists():
        notes.append("note: revision.js not found, placeholder injected")
    css_block = '<style data-rev="css">\n%s\n</style>\n' % css_text.rstrip("\n")
    safe_js = re.sub(r"</(script)", r"<\\/\1", js_text.rstrip("\n"), flags=re.I)
    js_block = '<script data-rev="js">\n%s\n</script>\n' % safe_js
    return css_block, SNAP_SCRIPT + "\n", js_block, notes


def insert_blocks(page_text):
    css_block, snap_block, js_block, notes = runtime_blocks()
    head_close = re.search(r"</head\s*>", page_text, re.I)
    body_open = re.search(r"<body\b", page_text, re.I)
    css_at = head_close.start() if head_close else (body_open.start() if body_open else 0)
    page_text = page_text[:css_at] + css_block + page_text[css_at:]
    body_closers = list(re.finditer(r"</body\s*>", page_text, re.I))
    body_close_at = body_closers[-1].start() if body_closers else len(page_text)
    snap_at = body_close_at
    tail_text = page_text[:body_close_at]
    while True:
        trailing_match = TRAILING_SCRIPT_PATTERN.search(tail_text)
        if not trailing_match:
            break
        snap_at = trailing_match.start()
        tail_text = tail_text[:snap_at]
    page_text = page_text[:body_close_at] + js_block + page_text[body_close_at:]
    page_text = page_text[:snap_at] + snap_block + page_text[snap_at:]
    return page_text, notes


def inject_page(source_path, default_mode, source_name, carry_path=None):
    original_text = read_page(source_path)
    clean_text = original_text
    for removal_pattern in BLOCK_REMOVAL_PATTERNS:
        clean_text = removal_pattern.sub("", clean_text)
    scan = PageScan(clean_text)
    carry_records = id_records_of(PageScan(read_page(carry_path))) if carry_path else []
    new_id_by_index, retired_ids = plan_ids(scan, carry_records)
    stamped_text = clean_text
    for element_index in sorted(new_id_by_index, key=lambda i: scan.element_list[i].insert_offset, reverse=True):
        offset = scan.element_list[element_index].insert_offset
        stamped_text = stamped_text[:offset] + ' data-rev-id="%s"' % new_id_by_index[element_index] + stamped_text[offset:]
    stem = re.sub(r"[^A-Za-z0-9_-]+", "-", Path(source_path).stem).strip("-") or "page"
    doc_hash = hashlib.sha256(content_text(scan).encode("utf-8")).hexdigest()[:8]
    stamped_text = set_html_attribute(stamped_text, "data-rev-doc", "%s-%s" % (stem, doc_hash), False)
    stamped_text = set_html_attribute(stamped_text, "data-rev-default", default_mode or "on", default_mode is not None)
    stamped_text = set_html_attribute(
        stamped_text, "data-rev-source", source_name or Path(source_path).name, source_name is not None
    )
    injected_text, notes = insert_blocks(stamped_text)
    return original_text, injected_text, len(new_id_by_index), notes, retired_ids


def compare_content_text(text_a, text_b):
    return first_difference_offset(content_text(PageScan(text_a)), content_text(PageScan(text_b)))


def command_inject(args):
    source_path = Path(args.input).resolve()
    out_path = Path(args.out).resolve()
    if source_path == out_path:
        print("INJECT FAIL: --out must differ from the input file")
        return 2
    carry_path = Path(args.carry_ids_from).resolve() if args.carry_ids_from else None
    original_text, injected_text, added_count, notes, retired_ids = inject_page(source_path, args.default, args.source, carry_path)
    difference_offset = compare_content_text(original_text, injected_text)
    if difference_offset is not None:
        print("TEXT DIFF: %d" % difference_offset)
        return 1
    with open(out_path, "w", encoding="utf-8", newline="") as out_file:
        out_file.write(injected_text)
    for note in notes:
        print(note)
    if retired_ids:
        print("rev-retired: " + ", ".join(retired_ids))
    print("INJECT OK: %d ids added, wrote %s" % (added_count, out_path.name))
    print("TEXT SAME")
    return 0


def command_textcheck(args):
    difference_offset = compare_content_text(read_page(args.first), read_page(args.second))
    if difference_offset is None:
        print("TEXT SAME")
        return 0
    print("TEXT DIFF: %d" % difference_offset)
    return 1


def annotation_problem(page, numbered_item_list):
    if page.get("@context") != ANNOTATION_CONTEXT:
        return "@context must be " + ANNOTATION_CONTEXT
    if page.get("type") != "AnnotationPage":
        return "type must be AnnotationPage"
    if not isinstance(page.get("items"), list):
        return "items must be a list"
    seen_ids = set()
    for position, item in numbered_item_list:
        label = "item %d" % position
        if not isinstance(item, dict) or item.get("type") != "Annotation":
            return label + " type must be Annotation"
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id:
            return label + " has no id"
        if item_id in seen_ids:
            return label + " repeats id " + item_id
        seen_ids.add(item_id)
        body = item.get("body")
        if not isinstance(body, dict) or not isinstance(body.get("value"), str) or not body["value"].strip():
            return label + " has no body value"
        target = item.get("target")
        selector_list = target.get("selector") if isinstance(target, dict) else None
        selector_by_type = {s.get("type"): s for s in selector_list or [] if isinstance(s, dict)}
        css_selector = selector_by_type.get("CssSelector")
        quote_selector = selector_by_type.get("TextQuoteSelector")
        if not css_selector or not CSS_SELECTOR_ID_PATTERN.match(str(css_selector.get("value"))):
            return label + " has no usable CssSelector"
        if not quote_selector or not isinstance(quote_selector.get("exact"), str) or not quote_selector["exact"]:
            return label + " has no TextQuoteSelector exact"
    return None


def annotations_block_text(scan):
    for element_index, element in enumerate(scan.element_list):
        if element.tag == "script" and element.attrs.get("id") == ANNOTATIONS_SCRIPT_ID:
            return "".join(data for owner_index, data in scan.text_chunk_list if owner_index == element_index)
    return None


def resolve_pin(quote_selector, target_id, id_set, page_text):
    """Returns id, quote or none: the id first, then quote with prefix and suffix, then a unique quote."""
    if target_id in id_set:
        return "id"
    exact = quote_selector["exact"]
    prefix = quote_selector.get("prefix") or ""
    suffix = quote_selector.get("suffix") or ""
    occurrence_list = []
    search_from = page_text.find(exact)
    while search_from != -1:
        occurrence_list.append(search_from)
        search_from = page_text.find(exact, search_from + 1)
    if prefix or suffix:
        for occurrence in occurrence_list:
            if page_text[:occurrence].endswith(prefix) and page_text[occurrence + len(exact):].startswith(suffix):
                return "quote"
    return "quote" if len(occurrence_list) == 1 else "none"


def command_extract(args):
    scan = PageScan(read_page(Path(args.saved).resolve()))
    block_text = annotations_block_text(scan)
    if block_text is None:
        print("ANNOTATIONS INVALID: no script#%s block" % ANNOTATIONS_SCRIPT_ID)
        return 1
    try:
        annotation_page = json.loads(block_text)
    except json.JSONDecodeError as problem:
        print("ANNOTATIONS INVALID: block is not JSON (%s)" % problem)
        return 1
    if not isinstance(annotation_page, dict):
        print("ANNOTATIONS INVALID: block must be a JSON object")
        return 1
    item_list = annotation_page.get("items") if isinstance(annotation_page.get("items"), list) else []
    problem_text = annotation_problem(annotation_page, list(enumerate(item_list, 1)))
    if problem_text:
        print("ANNOTATIONS INVALID: " + problem_text)
        return 1
    id_set = {e.attrs["data-rev-id"] for e in scan.element_list if e.attrs.get("data-rev-id")}
    page_text = content_text(scan)
    ledger_rows = []
    for item in item_list:
        selector_by_type = {s["type"]: s for s in item["target"]["selector"] if isinstance(s, dict) and "type" in s}
        target_id = CSS_SELECTOR_ID_PATTERN.match(selector_by_type["CssSelector"]["value"]).group(1)
        quote_selector = selector_by_type["TextQuoteSelector"]
        ledger_rows.append({
            "id": item["id"],
            "target": target_id,
            "kind": item.get("rev:kind", ""),
            "section": item.get("rev:section", ""),
            "quote": quote_selector["exact"],
            "comment": item["body"]["value"],
            "intent": item.get("rev:intent", ""),
            "resolved": resolve_pin(quote_selector, target_id, id_set, page_text),
        })
    if args.out:  # without --out, extract only validates the block
        with open(Path(args.out).resolve(), "w", encoding="utf-8", newline="") as ledger_file:
            json.dump(ledger_rows, ledger_file, indent=2, ensure_ascii=False)
            ledger_file.write("\n")
        Path(args.out + PINS_IN_SUFFIX).write_text(str(len(ledger_rows)) + "\n", encoding="ascii")
    print("ANNOTATIONS VALID: %d" % len(ledger_rows))
    return 0


def command_report(args):
    ledger_path = Path(args.ledger).resolve()
    try:
        ledger_rows = json.loads(ledger_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as problem:
        print("REVISE REPORT FAIL: ledger is not JSON (%s)" % problem)
        return 1
    if not isinstance(ledger_rows, list):
        print("REVISE REPORT FAIL: ledger must be a list of rows")
        return 1
    pins_in_path = Path(str(ledger_path) + PINS_IN_SUFFIX)
    if pins_in_path.is_file():
        pins_in_count = pins_in_path.read_text(encoding="ascii").strip()
        if pins_in_count != str(len(ledger_rows)):
            print("REVISE REPORT FAIL: extract found %s pins but the ledger has %d rows" % (pins_in_count, len(ledger_rows)))
            return 1
    seen_pin_ids = set()
    for position, row in enumerate(ledger_rows, 1):
        if not isinstance(row, dict) or not row.get("id") or not row.get("target"):
            print("REVISE REPORT FAIL: row %d has no id or target" % position)
            return 1
        if row["id"] in seen_pin_ids:
            print("REVISE REPORT FAIL: pin id %s appears twice" % row["id"])
            return 1
        seen_pin_ids.add(row["id"])
        if row.get("verdict") not in VERDICTS:
            print("REVISE REPORT FAIL: pin %s has no verdict of done, kept or orphaned" % row["id"])
            return 1
    v2_scan = PageScan(read_page(Path(args.v2).resolve()))
    v2_ids = {e.attrs["data-rev-id"] for e in v2_scan.element_list if e.attrs.get("data-rev-id")}
    ledger_changed = False
    for row in ledger_rows:
        if row["verdict"] != "orphaned" and row["target"] not in v2_ids:
            print("orphaned: target %s of pin %s is missing in v2 (was %s)" % (row["target"], row["id"], row["verdict"]))
            row["verdict"] = "orphaned"
            ledger_changed = True
    if ledger_changed:
        reported_path = Path(str(ledger_path) + REPORTED_SUFFIX)
        reported_path.write_text(json.dumps(ledger_rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="")
        print("orphaned verdicts written to %s; the input ledger is unchanged" % reported_path)
    else:
        Path(str(ledger_path) + REPORTED_SUFFIX).unlink(missing_ok=True)   # a stale file from an earlier run must not survive
    count_by_verdict = {verdict: sum(1 for row in ledger_rows if row["verdict"] == verdict) for verdict in VERDICTS}
    print("REVISE REPORT OK: %d pins = %d done, %d kept, %d orphaned" % (
        len(ledger_rows), count_by_verdict["done"], count_by_verdict["kept"], count_by_verdict["orphaned"]))
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description="Revision mode page tool")
    subcommands = parser.add_subparsers(dest="command", required=True)
    inject_parser = subcommands.add_parser("inject", help="stamp ids and add the revision blocks")
    inject_parser.add_argument("input")
    inject_parser.add_argument("--out", required=True)
    inject_parser.add_argument("--default", choices=["on", "off"])
    inject_parser.add_argument("--source")
    inject_parser.add_argument("--carry-ids-from")
    inject_parser.set_defaults(handler=command_inject)
    textcheck_parser = subcommands.add_parser("textcheck", help="compare the content text of two pages")
    textcheck_parser.add_argument("first")
    textcheck_parser.add_argument("second")
    textcheck_parser.set_defaults(handler=command_textcheck)
    extract_parser = subcommands.add_parser("extract", help="validate saved annotations and write the pin ledger")
    extract_parser.add_argument("saved")
    extract_parser.add_argument("--out", help="ledger JSON path; omit to validate only")
    extract_parser.set_defaults(handler=command_extract)
    report_parser = subcommands.add_parser("report", help="check a ledger against the v2 page")
    report_parser.add_argument("ledger")
    report_parser.add_argument("v2")
    report_parser.set_defaults(handler=command_report)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.handler(args)
    except (OSError, UnicodeDecodeError) as problem:
        print("%s FAIL: %s" % (args.command.upper(), problem))
        return 2


if __name__ == "__main__":
    sys.exit(main())
