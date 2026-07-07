# UI mode -- live mockup artifact

In UI mode the HTML artifact IS the prototype. Each of the N options is a real,
clickable mockup the user can look at and compare, not a description of one.

## Before building: learn the host style

The output has to "get the style match" -- it should look like it belongs in the
target repo, not like a generic Bootstrap page. So before generating mockups:

1. Find the host design system. Look for design tokens / theme files:
   `tailwind.config.*`, `:root { --... }` CSS custom properties, a `theme.ts`,
   a `tokens.css`, a component library import. Grep for `--color`, `--font`,
   `palette`, `theme`.
2. Extract the real values: primary/accent colors, font families, border-radius,
   spacing scale, shadow style. Use THOSE in the mockups.
3. If the repo has no design system (or this is a greenfield feature), pick one
   coherent aesthetic and state that you chose it (it is a SUGGESTION, not the
   host's confirmed style).

## Matching an EXISTING surface -- fidelity from real artifacts

If the prototype reproduces a screen that already exists (a page in the host app, a
design comp, or screenshots the user gave you), those artifacts are the spec -- not a
text description of them:

- Read the real source (the actual component/template + its styles) and inventory the
  controls before writing any HTML. The reference screenshot is the cross-check.
- Copy the real CSS class definitions / token values inline; base64-embed the real
  icons (find them in the source) -- never substitute text links or emoji.
- Pass the reference image paths to any builder subagent and require it to Read the
  images. A prose summary of a screenshot does not count and produces rejected layouts.
- Greenfield (no existing surface): this does not apply -- build from the brainstormed
  intent and the chosen aesthetic instead.

## Layout of the artifact

- One self-contained `.html` file. All CSS inline or in a single `<style>`. No
  external fonts/CDN/network calls -- it must render offline in `/browse`.
- Show the N options **side-by-side** (CSS grid/flex) for <= 3 options, or **tabbed**
  for 4+ so each mockup gets real width.
- Each mockup is a faithful rendering of that approach -- real buttons, real layout,
  realistic placeholder copy and data. Interactive where it clarifies the approach
  (a tab that switches, a toggle that shows state).
- Pin the **option card** (summary / pros / cons / cost / risk) next to or under each
  mockup so the visual and the tradeoffs are read together.

## Distinctness

The options must differ in UX mechanism, not paint. "Same layout, blue vs green" is
one option, not two. Genuinely distinct examples: a wizard vs a single dense form vs
an inline-edit table; a modal vs a slide-over vs a dedicated route; a card grid vs a
data table vs a kanban board.

## Iterating (phase 5)

Each pass: open in `/browse`, screenshot, ask "does this mockup actually look like the
host app, and does it make the tradeoff obvious?" Fix the weakest mockup, re-preview.
Stop when a pass adds nothing.

Keep the two verification gates separate (see SKILL.md Phase 8). The behavior gate
(interactions fire, no console errors) is NOT the visual gate. When matching an
existing surface, the visual gate means reading your screenshot AND the reference
image together and comparing region by region until they match -- "it works" is not
"it looks right." Run `scripts/check_prototype.py` on each built file to hold the
mechanical self-containment floor (no external resources, base64 icons, no
position:fixed, ASCII).
