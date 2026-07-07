# Eval Plan: personal-understanding

## Target Behavior

Given a `/personal-understanding [mode]` invocation, the skill routes to the correct mode
(`install` / `onboard` / `use`, or a read-only status probe when no mode is given) and
delegates the real work to the understand-anything plugin's own skills via the Skill tool.
It must NOT reimplement the analyzer pipeline, and must NOT claim it can run `/plugin`
commands itself (those are harness commands only the user can type -- AD-2).

This is an **instruction-only** skill (no scripts). The LEVER is `SKILL.md` + `references/*`.
The SUBJECT the eval grades is the skill text itself: its structural integrity and its
referential integrity (every plugin sub-skill and reference file it names must be valid).
Behavioral correctness of the delegated pipeline is owned by the understand-anything plugin
and is exercised in the goal's Phase 4 dogfood, not re-tested here.

## Failure Modes

| ID | Failure | Why It Matters | Grader |
| --- | --- | --- | --- |
| F01 | Frontmatter name/model/description corrupted | Skill stops triggering or loses its tier | code (R1) |
| F02 | Description drops trigger phrases / plugin name | Natural-language invocations never route here | code (R1) |
| F03 | A mode (install/onboard/use) undocumented | That lifecycle stage is unreachable | code (R2) |
| F04 | No-arg status default missing | Bare invocation has no safe behavior | code (R2) |
| F05 | A `use` sub-action undocumented | `ask`/`explain`/`diff`/`domain`/`guide` silently unavailable | code (R3) |
| F06 | References a misspelled understand-anything sub-skill | Delegation fails at runtime | code (R4) |
| F07 | Core delegation (understand / dashboard / chat) absent | A router that never delegates is broken | code (R5) |
| F08 | AD-2 boundary not stated (claims self-install) | Dishonest -- confident-wrong on a fresh box | code (R6) |
| F09 | Non-ASCII char in SKILL.md | PowerShell 5.1 cp1252 mojibake | code (ascii) |
| F10 | Names a references/<file>.md that does not exist | Broken internal link | code (ref_files) |

All failure modes are statically checkable, so there is no model judge -- correctness of an
orchestrator's contract is structure + referential integrity, which code measures exactly.

## Eval Cases

| ID | Input | Expected Behavior | Must Not Happen |
| --- | --- | --- | --- |
| E01 | real `SKILL.md` | passes R1-R6 + ascii + ref_files | a real regression slips through |
| E02 | `fixtures/good-skill.md` | passes all rules | grader over-strict (rejects valid) |
| E03 | `fixtures/bad-frontmatter.md` | rejected (R1) | grader accepts bad frontmatter |
| E04 | `fixtures/bad-missing-mode.md` | rejected (R2) | grader accepts a missing mode |
| E05 | `fixtures/bad-typo-subskill.md` | rejected (R4) | grader accepts a dead delegation |
| E06 | `fixtures/bad-self-install.md` | rejected (R6) | grader accepts the AD-2 violation |
| E07 | constructed em-dash string | ascii check flags it; clean string accepted | dead ascii metric |

## Graders

### Code Graders (`eval.ps1`)

- `skill_present`: 3-state artifact check -- SKILL.md exists.
- `structure`: `Get-SkillViolations` returns empty over the real SKILL.md (rules R1-R6).
- `ascii`: real SKILL.md has no byte outside 0x00-0x7F.
- `ref_files`: every `references/<file>.md` named in SKILL.md exists on disk.
- `calibration_good`: `fixtures/good-skill.md` yields zero violations (not over-strict).
- `calibration_bad`: every `fixtures/bad-*.md` yields >=1 violation (not over-lenient).
- `ascii_discriminates`: the ascii predicate flags an em-dash and accepts clean text.

### Model Judge

None. No taste dimension -- every rule is a static fact.

### Human Spot Checks

- One-time read of the rendered status table and mode playbooks during Phase 4 dogfood.

## Baseline Run

- date: 2026-06-15
- agent version: personal-understanding @ ping-personal (pre-release, branch topic/understand-anything)
- result summary: see eval.ps1 output captured in the Phase 3 beacon advance.

## Ship Gate

- `eval.ps1` exits 0 (all code graders green; good fixture still passes, all bad fixtures still fail).
- Highest-severity failure that blocks ship: F06 (dead delegation) and F08 (dishonest AD-2 claim).

## Known blind spot

Referential integrity for sub-skills is checked against a hardcoded valid vocabulary
(`$ValidSubskills`), NOT the live plugin on disk -- so the eval runs even where the plugin is
not installed. If understand-anything renames a skill, update `$ValidSubskills` to match.
