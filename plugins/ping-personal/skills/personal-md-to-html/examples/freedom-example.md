---
mode: freedom
---

# Freedom-mode example

Freedom mode lets the preprocessor restructure the document as long as
the gist survives. The validator is NOT invoked for freedom-mode
renders, so token-level fidelity is at the rendering session's
discretion.

This fixture is documentation-only: it demonstrates the kind of
source a freedom-mode render is allowed to be aggressive with.

## Background

Last quarter we shipped four features into the trade-entry path.
Cost was around $200K and 8h per change. The team agreed that the
balance-mode safety net was overkill for an internal brainstorming
deck, so this deck targets freedom mode.

## What we want from freedom

- Promote loose prose into the most expressive component.
- Drop or compress connective sentences that don't help the reader.
- Synthesize a callout grid or rules block from a list when the list
  is really a typology.
- Add visual structure (sketches, timelines) that wasn't asked for
  but makes the deck land.

## What we still want preserved

The general message: trade-entry shipped, cost was real, the team
prefers freedom mode for ideation decks. Specific numbers and
ticket IDs are nice-to-have but not contract-mandatory.

A freedom-mode render is judged by whether the deck reads well
end-to-end, not by a mechanical token-presence check.
