---
title: Accent override demo
accent: "#3E7BFF"
---

```eyebrow
Level-1 theming
```

# Accent override *demo*

Frontmatter `accent:` injects a `:root { --arc-accent: ... }` rule after the
arc palette. The override wins by cascade — no theme files changed.

```kpi
- label: DEPLOYS
  value: 47
  delta: +5%
- label: P95 LATENCY
  value: 184 ms
  delta: -11%
- label: ERROR RATE
  value: 0.03%
  delta: -0.01%
```

## Summary

```callout
- label: HOW IT WORKS
  quote: One frontmatter key re-tones every accent-bearing element — headings, eyebrows, pill outlines, table headers.
  body: Level 1 override. Works with any active theme. No new files required.

- label: SCOPE
  quote: v1 supports accent only. Future keys — paper, ink, good, warn, muted — follow the same injection pattern.
  body: Hold the full set for a v1.1 iteration when a real client request surfaces.
```
