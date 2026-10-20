---
name: personal-plugin-release
model: sonnet
description: Ship a new version of the ping-personal plugin end to end -- coordinated dual-runtime version bump, PR, merge, local install, reload, and VERIFIED-LOADED checks that prove the new version is actually live in Claude Code and Codex. Trigger on /personal-plugin-release, "release the plugin", "bump the plugin version", "ship the plugin", "install the latest plugin and verify", "why is the new skill not showing up". Also use when a merge to the default branch (main or master) conflicts on manifest version files.
---

# /personal-plugin-release

Ship a plugin version so that the new version is provably what Claude Code
and Codex load. The usual failure is not the bump -- it is the tail: the
version is reported as installed but the new skill is still not loaded. Every
release ends with verify-loaded gates; a release without them is not done.

## The manifest coupling (miss one and rollout silently breaks)

| File | Scope | What to bump |
|---|---|---|
| `plugins/ping-personal/.claude-plugin/plugin.json` | repo / Claude | `version` |
| `.claude-plugin/marketplace.json` (repo root) | repo / Claude | `metadata.version` and the plugin's `version` entry |
| `plugins/ping-personal/.codex-plugin/plugin.json` | repo / Codex | `version` |
| `.codex-plugin/marketplace.json` (repo root) | repo / Codex | must point to `./plugins/ping-personal` |
| `~/.claude/plugins/installed_plugins.json` | user / Claude | updated by the install step, not by hand-editing first -- verify it moved |
| `~/.codex/config.toml` + Codex plugin cache | user / Codex | updated by `codex plugin marketplace add/upgrade` + `codex plugin add`, not by hand-editing first -- verify it moved |

The install key in both runtimes is `ping-personal@ping-personal`, NOT
`ping-personal@personal-plugin`.

## Procedure

1. **Preflight.** Confirm clean working tree on a topic branch. Read all
   repo manifest files above; if versions already disagree, stop and
   reconcile before bumping. If merging the default branch conflicts only on manifest
   version files, resolve by taking the higher version, then continue.
2. **Bump** all version-bearing repo manifests to the same new semver. Run
   the dual-runtime check and eval suite:
   `python scripts/check_dual_runtime.py` must print `DUAL RUNTIME CHECK PASS`.
   `pwsh plugins/ping-personal/evals/run-all.ps1` must print `ALL EVALS PASS`
   before any release ships.
   If a critic-gate final review is cited, refuse its PASS unless its `Reviewed: <sha>` equals
   the commit being merged (`tally.py --final --sha <sha> --expect-head`, exit 2 = stale); a stale PASS needs a fresh review.
   An owner's "ship anyway" on a FIX is not blocked.
3. **PR + merge.** Commit, push the topic branch, open the PR (`gh pr create`),
   and pause for merge unless the user has already said to merge. Never push main
   directly. GO/NO-GO before merge: checks green, verify-loaded plan ready, and `Reviewed: <sha>`
   matches the PR head commit; any no is NO-GO.
4. **Local update -- Claude.** After merge, check out the default branch the remote
   names (`git symbolic-ref --short refs/remotes/origin/HEAD`, e.g. `origin/main` ->
   `main`) and `git pull`; confirm the merge commit is there
   (`git merge-base --is-ancestor <merge-sha> HEAD`), then
   `claude plugin update ping-personal@ping-personal` (or `/plugin
   install ping-personal@ping-personal --scope user` for a first install).
   Note: `/plugin marketplace add` is what triggers the marketplace clone;
   `extraKnownMarketplaces` alone does not.
5. **Local update -- Codex.** `~/.codex/config.toml` has other writers (the Codex
   desktop app, other sessions) and was once zeroed mid-write, so guard each command:
   - Before: list Codex processes (`Get-Process codex`); if the desktop app or a CLI
     session is open, ask the user to close it. Copy the config to
     `config.toml.bak-before-<version>-<yyyymmdd-hhmmss>` and confirm the copy is
     intact (non-null byte count equals the file size).
   - Run `codex plugin marketplace upgrade ping-personal` (a local-folder marketplace
     answers "not configured as a Git marketplace"; that is harmless, go on) or
     `codex plugin marketplace add <repo>` for a first install, then
     `codex plugin add ping-personal@ping-personal`.
   - After EACH command: non-null byte count equals size, `codex features list`
     exits 0, and the protected lines (`model`, `model_reasoning_effort`,
     `model_catalog_json`) match the backup. A damaged file: restore the backup. A
     changed protected line: stop and ask the user; never restore over it silently.
6. **Reload.** Ask the user to run `/reload-plugins` for Claude Code (harness
   command -- the skill cannot run it). A full restart also works. Start a
   fresh Codex session after the Codex install/update.
7. **VERIFY-LOADED gate -- Claude (mandatory).** Prove the new version is live:
   - `~/.claude/plugins/installed_plugins.json` names the new version for
     `ping-personal@ping-personal`.
   - `~/.claude/plugins/cache/ping-personal/ping-personal/<new-version>/`
     exists and contains the changed skill files (spot-check one changed line).
   - If a new skill was added: it appears in the session skill list after
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
   - `codex exec --skip-git-repo-check -s read-only "Reply PROBE_OK" < /dev/null`
     answers, and its output has no `failed to parse plugin hooks config` line (close
     stdin, or codex waits for input). Changed hooks run only after the user trusts them
     with `/hooks` in the Codex CLI.
   Report each gate with evidence (quote the version string found), never with
   "should be installed now".
9. **Rollback.** If a gate fails: revert the merge commit on a new topic branch through a PR, bump a
   patch version in all three manifests, reinstall in both runtimes (the Codex backup already exists).

## Rationalizations

| Excuse | Why it is wrong | Do instead | Source |
|---|---|---|---|
| "The commands exited 0, so it is installed" | Exit 0 does not prove the new version loaded | Quote the observed version string | `plugins/ping-personal/skills/personal-plugin-release/SKILL.md` Boundaries |
| "Restore the older config.toml backup" | A restore once reverted the user's model choice | Diff first, ask the user about each change | `plugins/ping-personal/skills/personal-plugin-release/SKILL.md` Boundaries |
| "Edit installed_plugins.json by hand" | It fakes the gate instead of passing it | Move it via the install/update command | `plugins/ping-personal/skills/personal-plugin-release/SKILL.md` Boundaries |

## Boundaries

- Never bump versions unless the user asked for a release.
- Never edit `installed_plugins.json` by hand to fake the gate -- it must
  move via the install/update command.
- Never edit `~/.codex/config.toml` by hand to fake a Codex install -- it must
  move via `codex plugin marketplace ...` and `codex plugin add`.
- Never restore an older `config.toml` backup without diffing it against the
  current file and asking the user about every changed setting: a restore once reverted
  their model choice.
- A failed verify-loaded gate is reported as FAILED with the observed state;
  do not claim success because the commands exited 0.
