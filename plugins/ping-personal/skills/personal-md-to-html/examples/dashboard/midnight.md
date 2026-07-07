---
title: Midnight theme demo
theme: midnight
---

```eyebrow
Theme showcase
```

# Midnight theme *demo*

This page renders with the `midnight` dark theme — warm-coral accent on dark paper.

```kpi
- label: SESSIONS
  value: 8,142
  delta: +18%
- label: CONVERSION
  value: 3.7%
  delta: -0.2%
- label: MRR
  value: $12,400
  delta: +9%
  trend: line
  data: "98, 103, 108, 115, 124"
```

## Findings

```callout
- label: SIGNAL
  quote: Night-mode users average 22% longer session times than light-mode peers.
  body: Correlates with power-user cohort. Segment before acting on aggregate numbers.

- label: WATCH
  quote: Conversion dipped 0.2 pp this week despite session growth.
  body: Check funnel step 3 — form redesign shipped Monday may be the cause.
```

## Rules

```rules
- title: Keep palette at 14 tokens
  body: Every color in the theme maps to one semantic role. No one-off hex values in components.
- title: Fallback to arc components
  body: Themes that only override tokens skip shipping components.css — the renderer falls back automatically.
- title: Test with a real doc
  body: The smoke test for midnight renders this file and diffs against the committed golden.
```
