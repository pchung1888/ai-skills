# Findings notes

One Markdown file per feature or prototype, at the `--notes` path. It collects what the lesson
found, so the next version starts from facts. Create it with this skeleton when it does not exist.

```markdown
# <Feature> - notes collected during the code lessons

Purpose: findings and decisions to carry into the next version.
Status: learning notes only. Nothing here is approved or built yet.

## Decisions taken
## Findings from the code lessons
## Open questions
```

## One finding

One bullet, with the step, `file:line`, what the code does, why it matters, and a label.

```markdown
- Step 9, `DetailPage.tsx:87`: the page calls `/app` only for `me` and the calendar list.
  The service still runs `pBrowseHoliday` (`Program.cs:124`), and the page throws the rows away.
  One wasted SP call on every detail open (EXTRACTED).
```

- EXTRACTED: you read it in the code, a command output or the database.
- INFERRED: you derived it. Say the basis in a few words: "(INFERRED from lines 121-153, not tested)".
- UNKNOWN: you could not check it. Say how to find out.

## One decision

When the user states a rule or picks an option mid-lesson, write it under "Decisions taken" with their
name and the date, in their words where possible. Then continue the lesson.

```markdown
- Never change an existing SP. ASP pages and VB6 DLLs call it (owner, 2026-11-12).
```

## No duplicates

Search the notes for the file name and the key word before you write. If the finding is there,
say "Already in the notes, under <heading>" and add only what is new to that bullet.
