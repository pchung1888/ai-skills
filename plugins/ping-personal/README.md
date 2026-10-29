# ping-personal

Cross-project Claude Code skills.

## Skills

### `/personal-goal` + `/personal-goal-next`

Multi-phase goal orchestration with crash-recovery beacons. Use when starting work that may span sessions or survive a crash.

- `/personal-goal <slug>` -- initialize a goal: write the beacon, register the audit tracker, dispatch the first phase.
- `/personal-goal-next` -- advance to the next phase, mark the previous one done, run the accept-gate.

Beacons land under `docs/<slug>/` by default. Override paths via the skill's preflight.

### `/personal-handoff`

Session handoff writer. Writes two linked files in `docs/progress/`: `YYYY-MM-DD-<task>-handoff.md`, the entry point with next steps, open decisions and suggested skills, and `YYYY-MM-DD-<task>-progress.md` with the history and facts. Start the next session with "read the handoff file". Triggers preparatively on phrases like "save progress", "wrap up the session", "stopping soon", "context limit". Uses the bundled template under `skills/personal-handoff/templates/`.

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

### `/personal-critic-judge`

Judged review, planned to replace `/personal-critic-gate`. Five reviewers (ms-mario, amanda,
maggie, rhea, and codex or iris) return findings only, with no votes. A fresh judge rules on each
finding against your main goal and the subtask under review: real or not, in scope or not, fix
now or later, and why. Only "fix now" rows get fixed, then the judge checks those fixes once.
A leaked secret, data loss, a security hole or a deleted test is never ruled "never".

### `/personal-md-to-html`

Render markdown (plans, specs, audit trackers) as styled HTML. Two themes: `arc` and `midnight`. Includes a check script that verifies the rendered HTML round-trips its content.

### `/personal-htsw` -- How This Shit Works

Re-explain code, a PR diff, a spec, a plan, or current conversation. Main modes:

- `walk` -- walk-me-through-it explainer (default)
- `pr` -- PR review brief
- `qa` -- QA testing brief
- `boss` -- pitch-it-to-my-boss summary
- `now` -- where this session stands: verdict, flowchart, focus table (used by the ping-hud Simple and Deep HTML buttons)

Every mode follows the "Explaining sentences" rules (who does what, one idea per
sentence, name the term then say what it does, say why it matters). Add
`--cantonese` to any mode for an answer in spoken Hong Kong Cantonese; technical
terms and punctuation stay ASCII English.

### `/personal-next`

Independent next-step recommender behind the ping-hud Next button. Writes a
facts-only brief of the session, asks one read-only seat (`next-recommender`) for
2-4 typed next steps as JSON, checks them with `validate.py`, then lets you pick
by clicking.

### `/personal-quota`

Report your REAL Claude usage: 5h (session) %, weekly %, per-model scoped %,
and context-window %, each with its reset time in local EST/EDT. Reads the
ping-hud mod's live-usage snapshot first when it is fresh, then ccstatusline's
cache when fresh, otherwise fetches the same `/api/oauth/usage`
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

### `/personal-mr-triage`

Triage reviewer comments on a GitLab MR or GitHub PR. Each finding is verified
against the code with evidence (`file:line` or command output), then fixed or
pushed back on with reasons. Replies are drafted to the reviewer in plain
language, never citing the private chat, and posted only after you approve.
Before it says "pushed" it shows the remote commit hash.

### `/personal-harness`

Apply, update, check or extend your global rules on the current machine. Apply
runs `scripts/bootstrap_machine.ps1` (clone or pull, install the generated
CLAUDE.md / AGENTS.md, install or update this plugin) and explains any FAIL line.
Add-rule edits `harness/`, installs, runs the sync check and pushes after you
approve the diff. A brand-new machine needs the bootstrap command once, before
the plugin (and so this skill) exists there.

### `/personal-copilot-talk`

A talking mode for the session, for an install, deploy, data scrub or runbook you
run by hand on a box the agent cannot reach. Each reply is one step: a verdict on
the last step, numbered actions, stop points, and a short "Tell me:" list. It
drops the mechanism and TL;DR sections until you say stop.

### Adapted from Matt Pocock's skills (MIT)

- `/personal-diagnosing-bugs` -- build a red-capable feedback loop before any theory: an HTTP request to the IIS page, `sqlcmd` for the stored procedure, or a `cscript` COM harness.
- `/personal-domain-modeling` -- keep `docs/glossary/GLOSSARY.md` and `docs/glossary/decisions/` current while designing; challenge fuzzy terms against the code.
- `/personal-wizard` -- generate a PowerShell wizard for steps only a person can do, such as an RDP deploy to a QA or client box.
- `/personal-teach` -- a multi-session learning workspace with a mission, lessons rendered by md-to-html, and learning records.
- `/personal-grill-me` -- stress-test a plan in rounds of questions, each with a recommended answer; "with docs" also writes `docs/glossary/`.
- `/personal-wait-what` -- re-pitch the last message: context first, 20-word sentences, the glossary's terms.
- `/personal-wayfinder` -- chart work too big for one session as a map of decision tickets: Jira for company repos, GitHub issues for personal repos, local Markdown otherwise.
- Aliases `grill-me`, `grilling`, `grill-with-docs` and `wait-what` forward to the two skills above, so old commands keep working without Matt's plugin.

License text: `THIRD-PARTY-NOTICES.md`.


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

One utility agent sits outside the line-up: `next-recommender`, the read-only seat that `/personal-next` dispatches.

The line-up assumes a "single dispatcher + multiple role agents" workflow. The dispatcher is the orchestrating main session; the agents only need to be invoked correctly.

## Hooks

### `pre-commit-backtick-guard.sh`

Optional pre-commit guard that detects fabricated code references in long markdown specs. Drop it into your repo's `.githooks/` directory and wire via `git config core.hooksPath .githooks`. See the script header for setup details.

### `pre-push-discipline.sh`

Optional pre-push guard that blocks the three most common "oh no" pushes: direct push to `main` / `master`, deletes of `feature/*` (long-lived integration branches), and any non-fast-forward push to any branch. Drop it into `.githooks/` alongside the backtick guard. Bypass with `git push --no-verify` (documented reason expected).

### Claude Code hooks (`hooks/hooks.json`)

Loaded automatically with the plugin. `stop-unpushed.sh` warns at session stop
when the current branch has commits that are not on its upstream.
`post-edit-check.sh` runs after Edit/Write and flags CRLF line endings in `.sh`
files and missing or malformed SKILL.md frontmatter. Both share `hook-lib.sh`.
Codex reads the same shell hooks from `hooks/codex-hooks.json` (no `modules` field).

### ping-hud mod (`hooks/register.tsx`, Claude Code only)

`hooks/hooks.json` loads `register.tsx` as a Claude Code mod. It draws a band
above the prompt (model, context, quota forecast) with two button rows: an
Action row (Handoff, Plan, Next, Agents, Goals) and an HTSW row (Pane, Simple,
Explain, Kid, Deep HTML, Motion). It also adds a Goals pane, an Agents pane, an
Explanation pane, and the `/personal-hud` command. The band is on after load;
`/personal-hud off` hides it and `/personal-hud on` brings it back. Quota numbers
need a Claude subscription login; on other accounts they may show `--`. The Plan
button needs the separate `html-plan` plugin. Tests: `claude plugin test plugins/ping-personal`.

The Explanation pane answers the HTSW buttons through a side call, so the
explanation stays out of the main chat. Motion puts a request in the prompt box;
after you send it, the main session starts `film-maker`, a background Sonnet
subagent registered by the mod and limited to the ToolSearch, Artifact and
ArtifactData tools. It makes a 30-second film, and the pane shows the link.

## Cross-runtime rules harness

`harness/` holds one set of global rules for every assistant runtime:
`harness/core/shared.md` (the rules, with your identity as placeholders) plus
thin overlays in `harness/runtime/` for Claude, Codex and ChatGPT. The shipped
files are a template: edit them before you install.

| Command | What it does |
|---|---|
| `python scripts/sync_harness_adapters.py --update-manifest` | Rebuild `harness/manifest.json` after editing `harness/` |
| `python scripts/sync_harness_adapters.py --install` | Write `~/.claude/CLAUDE.md` and `~/.codex/AGENTS.md` (the first install backs up the old files) |
| `python scripts/check_harness_sync.py --check` | Verify manifest, installed adapters, ASCII and secret scan |
| `powershell -ExecutionPolicy Bypass -File scripts\bootstrap_machine.ps1 -RepoPath <clone folder>` | New machine: clone or pull this repo, install adapters, install the plugin. Example `-RepoPath`: `C:\Users\<you>\src\ai-skills` |

`/personal-harness` wraps these commands.
