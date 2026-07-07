# Case Study -- "Position Rollover" Error, `DefaultRolloverDeadline` Unseeded

> Fully fictional, invented for this portfolio demo. No real app, client,
> table, or error code -- it exists to show the Preliminary Diagnostic SELECT
> mode end to end.

## The report

> A support engineer relayed: a client deployed a fresh install of "Northwind
> Trading", opened the Position Rollover page, and got:
>
> *System Error -- Procedure 'pRolloverPositions' expects parameter
> '@deadline', which was not supplied.*

## What `personal-cs-client-question` did

1. Ran `/graphify query "position rollover"` -> located `RolloverPositions`
   (page) and `pRolloverPositions` (stored procedure) with high confidence.
2. Read the page source. Found the fallback chain:
   - Read `deadline` from the URL query string -> empty
   - Fallback: `GetAppSetting("DefaultRolloverDeadline")` -> empty (no row in
     the settings table)
   - Result: an empty string gets passed to the stored procedure, which has
     no default for that parameter -> the error.
3. This is diagnostic ("why is X empty?"), the page/setting was located with
   high confidence, and the SELECT can be composed from what was just read
   -- all three Preliminary Diagnostic SELECT trigger conditions are met.

## Rendered answer

```
1. Main Menu -> Settings -> Rollover Defaults -> set "Default Rollover
   Deadline" to a value like "17:00".

SOURCE: app/RolloverPositions.page:42-45

PRELIMINARY DIAGNOSTIC SELECT (read-only, safe to share with the client):

    SELECT KeyName, Value, Description
    FROM AppSettings
    WHERE KeyName = 'DefaultRolloverDeadline';

EXPECTED: a non-empty Value (e.g. '17:00' -- INFERRED from the fallback
   chain at app/RolloverPositions.page:42-45). NULL / empty / missing row
   -> confirms this root cause.
READ-ONLY: SELECT only. Does not change any data. A DBA can run it safely.
IF VALUE LOOKS WRONG: escalate via personal-cs-escalate-to-dev.
```

## Why this is the shape to imitate

- The nav step tells the client what to click, not how the bug works.
- The SELECT is composed from lines actually read in step 2 -- no invented
  column names.
- `EXPECTED:` is explicitly labeled INFERRED with its source, per the
  Honesty Protocol -- it's a hypothesis grounded in code, not a guess.
- The metric line for this run would record `graph_hit: true`,
  `diagnostic_select_suggested: true`, `escalated: false`.
