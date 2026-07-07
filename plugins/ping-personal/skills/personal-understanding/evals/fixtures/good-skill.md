---
name: personal-understanding
model: sonnet
description: Lifecycle orchestrator for the understand-anything plugin. Trigger on /personal-understanding or "understand this codebase", "install understand-anything", "build the knowledge graph".
---

# /personal-understanding

Thin orchestrator. Modes: `install`, `onboard`, `use`. No-arg runs a read-only status probe.

## use sub-actions

`dashboard` (default), `ask`, `explain`, `diff`, `domain`, `guide`.

## delegations

- onboard -> understand-anything:understand
- use dashboard -> understand-anything:understand-dashboard
- use ask -> understand-anything:understand-chat
- use explain -> understand-anything:understand-explain
- use diff -> understand-anything:understand-diff
- use domain -> understand-anything:understand-domain
- use guide -> understand-anything:understand-onboard

## install mode

This skill CANNOT run /plugin marketplace add or /plugin install -- the user must type those.
