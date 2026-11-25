# Page mode: map the plan to a walk spec

The walk page rules live in `personal-htsw/references/walk-page.md`. Read them first. This file
says only how a code lesson fills the spec.

## One page or several

A walk page holds 6-14 steps, and the last step is the decision. Count the plan steps.

- 13 or fewer plan steps: one page. Add one decision step at the end.
- More: one page per part, in plan order. Example: `<slug>-web.html`, `<slug>-service.html`,
  `<slug>-install.html`. Each page ends with its own decision step. Link the pages in each
  opening's last point.

## Field map

| Spec field | Code lesson content |
|---|---|
| `title` | The feature and the part, 40 characters or fewer. Example: "Holiday v2, the web part". |
| `idea` | How the parts fit, in one sentence. Example: "One service sends the page and the data." |
| `decision` | Which findings the user wants fixed now and which go to the next version. |
| `opening` | What the code is, what it replaces in ASP, the reading order rule, and how to answer. |
| step `name` | A claim about what the section does. Example: "The URL holds the filter". |
| step `sub` | The file and line range. Example: "BrowsePage.tsx 41-57". |
| step `lead` | The job of the section, as a claim. |
| step `blocks` | A `table` of line range, what it says and what it means. Then `bullets` with the real code in backticks, an "In ASP terms" `table`, a `note` (tone `info`) titled "React pattern here" or ".NET idea here", and an `svg_file` for a runtime flow. |
| step `check` | One "what happens if" question from the step's Tell-me list. Put the others in a `bullets` block headed by `h3` "Also check". |
| step `takeaway` | The section's point in new words. |
| `glossary` | Every React, Vite, TypeScript, .NET and SQL term the page uses. |
| `answers.questions` | One question per open finding: fix now, next version, or drop. |
| `reference` | A section "Findings so far" that links the notes file path. |

Long code does not fit a walk block. Quote 1-5 lines in backticks per bullet, and give the line
range so the user can open the file.

## After the build

- Fix every FAIL line in the spec, never in the HTML, and rebuild.
- Fix cheap MISS lines (a missing check, takeaway or analogy). Report the ones left.
- Report the SCORE line in the chat reply.
