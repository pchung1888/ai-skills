_Explaining: YouTube 0oXOOlqVu5M "So I tried Matt's skills..." (38 min, auto-captions, 7,683 words) · purpose: walk_

## What this video really does - a streamer road-tests two skill packs

**TL;DR - the core idea:**

- ▶ **Two public skill packs get audited** against his own usage, not installed wholesale.
- ⚙ **Unslop is the hook** - one markdown file made his agents readable.
- 🧠 **Copy-paste the markdown** to try a text-only skill without installing.
- 📍 **The real lesson** - read every skill, steal only what fits you.

### ⚙ How this shit works

OK so the narrator is a TypeScript YouTuber who calls himself the second-best one, because Matt Pocock is number one [0:00]. He had been eyeing two skill repos for months: Matt Pocock's skills, which he says sit at 200K+ stars and in GitHub's top 10 [0:31], and pstack, built by "Potato" (Lauren), an ex-React-core engineer now at Cursor [1:32]. He doesn't install them blind. He points an agent at his own session history across his machines, has it rank every skill by fit, and then grabs the winners [4:35].

The whole rabbit hole started with one skill. He saw prose Potato's agents wrote and thought it looked "significantly less cringe" than what Claude gave him [5:06], so he grabbed `unslop`, ran the same T3 Code question with and without it, and the difference was stark enough that reading un-slopped output now "hurts me" [10:46]. The rest of the video is him walking the other skills, mostly by pasting the markdown into a live agent and watching what it does.

```
 1  Point an agent at your own usage history
    |  it reads threads across all your machines
    v
 2  Agent ranks each skill in the pack by fit
    |  writes a doc: fit, benefit, one-line why
    v
 3  Read the top skills' markdown yourself
    |  copy-paste text-only ones into a live session
    v
 4  Keep the winners in one "fleet" repo
    |  the agent syncs them to every machine
    v
 5  Ignore the rest
```

### The skills that made the cut

| Skill | Pack | What it does | His take |
|---|---|---|---|
| `unslop` | pstack | Strips AI tells from writing | "fundamentally changed my willingness to read" [35:44] |
| `grilling` / grill-with-docs | Matt | Interviews you about a plan, decision tree in rounds | "I'm seeing the light" [19:27] |
| `diagnosing-bugs` | Matt | Model-invoked root-cause hunting | Agents find root cause faster [14:52] |
| `wizard` | Matt | Walks a human through steps only they can run | Installed on every machine [27:35] |
| `blast-radius` | pstack | Finds what a change breaks somewhere else | Uses it "a ton" [33:13] |
| `arena` | pstack | Parallel attempts, pick the best, graft the rest | "cost me hundreds of dollars" [32:12] |

### Watch out for

- 🧠 He argues a skill's `description` is really a **trigger**, not a summary - it exists to make the model pull the skill in at the right moment, like a thumbnail exists to get the click [5:36]. That's directly relevant to how the ping-personal descriptions are written.
- 🚧 He roasts Matt's skills for being full of em dashes (nine on one page) and suspects that's why his agents started emitting them again [15:22]. Goddamn ironic for a writing-quality video, but it's a real mechanism: models copy the style of what's in context.
- 🚧 pstack is Cursor-flavored; a handful of skills lean on Cursor-only behavior [32:43].
- 🧠 The `unslop` he reads on screen has an "add soul" section and a self-audit step [6:38]. The copy ported into ping-personal (commit `bc697d0`) has neither, so upstream **most likely** trimmed it after this video was recorded.
- 🚧 Auto-captions mangle the names: "Pee Stack" / "P-Skill" = pstack, "on slop" = unslop, "Soul" is **probably** the Sol model. Minutes [1:32-3:04] are a Depot sponsor read - skip them.

### Where to look

1. pstack's `unslop` and `blast-radius` - the two pstack skills he leans on hardest.
2. Matt Pocock's `skills/engineering` directory, which he lists at [13:20].
3. His closing advice at [35:14-37:46]: don't copy someone's setup, edit your own skill files.
