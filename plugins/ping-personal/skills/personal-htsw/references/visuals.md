# visuals -- pick the chart or table by the question it answers

Read this before you draw anything for an htsw HTML page: a `--walk` page (walk-page.md) or a Deep
HTML page (now.md). A picture earns its place only when it answers one question the reader has.
Name that question first, then pick the shape from the tables below.

## Charts

| Chart | Question it answers | Pick it when | How to build it |
|---|---|---|---|
| Phase roadmap (lanes by release) | Which part changes in which release, and what stays fixed? | A plan runs over several releases or phases and some parts never change | `svg_file`: a phase band on top, one column per release (width shows length), one row per part. Outline the row that never changes. Use a range column ("7.60-7.80") for work with no set order |
| Routing or mechanism | How does one request reach the old or the new part? | One switch, router or rule decides where work goes | `svg_file`: boxes and arrows, one `--hi` arrow for the path that matters (starter in walk-page.md "Draw the mechanism") |
| End-goal staircase | How do small approved upgrades add up to one fixed target? | The reader fears one big change, and the plan is many small ones | `svg_file`: a step path climbing to one end-goal box. Stagger labels on two rows. Caption says step heights show the idea, not measured sizes |
| Swimlane (who does what) | Who does each step, and where does a failure send work back? | Several people or teams hand work along, and some steps are gates | `swimlane` block (walk-page.md "Block types"). One lane per person or group, one row per step, `gate` and `back` for every review that can fail |
| Hero picture | What is the whole plan in one picture? | Always, in the hero of a walk page | `hero_visual` (walk-page.md "Hero picture") |
| Roadmap at a glance | What is the real plan, before the step-by-step walk? | The plan has its own shape (releases, lanes) that a step chart cannot show | `flow_visual`: your svg leads the flow section and the clickable step chart folds under it |
| Before and after | What changes for the reader? | A today-versus-later contrast | `ba` block |

Rules that came from real corrections:

- One concept per chart. Two concepts are two charts, and usually two steps.
- When the story changes, redraw the chart from scratch. Patching box by box causes collisions.
- A chart that shows a design also shows its future seam (for example, the login source can be swapped).
- Every gate that can fail shows a loop-back arrow to the step where work restarts.
- Before you draw people, confirm three things for each step: who owns it, who approves it, and whether it is optional.
  Credit each skill or tool to the person who builds it. Show humans running the AI, never "AI does everything".
- Use the reader's own word for the main work step ("Implementation"), and mark it with the one `--hi` outline.
- A box that the generator cannot place cleanly (a long label, many lanes) is a sign to shorten the label, not to shrink the font.
- Use `markerUnits="userSpaceOnUse"` on arrow markers, so a short arrow does not hide its label (checker: `svg-marker-units`).
- Keep each label inside its box (checker: `svg-text-fits`). Path data must parse (walk-build refuses "M12748V1014").

## Tables

Every table gets zebra rows (alternate row color in light and dark mode). The walk builder and the
md-to-html themes add them; never turn them off.

| Table shape | Columns | Pick it when |
|---|---|---|
| Risk with its fix | Concern / What could happen / How we stop it / Checked | A boss or coworker must trust the plan. Never list a risk without its fix in the same row |
| Review timeline | When (release) / Item / What a person reviews / Why it matters | Items need human review across releases. Say "items that need human review", not "risky parts" |
| Lifecycle with proof | Step / Who / What happens / Proof it leaves | Each stage (Plan, Build, Release) must leave evidence. One table per stage |
| Handoff directions | Direction / How it works / Example | Old and new parts link both ways. Name a real example per row |
| Release map | Release / What it converts / Ticket | Releases map to tickets or deliverables |
| Path compare | Event / Option 1 / Option 2 | Two delivery paths. Add a `ba` block with `"kind": "options"` for what each gives and costs |
| Decision record | Topic / Answer (with who and when in the section title) | Record a decision. Quote the stakeholder's words verbatim |

## Words in charts and tables

- Name the category first and the example second: "simple CRUD pages, such as Holiday". A single
  example as the headline makes the reader fixate on it.
- Tie each example to what it proves ("CRUD pages build the router and the me interface").
- Give each speaker or source its own note color and keep it on every step (`note` tones `a`, `b`, `c`).
- Merge parallel annotation boxes ("will be removed", "suggestion") into one actionable box with its reason.
