---
name: personal-teach-me-how-to-code
description: Use when the user wants to learn a code base or feature they are weak at, file by file and section by section - a React + Vite page, a .NET 10 service, a feature converted from ASP Classic, or any unfamiliar stack. Trigger on /personal-teach-me-how-to-code, "teach me this code", "teach me how this code works", "explain the React code layer by layer", "code review lesson", "I want to learn this prototype". Not for a one-off question about one function (personal-htsw) or a multi-session concept course with no code (personal-teach).
argument-hint: "<code folder> [--out <folder>] [--notes <file>] [--interactive]"
---

# Teach me how to code

The user learns new code by reading it in build order, one section at a time, with a quiz after each
section. He knows VBScript, ASP Classic, VB6, T-SQL and IIS. Every step maps the new code to one of
those. Real defects found while teaching go into a findings notes file, so a lesson is also a review.

## Inputs

| Input | Meaning | Default |
|---|---|---|
| `<code folder>` | The code to teach. Read-only. Never edit it. | Ask once. |
| `--out <folder>` | Where the plan, page and notes go. | Ask once. Recommend `<repo>/docs/<ticket>/learn/`. |
| `--notes <file>` | The findings notes file. It may sit outside `--out`, for example a next-version notes file beside the learn folder. | `<out>/notes.md` |
| `--interactive` | Teach one step per reply in chat. | Off: page mode. |

The code folder is the source, not a workspace. This skill writes only the plan, the walk spec, its
SVGs, the page and the notes file, and only under `--out` and `--notes`. Those may sit in the same
repo's `docs/` folder, never in the code folder. That keeps the
personal-teach rule "never a code repo as workspace" for everything else.

## Plan first, in build order

1. List the source files. Skip generated and vendored files (`node_modules`, `dist`, `bin`, `obj`,
   `publish`, lock files). Read [references/reading-order.md](references/reading-order.md).
2. Order the files so each file uses only names from an earlier file. A shared part comes before
   the pages that use it. One exception: the entry file (`main.tsx`, `Program.cs` top) comes early,
   because it shows how the app starts. Start with the build file and end with the install scripts.
   One step may cover several small files (under 20 lines each) that do one job together.
3. Split every file of more than 60 lines, or with more than one job, into sub-steps by section
   (8a, 8b, 8c). One sub-step is one job: the screen, the URL and load, the buttons, derived values.
4. Write `<out>/plan.md`: a table `| Step | File | Lines | Topic |` with real line ranges, plus one
   line per step on why it comes there.
5. Run the coverage check. Fix the plan until it passes:

   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/skills/personal-teach-me-how-to-code/scripts/check_plan.py" <out>/plan.md --root <code folder>
   ```

   A gap means a skipped section. Never hand over a plan that prints PLAN FAIL. Tests, generated
   code, CSS, images and pure data files may stay out of the plan. List them under the table with
   the reason. Teach a CSS rule inside the step whose screen needs it.
6. If the code calls a backend (a stored procedure, a database query, an outside API), add
   one step per kind of call: auth or permission, read a list, read one, write. Each step traces
   one request end to end. Read [references/data-boundary.md](references/data-boundary.md).
   If the project has a parity or mapping file, read it first and use its names.

## Each step

Every step, in both modes, has these parts in this order. A full example is in
[references/step-example.md](references/step-example.md).

1. The file and line range, and one sentence on the job of this section.
2. Short real code excerpts, copied from the file. Never write code the file does not have.
   Never cut the key line of an excerpt with `...`. Elide only lines that are not the point.
3. Plain meaning, line by line where it matters, in sentences of 20 words or fewer.
4. The why: what breaks or gets harder without this code.
5. "In ASP terms": map each new idea to what the user knows (`Request.QueryString`, `IsNumeric`,
   `global.asa`, the `Application` object, a COM DLL, an IIS vdir, `Do While Not rs.EOF`).
6. One callout: "React pattern here" or ".NET idea here".
7. An ASCII flow diagram when the section has a runtime flow (one click, one save, one request).
8. Two or three checkable questions: "what happens if" questions with a one-line answer.

A step about an interface shows the whole wiring chain in one place: a table of every class that
shares the name, then the interface, the registration, the caller, the implementation and the
backend call. A backend step adds a mapping table: each parameter, how the result is read, the
old-stack equivalent, and how return codes become HTTP statuses.

Install, deploy and ops scripts are taught from the operator view instead, by
[references/ops-scripts.md](references/ops-scripts.md):

- Open the part with a `Step | File | Lines | Job` table in run order, on the page or in the
  first reply.
- For each script, answer in order: before you run it, what it changes on the box, how you know
  it worked, and when it fails.
- Rollback gets its own step: what it undoes, what it cannot undo, and how to check the old state.
- End the part with a `Symptom | Likely cause | Check | Fix` table built from real script messages.
- Read code lines last, only to explain a failure or a side effect.

Label every claim about the code EXTRACTED, INFERRED or UNKNOWN. Never guess a path, a line or a
value. Read the line before you quote it.

## Page mode (default): low talk

The user reads a page and answers in chat. Build it with the personal-htsw walk page.

1. Read `personal-htsw/references/walk-page.md`. This skill is the one allowed use of a walk page
   for code: one plan step is one walk step.
2. Follow [references/page-mode.md](references/page-mode.md) to map plan steps to the spec.
3. Build and check until `walk-check.py` exits 0:

   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/skills/personal-htsw/walk/walk-build.py" <out>/<slug>.walk.json --out <out>/<slug>.html
   python "${CLAUDE_PLUGIN_ROOT}/skills/personal-htsw/walk/walk-check.py" <out>/<slug>.html --spec <out>/<slug>.walk.json
   ```

4. Reply in chat with only: the page path as a `file:///` link, the plan path, the notes path, the
   check score, and "Answer the Check yourself questions here, by step number."
5. When the user answers, grade each answer as in interactive mode. Add any new finding to the notes.

## Interactive mode

REQUIRED SUB-SKILL: use personal-copilot-talk for the reply shape. One step per reply. The verdict
on the last step comes first, the step comes next, and **Tell me:** comes last.

- Show the plan table in the first reply. When a file splits, show its sub-step table first.
- Grade each answer: "passed", or "half right" plus the correction. Do not move on until the user
  answers the checks or says "skip".
- The user's next-step request ("step 9") moves on. A skipped sub-step is still taught first, in one
  short block, unless the user says skip.

## Findings notes

Format and rules: [references/findings-notes.md](references/findings-notes.md).

- Write each real defect, risk or improvement the moment you see it, with `file:line` and a label.
- Write the user's own ideas and decisions mid-lesson as dated decisions, then continue the lesson.
- Search the notes before you write. If the finding is there, say where. Do not duplicate it.

## Live demos

Show a demo in a browser only when it teaches the step (outline page parts, watch one network
call). First call `list_connected_browsers` and let the user pick the browser by name. Open only
`localhost` tabs. Close the tabs you opened when the demo ends.

## Red flags

| Thought | Do this instead |
|---|---|
| "This section is small, I will fold it in" | Teach it as its own sub-step. The user caught a skipped 8b. |
| "the user asked for step 9, so 8b can go" | Teach 8b in one short block first, unless they say skip. |
| "I remember what this line does" | Read the line. Quote the real code. |
| "The page is enough, no notes needed" | Write every finding to the notes file. |
| "This finding is close to one in the notes" | Point to the existing entry. Do not add a twin. |
| "The class name appears in many steps, so the user knows it" | Show the wiring chain once, in full, in its own step. |
| "Install scripts are code, so teach them like code" | Teach what the operator sets up, sees, checks and undoes. Code lines only to explain those. |
