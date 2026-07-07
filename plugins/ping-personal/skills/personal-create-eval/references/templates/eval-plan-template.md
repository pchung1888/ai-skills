# Eval Plan: <skill-name>

> Follows the agent-evals-playbook (see ../how-to-create-an-eval.md). Fill every <...>.
> Delete this quote block when done.

## Target Behavior

<One paragraph, plain English: given INPUT, the skill must produce OUTPUT with properties
X/Y/Z, and must NOT do W. Name the LEVER (the editable skill text/prompt) vs the SUBJECT
(the artifact the user receives). The eval grades the SUBJECT.>

## Failure Modes

| ID | Failure | Why It Matters | Grader |
| --- | --- | --- | --- |
| F01 | <a concrete way the output goes wrong> | <user-visible consequence> | code/judge/human |
| F02 |  |  |  |
| F03 |  |  |  |
<!-- aim for ~10. For each, ask: "if the skill does exactly the right thing, will this metric move?" -->

## Eval Cases

| ID | Input | Expected Behavior | Must Not Happen |
| --- | --- | --- | --- |
| E01 | <known-good input> | <passes> | <the failure it guards> |
| E02 | <known-bad input> | <grader rejects it> | <grader accepting bad output> |
<!-- Tier the full set: ~5 easy + 5 realistic + 5 edge + 5 regression + 3 adversarial.
     Add a regression case for EVERY bug this eval has ever caught. -->

## Graders

### Code Graders (`eval.ps1`)  -- build these first; if code can check it, use code

- `<grader_name>`: <what fact it checks, over what extracted structure, against what threshold>
<!-- 3-state artifact check first (missing/invalid/ok). Each grader: one threshold over a
     pre-parsed fact. Calibrate: it must PASS a known-good fixture AND FAIL a known-bad one,
     and SPLIT your examples (no dead metrics). -->

### Model Judge (`judge-rubric.md`)  -- only for taste code cannot measure

- `<judge_name>`: <the subjective dimension; reason-first; anchored; anti-leniency; sentinel for no-data>
<!-- Decouple "is X present" (code grader) from "is X good IF present" (judge). -->

### Human Spot Checks

- <which cases a human reviews to calibrate the cheaper graders>

## Baseline Run

- date: <YYYY-MM-DD>
- agent version: <skill @ plugin version>
- result summary: <eval.ps1 outcome + fixture calibration evidence>

## Ship Gate

- `eval.ps1` exits 0 (all code graders green; locked good fixture still passes).
- Highest-severity failure that blocks ship: <F0?>.
