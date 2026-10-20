_Explaining: YouTube 0oXOOlqVu5M "So I tried Matt's skills..." (38 min, auto-captions, 7,683 words) · purpose: walk_

## What this video shows - one developer tests two skill packs

**TL;DR - the core idea:**

- ▶ **He tests two public skill packs** against his own work history.
- ⚙ **The unslop skill started it** because it made agent replies easy to read.
- 🧠 **Paste the markdown into a session** to try a text-only skill.
- 📍 **His advice** is to read each skill and keep only the ones you need.

### ⚙ How this shit works

Context first. A skill is a markdown file that tells an agent how to do one task. Many people now publish packs of skills on GitHub. This video is a 38-minute stream where a TypeScript YouTuber tests two of those packs [0:00].

The first pack is Matt Pocock's skills. He says it has more than 200,000 GitHub stars [0:31]. The second pack is pstack. Lauren, called "Potato", wrote it. She worked on the React core team and now works at Cursor [1:32].

He does not install the packs as they are. He tells an agent to read his past sessions on all his machines. The agent then ranks each skill by how well it fits his work [4:35]. He reads the top skills and keeps some of them.

The `unslop` skill started the project. He saw text that Lauren's agents wrote, and it was easier to read than his Claude output [5:06]. He asked the same question about his T3 Code project with and without `unslop`. The answer without the skill now looks bad to him [10:46].

```
 1  An agent reads your past sessions
    |  from every machine you use
    v
 2  The agent ranks each skill by fit
    |  and writes the reason for each rank
    v
 3  You read the markdown of the top skills
    |  you paste text-only skills into a session to test them
    v
 4  You keep the good skills in one repo
    |  the agent copies them to each machine
    v
 5  You do not install the other skills
```

### The skills he kept

| Skill | Pack | What it does | What he says |
|---|---|---|---|
| `unslop` | pstack | Removes common AI writing patterns | It made him read his agents' replies again [35:44] |
| `grilling` | Matt | Asks you questions about a plan, in rounds | The questions were useful [19:27] |
| `diagnosing-bugs` | Matt | Starts by itself when you debug | His agents find the root cause faster [14:52] |
| `wizard` | Matt | Gives a person the steps that only a person can do | He installed it on every machine [27:35] |
| `blast-radius` | pstack | Finds what a change breaks in other places | He uses it often [33:13] |
| `arena` | pstack | Runs many attempts and joins the best parts | It cost him hundreds of dollars [32:12] |

### Watch out for

- 🧠 He says the `description` of a skill is a trigger. The model reads it to decide when to load the skill [5:36]. So write descriptions for that job, not as a summary.
- 🚧 Matt's skills use many em dashes, nine on one page [15:22]. He thinks his agents copy that style. Models copy the style of the text in their context.
- 🚧 Some pstack skills work only in Cursor [32:43].
- 🧠 The `unslop` version in the video has a section about personal voice and a self-check step [6:38]. The copy in ping-personal (commit `bc697d0`) does not have them. Upstream **most likely** removed them after the video.
- 🚧 The auto-captions spell names wrong. "Pee Stack" and "P-Skill" mean pstack. "On slop" means unslop. "Soul" is **probably** the Sol model. Minutes [1:32-3:04] are an advertisement.

### Where to look

1. The pstack `unslop` and `blast-radius` skills. He uses these two most.
2. The `skills/engineering` folder in Matt Pocock's repo. He lists its skills at [13:20].
3. His advice at [35:14-37:46]. Do not copy the setup of another person. Change your own skill files.
