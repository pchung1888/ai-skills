# htsw — How This Shit Works

> A skill for when someone says **"wait, how does this work?"** and you'd rather hand them a one-page brief than explain the same code for the eighth time this month.

Inspired by the *Get Shit Done* philosophy: cut the ceremony, name the moving parts, leave the reader with something they can act on. Built for engineers and PMs who already lost an hour today to "let me look at this and get back to you."

---

## What it does, in one sentence

Four operations you already do every week — **walk through, review, test, pitch** — done in a consistent voice with a validator behind it, so the output never reads like a stock template and never lies to you about what it found.

---

## The four modes

```
/personal-htsw [mode] [source]
```

| Mode | When you reach for it | What you get |
|---|---|---|
| **`walk`** *(default)* | "How does this work?" / "I'm new to this code, give me the lay of the land" | An explainer with a flow diagram, a knobs section, and the landmines — no verdict, no pitch |
| **`pr`** | About to review a PR you didn't write | Tier title verdict + TL;DR + ticket-vs-PR alignment + annotated diff + where-to-slow-down on big diffs |
| **`qa`** | About to test against a Jira story OR you found a bug | Test-case table (pre-test) OR Jira-vs-code reality table (post-test) — auto-detects which |
| **`boss`** | Pitching a feature or plan to a non-engineering sponsor | Polished prose + impact-at-a-glance — no icons, no jargon, no salt |

**Mode is optional.** `/personal-htsw src/user-service.ts` runs walk mode against the file. Picking a mode is the verb you bring; not picking one means *teach me.*

---

## Why you'd actually use this daily

Not "useful in theory." **Useful in the next two hours.** Five moments where it pays for itself:

1. **The "wait, how does this work?" moment.** You're handed an ASP page or a stored procedure you didn't write, and you need to understand it before you can change it. `/personal-htsw walk <file>` gives you the flow + knobs + landmines in 400 words. You go from 0 to oriented in three minutes instead of forty.

2. **The "review this PR" Slack ping.** Someone drops a 12-file MR and asks for eyes. `/personal-htsw pr` calls `/review` behind the scenes, maps the diff to the Jira ticket's acceptance criteria, drops `🟢/⚠/🔴` icons on each one, and tells you which files are load-bearing vs. skim-eligible. You spend your review time on the parts that swing the merge.

3. **The "the test plan was sparse" moment.** PM hands you a one-paragraph story and "test it." `/personal-htsw qa <story>` produces an AC-mapped test-case table, calls out edge cases the PM didn't think of, and flags spec gaps with `→ ask:` arrows. You walk back into the PM's office with concrete questions.

4. **The "this is broken — how do I write it up so the dev acts on it?" moment.** You found a real bug. `/personal-htsw qa` (post-test variant auto-detected) produces a Jira-vs-code reality-check table with status as the first column, a hypothesis labeled as a guess, a where-to-look pointer list, and a copy-pasteable ticket draft. The dev opens it and knows where to start in under sixty seconds.

5. **The "I have to pitch this to the boss in twenty minutes" moment.** You've been deep in implementation; you need to explain why the work matters to someone who doesn't read code. `/personal-htsw boss` produces an impact-at-a-glance table + a phase-shape diagram + cost-vs-unlock framing. Sponsor approves; you go back to building.

Every one of these is a 5-15 minute task that becomes a 90-second task. Five of them per week is a half-day reclaimed. **That's why it earns the daily-driver slot.**

---

## The voice — what makes it different

Most AI explainers either drown you in code-comment-style prose ("this function takes a parameter and returns a value") or launder everything into corporate non-speech ("this enhancement leverages existing infrastructure"). htsw does neither.

| Voice | What it sounds like | When it fires |
|---|---|---|
| **Mode 1 — baseline** | Blunt. Direct. No salt, no praise. "This SP reads X, decides Y, writes Z." | Most of every rendering — when nothing's broken |
| **Mode 2 — salty** | "This part's a goddamn weird design choice but it works because X." "Hot garbage." "Straight-up wrong." | Real defects — calibrated to defect size, gated by a density rule (3+ 🔴 forces Mode 2 into TL;DR + HOW-WORKS + bullets, not as garnish) |
| **Mode 3 — warm + 🌮** | "The clever bit is the shared helper 🌮 — without it the cache corrupts on retry." | Genuinely well-crafted design (PR/QA only) — inline punctuation in walk mode |

The f-word is banned in every mode. Personal attacks on authors are banned. Praise-washing ("looks good!" with no reason) is banned. Everything else is fair game when accurate.

**Boss mode is the clean version.** If you need polite for a non-engineering audience, switch to boss — no salt, no icons, no jargon.

---

## What makes the output trustworthy — the contract

This is the part most AI explainers skip. htsw's claims are checkable:

| Contract | What it enforces |
|---|---|
| **First-line citation** | Every rendering opens with `_Explaining: <source> · purpose: <mode>_` — you always know what was looked at |
| **Hedge rule** | Causal claims ("because", "causes", "triggers") not directly observable in the source MUST be qualified (`most likely`, `appears to`, `probably`). An inference stated as fact fails |
| **Evidence-and-suggestion contract** | Every `⚠`/`🔴` flag in a body section must carry (a) an evidence marker (file:line, RFC, quoted source, SQL/HTTP observation) AND (b) a suggestion arrow (`→ fix:`, `→ suggestion:`, `→ optional:`, `→ next:`, `→ ask:`) — accusations without evidence get dropped |
| **Voice intensity density rule** | The prose tone scales with the icon density — six `🔴` icons can't be surrounded by clinical prose; if shit's broken, it sounds broken |
| **Honest protocol** | "I don't know" is a valid output. Confident wrong answers are 3× worse than blanks. Made-up file paths get caught |
| **Validator** | `python3 htsw-check.py --input-file <rendering.md>` — cross-platform, stdlib-only, structural checks per mode. Add `--examples-file` to validate every example in a multi-rendering file at once |

The validator can't verify *truth* — only *shape*. But a rendering with correct shape is much harder to fake than one without.

---

## Try it in 30 seconds

```bash
# 1. Walk through a file
/personal-htsw walk src/user-service.ts

# 2. Review the current branch's PR (calls /review behind the scenes)
/personal-htsw pr

# 3. Test a Jira story
/personal-htsw qa JIRA-123

# 4. Pitch a feature to your boss
/personal-htsw boss "session-timeout warning modal — 3 days FE + 1 day BE + 1 day QA"
```

Output goes inline to chat. Copy-paste into Jira / Slack / the MR description. **The skill never writes files** — that's by design; you pick the destination.

---

## The four karpathy pillars, ported in

Anyone who's seen Andrej Karpathy's [LLM coding pitfalls](https://x.com/karpathy/status/2015883857489522876) knows the four behaviors that go wrong without discipline: surface assumptions, simplicity first, surgical changes, goal-driven execution. htsw bakes them in three times — in reviewer-form (for `pr`), tester-form (for `qa`), and explainer-form (for `walk`):

| Karpathy pillar (implementer) | Reviewer form (`pr`) | Tester form (`qa`) | Walker form (`walk`) |
|---|---|---|---|
| Surface assumptions | Findings trace to diff lines, not vibes | Spec gaps flagged, `→ ask: PM` | "The source doesn't say" — don't fill in |
| Simplicity first | Four strong findings > twelve weak ones | Minimum test cases that prove the feature | Minimum explanation; don't over-explain |
| Surgical scope | Every `⚠`/`🔴` traces to *this* diff | Every test row traces to an AC | Explain the thing asked about, not adjacent things |
| Goal-driven | Every finding has a `→` arrow | Every test has a verifiable expected output | Every section leaves the reader with something new |

There's a 5th pillar — pipeline awareness — that probes whether a non-trivial diff/spec/plan went through Researcher → Plan → Critic. If it didn't, the rendering flags `→ ask: was there a research step before code?`.

**The skill is portable across machines.** If your environment doesn't have a separate `/karpathy` skill installed, no problem — the four pillars are inlined into htsw's SKILL.md, pr.md, qa.md, and walk.md directly.

---

## What htsw is NOT

- **Not a code generator.** It explains, reviews, tests, and pitches — it doesn't write the next feature for you.
- **Not a file writer.** Output is inline. The skill never touches `Jira`, never opens a PR, never sends Slack.
- **Not a diagram tool.** ASCII flowcharts only — if you need rendered diagrams, use `graphify` or your favorite drawing tool.
- **Not a `--clean` flag on top of pr/qa.** If you want polished, use `boss` mode. The other modes keep the explicit voice on purpose.
- **Not a verdict on you.** It grades the code, the spec, the plan — never the human who wrote it.

---

## Cross-platform, zero dependencies

- **Python 3 stdlib only.** No `pip install` step. Runs on macOS, Linux, Windows with the same one-liner.
- **UTF-8 forced on stdout/stderr.** Em-dashes and icons render cleanly on Windows consoles (default cp1252) without mojibake.
- **No network calls.** The validator runs offline. The skill itself calls MCP tools (Jira fetch, `/review`) only when explicitly invoked — and falls back gracefully when they're unavailable.

---

## File layout

```
.claude/skills/personal-htsw/
├── README.md                         (this file)
├── SKILL.md                          (entry, dispatch, cross-mode rules)
├── htsw-check.py                     (validator — Python 3 stdlib, no deps)
└── references/
    ├── walk.md                       voice + structure for walk (default explainer) mode
    ├── pr.md                         voice + structure for PR review mode
    ├── qa.md                         voice + structure for QA test-design / bug-writeup mode
    ├── boss.md                       voice + structure for boss pitch mode
    └── examples/
        ├── walk-examples.md          worked walk renderings
        ├── pr-examples.md            four quality tiers (good / pass / warning / bad)
        ├── qa-examples.md            pre-test + post-test variants
        └── boss-examples.md          feature pitch + plan walkthrough
```

---

## The case for daily use, in one paragraph

You already know how to read code. You already know how to write a bug report. You already know how to pitch a feature. **What you don't have is a consistent voice for any of those that you can crank out in 90 seconds without thinking about structure.** htsw is that voice. It's the difference between *eventually* writing a good review and writing one *now*, before the meeting, before the context-switch, before the slack thread goes cold. The validator means you can trust the output enough to ship it without re-reading. The four modes mean the same skill covers the four operations you do anyway. The taco emoji 🌮 means the rendering still has some personality. **That's the whole pitch — pick a mode, hit enter, get on with your day.**

---

**Ship it.**
