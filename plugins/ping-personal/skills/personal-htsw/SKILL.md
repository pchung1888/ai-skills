---
name: personal-htsw
model: sonnet
description: How This Shit Works - re-explain code, a PR diff, a spec, a plan, or current conversation for one of six purposes (walk / pr / qa / boss / baby / code-explain). Default mode is **walk** (explain-it-to-me) when no mode is specified. Trigger on /personal-htsw or natural phrases like "how does this work", "wtf is this code", "walk me through this", "explain this PR", "QA brief on this", "pitch this to my boss", "explain this like I'm new", "explain this line by line", "walk me through this diff file by file". Output is inline only - no file writes (code-explain may save a doc on explicit request). For PR mode, the skill calls the built-in /review skill behind the scenes to get the diff, then layers the htsw voice on top.
---

# htsw — How This Shit Works

## What it's for

`/personal-htsw <mode> [<path>]` re-explains a source (file, diff, spec, plan,
or the current conversation when no path is given) for one of six purposes.
Mode is optional and defaults to `walk` -- most invocations want explanation,
not grading. Output is inline to the chat; the skill writes no files
(code-explain is the one carve-out -- it saves a `.md` only on explicit request).

## Modes and aliases

| Mode | Aliases | When you'd use it |
|---|---|---|
| `walk` (**default**) | `explain`, `tour`, `learn`, `how` | "How does X work?" / "Walk me through this" / "I'm new to this code/feature/spec." No verdict, no PR-review weight, no pitch — just explain it with the htsw voice. |
| `pr` | `review`, `reviewer` | About to review someone else's code or a PR you didn't write |
| `qa` | `tester`, `test` | About to test something against a Jira story, OR you found a bug and want to write it up |
| `boss` | `client`, `sales`, `pitch`, **`clean`** | Pitching a plan to your boss or a client. Also the "clean" version when you want any explanation in professional language. |
| `baby` | `eli5`, `analogy` | "Explain this with a concrete analogy." Every jargon term stays on the page AND gets paired with an everyday physical object so a junior dev learns both vocabularies at once. |
| `code-explain` | `code`, `explain-code`, `line-by-line`, `deep-dive`, `cx` | Understand a code change in depth — file-by-file, line-by-line, **why-first**. The deep sibling of `walk`. Inline by default; saves a doc on request. |

**There is no separate `--clean` flag.** If you want a clean / professional / suitable-for-client version of any explanation, just use `boss` mode. Walk / PR / QA are for internal use — they keep the explicit language. Boss is the polite version. Walk is the most common; reach for it when you want to *understand* something, not grade it.

## What each mode does

### Walk mode (default) — explain it to me, no verdict

When you just want to understand something — a piece of code, a feature, a spec, a plan, what came up in a conversation — and you don't want it graded or pitched, you want it **explained.** This is the default mode when you type `/personal-htsw <source>` with no mode arg.

What walk mode does:

1. Takes the source (file path, conversation, whatever you point it at).
2. Renders an explainer using the htsw voice: blunt, plain English, no jargon-without-translation, no sales-pitch sanitization.
3. Uses tables, ASCII flow diagrams, numbered checklists, and **navigation icons** (`▶ ⚙ 🧠 🚧 📍`) to make the structure scannable.
4. Does NOT use the PR/QA verdict icons (`🔴 ⚠ 🟢 🌮`) as a tier system. Those icons can appear *inline* — `🔴` when explaining something genuinely broken the user should know about, `🌮` when a piece of design is genuinely beautiful and the user might miss why — but they're punctuation, not grading.
5. Does NOT carry a tier title like PR/QA. The title is *descriptive* ("How this thing actually moves", "The shape of <subject>", "What this file really does") — it names the subject, not a verdict.

When NOT to use walk mode:
- You found a bug → `qa` (post-test variant)
- You're about to test a Jira story → `qa` (pre-test variant)
- You're reviewing a PR → `pr`
- You're pitching to a sponsor / client / non-engineering audience → `boss`

The voice is **Mode 1 (baseline) + Mode 2 (salty) when accurate** — same lexicon as the other internal modes, no f-word, no praise-washing. Walk mode is allowed to say "this part's a goddamn weird design choice but it works because X" — that's the htsw teaching tone. Boss mode would launder that to "this design choice is unconventional but functional"; walk mode shouldn't, because the salt is part of what makes the explanation memorable.

Full playbook: `references/walk.md`.

### Code-explain mode — deep file-by-file + line-by-line walkthrough

The deep sibling of walk. Use it when the user wants to *understand a code change well enough to maintain or defend it* — "walk me through this line by line", "explain this diff file by file", "I need to show my boss-the-engineer why we did this".

What code-explain does:

1. Resolves the source as a **change** by default — a diff, a commit, a branch-vs-master delta (`git diff <base>...HEAD`), or a single file. Reads the real lines at their real line numbers (NOT the diff's `@@` headers, which drift once the file moves past the diff).
2. **Leads with WHY** — the problem the change solves, stated before any code. This is the defining move: the most load-bearing sentence is usually the one thing the old code did wrong, or the gap the new code fills.
3. Maps **every file touched** (a file-by-file table), calling out which changes are real vs. noise (build artifacts, encoding churn) so the reader doesn't hunt for meaning that isn't there.
4. Walks the **load-bearing code line by line** — a code block + an annotation table (`| Line | What it says | What it means |`), with **adaptive depth**: line-by-line on what matters, grouped summaries for boilerplate.
5. Closes with **honest caveats** (the known rough edges, ideally lifted from the code's own comments) and **sources**.
6. Same voice as walk — plain English, every piece of jargon translated on first use, navigation icons (`▶ ⚙ 🧠 🚧 📍`), no verdict.

**Output:** inline by default like every other mode. It writes a `.md` file **only on request** (the user gives a destination or says "save it") — the one carve-out from htsw's inline-only rule.

When NOT to use code-explain:
- You just want the shape / how it works → `walk` (lighter, ≤ 700 words)
- You're grading the change → `pr`
- The audience is non-engineering → `boss`

Full playbook: `references/code-explain.md`.

### Baby mode — analogy walks alongside jargon, never instead of it

Baby mode teaches a technical subject by pairing every piece of jargon with an everyday physical analogy. The jargon stays literally on the page; the analogy is a companion, not a replacement. A junior dev reading baby-mode output learns both the mental model AND the vocabulary they need to talk to senior engineers.

Voice is mentor-explains-to-curious-junior -- not adult-explains-to-toddler. Every explanation assumes the reader is smart and capable; they just haven't seen this system before.

v0.3.0: the reader watches the play; characters introduce themselves.

What baby mode does:

1. Opens with a **vertical story arc** -- characters introduced one per step, each on its own line, each with an action verb. The reader learns the world incrementally; by the time a new character appears, the previous ones have already done something.
2. **Introduces each character inline as they enter the scene.** First mention is a dedicated sentence where the character is the subject, bolded, followed immediately by a parenthetical or dash gloss. Characters are never introduced inside subordinate clauses.
3. Uses BOTH vocabularies throughout the prose -- "the errand boy (`useEffect`) fetches from the filing cabinet (`Database`) once on mount."
4. Renders a **story-rhythm ASCII block** (plain code fence, no language tag): a vertical chain where each step line carries BOTH the jargon token AND the analogy in parens, separated by `|` connector lines.
5. Uses `📦` for physical-object analogies in TL;DR bullets and `🏷️` for labels that connect jargon to analogy. Walk's navigation icons (`▶ ⚙ 🧠 🚧 📍`) are also available.
6. Declares the **audience** on the second line (immediately after the citation): `_For: <persona -- what they know, what they don't know>_`. The analogy domain must match the declared audience's existing mental model.

Baby mode is **audience-agnostic** -- the analogy domain must match the declared audience's daily lived experience, never default to a fixed world. The N anchors in `references/examples/baby-examples.md` are illustrative, not bounding. The skill picks the best analogy for each invocation.

7. Places the **Cast of Characters table at the END** as a recap, not at the top. The Cast is a glossary you reach for when you forgot who character N was -- not an upfront roster to memorize.
8. Enforces **Cast Persistence** across follow-up questions: once a Cast exists in a thread, the next baby rendering extends it. Follow-up renderings open with a one-line continuity nod and append a Status column (`inherited` / `new`) to the recap Cast table.

When NOT to use baby mode:
- You want a code review verdict -- use `pr`
- You need a test brief -- use `qa`
- You're pitching to a sponsor -- use `boss`
- The audience already knows the jargon -- use `walk`

Banned in baby mode: the words `easy`, `simple`, `just`, `basic`, `don't worry` -- these are sanitization smells that signal the analogy is replacing thinking instead of supporting it. Also banned: `sweetie`, `honey`, `ok kiddo`, `buddy`, `lil'` -- baby mode is mentor voice, not kindergarten voice.

Full playbook: `references/baby.md`.

### PR mode — calls `/review` first, then explains

PR mode uses the built-in `/review` skill behind the scenes to pull the actual diff. Then it layers the htsw voice on top:

1. The skill calls `/review` to get the diff, the changed files, and any review comments.
2. The skill reads the current branch. If it's `topic/NNN` or `feature/NNN` (where NNN is a number), the skill assumes NNN is a Jira `ST-NNN` ticket and pulls the ticket via the Atlassian MCP tool.
3. The skill renders a brief that says: what the ticket asked for, what the PR delivers, where the gaps are, where to look first.
4. Every acceptance criterion gets a 🟢 (delivered) / 🔴 (missing) / ⚠ (uncertain) icon.
5. Every problem in the diff gets pinpointed with an inline `← 🔴 <problem>` annotation.
6. An "Impact at a glance" table summarizes the file-by-file picture.

If `/review` isn't available (some environments don't have it), the skill falls back to whatever the user passed as the source.

**Plan-mode input — when the source is a plan doc, not a diff or spec.** Both PR and QA pre-test modes handle forward-looking plan documents (anything with a `## Phase N` / `**File Map**` / `**Files NOT touched:**` structural signal). In that case the contract still applies but two section cells shift:

| Mode | Cell that shifts |
|---|---|
| PR mode | Impact-at-a-glance column → "What the plan proposes"; diff block → `(plan-mode review — no diff yet)` |
| QA pre-test | Coverage-at-a-glance "AC #" column → "Phase / Task #"; Spec gaps → "Plan gaps" |

Full rules: `references/pr.md` § "Plan-mode input" and `references/qa.md` § "Plan-mode input". This avoids needing a separate `/personal-htsw plan` mode.

### QA mode — tests OR bug writeups

QA mode handles two situations the user might be in:

- **Pre-test:** they have a Jira story and they're about to write tests. The skill produces a test brief with a Status column on the test-case table.
- **Post-test:** they have a Jira story AND they observed a bug. The skill produces a Jira-vs-code comparison table (the load-bearing artifact), a hypothesis, and a Jira-ready ticket draft.

The skill detects which situation by looking at the source. If the source has phrases like "Observed:", "Actual:", "Bug:", "Repro:", "Spec says X but…" — it's a bug writeup. Otherwise it's a test brief.

### Boss mode — sponsor / client / clean

Boss mode is professional, no jargon, no icons, no tacos. Use it when:

- Pitching a feature or plan to a non-engineering sponsor.
- Explaining the same thing to a client.
- You wrote a PR or QA explanation and want a clean version for sharing outside the team.

Boss output uses tables for visual structure — Impact-at-a-glance for features, Phase-shape table for plans. No 🔴 / ⚠ / 🟢. No 🌮. No slang.

## Source resolution

| Input | Source the skill uses |
|---|---|
| Path arg given | Read that file |
| No path arg, walk mode | Use the current conversation |
| No path arg, PR mode | Call `/review` first; fall back to current conversation if `/review` unavailable |
| No path arg, QA or boss mode | Use the current conversation |
| No path arg, baby mode | Use the current conversation |
| Path arg given, code-explain mode | Read that file/diff; if it's a *change*, also pull `git diff <base>...HEAD` / `git show <hash>` and read the live file at its real line numbers |
| No path arg, code-explain mode | The change just discussed, or `git diff <base>...HEAD` for the current branch |
| Path doesn't exist | Fail loud: "Source not found: \<path\>" |
| Path is empty | Fail loud: "Source is empty: \<path\>" |
| Path is binary (.pdf, .docx, .zip, .exe, etc.) | Fail loud: "Source appears binary — htsw renders text only" |
| No conversation AND no path | Fail loud: "No source detected. Pass a file path or ask me about something first." |

**No mode specified → walk mode.** `/personal-htsw src/user-service.ts` is the same as `/personal-htsw walk src/user-service.ts`. If you really want a verdict you have to ask for it explicitly with `pr` / `qa` / `boss`. This default reflects observation: most invocations want explanation, not grading.

## Source isolation rule — PR mode (anti-leakage)

**For PR mode specifically, the source MUST be the diff + the linked Jira ticket — and nothing else.** In particular, the **dev's own commit-message body MUST NOT reach the rendering pass.**

**Why:** the commit message is the dev's writeup of what they did and why. If the rendering can read that writeup, every "finding" it produces is at risk of being a paraphrase of the dev's own claims rather than an independent analysis of the diff. A reviewer who reads such a rendering thinks they're seeing an audit; they're actually seeing the dev marking their own homework.

**What this means in practice:**

- When `/personal-htsw pr` is invoked via `/review`, the rendering must consume `/review`'s diff output and (if available) the Jira ticket body. The git-commit body is excluded by default.
- When `/personal-htsw pr <path>` is invoked with an explicit file path, the file should be a diff or a Jira-ticket export — NOT a `git log` output with commit-message bodies attached.
- If the source string includes a "Commit message:" header, the skill MUST strip everything from that header to the next diff/ticket section before rendering.
- Eval evidence: an internal eval on 5 historical commits found commit-message leakage in 4 / 5 renderings — facts that *looked* like they came from the diff actually came from the dev's writeup, undermining the value of the review.

The validator cannot enforce this rule (it sees only the rendering, not the input that produced it). Authors and skill-invoking wrappers carry the responsibility.

## Status icon contract — verdict icons vs. navigation icons

Different modes use icons for different purposes:

**Walk mode (default) — navigation icons, not verdict icons.** Walk doesn't grade; it explains. Use `▶` (flow step), `⚙` (mechanism), `🧠` (non-obvious — read carefully), `🚧` (known wart that works), `📍` (focal point). The verdict icons (`🔴 ⚠ 🟢 🌮`) can appear *inline* in walk mode but only as punctuation when accurate -- `🔴` for something genuinely broken the reader needs to know about, `🌮` for a piece of design that's genuinely beautiful and worth pointing out. Never as a tier system, never as a section header.

**Baby mode -- navigation icons + 2 analogy icons.** Baby inherits walk's navigation icons AND adds two new ones: `📦` (physical-object analogy -- the errand boy, the filing cabinet, the whiteboard) and `🏷️` (the label connecting jargon to analogy). Use `📦` and `🏷️` primarily in TL;DR bullets to signal dual-vocabulary intent at a glance. Walk navigation icons (`▶ ⚙ 🧠 🚧 📍`) remain available in baby mode prose and optional sections. Verdict icons (`🔴 ⚠ 🟢 🌮`) follow the same inline-only punctuation rule as walk mode -- never as tier titles, never as section headers.

**PR and QA — verdict icons.** Every spec / acceptance / test / diff / file item gets one:

| Icon | Meaning |
|---|---|
| 🔴 | Missing / broken / wrong / blocking |
| ⚠ | Warning — worth flagging, not blocking |
| 🟢 | Delivered / correct / matches spec |

**Boss — icon-free.** Tables and prose carry the structure; no icons at all.

### Where icons must appear

**PR mode:**
- **TL;DR block (right after the tier title) — every bullet prefixed with an icon.**
- Ticket-vs-PR alignment list — one icon per acceptance criterion.
- The diff block — inline `← 🔴 <problem>` / `← ⚠ <warning>` / `← 🟢 covers AC #N` markers on the lines that matter.
- Impact-at-a-glance table — Status column showing the file-by-file picture.

**QA pre-test mode:**
- **TL;DR block — every bullet prefixed with an icon.**
- Test-case table — Status column with 🟢 / ⚠ / 🔴 per test case.
- Edge-cases section — each item prefixed with ⚠.
- Spec-gaps section (if any) — each item prefixed with 🔴.

**QA post-test mode:**
- **TL;DR block — every bullet prefixed with 🔴 (violation) or ⚠ (hypothesis/risk); no 🟢, no 🌮.**
- Jira-vs-code table — Status as the FIRST column.
- "What actually happened" — prefixed with 🔴.
- Hypothesis — prefixed with ⚠ (it's a guess).
- Where to look — each pointer prefixed with 🔴 or ⚠.

**Boss mode:**
- No icons. Anywhere. At all. No TL;DR section either — boss is for sponsor audiences who want context, not a rushed verdict.

**Walk mode (icon and signature contract):**
- **HOW-THIS-WORKS signature header is REQUIRED** at `###` (H3) level, one of the standard variations, optionally prefixed with `⚙` — e.g. `### ⚙ How this shit works`. When the section contains a flowchart/diagram, the signature header sits above the diagram. When it contains a table or ASCII flow, the header sits above that.
- **TL;DR is required, but with a descriptive label** (`**TL;DR — the core idea:**`, `**TL;DR — short version:**`, `**TL;DR — in one breath:**`), never a verdict label (`ship it`, `block this`, `file it`).
- TL;DR bullets use **navigation icons** (`▶ ⚙ 🧠 🚧 📍`) or no icons. Verdict icons (`🔴 ⚠ 🟢 🌮`) are FORBIDDEN in walk's TL;DR — they read as PR/QA verdict openers.
- Inline `🔴` is allowed once or twice in body text when the explanation hits something genuinely broken the reader needs to know about. When used, the inline `🔴` inherits the evidence-and-suggestion contract (file:line citation + `→ note:` or `→ ask:` arrow).
- Inline `🌮` allowed at most once or twice when a piece of design is genuinely beautiful and a newcomer might miss why. Never as a section-header opener.

The validator (`htsw-check.py`) checks this contract mechanically. Output that violates the contract fails the check.

## Four-tier signature — GOOD / PASS / WARNING / BAD

PR and QA pre-test renderings come in four tiers. Each tier has its own icon, its own action-verb vocabulary, and its own tier-title library (see `references/pr.md` and `references/qa.md` for the full lists).

| Tier | Icon in title | Action verbs | When it fires |
|---|---|---|---|
| GOOD | 🌮 | `ship it` / `merge it` / `green-light it` | The PR / spec is genuinely well-crafted. Close with 🌮 + Mode 3 voice. |
| PASS | 🟢 | `ship it` / `merge — no drama` / `approve as-is` | The PR / spec does the job. No celebration, no problems. Mode 1 voice. |
| WARNING | ⚠ | `address these and merge` / `fix three things first` / `comment and re-review` | The PR / spec is mostly fine but has minor gaps. Not blocking, but not ignorable. Mode 1 + a few ⚠ items. |
| BAD | 🔴 | `block this` / `send it back` / `not mergeable` / `hard nope` | The PR has blocking issues. Mode 2 voice. (QA pre-test has no BAD tier — escalate, don't test.) |

Post-test QA is one-tier-only: bug found, title opens with 🔴.

The tier icon in the title is what the reader sees first. The TL;DR action verb is the immediate follow-on. Together they answer the "what do I do with this?" question before the reader gets to any prose.

## TL;DR contract (PR + QA only — boss is TL;DR-free)

**Every PR and QA rendering must open with a TL;DR block right after the tier title.** This is the verdict-first layer that lets a busy PR reviewer or QA stakeholder make a decision without reading the rest of the brief.

**Shape:**

```
## <tier title — catchy headline (icon-prefixed for PASS/WARNING/BAD; 🌮 for GOOD)>

**TL;DR — <action verb>:**

- 🔴 / ⚠ / 🟢 **<bolded noun phrase>** — <short reason ≤ 12 words>.
- <2 more bullets, same shape>
- (max 4 bullets total)
```

**Rules:**

- Label is exactly `**TL;DR — <action verb>:**`. The action verb IS the verdict — `ship it`, `block this`, `address these and merge`, `fix three things first`, `file it`, etc.
- **Never use the word "Verdict:" anywhere in the rendering.** The TL;DR label is the verdict. A bottom-of-page "Overall verdict" section is forbidden — the brief should not repeat its own conclusion.
- 2-4 bullets. ≤ 15 words per bullet. ≤ 60 words for the whole block.
- Each bullet leads with the status icon, then a **bolded noun phrase** (3-6 words), then a short reason clause.
- Post-test QA TL;DR uses only 🔴 and ⚠ — no 🟢 (irrelevant when there's a bug on the table), no 🌮 (Mode 3 unavailable post-test).

## HOW-THIS-SHIT-WORKS contract (ALL explanatory modes — PR + QA + walk + baby + code-explain)

**Every PR, QA, walk, baby, and code-explain rendering must include exactly one HOW-THIS-WORKS section.** This is the skill's literal namesake -- `htsw` stands for "how this shit works." The contract applies to all five explanatory modes:

- **PR mode** -- 2-4 sentences explaining what the diff does. Bridge from raw diff to actionable review comments.
- **QA mode** -- 2-4 sentences explaining what the feature is supposed to do (pre-test) or what's actually happening when the bug fires (post-test).
- **Walk mode** -- the main artifact of the rendering. 3-5 sentences (or more -- walk IS the explanation), often paired with a table, ASCII flow, or mermaid flowchart. **When walk-mode output contains a flowchart, the signature header sits immediately above the chart** -- the chart is the explanation, the header is the brand.
- **Baby mode** -- the main explainer section, using BOTH vocabularies (jargon term AND analogy companion) in every sentence. Immediately followed by the ASCII flow diagram with dual-vocabulary nodes. The HOW-WORKS header in baby mode may be prefixed with `📦` or `🏷️` (e.g. `### 📦 How this shit works`, `### 🏷️ Under the hood`) as a visual signal that the dual-vocabulary contract is active.
- **Code-explain mode** -- the bridge from the WHY framing and file-by-file map into the line-by-line body. 30+ words; hedge inferred cause-effect chains (`most likely`, `appears to`). Sits after the file-by-file map and before the per-file line-by-line walkthrough.

The section header is one of a fixed library of variations (see `references/pr.md`, `references/qa.md`, `references/walk.md`) so renderings don't read like a template — `### How this shit works`, `### What this actually does`, `### Under the hood`, `### The flow`, `### In plain English`, `### Behind the scenes`, `### The plumbing`. **All modes use `###` (H3) level** for this header — the validator's `HTSW_HEADER_PATTERN` requires H3. Walk mode renderings have the descriptive subject-title at `##` (H2) and the HOW-WORKS section at `###` immediately following the TL;DR block. Walk mode may prefix the header with the `⚙` navigation icon — e.g. `### ⚙ How this shit works`.

The section is the **bridge from raw artifact to comprehension.** Without it, the reader has to reconstruct intent from code, tables, or charts. With it, they start with the design already in their head — which is the whole point of htsw.

## Evidence-and-suggestion contract — EVERY ⚠ AND 🔴 CLAIM

**This is the load-bearing honesty rule.** When you mark something ⚠ or 🔴, you are accusing the dev (or PM) of doing their job wrong. You do not get to make that accusation on vibes.

Every ⚠ and 🔴 in the body sections (Watch out for / Where to look / Edge cases / Spec gaps / Hypothesis) must satisfy both:

1. **An evidence marker** — one of: a backtick-wrapped file path with line (`` `middleware/rate-limit.ts:42` ``), an RFC/standard reference (`RFC 6585 §4`), a direct quote from the source (markdown blockquote), a SQL/HTTP observation, an explicit negative search ("searched X and found nothing"), or a "the source doesn't say" qualifier.
2. **A suggestion-arrow** — one of:
   - `→ fix:` — a defect that must be addressed before merge
   - `→ suggestion:` — a should-do that's strongly recommended before merge
   - `→ optional:` — a nice-to-have improvement; not blocking, fine to defer
   - `→ next:` — a follow-up action for after merge (e.g. open a separate ticket)
   - `→ ask:` — a question for the PM, the dev, or a stakeholder

The arrow-verb distinguishes severity — a reviewer scanning the body should be able to tell at a glance whether each finding is a `→ fix:` blocker, an `→ optional:` polish item, or a `→ next:` follow-up. **Do not pile must-do and nice-to-have suggestions under the same arrow.** This was an eval finding from internal testing: when every suggestion uses `→ fix:` or `→ suggestion:`, the reviewer has to re-read each one to decide whether it actually blocks merge.

**The validator (`htsw-check.py`) enforces the structural side of this rule** — every ⚠ / 🔴 bullet in the body must include both markers. It cannot verify the *truth* of a claim — only the shape of one. If the validator passes a rendering whose facts are wrong, that's a Mode-2 problem with the author, not the validator.

Where the rule does NOT apply: bullets inside the TL;DR block (deliberately terse), inline diff annotations (the file+line is implicit), and Status-column entries in tables (the row already supplies the citation in adjacent columns).

## Hedge rule — HOW-THIS-WORKS section (anti-overconfidence)

**Inferences in the HOW-WORKS section must be hedged.** If a claim describes a cause-effect chain that isn't directly observable from the diff (a "because", "causes", "triggers", "due to"), it must be qualified with one of: `most likely`, `appears to`, `seems to`, `probably`, `looks like`. Direct observations don't need hedging — only inferred mechanisms do.

**Examples:**

| Phrasing | OK? |
|---|---|
| "The middleware reads `req.ip` and rejects with 429" | ✓ direct observation of the diff |
| "An XML parse error throws with the source text attached" | ✗ inference about runtime behavior; must hedge |
| "An XML parse error **most likely** throws with the source text attached" | ✓ inference, properly hedged |
| "Because the SP marshals as Variant/String, the equality returns False" | ✗ "because" introduces a causal claim that's not in the diff |
| "The equality **appears to** return False because the SP marshals as Variant/String" | ✓ hedged causal claim |

**Why:** the HOW-WORKS section is the bridge from raw artifact to reviewer understanding. Stating an inference as a fact lets a wrong inference propagate into review comments and ultimately into the PR's history. A hedge costs one word and protects the reader from over-trusting an unverified mechanism. (Eval finding: 1 / 5 sampled renderings had an un-hedged causal claim that turned out to be plausible-but-unverified.)

## Deeper-dive contract — load-bearing-files map (PR mode only, large diffs)

**Big PRs need a heat map, not equal-treatment-for-every-file.** When a diff is sprawling, a reviewer treating every line equally will either drown or skim past the file that actually matters. The rendering must call out which 1-3 files are load-bearing and (optionally) which are skim-eligible.

**The trigger fires when ANY of these is true:**

- The diff touches **≥ 5 files**, OR
- **Any single file changed ≥ 100 lines** (insertions + deletions, per `git show --stat`), OR
- The diff includes a **binary or generated file** (`.dll`, `.cache`, `.pdb`, `.exe`, `.bin`, compiled output)

When the trigger fires, the rendering must include a "Where to slow down" section (one of the recognized headers below) that names 1-3 files in priority order, each with one sentence explaining why this file is load-bearing.

**Recognized section headers (pick one — vary across renderings):**

- `### Where to slow down`
- `### Reviewer attention map`
- `### Read these first`
- `### The load-bearing files`
- `### Where to focus`
- `### Heat map`
- `### Don't skim these`

**Shape:**

```
### Where to slow down

1. `<file path>` — <one sentence why this is load-bearing>.
2. `<file path>` — <one sentence why this matters>.
3. `<file path>` — <one sentence; tag "(skim-eligible)" if mechanical>.
```

**Skim-eligible tag:** if a file in the trigger set is genuinely mechanical (whitespace-only, generated binary, rename-only, `.cache`/`.pdb` swap, prettier formatting), tag it `(skim-eligible)` and put it last. Skim-eligible items signal "trigger fired but this row doesn't deserve reviewer time" — important because the reviewer might otherwise spend time pattern-matching a binary diff for meaning.

**Why a separate contract:** the Impact-at-a-glance table is a *catalog* (every changed file gets a row); the deeper-dive section is a *priority list* (which 1-3 files swing the review). For a 23-file diff with 4 DLLs and 1 SP, the catalog is overwhelming and the priority list is the load-bearing artifact.

**Validator note:** `htsw-check.py` counts `diff --git` headers in the rendered diff block; if ≥ 5, or if any binary-file marker (`Bin .* ->`, `.dll`, `.cache`, `.pdb`) is present, the deeper-dive section is required. Below threshold, the section is optional — adding one on a 1-file diff is fine but redundant.

## Reviewer discipline — the four karpathy pillars

This skill reviews other people's work. Reviewer discipline is the difference between a brief that builds trust and one that creates noise. Karpathy's [LLM coding pitfalls](https://x.com/karpathy/status/2015883857489522876) name four behaviors that go wrong without it — translated here into the reviewer-form htsw needs.

**The four pillars (reviewer-form):**

| # | Pillar | Implementer-form (Karpathy) | Reviewer-form (htsw) |
|---|---|---|---|
| 1 | **Surface assumptions** | State your assumptions; ask if uncertain | If the diff makes a behavior you can't verify, **say "the diff doesn't show whether X"** — don't assert X is broken or working. |
| 2 | **Simplicity first** | Minimum code; no speculative features | **Four strong findings > twelve weak ones.** If a body section has more than 5 bullets, the brief is rambling — cut the weakest. |
| 3 | **Surgical changes** | Touch only what's needed; don't refactor adjacent code | **Surgical findings.** Every ⚠ / 🔴 must trace to a line in *this* diff. No "while you're at it" — adjacent-file rants belong in a separate ticket. |
| 4 | **Goal-driven execution** | Define verifiable success | Every finding's `→` arrow IS the verification step. A finding without an arrow is just complaining (already enforced by the evidence-and-suggestion contract). |

**Pillar 5 — pipeline awareness (for non-trivial diffs):** Karpathy's planning pipeline (Researcher → Plan → Critic) exists because non-trivial work without it ships with avoidable bugs. When the deeper-dive trigger fires (≥ 5 files OR ≥ 100 lines OR binary present) **AND** there's no evidence the dev ran research / planning / adversarial-review before coding, the rendering MAY add one bullet to "Watch out for" flagging the gap — e.g. `⚠ Big diff, no plan doc in the ticket — → ask: was there design review before code?`. This is a soft probe, not a contract — only fire it when the diff actually warrants it.

**Why translate the pillars rather than copy them:** Karpathy's pillars are written for the dev who's about to *write* the code. htsw runs when someone is about to *review* the code. The behaviors look different on the two sides — "minimum code" (implementer) becomes "minimum findings" (reviewer); "surgical changes" (implementer) becomes "surgical findings" (reviewer). Same spirit, opposite verb.

**Project-portability note:** This section exists in SKILL.md (not just `references/pr.md`) because the htsw skill is portable across projects. A machine that installs only htsw — without a `/karpathy` skill alongside — must still get the karpathy discipline through htsw itself. Don't `Skill(karpathy)` from inside htsw; the wrapper might not have it.

## Voice contract (PR + QA only — boss has its own register)

PR and QA use three voice modes that match the quality of what they're describing:

| Mode | When | What it sounds like |
|---|---|---|
| 1 — Baseline | Code or spec is average / fine | Blunt and direct. No salt, no praise. |
| 2 — Salty (PG/R) | Real defect found | "This is hot garbage." "That's bullshit." "Straight-up wrong." Calibrated to the defect size. |
| 3 — Warm + 🌮 | Genuinely well-crafted source | "This is beautiful." "Chef's kiss." Close with 🌮 on a specific quality signal. |

Banned in pr/qa default voice (the icon-using one):
- The f-word — skip it, even when something is broken.
- Personal attacks on the author — criticize the code, not the human.
- Praise-washing — "looks good!" without naming WHY.

Boss mode uses its own professional register — no Mode 1/2/3 distinction, no salt, no warm vocab, no taco. Always polite.

## Honest protocol — in plain English

This skill works the same on any project — no project-level rules to lean on. So the honest protocol lives here.

**Rules — no special labels, just plain English:**

- If the source doesn't say something, **say "the source doesn't say"** — don't fill it in.
- If you're guessing about a root cause, **lead with "most likely cause:"** — so the reader knows it's a guess.
- If a tool returned nothing, **say "I searched X and didn't find anything"** — don't pretend you didn't search.
- If a number, file name, or error code isn't in the source, **don't invent one**. Say "the source doesn't mention a specific X."
- If you're uncertain, **just say so**. "I'm not sure whether…" or "Worth checking before you act on this."
- If something looks wrong but you can't confirm it, **say "looks suspicious — verify before acting"** — don't promote a hunch to a fact.

**What NOT to do:**

- Don't use the words `EXTRACTED` or `INFERRED` to label claims. Plain English only.
- Don't hedge every sentence — overhedging is its own dishonesty (signals nothing).
- Don't make up file paths, line numbers, function names, error codes, or API endpoints to fill out a section. Empty sections are fine.
- Don't promote "the source says X" when the source said "X probably" or "X is one option."

The point: a confident wrong answer is way worse than admitting you don't know. If you don't know for sure, say it out loud. The reader will trust you more.

## Diagram syntax — ASCII flowchart is the safer default; mermaid only when target supports it

**Default: ASCII flowchart.** It renders in every markdown viewer, every plain-text editor, terminal output, email, and copy-paste destination — because it's just monospace characters. No renderer required. For persisted docs in `docs/` or files a recipient might open in any viewer (including a stripped-down preview, a file:// URL, or grep output), **prefer ASCII over mermaid.** walk.md's canonical example uses ASCII flow exactly for this reason.

```
User input ──► AJAX POST ──► Browse_ajax.asp ──► clsDAL.RunSP ──► pBrowse<Entity>
     │              │                │                                   │
     │              └─ wraps as       └─ reads Request.Form               └─ wraps as
     │                 form-data         (no QueryString)                    '%' + @filter + '%'
     │                                                                       in WHERE LastName LIKE
     └─ typed in #txtSearch                                                  (substring match)
```

Use Unicode box-drawing characters: `│` `─` `┌` `┐` `└` `┘` `├` `┤` `┬` `┴` `┼` `▼` `►` `──►`. Fit within ~90 columns so monospace previews don't wrap. Wrap the whole block in triple-backticks with no language tag (plain code block) — that locks in monospace rendering everywhere.

**Use mermaid only when:** (a) the target rendering environment is confirmed to support it (GitHub UI, GitLab UI, VS Code with the Mermaid extension installed, Confluence with the mermaid plugin enabled, Mermaid Live Editor), AND (b) the diagram has dynamic-layout needs (very wide fan-out, deep nesting, dense edges) that ASCII can't reasonably express. Inline chat answers in this CLI session render markdown text, NOT mermaid — so even inline mode prefers ASCII.

**When you do use mermaid**, follow the renderer-safe subset in `references/diagrams.md` (no HTML in labels except `<br/>`, nothing complex in edge labels, test in the strictest target).

## Presentation rules

Output goes inline to the chat. Use the visual elements that fit the mode:

| Mode | Visual elements |
|---|---|
| `pr` | Diff block (with inline icon annotations), Ticket-vs-PR alignment list, Impact-at-a-glance table, prose risks |
| `qa` | Test-case table (pre-test) OR Jira-vs-code table (post-test), short prose sections |
| `boss` | Impact-at-a-glance table OR Phase-shape table + ASCII phase-bar, short prose |

**Restraint rules (all modes):**
- Tables ≤ 6 rows. Beyond that, it's a deck.
- Max 2 tables per rendering.
- No emoji decoration. Icons (🔴/⚠/🟢) and the 🌮 are the only emojis allowed, and only in pr/qa (not boss).
- One key number per section in bold, max.
- If you have 6+ bullets, that's a table waiting to happen.

## Length targets

| Mode | Word target |
|---|---|
| `walk` -- inline (chat answer) | <= 700 words |
| `walk` -- persisted (writes to a file) | <= 1200 words total; **soft warning at >300 words per `###` section** |
| `pr` | <= 600 words |
| `qa` | <= 700 words |
| `boss` | <= 400 words |
| `baby` -- inline (chat answer) | <= 1800 words |
| `baby` -- persisted (writes to a file) | <= 3000 words total; **soft warning at >300 words per `###` section** (inherited from walk) |

Soft caps. Going 10% over is fine; going 50% over means the rendering is rambling — tighten.

**Why walk has two caps:** an inline chat walk-mode answer and a persisted doc landed-on-cold are different shapes. Inline answers can lean on conversational context; persisted docs need metadata, citations, code, charts — supporting material that earns its words but inflates the count without adding rambling. The validator detects persistence from the invocation mode (`--input-file` and `--examples-file` are persisted; `--input-string` is inline) or via the explicit `--persisted` override flag.

**Why a per-section warning:** the relaxed 1200-word total cap gives more rope. The per-section soft warning (fired to stderr when any `###` section exceeds 300 words but does NOT fail the validator) restores the second-order check that the original tight cap was incidentally doing — catching one bloated section in an otherwise OK doc. Design pattern: when you relax one constraint, add a smaller compensating constraint for the side effect.

## What this skill does NOT do

- Write to any file. Output is inline only.
- Translate code to natural language line-by-line.
- Generate diagrams (use `graphify`).
- Auto-publish to Jira / Confluence / Slack.
- Have a `--clean` flag. Use `boss` mode instead.
- Sanitize jargon out of an explanation. The dropped kid / family / non-tech mode failed because analogy REPLACED jargon -- readers walked away unable to talk to engineers. **`baby` mode is the replacement: analogy walks ALONGSIDE jargon, never instead of it.**

## Files and the validator

Open only the playbook for the mode in use, and its examples file when the
tier or tone is unclear:

- `references/walk.md`, `pr.md`, `qa.md`, `boss.md`, `baby.md`, `code-explain.md` -- voice and structure rules per mode.
- `references/examples/` -- worked renderings: `walk-examples.md`, `pr-examples.md`, `qa-examples.md`, `boss-examples.md`, `baby-examples.md`, `code-explain-examples.md`.
- `references/diagrams.md` -- mermaid syntax rules; open only when a diagram must be mermaid.
- `references/validator.md` -- what `htsw-check.py` checks; open it when a check fails.

Check a rendering before handing it over:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/personal-htsw/htsw-check.py" --input-file <path-to-rendering.md>
```

Exit 0 = pass, exit 1 = fail with detail. The script checks shape, not truth.
