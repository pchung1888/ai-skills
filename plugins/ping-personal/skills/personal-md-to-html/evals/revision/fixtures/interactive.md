---
title: Bakery plan demo
eyebrow: fixture - interactive page
interactive: true
---

# The bakery *morning*

## A flow

```flow
dough = Mix the dough
rise  = Let it rise
bake  = Bake the loaf
| dough | rise |
| .     | bake |
dough -> rise : rest
rise -> bake : oven
```

## Notes and a question

```note
tone: warn
title: Oven check
body: The oven needs ten minutes to heat before the first loaf.
```

```ask
id: loaf-pick
question: Which loaf should we bake first?
options:
  - value: rye
    label: Rye loaf
    checked: true
  - value: white
    label: White loaf
```

## Closing

The shop opens at seven, so the first tray must be out by then.
