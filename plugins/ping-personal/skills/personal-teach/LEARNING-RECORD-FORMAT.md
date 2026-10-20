# Learning Record Format

Learning records live in `learning-records/` with sequential numbers: `0001-slug.md`,
`0002-slug.md`, and so on. Create the folder when the first record is written.

They are the teaching version of an ADR. They record what the user has shown they understand, and
they set what to teach next.

## Template

```md
# {Short title of what was learned or established}

{1-3 sentences: what was learned or what prior knowledge was established, and why it matters for future sessions.}
```

That is the whole format. A record can be one paragraph.

## Optional sections

Add these only when they carry real value.

- **Status** frontmatter (`active | superseded by LR-NNNN`): when an earlier understanding is replaced.
- **Evidence**: how the user showed the understanding (a question answered, an exercise done, prior experience cited).
- **Implications**: what this opens up or rules out for later sessions, when that is not obvious.

## Numbering

Find the highest number in `learning-records/` and add one.

## When to write one

1. **The user showed real understanding** of something non-trivial: evidence of use, not just exposure.
2. **The user stated prior knowledge**: "I already know X". Record how deep, so it is not re-taught.
3. **A misconception was corrected.** These predict future stumbling points.
4. **The mission shifted.** Update `MISSION.md` and link to it.

### What does not qualify

- Material that was only covered. Coverage is not learning. Wait for evidence.
- A term already defined in `GLOSSARY.md`.
- A session log. Records hold decision-grade insights, not a diary.

## Supersession

When a later record contradicts an earlier one, mark the old one `Status: superseded by LR-NNNN`.
Do not delete it. How understanding changed is useful signal.
