---
name: personal-wait-what
description: Use when the user says the last message did not land - "wait what", "I don't get it", "say that again simpler", "too much jargon", "you lost me", "explain that plainly". Re-pitches the last message with context first, short Simplified Technical English sentences, and the project's own glossary terms. Also reached by /wait-what.
---

# Wait, what?

Adapted from Matt Pocock's `wait-what` skill (MIT, see `THIRD-PARTY-NOTICES.md`).

The user did not understand where you have got to. Re-pitch your last message. Keep every fact,
number, file path and decision in it. Change only how it is said.

## How to re-pitch

1. **Context first.** Open with one to three sentences: what we are doing, and where we are now.
2. **Simplified Technical English (ASD-STE100).** Every sentence has 20 words or fewer. Use
   active voice: say who does what. Put one idea in each sentence. Prefer the common word over the fancy one.
3. **Name technical terms, then gloss them.** Keep the real term. Say in one short sentence what
   it does the first time it appears.
4. **Use the project's own words.** Read `docs/glossary/GLOSSARY.md` if it exists. If
   `docs/glossary/GLOSSARY-MAP.md` exists, follow it to the right glossary. Otherwise try a
   root `GLOSSARY.md`. Use the glossary's term and never its listed "avoid" words.
5. **Cut the AI writing patterns** that personal-unslop lists.
6. **End with the ask.** If the user must decide or do something, say exactly what in the last sentence.

## Limits

- Re-pitch only the last message. Add no new facts and no new opinions.
- A short re-pitch beats a long one. If the original had many points, keep the few that matter
  most and say how many you left out.
- This fixes one message. It does not change how later replies are written.
