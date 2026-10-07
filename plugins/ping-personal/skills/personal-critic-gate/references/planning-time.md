# Planning-time artifacts

Loaded from SKILL.md when the argument is a planning-time recommendation block.

In addition to pre-ship diffs and plan files, the gate fires on
planning-time recommendations -- cases where the driver has produced
"a set of options + a single recommendation" and wants a vote before
locking the pick.

Planning-time artifact block shape (inline text passed as the argument):

```
TYPE: planning-time-recommendation
OPTIONS: [A: <label>, B: <label>, ...]
RECOMMENDATION: <one of the option labels>
RATIONALE: <one paragraph of why this pick>
CONTEXT: <one paragraph: what is being decided, scope, constraints>
```

For planning-time artifacts:

- All 5 seats cast a vote using one OPTIONS label (or ABSTAIN).
- Majority (3+ seats) on the same option wins.
- If no option reaches 3 seats, fall through to ms-mario veto: ms-mario's
  pick wins if it dissents from the top vote-getter; otherwise the top
  vote-getter stands.
