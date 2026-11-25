# Check layers and drivers by stack

Open this in `create` step 3 and `maintain` step 4. Pick the cheapest layer that would catch the
bug a user would feel. A feature usually needs a runtime check plus one deeper layer.

## The four layers

| Layer | Question it answers | Proof artifact |
|---|---|---|
| Runtime | Does the feature work when driven the way a user drives it? | screenshot, saved HTML or response body, exit code |
| Database (characterization) | Does the query or stored procedure still return the same rows for the same data? | result set diffed against a golden file |
| Property | Does a stated rule hold for many generated inputs? | the failing input the tool shrinks to, or "N cases passed" |
| Mutation | Can each check above fail at all? | the planted change, the red run, the revert, the green rerun |

Formal verification (TLA+ / Lean) is not built in this version. When a feature has retries,
timeouts, two users acting at once, or a multi-step state flow, add a "Formal candidate" line to
its feature file: the rule that must always hold, in one sentence.

## Drivers by stack

Reuse what the repo already has first: Playwright specs, a `run-<name>` skill from
`/run-skill-generator`, test projects, seed scripts.

| Stack | Runtime driver | Deeper layer | Mutation to plant |
|---|---|---|---|
| ASP Classic page on IIS | `Invoke-WebRequest` or `curl` on the page URL; Playwright when the page needs clicks or a login | database layer on the procedure behind the page | change a filter, a join or a rounding call in the procedure or the page |
| VB6 COM DLL | a `cscript` VBScript harness that creates the object and calls the method with fixed inputs | property: loop over generated inputs in the harness | flip a comparison or a sign in the method; back up the good DLL, rebuild and re-register only on the local box; revert = restore the good DLL backup and re-register it, then restore the source |
| T-SQL stored procedure | `sqlcmd -S <server> -d <db copy> -Q "EXEC ..." -s"," -W` into a CSV | characterization: diff the CSV against `golden/<feature>.csv`; or tSQLt on the copy | delete a `WHERE` predicate, change `ROUND(x, 2)` to `ROUND(x, 0)` |
| React page | Playwright: navigate, act through accessible names or `data-testid`, screenshot | property: fast-check on the pure functions behind the page | remove a guard, invert a condition, drop a field from the request |
| .NET service | HTTP call to the endpoint (`Invoke-RestMethod`, `curl`), check status and body | property: FsCheck or CsCheck on the domain code; characterization on the procedure it calls | change a status code, drop a validation, swap two arguments |
| Python / other script | run the entry point with fixed input, check output and exit code | property: hypothesis | same as above |

## Characterization (golden file) rules

- The golden file records what the code does today. It is not proof the output is right. Say
  that in the feature file, and name the test oracle if one exists (a spreadsheet, a client
  statement, a hand calculation).
- Store golden files under `.claude/skills/verify/golden/`. Sort rows and fix the column order
  so a diff shows only real changes.
- Run against seeded or copied data that does not change between runs. A live database makes
  the golden file drift by itself.
- Updating a golden file is a decision: the runner takes an explicit `--approve <feature>` flag
  and the commit message says why the output changed.

## Data and isolation

- Drive and plant bugs only on the local box or a copy. QA, DEV and client servers get the
  doctor and read-only config checks only.
- If two instances cannot run side by side (one port, one database), say so in the generated
  skill and refuse to drive an instance it did not start.
