# PROJ-123 -- live status

## Decisions taken without the owner

| id | When | Decision | How to reverse it | Decided by |
|---|---|---|---|---|
| D1 | Fri 10-16 21:05 | AGENT-DEFERRED: one customer with no invoices gets no statement | send it by hand | critic 2-1 |

## Tasks

<!-- tasks:begin - scripts/build_table.py rewrites this section every tick; do not edit it -->
| # | Stage | Task | What it does | Status | Started | Finished | Tokens used | Token estimate | Notes |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Build | T1 | Fix invoice rounding | Done | Fri 10-16 19:40 | Fri 10-16 19:52 | 88,000 | don't know |  |
| 2 | Build | T2 | Monthly statement | Done (19/20) | Fri 10-16 19:53 | Fri 10-16 21:10 | 210,000 | don't know | fix rounds: 1 |
| 3 | Build | T2:fix | fix round | Done | Fri 10-16 20:30 | Fri 10-16 21:10 | 90,000 | don't know | ADDED |
<!-- tasks:end -->
