# /personal-loop Eval Plan

## Tiers

### Tier A: Lib unit tests (automated)
Run via `python evals/test_lib.py` from the skill root.
Covers 117 assertions across 7 modules:
- progress_hash (7): signature stability + progress-marker discrimination + no-progress window.
- stop_eval (20): each STOP condition, plus THE GATE LAW regressions (a green per-child
  accept_cmd must NOT complete a campaign), gate-error + campaign child-gate-error fail-loud,
  the fuzzy-judge STOP path, signature-history no-progress (no mutable flag), the
  deadline / run-ceiling never-stop guards, and the structured stop_detail.
- contract (7): parse/render roundtrip + validate_contract (required fields + legal ACTION).
- preflight (28): readiness, word-boundary + destructive-verb exclusion, the scope check
  (gate-scope-narrow / -undeclared) incl. test-runner / dotted-pattern / numeral / fuzzy-STOP
  cases, gate_is_single_artifact heuristics, and the untrusted-input validators.
- campaign (7): parse/advance + goal_exists + missing-slug no-op + idempotent mark.
- secrets_scan (13): pattern catches + the adjacent-env-var + connstring-per-field hardening +
  match-only _is_fp + widened vocabulary + non-reversible redaction.
- halt (2): circuit-breaker sentinel/detection + status-file write.

### Tier B: SKILL.md structural check (automated)
Verify all 10 required section headers are present: Roles block, Invocation, Pre-flight,
Role Resolution, Tick lifecycle, Fence, Survival, REPORT format, Evidence-gathering,
Orchestration.

### Tier C: SKILL.md content invariants (automated)
Header presence is not enough -- a section can be empty. Assert the load-bearing rules are
stated: "The Gate Law", "co-extensive", "all-goals-done", "Autonomy dial", "severity-aware",
"Trusted-input boundary", "human-evidence", "outer-loop-tracker". NOTE this is a deletion
tripwire (substring presence), NOT a semantic check: it catches a load-bearing rule being
removed, but cannot catch a rule being contradicted elsewhere in prose. Behavioural
correctness is enforced by Tier A, not Tier C.

### Tier D: Referenced lib files exist (automated)
Every `<name>.py` cited in SKILL.md OR references/*.md must resolve to a file under some
`skills/*/lib/` or `skills/*/evals/` -- with or without a `lib/` prefix or as a bare
backtick name. Allows correct cross-skill refs (`personal-workflow/lib/fence.py`,
`personal-critic-gate/lib/vote_parser.py`) while catching a truly dangling reference.

### Tier E: Role resolution (manual)
Manually verify the FAST_CRITIC resolution chain on a fresh machine:
1. `--critic <agent>` -> uses that agent.
2. Host repo with a critic agent -> discovers it via `personal-workflow/lib/discover.py`.
3. No critic agent, ms-mario plugin -> uses ms-mario.
4. No critic, no plugin -> inline judge, announced as degraded.
This tier requires a live Claude session and cannot be automated.

## Known gaps / deferred (honest backlog)
Code-backed + eval-covered today: `secrets_scan.py` (incl. per-field connstring FP),
`halt.py` (breaker primitives), `flag_excluded` (security denylist), `scope_warnings` +
`gate_is_single_artifact` (THE GATE LAW check), `validate_beacon_cell` / `validate_skill_ref`
(untrusted-input guards), and the `deadline` / `run-ceiling` never-stop conditions.

Still DRIVER-WIRED (prose contract in SKILL.md, marked inline `[DRIVER-WIRED]`, NOT yet a
standalone eval) -- each should gain a red-then-green eval before a production unattended run
with secrets in scope:
- the post-action pre-commit `git diff` -> secrets_scan -> block-commit wiring (tick step 5);
- the `--force-resume` resume-refusal path (consumes `halt.is_blocked`);
- the contract-integrity hash-compare between arm and resume (Trusted-input boundary);
- the fail-closed `--unattended` arm-time self-check (verifies the guard primitives exist);
- gate promotion (fuzzy/human -> accept_cmd) is a DRIVER state-compile step:
  stop_eval.py is unchanged, but the driver MUST (a) re-derive the gate each
  tick, (b) record `gate_promoted_at`, (c) fold a gate-mode marker into the
  signature on the promotion tick. [DRIVER-WIRED backlog -- red-then-green eval
  needed before an unattended run relies on late promotion.];
- the human-evidence halt+resume dispatch (tick step 7 `human-evidence` branch)
  is a driver step: the loop halts, emits an observation request, and resumes
  with the human's pasted evidence supplying `fuzzy_verdict`. [DRIVER-WIRED backlog.]

v3 DRIVER-WIRED backlog batch (added in personal-loop v3, each needs a red-then-green eval
before an unattended run):
- human-evidence halt dispatch: the driver halts and emits an observation request; resumes
  with human-pasted evidence supplying `fuzzy_verdict`. [DRIVER-WIRED backlog]
- auto-goal-phase selection: the driver auto-selects the current phase from the goal beacon
  without user confirmation. [DRIVER-WIRED backlog]
- gate-promotion state-compile: the driver re-derives the gate each tick, records
  `gate_promoted_at`, and folds a gate-mode marker into the signature on the promotion
  tick. [DRIVER-WIRED backlog]
- route() dispatch + depth/width-at-spawn + root-ledger accounting: orchestration branching
  and resource tracking wired in SKILL.md prose but not yet covered by a standalone eval.
  [DRIVER-WIRED backlog]
- heartbeat idempotency/CAS: the outer-loop-tracker heartbeat write must be atomic; CAS
  semantics are prose-specified but not yet eval-exercised. [DRIVER-WIRED backlog]

ST-690 replay tier (manual, Tier E): needs a driver-simulation harness that does not exist
yet -- a scoped cost; until built, this tier is manual (Tier E).
