# Judge rubric: personal-ask-like-expert

Use this for what `eval.ps1` cannot measure: is the rewrite actually better? The judge reads the
fixture question and the skill's output, writes observations first, then scores.

## Metric

Eight criteria, each scored 0, 1 or 2. Total is 0-16. The run score is the mean total over all
fixtures in `fixtures/`.

| # | Criterion | 0 | 1 | 2 |
|---|---|---|---|---|
| C1 | Expert gap | generic advice anyone would give | names a gap, but a shallow one | names what a real practitioner does that the question missed |
| C2 | Raw material | none, or a summary source | names a source, not the rawest one | names the primary source (log, spec, dataset, measurement) |
| C3 | Methods and tools | "best practices", no names | some names, some vague | real, named methods and tools fit for this question |
| C4 | Outside check | none, or "ask an AI" | a check that is weak or hard to run | a concrete outside check that would catch a wrong result |
| C5 | Deeper, not bigger | adds new deliverables or scope | some scope creep | same scope, sharper ask |
| C6 | Usable by a novice | no term glosses; prompt not pasteable | partly glossed or partly pasteable | every new term glossed; one pasteable prompt block |
| C7 | Ask check | takes the ask at face value | checks it, but misses a wrong term, a legacy technology or a better option the fixture contains | catches each wrong term or legacy technology, and names any counter-option by its real name; says so in one line when the ask is sound |
| C8 | Current sources | no sources | sources, but undated or not on the status and tool claims | status and tool claims cite a fetched URL and the date checked |

## Judge prompt

```text
You grade one output of the personal-ask-like-expert skill. Do not rewrite it yourself.

Fixture question (from a person new to the field):
<fixture>

Skill output:
<output>

First write 2-4 observations per criterion, quoting the output. Then score C1-C6 with the
anchors in judge-rubric.md. Return: observations, scores C1..C8, total, and the single
change to the SKILL.md that would raise the lowest score.
```

## Calibration

A bare rewrite of the question with no expert content should score 0-4. The skill's job is a
total of 12 or more on every fixture. That target is set by this rubric, not by the user; change it
if real use shows it is wrong.
