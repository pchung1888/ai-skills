# Eval plan: personal-jev

## Target Behavior

- **LEVER** (what we version): `jev.ps1` + `SKILL.md`.
- **SUBJECT** (what we grade): `jev.ps1` exit codes, text output, and `-Json` object.

Given a payload file, `jev.ps1` must (1) reject malformed Noul/Choice/Score or non-ASCII
payloads; (2) refuse payloads matching the leak tripwire; (3) preview by default and make NO
network connection without `-Send`; (4) never print the API key; (5) normalize scores and
compute per-option composites correctly; (6) flag `YOUR CALL` when Jev is split.

## Failure Modes

| ID | Failure | Why It Matters | Grader |
| --- | --- | --- | --- |
| F01 | Sends without OK | data leaves the box unapproved | `preview_is_default` + `control` (local TCP listener) |
| F02 | Leak passes / false positive | client data sent, or plain English blocked | `leak_tripwire`, `no_false_positive` |
| F03 | Key printed | credential in a shared transcript | `key_never_printed`, plus HTTP-error path in `control` |
| F04 | Bad shape passes | wasted call or misleading answer | `shape_check` |
| F05 | Wrong math | wrong composite -> wrong pick | `math` |
| F06 | Missing YOUR CALL | false confidence on a split decision | `your_call` |
| F07 | Frontmatter rot / dangling ref | skill stops triggering | `skill_frontmatter`, `referential_integrity` |
| F08 | Vacuous green | tests pass while broken | mutation run (Baseline) + F01 control |
| F09 | Sent payload differs from the approved preview | Ping OKs one thing, another is sent | `approval_bind` (no / wrong / stale fingerprint -> exit 6, no connection, correct fingerprint not echoed) |
| F10 | Key only found in the current folder | every send from the scratchpad fails | `key_file` (key via `-KeyFile`, empty env, empty cwd; none anywhere -> exit 1) |
| F11 | Composite hides unsure or missing inputs | a flat number ranks options on guesses | `composite_honesty` (missing -> null + listed; unsure -> YOUR CALL; choice ids skipped) |
| F12 | Receipt missing, lossy, leaky, or written for a refused payload | calibration impossible, or blocked text lands on disk | `receipt` (full odds, schema, decision slot, no key; none on leak / bad shape / no approval) |

All graders are code; no judge (nothing graded is a matter of taste).

## Not Covered (honest limits)

- Live API: one manual `-Send` with a harmless payload confirms the real request/response
  shape. Ask Ping before running (pricing unknown).
- Quality of Claude's abstraction and Which-tool advice: human spot check on 5 samples.
- Tripwire recall on paraphrased client details: by design it only catches identifiers.

## Baseline Run

- date: 2026-09-23
- agent version: personal-jev @ ping-personal 0.24.0
- result: `EVAL PASS personal-jev (11)`.
- RED path proven: replacing the preview gate `if (-not $Send -and -not $Fake)` with
  `if ($false)` -> `EVAL FAIL (2 of 11)` (F01 preview_is_default, F02 no_false_positive);
  restore -> `EVAL PASS (11)`.
- Finding from that run: the mutant reached the REAL endpoint from `no_false_positive`
  (sentinel key, clean payload, harmless). Fixed: `Invoke-Jev` now defaults every run to a
  dead local port (127.0.0.1:9), so no eval run can reach the real API.

- date: 2026-09-23 (0.25.0: approval fingerprint, key file, composite honesty, receipts)
- result: `EVAL PASS personal-jev (15)`.
- RED path proven: approval check -> `if ($false)` and composite `yourCall = $false` ->
  `EVAL FAIL (2 of 15)` (F09, F11); restore -> `EVAL PASS (15)`.

## Ship Gate

- `pwsh plugins/ping-personal/skills/personal-jev/evals/eval.ps1` -> `EVAL PASS`.
- `pwsh plugins/ping-personal/evals/run-all.ps1` -> `ALL EVALS PASS`.
- Highest-severity blockers: F01 and F03 must always be green.
