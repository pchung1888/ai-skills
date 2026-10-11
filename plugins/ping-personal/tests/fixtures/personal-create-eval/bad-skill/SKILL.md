---
name: bad-skill
description: Unhealthy fixture skill used to calibrate audit_eval.py (expect HIGH, exit 1). It has an evals/ directory but no runnable grader.
---

# bad-skill

A minimal fixture with evals/eval-plan.md but no runnable grader file, so audit_eval.py flags a
HIGH finding and exits 1. Used only by personal-create-eval's own eval.
