# ai-skills

A Claude Code marketplace + plugin (`ping-personal`) of 25 cross-project skills
and 8 persona agents, built and used daily in my own workflow. This repo is a
portfolio copy: same code, same evals, scrubbed of employer- and
client-specific identifiers so it's safe to share and demo.

## What this demonstrates

- **Context engineering** -- skills that write and read their own structured
  memory across sessions (`personal-goal`'s crash-recovery beacons,
  `personal-progress`'s handoff docs), rather than relying on conversation
  history staying in context.
- **Harness engineering** -- deterministic guardrails that sit *around* the
  model instead of trusting its judgment alone: `personal-workflow/lib/fence.py`
  (irreversible-action detection), `personal-loop/lib/preflight.py`
  (readiness/scope/exclusion checks before a goal is allowed to run
  unattended), `secrets_scan.py` (pre-commit secret detection), and a JSON
  Schema (`cs-metric-schema.json`) that's the actual source of truth for what
  a skill's telemetry may contain -- not just a suggestion in prose.
- **Loop engineering** -- `personal-loop` drives `personal-workflow`/`personal-goal`
  as an inner loop: one authoritative stop-gate per run (never a critic's
  opinion), an autonomy dial that trades gate frequency for unattended
  duration, and a fail-closed unattended mode that refuses to arm if its own
  safety primitives aren't provably present.
- **Evaluation-driven development** -- every skill ships an `evals/eval.ps1`
  deterministic grader (code-backed, not vibes), and `evals/run-all.ps1` is
  the actual ship gate: `ALL EVALS PASS (25 skills)` or nothing merges.
- **Multi-agent orchestration** -- 8 persona agents (`amanda`, `iris`, `bunny`,
  `vex`, `maggie`, `dora`, `rhea`, `ms-mario`) each scoped to one role
  (planning, research, implementation, parsing, design, git ops, audit,
  adversarial critique), dispatched by a router rather than one do-everything
  agent.

## Skills (highlights)

- `/personal-goal` + `/personal-goal-next` -- multi-phase goal orchestration with crash-recovery beacons.
- `/personal-loop` -- the outer loop: campaign-aware, condition-based autonomy over `personal-workflow`/`personal-goal`.
- `/personal-workflow` -- autopilot conductor: discovers a host repo's skills/agents, routes phases, fans out safely.
- `/personal-critic-gate` -- 5-seat adversarial review panel before high-risk actions.
- `/personal-create-eval` -- scaffolds or audits an eval for any skill (CREATE / ENHANCE modes).
- `/personal-cs-client-question`, `/personal-cs-step-by-step`, `/personal-cs-escalate-to-dev` -- a 3-skill customer-support triage pipeline (locate -> how-to -> escalate) with its own metric-telemetry schema and HTML dashboard, generalized from a production skill I run daily.
- `/personal-fix-decode` -- deterministic FIX 4.4 protocol message decoder.
- `/personal-understanding` -- orchestrates the `understand-anything` plugin to build a knowledge graph of any codebase.

See `plugins/ping-personal/README.md` for the full skill-by-skill list, and
each skill's own `SKILL.md` for exact behavior contracts.

## Install

Add to `~/.claude/settings.json`:

```json
"enabledPlugins": {
  "ping-personal@ping-personal": true
}
```

Then in a Claude Code session:

```
/plugin marketplace add pchung1888/ai-skills
```

`/reload-plugins` (or restart Claude Code) to load. See `install-instructions.md`
for the full auto-mode-safe procedure, including the Codex CLI junction setup.

## Evals

```powershell
pwsh plugins/ping-personal/evals/run-all.ps1            # prints "ALL EVALS PASS (<n> skills)"
pwsh plugins/ping-personal/evals/run-all.ps1 -Detailed  # also prints each grader's checks
```

`run-all.ps1` exits 0 only if every skill's grader is green -- it's the
acceptance gate for any change to this plugin.

## What's intentionally not here

This is a curated copy, not a mirror. Session-scoped working documents
(design docs, audit trackers, job-application material) never shipped as
part of the plugin and were excluded rather than scrubbed after the fact --
a fresh repo with a clean history, not a public flip of a private one.

## License

MIT (see LICENSE) -- use, fork, adapt freely.
