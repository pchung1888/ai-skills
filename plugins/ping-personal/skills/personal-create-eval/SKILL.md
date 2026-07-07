---
name: personal-create-eval
model: opus
description: Create or enhance an eval for any skill, agent, or artifact-producing thing, following the agent-evals-playbook. CREATE mode scaffolds evals/eval-plan.md + eval.ps1 (+ judge-rubric.md for taste-heavy skills) + calibration fixtures and lets run-all.ps1 auto-discover them. ENHANCE mode audits an existing eval for the failure curriculum (dead metrics, scope mismatch, prose guardrails, the unwired-registry trap, missing tiers) and fixes it. Trigger on /personal-create-eval or natural phrases like "create an eval", "add an eval for X", "enhance the eval", "eval this skill", "give X an eval", "audit the evals".
---

# /personal-create-eval -- the eval maker

Turns the eval methodology into a repeatable procedure. Two modes. The deep reference is
`references/how-to-create-an-eval.md` (the field guide -- read it once; it is the WHY behind
every step here). Templates live in `references/templates/`.

## The one rule everything serves

> If the failure can be checked with code, check it with code. Only spend a judge on taste.
> If you cannot explain what a score means, the score is not ready to optimize.
> Decisive test for any metric: **if the skill does exactly the right thing, will this number move?**
> If not, fix the grader before you touch the skill.

## Mode selection

- Target has no `evals/` (or no `eval.ps1`) -> **CREATE**.
- Target already has an eval you want to improve / you suspect a dead or wrong metric -> **ENHANCE**.
- "Audit everything" / "which skills lack evals" -> **ENHANCE** in scan mode (`audit_eval.py` over the whole plugin).

---

## CREATE mode -- give a target a good eval

1. **Name the target behavior** in one plain-English contract: given INPUT, the skill must
   produce OUTPUT with properties X/Y/Z and must NOT do W. Separate the **LEVER** (the editable
   skill text/prompt/model) from the **SUBJECT** (the artifact the user receives). You grade the
   SUBJECT, you version the LEVER.
2. **List the top ~10 failure modes.** This list IS the eval map. For each, run the decisive test.
3. **Classify each failure** with the decision tree:

   | If the failure is... | Use a... |
   |---|---|
   | a count / shape / boundary / file-exists / "no writes to read-only" / static check | **code grader** |
   | subjective but visible (coherence, taste, beginner-friendliness, "does it address the ask") | **model judge** (anchored, reason-first) |
   | high-stakes or the judge is untrusted | **human** spot check on a small calibration set |

4. **Scaffold the files:**
   ```
   python lib/scaffold_eval.py --skill <path-to-skill-dir> [--taste] [--dry-run]
   ```
   Creates `evals/eval-plan.md` + `evals/eval.ps1` (name substituted) + `evals/fixtures/`, and
   `evals/judge-rubric.md` when `--taste`. It will NOT overwrite without `--force`. `run-all.ps1`
   auto-discovers `evals/eval.ps1` by glob -- there is no separate registration step.
5. **Fill `eval-plan.md`** (target behavior + failure-mode table + tiered eval cases + ship gate).
6. **Write the code graders first.** Build a pure extractor (artifact -> typed facts) if one is
   needed, then thin threshold graders. Make the **3-state artifact check first**
   (missing / invalid / ok). For instruction-only skills (no scripts), grade STRUCTURE: frontmatter
   integrity, required sections, and **referential integrity** (every skill/agent/file this one
   names must exist on disk).
7. **Add judges only for what code cannot reach.** Use `judge-rubric.md`: anchored 0/1/3/5,
   reason-first, the anti-leniency line ("full spectrum 0-5"), a `-` sentinel for no-data, and
   **guardrails as code** (enforce after the judge returns; decide whether a missing modality is
   neutral or a mandatory zero -- it depends on whether the modality is required). Decouple
   "is X present" (code grader) from "is X good IF present" (judge).
8. **Calibrate every grader.** Bundle a **known-good** fixture (`fixtures/good-*`) that must PASS
   and **known-bad** fixtures (`fixtures/bad-*`) that must FAIL. Run the grader and confirm both.
   *A grader that passes everything measures nothing.* Confirm each metric SPLITS your examples
   (no dead metrics).
9. **Run the baseline, verify green:**
   ```
   pwsh plugins/ping-personal/skills/<skill>/evals/eval.ps1     # the one skill
   pwsh plugins/ping-personal/evals/run-all.ps1                 # the whole suite -> ALL EVALS PASS
   ```
   Quote the output; never claim PASS without it.
10. **Iterate by the loop:** pin a baseline, change ONE lever, rerun the SAME cases, compare
    per-case deltas, lock every new regression as a fixture. Never claim improvement from vibes.

---

## ENHANCE mode -- audit and improve an existing eval

1. **Run the auditor:**
   ```
   python lib/audit_eval.py --skills-dir plugins/ping-personal/skills     # scan all
   python lib/audit_eval.py --skill <path-to-skill-dir>                   # one skill
   ```
   It reports, per skill: missing `evals/`, missing `eval-plan.md`/`eval.ps1`, an `eval.ps1` that
   `run-all.ps1` cannot discover, leftover `<...>`/TODO placeholders, a grader with **no `throw`**
   (cannot fail -> measures nothing), and **no `bad-*` fixture** (uncalibrated). Exit 1 if any
   high-severity issue is found.
2. **Walk the failure curriculum** (the demo's instructive defects -- see the field guide section 6):

   | Check | The defect it catches |
   |---|---|
   | scope match | does each grader measure the unit the skill's rule actually controls? (the "dense" bug) |
   | discrimination | does each metric MOVE across known-good vs known-bad? (the "font<14" dead metric) |
   | compliance | does any grader penalize the skill for obeying its own rule? |
   | extractor honesty | does the parser silently miss inherited/templated values? document blind spots |
   | guardrails | any guardrail written as judge PROSE -> move it to deterministic code |
   | anchoring | upgrade endpoints-only / unanchored judges toward 0/1/3/5; add the anti-leniency line; put the rationale field FIRST if you want reasons-before-score |
   | wiring | is every grader you think runs actually registered/discoverable? (the unwired-registry trap) |
   | tiers | add the missing edge / regression / adversarial cases; a regression case per bug ever caught |

3. **Fix one thing, re-run `eval.ps1` + `run-all.ps1`, confirm green.** Re-baseline only when
   intended; do not let the eval set drift mid-comparison.

---

## Non-negotiables (apply in both modes)

- **Prove the aggregator's RED path** if you touch `run-all.ps1`: a planted failing grader must
  make it print `EVALS FAIL` / exit 1 and NOT falsely print `ALL EVALS PASS`. The aggregator is
  itself a grader; the "passes everything" rule applies to it most of all.
- **Wrap, don't duplicate.** If the target already ships a test suite, the eval INVOKES it (and
  adds frontmatter/structure checks); it does not re-implement it.
- **Honesty (global).** Quote verification output before any PASS claim. If a grader is red for a
  real reason (a pre-existing bug), surface it -- do not weaken the grader to go green.
- **ASCII only** in `.ps1`/`.py` (Windows PowerShell 5.1 cp1252 pitfall): no em-dashes, smart
  quotes, or Unicode arrows. Set `$env:PYTHONIOENCODING='utf-8'` in PowerShell graders.

## Files

```
SKILL.md
references/
  how-to-create-an-eval.md          the field guide (WHY)
  templates/
    eval-plan-template.md
    eval-grader-template.ps1
    judge-rubric-template.md
lib/
  scaffold_eval.py                  CREATE: generate evals/ for a target skill
  audit_eval.py                     ENHANCE: audit eval health across skills
evals/                              this skill's own eval (dogfood)
```
