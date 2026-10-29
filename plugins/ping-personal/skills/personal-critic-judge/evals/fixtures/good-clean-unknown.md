VERDICT: CLEAN (0 fix now, 1 flagged, 1 later, 0 never)
| # | Finding | Seats | Real | In scope | When | Why |
|---|---|---|---|---|---|---|
| 2 | Add a retry wrapper around the import | 3 | yes | no | later | A new capability the main goal does not ask for. |
| 2 | [floor] The export may stop at 4,000 rows | 5 | no | yes | later - flagged for the owner | UNKNOWN: the fetch call is in a DLL I cannot read. Sizing probe: count rows per day in the source table. |
