VERDICT: FIX (1 fix now, 0 flagged, 1 later, 2 never)
| # | Finding | Seats | Real | In scope | When | Why |
|---|---|---|---|---|---|---|
| 1 | The parser drops the last CSV row | 1, 5 | yes | yes | fix now | EXTRACTED parse.py line 12 stops at len - 1. A guard closes it. |
| 2 | Add a retry wrapper around the import | 3 | yes | no | later | A new capability the main goal does not ask for. |
| 3 | The date column may be null | 4 | no | yes | never | Line 40 already handles null. False alarm. |
| 4 | [floor] An API key is in config.sample.json | 4 | yes | no | never | EXTRACTED config.sample.json line 3. Outside this subtask, so the user decides. |
