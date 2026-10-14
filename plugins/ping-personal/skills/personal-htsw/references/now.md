# now -- what is going on right now

## What this is for

The person looks up from a long session and asks "where are we, and what do I do next?".
Typed as `/personal-htsw now`, it answers in the chat. The ping-hud Simple button sends this file
and SKILL.md's "Explaining sentences" and "Language switch" sections to a side call and shows the
answer in the Explanation pane instead. The source is always the current conversation (in the
pane's Quick context: the last question and reply). Without `--deep --html`, now mode writes no files.

## Required structure (in this order)

1. **Verdict** -- 1-2 lines: where the work stands and the one thing that matters next.
2. **Flowchart** -- a small text flowchart of the work: done -> doing -> next. Mark the
   current step. Top to bottom, one box per line, a `|` then a `v` between boxes (SKILL.md
   "Diagram syntax"), at most about 8 boxes. Never two boxes on one line.
3. **What you need to focus on** -- a table with exactly these columns:

   | When | Your job | Time |
   |---|---|---|
   | now | answer the question about X | 1 min |

   Only the person's own jobs (decisions, clicks, checks), not the assistant's work.
   Time is a rough estimate, labeled as one.
4. **Why this shape** -- 2-4 lines: why the work is ordered this way, in plain words.
5. **TL;DR** -- at most 5 bullets, each starting with an action verb.

## Rules

- Layman terms, but name every technical term and gloss it once in one sentence.
- Every claim about state (a test passed, a file changed) comes from the conversation; if the
  conversation does not show it, say it is not known rather than guess.
- No verdict tier titles, no icons. ASCII punctuation only; Chinese text is allowed with
  --cantonese (still ASCII `,` `.` `"`, no full-width marks).
- Keep it under about 40 lines; depth belongs in `walk` or `code-explain`.
- Check a saved rendering with `python htsw-check.py --purpose now --input-file <file>` (now output
  has no citation line, so the purpose is given on the command line).

## Deep HTML (`now --deep --html <path>`)

Typed in the chat, the steps below run there. The ping-hud Deep HTML button asks a side call for
the Markdown (step 1) and then saves and renders it itself (steps 2-3), showing the link and an
Open in browser button in the Explanation pane. `<path>` is in the bound goal's folder, like
`docs/mod/2026-10-08-1441-deep.html`, or `docs/explain/...` when no goal is bound.
Same source (the current conversation); `<path>` is only where the page goes.

1. Write the explanation as Markdown next to `<path>` (same name, `.md`). Start it with
   frontmatter `title:`, `eyebrow: htsw deep` and `interactive: true`, so the page gets comment
   boxes, Copy buttons, Day/Night and Respond. Then a `# <title>` line that names what is being
   explained, and right under it one line `**You asked:** <the subject, in a sentence>`, so the
   page says what it answers before any section. Structure:
   - the now-mode sections above (verdict, flowchart, focus table, why this shape, TL;DR), each a `##`;
   - one per-phase table per phase of the work: What was done | Evidence | Status;
   - a **Glossary** table: Term | Meaning (one sentence), for every technical term used;
   - an evidence label on each claim: EXTRACTED (seen in the conversation or a file),
     INFERRED (with its one-sentence basis), or UNKNOWN.
   Draw with md-to-html's html-plan blocks (syntax: personal-md-to-html SKILL.md "html-plan blocks"):
   - the flowchart is a `flow` block (real boxes and arrows), never a text flowchart or Mermaid;
   - code that matters is a `code-pins` block with a note on the line that matters;
   - a lifecycle is a `machine` block; a call chain is a `calls` block; command output is a
     `terminal` block (`{g}` marks a success line green);
   - each "watch out" item is a `note` block (warn, risk or info);
   - a choice the person must make is an `ask` block with the recommended option `checked`.
   Use a block only where it shows something real; the htsw voice, slang and headers stay.
   Exact syntax (copy these shapes; the pane does not send md-to-html's own docs):

   ````
   ```flow
   Merge the PR (done)
   Install 0.34.0 (done)
   Press Deep HTML (you are here)
   ```

   ```note warn
   One or two plain sentences. Tones: info, warn, risk, ok, idea.
   ```

   ```ask
   What should happen next?
   - [x] The recommended option
   - [ ] The other option
   ```

   ```terminal
   $ the command
   {g}the success line{/g}
   ```

   ```code-pins
   path: plugins/ping-personal/hooks/register.tsx
   lines: 1176-1185
   pins:
     1182: What this line does, in a clause.
   ```
   ````

   A `flow` is one step per line, top to bottom. Each `note` is its own block, one per item.
2. Render it: `python "${CLAUDE_PLUGIN_ROOT}/skills/personal-md-to-html/md-to-html.py" <md> --out <path>`.
3. Print the link to `<path>` (a `file:///` link and the plain Windows path) and stop.
   The chat reply is the verdict plus the link, not the whole page.
4. ASCII only in the Markdown (no em-dashes, smart quotes or Unicode arrows).
