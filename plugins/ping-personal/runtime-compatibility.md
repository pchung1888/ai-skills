# Runtime Compatibility

This repo is a dual-runtime plugin. The same `plugins/ping-personal/skills/`
tree is packaged for both Claude Code and Codex.

## Manifests

| Runtime | Marketplace manifest | Plugin manifest | Shared payload |
|---|---|---|---|
| Claude Code | `.claude-plugin/marketplace.json` | `plugins/ping-personal/.claude-plugin/plugin.json` | `plugins/ping-personal/skills/` |
| Codex | `.codex-plugin/marketplace.json` | `plugins/ping-personal/.codex-plugin/plugin.json` | `plugins/ping-personal/skills/` |

Do not fork or copy the skill files per runtime. If a skill needs
runtime-specific behavior, put the branching rule inside the skill text or a
helper script and keep one `SKILL.md`.

## Persona Agents

The Claude-native persona files live in `plugins/ping-personal/agents/`.
Codex does not load that top-level agent directory directly, so each persona
also has a lightweight skill wrapper:

| Persona | Codex skill wrapper | Canonical source |
|---|---|---|
| Amanda | `amanda` | `agents/amanda.md` |
| Bunny | `bunny` | `agents/bunny.md` |
| Dora | `dora` | `agents/dora.md` |
| Iris | `iris` | `agents/iris.md` |
| Maggie | `maggie` | `agents/maggie.md` |
| Ms.Mario | `ms-mario` | `agents/ms-mario.md` |
| Rhea | `rhea` | `agents/rhea.md` |
| Vex | `vex` | `agents/vex.md` |

The wrapper skill is only an adapter. It must read the canonical source file
before acting and must not duplicate the persona body. This keeps Claude and
Codex behavior aligned when a persona changes.

## Install

Claude Code:

```text
/plugin marketplace add pchung1888/ai-skills
/plugin add ping-personal@ping-personal
/reload-plugins
```

Codex from GitHub:

```powershell
codex plugin marketplace add pchung1888/ai-skills
codex plugin add ping-personal@ping-personal
```

For a local checkout:

```powershell
codex plugin marketplace add <path-to-this-repo>
codex plugin add ping-personal@ping-personal
```

Start a fresh session after installing or upgrading either runtime.

## Model Mapping

Claude frontmatter keeps its existing `model:` values for Claude Code. Codex
does not interpret `haiku`, `sonnet`, or `opus` as model names. Use Codex
configuration instead:

```toml
model = "gpt-5.5"
model_reasoning_effort = "high"
```

Suggested mapping:

| Claude skill model | Codex setting | Use |
|---|---|---|
| `haiku` | `gpt-5.5`, `model_reasoning_effort = "medium"` | routing, formatting, cheap deterministic chores |
| `sonnet` | `gpt-5.5`, `model_reasoning_effort = "high"` | normal implementation, review, explanation |
| `opus` | `gpt-5.5`, `model_reasoning_effort = "high"` or `"extra-high"` when available | eval design, visual/taste calls, high-risk planning |
| `inherit` | keep the active Codex session setting | method skills such as `personal-fable-mode` |

Codex one-off override:

```powershell
codex exec -m gpt-5.5 -c 'model_reasoning_effort="high"' "Use personal-fable-mode on this task"
```

## Compatibility Rules

- Prefer runtime-neutral terms in new skills: "agent", "driver", "tool",
  "project rules", "runtime state".
- When a Claude-only term is needed, name the Codex equivalent beside it.
  Example: `CLAUDE.md / AGENTS.md / project instructions`.
- Use `${CLAUDE_PLUGIN_ROOT}` only in Claude-only snippets. For portable
  scripts, resolve the skill directory from the script path or accept
  `PING_PERSONAL_PLUGIN_ROOT`.
- Keep user state outside the repo. Claude defaults to `~/.claude`; Codex
  defaults to `~/.codex`. Portable skills should accept
  `PING_PERSONAL_STATE_ROOT` when they need a shared state root.
- Do not rely on Claude-only slash commands (`/browse`, `/review`,
  `/workflows`, `/reload-plugins`) without a fallback path.
- Top-level Claude persona agents under `plugins/ping-personal/agents/` are
  exposed to Codex through wrapper skills. Each wrapper includes
  `skills/<persona>/agents/openai.yaml` so Codex can account for its invocation
  policy.

## Verification

Run the dual-runtime drift check before release:

```powershell
python scripts/check_dual_runtime.py
```

Run the full skill suite:

```powershell
pwsh plugins/ping-personal/evals/run-all.ps1
```

Both must pass before bumping or publishing.
