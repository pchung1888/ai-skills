---
name: personal-loop
model: sonnet
description: Outer loop that drives personal-workflow/personal-goal as an inner loop. Campaign-aware, condition-based autonomy (run until a verifiable stop-condition is true) plus timer cadence. Enforces THE GATE LAW (one gate, co-extensive with the goal), an autonomy dial for tick granularity, a severity-aware critic gate, and fail-closed unattended safety. Sequences a campaign of goals or resumes a single goal across quota windows. Triggers on /personal-loop <goal | --campaign slug | --resume slug | --every <interval> skill:<name>>.
---

# /personal-loop

The OUTER loop. Drives `personal-workflow`/`personal-goal` as the inner loop.
Does NOT modify them -- it drives them. Each outer tick runs ONE unit of inner
work as a FRESH beacon-anchored context, gates it, evaluates STOP, checkpoints,
and either schedules the next tick or halts + reports.

## The Gate Law

The single most important rule in this skill. The reported one-message-per-fire
stutter was a direct violation of it.

- **INVARIANT 1 -- the gate is co-extensive with the goal.** The STOP gate must
  verify EVERY ending condition the goal states. If the goal says "all / every /
  each / N artifacts", a gate that checks ONE artifact is INVALID -- it goes green
  after the first deliverable and halts a job that is 1/N done.
- **INVARIANT 2 -- exactly ONE authoritative completion gate per run.**
  - **Single-artifact goal** -> `accept_cmd` exit 0 is the authoritative gate.
  - **Multi-artifact / campaign goal** -> `all-goals-done` is the authoritative
    gate (`goals_done >= goals_total`). Any `accept_cmd` is a PER-CHILD health
    check only -- NEVER the run-level stop. `stop_eval.py` enforces this: in
    campaign mode a green `accept_cmd` does not complete the run.
- **INVARIANT 3 -- a condition that lives only in prose is not a gate.**
  `stop_eval.py` reads a `--state` JSON, not your goal description. Every datum
  the gate needs (`goals_total`, accept scope, the fuzzy rubric) must be compiled
  into the contract/beacon at arm time. Prose `contract.py` drops (any
  non-ALL-CAPS line) is invisible to the loop.
  The gate may be PROMOTED from `fuzzy-judge` / `human-evidence` to `accept_cmd`
  mid-run when a crisp machine check is DISCOVERED (e.g. a DB count, an exit-0
  command appears once data flows). Re-derive the `--state` JSON each tick; on
  promotion, set `accept_exit` from the new check, record `gate_promoted_at` in
  the beacon + tracker, and fold a gate-mode marker into the tick signature so
  the anti-stall logic does not read the transition as a stall. Exactly ONE
  authoritative gate per run is preserved -- it is just resolved late. Do NOT
  write the goal off as unverifiable because it was UNVERIFIED at arm.
- **INVARIANT 4 -- the loop never self-judges an unobservable.** When a goal's
  real gate is a human-only / GUI observation (a logon appears on a terminal;
  "is this doc accurate?"), the gate is `human-evidence`: the loop produces
  everything up to the observation boundary, states the EXACT observation it
  needs, and ALWAYS halts for an explicit human accept / paste. The pasted-back
  evidence -- never a model fuzzy verdict -- is the tick input. `human-evidence`
  MAY reuse the `fuzzy_verdict` plumbing mechanically, but auto-fuzzy-pass is
  FORBIDDEN for a `human-evidence` gate. This keeps the human in the accept loop
  for conditions a machine cannot observe.

If you internalize nothing else: **multi-artifact goal -> campaign mode ->
`all-goals-done`.** Do not wrap a "do all of X" goal around a single-file
`accept_cmd`.

## Roles block

```
BEACON      = personal-goal               # host goal beacon (a differently-named goal skill on other host repos)
CONDUCTOR   = personal-workflow            # the inner per-goal conductor
FAST_CRITIC = <resolved at runtime>        # see Role Resolution
PANEL       = personal-critic-gate         # full 5-seat escalation
```

## Invocation

`/personal-loop <bare goal>` | `--campaign <slug>` | `--resume <slug>` |
`--every <interval> skill:<name>` | `--unattended` (arm OS relauncher) |
`--force-resume` (clear a safety circuit-breaker -- see Survival)

Pass-through to personal-goal: `--accept-cmd / --accept-match / --area / --branch`.

## Autonomy dial -- tick granularity is the babysitting knob

A tick's ACTION can be a whole inner goal, a single goal-phase, or a bare skill.
This choice is the autonomy dial: each tick boundary inserts a critic gate + STOP
EVAL + reschedule, so smaller ticks = more gates = more stutter. The reason
`personal-workflow` runs for hours unattended is that it flows phase->phase in ONE
context; per-phase outer ticks throw that away.

| ACTION (granularity) | Autonomy | Gate frequency | Use when |
|---|---|---|---|
| `inner-goal` (DEFAULT) | highest -- inner conductor self-continues across its own phases | once per goal | the normal case; long unattended runs |
| `goal-phase` | medium -- outer loop re-enters every phase | once per phase | a phase needs a human fence, or one inner goal would blow the token ceiling |
| `skill:<name>` | n/a -- one bare skill per tick | once per skill | a simple recurring `--every` chore |

**DEFAULT = `inner-goal`.** Downgrade to `goal-phase` ONLY for reason (a) or (b)
above. Never default to per-phase -- it is the stutter.

**Per-tick, not per-goal.** The dial is re-evaluated EACH tick. Before a tick,
run `preflight.detect_external_actions` over the tick's goal/phase text; a hit
auto-selects `goal-phase` for THAT tick (fence per phase) with a one-line
announcement of why, e.g. `external-action detected -> goal-phase`. A goal can
legitimately be fence-per-phase early (external-world steps) and fully
autonomous late (pure machine-readable evidence pulls). Same word-boundary
mechanism as the `flag_excluded` security scan, but its output is a dial
setting + announcement, never a security halt.

## Pre-flight

Run `lib/preflight.py` at arm-time AND once per NEW child goal (before dispatching
that child's inner loop). It does NOT re-run on resumed ticks of an
already-vetted goal. Never fire mid-tick.

**Readiness (`check_readiness`) -- 6 points:**
1. Task recurs or is worth automating.
2. A machine-checkable gate exists: crisp `accept_cmd` OR `all-goals-done` OR a
   declared `fuzzy-judge` STOP (now backed by `stop_eval.py`, see Tick lifecycle).
   An UNVERIFIED goal (no `accept_cmd`, no `all-goals-done`) is NOT "not
   loopable" -- it is "not loopable UNATTENDED, but loopable ATTENDED via a
   `human-evidence` tick". `--unattended` still REFUSES it; attended proceeds.
3. Token/iteration budget set (`max_iters > 0` or `token_ceiling > 0`).
4. Hard stop declared.
5. Fence guarantees human review before irreversible actions.
6. Evidence surface is machine-readable -- logs land in a file or a named
   persisted artifact (FileStore, DB table), not a screen-only sink. A debug
   goal whose only evidence is a console no one is watching
   (`logs.screen_only == true`) is NOT autonomously verifiable -> fall back to
   the human-evidence tick (Tick lifecycle step 7).

**Before you arm -- compile prose ending-conditions into the gate (THE GATE LAW):**
1. List every ending condition stated in the goal / VISION / CLAUDE.md prose.
2. Count the deliverables (quantifiers: all/every/each/N; explicit lists; campaign
   children). Call it `N`.
3. If `N > 1`: set `goals_total = N`, `STOP = all-goals-done`, model it as a
   `--campaign`; `accept_cmd` (if any) becomes the per-child check.
4. If `N == 1`: a single-file `accept_cmd` is fine and is the authoritative gate.
5. Run the scope check: `preflight.py scope_warnings`. A `gate-scope-narrow` or
   `gate-scope-undeclared` warning means the gate cannot cover the goal --
   attended PAUSE and ask; `--unattended` REFUSES to arm.

**Judgment-call exclusion (`flag_excluded`, word-boundary matched):** scans intent
against `EXCLUSION_KEYWORDS` (auth, payment, billing, migration, schema,
architecture, encryption, secret, credential, plus destructive/production verbs:
deploy, production, prod, sudo, truncate, drop). This is a SECURITY gate, not a
taste gate -- over-blocking is acceptable, under-blocking is not. A hit at arm-time:
unattended -> ABORT; attended -> PAUSE and confirm.

GREEN-LIST (safe to loop): lint-and-fix, dep bumps, flaky-test triage,
doc/understanding generation, mechanical refactors with a green test gate.

`--unattended` REFUSES to arm on ANY readiness failure, scope warning, or
exclusion hit. Attended runs WARN and continue.

## Evidence-gathering

Before analysis, build the EVIDENCE MAP (spec / `references/evidence-gathering.md`):
run `lib/discover_sources.py:probe_repo` for the repo-local half, observe your
own available MCP servers / skills / agents for the service half, then
`merge_evidence` + `assert_no_secret_value` and record the map to the beacon and
`outer-loop-tracker.md`. Then PULL all local (and attended-allowed external)
evidence before asking the human anything -- "never ask what you can read".
Locations not secrets (the map stores a `.env` key NAME, never a value).
External reads are attended-free, unattended-allowlisted
(`preflight.is_external_read_allowed`). Re-probe when a pull is empty or a new
artifact is expected.

## Orchestration

A tick's ACTION may DECOMPOSE into sub-work dispatched as a BOUNDED TREE
(`references/dispatch-routing.md`). For each item the model extracts typed
features and `lib/orchestrate.py:route` returns a target: a bare subagent
(simple), `/personal-goal` (multi-step single-domain), `/personal-workflow`
(multi-phase / multi-domain), or a nested `/personal-loop` (long-horizon, own
gate). A model override of `route` is RECORDED in the tracker.

Bounds (all code-backed): `check_depth` refuses a nested-loop spawn at
depth >= 2 -- depth is PARENT-INJECTED and immutable, NEVER read from the
(untrusted) tracker. `check_width` returns free / confirm / stop over the TOTAL
live descendants charged to the root ledger (per CLAUDE.md Process Budget
Discipline; tightened when another session is active). All descendant fan-out
is charged to the root ledger before dispatch. Each child carries its OWN gate
(per-child GATE LAW); the run-level authoritative gate stays exactly one.

Runaway is stopped by COUNTED limits (depth, width, iters, deadline,
run-ceiling) -- the token budget is a reporting hint (`outer-loop-tracker.md`),
never the safety boundary. External reads obey `is_external_read_allowed`:
attended-free, unattended-allowlisted.

[DRIVER-WIRED backlog: the dispatch of route() results, depth/width
enforcement at spawn time, and root-ledger accounting are driver steps; each
needs a red-then-green eval before an unattended fan-out run -- see eval-plan
Known gaps.]

## Role Resolution

FAST_CRITIC precedence (portability contract -- never hardcode an agent name):

1. Explicit `--critic <agent>`
2. Host-discovered: `personal-workflow/lib/discover.py` scans the HOST project's
   `.claude/agents/*.md`, matches an agent whose name/description contains
   `critic` / `adversarial` / `review`.
3. Plugin critic in model context (`ms-mario`)
4. Inline-judge fallback: fresh generic subagent (claude/Explore) with
   adversarial-review + Honesty-Protocol brief.

ALWAYS announce the resolved tier, e.g. `FAST_CRITIC = your-host-critic-agent (host-discovered)`
or `= inline judge (no critic agent found)`. The inline judge is WEAKER (less
domain knowledge); both the announcement and the REPORT label the gate strength.

## Tick lifecycle

1. READ STATE: beacon + VISION + CLAUDE.md + loop-contract (anchor files only; no
   chat history). Compile the `--state` JSON for `stop_eval.py` from these anchors
   (THE GATE LAW invariant 3) -- set `goals_total`/`goals_done`/`next_pending` from
   the campaign beacon, `accept_exit` from the per-unit gate, and fold a MONOTONE
   progress marker (goals_done, or an in-scope artifact count) into the tick
   signature so a tick that truly advanced is never misread as a stall. (Progress
   is judged from the signature history, not a separate mutable flag -- a stale
   flag could otherwise disable the anti-stall guard forever.)
   Re-derive gate availability EACH tick (not only at arm): if a tick discovers
   a crisp machine check while the goal armed `fuzzy-judge` / `human-evidence`,
   PROMOTE it to `accept_cmd` for subsequent ticks and record `gate_promoted_at`.
   Also read outer-loop-tracker.md (its `## Next action` + `## Tree`) to reconstruct
   outer state.
2. PRE-FLIGHT: readiness + scope + exclusion (arm-time + per-new-child, per above).
3. SECRETS SCAN (planning-time): `lib/secrets_scan.py` over the files the tick
   plans to write. A hit HALTS via `lib/halt.py` (see Survival).
4. ACTION: one unit per the Autonomy dial (DEFAULT `inner-goal`).
   A non-gate WORKER/PROBE command that errors mid-tick is recorded and tolerated
   -- it does NOT abort the tick. Tick success is decided by the STOP gate
   (step 7), never by "did every command exit 0" (the turn-9 PowerShell-in-Bash
   slip is the canonical case: the DB gate was conclusive, the slip irrelevant).
5. SECRETS SCAN (post-action, pre-commit): re-run `secrets_scan.py` over the ACTUAL
   staged `git diff` before any commit. A hit blocks the commit and HALTS. (The
   step-3 scan sees only intent; this scan sees what the inner conductor produced.)
   [DRIVER-WIRED: the `secrets_scan.py` primitive is eval-covered; the
   diff -> scan -> block-commit wiring is enforced by the driver and is on the
   eval-plan Known-gaps backlog, not yet a standalone eval.]
6. FAST GATE: dispatch FAST_CRITIC on the tick's output (1 seat). Parse with
   `personal-critic-gate/lib/vote_parser.py --fast-lane`. Returns PASS | FIX | ESCALATE.
   The critic is **advisory**: it can neither declare the goal done nor halt a
   green-list run on taste alone. FIX is **severity-aware**:
   - PASS -> record + continue.
   - FIX, low/medium severity, green-list goal -> log the finding to the status
     file and CONTINUE.
   - FIX, high severity OR security-tagged (secret, irreversible action,
     scope-violation) OR a fenced/ship ACTION -> HALT; report the fix path.
   - ESCALATE -> fire the full PANEL; resolve per its verdict.
7. STOP EVAL: `lib/stop_eval.py --state <json>`. It returns a structured detail
   object (stop, reason, gloss, goals_done/total, remaining, next_pending).
   Completion is decided by the ONE authoritative gate (THE GATE LAW), never by
   critic opinion.
   For a `human-evidence` gate, STOP EVAL does NOT self-judge: the loop emits a
   one-block observation request (phrased per `references/prompt-as-ping.md`)
   and HALTS. On resume, the human's pasted evidence is parsed and supplies the
   `fuzzy_verdict`; only an explicit human accept advances the gate.
   [DRIVER-WIRED backlog: the human-evidence halt+resume dispatch is a driver
   step, not yet a standalone eval -- see eval-plan Known gaps.]
8. RECORD: checkpoint via `/personal-goal-next`; write detail to files not chat;
   driver commits + timestamps. Append the tick signature
   (`progress_hash.py`, include the progress marker) to the signature list.
   Write outer-loop-tracker.md via compare-and-swap against the beacon (the
   beacon is the single source of truth for child completion + budget; tracker
   cells are a read-through cache, never written back). The `## Next action` is
   STRUCTURED and regenerated from state -- never free-text the loop executes
   blindly. Emit the tracker for EVERY run (a depth-0 run degenerates to header
   + one-row tree + turn tape) so the prompt->return->fence trail always exists.
9. NEXT: STOP true -> HALT + REPORT. Else -> schedule next tick (see Survival).

**Halt precedence (canonical -- single source of truth, highest first):**
`secrets-HALT` > `fence-HALT` > `gate-error` (single) / `child-gate-error`
(campaign) > `all-goals-done` (campaign) / `accept_cmd-green` (single) >
`fuzzy-judge-pass` > `no-progress` > `iters` > `budget-spent` > `deadline` >
`run-ceiling`. The first two are enforced in steps 3/5 before STOP EVAL; the rest
are `stop_eval.py`'s precedence verbatim. Do not restate this list elsewhere --
reference it.

**Gate-error semantics:** `accept_cmd` MUST exit 0 (done) / small nonzero (not
done yet) and must NEVER be wrapped in a killer such as `timeout`. Exit `>= 126`
(command-not-found, not-executable, or signal-kill `128+n`) is read as a broken
gate (`gate-error` single-artifact, `child-gate-error` campaign) and fails loud
rather than silently looping as "not done".

**Worker-failure tolerance vs safety-exit (do not confuse).** The tolerance
above applies ONLY to worker/probe commands. Any nonzero exit from a SAFETY
guard -- `secrets_scan.py`, `fence.py`, `halt.py` -- stays fatal and outranks
tolerance per the Halt precedence list. A gate command (`accept_cmd`) erroring
is `gate-error` (fail loud), never tolerated. Tolerate the probe; never the
guard or the gate.

## Fence

Every proposed durable action runs through `personal-workflow/lib/fence.py`. Exit 2
-> PAUSE. In `--unattended` a fence hit HALTS and writes a status file -- never
auto-executes.

**Canonical irreversible-action set (exhaustive for auto-halt purposes):**
`git push`, any DDL (`DROP` / `TRUNCATE` / `ALTER`), writes to `.env*` or secret
stores, package publish/deploy, writes to a DEPLOYED config (Program Files /
ProgramData / a configured org-specific deploy root -- via
preflight.is_deployed_config_path), and anything `flag_excluded` tags.
NEVER auto-push.

**`skill:<name>` ACTION caveat:** a bare-skill tick does NOT route through
`personal-workflow`, so it bypasses the conductor's fence. For `skill:` ACTIONs the
driver MUST invoke `fence.py` directly before any durable action; if `fence.py` is
unreachable, `--unattended` REFUSES to proceed (fail closed).

## Survival

Default cadence: `/loop` (attended runs within a quota window).

`/loop` does NOT auto-resume across a 5h quota reset (verified; GitHub #36320).
For unattended cross-reset runs, arm `--unattended`:
- A Windows Task Scheduler task fires `claude -p "/personal-loop --resume <slug>"`.
- Each fire reads the campaign beacon and advances one inner goal.
- Blocked by quota -> exits clean; next scheduled fire retries.
- Beacon guarantees no lost work (committed every phase).

**Timer-cadence ceilings.** A `--every` chore has no `all-goals-done`, so it needs
its own never-stop guard. Set a wall-clock `deadline` and/or a cumulative
`runs_ceiling` (persist `runs_total` across Task Scheduler fires in the beacon).
`stop_eval.py` halts on `deadline` / `run-ceiling` -- the timer-cadence equivalent
of `all-goals-done`. Without one, a recurring chore fires forever.

**Circuit-breaker (secrets/fence HALT).** On a safety HALT, `lib/halt.py` writes a
`BLOCKED: <kind>` sentinel to the campaign child-goal state and a
`.claude/tmp/secret-halt-<ts>.md` status file. `--resume` reads the sentinel
(`halt.is_blocked`) and REFUSES to re-run a blocked goal without `--force-resume`.
Without this, Task Scheduler re-fires the same blocked goal every interval forever.
The breaker primitives are implemented and eval-covered; the driver wires them into
the resume path. See `references/unattended-setup.md`.

**Fail-closed unattended self-check.** Before arming `--unattended`, verify the
safety machinery is actually present and runnable: `secrets_scan.py`, `halt.py`,
and a reachable `fence.py`. If any is missing, REFUSE to arm and name the missing
guard -- a documented safety mechanism that is not backed by runnable code must
never be treated as present. [DRIVER-WIRED: the driver performs this self-check at
arm time; the guard primitives are eval-covered, the arm-time check is on the
Known-gaps backlog.]

**Heartbeat (orchestration tree).** Baseline = a long `ScheduleWakeup` poll
(1200s+). If the harness re-invokes the loop on background-task completion, that
is a latency OPTIMIZATION only -- never the sole liveness path. Idempotency:
each child dispatch carries a `child_id` + lease; a completion is processed
exactly once (check `## Handled completions` first); near-simultaneous wakeups
cannot double-dispatch (CAS against the beacon); a child whose lease expired
without completion is marked LOST and re-evaluated, never silently dropped.
[DRIVER-WIRED backlog: heartbeat idempotency + CAS are driver steps needing a
red-then-green eval before an unattended fan-out run.]

## Trusted-input boundary

In unattended mode the loop runs with shell authority on a schedule and re-reads
its own beacon/contract/campaign files each tick. Treat those files as UNTRUSTED
input:

- **Beacon cell values** (the file paths in the campaign table) are validated by
  `preflight.validate_beacon_cell` -- no path traversal, no shell metacharacters.
  (code-backed + eval-covered)
- **`skill:<name>` ACTIONs** are validated by `preflight.validate_skill_ref`
  against an allowlisted name shape before dispatch. (code-backed + eval-covered)
- **`accept_cmd` is itself a shell command** (it legitimately contains pipes,
  `$`, `;`), so it is NOT metacharacter-filtered. Instead it is hash-pinned at arm
  time: if `accept_cmd`, `ACTION`, or `UNATTENDED` changed between arm and resume,
  re-run preflight + human confirm before proceeding. [DRIVER-WIRED: the integrity
  hash-compare is a driver step on the Known-gaps backlog; the two validators above
  are the code-backed parts.]

## REPORT format

On halt, print plain English for humans AND the machine stop reason -- the reason
token is the single most diagnostic fact; never suppress it.

```
Loop <slug> halted.
Stop condition: <reason token> -- <plain-English gloss>.
Progress: <goals_done> of <goals_total> done; next pending: <next_pending>.
Ticks run: <N> of <max>.   Tokens: <T> of <ceiling>.
Last good checkpoint: phase <P> (commit <sha>).
Gate strength: <FAST_CRITIC tier>.
What's done: <bullet list>.
What's blocked / needs you: <bullet list with the fix path>.

Changed files -- read these before trusting this run:
  git diff --stat <START_REF>..HEAD
NOTE: A loop running unattended is a loop making mistakes unattended. Read the diffs.

Resume: /personal-loop --resume <slug>   (--force-resume if a circuit-breaker fired)
Tracker: outer-loop-tracker-<slug>.md (tree + budget + turn tape + next action).
```
