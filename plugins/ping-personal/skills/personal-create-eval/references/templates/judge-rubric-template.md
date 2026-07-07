# Judge Rubric: <skill-name> (taste dimension)

> Use ONLY for what `eval.ps1` cannot measure. The code grader already checks structure /
> deterministic facts; this rubric judges the subjective quality. Reason-first per the
> playbook (observations BEFORE the score). Fill every <...>; delete this block when done.

## When to run this judge

- <after the skill produces a taste-sensitive artifact; or as a calibration spot check on a
  known-good fixture so the judge agrees it is strong>

## What it judges (the failure modes code cannot reach)

- <F0?> <the subjective failure>

## Judge Prompt (reason-first)

```text
You are a strict evaluator of <artifact type>. Judge ONLY the supplied artifact. Do not reward
a <friendly/valid> artifact that is actually <wrong/bad>.

Task the artifact was trying to do:
<task>

Artifact:
<artifact>

Rubric (anchors -- define the ENDPOINTS and the midpoint, not just a scale):
- 0: <clearly-bad anchor>
- 1: <poor anchor>
- 3: <acceptable anchor>
- 5: <excellent anchor>

Rules:
- Do not reward missing content; if required evidence is absent, say so.
- Give scores across the FULL spectrum (0-5), not only 3-5.   <-- anti-leniency
- If you cannot verify a claim from the artifact alone, list it under uncertainty; do not assume.
- List observations BEFORE choosing the score.

Return JSON (observations first, score last):
{
  "positive_evidence": ["..."],
  "negative_evidence": ["..."],
  "missing_or_unclear": ["..."],
  "score": 0,
  "verdict": "pass" | "fail" | "needs_review",
  "actionable_fix": "..."
}
```

## Guardrails (encode as CODE, not prose)

- <e.g. "if the artifact has no <modality>, set <modality>_score = 0"> -- a sentence in the
  prompt is unreliable (proven: same no-image condition scored 0.86/0.26/2.06). Enforce in code
  AFTER the judge returns. Decide the POLICY: is a missing modality neutral (full credit) or a
  mandatory zero? It depends on whether the modality is required.
- No-data sentinel: return `-` (not `0`) when there is nothing to judge, so the aggregator skips
  it instead of counting a missing artifact as a real zero.

## Ship interpretation

- `verdict: fail` -> the artifact regressed the core promise; fix before relying on it.
- `needs_review` -> human spot check; a model-judge score is a SIGNAL, not truth -- never stack a
  probabilistic judge on a safety boundary and call it verified.
