# ai-skills

**A production dual-runtime plugin (Claude Code + Codex): 28 skills, 8
role-scoped agents, ~50 Python modules, and a deterministic eval gate that
blocks every merge.**

Built and used daily in my own engineering workflow, then curated into this
public copy: same code, same evals, scrubbed of employer- and client-specific
identifiers so it is safe to share. This is not a toy or a tutorial repo -- it
is the actual harness I use to get real work done with an AI agent, published
as evidence of how I approach agentic systems.

```
$ pwsh plugins/ping-personal/evals/run-all.ps1
  OK  dual-runtime ... personal-goal ... personal-loop ... personal-critic-gate (38) ...
  ALL EVALS PASS (36 skills)
```

(36 = the 28 skills plus 8 Codex persona-wrapper skills, one per agent.)

---

## Why this exists (and what it demonstrates)

Most "AI skills" repos are a folder of prompts. This one is an argument that
**the hard part of agentic engineering is not the prompt -- it is everything
around the prompt**: what the model sees, what it is allowed to do, when it is
allowed to stop, and how you prove any of it works. Each capability below maps
to a concrete, inspectable piece of this repo.

| Competency | Where to look | What it does |
|---|---|---|
| **Context engineering** | `personal-goal` beacons, `personal-progress` handoffs | Skills that write and re-read their own structured memory across sessions, so work survives a crash or a context reset instead of living only in a chat log. |
| **Harness engineering** | `personal-workflow/lib/fence.py`, `personal-loop/lib/preflight.py`, `secrets_scan.py` | Deterministic guardrails *around* the model: irreversible-action detection, readiness/scope/exclusion gates before an unattended run, pre-commit secret scanning. The model proposes; code disposes. |
| **Loop engineering** | `personal-loop` | An outer loop that drives inner goals with exactly one authoritative stop-gate per run (never a critic's opinion), an autonomy dial trading gate frequency for unattended duration, and a fail-closed mode that refuses to arm if its own safety primitives are not provably present. |
| **Evaluation-driven development** | every `skills/*/evals/`, `run-all.ps1` | 25 deterministic red/green graders, one per skill. `run-all.ps1` is the real ship gate: no green, no merge. |
| **Multi-agent orchestration** | `plugins/ping-personal/agents/` | 8 role-scoped persona agents (plan / research / implement / parse / design / git / audit / critique) dispatched by role, instead of one do-everything agent. |
| **Dual-runtime portability** | `runtime-compatibility.md`, `scripts/check_dual_runtime.py`, `.codex-plugin/` | One skill tree packaged for both Claude Code and Codex: parallel manifests, per-agent Codex wrapper skills, a Claude-to-Codex model/effort mapping table, and a drift check that fails the build if the two runtimes disagree. |
| **Model/effort routing** | `model:` frontmatter in every `SKILL.md` | Orchestrators (`personal-loop`, `personal-workflow`, `personal-goal`, `personal-fable-mode`, `personal-online-research`) run `inherit` so the driving session's tier is never silently downgraded; mechanical workers pin `haiku`; judgment-heavy workers pin `sonnet`/`opus`. Enforced by the eval gate, not convention. |

---

## The architecture, in one picture

```
/personal-loop            outer loop: campaign-aware, condition-based autonomy
    |                     one authoritative stop-gate; fail-closed when unattended
    v
/personal-workflow        conductor: discovers the host repo's skills + agents,
    |                     routes each phase to the best one, fans out when safe
    v
/personal-goal            phase engine: crash-recovery beacon, per-phase commits,
    |                     resumable across sessions and quota windows
    v
[ 8 persona agents ]      amanda(plan) iris(research) bunny(build) vex(parse)
                          maggie(design) dora(git) rhea(audit) ms-mario(critique)

        every durable action first passes through:
        fence.py (irreversible?) -> secrets_scan.py (leak?) -> critic gate (sound?)
```

Nothing here trusts the model to "just be careful." Safety is a property of the
harness, enforced by code with its own tests -- not a hope pinned on a prompt.

---

## A worked example: the customer-support triage copilot

Three skills (`personal-cs-client-question`, `personal-cs-step-by-step`,
`personal-cs-escalate-to-dev`) form a triage pipeline that answers "where is X
in the app / how do I do Y" against a codebase, and **refuses and escalates**
the moment its confidence drops below threshold or the request touches
something dangerous (raw SQL, credentials, a schema mutation).

What makes it interview-worthy is not the routing -- it is the discipline:

- **A confidence floor with a hard refusal.** Below 0.80, or on any
  data-mutating request, the skill stops and hands off rather than guessing.
- **A telemetry contract enforced by JSON Schema.** Every answer self-reports a
  metric row validated against `cs-metric-schema.json` -- the schema is the
  single source of truth, so the docs and the code cannot silently drift.
- **A cross-client confidentiality gate** that refuses even a yes/no leak of
  which client a past ticket belonged to.
- **An HTML dashboard** (`cs-metrics-viewer.html`) that reads the telemetry log
  so you can see, over time, how often the copilot answered vs. escalated and
  why.

It is a small, honest model of how I would build an AI feature on a real
production system: measurable, refusal-first, and safe by construction.

---

## Install

Claude Code:

```
/plugin marketplace add pchung1888/ai-skills
/reload-plugins
```

```json
// ~/.claude/settings.json
"enabledPlugins": { "ping-personal@ping-personal": true }
```

Codex CLI (the repo ships a parallel `.codex-plugin` manifest):

```
codex plugin marketplace add pchung1888/ai-skills
codex plugin add ping-personal@ping-personal
```

Full procedure (naming contract, Codex model settings, verification) is in
[`install-instructions.md`](./install-instructions.md); the dual-runtime
contract is in
[`plugins/ping-personal/runtime-compatibility.md`](./plugins/ping-personal/runtime-compatibility.md).

## Run the eval gate

```powershell
pwsh plugins/ping-personal/evals/run-all.ps1            # prints "ALL EVALS PASS (<n> skills)"
pwsh plugins/ping-personal/evals/run-all.ps1 -Detailed  # per-grader checks
```

Requires PowerShell 7+ and Python 3.11+ on PATH.

## Explore the skills

Start with these three to see the range:

- [`personal-loop`](./plugins/ping-personal/skills/personal-loop/SKILL.md) -- the loop-engineering centerpiece; read "The Gate Law" first.
- [`personal-critic-gate`](./plugins/ping-personal/skills/personal-critic-gate/SKILL.md) -- a multi-seat adversarial review panel that gates high-risk actions by majority vote.
- [`personal-cs-client-question`](./plugins/ping-personal/skills/personal-cs-client-question/SKILL.md) -- the refusal-first support copilot described above.
- [`personal-fable-mode`](./plugins/ping-personal/skills/personal-fable-mode/SKILL.md) -- a method skill: a five-gate working discipline (scope / evidence / adversarial reasoning / verification / calibrated reporting) that upgrades whichever model is already running.

Full skill-by-skill index: [`plugins/ping-personal/README.md`](./plugins/ping-personal/README.md).

---

## What is intentionally not here

This is a curated copy, not a mirror -- and how it was curated is itself part of
the point.

- **No history to leak.** Rather than flip a private repo public (which exposes
  every past commit), this is a fresh repo whose history only ever contains
  curated, scrub-verified snapshots.
- **No working documents.** Design docs, audit trackers, and job-application
  material never shipped as part of the plugin and were excluded, not scrubbed
  after the fact.
- **Scrubbed, and verified scrubbed.** Employer/client names, internal system
  names, real deploy paths, and real protocol-message identifiers were removed
  and confirmed absent by grep -- not assumed. Where a real value was doing
  double duty as a functional safety check (a deploy-path fence), the mechanism
  was kept and the identifier genericized into a documented extension point.

Doing the redaction as a design decision rather than an afterthought is the same
instinct the rest of this repo is built on.

## License

MIT -- see [`LICENSE`](./LICENSE). Use, fork, and adapt freely.
