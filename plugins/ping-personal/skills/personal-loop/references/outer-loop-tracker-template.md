# outer-loop-tracker template

The outer loop's working memory: read on heartbeat to reconstruct state +
decide the next action; written every tick via compare-and-swap against the
beacon. The beacon (personal-goal) is the SINGLE SOURCE OF TRUTH for child
completion + budget; the cells below are a read-through cache, overwritten from
the beacon at heartbeat, NEVER written back. Emitted for EVERY run, including a
depth-0 single-goal run (it degenerates to header + one-row tree + turn tape).

    # outer-loop-tracker: <slug>
    Root goal: <one line>     Root STOP: <reason token + gloss>
    Depth: <parent-injected; advisory copy>   Started: <ts>   Last heartbeat: <ts>
    gate_promoted_at: <none | T<k>: from=fuzzy to=accept_cmd check="<cmd>">

    ## Tree
    | id | child_id | what-to-do | target | own-STOP | status | lease | iters |

    ## Budget ledger     # ESTIMATE outside Workflow; NOT the safety boundary
    declared=<N>  estimated-spent=<M>  remaining=<N-M>  per-child=[...]

    ## Handled completions   # idempotency: child_ids already processed
    [<child_id>, ...]

    ## Turn tape   (annotated, append-only)
    - T<k>: PROMPT <...> | RETURNED <...> | FENCE <none|reason> | gate <token> | lens <line>

    ## Next action   (STRUCTURED, regenerated from state -- NOT free-text)
    { kind: <pull|dispatch|fence-wait|halt>, target: <...>,
      derived_from: <tree+gate state>, human_observable: <advisory text> }

Guard: the `## Next action` is regenerated from the tree+beacon state; the loop
does NOT execute free-text it wrote earlier. `human_observable` is advisory
narration only. Any durable action derived from it passes `fence.py` +
`flag_excluded` before execution. `validate_beacon_cell` guards ONLY the `##
Tree` path cells (path-traversal / shell-metachars) -- it cannot and does not
guard free-text.
