/* Revision mode runtime: one IIFE, no dependency. Core: toolbar, theme, ids, storage, event bus.
   Sections below: keyboard, placement, pins, panel, export (all attach to window.__rev). Never touches .sc-* / .nw-* or their storage keys. */
(function () {
  "use strict";
  if (window.__rev) return;
  var doc = document, root = doc.documentElement;
  var STORE_PREFIX = "rev:1:", WRITE_DELAY_MS = 300, MAX_SLUG = 32, SMALL_SVG = 48, NARROW_PX = 900;

  /* ---------- kind table (same rules as revision.py KIND_TABLE, tag rules only) ---------- */
  var INLINE = "span a em strong b i u code small sub sup mark kbd abbr label time br".split(" ");
  var NON_TEXT_BLOCK = ("html head body title meta link base noscript caption thead tbody tfoot tr td th colgroup col ul ol dl " +
    "select option optgroup textarea summary script style template section article main").split(" ");
  var CLOSED_TAGS = "script style template nav head svg canvas noscript select textarea picture".split(" ");
  var CLOSED_KINDS = ["h", "btn", "code", "img", "dia"];
  var KINDS = [
    ["fig", { tags: ["figure"], classes: ["fig"] }],
    ["tbl", { tags: ["table"] }],
    ["row", { tags: ["tr"], notUnder: ["thead", "tfoot"] }],
    ["code", { tags: ["pre"] }],
    ["dia", { tags: ["canvas", "doc-flow", "svg"], classes: ["mermaid"] }],
    ["img", { tags: ["img", "picture"] }],
    ["btn", { tags: ["button"], tagClasses: [["a", "btn"]], roles: ["button"], inputTypes: ["button", "submit"] }],
    ["box", { tags: ["aside", "doc-note", "doc-ask", "doc-claim", "doc-pin"], classes: ["callout", "say", "why", "why2"], tagClasses: [["div", "note"], ["div", "analogy"]], tagsWithoutClass: [["details", "lvl"]] }],
    ["h", { tags: ["h1", "h2", "h3", "h4", "h5", "h6"], parentClassTags: [["summary", "lvl"]] }],
    ["li", { tags: ["li"] }],
    ["def", { tags: ["dt", "dd"] }],
    ["p", { tags: ["p", "blockquote"] }]
  ];
  var KIND_SPEC = {};
  KINDS.forEach(function (k) { KIND_SPEC[k[0]] = k[1]; });

  function has(list, v) { return list.indexOf(v) >= 0; }
  function tagOf(el) { return el.localName; }
  function classesOf(el) { return (el.getAttribute("class") || "").split(/\s+/).filter(Boolean); }
  function anyClass(el, names) { var c = classesOf(el); return (names || []).some(function (n) { return has(c, n); }); }

  function matchesRule(el, parent, spec) {
    var tag = tagOf(el), classes = classesOf(el), i, r;
    if (has(spec.tags || [], tag) || (spec.classes || []).some(function (n) { return has(classes, n); })) return true;
    for (i = 0, r = spec.tagClasses || []; i < r.length; i++) if (tag === r[i][0] && has(classes, r[i][1])) return true;
    for (i = 0, r = spec.tagsWithoutClass || []; i < r.length; i++) if (tag === r[i][0] && !has(classes, r[i][1])) return true;
    if (parent) for (i = 0, r = spec.parentClassTags || []; i < r.length; i++) if (tag === r[i][0] && anyClass(parent, [r[i][1]])) return true;
    if (has(spec.roles || [], el.getAttribute("role") || "")) return true;
    return tag === "input" && has(spec.inputTypes || [], el.getAttribute("type") || "");
  }

  function isUiOrHidden(el) {
    var style = (el.getAttribute("style") || "").replace(/\s+/g, "").toLowerCase();
    return el.hasAttribute("data-rev-ui") || el.hasAttribute("hidden") || style.indexOf("display:none") >= 0 ||
      anyClass(el, ["bar", "nw-bar"]) || classesOf(el).some(function (n) { return n.indexOf("sc-") === 0 || n.indexOf("nw-") === 0; });
  }

  // True when a non-blank text node belongs to el directly or through inline children.
  function hasOwnText(el) {
    for (var n = el.firstChild; n; n = n.nextSibling) {
      if (n.nodeType === 3 && n.nodeValue.trim()) return true;
      if (n.nodeType === 1 && has(INLINE, tagOf(n)) && hasOwnText(n)) return true;
    }
    return false;
  }

  // Kind code of one element, or null. Does not apply the closed-subtree or figure rules (see stampIds).
  function kindOf(el) {
    var tag = tagOf(el), parent = el.parentElement;
    if (isUiOrHidden(el) || (has(CLOSED_TAGS, tag) && !has(["svg", "canvas", "picture"], tag))) return null;
    if (has(INLINE, tag) && !matchesRule(el, parent, KIND_SPEC.btn)) return null;
    for (var i = 0; i < KINDS.length; i++) {
      var kind = KINDS[i][0], spec = KINDS[i][1];
      if (!matchesRule(el, parent, spec)) continue;
      if (spec.notUnder) for (var a = parent; a; a = a.parentElement) if (has(spec.notUnder, tagOf(a))) return null;
      if (kind === "dia" && tag === "svg" && /^\d+$/.test((el.getAttribute("width") || "").trim()) && parseInt(el.getAttribute("width"), 10) < SMALL_SVG) return null;
      return kind;
    }
    if (hasOwnText(el) && !has(NON_TEXT_BLOCK, tag) && tag.indexOf("-") < 0) return "p";
    return null;
  }

  function slugify(text) {
    return text.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, MAX_SLUG).replace(/^-+|-+$/g, "");
  }
  function sectionOf(el) {
    for (var a = el.parentElement; a; a = a.parentElement) {
      var tag = tagOf(a);
      var isSec = (tag === "section" && a.getAttribute("id")) || (tag === "details" && anyClass(a, ["lvl"]) && a.getAttribute("id")) ||
        a.hasAttribute("data-sec") || anyClass(a, ["sec"]);
      if (isSec) { var s = slugify(a.getAttribute("id") || a.getAttribute("data-sec") || ""); if (s) return s; }
    }
    return null;
  }

  // Stamps data-rev-id on every meaningful element that has none, with the same rules as revision.py plan_ids.
  function stampIds() {
    var highest = {}, headingCounts = {}, currentHeading = null, stamped = 0;
    var ID_RE = /^(.+)-([a-z]+)-(\d+)$/;
    [].forEach.call(doc.querySelectorAll("[data-rev-id]"), function (e) {
      var m = ID_RE.exec(e.getAttribute("data-rev-id"));
      if (m) { var key = m[1] + "\n" + m[2]; highest[key] = Math.max(highest[key] || 0, parseInt(m[3], 10)); }
    });
    function walk(el) {
      var tag = tagOf(el);
      if (/^h[123]$/.test(tag)) {
        var base = slugify((el.textContent || "").split(/\s+/).filter(Boolean).join(" "));
        if (base) {
          headingCounts[base] = (headingCounts[base] || 0) + 1;
          currentHeading = headingCounts[base] === 1 ? base : base + "-" + headingCounts[base];
        }
      }
      var kind = kindOf(el);
      var closed = has(CLOSED_TAGS, tag) || tag.indexOf("-") >= 0 || has(CLOSED_KINDS, kind) || isUiOrHidden(el);
      if ((kind === "img" || kind === "dia")) {
        for (var a = el.parentElement; a; a = a.parentElement) if (matchesRule(a, null, KIND_SPEC.fig)) { kind = null; break; }
      }
      if (kind && !el.hasAttribute("data-rev-id")) {
        var section = sectionOf(el) || currentHeading || "s1", key = section + "\n" + kind;
        highest[key] = (highest[key] || 0) + 1;
        el.setAttribute("data-rev-id", section + "-" + kind + "-" + highest[key]);
        stamped++;
      }
      if (closed) return;
      for (var c = el.firstElementChild; c; c = c.nextElementSibling) walk(c);
    }
    walk(root);
    return stamped;
  }

  /* ---------- event bus ---------- */
  var rev = window.__rev = {
    kindOf: kindOf, hasOwnText: hasOwnText, matchesRule: matchesRule, stampIds: stampIds, KIND_SPEC: KIND_SPEC,
    emit: function (name, detail) { doc.dispatchEvent(new CustomEvent("rev:" + name, { detail: detail })); },
    on: function (name, fn) { doc.addEventListener("rev:" + name, fn); },
    state: null, ui: {}
  };

  /* ---------- storage: rev:1:<docId>, 300 ms write, memory fallback ---------- */
  var docId = root.getAttribute("data-rev-doc") || ("page-" + (location.pathname.split("/").pop() || "index"));
  var storeKey = STORE_PREFIX + docId, memoryOnly = false, writeTimer = 0;
  var defaultMode = root.getAttribute("data-rev-default") === "on" ? "on" : "off";

  function loadState() {
    var s = null;
    try { s = JSON.parse(localStorage.getItem(storeKey) || "null"); } catch (e) { memoryOnly = true; }
    if (!s || typeof s !== "object" || s.v !== 1) s = { v: 1, mode: defaultMode, armed: false, panel: false, pins: [] };
    if (s.mode !== "on" && s.mode !== "off") s.mode = defaultMode;
    if (!Array.isArray(s.pins)) s.pins = [];
    // merge pins from a saved copy's embedded annotations by id; the newer "modified" wins
    if (!Array.isArray(s.deleted)) s.deleted = [];
    if (!s.keep || typeof s.keep !== "object") s.keep = {};
    embeddedPins().forEach(function (e) {
      if (s.deleted.indexOf(e.id) >= 0) return;   // the user deleted this embedded pin earlier
      var wasKept = e.keepOpen; delete e.keepOpen;
      for (var i = 0; i < s.pins.length; i++) if (s.pins[i].id === e.id) { if ((e.modified || "") > (s.pins[i].modified || "")) { s.pins[i] = e; if (wasKept) s.keep[e.id] = true; else delete s.keep[e.id]; } return; }
      s.pins.push(e);
      if (wasKept) s.keep[e.id] = true;   // a saved copy remembers which post-its were Keep open
    });
    // saved post-its load folded to their pins unless the user marked them Keep open
    s.pins = s.pins.filter(function (p) { return p.state !== "editing" || (p.text || "").trim(); });   // an untouched draft is not kept
    s.pins.forEach(function (p) { if ((p.state === "open" || p.state === "editing") && !s.keep[p.id]) p.state = "hidden"; });
    return s;
  }
  function embeddedPins() {
    var tag = doc.getElementById("rev-annotations"), page;
    try { page = JSON.parse(tag ? tag.textContent : "null"); } catch (e) { return []; }
    return (page && Array.isArray(page.items) ? page.items : []).map(function (a) {
      var sel = {}; ((a.target || {}).selector || []).forEach(function (x) { sel[x.type] = x; });
      var m = /data-rev-id="([^"]+)"/.exec((sel.CssSelector || {}).value || ""), q = sel.TextQuoteSelector || {};
      return { id: a.id, target: m ? m[1] : "", kind: a["rev:kind"] || "", section: a["rev:section"] || "", intent: a["rev:intent"] || "",
        text: (a.body || {}).value || "", keepOpen: a["rev:keep"] === true, state: a["rev:state"] || "hidden", status: a["rev:status"] || "new", created: a.created, modified: a.modified,
        quote: { exact: q.exact || "", prefix: q.prefix || "", suffix: q.suffix || "" } };
    }).filter(function (p) { return p.id && p.target; });
  }
  function writeNow() {
    writeTimer = 0;
    if (memoryOnly) return;
    try { rev.state.keep = keep; localStorage.setItem(storeKey, JSON.stringify(rev.state)); }
    catch (e) { memoryOnly = true; rev.toast("Pins are not saved in this browser - use Save revisions"); }
  }
  rev.save = function () { if (writeTimer) clearTimeout(writeTimer); writeTimer = setTimeout(writeNow, WRITE_DELAY_MS); rev.emit("changed", {}); };
  rev.flush = function () { if (writeTimer) { clearTimeout(writeTimer); writeNow(); } };
  rev.memoryOnly = function () { return memoryOnly; };
  rev.docId = docId;
  window.addEventListener("pagehide", rev.flush);

  /* ---------- toast ---------- */
  var toastTimer = 0;
  rev.toast = function (text, actionLabel, onAction, ms) {
    var t = rev.ui.toast;
    if (!t) return;
    t.textContent = "";
    var span = doc.createElement("span"); span.textContent = text; t.appendChild(span);
    if (actionLabel) {
      var b = doc.createElement("button"); b.type = "button"; b.textContent = actionLabel;
      b.addEventListener("click", function () { t.removeAttribute("data-on"); if (onAction) onAction(); });
      t.appendChild(b);
    }
    t.setAttribute("data-on", "");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { t.removeAttribute("data-on"); }, ms || 4000);
  };

  /* ---------- theme: data-rev-theme, Day/Night proxy ---------- */
  function luminanceNight() {
    var els = [doc.body, root];
    for (var i = 0; i < els.length; i++) {
      var m = /rgba?\(([^)]+)\)/.exec(getComputedStyle(els[i]).backgroundColor || "");
      if (!m) continue;
      var p = m[1].split(",").map(function (x) { return parseFloat(x); });
      if (p.length > 3 && p[3] === 0) continue;
      return (0.2126 * p[0] + 0.7152 * p[1] + 0.0722 * p[2]) < 128;
    }
    return !!(window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches && root.getAttribute("data-theme") !== "light");
  }
  function currentTheme() {
    var t = (root.getAttribute("data-theme") || "").toLowerCase();
    if (t === "dark" || t === "night") return "night";
    if (t === "light" || t === "day") return "day";
    if (root.classList.contains("night") || (doc.body && doc.body.classList.contains("night"))) return "night";
    return luminanceNight() ? "night" : "day";
  }
  function applyTheme() {
    var t = currentTheme();
    if (root.getAttribute("data-rev-theme") !== t) root.setAttribute("data-rev-theme", t);
  }
  function flipTheme() {
    var night = currentTheme() === "night", btn;
    if ((btn = doc.querySelector(".theme-btn"))) btn.click();
    else if (doc.querySelector("[data-t]")) { (btn = doc.querySelector('[data-t="' + (night ? "light" : "dark") + '"]')) && btn.click(); }
    else if ((btn = doc.getElementById("themebtn"))) btn.click();
    else root.setAttribute("data-theme", night ? "light" : "dark");
    applyTheme();
  }

  /* ---------- toolbar ---------- */
  var ICONS = {
    daynight: '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>',
    toggle: '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="M13 7l4 4"/>',
    pinsource: '<path d="M12 21s-6-5.6-6-10a6 6 0 0 1 12 0c0 4.4-6 10-6 10z"/><circle cx="12" cy="11" r="2"/>',
    click: '<path d="M5 3l6 16 2.5-6.5L20 10z"/>',
    list: '<path d="M8 6h12M8 12h12M8 18h12"/><circle cx="4" cy="6" r="1"/><circle cx="4" cy="12" r="1"/><circle cx="4" cy="18" r="1"/>',
    hideall: '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    save: '<path d="M12 4v11"/><path d="M7 11l5 5 5-5"/><path d="M5 20h14"/>',
    tab: '<path d="M9 5l7 7-7 7"/>'
  };
  var BUTTONS = [
    ["daynight", "Day or Night", false], ["toggle", "Revision mode (R)", false],
    ["pinsource", "Drag a pin onto the page", true], ["click", "Click to pin (C)", true],
    ["list", "Pin list (L)", true], ["hideall", "Hide all post-its", true], ["save", "Save revisions", true]
  ];
  function makeButton(act, label, onlyOn) {
    var b = doc.createElement("button");
    b.type = "button"; b.className = "rev-btn"; b.setAttribute("data-rev-act", act);
    b.setAttribute("aria-label", label);
    if (onlyOn) b.setAttribute("data-rev-only", "on");
    b.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true">' + ICONS[act] + '</svg><span class="rev-tip" role="tooltip"></span>';
    b.lastChild.textContent = label;
    return b;
  }
  function buildUi() {
    var layer = doc.createElement("div"); layer.id = "rev-layer"; layer.setAttribute("data-rev-ui", "");
    layer.style.cssText = "position:absolute;left:0;top:0;width:0;height:0;pointer-events:none";
    var tb = doc.createElement("div"); tb.id = "rev-toolbar"; tb.className = "rev-toolbar"; tb.setAttribute("data-rev-ui", "");
    tb.setAttribute("role", "toolbar"); tb.setAttribute("aria-label", "Revision tools");
    var tab = makeButton("tab", "Open revision tools", false); tab.classList.add("rev-toolbar-tab"); tab.setAttribute("data-rev-act", "tab");
    tb.appendChild(tab);
    BUTTONS.forEach(function (d) { tb.appendChild(makeButton(d[0], d[1], d[2])); });
    var panel = doc.createElement("aside"); panel.id = "rev-panel"; panel.className = "rev-panel"; panel.setAttribute("data-rev-ui", "");
    panel.setAttribute("aria-label", "Pin list");
    var toast = doc.createElement("div"); toast.id = "rev-toast"; toast.className = "rev-toast"; toast.setAttribute("data-rev-ui", "");
    toast.setAttribute("role", "status");
    [layer, tb, panel, toast].forEach(function (n) { doc.body.appendChild(n); });
    rev.ui = { layer: layer, toolbar: tb, panel: panel, toast: toast };
    tb.addEventListener("click", function (e) {
      var b = e.target.closest("[data-rev-act]");
      if (!b) return;
      var act = b.getAttribute("data-rev-act");
      if (act === "tab") { if (tb.hasAttribute("data-collapsed")) tb.removeAttribute("data-collapsed"); else tb.setAttribute("data-collapsed", ""); }
      else if (act === "daynight") flipTheme();
      else if (act === "toggle") rev.setMode(rev.state.mode === "on" ? "off" : "on");
      else rev.emit("action", { act: act, button: b });
    });
  }

  rev.setMode = function (mode) {
    rev.state.mode = mode;
    root.setAttribute("data-rev-mode", mode);
    var on = mode === "on";
    [].forEach.call(rev.ui.toolbar.querySelectorAll("[data-rev-only]"), function (b) { b.style.display = on ? "" : "none"; });
    var t = rev.ui.toolbar.querySelector('[data-rev-act="toggle"]');
    t.setAttribute("aria-pressed", on ? "true" : "false");
    rev.save();
    rev.emit("mode", { mode: mode });
  };

  /* Moves the toolbar when a fixed or sticky page element sits under it (design D4). */
  function probeCollision() {
    var tb = rev.ui.toolbar, spots = ["", "66%", "bottom"], hit;
    function collides() {
      var r = tb.getBoundingClientRect();
      var pts = [[r.left + 4, r.top + 4], [r.right - 4, r.top + 4], [r.left + r.width / 2, r.top + r.height / 2], [r.left + 4, r.bottom - 4], [r.right - 4, r.bottom - 4]];
      return pts.some(function (p) {
        return doc.elementsFromPoint(p[0], p[1]).some(function (el) {
          if (el === root || el === doc.body || tb.contains(el) || el.closest("[data-rev-ui]")) return false;
          for (var a = el; a && a !== doc.body; a = a.parentElement) { var pos = getComputedStyle(a).position; if (pos === "fixed" || pos === "sticky") return true; }
          return false;
        });
      });
    }
    for (var i = 0; i < spots.length; i++) {
      if (i === 1) { tb.style.top = spots[1]; }
      else if (i === 2) {
        var nw = doc.querySelector(".nw-bar"), lift = nw ? nw.getBoundingClientRect().height + 8 : 8;
        tb.style.top = "auto"; tb.style.transform = "none"; tb.style.bottom = lift + "px";
      }
      if (!(hit = collides())) break;
    }
  }

  /* Keeps the toolbar clear of a position:fixed page element at the left edge (a side menu) by sitting just right of it.
     Sticky elements are ignored: they scroll away with the page. Runs at mount, on resize, on html class changes and when a transition ends; never per scroll frame. */
  var clearQueued = false;
  function clearFixedLeft() {
    var tb = rev.ui.toolbar; tb.style.left = "";
    var r = tb.getBoundingClientRect(), right = 0;
    [r.top + 4, r.top + r.height / 2, r.bottom - 4].forEach(function (y) {
      doc.elementsFromPoint(r.left + 4, y).forEach(function (el) {
        if (el === root || el === doc.body || el.closest("[data-rev-ui]")) return;
        for (var a = el; a && a !== doc.body; a = a.parentElement) {
          var cs = getComputedStyle(a);
          if (cs.position === "fixed") { var b = a.getBoundingClientRect(); if (b.width < window.innerWidth / 2 && b.right > right) right = b.right; return; }
        }
      });
    });
    if (right) tb.style.left = (right + 8) + "px";
  }
  // After an html class change a side menu may slide in; re-measure every frame for 400 ms, then stop.
  function trackMenu() {
    var end = Date.now() + 400;
    (function step() { clearFixedLeft(); if (Date.now() < end) requestAnimationFrame(step); })();
  }
  function queueClear() { if (clearQueued) return; clearQueued = true; requestAnimationFrame(function () { clearQueued = false; clearFixedLeft(); }); }

  function applyNarrow() {
    var tb = rev.ui.toolbar;
    if (window.innerWidth < NARROW_PX) { if (!tb.hasAttribute("data-collapsed") && !tb.hasAttribute("data-user")) tb.setAttribute("data-collapsed", ""); }
    else tb.removeAttribute("data-collapsed");
  }

  /* ---------- keyboard: R toggles revision mode (kept even when mode is off) ---------- */
  doc.addEventListener("keydown", function (e) {
    if (e.defaultPrevented || e.ctrlKey || e.metaKey || e.altKey || (e.key !== "r" && e.key !== "R")) return;
    var t = e.target, tag = t && t.localName;
    if (tag === "input" || tag === "textarea" || tag === "select" || (t && t.isContentEditable)) return;
    rev.setMode(rev.state.mode === "on" ? "off" : "on");
  });

  /* ---------- placement: right-click, armed click-to-pin, drag from the toolbar, keyboard (design ## Placement) ---------- */
  var LABEL = { h: "Heading", p: "Paragraph", li: "List item", def: "Term", btn: "Button", img: "Image", fig: "Figure",
    tbl: "Table", row: "Table row", code: "Code block", dia: "Diagram", box: "Callout" };
  var hiEl = null, hiTarget = null, hoverTimer = 0, lastNode = null, dragging = null, armChip = null, t0 = 0;

  function sizeOk(el) { var r = el.getBoundingClientRect(); return r.width >= 8 && r.height >= 8; }
  // Nearest meaningful ancestor of a node (inclusive), or null. A custom element is pinned as a whole.
  function resolveFrom(node) {
    var a = node && node.nodeType === 1 ? node : node && node.parentElement;
    for (; a && a !== doc.body && a !== root; a = a.parentElement) {
      if (a.hasAttribute("data-rev-ui")) return null;
      var k = kindOf(a);
      if (!k || !sizeOk(a) || (a.parentElement && a.parentElement.closest("svg, canvas, picture"))) continue;   // shapes inside a diagram belong to the diagram
      var best = a;
      for (var up = a.parentElement; up && up !== doc.body; up = up.parentElement) {
        if (up.hasAttribute("data-rev-ui")) return null;
        if ((k === "img" || k === "dia") && matchesRule(up, null, KIND_SPEC.fig)) best = up;
        else if (tagOf(up).indexOf("-") >= 0 && kindOf(up)) best = up;
      }
      return best;
    }
    return null;
  }
  // Event target in the light DOM: the custom element host when the path goes through a shadow root.
  function resolveEvent(e) {
    var path = e.composedPath ? e.composedPath() : [];
    for (var i = 0; i < path.length; i++) if (path[i].nodeType === 1 && path[i].getRootNode() === doc) return resolveFrom(path[i]);
    return resolveFrom(e.target);
  }
  function widen(el) { return el && resolveFrom(el.parentElement); }

  // Document position of the overlay layer's top-left corner; a positioned or padded body moves it away from 0,0.
  function origin() { var o = rev.ui.layer.getBoundingClientRect(); return { x: o.left + scrollX, y: o.top + scrollY }; }

  function showHi(el) {
    hiTarget = el;
    if (!el) { if (hiEl) hiEl.removeAttribute("data-on"); return; }
    if (!hiEl) {
      hiEl = doc.createElement("div"); hiEl.className = "rev-hi"; hiEl.setAttribute("data-rev-ui", "");
      hiEl.appendChild(doc.createElement("span")).className = "rev-hi-tag";
      rev.ui.layer.appendChild(hiEl);
    }
    var r = el.getBoundingClientRect(), o = origin();
    hiEl.style.cssText = "left:" + (r.left + scrollX - o.x) + "px;top:" + (r.top + scrollY - o.y) + "px;width:" + r.width + "px;height:" + r.height + "px";
    hiEl.firstChild.textContent = LABEL[kindOf(el)] || "Item";
    // The tag sits above the outline; with no room above it moves inside, and near the right edge it aligns right.
    hiEl.toggleAttribute("data-flip", r.top < 28);
    hiEl.toggleAttribute("data-right", r.left + 90 > innerWidth);
    hiEl.setAttribute("data-on", "");
  }

  function uuid() {
    var b = crypto.getRandomValues(new Uint8Array(16)), h = [].map.call(b, function (x) { return ("0" + x.toString(16)).slice(-2); }).join("");
    return "urn:uuid:" + h.slice(0, 8) + "-" + h.slice(8, 12) + "-4" + h.slice(13, 16) + "-" + ((b[8] & 3) | 8).toString(16) + h.slice(17, 20) + "-" + h.slice(20);
  }

  /* ---------- pins and post-its (design ## Post-it and pin UI) ---------- */
  var INTENTS = ["Wording", "Look", "Order", "Other"], NOTE_W = 264, EDGE = 12, MAX_DRAWN = 3;
  var fresh = {}, placing = {}, notes = {}, pinEls = {}, openSeq = 0, syncTimer = 0, keep = {}, focusNext = {};

  function targetOf(pin) { return pin.target ? doc.querySelector('[data-rev-id="' + String(pin.target).replace(/["\\]/g, "") + '"]') : null; }
  // A target inside a closed details (outside its summary) is not drawn.
  function inClosedDetails(el) {
    for (var a = el.parentElement, prev = el; a; prev = a, a = a.parentElement)
      if (tagOf(a) === "details" && !a.open && tagOf(prev) !== "summary") return true;
    return false;
  }
  function pinById(id) { for (var i = 0; i < rev.state.pins.length; i++) if (rev.state.pins[i].id === id) return rev.state.pins[i]; return null; }
  function touch(pin) { pin.modified = new Date().toISOString().replace(/\.\d+Z$/, "Z"); }
  function el_(tag, cls, text) { var e = doc.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function btn_(label, text, cls) { var b = el_("button", cls || "rev-note-btn", text); b.type = "button"; if (label) b.setAttribute("aria-label", label); return b; }

  function removePin(pin) {
    var i = rev.state.pins.indexOf(pin);
    if (i >= 0) rev.state.pins.splice(i, 1);
    delete fresh[pin.id];
    if (embeddedPins().some(function (e) { return e.id === pin.id; }) && rev.state.deleted.indexOf(pin.id) < 0) rev.state.deleted.push(pin.id);
    rev.save(); sync();
  }
  // Folds every other saved post-it to its pin, except the ones the user marked Keep open.
  function foldOthers(pin) {
    rev.state.pins.forEach(function (o) { if (o !== pin && o.state === "open" && !keep[o.id]) o.state = "hidden"; });
  }
  function setState(pin, st) {
    if (st === "open" || st === "editing") foldOthers(pin);
    if (st === "editing") for (var k in notes) { var o = pinById(k); if (o && o !== pin && o.state === "editing") cancelEdit(o); }
    pin.state = st; touch(pin); rev.save(); sync();
  }
  function cancelEdit(pin) {
    var had = notes[pin.id] && notes[pin.id].contains(doc.activeElement);
    if (fresh[pin.id] && !(pin.text || "").trim()) {
      removePin(pin);
      if (had) { var tb = rev.ui.toolbar.querySelector('[data-rev-act="toggle"]'); if (tb) tb.focus({ preventScroll: true }); }   // the pin is gone, so focus goes to the tool bar
      return;
    }
    delete fresh[pin.id];
    setState(pin, (pin.text || "").trim() ? "open" : "hidden");
    var b = pinEls[pin.id];
    if (had && b) b.focus({ preventScroll: true });   // focus returns to the pin, so the keyboard user keeps their place
  }
  function saveEdit(pin, note) {
    var text = note.querySelector("textarea").value;
    if (!text.trim()) { if (fresh[pin.id]) removePin(pin); else cancelEdit(pin); return; }
    var chip = note.querySelector('.rev-chip[aria-pressed="true"]');
    pin.text = text.trim(); pin.intent = chip ? chip.textContent : "";
    delete fresh[pin.id];
    note.setAttribute("data-saved", "");
    if (note.contains(doc.activeElement)) focusNext[pin.id] = true;   // keyboard save: keep focus in the note so Esc closes it
    setState(pin, "open");
  }
  function hideNote(pin) {
    var n = notes[pin.id];
    delete keep[pin.id];
    var pb = pinEls[pin.id];
    if (n && pb) { var nr = n.getBoundingClientRect(), pr = pb.getBoundingClientRect(); n.style.transformOrigin = (pr.left + 11 - nr.left) + "px " + (pr.top + 11 - nr.top) + "px"; }   // the note shrinks toward its pin
    if (n) n.setAttribute("data-hiding", "");
    var had = n && n.contains(doc.activeElement);
    setTimeout(function () {
      if (rev.state.pins.indexOf(pin) < 0) return;   // deleted during the 180 ms hide animation
      setState(pin, "hidden");
      var b = pinEls[pin.id];
      if (b && had) b.focus({ preventScroll: true });   // focus returns to the pin, so the keyboard user keeps their place
      if (b) { b.setAttribute("data-pulse", ""); setTimeout(function () { b.removeAttribute("data-pulse"); }, 200); }
    }, n ? 180 : 0);
  }
  function deletePin(pin) {
    var n = notes[pin.id], b = pinEls[pin.id], idx = rev.state.pins.indexOf(pin);
    if (n) n.setAttribute("data-removing", "");
    if (b) b.setAttribute("data-removing", "");
    setTimeout(function () {
      var undoCopy = { pin: pin, index: idx };   // one copy per delete, so two quick deletes undo separately
      removePin(pin);
      rev.toast("Pin deleted", "Undo", function () {
        if (!undoCopy) return;
        var di = rev.state.deleted.indexOf(pin.id); if (di >= 0) rev.state.deleted.splice(di, 1);
        pin.state = "hidden"; rev.state.pins.splice(Math.min(undoCopy.index, rev.state.pins.length), 0, pin);
        undoCopy = null; rev.save(); sync();
      }, 6000);
    }, 200);
  }
  function widenPin(pin) {
    var el = targetOf(pin), w = el && widen(el);
    if (!w) { rev.toast("Nothing wider to pin"); return; }
    stampIds();
    pin.target = w.getAttribute("data-rev-id"); pin.kind = kindOf(w); pin.section = sectionOf(w) || "";
    pin.quote = { exact: (w.textContent || "").replace(/\s+/g, " ").trim().slice(0, 200), prefix: "", suffix: "" };
    touch(pin); rev.save(); sync();
  }

  function renderNote(pin, note) {
    var editing = pin.state === "editing", pb = pinEls[pin.id];
    note.textContent = "";
    var head = el_("div", "rev-note-head");
    head.appendChild(el_("span", "", "#" + (pb ? pb.firstChild.firstChild.textContent : "")));
    head.appendChild(el_("span", "rev-note-kind", (LABEL[pin.kind] || "Item") + (!editing && pin.intent ? " - " + pin.intent : "")));
    var wb = btn_("Widen to the parent block", "Widen"); wb.addEventListener("click", function () { widenPin(pin); });
    head.appendChild(wb);
    note.appendChild(head);
    var foot = el_("div", "rev-note-foot");
    if (editing) {
      var chips = el_("div", "rev-chips");
      INTENTS.forEach(function (name) {
        var c = btn_("", name, "rev-chip"); c.setAttribute("aria-pressed", pin.intent === name ? "true" : "false");
        c.addEventListener("click", function () {
          var on = c.getAttribute("aria-pressed") !== "true";
          [].forEach.call(chips.children, function (x) { x.setAttribute("aria-pressed", "false"); });
          c.setAttribute("aria-pressed", on ? "true" : "false");
        });
        chips.appendChild(c);
      });
      note.appendChild(chips);
      var ta = el_("textarea"); ta.value = pin.text || ""; ta.setAttribute("aria-label", "Revision note"); ta.placeholder = "What should change here?";
      var grow = function () { ta.style.height = "auto"; ta.style.height = Math.min(320, Math.max(72, ta.scrollHeight)) + "px"; };
      ta.addEventListener("input", grow);
      ta.addEventListener("keydown", function (e) {
        if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); saveEdit(pin, note); }
        else if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); cancelEdit(pin); }
      });
      note.appendChild(ta);
      var sv = btn_("", "Save"); sv.title = "Ctrl+Enter"; sv.addEventListener("click", function () { saveEdit(pin, note); });
      var cn = btn_("", "Cancel"); cn.title = "Esc"; cn.addEventListener("click", function () { cancelEdit(pin); });
      foot.appendChild(sv); foot.appendChild(cn);
      ta.addEventListener("focus", function () { var d = placing[pin.id]; if (d && d.t1 == null) { d.t1 = performance.now(); delete placing[pin.id]; } });
      note._focus = function () { ta.focus({ preventScroll: true }); grow(); };
    } else {
      note.appendChild(el_("p", "rev-note-text", pin.text || ""));
      var ed = btn_("", "Edit"); ed.title = "E"; ed.addEventListener("click", function () { setState(pin, "editing"); });
      var hd = btn_("", "Hide"); hd.addEventListener("click", function () { hideNote(pin); });
      var kp = btn_("Keep this post-it open while others open", "Keep open"); kp.setAttribute("aria-pressed", keep[pin.id] ? "true" : "false");
      kp.addEventListener("click", function () { if (keep[pin.id]) delete keep[pin.id]; else keep[pin.id] = true; rev.save(); kp.setAttribute("aria-pressed", keep[pin.id] ? "true" : "false"); });
      foot.appendChild(ed); foot.appendChild(kp); foot.appendChild(hd);
      note._focus = focusNext[pin.id] ? function () { delete focusNext[pin.id]; ed.focus({ preventScroll: true }); } : null;
    }
    var del = btn_("", "Delete");
    del.setAttribute("data-danger", "");
    del.addEventListener("click", function () {
      var yes = btn_("", "Yes"), no = btn_("", "No"), ask = el_("span", "", "Delete?"), timer = 0;
      var restore = function () { clearTimeout(timer); ask.replaceWith(del); yes.remove(); no.remove(); };
      del.replaceWith(ask, yes, no);
      timer = setTimeout(restore, 3000);
      no.addEventListener("click", restore);
      yes.addEventListener("click", function () { clearTimeout(timer); deletePin(pin); });
      yes.focus();
    });
    foot.appendChild(del);
    note.appendChild(foot);
    note._st = pin.state;
    if (note._focus && note.isConnected) note._focus();
  }

  // Order: right gutter (284 px = 8 gap + 264 note + 12 edge, minus the pin list drawer), left margin (a wide target may use it too), above, below, then compact; always 12 px inside the viewport.
  var PANEL_W = 320;   // the pin list drawer's width in px; the page and post-its keep clear of it while it is open
  // True when text, an image or a control sits under the viewport box (x, y, NOTE_W wide, h tall); probes 5 columns every 24 px of height.
  // A probe point outside the viewport cannot be tested, so it counts as covered and the note moves off that gutter,
  // except below the bottom edge when the note starts inside the window: only controls and headings are tested there, so a note near the bottom stays full size when none is under it.
  // ctl true checks controls, links and images only, plus the target box tr (used for the compact note, which may sit over other plain text but never over a control or the text being revised).
  function coversContent(x, y, h, ctl, tr) {
    var pts = [], ys = [4];
    for (var yy = 28; yy < h - 4; yy += 24) ys.push(yy);
    ys.push(Math.max(4, h - 4));
    ys.forEach(function (dy) { pts.push([4, dy], [NOTE_W / 4, dy], [NOTE_W / 2, dy], [NOTE_W * 3 / 4, dy], [NOTE_W - 4, dy]); });
    var vh = doc.documentElement.clientHeight, vwid = doc.documentElement.clientWidth;
    return pts.some(function (d) {
      var px = x + d[0], py = y + d[1];
      if (py >= vh && y < vh && px >= 0 && px < vwid) {   // below the window: only controls and headings can be tested, by their boxes
        return Array.prototype.some.call(doc.querySelectorAll("input,textarea,button,select,a[href],img,svg,canvas,video,h1,h2,h3,h4,h5,h6"), function (e) {
          if (e.closest("[data-rev-ui]")) return false;
          var b = e.getBoundingClientRect();
          return b.width > 0 && px >= b.left && px <= b.right && py >= b.top && py <= b.bottom;
        });
      }
      if (px < 0 || py < 0 || px >= vwid || py >= vh) return true;
      if (ctl && tr && px >= tr.left && px <= tr.right && py >= tr.top && py <= tr.bottom) return true;
      var hit = doc.elementsFromPoint(px, py).filter(function (e) { return !e.closest("[data-rev-ui]"); })[0];
      if (!hit || hit === doc.documentElement || hit === doc.body) return false;
      if (/^(IMG|SVG|CANVAS|INPUT|BUTTON|TEXTAREA|SELECT|VIDEO)$/i.test(hit.tagName)) return true;
      if (hit.closest("a[href]")) return true;
      if (ctl) return false;
      return Array.prototype.some.call(hit.childNodes, function (c) { return c.nodeType === 3 && c.nodeValue.trim(); });
    });
  }
  // Tries right, left, above, then below the target and takes the first spot with no content under it; with none free, opens a compact note below.
  function layoutNote(pin, note, r) {
    var vw = doc.documentElement.clientWidth - (rev.state.panel ? PANEL_W : 0), left, top = r.top + scrollY, o = origin(), ok = false, h, cl;
    note.removeAttribute("data-compact");   // first, so the height below is the full one
    h = note.offsetHeight; cl = Math.max(EDGE, Math.min(r.left, vw - NOTE_W - EDGE));   // cl: the clamped left that is probed and used
    if (r.right + 8 + NOTE_W + EDGE <= vw && !coversContent(r.right + 8, r.top, h)) { left = r.right + scrollX + 8; ok = true; }
    else if (r.left - 34 - NOTE_W >= EDGE && !coversContent(r.left - 34 - NOTE_W, r.top, h)) { left = r.left + scrollX - 34 - NOTE_W; ok = true; }
    else if (r.top - 8 - h >= EDGE && !coversContent(cl, r.top - 8 - h, h)) { left = r.left + scrollX; top = r.top + scrollY - 8 - h; ok = true; }
    else if (!coversContent(cl, r.bottom + 8, h)) { left = r.left + scrollX; top = r.bottom + scrollY + 8; ok = true; }
    if (!ok) {   // no free spot: slide the full note down the page, then try a compact note, and never cover a control
      var d, cands = [];
      for (d = 0; d <= 200; d += 40) cands.push(r.bottom + 8 + d);
      var y = cands.filter(function (yy) { return !coversContent(cl, yy, h); })[0];
      if (y === undefined && pin.state === "open") {
        note.setAttribute("data-compact", ""); h = note.offsetHeight;
        y = cands.filter(function (yy) { return !coversContent(cl, yy, h, true, r); })[0];
        if (y === undefined) y = cands.concat([r.top - 8 - h]).filter(function (yy) { return yy >= EDGE && !coversContent(cl, yy, h, true, r); })[0];
      }
      left = cl + scrollX; top = (y === undefined ? r.bottom + 8 : y) + scrollY;
    }
    left = Math.max(scrollX + EDGE, Math.min(left, scrollX + vw - NOTE_W - EDGE));
    top = Math.max(EDGE, top);
    left -= o.x; top -= o.y;
    note.style.left = left + "px"; note.style.top = top + "px";
  }

  // Sets the open animation's origin to the pin; call after the post-it reached its final position.
  function setOrigin(pin, note) {
    var pb = pinEls[pin.id];
    if (pb) note.style.setProperty("--rev-ox", Math.round(parseFloat(pb.style.left) - parseFloat(note.style.left) + 11) + "px " + Math.round(parseFloat(pb.style.top) - parseFloat(note.style.top) + 11) + "px");
  }

  // Moves a post-it just below the post-it it overlaps, plus an 8 px gap, and repeats (at most 40 times)
  // until it clears every post-it laid out earlier in this pass. Never hides a post-it.
  function avoidNotes(note, placed) {
    for (var n = 0; n < 40; n++) {
      var hit = placed.filter(function (q) { return overlaps(note, q); })[0];
      if (!hit) break;
      note.style.top = (noteBox(hit).bottom + 8) + "px";
    }
    placed.push(note);
  }

  // Box from layout size (offsetWidth/offsetHeight) and style left/top, so the scale(.2) open animation does not shrink it.
  function noteBox(n) {
    var l = parseFloat(n.style.left) || 0, t = parseFloat(n.style.top) || 0;
    return { left: l, top: t, right: l + n.offsetWidth, bottom: t + n.offsetHeight };
  }
  function overlaps(a, b) {
    var x = noteBox(a), y = noteBox(b);
    return !(x.right <= y.left || y.right <= x.left || x.bottom <= y.top || y.bottom <= x.top);
  }

  function makePinEl(pin) {
    var b = el_("button", "rev-pin");
    b.type = "button"; b.setAttribute("data-rev-ui", ""); b.setAttribute("data-new", ""); b.setAttribute("data-rev-pin", pin.id);
    b.innerHTML = "<span><b></b></span>";
    b.addEventListener("animationend", function () { b.removeAttribute("data-new"); });
    b.addEventListener("click", function () { if (pin.state === "hidden") setState(pin, (pin.text || "").trim() ? "open" : "editing"); });
    rev.ui.layer.appendChild(b);
    return b;
  }
  function makeNoteEl(pin) {
    var note = el_("div", "rev-note");
    note.setAttribute("data-rev-ui", ""); note.setAttribute("data-new", ""); note.setAttribute("role", "dialog");
    note.addEventListener("animationend", function () { note.removeAttribute("data-new"); note.removeAttribute("data-saved"); });
    note.addEventListener("keydown", function (e) {
      if (pin.state !== "open") return;
      if (e.key === "Escape") { e.stopPropagation(); hideNote(pin); }
      else if ((e.key === "e" || e.key === "E") && !e.target.closest("button")) setState(pin, "editing");
    });
    note._seq = ++openSeq;
    return note;
  }

  // Redraws every pin and post-it from rev.state.pins; safe to call at any time.
  function sync() {
    syncTimer = 0;
    if (!rev.ui.layer) return;
    var pins = rev.state.pins, live = {}, perTarget = {}, placed = [], pinBoxes = [], o = origin();
    var items = pins.map(function (p, i) { return { pin: p, el: targetOf(p), i: i }; }).filter(function (x) { return x.el && !inClosedDetails(x.el); });
    items.sort(function (a, b) { var c = a.el.compareDocumentPosition(b.el); return c & 4 ? -1 : c & 2 ? 1 : a.i - b.i; });
    items.forEach(function (x, n) {
      var pin = x.pin, r = x.el.getBoundingClientRect(), k = perTarget[pin.target] = (perTarget[pin.target] || 0) + 1, off = (k - 1) * 16;
      live[pin.id] = true;
      var b = pinEls[pin.id] || (pinEls[pin.id] = makePinEl(pin));
      b.setAttribute("data-rev-target", pin.target);
      b.firstChild.firstChild.textContent = n + 1;
      b.setAttribute("aria-label", "Pin " + (n + 1) + ": " + (pin.text || (pin.quote && pin.quote.exact) || "").slice(0, 60));
      if (pin.status === "done") b.setAttribute("data-done", ""); else b.removeAttribute("data-done");
      b.style.display = k > MAX_DRAWN ? "none" : "";
      var more = b.querySelector(".rev-pin-more");
      if (k === 1) {
        var total = pins.filter(function (q) { return q.target === pin.target; }).length;
        if (total > MAX_DRAWN) { if (!more) { more = el_("span", "rev-pin-more"); b.appendChild(more); } more.textContent = "+" + (total - MAX_DRAWN); }
        else if (more) more.remove();
      }
      if (r.left < 30) { b.setAttribute("data-corner", ""); b.style.left = (r.right + scrollX - o.x - 22 - off) + "px"; b.style.top = (r.top + scrollY - o.y - 12) + "px"; }   // above the corner, so the badge sits off the text
      else { b.removeAttribute("data-corner"); b.style.left = (r.left + scrollX - o.x - 26 - off) + "px"; b.style.top = (r.top + scrollY - o.y + 2) + "px"; }
      var px = parseFloat(b.style.left), py = parseFloat(b.style.top);
      var minPx = EDGE - o.x, hitsPin = function () { return pinBoxes.some(function (q) { return Math.abs(q[0] - px) < 24 && Math.abs(q[1] - py) < 24; }); };
      px = Math.max(px, minPx);   // a stepped pin never goes past the left edge: it steps down instead
      for (var s = 0; s < 6 && k <= MAX_DRAWN && hitsPin(); s++) { if (px - 24 >= minPx) px -= 24; else py += 24; }
      b.style.left = px + "px"; b.style.top = py + "px";
      if (k <= MAX_DRAWN) pinBoxes.push([px, py]);   // a pin hidden by the per-target cap takes no stacking slot
      var note = notes[pin.id], want = pin.state !== "hidden" && pin.status !== "done";
      if (want) {
        var created = !note;
        if (created) { note = notes[pin.id] = makeNoteEl(pin); rev.ui.layer.appendChild(note); }
        if (created || note._st !== pin.state) renderNote(pin, note);
        note.setAttribute("data-state", pin.state);
        note.setAttribute("data-parity", (n + 1) % 2 ? "odd" : "even");
        note.setAttribute("aria-label", "Post-it for pin " + (n + 1));
        layoutNote(pin, note, r);
        avoidNotes(note, placed);
        setOrigin(pin, note);
      } else if (note) { note.remove(); delete notes[pin.id]; }
    });
    for (var pid in pinEls) if (!live[pid]) { pinEls[pid].remove(); delete pinEls[pid]; }
    for (var nid in notes) if (!live[nid]) { notes[nid].remove(); delete notes[nid]; }
    var anyOpen = pins.some(function (p) { return p.state !== "hidden"; }), ha = rev.ui.toolbar.querySelector('[data-rev-act="hideall"]');
    if (ha) { var lab = anyOpen ? "Hide all post-its" : "Show all post-its"; ha.setAttribute("aria-label", lab); ha.lastChild.textContent = lab; }
  }
  function syncSoon() { clearTimeout(syncTimer); syncTimer = setTimeout(sync, 100); }
  rev.sync = sync;

  function installPins() {
    rev.state.pins = rev.state.pins.filter(function (p) {
      if (p.state === "editing") { if (!(p.text || "").trim()) return false; p.state = "open"; }
      if (p.state !== "open" && p.state !== "hidden") p.state = "hidden";
      return true;
    });
    rev.on("action", function (e) {
      if (e.detail.act !== "hideall") return;
      var any = rev.state.pins.some(function (p) { return p.state !== "hidden"; });
      rev.state.pins.forEach(function (p) { if (any) { p.state = "hidden"; delete keep[p.id]; } else if ((p.text || "").trim()) { p.state = "open"; } });
      rev.save(); sync();
    });
    window.addEventListener("resize", syncSoon);
    doc.addEventListener("toggle", syncSoon, true);
    if (window.ResizeObserver) new ResizeObserver(syncSoon).observe(doc.body);
    sync();
  }

  function place(el, method) {
    if (!el.getAttribute("data-rev-id")) stampIds();
    var id = el.getAttribute("data-rev-id");
    if (!id) return null;
    var now = new Date().toISOString().replace(/\.\d+Z$/, "Z"), text = (el.textContent || "").replace(/\s+/g, " ").trim();
    var pin = { id: uuid(), target: id, kind: kindOf(el), section: sectionOf(el) || "", intent: "", text: "", state: "editing", status: "new",
      created: now, modified: now, quote: { exact: text.slice(0, 200), prefix: "", suffix: "" } };
    foldOthers(pin);
    rev.state.pins.push(pin);
    fresh[pin.id] = true;
    var detail = { targetId: id, method: method, t0: t0, t1: null, inputs: { contextmenu: 1, click: 1, drag: 2, key: 1 }[method], pin: pin };
    placing[pin.id] = detail;   // the note textarea focus handler fills t1
    rev.save();
    sync();
    if (detail.t1 == null) detail.t1 = performance.now();   // page without focus: no focus event fired
    delete placing[pin.id];
    rev.emit("placed", detail);
    return pin;
  }
  rev.place = place; rev.widen = widen;

  function setArmed(on) {
    rev.state.armed = on;
    root.toggleAttribute("data-rev-armed", on);
    var b = rev.ui.toolbar.querySelector('[data-rev-act="click"]');
    b.setAttribute("aria-pressed", on ? "true" : "false");
    if (on && !armChip) {
      armChip = doc.createElement("div"); armChip.className = "rev-chip"; armChip.setAttribute("data-rev-ui", "");
      armChip.textContent = "Click to pin - Esc to stop";
      armChip.style.cssText = "position:fixed;left:56px;top:calc(50% + 140px);pointer-events:none;z-index:calc(var(--rev-z) + 3)";
      rev.ui.layer.appendChild(armChip);
    } else if (!on && armChip) { armChip.remove(); armChip = null; showHi(null); }
    rev.save();
  }

  function endDrag(target) {
    var g = dragging; dragging = null;
    if (!g) return;
    showHi(null);
    if (target) { g.remove(); place(target, "drag"); return; }
    var r = rev.ui.toolbar.querySelector('[data-rev-act="pinsource"]').getBoundingClientRect();
    g.setAttribute("data-return", ""); g.style.left = (r.left + r.width / 2) + "px"; g.style.top = (r.top + r.height / 2) + "px";
    setTimeout(function () { g.remove(); }, 180);
  }
  function moveGhost(e) { dragging.style.left = e.clientX + "px"; dragging.style.top = e.clientY + "px"; }

  function installPlacement() {
    // right-click: capture phase, skipped on Shift, mode off, blank space and runtime UI
    doc.addEventListener("contextmenu", function (e) {
      if (rev.state.mode !== "on" || e.shiftKey) return;
      var el = resolveEvent(e);
      // the left toolbar can sit over page content: look through it to the page object underneath
      if (!el && e.target.closest && e.target.closest("#rev-toolbar")) {
        var under = doc.elementsFromPoint(e.clientX, e.clientY);
        for (var u = 0; u < under.length && !el; u++) if (!under[u].closest("[data-rev-ui]")) el = resolveFrom(under[u]);
      }
      if (!el) return;
      e.preventDefault(); t0 = performance.now();
      place(el, "contextmenu");
    }, true);

    // armed click-to-pin: links, buttons, summary and submit stop working until Esc
    function armedBlock(e) {
      if (!rev.state.armed || rev.state.mode !== "on" || (e.target.closest && e.target.closest("[data-rev-ui]"))) return;
      e.preventDefault(); e.stopPropagation();
      if (e.type === "click") { var el = resolveEvent(e); t0 = performance.now(); if (el) place(el, "click"); }
    }
    ["click", "auxclick", "mousedown", "submit"].forEach(function (t) { doc.addEventListener(t, armedBlock, true); });
    rev.on("action", function (e) { if (e.detail.act === "click") setArmed(!rev.state.armed); });
    rev.on("mode", function (e) { if (e.detail.mode !== "on") { showHi(null); if (rev.state.armed) setArmed(false); } });
    if (rev.state.armed && rev.state.mode === "on") setArmed(true); else rev.state.armed = false;

    // drag a pin from the toolbar: pointer events, ghost follows, highlight under it
    rev.ui.toolbar.addEventListener("pointerdown", function (e) {
      var b = e.target.closest('[data-rev-act="pinsource"]');
      if (!b || e.button !== 0) return;
      e.preventDefault(); t0 = performance.now();
      dragging = doc.createElement("div"); dragging.className = "rev-ghost"; dragging.setAttribute("data-rev-ui", "");
      rev.ui.layer.appendChild(dragging); moveGhost(e);
    });
    doc.addEventListener("pointermove", function (e) {
      if (dragging) { moveGhost(e); showHi(resolveFrom(doc.elementFromPoint(e.clientX, e.clientY))); return; }
      if (rev.state.mode !== "on") return;
      lastNode = e.target;
      if (rev.state.armed) { showHi(resolveEvent(e)); return; }
      clearTimeout(hoverTimer);   // right-click highlight waits 80 ms so fast travel does not flicker
      hoverTimer = setTimeout(function () { showHi(lastNode && lastNode.closest && !lastNode.closest("[data-rev-ui]") ? resolveFrom(lastNode) : null); }, 80);
    }, { passive: true });
    doc.addEventListener("pointerup", function (e) { if (dragging) endDrag(resolveFrom(doc.elementFromPoint(e.clientX, e.clientY))); });

    // keyboard: J K move, Enter pins, L list, C arm, Alt+Up/Down widen/narrow, Esc closes the top-most thing
    var trail = [], keyHint = false;
    doc.addEventListener("keydown", function (e) {
      var t = e.target, tag = t && t.localName;
      if (e.ctrlKey || e.metaKey || tag === "input" || tag === "textarea" || tag === "select" || (t && t.isContentEditable)) return;
      var navKey = e.key.toLowerCase() === "j" || e.key.toLowerCase() === "k" || (e.altKey && (e.key === "ArrowUp" || e.key === "ArrowDown"));
      if (e.key !== "Escape" && t && t.closest && t.closest("[data-rev-ui]") && !(navKey && t.closest(".rev-pin"))) return;   // keys on a revision control belong to that control; a focused pin still lets J/K and Alt+Up/Down through
      if (e.key === "Escape") {
        if (dragging) endDrag(null); else if (rev.state.armed) setArmed(false); else showHi(null);
        return;
      }
      if (rev.state.mode !== "on") return;
      var k = e.key.toLowerCase();
      if (e.altKey && (e.key === "ArrowUp" || e.key === "ArrowDown") && hiTarget) {
        e.preventDefault();
        if (e.key === "ArrowUp") { var w = widen(hiTarget); if (w) { trail.push(hiTarget); showHi(w); } }
        else if (trail.length) showHi(trail.pop());
      } else if (e.altKey) return;
      else if (k === "j" || k === "k") {
        var all = [].filter.call(doc.querySelectorAll("[data-rev-id]"), function (n) { return !n.closest("[data-rev-ui]") && !n.querySelector("[data-rev-id]") && sizeOk(n) && getComputedStyle(n).visibility !== "hidden"; });
        var i = all.indexOf(hiTarget), n2 = all[k === "j" ? i + 1 : (i < 0 ? all.length : i) - 1];
        if (i < 0 && hiTarget) {   // hiTarget is a container (after Alt+Up): continue from its position
          var after = all.filter(function (n) { return hiTarget.compareDocumentPosition(n) & 4 && !hiTarget.contains(n); }), before = all.filter(function (n) { return hiTarget.compareDocumentPosition(n) & 2; });
          n2 = k === "j" ? after[0] : before[before.length - 1];
        }
        if (n2) { trail = []; n2.scrollIntoView({ block: "nearest" }); showHi(n2); if (!keyHint) { keyHint = true; rev.toast("Keys: J/K move, Enter pins, Alt+Up widens, Esc closes", null, null, 6000); } }
      } else if (k === "enter" && hiTarget) { e.preventDefault(); t0 = performance.now(); place(hiTarget, "key"); }
      else if (k === "c") setArmed(!rev.state.armed);
      else if (k === "l") rev.emit("action", { act: "list", button: null });
    });
  }

  /* ---------- list panel and TOC markers (design ## Pin list panel and TOC markers) ---------- */
  var ENTRY_SEL = 'nav a[href^="#"], .toc a[href^="#"], .stepmap [data-go], .steps-list [data-go], details.lvl > summary';
  var panelBody, panelFilter, confirming = false, panelTimer = 0, tocTimer = 0;

  function entryTarget(e) {
    var r = e.getAttribute("href") || e.getAttribute("data-go") || "";
    return r.length > 1 && r.charAt(0) === "#" ? doc.getElementById(r.slice(1)) : null;
  }
  function summaryOf(d) { return d.querySelector(":scope > summary"); }
  function groupEl(el) {
    var d = el.closest("details.lvl");
    for (var a = el; !d && a && a !== doc.body; a = a.parentElement) if (a.id) d = a;
    return d;
  }
  function groupLabel(g, pin) {
    var h = g && (summaryOf(g) || g.querySelector("h1,h2,h3,h4"));
    var t = ((h || g || {}).textContent || "").replace(/\s+/g, " ").trim();
    // a heading holding its text twice (split-text screen-reader copy + visible words) prints once; case and spaces ignored
    var s = t.replace(/\s/g, ""), n = s.length / 2;
    if (n >= 3 && n % 1 === 0 && s.slice(0, n).toLowerCase() === s.slice(n).toLowerCase())
      for (var i = 0, c = 0; i < t.length; i++) if (/\S/.test(t[i]) && ++c === n) { t = t.slice(0, i + 1); break; }
    return (t.length > 60 ? t.slice(0, 59).trimEnd() + "..." : t) || "Page";
  }
  function pinsByDocOrder() {
    return rev.state.pins.map((p, i) => { return { pin: p, el: targetOf(p), i: i }; }).sort((a, b) => {
      if (!a.el || !b.el) return (a.el ? 1 : 0) - (b.el ? 1 : 0) || a.i - b.i;
      var c = a.el.compareDocumentPosition(b.el); return c & 4 ? -1 : c & 2 ? 1 : a.i - b.i;
    });
  }

  // Nearest heading with an id that comes before el in document order; el itself does not count.
  var HEAD_SEL = "h1[id],h2[id],h3[id],h4[id]";
  function headingBefore(el) {
    for (var a = el; a && a !== doc.body; a = a.parentElement)
      for (var s = a.previousElementSibling; s; s = s.previousElementSibling) {
        if (s.matches(HEAD_SEL)) return s;
        var q = s.querySelectorAll(HEAD_SEL); if (q.length) return q[q.length - 1];
      }
    return null;
  }
  function badge(b, n) { b.setAttribute("data-n", n); b.setAttribute("aria-label", n + " revision pins"); }
  function paintToc() {
    tocTimer = 0;
    var entries = [].filter.call(doc.querySelectorAll(ENTRY_SEL), e => { return !e.closest("[data-rev-ui]"); }), count = new Map();
    function add(e) { if (e) count.set(e, (count.get(e) || 0) + 1); }
    var links = entries.filter(e => e.matches("a[href]")), mirror = new Map();
    pinsByDocOrder().forEach(x => {
      var hit = null, d = x.el && x.el.closest("details.lvl"), s;
      if (!x.el) return;
      if (d && entries.indexOf(summaryOf(d)) >= 0) hit = summaryOf(d);
      for (var a = x.el; a && !hit; a = a.parentElement)
        if (a.id) entries.forEach(e => { if (!hit && entryTarget(e) === a) hit = e; });
      add(hit);
      var link = null;   // the Contents link also counts: by section id, else (flat page) by the heading above the pin
      for (a = x.el; a && !link; a = a.parentElement) if (a.id) links.forEach(e => { if (!link && entryTarget(e) === a) link = e; });
      for (var h = link ? null : x.el.querySelector(HEAD_SEL) || headingBefore(x.el); h && !link; h = headingBefore(h)) links.forEach(e => { if (!link && entryTarget(e) === h) link = e; });
      if (link && link !== hit) mirror.set(link, (mirror.get(link) || 0) + 1);
      for (var c = x.el.parentElement; c; c = c.parentElement)   // closed details: its summary shows the count
        if (tagOf(c) === "details" && !c.open) { s = summaryOf(c); if (s !== hit) add(s); break; }
    });
    mirror.forEach((n, e) => { if (count.has(e)) { count.set(e, count.get(e) + n); mirror.delete(e); } });   // one badge per link, with the total
    // rev-toc-badge marks the pin's own entry; rev-toc-link-badge repeats that count on the side Contents link
    [["rev-toc-badge", count], ["rev-toc-link-badge", mirror]].forEach(([cls, map]) => {
      [].forEach.call(doc.querySelectorAll("." + cls), b => {
        var n = map.get(b.parentElement); map.delete(b.parentElement);
        if (n) badge(b, n); else b.remove();
      });
      map.forEach((n, e) => { var b = el_("span", cls); b.setAttribute("data-rev-ui", ""); badge(b, n); e.appendChild(b); });
    });
    rev.ui.toolbar.querySelector('[data-rev-act="list"]').setAttribute("data-count", rev.state.pins.length || "");
  }
  function tocSoon() { clearTimeout(tocTimer); tocTimer = setTimeout(paintToc, 100); }

  function locate(pin, edit) {
    var el = targetOf(pin);
    if (!el) { rev.toast("Pin target not found"); return; }
    for (var a = el.parentElement; a; a = a.parentElement) if (tagOf(a) === "details") a.open = true;
    if (edit) setState(pin, "editing");
    else if (pin.state === "hidden") setState(pin, (pin.text || "").trim() ? "open" : "editing");
    el.scrollIntoView({ block: "center" });
    sync(); syncSoon(); showHi(el); hiEl.setAttribute("data-pulse", "");
    setTimeout(() => { hiEl.removeAttribute("data-pulse"); if (hiTarget === el) showHi(null); }, 950);
  }
  function askIn(btn, question, onYes) {
    var yes = btn_("", "Yes"), no = btn_("", "No"), ask = el_("span", "", question), timer = 0;
    var done = () => { clearTimeout(timer); confirming = false; ask.replaceWith(btn); yes.remove(); no.remove(); };
    confirming = true; btn.replaceWith(ask, yes, no); timer = setTimeout(done, 3000); yes.focus();
    no.addEventListener("click", e => { e.stopPropagation(); done(); });
    yes.addEventListener("click", e => { e.stopPropagation(); done(); onYes(); });
  }
  function copyMarkdown() {
    var text = pinsByDocOrder().map((x, n) => {
      var p = x.pin, g = x.el && groupEl(x.el);
      return (n + 1) + ". " + (g ? groupLabel(g, p) : "Orphaned") + " - " + (LABEL[p.kind] || "Item") + ": " + (p.text || "").replace(/\s+/g, " ").trim();
    }).join("\n");
    var t = el_("textarea"); t.value = text; doc.body.appendChild(t); t.select(); doc.execCommand("copy"); t.remove();
    rev.toast("Copied " + rev.state.pins.length + " pins");
  }

  function renderPanel() {
    panelTimer = 0;
    if (confirming || !panelBody) return;
    var q = panelFilter.value.trim().toLowerCase(), groups = [], byKey = new Map();
    panelBody.textContent = "";
    pinsByDocOrder().forEach(x => {
      var g = x.el ? groupEl(x.el) : null, key = x.el ? (g || "page") : "orphan", label = x.el ? groupLabel(g, x.pin) : "Orphaned";
      if (q && (x.pin.text || "").toLowerCase().indexOf(q) < 0 && label.toLowerCase().indexOf(q) < 0) return;
      if (!byKey.has(key)) { var grp = { key: key, label: label, rows: [] }; byKey.set(key, grp); if (key === "orphan") groups.unshift(grp); else groups.push(grp); }
      byKey.get(key).rows.push(x.pin);
    });
    if (!groups.length) panelBody.appendChild(el_("p", "rev-panel-empty", "No pins yet. Right-click anything to add one."));
    groups.forEach(grp => {
      var wrap = el_("div", grp.key === "orphan" ? "rev-orphan" : "");
      wrap.append(el_("div", "rev-group rev-panel-group", grp.label));
      grp.rows.forEach(pin => {
        var row = el_("div", "rev-row rev-panel-row"), pb = pinEls[pin.id], head = el_("div", "rev-row-head"), q40 = pin.quote && pin.quote.exact;
        row.tabIndex = 0; row._pin = pin;
        head.append(el_("b", "", "#" + (pb ? pb.firstChild.firstChild.textContent : "-")), el_("span", "rev-chip", LABEL[pin.kind] || "Item"));
        if (pin.intent) head.append(el_("span", "rev-chip", pin.intent));
        row.append(head, el_("div", "rev-row-text", pin.text || "(no comment yet)"));
        if (q40) row.append(el_("div", "rev-row-quote", q40.length > 40 ? q40.slice(0, 40).replace(/\s+\S*$/, "") + "..." : q40));
        var acts = el_("div", "rev-row-acts"), ed = btn_("", "Edit"), del = btn_("", "Delete");
        ed.addEventListener("click", e => { e.stopPropagation(); locate(pin, true); });
        del.addEventListener("click", e => { e.stopPropagation(); askIn(del, "Delete?", () => { deletePin(pin); }); });
        acts.append(ed, del); row.append(acts);
        row.addEventListener("click", () => { locate(pin, false); });
        wrap.appendChild(row);
      });
      panelBody.appendChild(wrap);
    });
  }
  function setPanel(on) {
    rev.state.panel = on; rev.ui.panel.toggleAttribute("data-open", on); root.toggleAttribute("data-rev-panel", on);
    rev.ui.toolbar.querySelector('[data-rev-act="list"]').setAttribute("aria-pressed", on);
    if (on) renderPanel();
    rev.save();
    sync(); syncSoon();   // the page may reflow around the panel: redraw the overlay now and once more after it settles
  }

  /* ---------- Save revisions (design ## Save and export, decision D8) ---------- */
  function annotationPage() {
    return { "@context": "http://www.w3.org/ns/anno.jsonld", type: "AnnotationPage", "rev:doc": docId,
      items: rev.state.pins.filter(p => (p.text || "").trim()).map(p => {   // a pin with no comment has nothing to revise
        return { id: p.id, type: "Annotation", motivation: "editing", created: p.created, modified: p.modified,
          body: { type: "TextualBody", format: "text/plain", purpose: "editing", value: p.text },
          target: { source: "urn:rev:" + docId, selector: [
            { type: "CssSelector", value: '[data-rev-id="' + p.target + '"]' },
            { type: "TextQuoteSelector", exact: (p.quote && p.quote.exact) || p.target, prefix: (p.quote && p.quote.prefix) || "", suffix: (p.quote && p.quote.suffix) || "" }] },
          "rev:kind": p.kind, "rev:section": p.section, "rev:intent": p.intent, "rev:state": p.state, "rev:status": p.status, "rev:keep": !!keep[p.id] };
      }) };
  }
  function exportHtml() {
    var snap = window.__revSnap, snapEl = doc.querySelector("script[data-rev=snap]");
    if (!snap || !snapEl) return null;
    snap = snap.replace(/<script[^>]*id="rev-annotations"[^>]*>[\s\S]*?<\/script>\n?/g, "");
    var tail = [].filter.call(doc.querySelectorAll("body script"), s => {
      return (snapEl.compareDocumentPosition(s) & 4) && s.id !== "rev-annotations";
    }).map(s => s.outerHTML).join("\n");
    var json = JSON.stringify(annotationPage(), null, 1).replace(/</g, "\\u003c");
    var block = '<script type="application/ld+json" id="rev-annotations">' + json + "</script>";
    var at = snap.lastIndexOf("</body>");
    return "<!DOCTYPE html>\n" + (at < 0 ? snap + tail + block : snap.slice(0, at) + tail + "\n" + block + "\n" + snap.slice(at));
  }
  function saveRevisions() {
    var html = exportHtml();
    if (html == null) { rev.toast("Save failed: this page has no snapshot - rebuild it with revision.py inject"); return; }
    var d = new Date(), p2 = n => ("0" + n).slice(-2);
    var stem = docId.replace(/-[0-9a-f]{8}$/, "");
    var a = el_("a"); a.download = stem + ".rev-" + d.getFullYear() + p2(d.getMonth() + 1) + p2(d.getDate()) + "-" + p2(d.getHours()) + p2(d.getMinutes()) + ".html";
    a.href = URL.createObjectURL(new Blob([html], { type: "text/html" })); a.setAttribute("data-rev-ui", "");
    doc.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    rev.ui.toolbar.querySelector('[data-rev-act="save"]').removeAttribute("data-dirty");
    rev.toast("Saved " + a.download);
  }
  rev.exportHtml = exportHtml;

  function installPanel() {
    rev.on("action", e => { if (e.detail.act === "save") saveRevisions(); });
    rev.on("changed", () => { rev.ui.toolbar.querySelector('[data-rev-act="save"]').setAttribute("data-dirty", ""); });
    var p = rev.ui.panel;
    panelFilter = el_("input"); panelFilter.type = "search"; panelFilter.placeholder = "Filter pins";

    panelBody = el_("div", "rev-panel-body");
    var foot = el_("div", "rev-panel-foot"), sv = btn_("", "Save revisions"), cp = btn_("", "Copy as Markdown"), cl = btn_("", "Clear all");
    sv.addEventListener("click", () => { rev.emit("action", { act: "save", button: null }); });
    cp.addEventListener("click", copyMarkdown);
    cl.addEventListener("click", () => {
      if (rev.state.pins.length) askIn(cl, "Clear all?", () => { embeddedPins().forEach(function (e) { if (rev.state.deleted.indexOf(e.id) < 0) rev.state.deleted.push(e.id); }); rev.state.pins.length = 0; rev.save(); sync(); rev.toast("All pins cleared"); });
    });
    var hd = el_("div", "rev-panel-head"), x = btn_("Close pin list", "Close", "rev-panel-close");
    x.addEventListener("click", () => { setPanel(false); });
    hd.append(el_("span", "rev-panel-title", "Pin list"), x);
    foot.append(sv, cp, cl); p.append(hd, panelFilter, panelBody, foot);
    panelFilter.addEventListener("input", renderPanel);
    p.addEventListener("keydown", e => {
      var row = e.target.closest(".rev-row"), rows = [...panelBody.querySelectorAll(".rev-row")], i = rows.indexOf(row), k = e.key;
      if (k === "Escape") setPanel(false);
      else if (e.target === panelFilter) { if (k !== "ArrowDown" || !rows[0]) return; rows[0].focus(); }
      else if (!row || e.target.closest("button")) return;
      else if (k === "ArrowDown") (rows[i + 1] || row).focus();
      else if (k === "ArrowUp") (rows[i - 1] || row).focus();
      else if (k === "Enter") locate(row._pin, false);
      else if (k === "e" || k === "E") locate(row._pin, true);
      else if (k === "Delete") row.querySelector(".rev-row-acts button:last-child").click();
      else return;
      e.preventDefault(); e.stopPropagation();
    });
    rev.on("action", e => { if (e.detail.act === "list") setPanel(!rev.state.panel); });
    rev.on("changed", () => { tocSoon(); if (rev.state.panel) { clearTimeout(panelTimer); panelTimer = setTimeout(renderPanel, 120); } });
    rev.on("mode", tocSoon); doc.addEventListener("toggle", tocSoon, true);
    new MutationObserver(muts => {   // html-plan builds its TOC at run time
      var own = n => { return n.nodeType === 1 && n.hasAttribute("data-rev-ui"); };
      if (muts.some(m => !m.target.closest("[data-rev-ui]") && ![...m.addedNodes, ...m.removedNodes].every(own))) tocSoon();
    }).observe(doc.body, { childList: true, subtree: true });
    if (rev.state.panel) setPanel(true);
    paintToc();
  }

  /* ---------- start ---------- */
  function start() {
    rev.state = loadState();
    keep = rev.state.keep;
    stampIds();
    buildUi();
    installPlacement();
    installPins();
    installPanel();
    applyTheme();
    new MutationObserver(applyTheme).observe(root, { attributes: true, attributeFilter: ["data-theme", "class", "style"] });
    new MutationObserver(applyTheme).observe(doc.body, { attributes: true, attributeFilter: ["class", "style"] });
    if (window.matchMedia) {
      var mq = matchMedia("(prefers-color-scheme: dark)");
      if (mq.addEventListener) mq.addEventListener("change", applyTheme);
    }
    window.addEventListener("resize", applyNarrow);
    rev.setMode(rev.state.mode);
    // start-up mode set is not an edit; restored local pins that differ from the file's embedded pins are unsaved
    var sig = function (p) { return [p.id, p.text, p.intent, p.modified].join("|"); };
    var local = rev.state.pins.map(sig).sort().join(";"), embedded = embeddedPins().map(sig).sort().join(";");
    var unsaved = local !== embedded || rev.state.deleted.length > 0;
    rev.ui.toolbar.querySelector('[data-rev-act="save"]')[unsaved ? "setAttribute" : "removeAttribute"]("data-dirty", "");
    applyNarrow();
    probeCollision();
    clearFixedLeft();
    window.addEventListener("resize", queueClear);
    // a side menu that slides in ends its move with one of these
    doc.addEventListener("transitionend", queueClear, true);
    doc.addEventListener("animationend", queueClear, true);
    new MutationObserver(trackMenu).observe(doc.documentElement, { attributes: true, attributeFilter: ["class"] });
    root.setAttribute("data-rev-mounted", "");
    if (memoryOnly) rev.toast("Pins are not saved in this browser - use Save revisions");
    rev.emit("ready", {});
  }
  if (doc.readyState === "loading") doc.addEventListener("DOMContentLoaded", start); else start();
})();
