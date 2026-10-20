# Decision Note Format

A decision note records a hard-to-reverse choice and why it was made. The industry calls it
an ADR (architecture decision record).

Decision notes live in `docs/glossary/decisions/` with sequential numbers: `0001-slug.md`,
`0002-slug.md`, and so on. Create the folder only when the first note is needed.

## Template

```md
# {Short title of the decision}

{1-3 sentences: the context, what was decided, and why.}
```

That is all. A note can be one paragraph. Its value is recording that a decision was made, and why.

## Optional sections

Add these only when they carry real value. Most notes need none.

- **Status** frontmatter (`proposed | accepted | deprecated | superseded by 0007`): when decisions get revisited.
- **Considered Options**: only when the rejected alternatives are worth remembering.
- **Consequences**: only when a downstream effect is not obvious.

## Numbering

Find the highest number in `docs/glossary/decisions/` and add one.

## When to offer a decision note

All three must be true:

1. **Hard to reverse**: changing your mind later would cost real time.
2. **Surprising without context**: a future reader will look at the code and wonder why.
3. **The result of a real trade-off**: there were genuine alternatives, and one won for reasons.

An easy-to-reverse decision needs no note, because you would just reverse it. An obvious one
needs none either, because nobody will wonder.

### What qualifies

- **Architectural shape.** "Business rules live in stored procedures, not in the VB6 layer."
- **Integration patterns.** "The pages call the DLL; the DLL alone calls the database."
- **Technology choices with lock-in.** A database, an auth provider, a deployment target.
- **Boundary and scope decisions.** Which part owns which data. The explicit "no" answers count too.
- **Deliberate departures from the obvious path.** Anything a reasonable reader would assume the opposite of. These stop the next engineer from "fixing" something deliberate.
- **Constraints not visible in the code.** "This client's box cannot reach the internet." "The report must finish in under 30 seconds."
- **Rejected alternatives when the rejection is not obvious.** Otherwise someone suggests it again in six months.
