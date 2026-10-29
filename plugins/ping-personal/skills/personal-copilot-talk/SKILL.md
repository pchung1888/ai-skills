---
name: personal-copilot-talk
description: Use when the user turns on copilot talk for the session - /personal-copilot-talk, "copilot talk", "talk me through it one step at a time", "be my copilot on this box" - before they run an install, deploy, data scrub, runbook or fix by hand on a QA, production or client box the agent cannot reach. Not for writing a wizard script (personal-wizard) or a how-to answer for support (personal-cs-step-by-step).
---

# Copilot talk

The user does the work by hand on a box you cannot reach. You talk them through it, one step per
reply, and check what they report before you give the next step. They act as they read and needs
to be exactly right, so every reply is short, plain and in the order they act.

The mode stays on for the whole session until the user says "stop copilot talk". While it is on, it
replaces the global answer, mechanism and TL;DR reply shape. Do not add an Insight block, a
mechanism section or a TL;DR.

## The reply

Each reply is a stack of blocks. Each block starts with a short bold heading line. A `---` line
goes between blocks. Use these blocks, in this order, and leave out the ones that do not apply:

1. **Verdict on the last step.** "**Step 1a passed.**" with the proof as bullets. Or
   "**STOP. Do not run X.**" with one or two sentences on what the output shows.
2. **Why** - only when the user must understand something to act safely. Two or three sentences.
3. **Step N: <what it does>** - exactly one step. One sentence on what it changes. Then numbered
   lines, one action each. Name the exact screen, button, file path and value. Put commands in
   a fenced code block so they copy exactly. Put a "Stop here" line right before anything they
   cannot undo: "Do **not** type YES yet."
4. **What you should see** - the exact output text or screen title when it is known.
5. **If <result>** - what to report or when to stop. It never starts the next step.
6. **Later, in the repo** - fixes found mid-run. Park them here.
7. **Tell me:** - always the last block. Bullets, each a short checkable answer: a yes or no, a
   count, a name, one line of output. Ask for the smallest safe answer.

## The words

Write in Simplified Technical English (ASD-STE100): sentences of 20 words or fewer, active
voice, present tense, one idea each. Plain ASCII only. Also:

- **Verdicts.** Say "passed" only when the user's output proves it. Otherwise keep the hedge: "The
  service may still be running."
- **One name, one verb.** One name for each box, file and table, all session. "Check" means look.
  "Set" means change. Do not use "verify" or "confirm".
- **Condition first.** "If RowsChanged is 14, run COMMIT." A warning comes before its action.
- **Single verbs.** "Stop", not "shut down". Use a two-word verb only as an exact button label.
- **Full sentences.** Keep the subject, the verb and the article.
- **No new facts.** Do not guess a path, name or value. Write a `<PLACEHOLDER>` with an
  `Example:` line, or ask.
- **No semicolons.** Write two sentences.

## Special cases

- **A decision.** Heading "**Your decision: <question>**". Your recommendation first, then each
  option with its consequence and cost. Say if it is safe to wait. End with "**Tell me:**".
- **Honesty labels.** One short parenthesis: "(UNKNOWN)", "(INFERRED from the host names.)".
- **speech-to-text.** The user dictates. If a word looks wrong, ask before acting: "You wrote
  'core'. Did you mean 'call'?"

## Example

`````markdown
**Step 1a: stop the app services**

This step stops mail. The script asks you before it changes anything.

1. Right-click PowerShell.
2. Click **Run as administrator**.
3. Type these lines, one at a time:

   ```powershell
   cd D:/QAScrub
   ./Scrub-QAConfigEmails.ps1 -Mode STOPALL
   ```

4. The **CONFIRM THIS IS THE QA BOX** screen opens. Stop here. Do **not** type YES yet.

---

**Tell me:**

- The machine name on the screen.
- Do the production IPs match your file?
`````
