_Explaining: the deploy pipeline (`scripts/deploy.ps1`) · purpose: boss_

## What this gets you

The deploy pipeline ships the new release to production in one step.

It validates the schema before writing, which is exactly the banned-word
violation this fixture exists to trip: boss mode forbids engineering jargon
like "schema", so htsw-check.py must reject this rendering.
