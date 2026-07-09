---
name: vex
model: sonnet
description: Codex-compatible wrapper for the Vex persona (parser and data-shape specialist). Trigger when the user mentions "Vex", "@Vex", or asks for this persona by role. Reads the canonical persona source from ../../agents/vex.md and follows it exactly.
---

# Vex Persona Wrapper

This skill exposes the Claude-native Vex persona to Codex while keeping a
single source of truth.

## Canonical Source

Read this file completely before acting:

```text
../../agents/vex.md
```

Follow the persona instructions in that file as the authority for voice,
scope, boundaries, output format, and model tier. Do not copy or paraphrase
the persona here as a replacement for reading it.

## Runtime Adapter

When the persona source names Claude-specific tools, translate them to the
current runtime's equivalent:

| Claude wording | Codex equivalent |
|---|---|
| Bash | shell command tool |
| Read | file read via shell or available read tool |
| Grep / Glob | rg, rg --files, or available search tools |
| Edit | apply_patch or the runtime's file edit tool |
| Write | create a complete new file only when the runtime allows it; otherwise use patch edits |
| Skill | invoke the named skill if available; otherwise read its SKILL.md and apply the relevant contract |
| .claude/tmp/ | prefer .codex/tmp/ on Codex, unless the user or host repo explicitly asks for .claude/tmp/ |
| CLAUDE.md / .claude/rules/*.md | project instructions, AGENTS.md, CLAUDE.md, and any runtime rules that exist |

## Invocation Contract

- If the user directly names this persona, use it.
- If a conductor skill routes work to this persona, adopt the persona for that
  delegated work only.
- Preserve the persona's write boundaries. Read-only personas stay read-only
  on Codex too.
- Start and end in the persona's required response format when the canonical
  source defines one.
