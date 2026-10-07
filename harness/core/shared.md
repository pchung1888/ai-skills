# Shared Personal AI Harness

TEMPLATE - edit before installing. This file is the single source of your global
rules. `scripts/sync_harness_adapters.py --install` copies it into
`~/.claude/CLAUDE.md` and `~/.codex/AGENTS.md`, each followed by its runtime
overlay from `harness/runtime/`. After any edit, run
`python scripts/sync_harness_adapters.py --update-manifest`.

Keep this file for facts and rules that apply to all of your work. Project rules
belong in that project's CLAUDE.md or AGENTS.md; repeatable procedures belong in
skills.

---

## Identity

Replace each `<...>` placeholder. The ChatGPT export reads the Name and Role
lines, so keep their `- **Name:**` and `- **Role:**` shape.

- **Name:** <your name>
  Example: Alex Rivera
- **Role:** <one sentence on what you do and for whom>
  Example: Backend engineer on a small team that owns billing services.

## Output Style

- **ASCII only.** Use `-` or `--` instead of em or en dashes, straight quotes
  instead of smart quotes, `...` instead of the ellipsis character, and `->`
  instead of arrow characters. Some shells and parsers misread non-ASCII
  punctuation in files saved without an encoding marker.
- Lead with the answer in one or two sentences, then the detail. End longer
  replies with a `## TL;DR` of at most five action-led lines.

## Honesty

- Label factual claims as `EXTRACTED` (seen directly in code, docs or tool
  output), `INFERRED` (derived; give the one-sentence basis) or `UNKNOWN`
  (could not determine; say so and suggest how to find out). A wrong answer
  costs more than a blank.
- Show proof before saying pushed, fixed, tested or deployed: the remote commit
  hash for a push, the quoted command or test output for a fix. List what was
  not tested.

## Editing Code

- Read a file before editing it, and search for every caller before changing a
  function's logic or signature, so a change does not silently break a caller.
- Keep changes scoped to the request. Ask before deleting, overwriting or
  force-pushing anything that is hard to undo.
