# Eval Plan: personal-htsw

> Follows `personal-dashboard/knowledge/wiki/concepts/agent-evals-playbook.md`.
> This is the **approved-shape teaching example** for the skill-evals goal. Every
> other ping-personal skill's `evals/` folder mirrors this structure.

## Target Behavior

Given a source (a file path, or the current conversation) and a mode
(`walk` / `pr` / `qa` / `boss` / `baby` / `code-explain`, default `walk`), personal-htsw produces an
**inline** explanation in the htsw voice that conforms to that mode's output
contract: a first-line citation (an `_Explaining: ... purpose: <mode>_` line), a
title, a TL;DR block with 2-4 icon bullets, the mode-appropriate body sections,
the evidence-and-suggestion rule on every WARN/BAD-tier bullet, the per-mode length cap,
and the boss-mode banned-word / icon-free rules. It never writes files.

The skill ships its own contract checker, `htsw-check.py`, which is the code
grader. This eval verifies (a) the skill is structurally intact and (b) the
checker still measures what it claims (accepts good output, rejects bad output).

## Failure Modes

| ID | Failure | Why It Matters | Grader |
| --- | --- | --- | --- |
| F01 | First-line citation missing or malformed | Downstream tooling + the checker key off it; breaks every mode | code |
| F02 | TL;DR missing or not 2-4 icon bullets | TL;DR is the scannable contract Ping relies on | code |
| F03 | Rendering exceeds the per-mode length cap | Long renderings defeat the "fast brief" purpose | code |
| F04 | Boss mode leaks engineering jargon or status icons | Boss output goes to clients; jargon/icons break the polish contract | code |
| F05 | A WARN/BAD-tier bullet has no evidence + no fix-arrow | Verdicts without evidence are guessing (Honesty Protocol) | code |
| F06 | A documented mode silently dropped from SKILL.md | Users lose a mode without warning | code (structural) |
| F07 | A mode's reference playbook missing from `references/` | The mode's full rules vanish | code (structural) |
| F08 | `htsw-check.py` regresses (passes bad output or rejects good) | A broken grader gives false confidence | code (calibration) |
| F09 | baby mode analogy *replaces* jargon instead of pairing with it | Reader never learns the real vocabulary (the whole point of baby) | judge |
| F10 | Explanation reads beginner-friendly but is technically wrong | Confident-but-wrong teaching is worse than blank | judge |
| F11 | walk mode launders the salt or adds a pr/qa-style verdict | Loses the memorable teaching tone / mislabels as a review | judge |

## Eval Cases

| ID | Input | Expected Behavior | Must Not Happen |
| --- | --- | --- | --- |
| E01 | `fixtures/good-baby.md` (real passing baby rendering) | `htsw-check.py` exits 0 | Grader rejects a conforming rendering |
| E02 | `fixtures/bad-no-citation.md` | `htsw-check.py` exits 1 (F01) | Grader accepts output with no citation |
| E03 | `fixtures/bad-boss-banned-word.md` | `htsw-check.py` exits 1 (F04) | Grader accepts boss output with banned jargon |
| E04 | `SKILL.md` frontmatter + body | name=personal-htsw, all 6 modes documented | A mode is missing from the docs |
| E05 | `references/` directory | walk/pr/qa/boss/baby/code-explain playbooks all present | A mode's playbook is absent |
| E06 | `htsw-check.py` | file exists and is runnable | Checker deleted/renamed without updating the eval |
| E07 (judge) | a fresh baby-mode rendering | analogy pairs with jargon; beginner-correct | analogy replaces jargon; factual error |
| E08 | `references/examples/code-explain-examples.md` | `htsw-check.py --examples-file` exits 0 | Checker rejects a conforming code-explain rendering |

## Graders

### Code Graders (`eval.ps1`)

- `skill_frontmatter`: SKILL.md has `name: personal-htsw` + a description line.
- `six_modes_documented`: walk, pr, qa, boss, baby, code-explain all named in SKILL.md.
- `reference_playbooks_present`: walk/pr/qa/boss/baby/code-explain `.md` all exist in `references/`.
- `checker_present`: `htsw-check.py` exists.
- `checker_accepts_good`: `htsw-check.py` exits 0 on `fixtures/good-baby.md` (E01).
- `checker_rejects_bad`: `htsw-check.py` exits 1 on every `fixtures/bad-*.md` (E02, E03).
- `checker_accepts_code_explain_example`: `htsw-check.py --examples-file` exits 0 on `references/examples/code-explain-examples.md` (E08).

### Model Judge (`judge-rubric.md`)

- `baby_analogy_quality`: does baby-mode output pair every jargon term with an
  everyday analogy (not replace it), and is the explanation technically correct?
  Reason-first scoring, run only on `baby`/`walk` renderings (F09, F10, F11).

### Human Spot Checks

- Review a real baby-mode rendering for an unfamiliar audience (calibrates the judge).
- Confirm boss-mode output is genuinely client-safe before sending externally.

## Baseline Run

- date: 2026-05-31
- agent version: personal-htsw @ plugin 0.5.0
- model: n/a (code grader is deterministic)
- result summary: `eval.ps1` -> all code graders PASS; fixtures calibrated
  (good-baby exit 0, both bad fixtures exit 1).

## Ship Gate

- No code-grader failure (`eval.ps1` exits 0).
- Locked good fixture (`good-baby.md`) must keep passing `htsw-check.py` (no regression).
- Judge may flag taste issues for follow-up, but a code-grader red blocks ship.
