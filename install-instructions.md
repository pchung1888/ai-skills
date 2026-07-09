# Install -- ai-skills

This plugin ships as a self-contained marketplace for both Claude Code and
Codex. Both runtimes load the same `plugins/ping-personal/skills/` tree.
Claude Code first:

## 1. Add the marketplace (this is the load-bearing step)

In any active Claude Code session, run:

```
/plugin marketplace add pchung1888/ai-skills
```

You should see: `Successfully added marketplace: ping-personal`.

That command does THREE things automatically -- you do NOT need to edit
settings.json manually:

1. Clones the repo to `~/.claude/plugins/marketplaces/ping-personal/`.
2. Registers it in `~/.claude/plugins/known_marketplaces.json`.
3. (On first add) Prompts you to enable plugins it found.

If the prompt did not enable the plugin, do step 2.

## 2. Enable the plugin in `~/.claude/settings.json`

Open `~/.claude/settings.json` and add this line inside the
`enabledPlugins` block (merge with existing entries, do not overwrite):

```json
"enabledPlugins": {
  "ping-personal@ping-personal": true
}
```

Naming contract (read this once and never get burned again):

- The KEY is `<plugin-name>@<marketplace-name>`.
- `<plugin-name>` comes from `plugins/ping-personal/.claude-plugin/plugin.json` -> `"name"` field. Currently `ping-personal`.
- `<marketplace-name>` comes from `.claude-plugin/marketplace.json` -> top-level `"name"` field. Currently `ping-personal`. (It does NOT come from the GitHub repo slug -- the repo is `ai-skills` but the marketplace name inside the JSON is `ping-personal`.)
- So the correct entry is `ping-personal@ping-personal`. Both halves
  happen to be the same string because this repo names the marketplace
  and its single plugin identically -- neither one matches the repo's
  own name, which is a deliberate design choice, not a typo.

`extraKnownMarketplaces` is NOT required for installs from GitHub --
`/plugin marketplace add` populates `known_marketplaces.json` directly.
Skip it.

## 3. Reload plugins

Run this in any active Claude Code session:

```
/reload-plugins
```

Or just restart Claude Code.

## 4. Verify

Type `/` in the Claude Code prompt and confirm these skills appear in the
list:

- `/personal-goal`
- `/personal-goal-next`
- `/personal-progress`
- `/personal-critic-gate`
- `/personal-md-to-html`
- `/personal-htsw`
- `/personal-cache-stats`
- `/personal-lesson`
- `/personal-fable-mode`
- `/personal-online-research`

Then dogfood-test one:

```
/personal-htsw walk plugins/ping-personal/skills/personal-htsw/SKILL.md
```

You should get a walk-mode rendering explaining the htsw skill's own
SKILL.md.

## Optional dependency -- the Codex plugin

`/personal-critic-gate` Vote 3 routes through `/codex:rescue`. If you don't have
the `codex` plugin installed, `/personal-critic-gate` still works -- it falls back
to the **reviewer-as-veto** rule (ms-mario's vote becomes
load-bearing). Vote 3 is logged as unavailable, no error.

To install the `codex` plugin separately, see:
<https://github.com/openai/codex-claude-code-plugin>

## Python prerequisite -- the `/personal-goal` skill

`/personal-goal` and `/personal-goal-next` use Python helper scripts under
`plugins/ping-personal/skills/personal-goal/lib/` and
`plugins/ping-personal/skills/personal-goal-next/lib/`. They require **Python >=
3.11** on your PATH. If `python --version` reports < 3.11, install a
newer Python first.

## Codex install

This is separate from the optional Codex *plugin* dependency above. Here the
goal is the reverse: making the **ping-personal skills** themselves usable
inside **Codex CLI** sessions.

Codex does not read Claude Code's plugin install. This repo ships a Codex
marketplace manifest at `.codex-plugin/marketplace.json` and a Codex plugin
manifest at `plugins/ping-personal/.codex-plugin/plugin.json`, both pointing
at the same `skills/` tree the Claude plugin uses -- one source of truth, two
runtimes.

From GitHub:

```powershell
codex plugin marketplace add pchung1888/ai-skills
codex plugin add ping-personal@ping-personal
```

From a local checkout:

```powershell
codex plugin marketplace add <path-to-this-repo>
codex plugin add ping-personal@ping-personal
```

Then start a **fresh Codex session**. Skills load at session start, so the
session you ran the command from will not see them.

### Persona agents on Codex

Codex does not load the top-level `agents/` directory, so each of the 8
persona agents also ships as a lightweight wrapper skill (`amanda`, `bunny`,
`dora`, `iris`, `maggie`, `ms-mario`, `rhea`, `vex`). Each wrapper reads the
canonical `agents/<name>.md` before acting, so Claude and Codex behavior stay
aligned when a persona changes. Verify by asking Codex:

```text
Use Iris to research where the auth flow lives.
Ask Ms.Mario to critique this plan.
```

### Codex model settings

Claude skill frontmatter keeps `model: haiku|sonnet|opus|inherit` for Claude
Code. Codex ignores those as model names -- configure Codex itself in
`~/.codex/config.toml`:

```toml
model = "gpt-5.5"
model_reasoning_effort = "high"
```

Rule of thumb: Claude `haiku` -> Codex `medium` effort; `sonnet`/`opus` ->
`high` (or `extra-high` when available and worth it); `inherit` -> keep the
current Codex session setting. See
[`plugins/ping-personal/runtime-compatibility.md`](./plugins/ping-personal/runtime-compatibility.md)
for the full runtime contract.

### Parity caveat

A few behaviors remain Claude-only: `/personal-htsw` pr mode calls Claude
Code's built-in `/review` skill, and `/personal-critic-gate` Vote 3 routes
through `/codex:rescue`. Both degrade gracefully (documented fallbacks, no
errors).

## Release verification

Before publishing a version for either runtime:

```powershell
python scripts/check_dual_runtime.py
pwsh plugins/ping-personal/evals/run-all.ps1
```

The first proves the Claude and Codex manifests point at the same plugin and
agree on version. The second proves every skill eval is green -- it must print
`ALL EVALS PASS (35 skills)`.

## Troubleshooting

If `/reload-plugins` doesn't pick up the new plugin:

1. Check that the marketplace clone landed at
   `~/.claude/plugins/marketplaces/ping-personal/` (the directory is named
   after the MARKETPLACE, not the GitHub repo). If it doesn't exist, re-run
   `/plugin marketplace add pchung1888/ai-skills` and watch for errors.
2. Check that `plugins/ping-personal/.claude-plugin/plugin.json` is valid
   JSON. A parse error there silently hides the plugin.
3. Check that the skills directories exist under
   `plugins/ping-personal/skills/<skill-name>/SKILL.md` -- Claude Code
   auto-discovers skills from this layout; there's no explicit registration
   in `plugin.json`.

If the plugin clones but skills don't appear in `/`:

- Open `~/.claude/plugins/marketplaces/ping-personal/plugins/ping-personal/.claude-plugin/plugin.json`
  and confirm `"name": "ping-personal"` matches the `<plugin-name>` half
  of your `enabledPlugins` entry.

## Optional -- install the pre-commit hook in your other repos

`plugins/ping-personal/hooks/pre-commit-backtick-guard.sh` is a
standalone bash hook for catching fabricated code references in long
markdown specs. To use it in another repo:

```bash
mkdir -p .githooks
cp ~/.claude/plugins/marketplaces/ping-personal/plugins/ping-personal/hooks/pre-commit-backtick-guard.sh .githooks/
chmod +x .githooks/pre-commit-backtick-guard.sh
git config core.hooksPath .githooks
```

Or call it from an existing hook runner (husky, lefthook, pre-commit).
