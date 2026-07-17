# ping-personal

Cross-project Claude Code skills.

## Skills

### `/personal-goal` + `/personal-goal-next`

Multi-phase goal orchestration with crash-recovery beacons. Use when starting work that may span sessions or survive a crash.

- `/personal-goal <slug>` -- initialize a goal: write the beacon, register the audit tracker, dispatch the first phase.
- `/personal-goal-next` -- advance to the next phase, mark the previous one done, run the accept-gate.

Beacons land under `docs/<slug>/` by default. Override paths via the skill's preflight.

### `/personal-progress`

Session handoff writer. Writes `docs/progress/YYYY-MM-DD-<task>-progress.md` (and optionally a sibling `*-handoff.md` for open decisions) so the next session can resume without losing context. Triggers preparatively on phrases like "save progress", "wrap up the session", "stopping soon", "context limit". Uses the bundled template under `skills/personal-progress/templates/`.

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

## Agents — the maid line-up

Eight project-agnostic persona-overlay agents. Each speaks HK Cantonese + English, starts every response with `<Name>: `, follows a consistent response-block format, and reads your project's `CLAUDE.md` / `.claude/rules/*.md` for project-specific constraints. Dispatch by `@-mention` or natural language (e.g. "dispatch Iris on src/auth.ts"), or as `subagent_type: <name>` via the Agent tool.

| Agent | Persona | Role |
|---|---|---|
| `amanda` | 🕊️ 艾曼達 (COO · Plan Writer) | Turns clarified intent into an executable plan with persona-routed dispatch sequence. Never dispatches or writes production code -- writes the plan and returns. |
| `iris` | 🦉 鳶鳶 (Lead Researcher) | Read-only investigator. Produces EXTRACTED / INFERRED / BLANK-tagged findings under `.claude/tmp/`. Never writes source files. |
| `bunny` | 🐰 繽繽 (Full-Stack Implementer) | Writes and edits code surgically per the plan. Verifies via the project's test/dev command. Diagnose workflow for hard bugs. |
| `vex` | 🖤 薇絲 (Parser Specialist · Warlock) | Owns parsers, data-shape contracts, CSV/PDF/JSON ingestion, knowledge-graph adapters. Goth-style loyalty. Strict variable-naming discipline. Closes reports with `Done.` / `Fixed.` |
| `maggie` | 🔮 瑪姬 (CTO · Design System + Chart Designer) | Owns design tokens and chart decisions. Uses `grill-me` to surface decision branches. TL;DR Decision Briefs with recommendation. Pre-impl gate for Bunny. |
| `dora` | 🐗 多拉 (Git Sentinel · DevOps) | All git/PR ops. Sibling-only worktrees. Backup before destructive ops. PR-hygiene gate (TODO + progress + lessons) before push. Never bypasses hooks. |
| `rhea` | 🛡️ 莉雅 (CISO + CQO · Sacred Auditor) | Post-impl audit + governance hardening. Binary verdict: ✅ SANCTIFIED or ❌ REJECTED. Owns TDD/BDD decisions, secrets scan, maid-scope check, persona integrity. |
| `ms-mario` | 🎓 瑪莉奧夫人 (Chief Critic) | Adversarial GAN-style reviewer. Severity-tagged findings (🔴/🟠/🟡/🟢). Code-Reading Pre-Flight. Vote 2 of `/personal-critic-gate`. |

The line-up assumes a "single dispatcher + multiple maids" workflow. In the personal-dashboard repo, the dispatcher is **Foxy** (a Cantonese-speaking main-session persona defined in that repo's CLAUDE.md). The maids are designed to work with Foxy but also work fine when the orchestrating session is plain Claude -- they only need to be invoked correctly.

## Hooks

### `pre-commit-backtick-guard.sh`

Optional pre-commit guard that detects fabricated code references in long markdown specs. Drop it into your repo's `.githooks/` directory and wire via `git config core.hooksPath .githooks`. See the script header for setup details.

### `pre-push-discipline.sh`

Optional pre-push guard that blocks the three most common "oh no" pushes: direct push to `main` / `master`, deletes of `feature/*` (long-lived integration branches), and any non-fast-forward push to any branch. Drop it into `.githooks/` alongside the backtick guard. Bypass with `git push --no-verify` (documented reason expected).
