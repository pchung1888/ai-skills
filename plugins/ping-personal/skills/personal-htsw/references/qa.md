# qa — test-design or bug-writeup playbook

## What this is for

Two situations:

1. **Pre-test:** you have a Jira story and you're about to design test cases.
2. **Post-test:** you found a bug. The code isn't doing what the story said.

This playbook handles both, in the htsw voice. There is no separate "clean" version of QA output — if you need a polished version for filing in Jira or sharing with a client, use `boss` mode.

## How the skill picks the variant

It looks at the source. If the source has any of these markers, it's a bug writeup (post-test):

- `Observed:` / `Observed behavior:`
- `Actual:` / `Actual result:`
- `What I see:` / `What happens:`
- `Actually:` / `In reality:`
- `Bug:` / `Defect:` / `Failure:`
- `Repro:` / `To reproduce:` / `In production we saw…`
- "Spec says X but…" / "…but observed Y"
- Any two clearly-contrasting sections (one prescriptive, one descriptive)

Otherwise it's a pre-test brief.

If the source is ambiguous, the skill renders pre-test AND adds a one-line note at the bottom:
`If you found a bug, re-run with one of the markers above included in your source.`

## Workflow shape

```
[Jira story]  ──►  [Read spec carefully]  ──►  Has observed behavior?
                                                  │
                              ┌───────────────────┴───────────────────┐
                              │ no (pre-test)                         │ yes (post-test)
                              ▼                                       ▼
                  [Design test cases]                  [Jira vs. code reality-check table]
                  [Flag edge cases]                    [Hypothesis (labeled as guess)]
                  [Flag regressions to watch]          [Where to look / how to file]
                              │                                       │
                              └─────────► [Test brief output] ◄───────┘ [Bug writeup output]
```

## The voice — three modes

| Mode | When | Sounds like |
|---|---|---|
| 1 — Baseline | Spec is average; you're designing routine test cases | "OK so the spec says X. Here are the cases that exercise the real risk." |
| 2 — Salty (PG/R) | You found a bug | "The bypass isn't bypassing — which is the whole damn point of having 'all' in the spec." Mode 2 is the post-test voice. |
| 3 — Warm + 🌮 | The spec is well-written (pre-test only) | "This spec is solid 🌮 — acceptance is concrete, idempotency is named, the resurrection edge case is called out." |

**Post-test variant skips Mode 3 entirely.** You found a bug; celebrating the spec while writing up its violation reads tone-deaf. Save the praise for the next good spec.

### Voice intensity — density rule (don't be polite when shit's broken)

How loud you get is a function of how many 🔴 / ⚠ icons land in the body. The skill is named after "How This Shit Works" — when shit isn't working, the rendering should sound like a reviewer who's seen this fail before, not a clinical auditor reading findings to a jury.

| 🔴 count in body | Required voice load |
|---|---|
| **0-2** | Mode 1 (baseline) is fine. One Mode-2 phrase allowed but not required. |
| **3-4** | Mode 2 MUST appear in: (a) TL;DR action verb — pick the strongest available (`send it back`, `hard nope`, `block — and re-do`), (b) the What-actually-happened paragraph, AND (c) at least one body-section bullet. |
| **5+** | Mode 2 carries the **entire What-actually-happened paragraph** (every sentence in the right register). Mode-2 phrases appear in **3+ body bullets**. TL;DR opens with the strongest action verb available (`yeah no, ain't shipping`, `block this — needs a real pass`, `revert and re-do`). |

**Warning-heavy variant** (5+ ⚠ AND 0 🔴): Mode 2 stays muted, but cumulative tone shifts — TL;DR can use `address these and merge`, but the body should NOT read cheerful. Pile of warnings is its own signal even without a hard block.

**The point: a reviewer who finds 6 broken things shouldn't write like they found a typo.** The 🔴 icons signal urgency; the prose must match. Symptom of failing this rule: a rendering that uses six 🔴 markers and one "hot garbage" surrounded by neutral prose. That reads as a confused brief — the icons say BAD, the words say NEUTRAL, and the reader gets mixed signals.

**Mode 2 is calibration, not blanket profanity.** Use the strongest word in the allowed list that genuinely matches the defect — `straight-up wrong` for a clear violation, `hot garbage` for a regression with downstream impact, `broken as hell` for a feature that doesn't deliver, `the X ain't Y-ing` for a behavior that literally fails its own name (the "logout ain't logging out", the "search ain't searching"). Don't escalate past the actual defect; don't under-call it either.

### Allowed salty words (Mode 2)
`shit`, `bullshit`, `hot garbage`, `damn`, `goddamn`, `hell`, `wtf`, `broken as hell`, `straight-up wrong`, `sketchy as hell`.

### Allowed warm words (Mode 3, pre-test only)
`beautiful`, `awesome`, `fantastic`, `solid`, `clean`, `tight`, `chef's kiss`, `nailed it`, 🌮.

### Banned (always)
- The f-word. PG/R only.
- Personal attacks on the author. Criticize the code or the spec, not the human.
- Praise-washing. "Great spec!" without saying WHY is worse than no praise.

## Honest protocol (plain English)

- If the spec doesn't say something, say "the spec doesn't say" — don't fill it in.
- If your hypothesis about the bug is a guess, lead with "most likely cause" — don't promote a guess to a fact.
- If you can't reproduce the bug, say so — don't pretend you could.
- If the bug report doesn't include reproduction steps, ask for them; don't invent them.
- If you don't know which file the bug is in, say "look at the handler for X" instead of inventing a file path.

A confident wrong answer wastes a developer's day. Honest uncertainty saves it.

## Evidence-and-suggestion contract — EVERY ⚠ AND 🔴 CLAIM

**This is the load-bearing honesty rule for QA renderings.** When you mark something ⚠ or 🔴, you're either accusing the dev of shipping a bug or accusing the spec of being broken. You don't get to make that accusation on vibes. Every accusation MUST satisfy both:

### Required: a verifiable evidence marker

The claim must be backed by at least ONE of these forms of evidence — and the marker must appear in the **body** (Jira-vs-code table / Where to look / Edge cases / Spec gaps) where the claim is elaborated. The TL;DR itself can stay terse; it's allowed to summarize without inline citations because the body backs each bullet up.

| Evidence form | What it looks like (QA examples) |
|---|---|
| File + line reference | `` `handlers/logout.ts:42` `` or `handlers/logout.ts L42-L51` |
| Direct quote from the spec | `> the spec says: "all sessions for this user"` |
| SQL/query evidence | `` `SELECT user_id, is_active FROM sessions WHERE user_id = X` shows 1-of-N rows updated `` |
| HTTP response evidence | `` `GET /api/me` from Device B returns 200 + full payload (expected 401) `` |
| Reproduction steps | A numbered list of 3-6 concrete steps that produce the observed behavior |
| Negative observation | "the spec doesn't mention what happens when zero sessions exist" |

If you can't produce any of these for a claim, **drop the claim**. Honest gap > confident accusation.

### Required: a concrete suggestion

Every ⚠ and 🔴 needs to be followed (in the body) by what to do about it. **The arrow-verb you pick is part of the contract — it tells the reader how to triage the finding:**

| Arrow | Meaning | Example |
|---|---|---|
| `→ fix:` | A defect that must be addressed before merge / re-test | `→ fix: change the UPDATE to key on user_id instead of session_id` |
| `→ suggestion:` | A should-do that's strongly recommended before merge | `→ suggestion: add a test case covering the all-device path before considering this fixed` |
| `→ optional:` | A nice-to-have improvement; not blocking, fine to defer | `→ optional: add a smoke test for the cache-invalidation atomicity edge case` |
| `→ next:` | A follow-up action for after the bug lands (separate ticket / future test pass) | `→ next: file the ticket with the reproduction steps in section 8 below` |
| `→ ask:` | A question for the PM, the dev, or a stakeholder | `→ ask: what's the expected behavior when the user has zero active sessions?` |

A ⚠ or 🔴 without a suggestion is just complaining. The dev or PM should be able to read your accusation and know exactly what to do next — AND whether the finding blocks the fix or can be deferred.

**Don't pile must-do and nice-to-have under the same arrow.** Match the arrow to the actual severity so a busy reader can scan and skip the optional items.

**The validator (`htsw-check.py`) enforces the structural side of this rule:** every ⚠ or 🔴 outside the TL;DR is checked for both an evidence marker and a suggestion-arrow marker. The validator can't verify the *truth* of a claim — it only verifies that the claim has the shape of something a reader could verify. If the validator passes a rendering whose claims are factually wrong, that's a Mode-2 problem with the author, not the validator.

## Tester discipline — the four karpathy pillars (in plain English)

QA reads other people's specs and writes tests against them. Tester discipline is the difference between a test plan that earns the dev's respect and one that gets ignored. Each pillar adapts [Karpathy's LLM coding pitfalls](https://x.com/karpathy/status/2015883857489522876) to the tester's seat:

| # | Pillar | Implementer-form (Karpathy) | Tester-form (htsw QA) |
|---|---|---|---|
| 1 | **Surface assumptions** | State your assumptions; ask if uncertain | If the spec doesn't say a behavior, **don't test for it without asking**. Flag as 🔴 in Spec gaps, follow with `→ ask: PM`. Don't quietly invent test inputs based on a hunch. |
| 2 | **Simplicity first** | Minimum code; no speculative features | **Minimum test cases that prove the feature works.** Four cases that exercise the real ACs beat twelve cases that test impossible scenarios. Don't pad the table to look thorough. |
| 3 | **Surgical test scope** | Touch only what you must | **Surgical test cases.** Every test row traces to an AC or to a stated edge case in the spec. Don't smuggle in "while you're testing this feature, also retest the login flow" — that's a separate ticket. |
| 4 | **Goal-driven** | Define verifiable success | **Every test case has a verifiable expected output.** "Manually check the screen" doesn't count. SQL row count, HTTP status code, specific text, AJAX response shape — concrete. The validator can't enforce this; the tester carries it. |

**Pillar 5 — pipeline awareness (for non-trivial features):** Karpathy's planning pipeline (Researcher → Plan → Critic) exists because non-trivial work without it ships with avoidable bugs. When the spec describes a non-trivial feature (multi-table writes, multi-page flows, COM bridge calls, cross-mode UI gating) **AND** there's no visible research step (the spec doesn't cite existing related tests / SP signatures / DOM ids), the tester can probe with `→ ask: was there a research step that named the existing related test fixtures so this test plan doesn't duplicate them?`. Soft probe, not a hard contract — only fire when the spec really doesn't show grounding.

**Why translate the pillars rather than copy them:** Karpathy's pillars are written for the dev who's about to *write* the code. QA runs when someone is about to *test* the code. The behaviors look different on the two sides — "minimum code" (implementer) becomes "minimum tests" (tester); "surgical changes" (implementer) becomes "surgical test scope" (tester). Same spirit, different verb.

**Project-portability note:** This section exists in `qa.md` (and `pr.md`, and `SKILL.md`) so the karpathy discipline travels with the skill. Wrappers on other machines that haven't installed `/karpathy` still get the behavior through htsw itself. Don't `Skill(karpathy)` from inside htsw.

## Plan-mode input — when the source is a plan doc, not a spec

Pre-test QA is built for Jira specs. When the source is a forward-looking implementation plan (a doc with `## Phase N` / `**File Map**` / `**Files NOT touched:**` / `**Goal:**` headers), the contract still applies but two sections shift their framing:

| Section | Spec-mode framing | Plan-mode framing |
|---|---|---|
| **Coverage at a glance** column "AC #" | Acceptance criterion from Jira | "Phase / Task #" from the plan |
| **Coverage at a glance** column "Spec line" | Quoted text from the Jira ticket | Quoted goal-statement or task title from the plan |
| **Spec gaps** section | Questions for the PM | "Plan gaps" — questions for the plan author about what *isn't* in the plan but should be tested |

Everything else (tier title, TL;DR, HOW-WORKS, Test cases, Edge cases, Regressions to watch) renders normally. Action verbs shift: `test against this plan`, `defer tests, ask planner first`, `test-design hinges on Phase 2 clarity`.

**When does this branch fire?** Detect plan-mode input by structural signals in the source: `## Phase N` heading, `## File Map` / `**File Map**` section, explicit `**Files NOT touched:**` list, `**Goal:**` / `**Spec reference:**` header pair. Two or more signals = plan mode. A Jira ticket export with "Acceptance Criteria" / "Description" / "AC #" is always spec mode.

**Pipeline-awareness probe lands here too.** If the plan has no visible spec / no research findings / no critic pass, the karpathy pillar-5 probe fires as `🔴 <plan-has-no-critic-step>` in Plan gaps with `→ ask: was the spec / research / critic pipeline run before this plan was written?`.

**Why a sub-branch rather than a new mode:** the surrounding contract (tier title, TL;DR, HOW-WORKS, evidence-and-suggestion, test-case table shape) is identical — only two cells shift. A separate `/personal-htsw plan-qa` mode would double the validator's test surface for what is essentially one column-rename rule.

## The signature element — tier title

**This is the skill's signature.** Every QA rendering opens with a catchy, street-real headline that signals the verdict in the first half-second. Body stays blunt and analytical. Title carries the energy.

Pick ONE title per rendering from the library below. Vary across renderings.

### Tier title library — PRE-TEST variant (four tiers, four icons)

**GOOD spec (🌮 — the Jira story is well-written):**
- `## 🌮 PM nailed this spec`
- `## 🌮 Easy to test — chef's kiss`
- `## 🌮 Spec slaps`
- `## 🌮 No ambiguity, big W`
- `## 🌮 This is what a good story looks like`
- `## 🌮 Acceptance criteria done right`

**PASS spec (🟢 — the spec is testable, no celebration needed, no problems either):**
- `## 🟢 Testable as-written`
- `## 🟢 Clear enough — let's test`
- `## 🟢 Spec is fine, let's get to work`
- `## 🟢 Gets the job done`
- `## 🟢 Routine spec, routine tests`
- `## 🟢 No drama — proceed`

PASS-tier voice is Mode 1 (baseline). The spec is good enough to write tests against; no need to celebrate, no need to flag anything. Get on with it.

**WARNING spec (⚠ — workable but with minor gaps that aren't critical):**
- `## ⚠ Workable spec, needs PM clarification on a few things`
- `## ⚠ Solid happy path, edge cases missing`
- `## ⚠ Mostly clear, some gaps`
- `## ⚠ Good intent, ambiguous in spots`
- `## ⚠ Testable today, better with answers`
- `## ⚠ Close — but ask PM first`

WARNING-tier voice is mostly Mode 1 with a few ⚠ items. The spec is testable, but you'll want PM clarification before writing tests that depend on the ambiguous parts. Distinct from a hypothetical BAD spec tier (untestable, send back to PM); there is no BAD pre-test tier here — if a spec is untestable, the right action is to escalate, not write tests.

### Tier title library — POST-TEST variant (bug found — open with 🔴)

- `## 🔴 This shit ain't doing what the spec says`
- `## 🔴 Found a real one`
- `## 🔴 Reality check failed`
- `## 🔴 Spec says X, code does Y`
- `## 🔴 The bypass ain't bypassing`
- `## 🔴 Yeah, this is broken`
- `## 🔴 Spec says ALL — code says one`
- `## 🔴 Bug confirmed — here's the breakdown`
- `## 🔴 Not a feature, a defect`

### Banned title patterns (generic = boring = no signature)

The validator rejects any of these as the tier title:
- `## QA Review`
- `## QA Brief`
- `## Test Plan`
- `## Summary`
- `## Overview`
- `## Brief`
- `## Introduction`
- `## Intro`

Generic titles read like a stock template — the skill's signature is that it never does.

## Pre-test variant — required structure

### 1. Tier title (REQUIRED — see signature element above)

Pick one from the pre-test library — GOOD or FAIR.

### 2. TL;DR — verdict-first scannable block (REQUIRED)

**Right after the tier title.** Three lines max. The label is `**TL;DR — <action verb>:**` where the verb IS the verdict — no separate "Verdict:" line in the rendering.

| Spec quality | Action-verb examples |
|---|---|
| GOOD spec | `test against it`, `green-light it`, `easy day`, `chef's-kiss spec` |
| FAIR spec | `test it, ask PM first`, `workable, with caveats`, `clarify three things` |

Body is 2-4 bullets. Each bullet leads with 🟢/⚠/🔴, then a **bolded noun phrase**, then a short reason. ≤ 15 words/bullet, ≤ 60 words total.

Example:
```
**TL;DR — test against it:**

- 🟢 **All 4 ACs covered** by test cases #1–#4.
- ⚠ **Cache atomicity edge case** — confirm with PM before writing test #5.
- 🟢 **No spec gaps** worth blocking on.
```

### 3. How this shit works (REQUIRED — plain-English explanation of the feature)

**This is the skill's namesake section.** Two to four sentences explaining what the feature is supposed to do, in plain English. A test designer who skipped the spec should be able to read this paragraph and walk away knowing what behavior to exercise.

Pick ONE heading from the library. Vary across renderings.

**Section-header library — pick one:**
- `### How this shit works`
- `### What this is supposed to do`
- `### In plain English`
- `### The intended flow`
- `### How it should behave`
- `### What the user sees`
- `### The expected mechanics`

**What goes in the section:**
- The *purpose* of the feature in one sentence: "When the user clicks 'Log out', the app is supposed to terminate every active session for that user across every device."
- The *flow* in 1-2 sentences: "On click, the backend flips `is_active=false` for every session row matching the user, and any subsequent `/api/me` call from any device should return 401."
- (Optional) the *invariant* worth testing: "The crucial bit is *every* session, not just the initiating one — that's where the spec earned its strong wording."

This section is the **bridge from spec text to test cases**. Without it, the test cases below have no shared mental model; with it, every test case explicitly exercises the flow described here.

**Hedge rule for causal claims:** if a sentence describes a cause-effect chain that isn't directly observable from the spec (a "because", "causes", "triggers", "due to"), qualify it with `most likely`, `appears to`, `seems to`, `probably`, or `looks like`. Direct quotes from the spec don't need hedging — only inferences about runtime behavior do. A hedge costs one word and protects the reader from over-trusting an unverified mechanism.

### 4. Coverage at a glance (required — table summarizing AC coverage)

A short table mapping each acceptance criterion to whether your test cases cover it.

| AC # | Spec line | Covered by |
|---|---|---|
| 1 | All sessions invalidated | 🟢 Test cases #1, #2 |
| 2 | /api/me returns 401 | 🟢 Test cases #1, #2 |
| 3 | Idempotent | 🟢 Test case #4 |
| 4 | Expired sessions stay expired | 🟢 Test case #3 |

If an AC isn't covered, mark it 🔴 and add a row in the spec-gaps section.

### 5. Test cases (required — table with Status column)

| # | Status | Input | Expected |
|---|---|---|---|
| 1 | 🟢 | 1 active session, logout | row `is_active=false`; `/api/me` → 401 |
| 2 | 🟢 | 3 active sessions, logout from one | all 3 rows false; `/api/me` → 401 on all 3 |
| 3 | ⚠ | Logout when session cache exists | Cache invalidated atomically? Check with PM |

Status meanings:
- 🟢 — this case covers a spec acceptance criterion directly
- ⚠ — edge case worth probing; not explicit in the spec
- 🔴 — spec gap; need PM clarification before writing the test

### 6. Edge cases worth probing (optional)

Bulleted list. Each item prefixed with ⚠.

> - ⚠ Concurrent in-flight request mid-logout — see pre-logout or post-logout state?
> - ⚠ Cache invalidation atomicity (if a cache exists in this codebase)

### 7. Regressions to watch (optional)

Bulleted list. Each item prefixed with ⚠.

> - ⚠ Login flow unaffected — confirm with smoke test
> - ⚠ "Remember me" tokens (out of spec scope) stay in a separate path

### 8. Spec gaps (optional — fires when the spec has material gaps)

Bulleted list of questions to ask the PM before writing tests. Each item prefixed with 🔴.

> - 🔴 What's the behavior when zero sessions exist? Spec doesn't say.
> - 🔴 Is logout async or sync from the client's perspective?

## Post-test variant — required structure

**Mode 3 is unavailable here.** You found a bug; celebrating reads tone-deaf.

### 1. Tier title (REQUIRED — pick from the POST-TEST library above)

A 🔴-opening street-real headline. Examples: `## 🔴 This shit ain't doing what the spec says`, `## 🔴 Found a real one`, `## 🔴 Spec says X, code does Y`.

### 2. TL;DR — verdict-first scannable block (REQUIRED — no 🌮)

**Right after the tier title.** Three lines max. Label is `**TL;DR — <action verb>:**`.

Action verbs (post-test only — all signal "this is broken, act on it"):
`file it`, `block the release`, `escalate`, `fix before ship`, `hotfix candidate`, `revert and re-do`, `send back to dev`.

Body is 2-4 bullets. Each bullet leads with 🔴 (the violation) or ⚠ (a hypothesis or related risk), then a **bolded noun phrase**, then a short reason. No 🌮. No 🟢 in the TL;DR — green never matters when there's a bug on the table.

Example:
```
**TL;DR — file it:**

- 🔴 **Logout only kills the initiating session** — spec says "all devices".
- 🔴 **Security implication** — clicking "log out" doesn't log you out elsewhere.
- ⚠ **Most likely cause** — `UPDATE` keys on `session_id` instead of `user_id`.
```

### 3. How this shit works (REQUIRED — plain-English explanation of the bug)

**This is the skill's namesake section.** Two to four sentences explaining (a) what the feature is supposed to do and (b) what it's actually doing instead. A dev who skipped the table should be able to read this paragraph and walk away knowing the bug.

Pick ONE heading from the library. Vary across renderings.

**Section-header library — pick one:**
- `### How this shit works`
- `### What's actually happening`
- `### In plain English`
- `### The real flow`
- `### What's broken about it`
- `### Under the hood`
- `### The mechanics of the bug`

**What goes in the section:**
- The *intended flow* in one sentence: "On logout, the backend is supposed to mark every session for the user as inactive."
- The *actual flow* in 1-2 sentences: "Instead, only the session belonging to the device that initiated the logout is updated; sessions on other devices remain active and continue to authorize requests."
- (Optional) the *user-visible impact* in one sentence: "From a user's perspective, clicking 'Log out' on their phone leaves them logged in on their laptop."

This section is the **bridge from the reality-check table to the where-to-look pointers**. Without it, the dev has to reconstruct the bug's shape from the table rows; with it, they can read three sentences and immediately understand both what's wrong and what the fix needs to achieve.

**Hedge rule for causal claims:** if a sentence describes a cause-effect chain that isn't directly observable (a "because", "causes", "triggers", "due to"), qualify it with `most likely`, `appears to`, `seems to`, `probably`, or `looks like`. A bug writeup's hypothesis is by definition a guess — and the hypothesis section already labels it ⚠ — but the HOW-WORKS section is where readers expect mechanism, and an un-hedged mechanism reads as fact. Hedge inferences; observe what's actually in the code or response.

### 4. Jira vs. code — reality check (REQUIRED)

The load-bearing artifact. A table with **Status as the first column**.

| Status | Spec says | Code does | Evidence |
|---|---|---|---|
| 🔴 | Logout invalidates ALL sessions for user | Invalidates only the initiating session | `SELECT user_id, is_active FROM sessions WHERE user_id = X` → 1-of-N rows updated |
| 🔴 | /api/me returns 401 from every device | Returns 200 from non-initiating devices | `GET /api/me` from Device B post-logout returns 200 + full payload |
| ⚠ | Logout is idempotent | Untested — primary defect blocks observation | Will test after the 🔴 rows are fixed |

Even if the bug is narrow, pick the 1-3 spec lines that touch the bug and show them side-by-side. The icons let a developer scan the table in two seconds and find the 🔴 rows they need to fix.

### 5. What actually happened (required — Mode 2 voice, prefixed 🔴)

> 🔴 Users who log out from one device remain authenticated on their other devices. `/api/me` happily hands out their data. The logout isn't logging anything out except the device that started it — which is the whole damn point of having "all" in the spec. Security implication: clicking "log out" doesn't log you out.

### 6. Why this is likely broken — hypothesis (required — ⚠ prefix because it's a guess)

> ⚠ Most likely cause: the logout handler's `UPDATE` keys on `session_id` (the current request) instead of `user_id`. Single-device logout instead of all-device. Classic — somebody read "logout" and implemented the obvious thing without re-reading the "all devices" part.

### 7. Where to look (required — icon per pointer)

- 🔴 The logout endpoint handler — find the `UPDATE` statement, check the WHERE clause.
- ⚠ The session-cache layer (if there is one) — make sure cache invalidates on logout.
- ⚠ Auth middleware — confirm it reads `is_active` on each request, not just JWT signature.

### 8. How to file the ticket (required)

```
Title: "Logout invalidates only initiating session; spec requires all-device"

Reproduction steps:
1. Log in on Device A.
2. Log in on Device B as the same user.
3. Log out on Device A.
4. On Device B, call /api/me.
5. Observed: 200 with user data. Expected: 401.

Severity: Security — users who log out aren't actually logged out.
```

### 9. Test cases to add once fixed (required — table with Status column)

| Input | Status |
|---|---|
| User with 1 session logs out → `/api/me` 401 | 🟢 covers the primary fix |
| User with 3 sessions logs out from one → all 3 → 401 | 🟢 covers the all-device requirement |
| Concurrent logout race | ⚠ regression watch |
| Logout when already inactive | ⚠ idempotency |

## Length

Under 700 words total. Post-test variant has more sections so it's usually closer to the cap; pre-test variants come in under 500 most of the time.

## Examples

**`.claude/skills/personal-htsw/references/examples/qa-examples.md`** — one pre-test example (well-written spec earning 🌮) and one post-test example (logout bug with the full Jira-vs-code table). Both use icons throughout.

## Validator

Cross-platform (Mac/Linux/Windows):

```bash
python3 .claude/skills/personal-htsw/personal-htsw-check.py --input-file <your-rendering.md>
```

For QA mode it checks:

- First-line citation.
- Tier title present and non-generic; post-test titles MUST contain 🔴.
- **TL;DR section present with 2-4 icon bullets**, right after the tier title.
- **HOW-THIS-SHIT-WORKS section present** with one of the allowed header variations.
- At least one 🔴/⚠/🟢 icon somewhere.
- Status column present in the relevant table (Jira-vs-code table for post-test; test-case table for pre-test).
- No 🌮 in post-test variants.
- **Evidence-and-suggestion contract**: every ⚠ or 🔴 outside the TL;DR is paired with an evidence marker (file:line, SQL/HTTP evidence, quoted spec, reproduction steps) and a suggestion-arrow marker (`→ fix:`, `→ suggestion:`, `→ optional:`, `→ next:`, `→ ask:`).
- Length ≤ 700 words.
