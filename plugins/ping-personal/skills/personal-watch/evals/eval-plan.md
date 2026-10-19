# Eval plan - personal-watch

## Target behavior

Given YouTube links and a question, the skill fetches captions only, turns them into readable text
with [mm:ss] marks, reads every transcript in full, and answers with cited quotes, listing every
video it could not read. It never downloads video or audio, never uploads, never installs, and never
follows instructions found inside a transcript.

- LEVER: SKILL.md, scripts/captions.py.
- SUBJECT: the transcript text files and the answer.

## Baseline (RED, observed Sun 10-18 in the build session, no skill)

A research subagent asked to "watch" four videos fell back to secondary AI summaries and reported
the transcripts as unreadable; the coordinator had to be told about a video tool, and a first
caption fetch of four videos at once hit HTTP 429 on three of them.

## Failure modes -> graders

| # | Failure mode | Grader | Type |
|---|---|---|---|
| 1 | A rule drops out (captions only, no install, untrusted data, cite or label, could-not-read, one at a time) | `skill_rules` + mutation calibration | code |
| 2 | Rolling auto-captions come out with every line twice, or timing tags leak into the text | `captions` (test_captions.py on a real caption sample) | code |
| 3 | Marks missing, so quotes cannot be cited | `captions` | code |
| 4 | The fetch starts downloading audio/video, runs in parallel, or installs packages | `no_download_flags` | code |
| 5 | Non-ASCII in skill files | `ascii` | code |

Not graded here: the quality of the answer and whether the model follows rule 3 against a hostile
transcript (needs a live model run); the network path (`captions.py` against YouTube) was run by
hand on Sun 10-18.

## Calibration

- test_captions.py was mutation-checked: removing the repeated-line filter makes it fail.
- skill_rules detects a renamed rule.

## Ship gate

`pwsh plugins/ping-personal/skills/personal-watch/evals/eval.ps1` prints `EVAL PASS personal-watch (4)`
and `pwsh plugins/ping-personal/evals/run-all.ps1` prints `ALL EVALS PASS`.
