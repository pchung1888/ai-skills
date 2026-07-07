---
name: personal-plugin-release
model: sonnet
description: Ship a new version of the ping-personal plugin end to end -- coordinated three-file version bump, PR, merge, local install, reload, and a VERIFIED-LOADED check that proves the new version is actually live. Trigger on /personal-plugin-release, "release the plugin", "bump the plugin version", "ship the plugin", "install the latest plugin and verify", "why is the new skill not showing up". Also use when a merge to master conflicts on the two version files.
---

# /personal-plugin-release

Ship a plugin version so that the NEW version is provably what Claude Code
loads. The historical failure is not the bump -- it is the tail: "you said
0.13.0 is installed, /personal-loop is still not there." Every release ends
with the verify-loaded gate; a release without it is not done.

## The three-file coupling (miss one and rollout silently breaks)

| File | Scope | What to bump |
|---|---|---|
| `plugins/ping-personal/.claude-plugin/plugin.json` | repo | `version` |
| `.claude-plugin/marketplace.json` (repo root) | repo | the plugin's `version` entry |
| `~/.claude/plugins/installed_plugins.json` | user | updated by the install step, NOT by hand-editing first -- verify it moved |

The enabledPlugins/install key is `ping-personal@ping-personal` (owner@name),
NOT `ping-personal@personal-plugin`.

## Procedure

1. **Preflight.** Confirm clean working tree on a topic branch. Read both
   repo version files; if they already disagree, stop and reconcile before
   bumping. If merging master conflicts on exactly these two files, resolve
   by taking the HIGHER version, then continue.
2. **Bump** both repo files to the same new semver. Run the eval suite:
   `pwsh plugins/ping-personal/evals/run-all.ps1` must print `ALL EVALS PASS`
   before any release ships.
3. **PR + merge.** Commit, push the topic branch, open the PR (`gh pr create`),
   and pause for merge unless Ping has already said to merge. Never push main
   directly.
4. **Local update.** After merge: `git checkout master && git pull`, then
   `claude plugin update ping-personal@ping-personal` (or `/plugin install
   ping-personal@ping-personal --scope user` for a first install). Note:
   `/plugin marketplace add` is what triggers the marketplace clone;
   `extraKnownMarketplaces` alone does not.
5. **Reload.** Ask Ping to run `/reload-plugins` (harness command -- the skill
   cannot run it). A full restart also works.
6. **VERIFY-LOADED gate (mandatory).** Prove the new version is live:
   - `~/.claude/plugins/installed_plugins.json` names the new version for
     `ping-personal@ping-personal`.
   - `~/.claude/plugins/cache/ping-personal/ping-personal/<new-version>/`
     exists and contains the changed skill files (spot-check one changed line).
   - If a NEW skill was added: it appears in the session skill list after
     reload. If it does not, the usual causes in order: reload not run yet,
     install pulled a stale marketplace clone (re-run `/plugin marketplace
     update ping-personal`), or the three-file coupling was incomplete.
   Report the gate with evidence (quote the version string found), never with
   "should be installed now".

## Boundaries

- Never bump versions unless Ping asked for a release.
- Never edit `installed_plugins.json` by hand to fake the gate -- it must
  move via the install/update command.
- A failed verify-loaded gate is reported as FAILED with the observed state;
  do not claim success because the commands exited 0.
