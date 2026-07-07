# Judge Rubric: personal-htsw (taste dimension)

> Use ONLY for what `eval.ps1` cannot measure. The code grader already checks the
> structural contract (citation, TL;DR, length, banned words, evidence-arrows). This
> rubric judges whether a `baby`/`walk` rendering is *actually* a good explanation.
> Reason-first scoring per the agent-evals-playbook (Step 8): observations BEFORE the score.

## When to run this judge

- After a `baby` or `walk` mode rendering, when you want to know if it teaches well
  (not just whether it passes the structural checker).
- As a calibration spot check: run on `evals/fixtures/good-baby.md` and confirm the
  judge agrees it is a strong rendering (anchors the judge against a known-good case).

## What it judges (the failure modes code cannot reach)

- **F09** baby-mode analogy *replaces* jargon instead of pairing with it.
- **F10** explanation reads beginner-friendly but is technically wrong.
- **F11** walk mode launders the salt or smuggles in a pr/qa-style verdict.

## How to run

Paste the rendering as `<artifact>` into the prompt below. Run it with the model
judge (or 3 independent judges and take the majority if the decision is high-stakes,
per playbook Step 6). Require evidence before the score every time.

## Judge Prompt (reason-first)

```text
You are a strict evaluator of an htsw "baby"/"walk" mode explanation. Judge ONLY the
supplied rendering. Do not reward a rendering for being friendly if it is wrong.

Task the rendering was trying to do:
Explain a technical subject to the audience named on its `_For:_` line (baby mode) or
to a developer new to the subject (walk mode), in the htsw voice.

Rendering:
<artifact>

Rubric (anchors):
- 0: Analogy REPLACES the jargon (reader never sees the real term), OR a clear factual
     error about how the subject works.
- 1: Jargon present but analogy is decorative/loose; or vague hand-waving ("it just works").
- 3: Every major jargon term is paired with a concrete everyday analogy that matches the
     declared audience; technically accurate; reader could repeat the real vocabulary after.
- 5: As 3, plus the analogy genuinely illuminates the *mechanism* (not just labels it), and
     the salt/voice makes a tricky part memorable without sacrificing accuracy.

Rules:
- Do not reward missing content. If a required pairing is absent, say so.
- baby mode MUST keep the jargon on the page; an analogy-only explanation scores 0.
- If you cannot verify a technical claim from the rendering alone, list it under uncertainty;
  do not assume it is correct.
- List observations BEFORE choosing the score.

Return JSON:
{
  "positive_evidence": ["..."],
  "negative_evidence": ["..."],
  "missing_or_unclear": ["..."],
  "jargon_paired_not_replaced": true | false,
  "technically_accurate": true | false | "uncertain",
  "score": 0,
  "verdict": "pass" | "fail" | "needs_review",
  "actionable_fix": "..."
}
```

## Ship interpretation

- `verdict: fail` or `jargon_paired_not_replaced: false` -> the rendering regressed the
  core baby-mode promise; fix before relying on the skill for teaching.
- `technically_accurate: false` -> highest severity (Honesty Protocol); block.
- `needs_review` -> route to a human spot check; do not silently ship on a judge alone
  (playbook: a model-judge score is a signal, not truth).
