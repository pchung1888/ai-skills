# code-explain — the deep file-by-file + line-by-line walkthrough playbook

## What this is for

You point at a **code change** (a diff, a commit, a branch-vs-master delta) or a **piece of source**, and you want it taught the way you'd teach a new teammate who has to maintain it: **why** it exists first, then **what changed where**, then the load-bearing code **line by line** in plain English. The output is a teaching document — the kind you'd hand to a colleague who needs to understand *and defend* the change.

It is the deep sibling of `walk`. Where walk gives you the shape, code-explain gives you the maintainable, defensible, line-level understanding.

## code-explain vs walk — when to use which

| | `walk` | `code-explain` |
|---|---|---|
| Question | "How does this work?" | "Walk me through this change, line by line, so I can explain *why* we did it." |
| Depth | Quick explainer — the shape, the knobs, the gotchas | Deep — every load-bearing line annotated, every file accounted for |
| Length | ≤ 700 inline / ≤ 1200 persisted | generous (≤ 3000 inline / ≤ 4000 persisted) — line-by-line needs room |
| Opens with | The mechanism | **The WHY** — the problem the change solves, stated before any code |
| Code | Source quotes are punctuation, not the artifact | Code blocks ARE the artifact; annotation tables sit next to them |
| Default subject | A feature / file / system as it stands | A *change* (diff/commit), though it works on a single file too |

Rule of thumb: if the user says "line by line", "file by file", "explain this change so I can hand it off / defend it / show my boss-the-engineer", or points at a diff and wants depth — that's `code-explain`. If they just want to understand how something works, that's `walk`.

## Source resolution

| Input | Source |
|---|---|
| A diff / commit hash / "the change on this branch" | `git diff <base>...HEAD` (or `git show <hash>`) — read the real lines at their real line numbers |
| A file path | Read that file; if explaining a *change* to it, pull the diff too |
| No source | The current conversation / the change just discussed |

**Verify line numbers against the live file, not the diff's `@@` hunk headers** — hunk headers drift once the file has moved a few edits past the diff. When the deliverable is line-level precision, `Read` the file at its real offsets before citing a line. A citation that's off by three silently destroys the reader's trust in the whole document.

## Output — inline by default, save on request

code-explain is **inline by default**, like every other htsw mode — render it in the chat.

**Write a `.md` file only when the user asks** ("save it to X", gives a destination path, or says "write the doc"). When you do save it, match the destination repo's house style for docs (e.g. an H1 title + a blockquote metadata header — Audience / From / Source / Companions), but keep the validator-required skeleton intact: the `_Explaining: … · purpose: code-explain_` citation line first, then the `##` title, TL;DR, and HOW-THIS-WORKS section. The citation line doubles as a provenance stamp on the saved doc.

This is the one place code-explain differs from htsw's blanket "never writes files" rule — and only on explicit request.

## The voice — same as walk

Plain English, blunt, **translate every piece of jargon on first use** (the reader may not know what `ServicePointManager`, `RST`, or `marshalling` means — say it in human terms, then name it). Mode 2 (salty) is allowed when a design choice is genuinely weird-but-works ("this part's a goddamn weird choice, but it works because X"). No f-word. No praise-washing. The inline `🌮` is allowed once or twice for a genuinely elegant bit; inline `🔴` once or twice for something genuinely broken the reader must know about (with a `→ note:`/`→ ask:` arrow + citation).

## Honest protocol (plain English)

- If you can't tell what a line does, say "I can't tell from this — read X to confirm." Don't invent behavior.
- Inferring from naming/context → lead with "looks like" / "**most likely**".
- Don't fabricate line numbers, file paths, or function signatures to round out a table. Read the file and cite what's actually there.
- If a "change" turns out to be a no-op (encoding churn, whitespace), **say so and tell the reader to ignore it** — don't manufacture meaning.

## Required structure (the contract)

A code-explain rendering has these sections. The validator checks the **bold** ones mechanically.

### 1. Citation line (REQUIRED)
First line: `_Explaining: <source> · purpose: code-explain_`

### 2. Title (REQUIRED — descriptive, names the change)
A `##` heading naming the change and ideally its point — e.g. `## What changed in parseConfig — and why the retry path works now`. Not generic (`## Code walkthrough` fails). No `🌮` opener.

### 3. TL;DR — the core idea (REQUIRED, descriptive label)
`**TL;DR — the core idea:**` (or "short version" / "why this exists"). 2-4 bullets, navigation icons (`▶ ⚙ 🧠 🚧 📍`) or none. NOT a verdict label (`ship it` / `block this`).

### 4. Why we did it / The problem (REQUIRED — the WHY, first)
**Lead with the reason the change exists**, before any line-by-line. This is the defining feature of code-explain — the single most load-bearing sentence is usually the one thing the old code did wrong (or the gap the new code fills). State it, prove it (a citation, a reproduced error, a spec line), and — when it applies — say plainly "this is the whole reason for the change."

### 5. File-by-file map (REQUIRED)
A table (or per-file `## File N` headings) listing every file touched, how many lines, **whether it's a real change or noise** (build artifacts, encoding churn — call them out so the reader doesn't hunt for meaning), and one line on what it is. This is the reader's heat map: where to spend attention.

### 6. How this shit works (REQUIRED — the HOW-WORKS signature, `###`)
One of the recognized HOW-WORKS headers (`### How this shit works`, `### Under the hood`, `### The plumbing`, etc.). 30+ words. Hedge inferred cause-effect chains (`most likely`, `appears to`).

### 7. Line-by-line, per load-bearing file (the body — REQUIRED to have ≥1 code block)
For each load-bearing file: a fenced code block quoting the real lines, then an annotation **table** (`| Line | What it says | What it means |`) or annotated prose. **Adaptive depth** — go line-by-line on the load-bearing files; *group* the mechanical/trivial lines ("lines 2105-2125 are boilerplate binding setup — unchanged"). Don't paste 150 lines and annotate 3; don't annotate 150 lines that don't matter. Mirror the change's own weighting.

### 8. Honest caveats (OPTIONAL but usually present)
The known rough edges — straight from the code's own comments where possible. `🚧` for known-wart-that-works, `🔴` for genuinely broken. Tell the reader what NOT to over-claim.

### 9. Sources / where to look (OPTIONAL)
Citations for any external fact (a framework limitation, an RFC), plus 1-3 files to read next. Don't invent links.

## Length

Generous dual cap — line-by-line of real code legitimately runs long.

- **Inline** (`--input-string`): ≤ 3000 words
- **Persisted** (`--input-file` / `--examples-file` / `--persisted`): ≤ 4000 words
- Per-`###`-section soft warning at > 600 words (advisory; does not fail). If a single file's section blows past that, consider splitting it or grouping more of its trivial lines.

## What code-explain does NOT do

- Grade the change (that's `pr`). No tier title, no verdict TL;DR.
- Sanitize for a non-engineering audience (that's `boss`).
- Paste raw code with no translation. Every block gets plain-English annotation.
- Write a file unless explicitly asked.

## Validator

```bash
python3 .claude/skills/personal-htsw/personal-htsw-check.py --input-file <your-code-explain-rendering.md>
```

Enforced: citation with `purpose: code-explain`; descriptive non-generic title; TL;DR present with a descriptive (non-verdict) label; a HOW-THIS-WORKS `###` section (≥30 words); a WHY framing; a file-by-file map; ≥1 fenced code block; no verdict-icon H2 opener; length under cap. The honest protocol, jargon-translation, and adaptive-depth rules are human-readable contracts the author carries — the validator checks shape, not truth.

## Examples

`references/examples/code-explain-examples.md` — a compact worked rendering.
