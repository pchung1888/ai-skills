---
name: personal-goal-next
model: haiku
description: Advance the audit-tracker beacon after a phase finishes. Called by the driving Claude session. Triggers on /personal-goal-next <slug> ...
---

# /personal-goal-next

## Invocation

`/personal-goal-next <slug> --phase <N> --outcome <PASS|FAIL|BLOCKED> --tokens <N> --duration <minutes> --commit <sha> --subagent <name> --verify "<Gate 4 evidence>" [--notes "<text>"]`

`--verify` carries the phase's Gate 4 evidence (personal-fable-mode): the check
that was run plus one quoted output line, taken from the `verification` field of
the agent's return payload. `'UNVERIFIED: <reason>'` is accepted but recorded
(pipe-sanitized) in the PASS row's Cost Log notes so the critic sees it.
Required on PASS; ignored on FAIL/BLOCKED/--abort, where the failure notes carry
their own evidence and must stay clean for the no-progress detector.

Special modes:
- `/personal-goal-next <slug> --finalize` -- run acceptance command + mark goal done in TODO.md.
- `/personal-goal-next <slug> --abort "<reason>"` -- mark current phase BLOCKED with "ABORT: <reason>", update checkpoint, commit.

## Procedure

1. Resolve beacon path: read `.claude/TODO.md` "## In Progress" entry for `<slug>` to find the beacon. (Or use `docs/<area>/<slug>-audit-tracker.md` if convention holds.)
2. For per-phase advance:
   - `python ${CLAUDE_PLUGIN_ROOT}/skills/personal-goal-next/lib/advance.py --beacon <p> --phase <N> --outcome <O> --tokens <T> --duration <D> --commit <S> --subagent <A> --verify <E> [--notes <X>]`
   - This atomically: updates the Phase Status row, appends Cost Log and Activity Log rows, updates the Last Known Good Checkpoint (PASS only), appends Failure Log (BLOCKED only), then commits the beacon via `git commit`.
3. For --finalize:
   - `python ${CLAUDE_PLUGIN_ROOT}/skills/personal-goal-next/lib/finalize.py --beacon <p> --todo .claude/TODO.md --slug <s> [--skip-if-cached] [--force] [--shell pwsh|bash]`
   - Runs the acceptance command from the beacon header. On PASS: writes an acceptance cache file (`<beacon>.accept-cache`) and moves the In Progress TODO entry to "## To Be Tested". On FAIL: appends a Failure Log row and exits non-zero.
4. For --abort:
   - `python ${CLAUDE_PLUGIN_ROOT}/skills/personal-goal-next/lib/advance.py --beacon <p> --phase <N> --abort "<reason>" --tokens <T> --duration <D> --subagent <A>`
   - Marks current phase BLOCKED, appends Failure Log row, updates checkpoint to "ABORT: <reason>", commits.
5. Surface the result to the driver.

## Refusal cases

| Condition | Response |
|---|---|
| `--tokens` missing | Refuse: "preflight rule 4: --tokens required." |
| `--tokens` <= 0 | Warning to stderr + appended to notes; continue. |
| `--tokens` > 500000 | Warning to stderr + appended to notes; continue. |
| `--tokens` > 10000000 | Refuse (exit 2): value is absurd, check and retry. |
| Double-call with same `--phase` already Done | Refuse: "duplicate advance." |
| `--phase N` not in Phase Status table | Refuse: "phase N not declared." |
| `--outcome PASS` without `--commit` | Refuse: "--commit required when --outcome=PASS." |
| `--outcome PASS` without `--verify` | Refuse (exit 2): unverified done. Supply Gate 4 evidence or an explicit `UNVERIFIED: <reason>`. |
| `accept_shell=bash` on Windows without bash | Refuse: install Git bash/WSL or --shell pwsh. |
| `accept_shell=pwsh` on non-Windows without pwsh | Refuse: install PowerShell Core or --shell bash. |

## Collision warning

When advance.py or finalize.py is given a beacon path, they glob under `docs/` for
other `*<slug>*-audit-tracker.md` files. If more than one matches the slug, a WARNING
is printed to stderr listing all candidates. The command does NOT refuse -- the operator
must resolve the ambiguity manually.

## Acceptance caching (finalize.py)

After a PASS, finalize.py writes `<beacon>.accept-cache` (sha256 of accept_cmd +
matched output line + timestamp). On the next finalize run:

- If cache exists and `--force` is not set: prints "acceptance previously PASSED at <ts>; rerunning anyway (use --skip-if-cached to skip)."
- If `--skip-if-cached` is also set: prints the message and exits 0 without re-running.
- `--force`: ignores cache and always re-runs the acceptance command.

## Shell handling

`accept_shell` in beacon frontmatter controls which interpreter runs `accept_cmd`:
- `pwsh` (default): `["pwsh", "-NoProfile", "-Command", cmd]`
- `bash`: `["bash", "-c", cmd]`

Override with `--shell pwsh|bash` on the CLI. Shell mismatch (bash requested but
unavailable, or pwsh requested but unavailable) causes a clear refusal with instructions.

`accept_cmd` is passed as a single argument to the interpreter -- not shell=True --
so $vars, pipes, and quotes are handled by the interpreter, not the OS shell wrapper.
This avoids both the re-wrapping $var interpolation bug and command-injection risk.
