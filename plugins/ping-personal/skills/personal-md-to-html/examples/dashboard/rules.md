---
title: Rules demo
---
# Chart-picker rules

```rules
columns: [WHEN COLUMN SHAPE, W/ CARDINALITY, "→ RENDER AS"]
items:
  - data: [categorical, 9-30, "vertical bar, top-10 + 'other'"]
    note: Bucket the long tail; never render >12 bars.
  - data: [categorical, ">30", "top-10 list w/ counts"]
    note: A chart is the wrong shape. Show as a small table.
  - data: ["numeric (single)", "—", "histogram, 20 bins"]
    note: Distribution shape is the only honest summary.
  - data: ["numeric (pair)", "—", "scatter plot"]
    note: Reserve for the strongest correlation only.
```
