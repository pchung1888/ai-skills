---
name: personal-lesson-ui
model: haiku
description: UI / frontend lessons -- React, Next.js, TypeScript TSX patterns, CSS, layout, hydration, app router. Invoked by personal-lesson master router when classification matches UI keywords, or directly via /personal-lesson-ui or natural phrases like "lessons about UI", "lessons about React", "lessons about Next.js", "lessons about styling", "lessons about components". Appends new lessons to ~/.claude/lessons/personal-lesson-ui.md and reads from there for browse mode.
user_invocable: true
---

# /personal-lesson-ui -- UI / Frontend Lessons

Lessons about the browser-side of any project: React components, Next.js App
Router, TypeScript TSX patterns, CSS, layout, hydration, and general frontend
behavior. Not specific to any single project.

---

## Capture flow (invoked by master router or directly)

### Step 0 -- Hard-rule gate (when invoked directly)

If invoked directly (not via the master router), check CLAUDE.md and
.claude/rules/*.md for hard rules that the incoming lesson would duplicate. If
the lesson IS a duplicate of a hard rule, reply:

> This is already a hard rule in CLAUDE.md / .claude/rules/. Nothing appended.

Then STOP. If invoked via the master router, skip Step 0 (the router already
ran it).

### Step 1 -- Duplicate check

Grep BOTH sources for a distinctive phrase from the incoming lesson (a component
name, an error string, a 5-word snippet of the Rule):

1. `~/.claude/lessons/personal-lesson-ui.md` (user-scope appends, skip if absent)
2. The `## Seed Lessons` section of THIS file (`personal-lesson-ui/SKILL.md`)

If either matches, reply:

> Duplicate: already recorded as "<existing title>" in personal-lesson-ui.
> Nothing appended.

Then STOP.

### Step 2 -- Append

Use Edit (or Write if the file does not exist) to append before the end of
`~/.claude/lessons/personal-lesson-ui.md`, using the standard format:

```markdown
---

## [SEVERITY] [Short Title]
**Domain:** ui
**Discovered:** [YYYY-MM in America/New_York -- never UTC]
**Context:** [1-2 sentences -- when this surfaced]
**Problem:** [What goes wrong without this knowledge]
**Rule:** [Actionable imperative -- concrete thing to do or avoid]
**Example:** [Optional: wrong vs right snippet, error message, or file reference]
```

Create `~/.claude/lessons/personal-lesson-ui.md` if absent. The file should
begin with a brief one-line header on creation:
`# Lessons -- UI / Frontend (user-scope, auto-appended)`

After appending, confirm: "Appended to ~/.claude/lessons/personal-lesson-ui.md."

---

## Browse mode

When asked "show me UI lessons" or "lessons about <topic> in UI":
1. Read `~/.claude/lessons/personal-lesson-ui.md` if it exists.
2. Also read the Seed Lessons section below.
3. Search for the user's term across both sources.
4. Quote lesson text verbatim -- do not paraphrase.

---

## Seed Lessons

The lessons below are cross-project reference seeds. They show the format and
record patterns likely to recur in any React/Next.js/TypeScript project.

---

## CAUTION TypeScript Recharts Tooltip Formatter Must Use `unknown`, Not `number`
**Domain:** ui
**Discovered:** 2026-04
**Context:** TypeScript strict mode rejects `formatter={(v: number) => ...}` on
a Recharts Tooltip. The inferred type is `ValueType` (union), not `number`.
**Problem:** TSC errors at build time; the component fails to compile.
**Rule:** Use `(v: unknown)` plus `Number(v)` cast in every Recharts Tooltip
formatter: `formatter={(v: unknown) => [fmt(Number(v)), 'Label']}`.
**Example:** Any charting library that exposes a generic callback type -- reach
for `unknown` plus an explicit cast rather than assuming `number`.

---

## CAUTION `@ts-expect-error` Directive Must Be a Line Comment, Not a JSX Comment
**Domain:** ui
**Discovered:** 2026-04
**Context:** Suppressing TypeScript errors on a JSX prop in a React component.
**Problem:** `{/* @ts-expect-error */}` (JSX comment form) is NOT recognized by
TypeScript as a directive -- the error still fires. The JSX comment is treated
as a node, not a directive.
**Rule:** Always use `// @ts-expect-error` as a plain line comment on the line
directly above the problematic JSX prop -- never the JSX comment form.
**Example:**
```tsx
// @ts-expect-error: third-party type incompatibility
<Chart dataKey={key} fill={palette[i]} />
```

---

## CAUTION "MMM D" Date Strings Sort Alphabetically, Not Chronologically
**Domain:** ui
**Discovered:** 2026-04
**Context:** Displaying and sorting bank statement transactions with dates like
"Mar 20" or "Apr 5" -- month abbreviation plus day, no year.
**Problem:** `String.localeCompare` on "MMM D" strings gives alphabetical order
("Apr" < "Dec" < "Feb" < "Jan"), not date order. Data appears scrambled.
**Rule:** Build a real ISO date string for sort keys using a month-name-to-number
lookup plus the statement's year context. Never sort on the raw "MMM D" string.
**Example:**
```ts
const MMM: Record<string, number> = { Jan:1,Feb:2,Mar:3,Apr:4,May:5,Jun:6,Jul:7,Aug:8,Sep:9,Oct:10,Nov:11,Dec:12 };
const toISO = (date: string, monthKey: string) => {
  const [mmm, d] = date.split(" ");
  const [yr, mo] = monthKey.split("-").map(Number);
  const dm = MMM[mmm] ?? 1;
  const year = dm > mo + 1 ? yr - 1 : yr; // year rollover guard
  return `${year}-${String(dm).padStart(2,"0")}-${String(Number(d)).padStart(2,"0")}`;
};
```
Critical: the transaction date month can differ from its statement month key --
always use the statement's year context for the rollover guard.

---

## NOTE Inline Theme-Boot Script Requires `suppressHydrationWarning` on `<html>`
**Domain:** ui
**Discovered:** 2026-05
**Context:** Adding a theme-boot script that mutates `data-theme` on `<html>`
before React hydrates, to prevent a flash of the wrong theme on page load.
**Problem:** React warns about SSR/client mismatch on `<html>` because the
server-rendered fallback differs from the client preference. Removing the boot
script "fixes" the warning but brings back the theme-flash bug.
**Rule:** Add `suppressHydrationWarning` on the `<html>` element when an inline
theme-boot script is present. The mismatch IS the design -- suppress the warning,
not the script.
**Example:** `<html lang="en" suppressHydrationWarning>` in the root layout.

---

## CAUTION Spec-Driven UI Ports Need a Feature Checklist, Not Just Visual Matching
**Domain:** ui
**Discovered:** 2026-04
**Context:** A complex multi-tab UI was ported to a new framework and restyled.
Several interactive elements (sliders, output cards, charts, formulas) were
silently dropped because the new version looked acceptable.
**Problem:** A restyle can look complete while silently omitting interactive
behavior, output cards, formulas, or specific chart elements from the original
spec.
**Rule:** For any spec-driven UI port, build an explicit checklist of every
interactive element, output card, chart, reference line, and formula from the
original spec or reference implementation. Check off each item individually
before declaring the port complete.

---

## CAUTION Simulator State Must Persist Across Page Reloads
**Domain:** ui
**Discovered:** 2026-04
**Context:** A planning tool with user-tunable sliders reset all settings on
page reload because it used plain `useState` with no persistence.
**Problem:** Planning tools feel broken if a user tunes parameters and the page
forgets them on refresh or tab navigation. Users re-tune repeatedly; trust erodes.
**Rule:** Store user-tuned simulator settings in `localStorage` from a
`'use client'` component. Load once in `useEffect` with a `settingsLoaded` guard,
and only write to `localStorage` after the initial load completes to prevent
overwriting saved state on mount.
