---
name: personal-plugin-release
model: sonnet
description: Ship a new version of the ping-personal plugin end to end -- coordinated dual-runtime version bump, PR, merge, local install, reload, and VERIFIED-LOADED checks that prove the new version is actually live in Claude Code and Codex. Trigger on /personal-plugin-release, "release the plugin", "bump the plugin version", "ship the plugin", "install the latest plugin and verify", "why is the new skill not showing up". Also use when a merge to master conflicts on manifest version files.
---

# /personal-plugin-release

Ship a plugin version so that the NEW version is provably what Claude Code
and Codex load. The historical failure is not the bump -- it is the tail:
"you said 0.13.0 is installed, /personal-loop is still not there." Every
release ends with verify-loaded gates; a release without them is not done.

## The manifest coupling (miss one and rollout silently breaks)

| File | Scope | What to bump |
|---|---|---|
| `plugins/ping-personal/.claude-plugin/plugin.json` | repo / Claude | `version` |
| `.claude-plugin/marketplace.json` (repo root) | repo / Claude | `metadata.version` and the plugin's `version` entry |
| `plugins/ping-personal/.codex-plugin/plugin.json` | repo / Codex | `version` |
| `.codex-plugin/marketplace.json` (repo root) | repo / Codex | must point to `./plugins/ping-personal` |
| `~/.claude/plugins/installed_plugins.json` | user / Claude | updated by the install step, NOT by hand-editing first -- verify it moved |
| `~/.codex/config.toml` + Codex plugin cache | user / Codex | updated by `codex plugin marketplace add/upgrade` + `codex plugin add`, NOT by hand-editing first -- verify it moved |

The install key in both runtimes is `ping-personal@ping-personal`, NOT
`ping-personal@personal-plugin`.

## Procedure

1. **Preflight.** Confirm clean working tree on a topic branch. Read all
   repo manifest files above; if versions already disagree, stop and
   reconcile before bumping. If merging master conflicts only on manifest
   version files, resolve by taking the HIGHER version, then continue.
2. **Bump** all version-bearing repo manifests to the same new semver. Run
   the dual-runtime check and eval suite:
   `python scripts/check_dual_runtime.py` must print `DUAL RUNTIME CHECK PASS`.
   `pwsh plugins/ping-personal/evals/run-all.ps1` must print `ALL EVALS PASS`
   before any release ships.
3. **PR + merge.** Commit, push the topic branch, open the PR (`gh pr create`),
   and pause for merge unless Ping has already said to merge. Never push main
   directly.
4. **Local update -- Claude.** After merge: `git checkout master && git pull`,
   then `claude plugin update ping-personal@ping-personal` (or `/plugin
   install ping-personal@ping-personal --scope user` for a first install).
   Note: `/plugin marketplace add` is what triggers the marketplace clone;
   `extraKnownMarketplaces` alone does not.
5. **Local update -- Codex.** Run `codex plugin marketplace upgrade
   ping-personal` if the marketplace is already configured, or
   `codex plugin marketplace add <repo>` for a first install. Then run
   `codex plugin add ping-personal@ping-personal`.
6. **Reload.** Ask Ping to run `/reload-plugins` for Claude Code (harness
   command -- the skill cannot run it). A full restart also works. Start a
   fresh Codex session after the Codex install/update.
7. **VERIFY-LOADED gate -- Claude (mandatory).** Prove the new version is live:
   - `~/.claude/plugins/installed_plugins.json` names the new version for
     `ping-personal@ping-personal`.
   - `~/.claude/plugins/cache/ping-personal/ping-personal/<new-version>/`
     exists and contains the changed skill files (spot-check one changed line).
   - If a NEW skill was added: it appears in the session skill list after
     reload. If it does not, the usual causes in order: reload not run yet,
     install pulled a stale marketplace clone (re-run `/plugin marketplace
     update ping-personal`), or the three-file coupling was incomplete.
8. **VERIFY-LOADED gate -- Codex (mandatory when Codex is installed).** Prove
   the new version is live:
   - `codex plugin list --json` shows `ping-personal@ping-personal` installed
     at the new version, OR the Codex plugin cache for `ping-personal`
     contains `plugins/ping-personal/.codex-plugin/plugin.json` with the new
     version.
   - The cached plugin contains the changed skill files (spot-check one
     changed line).
   Report each gate with evidence (quote the version string found), never with
   "should be installed now".

## Boundaries

- Never bump versions unless Ping asked for a release.
- Never edit `installed_plugins.json` by hand to fake the gate -- it must
  move via the install/update command.
- Never edit `~/.codex/config.toml` by hand to fake a Codex install -- it must
  move via `codex plugin marketplace ...` and `codex plugin add`.
- A failed verify-loaded gate is reported as FAILED with the observed state;
  do not claim success because the commands exited 0.
