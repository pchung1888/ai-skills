---
mode: balance
---

# Fenced-block preservation test

This fixture exercises spec section 6.1 R1: real fenced code blocks
must survive verbatim through balance-mode rendering. Every F1-F6
token below appears inside a fenced `python` block, NOT in surrounding
prose, so the only way they reach the rendered HTML body is through
the preprocessor's R1 immutability guarantee.

```python
# Worked example combining all six protected-token classes.
# F1 number with unit:   $200M budget, 8h estimate
# F2 inline code lookalike: doProcessRequest
# F3 bold marker:        **critical path**
# F4 ALL-CAPS warning:   MUST NOT bypass validator
# F5 blockquote source:  > Reviewer confirmed single-predicate
# F6 ticket reference:   JIRA-670, P12

def estimate():
    budget = "$200M"           # F1
    routine = "doProcessRequest"  # F2
    headline = "**critical path**"  # F3
    rule = "MUST NOT"          # F4
    review = "> Reviewer confirmed single-predicate"  # F5
    ticket = "JIRA-670"          # F6
    return (budget, routine, headline, rule, review, ticket)
```

Outside the fence, a single callout block satisfies the validator's
"at least one custom artifact" check without introducing new F-tokens
that the assertion would have to track.

```callout
- label: KEEP
  quote: Real code fences are R1-protected.
  body: The preprocessor must never edit, delete, split, or merge them.
```
