# Eval plan -- personal-drift-check

## What this skill is for

Report whether a session has stopped gathering evidence (harness drift), as a
number comparable to the measured baseline in `docs/harness-drift/`.

## Why the eval looks like this

The skill's only value is that its numbers mean something. A drift meter that
silently changes its own definition is worse than no meter -- it would report
"HEALTHY" after a refactor and nobody could tell. So the eval is built around
one invariant plus a set of exclusion traps.

**The load-bearing test is E03, the calibration invariant.** If `drift-check.ps1`
stops reproducing BASELINE 144/375 = 38.4% and RECENT 78/733 = 10.6%, the metric
definition has moved and every historical comparison is void. That test is the
reason this eval exists; the rest are guards on the parser.

E03 is machine-dependent (it needs the reference transcripts, located via the
`DRIFT_CHECK_REF_DIR` env var). It reports SKIP rather than FAIL when they are
absent, because their absence is not a defect in the script. This is a deliberate
trade: on the author's box the invariant is enforced.

## Ground truth

`fixtures/sample-transcript.jsonl` -- 14 lines, hand-computed:

| Quantity | Value | Why |
|---|---|---|
| work-tool denominator | 9 | Read x2, Grep, Glob, Bash x3, Edit, Write |
| evidence share | 44.4% | 4/9 |
| probe share | 55.6% | 5/9 -- one Bash is a read-only `grep` |
| Agent calls | 1 | counted, but NOT in the denominator |
| verdict | HEALTHY | 44.4% is above the 30% band |

Deliberately excluded by the fixture: a `user`-type line, a `ToolSearch` meta
call, a subagent (`isSidechain:true`) Read, and one malformed JSON line.

## Failure curriculum

| ID | Failure mode | Test |
|---|---|---|
| E01 | Share math wrong | `evidence_share_math` |
| E02 | Verdict band mis-thresholded | `verdict_band` |
| E03 | **Metric definition drifts from the published baseline** | `CALIBRATION` |
| F01 | Meta/UI tools inflate the denominator, diluting the signal | `denominator_excludes_meta_agent_sidechain` |
| F02 | Subagent turns counted, making a drifted session read healthy | same |
| F03 | Malformed line aborts the parse | `survives_malformed_json` |
| F04 | `Agent` in the denominator -- delegating would look like drift | `agent_counted_but_not_in_denominator` |
| F05 | Read-only shell leaks into the calibrated evidence numerator | `readonly_shell_counts_as_probe_not_evidence` |
| F06 | Mutating shell miscounted as a probe, hiding real drift | `mutating_shell_is_not_a_probe` |
| F07 | Crash on a real transcript | `survives_malformed_json` |

## Known gaps

- **The decay/cliff table is untested.** The fixture is too short (9 calls) to
  exercise decile bucketing meaningfully. A longer synthetic fixture with a
  planted cliff would close this. The cliff output is currently advisory only.
- **No test that the verdict is *useful*,** only that it is arithmetically
  correct. Whether 30/20/10 are the right band edges is an open empirical
  question (F-G11 in the facts doc), not something an eval can settle.
- **`-Cohort` ordering is not asserted.** Decay across a multi-session cohort is
  suppressed by design, but nothing tests that suppression.
