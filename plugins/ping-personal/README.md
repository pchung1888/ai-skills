# ping-personal

Cross-project Claude Code skills.

## Skills

### `/personal-goal` + `/personal-goal-next`

Multi-phase goal orchestration with crash-recovery beacons. Use when starting work that may span sessions or survive a crash.

- `/personal-goal <slug>` -- initialize a goal: write the beacon, register the audit tracker, dispatch the first phase.
- `/personal-goal-next` -- advance to the next phase, mark the previous one done, run the accept-gate.

Beacons land under `docs/<slug>/` by default. Override paths via the skill's preflight.

### `/personal-handoff`

Session handoff writer. Writes `docs/progress/YYYY-MM-DD-<task>-progress.md` (and optionally a sibling `*-handoff.md` for open decisions) so the next session can resume without losing context. Triggers preparatively on phrases like "save progress", "wrap up the session", "stopping soon", "context limit". Uses the bundled template under `skills/personal-handoff/templates/`.

### `/personal-cache-stats`

Parses the most recent Claude Code transcript JSONL and reports the prompt-cache hit rate, plus the 1-hour vs 5-minute TTL split on cache writes. Auto-detects the project transcript dir from `$PWD`; falls back to the most recent JSONL across all project dirs when the auto-detect fails. PowerShell 7+ on `pwsh`.

### `/personal-critic-gate`

Adversarial-review gate. Fires a 3-vote majority before high-risk actions (force-push, schema migration, mass file rewrite, etc.):

- **Vote 1:** the proposer (the agent that wants to act).
- **Vote 2:** the `ms-mario` agent reads the cited code and produces an EXTRACTED / INFERRED / UNKNOWN findings table.
- **Vote 3:** `/codex:rescue` (Path B). Falls through to reviewer-as-veto when Codex is unavailable.

Two modes:
- **PAUSE** (interactive) -- gate prints findings, hands control back to user.
- **AUTO-RESOLVE** (autonomous) -- gate decides per the 3-vote rule, logs the decision.

### `/personal-md-to-html`

Render markdown (plans, specs, audit trackers) as styled HTML. Two themes: `arc` and `midnight`. Includes a check script that verifies the rendered HTML round-trips its content.

### `/personal-htsw` -- How This Shit Works

Re-explain code, a PR diff, a spec, a plan, or current conversation for one of four purposes:

- `walk` -- walk-me-through-it explainer (default)
- `pr` -- PR review brief
- `qa` -- QA testing brief
- `boss` -- pitch-it-to-my-boss summary

### `/personal-quota`

Report your REAL Claude usage: 5h (session) %, weekly %, per-model scoped %,
and context-window %, each with its reset time in local EST/EDT. Reads
ccstatusline's cache when fresh, otherwise fetches the same `/api/oauth/usage`
endpoint directly with your subscription OAuth token -- so it never depends on
ccstatusline being installed or alive. Context % is captured by an opt-in,
self-owned statusline shim (`ctx-sidecar`) that chains to ccstatusline so your
visible statusline is unchanged. The access token is never printed or logged.

### `/personal-jev`

A second opinion with a confidence meter from TypeSafe Jev. Four on-demand modes:
Decide (pick among options, with per-option composite scores), Which-tool (Noul vs
Choice vs Score), Checklist (batch yes/no checks), and Claim check. `jev.ps1` rejects
malformed questions, refuses payloads that look like client data (emails, company
name, GUIDs, SQL, stored-proc names, keys), previews by default, and only sends with
`-Send` after approval. It prints `YOUR CALL` when Jev is split. Needs
`TYPESAFE_API_KEY` (env var or `.env.local`); the key is never printed.

### `/personal-drift-check`

Measures harness drift: parses Claude Code JSONL transcripts and reports evidence share, skill-attribution share, and the decay curve across a session or a cohort of past sessions.

## Agents -- the role line-up

Eight project-agnostic role agents. Each follows a consistent response format and reads your project's `CLAUDE.md` / `.claude/rules/*.md` for project-specific constraints. Dispatch by `@-mention` or natural language (e.g. "dispatch iris on src/auth.ts"), or as `subagent_type: <name>` via the Agent tool.

| Agent | Role | What it does |
|---|---|---|
| `amanda` | Plan writer | Turns clarified intent into an executable plan with an owner-routed dispatch sequence. Never dispatches or writes production code -- writes the plan and returns. |
| `iris` | Researcher | Read-only investigator. Produces EXTRACTED / INFERRED / BLANK-tagged findings under `.claude/tmp/`. Never writes source files. |
| `bunny` | Implementer | Writes and edits code surgically per the plan. Verifies via the project's test/dev command. Diagnose workflow for hard bugs. |
| `vex` | Parser and data-contract specialist | Owns parsers, data-shape contracts, CSV/PDF/JSON ingestion, knowledge-graph adapters. Strict variable-naming discipline. |
| `maggie` | Architect and design-system owner | Owns design tokens and chart decisions. Uses `grill-me` to surface decision branches. TL;DR Decision Briefs with recommendation. Pre-implementation gate for bunny. |
| `dora` | Git and PR operations | All git/PR ops. Sibling-only worktrees. Backup before destructive ops. PR-hygiene gate (TODO + progress + lessons) before push. Never bypasses hooks. |
| `rhea` | Quality, security, and governance auditor | Post-implementation audit + governance hardening. Binary verdict: APPROVED or REJECTED. Owns TDD/BDD decisions, secrets scan, agent-scope check, token-cost gate. |
| `ms-mario` | Critic | Adversarial GAN-style reviewer. Severity-tagged findings (Critical / High / Medium / Low). Code-Reading Pre-Flight. Vote 2 of `/personal-critic-gate`. |

The line-up assumes a "single dispatcher + multiple role agents" workflow. The dispatcher is the orchestrating main session; the agents only need to be invoked correctly.

## Hooks

### `pre-commit-backtick-guard.sh`

Optional pre-commit guard that detects fabricated code references in long markdown specs. Drop it into your repo's `.githooks/` directory and wire via `git config core.hooksPath .githooks`. See the script header for setup details.

### `pre-push-discipline.sh`

Optional pre-push guard that blocks the three most common "oh no" pushes: direct push to `main` / `master`, deletes of `feature/*` (long-lived integration branches), and any non-fast-forward push to any branch. Drop it into `.githooks/` alongside the backtick guard. Bypass with `git push --no-verify` (documented reason expected).
