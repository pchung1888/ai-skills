# Mermaid syntax rules

Loaded from SKILL.md "Diagram syntax" only when a diagram must be mermaid. ASCII stays the default.

**When you do use mermaid**, the syntax rules below keep diagrams renderable across GitHub, VS Code preview, the Mermaid Live Editor, and Confluence's mermaid plugin:

1. **No HTML tags inside labels except `<br/>`.** Specifically: NO `<b>`, `<i>`, `<u>`, `<span>`, `<font>`. Most renderers either sanitize HTML out of labels entirely or fail to parse the line. The only universally supported tag is `<br/>` for line breaks.

2. **No HTML at all inside edge labels** (the bit between `|...|` pipes), quoted or unquoted. The edge-label parser is stricter than the node-label parser. Quoted edge labels like `-->|"label"|` accept colons, commas, slashes — but HTML breaks.

3. **Move complex annotations from edge labels into destination node text.** If an edge label needs more than ~6 words or any styling, put the text into the node it points to and let the edge be unlabeled (or use a minimal `|Bug 1|` style label).

4. **Avoid `#` in unquoted edge labels.** Mermaid uses `#` as a comment char at statement level, and the lexer can get confused even inside `|...|`. Write `Bug 2` instead of `Bug #2`.

5. **Parens with internal commas inside node labels MUST be inside `"..."` quotes.** `node1[UBound(arr, 2)]` breaks; `node1["UBound(arr, 2)"]` works.

6. **Apostrophes are fine inside double-quoted labels** but get fragile when stacked with HTML, parens, and pipes on the same line. If a label has parens + commas + apostrophes + HTML, rewrite it in plain text rather than try to escape your way out.

7. **`classDef` styling works everywhere; inline `style` per-node is harder to reuse.** Prefer `classDef bad fill:#7a1f1f` + `class WX,GX bad` over `style WX fill:#7a1f1f`.

8. **Test in the actual target renderer.** GitHub's mermaid is more permissive than VS Code's; Mermaid Live Editor is more permissive than both; Confluence's mermaid plugin is the strictest of all. The lowest-common-denominator rule: if it works in Confluence's plugin, it works everywhere.

When a diagram doesn't render and the cause isn't obvious, the diagnostic order is: (a) strip all HTML tags, (b) remove all edge labels, (c) simplify to plain ASCII node IDs. If it renders at step (c), reintroduce features one at a time to bisect the breaker.

**History note (2026-05-18):** Added after a walk-mode rendering on a sibling project shipped a mermaid chart with `<b>...</b>` inside both node and edge labels — failed to render in the user's preview environment. The rules above are the conservative subset that survives every renderer tested.
