---
title: html-plan blocks demo
eyebrow: md-to-html - interactive page
---

# The html-plan *blocks*

## A flow

```flow
press = You press the button
ask   = The pane asks the model
page  = md-to-html builds the page
| press | ask |
| .     | page |
press -> ask : click
ask -> page : markdown
```

## A call tree

```calls
  runExplain(mode deep)          @ hooks/register.tsx:1075
    xDeepPage(answer)            @ hooks/register.tsx:1176
```

## A lifecycle

```machine
machine demo initial idle
state idle   # Waiting.
state done final  # Finished.

| idle | done |

idle -go-> done
```

## Code with pins

```code-pins
title: example.py
code: |
  def add(a, b):
      return a + b
start: 10
pins:
  11: The only line that does work.
```

## Output and notes

```terminal
$ md-to-html page.md
{g}page ready{/g} {dim}(0.2 s){/dim}
```

```note
tone: warn
title: Watch out
body: The page inlines the html-plan runtime, so it is about 230 KB.
```

```ask
id: demo-pick
question: Which block do you like most?
options:
  - value: flow
    label: The flow
    checked: true
  - value: code
    label: Code with pins
```
