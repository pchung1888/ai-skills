# Eval Plan: personal-cache-stats

> Follows the agent-evals-playbook. Mirrors the approved shape from `personal-htsw/evals/`.

## Target Behavior

Given a Claude Code transcript JSONL (auto-detected, or `-SessionFile <path>`),
personal-cache-stats aggregates the `message.usage` blocks and reports cache READ
(hit), cache WRITE (miss), fresh INPUT, output tokens, and a hit-rate percentage
with a WARM/MIXED/COLD/FROZEN verdict. It must skip lines that have no usage block
and tolerate malformed JSON lines without crashing.

## Failure Modes

| ID | Failure | Why It Matters | Grader |
| --- | --- | --- | --- |
| F01 | hit-rate math wrong (read / (read+write+fresh)) | the headline number Ping decides on is wrong | code |
| F02 | a malformed JSON line crashes the whole run | one bad line zeroes the whole report | code |
| F03 | lines without a usage block are counted as turns | turn count + denominators inflate | code |
| F04 | `-SessionFile` ignored / not honored | cannot point it at a known transcript -> not testable | code |
| F05 | frontmatter name/description corrupted | skill stops triggering | code |
| F06 | verdict band mislabeled (e.g. 80% not WARM) | misleads the "is my cache warm?" answer | code |

## Eval Cases

| ID | Input | Expected Behavior | Must Not Happen |
| --- | --- | --- | --- |
| E01 | `fixtures/sample-transcript.jsonl` (2 valid turns + 1 no-usage + 1 malformed) | Turns=2; READ=800; WRITE=100; FRESH=100; Hit rate=80%; verdict WARM; exit 0 | crash on the malformed line; Turns!=2; wrong hit rate |

The fixture is a locked regression case: 2 valid usage turns (read 0/800, write 100/0,
fresh 100/0) -> read=800, total=1000, hit=80.0%. The no-usage line and the
not-valid-json line must both be silently skipped (proves F02 + F03 fixed).

## Graders

### Code Graders (`eval.ps1`)

- `skill_frontmatter`: SKILL.md declares name=personal-cache-stats + a description.
- `script_present`: cache-stats.ps1 exists.
- `parses_known_fixture`: runs cache-stats.ps1 -SessionFile on the fixture and
  asserts the deterministic golden output -- Turns=2, Cache READ=800, Hit rate=80,
  verdict WARM, exit 0. (Covers F01, F04, F06.)
- `skips_noise`: the same run proving Turns=2 (not 4) confirms the no-usage and
  malformed lines were skipped (F02, F03).

### Model Judge

- None. This is pure arithmetic over a known transcript -- deterministic; code only.

## Baseline Run

- date: 2026-05-31
- result summary: `eval.ps1` -> fixture yields Turns=2, READ=800, Hit rate 80% WARM, exit 0.

## Ship Gate

- `eval.ps1` exits 0. Any drift in the hit-rate math or a crash on the malformed
  line (the locked regression case) blocks ship.
