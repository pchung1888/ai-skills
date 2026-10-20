# Fixture: a lesson that matches one already stored

Existing lesson: "## [CAUTION] Git Bash date prints GMT" (Rule: use plain date, not TZ=).
Incoming lesson: "TZ=America/New_York date printed GMT again in Git Bash."
Expected: the router proposes moving it up the ladder (for example a check that fails on TZ= date
use) instead of appending a duplicate doc entry.
