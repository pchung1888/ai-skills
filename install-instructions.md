# Install -- ai-skills

This plugin ships as a self-contained marketplace. To use it on any machine
with Claude Code:

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

## 3. Verify

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

## Use these skills from Codex CLI

This is separate from the optional Codex *plugin* dependency above. Here the
goal is the reverse: making the **ping-personal skills** themselves usable
inside **Codex CLI** sessions.

Codex does not read Claude Code's plugin install. It discovers skills from its
own global skill root, `~/.agents/skills/`. The cleanest way to share without
duplicating files is an NTFS **junction** per skill folder -- one source of
truth (this repo), zero config edits. This mirrors how `superpowers` and
`claude-official` are already linked into that root.

### Why junctions, not a Codex plugin manifest

Codex *can* consume a `.codex-plugin/plugin.json` registered as a local
marketplace in `~/.codex/config.toml`. We deliberately do NOT do that here:

- Junctions keep a single source of truth -- no second `version` field to keep
  in sync, no repackaging on every skill edit.
- A marketplace entry adds skill/plugin context noise to every Codex session
  and is harder to back out cleanly.

### Steps (Windows / PowerShell)

```powershell
$root = "$env:USERPROFILE\.agents\skills"
$src  = "<path-to-this-repo>\plugins\ping-personal\skills"
$skills = "personal-goal","personal-goal-next","personal-progress",
          "personal-critic-gate","personal-md-to-html","personal-htsw",
          "personal-cache-stats","personal-lesson","personal-lesson-ui",
          "personal-lesson-parser","personal-lesson-data","personal-lesson-tooling"
foreach ($s in $skills) {
  $link = Join-Path $root $s
  if (Test-Path $link) { Write-Host "SKIP (exists): $s"; continue }
  New-Item -ItemType Junction -Path $link -Target (Join-Path $src $s) | Out-Null
  Write-Host "LINKED: $s"
}
```

On macOS / Linux, use a symlink instead of a junction:

```bash
root="$HOME/.agents/skills"
src="<path-to-this-repo>/plugins/ping-personal/skills"
for s in personal-goal personal-goal-next personal-progress \
         personal-critic-gate personal-md-to-html personal-htsw \
         personal-cache-stats personal-lesson personal-lesson-ui \
         personal-lesson-parser personal-lesson-data personal-lesson-tooling; do
  ln -s "$src/$s" "$root/$s"
done
```

### Then

Start a **fresh Codex session**. Skills load at session start, so the session
you ran the command from will not see them. Verify by asking Codex to list its
available skills, or invoke `/personal-goal`.

### Parity caveat -- not every skill fully works on Codex

The junction exposes the `skills/` folder only. Skills that reach into the
plugin's `agents/` directory or call Claude built-in skills will load but not
fully function on Codex:

- `/personal-critic-gate` -- dispatches the maid agents (`ms-mario`) and
  `/codex:rescue`, which live in `agents/`, not `skills/`.
- `/personal-htsw` pr mode -- calls the built-in `/review` skill.

The other ten (`personal-goal`, `personal-goal-next`, `personal-progress`,
`personal-md-to-html`, `personal-cache-stats`, `personal-lesson`,
`personal-lesson-ui`, `personal-lesson-parser`, `personal-lesson-data`,
`personal-lesson-tooling`) are self-contained and behave normally.

## Troubleshooting

If `/reload-plugins` doesn't pick up the new plugin:

1. Check that the marketplace clone landed at
   `~/.claude/plugins/marketplaces/ai-skills/`. If the directory
   doesn't exist, the `extraKnownMarketplaces` entry is malformed --
   diff against your existing `openai-codex` entry to verify shape.
2. Check that `plugins/ping-personal/.claude-plugin/plugin.json` is valid
   JSON. A parse error there silently hides the plugin.
3. Check that the skills directories exist under
   `plugins/ping-personal/skills/<skill-name>/SKILL.md` -- Claude Code
   auto-discovers skills from this layout; there's no explicit registration
   in `plugin.json`.

If the plugin clones but skills don't appear in `/`:

- Open `~/.claude/plugins/marketplaces/ai-skills/plugins/ping-personal/.claude-plugin/plugin.json`
  and confirm `"name": "ping-personal"` matches the `<plugin-name>` half
  of your `enabledPlugins` entry.

## Optional -- install the pre-commit hook in your other repos

`plugins/ping-personal/hooks/pre-commit-backtick-guard.sh` is a
standalone bash hook for catching fabricated code references in long
markdown specs. To use it in another repo:

```bash
mkdir -p .githooks
cp ~/.claude/plugins/marketplaces/ai-skills/plugins/ping-personal/hooks/pre-commit-backtick-guard.sh .githooks/
chmod +x .githooks/pre-commit-backtick-guard.sh
git config core.hooksPath .githooks
```

Or call it from an existing hook runner (husky, lefthook, pre-commit).
