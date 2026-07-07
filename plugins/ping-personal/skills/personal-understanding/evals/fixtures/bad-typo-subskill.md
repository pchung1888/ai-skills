---
name: personal-understanding
model: sonnet
description: References a misspelled understand-anything sub-skill -- R4 referential integrity must fail.
---

# /personal-understanding

Modes: `install`, `onboard`, `use`. No-arg runs a status probe.

## use sub-actions

`dashboard`, `ask`, `explain`, `diff`, `domain`, `guide`.

Delegations: understand-anything:understand, understand-anything:understand-dashbord, understand-anything:understand-chat.

This skill CANNOT run /plugin install -- the user must type that.
