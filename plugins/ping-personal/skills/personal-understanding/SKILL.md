---
name: personal-understanding
model: sonnet
description: Lifecycle orchestrator for the understand-anything plugin -- install, onboard a project, and use the knowledge graph. Trigger on /personal-understanding or natural phrases like "understand this codebase", "install understand-anything", "onboard this project to understand-anything", "build the knowledge graph", "open the understanding dashboard", "let Claude understand this repo", "scan this repo into a knowledge graph", "set up understand-anything", "analyze this project for Claude", "show me the understanding dashboard", "bootstrap understand-anything".
---

# /personal-understanding

Thin orchestrator over the understand-anything plugin. Handles the full lifecycle:
**install** -> **onboard** -> **use**.

The skill detects state, routes to the right mode, and then delegates to the
plugin's own skills via the Skill tool. It does NOT reimplement the analyzer
pipeline or the dashboard -- those stay in the plugin.

## Modes and aliases

| Mode | Aliases | Args | What it does |
|---|---|---|---|
| (none) | -- | -- | Status probe + recommendation. Read-only. Never starts a server or analysis. |
| `install` | `--install`, `setup`, `bootstrap` | -- | Prereq checks, install detection, build step. Prints `/plugin` commands the USER must run if the plugin is missing. |
| `onboard` | `analyze`, `scan`, `build`, `graph` | `[path] [passthrough flags]` | Ensure installed+built, then run `/understand` to create `.understand-anything/`. |
| `use` | `view`, `explore`, `dashboard` | `[sub-action]` | Require graph exists, then route sub-action to the matching plugin skill. Default sub-action: `dashboard`. |

### use sub-actions

| Sub-action | Delegates to |
|---|---|
| `dashboard` (default) | `understand-anything:understand-dashboard` |
| `ask <question>` | `understand-anything:understand-chat` |
| `explain <file/fn>` | `understand-anything:understand-explain` |
| `diff [ref]` | `understand-anything:understand-diff` |
| `domain` | `understand-anything:understand-domain` |
| `guide` | `understand-anything:understand-onboard` (team doc -- NOT a graph build) |

**Note on naming (AD-3):** "onboard" in this skill means "scan the project and
create the knowledge graph" -- that maps to `/understand`. The plugin's own
`/understand-onboard` generates a team onboarding doc and is exposed here as
`use guide`, not as the `onboard` mode, to avoid confusion.

**Out of scope (v1):** `/understand-knowledge` (Karpathy-pattern LLM-wiki graph)
is not wrapped. Use the plugin skill directly if you need it.

## No-arg mode -- status probe (AD-7)

Bare `/personal-understanding` runs a read-only status check and recommends the
next action. It never launches a server or kicks off analysis.

Steps:

1. Run the layered install detection (see `references/install-detection.md`).
2. Check whether `$PROJECT_ROOT/.understand-anything/knowledge-graph.json` exists.
3. If graph exists, read `$PROJECT_ROOT/.understand-anything/meta.json` and compare
   `gitCommitHash` against `git rev-parse HEAD`.
4. Print a status table:

```
understand-anything status
--------------------------
Plugin installed:  YES / NO
Core built:        YES / NO
Graph present:     YES / NO
Graph age:         <lastAnalyzedAt> / n/a
Graph at HEAD:     YES / NO / n/a
```

5. Recommend the next mode:
   - Plugin missing -> "Run `/personal-understanding install` first."
   - Core not built -> "Run `/personal-understanding install` to build core."
   - Graph missing -> "Run `/personal-understanding onboard` to create the knowledge graph."
   - Graph stale (commit changed) -> "Run `/personal-understanding onboard` to refresh the graph."
   - All green -> "Run `/personal-understanding use` to open the dashboard."

## install mode (AD-2 + AD-5)

Full procedure: `references/install.md`.

**Critical boundary (AD-2):** This skill CANNOT run `/plugin marketplace add` or
`/plugin install` -- those are Claude Code harness commands, not Bash commands.
If the plugin is missing, install mode prints the exact lines for the user to
type. It does NOT attempt to self-install.

Summary of what install mode does vs. what the USER does:

| Step | Who runs it |
|---|---|
| Check node/pnpm/python/git versions | Skill (via Bash) |
| Run layered install detection | Skill (via Bash) |
| Print `/plugin marketplace add` lines | USER types these |
| Build `@understand-anything/core` | Skill (via Bash, after plugin is present) |
| Verify `packages/core/dist/index.js` | Skill (via Bash) |

After install mode confirms the plugin is present and core is built, it reports
success and prompts the user to run `onboard`.

## onboard mode

1. Run install detection. If plugin is missing or core is not built, route to
   `install` mode first and stop.
2. Resolve `PROJECT_ROOT`: use the path argument if provided, else current
   working directory.
3. Delegate to the plugin skill:
   ```
   Skill(skill: "understand-anything:understand", args: "<passthrough args>")
   ```
4. After the skill returns, verify `.understand-anything/knowledge-graph.json`
   exists. Report success or failure.

Pass any extra flags (e.g. `--full`, `--language zh`) through as-is to the
plugin skill via `$ARGUMENTS`.

## use mode (AD-6)

1. Check that `.understand-anything/knowledge-graph.json` exists in the project.
   If not, print:
   ```
   No knowledge graph found. Run /personal-understanding onboard first.
   ```
   and stop.
2. Route by sub-action per the "use sub-actions" table above (default:
   `dashboard`), invoking `Skill(skill: "<delegate>", args: "<sub-action args>")`.
3. Pass the project path argument to `dashboard` if one was given:
   ```
   Skill(skill: "understand-anything:understand-dashboard", args: "<project-path>")
   ```

## Reference files

- `references/install.md` -- full bootstrap procedure (prereqs, install detection,
  build step, disk-space warning, platform notes)
- `references/install-detection.md` -- layered detection logic (AD-4) with bash
  snippets for each layer
