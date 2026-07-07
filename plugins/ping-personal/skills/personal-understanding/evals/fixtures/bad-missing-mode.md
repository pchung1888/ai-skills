---
name: personal-understanding
model: sonnet
description: Drops the install mode entirely -- R2 mode-documentation must fail for understand-anything.
---

# /personal-understanding

Modes: `onboard`, `use`. No-arg runs a status probe. (The setup/bootstrap mode is absent here.)

## use sub-actions

`dashboard`, `ask`, `explain`, `diff`, `domain`, `guide`.

Delegations: understand-anything:understand, understand-anything:understand-dashboard, understand-anything:understand-chat.

This skill CANNOT run /plugin install -- the user must type that.
