# Claude Runtime Overlay

TEMPLATE - rules here load only in Claude Code, after the shared core.

- Use `Read`, `Glob` and `Grep` for file inspection instead of shell commands.
- When the context window is nearly full, run `/compact` or start a fresh
  session with a short handoff note.

## Explaining Sentences - Human Voice

Every sentence that explains an idea, a step you did, or how something
technical works must read like a person telling the user across the desk.
Headers, tables and icons stay; this is about the sentences.

1. Say who does what: "the safety check refuses the path", not "the path
   is refused".
2. One idea per sentence. Two ideas means two sentences.
3. Name the term, then say right away what it does: "`normPath`, a small
   helper that turns every backslash into a forward slash".
4. Say why it matters in the same or the next sentence. A fact with no
   "so what" is not done.
5. Never point at something the user was not shown: say what "the flip" or
   "the gate" is before using the name.
6. Code names are fine, but plain words must still say what changed. A
   sentence that is only a pile of code names fails.

This applies to every reply, subagent report and written explanation,
with or without the htsw skill. `/personal-htsw` holds the full version
with before-and-after examples.
