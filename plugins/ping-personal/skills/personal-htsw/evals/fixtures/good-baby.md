_Explaining: React TodoApp (`docs/htsw/dogfood-sample.tsx`) -- useTodos hook, useState, useEffect, verifyAttrs, data-verify-* attrs, registerUnit · purpose: baby_
_For: junior front-end developer -- knows JavaScript and the DOM, has heard "useState" and "useEffect" once but cannot say what they do, knows what an HTTP request is and what HTML attributes are_

## How the TodoApp loads, paints, and gets verified -- the office building

**TL;DR -- the core idea:**

- 📦 **errand boy (`useEffect`)** -- runs once when the office opens; walks to the back room and brings back the todo rows.
- 📦 **whiteboard on the wall (`useState`)** -- the value the whole room reads; React repaints the room every time the whiteboard changes.
- 📦 **receptionist (`verifyAttrs()`)** -- every repaint, she copies the latest counts from the whiteboard onto Post-its and sticks them on the outside of the door.
- 🏷️ **index card from the building manager (`props`)** -- slid under the door when the room opens; the title comes from the building manager and cannot be rewritten from inside.
- 🏷️ **Post-its on the door (`data-verify-*` attrs)** -- the only surface the inspector reads; he never enters the room.

### 📦 How this shit works

The office opens for the day (the page mounts the `TodoApp` component). Before the painters even pick up their brushes, **the errand boy (`useEffect`)** (the character who runs exactly once when the room first opens) walks to the back room and rings the bell at the counter.

**The warehouse clerk (`fetchTodos`)** (the person behind the counter who pulls rows off the shelves) hears the bell, walks back into the stacks, gathers the todo rows, and carries them out to the front. The errand boy takes the stack and returns to the main room.

Back at the room, the errand boy writes the new value onto **the whiteboard on the wall (`useState`)** (the shared surface every component in the room reads). Two whiteboards live on this wall, actually -- one holds the `todos` list, the other holds the `loading` flag. The moment a whiteboard changes, React tells the painters to repaint the room. That is React's one job.

During that repaint, the visible component reads both whiteboards, counts how many todos are done, and hands the totals to **the receptionist (`verifyAttrs()`)** (the person who bridges the inside of the room and the hallway). She takes the totals, copies them onto fresh Post-its, and sticks them on the outside of the door as `data-verify-total`, `data-verify-done`, and `data-verify-loading`.

**The index card from the building manager (`props`)** was already there -- slid under the door when the room first opened, written by whoever rendered `<TodoApp title="...">` from the outside. The room reads `props.title` to know what headline to paint, but cannot rewrite the card from inside.

Down the hallway, **the inspector (Agent / Claude)** walks past the door and reads the Post-its. He never enters the room. He never touches the whiteboards. He never visits the warehouse. He reads only what the receptionist stuck on the outside.

```
Page mounts the component (the office opens for the day)
   |
useEffect fires once (the errand boy walks to the back room)
   |
fetchTodos resolves with rows (the warehouse clerk hands the stack over the counter)
   |
setTodos and setLoading run (the errand boy writes new values on both whiteboards)
   |
React repaints the component (painters read the whiteboards, redraw the room)
   |
verifyAttrs runs during repaint (the receptionist copies the counts onto Post-its)
   |
data-verify-* attributes go onto the div (the Post-its are stuck on the outside of the door)
   |
Agent reads data-verify-* from the DOM (the inspector walks the hallway and reads them)
   -- never sees useState (cannot reach the whiteboards)
   -- never sees fetchTodos (cannot enter the warehouse)
```

**Why two whiteboards instead of one:** `todos` and `loading` change at different moments. The errand boy flips `loading` from `true` to `false` only after the warehouse hands over the rows. Until then, the room paints a "Loading..." view. Two whiteboards mean React can repaint at each step without confusing the two states.

**Why the cleanup function (`cancelled = true`):** if the room closes before the warehouse clerk finishes (the component unmounts mid-fetch), the errand boy might still come back holding rows. The `cancelled` flag tells him "the office is closed, drop the stack." Without it, he tries to write on a whiteboard that no longer exists -- React logs a warning.

### Watch out for

- 🧠 The receptionist (`verifyAttrs()`) runs DURING the repaint, not after. If you call `setTodos` and synchronously inspect the DOM in the same tick, the Post-its may still show the previous render's values.
- 🚧 **`registerUnit`** (the nameplate posted in the building directory -- it announces the room exists, nothing more) lives in a sibling spec file (`todoApp.verify.ts`). It does NOT call `verifyAttrs`; it only tells the registry "a unit named TodoApp exists." If the room registers but never has the receptionist run, the door stays blank: a silent verify gap.

### Cast of characters

| Jargon | Analogy | What it actually does |
|---|---|---|
| `useEffect` | errand boy who runs once when the room opens | runs the fetch callback once on mount; sets up a cleanup function for unmount |
| `useState` | whiteboard on the wall the whole room reads | holds a value the component re-reads on every render; React redraws on every change |
| `fetchTodos` | warehouse clerk who pulls rows from the shelves | async function that returns the todo rows from the API |
| `verifyAttrs()` | receptionist who copies the whiteboard onto Post-its | takes a map of values and returns a props object of `data-verify-*` attributes |
| `data-verify-*` | Post-its on the outside of the door | HTML attributes the Agent reads from the rendered DOM |
| `props` | index card from the building manager | values passed in by the parent component; immutable from inside the room |
| `registerUnit` | the room's nameplate posted in the building directory | records that a unit exists in the registry; does not itself stamp Post-its |
| Agent / Claude | inspector walking the hallway | reads `data-verify-*` from the DOM; never sees React state or fetch internals |
