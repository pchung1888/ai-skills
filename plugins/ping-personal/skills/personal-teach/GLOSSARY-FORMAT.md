# GLOSSARY.md Format

`GLOSSARY.md` is the canonical language of the workspace. Lessons, exercises and learning
records all use its terms. Writing a tight definition is itself evidence of understanding.

## Structure

```md
# {Topic} Glossary

{One or two sentences on what the topic covers.}

## Terms

**Context window**:
The full set of tokens a model can read in one request, including the system prompt and tool output.
_Avoid_: Memory, buffer

**Progressive disclosure**:
Loading detail only when a task needs it, so the context holds what matters now.
_Avoid_: Lazy loading, on-demand context
```

## Rules

- **Add a term only once the user understands it.** The glossary records compressed knowledge. Wait until the user can use the term correctly.
- **Be opinionated.** When several words mean one thing, pick the best and list the rest under `_Avoid_`.
- **Keep definitions tight.** One or two sentences. Define what the term IS.
- **Use glossary terms inside definitions.** That makes later terms easier to grasp.
- **Group under subheadings** when clusters appear. A flat list is fine otherwise.
- **Flag ambiguity.** If the wider field uses a term loosely, say how this workspace uses it.
- **Revise as understanding deepens.** Update in place. Do not leave stale entries.
