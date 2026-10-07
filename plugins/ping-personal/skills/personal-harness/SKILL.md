---
name: personal-harness
model: sonnet
description: Applies, updates, checks, or extends the personal harness - the global CLAUDE.md / AGENTS.md rules generated from this plugin's repo - on the current machine. Use when the user says /personal-harness, "apply the harness", "set up this machine", "update my rules on this machine", "sync the harness", "check the harness", "add a global rule", or a machine is missing the global rules.
---

# /personal-harness

The global rules live in this plugin's repo (ai-skills, or your fork of it) under
`harness/`. The shipped `harness/` is a template: fill in your identity and rules
before the first apply. Every
machine gets them by running `scripts/bootstrap_machine.ps1`, which clones or
pulls the repo, installs the generated `~/.claude/CLAUDE.md` and
`~/.codex/AGENTS.md`, and installs or updates the ping-personal plugin.
This skill drives that script and the rule-editing loop around it.

| Mode | Say | Does |
|---|---|---|
| apply (default) | "apply the harness", "set up this machine" | install or update everything on this machine |
| check | "check the harness" | report drift without changing anything |
| add-rule | "add a global rule: ..." | edit the canonical source, install, commit, push |

## Find the repo

Use the first folder whose `git remote get-url origin` ends in `/ai-skills` or
`/ai-skills.git` (the public repo or your fork), starting with `$HOME\src\ai-skills`.
If none exists, use `$HOME\src\ai-skills`; apply mode clones it there.
Add-rule pushes, so point `origin` at your own fork, not the public repo.

## apply

1. If the repo folder does not exist, clone it:
   `git clone https://github.com/pchung1888/ai-skills.git "<repo>"`
   (or your fork's URL; pass the same URL to the script as `-RepoUrl`).
2. Run, from PowerShell:
   `powershell -ExecutionPolicy Bypass -File "<repo>\scripts\bootstrap_machine.ps1" -RepoPath "<repo>"`
3. Quote the last line. `MACHINE BOOTSTRAP PASS <version> <sha256>` is done.
   A FAIL line names the missing piece; fix it with the table below, then
   return to step 2.
4. If the output has a `First install: backed up ...` line, tell the user the
   backup path. Offer to compare that old file with the new CLAUDE.md and
   propose rules worth adding through add-rule; never merge them silently.
5. Tell the user to run `/reload-plugins` (or start a new session), because
   the running session keeps the rules and plugin it started with.

| FAIL says | Fix |
|---|---|
| git is not on PATH | install Git for Windows |
| git clone failed / GitHub access | sign in to GitHub on this machine (`gh auth login` or Git Credential Manager), then retry |
| git pull --ff-only failed | `git -C "<repo>" status`; commit, stash or discard local edits only with the user's OK |
| Python 3.9 or newer not found | install Python from python.org (not the Microsoft Store alias) |
| manual drift | someone edited `~/.claude/CLAUDE.md` by hand; show the diff against `~/.ping-harness\staging\claude-global.md`, move wanted lines into add-rule, then ask before re-running |
| the claude CLI is not on PATH | install Claude Code, then retry |

## check

Run `python "<repo>\scripts\check_harness_sync.py" --check` and
`git -C "<repo>" fetch` then `git -C "<repo>" status -sb`. Report: the PASS
or FAIL line, whether the repo is behind `origin`, and whether line 1 of
`~/.claude/CLAUDE.md` is the generated notice. Change nothing.

## add-rule

1. `git -C "<repo>" pull --ff-only`. Pick the file: a rule for all work goes
   in `harness/core/shared.md`; a Claude-only rule in `harness/runtime/claude.md`.
   A rule that must hold on every run belongs in a plugin hook, and a
   repeatable procedure in a skill - say so instead of adding prose.
2. Search the file for a section that already covers the topic and tighten
   it instead of adding a duplicate. Keep the rule to 1-3 lines with its
   reason. ASCII only; keep the file's existing line endings.
3. Show the diff and wait for the user's OK, because the rule will load in
   every future session on every machine.
4. Run `python scripts/sync_harness_adapters.py --update-manifest`, then
   `--install`, then `python scripts/check_harness_sync.py --check`; quote
   the PASS lines. If a check fails, return to step 2.
5. Commit with a technical message (no personal names), push, and show the
   remote hash from `git ls-remote origin <branch>`. Other machines pick it
   up by running apply.

## Boundaries

- Never hand-edit `~/.claude/CLAUDE.md` or `~/.codex/AGENTS.md`; they are
  generated and the installer refuses manual drift.
- Never commit anything from `~/.ping-harness` (backups, memory provenance,
  install state); it is per-machine and personal.
- Ask before deleting or renaming `~/.ping-harness`, force-pushing, or
  overwriting local edits in the repo.
